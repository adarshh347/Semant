"""WAVE3 — agent movement: the five places a fake world would hide, and the guard on each.

Movement is where an unearned world is easiest to build, because the sentence it produces —
*"I went there, and there I found…"* — carries its own authority. Nobody re-checks a journey. So
these tests are not coverage of a traversal feature; each one guards a claim that would still LOOK
right from the outside if it failed:

  1. REACHABILITY — an agent steps only along a crossing it can prove was MEASURED, and one it
     cannot prove stays visible in its horizon wearing its reason. A horizon that silently dropped
     its refusals would report a tidier world in which every visible relation was also a road. §1.
  2. FOOTING — the far half of the WAVE2.5 ruling is on the edge's mark; the near half is under the
     agent's feet, and the agent checks that itself. A movement edge cites ONE mark, and a crossing
     rests on two. §2.
  3. NO NARRATED ARRIVAL — after a step the agent knows nothing. A percept field carried across a
     step would be sentences about the image it left wearing the name of the image it reached. §3.
  4. NO GOAL — selection is a stated, deterministic rule, recorded on the step it produced. An
     agent that "wanted" to go somewhere would be confabulating intent it has no organ for. §4.
  5. THE AGENT DOES NOT GROUND ITS OWN CROSSINGS — asserted structurally over the module, the same
     way the package's no-language-model guard is asserted over the package. §5.

§6 is the walk itself: two loci, two images, one measured edge, and both readings of it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.services import mask_geometry as mg
from backend.services import nestedness_organ as organ
from backend.services.agents import movement as mv
from backend.services.agents import observation as obs_mod
from backend.services.agents import situated_agent as sa
from backend.services.epistemics import STATUS_KEY, EpistemicStatus
from backend.services.movement_graph import movement_edge_entry

STAMP = "2026-08-06T00:00:00+00:00"
AXIS = organ.AXIS_NESTEDNESS
RASTER = 20


# ── fixtures: real geometry, because the ruling is about geometry ────────────

def _rle(x0, y0, x1, y1, size=RASTER):
    """A filled rectangle as a COCO RLE — the same measured substrate a SAM 3 region carries.

    Built rather than faked: every admissibility claim in this lane turns on whether the organ took
    the mask path or the box path, and a stubbed measurement would let a test pass while the thing
    it tests never happened.
    """
    rows = [[1 if (y0 <= r < y1 and x0 <= c < x1) else 0 for c in range(size)]
            for r in range(size)]
    return mg.rle_encode_mask(rows)


def _masked(region_id, x0, y0, x1, y1, label=""):
    return {"id": region_id, "label": label, "mask_rle": _rle(x0, y0, x1, y1)}


def _boxed(region_id, x, y, w, h, label=""):
    return {"id": region_id, "label": label, "box": {"x": x, "y": y, "w": w, "h": h}}


def _masked_post(post_id, part, whole, extra=""):
    """An image whose part/whole nesting is measurable ON MASKS — so it can carry a crossing.

    `extra` adds a third masked region the agent is NOT standing on, which is what makes the
    partiality assertions non-vacuous.
    """
    regions = [_masked(part, 8, 8, 12, 12, label="part"),
               _masked(whole, 2, 2, 18, 18, label="whole")]
    if extra:
        regions.append(_masked(extra, 0, 0, 20, 4, label="strip"))
    return {"_id": post_id, "region_annotations": regions}


def _boxed_post(post_id, part, whole):
    """The same shape in ESTIMATED geometry — a VLM's boxes, which may propose and never ground."""
    return {"_id": post_id, "region_annotations": [
        _boxed(part, 0.40, 0.40, 0.10, 0.10, label="part"),
        _boxed(whole, 0.10, 0.10, 0.80, 0.80, label="whole"),
    ]}


def _mark_for(post, inner_id, outer_id):
    """The organ's own grounding mark for one pair, measured for real. Never committed."""
    regions = {str(r["id"]): r for r in post["region_annotations"]}
    measurement = organ.measure(regions[inner_id], regions[outer_id])
    return organ.grounding_mark(measurement, post_id=str(post["_id"]),
                                step_id="test:movement", now=STAMP)


