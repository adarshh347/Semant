"""
HARNESS-003B — the chain as resumable steps, each deciding from persisted state whether it has run.

## What was wrong with one `begin()`

`coordinator.begin` frames, reads, compiles and deliberates inside one synchronous call. Nothing
about that is incorrect and it cannot be watched: the request returns when the last stage does, so
a person waiting on a two-minute reading sees `Starting…` and nothing else — 002R's first and most
visible finding. It is also all-or-nothing under a crash: a process that died after the theorist's
call left a session with no record that the call had been made and paid for.

This module makes the same order steppable. One step per call, its outcome persisted before the
next begins, and every step deciding FROM THE STORE whether it is pending, running or done.

## Position is read, never carried

`plan()` takes a session and returns the next stage. It consults the attempt ledger and nothing
else — no counter passed between calls, no field saying "we got to here". That is what makes a step
idempotent across a restart, a duplicate schedule and a second process: two drivers asking the same
question of the same document get the same answer, and the CAS on the write decides which one acts.

A stage is DONE when its latest attempt is terminal. A stage is RUNNING when its latest attempt is
`started`. There is no third source of truth, so there is nothing for the ledger to disagree with.

## An interrupted call is never silently re-run

A `started` attempt with no terminal successor means the process ended while the call may have been
in flight. `reopen()` converts it to `interrupted` and STOPS. It does not retry, and the reason is
not caution: a model call is not idempotent. Re-entering one would charge twice for a result the
session may already have had, and could produce a second, different answer for the same recorded
intent — which would then be indistinguishable from the first.

The ambiguity is left visible instead. That is a worse-looking session and a more honest one.

PURE. No database, no network, no clock it was not handed. `driver.py` is what makes these steps
run; this module is what makes them steps.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from backend.schemas.inquiry_session import SemanticInquirySession, StageName, StageOutcome
from backend.schemas.inquiry_stage import StageAttempt, StageAttemptOutcome
from backend.schemas.inquiry_interaction import SessionState

from . import coordinator

#: The order stages are entered. The SAME order `coordinator.begin`/`_continue` already ran, kept
#: as data so the sequence is answerable without reading control flow — and so a test can assert
#: that the stepped path and the monolithic one visit the same stages in the same order.
STEP_ORDER: Tuple[StageName, ...] = (
    StageName.FRAMER, StageName.THEORIST, StageName.COMPILER, StageName.STEWARD,
    StageName.CAPABILITY, StageName.JUDGE, StageName.COMPOSER,
)

#: Stages that enter EXTERNAL, non-idempotent work — a model call or a capability invocation. These
#: are the ones whose `started` attempt must be persisted before the call, and the ones that are
#: never re-entered after an interruption. The framer is deterministic and local; the steward,
#: judge and composer are pure functions of what is already on the session (the composer's model
#: binding is the one exception, and it is listed).
EXTERNAL_STAGES: Tuple[StageName, ...] = (
    StageName.THEORIST, StageName.COMPILER, StageName.CAPABILITY, StageName.COMPOSER,
)

#: Session states from which no further stage is entered. Three are terminal; `awaiting_user` is
#: the one that is not — it is a session that is working correctly and waiting for a person.
HALTED_STATES = (SessionState.AWAITING_USER, SessionState.COMPLETE, SessionState.EXHAUSTED,
                 SessionState.REFUSED, SessionState.ERROR)


class DriverHalted(Exception):
    """The chain cannot continue and the session says why. Not an error — see `Plan.reason`."""


@dataclass(frozen=True)
class Plan:
    """What happens next, and why nothing does when nothing does."""
    stage: Optional[StageName]
    reason: str
    interrupted: Tuple[str, ...] = ()

    @property
    def done(self) -> bool:
        return self.stage is None


def latest_by_stage(session: SemanticInquirySession) -> Dict[str, StageAttempt]:
    """The last attempt recorded for each stage. Later entries win, because the ledger is
    append-only and a stage's second attempt supersedes its first."""
    out: Dict[StageName, StageAttempt] = {}
    for attempt in session.stages:
        out[attempt.stage] = attempt
    return out


def status_of(session: SemanticInquirySession, stage: StageName) -> str:
    """`pending` | `running` | `done`, from the ledger and nothing else."""
    attempt = latest_by_stage(session).get(stage)
    if attempt is None:
        return "pending"
    if attempt.outcome is StageAttemptOutcome.STARTED:
        return "running"
    if attempt.outcome is StageAttemptOutcome.QUEUED:
        return "pending"
    return "done"


