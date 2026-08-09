"""
HARNESS-002D — the wire projection: one session, in the shape the workbench actually reads.

WHY THIS EXISTS AT ALL. Three lanes named overlapping things in parallel and the names did not all
land in the same place. Lane A's compiler writes `success_when`; Lane C's reader looks for
`success_condition`. Lane A writes `sources[]`; Lane C reads one `source_span`. Lane A's remainder
item has `term`/`why`; Lane C's has `text`/`why_unresolved`. None of those is a disagreement about
what the thing IS, and none of them is worth reopening a merged lane over.

So the divergence is resolved HERE, in one function per object, with the two spellings side by side
where a reader can check them. The alternative — renaming fields inside a merged lane — would have
edited two packages this lane does not own to fix a problem that only exists at the boundary
between them.

WHAT THIS MODULE MAY NOT DO. It may not strengthen anything. No status is promoted, no receipt
becomes evidence, no absent value becomes a confident default, and nothing is invented to fill a
field the producing lane left empty — an empty string reaches the client as an empty string and
renders as unknown, which is the correct outcome and the one the workbench was built to show.

THE ONE THING IT DERIVES. `availability` on an observable. Lane A does not declare it, because Lane
A does not know what any deployment can run; this lane binds the capability adapter and therefore
does know. An observable asking for a class the adapter cannot serve is a `capability_gap`, and
saying so is the difference between "nothing has run yet" and "nothing can".
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from backend.schemas.inquiry_session import SemanticInquirySession
from backend.services.inquiry_interaction import machine, projections

from . import ids

PRODUCER = "inquiry_session/view-v1"


def _m(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> List[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _s(value: Any) -> str:
    return str(value) if isinstance(value, (str, int, float)) and value is not None else ""


# ── the graph ────────────────────────────────────────────────────────────────

def image_ref_view(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """`image_url` is the same string as `image_ref`, under the name the thumbnail reads.

    Not a duplicate for symmetry: the workbench renders `image_url` and falls back to a blank tile
    without it, so a session with perfectly good images would show an empty grid. One assignment
    here is cheaper than a component edit in a merged lane.
    """
    url = _s(raw.get("image_ref"))
    return {"post_id": _s(raw.get("post_id")), "title": _s(raw.get("title")),
            "image_ref": url, "image_url": url, "note": _s(raw.get("note"))}


def reading_view(raw: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """The scene reading, with the model lifted out of its receipt.

    `status` is passed through UNCHANGED even when the compiler over-declared it. The client caps it
    to `interpretive` and shows what it capped — a cap applied here as well would hide the upstream
    defect from the only surface built to display it.
    """
    reading = _m(raw)
    receipt = _m(reading.get("provenance"))
    return {
        "text": _s(reading.get("text")),
        "status": _s(reading.get("status")),
        "source": _s(reading.get("source")),
        "model": _s(receipt.get("model")),
        "blocks": [{"block_id": _s(b.get("block_id")), "kind": _s(b.get("kind")),
                    "text": _s(b.get("text")), "image_refs": [_s(i) for i in _list(b.get("image_refs"))]}
                   for b in _list(reading.get("blocks")) if isinstance(b, Mapping)],
        "provenance": receipt,
    }


def claim_view(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """One claim. `source_span` is the first pointer; `source_spans` is all of them.

    The client reads one and the compiler may produce several. Emitting only the first would make
    the wire lossy in a way nothing downstream could detect, so both are here and the singular is
    documented as the client's view of the plural rather than as the truth.
    """
    spans = [source_span_view(s) for s in _list(raw.get("sources")) if isinstance(s, Mapping)]
    scope = raw.get("image_scope")
    return {
        "claim_id": _s(raw.get("claim_id")),
        "text": _s(raw.get("text")),
        # Lane C reads `claim_kind ?? kind`; both are emitted so neither spelling is load-bearing.
        "claim_kind": _s(raw.get("claim_kind")),
        "kind": _s(raw.get("claim_kind")),
        "status": _s(raw.get("status")),
        "subject": _s(raw.get("subject")),
        "predicate": _s(raw.get("predicate")),
        "object": _s(raw.get("object")),
        "vocabulary": _s(raw.get("vocabulary")),
        "source_span": spans[0] if spans else None,
        "source_spans": spans,
        # Lane A's scope is ONE enum ("all images", "this image"); the client reads a list.
        "image_scope": [_s(scope)] if scope else [],
        "epistemic_demand": _s(raw.get("epistemic_demand")),
        "inferred_from": [_s(i) for i in _list(raw.get("inferred_from"))],
        "note": _s(raw.get("note")),
        # No confidence is declared anywhere upstream. Null, not a number nobody computed.
        "confidence": None,
        # Every claim on this graph was written by the compiler. A person's contribution arrives as
        # an amendment standing beside a claim, never as an edit of one — Lane B's law.
        "author": "model",
    }


def source_span_view(raw: Mapping[str, Any]) -> Dict[str, Any]:
    span = raw.get("span")
    start, end = (span[0], span[1]) if isinstance(span, (list, tuple)) and len(span) == 2 \
        else (None, None)
    return {"origin": _s(raw.get("source_type")), "text": _s(raw.get("text")),
            "start": start, "end": end, "source_id": _s(raw.get("source_id"))}


def claim_edge_view(raw: Mapping[str, Any]) -> Dict[str, Any]:
    return {"edge_id": _s(raw.get("edge_id")), "from_claim": _s(raw.get("from_claim")),
            "to_claim": _s(raw.get("to_claim")),
            # Lane A calls it `kind`; the client calls it `relation`. Same value, both names.
            "relation": _s(raw.get("kind")), "kind": _s(raw.get("kind")),
            "note": _s(raw.get("why"))}


def alternative_view(raw: Mapping[str, Any]) -> Dict[str, Any]:
    classes = [_s(c) for c in _list(raw.get("capability_classes"))]
    return {
        "alternative_id": _s(raw.get("alternative_id")),
        "label": _s(raw.get("label")),
        # Singular for the client, plural kept: an alternative asking for two classes is a real
        # thing the compiler can produce, and collapsing it to the first would silently drop one.
        "capability_class": classes[0] if classes else "",
        "capability_classes": classes,
        "consequence": _s(raw.get("consequence")) or _s(raw.get("description")),
        "recommended": raw.get("recommended") is True,
        # Tri-state on purpose: `null` where no adapter is bound, because "we did not check" and
        # "we checked and it cannot run" must not render alike.
        "available": None,
    }


def observable_view(raw: Mapping[str, Any], *, servable: Sequence[str] = ()) -> Dict[str, Any]:
    """One observable REQUEST, with availability derived from what this deployment can serve."""
    classes = [_s(c) for c in _list(raw.get("capability_classes"))]
    served = set(servable)
    alternatives = [alternative_view(a) for a in _list(raw.get("alternatives"))
                    if isinstance(a, Mapping)]
    for alt in alternatives:
        if served:
            alt["available"] = bool(alt["capability_classes"]) \
                and set(alt["capability_classes"]) <= served

    if not served:
        availability, gap = "unavailable", ("no capability adapter is bound to this deployment, so "
                                            "nothing was checked and nothing could run")
    elif classes and set(classes) <= served:
        availability, gap = "available", ""
    else:
        availability = "capability_gap"
        missing = sorted(set(classes) - served) or ["(the observable names no capability class)"]
        gap = ("nothing bound here can produce: " + ", ".join(missing))

    scope = raw.get("image_scope")
    targets = [_s(t) for t in _list(raw.get("targets"))]
    return {
        "observable_id": _s(raw.get("observable_id")),
        "claim_ref": _s(raw.get("claim_id")),
        "observable_kind": _s(raw.get("observable_kind")),
        "target": ", ".join(t for t in targets if t),
        "targets": targets,
        "image_scope": [_s(scope)] if scope else [],
        "ground_forms": [_s(g) for g in _list(raw.get("ground_forms"))],
        "capability_classes": classes,
        "alternatives": alternatives,
        "success_condition": _s(raw.get("success_when")),
        "ambiguity_condition": _s(raw.get("ambiguous_when")),
        "refusal_condition": _s(raw.get("refused_when")),
        "residual_interpretation": _s(raw.get("remains_interpretive")),
        "availability": availability,
        "gap_reason": gap,
        "note": _s(raw.get("note")),
    }


def remainder_view(raw: Mapping[str, Any], *, inquiry_id: str = "") -> Dict[str, Any]:
    """Lane A's remainder item carries no id. One is minted from its content so the client has a
    stable key and a synthesis can reference it — content-derived, so a replay reproduces it."""
    term = _s(raw.get("term"))
    return {"remainder_id": ids.remainder_id(inquiry_id, term), "text": term,
            "why_unresolved": _s(raw.get("why")),
            "claim_refs": [_s(c) for c in _list(raw.get("claim_refs"))],
            "contributing_capability_classes":
                [_s(c) for c in _list(raw.get("contributing_capability_classes"))]}


def refusal_view(raw: Mapping[str, Any]) -> Dict[str, Any]:
    detail = [_s(d) for d in _list(raw.get("detail"))]
    return {"refusal_id": _s(raw.get("refusal_id")),
            # `kind` is the machine-readable reason; `why` is the sentence. The client shows both
            # under its own two names.
            "reason": _s(raw.get("kind")), "kind": _s(raw.get("kind")),
            "detail": " · ".join([_s(raw.get("why")), *detail]).strip(" ·"),
            "what": _s(raw.get("what")),
            "refs": [_s(raw.get("what"))] if raw.get("what") else []}


def graph_view(graph: Mapping[str, Any], *, servable: Sequence[str] = ()) -> Dict[str, Any]:
    raw = _m(graph)
    inquiry_id = _s(raw.get("inquiry_id"))
    return {
        "schema_version": _s(raw.get("schema_version")),
        "graph_id": _s(raw.get("graph_id")),
        "inquiry_id": inquiry_id,
        # Byte for byte. Every source span indexes into this exact string.
        "prompt": raw.get("prompt") if isinstance(raw.get("prompt"), str) else "",
        "image_refs": [image_ref_view(i) for i in _list(raw.get("image_refs"))
                       if isinstance(i, Mapping)],
        "reading": reading_view(raw.get("reading")),
        "claims": [claim_view(c) for c in _list(raw.get("claims")) if isinstance(c, Mapping)],
        "claim_edges": [claim_edge_view(e) for e in _list(raw.get("claim_edges"))
                        if isinstance(e, Mapping)],
        "observables": [observable_view(o, servable=servable)
                        for o in _list(raw.get("observables")) if isinstance(o, Mapping)],
        "semantic_remainder": [remainder_view(r, inquiry_id=inquiry_id)
                               for r in _list(raw.get("semantic_remainder"))
                               if isinstance(r, Mapping)],
        "refusals": [refusal_view(r) for r in _list(raw.get("refusals"))
                     if isinstance(r, Mapping)],
        "notes": [_s(n) for n in _list(raw.get("notes"))],
        "provenance": _m(raw.get("provenance")),
    }


# ── the deliberation ─────────────────────────────────────────────────────────

#: Lane B's `ResponseKind` → the verb the workbench prints. The record of an AUTO choice has no
#: response behind it, so its action is derived from the outcome instead: `auto_resolved` means an
#: option was selected, by the policy, without asking. Saying `select_option` there is not a
#: flattening — it is what happened; the `decider` column is what makes it different.
_AUTO_ACTION = {"auto_resolved": "select_option", "answered": "select_option",
                "unresolved": "unresolved", "deferred": "skip", "rejected": "reject_all"}


def decision_request_view(request: Mapping[str, Any], *, answered: bool) -> Dict[str, Any]:
    return {
        "decision_id": _s(request.get("decision_id")),
        "session_id": _s(request.get("session_id")),
        "kind": _s(request.get("kind")),
        "question": _s(request.get("question")),
        "why_now": _s(request.get("why_now")),
        "affected_refs": [_s(r) for r in _list(request.get("affected_refs"))],
        "options": [{"option_id": _s(o.get("option_id")), "label": _s(o.get("label")),
                     "consequence": _s(o.get("consequence")),
                     "recommended": o.get("recommended") is True,
                     "reversible": o.get("reversible"),
                     "authorial": o.get("authorial") is True,
                     "accepts_to_ledger": o.get("accepts_to_ledger") is True,
                     "detail": _s(o.get("detail"))}
                    for o in _list(request.get("options")) if isinstance(o, Mapping)],
        "allow_free_text": request.get("allow_free_text") is True,
        "blocking": request.get("blocking") is True,
        "answered": answered,
        "formatter": _s(request.get("formatter")),
        "provenance": _m(request.get("provenance")),
    }


def decision_record_view(entry: Mapping[str, Any], *, labels: Mapping[str, str],
                         free_text: Mapping[str, str]) -> Dict[str, Any]:
    """One settled fork, from Lane B's own `decisions` projection — never re-derived from events."""
    decision_id = _s(entry.get("decision_id"))
    outcome = _s(entry.get("outcome"))
    chosen = _s(entry.get("chosen_option_id"))
    return {
        "record_id": f"rec_{decision_id}" if decision_id else "",
        "decision_id": decision_id,
        "decider": _s(entry.get("by")),
        "action": _AUTO_ACTION.get(outcome, outcome),
        "outcome": outcome,
        "question": _s(entry.get("question")),
        "selected_option_id": chosen,
        "selected_label": _s(labels.get(chosen)),
        "free_text": _s(free_text.get(decision_id)),
        "rationale": _s(entry.get("reason")),
        "affected_refs": [_s(r) for r in _list(entry.get("affected_refs"))],
        "at": entry.get("at") or None,
        "revision": entry.get("revision"),
    }


