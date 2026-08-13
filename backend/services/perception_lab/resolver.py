"""
PERCEPTUAL-ORGANS-002 Lane D — the resolver: the only thing in the laboratory that authorizes.

Three planners feed this one function. A direct button press, a deterministic phrase match and a
language model's structured output all arrive as the same `Proposal`, and all five gates run on
all three identically. That is the architecture in one sentence: THE PLANNER PROPOSES, THE
RESOLVER AUTHORIZES, and the difference between the arms is where the proposal came from and
nothing else.

The mechanism is Lane A's, not a new one. `ProposedStep` has no authorization field to set, and
`ResolvedStep.authorized_by` is `Literal["resolver"]` — so "a planner cannot grant itself
permission" is not a rule anyone obeys, it is a sentence that cannot be typed. This module is the
only place in the lane that constructs a `ResolvedStep`.

FIVE GATES, IN THIS ORDER, and the order is a decision about what a person is told first:

    1. organ lock      unsupported_operation | organ_locked
    2. references      unknown_reference
    3. parameters      invalid_parameters  (+ dropped and clamped, recorded either way)
    4. inputs          missing_extent_inputs | missing_depth_artifact
    5. capability      capability_unavailable

Organ lock is first because it is the law of the session, and a person who asked a topology
question of an extent session needs to hear THAT, not that their parameters were also wrong.
References come before parameters because an invented id is a categorically worse failure than a
bad number: one is a caller that mistyped, the other is a planner that made something up.

WHAT IS RECORDED EVEN WHEN A STEP DIES. Dropped and clamped parameters. A step that refuses at the
inputs gate still contributes its dropped keys to the plan, because "the model tried to hand the
runner a mask_rle" is the observation worth having, and losing it because a LATER gate refused
would hide the smuggling attempt behind the refusal that happened to come after it.

WHAT THIS MODULE NEVER DOES. Call an adapter, read a store, look at an image, mint an artifact, or
decide anything from a prompt's words. It reads a proposal, a session view and a capability table.

PURE. No database, no network, no model. The clock and the id factory are injected.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.perception_lab import (CapabilityState, ClampedParameter, DroppedParameter,
                                            LabPlan, OrganFamily, PlannerIdentity, ProposedStep,
                                            RefusalCode, RefusalRecord, ResolvedStep, SessionMode)
from backend.services.perception_lab.clock import Clock, IdFactory
# Deliberately the module-private template filler rather than a second one written here. Lane A's
# argument against a fallback contract applies exactly: two functions that fill the same templates
# are two sentences said to one person, and they drift on the first edit.
from backend.services.perception_lab.definitions import (_message as contract_message,
                                                         OperationDefinition, check_capability,
                                                         check_inputs, check_organ_lock,
                                                         operation, operations, resolve_parameters)
from backend.services.perception_lab.session import SessionView


class IsolationBreach(RuntimeError):
    """A resolved step left the locked organ.

    NOT a refusal. A refusal is what this laboratory says to a person who asked for something it
    will not do; this is what it says to itself when the lock it just applied did not hold. There
    is no message worth showing a person here, because the only correct response is a fix.
    """


@dataclass(frozen=True)
class Proposal:
    """What a planner produced. Carries no authority, and has no field in which to claim any.

    `refusals` is on the PROPOSAL as well as on the plan because some refusals are the planner's
    own and could not be anything else — a model that named an operation nobody registered is
    refused where the name was read, and the resolver never sees a step for it. Those refusals
    travel here so the plan can carry them beside the resolver's.
    """
    planner: PlannerIdentity
    steps: Tuple[ProposedStep, ...] = ()
    fell_back_from: Optional[PlannerIdentity] = None
    refusals: Tuple[RefusalRecord, ...] = ()
    prerequisites: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Resolution:
    """The plan, plus the things a plan has no field for.

    `notes` are the planner's and the resolver's remarks to a reader. They are NOT refusals and
    the response builder never turns one into an outcome; keeping them off `LabPlan` is what stops
    a note from being mistaken for a reason something did not run.
    """
    plan: LabPlan
    notes: Tuple[str, ...] = ()

    @property
    def authorized(self) -> bool:
        return bool(self.plan.resolved_steps)


def resolve(proposal: Proposal, session: SessionView, *,
            capabilities: Mapping[str, CapabilityState],
            clock: Clock, ids: IdFactory,
            plan_id: Optional[str] = None) -> Resolution:
    """A proposal, through five gates, into a plan a runner may execute.

    Returns a plan whether or not anything survived. A plan with no resolved steps and three
    refusals is the useful answer to a request this laboratory will not perform, and returning
    `None` instead would throw away every reason it gave.
    """
    resolved: List[ResolvedStep] = []
    refusals: List[RefusalRecord] = list(proposal.refusals)
    dropped: List[DroppedParameter] = []
    clamped: List[ClampedParameter] = []
    prerequisites: List[str] = list(proposal.prerequisites)
    notes: List[str] = list(proposal.notes)
    confirm = False

    for step in proposal.steps:
        outcome = _resolve_step(step, proposal, session, capabilities)
        dropped.extend(outcome.dropped)
        clamped.extend(outcome.clamped)
        prerequisites.extend(outcome.prerequisites)
        if outcome.prerequisites:
            confirm = True
        if outcome.refusal is not None:
            refusals.append(outcome.refusal)
            continue
        resolved.append(outcome.step)                      # type: ignore[arg-type]
        confirm = confirm or operation(step.operation).requires_confirmation

    # ── the isolation firewall ──
    #
    # `LabPlan` refuses a crossing plan too, and this check is deliberately in front of it. A
    # ValidationError from a schema says "this object is malformed"; this says which step crossed
    # and that the lock — not the schema — is what failed. The mutation test disables a gate and
    # expects THIS, because a lane that only ever saw the schema's error could remove every gate
    # in this file and still look protected.
    if session.mode is SessionMode.ISOLATION:
        crossing = [s.step_id for s in resolved if s.organ is not session.selected_organ]
        if crossing:
            raise IsolationBreach(
                f"the resolver authorized {crossing} outside the locked {session.selected_organ.value} "
                f"organ. In isolation mode a prompt may not change organs, and a resolver that "
                f"produced this plan has stopped being the thing that authorizes.")

    # ── an explicit crossing asks first, and says so where a person can read it ──
    if session.mode is SessionMode.CHAIN and len({s.organ for s in resolved}) > 1:
        confirm = True
        prerequisites.append(
            "this chain crosses the organ boundary. Every stage keeps its own artifact, adapter, "
            "timing and status, and the result is never collapsed into one organ's finding.")

    plan = LabPlan(
        plan_id=plan_id or ids.mint("plan"),
        session_id=session.session_id,
        planner=proposal.planner,
        planner_fell_back_from=proposal.fell_back_from,
        selected_organ=session.selected_organ,
        mode=session.mode,
        proposed_steps=list(proposal.steps),
        resolved_steps=resolved,
        prerequisites=prerequisites,
        refusals=refusals,
        dropped_parameters=dropped,
        clamped_parameters=clamped,
        requires_confirmation=confirm,
        created_at=clock.now_iso())
    return Resolution(plan=plan, notes=tuple(notes))


# ── one step, through the gates ──────────────────────────────────────────────


@dataclass
class _StepOutcome:
    step: Optional[ResolvedStep] = None
    refusal: Optional[RefusalRecord] = None
    dropped: List[DroppedParameter] = field(default_factory=list)
    clamped: List[ClampedParameter] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)


def _resolve_step(step: ProposedStep, proposal: Proposal, session: SessionView,
                  capabilities: Mapping[str, CapabilityState]) -> _StepOutcome:
    out = _StepOutcome()
    checked: List[str] = []

    # ── 1. organ lock ──
    lock = check_organ_lock(step.operation, selected_organ=session.selected_organ.value,
                            mode=session.mode)
    if lock is not None:
        out.refusal = lock
        return out
    checked.append("organ_lock")

    op = operation(step.operation)

    # The organ a planner WROTE on a step is not consulted for anything but this. The operation
    # registry owns which organ an operation belongs to, so a planner that labelled
    # `topology.adjacency` as `extent` in order to slip past the lock is caught here rather than
    # succeeding — `check_organ_lock` read the key, not the label.
    if step.organ.value != op.organ:
        out.refusal = RefusalRecord(
            code=RefusalCode.UNSUPPORTED_OPERATION, organ=session.selected_organ,
            operation=step.operation,
            message=contract_message("unsupported_operation", operation=step.operation,
                                     organ=step.organ.value),
            missing=[],
            remedy=f"{step.operation} belongs to the {op.organ} organ; a step may not relabel it",
            detail={"claimed_organ": step.organ.value, "operation_organ": op.organ})
        return out

    # ── 2. references ──
    stranger = next((r for r in step.input_refs if not session.knows(r)), None)
    if stranger is not None:
        name = session.unknown(stranger)
        out.refusal = RefusalRecord(
            code=RefusalCode.UNKNOWN_REFERENCE, organ=step.organ, operation=step.operation,
            message=contract_message("unknown_reference", reference=name),
            missing=[name],
            remedy="select the artifact first — 'that mask' resolves through ids, never through "
                   "language",
            detail={"reference": name, "role": stranger.role,
                    "declared_artifacts": list(session.artifact_ids),
                    # `art#inst` pairs, because that is what a person has to select back. A bare
                    # instance id in this list would name every set's first mask at once.
                    "declared_instances": [f"{a}#{i}" for a, i in session.instance_keys],
                    "declared_regions": list(session.region_ids)})
        return out
    if step.input_refs:
        checked.append("references")

    # ── 3. parameters ──
    params = resolve_parameters(step.operation, step.parameters)
    out.dropped = [DroppedParameter(step_id=step.step_id, name=n, reason=why)
                   for n, why in params.dropped]
    out.clamped = [ClampedParameter(step_id=step.step_id, name=n, requested=req, applied=app,
                                    bound=bound)
                   for n, req, app, bound in params.clamped]
    if not params.ok:
        out.refusal = params.refusal
        return out
    checked.append("parameters")

    # ── 4. inputs ──
    #
    # `for_execution=False`: this is plan time. An input declared `required` is required to SAY the
    # sentence and refuses here; `topology.occlusion`'s depth field is declared required only for
    # execution, so a person may compose the request before they have a depth artifact and is
    # refused `missing_depth_artifact` when they press run. Those are two different moments and
    # collapsing them would either forbid the thought or fake the field.
    if op.inputs:
        missing = check_inputs(step.operation, list(step.input_refs), for_execution=False)
        if missing is not None:
            out.refusal = missing
            if session.mode is SessionMode.CHAIN \
                    and missing.code is RefusalCode.MISSING_EXTENT_INPUTS:
                out.prerequisites = _chain_prerequisite(step, proposal)
            return out
        checked.append("inputs")

    # ── 5. capability ──
    adapter = params.clean.get("adapter") or _choose_adapter(op, capabilities)
    unavailable = check_capability(step.operation, adapter=adapter, states=capabilities)
    if unavailable is not None:
        out.refusal = unavailable
        return out
    if op.adapters:
        checked.append("capability")

    out.step = ResolvedStep(
        step_id=step.step_id, organ=step.organ, operation=step.operation,
        parameters=dict(params.clean), input_refs=list(step.input_refs), adapter=adapter,
        authorized_by="resolver", prerequisites_checked=checked)
    return out


def _chain_prerequisite(step: ProposedStep, proposal: Proposal) -> List[str]:
    """The visible chain a topology step with no extents offers instead of inventing one.

    THE HUMAN STEP IS NOT OPTIONAL. The master plan's chain is `Extent preparation → the person
    inspects or chooses regions → Topology measurement`, and a resolver that wired step B's inputs
    to step A's future output would delete the middle term — which is the term the whole mode
    exists for. So the preparation resolves, the measurement refuses `missing_extent_inputs`, and
    the plan says in words what the person has to do between them.

    Returns nothing when no preparation step was proposed. A prerequisite naming a step that does
    not exist is worse than a bare refusal.
    """
    prep = [s.step_id for s in proposal.steps
            if s.organ is OrganFamily.EXTENT and s.step_id != step.step_id]
    if not prep:
        return []
    return [f"{step.step_id} needs extents that no selected artifact supplies. "
            f"{', '.join(prep)} proposes them; the person inspects the result and selects the "
            f"extents to measure, and {step.step_id} is planned again against those ids. The "
            f"laboratory does not feed one stage into the next behind the person's back."]


def _choose_adapter(op: OperationDefinition,
                    capabilities: Mapping[str, CapabilityState]) -> Optional[str]:
    """The first declared adapter that is not known to be unavailable.

    This is a choice about ORDER, not a default value: the operation declares its adapters in
    preference order and the resolver walks it. An adapter nobody has an opinion about is
    `unknown_until_runtime` and is a candidate — Lane A's rule that a caller who has not looked is
    not a caller who found nothing.

    Returns None when every declared adapter is unavailable, and `check_capability` then refuses
    naming all of them. Returning the first one anyway would name a single adapter in a message
    whose real subject is that none of them are here.
    """
    for name in op.adapters:
        if capabilities.get(name, CapabilityState.UNKNOWN_UNTIL_RUNTIME) \
                is not CapabilityState.UNAVAILABLE:
            return name
    return None


def declared_operations(family: Optional[str] = None) -> Tuple[str, ...]:
    """Every operation key, or one organ's. The closed vocabulary a planner may choose from."""
    return tuple(k for k, owner in operations().items()
                 if family is None or owner.organ == family)


def as_dict(refusal: RefusalRecord) -> Dict[str, Any]:
    """A refusal as plain data, for a response or a test that wants to read one field."""
    return refusal.model_dump(mode="json")


__all__ = ["IsolationBreach", "Proposal", "Resolution", "resolve", "declared_operations",
           "as_dict"]
