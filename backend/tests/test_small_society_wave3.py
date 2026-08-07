"""WAVE3 — the first small society: what appears at three, and the two ways it would fake it.

Three agents is not "two agents, plus one". Two structures exist here that CANNOT ARISE in a pair,
and each of them is a place a lie would be invisible:

  1. THE COMPARABILITY PARTITION — some pairs can be about the same thing and some cannot, and the
     difference between "we found nothing in common" and "there is nothing we could have in common"
     is the whole content of this lane. A society that flattened them would print the same
     transcript. §1.
  2. THE WHOLLY-RECEIVED BELIEF — with two agents every joint hypothesis has both of them as
     contributors, so an agent holding a claim it contributed nothing to is a state that cannot
     occur. At three it occurs immediately, and `dialogue.hold` would record it without complaint
     as `contributed=0 received=2`. §2.

§3 is the three-way outcome itself (two compose, the third is asked and refuses), §4 the guards
this lane inherits and must not weaken, §5 the substrate claims it rests on.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.services import adjacency_organ as adj
from backend.services import chroma_organ as chroma
from backend.services import mask_geometry as mg
from backend.services import nestedness_organ as nest
from backend.services.agents import dialogue as dlg
from backend.services.agents import meeting as mt
from backend.services.agents import movement as mv
from backend.services.agents import observation as obs_mod
from backend.services.agents import situated_agent as sa
from backend.services.agents import society as soc
from backend.services.epistemics import STATUS_KEY, EpistemicStatus
from backend.services.movement_graph import movement_edge_entry

STAMP = "2026-08-07T00:00:00+00:00"
AXIS = nest.AXIS_NESTEDNESS
RASTER = 10


# ── fixtures: the rim, and a raster with light in it ────────────────────────

def _rle(x0, x1, y0, y1, w=RASTER, h=RASTER):
    bits = [0] * (w * h)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * w + x] = 1
    return mg.rle_encode(bits, w, h)


#: The dialogue lane's geometry: `r_rim` is INSIDE `r_whole` and MEETS its lip — the one position
#: that needs two organs to state, and the only reason any pair here composes at all.
WHOLE = {"id": "r_whole", "label": "whole", "mask_rle": _rle(0, 6, 0, 10)}
RIM = {"id": "r_rim", "label": "part", "mask_rle": _rle(3, 6, 4, 8)}


class FakeImage:
    """A raster with a warm left half, duck-typed on the three methods `sample_rgb` calls.

    No image library, deliberately — the chroma organ's own tests make the same choice and give the
    same reason: an organ whose tests need PIL is an organ whose numbers are partly PIL's.
    """

    def __init__(self, size=RASTER):
        self.size = size

    def convert(self, _mode):
        return self

    def resize(self, wh):
        return FakeImage(int(wh[0]))

    def getdata(self):
        return [self._px(i) for i in range(self.size * self.size)]

    def _px(self, i):
        x = i % self.size
        return (220, 90, 40) if x < self.size // 2 else (40, 90, 220)


#: The other half of the dialogue lane's 2×2, and the fixture that separates `coexistent` from
#: `incommensurable`: `r_deep` is inside `r_whole` and nowhere near its boundary, and touches
#: `r_neigh` without being inside it. Two geometry agents there share no subject at all.
DEEP = {"id": "r_deep", "label": "core", "mask_rle": _rle(2, 4, 2, 8)}
NEIGH = {"id": "r_neigh", "label": "next", "mask_rle": _rle(4, 6, 2, 8)}


def _post(post_id):
    return {"_id": post_id, "region_annotations": [dict(RIM), dict(WHOLE)]}


def _deep_post(post_id):
    return {"_id": post_id, "region_annotations": [dict(DEEP), dict(WHOLE), dict(NEIGH)]}


def _node(post_id, region_id):
    return obs_mod.node_id_for(post_id, region_id)


def _mark(post, inner, outer):
    regions = {str(r["id"]): r for r in post["region_annotations"]}
    return nest.grounding_mark(nest.measure(regions[inner], regions[outer]),
                               post_id=str(post["_id"]), step_id="test:society", now=STAMP)


def _edge(mark, source_node, target_node, spans, *, systematicity=0.6):
    return movement_edge_entry(
        mark_id=str(mark["id"]), source_node=source_node, target_node=target_node, spans=spans,
        axis_ref=AXIS, systematicity=systematicity, weight=0.25, now=STAMP)


def _society(organ_sets=None, *, image=None):
    """Three agents in three different images, each walking one measured crossing to a fourth.

    Default bodies: containment, boundary contact, and warmth — two geometry agents that can
    compose, and one that cannot be about the same thing as either.
    """
    organ_sets = organ_sets or [(nest.ORGAN,), (adj.ORGAN,), (chroma.ORGAN,)]
    # A DECLARED frame, not a bare stub: ORGAN-PROVENANCE-001 made that chroma's contract, and a
    # fixture that skipped the declaration would be exercising a call shape no real caller can use.
    image = image or chroma.image_frame(FakeImage(), source="fixture:society")
    posts = {pid: _post(pid) for pid in ("pA", "pB", "pC", "pMeet")}
    far = _mark(posts["pMeet"], "r_rim", "r_whole")
    graph = {"edges": [
        _edge(far, _node(home, "r_rim"), _node("pMeet", "r_rim"), [home, "pMeet"],
              systematicity=0.6 + i / 100)
        for i, home in enumerate(("pA", "pB", "pC"))]}

    agents = []
    for name, home, organ_set in zip(("alpha", "beta", "gamma"), ("pA", "pB", "pC"), organ_sets):
        agent = sa.inhabit(agent_id=name, post_id=home, region_id="r_rim", organ_set=organ_set)
        sa.perceive(agent, posts[home], now=STAMP, image=image)
        rows = mv.horizon(agent, graph, posts, proposed_marks=[far])
        mv.step(agent, mv.select(rows), now=STAMP)
        sa.perceive(agent, posts["pMeet"], now=STAMP, image=image)
        agents.append(agent)
    return posts, agents


def test_the_meeting_locus_needs_two_organs_to_describe():
    """The fixture's premise. If `r_rim` stopped being both nested in and adjacent to `r_whole`,
    nothing would compose and half this file would pass by testing an empty list."""
    regions = {str(r["id"]): r for r in _post("p")["region_annotations"]}
    assert nest.measure(regions["r_rim"], regions["r_whole"])["nested"]
    assert adj.measure(regions["r_rim"], regions["r_whole"])["adjacent"]
    assert chroma.measure(regions["r_rim"], chroma.image_frame(FakeImage(), source="fixture"))["basis"] == "mask"


# ── 1. the comparability partition ─────────────────────────────────────────

def test_the_society_splits_into_who_could_be_about_the_same_thing():
    posts, agents = _society()
    society = soc.convene(agents, now=STAMP)

    assert society.classes() == [["alpha", "beta"], ["gamma"]]
    assert soc.comparable(agents[0], agents[1]) is True
    assert soc.comparable(agents[0], agents[2]) is False


def test_the_geometry_pair_composes_and_both_other_pairs_cannot_even_try():
    posts, agents = _society()
    society = soc.convene(agents, now=STAMP)
    outcomes = {(v.left_id, v.right_id): v.outcome for v in society.verdicts}

    assert outcomes[("alpha", "beta")] == soc.COMPOSED
    assert outcomes[("alpha", "gamma")] == soc.INCOMMENSURABLE
    assert outcomes[("beta", "gamma")] == soc.INCOMMENSURABLE
    assert society.hypotheses(), "the composing pair produced nothing — the fixture is inert"


def test_incommensurable_is_not_the_same_answer_as_nothing_in_common():
    """THE DISTINCTION THIS LANE EXISTS TO REPRESENT, over a locus built to separate them.

    On `r_deep` the containment agent relates the locus to `r_whole` and the contact agent relates
    it to `r_neigh` — deep inside one thing, touching another, sharing no subject at all. They
    `coexist`: they could have been about the same thing (at the rim they are) and here they are
    not. A chroma agent at the same locus never could be.
    """
    posts, agents = _society()
    posts["pDeep"] = _deep_post("pDeep")
    alpha, _, gamma = agents

    pair = []
    for name, organ_set in (("delta", (nest.ORGAN,)), ("epsilon", (adj.ORGAN,))):
        agent = sa.inhabit(agent_id=name, post_id="pDeep", region_id="r_deep",
                           organ_set=organ_set)
        sa.perceive(agent, posts["pDeep"], now=STAMP)
        pair.append(agent)
    assert {p.reading.other_region_id for p in pair[0].percept_field} == {"r_whole"}
    assert {p.reading.other_region_id for p in pair[1].percept_field} == {"r_neigh"}

    coexist = soc.relate(*pair, now=STAMP)
    assert coexist.outcome == soc.COEXISTENT and coexist.shared_subjects == ()
    assert "fact about this locus, not about these bodies" in coexist.detail

    unrelatable = soc.relate(alpha, gamma, now=STAMP)
    assert unrelatable.outcome == soc.INCOMMENSURABLE
    assert "no common scale" in unrelatable.detail


def test_a_member_that_measured_nothing_is_undetermined_and_not_incommensurable():
    """CAUGHT BY THIS FILE, from the inside. `comparable` reads arities off the readings, so an
    agent with an empty field has none — and the first version reported a SILENT agent as
    incommensurable with everyone, which is the exact confusion the lane exists to prevent.

    "We could never be about the same thing" is a strong claim. Saying nothing is no evidence for
    it.
    """
    posts, agents = _society()
    mute = sa.inhabit(agent_id="delta", post_id="pMeet", region_id="r_rim",
                      organ_set=(adj.ORGAN,))
    sa.perceive(mute, posts["pMeet"], now=STAMP)
    mute.percept_field = []

    verdict = soc.relate(agents[0], mute, now=STAMP)
    assert verdict.outcome == soc.UNDETERMINED
    assert "no evidence that there is nothing to find" in verdict.detail

    quiet = soc.Society(members=[*agents, mute])
    assert quiet.silent() == ["delta"]
    assert ["delta"] not in quiet.classes(), "silence must not become a class of its own"


def test_comparability_is_read_off_the_readings_and_not_off_an_organ_name():
    """The tempting implementation is `if organ == 'chroma_organ'`, which hard-codes today's
    sensorium into the society layer and would be wrong the day a chromatic RELATION exists."""
    source = Path(soc.__file__).read_text()
    assert "chroma_organ" not in re.sub(r'""".*?"""', "", source, flags=re.S).replace(
        "from backend.services import chroma_organ", "").replace(
        "chroma_organ.compare_across_senses", "").replace(
        "chroma_organ.Incommensurable", ""), \
        "the society layer decides comparability by organ NAME somewhere"

    posts, agents = _society()
    assert soc.arity(agents[0].percept_field[0].reading) == 2      # relates two regions
    assert soc.arity(agents[2].percept_field[0].reading) == 1      # a property of one place


def test_the_refusal_comes_from_the_sensorium_and_is_not_paraphrased_here():
    """Reused, not re-implemented — the discipline `dialogue.say` keeps with `attest`. A society
    layer with its own copy of "these cannot be compared" is a second place that can stop saying
    so, and it is the place deciding whether two senses may be compared."""
    posts, agents = _society()
    detail = soc.refuse_comparison(agents[0], agents[2])
    try:
        chroma.compare_across_senses({}, {})
    except chroma.Incommensurable as exc:
        assert detail == str(exc)


def test_a_comparison_that_stops_refusing_is_a_defect_and_raises(monkeypatch):
    """If `compare_across_senses` ever answers, this layer must not carry the number on. A
    cross-sense magnitude is the single easiest way to make the system confident about something
    nobody has measured."""
    posts, agents = _society()
    monkeypatch.setattr(chroma, "compare_across_senses", lambda *a, **k: 0.42)
    with pytest.raises(soc.CompatibilityLeak, match="instead of refusing"):
        soc.refuse_comparison(agents[0], agents[2])


# ── 2. the wholly-received belief ──────────────────────────────────────────

def test_an_agent_may_not_hold_a_claim_it_contributed_nothing_to():
    """THE STATE THAT ONLY EXISTS AT THREE. γ stands in the room while α and β compose."""
    posts, agents = _society()
    society = soc.convene(agents, now=STAMP)
    held = soc.hold_all(society, now=STAMP)

    for agent_id in ("alpha", "beta"):
        beliefs = soc.held_beliefs(held[agent_id])
        assert beliefs and all(b[STATUS_KEY] == EpistemicStatus.INTERPRETIVE.value
                               for b in beliefs)
        assert all(b["contributed"] == 1 and b["received"] == 1 for b in beliefs)
        assert not soc.refusals_to_hold(held[agent_id])

    assert soc.held_beliefs(held["gamma"]) == []
    refused = soc.refusals_to_hold(held["gamma"])
    assert refused and all(r["reason"] == soc.WHOLLY_RECEIVED for r in refused)
    assert "hearsay however many other agents stand behind it" in refused[0]["detail"]


def test_the_hole_this_closes_is_real_and_dialogue_alone_would_not_catch_it():
    """`dialogue.hold` is written for a belief the holder contributed something to, because with
    two agents that is the only kind there is. Called on a non-contributor it records the claim
    without complaint — which is what makes this worth a rule rather than a convention."""
    posts, agents = _society()
    society = soc.convene(agents, now=STAMP)
    hypothesis = society.hypotheses()[0]

    unearned = dlg.hold(agents[2], hypothesis, now=STAMP)
    assert unearned["contributed"] == 0 and unearned["received"] == 2
    assert unearned[STATUS_KEY] == EpistemicStatus.INTERPRETIVE.value, \
        "it is not even flagged — it reads exactly like a legitimately held joint belief"


def test_a_refusal_to_hold_is_a_refusal_and_never_a_weaker_holding():
    """Not `uncertain`, not held-with-a-flag. A supported way to hold a wholly received claim is a
    supported way to launder one."""
    posts, agents = _society()
    society = soc.convene(agents, now=STAMP)
    refused = soc.refusals_to_hold(soc.hold_all(society, now=STAMP)["gamma"])
    for row in refused:
        assert STATUS_KEY not in row
        assert row["kind"] == "refused_to_hold"
    assert not any(r.get("kind") == "joint_hypothesis" for r in agents[2].memory)


# ── 3. the three-way outcome ───────────────────────────────────────────────

def test_two_compose_and_the_third_is_asked_and_refuses():
    posts, agents = _society()
    society = soc.convene(agents, now=STAMP)
    answer = soc.put_to(agents[2], society.hypotheses()[0])

    assert answer["answer"] == "refused" and answer["reason"] == "hearsay"
    assert "no organ reading behind" in answer["detail"]


def test_a_third_agent_that_measured_it_too_restates_and_does_not_corroborate():
    """The other honest answer, and it is not a vote. Two agents measuring the same thing is two
    readings; `movement_graph.strengthen` refuses to move a weight on agreement for this reason."""
    posts, agents = _society()
    society = soc.convene(agents, now=STAMP)
    hypothesis = society.hypotheses()[0]

    # a second containment body at the meeting locus measures α's half for itself
    echo = sa.inhabit(agent_id="delta", post_id="pMeet", region_id="r_rim",
                      organ_set=(nest.ORGAN,))
    sa.perceive(echo, posts["pMeet"], now=STAMP)
    answer = soc.put_to(echo, hypothesis)
    assert answer["answer"] == "restated"
    assert answer["corroborates"] is False


def test_the_society_refuses_to_stage_a_measured_contradiction():
    """Reported rather than manufactured. The organs are deterministic geometry and a
    `nested_within` reading and a `meets` reading about one pair are compatible BY CONSTRUCTION —
    that is why they compose. What a third agent adds is refusal, not contradiction, and dressing
    the second as the first would be the lane inventing its own headline."""
    source = Path(soc.__file__).read_text()
    assert "contradiction" in source, "the limit must be named where the code lives"
    for invented in ("disagrees", "contradicts", "refutes"):
        assert f'"{invented}"' not in source


# ── 4. what the society inherits and does not weaken ───────────────────────

def test_a_member_who_did_not_walk_here_is_refused():
    posts, agents = _society()
    placed = sa.inhabit(agent_id="delta", post_id="pMeet", region_id="r_rim",
                        organ_set=(adj.ORGAN,))
    sa.perceive(placed, posts["pMeet"], now=STAMP)
    with pytest.raises(mt.NotTravelled, match="staged meeting"):
        soc.convene([agents[0], agents[2], placed], now=STAMP)


def test_a_member_who_has_not_looked_since_arriving_is_refused():
    posts, agents = _society()
    agents[1].percept_field = []
    with pytest.raises(mt.NotHere, match="measured nothing here"):
        soc.convene(agents, now=STAMP)


def test_two_is_not_a_society_and_three_identical_bodies_are_not_either():
    posts, agents = _society()
    with pytest.raises(soc.NotASociety, match="dialogue lane"):
        soc.convene(agents[:2], now=STAMP)

    posts, uniform = _society(organ_sets=[(nest.ORGAN,)] * 3)
    with pytest.raises(soc.NotASociety, match="one world enacted three times"):
        soc.convene(uniform, now=STAMP)


def test_two_members_with_one_body_coexist_as_two_copies_of_one_world():
    """Allowed in a society (the card asks for ≥2 organ-sets, not three), and named for what it
    is. `dialogue.exchange` owns this rule; it is called and its refusal caught, not pre-empted."""
    posts, agents = _society(organ_sets=[(nest.ORGAN,), (nest.ORGAN,), (chroma.ORGAN,)])
    society = soc.convene(agents, now=STAMP)
    outcomes = {(v.left_id, v.right_id): v.outcome for v in society.verdicts}
    assert outcomes[("alpha", "beta")] == soc.SAME_BODY
    assert society.classes() == [["alpha", "beta"], ["gamma"]]
    assert society.hypotheses() == [], "two copies of one world compose nothing"


def test_the_joint_hypothesis_is_still_proposed_with_three_in_the_room():
    posts, agents = _society()
    society = soc.convene(agents, now=STAMP)
    for h in society.hypotheses():
        assert dlg.hydrate_hypothesis(h, posts)["ledger_status"] == obs_mod.LEDGER_PROPOSED
        committed = {**posts, "pMeet": {**posts["pMeet"], "visual_marks": list(h["rests_on"])}}
        assert dlg.hydrate_hypothesis(h, committed)["ledger_status"] == obs_mod.LEDGER_PROPOSED


def test_the_hypotheses_still_carry_how_each_contributor_arrived():
    posts, agents = _society()
    society = soc.convene(agents, now=STAMP)
    for h in society.hypotheses():
        assert sorted(h["arrived_by"]) == ["alpha", "beta"]
        assert all(j["steps"] == 1 for j in h["arrived_by"].values())
        dlg.assert_valid_hypothesis(h)


def test_this_module_writes_no_status_of_its_own():
    source = Path(soc.__file__).read_text()
    assert "EpistemicStatus" not in source
    assert not re.search(r"STATUS_KEY\s*[:=]", source)


def test_a_society_leaves_every_post_byte_identical():
    from backend.services.movement_kernel import assert_posts_unchanged, posts_fingerprint

    posts, agents = _society()
    before = posts_fingerprint(posts)
    society = soc.convene(agents, now=STAMP)
    soc.hold_all(society, now=STAMP)
    soc.put_to(agents[2], society.hypotheses()[0])
    assert_posts_unchanged(before, posts_fingerprint(posts))
    assert all("visual_marks" not in p for p in posts.values())


# ── 5. the substrate ───────────────────────────────────────────────────────

def test_the_chroma_agent_really_did_measure_something_here():
    """Its incommensurability must not be an empty field wearing a principle."""
    posts, agents = _society()
    gamma = agents[2]
    assert gamma.percept_field
    reading = gamma.percept_field[0].reading
    assert reading.relation == chroma.FIELD_WARMTH and reading.other_region_id == ""
    assert reading.epistemic_status == EpistemicStatus.MEASURED.value


def test_no_comparable_number_is_hiding_under_another_name():
    """#158's second guard, re-run from the society's side: a refusal is worth nothing if the
    thing it refuses is available next door."""
    posts, agents = _society()
    geo = dict(agents[0].percept_field[0].reading.measurement)
    chr_ = dict(agents[2].percept_field[0].reading.measurement)
    for shared in set(geo) & set(chr_):
        assert not isinstance(geo[shared], float) or not isinstance(chr_[shared], float), \
            f"{shared!r} is a float in both senses and invites a comparison nobody has earned"