def _edge(mark, source_node, target_node, spans, *, systematicity=0.6, weight=0.25, valid_to=None):
    return movement_edge_entry(
        mark_id=str(mark["id"]), source_node=source_node, target_node=target_node,
        spans=spans, axis_ref=AXIS, systematicity=systematicity, weight=weight,
        valid_to=valid_to, now=STAMP)


def _node(post_id, region_id):
    return obs_mod.node_id_for(post_id, region_id)


def _standing(post, region_id, agent_id="agent_alpha"):
    """An agent inhabiting a locus and having perceived from it — the state a step requires."""
    agent = sa.inhabit(agent_id=agent_id, post_id=str(post["_id"]), region_id=region_id,
                       organ_set=(organ.ORGAN,))
    sa.perceive(agent, post, now=STAMP)
    return agent


def _world():
    """Two masked images and the one measured crossing between them.

    p1 is where the agent starts; p2 is another image entirely. The mark cites p2's own nesting,
    which is what the kernel's `movement_from` puts on an edge: the measurement that established
    the relation holds over there.
    """
    p1 = _masked_post("p1", "m_part", "m_whole", extra="m_strip")
    p2 = _masked_post("p2", "m_part2", "m_whole2")
    far_mark = _mark_for(p2, "m_part2", "m_whole2")
    edge = _edge(far_mark, _node("p1", "m_part"), _node("p2", "m_part2"), ["p1", "p2"])
    posts = {"p1": p1, "p2": p2}
    return posts, {"edges": [edge]}, [far_mark]


# ── 1. reachability: visible is not the same as reachable ────────────────────

def test_the_measured_crossing_is_reachable_and_says_on_what():
    posts, doc, marks = _world()
    agent = _standing(posts["p1"], "m_part")

    rows = mv.horizon(agent, doc, posts, proposed_marks=marks)
    assert len(rows) == 1
    row = rows[0]
    assert row.reachable is True and row.reason == ""
    assert row.basis == organ.ADMISSIBLE_BASIS
    assert row.epistemic == EpistemicStatus.MEASURED.value
    assert row.other_node == _node("p2", "m_part2")
    assert agent.horizon == rows, "the horizon is the agent's, not a value the caller carries"


def test_the_horizon_holds_only_movements_touching_where_the_agent_stands():
    """The locus constraint, arriving in the movement layer. `read_neighbours` is the graph's
    reader and it is happy to describe any node; an agent's horizon is what reaches THIS one, and
    a horizon that widened would be a reachable world the agent never earned."""
    posts, doc, marks = _world()
    elsewhere = _mark_for(posts["p2"], "m_part2", "m_whole2")
    posts["p2"]["visual_marks"] = [elsewhere]
    doc["edges"].append(_edge(elsewhere, _node("p1", "m_whole"), _node("p2", "m_whole2"),
                              ["p1", "p2"]))

    agent = _standing(posts["p1"], "m_part")
    rows = mv.horizon(agent, doc, posts, proposed_marks=marks)
    assert [r.other_node for r in rows] == [_node("p2", "m_part2")]


def test_a_box_grounded_crossing_is_visible_and_not_reachable():
    """THE RULING, as the difference between seeing and going. A box is an estimate of an extent;
    the crossing it names may be real and the agent still may not walk it — and the row stays in
    the horizon so that "cannot get there" is legible rather than expressed by absence."""
    posts, doc, marks = _world()
    posts["p3"] = _boxed_post("p3", "b_part", "b_whole")
    box_mark = _mark_for(posts["p3"], "b_part", "b_whole")
    assert box_mark[STATUS_KEY] == EpistemicStatus.INTERPRETIVE.value
    doc["edges"].append(_edge(box_mark, _node("p1", "m_part"), _node("p3", "b_part"),
                              ["p1", "p3"]))

    agent = _standing(posts["p1"], "m_part")
    rows = mv.horizon(agent, doc, posts, proposed_marks=[*marks, box_mark])
    refused = [r for r in rows if not r.reachable]
    assert len(rows) == 2 and len(refused) == 1
    assert refused[0].reason == mv.UNREACHABLE_INTERPRETIVE
    assert "may propose" in refused[0].detail
    assert mv.horizon_tally(rows) == {
        "visible": 2, "reachable": 1, "refused": {mv.UNREACHABLE_INTERPRETIVE: 1}}


