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

## HARNESS-003E: batched, with the neighbours in view

This pass used to make one call over the whole graph, and the comment above `EpistemicOperationalizer`
gave the reason: what is observable about a claim depends on the other claims, so a batched
operationalizer would propose the same observable twice from two halves. That reason is right and
the arrangement it justified is unsendable — the graph does not fit under the account's per-minute
allowance any more than the atoms did.

Both are answered by the same distinction. Every claim is PRIMARY in exactly one batch and the model
may emit observables only for primary ids; its neighbours arrive as CONTEXT, with the edges between
them, so the dependence the old comment names is preserved without the same claim being
operationalized from two neighbourhoods. `MAX_OBSERVABLES_PER_CLAIM` is counted across the whole
pass rather than per batch, for the same reason.

Batches follow the CLAIM GRAPH: claims joined by an edge go in one batch where they fit, because
claims that relate are the ones whose forks are only visible together. What does not fit is
reconciled afterwards, over compact cards, and the pairs that never met are named.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from backend.schemas.inquiry import DemandKind
from backend.schemas.semantic_compilation import (BatchPlanRecord, CapabilityClass, ClaimEdge,
                                                  ClaimKind, ClaimNode, ComparisonPair,
                                                  CompilerRefusal, CompilerRefusalKind,
                                                  DecisionCandidate, DecisionKind, DissolutionPass,
                                                  GroundForm, ImageScope, ItemDisposition,
                                                  ItemDispositionKind, NON_MEASURING_CLASSES,
                                                  ObservableSpec, OperationalAlternative,
                                                  PassOutcome, PassReceipt, ReconciliationRound,
                                                  SemanticRemainderItem)

from . import contracts, ids, reconciliation, sizing
from .base import refusal
from .compiler import _alternatives, _enum_list
from .passes import ModelPass, PassBudget, PassResult, merge_receipts

ROLE = "epistemic_operationalizer"
PRODUCER = "semantic_compilation/operationalizer-v1"

#: 4096, for the reason the dissector's comment gives at length: a provider counts
#: `max_completion_tokens` against the per-minute allowance whether or not the model uses them, and
#: this account's is 8000. A budget nearer that ceiling is a request that cannot be sent.
DEFAULT_BUDGET = PassBudget(max_completion_tokens=4096, batch_size=0)

#: What one operationalization request reserves for its answer. HARNESS-003E, replacing the flat
#: 4096 this pass spent on every call — see `architect.ARCHITECT_COMPLETION` for why the reasoning
#: headroom is a separate term from the per-item share.
#:
#: The per-item share is larger than the architect's because an observable is a bigger object than a
#: claim: it carries success, ambiguity and refusal conditions, a residue sentence, capability
#: classes and its alternatives.
OPERATIONALIZE_COMPLETION = sizing.CompletionPolicy(
    reserved_tokens=1536, per_item_tokens=160, minimum_tokens=1024, maximum_tokens=4096)

#: What the final cross-batch round reserves. It emits forks and remainder over cards it was given
#: rather than observables built from scratch, so its per-item share is small.
FORK_COMPLETION = sizing.CompletionPolicy(
    reserved_tokens=1536, per_item_tokens=24, minimum_tokens=1024, maximum_tokens=4096)

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


#: See `architect._COMPACT`: the whitespace is a fifth of every request and nobody reads it.
_COMPACT = dict(separators=(",", ":"), ensure_ascii=False)


def claim_digest(claims: Sequence[ClaimNode], edges: Sequence[ClaimEdge],
                 context: Sequence[ClaimNode] = ()) -> Dict[str, Any]:
    """What one request sees: the claims it answers for, its neighbours, and the edges between.

    `context` is a SEPARATE LIST rather than a flag on the claims, because the difference is what
    the model is allowed to do with them and a flag inside a row is the kind of thing a model reads
    past. An observable for a context claim is refused by the parser either way — but a prompt that
    made the distinction structurally is one the model can follow.
    """
    def row(claim: ClaimNode) -> Dict[str, Any]:
        return {"claim_id": claim.claim_id, "text": claim.text, "kind": claim.claim_kind.value,
                "subject": claim.subject, "predicate": claim.predicate, "object": claim.object_,
                "image_scope": claim.image_scope.value, "demand": claim.epistemic_demand.value}

    digest: Dict[str, Any] = {
        "claims": [row(c) for c in claims],
        "relations": [{"kind": e.kind.value, "from": e.from_claim, "to": e.to_claim, "why": e.why}
                      for e in edges],
    }
    if context:
        digest["context_claims"] = [row(c) for c in context]
    return digest


