"""
HARNESS-001B §7 — the boundary tests: the eight things a goal engine must not be able to do.

Every one of these is a way this layer would lie while every component below it stayed honest. That
is what makes them boundary tests rather than unit tests: none of the modules underneath is wrong in
any of these scenarios, and the composition would be.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from backend.services import nestedness_organ as nest
from backend.services.agents import situated_agent as sa
from backend.services.epistemics import STATUS_KEY
from backend.services.inquiry_engine import adapters as ad
from backend.services.inquiry_engine import capability as cap
from backend.services.inquiry_engine import engine as eng
from backend.services.inquiry_engine import evaluator as ev
from backend.services.inquiry_engine import fixtures
from backend.services.inquiry_engine import goals as gl
from backend.services.inquiry_engine.events import (EVIDENCE_TESTIMONY, Evidence,
                                                    EvidenceFabricated)
from backend.services.movement_kernel import posts_fingerprint

STAMP = fixtures.STAMP

PARTS_SUGGESTION = {
    "id": None, "type": "region_mask", "producer": "find_parts",
    "epistemic_status": "measured", "label": "a part",
    "provenance": {"producer": "find_parts", "adapter": "fixture:find_parts"},
}


def _mark(posts, pid="post_renaissance"):
    pairs = nest.find_nested_pairs(posts[pid]["region_annotations"])
    return nest.grounding_mark(pairs[0], post_id=pid, now=STAMP)


# ── 1. the Director cannot stamp an agent perception ─────────────────────────

def test_a_director_proposal_offered_to_a_body_as_its_own_perception_is_refused():
    """The most consequential fabrication available at this seam. A Director suggestion that opened
    a crossing would give an agent a first-person claim nothing it owns ever measured — and every
    sentence built on it would parse."""
    director_suggestion = {
        "id": "sug_1", "type": "region_mask",
        "provenance": {"producer": "concept_segment", "adapter": "sam3"},
        STATUS_KEY: "measured",
    }
    with pytest.raises(ad.ProposalNotAPerception, match="not an organ"):
        ad.assert_organ_authored([director_suggestion])


def test_an_organ_authored_mark_passes_the_same_wall():
    """The negative control: prove the wall admits what it should, or 'it refused' says nothing."""
    posts, _graph, _marks = fixtures.control_world()
    assert ad.assert_organ_authored([_mark(posts)])


def test_the_wall_holds_for_the_fake_adapter_too():
    """A guard that only the real implementation carries is a guard the fast tests run without."""
    fake = ad.FakeSimulatorAdapter()
    mission = gl.AgentMission(id="am", kind=gl.KIND_MISSION, post_id="p", region_id="r")
    with pytest.raises(ad.ProposalNotAPerception):
        fake.dispatch(mission, {}, run_id="r", inquiry_id="i", evidence_goal_id="eg",
                      proposed_marks=[{"id": "x", "provenance": {"producer": "a_planner"}}])


# ── 2. a goal does not alter an organ's output ───────────────────────────────

def test_the_same_locus_yields_the_same_marks_with_and_without_an_inquiry():
    """THE BRIGHT LINE, carried up from WAVE5. A goal may change SELECTION; if it could reach a
    measurement, every number downstream would inherit the aim and 'the system found what it was
    looking for' would become literally true in the worst sense."""
    posts, graph, marks = fixtures.control_world()

    plain = sa.inhabit(agent_id="plain", post_id="post_renaissance", region_id="finial",
                       organ_set=(nest.ORGAN,))
    sa.perceive(plain, posts["post_renaissance"], now=STAMP)
    direct = [{k: v for k, v in p.mark.items() if k != "id"} for p in plain.percept_field]

    run = eng.run_inquiry(fixtures.control_frame(), posts=posts, now=STAMP,
                          post_id="post_renaissance", region_id="finial", graph=graph,
                          proposed_marks=marks, simulator=ad.SimulatorAdapter(),
                          director=ad.FakeDirectorAdapter(ran=False, available=False))
    through_goal = [{k: v for k, v in e.ref.items() if k != "id"}
                    for e in run.evidence if e.kind == "organ_mark"]

    assert direct, "the control fixture measured nothing — the comparison would be vacuous"
    assert json.dumps(sorted(direct, key=str), sort_keys=True) == \
           json.dumps(sorted(through_goal, key=str), sort_keys=True)


