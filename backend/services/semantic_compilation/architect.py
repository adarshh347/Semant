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

## HARNESS-003E: batched locally, then reconciled across the batches

This pass used to make ONE call over the first forty atoms and report the rest as overflow. Forty
was a guess — the constant's own comment said "forty is what fits under an 8000-token allowance" —
and the live fold rehearsal refuted it: forty atoms plus a 4096-token reservation is 9,827 tokens
against an 8,000 ceiling, and the request could not be sent at all.

The repair is NOT to slice the atoms into independent calls. Relations are what this pass is for and
a batch boundary is a relation it was structurally unable to see, so independent slices would make
the 413 vanish by making cross-image relations impossible to discover — a green request rather than
a successful relation pass.

So it is two halves:

    every atom -> sized local batches, each atom PRIMARY exactly once -> claims and local edges
               -> compact CLAIM CARDS -> reconciliation rounds covering every pair of batches
               -> edges, duplicate mappings and parented cross-batch claims

and `completed` requires both: every atom locally considered AND every planned pair of batches
actually compared. An unexamined pair is named in the coverage matrix rather than rounded off.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from backend.schemas.inquiry import DemandKind
from backend.schemas.semantic_compilation import (AtomKind, BatchPlanRecord, ClaimEdge,
                                                  ClaimEdgeKind, ClaimKind, ClaimNode, ClaimStatus,
                                                  ComparisonPair, CompilerRefusal,
                                                  CompilerRefusalKind, DissolutionPass,
                                                  DuplicateClaim, FORBIDDEN_INITIAL_STATUSES,
                                                  ImageScope, ItemDisposition, ItemDispositionKind,
                                                  PassOutcome, PassReceipt, ReconciliationRound,
                                                  SemanticAtom, SourcePointer, SourceType,
                                                  SourceUnit, SourceUnitKind, _FORBIDDEN_DEMANDS,
                                                  _REQUIRED_DEMANDS)

from . import contracts, ids, reconciliation, sizing
from .base import refusal
from .passes import ModelPass, PassBudget, PassResult, merge_receipts

ROLE = "relation_architect"
PRODUCER = "semantic_compilation/architect-v1"

#: 4096, for the reason the dissector's comment gives at length: a provider counts
#: `max_completion_tokens` against the per-minute allowance whether or not the model uses them, and
#: this account's is 8000. A budget nearer that ceiling is a request that cannot be sent.
DEFAULT_BUDGET = PassBudget(max_completion_tokens=4096, batch_size=0)

MAX_CLAIMS = 80

#: What one architect request reserves for its answer. HARNESS-003E, and it replaces the flat 4096
#: this pass used to spend on every call.
#:
#: `reserved_tokens` is the headroom 003D's second-order finding named and nothing counted: a
#: reasoning model emits its reasoning into the same completion budget as the JSON, so a reservation
#: sized only from the expected output is short by however much thinking the model does first.
#: `per_item_tokens` is one atom's share of the claims and edges built from it — the frozen fixtures
#: run at roughly 0.7 claims per atom at about eighty tokens of JSON each.
#:
#: `maximum_tokens` is `DEFAULT_BUDGET.max_completion_tokens` and is a ceiling that is never raised.
ARCHITECT_COMPLETION = sizing.CompletionPolicy(
    reserved_tokens=1536, per_item_tokens=80, minimum_tokens=1024, maximum_tokens=4096)

#: What one reconciliation round reserves. Smaller per item than the local pass because a round
#: emits edges and duplicate mappings over cards it was GIVEN rather than claims built from scratch,
#: and larger at the floor because comparing two groups is where the reasoning actually happens.
RECONCILE_COMPLETION = sizing.CompletionPolicy(
    reserved_tokens=1536, per_item_tokens=24, minimum_tokens=1024, maximum_tokens=4096)

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