def test_a_crossing_whose_measurement_cannot_be_read_is_unreachable():
    """The default state of this corpus, and the reason the run reports two worlds. Nobody has
    committed a movement mark, so against the durable ledger ALONE nothing is reachable at all —
    which is a fact to report, not one to route around by quietly overlaying the run's own marks."""
    posts, doc, _ = _world()
    agent = _standing(posts["p1"], "m_part")

    rows = mv.horizon(agent, doc, posts)                     # no marks in hand, none committed
    assert [r.reason for r in rows] == [mv.UNREACHABLE_NO_MARK]
    assert rows[0].epistemic is None, "None is 'cannot tell you', never 'uncertain'"
    assert rows[0].ledger_status == obs_mod.LEDGER_PROPOSED


def test_a_mark_that_misstates_its_own_basis_is_not_a_passport():
    """The flattering one-line failure, in the one place it would be least checkable. A box mark
    stamped `measured` is the 2D-projection artefact wearing the strongest word the vocabulary has
    — and a per-producer table would wave it through, because the organ's ceiling IS `measured`."""
    posts, doc, _ = _world()
    posts["p3"] = _boxed_post("p3", "b_part", "b_whole")
    forged = {**_mark_for(posts["p3"], "b_part", "b_whole"),
              STATUS_KEY: EpistemicStatus.MEASURED.value}
    doc["edges"] = [_edge(forged, _node("p1", "m_part"), _node("p3", "b_part"), ["p1", "p3"])]

    agent = _standing(posts["p1"], "m_part")
    rows = mv.horizon(agent, doc, posts, proposed_marks=[forged])
    assert [r.reason for r in rows] == [mv.UNREACHABLE_MISSTATED]


def test_a_mark_measuring_some_other_pair_does_not_ground_this_crossing():
    """Well-formed, mask-basis, honestly stamped — and about somewhere else. An edge citing it is
    an assertion nobody grounded, and the check is easy to leave out precisely because every other
    property of the mark is impeccable."""
    posts, doc, _ = _world()
    unrelated = _mark_for(posts["p1"], "m_strip", "m_whole")
    assert unrelated[STATUS_KEY] == EpistemicStatus.MEASURED.value
    doc["edges"] = [_edge(unrelated, _node("p1", "m_part"), _node("p2", "m_part2"), ["p1", "p2"])]

    agent = _standing(posts["p1"], "m_part")
    rows = mv.horizon(agent, doc, posts, proposed_marks=[unrelated])
    assert [r.reason for r in rows] == [mv.UNREACHABLE_ELSEWHERE]


def test_a_closed_movement_is_visible_and_not_traversable():
    """A contradiction ends a movement's claim, not its record (Lane G). So it stays in the horizon
    and it is not a road — `read_neighbours` would have hidden it, which is why this lane asks for
    the dead ones and classifies them itself."""
    posts, doc, marks = _world()
    doc["edges"] = [_edge(marks[0], _node("p1", "m_part"), _node("p2", "m_part2"),
                          ["p1", "p2"], valid_to=STAMP)]
    agent = _standing(posts["p1"], "m_part")
    rows = mv.horizon(agent, doc, posts, proposed_marks=marks)
    assert [r.reason for r in rows] == [mv.UNREACHABLE_CLOSED]


def test_stepping_to_a_visible_but_unreachable_movement_is_refused_and_moves_nothing():
    posts, doc, _ = _world()
    agent = _standing(posts["p1"], "m_part")
    rows = mv.horizon(agent, doc, posts)                     # unreadable mark → unreachable

    with pytest.raises(mv.Unreachable, match=mv.UNREACHABLE_NO_MARK):
        mv.step(agent, rows[0], now=STAMP)

    assert agent.locus.region_id == "m_part" and agent.locus.post_id == "p1"
    assert [e["kind"] for e in agent.trajectory] == [sa.TRAJECTORY_PERCEIVE]


# ── 2. footing: the near half of the ruling, under the agent's own feet ──────

