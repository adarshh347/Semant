"""
PERCEPTUAL-ORGANS-002 Lane D — the resolver, gate by gate.

Every test here builds a proposal by hand. That is deliberate: the planners are tested against
this same resolver in their own files, and a resolver test that went through a planner would only
prove the pair agree, not that the gate holds against anything else. A hand-built proposal is what
a future lane, a route, or a bug looks like.
"""
from __future__ import annotations

import pytest

from backend.schemas.perception_lab import (CapabilityState, IdentityScope, InputRef, OrganFamily,
                                            PlannerIdentity, ProposedStep, RefusalCode,
                                            SessionMode)
from backend.services.perception_lab import resolver as R
from backend.services.perception_lab.clock import FrozenClock, SequentialIds
from backend.services.perception_lab.session import SessionView

AVAILABLE = {
    "yolo_sam2_auto": CapabilityState.AVAILABLE,
    "sam3_concept": CapabilityState.AVAILABLE,
    "grounded_sam": CapabilityState.AVAILABLE,
    "sam2_refine": CapabilityState.AVAILABLE,
    "human": CapabilityState.AVAILABLE,
    "canonical_region": CapabilityState.AVAILABLE,
    "lab_compare": CapabilityState.AVAILABLE,
    "nestedness_organ": CapabilityState.AVAILABLE,
    "adjacency_organ": CapabilityState.AVAILABLE,
    "mask_arithmetic": CapabilityState.AVAILABLE,
    "distance_transform": CapabilityState.AVAILABLE,
    "occlusion_organ": CapabilityState.AVAILABLE,
}


def extent_session(**over) -> SessionView:
    base = dict(session_id="labs_1", selected_organ=OrganFamily.EXTENT,
                mode=SessionMode.ISOLATION, active_artifact_id="art_1",
                selected_artifact_ids=("art_1", "art_2"))
    base.update(over)
    return SessionView(**base)


def topology_session(**over) -> SessionView:
    base = dict(session_id="labs_2", selected_organ=OrganFamily.TOPOLOGY,
                mode=SessionMode.ISOLATION, selected_artifact_ids=("art_1", "art_2"))
    base.update(over)
    return SessionView(**base)


def step(operation: str, *, organ: OrganFamily, step_id: str = "step_1", params=None,
         refs=()) -> ProposedStep:
    return ProposedStep(step_id=step_id, organ=organ, operation=operation,
                        parameters=dict(params or {}), input_refs=list(refs))


def ref(role: str, artifact_id: str) -> InputRef:
    return InputRef(role=role, scope=IdentityScope.SESSION, artifact_id=artifact_id)


def run(proposal: R.Proposal, session: SessionView, caps=None) -> R.Resolution:
    return R.resolve(proposal, session, capabilities=caps if caps is not None else AVAILABLE,
                     clock=FrozenClock(), ids=SequentialIds())


def direct(*steps: ProposedStep, **kw) -> R.Proposal:
    return R.Proposal(planner=PlannerIdentity.DIRECT, steps=steps, **kw)


def codes(plan) -> list:
    return [r.code for r in plan.refusals]


# ── the happy path, and what it records ──────────────────────────────────────

def test_a_declared_operation_resolves_and_names_the_adapter_it_will_use():
    plan = run(direct(step("extent.find_all", organ=OrganFamily.EXTENT)), extent_session()).plan
    assert len(plan.resolved_steps) == 1
    resolved = plan.resolved_steps[0]
    assert resolved.authorized_by == "resolver"
    assert resolved.adapter == "yolo_sam2_auto"
    assert resolved.prerequisites_checked == ["organ_lock", "parameters", "capability"]
    assert plan.refusals == []


def test_only_the_resolver_can_say_who_authorized_a_step():
    """`authorized_by` is a one-member Literal, so there is no second sayable value."""
    from pydantic import ValidationError

    from backend.schemas.perception_lab import ResolvedStep
    with pytest.raises(ValidationError):
        ResolvedStep(step_id="s", organ=OrganFamily.EXTENT, operation="extent.find_all",
                     authorized_by="planner")


def test_a_bounded_parameter_is_clamped_and_the_clamp_is_visible():
    plan = run(direct(step("extent.find_all", organ=OrganFamily.EXTENT,
                           params={"max_instances": 900})), extent_session()).plan
    assert plan.resolved_steps[0].parameters == {"max_instances": 64}
    assert [(c.name, c.requested, c.applied, c.bound) for c in plan.clamped_parameters] == \
        [("max_instances", 900, 64, "maximum=64")]
    assert plan.refusals == []