#: Compact separators, and the saving is not cosmetic. `indent=2` spends about a fifth of every
#: prompt on newlines and leading spaces that no reader ever sees — the prompt goes to a model, not
#: to a person — and inside an 8000-token allowance that fifth is atoms that would otherwise fall
#: into another batch, and another batch is another pair of groups the reconciliation has to
#: compare. Nothing about the content changes; this is the same JSON.
_COMPACT = dict(separators=(",", ":"), ensure_ascii=False)


def _vocabulary() -> Dict[str, Any]:
    contract = contracts.graph_contract()
    return {
        "claim_kinds": contract["claim_kinds"],
        "claim_edge_kinds": list(contracts.closed_set("claim_edge_kinds")),
        "epistemic_demands": list(contracts.closed_set("epistemic_demands")),
        "claim_statuses": list(contracts.closed_set("claim_statuses")),
        "image_scopes": list(contracts.closed_set("image_scopes")),
        "atom_kind_to_claim_kind": contracts.atom_kind_to_claim_kind(),
    }


def build_prompt(atoms: Sequence[SemanticAtom], units: Mapping[str, SourceUnit]) -> str:
    vocabulary = _vocabulary()
    return (
        f"THE ATOMS — this is everything you may build from:\n"
        f"{json.dumps(atom_digest(atoms, units), **_COMPACT)}\n\n"
        f"THE VOCABULARY — use only these:\n{json.dumps(vocabulary, **_COMPACT)}\n\n"
        f"Return JSON of exactly this shape. `ref` values are yours and link objects within this "
        f"response:\n"
        f'{{"claims": [{{"ref": "c1", "text": "<one claim>", "kind": "<claim kind>", '
        f'"atom_ids": ["<an atom id from above>"], "subject": "", "predicate": "", "object": "", '
        f'"image_scope": "<image scope>", "demand": "<epistemic demand>", '
        f'"status": "<claim status>", "inferred_from": [], "note": ""}}], '
        f'"edges": [{{"kind": "<edge kind>", "from": "c1", "to": "c2", "why": ""}}]}}\n'
        f"Return empty lists rather than inventing content."
    )


def fixed_prompt_text() -> str:
    """Everything charged on EVERY architect request, whatever atoms it carries.

    Handed to `sizing.plan` so the room left for atoms is what is actually left rather than the
    whole allowance. Built from the same pieces `build_prompt` uses — an empty atom list through the
    real builder, plus the system prompt — so it cannot drift from the thing it is measuring.
    """
    return SYSTEM_PROMPT + build_prompt([], {})


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