def test_the_engine_module_never_calls_an_organ_or_mints_a_mark():
    """Structural, and with its own negative control below: a scan that matches nothing is
    indistinguishable from a scan that ran against the wrong file."""
    body = pathlib.Path(eng.__file__).read_text(encoding="utf-8").split('"""', 2)[2]
    for forbidden in ("grounding_mark", "nestedness_organ.measure", "organs.invoke",
                      "EpistemicStatus."):
        assert forbidden not in body, f"the engine calls {forbidden!r} — it must not measure"


def test_that_scan_can_actually_fail():
    """The negative control. `situated_agent` DOES reach organs, so a scanner that finds nothing
    there is broken rather than reassuring."""
    body = pathlib.Path(sa.__file__).read_text(encoding="utf-8").split('"""', 2)[2]
    assert "organs.invoke" in body


# ── 3. agreement is not satisfaction ─────────────────────────────────────────

def test_dialogue_agreement_does_not_satisfy_a_measured_criterion():
    """Two differently-embodied agents concurring is two readings. A composition becomes measured
    knowledge only by being re-grounded on new loci — never by being agreed with."""
    criterion = gl.Criterion(id="c1", clause="containment is measured",
                             demands=gl.CLAUSE_MEASURED, relation="nested_within", basis="mask")
    goal = gl.EvidenceGoal(id="eg", kind=gl.KIND_EVIDENCE, criteria=(criterion,))
    testimony = Evidence.of_testimony(
        {"claim": "we both see the finial inside the sky", "agreed": True},
        evidence_id="evd_1", goal_id="eg")

    verdict = ev.evaluate(goal, [testimony])
    assert verdict.status == gl.STATUS_UNRESOLVED
    assert "Testimony is not a measurement" in verdict.clauses[0].why


def test_testimony_cannot_be_constructed_as_measured_at_all():
    """Not a policy in the evaluator — a shape in the constructor. There is no argument that makes
    `of_testimony` produce a measured item."""
    item = Evidence.of_testimony({"claim": "x"}, evidence_id="e", goal_id="g")
    assert item.kind == EVIDENCE_TESTIMONY
    assert item.epistemic_status == ""
    assert item.measured is False


def test_a_completed_actuator_call_is_not_satisfaction():
    """A step that ran and produced nothing contributes no evidence, so a goal cannot be satisfied
    by the fact that work happened."""
    criterion = gl.Criterion(id="c1", clause="the extent is measured",
                             demands=gl.CLAUSE_MEASURED, produced_by=("concept_segment",))
    goal = gl.EvidenceGoal(id="eg", kind=gl.KIND_EVIDENCE, criteria=(criterion,))
    result = ad.PreparationResult(task_id="pt", goal_id="eg", ran=True, available=True,
                                  records=({"step_id": "s", "actuator": "concept_segment",
                                            "status": "ok"},),
                                  suggestions=())
    items = eng._evidence_from_preparation(result, goal_id="eg", ids=eng._Ids(run_id="r"))
    assert items == []
    assert ev.evaluate(goal, items).status == gl.STATUS_UNRESOLVED


def test_a_goal_reported_satisfied_with_no_cited_evidence_raises():
    verdict = ev.GoalVerdict(goal_id="eg", status=gl.STATUS_SATISFIED,
                             clauses=(ev.ClauseVerdict(criterion_id="c", clause="x",
                                                       demands=gl.CLAUSE_MEASURED, met=True,
                                                       why="", evidence_ids=()),))
    with pytest.raises(AssertionError, match="not a third way"):
        ev.assert_not_satisfied_without_evidence(verdict)


def test_evidence_cannot_state_a_status_the_referenced_object_disagrees_with():
    with pytest.raises(EvidenceFabricated, match="drift"):
        Evidence.of_production({"step_id": "s", STATUS_KEY: "interpretive"},
                               evidence_id="e", goal_id="g", epistemic_status="measured")


def test_a_mark_with_no_status_cannot_be_given_one_here():
    with pytest.raises(EvidenceFabricated, match="carries no"):
        Evidence.of_mark({"id": "m1"}, evidence_id="e", goal_id="g")


# ── 4. unavailable differs from measured absence ─────────────────────────────

