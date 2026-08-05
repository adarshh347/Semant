"""
WAVE2 Lane G — the stigmergic API: writers post, readers react, nobody conducts.

`movement_graph` is pure — shaping, dynamics and hydration with no database and no clock it did not
receive. This is the half that touches the store, kept apart for the reason `atlas_relation` gives
for the same split: the shaping rules are the part worth testing exhaustively, and they should not
need a Mongo to be exercised.

## Stigmergic, concretely

There is no controller. A writer that measures a movement calls `write_edge` and stops caring; a
reader that wants to move calls `read_neighbours` or `retrieve_along_axis` and finds whatever the
graph currently holds. The trace in the environment IS the coordination — which is why the weight
lives on the edge and not in any agent's head, and why `subscribe` hands out notifications rather
than instructions.

`subscribe` is in-process and deliberately small: a pattern, a callback, and a handle to drop it.
It is not a message bus, it does not persist, and a subscriber that raises is dropped from that
notification rather than being allowed to fail the write. A durable event log is a real thing Lane M
may want; it is not this, and pretending otherwise by naming this one `events` would invite exactly
that confusion.

## Every write goes through the Atlas's own guard

`write_edge` calls `atlas_service.add_edge`, which `$push`es (never read-modify-`$set`, so two
writers cannot silently drop each other's edge) and runs `assert_no_percept_data` on the document
as it will be. This module adds no second write path and no second validation. If a movement edge
is ever malformed, it is refused by the same code that refuses a malformed C3 relation.
"""
from __future__ import annotations

import fnmatch
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from backend.services import atlas_service
from backend.services.movement_graph import (assert_valid_movement_edge, hydrate_axis,
                                             hydrate_movement_edge, is_live, is_movement_edge,
                                             keeper_tick, movement_edge_entry, new_axis, utc_now)


def _axis_collection(collection=None):
    """The axes collection, injectable — the pattern `atlas_service._collection` established, so a
    test hands a fake and this module imports no database at all until something really writes."""
    if collection is not None:
        return collection
    from backend.database import movement_axis_collection
    return movement_axis_collection


# ── write ────────────────────────────────────────────────────────────────────

async def write_edge(atlas_id: str, *, mark_id: str, source_node: str, target_node: str,
                     spans: Sequence[str], axis_ref: str,
                     systematicity: Optional[float] = None,
                     weight: Optional[float] = None,
                     now: str = "", collection=None) -> Optional[Dict[str, Any]]:
    """Post one movement into the Atlas. Returns the updated document, or None if no such Atlas.

    PROPOSE-NEVER-COMMIT holds by construction: this writes a REFERENCE to a mark that a curator
    (or an accept path) already committed. It cannot create the relation it points at, so there is
    no path from here to a percept nobody accepted. `movement_edge_entry` refuses a blank
    `mark_id`, which is the same rule stated as an exception.
    """
    entry = movement_edge_entry(
        mark_id=mark_id, source_node=source_node, target_node=target_node, spans=spans,
        axis_ref=axis_ref, systematicity=systematicity,
        **({"weight": weight} if weight is not None else {}), now=now)
    assert_valid_movement_edge(entry)
    doc = await atlas_service.add_edge(atlas_id, entry, now=now, collection=collection)
    if doc is not None:
        _notify(f"edge/{axis_ref}", {"atlas_id": str(atlas_id), "edge": entry})
    return doc


async def write_axis(*, name: str, relation_kind: str, axis_id: str = "",
                     grounded_instances: Optional[Sequence[str]] = None,
                     now: str = "", collection=None) -> Dict[str, Any]:
    """Mint a discovered dimension and store it. Returns the axis document.

    Upsert by `axis_id` when one is supplied, so re-declaring a known axis is idempotent rather
    than a duplicate — two rows for `nestedness` would split every retrieval along it in half, and
    nothing downstream would report the split.
    """
    axis = new_axis(name=name, relation_kind=relation_kind, axis_id=axis_id,
                    grounded_instances=grounded_instances, now=now)
    await _axis_collection(collection).update_one(
        {"_id": axis["axis_id"]}, {"$set": {**axis, "_id": axis["axis_id"]}}, upsert=True)
    _notify(f"axis/{axis['axis_id']}", {"axis": axis})
    return axis


