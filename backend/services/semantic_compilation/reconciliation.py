"""
HARNESS-003E §3 — the cross-batch pass: what local batching cannot see, looked for on purpose.

    the claims every local batch built
      -> compact CLAIM CARDS, grouped by the batch that built them
      -> rounds in which every PAIR of groups co-occurs at least once
      -> edges between existing claims, duplicate mappings, parented cross-batch claims
      -> a coverage matrix saying which pairs were actually compared

## Why this exists at all

Batching the architect makes its requests sendable. On its own it also makes every relation that
crosses a boundary structurally invisible — the model is never shown both sides — so a batched pass
with no reconciliation would report a green request as a successful relation search. That is the
one failure this lane was written to prevent, and it is worse than the 413 it replaces: a 413 is
loud.

So `completed` is not available to the architect on local coverage alone. It requires that every
planned pair of groups was actually put in front of the model, and an unexamined pair is NAMED in
the matrix rather than rounded off.

## What a round may do, and the three things it may not

MAY: add an edge between two claims that already exist; say that one claim duplicates another and
name which is canonical; add a claim of its own that names the parent claims it follows from.

MAY NOT:

  · ADD AN UNPARENTED CLAIM. An assertion arriving at this stage has no atoms behind it and no
    parents either, which is content nobody said and nothing produced.
  · ADD A CLAIM WHOSE PARENTS ARE ALL IN ONE BATCH. That is not a cross-batch inference; it is
    content the local pass could have built and did not, and admitting it here is the door through
    which a reconciliation invents ordinary claims with no atoms behind them.
  · MERGE ACROSS KINDS. A claim id is keyed on kind and text, so two claims typed differently are
    two readings of the same words — a quality and the effect that quality produces are the exact
    pair this council exists to keep apart, and "they are duplicates" is how they get fused.

## What a card carries, and what it does not

Stable id, exact text, kind, subject/predicate/object, image scope, its group, and the source ids
behind it. NOT the source paragraphs, NOT geometry, and NOT a second look at the pictures — the
whole point is a bounded request over what the local passes already produced, and a card that
repeated its prose would put this pass back over the allowance it was written to fit under.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from backend.schemas.inquiry import DemandKind
from backend.schemas.semantic_compilation import (ClaimEdge, ClaimEdgeKind, ClaimKind, ClaimNode,
                                                  ClaimStatus, ComparisonPair, CompilerRefusal,
                                                  CompilerRefusalKind, DuplicateClaim,
                                                  FORBIDDEN_INITIAL_STATUSES, ImageScope,
                                                  PassOutcome, ReconciliationRound, SourcePointer,
                                                  SourceType, _FORBIDDEN_DEMANDS, _REQUIRED_DEMANDS)

from . import contracts, ids, sizing
from .base import refusal

PRODUCER = "semantic_compilation/reconciliation-v1"

#: Why a pair of groups was never put in front of the model. Reasons rather than a bare `False`,
#: because "there was nothing to schedule" and "the budget ran out" are different reports and the
#: repairs for them are opposite.
NOT_SCHEDULED = ("this pair was never scheduled: the two groups' claim cards do not fit in one "
                 "request together, so no round could hold both")
NOT_REACHED = ("the run stopped before this pair's round: the declared wall-clock budget or the "
               "transport attempt bound ended the pass")
ROUND_FAILED = "the round that would have compared this pair did not return a usable answer"

SYSTEM_PROMPT = (
    "You are a relation architect performing a CROSS-BATCH RECONCILIATION inside a visual "
    "close-reading tool. Claims were built in several separate passes, each of which saw only part "
    "of the material. You are given compact CARDS for claims from two or more of those groups. You "
    "do not see the images, the source prose, or the atoms. You output JSON and nothing else.\n\n"
    "Your ONLY job is to find what the separate passes could not see, because it lies BETWEEN "
    "them.\n\n"
    "1. RELATE ACROSS GROUPS. Connect claims with supports / complicates / challenges / "
    "composes_from / generalizes, naming their claim ids, and say why in a few words. Prefer "
    "relations whose two claims come from DIFFERENT groups — a relation inside one group is one "
    "that pass already had the chance to draw.\n"
    "2. NAME DUPLICATES. Where two groups produced the same claim in different words, say which "
    "claim duplicates which, and give the reason. Two claims of DIFFERENT kinds are never "
    "duplicates: a quality, the effect it produces and a comparison between two such effects are "
    "three claims, and merging them destroys the distinction.\n"
    "3. A CLAIM OF YOUR OWN MUST CROSS. You may add a comparison or an inference that only becomes "
    "visible with both groups in view — but it must name, in `inferred_from`, the claim ids it "
    "follows from, and those must come from MORE THAN ONE group. A claim whose parents are all in "
    "one group is one that group could have made itself.\n\n"
    "Hard rules:\n"
    "- Never invent a claim id. Use only the ids on the cards.\n"
    "- Never add content that is in no card. You cannot see the pictures and you have not read the "
    "source; anything not derivable from these cards is something you made up.\n"
    "- Never output a mask, box, point, polygon, coordinate, pixel count, region id or confidence.\n"
    "- Never mark a claim `visible` or `measured`. Nothing has run.\n"
    "- A claim holding across images is a `comparison` and may not be scoped to one image.\n"
    "- Return empty lists rather than inventing content. Finding nothing between two groups is a "
    "legitimate answer and is more useful than a relation nobody can trace."
)

_COMPACT = dict(separators=(",", ":"), ensure_ascii=False)


def claim_card(claim: ClaimNode, *, group: str) -> Dict[str, Any]:
    """One claim, compact enough to put a hundred of them in one request.

    Everything needed to relate it and to trace it; nothing needed to re-read it. The source ids
    travel and the source TEXT does not — a card that repeated its paragraph would put this pass
    back over the allowance the batching exists to fit under.
    """
    return {
        "claim_id": claim.claim_id, "text": claim.text, "kind": claim.claim_kind.value,
        "group": group, "subject": claim.subject, "predicate": claim.predicate,
        "object": claim.object_, "image_scope": claim.image_scope.value,
        "demand": claim.epistemic_demand.value,
        "sources": sorted({p.source_id for p in claim.sources if p.source_id}),
        "images": sorted({r for p in claim.sources for r in p.image_refs}),
    }


def build_prompt(cards: Sequence[Mapping[str, Any]]) -> str:
    vocabulary = {
        "claim_kinds": list(contracts.closed_set("claim_kinds")),
        "claim_edge_kinds": list(contracts.closed_set("claim_edge_kinds")),
        "epistemic_demands": list(contracts.closed_set("epistemic_demands")),
        "claim_statuses": list(contracts.closed_set("claim_statuses")),
        "image_scopes": list(contracts.closed_set("image_scopes")),
    }
    groups = sorted({str(c.get("group") or "") for c in cards})
    return (
        f"THE CLAIM CARDS — {len(cards)} claim(s) from {len(groups)} group(s). Every id you may "
        f"name is here:\n{json.dumps(list(cards), **_COMPACT)}\n\n"
        f"THE GROUPS in this round: {json.dumps(groups)}\n\n"
        f"THE VOCABULARY — use only these:\n{json.dumps(vocabulary, **_COMPACT)}\n\n"
        f"Return JSON of exactly this shape:\n"
        f'{{"edges": [{{"kind": "<edge kind>", "from": "<claim_id>", "to": "<claim_id>", '
        f'"why": ""}}], '
        f'"duplicates": [{{"claim": "<claim_id>", "duplicate_of": "<claim_id>", "why": ""}}], '
        f'"claims": [{{"text": "<one claim only both groups make visible>", '
        f'"kind": "<claim kind>", "inferred_from": ["<claim_id from one group>", '
        f'"<claim_id from another>"], "subject": "", "predicate": "", "object": "", '
        f'"image_scope": "<image scope>", "demand": "<epistemic demand>", '
        f'"status": "<claim status>", "note": ""}}]}}\n'
        f"Return empty lists rather than inventing content."
    )


def fixed_prompt_text() -> str:
    """Everything charged on every reconciliation request, whatever cards it carries."""
    return SYSTEM_PROMPT + build_prompt([])


class Reconciliation:
    """One round's parse, applied to the merged graph. Every reference is checked against it."""

    def __init__(self, inquiry_id: str, claims: Mapping[str, ClaimNode],
                 group_of: Mapping[str, str]):
        self.inquiry_id = inquiry_id
        self.claims = dict(claims)
        self.group_of = dict(group_of)
        self.refusals: List[CompilerRefusal] = []
        self.notes: List[str] = []
        self.added: List[ClaimNode] = []
        self.edges: List[ClaimEdge] = []
        self.duplicates: List[DuplicateClaim] = []

    def refuse(self, kind: CompilerRefusalKind, what: str, why: str,
               detail: Sequence[str] = ()) -> None:
        self.refusals.append(refusal(self.inquiry_id, kind, what, why, detail))

    # ── edges ──

    def read_edges(self, rows: Sequence[Mapping[str, Any]], *, round_id: str) -> None:
        seen: Set[str] = set()
        for index, row in enumerate(rows):
            where = f"reconciliation edge {index}"
            raw = str(row.get("kind") or "").strip()
            if raw not in set(contracts.closed_set("claim_edge_kinds")):
                self.refuse(CompilerRefusalKind.UNKNOWN_EDGE_KIND, raw or "(empty)",
                            f"not one of {list(contracts.closed_set('claim_edge_kinds'))}. Dropped "
                            f"rather than read as `supports`.", detail=[where, round_id])
                continue
            source = str(row.get("from") or row.get("from_claim") or "").strip()
            target = str(row.get("to") or row.get("to_claim") or "").strip()
            if source not in self.claims or target not in self.claims or source == target:
                self.refuse(CompilerRefusalKind.DANGLING_REFERENCE, f"{source} -> {target}",
                            "a reconciliation edge between claims that are not both in the graph, "
                            "or from a claim to itself. The reconciliation may only relate claims "
                            "the local passes already built.", detail=[where, round_id])
                continue
            kind = ClaimEdgeKind(raw)
            edge_id = ids.edge_id(self.inquiry_id, kind, source, target)
            if edge_id in seen:
                continue
            seen.add(edge_id)
            self.edges.append(ClaimEdge(edge_id=edge_id, kind=kind, from_claim=source,
                                        to_claim=target, why=str(row.get("why") or "").strip()))

    # ── duplicates ──

    def read_duplicates(self, rows: Sequence[Mapping[str, Any]], *, round_id: str) -> None:
        for index, row in enumerate(rows):
            where = f"reconciliation duplicate {index}"
            claim_id = str(row.get("claim") or "").strip()
            canonical = str(row.get("duplicate_of") or row.get("canonical") or "").strip()
            if claim_id not in self.claims or canonical not in self.claims:
                self.refuse(CompilerRefusalKind.DANGLING_REFERENCE,
                            f"{claim_id} == {canonical}",
                            "a duplicate mapping naming a claim that is not in the graph.",
                            detail=[where, round_id])
                continue
            if claim_id == canonical:
                self.refuse(CompilerRefusalKind.DUPLICATE_POINTS_AT_ITSELF, claim_id,
                            "a claim said to duplicate itself. It would remove the claim from the "
                            "graph while looking like an entry in it.", detail=[where, round_id])
                continue
            if self.claims[claim_id].claim_kind is not self.claims[canonical].claim_kind:
                # THE MERGE THAT DESTROYS THE DISTINCTION. A quality, the effect it produces and a
                # comparison between two such effects are three claims with three warrants, and
                # "they say the same thing" is exactly how they get fused into one.
                self.refuse(CompilerRefusalKind.UNKNOWN_CLAIM_KIND, claim_id,
                            f"a {self.claims[claim_id].claim_kind.value!r} claim was called a "
                            f"duplicate of a {self.claims[canonical].claim_kind.value!r} one. Two "
                            f"claims of different kinds are two readings of the same words; merging "
                            f"them discards whichever arrived second along with its kind.",
                            detail=[where, round_id])
                continue
            self.duplicates.append(DuplicateClaim(
                claim_id=claim_id, canonical_id=canonical, round_id=round_id,
                why=str(row.get("why") or "").strip()
                    or "the reconciliation gave no reason; recorded as stated rather than invented"))

    # ── claims of its own ──

    def read_claims(self, rows: Sequence[Mapping[str, Any]], *, round_id: str) -> None:
        for index, row in enumerate(rows):
            where = f"reconciliation claim {index}"
            found = contracts.geometry_keys_in(row)
            if found:
                self.refuse(CompilerRefusalKind.GEOMETRY_IN_A_READING, ", ".join(found),
                            "a reconciled claim may not carry geometry, a region id or a "
                            "confidence. Dropped rather than stripped.", detail=[where, round_id])
                continue
            text = str(row.get("text") or "").strip()
            if not text:
                continue
            named = [str(p).strip() for p in row.get("inferred_from") or () if str(p).strip()]
            parents = [p for p in named if p in self.claims]
            for bad in [p for p in named if p not in self.claims]:
                self.refuse(CompilerRefusalKind.DANGLING_REFERENCE, bad,
                            "the reconciliation built a claim on a parent that is not in the "
                            "graph — either it invented the id, or the parent was refused.",
                            detail=[where, text[:120]])
            if not parents:
                self.refuse(CompilerRefusalKind.INFERENCE_WITHOUT_PARENT, text[:120],
                            "a reconciliation claim that names no parent that resolves. It has no "
                            "atoms behind it and nothing to follow from, which is an assertion "
                            "wearing an inference's clothes.", detail=[where, round_id])
                continue
            if len({self.group_of.get(p, "") for p in parents}) < 2:
                self.refuse(CompilerRefusalKind.RECONCILIATION_ADDED_LOCAL_CONTENT, text[:120],
                            "a cross-batch claim whose parents all come from one batch. That batch "
                            "had this material in front of it and did not build this claim, so "
                            "adding it here is the reconciliation making an ordinary claim with no "
                            "atoms behind it rather than finding one that crosses.",
                            detail=[where, round_id])
                continue

            kind = self._kind(row, where)
            if kind is None:
                continue
            demand = self._demand(row, kind, where)
            status = self._status(row, where)
            scope = self._scope(row, kind, parents, where)
            claim_id = ids.claim_id(self.inquiry_id, kind, text)
            if claim_id in self.claims or any(c.claim_id == claim_id for c in self.added):
                continue
            self.added.append(ClaimNode(
                claim_id=claim_id, text=text, claim_kind=kind,
                subject=str(row.get("subject") or "").strip(),
                predicate=str(row.get("predicate") or "").strip(),
                object=str(row.get("object") or "").strip(),
                # A COMPILER INFERENCE, and it says so. The parents carry the anchoring; borrowing
                # their source pointers would make a derived claim look source-anchored.
                sources=[SourcePointer(source_type=SourceType.COMPILER_INFERENCE,
                                       source_id="relation_architect/cross_batch_reconciliation",
                                       text=text)],
                image_scope=scope, epistemic_demand=demand, status=status,
                inferred_from=parents, atom_refs=[],
                note=str(row.get("note") or "").strip()))

    def _kind(self, row: Mapping[str, Any], where: str) -> Optional[ClaimKind]:
        raw = str(row.get("kind") or row.get("claim_kind") or "").strip()
        if raw and raw not in set(contracts.closed_set("claim_kinds")):
            self.refuse(CompilerRefusalKind.UNKNOWN_CLAIM_KIND, raw,
                        f"not one of {list(contracts.closed_set('claim_kinds'))}. Dropped rather "
                        f"than filed under `unknown`, which means something else.", detail=[where])
            return None
        return ClaimKind(raw) if raw else ClaimKind.UNKNOWN

    def _demand(self, row: Mapping[str, Any], kind: ClaimKind, where: str) -> DemandKind:
        raw = str(row.get("demand") or row.get("epistemic_demand") or "").strip()
        if raw and raw not in {d.value for d in DemandKind}:
            self.refuse(CompilerRefusalKind.UNKNOWN_DEMAND_KIND, raw,
                        "not a declared demand. Read as `interpretive`, the only direction with no "
                        "way to overstate.", detail=[where])
            raw = ""
        demand = DemandKind(raw) if raw else DemandKind.INTERPRETIVE
        forbidden = _FORBIDDEN_DEMANDS.get(kind)
        if forbidden and demand in forbidden:
            corrected = (DemandKind.SOURCED if kind is ClaimKind.HISTORICAL_OR_SOURCED
                         else DemandKind.INTERPRETIVE)
            self.refuse(CompilerRefusalKind.MEASURED_STATUS_CLAIMED, demand.value,
                        f"a {kind.value!r} claim may not ask for a measurement. Corrected DOWNWARD "
                        f"to {corrected.value!r} and recorded.", detail=[where])
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
                        "not a declared claim status. Read as `uncertain`.", detail=[where])
            return ClaimStatus.UNCERTAIN
        return ClaimStatus(raw) if raw else ClaimStatus.INTERPRETIVE

    def _scope(self, row: Mapping[str, Any], kind: ClaimKind, parents: Sequence[str],
               where: str) -> ImageScope:
        raw = str(row.get("image_scope") or "").strip()
        if raw in {s.value for s in ImageScope}:
            scope = ImageScope(raw)
        else:
            scopes = {self.claims[p].image_scope for p in parents if p in self.claims}
            scope = next(iter(scopes)) if len(scopes) == 1 else ImageScope.CORPUS
        if kind is ClaimKind.COMPARISON and scope is ImageScope.ONE_IMAGE:
            self.refuse(CompilerRefusalKind.IMAGE_SCOPE_CORRECTED, "one_image",
                        "a comparison scoped to one image. One observation typed as a corpus "
                        "tendency is the cheapest way to manufacture a finding, so the scope was "
                        "widened to `corpus` and the correction recorded.", detail=[where])
            return ImageScope.CORPUS
        return scope


