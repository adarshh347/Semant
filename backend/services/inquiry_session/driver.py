"""
HARNESS-003B — what makes the steps run: one driver per session, a checkpoint per stage.

## The architecture this repairs

`POST /api/v1/inquiries` called the whole synchronous chain before returning. The frontend could
not subscribe to the event stream until that call came back, so its `Starting…` state was
structurally incapable of showing progress — 002R's first finding, and a UI bug only in the sense
that the UI was the place you noticed it.

The driver inverts it. The route creates a durable session, schedules a driver and returns. Every
stage checkpoints on the way in and on the way out, so `GET` and the stream are reading a document
that moves while the work happens rather than one that appears at the end.

## Where the work runs, and why not on the Director's worker

`runs.py` drives the Director on a single persistent worker thread, and the comment there says why:
the loop's runners call `run_until_complete`, which cannot nest inside the server's loop, and *two
workers would race for one GPU*. Both reasons are about that chain and neither is true of this one.

The census, which is the whole of the reconciliation:

    the theorist and the compiler call `client.chat.completions.create(...)` — a blocking HTTPS
    request to a remote provider. They take no `loop=`, bind no `ModelManager` semaphore, hold no
    device, and never call `run_until_complete`.

So the constraint that produced a single serialised worker does not reach here, and honouring it
anyway would be worse than pointless: an inquiry's remote API call would occupy the lane a GPU plan
needs, and a Director run would delay every inquiry behind it, for a resource neither of them
shares. This driver therefore uses its OWN small pool for blocking-SDK work, and a structural test
asserts that nothing in this package touches the orchestration worker — paired with a control
proving `runs.py` still does, so the scan cannot pass by being pointed somewhere empty.

No worker was extracted and no Director behaviour was edited.

## One driver per session

The lease is a compare-and-set on the session document, not an in-process registry. A registry
would be correct in one process and silently wrong in two, which is the deployment this repository
is heading towards. A second scheduler for a session that already has a driver finds the lease
taken and returns without entering a stage — which is what "duplicate schedule does not duplicate
calls" has to mean when the duplicate arrives at another worker.

## Nothing in memory is the only record

Every checkpoint is a store write under compare-and-set on `session.checkpoint`. The in-process task
handle exists so a test can await settlement and so the route can avoid scheduling twice in the
common case; it is never consulted to decide what has happened. Kill the process at any point and
the store still answers.
"""
from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import itertools
import os
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, List, Optional

from backend.schemas.inquiry_session import SemanticInquirySession
from backend.schemas.inquiry_stage import StageAttemptOutcome, SubstageEvent

from . import ids, steps, store
from .coordinator import Stages

#: Blocking-SDK work for inquiry stages. Separate from the Director's single `director-orch` worker
#: for the reason in the module note: nothing here holds a device or nests an event loop, and
#: sharing that lane would serialise two chains against a resource neither of them contends for.
#: Small rather than unbounded — a provider that is slow for one inquiry is slow for all of them,
#: and an unbounded pool converts that into unbounded memory.
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="inquiry-stage")

#: Unique per driver INSTANCE, and the uniqueness is load-bearing. The first version of this module
#: defaulted `driver_id` to `f"drv_{session_id}"` — derived from the thing being excluded, so two
#: drivers for one session computed the SAME id, `claim` read `lease == driver_id` as "I already
#: hold this", and both entered the stage. A lease whose default defeats the lease.
#: `getpid` distinguishes processes; the counter distinguishes drivers within one.
_SEQ = itertools.count(1)


def new_driver_id() -> str:
    return f"drv_{os.getpid()}_{next(_SEQ)}"


#: session_id → the running driver task. A convenience for scheduling and for tests that want to
#: await settlement. NEVER consulted to decide what has already happened; the store is.
_TASKS: Dict[str, "asyncio.Task[None]"] = {}


class DriverBusy(RuntimeError):
    """Another driver holds this session. Not an error the person caused, and not a failure."""


@dataclass(frozen=True)
class DriverReport:
    """What one drive did. Returned for tests and for a caller that drove synchronously."""
    session_id: str
    stages_run: tuple
    checkpoints: int
    final_state: str
    claimed: bool = True
    reason: str = ""


def _lease_of(session: SemanticInquirySession) -> str:
    return str((session.driver or {}).get("lease_id") or "")


