"""WAVE3 — two agents move, then meet: the four ways an EARNED meeting would fake being one.

A staged meeting and an earned one produce the same transcript. Same two fields, same exchange,
same composition, same `proposed` row — the only difference is whether each agent walked to the
place it is speaking from, and nothing downstream can tell. So these tests are not coverage of a
fusion; each guards a claim that would still look right if it failed:

  1. TRAVELLED — a meeting neither agent walked to is #148 in this lane's vocabulary, and it is
     refused rather than arranged against. §1.
  2. ARRIVED EMPTY — an agent speaks only from what it measured AFTER arriving. `step` empties the
     percept field; this checks the emptiness is real, not that the docstring says so. §2.
  3. THE MEETING IS COMPUTED, NOT WISHED FOR — `rendezvous` is the intersection of two horizons of
     MEASURED crossings, neither agent sees the other's, and the rule that picks one is the
     observer's and is named on the record. §3.
  4. THE COMPOSITION IS STILL `proposed` — travel is not an argument for promotion. An agent that
     walked further has not measured more, and this module has no path to `measured`. §4.

§5 covers what the lane inherits and must not weaken: hearsay, testimony-is-interpretive, the
dialogue contract, and posts byte-identical.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.services import adjacency_organ as adj
from backend.services import mask_geometry as mg
from backend.services import nestedness_organ as nest
from backend.services.agents import dialogue as dlg
from backend.services.agents import meeting as mt
from backend.services.agents import movement as mv
from backend.services.agents import observation as obs_mod
from backend.services.agents import situated_agent as sa
from backend.services.epistemics import STATUS_KEY, EpistemicStatus
from backend.services.movement_graph import movement_edge_entry

STAMP = "2026-08-06T00:00:00+00:00"
AXIS = nest.AXIS_NESTEDNESS


# ── fixtures: the rim, on one 10×10 raster, in three different images ────────

def _rle(x0, x1, y0, y1, w=10, h=10):
    bits = [0] * (w * h)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * w + x] = 1
    return mg.rle_encode(bits, w, h)


#: The dialogue lane's own geometry, reused rather than re-derived: `r_rim` is INSIDE `r_whole` and
#: MEETS its lip, which is the one position that needs both organs to state. If this pair ever
#: stopped being both, every composition in this file would vanish and the tests would pass by
#: asserting nothing — so `test_the_meeting_locus_really_is_the_rim` pins it directly.
WHOLE = {"id": "r_whole", "label": "whole", "mask_rle": _rle(0, 6, 0, 10)}
RIM = {"id": "r_rim", "label": "part", "mask_rle": _rle(3, 6, 4, 8)}
BESIDE = {"id": "r_beside", "label": "next", "mask_rle": _rle(6, 9, 2, 8)}

#: A SECOND whole that `r_rim` is also at the rim of, so the meeting post affords two compositions
#: about two different regions. Without it the "two claims do not read as one sentence" test would
#: pass by having only one claim to render.
WHOLE2 = {"id": "r_whole2", "label": "outer", "mask_rle": _rle(0, 7, 0, 10)}


def _post(post_id, *, two_wholes=False):
    regions = [dict(RIM), dict(WHOLE), dict(BESIDE)]
    if two_wholes:
        regions.append(dict(WHOLE2))
    return {"_id": post_id, "region_annotations": regions}


def _node(post_id, region_id):
    return obs_mod.node_id_for(post_id, region_id)


def _mark(post, inner, outer):
    """A real nestedness measurement on this post's geometry — mask basis, never committed."""
    regions = {str(r["id"]): r for r in post["region_annotations"]}
    measurement = nest.measure(regions[inner], regions[outer])
    return nest.grounding_mark(measurement, post_id=str(post["_id"]), step_id="test:meet",
                               now=STAMP)


def _edge(mark, source_node, target_node, spans, *, systematicity=0.6):
    return movement_edge_entry(
        mark_id=str(mark["id"]), source_node=source_node, target_node=target_node, spans=spans,
        axis_ref=AXIS, systematicity=systematicity, weight=0.25, now=STAMP)