def interrupted_stages(session: SemanticInquirySession) -> Tuple[str, ...]:
    """Stages whose last attempt entered external work and never recorded leaving it."""
    return tuple(name.value for name, attempt in latest_by_stage(session).items()
                 if attempt.outcome is StageAttemptOutcome.STARTED)


def plan(session: SemanticInquirySession) -> Plan:
    """Which stage runs next, decided from the persisted session alone.

    Order of checks matters. An interruption is reported BEFORE the halt states, because a session
    that crashed mid-theorist and then had its state written as `exhausted` would otherwise read as
    a finished inquiry rather than an abandoned one.
    """
    dangling = interrupted_stages(session)
    if dangling:
        return Plan(stage=None, interrupted=dangling,
                    reason=(f"{', '.join(sorted(dangling))} entered external work and never "
                            f"recorded leaving it. The call may have happened, so nothing is "
                            f"retried on its own."))

    state = _state_of(session)
    if state in HALTED_STATES:
        return Plan(stage=None, reason=f"the session is {state.value}")

    for stage in STEP_ORDER:
        if status_of(session, stage) == "pending":
            return Plan(stage=stage, reason=f"{stage.value} has not been entered")
    return Plan(stage=None, reason="every stage has been entered")


def _state_of(session: SemanticInquirySession) -> SessionState:
    try:
        return SessionState(session.state)
    except ValueError:
        return SessionState.FRAMING


def reopen(session: SemanticInquirySession, *, at: str) -> SemanticInquirySession:
    """Turn every dangling `started` attempt into a visible `interrupted` one. Never a retry.

    Called when a driver claims a session it did not start. The attempt keeps its `started_at`, so
    a reader can see how long the process was inside the call before it went — which is usually the
    only evidence available about whether the call completed.
    """
    dangling = interrupted_stages(session)
    if not dangling:
        return session
    ledger = coordinator._Ledger(session.session_id, seq=len(session.stages))
    for name in sorted(dangling):
        prior = latest_by_stage(session).get(StageName(name))
        ledger.record(
            StageName(name), StageAttemptOutcome.INTERRUPTED, at=at,
            started_at=prior.started_at if prior else None,
            detail=("this stage entered external work and the process did not return. The call "
                    "may have been made. It is not repeated, because a model or capability call "
                    "is not idempotent and a second one could produce a different answer for the "
                    "same recorded intent."),
            inputs=list(prior.input_refs) if prior else [],
            input_counts=dict(prior.input_counts) if prior else {},
            role=prior.role if prior else "",
            provenance={"interrupted_attempt": prior.attempt_id if prior else ""})
    return session.model_copy(update={
        "stages": [*session.stages, *ledger.events],
        "error": session.error or f"interrupted during {', '.join(sorted(dangling))}",
    })


@dataclass(frozen=True)
class StepResult:
    """One step's effect, and whether the chain may continue."""
    session: SemanticInquirySession
    stage: Optional[StageName]
    started: bool = False
    finished: bool = False
    reason: str = ""


def start(session: SemanticInquirySession, stage: StageName, stages: coordinator.Stages,
          *, at: Optional[str] = None) -> SemanticInquirySession:
    """Record that this stage is being entered. PERSISTED BEFORE THE CALL.

    The order is the whole point of the checkpoint. Written afterwards, a process that died mid-call
    would leave no trace of a call that may have been made and charged for — and the session would
    reopen looking as though the stage had never been tried.
    """
    stamp = at or stages.clock()
    ledger = coordinator._Ledger(session.session_id, seq=len(session.stages))
    ledger.record(stage, StageOutcome.STARTED, at=stamp,
                  detail=f"{stage.value} entered",
                  provenance={"checkpoint": "started, persisted before external work"})
    return session.model_copy(update={"stages": [*session.stages, *ledger.events]})


def run(session: SemanticInquirySession, stage: StageName,
        stages: coordinator.Stages) -> SemanticInquirySession:
    """Do this stage's work and record its terminal attempt.

    The `started` attempt written by `start` is DROPPED from the ledger as the terminal one is
    appended — one attempt per entry, not a started/finished pair, so the ledger is a list of
    stages rather than a list of transitions twice as long as the chain. `started_at` is carried
    across, which is where the duration comes from.
    """
    latest = latest_by_stage(session).get(stage)
    opened = latest if latest is not None and latest.outcome is StageAttemptOutcome.STARTED else None
    trimmed = [a for a in session.stages if opened is None or a.attempt_id != opened.attempt_id]
    working = session.model_copy(update={"stages": trimmed})
    started_at = opened.started_at or opened.queued_at if opened else None

    ledger = coordinator._Ledger(working.session_id, seq=len(trimmed))
    at = stages.clock()
    runner = _RUNNERS[stage]
    advanced = runner(working, stages, ledger, at, started_at)
    return advanced.model_copy(update={"stages": [*advanced.stages, *ledger.events]})


