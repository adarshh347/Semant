"""
PERCEPTUAL-ORGANS-002 Lane D — the Direct and deterministic arms.

Two things are being proved, and they are not the same thing:

  · the planners propose what the sentence or the control actually asked for;
  · everything they propose still goes through the resolver, and the resolver still refuses.

The second is the one that matters. A planner test that stopped at the proposal would pass just as
happily for a planner that proposed `topology.adjacency` in a locked extent session and called it
authorized.
"""
from __future__ import annotations

import pytest

from backend.schemas.perception_lab import (CapabilityState, OrganFamily, PlannerIdentity,
                                            RefusalCode, SessionMode)
from backend.services.perception_lab import resolver as R
from backend.services.perception_lab.clock import FrozenClock, SequentialIds
from backend.services.perception_lab.planners import DirectCommand, DirectPlanner, RulesPlanner
from backend.services.perception_lab.session import SessionView

from .test_perception_lab_resolver import AVAILABLE, extent_session, ref, topology_session


def rules(prompt: str, session: SessionView) -> R.Proposal:
    return RulesPlanner(ids=SequentialIds()).plan(prompt, session)


def plan_of(proposal: R.Proposal, session: SessionView, caps=None):
    return R.resolve(proposal, session, capabilities=caps if caps is not None else AVAILABLE,
                     clock=FrozenClock(), ids=SequentialIds()).plan


def ops(proposal: R.Proposal):
    return [s.operation for s in proposal.steps]


# ── the Direct arm ───────────────────────────────────────────────────────────

def test_a_control_press_becomes_one_typed_command():
    proposal = DirectPlanner(SequentialIds()).plan(
        DirectCommand("extent.find_all", {"max_instances": 8}), extent_session())
    assert proposal.planner is PlannerIdentity.DIRECT
    assert ops(proposal) == ["extent.find_all"]
    assert proposal.steps[0].organ is OrganFamily.EXTENT
    assert proposal.steps[0].parameters == {"max_instances": 8}


def test_the_direct_arm_is_clamped_and_recorded_exactly_like_a_prompt():
    """No shortcut past the resolver. A pressed control that asked for 900 gets the same 64."""
    plan = plan_of(DirectPlanner(SequentialIds()).plan(
        DirectCommand("extent.find_all", {"max_instances": 900}), extent_session()),
        extent_session())
    assert plan.resolved_steps[0].parameters == {"max_instances": 64}
    assert plan.clamped_parameters[0].applied == 64


def test_the_direct_arm_reaches_the_manual_operation_the_prompt_arms_cannot():
    """`extent.draw` carries a person's hand, so a control may author it and a sentence may not."""
    proposal = DirectPlanner(SequentialIds()).plan(
        DirectCommand("extent.draw", {"tool": "polygon", "polygon": [[0.1, 0.1], [0.2, 0.2]]}),
        extent_session())
    plan = plan_of(proposal, extent_session())
    assert plan.resolved_steps[0].operation == "extent.draw"
    assert "extent.draw" not in ops(rules("draw a polygon around the figure", extent_session()))


def test_an_invented_operation_is_refused_by_name_at_the_planner_seam():
    proposal = DirectPlanner(SequentialIds()).plan(
        DirectCommand("extent.imagine"), extent_session())
    assert proposal.steps == ()
    assert proposal.refusals[0].code is RefusalCode.UNSUPPORTED_OPERATION
    assert proposal.refusals[0].detail["invented"] == "extent.imagine"
    assert plan_of(proposal, extent_session()).refusals[0].operation == "extent.imagine"


def test_several_controls_compose_a_chain_in_the_order_they_were_pressed():
    session = topology_session(mode=SessionMode.CHAIN)
    proposal = DirectPlanner(SequentialIds()).plan_many(
        [DirectCommand("extent.find_all"),
         DirectCommand("topology.adjacency",
                       input_refs=(ref("source", "art_1"), ref("target", "art_2")))],
        session)
    assert ops(proposal) == ["extent.find_all", "topology.adjacency"]
    plan = plan_of(proposal, session)
    assert plan.requires_confirmation is True