def build_prompt(claims: Sequence[ClaimNode], edges: Sequence[ClaimEdge],
                 context: Sequence[ClaimNode] = ()) -> str:
    contract = contracts.graph_contract()
    vocabulary = {
        "capability_classes": contract["capability_classes"],
        "ground_forms": contract["ground_forms"],
        "image_scopes": list(contracts.closed_set("image_scopes")),
        "decision_kinds": list(contracts.closed_set("decision_kinds")),
    }
    neighbours = (
        f"\nCONTEXT ONLY — these claims are here so you can see what the ones above stand next to. "
        f"You may NOT propose an observable for any of them; another request answers for those. A "
        f"fork or a remainder item may name them.\n" if context else "\n")
    return (
        f"THE CLAIMS YOU ANSWER FOR — an observable may name only these:\n"
        f"{json.dumps(claim_digest(claims, edges, context), **_COMPACT)}\n"
        f"{neighbours}\n"
        f"THE VOCABULARY — use only these:\n{json.dumps(vocabulary, **_COMPACT)}\n\n"
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


def fixed_prompt_text() -> str:
    """Everything charged on every operationalization request, whatever claims it carries."""
    return SYSTEM_PROMPT + build_prompt([], [])


FORK_SYSTEM_PROMPT = (
    "You are an epistemic operationalizer performing a FINAL CROSS-BATCH pass inside a visual "
    "close-reading tool. The claims below were operationalized in several separate requests, each "
    "of which saw only part of the graph. You are given compact cards for claims from two or more "
    "of those groups. You output JSON and nothing else.\n\n"
    "Your ONLY job is what the separate requests could not see, because it lies BETWEEN them.\n\n"
    "1. A FORK THAT SPANS GROUPS. Raise a decision only where choosing changes the investigation "
    "of claims in MORE THAN ONE group, and say what changes downstream in `why_now`. Two "
    "alternatives leading to the same work are not a fork, and 'the system is uncertain' is not a "
    "reason to interrupt somebody.\n"
    "2. REMAINDER THAT SPANS GROUPS. What will no instrument reach, across the graph as a whole "
    "rather than within any one group? Name the claims it bears on.\n\n"
    "Hard rules:\n"
    "- You may NOT propose an observable. Every claim has already been answered for.\n"
    "- Never invent a claim id. Use only the ids on the cards.\n"
    "- Never add content that is in no card. You have not seen the pictures or the source.\n"
    "- Never output a mask, box, point, polygon, coordinate, pixel count, region id or confidence.\n"
    "- Return empty lists rather than inventing content. Finding no fork between two groups is a "
    "legitimate answer."
)


def fork_prompt(cards: Sequence[Mapping[str, Any]]) -> str:
    vocabulary = {"decision_kinds": list(contracts.closed_set("decision_kinds")),
                  "capability_classes": contracts.graph_contract()["capability_classes"]}
    groups = sorted({str(c.get("group") or "") for c in cards})
    return (
        f"THE CLAIM CARDS — {len(cards)} claim(s) from {len(groups)} group(s). Every id you may "
        f"name is here:\n{json.dumps(list(cards), **_COMPACT)}\n\n"
        f"THE GROUPS in this round: {json.dumps(groups)}\n\n"
        f"THE VOCABULARY — use only these:\n{json.dumps(vocabulary, **_COMPACT)}\n\n"
        f"Return JSON of exactly this shape:\n"
        f'{{"decisions": [{{"kind": "<decision kind>", "question": "", "why_now": "", '
        f'"affects": ["<a claim_id>"], "blocking": false, '
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
    """Every claim primary in exactly one batch, with its neighbours in view. HARNESS-003E.

    What is observable about a claim depends on the other claims — which is why this pass used to
    make one call over the whole graph, and why the answer is not independent slices. The neighbours
    travel as CONTEXT, and only primary ids may receive an observable, so the dependence survives
    without the same claim being operationalized from two neighbourhoods.
    """

    role = ROLE
    pass_name = DissolutionPass.EPISTEMIC_OPERATIONALIZER
    system_prompt = SYSTEM_PROMPT
    budget = DEFAULT_BUDGET

    # ── the partition ──

    def plan_batches(self, claims: Sequence[ClaimNode], edges: Sequence[ClaimEdge], *,
                     inquiry_id: str) -> sizing.BatchPlan:
        """Sized against the allowance, with the CLAIM GRAPH as the affinity.

        Claims joined by an edge are the ones whose forks are only visible together, so a seam
        between two connected claims is the expensive kind and a seam between two components costs
        least. The component is keyed on its smallest member's id rather than on a counter, so the
        same graph partitions the same way on a re-run.
        """
        component = _components(claims, edges)
        neighbours = _neighbours(edges)
        items = [sizing.SizedItem(
            ref=c.claim_id,
            text=json.dumps(claim_digest([c], [])["claims"][0], **_COMPACT),
            affinity=component.get(c.claim_id, c.claim_id)) for c in claims]

        def context_for(refs: Sequence[str]) -> List[str]:
            mine = set(refs)
            return sorted({n for r in refs for n in neighbours.get(r, ()) if n not in mine})

        return sizing.plan(items, inquiry_id=inquiry_id, pass_name=self.pass_name, unit="claim",
                           fixed_text=fixed_prompt_text(), completion=OPERATIONALIZE_COMPLETION,
                           context_refs_for=context_for)

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

        by_id = {c.claim_id: c for c in claims}
        plan = self.plan_batches(claims, edges, inquiry_id=inquiry_id)
        ops.notes.extend(plan.record.notes)
        receipts: List[PassReceipt] = []
        observables: List[ObservableSpec] = []
        decisions: List[DecisionCandidate] = []
        remainder: List[SemanticRemainderItem] = []
        by_ref: Dict[str, str] = {}
        #: SHARED ACROSS BATCHES, deliberately. `MAX_OBSERVABLES_PER_CLAIM` is a bound on how many
        #: ways one claim may be investigated, and counting it per batch would let a claim that is
        #: primary once and contextual twice collect three times the allowance.
        per_claim: Dict[str, int] = {}
        answered: Set[str] = set()

        for batch in plan.batches:
            primary = [by_id[r] for r in batch.assignment.primary_refs if r in by_id]
            context = [by_id[r] for r in batch.assignment.context_refs if r in by_id]
            incident = {c.claim_id for c in primary} | {c.claim_id for c in context}
            local_edges = [e for e in edges
                           if e.from_claim in incident and e.to_claim in incident]
            number, total = batch.assignment.index, batch.assignment.total

            if not batch.sendable:
                for claim in primary:
                    ops.refuse(CompilerRefusalKind.PASS_UNAVAILABLE, claim.claim_id,
                               f"this claim alone estimates larger than one whole request may "
                               f"carry, so no operationalization call could include it. Refused "
                               f"before transport. {batch.assignment.note}")
                self.observe(f"operationalizing batch {number} of {total}", index=number,
                             total=total, outcome="refused",
                             refs=list(batch.assignment.primary_refs),
                             detail="too large to send; refused before transport")
                continue

            self.observe(f"operationalizing batch {number} of {total}", index=number, total=total,
                         outcome="started", refs=list(batch.assignment.primary_refs),
                         detail=f"{len(primary)} claim(s), {len(context)} in context")
            result = self.invoke(
                build_prompt(primary, local_edges, context), inquiry_id=inquiry_id, attempt=attempt,
                inputs=len(primary),
                estimated_prompt_tokens=batch.assignment.estimated_prompt_tokens,
                completion_tokens=batch.assignment.requested_completion_tokens)
            receipts.append(result.receipt)
            ops.refusals.extend(result.refusals)
            answered.update(c.claim_id for c in primary)

            if result.payload is not None:
                found, refs = self._observables(
                    result.payload, by_id, ops, primary={c.claim_id for c in primary},
                    per_claim=per_claim, seen={o.observable_id for o in observables})
                observables.extend(found)
                by_ref.update(refs)
                decisions.extend(self._decisions(result.payload, by_id, by_ref, ops,
                                                 seen={d.decision_id for d in decisions}))
                remainder.extend(self._remainder(
                    result.payload, by_id, observables, claims, ops,
                    seen={r.term.lower() for r in remainder}))
            self.observe(f"operationalizing batch {number} of {total}", index=number, total=total,
                         outcome=result.receipt.outcome.value,
                         refs=list(batch.assignment.primary_refs),
                         detail=result.receipt.detail
                                or f"{len(observables)} observable(s) so far")

        rounds, pairs = self._forks(
            plan, by_id, observables, claims, decisions, remainder, by_ref, ops,
            inquiry_id=inquiry_id, attempt=attempt, receipts=receipts)

        record = self._close_plan(plan, claims=claims, observables=observables,
                                  remainder=remainder, answered=answered, rounds=rounds,
                                  pairs=pairs)
        outcome, detail = self._outcome(claims, observables, remainder, receipts, record, ops)
        receipt = merge_receipts(self.pass_name, receipts, inquiry_id=inquiry_id, outcome=outcome,
                                 attempt=attempt, outputs=len(observables), detail=detail,
                                 batch_plan=record)
        return observables, decisions, remainder, ops.refusals, ops.notes, receipt

    # ── the fork the separate batches could not see ──

    def _forks(self, plan: sizing.BatchPlan, by_id: Mapping[str, ClaimNode],
               observables: Sequence[ObservableSpec], claims: Sequence[ClaimNode],
               decisions: List[DecisionCandidate], remainder: List[SemanticRemainderItem],
               by_ref: Dict[str, str], ops: _Ops, *, inquiry_id: str, attempt: int,
               receipts: List[PassReceipt]
               ) -> Tuple[List[ReconciliationRound], List[ComparisonPair]]:
        """One compact pass over the whole graph's cards, for forks and remainder that span batches.

        NOT A SECOND READING. It may emit only decisions and remainder, both of which connect refs
        that already exist; an observable here would be a claim operationalized twice, which is the
        thing the primary/context split was built to make impossible.
        """
        groups = [b.batch_id for b in plan.batches if b.assignment.primary_refs and b.sendable]
        if len(groups) < 2:
            ops.notes.append(
                "one batch answered for every claim, so every fork was already visible in one "
                "request. The coverage matrix is empty because there is nothing across, not "
                "because nothing was compared.")
            return [], []

        cards_by_group = {b.batch_id: [reconciliation.claim_card(by_id[r], group=b.batch_id)
                                       for r in b.assignment.primary_refs if r in by_id]
                          for b in plan.batches if b.batch_id in set(groups)}
        fixed = FORK_SYSTEM_PROMPT + fork_prompt([])
        room = FORK_COMPLETION.room(sizing.configured_allowance(), fixed)
        sizes = {g: sum(sizing.estimate_tokens(json.dumps(c, **_COMPACT))
                        + FORK_COMPLETION.per_item_tokens for c in cards_by_group[g])
                 for g in groups}
        capacity = reconciliation.group_capacity(sizes, room=room, share=0)
        if capacity < 2:
            ops.notes.append(
                f"no two batches' claim cards fit in one cross-batch request ({room} token(s) of "
                f"room), so no fork spanning them could be looked for. Every pair is reported "
                f"unexamined rather than compared over a shortened set of cards.")
            return [], reconciliation.matrix_for(groups, [], {})

        schedule = sizing.schedule_rounds(groups, capacity=capacity)
        outcomes: Dict[Tuple[str, ...], ReconciliationRound] = {}
        rounds: List[ReconciliationRound] = []
        stopped = ""
        for number, members in enumerate(schedule, 1):
            if stopped:
                continue
            round_id = ids.round_id(inquiry_id, self.pass_name, members)
            cards = [c for g in members for c in cards_by_group[g]]
            prompt = fork_prompt(cards)
            estimate = (sizing.estimate_tokens(fixed) + sizing.estimate_tokens(prompt)
                        - sizing.estimate_tokens(fork_prompt([])))
            self.observe(f"cross-batch forks, round {number} of {len(schedule)}", index=number,
                         total=len(schedule), outcome="started", refs=list(members),
                         detail=f"{len(cards)} claim card(s) across {len(members)} batch(es)")
            result = self.invoke(prompt, inquiry_id=inquiry_id, attempt=attempt, inputs=len(cards),
                                 system_prompt=FORK_SYSTEM_PROMPT,
                                 estimated_prompt_tokens=max(0, estimate),
                                 completion_tokens=FORK_COMPLETION.for_batch(len(cards)))
            receipts.append(result.receipt)
            ops.refusals.extend(result.refusals)

            before_d, before_r = len(decisions), len(remainder)
            if result.payload is not None:
                if result.payload.get("observables"):
                    ops.refuse(CompilerRefusalKind.DANGLING_REFERENCE, "observables",
                               "the cross-batch round proposed an observable. Every claim was "
                               "already answered for by the batch it was primary in, and a second "
                               "one here is one claim operationalized twice. Dropped.",
                               detail=[round_id])
                decisions.extend(self._decisions(result.payload, by_id, by_ref, ops,
                                                 seen={d.decision_id for d in decisions}))
                remainder.extend(self._remainder(
                    result.payload, by_id, observables, claims, ops,
                    seen={r.term.lower() for r in remainder}))

            entry = ReconciliationRound(
                round_id=round_id, index=number, total=len(schedule), group_ids=list(members),
                estimated_prompt_tokens=max(0, estimate), outcome=result.receipt.outcome,
                added_edges=0, added_claims=0, duplicate_claims=0,
                detail=f"{len(decisions) - before_d} fork(s), "
                       f"{len(remainder) - before_r} remainder item(s)")
            rounds.append(entry)
            outcomes[tuple(members)] = entry
            self.observe(f"cross-batch forks, round {number} of {len(schedule)}", index=number,
                         total=len(schedule), outcome=result.receipt.outcome.value,
                         refs=list(members), detail=entry.detail)
            if any(not w.taken for w in result.receipt.capacity_waits):
                stopped = reconciliation.NOT_REACHED
                ops.notes.append(
                    f"the cross-batch fork pass stopped after round {number} of {len(schedule)}: "
                    f"the provider refused capacity and the declared budget would not cover the "
                    f"wait. The pairs the remaining rounds would have compared are named in the "
                    f"coverage matrix.")

        pairs = reconciliation.matrix_for(groups, [list(r.group_ids) for r in rounds], outcomes,
                                          unscheduled_reason=stopped
                                          or reconciliation.NOT_SCHEDULED)
        return rounds, pairs

    # ── what became of every claim ──

    def _close_plan(self, plan: sizing.BatchPlan, *, claims: Sequence[ClaimNode],
                    observables: Sequence[ObservableSpec],
                    remainder: Sequence[SemanticRemainderItem], answered: Set[str],
                    rounds: Sequence[ReconciliationRound],
                    pairs: Sequence[ComparisonPair]) -> BatchPlanRecord:
        """One disposition per claim. AN EMPTY OBSERVABLE LIST MAY BE CORRECT — a wholly
        interpretive graph has nothing to measure — but silence is not a disposition, so a claim
        nothing proposed and nothing set aside is `not_investigated` with the reason said out loud.
        """
        served = {o.claim_id for o in observables}
        residual = {r for item in remainder for r in item.claim_refs}
        where = {ref: b.batch_id for b in plan.record.batches for ref in b.primary_refs}
        unsendable = {ref for b in plan.record.unsendable_batches for ref in b.primary_refs}
        out: List[ItemDisposition] = []
        for claim in claims:
            batch = where.get(claim.claim_id, "")
            if claim.claim_id in unsendable:
                out.append(ItemDisposition(
                    ref=claim.claim_id, disposition=ItemDispositionKind.REFUSED, batch_id=batch,
                    reason="no request could carry this claim, so nothing was asked about it"))
            elif claim.claim_id in served:
                out.append(ItemDisposition(ref=claim.claim_id, batch_id=batch,
                                           disposition=ItemDispositionKind.OPERATIONALIZED))
            elif claim.claim_id in residual:
                out.append(ItemDisposition(ref=claim.claim_id, batch_id=batch,
                                           disposition=ItemDispositionKind.SEMANTIC_REMAINDER))
            elif claim.claim_id in answered:
                out.append(ItemDisposition(
                    ref=claim.claim_id, disposition=ItemDispositionKind.NOT_INVESTIGATED,
                    batch_id=batch,
                    reason="the operationalizer was asked about this claim and proposed nothing "
                           "for it. Not every claim can be investigated, and inventing an "
                           "observable to fill the gap is worse than saying so."))
        return plan.record.model_copy(update={
            "dispositions": out, "rounds": list(rounds), "pairs": list(pairs)})

    # ── observables ──

    def _observables(self, payload: Mapping[str, Any], by_id: Mapping[str, ClaimNode],
                     ops: _Ops, *, primary: Optional[Set[str]] = None,
                     per_claim: Optional[Dict[str, int]] = None,
                     seen: Optional[Set[str]] = None
                     ) -> Tuple[List[ObservableSpec], Dict[str, str]]:
        out: List[ObservableSpec] = []
        by_ref: Dict[str, str] = {}
        per_claim = {} if per_claim is None else per_claim
        already = set() if seen is None else set(seen)
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
            if primary is not None and claim_id not in primary:
                # THE CONTEXTUAL CLAIM, ANSWERED FOR TWICE. Its own batch is where it gets an
                # observable; one proposed from a neighbourhood would be the same claim
                # operationalized again, and two requests each finding "one observable" would read
                # downstream as two ways of investigating it rather than one, seen twice.
                ops.refuse(CompilerRefusalKind.DANGLING_REFERENCE, claim_id,
                           "an observable for a claim this request carries only as CONTEXT. The "
                           "batch that claim is primary in answers for it; proposing one here "
                           "would operationalize it from two neighbourhoods at once. Dropped.",
                           detail=[where])
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
            if observable_id in already or any(o.observable_id == observable_id for o in out):
                continue
            already.add(observable_id)
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
                   by_ref: Mapping[str, str], ops: _Ops,
                   seen: Optional[Set[str]] = None) -> List[DecisionCandidate]:
        """A fork may name any claim in the graph — including one this request held as CONTEXT.

        The opposite rule to the one observables follow, and for a reason rather than by oversight:
        an observable is WORK ASSIGNED to a claim and doing it twice is doing it twice, while a fork
        is a question about what to do next and the whole point of showing a batch its neighbours is
        that a fork may span them. Merged on the content-derived id, so two batches raising the same
        question raise it once.
        """
        out: List[DecisionCandidate] = []
        already = set() if seen is None else set(seen)
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
            if decision_id in already or any(d.decision_id == decision_id for d in out):
                continue
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
                   ops: _Ops, seen_terms: Optional[Set[str]] = None,
                   *, seen: Optional[Set[str]] = None) -> List[SemanticRemainderItem]:
        measurable_subjects = {c.subject.strip().lower() for c in claims
                               if c.epistemic_demand is DemandKind.MEASURABLE and c.subject.strip()}
        measurable_targets = {t.strip().lower() for o in observables for t in o.targets
                              if t.strip()
                              and not set(o.capability_classes) <= NON_MEASURING_CLASSES}
        out: List[SemanticRemainderItem] = []
        # KEYED ON THE TERM, ACROSS BATCHES. Two batches naming the same residue name one residue,
        # and a list carrying it twice would report the same unreachable thing as two of them.
        seen: Set[str] = set(seen or seen_terms or ())
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
                 remainder: Sequence[SemanticRemainderItem], receipts: Sequence[PassReceipt],
                 record: BatchPlanRecord, ops: _Ops) -> Tuple[PassOutcome, str]:
        """`thin` is judged against what the CLAIMS implied, never padded to avoid.

        A graph full of measurable demands and no observable is thin. A wholly interpretive graph
        with no observable is complete — and telling those apart is the reason this looks at the
        demands rather than counting.
        """
        if not receipts:
            return PassOutcome.EMPTY, "no operationalization request could be sent"
        if all(r.outcome is PassOutcome.UNAVAILABLE for r in receipts):
            return PassOutcome.UNAVAILABLE, "no batch reached the operationalizer"
        if any(r.truncated for r in receipts):
            return (PassOutcome.TRUNCATED,
                    f"{sum(1 for r in receipts if r.truncated)} of {len(receipts)} "
                    f"operationalization request(s) hit the completion budget after "
                    f"{len(observables)} observable(s). One truncated batch is a truncated pass.")
        failed = [r for r in receipts if r.outcome is PassOutcome.ERROR]
        if failed:
            return (PassOutcome.ERROR,
                    f"{len(failed)} of {len(receipts)} operationalization request(s) failed: "
                    f"{failed[0].detail}")

        # EVERY CLAIM HAS AN EXPLICIT DISPOSITION, or the pass lost track of one. An empty
        # observable list may be right for a wholly interpretive graph; silence about a claim
        # never is.
        missing = len(claims) - len(record.dispositions)
        if missing:
            return (PassOutcome.COVERAGE_FAILED,
                    f"{missing} of {len(claims)} claim(s) have no disposition in the batch plan. A "
                    f"claim nothing accounted for is one the partition lost.")
        refused = [d for d in record.dispositions
                   if d.disposition is ItemDispositionKind.REFUSED]
        if refused:
            return (PassOutcome.COVERAGE_FAILED,
                    f"{len(refused)} of {len(claims)} claim(s) were too large for any request and "
                    f"nothing was asked about them")
        unexamined = record.unexamined_pairs
        if unexamined:
            named = ", ".join(f"{p.left_batch_id}/{p.right_batch_id}" for p in unexamined[:3])
            return (PassOutcome.THIN,
                    f"{len(unexamined)} of {len(record.pairs)} claim-group pair(s) were never "
                    f"compared, so any fork between them was invisible to this pass: {named}"
                    f"{'…' if len(unexamined) > 3 else ''}. {unexamined[0].reason}")

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
                f"{len(claims)} claim(s) in {len(record.batches)} batch(es), with "
                f"{record.pairs_examined} of {len(record.pairs)} claim-group pair(s) compared")