def test_an_unavailable_model_and_a_missing_instrument_produce_different_run_states():
    """The two look identical from the outside — nothing came back — and mean opposite things: one
    says try again, the other says build something."""
    posts = fixtures.fold_world()
    unavailable = eng.run_inquiry(
        fixtures.fold_frame(), posts=posts, now=STAMP, post_id="post_renaissance",
        region_id="drapery", simulator=ad.SimulatorAdapter(),
        director=ad.FakeDirectorAdapter(ran=False, available=False))
    assert unavailable.stop_reason == "execution_unavailable"

    gap_goal = next(g for g in unavailable.goals
                    if g.kind == gl.KIND_EVIDENCE and g.need == "fold_morphology")
    assert gap_goal.status == gl.STATUS_CAPABILITY_GAP
    # And the two are held apart on the SAME run: an unavailable Director did not turn the fold
    # gap into an availability problem, and did not turn availability into a gap.
    assert [g.need for g in unavailable.gaps] == ["fold_morphology"]


def test_an_empty_result_and_a_capability_gap_are_different_goal_statuses():
    posts, graph, marks = fixtures.control_world()
    run = eng.run_inquiry(fixtures.control_frame(), posts=posts, now=STAMP,
                          post_id="post_renaissance", region_id="finial", graph=graph,
                          proposed_marks=marks, simulator=ad.SimulatorAdapter(),
                          director=ad.FakeDirectorAdapter(ran=False))
    adjacency = next(g for g in run.goals if getattr(g, "need", "") == "adjacency_here")
    assert adjacency.status == gl.STATUS_UNRESOLVED           # looked, measured nothing
    assert adjacency.status != gl.STATUS_CAPABILITY_GAP       # the organ exists and was invoked


# ── 5. no new evidence stops the loop, with decomposed reasons ───────────────

def test_a_run_that_produces_nothing_stops_with_a_named_reason_and_never_loops():
    posts = fixtures.fold_world()
    run = eng.run_inquiry(
        {**fixtures.fold_frame(), "proposed_actions": [], "unresolved_terms": [],
         "attentions": [], "epistemic_demands": []},
        posts=posts, now=STAMP, post_id="post_renaissance", region_id="drapery",
        simulator=ad.SimulatorAdapter(), max_rounds=9)
    assert run.rounds == 1, "a run with nothing to do went around more than once"
    assert run.stop_reason in ("no_new_evidence", "execution_unavailable")
    assert run.outcome == "exhausted"


def test_the_stop_reasons_are_a_closed_set_and_none_of_them_is_it_finished():
    from backend.services.inquiry_engine.events import STOP_REASONS
    assert set(STOP_REASONS) == {"satisfied", "no_new_evidence", "budget_exhausted",
                                 "awaiting_human", "capability_gap", "execution_unavailable"}


def test_a_run_with_no_timestamp_is_refused_rather_than_reading_a_clock():
    """A run stamped from the wall clock could not be replayed and compared, and every proof in
    this lane is a comparison of two runs."""
    with pytest.raises(ValueError, match="replayed"):
        eng.run_inquiry(fixtures.control_frame(), posts={}, now="")


# ── 6. an unknown organ or action is refused visibly ────────────────────────

def test_an_unknown_organ_is_refused_by_name_with_the_binding_tables_own_words():
    resolution = cap.resolve_need("nestedness_here", locus=True)
    assert resolution.kind == cap.AGENT_MISSION            # the real one resolves
    state = cap.organ_availability(("a_third_eye",))
    assert state["unknown"] == ["a_third_eye"]
    assert "no organ named" in state["detail"]["a_third_eye"]


def test_a_mission_with_an_unusable_body_comes_back_refused_and_not_empty():
    """An empty percept field means 'the organs looked and measured nothing'. A body that could not
    be used is not that, and a mission that reported it as one would describe a quiet locus."""
    posts, _graph, _marks = fixtures.control_world()
    mission = gl.AgentMission(id="am", kind=gl.KIND_MISSION, post_id="post_renaissance",
                              region_id="finial", organ_set=("a_third_eye",))
    result = ad.SimulatorAdapter().dispatch(mission, posts, run_id="r", inquiry_id="i",
                                            evidence_goal_id="eg", now=STAMP)
    assert result.dispatched is False
    assert result.refusals and result.refusals[0]["reason"] == "organ_refusal"
    assert result.perceptions == ()


def test_a_mission_pointed_at_a_post_that_is_not_there_is_refused_rather_than_dispatched():
    mission = gl.AgentMission(id="am", kind=gl.KIND_MISSION, post_id="post_nowhere",
                              region_id="finial", organ_set=(nest.ORGAN,))
    result = ad.SimulatorAdapter().dispatch(mission, {}, run_id="r", inquiry_id="i",
                                            evidence_goal_id="eg", now=STAMP)
    assert result.dispatched is False
    assert result.refusals[0]["reason"] == "no_post"