def test_an_agent_on_box_geometry_may_not_start_a_measured_crossing():
    """A movement edge stores ONE mark — the far measurement — and a crossing rests on two. So the
    near side is not verifiable from the edge, and the agent verifies the one thing it genuinely
    can: what its own organ measured from where it is standing."""
    posts, _, _ = _world()
    posts["p0"] = _boxed_post("p0", "b_part", "b_whole")
    far_mark = _mark_for(posts["p2"], "m_part2", "m_whole2")
    doc = {"edges": [_edge(far_mark, _node("p0", "b_part"), _node("p2", "m_part2"),
                           ["p0", "p2"])]}

    agent = _standing(posts["p0"], "b_part")
    rows = mv.horizon(agent, doc, posts, proposed_marks=[far_mark])
    assert rows[0].reachable is True, "the far end really is measured — this is about the near end"

    stood = mv.footing(agent)
    assert stood["admissible"] is False and stood["reason"] == mv.UNFOOTED_BOX
    with pytest.raises(mv.Unreachable, match=mv.UNFOOTED_BOX):
        mv.step(agent, rows[0], now=STAMP)
    assert agent.locus.post_id == "p0"


def test_an_agent_that_has_not_perceived_here_has_not_measured_its_footing():
    """"I looked and everything was an estimate" and "I have not looked" are different states, and
    an agent that stepped from the second would be crossing on geometry nobody consulted."""
    posts, doc, marks = _world()
    agent = sa.inhabit(agent_id="agent_alpha", post_id="p1", region_id="m_part",
                       organ_set=(organ.ORGAN,))
    rows = mv.horizon(agent, doc, posts, proposed_marks=marks)

    assert mv.footing(agent)["reason"] == mv.UNFOOTED_UNPERCEIVED
    with pytest.raises(mv.Unreachable, match=mv.UNFOOTED_UNPERCEIVED):
        mv.step(agent, rows[0], now=STAMP)


def test_a_measured_footing_names_how_many_of_its_readings_earned_it():
    posts, _, _ = _world()
    agent = _standing(posts["p1"], "m_part")
    stood = mv.footing(agent)
    assert stood["admissible"] is True and stood["basis"] == organ.ADMISSIBLE_BASIS
    assert 0 < stood["admissible_readings"] <= stood["readings"]


# ── 3. no narrated arrival ──────────────────────────────────────────────────

def test_the_agent_arrives_knowing_nothing_about_where_it_arrived():
    """The step empties the field and the horizon. Between arriving and looking, the agent holds no
    sentence about the destination — it cannot import the seed's knowledge, and it cannot describe
    an image it has not measured."""
    posts, doc, marks = _world()
    agent = _standing(posts["p1"], "m_part")
    before = [p.reading.other_region_id for p in agent.percept_field]
    assert before, "the fixture must give the agent something to lose"

    mv.step(agent, mv.select(mv.horizon(agent, doc, posts, proposed_marks=marks)), now=STAMP)

    assert agent.percept_field == [] and agent.horizon == []
    assert agent.locus.node_id == _node("p2", "m_part2")


def test_what_the_agent_perceives_after_a_step_is_measured_at_the_new_locus_only():
    posts, doc, marks = _world()
    agent = _standing(posts["p1"], "m_part")
    mv.step(agent, mv.select(mv.horizon(agent, doc, posts, proposed_marks=marks)), now=STAMP)

    field = sa.perceive(agent, posts["p2"], now=STAMP)
    assert field, "the destination affords something, or this test proves nothing"
    for perception in field:
        assert perception.reading.locus_region_id == "m_part2"
        assert perception.reading.other_region_id in ("m_whole2",)
    # and nothing from the image it left came with it
    assert all("p1" not in str(p.mark.get("post_id")) for p in field)


def test_perceiving_at_a_post_the_agent_is_not_in_is_still_refused_after_a_step():
    """The god's-eye guard does not weaken because the agent can move. It is the same check; what
    changed is which post satisfies it."""
    posts, doc, marks = _world()
    agent = _standing(posts["p1"], "m_part")
    mv.step(agent, mv.select(mv.horizon(agent, doc, posts, proposed_marks=marks)), now=STAMP)

    from backend.services.agents import organs
    with pytest.raises(organs.OrganRefusal, match="god's-eye"):
        sa.perceive(agent, posts["p1"], now=STAMP)


# ── 4. no goal: a stated rule, written on the step it produced ──────────────

