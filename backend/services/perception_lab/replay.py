"""
PERCEPTUAL-ORGANS-002 Lane D — replay: a run re-shown, with nothing in reach to re-run it.

A replay reopens what happened. It is not a cheaper way to run something again, and the difference
is the entire point: if a REPLAY could recompute, then `LIVE` and `REPLAY` would be two words for
the same event and the badge on the screen would mean nothing.

FOUR INDEPENDENT GUARDS, because one guard is a guard somebody eventually moves:

  1. STRUCTURAL — `replay()` never receives an `AdapterRegistry`. There is no parameter for one
     and no attribute holding one. The most direct way to invoke an adapter from here is to
     import the registry, and nothing in this file does.

  2. SEALED — `SealedAdapterRegistry` satisfies the same shape a live registry does and raises
     from `resolve()` BEFORE returning an adapter. It exists for the path where some future code
     is handed "a registry" and does not check which kind. Its `capabilities()` is empty: nothing
     is callable, and saying so is different from saying nothing is loadable.

  3. OBSERVED — the replay's `RunObserver` is built with `may_invoke=False`, so the single line in
     this lane that can set `invoked=True` raises instead.

  4. VALIDATED — `LabRun` refuses to hold a non-LIVE run with an invoked stage on it. This is the
     LAST guard, not the first, and the ordering matters: by the time a schema refuses the record,
     a call would already have happened.

WHAT A REPLAY DOES WITH TIME. It re-times itself. The original stage's 1840ms measured a model;
this measures a dictionary lookup, and carrying the first number onto the second would erase the
one column that distinguishes the two runs. The contract's own `run.replay-extent.json` fixture
makes the same point in its `detail`.

WHEN THE LEDGER CANNOT ANSWER. A source run that is not in the store, or one whose artifacts are
gone, is `replay_cannot_recompute` — a REFUSAL, with a REPLAY identity and an outcome of
`refused`. Not an attempt to rebuild the missing artifact from the plan, which is the one thing a
replay must never do, and which would be easy: the plan is right there.

PURE. No database, no network, no model, no adapter. Clock, ids and store are injected.
"""
from __future__ import annotations

from typing import Mapping, Optional, Sequence, Tuple

from backend.schemas.perception_lab import (CapabilityState, ExecutionIdentity, LabPlan, LabRun,
                                            PerceptualArtifact, RefusalCode, RefusalRecord,
                                            ReplayProvenance, RunOutcome)
from backend.services.perception_lab.adapters import NotRegistered
from backend.services.perception_lab.clock import Clock, IdFactory
from backend.services.perception_lab.definitions import _message as contract_message
from backend.services.perception_lab.observer import RunObserver
from backend.services.perception_lab.orchestrator import Execution
from backend.services.perception_lab.response import respond
from backend.services.perception_lab.session import SessionMachine
from backend.services.perception_lab.store import LabStore


class ReplayCannotRecompute(NotRegistered):
    """Something asked a replay for an adapter.

    Subclasses `NotRegistered` so that a caller written against the live registry's failure mode
    still handles it — but with its own name, because "not wired here" and "this run may never
    call anything" are two different facts and a reader of a traceback deserves the second.
    """


class SealedAdapterRegistry:
    """A registry shaped like the real one that will never hand anything back.

    GUARD 2. `replay()` does not use this — it has no registry at all — and that is exactly why it
    exists: the guard for the code that does not exist yet, which will be handed "a registry" by
    a Lane F route and will not think to ask which kind it is.
    """

    def register(self, adapter) -> "SealedAdapterRegistry":
        raise ReplayCannotRecompute(
            f"nothing may be registered on a replay registry; {getattr(adapter, 'name', adapter)!r} "
            f"was offered")

    def resolve(self, op_key: str, adapter_name: Optional[str]):
        raise ReplayCannotRecompute(
            f"a replay asked for adapter {adapter_name!r} to run {op_key!r}. A replay has nothing "
            f"to call: its content is the record of a call that already happened, and calling "
            f"again would produce a different measurement wearing this run's identity.")

    def capabilities(self) -> Mapping[str, CapabilityState]:
        """Empty. Nothing is callable here, which is not the same claim as nothing being
        loadable — so no adapter is reported `unavailable` either."""
        return {}

    @property
    def names(self) -> Tuple[str, ...]:
        return ()


