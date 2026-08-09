"""
HARNESS-003A §6 — the epistemic operationalizer: claims in, what could bear on them out.

    claims + relations
      -> observables, each requesting a capability CLASS and never an instrument
      -> alternatives where operationalization is genuinely plural
      -> decision candidates ONLY where choosing changes the investigation
      -> semantic remainder: what stays interpretive whatever succeeds

## It receives the graph, not the images

Same rule as the architect, one step further along. This pass never sees a picture, so it cannot
notice something and propose an observable for it — every observable serves a claim that already
existed, which is what keeps "what could we look at" tied to "what did somebody say".

## A measurement never exhausts an interpretation

The rule HARNESS-001A's semantic remainder exists for, applied where it is most tempting to break.
An observable serving an interpretation must state what remains interpretive even if it succeeds;
one that cannot say is refused rather than accepted with an empty field, because an interpretation
with a satisfied observable and no residue reads downstream as a settled question.

## A fork is raised only where it changes something

`uncertainty` is not a reason to interrupt a person. A decision candidate needs at least two real
branches and a stated downstream consequence, and a candidate whose consequences point at nothing
is dropped with the reason recorded — the reference that failed to resolve is usually an observable
that was itself refused, which is the fact worth surfacing.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from backend.schemas.inquiry import DemandKind
from backend.schemas.semantic_compilation import (CapabilityClass, ClaimEdge, ClaimKind, ClaimNode,
                                                  CompilerRefusal, CompilerRefusalKind,
                                                  DecisionCandidate, DecisionKind, DissolutionPass,
                                                  GroundForm, ImageScope, NON_MEASURING_CLASSES,
                                                  ObservableSpec, OperationalAlternative,
                                                  PassOutcome, PassReceipt, SemanticRemainderItem)

from . import contracts, ids
from .base import refusal
from .compiler import _alternatives, _enum_list
from .passes import ModelPass, PassBudget, PassResult, merge_receipts

ROLE = "epistemic_operationalizer"
PRODUCER = "semantic_compilation/operationalizer-v1"

#: 4096, for the reason the dissector's comment gives at length: a provider counts
#: `max_completion_tokens` against the per-minute allowance whether or not the model uses them, and
#: this account's is 8000. A budget nearer that ceiling is a request that cannot be sent.
DEFAULT_BUDGET = PassBudget(max_completion_tokens=4096, batch_size=0)

MAX_OBSERVABLES_PER_CLAIM = 4

SYSTEM_PROMPT = (
    "You are an epistemic operationalizer inside a visual close-reading tool. You are given a graph "
    "of CLAIMS and the relations between them. You do not see the images. You output JSON and "
    "nothing else.\n\n"
    "For each claim that could be investigated at all, say what would have to become OBSERVABLE.\n\n"
    "1. REQUEST A CAPABILITY CLASS, NEVER A TOOL. You are naming the KIND of instrument a claim "
    "would need. Choosing an implementation is somebody else's job, and a class nothing can serve "
    "today is a visible gap rather than a planning error.\n"
    "2. OFFER ALTERNATIVES where more than one honest operationalization exists — measuring a thing "
    "as one extent and measuring its parts and counting them are different investigations with "
    "different costs.\n"
    "3. RAISE A DECISION ONLY WHERE CHOOSING MATTERS. Two alternatives that lead to the same work "
    "are not a fork. 'The system is uncertain' is not a reason to interrupt somebody. Say what "
    "changes downstream in `why_now`.\n"
    "4. SAY WHAT STAYS INTERPRETIVE. For every observable serving an interpretation, state in "
    "`remains_interpretive` what would still be a reading even if the measurement succeeded. A "
    "measurement contributes to an interpretation; it does not exhaust it.\n"
    "5. SEMANTIC REMAINDER IS FIRST-CLASS. What in this graph will no instrument reach? An "
    "interpretive graph with an empty remainder is a wrong answer.\n"
    "6. LEAVE CLAIMS ALONE THAT CANNOT BE INVESTIGATED. Not every claim gets an observable, and "
    "inventing one to make the graph look complete is worse than saying nothing.\n\n"
    "Hard rules:\n"
    "- Never output a mask, box, point, polygon, coordinate, pixel count, region id or confidence. "
    "An observable REQUESTS a measurement; it may not carry one.\n"
    "- A claim whose warrant is outside the picture may only request `external_source`.\n"
    "- Never name a model, a tool, an actuator or an organ."
)


def claim_digest(claims: Sequence[ClaimNode], edges: Sequence[ClaimEdge]) -> Dict[str, Any]:
    return {
        "claims": [{"claim_id": c.claim_id, "text": c.text, "kind": c.claim_kind.value,
                    "subject": c.subject, "predicate": c.predicate, "object": c.object_,
                    "image_scope": c.image_scope.value, "demand": c.epistemic_demand.value}
                   for c in claims],
        "relations": [{"kind": e.kind.value, "from": e.from_claim, "to": e.to_claim, "why": e.why}
                      for e in edges],
    }


def build_prompt(claims: Sequence[ClaimNode], edges: Sequence[ClaimEdge]) -> str:
    contract = contracts.graph_contract()
    vocabulary = {
        "capability_classes": contract["capability_classes"],
        "ground_forms": contract["ground_forms"],
        "image_scopes": list(contracts.closed_set("image_scopes")),
        "decision_kinds": list(contracts.closed_set("decision_kinds")),
    }
    return (
        f"THE GRAPH — this is everything you may operationalize:\n"
        f"{json.dumps(claim_digest(claims, edges), indent=2, ensure_ascii=False)}\n\n"
        f"THE VOCABULARY — use only these:\n{json.dumps(vocabulary, indent=2)}\n\n"
        f"Return JSON of exactly this shape:\n"
        f'{{"observables": [{{"ref": "o1", "claim": "<a claim_id from above>", '
        f'"kind": "<what to observe>", "targets": ["<what to look at>"], '
        f'"image_scope": "<image scope>", "capability_classes": ["<capability class>"], '
        f'"ground_forms": ["<ground form>"], "success_when": "", "ambiguous_when": "", '
        f'"refused_when": "", "remains_interpretive": "", '
        f'"alternatives": [{{"label": "", "consequence": "", "capability_classes": [], '
        f'"ground_forms": [], "recommended": false}}]}}], '
        f'"decisions": [{{"kind": "<decision kind>", "question": "", "why_now": "", '
        f'"affects": ["<a claim_id or o1>"], "blocking": false, '
        f'"options": [{{"label": "", "consequence": "", "recommended": false}}]}}], '
        f'"semantic_remainder": [{{"term": "", "why": "", '
        f'"contributing_capability_classes": [], "claims": ["<a claim_id>"]}}]}}\n'
        f"Return empty lists rather than inventing content."
    )


class _Ops:
    """The minimum `_alternatives` needs, so HARNESS-002A's alternative parser is reused verbatim
    rather than copied. A second copy would be a second place for the de-duplication rule to drift."""

    def __init__(self, inquiry_id: str):
        self.inquiry_id = inquiry_id
        self.refusals: List[CompilerRefusal] = []
        self.notes: List[str] = []

    def refuse(self, kind: CompilerRefusalKind, what: str, why: str,
               detail: Sequence[str] = ()) -> None:
        self.refusals.append(refusal(self.inquiry_id, kind, what, why, detail))


class EpistemicOperationalizer(ModelPass):
    """One call over the whole graph. What is observable about a claim depends on the other
    claims — a batched operationalizer would propose the same observable twice from two halves."""

    role = ROLE
    pass_name = DissolutionPass.EPISTEMIC_OPERATIONALIZER
    system_prompt = SYSTEM_PROMPT
    budget = DEFAULT_BUDGET

    def operationalize(self, claims: Sequence[ClaimNode], edges: Sequence[ClaimEdge], *,
                       inquiry_id: str, attempt: int = 1
                       ) -> Tuple[List[ObservableSpec], List[DecisionCandidate],
                                  List[SemanticRemainderItem], List[CompilerRefusal], List[str],
                                  PassReceipt]:
        ops = _Ops(inquiry_id)
        if not claims:
            receipt = merge_receipts(self.pass_name, [], inquiry_id=inquiry_id,
                                     outcome=PassOutcome.EMPTY, attempt=attempt,
                                     detail="no claim reached the operationalizer")
            return [], [], [], [], ["there was no claim to operationalize"], receipt

        result = self.invoke(build_prompt(claims, edges), inquiry_id=inquiry_id, attempt=attempt,
                             inputs=len(claims))
        ops.refusals.extend(result.refusals)
        if result.payload is None:
            receipt = merge_receipts(self.pass_name, [result.receipt], inquiry_id=inquiry_id,
                                     outcome=result.receipt.outcome, attempt=attempt,
                                     detail=result.receipt.detail)
            return [], [], [], ops.refusals, ops.notes, receipt

        by_id = {c.claim_id: c for c in claims}
        observables, by_ref = self._observables(result.payload, by_id, ops)
        decisions = self._decisions(result.payload, by_id, by_ref, ops)
        remainder = self._remainder(result.payload, by_id, observables, claims, ops)

        outcome, detail = self._outcome(claims, observables, remainder, result, ops)
        receipt = merge_receipts(self.pass_name, [result.receipt], inquiry_id=inquiry_id,
                                 outcome=outcome, attempt=attempt, outputs=len(observables),
                                 detail=detail)
        return observables, decisions, remainder, ops.refusals, ops.notes, receipt

    # ── observables ──

    def _observables(self, payload: Mapping[str, Any], by_id: Mapping[str, ClaimNode],
                     ops: _Ops) -> Tuple[List[ObservableSpec], Dict[str, str]]:
        out: List[ObservableSpec] = []
        by_ref: Dict[str, str] = {}
        per_claim: Dict[str, int] = {}
        rows = payload.get("observables")
        for index, row in enumerate(rows if isinstance(rows, list) else []):
            if not isinstance(row, Mapping):
                continue
            where = f"observable {index}"
            found = contracts.geometry_keys_in(row)
            if found:
                ops.refuse(CompilerRefusalKind.GEOMETRY_IN_A_READING, ", ".join(found),
                           "an observable REQUESTS a measurement; it may not carry one. Dropped.",
                           detail=[where])
                continue
            claim_id = str(row.get("claim") or row.get("claim_ref") or "").strip()
            if claim_id not in by_id:
                ops.refuse(CompilerRefusalKind.DANGLING_REFERENCE, claim_id or "(empty)",
                           "an observable for a claim that is not in this graph.", detail=[where])
                continue
            kind_text = str(row.get("kind") or row.get("observable_kind") or "").strip()
            if not kind_text:
                continue
            classes = _enum_list(row.get("capability_classes"), CapabilityClass,
                                 "capability_classes",
                                 CompilerRefusalKind.UNKNOWN_CAPABILITY_CLASS, where,
                                 ops.inquiry_id, ops.refusals)
            if not classes:
                ops.refuse(CompilerRefusalKind.UNKNOWN_CAPABILITY_CLASS, kind_text[:120],
                           "the observable requested no capability class this system declares, so "
                           "there is nothing to broker and nothing to report as a gap. Dropped.",
                           detail=[where])
                continue
            claim = by_id[claim_id]
            if claim.claim_kind is ClaimKind.HISTORICAL_OR_SOURCED and \
                    CapabilityClass.EXTERNAL_SOURCE not in classes:
                ops.refuse(CompilerRefusalKind.SOURCED_CLAIM_ASKED_OF_AN_ORGAN,
                           ", ".join(c.value for c in classes),
                           "a historical claim routed to an image capability. Its warrant is "
                           "outside the picture. Dropped rather than rewritten to "
                           "`external_source`, which would be the pass inventing a request.",
                           detail=[where, claim.text[:120]])
                continue

            residue = str(row.get("remains_interpretive") or "").strip()
            if claim.claim_kind is ClaimKind.INTERPRETATION and not residue:
                # THE RULE MOST TEMPTING TO BREAK. An interpretation with a satisfied observable and
                # no stated residue reads downstream as a settled question.
                ops.refuse(CompilerRefusalKind.REMAINDER_CLAIMED_MEASURABLE, claim.text[:120],
                           "an observable serving an interpretation that does not say what stays "
                           "interpretive if it succeeds. A measurement contributes to an "
                           "interpretation; it does not exhaust it. Dropped rather than accepted "
                           "with an empty field.", detail=[where])
                continue
            if per_claim.get(claim_id, 0) >= MAX_OBSERVABLES_PER_CLAIM:
                ops.notes.append(f"{where}: more than {MAX_OBSERVABLES_PER_CLAIM} observables were "
                                 f"requested for one claim; the extras were not kept")
                continue

            targets = [str(t).strip() for t in row.get("targets") or () if str(t).strip()]
            observable_id = ids.observable_id(ops.inquiry_id, claim_id, kind_text, targets)
            if any(o.observable_id == observable_id for o in out):
                continue
            grounds = _enum_list(row.get("ground_forms"), GroundForm, "ground_forms",
                                 CompilerRefusalKind.UNKNOWN_GROUND_FORM, where,
                                 ops.inquiry_id, ops.refusals)
            raw_scope = str(row.get("image_scope") or "").strip()
            out.append(ObservableSpec(
                observable_id=observable_id, claim_id=claim_id, observable_kind=kind_text,
                targets=targets,
                image_scope=(ImageScope(raw_scope) if raw_scope in {s.value for s in ImageScope}
                             else claim.image_scope),
                capability_classes=classes, ground_forms=grounds,
                success_when=str(row.get("success_when") or "").strip(),
                ambiguous_when=str(row.get("ambiguous_when") or "").strip(),
                refused_when=str(row.get("refused_when") or "").strip(),
                remains_interpretive=residue,
                alternatives=_alternatives(ops, [r for r in (row.get("alternatives") or [])
                                                 if isinstance(r, Mapping)], observable_id, where),
                note=str(row.get("note") or "").strip()))
            per_claim[claim_id] = per_claim.get(claim_id, 0) + 1
            by_ref[str(row.get("ref") or f"#{index}")] = observable_id
        return out, by_ref

    # ── decisions ──

    def _decisions(self, payload: Mapping[str, Any], by_id: Mapping[str, ClaimNode],
                   by_ref: Mapping[str, str], ops: _Ops) -> List[DecisionCandidate]:
        out: List[DecisionCandidate] = []
        rows = payload.get("decisions")
        for index, row in enumerate(rows if isinstance(rows, list) else []):
            if not isinstance(row, Mapping):
                continue
            where = f"decision {index}"
            raw = str(row.get("kind") or "").strip()
            if raw not in {k.value for k in DecisionKind}:
                ops.refuse(CompilerRefusalKind.UNKNOWN_DECISION_KIND, raw or "(empty)",
                           f"not one of {[k.value for k in DecisionKind]}; dropped rather than "
                           f"filed under the nearest kind.", detail=[where])
                continue
            kind = DecisionKind(raw)
            question = str(row.get("question") or "").strip()
            why_now = str(row.get("why_now") or "").strip()
            if not question or not why_now:
                ops.notes.append(f"{where}: a fork with no question or no stated consequence was "
                                 f"dropped. 'The system is uncertain' is not a reason to interrupt "
                                 f"somebody.")
                continue
            decision_id = ids.decision_id(ops.inquiry_id, kind, question)
            options = _alternatives(ops, [r for r in (row.get("options") or [])
                                          if isinstance(r, Mapping)], decision_id, where)
            if len(options) < 2 and kind is not DecisionKind.CONFIRM_AUTHOR_EXCLUSIVE_ACT:
                ops.notes.append(f"{where}: a fork with {len(options)} branch(es) was dropped. "
                                 f"Asking about a choice that has one answer trains a person to "
                                 f"click through.")
                continue
            named = [str(r).strip() for r in row.get("affects") or () if str(r).strip()]
            affected: List[str] = []
            for key in named:
                resolved = key if key in by_id else by_ref.get(key)
                if not resolved:
                    ops.refuse(CompilerRefusalKind.DANGLING_REFERENCE, key,
                               "a fork named something it would change that is not in the graph — "
                               "usually an observable that was itself refused.", detail=[where])
                elif resolved not in affected:
                    affected.append(resolved)
            if named and not affected:
                ops.notes.append(f"{where}: every object this fork said it would change was "
                                 f"refused, so the fork was dropped. A question whose consequences "
                                 f"point at nothing is one nobody can act on.")
                continue
            out.append(DecisionCandidate(
                decision_id=decision_id, kind=kind, question=question, why_now=why_now,
                affected_refs=affected, options=options,
                allow_free_text=bool(row.get("allow_free_text", True)),
                blocking=bool(row.get("blocking"))))
        return out

    # ── remainder ──

    def _remainder(self, payload: Mapping[str, Any], by_id: Mapping[str, ClaimNode],
                   observables: Sequence[ObservableSpec], claims: Sequence[ClaimNode],
                   ops: _Ops) -> List[SemanticRemainderItem]:
        measurable_subjects = {c.subject.strip().lower() for c in claims
                               if c.epistemic_demand is DemandKind.MEASURABLE and c.subject.strip()}
        measurable_targets = {t.strip().lower() for o in observables for t in o.targets
                              if t.strip()
                              and not set(o.capability_classes) <= NON_MEASURING_CLASSES}
        out: List[SemanticRemainderItem] = []
        seen: Set[str] = set()
        rows = payload.get("semantic_remainder")
        for index, row in enumerate(rows if isinstance(rows, list) else []):
            if not isinstance(row, Mapping):
                continue
            where = f"semantic remainder {index}"
            term = str(row.get("term") or "").strip()
            if not term or term.lower() in seen:
                continue
            if term.lower() in measurable_subjects or term.lower() in measurable_targets:
                ops.refuse(CompilerRefusalKind.REMAINDER_CLAIMED_MEASURABLE, term,
                           "called both a semantic remainder and something a measurement would "
                           "reach. A remainder is what measurement does not reach; the remainder "
                           "entry was dropped and the measurable request stands.", detail=[where])
                continue
            seen.add(term.lower())
            classes = _enum_list(row.get("contributing_capability_classes"), CapabilityClass,
                                 "capability_classes", CompilerRefusalKind.UNKNOWN_CAPABILITY_CLASS,
                                 where, ops.inquiry_id, ops.refusals)
            refs: List[str] = []
            for key in row.get("claims") or ():
                key = str(key).strip()
                if key in by_id and key not in refs:
                    refs.append(key)
                elif key and key not in by_id:
                    ops.refuse(CompilerRefusalKind.DANGLING_REFERENCE, key,
                               "a remainder item pointing at a claim that is not in this graph.",
                               detail=[where])
            out.append(SemanticRemainderItem(
                term=term, why=str(row.get("why") or "").strip() or "the pass gave no reason",
                contributing_capability_classes=classes, claim_refs=refs))
        return out

    # ── the outcome ──

    def _outcome(self, claims: Sequence[ClaimNode], observables: Sequence[ObservableSpec],
                 remainder: Sequence[SemanticRemainderItem], result: PassResult,
                 ops: _Ops) -> Tuple[PassOutcome, str]:
        """`thin` is judged against what the CLAIMS implied, never padded to avoid.

        A graph full of measurable demands and no observable is thin. A wholly interpretive graph
        with no observable is complete — and telling those apart is the reason this looks at the
        demands rather than counting.
        """
        if result.receipt.truncated:
            return (PassOutcome.TRUNCATED,
                    f"the operationalizer hit its completion budget after "
                    f"{len(observables)} observable(s)")
        investigable = [c for c in claims if c.epistemic_demand is DemandKind.MEASURABLE]
        interpretive = [c for c in claims if c.epistemic_demand in
                        (DemandKind.INTERPRETIVE, DemandKind.IMAGINED)]
        if not observables and not remainder:
            return (PassOutcome.EMPTY,
                    "the operationalizer produced neither an observable nor a remainder item")
        if investigable and not observables:
            return (PassOutcome.THIN,
                    f"{len(investigable)} claim(s) ask to be measured and no observable was "
                    f"requested for any of them. Nothing was invented to fill the gap.")
        if interpretive and not remainder:
            return (PassOutcome.THIN,
                    f"{len(interpretive)} interpretive or imagined claim(s) and no semantic "
                    f"remainder. What measurement will not reach is the part of this pass that "
                    f"cannot be recovered downstream.")
        return (PassOutcome.COMPLETED,
                f"{len(observables)} observable(s) and {len(remainder)} remainder item(s) over "
                f"{len(claims)} claim(s)")


class FrozenEpistemicOperationalizer(EpistemicOperationalizer):
    """The same parse and the same laws, over a frozen payload."""

    def __init__(self, payload: Any, *, model: Optional[str] = None):
        super().__init__(client=None, model=model)
        self._frozen = payload

    def is_available(self) -> bool:
        return True

    def invoke(self, user_prompt: str, *, inquiry_id: str, attempt: int = 1,
               inputs: int = 0) -> PassResult:
        from .passes import FrozenPass
        through = FrozenPass([self._frozen], model=self._model)
        through.role = self.role
        through.pass_name = self.pass_name
        self.calls += 1
        return through.invoke(user_prompt, inquiry_id=inquiry_id, attempt=attempt, inputs=inputs)


__all__ = ["ROLE", "PRODUCER", "DEFAULT_BUDGET", "MAX_OBSERVABLES_PER_CLAIM", "SYSTEM_PROMPT",
           "build_prompt", "claim_digest", "EpistemicOperationalizer",
           "FrozenEpistemicOperationalizer"]