def test_the_selection_rule_is_named_recorded_and_deterministic():
    posts, doc, marks = _world()
    agent = _standing(posts["p1"], "m_part")
    rows = mv.horizon(agent, doc, posts, proposed_marks=marks)

    chosen = mv.select(rows, policy=mv.POLICY_SYSTEMATICITY)
    assert mv.select(rows, policy=mv.POLICY_SYSTEMATICITY) is chosen, "a walk must re-run the same"

    entry = mv.step(agent, chosen, policy=mv.POLICY_SYSTEMATICITY, now=STAMP)
    assert entry["policy"] == mv.POLICY_SYSTEMATICITY
    assert entry["rule"] == mv.POLICIES[mv.POLICY_SYSTEMATICITY]
    assert "structure-map score" in entry["rule"]


def test_the_two_policies_are_different_rules_and_say_so():
    """Not interchangeable, and the difference is visible in the choice rather than in a comment."""
    posts, doc, marks = _world()
    second = _mark_for(posts["p2"], "m_part2", "m_whole2")
    doc["edges"].append(_edge(second, _node("p1", "m_part"), _node("p2", "m_part2"),
                              ["p1", "p2"], systematicity=0.2, weight=0.9))
    agent = _standing(posts["p1"], "m_part")
    rows = mv.horizon(agent, doc, posts, proposed_marks=[*marks, second])

    assert mv.select(rows, policy=mv.POLICY_SYSTEMATICITY).systematicity == 0.6
    assert mv.select(rows, policy=mv.POLICY_WEIGHT).weight == 0.9


def test_a_tie_is_broken_on_the_destination_and_not_on_a_freshly_minted_id():
    """CAUGHT BY RE-RUNNING THE REAL WALK, not by reasoning about it.

    Two crossings from the seed tied at systematicity 0.8667 and the walk went to a different image
    on each run — because the tie-break was `edge_id`, which `new_movement_edge_id` mints fresh
    (uuid-backed, and rightly so: a positional id would be repointed by the next re-dissect). A
    stated rule that resolves differently every run is not a rule anyone can check.

    `other_node` is a content identity — `vm_<post>:<region>` — and it is what the step MEANS.
    """
    posts, doc, marks = _world()
    tied = _mark_for(posts["p2"], "m_part2", "m_whole2")
    posts["p4"] = _masked_post("p4", "m_part4", "m_whole4")
    far4 = _mark_for(posts["p4"], "m_part4", "m_whole4")
    doc["edges"] = [
        _edge(far4, _node("p1", "m_part"), _node("p4", "m_part4"), ["p1", "p4"], systematicity=0.6),
        _edge(tied, _node("p1", "m_part"), _node("p2", "m_part2"), ["p1", "p2"], systematicity=0.6),
    ]
    agent = _standing(posts["p1"], "m_part")
    rows = mv.horizon(agent, doc, posts, proposed_marks=[far4, tied])
    assert all(r.reachable for r in rows) and len({r.systematicity for r in rows}) == 1

    first = mv.select(rows).other_node
    # re-mint every edge: same crossings, new ids, and the same destination must win
    doc["edges"] = [_edge(far4, _node("p1", "m_part"), _node("p4", "m_part4"), ["p1", "p4"],
                          systematicity=0.6),
                    _edge(tied, _node("p1", "m_part"), _node("p2", "m_part2"), ["p1", "p2"],
                          systematicity=0.6)]
    again = mv.horizon(agent, doc, posts, proposed_marks=[far4, tied])
    assert {r.edge_id for r in rows}.isdisjoint({r.edge_id for r in again})
    assert mv.select(again).other_node == first


def test_an_unnamed_policy_is_refused_rather_than_defaulted():
    """A rule nobody can look up is not a rule. Defaulting would let a walk be explained by a
    string that means nothing."""
    with pytest.raises(ValueError, match="unknown selection policy"):
        mv.select([], policy="whatever_looks_best")


def test_selection_returns_nothing_when_nothing_is_reachable():
    posts, doc, _ = _world()
    agent = _standing(posts["p1"], "m_part")
    assert mv.select(mv.horizon(agent, doc, posts)) is None


# ── 5. the agent reads the graph; it does not ground ────────────────────────

_MODULE = Path(mv.__file__)


