"""
HARNESS-002D §5 — one verdict per claim, and the receipt that can never produce a supported one.

Phase 1's honest answer for almost every claim is one of two things, and the difference between
them is the whole reason there are six outcomes rather than "supported / not":

    interpretive_only   it was looked at, and nothing measurable bears on it
    not_investigated    nobody asked

A reader deciding whether to trust an answer needs both. Collapsing them would let a claim nothing
ever examined sit in the same column as one that was examined and found to be a reading.

WHAT A RECEIPT CAN AND CANNOT DO. A capability receipt proves that an operational route was
selected and invoked. It is not a finding, and in Phase 1 it is explicitly a stand-in, so it moves a
claim from `not_investigated` to `unresolved` — from "nobody asked" to "we asked and nothing came
back that bears on it" — and no further. The two supported outcomes require an EVIDENCE object, and
the schema refuses a verdict that claims one without citing it, so this is checked in two places
that cannot both be edited by accident.

THE OTHER THREE ARE IMPLEMENTED, NOT DECLARED. `supported_by_evidence`, `partially_supported` and
`contradicted` are unreachable in Phase 1 because nothing mints evidence. They are still written and
still tested — against hand-made evidence — because an outcome that exists only in an enum is one
nobody has checked the logic for, and Phase 2's first act is to make one of them reachable.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from backend.schemas.inquiry_session import (CapabilityReceipt, ClaimVerdict, ClaimVerdictOutcome,
                                             ReceiptStatus, SemanticInquirySession)

from . import ids

PRODUCER = "inquiry_session/judge-v1"

#: Demands nothing measured can settle, whatever ran. A claim asking to be READ rather than measured
#: is `interpretive_only` even with a receipt against it, because the receipt was never the kind of
#: thing that could have settled it.
_NEVER_MEASURABLE = ("interpretive", "imagined")

#: Receipt statuses meaning an instrument was there and produced nothing usable, versus statuses
#: meaning there was no instrument. The two lead to different verdicts and different advice.
_RAN_AND_GAVE_NOTHING = (ReceiptStatus.SIMULATED, ReceiptStatus.EMPTY, ReceiptStatus.REFUSED)
_NOTHING_TO_RUN = (ReceiptStatus.UNAVAILABLE, ReceiptStatus.CAPABILITY_GAP)


def _observables_for(graph: Mapping[str, Any], claim_id: str) -> List[Mapping[str, Any]]:
    return [o for o in (graph.get("observables") or ())
            if isinstance(o, Mapping) and str(o.get("claim_id") or "") == claim_id]


def _evidence_for(evidence: Sequence[Mapping[str, Any]], claim_id: str) -> List[Mapping[str, Any]]:
    out = []
    for item in evidence:
        if not isinstance(item, Mapping):
            continue
        refs = [str(r) for r in (item.get("claim_refs") or ())]
        if claim_id in refs and item.get("usable_as_evidence") is True:
            out.append(item)
    return out


def _verdict_from_evidence(items: Sequence[Mapping[str, Any]]) -> Optional[str]:
    """The three outcomes that need an evidence object. Unreachable in Phase 1; written anyway."""
    stances = {str(i.get("stance") or i.get("verdict") or "supports") for i in items}
    if stances == {"refutes"}:
        return ClaimVerdictOutcome.CONTRADICTED
    if "refutes" in stances or "complicates" in stances or "inconclusive" in stances:
        return ClaimVerdictOutcome.PARTIALLY_SUPPORTED
    return ClaimVerdictOutcome.SUPPORTED_BY_EVIDENCE


def judge_claim(claim: Mapping[str, Any], *, session_id: str, graph: Mapping[str, Any],
                receipts: Sequence[CapabilityReceipt],
                evidence: Sequence[Mapping[str, Any]]) -> ClaimVerdict:
    claim_id = str(claim.get("claim_id") or "")
    demand = str(claim.get("epistemic_demand") or "")
    observables = _observables_for(graph, claim_id)
    observable_ids = {str(o.get("observable_id") or "") for o in observables}
    mine = [r for r in receipts if r.request_ref in observable_ids]
    supporting = _evidence_for(evidence, claim_id)

    verdict = dict(verdict_id=ids.verdict_id(session_id, claim_id), claim_ref=claim_id,
                   receipt_refs=[r.receipt_id for r in mine])

    if supporting:
        return ClaimVerdict(
            outcome=_verdict_from_evidence(supporting),
            evidence_refs=[str(e.get("evidence_id") or "") for e in supporting],
            why="an evidence object cites this claim and is usable as evidence",
            **verdict)

    if demand in _NEVER_MEASURABLE:
        return ClaimVerdict(
            outcome=ClaimVerdictOutcome.INTERPRETIVE_ONLY,
            why=(f"this claim asks to be {demand}, not measured. No instrument settles it, and it "
                 f"is not the weaker for that — it is a different kind of claim."),
            **verdict)

    if any(r.status in _RAN_AND_GAVE_NOTHING for r in mine):
        simulated = [r for r in mine if r.status is ReceiptStatus.SIMULATED]
        return ClaimVerdict(
            outcome=ClaimVerdictOutcome.UNRESOLVED,
            why=("an operational route was selected and invoked, and what came back does not bear "
                 "on the claim" + (" — the receipt is a declared simulation, which proves the route "
                                   "ran and nothing else" if simulated else "")),
            **verdict)

    if any(r.status in _NOTHING_TO_RUN for r in mine):
        return ClaimVerdict(
            outcome=ClaimVerdictOutcome.NOT_INVESTIGATED,
            why=("nothing bound to this deployment can produce what this claim would need, so "
                 "nothing was attempted and nothing was learned about it"),
            **verdict)

    if not observables:
        return ClaimVerdict(
            outcome=ClaimVerdictOutcome.NOT_INVESTIGATED,
            why="the compiler declared no observable for this claim; there was nothing to ask",
            **verdict)

    return ClaimVerdict(
        outcome=ClaimVerdictOutcome.NOT_INVESTIGATED,
        why=(f"{len(observables)} observable(s) were declared for this claim and none was "
             f"invoked. Phase 1 spends its one capability attempt on the fork a person settled."),
        **verdict)


def judge(session: SemanticInquirySession) -> List[ClaimVerdict]:
    """A verdict for EVERY claim, including the ones nobody looked at.

    Judging only what was investigated would make a session's verdict list a list of its successes,
    and the claims that quietly received no attention would be the ones that disappeared.
    """
    graph = session.graph if isinstance(session.graph, dict) else {}
    return [judge_claim(c, session_id=session.session_id, graph=graph,
                        receipts=session.capability_receipts, evidence=session.evidence)
            for c in (graph.get("claims") or ()) if isinstance(c, Mapping) and c.get("claim_id")]


def tally(verdicts: Sequence[ClaimVerdict]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for v in verdicts:
        counts[v.outcome.value] = counts.get(v.outcome.value, 0) + 1
    return counts


__all__ = ["PRODUCER", "judge", "judge_claim", "tally"]