# ── the deterministic arm: what it reads ─────────────────────────────────────

@pytest.mark.parametrize("prompt,expected", [
    ("mask every face", "extent.find_named"),
    ("find the drapery", "extent.find_named"),
    ("segment the left figure", "extent.find_named"),
    ("mask every instance", "extent.find_all"),
    ("find everything", "extent.find_all"),
    ("how many are there", "extent.find_all"),
    ("what's in this image", "extent.find_all"),
    ("refine the left figure around the hand", "extent.refine"),
    ("repeat that with the other adapter", "extent.compare"),
    ("do those two touch?", "topology.adjacency"),
    ("do those two overlap?", "topology.overlap"),
    ("are they separate from each other", "topology.disjoint"),
    ("what surrounds the left figure?", "topology.negative_space"),
    ("which selected shapes touch?", "topology.all_pairs"),
    ("is the finial inside the sky, or merely in front of it?", "topology.occlusion"),
])
def test_the_table_reads_the_contracts_own_prompt_examples(prompt, expected):
    # Two artifacts are selected, so no chain preparation is offered and the plan is one step.
    session = topology_session(selected_artifact_ids=("art_1", "art_2"), mode=SessionMode.CHAIN)
    assert ops(rules(prompt, session)) == [expected]


def test_the_longest_cue_wins_and_the_other_reading_is_recorded_not_lost():
    session = topology_session()
    proposal = rules("is the finial inside the sky, or merely in front of it?", session)
    assert ops(proposal) == ["topology.occlusion"]
    assert any("topology.containment also matched" in n for n in proposal.notes)


def test_a_negated_cue_beats_the_word_it_negates():
    session = topology_session()
    assert ops(rules("do those two not touch at all", session)) == ["topology.disjoint"]


def test_an_all_pairs_sweep_is_bounded_to_the_relation_the_sentence_named():
    session = topology_session(selected_artifact_ids=("art_1", "art_2", "art_3"))
    proposal = rules("which selected shapes touch?", session)
    assert proposal.steps[0].parameters == {"relations": ["meets"]}
    assert len(proposal.steps[0].input_refs) == 3


def test_a_prompt_the_table_does_not_read_proposes_nothing_rather_than_guessing():
    proposal = rules("this is a beautiful and very sad photograph", extent_session())
    assert proposal.steps == ()
    assert proposal.refusals == ()
    assert any("honest answer" in n for n in proposal.notes)


def test_an_empty_prompt_has_no_default_operation():
    assert rules("   ", extent_session()).steps == ()


def test_a_long_noun_phrase_is_cut_and_the_cut_is_stated():
    proposal = rules("mask the very long and elaborately described piece of folded silk drapery "
                     "hanging at the left", extent_session())
    concept = proposal.steps[0].parameters["concept"]
    assert len(concept.split()) == 8
    assert any("cut to the first 8 words" in n for n in proposal.notes)


def test_the_concept_drops_the_words_that_name_the_image_rather_than_the_thing():
    proposal = rules("find the drapery in this photograph", extent_session())
    assert proposal.steps[0].parameters == {"concept": "drapery"}


@pytest.mark.parametrize("prompt,mode", [
    ("refine that mask and add the hand", "add"),
    ("refine that mask, remove the background", "subtract"),
    ("refine the left figure around the hand", "replace"),
])
def test_the_refine_mode_is_read_from_the_sentence_and_never_defaulted(prompt, mode):
    proposal = rules(prompt, extent_session())
    assert proposal.steps[0].parameters["mode"] == mode


def test_the_same_sentence_produces_a_byte_identical_plan_twice():
    a = plan_of(rules("mask every face", extent_session()), extent_session())
    b = plan_of(rules("mask every face", extent_session()), extent_session())
    assert a.model_dump(mode="json") == b.model_dump(mode="json")


# ── the deterministic arm meets the resolver ─────────────────────────────────