def test_the_movement_module_cannot_ground_its_own_crossings():
    """Structural, over the module, rather than promised in its docstring — the same shape as the
    package's no-language-model guard. An agent that could call the kernel would be minting the
    edges it then reports having found, and every walk would be a world it authored."""
    imports = [line for line in _MODULE.read_text().splitlines()
               if line.startswith(("import ", "from "))]
    assert imports, "a scan that scans nothing passes vacuously"
    offenders = [line for line in imports if "movement_kernel" in line or "structure_map" in line]
    assert not offenders, (
        f"{offenders} — the kernel grounds a crossing and mints the edge; this module reads one. "
        f"An agent that grounds its own movements is authoring the world it reports finding.")


def test_the_trajectory_decay_hook_is_declared_and_deliberately_not_implemented():
    """An unbounded trajectory eventually makes every agent omniscient, at which point partiality —
    the reason a second agent is worth talking to — is gone. Out of scope here; pinned so that
    implementing it is a deliberate act, and so this test fails when someone does."""
    assert mv.TRAJECTORY_DECAY_HALF_LIFE_SECONDS is None
    posts, doc, marks = _world()
    agent = _standing(posts["p1"], "m_part")
    mv.step(agent, mv.select(mv.horizon(agent, doc, posts, proposed_marks=marks)), now=STAMP)
    assert all(entry.get("at") for entry in agent.trajectory), \
        "the hook IS the stamp on every entry — a decay pass must not need a new record shape"


def test_a_node_id_that_cannot_be_rebuilt_is_not_a_destination():
    """Verified by reconstruction, not by splitting: an endpoint this lane cannot round-trip is one
    it must not walk to, because the place it would land is not the place the edge names."""
    assert mv.parse_node_id(_node("p1", "m_part")) == ("p1", "m_part")
    for junk in ("", "p1:m_part", "vm_p1", "vm_:m_part", "vm_p1:"):
        assert mv.parse_node_id(junk) is None


def test_an_endpoint_outside_the_movements_own_span_is_refused():
    """A malformed edge — and the honest response is to stop, not to put the agent in an image the
    crossing never measured.

    The mark here measures the end the agent is STANDING on, which is legitimate: an edge cites one
    of its two grounding marks and a reader can arrive along either direction. So the crossing
    passes every admissibility check and is still refused, because the far endpoint names an image
    this movement never spanned.
    """
    posts, _, _ = _world()
    near_mark = _mark_for(posts["p1"], "m_part", "m_whole")
    doc = {"edges": [_edge(near_mark, _node("p1", "m_part"), _node("p9", "ghost"),
                           ["p1", "p2"])]}
    agent = _standing(posts["p1"], "m_part")
    rows = mv.horizon(agent, doc, posts, proposed_marks=[near_mark])
    assert rows[0].reachable is True, "the crossing itself is admissible — this is about the span"

    with pytest.raises(mv.Unreachable, match="spans"):
        mv.step(agent, rows[0], now=STAMP)
    assert agent.locus.post_id == "p1"


# ── 6. the walk ─────────────────────────────────────────────────────────────

def test_an_agent_walks_to_another_image_and_perceives_there():
    """THE DELIVERABLE, in miniature: two loci across two posts, stitched by one measured edge, and
    a percept field at the far end that the agent measured after it arrived."""
    posts, doc, marks = _world()
    agent = _standing(posts["p1"], "m_part")
    entry = mv.step(agent, mv.select(mv.horizon(agent, doc, posts, proposed_marks=marks)),
                    now=STAMP)
    sa.perceive(agent, posts["p2"], now=STAMP)

    assert entry["crossed_image"] is True
    assert entry["from_node"] == _node("p1", "m_part")
    assert entry["to_node"] == _node("p2", "m_part2")

    world = mv.constellation(agent)
    assert world["posts"] == ["p1", "p2"]
    assert len(world["loci"]) == 2 and len(world["steps"]) == 1
    assert world["legible"] == (f"agent {agent.id}: {_node('p1', 'm_part')} "
                                f"—[{AXIS}, measured, mask]→ {_node('p2', 'm_part2')}")


def test_every_step_cites_the_mark_it_rests_on():
    posts, doc, marks = _world()
    agent = _standing(posts["p1"], "m_part")
    entry = mv.step(agent, mv.select(mv.horizon(agent, doc, posts, proposed_marks=marks)),
                    now=STAMP)
    assert entry["mark_id"] == marks[0]["id"]
    assert entry["edge_id"] == doc["edges"][0]["edge_id"]
    assert entry["basis"] == organ.ADMISSIBLE_BASIS


