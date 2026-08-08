"""
HARNESS-001B — the goal hierarchy: five kinds, nine statuses, and the round trip.

What this file is for: the directive's §2 asks for distinct, nested types that are NOT flattened
into one `goal`, and for a `satisfied` that requires evidence meeting an explicit criterion. Both of
those are claims about SHAPE, and a shape claim that nothing checks is a comment.
"""
from __future__ import annotations

import pytest

from backend.services.agents import goal as agent_goal
from backend.services.epistemics import EpistemicStatus
from backend.services.inquiry_engine import goals as gl


# ── 1. the five kinds are five kinds ─────────────────────────────────────────

def test_the_hierarchy_is_five_distinct_types_and_not_one_goal_with_a_scope_field():
    """The flatten this lane refuses. If these were one type with a `kind` string, the moment
    somebody added a field for one they would have added it to all five."""
    kinds = {gl.InquiryGoal("i", gl.KIND_INQUIRY).kind,
             gl.EvidenceGoal("e", gl.KIND_EVIDENCE).kind,
             gl.PreparationTask("p", gl.KIND_PREPARATION).kind,
             gl.AgentMission("m", gl.KIND_MISSION).kind,
             gl.SituatedGoal("s", gl.KIND_SITUATED).kind}
    assert kinds == set(gl.GOAL_KINDS)
    assert len({gl.InquiryGoal, gl.EvidenceGoal, gl.PreparationTask,
                gl.AgentMission, gl.SituatedGoal}) == 5

    # Each carries at least one field none of the others has — the proof they are not one type
    # wearing five names.
    assert hasattr(gl.InquiryGoal("i", gl.KIND_INQUIRY), "prompt")
    assert hasattr(gl.EvidenceGoal("e", gl.KIND_EVIDENCE), "need")
    assert hasattr(gl.PreparationTask("p", gl.KIND_PREPARATION), "actuator")
    assert hasattr(gl.AgentMission("m", gl.KIND_MISSION), "budget")
    assert hasattr(gl.SituatedGoal("s", gl.KIND_SITUATED), "relation")


def test_every_child_carries_a_parent_goal_id():
    """§2: 'Every child carries `parent_goal_id`.' The causal tree has to be reconstructible from
    the flat list, because the event log and the goal list are two different views and neither is
    derivable from the other."""
    inquiry = gl.InquiryGoal("iq", gl.KIND_INQUIRY, prompt="p")
    child = gl.EvidenceGoal("eg", gl.KIND_EVIDENCE, parent_goal_id=inquiry.id)
    task = gl.PreparationTask("pt", gl.KIND_PREPARATION, parent_goal_id=child.id)
    mission = gl.AgentMission("am", gl.KIND_MISSION, parent_goal_id=child.id)
    assert gl.children_of([child, task, mission], inquiry.id) == (child,)
    assert list(gl.children_of([child, task, mission], child.id)) == [task, mission]


def test_the_nine_statuses_are_all_declared_and_a_tenth_is_refused():
    assert len(gl.STATUSES) == 9
    for name in ("proposed", "ready", "active", "satisfied", "partially_satisfied",
                 "unresolved", "capability_gap", "exhausted", "refused"):
        assert name in gl.STATUSES
    with pytest.raises(gl.GoalMalformed, match="status"):
        gl.EvidenceGoal("eg", gl.KIND_EVIDENCE, status="probably_fine")


def test_capability_gap_is_its_own_status_and_not_a_flavour_of_unresolved():
    """The distinction the whole lane turns on: 'there is no instrument' and 'the instrument found
    nothing' tell a curator to do two different things."""
    assert gl.STATUS_CAPABILITY_GAP != gl.STATUS_UNRESOLVED
    assert gl.STATUS_CAPABILITY_GAP in gl.TERMINAL_STATUSES
    assert gl.STATUS_UNRESOLVED in gl.TERMINAL_STATUSES


# ── 2. clause modes ──────────────────────────────────────────────────────────

def test_three_clause_modes_are_epistemic_statuses_and_imagined_deliberately_is_not():
    """`imagined` having no `EpistemicStatus` is the design. Giving speculation one would create a
    supported way to publish a fabrication as evidence."""
    values = {s.value for s in EpistemicStatus}
    assert gl.CLAUSE_MEASURED in values
    assert gl.CLAUSE_INTERPRETIVE in values
    assert gl.CLAUSE_SOURCED in values
    assert gl.CLAUSE_IMAGINED not in values