class _Merged:
    """Claims and edges accumulated across batches, keyed by their content-derived ids.

    A DUPLICATE IS ONE OBJECT SEEN TWICE, not two claims silently retained. Two batches that both
    arrive at the same sentence under the same kind produce the same `claim_id`, and what the second
    sighting adds is its ANCHORS: the atoms it was built from and the source pointers those imply.
    So the merge is a union of provenance rather than a first-writer-wins, and dropping the second
    copy without taking its atoms would report those atoms as orphans the architect never used.
    """

    def __init__(self, inquiry_id: str = "") -> None:
        self._inquiry_id = inquiry_id
        self.claims: Dict[str, ClaimNode] = {}
        self.edges: Dict[str, ClaimEdge] = {}
        self.batch_of: Dict[str, str] = {}
        self.duplicates = 0
        #: What the reconciliation rounds SAID duplicates what. Applied once at the end rather than
        #: per round, because a later round may map the survivor of an earlier one onto a third
        #: claim and only the whole set can be followed to a fixpoint.
        self.pending_duplicates: List[DuplicateClaim] = []

    def add_claims(self, claims: Sequence[ClaimNode], *, batch_id: str = "") -> None:
        for claim in claims:
            self.batch_of.setdefault(claim.claim_id, batch_id)
            seen = self.claims.get(claim.claim_id)
            if seen is None:
                self.claims[claim.claim_id] = claim
                continue
            self.duplicates += 1
            self.claims[claim.claim_id] = seen.model_copy(update={
                "atom_refs": _union(seen.atom_refs, claim.atom_refs),
                "inferred_from": _union(seen.inferred_from, claim.inferred_from),
                "sources": _union_pointers(seen.sources, claim.sources),
                # The FIRST note stands. A note is one batch's account of its own typing decision,
                # and concatenating two of them makes a sentence neither batch wrote.
                "note": seen.note or claim.note})

    def add_edges(self, edges: Sequence[ClaimEdge]) -> None:
        for edge in edges:
            self.edges.setdefault(edge.edge_id, edge)

    def apply_duplicates(self, notes: List[str]) -> List[DuplicateClaim]:
        """Merge every claim the reconciliation called a duplicate into the one it named canonical.

        A MERGE IS A DELETION, so everything that pointed at the removed id has to move with it:
        its atoms and source pointers go to the survivor (otherwise those atoms become orphans the
        architect never used), edges are re-minted around the survivor, and any claim that named the
        removed id as a parent names the survivor instead. An edge that becomes a self-edge under
        the rewrite is dropped — a claim supporting itself is what a merged pair leaves behind.
        """
        mapping, kept, cycle_notes = reconciliation.resolve_duplicates(
            self.claims, self.pending_duplicates)
        notes.extend(cycle_notes)
        if not mapping:
            return []

        for dead, canonical in mapping.items():
            gone, survivor = self.claims.pop(dead), self.claims[canonical]
            self.claims[canonical] = survivor.model_copy(update={
                "atom_refs": _union(survivor.atom_refs, gone.atom_refs),
                "inferred_from": _union(survivor.inferred_from, gone.inferred_from),
                "sources": _union_pointers(survivor.sources, gone.sources)})

        rewritten: Dict[str, ClaimEdge] = {}
        for edge in self.edges.values():
            source = mapping.get(edge.from_claim, edge.from_claim)
            target = mapping.get(edge.to_claim, edge.to_claim)
            if source == target:
                continue
            edge_id = ids.edge_id(self._inquiry_id, edge.kind, source, target)
            rewritten.setdefault(edge_id, edge.model_copy(update={
                "edge_id": edge_id, "from_claim": source, "to_claim": target}))
        self.edges = rewritten

        for claim_id, claim in list(self.claims.items()):
            parents = [mapping.get(p, p) for p in claim.inferred_from]
            parents = [p for p in dict.fromkeys(parents) if p != claim_id]
            if parents != claim.inferred_from:
                self.claims[claim_id] = claim.model_copy(update={"inferred_from": parents})

        notes.append(
            f"{len(kept)} claim(s) were identified as duplicates across batches and merged into "
            f"the claim named canonical, carrying their atoms and source pointers with them. The "
            f"mapping is on the batch plan: a merge removes an id, and a removal nobody can trace "
            f"is a deletion.")
        return kept

    def live(self) -> List[ClaimNode]:
        """Claims whose parents all survived. The graph validator refuses a dangling
        `inferred_from`, and a claim built in one batch may name a parent another batch's claim
        supplied — so the check happens once, over the merged set, rather than per batch."""
        kept = set(self.claims)
        return [c.model_copy(update={"inferred_from": [p for p in c.inferred_from if p in kept]})
                for c in self.claims.values()]

    def edge_list(self) -> List[ClaimEdge]:
        kept = set(self.claims)
        return [e for e in self.edges.values() if e.from_claim in kept and e.to_claim in kept]


def _union(first: Sequence[str], second: Sequence[str]) -> List[str]:
    out = list(first)
    out.extend(x for x in second if x not in set(first))
    return out


def _union_pointers(first: Sequence[SourcePointer],
                    second: Sequence[SourcePointer]) -> List[SourcePointer]:
    seen = {(p.source_type.value, p.source_id) for p in first}
    out = list(first)
    for pointer in second:
        key = (pointer.source_type.value, pointer.source_id)
        if key not in seen:
            seen.add(key)
            out.append(pointer)
    return out