def _world():
    """Two agents in two different images, and one image both can reach on a measured crossing.

    α carries containment and β carries boundary contact — they MUST differ, or the exchange is one
    world enacted twice (`dialogue.exchange` refuses it). Both crossings are grounded on
    nestedness, because that is the only relation the kernel grounds in this corpus: β walks a road
    it did not survey, on ground its own organ checked.
    """
    posts = {"pA": _post("pA"), "pB": _post("pB"), "pMeet": _post("pMeet")}
    far = _mark(posts["pMeet"], "r_rim", "r_whole")
    graph = {"edges": [
        _edge(far, _node("pA", "r_rim"), _node("pMeet", "r_rim"), ["pA", "pMeet"],
              systematicity=0.6),
        _edge(far, _node("pB", "r_rim"), _node("pMeet", "r_rim"), ["pB", "pMeet"],
              systematicity=0.8),
    ]}
    alpha = sa.inhabit(agent_id="alpha", post_id="pA", region_id="r_rim",
                       organ_set=(nest.ORGAN,))
    beta = sa.inhabit(agent_id="beta", post_id="pB", region_id="r_rim",
                      organ_set=(adj.ORGAN,))
    sa.perceive(alpha, posts["pA"], now=STAMP)
    sa.perceive(beta, posts["pB"], now=STAMP)
    return posts, graph, [far], alpha, beta


def _walk_both(posts, graph, marks, alpha, beta, *, rule=mt.RENDEZVOUS_MIN):
    """Both agents to the shared node, each perceiving after it arrives."""
    options = mt.rendezvous(alpha, beta,
                            mv.horizon(alpha, graph, posts, proposed_marks=marks),
                            mv.horizon(beta, graph, posts, proposed_marks=marks))
    chosen = mt.choose(options, rule=rule)
    assert chosen is not None, "the fixture must offer a meeting, or nothing below is tested"
    mv.step(alpha, chosen.alpha, now=STAMP)
    mv.step(beta, chosen.beta, now=STAMP)
    for agent in (alpha, beta):
        sa.perceive(agent, posts[chosen.post_id], now=STAMP)
    return chosen


def test_the_meeting_locus_really_is_the_rim():
    """THE FIXTURE'S PREMISE, checked rather than assumed. If `r_rim` stopped being both nested in
    and adjacent to `r_whole`, `compose` would return nothing and half this file would pass by
    testing an empty list."""
    regions = {str(r["id"]): r for r in _post("p")["region_annotations"]}
    nested = nest.measure(regions["r_rim"], regions["r_whole"])
    meets = adj.measure(regions["r_rim"], regions["r_whole"])
    assert nested["nested"] and nested["basis"] == "mask"
    assert meets["adjacent"] and meets["basis"] == "mask"


# ── 1. travelled: the one thing that makes a meeting earned ─────────────────

def test_two_agents_walk_from_different_images_and_meet():
    posts, graph, marks, alpha, beta = _world()
    chosen = _walk_both(posts, graph, marks, alpha, beta)

    assert chosen.node_id == _node("pMeet", "r_rim")
    assert alpha.locus == beta.locus
    record = mt.meet(alpha, beta, now=STAMP)

    assert [j["origin_node"] for j in record["journeys"]] == [
        _node("pA", "r_rim"), _node("pB", "r_rim")]
    assert all(j["steps"] == 1 and j["arrived_node"] == chosen.node_id
               for j in record["journeys"])
    assert record["hypotheses"], "the meeting produced nothing neither knew alone"


def test_a_meeting_one_agent_did_not_walk_to_is_refused():
    """The staged meeting, arriving under this lane's name. #148 built it and it is a real thing;
    what it is not is EARNED, and the two transcripts are otherwise identical."""
    posts, graph, marks, alpha, beta = _world()
    chosen = _walk_both(posts, graph, marks, alpha, beta)

    # β is placed at the meeting locus instead of walking there
    stationary = sa.inhabit(agent_id="beta", post_id=chosen.post_id, region_id=chosen.region_id,
                            organ_set=(adj.ORGAN,))
    sa.perceive(stationary, posts[chosen.post_id], now=STAMP)
    assert stationary.percept_field, "it is standing in the right place with a real field"

    with pytest.raises(mt.NotTravelled, match="staged meeting"):
        mt.meet(alpha, stationary, now=STAMP)