# ── the seven runners ────────────────────────────────────────────────────────
#
# Each delegates to the coordinator's existing stage body. Nothing about WHAT a stage does moved
# here; only when it is entered and what is recorded around it.

def _run_framer(session, stages, ledger, at, started_at):
    return _timed(coordinator._frame, session, stages, ledger, at, started_at)


def _run_theorist(session, stages, ledger, at, started_at):
    advanced, _ = coordinator._read(session, stages, ledger, at)
    return _stamp(advanced, ledger, started_at)


def _run_compiler(session, stages, ledger, at, started_at):
    advanced = coordinator._compile(session, coordinator.reading_of(session), stages, ledger, at)
    return _stamp(advanced, ledger, started_at)


def _run_steward(session, stages, ledger, at, started_at):
    """Open Lane B's state machine if there is a graph to open it about, then offer every fork."""
    if not (session.graph.get("claims") or ()):
        ledger.record(StageName.STEWARD, StageOutcome.SKIPPED, at=at,
                      detail=exhausted_reason(session), started_at=started_at,
                      input_counts=_compiler_counts(session, "input"),
                      output_counts=_compiler_counts(session, "output"))
        return session
    if not coordinator.has_interaction(session):
        session = coordinator._open_interaction(session, stages, ledger, at)
    return _stamp(coordinator._deliberate(session, stages, ledger, at), ledger, started_at)


def _run_capability(session, stages, ledger, at, started_at):
    session = _to_state(session, SessionState.READY, stages, at,
                        "every fork is settled; work may be commissioned")
    session = _to_state(session, SessionState.EXECUTING, stages, at,
                        "commissioning at most one capability request")
    return _stamp(coordinator._execute(session, stages, ledger, at), ledger, started_at)


def _run_judge(session, stages, ledger, at, started_at):
    session = _to_state(session, SessionState.JUDGING, stages, at,
                        "deciding what each claim now rests on")
    return _stamp(coordinator._judge(session, stages, ledger, at), ledger, started_at)


def _run_composer(session, stages, ledger, at, started_at):
    if stages.composer is None:
        ledger.record(StageName.COMPOSER, StageOutcome.SKIPPED, at=at, started_at=started_at,
                      detail="no synthesis composer is bound to this deployment")
        return session
    session = _to_state(session, SessionState.COMPOSING, stages, at,
                        "binding an answer to the claims it rests on")
    return _stamp(coordinator._compose(session, stages, ledger, at), ledger, started_at)


_RUNNERS = {
    StageName.FRAMER: _run_framer,
    StageName.THEORIST: _run_theorist,
    StageName.COMPILER: _run_compiler,
    StageName.STEWARD: _run_steward,
    StageName.CAPABILITY: _run_capability,
    StageName.JUDGE: _run_judge,
    StageName.COMPOSER: _run_composer,
}


def _timed(fn, session, stages, ledger, at, started_at):
    return _stamp(fn(session, stages, ledger, at), ledger, started_at)


def _stamp(session, ledger, started_at):
    """Carry the `started` attempt's clock onto the terminal one this runner just recorded.

    Without it every duration would be null: the stage bodies record their own attempt and know
    nothing about when the driver entered them, which is the only moment the elapsed time is
    measured from.
    """
    if started_at is None or not ledger.events:
        return session
    last = ledger.events[-1]
    if last.started_at is not None or last.completed_at is None:
        return session
    from backend.schemas.inquiry_stage import duration_ms_between
    ledger.events[-1] = last.model_copy(update={
        "started_at": started_at,
        "duration_ms": duration_ms_between(started_at, last.completed_at)})
    return session


def _to_state(session, state, stages, at, reason):
    """Advance Lane B's state machine, when this session has one. A session that compiled nothing
    never opened one and has nothing to advance."""
    if not coordinator.has_interaction(session):
        return session
    current = coordinator.machine.from_dict(session.interaction)
    if current.state in (SessionState.AWAITING_USER, *HALTED_STATES[1:]):
        return session
    advanced = coordinator.machine.advance(current, state, at=at, reason=reason)
    return session.model_copy(update={"interaction": coordinator.machine.to_dict(advanced),
                                      "revision": advanced.revision})