def trace_view(state: Any) -> List[Dict[str, Any]]:
    """Lane B's chronology, in the client's field names. Thin — kinds, actors, reasons, refs."""
    return [{
        "event_id": _s(e.get("kind")) + f"#{e.get('seq')}",
        "at": e.get("at") or None,
        "actor": _s(e.get("actor")),
        "actor_kind": _s(e.get("actor")),
        "transition": _s(e.get("kind")),
        "reason": _s(e.get("reason")),
        "refs": [_s(r) for r in _list(e.get("refs"))] + (
            [_s(e.get("decision_id"))] if e.get("decision_id") else []),
        "revision": e.get("revision"),
    } for e in projections.trace(state)]


def stage_view(session: SemanticInquirySession) -> List[Dict[str, Any]]:
    """This lane's own ledger, which no other lane has an equivalent of.

    Not folded into `trace`: Lane B's chronology is the history of a DELIBERATION and this is the
    history of the machinery. Merging them would put "the compiler returned nothing" in the same
    list as "the person chose option two".
    """
    return [{"event_id": e.event_id, "stage": e.stage.value, "outcome": e.outcome.value,
             "at": e.at, "revision": e.revision, "detail": e.detail,
             "input_refs": list(e.input_refs), "output_refs": list(e.output_refs)}
            for e in session.stages]