def test_the_step_copies_the_marks_status_and_names_none_of_its_own():
    """The rule this wave left behind after recording `measured` for a box reading in a first-person
    memory: a lane may never name the epistemic status of evidence it did not produce."""
    posts, doc, marks = _world()
    agent = _standing(posts["p1"], "m_part")
    entry = mv.step(agent, mv.select(mv.horizon(agent, doc, posts, proposed_marks=marks)),
                    now=STAMP)
    assert entry[STATUS_KEY] == marks[0][STATUS_KEY] == EpistemicStatus.MEASURED.value

    # and it is copied because there is nothing here that COULD name one. The module imports no
    # `EpistemicStatus` to assign, and the one place it writes the status key reads it off the mark
    # — `nestedness_organ.epistemic_for` appears only to CHECK a mark against its own basis, which
    # is the organ's derivation being consulted rather than a second opinion being formed.
    source = _MODULE.read_text()
    assert "EpistemicStatus" not in source, (
        f"{_MODULE.name} can name a status — a lane may never name the epistemic status of "
        f"evidence it did not produce. This wave shipped that failure once, in an agent's "
        f"first-person memory, and it read as principled on the line that caused it.")
    written = re.findall(r"STATUS_KEY:\s*(.+)", source)
    assert written == ["(reach.mark or {}).get(STATUS_KEY),"], written


def test_the_step_carries_both_readings_and_the_ledger_has_accepted_nothing():
    """`DECISION-measured-private-vs-shared-ledger`, on the row that records the journey. The agent
    moved on its own measured evidence; the durable record says `proposed`, and the gap between
    those two numbers is the curator's act nobody has performed."""
    posts, doc, marks = _world()
    agent = _standing(posts["p1"], "m_part")
    entry = mv.step(agent, mv.select(mv.horizon(agent, doc, posts, proposed_marks=marks)),
                    now=STAMP)
    assert entry[STATUS_KEY] == EpistemicStatus.MEASURED.value
    assert entry["ledger_status"] == obs_mod.LEDGER_PROPOSED

    # and once a curator commits the mark, the same edge reads measured on the shared record too
    committed = {**posts, "p2": {**posts["p2"], "visual_marks": [marks[0]]}}
    walker = _standing(committed["p1"], "m_part")
    row = mv.horizon(walker, doc, committed)[0]
    assert row.reachable is True and row.ledger_status == EpistemicStatus.MEASURED.value


def test_a_walk_leaves_every_post_byte_identical():
    """Suggestions-only, checked rather than claimed — the same guard the kernel and the first
    agent lane both make unfalsifiable."""
    from backend.services.movement_kernel import assert_posts_unchanged, posts_fingerprint

    posts, doc, marks = _world()
    before = posts_fingerprint(posts)
    agent = _standing(posts["p1"], "m_part")
    mv.step(agent, mv.select(mv.horizon(agent, doc, posts, proposed_marks=marks)), now=STAMP)
    sa.perceive(agent, posts["p2"], now=STAMP)
    sa.remember(agent, now=STAMP)
    sa.report(agent, now=STAMP)

    assert_posts_unchanged(before, posts_fingerprint(posts))
    assert all("visual_marks" not in post for post in posts.values())


def test_the_trajectory_tells_looking_apart_from_going():
    posts, doc, marks = _world()
    agent = _standing(posts["p1"], "m_part")
    mv.step(agent, mv.select(mv.horizon(agent, doc, posts, proposed_marks=marks)), now=STAMP)
    sa.perceive(agent, posts["p2"], now=STAMP)
    assert [e["kind"] for e in agent.trajectory] == [
        sa.TRAJECTORY_PERCEIVE, sa.TRAJECTORY_STEP, sa.TRAJECTORY_PERCEIVE]


def test_the_agent_dumps_its_horizon_alongside_its_field():
    posts, doc, marks = _world()
    agent = _standing(posts["p1"], "m_part")
    mv.horizon(agent, doc, posts, proposed_marks=marks)
    dumped = agent.as_dict()
    assert dumped["horizon"][0]["reachable"] is True
    assert dumped["horizon"][0]["destination"] == {"post_id": "p2", "region_id": "m_part2"}
    assert dumped["horizon"][0]["ledger_status"] == obs_mod.LEDGER_PROPOSED
