"""WAVE5 — the first pursued goal: the claims, and the one lie a goal makes easy.

Every prior lane could be wrong by measuring badly. A goal can be wrong by making a measurement
*mean* something it does not, and the failure is silent and flattering:

  1. IT TOUCHES THE MEASUREMENT. If having an aim could change what an organ reports, every number
     downstream inherits the aim and "the system found what it was looking for" becomes literally
     true in the worst sense. §1 pins measurement as goal-invariant, byte for byte.
  2. IT FABRICATES ARRIVAL. `satisfied` without a mark is the whole confabulation. §2.
  3. IT FABRICATES PROGRESS. A gradient over loci nobody has stood in is an imagination with a
     number attached. §3.
  4. IT REACHES ACROSS MODALITIES. "Closer to my aim" between a depth move and an analogy move is
     a comparison on a scale nobody measured — the incommensurability wall. §4.
"""
from __future__ import annotations

import pytest

from backend.services import mask_geometry as mg
from backend.services import movement_graph as mgraph
from backend.services import nestedness_organ as nest
from backend.services.agents import goal as gl
from backend.services.agents import movement as mv
from backend.services.agents import situated_agent as sa
from backend.services.agents import temperament as tp

N = 16
STAMP = "2026-08-08T00:00:00+00:00"


def _rle(x0, x1, y0, y1):
    bits = [0] * (N * N)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * N + x] = 1
    return mg.rle_encode(bits, N, N)


def _post(pid):
    return {"_id": pid, "region_annotations": [
        {"id": "part", "label": "part", "mask_rle": _rle(4, 16, 4, 12)},
        {"id": "whole", "label": "whole", "mask_rle": _rle(0, 16, 0, 16)},
    ]}


def _marks(posts):
    return [nest.grounding_mark(m, post_id=pid)
            for pid, post in posts.items()
            for m in nest.find_nested_pairs(post["region_annotations"])]


def _edge(eid, src, dst, spans, mark_id, axis="axis_nestedness", syst=0.7):
    return mgraph.movement_edge_entry(mark_id=mark_id, source_node=src, target_node=dst,
                                      spans=list(spans), axis_ref=axis, systematicity=syst,
                                      weight=1.0, edge_id=eid)


def _world():
    posts = {"pA": _post("pA"), "pB": _post("pB")}
    marks = _marks(posts)
    first = [m for m in marks if m["post_id"] == "pA"][0]["id"]
    graph = {"_id": "atlas_goal", "edges": [
        _edge("e1", "vm_pA:part", "vm_pB:part", ["pA", "pB"], first)]}
    return posts, graph, marks


def _agent(temperament="", aid="a"):
    return sa.inhabit(agent_id=aid, post_id="pA", region_id="part",
                      organ_set=(nest.ORGAN,), temperament=temperament)


# ── 1. measurement is goal-invariant ───────────────────────────────────────

def test_the_same_pair_yields_the_same_mark_with_and_without_a_goal():
    """THE BRIGHT LINE OF THE LANE. If an aim could reach an organ, every number downstream would
    inherit it — and the system would find what it was looking for, literally."""
    posts, graph, marks = _world()

    plain = _agent(aid="plain")
    sa.perceive(plain, posts["pA"], now=STAMP)

    pursuing = _agent(aid="pursuing")
    gl.pursue(pursuing, graph, posts, goal_name="reach_measurable_nesting",
              marks=marks, bound=0, now=STAMP)

    def signature(agent):
        return sorted((p.organ, p.reading.relation, p.reading.direction,
                       p.reading.other_region_id, p.reading.basis, p.epistemic_status,
                       p.reading.detail) for p in agent.percept_field)

    assert signature(plain) == signature(pursuing), "the aim reached into an organ"


def test_a_goal_names_no_status_and_no_organ_of_its_own():
    """A goal that could stamp a status would be an aim deciding what kind of knowing something is."""
    import pathlib

    body = pathlib.Path(gl.__file__).read_text().split('"""', 2)[2]
    assert "EpistemicStatus.MEASURED.value" in body, "it may READ the organ's word"
    for forbidden in ("grounding_mark", "measure(", "nestedness_organ.measure"):
        assert forbidden not in body, f"the goal module calls {forbidden!r} — it must not measure"