def resolve_duplicates(claims: Mapping[str, ClaimNode], mappings: Sequence[DuplicateClaim]
                       ) -> Tuple[Dict[str, str], List[DuplicateClaim], List[str]]:
    """The canonical mapping, followed to a fixpoint, with cycles refused rather than broken.

    `a duplicates b` and `b duplicates c` means `a` and `b` both resolve to `c`. A cycle means the
    reconciliation said each of two claims is the other's duplicate, and there is no fact of the
    matter about which survives — so the whole cycle is dropped from the mapping and both claims
    stay, which is the outcome that loses nothing.
    """
    direct: Dict[str, str] = {}
    kept: List[DuplicateClaim] = []
    notes: List[str] = []
    for entry in mappings:
        if entry.claim_id in direct or entry.claim_id not in claims \
                or entry.canonical_id not in claims:
            continue
        direct[entry.claim_id] = entry.canonical_id
        kept.append(entry)

    resolved: Dict[str, str] = {}
    for start in list(direct):
        # A ring dropped below removes several entries at once, so a later start may already be
        # gone. Checked rather than assumed: reading a popped key here raised, and the failure was
        # a `KeyError` out of the middle of a merge rather than a cycle reported as one.
        if start not in direct:
            continue
        seen, node = [start], direct[start]
        while node in direct and node not in seen:
            seen.append(node)
            node = direct[node]
        if node in seen:
            notes.append(f"a cycle of {len(seen)} duplicate mapping(s) was dropped: each claim was "
                         f"said to duplicate another in the ring, so none of them can be the one "
                         f"that survives. Every claim in the ring was kept.")
            for member in seen:
                direct.pop(member, None)
            continue
        resolved[start] = node
    kept = [e for e in kept if e.claim_id in resolved]
    return resolved, kept, notes