# ── the sentence 002R asked for ──────────────────────────────────────────────

def _compiler_counts(session: SemanticInquirySession, which: str) -> Dict[str, int]:
    attempt = latest_by_stage(session).get(StageName.COMPILER)
    if attempt is None:
        return {}
    return dict(attempt.input_counts if which == "input" else attempt.output_counts)


def exhausted_reason(session: SemanticInquirySession) -> str:
    """Why this inquiry stopped, NAMING the stage and carrying its counts.

    002R's session said "nothing was compiled, so there is nothing to investigate". Every word of
    that was true and it sent nobody anywhere. What a reader needs is which stage came up short and
    what actually passed through it — `31 reading blocks in → 4 claims · 0 observables out` — so the
    difference between a prompt that decomposes into little and a compiler that stopped early is
    visible without opening the store.

    ONLY DECLARED COUNTS. A stage that reported none contributes none; nothing here derives a
    count from a length or from a downstream artifact, because an invented zero reads exactly like
    a measured one.
    """
    latest = latest_by_stage(session)
    ordered = [a for a in (latest.get(s) for s in STEP_ORDER) if a is not None]
    # A stage that RAN and came up short outranks one that never ran. Otherwise a deployment with
    # no framer bound would blame the framer for a compiler that returned nothing — the first
    # barren entry in the order is not the same as the one that actually cost the inquiry its
    # answer.
    lead = next((a for a in ordered if a.underperformed), None) \
        or next((a for a in ordered if a.produced_nothing), None)
    if lead is None:
        return ("nothing was compiled, so there is nothing to investigate and nothing to compose. "
                "That is a result, not a failure.")
    counts = lead.counts_line()
    detail = f" ({counts})" if counts else ""
    tail = f" {lead.summary}" if lead.summary else ""
    return (f"the {lead.stage.value} stage came back {lead.outcome.value}{detail}, so there was "
            f"nothing for the stages after it to work on.{tail} Nothing was invented in its place.")


__all__ = ["STEP_ORDER", "EXTERNAL_STAGES", "HALTED_STATES", "Plan", "StepResult", "DriverHalted",
           "plan", "status_of", "latest_by_stage", "interrupted_stages", "reopen", "start", "run",
           "exhausted_reason"]


# ── closing ──────────────────────────────────────────────────────────────────

def settle(session: SemanticInquirySession, stages: coordinator.Stages) -> SemanticInquirySession:
    """Close the session once every stage has been entered, or leave it where it honestly stands.

    Four outcomes and each is a different sentence to a person:

        awaiting_user   a fork is open. Not closed, not finished, and not a failure.
        error           an attempt is interrupted. The chain stopped and cannot decide for itself
                        whether the call it was inside completed.
        exhausted       every stage was entered and the chain produced no answer. `exhausted_reason`
                        names the stage that came up short and carries its declared counts.
        complete        an answer exists and every sentence of it names what it rests on.
    """
    if interrupted_stages(session):
        return coordinator._finish(session, SessionState.ERROR, stages.clock(),
                                   exhausted_reason(session), stages)
    state = _state_of(session)
    if state in HALTED_STATES:
        return session
    at = stages.clock()
    if session.synthesis is not None and session.synthesis.sections:
        return coordinator._finish(
            session, SessionState.COMPLETE, at,
            "the chain closed: every claim carries a verdict and every sentence of the answer "
            "names what it rests on.", stages)
    return coordinator._finish(session, SessionState.EXHAUSTED, at, exhausted_reason(session),
                               stages)


def advance_all(session: SemanticInquirySession, stages: coordinator.Stages,
                *, limit: int = 32) -> SemanticInquirySession:
    """Every pending stage, in order, to the next honest boundary — the stepped form of `begin`.

    `limit` is a runaway guard, not a budget. Each stage is entered at most once because `plan`
    reads the ledger, so reaching the limit means the ledger stopped recording — a defect, and one
    that would otherwise present as a hung request rather than as a bounded, reported stop.
    """
    for _ in range(limit):
        step = plan(session)
        if step.done:
            return settle(session, stages)
        session = start(session, step.stage, stages)
        session = run(session, step.stage, stages)
    raise DriverHalted(
        f"session {session.session_id} did not reach a boundary in {limit} steps. Every stage is "
        f"entered at most once, so this means a stage ran without recording a terminal attempt.")


__all__ = [*__all__, "settle", "advance_all"]