async def get_axis(axis_id: str, *, collection=None) -> Optional[Dict[str, Any]]:
    return await _axis_collection(collection).find_one({"_id": str(axis_id)})


async def list_axes(*, limit: int = 50, collection=None) -> List[Dict[str, Any]]:
    cursor = _axis_collection(collection).find({}).limit(int(limit))
    return [doc async for doc in cursor]


# ── read ─────────────────────────────────────────────────────────────────────

def read_neighbours(doc: Mapping[str, Any], node_id: str, *,
                    axis: str = "", posts: Optional[Mapping[str, Mapping[str, Any]]] = None,
                    include_dead: bool = False) -> List[Dict[str, Any]]:
    """Every live movement touching `node_id`, optionally narrowed to one axis.

    Undirected on purpose. A movement asserts that two things stand in a relation along an axis;
    which end the writer happened to drag from is a fact about the gesture, not about the relation,
    and a reader traversing the graph should not have to know it. `direction` is reported so a
    caller that DOES care (the façade prepares the rotunda; the reverse is a different claim) can
    still tell.

    Hydrated, so what comes back carries the ledger's answer — including `epistemic`, which this
    module never stored and would not be entitled to invent.
    """
    posts = posts or {}
    out: List[Dict[str, Any]] = []
    for edge in doc.get("edges") or []:
        if not is_movement_edge(edge):
            continue
        if axis and str(edge.get("axis_ref") or "") != str(axis):
            continue
        source, target = str(edge.get("source_node")), str(edge.get("target_node"))
        if str(node_id) not in (source, target):
            continue
        if not include_dead and not is_live(edge):
            continue
        hydrated = hydrate_movement_edge(edge, posts)
        hydrated["direction"] = "outgoing" if source == str(node_id) else "incoming"
        hydrated["other_node"] = target if source == str(node_id) else source
        out.append(hydrated)
    # Heaviest first: concentration is the graph's own answer to "what is worth traversing", and a
    # caller that wants another order can sort, but a caller handed an arbitrary one cannot recover
    # this one.
    out.sort(key=lambda e: float(e.get("weight") or 0.0), reverse=True)
    return out


def retrieve_along_axis(doc: Mapping[str, Any], axis_id: str, candidate: Mapping[str, Any], *,
                        posts: Optional[Mapping[str, Mapping[str, Any]]] = None,
                        limit: int = 12) -> Dict[str, Any]:
    """What this axis says about a candidate the retina proposed.

    The seam Lane M is built on, and the reason an axis is first-class at all: the retina answers
    "what looks like this", which is similarity and says nothing about *how* two things are related.
    An axis answers "what stands in THIS relation to it", which is movement. Handing the kernel a
    candidate and getting back the movements along one named dimension is the whole point.

    Returns a status envelope rather than a bare list, copying `retina.propose_candidates`' rule
    for the same reason it has one: `unknown` (this axis has no movements at all) and `empty` (it
    has some, none touching this candidate) are different facts, and a caller handed `[]` for both
    cannot tell a cold axis from an unrelated candidate.
    """
    posts = posts or {}
    node_id = str(candidate.get("node_id") or candidate.get("post_id") or "")
    along = [e for e in doc.get("edges") or []
             if is_movement_edge(e) and str(e.get("axis_ref") or "") == str(axis_id)]
    if not along:
        return {"status": "unknown", "axis_ref": str(axis_id), "candidate": node_id,
                "movements": [], "detail": "no movement has ever been recorded along this axis"}

    live = [e for e in along if is_live(e)]
    touching = [e for e in live
                if node_id in (str(e.get("source_node")), str(e.get("target_node")))]
    if not touching:
        return {"status": "empty", "axis_ref": str(axis_id), "candidate": node_id,
                "movements": [], "axis_movements": len(live),
                "detail": "this axis holds movements, none of them touching this candidate"}

    hydrated = [hydrate_movement_edge(e, posts) for e in touching]
    hydrated.sort(key=lambda e: float(e.get("weight") or 0.0), reverse=True)
    return {"status": "ok", "axis_ref": str(axis_id), "candidate": node_id,
            "movements": hydrated[:limit], "axis_movements": len(live),
            "truncated": len(hydrated) > limit}


