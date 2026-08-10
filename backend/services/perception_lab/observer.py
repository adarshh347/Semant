"""
PERCEPTUAL-ORGANS-002 Lane D — the observer: what happened, held apart from what was found.

A `StageAttempt` is the machinery's account of one step. The measurement is the adapter's account
of the same step, and the two are separate records because they fail separately: a stage can
complete perfectly and find nothing, and a stage can be skipped without anything having gone
wrong with the thing it would have measured.

`invoked` IS THE FIELD THE WHOLE REPLAY LAW TURNS ON, and it is set in exactly one place: here,
inside `invoke()`, immediately before the adapter is called. It is not derived from `adapter`
being set — a replay stage legitimately NAMES the adapter whose recorded output it is showing —
and it is not something a caller passes in. There is one line in this lane that can make `invoked`
true, and `may_invoke` guards it.

THE OBSERVER HOLDS THE STOPWATCH, NOT THE ADAPTER. `duration_ms` is measured around the call by
the monotonic clock the conductor was handed. An adapter reporting its own duration would be
reporting the number it wished were true, and this is the number a phase gate reads.

WHY A REPLAY'S DURATIONS ARE NOT THE ORIGINAL'S. A replay records how long it took to READ the
ledger. Copying the original's 1840ms onto the replay would make the two runs indistinguishable in
the one column that says whether a model was asked anything — which is the contract's own fixture
note on `run.replay-extent.json`, and it is right.

PURE. No database, no network, no model. Clock and ids are injected.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from backend.schemas.perception_lab import StageAttempt, StageState
from backend.services.perception_lab.clock import Clock, IdFactory


class ReplayCannotInvoke(RuntimeError):
    """A run that is not LIVE tried to call an adapter.

    RAISED, not refused, and raised BEFORE the call rather than reported after it. A refusal would
    be an answer to a person; this is a defect, and the only correct response to it is that the
    call did not happen. `LabRun` refuses the record too, and that second guard is what would
    catch a hand-built run — but by then the adapter would already have run, which is precisely
    what must not be true.
    """


@dataclass
class Stage:
    """One attempt in flight. Held by the observer, closed by `end`."""
    attempt_id: str
    step_id: str
    operation: str
    adapter: Optional[str]
    invoked: bool
    started_at: str
    started_ms: int


class RunObserver:
    """The stage stream of one run.

    `may_invoke` is set from the run's execution identity at construction and never changes. A
    REPLAY or FIXTURE observer cannot be talked into permitting a call halfway through, because
    there is no method that sets it.
    """

    def __init__(self, run_id: str, *, clock: Clock, ids: IdFactory, may_invoke: bool):
        self.run_id = run_id
        self._clock = clock
        self._ids = ids
        self.may_invoke = may_invoke
        self.attempts: List[StageAttempt] = []
        self.started_ms = clock.monotonic_ms()
        self.started_at = clock.now_iso()

    # -- stages that never reached an adapter --

    def refused(self, step_id: str, operation: str, detail: str,
                adapter: Optional[str] = None) -> StageAttempt:
        """A law said no. Nothing was called, and `invoked` says so."""
        return self._closed(step_id, operation, StageState.REFUSED, adapter, detail)

    def unavailable(self, step_id: str, operation: str, detail: str,
                    adapter: Optional[str] = None) -> StageAttempt:
        return self._closed(step_id, operation, StageState.UNAVAILABLE, adapter, detail)

    def skipped(self, step_id: str, operation: str, detail: str,
                adapter: Optional[str] = None) -> StageAttempt:
        """Cancelled, or out of budget. The step was authorized and the run stopped asking."""
        return self._closed(step_id, operation, StageState.SKIPPED, adapter, detail)

    def failed(self, step_id: str, operation: str, detail: str,
               adapter: Optional[str] = None) -> StageAttempt:
        """Something broke BEFORE a call. A call that broke is `begin` then `end(FAILED)`, which
        keeps its `invoked: true` — the attempt happened and the record must say so."""
        return self._closed(step_id, operation, StageState.FAILED, adapter, detail)

    # -- a stage that will reach one --

    def begin(self, step_id: str, operation: str, adapter: Optional[str], *,
              invoking: bool) -> Stage:
        """Open a stage. THE ONLY PLACE `invoked` CAN BECOME TRUE.

        `invoking=True` on an observer whose run may not invoke raises here, before the caller
        gets a handle and therefore before it can reach an adapter. That ordering is the test:
        `replay raises before any adapter invocation` passes only because this check is in front
        of the call rather than beside it.
        """
        if invoking and not self.may_invoke:
            raise ReplayCannotInvoke(
                f"stage {step_id!r} on run {self.run_id!r} tried to invoke {adapter!r}. This run "
                f"is not LIVE and has nothing to call: its content is a record of a call that "
                f"already happened, and calling again would produce a different measurement "
                f"wearing the same run's identity.")
        return Stage(attempt_id=self._ids.mint("att"), step_id=step_id, operation=operation,
                     adapter=adapter, invoked=invoking, started_at=self._clock.now_iso(),
                     started_ms=self._clock.monotonic_ms())

    def end(self, stage: Stage, state: StageState, detail: Optional[str] = None) -> StageAttempt:
        attempt = StageAttempt(
            attempt_id=stage.attempt_id, step_id=stage.step_id, operation=stage.operation,
            state=state, adapter=stage.adapter, invoked=stage.invoked,
            started_at=stage.started_at, completed_at=self._clock.now_iso(),
            duration_ms=max(0, self._clock.monotonic_ms() - stage.started_ms), detail=detail)
        self.attempts.append(attempt)
        return attempt

    # -- replay: a stage re-shown, never re-run --

    def reshown(self, original: StageAttempt, detail: str) -> StageAttempt:
        """One recorded stage, re-timed as the reading it now is.

        The original's duration is DROPPED. It measured a model; this measures a dictionary
        lookup, and carrying the first number onto the second would erase the only column that
        distinguishes a replay from the run it replays.
        """
        started_ms = self._clock.monotonic_ms()
        started_at = self._clock.now_iso()
        attempt = StageAttempt(
            attempt_id=self._ids.mint("att"), step_id=original.step_id,
            operation=original.operation, state=original.state, adapter=original.adapter,
            invoked=False, started_at=started_at, completed_at=self._clock.now_iso(),
            duration_ms=max(0, self._clock.monotonic_ms() - started_ms), detail=detail)
        self.attempts.append(attempt)
        return attempt

    # -- the run's own clock --

    @property
    def elapsed_ms(self) -> int:
        return max(0, self._clock.monotonic_ms() - self.started_ms)

    def _closed(self, step_id: str, operation: str, state: StageState, adapter: Optional[str],
                detail: str, *, invoked: bool = False) -> StageAttempt:
        now = self._clock.now_iso()
        attempt = StageAttempt(
            attempt_id=self._ids.mint("att"), step_id=step_id, operation=operation, state=state,
            adapter=adapter, invoked=invoked, started_at=now, completed_at=now,
            duration_ms=0, detail=detail)
        self.attempts.append(attempt)
        return attempt

    @property
    def states(self) -> Tuple[StageState, ...]:
        return tuple(a.state for a in self.attempts)

    @property
    def invoked_any(self) -> bool:
        return any(a.invoked for a in self.attempts)


__all__ = ["RunObserver", "Stage", "ReplayCannotInvoke"]
