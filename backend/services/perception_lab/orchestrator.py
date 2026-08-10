"""
PERCEPTUAL-ORGANS-002 Lane D — the conductor.

    prompt or control + selected organ + session manifest
      -> proposed plan
      -> closed resolver
      -> visible resolved plan, refusals, dropped and clamped parameters
      -> EXPLICIT execution
      -> injected adapter
      -> observer
      -> contract-valid run and artifact history
      -> restrained templated response

Deliberately smaller than the inquiry engine, and the smallness is the specification: this thing
translates intent into a closed vocabulary and records what happened. It does not reason about
pictures, and there is no component here that could.

THE FOUR LINES BETWEEN PLANNING AND RUNNING, and each is a separate call a person makes:

    plan_prompt / plan_direct   proposes, resolves, stores, and returns something to LOOK at
    execute                     runs, and refuses to run an unconfirmed plan that asked to be
    replay                      re-shows, with no registry in reach
    review                      a person's verdict, which is none of the above

`execute` raising `ConfirmationRequired` rather than refusing is on purpose. A refusal is what the
laboratory says to a PERSON about their request; a caller that ran a plan whose
`requires_confirmation` is true has a bug, and turning that into a polite refusal record would let
the bug ship looking like a feature. Same for `NothingToRun`.

WHAT THIS FILE CANNOT REACH, and the orchestration suite proves it by walking the import graph:
posts, regions, marks, Ground, percepts, the database, Director, HARNESS. The store interface it
was handed has five record types on it and none of them is a post, so "lab execution is
non-mutating" is not a rule this code follows — it is a description of what it was given.

WHAT IT OWNS THAT AN ADAPTER MUST NOT. Every id in the laboratory, the clock, the outcome of a
run, and the decision that a stage was invoked.

PURE apart from what is injected: a store, a registry, a clock, an id factory, and the planners.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.perception_lab import (ArtifactIdentity, ArtifactKind, ArtifactLifecycle,
                                            ArtifactProvenance, ExecutionIdentity, IdentityScope,
                                            InputRef, LabPlan, LabReview, LabRun, LabSession,
                                            LabSource, LifecycleState, OrganFamily,
                                            PerceptualArtifact, ProducerKind, RefusalCode,
                                            RefusalRecord, ResolvedStep, ReviewCorrection,
                                            ReviewVerdict, RunOutcome, SessionMode, StageState)
from backend.services.perception_lab.adapters import (AdapterCall, AdapterRegistry, CallBudget,
                                                      Cancelled, CancelToken, NotRegistered)
from backend.services.perception_lab.clock import Clock, IdFactory, SystemClock, UuidIds
from backend.services.perception_lab.definitions import _message as contract_message
from backend.services.perception_lab.definitions import check_inputs, operation
from backend.services.perception_lab.observer import RunObserver
from backend.services.perception_lab.planners import (DirectCommand, DirectPlanner, ModelPlanner,
                                                      RulesPlanner)
from backend.services.perception_lab.resolver import Proposal, Resolution, resolve
from backend.services.perception_lab.response import LabResponse, respond
from backend.services.perception_lab.session import SessionMachine, SessionView
from backend.services.perception_lab.store import InMemoryLabStore, LabStore, resolve_inputs

PRODUCER = "perception_lab/conductor-v1"


class ConfirmationRequired(RuntimeError):
    """A plan that asked to be confirmed was executed without confirmation.

    Raised rather than refused. See the module docstring: a refusal is an answer to a person, and
    this is a caller with a bug.
    """

    def __init__(self, plan: LabPlan):
        super().__init__(
            f"plan {plan.plan_id!r} requires confirmation and was not confirmed. The crossing, "
            f"the sweep or the prerequisite it carries is a decision, and executing it silently "
            f"would make the confirmation flag decorative.")
        self.plan = plan


class NothingToRun(RuntimeError):
    """A plan with no resolved steps and no refusals. The planner proposed nothing at all.

    Not a run with a sad outcome: a run is a record of something having been attempted, and
    minting one here would put an entry in the ledger for a question nobody managed to ask.
    """


@dataclass(frozen=True)
class Execution:
    """One run, everything it made, and what the laboratory says about it."""
    run: LabRun
    plan: LabPlan
    artifacts: Tuple[PerceptualArtifact, ...]
    response: LabResponse

    @property
    def outcome(self) -> RunOutcome:
        return self.run.outcome

    @property
    def identity(self) -> ExecutionIdentity:
        return self.run.execution_identity


class PerceptionConductor:
    """The organ-scoped conductor. One per process is fine; one per request is fine too."""

    def __init__(self, *, store: Optional[LabStore] = None,
                 registry: Optional[AdapterRegistry] = None,
                 clock: Optional[Clock] = None, ids: Optional[IdFactory] = None,
                 rules: Optional[RulesPlanner] = None, model: Optional[ModelPlanner] = None,
                 direct: Optional[DirectPlanner] = None,
                 budget: Optional[CallBudget] = None,
                 source_probe: Optional[Any] = None):
        self.store = store if store is not None else InMemoryLabStore()
        self.registry = registry if registry is not None else AdapterRegistry()
        self.clock = clock if clock is not None else SystemClock()
        self.ids = ids if ids is not None else UuidIds()
        self.rules = rules if rules is not None else RulesPlanner(self.ids)
        self.model = model
        self.direct = direct if direct is not None else DirectPlanner(self.ids)
        self.budget = budget if budget is not None else CallBudget()
        #: Optional callable returning the source digest as it is RIGHT NOW. Lane F wires it. With
        #: no probe the run records `source_digest_after: None`, which is honestly "nobody
        #: looked" — rather than copying the before-digest forward, which would be this file
        #: asserting the image did not move on no evidence at all.
        self.source_probe = source_probe

    # -- sessions --

    def open_session(self, *, source: LabSource, organ: OrganFamily,
                     mode: SessionMode = SessionMode.ISOLATION) -> SessionMachine:
        machine = SessionMachine.open(source=source, organ=organ, mode=mode, clock=self.clock,
                                      ids=self.ids)
        self.store.put_session(machine.session)
        return machine

    def save(self, machine: SessionMachine) -> LabSession:
        return self.store.put_session(machine.session)

    def reopen(self, session_id: str) -> SessionMachine:
        session = self.store.get_session(session_id)
        if session is None:
            raise KeyError(f"no session {session_id!r} in this store")
        return SessionMachine(session, clock=self.clock, ids=self.ids)

    # -- planning --

    def plan_direct(self, machine: SessionMachine,
                    *commands: DirectCommand) -> Resolution:
        """A control press, or several. No prompt turn is recorded: nobody said anything."""
        return self._resolve(machine, self.direct.plan_many(list(commands), machine.view()))

    def plan_prompt(self, machine: SessionMachine, prompt: str, *,
                    planner: str = "rules") -> Resolution:
        """A sentence. The turn is recorded BEFORE the plan exists and bound to it after.

        In that order because the turn is what the person did and the plan is what the laboratory
        made of it. Recording the turn only on success would lose every sentence that refused,
        and those are the sentences worth reading later.
        """
        turn = machine.record_turn(prompt)
        arm = self._planner(planner)
        resolution = self._resolve(machine, arm.plan(prompt, machine.view()))
        machine.attach_plan(turn.turn_id, resolution.plan.plan_id)
        self.store.put_session(machine.session)
        return resolution

    def _planner(self, name: str):
        if name == "rules":
            return self.rules
        if name == "model":
            if self.model is None:
                raise KeyError(
                    "no model planner is configured. There is no implicit fallback here: a "
                    "caller that asked for the model arm and silently got the rules arm would be "
                    "the exact dishonesty `planner_fell_back_from` exists to prevent. Configure "
                    "one, or ask for 'rules'.")
            return self.model
        raise KeyError(f"{name!r} is not a planner arm; the three are direct, rules and model")

    def _resolve(self, machine: SessionMachine, proposal: Proposal) -> Resolution:
        resolution = resolve(proposal, machine.view(),
                             capabilities=self.registry.capabilities(), clock=self.clock,
                             ids=self.ids)
        self.store.put_plan(resolution.plan)
        return resolution

    # -- execution --

    def execute(self, machine: SessionMachine, plan: LabPlan, *, confirmed: bool = False,
                cancel: Optional[CancelToken] = None,
                identity: ExecutionIdentity = ExecutionIdentity.LIVE) -> Execution:
        """Run an authorized plan. The only path in this lane that reaches an adapter."""
        if plan.requires_confirmation and not confirmed:
            raise ConfirmationRequired(plan)
        if not plan.resolved_steps and not plan.refusals:
            raise NothingToRun(
                f"plan {plan.plan_id!r} authorized nothing and refused nothing. The planner "
                f"proposed no operation, and a run recording that would be a ledger entry for a "
                f"question nobody managed to ask.")

        cancel = cancel if cancel is not None else CancelToken()
        run_id = self.ids.mint("run")
        observer = RunObserver(run_id, clock=self.clock, ids=self.ids,
                               may_invoke=identity is ExecutionIdentity.LIVE)
        session = machine.session
        refusals: List[RefusalRecord] = []
        artifacts: List[PerceptualArtifact] = []
        calls = 0

        # Plan-level refusals become stages too, so the stage stream is the WHOLE story of the
        # request rather than only of the part that survived the resolver.
        for refusal in plan.refusals:
            refusals.append(refusal)
            observer.refused(self._step_id_for(plan, refusal), refusal.operation or "(none)",
                             refusal.message)

        for step in plan.resolved_steps:
            if cancel.cancelled:
                observer.skipped(step.step_id, step.operation,
                                 cancel.reason or "cancelled by the person", step.adapter)
                continue
            if self.budget.exceeded_calls(calls):
                observer.skipped(step.step_id, step.operation,
                                 f"the run's budget of {self.budget.max_adapter_calls} adapter "
                                 f"calls was already spent", step.adapter)
                continue
            if self.budget.exceeded_wall(observer.elapsed_ms):
                observer.skipped(step.step_id, step.operation,
                                 f"the run's budget of {self.budget.max_wall_ms}ms was already "
                                 f"spent", step.adapter)
                continue

            made, refusal, artifact = self._run_step(step, plan, session, observer, cancel)
            calls += made
            if refusal is not None:
                refusals.append(refusal)
            if artifact is not None:
                artifacts.append(artifact)

        digest_after, mutated = self._check_source(session)
        if mutated is not None:
            refusals.append(mutated)

        run = LabRun(
            run_id=run_id, session_id=session.session_id, execution_identity=identity,
            outcome=self._outcome(observer.states, artifacts, refusals, mutated is not None),
            requested_plan_id=plan.plan_id, resolved_plan_id=plan.plan_id,
            artifact_ids=[a.identity.artifact_id for a in artifacts],
            stage_attempts=observer.attempts, refusals=refusals,
            source_digest_before=session.source.image_digest, source_digest_after=digest_after,
            started_at=observer.started_at, completed_at=self.clock.now_iso(),
            duration_ms=observer.elapsed_ms)
        self.store.put_run(run)
        machine.record_run(run_id)
        self.store.put_session(machine.session)
        return Execution(run=run, plan=plan, artifacts=tuple(artifacts),
                         response=respond(run, plan, artifacts))

    def _run_step(self, step: ResolvedStep, plan: LabPlan, session: LabSession,
                  observer: RunObserver, cancel: CancelToken
                  ) -> Tuple[int, Optional[RefusalRecord], Optional[PerceptualArtifact]]:
        """One authorized step, from its inputs to its artifact. Returns (calls made, …)."""
        inputs = resolve_inputs(self.store, step.input_refs)

        # THE EXECUTION-TIME INPUT CHECK, against what actually RESOLVED rather than what was
        # cited. This is where `topology.occlusion` meets `missing_depth_artifact`: the depth
        # input is optional to plan and required to run, and the two moments are two calls to the
        # same function with one boolean between them.
        present = [r for r in step.input_refs
                   if r.region_id is not None
                   or any(a.identity.artifact_id == r.artifact_id
                          for a in inputs.get(r.role, ()))]
        missing = check_inputs(step.operation, present, for_execution=True)
        if missing is not None:
            observer.refused(step.step_id, step.operation, missing.message, step.adapter)
            return 0, missing, None

        try:
            adapter = self.registry.resolve(step.operation, step.adapter)
        except NotRegistered as exc:
            refusal = RefusalRecord(
                code=RefusalCode.CAPABILITY_UNAVAILABLE, organ=step.organ,
                operation=step.operation,
                message=contract_message("capability_unavailable",
                                         adapter=step.adapter or "(none)"),
                missing=[step.adapter] if step.adapter else [],
                remedy="choose another adapter, or run where the model lives",
                detail={"why": str(exc)})
            observer.unavailable(step.step_id, step.operation, refusal.message, step.adapter)
            return 0, refusal, None

        stage = observer.begin(step.step_id, step.operation, adapter.name, invoking=True)
        call = AdapterCall(
            session_id=session.session_id, run_id=observer.run_id, step_id=step.step_id,
            organ=step.organ, operation=step.operation, adapter=adapter.name,
            parameters=dict(step.parameters), input_refs=tuple(step.input_refs),
            inputs={role: tuple(found) for role, found in inputs.items()},
            source=session.source, cancel=cancel,
            deadline_ms=max(0, self.budget.max_wall_ms - observer.elapsed_ms))
        try:
            outcome = adapter.invoke(call)
        except Cancelled as exc:
            observer.end(stage, StageState.SKIPPED, str(exc) or "cancelled during the call")
            return 1, None, None
        except Exception as exc:                      # noqa: BLE001 - an organ may raise anything
            observer.end(stage, StageState.FAILED, f"{type(exc).__name__}: {exc}")
            return 1, None, None

        attempt = observer.end(stage, outcome.state, outcome.detail)
        if outcome.state in (StageState.COMPLETED, StageState.EMPTY):
            artifact = self._artifact(step, outcome, attempt, session, observer.run_id)
            self.store.put_artifact(artifact)
            return 1, None, artifact
        return 1, outcome.refusal, None

    def _artifact(self, step: ResolvedStep, outcome, attempt, session: LabSession,
                  run_id: str) -> PerceptualArtifact:
        """The adapter's measurement, wrapped in the identity and receipt only the lab can give.

        `producer_kind` is read from the operation rather than the adapter's name: a MANUAL
        operation is a person's hand, and `ArtifactProvenance` refuses a human-produced artifact
        that names an adapter — because one that did would be indistinguishable from a segmented
        mask in every later report.
        """
        manual = operation(step.operation).manual
        return PerceptualArtifact(
            identity=ArtifactIdentity(
                artifact_id=self.ids.mint("art"), session_id=session.session_id, run_id=run_id,
                step_id=step.step_id, organ_family=step.organ,
                artifact_kind=ArtifactKind(outcome.measurement.payload_variant),
                operation=step.operation, identity_scope=IdentityScope.SESSION,
                input_refs=list(step.input_refs),
                derived_from=[r.artifact_id for r in step.input_refs
                              if r.artifact_id is not None]),
            measurement=outcome.measurement,
            projection=outcome.projection,
            interpretation=outcome.interpretation,
            lifecycle=ArtifactLifecycle(status=LifecycleState.PROPOSED,
                                        changed_at=self.clock.now_iso(), changed_by=PRODUCER),
            provenance=ArtifactProvenance(
                producer_kind=ProducerKind.HUMAN if manual else ProducerKind.ADAPTER,
                producer=step.adapter or PRODUCER,
                adapter=None if manual else step.adapter,
                model=None if manual else outcome.model, revision=outcome.revision,
                source_image_digest=session.source.image_digest,
                started_at=attempt.started_at, completed_at=attempt.completed_at,
                duration_ms=attempt.duration_ms, device=outcome.device,
                peak_memory_mb=outcome.peak_memory_mb))

    def replay(self, machine: SessionMachine, source_run_id: str) -> Execution:
        """Re-show a run. NOTE WHAT IS NOT PASSED: `self.registry`.

        The late import is not a cycle workaround dressed up — `replay` imports `Execution` from
        here, and putting the call here rather than the type there is what keeps the replay module
        free of every adapter symbol in the lane. The conductor holds a live registry; this method
        is the one place it deliberately does not hand it on.
        """
        from backend.services.perception_lab.replay import replay as _replay
        return _replay(source_run_id, machine, store=self.store, clock=self.clock, ids=self.ids)

    # -- reviews: a person's verdict, which is none of the three other axes --

    def review(self, machine: SessionMachine, artifact_id: str, *, reviewer: str,
               verdict: ReviewVerdict, notes: Optional[str] = None,
               corrections: Sequence[ReviewCorrection] = ()) -> LabReview:
        """Record what a person thought. It changes no lifecycle and no epistemic status.

        Saying `correct` does not make a box-basis containment `measured` and does not make the
        artifact `kept`. Three decisions, three deciders, and this method makes exactly one of
        them — which is why it does not touch the artifact at all.
        """
        if self.store.get_artifact(artifact_id) is None:
            raise KeyError(f"no artifact {artifact_id!r} in this store to review")
        review = LabReview(review_id=self.ids.mint("rev"), session_id=machine.session.session_id,
                           artifact_id=artifact_id, reviewer=reviewer, verdict=verdict,
                           notes=notes, corrections=list(corrections),
                           reviewed_at=self.clock.now_iso())
        self.store.put_review(review)
        machine.record_review(review.review_id)
        self.store.put_session(machine.session)
        return review

    # -- the pieces --

    def _check_source(self, session: LabSession) -> Tuple[Optional[str], Optional[RefusalRecord]]:
        if self.source_probe is None:
            return None, None
        now = str(self.source_probe())
        if now == session.source.image_digest:
            return now, None
        return now, RefusalRecord(
            code=RefusalCode.SOURCE_MUTATED, organ=session.selected_organ,
            message=contract_message("source_mutated"),
            missing=[], remedy="re-open the session against the current source",
            detail={"before": session.source.image_digest, "after": now})

    @staticmethod
    def _step_id_for(plan: LabPlan, refusal: RefusalRecord) -> str:
        for step in plan.proposed_steps:
            if step.operation == refusal.operation:
                return step.step_id
        return "plan"

    @staticmethod
    def _outcome(states: Sequence[StageState], artifacts: Sequence[PerceptualArtifact],
                 refusals: Sequence[RefusalRecord], mutated: bool) -> RunOutcome:
        """The six endings, decided from the record rather than asserted alongside it.

        The order of these branches is the order in which the answers stop being true, and each
        of the four boundaries is a distinction the absence vocabulary exists to keep:

          MUTATED first — a measurement of an image that moved is a measurement of neither, so
          nothing else about the run can be reported as its result.

          FAILED next — something raised, and `failed` means no claim is made at all.

          REFUSALS before EMPTY — because `LabRun` forbids `ready`/`empty` with a refusal
          attached: two answers in one record. A run with some artifacts and some refusals is
          `partial`, which is the honest word for it, and one with only refusals is `refused`
          unless every one of them is a capability, in which case `unavailable` names the thing
          that is not here.

          EMPTY before READY — every stage having looked and found nothing is a MEASURED
          emptiness, and it is not the same answer as having found something.
        """
        if mutated:
            return RunOutcome.FAILED
        if StageState.FAILED in states:
            return RunOutcome.FAILED
        if refusals:
            if artifacts:
                return RunOutcome.PARTIAL
            if all(r.code is RefusalCode.CAPABILITY_UNAVAILABLE for r in refusals):
                return RunOutcome.UNAVAILABLE
            return RunOutcome.REFUSED
        if StageState.SKIPPED in states:
            # Cancelled, or out of budget. No law said no; the run stopped asking. `partial` when
            # something was produced, `failed` when nothing was — see `CallBudget`.
            return RunOutcome.PARTIAL if artifacts else RunOutcome.FAILED
        if not artifacts:
            return RunOutcome.FAILED
        if all(s is StageState.EMPTY for s in states if s in (StageState.EMPTY,
                                                             StageState.COMPLETED)):
            return RunOutcome.EMPTY
        return RunOutcome.READY


__all__ = ["PerceptionConductor", "Execution", "ConfirmationRequired", "NothingToRun", "PRODUCER"]