async def claim(session_id: str, driver_id: str, *, at: str,
                collection=None) -> Optional[SemanticInquirySession]:
    """Take the lease, or return None because somebody else holds it.

    A COMPARE-AND-SET on the document, not a lock in this process. An in-process registry would be
    correct in one worker and silently wrong in two, and the second worker is the one that would
    make a second model call for a stage the first was already inside.

    NO AUTOMATIC TAKEOVER, and the reason is that it cannot be done honestly. A held lease with a
    dangling `started` attempt is what a process killed inside a call leaves behind — and it is
    ALSO exactly what a live driver currently inside that call looks like. From persisted state
    alone the two are indistinguishable, so any rule that reclaims one reclaims the other, and
    guessing wrong means two model calls for one stage. A heartbeat would only move the guess to a
    threshold: a provider slower than the timeout is a driver declared dead while it is working.

    So this refuses, and `reclaim` exists for the case where somebody can assert what this function
    cannot infer. A stuck lease is a visible, inspectable session; a stolen one is a second charge
    and a second answer.
    """
    session = await store.load(session_id, collection=collection)
    held = _lease_of(session)
    if held and held != driver_id:
        return None
    claimed = session.model_copy(update={
        "driver": {"lease_id": driver_id, "claimed_at": at, "state": "running"}})
    try:
        await store.save(claimed, expected_checkpoint=session.checkpoint, collection=collection)
    except store.SessionWriteFailed:
        # Somebody checkpointed between the read and the write. They hold it.
        return None
    return claimed


async def reclaim(session_id: str, driver_id: str, *, at: str,
                  collection=None) -> Optional[SemanticInquirySession]:
    """Take a lease its holder is ASSERTED to have lost, name the interruption, and stop.

    EXPLICIT AND NEVER AUTOMATIC. `claim` refuses a held lease because it cannot tell a dead driver
    from a working one; this function is how a caller who CAN tell — an operator, or a startup sweep
    that knows which process ids died with it — says so. The assertion is the caller's, and it is
    recorded on the session as theirs.

    It reopens and returns. It does not resume the chain: `plan` refuses to continue past an
    interrupted stage, so the recovered session is inspectable and stopped, which is the honest end
    for a call nobody can say landed or not.
    """
    session = await store.load(session_id, collection=collection)
    reopened = steps.reopen(session, at=at)
    taken = reopened.model_copy(update={
        "checkpoint": session.checkpoint + 1,
        "driver": {"lease_id": "", "state": "idle", "reclaimed_at": at,
                   "reclaimed_from": _lease_of(session), "reclaimed_by": driver_id,
                   "assertion": "the caller asserts the previous holder is gone; nothing was "
                                "inferred from the document, which cannot tell a dead driver from "
                                "a working one"}})
    try:
        await store.save(taken, expected_checkpoint=session.checkpoint, collection=collection)
    except store.SessionWriteFailed:
        return None
    return taken


async def release(session: SemanticInquirySession, driver_id: str, *, at: str,
                  collection=None) -> None:
    """Give the lease back, whatever happened. A session left leased by a dead driver would be
    unclaimable forever, which turns one crash into a permanently stuck inquiry."""
    if _lease_of(session) not in ("", driver_id):
        return
    released = session.model_copy(update={
        "driver": {**dict(session.driver or {}), "lease_id": "", "state": "idle",
                   "released_at": at}})
    with contextlib.suppress(store.SessionWriteFailed):
        await store.save(released, expected_checkpoint=session.checkpoint, collection=collection)


async def checkpoint(session: SemanticInquirySession, *, expected: int,
                     collection=None) -> SemanticInquirySession:
    """Persist one step's effect under compare-and-set, and hand back the advanced session.

    `checkpoint` is incremented HERE rather than by the caller, so every write through this
    function moves it exactly once and no step can persist twice under one number.
    """
    advanced = session.model_copy(update={"checkpoint": expected + 1})
    await store.save(advanced, expected_checkpoint=expected, collection=collection)
    return advanced


def _replace(stages: Stages, **fields: Any) -> Stages:
    """`Stages` is frozen, and the observer is bound per stage entry rather than per driver.

    Per ENTRY because the tap has to know which attempt it is writing progress onto. A driver-wide
    observer would have to look that up on every event, which is the same lookup done N times with
    N chances to disagree with the checkpoint the driver is holding.
    """
    return dataclasses.replace(stages, **fields)