def axis_view(axis: Mapping[str, Any], doc: Mapping[str, Any],
              posts: Optional[Mapping[str, Mapping[str, Any]]] = None) -> Dict[str, Any]:
    """An axis + the Atlas it is read against → the axis wearing its derived status."""
    return hydrate_axis(axis, doc.get("edges") or [], posts or {})


# ── the keeper ───────────────────────────────────────────────────────────────

async def keeper_pass(atlas_id: str, *, now: str = "", collection=None,
                      dry_run: bool = False) -> Optional[Dict[str, Any]]:
    """Decay every movement on one Atlas and drop what has faded. Returns a report.

    Idle/event-tick shaped: it takes no lock and holds no state, so running it twice changes
    nothing the second time (decay is computed from `last_measured_at`, not accumulated per call).

    `dry_run` exists because the first question anybody asks of an evaporating graph is "what would
    this remove", and the honest way to answer it is to compute the answer without doing it.
    """
    doc = await atlas_service.get_atlas(atlas_id, collection=collection)
    if doc is None:
        return None
    stamp = now or utc_now()
    result = keeper_tick(doc.get("edges") or [], now=stamp)
    report = {"atlas_id": str(atlas_id), "at": stamp,
              "kept": len(result["kept"]), "pruned": len(result["pruned"]),
              "untouched": len(result["untouched"]),
              "pruned_edge_ids": [str(e.get("edge_id")) for e in result["pruned"]],
              "dry_run": bool(dry_run)}
    if dry_run or not result["pruned"]:
        # Nothing pruned still means weights moved, but a write that only lowers numbers is not
        # worth a round trip on every idle tick — the decay is recomputed from timestamps on the
        # next read anyway. Persisting happens when something is actually removed.
        return report

    kept_edges = [*result["untouched"], *result["kept"]]
    await atlas_service._collection(collection).update_one(
        {"_id": str(atlas_id)}, {"$set": {"edges": kept_edges, "updated_at": stamp}})
    for edge in result["pruned"]:
        _notify(f"prune/{edge.get('axis_ref')}", {"atlas_id": str(atlas_id), "edge": dict(edge)})
    return report


# ── subscribe: notification, not instruction ─────────────────────────────────

_SUBSCRIBERS: List[Dict[str, Any]] = []


def subscribe(pattern: str, callback: Callable[[str, Dict[str, Any]], None]) -> Callable[[], None]:
    """React to writes matching a glob (`edge/*`, `axis/*`, `prune/nestedness`, `*`).

    Returns an unsubscribe callable rather than an id, so a caller cannot leak a subscription by
    losing track of a number.

    NOT A CONTROLLER. A subscriber is told what happened; it is never asked what should happen, and
    its return value is discarded. The moment a callback's answer could steer the write, this stops
    being stigmergy and becomes an event-driven orchestrator with the coordination back in one
    place — which is the shape this lane exists to avoid.
    """
    entry = {"pattern": str(pattern), "callback": callback}
    _SUBSCRIBERS.append(entry)

    def unsubscribe() -> None:
        try:
            _SUBSCRIBERS.remove(entry)
        except ValueError:
            pass
    return unsubscribe


def _notify(topic: str, payload: Mapping[str, Any]) -> None:
    """Fan a write out to whoever is listening. A raising subscriber is skipped, never propagated:
    a reader that breaks must not be able to fail the writer's write."""
    for entry in list(_SUBSCRIBERS):
        if not fnmatch.fnmatch(topic, entry["pattern"]):
            continue
        try:
            entry["callback"](topic, dict(payload))
        except Exception:                      # noqa: BLE001 — a reader cannot break a writer
            continue


def _reset_subscribers() -> None:
    """Test aid only — the same escape hatch `visualMarks._resetMarkIds` provides."""
    _SUBSCRIBERS.clear()