def matrix_for(groups: Sequence[str], rounds: Sequence[Sequence[str]],
               outcomes: Mapping[Tuple[str, ...], ReconciliationRound],
               *, unscheduled_reason: str = NOT_SCHEDULED) -> List[ComparisonPair]:
    """The coverage matrix: every pair of groups, and the round that actually compared them.

    Built from every pair up front rather than accumulated as rounds complete. A pair that was never
    scheduled and a pair whose round failed are both PRESENT and differ only in their reason —
    accumulating would make a pair nobody thought of indistinguishable from one that was tried.
    """
    order = {name: i for i, name in enumerate(groups)}
    covered: Dict[Tuple[str, str], ReconciliationRound] = {}
    for members in rounds:
        entry = outcomes.get(tuple(members))
        if entry is None or entry.outcome is not PassOutcome.COMPLETED:
            continue
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                key = (a, b) if order.get(a, 0) < order.get(b, 0) else (b, a)
                covered.setdefault(key, entry)

    attempted: Set[Tuple[str, str]] = set()
    for members in rounds:
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                attempted.add((a, b) if order.get(a, 0) < order.get(b, 0) else (b, a))

    out: List[ComparisonPair] = []
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            key = (groups[i], groups[j])
            entry = covered.get(key)
            if entry is not None:
                out.append(ComparisonPair(left_batch_id=key[0], right_batch_id=key[1],
                                          round_id=entry.round_id, examined=True))
            else:
                out.append(ComparisonPair(
                    left_batch_id=key[0], right_batch_id=key[1], examined=False,
                    reason=ROUND_FAILED if key in attempted else unscheduled_reason))
    return out


def group_capacity(sizes: Mapping[str, int], *, room: int, share: int) -> int:
    """How many groups may share one request, sized against the LARGEST of them.

    Conservative on purpose: a capacity derived from the average would schedule a round of the four
    biggest groups and discover at send time that it does not fit, and the honest options at that
    point are both bad — split the round and lose the pair coverage it was scheduled for, or send it
    and take the 413 this lane exists to prevent. Sizing against the largest means every round the
    schedule produces fits by construction.
    """
    costs = sorted(sizes.values(), reverse=True)
    total, admitted = 0, 0
    for cost in costs:
        if total + cost > room:
            break
        total += cost
        admitted += 1
    return admitted


__all__ = ["PRODUCER", "SYSTEM_PROMPT", "NOT_SCHEDULED", "NOT_REACHED", "ROUND_FAILED",
           "claim_card", "build_prompt", "fixed_prompt_text", "Reconciliation",
           "resolve_duplicates", "matrix_for", "group_capacity"]