def _neighbours(edges: Sequence[ClaimEdge]) -> Dict[str, Set[str]]:
    out: Dict[str, Set[str]] = {}
    for edge in edges:
        out.setdefault(edge.from_claim, set()).add(edge.to_claim)
        out.setdefault(edge.to_claim, set()).add(edge.from_claim)
    return out


def _components(claims: Sequence[ClaimNode], edges: Sequence[ClaimEdge]) -> Dict[str, str]:
    """Which connected piece of the claim graph each claim belongs to.

    Keyed on the SMALLEST member's id rather than on a counter, so the same graph names the same
    components on a re-run and a plan built from it is replay-stable. Claims joined by an edge, or
    by an `inferred_from` link, are one component: those are the claims whose forks are only visible
    together, so a batch seam between them is the expensive kind.
    """
    parent: Dict[str, str] = {c.claim_id: c.claim_id for c in claims}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: str, b: str) -> None:
        if a in parent and b in parent:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)

    for edge in edges:
        union(edge.from_claim, edge.to_claim)
    for claim in claims:
        for parent_id in claim.inferred_from:
            union(claim.claim_id, parent_id)
    return {c.claim_id: find(c.claim_id) for c in claims}


class FrozenEpistemicOperationalizer(EpistemicOperationalizer):
    """The same parse and the same laws, over frozen payloads — one per request.

    A SEQUENCE since HARNESS-003E, for the reason `FrozenPass` gives: a batched pass makes several
    calls, and one payload replayed to every batch is a batch answered by a response written for
    different claims.
    """

    def __init__(self, payloads: Any, *, model: Optional[str] = None):
        super().__init__(client=None, model=model)
        self._frozen = list(payloads) if isinstance(payloads, (list, tuple)) else [payloads]
        self._served = 0

    def is_available(self) -> bool:
        return True

    def invoke(self, user_prompt: str, *, inquiry_id: str, attempt: int = 1, inputs: int = 0,
               system_prompt: Optional[str] = None, estimated_prompt_tokens: int = 0,
               completion_tokens: Optional[int] = None) -> PassResult:
        from .passes import FrozenPass
        through = FrozenPass(self._frozen[self._served:self._served + 1], model=self._model)
        through.role = self.role
        through.pass_name = self.pass_name
        self._served += 1
        self.calls += 1
        return through.invoke(user_prompt, inquiry_id=inquiry_id, attempt=attempt, inputs=inputs)


__all__ = ["ROLE", "PRODUCER", "DEFAULT_BUDGET", "OPERATIONALIZE_COMPLETION", "FORK_COMPLETION",
           "MAX_OBSERVABLES_PER_CLAIM", "SYSTEM_PROMPT", "FORK_SYSTEM_PROMPT", "build_prompt",
           "fork_prompt", "fixed_prompt_text", "claim_digest", "EpistemicOperationalizer",
           "FrozenEpistemicOperationalizer"]