def test_an_undeclared_parameter_is_dropped_and_recorded_rather_than_refused():
    """A planner trying to hand the runner geometry should be visible HAVING TRIED."""
    plan = run(direct(step("extent.find_all", organ=OrganFamily.EXTENT,
                           params={"mask_rle": {"size": [2, 2], "counts": [0, 4]}})),
               extent_session()).plan
    assert plan.resolved_steps[0].parameters == {}
    assert [d.name for d in plan.dropped_parameters] == ["mask_rle"]
    assert plan.refusals == []


def test_a_declared_parameter_of_the_wrong_type_fails_closed():
    plan = run(direct(step("extent.find_named", organ=OrganFamily.EXTENT,
                           params={"concept": 7})), extent_session()).plan
    assert plan.resolved_steps == []
    assert codes(plan) == [RefusalCode.INVALID_PARAMETERS]


def test_a_missing_required_parameter_fails_closed():
    plan = run(direct(step("extent.find_named", organ=OrganFamily.EXTENT)), extent_session()).plan
    assert plan.resolved_steps == []
    assert codes(plan) == [RefusalCode.INVALID_PARAMETERS]


def test_dropped_parameters_survive_a_refusal_from_a_later_gate():
    """The smuggling attempt is the observation; a later gate's no must not erase it."""
    plan = run(direct(step("topology.adjacency", organ=OrganFamily.TOPOLOGY,
                           params={"region_id": "reg_invented"})),
               topology_session(selected_artifact_ids=())).plan
    assert codes(plan) == [RefusalCode.MISSING_EXTENT_INPUTS]
    assert [d.name for d in plan.dropped_parameters] == ["region_id"]


# ── gate 1: the organ lock ───────────────────────────────────────────────────

def test_a_prompt_cannot_reach_another_organ_in_isolation_mode():
    plan = run(direct(step("topology.adjacency", organ=OrganFamily.TOPOLOGY,
                           refs=[ref("source", "art_1"), ref("target", "art_2")])),
               extent_session()).plan
    assert plan.resolved_steps == []
    assert codes(plan) == [RefusalCode.ORGAN_LOCKED]
    assert plan.refusals[0].detail["operation_organ"] == "topology"


def test_an_operation_nobody_registered_is_unsupported_not_a_best_guess():
    plan = run(direct(step("extent.find_everything", organ=OrganFamily.EXTENT)),
               extent_session()).plan
    assert plan.resolved_steps == []
    assert codes(plan) == [RefusalCode.UNSUPPORTED_OPERATION]


def test_relabelling_a_step_does_not_help_it_past_the_lock():
    """The lock reads the OPERATION KEY. A topology step wearing an `extent` label is still
    topology, and it is refused for the reason that is true of it."""
    plan = run(direct(step("topology.adjacency", organ=OrganFamily.EXTENT,
                           refs=[ref("source", "art_1"), ref("target", "art_2")])),
               extent_session()).plan
    assert plan.resolved_steps == []
    assert codes(plan) == [RefusalCode.ORGAN_LOCKED]


def test_a_relabelled_step_is_refused_even_where_the_lock_would_have_let_it_through():
    """Chain mode permits the crossing, so the lock passes and the LABEL is what is now wrong.

    Without this gate a chain step could carry `organ: extent` on a topology operation, and every
    later reader — the stage stream, the artifact's organ_family, the response — would attribute
    the measurement to the organ that did not make it.
    """
    session = topology_session(mode=SessionMode.CHAIN)
    plan = run(direct(step("topology.adjacency", organ=OrganFamily.EXTENT,
                           refs=[ref("source", "art_1"), ref("target", "art_2")])),
               session).plan
    assert plan.resolved_steps == []
    assert codes(plan) == [RefusalCode.UNSUPPORTED_OPERATION]
    assert plan.refusals[0].detail == {"claimed_organ": "extent", "operation_organ": "topology"}


def test_chain_mode_permits_the_crossing_and_makes_it_ask_first():
    session = topology_session(mode=SessionMode.CHAIN)
    plan = run(direct(step("extent.find_all", organ=OrganFamily.EXTENT, step_id="step_a"),
                      step("topology.adjacency", organ=OrganFamily.TOPOLOGY, step_id="step_b",
                           refs=[ref("source", "art_1"), ref("target", "art_2")])),
               session).plan
    assert [s.step_id for s in plan.resolved_steps] == ["step_a", "step_b"]
    assert plan.requires_confirmation is True
    assert any("crosses the organ boundary" in p for p in plan.prerequisites)


