"""
HARNESS-003A §5 — the relation architect: accepted atoms in, claims and relations out.

    atoms + their source pointers
      -> typed claims, each naming the atoms it was built from
      -> edges: supports / complicates / challenges / composes_from / generalizes

## What it is not given, and why the omission is the whole design

No images, no post documents, no urls, and NOT the theorist's unanchored prose. A pass that could
see would add visual content with no source unit behind it — and the coverage ledger would still
report complete, because the ledger accounts for source units and an invented claim has none. The
one check that would catch it does not apply to it. So the input is atoms, and `build_prompt` shows
nothing else.

## Preserving distinctions rather than collapsing them

The failure this pass is written against is a graph that turns four different atoms into one
comfortable sentence about how things compare. A quality, the effect that quality produces, and the
comparison between two such effects are three claims with three different warrants: the first might
be observable, the second is a hypothesis about perception, and the third holds across images or
not at all. `atom_kind_to_claim_kind` is the DEFAULT that keeps them apart; the architect may
override it, and an override is recorded rather than applied silently.

## Composition is allowed; deletion is not

An atom may end up inside a composed claim, and several atoms may compose one. What may not happen
is an atom quietly having no claim: `orphaned_atoms` reports every atom no claim was built from, so
"the architect ignored half the dissection" is a number rather than something a reader has to
notice.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from backend.schemas.inquiry import DemandKind
from backend.schemas.semantic_compilation import (AtomKind, ClaimEdge, ClaimEdgeKind, ClaimKind,
                                                  ClaimNode, ClaimStatus, CompilerRefusal,
                                                  CompilerRefusalKind, DissolutionPass,
                                                  FORBIDDEN_INITIAL_STATUSES, ImageScope,
                                                  PassOutcome, PassReceipt, SemanticAtom,
                                                  SourcePointer, SourceType, SourceUnit,
                                                  SourceUnitKind, _FORBIDDEN_DEMANDS,
                                                  _REQUIRED_DEMANDS)

from . import contracts, ids
from .base import refusal
from .passes import ModelPass, PassBudget, PassResult, bounded, merge_receipts

ROLE = "relation_architect"
PRODUCER = "semantic_compilation/architect-v1"

#: 4096, for the reason the dissector's comment gives at length: a provider counts
#: `max_completion_tokens` against the per-minute allowance whether or not the model uses them, and
#: this account's is 8000. A budget nearer that ceiling is a request that cannot be sent.
DEFAULT_BUDGET = PassBudget(max_completion_tokens=4096, batch_size=0)

MAX_CLAIMS = 80

#: How many atoms may go into one architect request. The live run sent 88 and the provider answered
#: `413 Request too large for model`, and forty is what fits under an 8000-token allowance
#: alongside the completion budget — a fact worth having rather than guessing at, which is why the
#: provider's message now travels onto the receipt.
#:
#: NOT BATCHED, and the cap is the price of that: relations are what this pass is FOR, and a batch
#: boundary is a relation it was structurally unable to see. So it gets one call over as many atoms
#: as fit, and the remainder is REPORTED — a pass that quietly used half its input and called itself
#: complete is the shape this lane exists to make impossible.
MAX_ATOMS_PER_CALL = 40

SYSTEM_PROMPT = (
    "You are a relation architect inside a visual close-reading tool. You are given SEMANTIC "
    "ATOMS: units of meaning that were already extracted from a person's question and from a "
    "vision model's reading of their images. You do not see the images and you do not see any "
    "prose beyond these atoms. You output JSON and nothing else.\n\n"
    "Your job is to assemble atoms into claims and to state the relations between them.\n\n"
    "1. BUILD FROM ATOMS ONLY. Every claim names the atom ids it was built from. You may compose "
    "several atoms into one claim, and you may build several claims from one atom. You may not "
    "introduce content that is in no atom.\n"
    "2. PRESERVE THE DISTINCTIONS. A quality, the effect that quality produces, and a comparison "
    "between two such effects are THREE claims, not one. Do not flatten them into a sentence about "
    "how things compare — the first might be observable, the second is a hypothesis about "
    "perception, and the third holds across images or not at all.\n"
    "3. TYPE EACH CLAIM from the closed list. A default mapping from atom kind to claim kind is "
    "given; follow it unless the atoms genuinely say otherwise, and give a `note` when you depart "
    "from it.\n"
    "4. SCOPE. A claim holding across images is a `comparison` and may not be scoped to one image. "
    "A claim about one picture is `one_image`.\n"
    "5. RELATE. Connect claims with supports / complicates / challenges / composes_from / "
    "generalizes, and say why in a few words.\n"
    "6. AN INFERENCE OF YOUR OWN names the claims it follows from, in `inferred_from`. An "
    "inference with no parents is an assertion wearing an inference's clothes.\n\n"
    "Hard rules:\n"
    "- Never output a mask, box, point, polygon, coordinate, pixel count, region id or confidence.\n"
    "- Never mark a claim `visible` or `measured`. Nothing has run.\n"
    "- A claim whose warrant is outside the picture is `historical_or_sourced` and asks for "
    "`sourced`, never `measurable`.\n"
    "- An interpretation does not become measurable because measurements contribute to it.\n"
    "- Do not drop an atom because it is hard to type. `unknown` is a legitimate claim kind."
)


def atom_digest(atoms: Sequence[SemanticAtom], units: Mapping[str, SourceUnit]) -> List[Dict[str, Any]]:
    """What the architect is shown. Atoms, their kinds, their authors and their quotes.

    The quotes are included and the SOURCE PROSE is not: a quote is the atom's own evidence for
    itself, and the surrounding paragraph is the thing this pass must not read.
    """
    return [{
        "atom_id": a.atom_id, "text": a.text, "unit_kind": a.unit_kind.value,
        "author": a.author.value, "image_scope": a.image_scope.value,
        "subject": a.subject, "predicate": a.predicate, "object": a.object_,
        "quotes": list(a.quotes),
        "from_the_person": all(units[u].is_user_authored for u in a.source_unit_ids
                               if u in units) if a.source_unit_ids else False,
    } for a in atoms]


def build_prompt(atoms: Sequence[SemanticAtom], units: Mapping[str, SourceUnit]) -> str:
    contract = contracts.graph_contract()
    vocabulary = {
        "claim_kinds": contract["claim_kinds"],
        "claim_edge_kinds": list(contracts.closed_set("claim_edge_kinds")),
        "epistemic_demands": list(contracts.closed_set("epistemic_demands")),
        "claim_statuses": list(contracts.closed_set("claim_statuses")),
        "image_scopes": list(contracts.closed_set("image_scopes")),
        "atom_kind_to_claim_kind": contracts.atom_kind_to_claim_kind(),
    }
    return (
        f"THE ATOMS — this is everything you may build from:\n"
        f"{json.dumps(atom_digest(atoms, units), indent=2, ensure_ascii=False)}\n\n"
        f"THE VOCABULARY — use only these:\n{json.dumps(vocabulary, indent=2)}\n\n"
        f"Return JSON of exactly this shape. `ref` values are yours and link objects within this "
        f"response:\n"
        f'{{"claims": [{{"ref": "c1", "text": "<one claim>", "kind": "<claim kind>", '
        f'"atom_ids": ["<an atom id from above>"], "subject": "", "predicate": "", "object": "", '
        f'"image_scope": "<image scope>", "demand": "<epistemic demand>", '
        f'"status": "<claim status>", "inferred_from": [], "note": ""}}], '
        f'"edges": [{{"kind": "<edge kind>", "from": "c1", "to": "c2", "why": ""}}]}}\n'
        f"Return empty lists rather than inventing content."
    )


class _Assembly:
    """One parse. Local refs resolve to content-derived ids; every atom ref is checked."""

    def __init__(self, inquiry_id: str, atoms: Sequence[SemanticAtom],
                 units: Mapping[str, SourceUnit]):
        self.inquiry_id = inquiry_id
        self.atoms = {a.atom_id: a for a in atoms}
        self.units = dict(units)
        self.refusals: List[CompilerRefusal] = []
        self.notes: List[str] = []
        self.pending: List[Dict[str, Any]] = []
        self.by_ref: Dict[str, str] = {}
        self.claims: List[ClaimNode] = []
        self.default_kind = contracts.atom_kind_to_claim_kind()

    def refuse(self, kind: CompilerRefusalKind, what: str, why: str,
               detail: Sequence[str] = ()) -> None:
        self.refusals.append(refusal(self.inquiry_id, kind, what, why, detail))

    # ── source pointers, derived rather than asked for ──

    def pointers(self, atom_ids: Sequence[str]) -> List[SourcePointer]:
        """A claim's pointers come from its ATOMS' units, not from the model.

        The architect is never asked where a claim came from: it names atoms, and the atoms already
        carry that. Asking would let a pass that had drifted from its atoms still produce a
        plausible-looking anchor.
        """
        out: List[SourcePointer] = []
        seen: Set[Tuple[str, str]] = set()
        for atom_id in atom_ids:
            atom = self.atoms.get(atom_id)
            if atom is None:
                continue
            for unit_id in atom.source_unit_ids:
                unit = self.units.get(unit_id)
                if unit is None:
                    continue
                source_type = (SourceType.PROMPT if unit.is_user_authored
                               else SourceType.SCENE_READING)
                key = (source_type.value, unit.source_ref)
                if key in seen:
                    continue
                seen.add(key)
                out.append(SourcePointer(
                    source_type=source_type, source_id=unit.source_ref, text=unit.exact_quote,
                    span=tuple(unit.span) if unit.span else None,
                    image_refs=list(unit.image_refs)))
        return out

    # ── claims ──

    def claim(self, index: int, row: Mapping[str, Any]) -> None:
        where = f"claim {index}"
        found = contracts.geometry_keys_in(row)
        if found:
            self.refuse(CompilerRefusalKind.GEOMETRY_IN_A_READING, ", ".join(found),
                        "a compiled claim may not carry geometry, a region id or a confidence. "
                        "The claim was dropped rather than stripped.", detail=[where])
            return
        text = str(row.get("text") or "").strip()
        if not text:
            return

        named = [str(a).strip() for a in row.get("atom_ids") or () if str(a).strip()]
        atom_refs = [a for a in named if a in self.atoms]
        for bad in [a for a in named if a not in self.atoms]:
            self.refuse(CompilerRefusalKind.DANGLING_REFERENCE, bad,
                        "the architect built a claim from an atom that is not in this dissection — "
                        "either it invented the id, or the atom was refused upstream.",
                        detail=[where, text[:120]])
        parents = [str(p).strip() for p in row.get("inferred_from") or () if str(p).strip()]
        if not atom_refs and not parents:
            self.refuse(CompilerRefusalKind.UNANCHORED_CLAIM, text[:120],
                        "a claim built from no atom and inferred from nothing. It reads exactly "
                        "like one that came from the dissection.", detail=[where])
            return

        kind = self._kind(row, atom_refs, where, text)
        if kind is None:
            return
        demand = self._demand(row, kind, where)
        status = self._status(row, where)
        scope = self._scope(row, kind, atom_refs, where)

        pointers = self.pointers(atom_refs)
        if not pointers and not parents:
            self.refuse(CompilerRefusalKind.UNANCHORED_CLAIM, text[:120],
                        "every atom this claim named resolved to no source unit, so it carries no "
                        "pointer and no parent.", detail=[where])
            return
        if not pointers:
            pointers = [SourcePointer(source_type=SourceType.COMPILER_INFERENCE,
                                      source_id="relation_architect", text=text)]

        claim_id = ids.claim_id(self.inquiry_id, kind, text)
        self.by_ref[str(row.get("ref") or f"#{index}")] = claim_id
        if any(p["claim_id"] == claim_id for p in self.pending):
            return
        self.pending.append({
            "claim_id": claim_id, "text": text, "claim_kind": kind, "atom_refs": atom_refs,
            "subject": str(row.get("subject") or "").strip(),
            "predicate": str(row.get("predicate") or "").strip(),
            "object": str(row.get("object") or "").strip(),
            "sources": pointers, "image_scope": scope, "epistemic_demand": demand,
            "status": status, "note": str(row.get("note") or "").strip(),
            "parents": parents, "where": where})

    def _kind(self, row: Mapping[str, Any], atom_refs: Sequence[str], where: str,
              text: str) -> Optional[ClaimKind]:
        raw = str(row.get("kind") or row.get("claim_kind") or "").strip()
        if raw and raw not in set(contracts.closed_set("claim_kinds")):
            self.refuse(CompilerRefusalKind.UNKNOWN_CLAIM_KIND, raw,
                        f"not one of {list(contracts.closed_set('claim_kinds'))}. The claim was "
                        f"dropped rather than filed under `unknown`, which means something else.",
                        detail=[where, text[:160]])
            return None
        if raw:
            expected = self._default_kind_for(atom_refs)
            if expected and raw != expected:
                # NOT a refusal. The default is a default; the architect may know better. It is
                # RECORDED so a reader can see the mapping was departed from rather than ignored.
                self.notes.append(
                    f"{where}: typed {raw!r} where its atoms default to {expected!r}"
                    + (f" — {row.get('note')}" if row.get("note") else " with no reason given"))
            return ClaimKind(raw)
        fallback = self._default_kind_for(atom_refs)
        return ClaimKind(fallback) if fallback else ClaimKind.UNKNOWN

    def _default_kind_for(self, atom_refs: Sequence[str]) -> str:
        kinds = {self.atoms[a].unit_kind.value for a in atom_refs if a in self.atoms}
        if len(kinds) != 1:
            return ""
        return self.default_kind.get(next(iter(kinds)), "")

    def _demand(self, row: Mapping[str, Any], kind: ClaimKind, where: str) -> DemandKind:
        raw = str(row.get("demand") or row.get("epistemic_demand") or "").strip()
        if raw and raw not in {d.value for d in DemandKind}:
            self.refuse(CompilerRefusalKind.UNKNOWN_DEMAND_KIND, raw,
                        f"not one of {[d.value for d in DemandKind]}. Read as `interpretive`, the "
                        f"only direction with no way to overstate.", detail=[where])
            raw = ""
        demand = DemandKind(raw) if raw else DemandKind.INTERPRETIVE

        forbidden = _FORBIDDEN_DEMANDS.get(kind)
        if forbidden and demand in forbidden:
            corrected = (DemandKind.SOURCED if kind is ClaimKind.HISTORICAL_OR_SOURCED
                         else DemandKind.INTERPRETIVE)
            self.refuse(CompilerRefusalKind.MEASURED_STATUS_CLAIMED, demand.value,
                        f"a {kind.value!r} claim may not ask for a measurement. Corrected DOWNWARD "
                        f"to {corrected.value!r} and recorded: a demand is an aspiration, and "
                        f"correcting it down can only make the claim look weaker than the "
                        f"architect hoped.", detail=[where])
            return corrected
        required = _REQUIRED_DEMANDS.get(kind)
        if required and demand not in required:
            corrected = sorted(required, key=lambda d: d.value)[0]
            self.refuse(CompilerRefusalKind.UNKNOWN_DEMAND_KIND, demand.value,
                        f"a {kind.value!r} claim must ask for one of "
                        f"{sorted(d.value for d in required)}. Corrected to {corrected.value!r}.",
                        detail=[where])
            return corrected
        return demand

    def _status(self, row: Mapping[str, Any], where: str) -> ClaimStatus:
        raw = str(row.get("status") or "").strip().lower()
        if raw in FORBIDDEN_INITIAL_STATUSES:
            self.refuse(CompilerRefusalKind.MEASURED_STATUS_CLAIMED, raw,
                        f"nothing has run, so no claim may start {raw!r}. Read as `uncertain`.",
                        detail=[where])
            return ClaimStatus.UNCERTAIN
        if raw and raw not in {s.value for s in ClaimStatus}:
            self.refuse(CompilerRefusalKind.UNKNOWN_CLAIM_STATUS, raw,
                        f"not one of {[s.value for s in ClaimStatus]}. Read as `uncertain`.",
                        detail=[where])
            return ClaimStatus.UNCERTAIN
        return ClaimStatus(raw) if raw else ClaimStatus.INTERPRETIVE

    def _scope(self, row: Mapping[str, Any], kind: ClaimKind, atom_refs: Sequence[str],
               where: str) -> ImageScope:
        raw = str(row.get("image_scope") or "").strip()
        scope = (ImageScope(raw) if raw in {s.value for s in ImageScope}
                 else self._default_scope(atom_refs))
        if kind is ClaimKind.COMPARISON and scope is ImageScope.ONE_IMAGE:
            self.refuse(CompilerRefusalKind.IMAGE_SCOPE_CORRECTED, "one_image",
                        "a comparison scoped to one image. One observation typed as a corpus "
                        "tendency is the cheapest way to manufacture a finding, so the scope was "
                        "widened to `corpus` and the correction recorded.", detail=[where])
            return ImageScope.CORPUS
        return scope

    def _default_scope(self, atom_refs: Sequence[str]) -> ImageScope:
        scopes = {self.atoms[a].image_scope for a in atom_refs if a in self.atoms}
        return next(iter(scopes)) if len(scopes) == 1 else ImageScope.CORPUS

    def build(self) -> None:
        """Resolve parents to a fixpoint, then construct. HARNESS-002A's rule, kept.

        A claim may name a parent the model listed after it, and dropping one claim can orphan
        another's parent — so a single pass would leave an inference standing on a parent that had
        itself been refused.
        """
        if len(self.pending) > MAX_CLAIMS:
            self.notes.append(f"the architect produced {len(self.pending)} claims; the first "
                              f"{MAX_CLAIMS} are kept and the overflow is reported")
            self.pending = self.pending[:MAX_CLAIMS]

        live = {p["claim_id"] for p in self.pending}
        orphaned: List[Dict[str, Any]] = []
        while True:
            dropped: Set[str] = set()
            for entry in self.pending:
                entry["resolved_parents"] = [
                    t for t in (self.by_ref.get(r) for r in entry["parents"])
                    if t and t in live and t != entry["claim_id"]]
                if not entry["atom_refs"] and not entry["resolved_parents"]:
                    dropped.add(entry["claim_id"])
                    orphaned.append(entry)
            if not dropped:
                break
            live -= dropped
            self.pending = [p for p in self.pending if p["claim_id"] not in dropped]

        for entry in [*self.pending, *orphaned]:
            for ref in entry["parents"]:
                target = self.by_ref.get(ref)
                if target is None or target not in live or target == entry["claim_id"]:
                    self.refuse(CompilerRefusalKind.DANGLING_REFERENCE, str(ref),
                                "a claim was said to follow from something that is not in the "
                                "graph. The parent link was dropped.", detail=[entry["where"]])
        for entry in orphaned:
            self.refuse(CompilerRefusalKind.INFERENCE_WITHOUT_PARENT, entry["text"][:120],
                        "every parent this inference named was dropped and it names no atom, "
                        "leaving an assertion wearing an inference's clothes.",
                        detail=[entry["where"]])

        for entry in self.pending:
            self.claims.append(ClaimNode(
                claim_id=entry["claim_id"], text=entry["text"], claim_kind=entry["claim_kind"],
                subject=entry["subject"], predicate=entry["predicate"], object=entry["object"],
                sources=entry["sources"], image_scope=entry["image_scope"],
                epistemic_demand=entry["epistemic_demand"], status=entry["status"],
                inferred_from=entry["resolved_parents"], atom_refs=entry["atom_refs"],
                note=entry["note"]))

    # ── edges ──

    def edges(self, rows: Sequence[Mapping[str, Any]]) -> List[ClaimEdge]:
        live = {c.claim_id for c in self.claims}
        out: List[ClaimEdge] = []
        seen: Set[str] = set()
        for index, row in enumerate(rows):
            where = f"edge {index}"
            raw = str(row.get("kind") or "").strip()
            if raw not in set(contracts.closed_set("claim_edge_kinds")):
                self.refuse(CompilerRefusalKind.UNKNOWN_EDGE_KIND, raw or "(empty)",
                            f"not one of {list(contracts.closed_set('claim_edge_kinds'))}. Dropped "
                            f"rather than read as `supports`: an unreadable rhetorical job silently "
                            f"turned into support is how an argument gains evidence nobody offered.",
                            detail=[where])
                continue
            source = self.by_ref.get(str(row.get("from") or row.get("from_claim") or "").strip())
            target = self.by_ref.get(str(row.get("to") or row.get("to_claim") or "").strip())
            if source not in live or target not in live or source == target:
                self.refuse(CompilerRefusalKind.DANGLING_REFERENCE,
                            f"{row.get('from')} -> {row.get('to')}",
                            "an edge between claims that are not both in the graph, or from a claim "
                            "to itself. A dangling edge renders as a supported claim in any UI that "
                            "follows edges.", detail=[where])
                continue
            kind = ClaimEdgeKind(raw)
            edge_id = ids.edge_id(self.inquiry_id, kind, source, target)
            if edge_id in seen:
                continue
            seen.add(edge_id)
            out.append(ClaimEdge(edge_id=edge_id, kind=kind, from_claim=source, to_claim=target,
                                 why=str(row.get("why") or "").strip()))
        return out


class RelationArchitect(ModelPass):
    """One call over all accepted atoms. Not batched: relations are what it is for, and a batch
    boundary is a relation the pass was structurally unable to see."""

    role = ROLE
    pass_name = DissolutionPass.RELATION_ARCHITECT
    system_prompt = SYSTEM_PROMPT
    budget = DEFAULT_BUDGET

    def assemble(self, atoms: Sequence[SemanticAtom], units: Sequence[SourceUnit], *,
                 inquiry_id: str, attempt: int = 1
                 ) -> Tuple[List[ClaimNode], List[ClaimEdge], List[CompilerRefusal], List[str],
                            PassReceipt]:
        by_unit = {u.source_unit_id: u for u in units}
        atoms, overflow = bounded(atoms, MAX_ATOMS_PER_CALL)
        comp = _Assembly(inquiry_id, atoms, by_unit)
        if overflow:
            comp.notes.append(
                f"{len(overflow)} atom(s) beyond the first {MAX_ATOMS_PER_CALL} were not sent to "
                f"the architect: one request over all of them is refused by the provider as too "
                f"large. They remain in the graph, unbuilt-from, and are counted in the orphan "
                f"total rather than dropped.")
        if not atoms:
            receipt = merge_receipts(self.pass_name, [], inquiry_id=inquiry_id,
                                     outcome=PassOutcome.EMPTY, attempt=attempt,
                                     detail="no atom reached the architect")
            return [], [], [], ["the architect was given no atom, so it built nothing"], receipt

        result = self.invoke(build_prompt(atoms, by_unit), inquiry_id=inquiry_id, attempt=attempt,
                             inputs=len(atoms))
        comp.refusals.extend(result.refusals)
        if result.payload is None:
            receipt = merge_receipts(self.pass_name, [result.receipt], inquiry_id=inquiry_id,
                                     outcome=result.receipt.outcome, attempt=attempt,
                                     detail=result.receipt.detail)
            return [], [], comp.refusals, comp.notes, receipt

        rows = result.payload.get("claims")
        for index, row in enumerate(rows if isinstance(rows, list) else []):
            if isinstance(row, Mapping):
                comp.claim(index, row)
        comp.build()
        rows = result.payload.get("edges")
        edges = comp.edges([r for r in (rows if isinstance(rows, list) else [])
                            if isinstance(r, Mapping)])

        outcome, detail = self._outcome(atoms, comp, edges, result)
        receipt = merge_receipts(self.pass_name, [result.receipt], inquiry_id=inquiry_id,
                                 outcome=outcome, attempt=attempt, outputs=len(comp.claims),
                                 detail=detail)
        return comp.claims, edges, comp.refusals, comp.notes, receipt

    def _outcome(self, atoms: Sequence[SemanticAtom], comp: _Assembly,
                 edges: Sequence[ClaimEdge], result: PassResult) -> Tuple[PassOutcome, str]:
        if result.receipt.truncated:
            return (PassOutcome.TRUNCATED,
                    f"the architect hit its completion budget after {len(comp.claims)} claim(s)")
        if not comp.claims:
            return PassOutcome.EMPTY, "no claim survived anchoring to an atom"

        orphans = orphaned_atoms(atoms, comp.claims)
        if orphans:
            comp.notes.append(
                f"{len(orphans)} of {len(atoms)} atom(s) were not built into any claim. They are "
                f"kept in the graph and reported: an atom with no claim is the dissector's work "
                f"the architect did not use, which is a different fact from the dissector not "
                f"having done it.")

        # THIN IS A JUDGEMENT ABOUT WHAT THE ATOMS IMPLIED, not a threshold on the claim count. If
        # the dissection found causes and comparisons and the architect drew no relation between
        # anything, the relational work this pass exists for did not happen.
        relational = {AtomKind.RELATION, AtomKind.COMPARISON, AtomKind.CAUSAL_HYPOTHESIS}
        implied = [a for a in atoms if a.unit_kind in relational]
        if implied and not edges:
            return (PassOutcome.THIN,
                    f"{len(implied)} atom(s) name a relation, a comparison or a cause and the "
                    f"architect drew no edge between any claims. The relations are the part of "
                    f"this pass that is not also the dissector's work.")
        if len(orphans) > len(atoms) // 2:
            return (PassOutcome.THIN,
                    f"{len(orphans)} of {len(atoms)} atom(s) reached no claim; more of the "
                    f"dissection was set aside than was used")
        return (PassOutcome.COMPLETED,
                f"{len(comp.claims)} claim(s) and {len(edges)} relation(s) over {len(atoms)} atoms")


def orphaned_atoms(atoms: Sequence[SemanticAtom],
                   claims: Sequence[ClaimNode]) -> List[str]:
    """Atoms no claim was built from. Reported, never deleted — see the module note."""
    used = {ref for claim in claims for ref in claim.atom_refs}
    return [a.atom_id for a in atoms if a.atom_id not in used]


class FrozenRelationArchitect(RelationArchitect):
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


__all__ = ["ROLE", "PRODUCER", "DEFAULT_BUDGET", "MAX_CLAIMS", "SYSTEM_PROMPT", "build_prompt",
           "atom_digest", "orphaned_atoms", "RelationArchitect", "FrozenRelationArchitect"]