def test_the_journey_cites_the_mark_each_leg_rested_on():
    posts, graph, marks, alpha, beta = _world()
    _walk_both(posts, graph, marks, alpha, beta)
    for j in (mt.journey(alpha), mt.journey(beta)):
        assert j["steps"] == 1
        leg = j["legs"][0]
        assert leg["mark_id"] == marks[0]["id"]
        assert leg["basis"] == nest.ADMISSIBLE_BASIS
        assert leg["epistemic_status"] == EpistemicStatus.MEASURED.value
        assert leg["ledger_status"] == obs_mod.LEDGER_PROPOSED


# ── 2. arrived empty: no knowledge carried across the step ──────────────────

def test_an_agent_that_arrived_and_has_not_looked_cannot_speak():
    posts, graph, marks, alpha, beta = _world()
    options = mt.rendezvous(alpha, beta,
                            mv.horizon(alpha, graph, posts, proposed_marks=marks),
                            mv.horizon(beta, graph, posts, proposed_marks=marks))
    chosen = mt.choose(options)
    mv.step(alpha, chosen.alpha, now=STAMP)
    mv.step(beta, chosen.beta, now=STAMP)

    assert alpha.percept_field == [] and beta.percept_field == []
    with pytest.raises(mt.NotHere, match="measured nothing here"):
        mt.meet(alpha, beta, now=STAMP)


def test_a_field_measured_at_the_previous_locus_is_refused_as_the_wrong_image():
    """`step` empties the field so this state cannot arise from the outside. The guard exists for
    the day something reaches around it: a stale field would make every sentence parse, and every
    one would be about the image the agent left."""
    posts, graph, marks, alpha, beta = _world()
    stale = list(alpha.percept_field)                       # measured at pA, before the step
    chosen = _walk_both(posts, graph, marks, alpha, beta)
    alpha.percept_field = stale

    with pytest.raises(mt.NotHere, match="wearing the name of the image it reached"):
        mt.meet(alpha, beta, now=STAMP)
    assert chosen.post_id == "pMeet"


def test_what_each_agent_says_at_the_meeting_was_measured_there():
    posts, graph, marks, alpha, beta = _world()
    chosen = _walk_both(posts, graph, marks, alpha, beta)
    record = mt.meet(alpha, beta, now=STAMP)

    for side in ("alpha", "beta"):
        for said in record["exchange"][side]["said"]:
            assert said["post_id"] == chosen.post_id
            assert said["region_id"] == chosen.region_id


def test_a_view_no_organ_of_the_speaker_measured_here_is_still_hearsay():
    """The refusal that looks like cooperation. β is standing in the same place and has just heard
    α say it; none of that makes it β's to say. Reused from `situated_agent.attest`, not
    re-implemented — `dialogue` already asserts the identity."""
    posts, graph, marks, alpha, beta = _world()
    _walk_both(posts, graph, marks, alpha, beta)

    alphas_finding = {"relation": nest.RELATION_NESTED_WITHIN, "direction": "within",
                      "other_region_id": "r_whole"}
    assert dlg.say(alpha, alphas_finding)                   # α measured it
    with pytest.raises(sa.Hearsay, match="no organ reading behind"):
        dlg.say(beta, alphas_finding)                       # β heard it


# ── 3. the meeting is computed, and the rule that picks one is the observer's ──

def test_a_rendezvous_is_the_intersection_of_two_measured_horizons():
    posts, graph, marks, alpha, beta = _world()
    options = mt.rendezvous(alpha, beta,
                            mv.horizon(alpha, graph, posts, proposed_marks=marks),
                            mv.horizon(beta, graph, posts, proposed_marks=marks))
    assert [r.node_id for r in options] == [_node("pMeet", "r_rim")]
    assert options[0].alpha.reachable and options[0].beta.reachable