class RelationArchitect(ModelPass):
    """Every atom locally considered, then every pair of batches compared. HARNESS-003E.

    Not one call: forty atoms and a 4096-token reservation is 9,827 tokens against an 8,000
    ceiling, so the single call this pass used to make could not be sent. Not independent slices
    either: relations are what this pass is FOR and a batch boundary is a relation it was
    structurally unable to see, so the cross-batch reconciliation is not an optimisation on top of
    the batching — it is the half that makes the batching legitimate.
    """

    role = ROLE
    pass_name = DissolutionPass.RELATION_ARCHITECT
    system_prompt = SYSTEM_PROMPT
    budget = DEFAULT_BUDGET

    def plan_batches(self, atoms: Sequence[SemanticAtom], *,
                     inquiry_id: str) -> sizing.BatchPlan:
        """The partition, sized against the account's allowance.

        AFFINITY IS THE SOURCE UNIT. Atoms dissolved out of one reading block or one prompt clause
        are the atoms most likely to relate to each other, so a seam between them is the most
        expensive kind — and one placed between two source units costs least. It is a preference,
        never a constraint: a source unit whose atoms exceed one request is split, and the split
        shows up in the plan as `allowance_reached` rather than as an affinity boundary.
        """
        units = {}
        items = []
        for atom in atoms:
            digest = atom_digest([atom], units)
            items.append(sizing.SizedItem(
                ref=atom.atom_id, text=json.dumps(digest[0], **_COMPACT),
                affinity=atom.source_unit_ids[0] if atom.source_unit_ids else atom.atom_id))
        return sizing.plan(items, inquiry_id=inquiry_id, pass_name=self.pass_name,
                           unit="semantic_atom", fixed_text=fixed_prompt_text(),
                           completion=ARCHITECT_COMPLETION)

    def assemble(self, atoms: Sequence[SemanticAtom], units: Sequence[SourceUnit], *,
                 inquiry_id: str, attempt: int = 1
                 ) -> Tuple[List[ClaimNode], List[ClaimEdge], List[CompilerRefusal], List[str],
                            PassReceipt]:
        by_unit = {u.source_unit_id: u for u in units}
        by_atom = {a.atom_id: a for a in atoms}
        if not atoms:
            receipt = merge_receipts(self.pass_name, [], inquiry_id=inquiry_id,
                                     outcome=PassOutcome.EMPTY, attempt=attempt,
                                     detail="no atom reached the architect")
            return [], [], [], ["the architect was given no atom, so it built nothing"], receipt

        plan = self.plan_batches(atoms, inquiry_id=inquiry_id)
        merged = _Merged(inquiry_id)
        refusals: List[CompilerRefusal] = []
        notes: List[str] = list(plan.record.notes)
        receipts: List[PassReceipt] = []
        considered: Set[str] = set()

        for batch in plan.batches:
            picked = [by_atom[r] for r in batch.assignment.primary_refs if r in by_atom]
            number, total = batch.assignment.index, batch.assignment.total
            if not batch.sendable:
                # THE 413, CAUGHT BY ARITHMETIC. Refused by name, at no cost to the allowance.
                for atom in picked:
                    refusals.append(refusal(
                        inquiry_id, CompilerRefusalKind.PASS_UNAVAILABLE, atom.atom_id,
                        f"this atom alone estimates larger than one whole request may carry, so no "
                        f"architect call could include it. Refused before transport rather than "
                        f"sent and refused by the provider. {batch.assignment.note}"))
                self.observe(f"relating batch {number} of {total}", index=number, total=total,
                             outcome="refused", refs=list(batch.assignment.primary_refs),
                             detail="too large to send; refused before transport")
                continue

            self.observe(f"relating batch {number} of {total}", index=number, total=total,
                         outcome="started", refs=list(batch.assignment.primary_refs),
                         detail=f"{len(picked)} atom(s), "
                                f"~{batch.assignment.estimated_total_tokens} token(s)")
            comp = _Assembly(inquiry_id, picked, by_unit)
            result = self.invoke(
                build_prompt(picked, by_unit), inquiry_id=inquiry_id, attempt=attempt,
                inputs=len(picked),
                estimated_prompt_tokens=batch.assignment.estimated_prompt_tokens,
                completion_tokens=batch.assignment.requested_completion_tokens)
            receipts.append(result.receipt)
            refusals.extend(result.refusals)
            considered.update(a.atom_id for a in picked)

            if result.payload is not None:
                rows = result.payload.get("claims")
                for index, row in enumerate(rows if isinstance(rows, list) else []):
                    if isinstance(row, Mapping):
                        comp.claim(index, row)
                comp.build()
                rows = result.payload.get("edges")
                merged.add_claims(comp.claims, batch_id=batch.batch_id)
                merged.add_edges(comp.edges([r for r in (rows if isinstance(rows, list) else [])
                                             if isinstance(r, Mapping)]))
            refusals.extend(comp.refusals)
            notes.extend(comp.notes)
            self.observe(f"relating batch {number} of {total}", index=number, total=total,
                         outcome=result.receipt.outcome.value,
                         refs=list(batch.assignment.primary_refs),
                         detail=result.receipt.detail
                                or f"{len(comp.claims)} claim(s) from {len(picked)} atom(s)")

        if merged.duplicates:
            notes.append(
                f"{merged.duplicates} claim(s) were built in more than one batch and merged into "
                f"one, taking the union of the atoms each sighting named. A duplicate is one object "
                f"seen twice, not two claims kept.")

        # THE HALF THAT MAKES THE BATCHING LEGITIMATE. Without it the pass sends green requests and
        # reports a relation search it never performed across any boundary.
        rounds, pairs, duplicate_map = self._reconcile(
            merged, inquiry_id=inquiry_id, attempt=attempt, plan=plan, receipts=receipts,
            refusals=refusals, notes=notes)

        claims = merged.live()
        edges = merged.edge_list()
        record = self._close_plan(plan, atoms=atoms, claims=claims, considered=considered,
                                  rounds=rounds, pairs=pairs, duplicate_map=duplicate_map)
        outcome, detail = self._outcome(atoms, claims, edges, receipts, record, notes)
        receipt = merge_receipts(self.pass_name, receipts, inquiry_id=inquiry_id, outcome=outcome,
                                 attempt=attempt, outputs=len(claims), detail=detail,
                                 batch_plan=record)
        return claims, edges, refusals, notes, receipt

    # ── across the boundaries ──

    def _reconcile(self, merged: "_Merged", *, inquiry_id: str, attempt: int,
                   plan: sizing.BatchPlan, receipts: List[PassReceipt],
                   refusals: List[CompilerRefusal], notes: List[str]
                   ) -> Tuple[List[ReconciliationRound], List[ComparisonPair],
                              List[DuplicateClaim]]:
        """Every pair of batches put in front of the model at least once, or named as unexamined.

        The rounds are scheduled from a capacity sized against the LARGEST groups, so every round
        the schedule produces fits by construction — the alternative is discovering at send time
        that a round does not fit, at which point both options are bad.

        A round that the pacer could not send stops the schedule. The remaining pairs are reported
        as unreached rather than silently dropped, because "the budget ended the run" and "nothing
        was found between these two" are opposite reports.
        """
        cards_by_group: Dict[str, List[Dict[str, Any]]] = {}
        for claim in merged.claims.values():
            group = merged.batch_of.get(claim.claim_id, "")
            cards_by_group.setdefault(group, []).append(
                reconciliation.claim_card(claim, group=group))
        groups = [b.batch_id for b in plan.batches if cards_by_group.get(b.batch_id)]

        if len(groups) < 2:
            # WHY THERE IS NOTHING ACROSS, not just that there is. The live control planned THREE
            # batches and two of them were refused for capacity, so one batch's claims were all
            # there was to reconcile — and the note said "one batch" three lines under a plan
            # saying three, which reads as the plan contradicting itself rather than as two
            # requests having failed.
            silent = len(plan.batches) - len(groups)
            notes.append(
                f"{len(groups)} of {len(plan.batches)} batch(es) produced a claim"
                + (f"; the other {silent} returned none, so there was no second group to compare "
                   f"against" if silent else
                   ", so every claim was already in front of the model together")
                + ". The coverage matrix is empty because there is nothing across, not because "
                  "nothing was compared.")
            return [], [], []

        fixed = reconciliation.fixed_prompt_text()
        room = RECONCILE_COMPLETION.room(sizing.configured_allowance(), fixed)
        sizes = {g: sum(sizing.estimate_tokens(json.dumps(c, **_COMPACT))
                        + RECONCILE_COMPLETION.per_item_tokens for c in cards_by_group[g])
                 for g in groups}
        capacity = reconciliation.group_capacity(sizes, room=room, share=0)
        if capacity < 2:
            notes.append(
                f"no two batches' claim cards fit in one reconciliation request "
                f"({room} token(s) of room). Every pair is reported unexamined rather than "
                f"compared over a shortened set of cards.")
            return [], reconciliation.matrix_for(groups, [], {}), []

        schedule = sizing.schedule_rounds(groups, capacity=capacity)
        outcomes: Dict[Tuple[str, ...], ReconciliationRound] = {}
        rounds: List[ReconciliationRound] = []
        stopped = ""
        for number, members in enumerate(schedule, 1):
            round_id = ids.round_id(inquiry_id, self.pass_name, members)
            if stopped:
                continue
            cards = [c for g in members for c in cards_by_group[g]]
            prompt = reconciliation.build_prompt(cards)
            estimate = sizing.estimate_tokens(fixed) + sizing.estimate_tokens(prompt) \
                - sizing.estimate_tokens(reconciliation.build_prompt([]))
            self.observe(f"reconciling round {number} of {len(schedule)}", index=number,
                         total=len(schedule), outcome="started", refs=list(members),
                         detail=f"{len(cards)} claim card(s) across {len(members)} batch(es)")
            result = self.invoke(
                prompt, inquiry_id=inquiry_id, attempt=attempt, inputs=len(cards),
                system_prompt=reconciliation.SYSTEM_PROMPT,
                estimated_prompt_tokens=max(0, estimate),
                completion_tokens=RECONCILE_COMPLETION.for_batch(len(cards)))
            receipts.append(result.receipt)
            refusals.extend(result.refusals)

            comp = reconciliation.Reconciliation(inquiry_id, merged.claims, merged.batch_of)
            if result.payload is not None:
                comp.read_edges([r for r in (result.payload.get("edges") or [])
                                 if isinstance(r, Mapping)], round_id=round_id)
                comp.read_duplicates([r for r in (result.payload.get("duplicates") or [])
                                      if isinstance(r, Mapping)], round_id=round_id)
                comp.read_claims([r for r in (result.payload.get("claims") or [])
                                  if isinstance(r, Mapping)], round_id=round_id)
                merged.add_claims(comp.added, batch_id=round_id)
                merged.add_edges(comp.edges)
                merged.pending_duplicates.extend(comp.duplicates)
            refusals.extend(comp.refusals)
            notes.extend(comp.notes)

            entry = ReconciliationRound(
                round_id=round_id, index=number, total=len(schedule), group_ids=list(members),
                estimated_prompt_tokens=max(0, estimate), outcome=result.receipt.outcome,
                added_edges=len(comp.edges), added_claims=len(comp.added),
                duplicate_claims=len(comp.duplicates),
                detail=result.receipt.detail or f"{len(cards)} card(s)")
            rounds.append(entry)
            outcomes[tuple(members)] = entry
            self.observe(f"reconciling round {number} of {len(schedule)}", index=number,
                         total=len(schedule), outcome=result.receipt.outcome.value,
                         refs=list(members),
                         detail=f"{len(comp.edges)} edge(s), {len(comp.added)} cross-batch "
                                f"claim(s), {len(comp.duplicates)} duplicate(s)")
            if any(not w.taken for w in result.receipt.capacity_waits):
                stopped = reconciliation.NOT_REACHED
                notes.append(
                    f"the reconciliation stopped after round {number} of {len(schedule)}: the "
                    f"provider refused capacity and the declared budget would not cover the wait. "
                    f"The pairs the remaining rounds would have compared are named in the coverage "
                    f"matrix as unexamined.")

        ran = [list(r.group_ids) for r in rounds]
        pairs = reconciliation.matrix_for(
            groups, ran, outcomes,
            unscheduled_reason=stopped or reconciliation.NOT_SCHEDULED)
        duplicate_map = merged.apply_duplicates(notes)
        return rounds, pairs, duplicate_map

    # ── what the plan says happened ──

    def _close_plan(self, plan: sizing.BatchPlan, *, atoms: Sequence[SemanticAtom],
                    claims: Sequence[ClaimNode], considered: Set[str],
                    rounds: Sequence[ReconciliationRound] = (),
                    pairs: Sequence[ComparisonPair] = (),
                    duplicate_map: Sequence[DuplicateClaim] = ()) -> BatchPlanRecord:
        """One disposition per atom, written onto the plan rather than into prose.

        `orphan` and `used` are read off the output; `refused` is the decision the sizing made about
        an atom no request could carry. An atom absent from this list is an atom the pass lost, and
        `_outcome` refuses to call that `completed`.
        """
        used = {ref for claim in claims for ref in claim.atom_refs}
        where = {ref: b.batch_id for b in plan.record.batches for ref in b.primary_refs}
        unsendable = {ref for b in plan.record.unsendable_batches for ref in b.primary_refs}
        dispositions: List[ItemDisposition] = []
        for atom in atoms:
            batch = where.get(atom.atom_id, "")
            if atom.atom_id in unsendable:
                dispositions.append(ItemDisposition(
                    ref=atom.atom_id, disposition=ItemDispositionKind.REFUSED, batch_id=batch,
                    reason="no request could carry this atom, so no architect call saw it"))
            elif atom.atom_id in used:
                dispositions.append(ItemDisposition(
                    ref=atom.atom_id, disposition=ItemDispositionKind.USED, batch_id=batch))
            elif atom.atom_id in considered:
                dispositions.append(ItemDisposition(
                    ref=atom.atom_id, disposition=ItemDispositionKind.ORPHAN, batch_id=batch))
        return plan.record.model_copy(update={
            "dispositions": dispositions, "rounds": list(rounds), "pairs": list(pairs),
            "duplicate_map": list(duplicate_map)})

    def _outcome(self, atoms: Sequence[SemanticAtom], claims: Sequence[ClaimNode],
                 edges: Sequence[ClaimEdge], receipts: Sequence[PassReceipt],
                 record: BatchPlanRecord, notes: List[str]) -> Tuple[PassOutcome, str]:
        if not receipts:
            return PassOutcome.EMPTY, "no architect request could be sent"
        if all(r.outcome is PassOutcome.UNAVAILABLE for r in receipts):
            return PassOutcome.UNAVAILABLE, "no batch reached the architect"
        # REQUESTS, NOT BATCHES. `receipts` holds one entry per REQUEST, and the reconciliation
        # rounds are requests too — the live fold rehearsal reported "12 of 27 architect batch(es)"
        # over a plan that says ten, which sends a reader looking for seventeen batches that do not
        # exist. The count is right; the noun was wrong.
        if any(r.truncated for r in receipts):
            return (PassOutcome.TRUNCATED,
                    f"{sum(1 for r in receipts if r.truncated)} of {len(receipts)} architect "
                    f"request(s) — {len(record.batches)} batch(es) plus {len(record.rounds)} "
                    f"reconciliation round(s) — hit the completion budget after {len(claims)} "
                    f"claim(s). One truncated request is a truncated pass: what it produced is a "
                    f"prefix.")
        failed = [r for r in receipts if r.outcome is PassOutcome.ERROR]
        if failed:
            return (PassOutcome.ERROR,
                    f"{len(failed)} of {len(receipts)} architect request(s) failed: "
                    f"{failed[0].detail}")
        if not claims:
            return PassOutcome.EMPTY, "no claim survived anchoring to an atom"

        # EVERY ATOM CONSIDERED, OR THE PASS DID NOT DO ITS JOB. Not a count of claims — an atom
        # nothing looked at is a different failure from an atom nothing could be built from, and
        # only the first means a request never happened.
        unconsidered = [d for d in record.dispositions
                        if d.disposition is ItemDispositionKind.REFUSED]
        missing = len(atoms) - len(record.dispositions)
        if missing:
            return (PassOutcome.COVERAGE_FAILED,
                    f"{missing} of {len(atoms)} atom(s) have no disposition in the batch plan. An "
                    f"atom nothing accounted for is one the partition lost.")
        if unconsidered:
            return (PassOutcome.COVERAGE_FAILED,
                    f"{len(unconsidered)} of {len(atoms)} atom(s) were too large for any request "
                    f"and no architect call saw them")

        # EVERY PAIR OF BATCHES COMPARED, OR THE RELATION SEARCH DID NOT HAPPEN ACROSS THEM. This is
        # the gate the batching is not legitimate without: local batches alone make a cross-boundary
        # relation structurally invisible, so a pass that never put two groups in front of the model
        # has no grounds to say it looked. The pairs are named, never counted away.
        unexamined = record.unexamined_pairs
        if unexamined:
            named = ", ".join(f"{p.left_batch_id}/{p.right_batch_id}" for p in unexamined[:3])
            return (PassOutcome.THIN,
                    f"{len(unexamined)} of {len(record.pairs)} batch pair(s) were never compared, "
                    f"so any relation between them was invisible to this pass: {named}"
                    f"{'…' if len(unexamined) > 3 else ''}. {unexamined[0].reason}")

        orphans = [d.ref for d in record.dispositions
                   if d.disposition is ItemDispositionKind.ORPHAN]
        if orphans:
            notes.append(
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
                f"{len(claims)} claim(s) and {len(edges)} relation(s) over {len(atoms)} atoms in "
                f"{len(record.batches)} batch(es), with {record.pairs_examined} of "
                f"{len(record.pairs)} batch pair(s) compared across "
                f"{len(record.rounds)} reconciliation round(s)")