# ── 2. success requires a measured mark ───────────────────────────────────

def test_an_agent_cannot_report_satisfied_without_the_organ_measurement():
    """THE CONFABULATION THIS LANE EXISTS TO REFUSE, on the asserting path rather than the asking
    one."""
    posts, _g, _m = _world()
    agent = _agent()
    sa.perceive(agent, posts["pA"], now=STAMP)
    agent.percept_field = []                       # it measured nothing here

    assert gl.is_satisfied(agent, "reach_measurable_nesting") is False
    with pytest.raises(gl.GoalNotMeasured, match="no third state"):
        gl.assert_satisfied_is_measured(agent, "reach_measurable_nesting", claimed=True)


def test_satisfaction_cites_the_marks_that_made_it_true():
    posts, graph, marks = _world()
    agent = _agent()
    result = gl.pursue(agent, graph, posts, goal_name="reach_measurable_nesting",
                       marks=marks, bound=2, now=STAMP)
    assert result["outcome"] == gl.SATISFIED
    assert result["satisfying_marks"], "a satisfaction that names no mark is a claim"
    assert all(mid.startswith("vm_") for mid in result["satisfying_marks"])


def test_a_box_basis_reading_cannot_satisfy_a_goal():
    """An estimate is not an arrival. WAVE2.5 reaching the aim layer."""
    boxed = {"_id": "pX", "region_annotations": [
        {"id": "part", "box": {"x": 0.25, "y": 0.25, "w": 0.4, "h": 0.4}},
        {"id": "whole", "box": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}}]}
    agent = sa.inhabit(agent_id="b", post_id="pX", region_id="part", organ_set=(nest.ORGAN,))
    sa.perceive(agent, boxed, now=STAMP)

    assert agent.percept_field, "the fixture must produce a box-basis reading"
    assert all(p.reading.basis == "box" for p in agent.percept_field)
    assert gl.is_satisfied(agent, "reach_measurable_nesting") is False


def test_the_status_check_stands_on_its_own():
    """WRITTEN BECAUSE MUTATION-TESTING CAUGHT THE TEST ABOVE PASSING FOR THE WRONG REASON.

    Removing the basis check broke nothing — a box mark already reads `interpretive`, so the status
    check was doing the work while the box test claimed the basis check was. Both guards stay
    (they say different things, and `MarkMisstated` exists because a mark CAN claim a kind its basis
    does not support), and this pins the status one alone: a mask-basis mark whose organ did not
    call it `measured` must not satisfy an aim.
    """
    posts, _g, _m = _world()
    agent = _agent()
    sa.perceive(agent, posts["pA"], now=STAMP)
    assert gl.is_satisfied(agent, "reach_measurable_nesting"), "the fixture must start satisfied"

    for perception in agent.percept_field:
        assert perception.reading.basis == "mask", "mask basis, so only the status can decide"
        perception.mark["epistemic_status"] = "interpretive"

    assert gl.is_satisfied(agent, "reach_measurable_nesting") is False
    with pytest.raises(gl.GoalNotMeasured):
        gl.assert_satisfied_is_measured(agent, "reach_measurable_nesting", claimed=True)


def test_an_undeclared_goal_is_refused_rather_than_approximated():
    with pytest.raises(gl.UnknownGoal, match="has to be declared"):
        gl.resolve("find_something_beautiful")


# ── 3. failure is a finding, and progress is never fabricated ────────────

def test_a_pursuit_that_does_not_arrive_reports_how_far_it_got():
    """NOT an error, and not a near miss — there is no measured distance to an aim, so 'how close'
    is not a question this system can answer."""
    posts, graph, marks = _world()
    agent = _agent()
    # an aim no organ in this body can ever satisfy
    result = gl.pursue(agent, graph, posts, goal_name="reach_measurable_occlusion",
                       marks=marks, bound=2, now=STAMP)

    assert result["outcome"] == gl.NOT_REACHED
    assert result["satisfying_marks"] == []
    assert result["steps_taken"] <= result["bound"]
    assert "not an error" in result["detail"] and "not a near miss" in result["detail"]
    assert "measured_here" in result, "how far it got, in what it actually measured"