def test_a_destination_only_one_agent_can_reach_is_not_a_meeting():
    posts, graph, marks, alpha, beta = _world()
    posts["pC"] = _post("pC")
    solo = _mark(posts["pC"], "r_rim", "r_whole")
    graph["edges"].append(_edge(solo, _node("pA", "r_rim"), _node("pC", "r_rim"),
                                ["pA", "pC"], systematicity=0.99))

    options = mt.rendezvous(alpha, beta,
                            mv.horizon(alpha, graph, posts, proposed_marks=[*marks, solo]),
                            mv.horizon(beta, graph, posts, proposed_marks=[*marks, solo]))
    assert [r.node_id for r in options] == [_node("pMeet", "r_rim")], \
        "pC is α's strongest crossing and β cannot get there — it is not a meeting"


def test_a_crossing_one_of_them_can_only_SEE_is_not_a_meeting():
    """The WAVE2.5 gate, inherited whole. β's leg is grounded on box geometry, so β may see the
    node and may not step to it — and a rendezvous built from what agents can see rather than
    where they can go would put them in a room only one of them could enter."""
    posts, graph, marks, alpha, beta = _world()
    boxed = {"_id": "pD", "region_annotations": [
        {"id": "r_rim", "box": {"x": 0.30, "y": 0.40, "w": 0.30, "h": 0.40}},
        {"id": "r_whole", "box": {"x": 0.00, "y": 0.00, "w": 0.60, "h": 1.00}}]}
    posts["pD"] = boxed
    estimate = _mark(boxed, "r_rim", "r_whole")
    assert estimate[STATUS_KEY] == EpistemicStatus.INTERPRETIVE.value
    for source in ("pA", "pB"):
        graph["edges"].append(_edge(estimate, _node(source, "r_rim"), _node("pD", "r_rim"),
                                    [source, "pD"], systematicity=0.99))

    held = [*marks, estimate]
    alpha_rows = mv.horizon(alpha, graph, posts, proposed_marks=held)
    beta_rows = mv.horizon(beta, graph, posts, proposed_marks=held)
    assert any(r.other_node == _node("pD", "r_rim") and not r.reachable for r in alpha_rows)
    assert [r.node_id for r in mt.rendezvous(alpha, beta, alpha_rows, beta_rows)] == \
        [_node("pMeet", "r_rim")]


def test_a_node_one_of_them_is_already_standing_on_is_not_a_meeting():
    """It would make that agent's journey zero steps — the staged meeting, offered by the
    rendezvous rather than caught by the guard afterwards."""
    posts, graph, marks, alpha, beta = _world()
    back = _mark(posts["pA"], "r_rim", "r_whole")
    graph["edges"].append(_edge(back, _node("pB", "r_rim"), _node("pA", "r_rim"),
                                ["pA", "pB"], systematicity=0.99))
    options = mt.rendezvous(alpha, beta,
                            mv.horizon(alpha, graph, posts, proposed_marks=[*marks, back]),
                            mv.horizon(beta, graph, posts, proposed_marks=[*marks, back]))
    assert _node("pA", "r_rim") not in {r.node_id for r in options}


def test_the_rendezvous_rule_is_named_recorded_and_deterministic():
    posts, graph, marks, alpha, beta = _world()
    posts["pE"] = _post("pE")
    other = _mark(posts["pE"], "r_rim", "r_whole")
    # α's leg is excellent, β's is marginal: SUM prefers it, MIN refuses to let one strong leg
    # carry a weak one into the record.
    graph["edges"].append(_edge(other, _node("pA", "r_rim"), _node("pE", "r_rim"),
                                ["pA", "pE"], systematicity=0.99))
    graph["edges"].append(_edge(other, _node("pB", "r_rim"), _node("pE", "r_rim"),
                                ["pB", "pE"], systematicity=0.55))

    held = [*marks, other]
    options = mt.rendezvous(alpha, beta,
                            mv.horizon(alpha, graph, posts, proposed_marks=held),
                            mv.horizon(beta, graph, posts, proposed_marks=held))
    assert len(options) == 2
    assert mt.choose(options, rule=mt.RENDEZVOUS_SUM).node_id == _node("pE", "r_rim")
    assert mt.choose(options, rule=mt.RENDEZVOUS_MIN).node_id == _node("pMeet", "r_rim")
    assert mt.choose(options) is mt.choose(options), "an arranged meeting must re-arrange the same"


def test_an_unnamed_rendezvous_rule_is_refused_rather_than_defaulted():
    with pytest.raises(ValueError, match="unknown rendezvous rule"):
        mt.choose([], rule="wherever_feels_right")