# ── 7. no Mongo write, no post mutation ──────────────────────────────────────

def test_no_module_in_this_package_touches_a_collection_or_the_database():
    """This lane opens no Mongo collection and performs no write. Structural, because a promise in
    a docstring is not a check — and with a negative control, because a scan that matches nothing
    is indistinguishable from a scan pointed at the wrong directory."""
    package = pathlib.Path(eng.__file__).parent
    forbidden = ("backend.database", "insert_one", "update_one", "delete_one", "find_one",
                 "get_collection", "motor")
    scanned = 0
    for path in sorted(package.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        scanned += 1
        for token in forbidden:
            assert token not in source, f"{path.name} references {token!r}"
    assert scanned >= 8, f"the scan only saw {scanned} module(s) — it is pointed somewhere wrong"


def test_that_database_scan_can_actually_fail():
    """The negative control. `run_store` DOES write to a collection."""
    from backend.services import run_store
    source = pathlib.Path(run_store.__file__).read_text(encoding="utf-8")
    assert "insert_one" in source and "update_one" in source


def test_no_module_in_this_package_imports_a_language_model_client():
    package = pathlib.Path(eng.__file__).parent
    for path in sorted(package.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for token in ("import groq", "from groq", "llm_service", "openai", "anthropic"):
            assert token not in source, f"{path.name} reaches a model: {token!r}"


def test_a_whole_run_leaves_every_post_byte_identical():
    posts, graph, marks = fixtures.control_world()
    before = posts_fingerprint(posts)
    eng.run_inquiry(fixtures.control_frame(), posts=posts, now=STAMP,
                    post_id="post_renaissance", region_id="finial", graph=graph,
                    proposed_marks=marks, simulator=ad.SimulatorAdapter(),
                    director=ad.FakeDirectorAdapter(suggestions=[PARTS_SUGGESTION], ran=True))
    assert posts_fingerprint(posts) == before


# ── 8. the adapters are replaceable without changing engine semantics ────────

def test_the_engines_own_decisions_do_not_move_when_the_adapter_behind_the_seam_does():
    """If the engine's semantics moved with the adapter, every fast test in this lane would be
    testing the fake rather than the engine.

    What is compared is the ENGINE's part — which goals it derived, how it resolved them, and which
    missions it dispatched. The event stream as a whole is deliberately NOT compared: a canned fake
    returns different DATA, the run says so, and a test that demanded identical output would be
    asserting that the two adapters are the same object.
    """
    posts, graph, marks = fixtures.control_world()

    def _hierarchy(run):
        return [(g.kind, getattr(g, "need", ""), g.parent_goal_id) for g in run.goals]

    def _resolutions(run):
        return [(e.goal_id, e.payload["kind"], tuple(e.payload["organs"]))
                for e in run.events if e.kind == "capability_resolved"]

    real = eng.run_inquiry(fixtures.control_frame(), posts=posts, now=STAMP,
                           post_id="post_renaissance", region_id="finial", graph=graph,
                           proposed_marks=marks, simulator=ad.SimulatorAdapter(),
                           director=ad.FakeDirectorAdapter(ran=False))

    fake_sim = ad.FakeSimulatorAdapter(marks=[_mark(posts)])
    fake = eng.run_inquiry(fixtures.control_frame(), posts=posts, now=STAMP,
                           post_id="post_renaissance", region_id="finial", graph=graph,
                           proposed_marks=marks, simulator=fake_sim,
                           director=ad.FakeDirectorAdapter(ran=False))

    assert _hierarchy(real) == _hierarchy(fake)
    assert _resolutions(real) == _resolutions(fake)

    # And the fake was asked exactly the same questions, in the same order, with the same bodies.
    dispatched = [g for g in real.goals if g.kind == gl.KIND_MISSION]
    assert [(m.id, m.post_id, m.region_id, m.organ_set) for m in fake_sim.calls] == \
           [(m.id, m.post_id, m.region_id, m.organ_set) for m in dispatched]


def test_the_recommended_run_store_is_stated_rather_than_left_to_a_reader():
    """The directive requires this lane to report which existing store should eventually persist an
    `InquiryRun`. A recommendation only in prose is one a persistence lane can miss."""
    from backend.services import inquiry_engine
    assert inquiry_engine.RECOMMENDED_RUN_STORE == "runs"
    assert inquiry_engine.RECOMMENDED_RUN_STORE_MODULE == "backend.services.run_store"
    assert "RUN-STORE RECONCILIATION" in (inquiry_engine.__doc__ or "")
