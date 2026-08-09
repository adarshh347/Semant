"""
HARNESS-002B §6 — the read projections a workbench needs, derived and never stored.

WHY DERIVED. Everything here is a function of the event log. Storing a projection beside the log
would create a second thing that can be wrong, and the one that would be wrong is the one people
look at: a UI reads the projection, not the events, so a drift between them is invisible exactly
where it matters. Derivation costs a list comprehension and buys the guarantee that what a person
sees came from what actually happened.

THIS IS NOT A SECOND EVIDENCE LOG. Nothing here holds a mark, a percept, a receipt or a
measurement. Interaction events sit BESIDE the goal engine's `InquiryRun` events and reference
graph and run objects by id. A projection that inlined a result would become a place where a
result could be described differently from where it is defined, and the difference would be
unfalsifiable because nobody would know which was the copy.

THE ONE THAT DOES REAL WORK. `why_paused` exists because "awaiting_user" is not an explanation. A
person returning to a session needs the fork, the consequence of each way out of it, and the reason
this system could not settle it alone — and that last part is the policy's own recorded sentence,
not a re-derivation of it.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.schemas.inquiry_interaction import (DecisionRecord, DecisionRequest, EventKind,
                                                 InquiryInteractionState, InteractionRefusal,
                                                 SessionState, UserAmendment)
from backend.services.inquiry_interaction import machine as mach


def open_decision(state: InquiryInteractionState) -> Optional[DecisionRequest]:
    """The question the person is being asked, or None. The single source for "is this waiting?"."""
    return state.open_decision


def status(state: InquiryInteractionState) -> Dict[str, Any]:
    """The scalars a client polls: what state, which revision, and whether it may answer.

    `answerable` is both conditions, not one — waiting AND naming something to answer. `run_store`
    holds the same rule for the Director's runs, because either alone is a session that would
    answer into a void.
    """
    return {
        "session_id": state.session_id,
        "inquiry_id": state.inquiry_id,
        "mode": state.mode.value,
        "state": state.state.value,
        "paused_from": state.paused_from.value if state.paused_from else "",
        "revision": state.revision,
        "answerable": bool(state.state is SessionState.AWAITING_USER and state.open_decision_id),
        "open_decision_id": state.open_decision_id,
        "pending": len(state.pending),
        "graph_hash": state.graph.graph_hash,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
    }


def why_paused(state: InquiryInteractionState) -> Dict[str, Any]:
    """Why this session is waiting, in the policy's own words, with the way out of it.

    Empty when nothing is open — an empty mapping rather than a sentence like "not paused", so a
    caller branches on presence instead of parsing prose.
    """
    request = state.open_decision
    if request is None:
        return {}
    event = next((e for e in reversed(state.events)
                  if e.kind is EventKind.DECISION_REQUESTED
                  and e.decision_id == request.decision_id), None)
    return {
        "decision_id": request.decision_id,
        "kind": request.kind.value,
        "question": request.question,
        "why_now": request.why_now,
        # The policy's recorded reason, not a re-derivation. Re-deriving it here would create a
        # second explanation that could disagree with the one in the record.
        "policy_reason": event.reason if event else "",
        "pause_class": str((event.payload.get("pause_class") if event else "") or ""),
        "paused_from": state.paused_from.value if state.paused_from else "",
        "affected_refs": list(request.affected_refs),
        "allow_free_text": request.allow_free_text,
        "options": [{"option_id": o.option_id, "label": o.label, "consequence": o.consequence,
                     "recommended": o.recommended, "reversible": o.reversible,
                     "authorial": o.authorial, "accepts_to_ledger": o.accepts_to_ledger}
                    for o in request.options],
    }


def decisions(state: InquiryInteractionState) -> List[Dict[str, Any]]:
    """Every fork this session reached, in order, INCLUDING the ones nobody was asked about.

    Auto decisions are here beside the answered ones and carry `by` = `policy`. That is the whole
    content of "auto mode means no interruption, not invisible agency": if this list showed only
    what a person answered, an uninterrupted session would look like a session with no decisions
    in it.
    """
    by_decision: Dict[str, DecisionRecord] = {}
    for record in state.records:
        by_decision[record.decision_id] = record          # last record wins; they are appended
    out: List[Dict[str, Any]] = []
    for request in state.requests:
        record = by_decision.get(request.decision_id)
        out.append({
            "decision_id": request.decision_id,
            "kind": request.kind.value,
            "question": request.question,
            "why_now": request.why_now,
            "affected_refs": list(request.affected_refs),
            "options": [{"option_id": o.option_id, "label": o.label,
                         "consequence": o.consequence, "recommended": o.recommended}
                        for o in request.options],
            "formatter": request.formatter,
            "settled": record is not None,
            "outcome": record.outcome if record else "",
            "by": record.actor.value if record else "",
            "chosen_option_id": record.chosen_option_id if record else "",
            "alternatives": list(record.alternatives) if record else [],
            "reason": record.reason if record else "",
            "amendment_ids": list(record.amendment_ids) if record else [],
            "at": record.at if record else request.created_at,
            "revision": record.revision if record else request.revision,
        })
    return out


def amendments(state: InquiryInteractionState) -> List[Dict[str, Any]]:
    """What the person authored, attributed to them and standing beside what it references.

    `epistemic_status` is deliberately absent from this projection and there is no field it could
    come from. A UI rendering an amendment has nothing to read that would let it print a kind of
    knowing next to a person's opinion.
    """
    return [{
        "amendment_id": a.amendment_id,
        "target_ref": a.target_ref,
        "decision_id": a.decision_id,
        "relation": a.relation.value,
        "text": a.text,
        "actor": a.actor.value,
        "at": a.at,
    } for a in state.amendments]


def changed_refs(state: InquiryInteractionState) -> List[Dict[str, Any]]:
    """Which graph objects a settled decision changed, and by whose hand.

    The question a workbench asks to draw the causal arrow from an answer to the part of the graph
    it moved: "the person's answer changes the remaining graph and that causal change is visible"
    is a phase gate, and this is the projection that makes it drawable rather than asserted.
    """
    out: List[Dict[str, Any]] = []
    for record in state.records:
        request = state.request(record.decision_id)
        if request is None or record.outcome in (mach.OUTCOME_UNRESOLVED, mach.OUTCOME_DEFERRED):
            continue
        chosen = request.option(record.chosen_option_id) if record.chosen_option_id else None
        refs = list(chosen.affects_refs) if chosen and chosen.affects_refs \
            else list(request.affected_refs)
        for ref in refs:
            out.append({"ref": ref, "decision_id": record.decision_id,
                        "outcome": record.outcome, "by": record.actor.value,
                        "option_id": record.chosen_option_id, "at": record.at})
    return out


def refusals(state: InquiryInteractionState) -> List[Dict[str, Any]]:
    """Everything produced that did not become part of the session.

    Surfaced rather than swallowed for the reason the inquiry frame keeps its own refusals: the
    refusal rate is the only observable that says whether a formatter or a candidate producer can
    be trusted, and a silent drop hides exactly the cases worth counting.
    """
    return [r.model_dump() for r in state.refusals]


def trace(state: InquiryInteractionState) -> List[Dict[str, Any]]:
    """The chronological history, thin — kind, actor, reason, refs. Not the payloads.

    A trace view that inlined every payload would be the whole session twice, and the second copy
    is the one a reader would skim.
    """
    return [{"seq": e.seq, "kind": e.kind.value, "actor": e.actor.value, "at": e.at,
             "revision": e.revision, "decision_id": e.decision_id, "refs": list(e.refs),
             "reason": e.reason} for e in state.events]


def view(state: InquiryInteractionState) -> Dict[str, Any]:
    """One mapping a frontend can render whole. Composed of the projections above, not of new work."""
    return {
        "schema_version": state.schema_version,
        "status": status(state),
        "open_decision": (open_decision(state).model_dump(mode="json")
                          if open_decision(state) else None),
        "why_paused": why_paused(state),
        "decisions": decisions(state),
        "amendments": amendments(state),
        "changed_refs": changed_refs(state),
        "deferred": list(state.deferred),
        "refusals": refusals(state),
        "trace": trace(state),
    }


__all__ = ["open_decision", "status", "why_paused", "decisions", "amendments", "changed_refs",
           "refusals", "trace", "view"]