class _LiveProgress:
    """A stage's own account of itself, persisted WHILE the stage is still inside its call.

    ## Why this exists at all

    HARNESS-003B made the chain watchable BETWEEN stages: a `started` attempt goes in before the
    call and a terminal one after, so a person sees which of seven stages is running and for how
    long. That is enough while a stage takes seconds. It is not enough for a compiler that spends
    four minutes queueing against an 8000 TPM allowance, because `compiler · started · 4m 12s` and
    a hung process are the same screen — and `DECISION-harness-003D` says in as many words that the
    UI may say `waiting for provider capacity` and may not look frozen.

    So the substages are flushed to the store as they are reported, onto the `started` attempt the
    driver already wrote. `GET` and the stream then show the council's passes arriving one at a
    time, and each capacity wait the moment it is planned rather than once it is over.

    ## What makes it safe

    The stage runs on a pool thread and every write happens on the event loop. The observer does not
    write; it BUFFERS under a plain lock and schedules a drain. So there is exactly one writer, and
    it is the same coroutine that does the driver's own checkpoints — which is why the moving
    checkpoint can live in a plain attribute here rather than needing a second compare-and-set
    scheme on top of the store's.

    Fire and forget, deliberately: a model call must never be paced by a store write. A flush that
    fails is dropped and the terminal attempt still carries the whole substage list, because
    `_Ledger` records them regardless — see `coordinator._sink_for`, which feeds both.
    """

    def __init__(self, session: SemanticInquirySession, stage: Any, *, collection: Any,
                 on_checkpoint: Optional[Callable[[SemanticInquirySession], None]] = None):
        self.session = session
        self._stage = stage
        self._collection = collection
        self._on_checkpoint = on_checkpoint
        self._loop = asyncio.get_running_loop()
        self._pending: Deque[Dict[str, Any]] = deque()
        self._buffer_lock = threading.Lock()
        self._write_lock = asyncio.Lock()
        self._seen = 0

    @property
    def checkpoint(self) -> int:
        return self.session.checkpoint

    # ── called from the stage's thread ──

    def __call__(self, label: str, **fields: Any) -> None:
        with self._buffer_lock:
            self._seen += 1
            self._pending.append({"label": str(label), "seq": self._seen, **fields})
        with contextlib.suppress(RuntimeError):
            # RuntimeError: the loop is closing. A late progress report is dropped rather than
            # raised — it would otherwise fail a stage that had already finished its work.
            asyncio.run_coroutine_threadsafe(self._flush(), self._loop)

    # ── called on the loop ──

    async def _flush(self) -> None:
        async with self._write_lock:
            with self._buffer_lock:
                if not self._pending:
                    return
                batch = list(self._pending)
                self._pending.clear()
            events = [self._event(row) for row in batch]
            advanced = _with_substages(self.session, self._stage, events)
            if advanced is None:
                return
            try:
                self.session = await checkpoint(advanced, expected=self.session.checkpoint,
                                                collection=self._collection)
            except store.SessionWriteFailed:
                # Somebody else moved the document. Progress is a courtesy; the terminal attempt
                # carries the same events, so nothing is lost by giving up on this one.
                return
            if self._on_checkpoint:
                self._on_checkpoint(self.session)

    def _event(self, row: Dict[str, Any]) -> SubstageEvent:
        seq = int(row.pop("seq"))
        label = str(row.pop("label"))
        return SubstageEvent(
            substage_id=ids.stage_id(self.session.session_id, "substage", label, seq),
            label=label,
            index=row.get("index"), total=row.get("total"), at=row.get("at"),
            outcome=str(row.get("outcome") or ""),
            refs=[str(r) for r in (row.get("refs") or ())],
            detail=str(row.get("detail") or ""))


def _with_substages(session: SemanticInquirySession, stage: Any,
                    events: List[SubstageEvent]) -> Optional[SemanticInquirySession]:
    """Append progress to the `started` attempt this driver wrote for `stage`.

    ONLY onto a `started` attempt, and `None` when there is not one. A terminal attempt is a closed
    record: writing progress onto it after the fact would let a stage that had already reported its
    ending grow a longer story afterwards.
    """
    latest = steps.latest_by_stage(session).get(stage)
    if latest is None or latest.outcome is not StageAttemptOutcome.STARTED:
        return None
    grown = latest.model_copy(update={"substages": [*latest.substages, *events]})
    return session.model_copy(update={
        "stages": [grown if a.attempt_id == latest.attempt_id else a for a in session.stages]})


