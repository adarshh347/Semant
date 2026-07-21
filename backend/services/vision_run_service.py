"""
CIRCULATION-SPINE-001 · P1 — VisionRun persistence (write-behind telemetry).

Owns the ``vision_runs`` collection: mint / create / append-event / transition /
finalize / read / project. It mirrors the proven ``agent_runs`` run-with-step-ledger
shape (one poll-friendly document, events embedded, atomic ``$push`` append) rather than
a separate events collection — a Dissect run emits ~8–13 events, far under any Mongo
document-size concern, and the poll pattern wants the whole run in one read.

WRITE-BEHIND CONTRACT (the load-bearing rule): telemetry must never become load-bearing.
The route-facing ``DissectRunRecorder`` swallows every persistence error and flags
``telemetry_degraded``; it can never raise into — nor alter the result of — the
instrumented route (Invariant 7). The strict lower-level coroutines DO raise
(lifecycle/idempotency guarantees) and are what the unit tests exercise directly; the
recorder is the safe adapter the route actually uses.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from bson.objectid import ObjectId
from bson.errors import InvalidId

from backend.database import vision_run_collection
from backend.services.vision_orchestrator.contracts import JobStatus
from backend.services.vision_orchestrator.vision_run_contracts import (
    ACTIVE_STATUSES,
    OPERATION_DISSECT,
    TERMINAL_STATUSES,
    EventRunMismatch,
    IllegalRunTransition,
    as_status,
    assert_bounded_payload,
    bound_error,
    make_event,       # re-exported for callers/tests
    new_run_doc,
    project_run,
)

__all__ = [
    "create_run", "append_event", "transition", "finalize",
    "get_run", "get_latest_run", "ensure_indexes",
    "VisionRunRecorder", "DissectRunRecorder", "make_event",
]

log = logging.getLogger("vision_run")

_ACTIVE_VALUES = [s.value for s in ACTIVE_STATUSES]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _coll(collection):
    return collection if collection is not None else vision_run_collection


# --- strict core (raises; directly unit-tested) -----------------------------

async def create_run(
    *, post_id: str, operation: str = OPERATION_DISSECT, initiator: Optional[str] = None,
    requested_profile: Optional[Dict[str, Any]] = None, collection=None,
) -> str:
    """Mint a run (status RUNNING, started_at set). Returns the run_id (str(_id))."""
    coll = _coll(collection)
    doc = new_run_doc(post_id=post_id, operation=operation, initiator=initiator,
                      requested_profile=requested_profile, status=JobStatus.RUNNING)
    doc["_id"] = ObjectId()
    await coll.insert_one(doc)
    return str(doc["_id"])


async def append_event(run_id: str, event: Dict[str, Any], *, collection=None) -> bool:
    """Atomic, idempotent append with run-ownership enforcement.

    Ownership (P1.1): if ``event['run_id']`` is absent/None it is set to ``run_id``; if it
    is present and differs, the append is rejected with ``EventRunMismatch`` — an event is
    never persisted inside run A while claiming ``run_id == B``.

    ``event_id`` uniqueness is enforced here too: a duplicate event_id is a deterministic
    no-op returning ``False`` (never a second copy). Array position is observation order
    only (Invariant 14); immutability is service-enforced (append-only ``$push`` — existing
    events are never updated), not a Mongo-level prohibition."""
    coll = _coll(collection)
    oid = ObjectId(run_id)
    event = dict(event)
    ev_run_id = event.get("run_id")
    if ev_run_id is None:
        event["run_id"] = run_id
    elif ev_run_id != run_id:
        raise EventRunMismatch(
            f"event claims run_id {ev_run_id!r} but is being appended to run {run_id!r}")
    res = await coll.update_one(
        {"_id": oid, "events.event_id": {"$ne": event["event_id"]}},
        {"$push": {"events": event}, "$set": {"updated_at": _now()}},
    )
    return res.modified_count == 1


async def transition(
    run_id: str, new_status: Any, *, terminal_reason: Optional[str] = None,
    error: Optional[str] = None, result_summary: Optional[Dict[str, Any]] = None,
    actual_source: Optional[str] = None, collection=None,
) -> Dict[str, Any]:
    """Guarded status transition.

    Active → anything is allowed (and stamps ``completed_at`` when the target is
    terminal). Terminal → the *same* status is an idempotent no-op. Terminal → a
    *different* status (including terminal → running) is rejected with
    ``IllegalRunTransition`` (Invariants 13 & the lifecycle stop-gate). The active→X
    write is atomic (conditional on the current status still being active), so a racing
    finalize cannot double-apply."""
    coll = _coll(collection)
    oid = ObjectId(run_id)
    new_status = as_status(new_status)

    set_fields: Dict[str, Any] = {"status": new_status.value, "updated_at": _now()}
    if new_status in TERMINAL_STATUSES:
        set_fields["completed_at"] = _now()
    if terminal_reason is not None:
        set_fields["terminal_reason"] = bound_error(terminal_reason)
    if error is not None:
        set_fields["error"] = bound_error(error)          # bound provider output (P1.1)
    if result_summary is not None:
        assert_bounded_payload(result_summary, "result_summary")   # geometry-free + bounded
        set_fields["result_summary"] = result_summary
    if actual_source is not None:
        assert_bounded_payload(actual_source, "actual_source")
        set_fields["actual_source"] = actual_source

    res = await coll.update_one(
        {"_id": oid, "status": {"$in": _ACTIVE_VALUES}}, {"$set": set_fields})
    if res.matched_count == 1:
        return await coll.find_one({"_id": oid})

    # Not matched: either the run is gone, or it is already terminal.
    doc = await coll.find_one({"_id": oid})
    if not doc:
        raise IllegalRunTransition(f"run {run_id} not found")
    cur = as_status(doc.get("status"))
    if cur in TERMINAL_STATUSES and new_status == cur:
        return doc                                      # idempotent duplicate finalize
    raise IllegalRunTransition(
        f"{cur.value} → {new_status.value} forbidden (run already terminal)")


async def finalize(
    run_id: str, status: Any, *, terminal_reason: Optional[str] = None,
    error: Optional[str] = None, result_summary: Optional[Dict[str, Any]] = None,
    actual_source: Optional[str] = None, collection=None,
) -> Dict[str, Any]:
    """Reach a terminal status. Thin alias over ``transition`` for readability."""
    return await transition(
        run_id, status, terminal_reason=terminal_reason, error=error,
        result_summary=result_summary, actual_source=actual_source, collection=collection)


# --- reads ------------------------------------------------------------------

async def get_run(
    run_id: str, *, post_id: Optional[str] = None, now: Optional[datetime] = None,
    collection=None,
) -> Optional[Dict[str, Any]]:
    """Projected run, scoped to ``post_id`` when given (returns None if it belongs to a
    different post — the read API must validate ownership)."""
    coll = _coll(collection)
    try:
        oid = ObjectId(run_id)
    except (InvalidId, TypeError):
        return None
    query: Dict[str, Any] = {"_id": oid}
    if post_id is not None:
        query["post_id"] = post_id
    doc = await coll.find_one(query)
    return project_run(doc, now=now) if doc else None


async def get_latest_run(
    post_id: str, *, operation: str = OPERATION_DISSECT, now: Optional[datetime] = None,
    collection=None,
) -> Optional[Dict[str, Any]]:
    """Most recent run for a post+operation — small additive query for refresh recovery."""
    coll = _coll(collection)
    cursor = coll.find({"post_id": post_id, "operation": operation}) \
        .sort("created_at", -1).limit(1)
    docs = [d async for d in cursor]
    return project_run(docs[0], now=now) if docs else None


async def ensure_indexes(collection=None) -> None:
    """Idempotent index creation (wired into app startup, mirroring the other services).

    P1.1: keep only indexes backed by a real query. The single non-``_id`` read is
    ``get_latest_run`` — ``find({post_id, operation}).sort(created_at, -1)`` — served by the
    compound below. Single-run reads/appends/transitions all key on ``_id`` (auto-indexed).
    The earlier speculative indexes (``post_id+created_at``, ``status+updated_at``, bare
    ``operation``) matched no real query and were removed; a future P2 "list runs for a
    post" endpoint would add its own."""
    coll = _coll(collection)
    try:
        await coll.create_index(
            [("post_id", 1), ("operation", 1), ("created_at", -1)],
            name="post_operation_created_idx")
    except Exception as e:                              # never block startup on an index
        log.warning("vision_run ensure_indexes skipped: %s", e)