# ── the session ──────────────────────────────────────────────────────────────

def session_view(session: SemanticInquirySession, *,
                 servable_classes: Sequence[str] = ()) -> Dict[str, Any]:
    """One session, as the workbench reads it. The single response body of every route here."""
    interaction = session.interaction
    state = machine.from_dict(interaction) if interaction.get("session_id") else None

    requests: List[Dict[str, Any]] = []
    records: List[Dict[str, Any]] = []
    trace: List[Dict[str, Any]] = []
    why_paused: Dict[str, Any] = {}
    amendments: List[Dict[str, Any]] = []
    changed_refs: List[Dict[str, Any]] = []
    interaction_refusals: List[Dict[str, Any]] = []

    if state is not None:
        settled = {d["decision_id"] for d in projections.decisions(state) if d["settled"]}
        requests = [decision_request_view(r.model_dump(mode="json"),
                                          answered=r.decision_id in settled)
                    for r in state.requests]
        labels = {o["option_id"]: o["label"] for r in requests for o in r["options"]}
        free_text = {r.decision_id: r.free_text for r in state.responses if r.free_text}
        records = [decision_record_view(d, labels=labels, free_text=free_text)
                   for d in projections.decisions(state) if d["settled"]]
        trace = trace_view(state)
        why_paused = projections.why_paused(state)
        amendments = projections.amendments(state)
        changed_refs = projections.changed_refs(state)
        interaction_refusals = projections.refusals(state)

    return {
        "schema_version": session.schema_version,
        "session_id": session.session_id,
        "inquiry_id": session.inquiry_id,
        "revision": session.revision,
        "state": session.state,
        "mode": session.mode,
        "prompt": session.prompt,
        "posts": [p.model_dump(mode="json") for p in session.posts],
        "graph": graph_view(session.graph, servable=servable_classes),
        "frame": session.frame,
        "decision_requests": requests,
        "decision_records": records,
        "why_paused": why_paused,
        "amendments": amendments,
        "changed_refs": changed_refs,
        "capability_receipts": [r.model_dump(mode="json") for r in session.capability_receipts],
        # Empty in Phase 1, and present so that "nothing was measured" is a visible empty list
        # rather than a missing key somebody reads as not-yet-populated.
        "evidence": list(session.evidence),
        "verdicts": [v.model_dump(mode="json") for v in session.verdicts],
        "synthesis": session.synthesis.model_dump(mode="json") if session.synthesis else None,
        "stages": stage_view(session),
        "trace": trace,
        "gaps": list(session.gaps),
        "refusals": [refusal_view(r) for r in session.refusals] + interaction_refusals,
        "stop_reason": session.stop_reason,
        "error": session.error,
        "provenance": session.provenance.model_dump(mode="json"),
    }


__all__ = ["PRODUCER", "session_view", "graph_view", "claim_view", "observable_view",
           "alternative_view", "remainder_view", "refusal_view", "reading_view",
           "decision_request_view", "decision_record_view", "trace_view", "stage_view"]