def test_the_firewall_raises_rather_than_refusing_when_a_gate_has_stopped_working():
    """MUTATION. Disable the organ lock and an isolation session must not merely mis-plan.

    A refusal is what the laboratory says to a person. This is what it says to itself, and it is
    a different kind of event: the lock did not hold.
    """
    session = extent_session()
    proposal = direct(step("topology.adjacency", organ=OrganFamily.TOPOLOGY,
                           refs=[ref("source", "art_1"), ref("target", "art_2")]))
    original = R.check_organ_lock
    R.check_organ_lock = lambda *a, **k: None
    try:
        with pytest.raises(R.IsolationBreach) as exc:
            run(proposal, session)
    finally:
        R.check_organ_lock = original
    assert "step_1" in str(exc.value)


# ── gate 2: references ───────────────────────────────────────────────────────

def test_an_id_this_session_never_declared_is_refused_rather_than_looked_up():
    plan = run(direct(step("topology.adjacency", organ=OrganFamily.TOPOLOGY,
                           refs=[ref("source", "art_1"), ref("target", "art_hallucinated")])),
               topology_session()).plan
    assert plan.resolved_steps == []
    assert codes(plan) == [RefusalCode.UNKNOWN_REFERENCE]
    assert plan.refusals[0].missing == ["art_hallucinated"]
    assert plan.refusals[0].detail["declared_artifacts"] == ["art_1", "art_2"]


def test_a_region_id_resolves_only_through_the_sessions_active_regions():
    session = topology_session(active_region_ids=("reg_7",))
    good = InputRef(role="regions", scope=IdentityScope.CANONICAL, region_id="reg_7",
                    geometry_rev=2)
    bad = InputRef(role="regions", scope=IdentityScope.CANONICAL, region_id="reg_9",
                   geometry_rev=0)
    assert session.knows(good) is True
    assert session.knows(bad) is False


def test_a_reference_gate_that_passed_is_recorded_on_the_step():
    plan = run(direct(step("topology.adjacency", organ=OrganFamily.TOPOLOGY,
                           refs=[ref("source", "art_1"), ref("target", "art_2")])),
               topology_session()).plan
    assert plan.resolved_steps[0].prerequisites_checked == \
        ["organ_lock", "references", "parameters", "inputs", "capability"]


# ── gate 4: inputs ───────────────────────────────────────────────────────────

def test_topology_with_no_extents_refuses_rather_than_measuring_nothing():
    plan = run(direct(step("topology.adjacency", organ=OrganFamily.TOPOLOGY)),
               topology_session(selected_artifact_ids=())).plan
    assert plan.resolved_steps == []
    assert codes(plan) == [RefusalCode.MISSING_EXTENT_INPUTS]
    assert plan.refusals[0].missing == ["source"]


def test_topology_with_no_extents_in_chain_mode_offers_a_visible_preparation():
    """The middle term of the chain is the PERSON, and the plan says so instead of wiring past it."""
    session = topology_session(mode=SessionMode.CHAIN, selected_artifact_ids=())
    plan = run(direct(step("extent.find_all", organ=OrganFamily.EXTENT, step_id="step_a"),
                      step("topology.adjacency", organ=OrganFamily.TOPOLOGY, step_id="step_b")),
               session).plan
    assert [s.step_id for s in plan.resolved_steps] == ["step_a"]
    assert codes(plan) == [RefusalCode.MISSING_EXTENT_INPUTS]
    assert plan.requires_confirmation is True
    assert any("step_a proposes them" in p for p in plan.prerequisites)


def test_a_chain_prerequisite_is_not_offered_when_no_preparation_was_proposed():
    session = topology_session(mode=SessionMode.CHAIN, selected_artifact_ids=())
    plan = run(direct(step("topology.adjacency", organ=OrganFamily.TOPOLOGY)), session).plan
    assert plan.prerequisites == []
    assert codes(plan) == [RefusalCode.MISSING_EXTENT_INPUTS]


def test_occlusion_may_be_planned_without_a_depth_field_and_still_declares_it():
    """Composing the request is not running it. The depth refusal belongs at execution."""
    plan = run(direct(step("topology.occlusion", organ=OrganFamily.TOPOLOGY,
                           refs=[ref("source", "art_1"), ref("target", "art_2")])),
               topology_session()).plan
    assert len(plan.resolved_steps) == 1
    assert plan.requires_confirmation is True          # the operation declares it
    assert codes(plan) == []