def replay(source_run_id: str, machine: SessionMachine, *, store: LabStore, clock: Clock,
           ids: IdFactory) -> Execution:
    """Re-show a run. GUARD 1: there is no registry parameter, and no adapter is importable here.

    The new run is REPLAY, its stages are re-timed, every `invoked` is false, and it names the run
    it replays. Its artifacts are the ORIGINAL artifact ids — a replay does not copy a measurement
    into a new identity, because two artifact ids carrying one measurement is how a lab ends up
    reviewing the same mask twice and counting it as agreement.
    """
    run_id = ids.mint("run")
    observer = RunObserver(run_id, clock=clock, ids=ids, may_invoke=False)
    session = machine.session
    source = store.get_run(source_run_id)

    if source is None:
        return _refuse(run_id, observer, machine, store,
                       f"run {source_run_id!r} is not in this laboratory's ledger",
                       source_run_id, clock, recorded_at=clock.now_iso())

    plan = store.get_plan(source.resolved_plan_id or source.requested_plan_id)
    artifacts = [a for a in (store.get_artifact(i) for i in source.artifact_ids) if a is not None]
    lost = [i for i in source.artifact_ids if store.get_artifact(i) is None]
    if lost:
        return _refuse(run_id, observer, machine, store,
                       f"the ledger no longer holds {', '.join(lost)}. A replay re-shows what was "
                       f"measured; it does not rebuild it from the plan",
                       source_run_id, clock, recorded_at=source.completed_at or source.started_at
                       or clock.now_iso(), plan=plan)

    for attempt in source.stage_attempts:
        observer.reshown(attempt,
                         f"re-shown from run {source.run_id}. The {attempt.duration_ms}ms on that "
                         f"run measured the organ; this measures the reading of it.")

    run = LabRun(
        run_id=run_id, session_id=session.session_id,
        execution_identity=ExecutionIdentity.REPLAY, outcome=source.outcome,
        requested_plan_id=source.requested_plan_id, resolved_plan_id=source.resolved_plan_id,
        artifact_ids=list(source.artifact_ids), stage_attempts=observer.attempts,
        refusals=list(source.refusals),
        source_digest_before=source.source_digest_before,
        source_digest_after=source.source_digest_after,
        started_at=observer.started_at, completed_at=clock.now_iso(),
        duration_ms=observer.elapsed_ms,
        replay=ReplayProvenance(
            source_run_id=source.run_id,
            recorded_at=source.completed_at or source.started_at or session.created_at,
            adapter_callable=False,
            reason="re-opened from the lab ledger"))
    store.put_run(run)
    machine.record_run(run_id)
    store.put_session(machine.session)
    return Execution(run=run, plan=plan or _placeholder(source, session), artifacts=tuple(artifacts),
                     response=respond(run, plan or _placeholder(source, session), artifacts))


def _refuse(run_id: str, observer: RunObserver, machine: SessionMachine, store: LabStore,
            why: str, source_run_id: str, clock: Clock, *, recorded_at: str,
            plan: Optional[LabPlan] = None) -> Execution:
    """A replay that cannot be shown. Still a REPLAY run, and still records nothing was called."""
    session = machine.session
    refusal = RefusalRecord(
        code=RefusalCode.REPLAY_CANNOT_RECOMPUTE, organ=session.selected_organ,
        message=contract_message("replay_cannot_recompute"), missing=[source_run_id],
        remedy="run LIVE if you want a new measurement", detail={"why": why})
    observer.refused("plan", "(replay)", why)
    run = LabRun(
        run_id=run_id, session_id=session.session_id,
        execution_identity=ExecutionIdentity.REPLAY, outcome=RunOutcome.REFUSED,
        requested_plan_id=plan.plan_id if plan else source_run_id,
        artifact_ids=[], stage_attempts=observer.attempts, refusals=[refusal],
        source_digest_before=session.source.image_digest,
        started_at=observer.started_at, completed_at=clock.now_iso(),
        duration_ms=observer.elapsed_ms,
        replay=ReplayProvenance(source_run_id=source_run_id, recorded_at=recorded_at,
                                adapter_callable=False, reason=why))
    store.put_run(run)
    machine.record_run(run_id)
    store.put_session(machine.session)
    resolved_plan = plan or _placeholder(run, session)
    return Execution(run=run, plan=resolved_plan, artifacts=(),
                     response=respond(run, resolved_plan, ()))


def _placeholder(run, session) -> LabPlan:
    """A plan record for a response whose original plan is gone from the ledger.

    Carries the session's own organ and mode and NOTHING else — no steps, no planner claim beyond
    `direct`, no refusals. A replay whose plan is missing should look like a replay whose plan is
    missing, not like a plan that authorized nothing.
    """
    from backend.schemas.perception_lab import PlannerIdentity
    return LabPlan(
        plan_id=getattr(run, "requested_plan_id", "(unknown)"), session_id=session.session_id,
        planner=PlannerIdentity.DIRECT, selected_organ=session.selected_organ, mode=session.mode,
        requires_confirmation=False, created_at=session.created_at)


__all__ = ["replay", "SealedAdapterRegistry", "ReplayCannotRecompute"]