def test_a_criterion_demanding_an_undeclared_mode_is_refused_not_defaulted():
    with pytest.raises(gl.UnknownClauseMode, match="declared modes"):
        gl.Criterion(id="c", clause="something", demands="vibes")


def test_only_measured_and_sourced_clauses_are_measurable():
    assert gl.Criterion(id="c", clause="x", demands=gl.CLAUSE_MEASURED).measurable
    assert gl.Criterion(id="c", clause="x", demands=gl.CLAUSE_SOURCED).measurable
    assert not gl.Criterion(id="c", clause="x", demands=gl.CLAUSE_INTERPRETIVE).measurable
    assert not gl.Criterion(id="c", clause="x", demands=gl.CLAUSE_IMAGINED).measurable


# ── 3. SituatedGoal is an adapter and adds nothing ───────────────────────────

def test_a_situated_goal_holds_exactly_what_agents_goal_declares_and_nothing_more():
    """'never overloaded' made structural. The moment this carried a criterion or a budget there
    would be two places deciding when a situated aim is met."""
    situated = gl.SituatedGoal.of("reach_measurable_nesting")
    declared = agent_goal.resolve("reach_measurable_nesting")
    assert situated.name == declared["name"]
    assert situated.relation == declared["relation"]
    assert situated.axis == declared["axis"]
    assert situated.detail == declared["detail"]
    # No field of its own beyond the base goal's plus the three the other module declares.
    own = set(situated.to_dict()) - {"id", "kind", "title", "parent_goal_id", "status", "detail"}
    assert own == {"name", "relation", "axis"}


def test_an_undeclared_situated_aim_is_refused_by_agents_goal_and_not_approximated_here():
    with pytest.raises(agent_goal.UnknownGoal):
        gl.SituatedGoal.of("reach_something_lovely")


# ── 4. the round trip is a required proof ────────────────────────────────────

@pytest.mark.parametrize("goal", [
    gl.InquiryGoal(id="iq", kind=gl.KIND_INQUIRY, prompt="the folds", mode="explore",
                   criteria=(gl.Criterion(id="c1", clause="extent", demands=gl.CLAUSE_MEASURED,
                                          relation="nested_within", basis="mask",
                                          produced_by=("nestedness_organ",), detail="d"),)),
    gl.EvidenceGoal(id="eg", kind=gl.KIND_EVIDENCE, need="nestedness_here", question="q",
                    phrase="fold", post_id="p1", region_id="r1", origin="attention",
                    action={"type": "brush_field", "role": "fold"},
                    criteria=(gl.Criterion(id="c2", clause="c"),)),
    gl.PreparationTask(id="pt", kind=gl.KIND_PREPARATION, actuator="concept_segment",
                       intention="i", params={"phrase": "fold"}, post_ids=("p1", "p2")),
    gl.AgentMission(id="am", kind=gl.KIND_MISSION, post_id="p1", region_id="r1",
                    organ_set=("nestedness_organ",), question="q", budget=2,
                    temperament="depth_seeker",
                    situated_goal=gl.SituatedGoal.of("reach_measurable_nesting"),
                    return_contract=("marks",)),
    gl.SituatedGoal.of("reach_measurable_contact"),
])
def test_every_goal_kind_survives_its_own_serialization_with_no_field_loss(goal):
    """Field loss here would make the run's round-trip proof pass while the run lost half itself."""
    assert gl.goal_from_dict(goal.to_dict()) == goal


def test_an_unknown_kind_raises_rather_than_degrading_to_the_base_class():
    """Degrading would drop every subclass field and the round trip would still 'succeed' — the
    exact shape of a proof that cannot fail."""
    with pytest.raises(gl.GoalMalformed, match="round trip"):
        gl.goal_from_dict({"id": "x", "kind": "mission_but_spelled_wrong"})


def test_a_status_transition_returns_a_new_goal_and_never_edits_the_old_one():
    """Goals are held by value in the run. An in-place edit would leave the event log describing a
    state no object is in."""
    goal = gl.EvidenceGoal("eg", gl.KIND_EVIDENCE, status=gl.STATUS_PROPOSED)
    moved = goal.with_status(gl.STATUS_SATISFIED)
    assert goal.status == gl.STATUS_PROPOSED
    assert moved.status == gl.STATUS_SATISFIED
    assert moved is not goal