def test_too_many_inputs_for_a_role_is_refused():
    session = topology_session(selected_artifact_ids=("art_1", "art_2", "art_3"))
    plan = run(direct(step("topology.adjacency", organ=OrganFamily.TOPOLOGY,
                           refs=[ref("source", "art_1"), ref("source", "art_2"),
                                 ref("target", "art_3")])), session).plan
    assert codes(plan) == [RefusalCode.INVALID_PARAMETERS]


# ── gate 5: capability ───────────────────────────────────────────────────────

def test_an_adapter_that_is_not_running_here_refuses_rather_than_returning_empty():
    caps = dict(AVAILABLE, sam3_concept=CapabilityState.UNAVAILABLE,
                grounded_sam=CapabilityState.UNAVAILABLE)
    plan = run(direct(step("extent.find_named", organ=OrganFamily.EXTENT,
                           params={"concept": "drapery"})), extent_session(), caps).plan
    assert plan.resolved_steps == []
    assert codes(plan) == [RefusalCode.CAPABILITY_UNAVAILABLE]
    assert plan.refusals[0].missing == ["sam3_concept", "grounded_sam"]


def test_the_resolver_walks_the_declared_adapter_order_and_skips_the_unavailable_one():
    caps = dict(AVAILABLE, sam3_concept=CapabilityState.UNAVAILABLE)
    plan = run(direct(step("extent.find_named", organ=OrganFamily.EXTENT,
                           params={"concept": "drapery"})), extent_session(), caps).plan
    assert plan.resolved_steps[0].adapter == "grounded_sam"


def test_an_adapter_nobody_has_looked_at_is_a_candidate_not_a_refusal():
    plan = run(direct(step("extent.find_all", organ=OrganFamily.EXTENT)),
               extent_session(), {}).plan
    assert plan.resolved_steps[0].adapter == "yolo_sam2_auto"


def test_a_person_who_named_an_unavailable_adapter_is_told_about_that_one():
    caps = dict(AVAILABLE, sam3_concept=CapabilityState.UNAVAILABLE)
    plan = run(direct(step("extent.find_named", organ=OrganFamily.EXTENT,
                           params={"concept": "drapery", "adapter": "sam3_concept"})),
               extent_session(), caps).plan
    assert codes(plan) == [RefusalCode.CAPABILITY_UNAVAILABLE]
    assert plan.refusals[0].missing == ["sam3_concept"]


# ── the plan as a whole ──────────────────────────────────────────────────────

def test_a_plan_with_nothing_authorized_is_still_a_plan_carrying_every_reason():
    plan = run(direct(step("extent.find_everything", organ=OrganFamily.EXTENT, step_id="s1"),
                      step("extent.find_named", organ=OrganFamily.EXTENT, step_id="s2")),
               extent_session()).plan
    assert plan.resolved_steps == []
    assert codes(plan) == [RefusalCode.UNSUPPORTED_OPERATION, RefusalCode.INVALID_PARAMETERS]
    assert plan.requires_confirmation is False


def test_a_planners_own_refusal_travels_onto_the_plan():
    from backend.schemas.perception_lab import RefusalRecord
    invented = RefusalRecord(code=RefusalCode.UNSUPPORTED_OPERATION, organ=OrganFamily.EXTENT,
                             operation="extent.imagine", message="extent.imagine is not real.")
    plan = run(R.Proposal(planner=PlannerIdentity.MODEL, steps=(), refusals=(invented,)),
               extent_session()).plan
    assert codes(plan) == [RefusalCode.UNSUPPORTED_OPERATION]


def test_a_fallback_plan_names_what_it_fell_back_from():
    plan = run(R.Proposal(planner=PlannerIdentity.RULES,
                          fell_back_from=PlannerIdentity.MODEL,
                          steps=(step("extent.find_all", organ=OrganFamily.EXTENT),)),
               extent_session()).plan
    assert plan.planner is PlannerIdentity.RULES
    assert plan.planner_fell_back_from is PlannerIdentity.MODEL


def test_the_plan_is_byte_identical_for_the_same_input_twice():
    proposal = direct(step("extent.find_all", organ=OrganFamily.EXTENT))
    a = run(proposal, extent_session()).plan.model_dump(mode="json")
    b = run(proposal, extent_session()).plan.model_dump(mode="json")
    assert a == b


def test_the_declared_vocabulary_is_the_contracts_and_has_no_extras():
    assert R.declared_operations("extent") == (
        "extent.find_all", "extent.find_named", "extent.refine", "extent.draw", "extent.reuse",
        "extent.compare")
    assert "topology.occlusion" in R.declared_operations("topology")
    assert len(R.declared_operations()) == 13