def test_no_overlap_is_no_meeting_and_not_an_error():
    posts, graph, marks, alpha, beta = _world()
    graph["edges"] = [graph["edges"][0]]                    # only α can move
    assert mt.choose(mt.rendezvous(
        alpha, beta,
        mv.horizon(alpha, graph, posts, proposed_marks=marks),
        mv.horizon(beta, graph, posts, proposed_marks=marks))) is None


def test_neither_agent_can_see_the_others_horizon():
    """The rendezvous is the OBSERVER's act. If an agent could reach the other's horizon it would
    have an interest in where the other is, which is a goal — the thing this lane must not smuggle
    in while building the one arrangement that needs coordinating."""
    posts, graph, marks, alpha, beta = _world()
    mv.horizon(alpha, graph, posts, proposed_marks=marks)
    mv.horizon(beta, graph, posts, proposed_marks=marks)

    assert alpha.horizon and beta.horizon
    assert alpha.horizon is not beta.horizon
    # each row of α's horizon is a crossing FROM α's node, and none of it mentions β
    for row in alpha.horizon:
        assert row.edge["source_node"] == alpha.locus.node_id or \
            row.edge["target_node"] == alpha.locus.node_id
        assert beta.id not in str(row.as_dict())

    chosen = _walk_both(posts, graph, marks, alpha, beta, rule=mt.RENDEZVOUS_MIN)
    for step in [e for e in (*alpha.trajectory, *beta.trajectory)
                 if e.get("kind") == mv.TRAJECTORY_STEP]:
        assert step["policy"] in mv.POLICIES, \
            "a step is taken by the AGENT's rule; the meeting's rule never reaches the step"
        assert step["policy"] not in mt.RENDEZVOUS_RULES
        assert "rendezvous" not in step and "other_agent" not in step
    assert chosen.node_id  # the arrangement lives here, in the observer's hands, not on the step


# ── 4. travel is not an argument for promotion ─────────────────────────────

def test_the_earned_hypothesis_is_still_proposed_on_the_ledger():
    posts, graph, marks, alpha, beta = _world()
    _walk_both(posts, graph, marks, alpha, beta)
    record = mt.meet(alpha, beta, now=STAMP)

    for h in record["hypotheses"]:
        assert dlg.hydrate_hypothesis(h, posts)["ledger_status"] == obs_mod.LEDGER_PROPOSED
        committed = {**posts, "pMeet": {**posts["pMeet"], "visual_marks": list(marks)}}
        hydrated = dlg.hydrate_hypothesis(h, committed)
        assert hydrated["ledger_status"] == obs_mod.LEDGER_PROPOSED, \
            "committing the marks makes the INPUTS durable; the composition is still a reading"


def test_this_module_has_no_path_to_a_stronger_status():
    """Read off the source, not off behaviour — a test over inputs can only cover the cases it
    imagined, and the failure here is one line that would look like the system finally learning
    something."""
    source = Path(mt.__file__).read_text()
    assert "EpistemicStatus" not in source
    for literal in ('"measured"', "'measured'"):
        assert literal not in source
    assert not re.search(r"STATUS_KEY\s*[:=]", source), \
        "nothing in this module writes an epistemic status; travel is not evidence"


def test_each_holder_holds_the_earned_claim_interpretive_with_its_provenance():
    """`DECISION-testimony-is-interpretive`, inherited unchanged: half of this arrived by
    testimony, and walking to the room does not make it the walker's measurement."""
    posts, graph, marks, alpha, beta = _world()
    _walk_both(posts, graph, marks, alpha, beta)
    record = mt.meet(alpha, beta, now=STAMP)

    for agent_id, held in record["held"].items():
        for entry in held:
            assert entry[STATUS_KEY] == EpistemicStatus.INTERPRETIVE.value
            assert entry["contributed"] == 1 and entry["received"] == 1, agent_id


# ── 5. the artefact, and what it inherits ──────────────────────────────────