def orphaned_atoms(atoms: Sequence[SemanticAtom],
                   claims: Sequence[ClaimNode]) -> List[str]:
    """Atoms no claim was built from. Reported, never deleted — see the module note."""
    used = {ref for claim in claims for ref in claim.atom_refs}
    return [a.atom_id for a in atoms if a.atom_id not in used]


class FrozenRelationArchitect(RelationArchitect):
    """The same parse and the same laws, over frozen payloads — one per request.

    A SEQUENCE since HARNESS-003E, because a batched pass makes several calls and a single payload
    would replay the first batch's answer to every batch. A fixture that runs out is `empty` rather
    than repeated, for the reason `FrozenPass` gives: a batch answered by a response written for
    different inputs is a replay proving nothing.
    """

    def __init__(self, payloads: Any, *, model: Optional[str] = None):
        super().__init__(client=None, model=model)
        self._frozen = list(payloads) if isinstance(payloads, (list, tuple)) else [payloads]
        self._served = 0

    def is_available(self) -> bool:
        return True

    def invoke(self, user_prompt: str, *, inquiry_id: str, attempt: int = 1,
               inputs: int = 0, system_prompt: Optional[str] = None,
               estimated_prompt_tokens: int = 0,
               completion_tokens: Optional[int] = None) -> PassResult:
        from .passes import FrozenPass
        through = FrozenPass(self._frozen[self._served:self._served + 1], model=self._model)
        through.role = self.role
        through.pass_name = self.pass_name
        self._served += 1
        self.calls += 1
        return through.invoke(user_prompt, inquiry_id=inquiry_id, attempt=attempt, inputs=inputs)


__all__ = ["ROLE", "PRODUCER", "DEFAULT_BUDGET", "ARCHITECT_COMPLETION", "RECONCILE_COMPLETION",
           "MAX_CLAIMS", "SYSTEM_PROMPT", "build_prompt", "fixed_prompt_text", "atom_digest",
           "orphaned_atoms", "RelationArchitect", "FrozenRelationArchitect"]
