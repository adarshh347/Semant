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


# ── the dissolution, projected (HARNESS-003D) ────────────────────────────────
#
# Lane A's council writes four objects nothing outside the backend could read: the source ledger,
# the atoms, the coverage dispositions and the per-pass receipts. Lane C wrote normalisers for the
# first three against a shape nobody had produced yet, and `graph_view` did not send them — which is
# `disconnected_artifact` exactly, and the phase's central artifact at that. A coverage ledger the
# person cannot see is a coverage ledger that only the tests benefit from.

def source_unit_view(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """One piece of source prose. `kind` here, `source_type` there — both are emitted.

    Lane A named the field `kind` and Lane C's normaliser reads `source_type`. The same divergence
    this module already resolves for `success_when`/`success_condition`, and resolved the same way:
    both spellings on the wire, with the disagreement visible in one place rather than settled by
    renaming a field inside a merged lane.
    """
    span = raw.get("span")
    start, end = (span[0], span[1]) if isinstance(span, (list, tuple)) and len(span) == 2 \
        else (None, None)
    kind = _s(raw.get("kind"))
    return {
        "source_unit_id": _s(raw.get("source_unit_id")),
        "kind": kind,
        "source_type": kind,
        "source_ref": _s(raw.get("source_ref")),
        # BYTE FOR BYTE. The span indexes into the prompt, so a projection that trimmed this would
        # misalign every highlight over the person's own words.
        "exact_quote": raw.get("exact_quote") if isinstance(raw.get("exact_quote"), str) else "",
        "span": [start, end] if start is not None and end is not None else None,
        "start": start,
        "end": end,
        "image_refs": [_s(i) for i in _list(raw.get("image_refs"))],
        "block_kind": _s(raw.get("block_kind")),
        "ordinal": raw.get("ordinal") if isinstance(raw.get("ordinal"), int) else None,
        # Derived from the kind rather than read: `prompt_clause` IS the person's, and a field a
        # model could fill would be the one attribution error nothing downstream can detect.
        "author": "user" if kind == "prompt_clause" else "scene_theorist",
        "note": _s(raw.get("note")),
    }


def atom_view(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """One semantic atom. Its ceiling and its author travel with it, and neither is strengthened."""
    return {
        "atom_id": _s(raw.get("atom_id")),
        "text": _s(raw.get("text")),
        "unit_kind": _s(raw.get("unit_kind")),
        "source_unit_ids": [_s(s) for s in _list(raw.get("source_unit_ids"))],
        "quotes": [_s(q) for q in _list(raw.get("quotes"))],
        "subject": _s(raw.get("subject")),
        "predicate": _s(raw.get("predicate")),
        "object": _s(raw.get("object")),
        # One enum there, a list here — the same shape `claim_view` gives `image_scope`.
        "image_scope": [_s(raw.get("image_scope"))] if raw.get("image_scope") else [],
        "image_refs": [_s(i) for i in _list(raw.get("image_refs"))],
        # `user` on anything anchored to a prompt clause, and this projection does not touch it.
        # The graph validator freezes it; a view that recomputed it would be a second opinion about
        # whose hypothesis it is.
        "author": _s(raw.get("author")),
        "epistemic_ceiling": _s(raw.get("epistemic_ceiling")),
        "note": _s(raw.get("note")),
        "provenance": _m(raw.get("provenance")),
    }


def coverage_view(raw: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "coverage_id": _s(raw.get("coverage_id")),
        "source_unit_id": _s(raw.get("source_unit_id")),
        "disposition": _s(raw.get("disposition")),
        "refs": [_s(r) for r in _list(raw.get("refs"))],
        "reason": _s(raw.get("reason")),
    }


def capacity_wait_view(raw: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "attempt": raw.get("attempt") if isinstance(raw.get("attempt"), int) else None,
        "seconds": raw.get("seconds") if isinstance(raw.get("seconds"), (int, float)) else None,
        "source": _s(raw.get("source")),
        "detail": _s(raw.get("detail")),
        "taken": raw.get("taken") is not False,
    }


def batch_plan_view(raw: Any) -> Optional[Dict[str, Any]]:
    """How a pass was cut into sendable requests, and what that cost in coverage. HARNESS-003E.

    `None` on a pass that was never partitioned — the ledger and the audit make no request at all,
    and an empty plan on them would say a partition happened and found one batch.

    THE UNEXAMINED PAIRS TRAVEL IN FULL and the dispositions travel as counts. Opposite decisions
    about the same kind of object, for one reason: a pair nobody compared is a relation nobody
    looked for, and "these two were never put in front of the model because the budget stopped the
    run" is a sentence a person can act on. One hundred and eighty `used` atoms is a number. The
    graph itself carries every disposition for anyone who wants them.
    """
    if not isinstance(raw, Mapping):
        return None
    batches = [b for b in _list(raw.get("batches")) if isinstance(b, Mapping)]
    pairs = [p for p in _list(raw.get("pairs")) if isinstance(p, Mapping)]
    dispositions: Dict[str, int] = {}
    for entry in _list(raw.get("dispositions")):
        if isinstance(entry, Mapping):
            key = _s(entry.get("disposition"))
            dispositions[key] = dispositions.get(key, 0) + 1
    sizes = [int(b.get("estimated_prompt_tokens") or 0)
             + int(b.get("requested_completion_tokens") or 0) for b in batches]
    return {
        "plan_id": _s(raw.get("plan_id")),
        "plan_version": _s(raw.get("plan_version")),
        "unit": _s(raw.get("unit")),
        "total_items": raw.get("total_items") if isinstance(raw.get("total_items"), int) else None,
        "batches": len(batches),
        # HARNESS-003F. How many of them were actually sent, apart from how many were planned. A
        # declared scope may permit fewer requests than the partition contains, and one number for
        # both would render a bounded pass as a complete one.
        "batches_sent": (raw.get("batches_sent")
                         if isinstance(raw.get("batches_sent"), int) else None),
        "unsendable_batches": sum(1 for b in batches if b.get("sendable") is False),
        "allowance_tokens": next((b.get("allowance_tokens") for b in batches
                                  if isinstance(b.get("allowance_tokens"), int)), None),
        "largest_request_tokens": max(sizes) if sizes else None,
        "pairs_total": len(pairs),
        "pairs_examined": sum(1 for p in pairs if p.get("examined") is True),
        "unexamined_pairs": [{"left": _s(p.get("left_batch_id")),
                              "right": _s(p.get("right_batch_id")),
                              "reason": _s(p.get("reason"))}
                             for p in pairs if p.get("examined") is not True],
        "rounds": [{"round_id": _s(r.get("round_id")),
                    "index": r.get("index"), "total": r.get("total"),
                    "groups": len(_list(r.get("group_ids"))),
                    "outcome": _s(r.get("outcome")),
                    "added_edges": r.get("added_edges"),
                    "added_claims": r.get("added_claims"),
                    "duplicate_claims": r.get("duplicate_claims"),
                    "detail": _s(r.get("detail"))}
                   for r in _list(raw.get("rounds")) if isinstance(r, Mapping)],
        "dispositions": dispositions,
        "duplicates_merged": len([d for d in _list(raw.get("duplicate_map"))
                                  if isinstance(d, Mapping)]),
        "notes": [_s(n) for n in _list(raw.get("notes"))],
    }


#: HARNESS-003F. The scope record, as the workbench reads it.
#:
#: EVERY SESSION HAS ONE, including a full-coverage one and including a session that died before the
#: compiler ran. The banner is the whole reason: it has to survive onto a completed, exhausted,
#: refused and errored session alike, and a projection that emitted the key only where a graph
#: carried a record would leave a slice that failed in the theorist looking like a full reading.
def execution_scope_view(raw: Any, *, declared_mode: str = "") -> Dict[str, Any]:
    """One scope, from the graph's record where there is one and from the session's word where not.

    THE TWO SOURCES ARE NOT THE SAME CLAIM and the projection says which it used. A record was
    written by a compilation that actually ran and selected; a declared mode is what the request
    asked for and nothing more. `recorded: false` is how a reader tells "this run was bounded and
    here is what it left out" from "this run was ASKED to be bounded and got no further".
    """
    record = raw if isinstance(raw, Mapping) else {}
    mode = _s(record.get("mode")) or _s(declared_mode) or "full"
    exclusions = [e for e in _list(record.get("exclusions")) if isinstance(e, Mapping)]
    slice_mode = mode == "vertical_slice"
    return {
        "mode": mode,
        "recorded": bool(record),
        "scope_version": _s(record.get("scope_version")),
        "purpose": _s(record.get("purpose")),
        "selection_producer": _s(record.get("selection_producer")),
        "allowance_tokens": (record.get("allowance_tokens")
                             if isinstance(record.get("allowance_tokens"), int) else None),
        # THE FIELD THE BANNER IS KEYED ON, and it is False for an unrecorded slice too. A run that
        # asked to be bounded has not produced a complete reading whatever became of it, and
        # defaulting an unrecorded slice to `true` would be the one lie this object exists to stop.
        "full_coverage": (bool(record.get("full_coverage")) if record else not slice_mode),
        "selected_source_units": len(_list(record.get("selected_source_unit_ids"))),
        "deferred_source_units": len(_list(record.get("deferred_source_unit_ids"))),
        "selected_atoms": len(_list(record.get("selected_atom_ids"))),
        "atoms_not_investigated": len(_list(record.get("atoms_not_investigated"))),
        "selected_claims": len(_list(record.get("selected_claim_ids"))),
        "claims_not_investigated": len(_list(record.get("claims_not_investigated"))),
        "relation_batches_allowed": record.get("relation_batches_allowed"),
        "relation_batches_sent": record.get("relation_batches_sent"),
        "operationalizer_batches_allowed": record.get("operationalizer_batches_allowed"),
        "operationalizer_batches_sent": record.get("operationalizer_batches_sent"),
        "reconciliation_rounds_allowed": record.get("reconciliation_rounds_allowed"),
        "reconciliation_rounds_sent": record.get("reconciliation_rounds_sent"),
        # IN FULL, never as a count. The same decision `batch_plan_view` makes about unexamined
        # pairs and for the same reason: a count tells a reader the size of the gap and not where
        # it is, and where it is is the only thing they can act on.
        "exclusions": [{"ref": _s(e.get("ref")), "kind": _s(e.get("kind")),
                        "reason": _s(e.get("reason"))} for e in exclusions],
        "notes": [_s(n) for n in _list(record.get("notes"))],
    }


def pass_view(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """One pass of the council: which mind, what it cost, and how it ended IN ITS OWN WORD.

    `outcome` is passed through unchanged, including `coverage_failed` and `truncated`. This is the
    field the whole lane turns on — a pass that ran out of budget and happened to close its JSON is
    indistinguishable from an honest short one by every other measure — so nothing here maps it onto
    a friendlier neighbour.

    `waited_ms` stays null where nothing waited. Zero would say a pacer answered and reported no
    wait, and a reader deciding whether the account's allowance is the problem needs that apart from
    "nothing paced this run".
    """
    waits = [capacity_wait_view(w) for w in _list(raw.get("capacity_waits"))
             if isinstance(w, Mapping)]
    return {
        "pass_id": _s(raw.get("pass_id")),
        "pass_name": _s(raw.get("pass_name")),
        "outcome": _s(raw.get("outcome")),
        "model": _s(raw.get("model")),
        "provider": _s(raw.get("provider")),
        # SEMANTIC ATTEMPTS AND TRANSPORT ATTEMPTS, apart. One is how many times the pass asked; the
        # other is how many times bytes went on the wire. Merging them would make a rate-limited run
        # read as a pass that could not make up its mind.
        "call_count": raw.get("call_count") if isinstance(raw.get("call_count"), int) else None,
        "transport_attempts": (raw.get("transport_attempts")
                               if isinstance(raw.get("transport_attempts"), int) else None),
        "finish_reasons": [_s(f) for f in _list(raw.get("finish_reasons"))],
        "prompt_tokens": raw.get("prompt_tokens"),
        "completion_tokens": raw.get("completion_tokens"),
        "duration_ms": raw.get("duration_ms"),
        "waited_ms": raw.get("waited_ms"),
        "capacity_waits": waits,
        "inputs": raw.get("inputs") if isinstance(raw.get("inputs"), int) else None,
        "outputs": raw.get("outputs") if isinstance(raw.get("outputs"), int) else None,
        "detail": _s(raw.get("detail")),
        "notes": [_s(n) for n in _list(raw.get("notes"))],
        "batch_plan": batch_plan_view(raw.get("batch_plan")),
    }


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
        # The dissolution, in the order it happened. Empty lists on a v1 graph, and empty is the
        # truth there rather than a missing key a reader would take for not-yet-populated.
        "source_units": [source_unit_view(u) for u in _list(raw.get("source_units"))
                         if isinstance(u, Mapping)],
        "semantic_atoms": [atom_view(a) for a in _list(raw.get("semantic_atoms"))
                           if isinstance(a, Mapping)],
        "coverage": [coverage_view(c) for c in _list(raw.get("coverage"))
                     if isinstance(c, Mapping)],
        "passes": [pass_view(p) for p in _list(raw.get("passes")) if isinstance(p, Mapping)],
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
        # HARNESS-003F. What this compilation was allowed to investigate, and what it therefore did
        # not. `null` on a graph compiled before the contract; the session-level projection is the
        # one that is always present.
        "execution_scope": (execution_scope_view(raw.get("execution_scope"))
                            if isinstance(raw.get("execution_scope"), Mapping) else None),
        # The council's own verdict on its own coverage, computed from the ledger rather than
        # restated — see `coverage_summary`.
        "coverage_summary": coverage_summary(raw),
    }


#: The four dispositions, and which of them mean a source unit SURVIVED into the graph. A unit that
#: is `duplicate_of` another is accounted for; one that is `semantic_remainder` or `refused` is
#: accounted for and NOT represented, which is a different thing again from a unit with no entry.
_REPRESENTED = ("represented_by", "duplicate_of")


def coverage_summary(graph: Mapping[str, Any]) -> Dict[str, Any]:
    """What became of the source prose, in one object a surface can render without arithmetic.

    LOST IS ITS OWN NUMBER, and it is the one this exists for. A unit with no disposition is not a
    remainder — a remainder is a decision, with a reason — it is a unit the compiler dropped, and
    the contract says every unit gets exactly one entry. Those two must never read alike, and a
    surface computing this itself would be free to fold them together on any render site that
    forgot.
    """
    units = [u for u in _list(graph.get("source_units")) if isinstance(u, Mapping)]
    entries = [c for c in _list(graph.get("coverage")) if isinstance(c, Mapping)]
    by_unit = {_s(c.get("source_unit_id")): _s(c.get("disposition")) for c in entries}

    counts: Dict[str, int] = {}
    for disposition in by_unit.values():
        counts[disposition] = counts.get(disposition, 0) + 1
    lost = [_s(u.get("source_unit_id")) for u in units
            if _s(u.get("source_unit_id")) not in by_unit]
    represented = sum(1 for d in by_unit.values() if d in _REPRESENTED)

    return {
        "source_units": len(units),
        "disposed": len(by_unit),
        "represented": represented,
        "by_disposition": counts,
        "lost": lost,
        "lost_count": len(lost),
        "user_units": sum(1 for u in units if _s(u.get("kind")) == "prompt_clause"),
        "reading_units": sum(1 for u in units if _s(u.get("kind")) == "reading_block"),
        # `complete` is the producer's own arithmetic over its own ledger, not a threshold. Null
        # where there is no ledger at all — a v1 graph has no coverage claim to report, and `False`
        # there would accuse a compilation of failing a check it never declared.
        "complete": (len(lost) == 0 and bool(units)) if units else None,
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
    return [attempt_view(e) for e in session.stages]


def attempt_view(e: Any) -> Dict[str, Any]:
    """One stage attempt, as the workbench reads it.

    `event_id` is kept beside `attempt_id` and `detail` beside `summary`: the frontend contract
    predates HARNESS-003B and Lane C is being written in parallel against the old names. Dropping
    them here to be tidy would break a lane that cannot see this change yet, so both spellings are
    served and Lane D retires one.

    `duration_ms` is passed through UNTOUCHED, including when it is null. A projection that
    substituted 0 for an unmeasured stage would put the whole null-duration law back in the one
    place the person actually looks.
    """
    return {
        "attempt_id": e.attempt_id, "event_id": e.attempt_id,
        "stage": e.stage.value, "outcome": e.outcome.value, "sequence": e.sequence,
        "revision": e.revision,
        "queued_at": e.queued_at, "started_at": e.started_at, "completed_at": e.completed_at,
        "at": e.completed_at or e.started_at or e.queued_at,
        "duration_ms": e.duration_ms,
        "role": e.role, "model": e.model, "provider": e.provider,
        "execution_mode": e.execution_mode.value,
        "summary": e.summary, "detail": e.summary,
        "input_refs": list(e.input_refs), "output_refs": list(e.output_refs),
        "input_counts": dict(e.input_counts), "output_counts": dict(e.output_counts),
        "counts_line": e.counts_line(),
        "call_topology": e.call_topology, "planned_calls": e.planned_calls,
        "actual_calls": e.actual_calls,
        "calls": [c.model_dump(mode="json") for c in e.calls],
        "substages": [s.model_dump(mode="json") for s in e.substages],
        "truncation_source": e.truncation_source.value,
        "terminal": e.terminal, "underperformed": e.underperformed,
        "receipt_refs": list(e.receipt_refs), "gap_refs": list(e.gap_refs),
        "refusal_refs": list(e.refusal_refs),
        "provenance": dict(e.provenance),
    }


# ── the session ──────────────────────────────────────────────────────────────

def _deployment_view(raw: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """The badge, or the admission that nobody said.

    `declared: False` is the whole reason this is a function. A missing key would be read by every
    client as "not implemented yet" and silently rendered as nothing, which puts a replay and a live
    run back on the same screen — the thing the badge exists to separate.
    """
    block = _m(raw)
    if not block:
        return {"kind": "undeclared", "declared": False, "reachable": None, "stages": {},
                "detail": "this response was built without a stage binding, so nothing here can "
                          "say whether the session was read live or replayed. It is not a claim "
                          "that it was live."}
    return {
        "kind": _s(block.get("kind")) or "undeclared",
        "declared": block.get("declared") is True,
        # Tri-state, and null is not false: "we did not check whether the provider answers" and
        # "we checked and it does not" send a reader to different places.
        "reachable": block.get("reachable") if isinstance(block.get("reachable"), bool) else None,
        "stages": {str(k): _s(v) for k, v in _m(block.get("stages")).items()},
        "detail": _s(block.get("detail")),
    }


def session_view(session: SemanticInquirySession, *,
                 servable_classes: Sequence[str] = (),
                 deployment: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """One session, as the workbench reads it. The single response body of every route here.

    `deployment` is what PRODUCED this session — live models, a frozen replay, or nothing bound.
    Absent, it is reported as `undeclared`, which is the honest answer and is deliberately not one
    of the three: a caller that did not say must not read as one that said `live`.
    """
    interaction = session.interaction
    state = machine.from_dict(interaction) if interaction.get("session_id") else None   # a `_finish` stub is truthy and is not a state machine

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
        # BESIDE THE STATE, in every response, because a replay screenshot and a live one are
        # otherwise the same picture. Computed by the caller from the stages it bound — this module
        # cannot ask, and inventing an answer here would be the invention the badge exists to stop.
        "deployment": _deployment_view(deployment),
        # BESIDE THE DEPLOYMENT BADGE, for the same argument one field up. A screenshot of a run
        # that investigated a declared subset is otherwise the same picture as a screenshot of a
        # complete reading, and the scope is the more dangerous of the two to lose: a replay at
        # least produces the objects it claims to, and a slice produces FEWER of them and would
        # read as a thin result rather than as a bounded one.
        #
        # ALWAYS PRESENT. It falls back to the session's own declared word, so a slice that never
        # reached the compiler still says it was a slice.
        "execution_scope": execution_scope_view(
            (session.graph or {}).get("execution_scope") if isinstance(session.graph, Mapping)
            else None, declared_mode=session.execution_scope),
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
           "execution_scope_view",
           "alternative_view", "remainder_view", "refusal_view", "reading_view",
           "decision_request_view", "decision_record_view", "trace_view", "stage_view"]