# --- route-facing write-behind recorder (never raises) ----------------------

class VisionRunRecorder:
    """Route-facing, write-behind telemetry handle for ANY vision operation.

    P2.1 generalized this from the P1 ``DissectRunRecorder`` (kept as an alias below) —
    the same write-behind contract now records heterogeneous operations (dissect / refine /
    semantic_read / find_similar) by varying ``operation``. Every method swallows persistence
    errors and flags ``telemetry_degraded``; none can raise into the instrumented route. If
    the run doc itself can't be created, ``run_id`` stays ``None`` and every later call is a
    safe no-op — the route runs exactly as it did before instrumentation, and the additive
    ``run_id`` response field is ``None``.
    """

    def __init__(
        self, *, post_id: str, operation: str = OPERATION_DISSECT,
        initiator: Optional[str] = None, requested_profile: Optional[Dict[str, Any]] = None,
        collection=None,
    ):
        self.post_id = post_id
        self.operation = operation
        self.initiator = initiator
        self.requested_profile = requested_profile
        self._collection = collection
        self.run_id: Optional[str] = None
        self.telemetry_degraded: bool = False
        self._finished: bool = False

    async def start(self) -> Optional[str]:
        try:
            self.run_id = await create_run(
                post_id=self.post_id, operation=self.operation, initiator=self.initiator,
                requested_profile=self.requested_profile, collection=self._collection)
        except Exception as e:
            self.telemetry_degraded = True
            log.warning("vision_run start failed (write-behind, non-fatal): %s", e)
        return self.run_id

    async def event(self, stage_id: str, status: Any, **kwargs) -> None:
        if not self.run_id:
            self.telemetry_degraded = True
            return
        try:
            ev = make_event(stage_id=stage_id, status=status, run_id=self.run_id, **kwargs)
            ok = await append_event(self.run_id, ev, collection=self._collection)
            if not ok:
                self.telemetry_degraded = True
        except Exception as e:
            self.telemetry_degraded = True
            log.warning("vision_run event %s failed (write-behind, non-fatal): %s", stage_id, e)

    async def finish(
        self, status: Any, *, actual_source: Optional[str] = None,
        result_summary: Optional[Dict[str, Any]] = None,
        terminal_reason: Optional[str] = None, error: Optional[str] = None,
    ) -> None:
        """Terminalize the run (write-behind). Idempotent.

        R1 hardening: the finalize is a SHORT telemetry write wrapped in ``asyncio.shield`` —
        if the surrounding request is cancelled *during this write*, the write still runs to
        completion (the run is terminalized) instead of aborting mid-flight and stranding the
        run in RUNNING. ``_finished`` is only set once a finalize attempt has been made, so a
        premature flag can't suppress the sole viable cleanup. Cancellation is NEVER swallowed
        or translated — it is re-raised. Only this telemetry op is shielded, never model/route
        work.

        Residual (documented): if the shielded write itself fails (DB down) or the event loop
        is torn down before it commits, the run can still be left as a *stale* RUNNING record —
        honestly surfaced by the read projection, not silently 'completed'."""
        if self._finished:
            return
        if not self.run_id:
            self._finished = True
            self.telemetry_degraded = True
            return
        try:
            await asyncio.shield(finalize(
                self.run_id, status, terminal_reason=terminal_reason, error=error,
                result_summary=result_summary, actual_source=actual_source,
                collection=self._collection))
            self._finished = True
            if self.telemetry_degraded:
                # Best-effort: record that some earlier event write was lost.
                try:
                    coll = _coll(self._collection)
                    await asyncio.shield(coll.update_one(
                        {"_id": ObjectId(self.run_id)}, {"$set": {"telemetry_degraded": True}}))
                except Exception:
                    pass
        except asyncio.CancelledError:
            # The shielded finalize is running to completion; the cancellation targets the
            # request, not the write. Mark finished so a retry can't double-finalize, and
            # re-raise — cancellation is never swallowed (R1).
            self._finished = True
            raise
        except Exception as e:
            self._finished = True
            self.telemetry_degraded = True
            log.warning("vision_run finish failed (write-behind, non-fatal): %s", e)


# Backward-compat alias: P1 shipped this as `DissectRunRecorder`. The recorder is generic
# (its `operation` param carries the family), so P2.1 renamed it `VisionRunRecorder` and keeps
# this alias so the P1 detect_regions route and existing tests are untouched.
DissectRunRecorder = VisionRunRecorder