def test_a_prompt_cannot_switch_organs_in_isolation_mode():
    """The planner proposes the crossing; the resolver refuses it; the person can SEE both."""
    proposal = rules("do those two touch?", extent_session())
    assert ops(proposal) == ["topology.adjacency"]
    plan = plan_of(proposal, extent_session())
    assert plan.resolved_steps == []
    assert [r.code for r in plan.refusals] == [RefusalCode.ORGAN_LOCKED]
    assert plan.proposed_steps[0].organ is OrganFamily.TOPOLOGY


def test_a_crossing_that_was_neither_run_nor_refused_cannot_be_recorded():
    """LabPlan's own validator. A quietly dropped crossing is the failure this guards."""
    from pydantic import ValidationError

    from backend.schemas.perception_lab import LabPlan
    proposal = rules("do those two touch?", extent_session())
    with pytest.raises(ValidationError):
        LabPlan(plan_id="p", session_id="s", planner=PlannerIdentity.RULES,
                selected_organ=OrganFamily.EXTENT, mode=SessionMode.ISOLATION,
                proposed_steps=list(proposal.steps), resolved_steps=[], refusals=[],
                requires_confirmation=False, created_at="2026-08-10T09:00:00Z")


def test_a_topology_question_with_nothing_selected_refuses_in_isolation():
    session = topology_session(selected_artifact_ids=())
    plan = plan_of(rules("do those two touch?", session), session)
    assert plan.resolved_steps == []
    assert [r.code for r in plan.refusals] == [RefusalCode.MISSING_EXTENT_INPUTS]


def test_the_same_question_in_chain_mode_proposes_a_visible_preparation_that_asks_first():
    session = topology_session(mode=SessionMode.CHAIN, selected_artifact_ids=())
    proposal = rules("do those two touch?", session)
    assert ops(proposal) == ["extent.find_all", "topology.adjacency"]
    plan = plan_of(proposal, session)
    assert [s.operation for s in plan.resolved_steps] == ["extent.find_all"]
    assert [r.code for r in plan.refusals] == [RefusalCode.MISSING_EXTENT_INPUTS]
    assert plan.requires_confirmation is True
    assert any("crossing the boundary" in p for p in plan.prerequisites)
    assert any("the person inspects the result" in p for p in plan.prerequisites)


def test_a_chain_is_not_prepared_when_the_session_already_has_the_extents():
    session = topology_session(mode=SessionMode.CHAIN)
    assert ops(rules("do those two touch?", session)) == ["topology.adjacency"]


def test_the_planner_never_proposes_an_operation_that_would_author_geometry():
    for prompt in ("draw a mask over the figure", "paint the region by hand",
                   "reuse the canonical region", "trace a polygon around it"):
        assert not {"extent.draw", "extent.reuse"} & set(ops(rules(prompt, extent_session())))


def test_an_unavailable_adapter_refuses_the_prompted_plan_exactly_as_it_refuses_direct():
    caps = dict(AVAILABLE, sam3_concept=CapabilityState.UNAVAILABLE,
                grounded_sam=CapabilityState.UNAVAILABLE)
    prompted = plan_of(rules("find the drapery", extent_session()), extent_session(), caps)
    pressed = plan_of(DirectPlanner(SequentialIds()).plan(
        DirectCommand("extent.find_named", {"concept": "drapery"}), extent_session()),
        extent_session(), caps)
    assert [r.code for r in prompted.refusals] == [RefusalCode.CAPABILITY_UNAVAILABLE]
    assert [r.code for r in pressed.refusals] == [RefusalCode.CAPABILITY_UNAVAILABLE]


def test_direct_and_prompt_resolve_to_the_same_operation_adapter_and_parameters():
    """The plan-level half of the equivalence. The adapter-level half is in the orchestration
    suite, where both arms are watched arriving at one callable."""
    prompted = plan_of(rules("find the drapery", extent_session()), extent_session())
    pressed = plan_of(DirectPlanner(SequentialIds()).plan(
        DirectCommand("extent.find_named", {"concept": "drapery"}), extent_session()),
        extent_session())
    a, b = prompted.resolved_steps[0], pressed.resolved_steps[0]
    assert (a.operation, a.adapter, a.parameters) == (b.operation, b.adapter, b.parameters)
    assert prompted.planner is PlannerIdentity.RULES
    assert pressed.planner is PlannerIdentity.DIRECT