def test_the_outcome_carries_no_distance_to_the_aim():
    posts, graph, marks = _world()
    result = gl.pursue(_agent(), graph, posts, goal_name="reach_measurable_occlusion",
                       marks=marks, bound=1, now=STAMP)
    for forbidden in ("distance", "closeness", "progress", "score", "remaining"):
        assert not [k for k in result if forbidden in k], forbidden


def test_advantage_reads_only_the_edge_the_organ_already_measured():
    """No gradient over unvisited loci. An agent cannot know what it will find where it has not
    stood — `step` empties the field for that reason — so scoring destinations would score an
    imagination."""
    posts, graph, marks = _world()
    agent = _agent()
    sa.perceive(agent, posts["pA"], now=STAMP)
    entries = mv.horizon(agent, graph, posts, proposed_marks=marks)
    reachable = [e for e in entries if e.reachable]
    assert reachable, "the fixture must afford a move"

    matches, strength = gl.advantage(reachable[0], "reach_measurable_nesting")
    assert matches in (0, 1)
    assert strength == pytest.approx(float(reachable[0].edge.get("systematicity") or 0.0))


# ── 4. the goal is modality-bound ────────────────────────────────────────

def test_a_goal_never_pulls_the_agent_onto_another_axis():
    """The incommensurability wall at the aim layer. Ranking across kinds would compare two
    measurements that share no scale."""
    posts, graph, marks = _world()
    agent = _agent(temperament="analogy_seeker")
    sa.perceive(agent, posts["pA"], now=STAMP)
    entries = mv.horizon(agent, graph, posts, proposed_marks=marks)

    decision = gl.choose(entries, goal_name="reach_measurable_occlusion",
                         temperament="analogy_seeker")
    assert decision["chose_kind"] == "axis_nestedness", "temperament picks the axis"
    assert decision["goal_biased"] is False
    assert "share no scale" in decision["goal_reason"]


def test_temperament_picks_the_mode_and_the_goal_ranks_within_it():
    posts, graph, marks = _world()
    agent = _agent(temperament="analogy_seeker")
    sa.perceive(agent, posts["pA"], now=STAMP)
    entries = mv.horizon(agent, graph, posts, proposed_marks=marks)

    decision = gl.choose(entries, goal_name="reach_measurable_nesting",
                         temperament="analogy_seeker")
    assert decision["chose_kind"] == "axis_nestedness"
    assert decision["goal"] == "reach_measurable_nesting"
    assert decision["reach"] is not None
    # the aim ranked within the axis temperament chose — never outside it
    assert str(decision["reach"].axis_ref) == decision["chose_kind"]


def test_an_agent_with_no_goal_behaves_exactly_as_before():
    """A goal is ASSIGNED. An agent given none must be indistinguishable from one in a world where
    this module does not exist."""
    posts, graph, marks = _world()
    agent = _agent(temperament="analogy_seeker")
    sa.perceive(agent, posts["pA"], now=STAMP)
    entries = mv.horizon(agent, graph, posts, proposed_marks=marks)

    plain = tp.choose(entries, temperament="analogy_seeker")
    with_none = gl.choose(entries, goal_name="", temperament="analogy_seeker")
    assert with_none["reach"] is plain["reach"]
    assert with_none["goal"] is None and with_none["goal_biased"] is False


def test_every_declared_goal_names_a_relation_an_organ_produces():
    """An aim whose predicate no organ measures could never be satisfied, and would look like a
    pursuit that simply always fails."""
    from backend.services import adjacency_organ as adj
    from backend.services import occlusion_organ as occ

    produced = {nest.RELATION_NESTED_WITHIN, adj.RELATION_MEETS, occ.RELATION_IN_FRONT_OF}
    for name, spec in gl.GOALS.items():
        assert spec["relation"] in produced, f"{name} names a relation no organ produces"
        assert spec["axis"] and spec["detail"]