async def drive(session_id: str, stages: Stages, *, driver_id: str = "",
                collection=None, on_checkpoint: Optional[Callable[[SemanticInquirySession], None]] = None,
                limit: int = 32) -> DriverReport:
    """Run every pending stage, persisting before and after each one.

    THE ORDER INSIDE THE LOOP IS THE FEATURE:

        1. read the session from the store — never from the previous iteration's memory, so a
           decision written by another request is seen;
        2. ask `steps.plan` what is next;
        3. write the `started` attempt BEFORE entering the stage;
        4. run the stage off the event loop;
        5. write its terminal attempt.

    Step 3 is what a crash lands on. Written after the call instead, a process that died mid-model
    would leave a session that looked as though the stage had never been tried — and the next
    driver would try it again, buying the same reading twice.
    """
    driver_id = driver_id or new_driver_id()
    at = stages.clock()
    session = await claim(session_id, driver_id, at=at, collection=collection)
    if session is None:
        return DriverReport(session_id=session_id, stages_run=(), checkpoints=0, final_state="",
                            claimed=False,
                            reason="another driver holds this session; nothing was entered twice")

    ran: list = []
    writes = 0
    try:
        # A session claimed with a dangling `started` attempt crashed mid-call. It is reopened as
        # `interrupted` and NOT retried — see `steps.reopen`.
        reopened = steps.reopen(session, at=stages.clock())
        if reopened is not session:
            session = await checkpoint(reopened, expected=session.checkpoint,
                                       collection=collection)
            writes += 1

        for _ in range(limit):
            step = steps.plan(session)
            if step.done:
                settled = steps.settle(session, stages)
                if settled is not session:
                    session = await checkpoint(settled, expected=session.checkpoint,
                                               collection=collection)
                    writes += 1
                    if on_checkpoint:
                        on_checkpoint(session)
                break

            session = await checkpoint(steps.start(session, step.stage, stages),
                                       expected=session.checkpoint, collection=collection)
            writes += 1
            if on_checkpoint:
                on_checkpoint(session)

            # THE LIVE TAP, bound for the duration of this stage only. A stage reports its own
            # insides through it and the progress lands in the store while the call is still in
            # flight — which is what stops a four-minute wait for provider capacity from looking
            # like a hung process. `_LiveProgress` holds the moving checkpoint, so the terminal
            # write below expects whatever the flushes left rather than what this iteration read.
            progress = _LiveProgress(session, step.stage, collection=collection,
                                     on_checkpoint=on_checkpoint)
            watched = _replace(stages, observer=progress)

            loop = asyncio.get_running_loop()
            advanced = await loop.run_in_executor(_POOL, steps.run, session, step.stage, watched)

            session = await checkpoint(advanced, expected=progress.checkpoint,
                                       collection=collection)
            writes += 1
            ran.append(step.stage.value)
            if on_checkpoint:
                on_checkpoint(session)
        else:
            raise steps.DriverHalted(
                f"session {session_id} did not reach a boundary in {limit} steps")
    except Exception as exc:                                # noqa: BLE001
        # A driver that fell over says so ON THE SESSION. The alternative is a session frozen at
        # whatever stage it was in, with the reason living only in a server log the person asking
        # the question cannot read.
        session = await _record_failure(session, exc, stages, collection=collection)
        writes += 1
        raise
    finally:
        await release(session, driver_id, at=stages.clock(), collection=collection)

    return DriverReport(session_id=session_id, stages_run=tuple(ran), checkpoints=writes,
                        final_state=session.state)


async def _record_failure(session: SemanticInquirySession, exc: BaseException, stages: Stages,
                          *, collection=None) -> SemanticInquirySession:
    failed = session.model_copy(update={
        "error": f"driver_failed:{type(exc).__name__}",
        "stop_reason": session.stop_reason or f"the stage driver stopped: {str(exc)[:300]}"})
    with contextlib.suppress(store.SessionWriteFailed):
        return await checkpoint(failed, expected=session.checkpoint, collection=collection)
    return failed


def schedule(session_id: str, stages: Stages, **kwargs: Any) -> "asyncio.Task[None]":
    """Start a driver in the background, or hand back the one already running.

    The in-process check is an OPTIMISATION and not the guard. Two workers cannot see each other's
    task table, so the lease in `claim` is what actually prevents a second driver — this only saves
    the common single-process case a pointless round trip to the store.
    """
    existing = _TASKS.get(session_id)
    if existing is not None and not existing.done():
        return existing

    async def _run() -> None:
        try:
            await drive(session_id, stages, **kwargs)
        finally:
            if _TASKS.get(session_id) is task:
                _TASKS.pop(session_id, None)

    task = asyncio.get_running_loop().create_task(_run())
    _TASKS[session_id] = task
    return task


async def settled(session_id: str) -> None:
    """Await the in-process driver, if there is one. For tests and for a synchronous rehearsal.

    Deliberately not part of the request path: a route that awaited this would have re-created the
    blocking POST this lane exists to remove.
    """
    task = _TASKS.get(session_id)
    if task is None:
        return
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.shield(task)


def running(session_id: str) -> bool:
    task = _TASKS.get(session_id)
    return task is not None and not task.done()


__all__ = ["DriverBusy", "DriverReport", "new_driver_id", "claim", "reclaim", "release",
           "checkpoint", "drive", "schedule", "settled", "running"]