def test_the_stored_row_carries_how_each_contributor_arrived():
    posts, graph, marks, alpha, beta = _world()
    _walk_both(posts, graph, marks, alpha, beta)
    record = mt.meet(alpha, beta, now=STAMP)

    h = record["hypotheses"][0]
    assert sorted(h["arrived_by"]) == ["alpha", "beta"]
    assert h["arrived_by"]["alpha"]["origin_node"] == _node("pA", "r_rim")
    assert h["arrived_by"]["beta"]["origin_node"] == _node("pB", "r_rim")
    assert all(j["arrived_node"] == h["node_id"] for j in h["arrived_by"].values())
    # and the dialogue contract is untouched by the addition
    dlg.assert_valid_hypothesis(h)


def test_the_hypothesis_reads_as_a_sentence_with_the_travel_in_it():
    posts, graph, marks, alpha, beta = _world()
    _walk_both(posts, graph, marks, alpha, beta)
    record = mt.meet(alpha, beta, now=STAMP)
    assert record["legible"][0] == (
        f"agent alpha (via {_node('pA', 'r_rim')} —1 step(s)→ {_node('pMeet', 'r_rim')}) and "
        f"agent beta (via {_node('pB', 'r_rim')} —1 step(s)→ {_node('pMeet', 'r_rim')}) "
        f"jointly propose {dlg.CLAIM_AT_THE_RIM} about 'r_whole' "
        f"at {_node('pMeet', 'r_rim')} — proposed")


def test_two_claims_from_one_meeting_do_not_read_as_the_same_sentence():
    """The first real run composed three hypotheses about three different regions and printed the
    same line three times. A rendering that cannot tell its own outputs apart is not legibility."""
    posts, graph, marks, alpha, beta = _world()
    posts["pMeet"] = _post("pMeet", two_wholes=True)
    _walk_both(posts, graph, marks, alpha, beta)
    record = mt.meet(alpha, beta, now=STAMP)

    assert len(record["hypotheses"]) == 2, "the fixture must offer two claims to tell apart"
    assert len(set(record["legible"])) == 2
    assert {h["about_region_id"] for h in record["hypotheses"]} == {"r_whole", "r_whole2"}


def test_a_hypothesis_whose_contributor_has_no_journey_is_refused():
    posts, graph, marks, alpha, beta = _world()
    _walk_both(posts, graph, marks, alpha, beta)
    hypotheses = dlg.compose(dlg.exchange(alpha, beta), now=STAMP)
    with pytest.raises(mt.NotTravelled, match="no journey"):
        mt.earned_hypothesis(hypotheses[0], [mt.journey(alpha)])


def test_two_agents_with_the_same_body_are_still_refused_however_far_they_walked():
    """Inherited from `dialogue.exchange`. Two identical bodies at one locus enact one world twice,
    and travel does not make their agreement informative — it makes it better travelled."""
    posts, graph, marks, alpha, beta = _world()
    twin = sa.inhabit(agent_id="beta", post_id="pB", region_id="r_rim", organ_set=(nest.ORGAN,))
    sa.perceive(twin, posts["pB"], now=STAMP)
    _walk_both(posts, graph, marks, alpha, twin)
    with pytest.raises(ValueError, match="SAME world twice"):
        mt.meet(alpha, twin, now=STAMP)


def test_the_meeting_leaves_every_post_byte_identical():
    from backend.services.movement_kernel import assert_posts_unchanged, posts_fingerprint

    posts, graph, marks, alpha, beta = _world()
    before = posts_fingerprint(posts)
    _walk_both(posts, graph, marks, alpha, beta)
    mt.meet(alpha, beta, now=STAMP)
    assert_posts_unchanged(before, posts_fingerprint(posts))
    assert all("visual_marks" not in p for p in posts.values())


def test_the_meeting_module_does_not_ground_its_own_crossings():
    """#151's rule, carried forward: the kernel grounds and mints, the agent reads and walks. The
    two hash helpers are taken from `movement_kernel` (as `dialogue` already does) and no grounding
    entry point is referenced at all."""
    source = Path(mt.__file__).read_text()
    for grounding in ("run_kernel", "movement_from", "structure_map", "consider("):
        assert grounding not in source, (
            f"{grounding} appears in meeting.py — an agent that grounds the crossing it then walks "
            f"is authoring the world it reports having travelled through.")
