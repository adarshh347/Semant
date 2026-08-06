"""WAVE3 — two agents, one locus: the claims, and the places a dialogue would hide a lie.

Dialogue is where confabulation hides best, because "we both saw it" is the most persuasive
sentence this system can produce. Every test here guards a claim that would still LOOK correct from
the outside if it failed:

  1. TWO BODIES, TWO WORLDS — the disagreement between α and β comes from their ORGANS, not from
     their positions, their names, or the fixture. A staged disagreement and a real one produce
     identical transcripts, so the independence of the two measurements is pinned directly (the
     2×2: deep / rim / beside / far) rather than inferred from the run. §1.
  2. HEARSAY IN THE EXCHANGE — the room where claims are traded is exactly the room where an
     unmeasured one gets laundered. Both refusals are re-checked here, and the exchange is shown to
     REUSE `situated_agent.attest` rather than carry a second copy of the rule. §2.
  3. `proposed`, FULL STOP — the flattering one-line failure of this lane is a hypothesis that
     reads `measured` once a curator commits its two marks. It would look like the system finally
     learning something. It is agreement being counted as grounding. §3.
  4. WHAT AN AGENT PRIVATELY HOLDS — `interpretive`, with `contributed` vs `received` per mark.
     This is where the lane DEPARTS from its card, and the departure is pinned so it cannot be
     quietly undone. §4.
  5. TWO CHANNELS — the ephemeral exchange is never persisted; the durable hypothesis is written to
     `agent_hypotheses` and nowhere else, and the post comes out byte-identical. §5.
  6. THE SUBSTRATE — the new organ is pure, registered with the guard, honest about its box basis,
     and cannot ask a language model. §6.
"""
from __future__ import annotations

import asyncio
import inspect
import re
from pathlib import Path

import pytest

from backend.services import adjacency_organ as adj
from backend.services import epistemics, nestedness_organ as nest
from backend.services.agents import dialogue as dlg
from backend.services.agents import observation as obs_mod
from backend.services.agents import organs
from backend.services.agents import situated_agent as sa
from backend.services.epistemics import STATUS_KEY, EpistemicStatus

STAMP = "2026-08-06T00:00:00+00:00"


def run(coro):
    return asyncio.run(coro)


# ── fixtures: one 10×10 raster, four positions relative to one whole ─────────

def _rle(x0, x1, y0, y1, w=10, h=10):
    from backend.services import mask_geometry as mg

    bits = [0] * (w * h)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * w + x] = 1
    return mg.rle_encode(bits, w, h)


#: The container. Left 6×10 block; its own boundary is the frame on three sides and the column
#: x=5 on the fourth.
WHOLE = {"id": "r_whole", "label": "whole", "mask_rle": _rle(0, 6, 0, 10)}

#: The four positions the two organs must be able to tell apart. THIS TABLE IS THE LANE'S
#: PREMISE — if any two rows collapsed, α and β would be two names for one body.
#:
#:      r_deep     inside, boundary nowhere near     nested, NOT adjacent
#:      r_rim      inside, meeting the lip           nested AND adjacent   ← the composition
#:      r_beside   outside, sharing the border       adjacent, NOT nested
#:      r_far      outside, away                     neither
DEEP = {"id": "r_deep", "label": "core", "mask_rle": _rle(2, 4, 2, 8)}
RIM = {"id": "r_rim", "label": "part", "mask_rle": _rle(3, 6, 4, 8)}
BESIDE = {"id": "r_beside", "label": "next", "mask_rle": _rle(6, 9, 2, 8)}
FAR = {"id": "r_far", "label": "far", "mask_rle": _rle(7, 10, 6, 10)}


def _post(post_id="prim"):
    """The minimal locus: one region at the rim of one whole. Exactly one composition available."""
    return {"_id": post_id, "region_annotations": [dict(RIM), dict(WHOLE)]}


def _lattice_post(post_id="plat"):
    """All four positions on one post, so an agent's BLINDNESS is measurable rather than asserted:
    standing on `r_rim`, β meets `r_beside` and α cannot report it at all."""
    return {"_id": post_id, "region_annotations": [dict(r) for r in (DEEP, RIM, WHOLE, BESIDE, FAR)]}


def _pair(post=None, region_id="r_rim"):
    """α with containment, β with boundary contact, both standing on the same region."""
    post = post or _post()
    post_id = str(post["_id"])
    alpha = sa.inhabit(agent_id="alpha", post_id=post_id, region_id=region_id,
                       organ_set=(nest.ORGAN,))
    beta = sa.inhabit(agent_id="beta", post_id=post_id, region_id=region_id,
                      organ_set=(adj.ORGAN,))
    for agent in (alpha, beta):
        sa.perceive(agent, post, now=STAMP)
    return alpha, beta, post


def _one_hypothesis(post=None):
    alpha, beta, post = _pair(post)
    hypotheses = dlg.compose(dlg.exchange(alpha, beta), now=STAMP)
    assert len(hypotheses) == 1, "fixture broken: expected exactly one composition"
    return hypotheses[0], alpha, beta, post


class FakeCollection:
    """Enough Motor to store a hypothesis, and nothing that could touch a post."""

    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return type("R", (), {"inserted_id": len(self.docs)})()


# ── 1. two bodies, two worlds — and the difference is the organs ─────────────

@pytest.mark.parametrize("region,nested,adjacent", [
    (DEEP, True, False),
    (RIM, True, True),
    (BESIDE, False, True),
    (FAR, False, False),
])
def test_containment_and_contact_are_independent_in_both_directions(region, nested, adjacent):
    """THE PREMISE OF THE WHOLE LANE, over the same four pairs.

    `r_deep` is nested and not adjacent; `r_beside` is adjacent and not nested. Neither organ is a
    coarser version of the other, and neither can be derived from the other — so two agents
    carrying one each genuinely enact two worlds. If this 2×2 ever collapsed to a diagonal, every
    "disagreement" downstream would be bookkeeping, and the run would look exactly the same.
    """
    n = nest.measure(region, WHOLE)
    a = adj.measure(region, WHOLE)
    assert n["nested"] is nested, f"{region['id']}: nestedness says {n['nested']}, {n['detail']}"
    assert a["adjacent"] is adjacent, f"{region['id']}: adjacency says {a['adjacent']}, {a['detail']}"
    assert n["basis"] == a["basis"] == "mask", \
        "both readings must be mask-basis or the 2×2 is comparing a measurement to an estimate"


def test_two_agents_at_one_locus_measure_different_fields():
    """Same post, same region, same instant — and two different worlds, both `measured`.

    Asserted on the RELATION rather than only on the organ name, because two organs emitting the
    same relation would be one world reported twice under two labels.
    """
    alpha, beta, _ = _pair()
    assert [p.organ for p in alpha.percept_field] == [nest.ORGAN]
    assert [p.organ for p in beta.percept_field] == [adj.ORGAN]

    relations = {p.reading.relation for p in alpha.percept_field}, \
                {p.reading.relation for p in beta.percept_field}
    assert relations[0] == {nest.RELATION_NESTED_WITHIN}
    assert relations[1] == {adj.RELATION_MEETS}
    assert not (relations[0] & relations[1]), "the two fields report the same relation"

    for agent in (alpha, beta):
        for p in agent.percept_field:
            assert p.epistemic_status == EpistemicStatus.MEASURED.value
            assert p.reading.basis == "mask"


def test_each_agent_is_blind_exactly_where_the_other_is_not():
    """The disagreement made countable. On the lattice, β relates the locus to a region α cannot
    see at all — and that is not β being better, it is the shape of α's body. `only_beta` being
    non-empty is the first thing in this system neither agent could know alone."""
    alpha, beta, _ = _pair(_lattice_post())
    ex = dlg.exchange(alpha, beta)

    assert BESIDE["id"] in ex.only_beta, (
        "β's organ measures contact, so a region OUTSIDE the locus's container is in its world; "
        "α's cannot report it under any threshold")
    assert WHOLE["id"] in ex.both, "no shared region means no composition is even possible"
    assert ex.alpha_regions != ex.beta_regions, "the two fields cover the same regions"


def test_two_identical_bodies_are_refused_because_their_disagreement_would_be_staged():
    post = _post()
    twins = [sa.inhabit(agent_id=name, post_id=str(post["_id"]), region_id="r_rim",
                        organ_set=(nest.ORGAN,)) for name in ("alpha", "beta")]
    for agent in twins:
        sa.perceive(agent, post, now=STAMP)
    with pytest.raises(ValueError, match="identical bodies"):
        dlg.exchange(*twins)


def test_two_agents_at_different_loci_are_refused():
    """Two places would explain the difference in their fields without saying anything about their
    organs — and the transcript would be indistinguishable from the real result."""
    post = _lattice_post()
    alpha = sa.inhabit(agent_id="alpha", post_id=str(post["_id"]), region_id="r_rim",
                       organ_set=(nest.ORGAN,))
    beta = sa.inhabit(agent_id="beta", post_id=str(post["_id"]), region_id="r_deep",
                      organ_set=(adj.ORGAN,))
    for agent in (alpha, beta):
        sa.perceive(agent, post, now=STAMP)
    with pytest.raises(ValueError, match="two BODIES at one place"):
        dlg.exchange(alpha, beta)


def test_an_agent_does_not_converse_with_itself():
    alpha, _, _ = _pair()
    with pytest.raises(ValueError, match="does not converse with itself"):
        dlg.exchange(alpha, alpha)


def test_every_utterance_traces_to_a_mark_of_the_speaking_agent():
    """Nothing in the exchange is narrated. Each utterance carries the mark id its own agent's
    organ produced, and the two agents' mark sets do not overlap."""
    alpha, beta, _ = _pair()
    ex = dlg.exchange(alpha, beta)
    for agent, said in ((alpha, ex.alpha_said), (beta, ex.beta_said)):
        mine = {str(m["id"]) for m in sa.proposed_marks(agent)}
        assert said, "an agent that said nothing proves nothing"
        for u in said:
            assert u.agent_id == agent.id
            assert u.mark_id in mine, f"{u.mark_id} is not a mark {agent.id}'s organs produced"


# ── 2. hearsay, in the room where claims are traded ─────────────────────────

def test_an_agent_may_not_say_what_the_other_agent_measured():
    """THE CENTRAL REFUSAL. β heard α's claim, and repeating a heard claim in the first person is
    precisely the laundering this lane is arranged against — even though the claim is TRUE, α
    measured it, and β is standing in the same place."""
    alpha, beta, _ = _pair()
    alphas_claim = {"relation": nest.RELATION_NESTED_WITHIN, "direction": "within",
                    "other_region_id": WHOLE["id"]}

    dlg.say(alpha, alphas_claim)  # α is entitled to it
    with pytest.raises(sa.Hearsay, match="no organ reading behind"):
        dlg.say(beta, alphas_claim)


def test_an_agent_may_not_say_something_about_where_it_is_not_standing():
    """The second refusal, kept separate because it is a different mistake: not 'nothing measured
    that' but 'that is not mine to report'."""
    alpha, _, _ = _pair(_lattice_post())
    with pytest.raises(sa.Hearsay, match="report from nowhere"):
        dlg.say(alpha, {"region_id": DEEP["id"], "relation": nest.RELATION_NESTED_WITHIN})


def test_a_claim_no_organ_measured_is_refused_even_when_it_names_the_right_locus():
    alpha, _, _ = _pair()
    with pytest.raises(sa.Hearsay, match="hearsay, not admissible"):
        dlg.say(alpha, {"region_id": "r_rim", "relation": adj.RELATION_MEETS,
                        "other_region_id": WHOLE["id"]})


def test_the_exchange_reuses_the_guard_rather_than_carrying_a_copy_of_it():
    """STRUCTURAL, because a second copy of the hearsay rule is two rules that will disagree — and
    the one that disagrees quietly is the one in the room where claims are exchanged."""
    source = inspect.getsource(dlg.say)
    assert "attest(" in source, "dialogue.say must route through situated_agent.attest"
    assert dlg.attest is sa.attest


# ── 3. a joint hypothesis is `proposed`, full stop ──────────────────────────

def test_a_joint_hypothesis_stores_no_epistemic_status():
    h, _, _, _ = _one_hypothesis()
    assert STATUS_KEY not in h
    for key in dlg._FORBIDDEN_HYPOTHESIS_KEYS:
        assert key not in h


def test_a_joint_hypothesis_reads_proposed_before_any_mark_is_committed():
    h, _, _, post = _one_hypothesis()
    hydrated = dlg.hydrate_hypothesis(h, {str(post["_id"]): post})
    assert hydrated["ledger_status"] == obs_mod.LEDGER_PROPOSED
    assert hydrated["marks_live"] == "0/2"


def test_a_joint_hypothesis_still_reads_proposed_when_EVERY_mark_is_committed():
    """THE ONE-LINE FAILURE THIS LANE EXISTS TO PREVENT, and it would read as progress.

    Both agents measured on the mask basis, both marks say `measured`, a curator has committed
    both. An observation citing either would now read `measured` and be right to. The COMPOSITION
    does not, because it says something neither mark says — and two agents concurring is two
    readings, not evidence. Only the mark count changes.
    """
    h, alpha, beta, post = _one_hypothesis()
    marks = [*sa.proposed_marks(alpha), *sa.proposed_marks(beta)]
    assert {m[STATUS_KEY] for m in marks} == {EpistemicStatus.MEASURED.value}, \
        "fixture broken: with interpretive marks this test would pass for the wrong reason"

    committed = sa.overlay_posts({str(post["_id"]): post}, marks)
    hydrated = dlg.hydrate_hypothesis(h, committed)

    assert hydrated["marks_live"] == "2/2"
    assert hydrated["ledger_status"] == obs_mod.LEDGER_PROPOSED
    assert {c["epistemic"] for c in hydrated["rests_on"]} == {EpistemicStatus.MEASURED.value}, \
        "the INPUTS must read measured — otherwise the composition staying proposed proves nothing"


def test_hydration_has_no_branch_that_could_make_a_hypothesis_measured():
    """Read off the source, not the behaviour, because a test over inputs can only cover the cases
    it imagined and this says there is no case to imagine.

    Two things are asserted about the module's own code: `ledger_status` is bound to the constant
    unconditionally, and the word `measured` appears nowhere in the function body. The second is
    the one that would catch a future edit — the way this fails is somebody adding
    `if live == total` and a plausible sentence about why that counts.
    """
    body = inspect.getsource(dlg.hydrate_hypothesis).split('"""')[2]

    assert EpistemicStatus.MEASURED.value not in body, \
        "hydrate_hypothesis names `measured` in its body — there must be no path to it"

    ledger_lines = [ln.strip() for ln in body.splitlines() if '"ledger_status"' in ln]
    assert ledger_lines == ['"ledger_status": obs_mod.LEDGER_PROPOSED,'], \
        f"ledger_status is not an unconditional constant: {ledger_lines}"

    # The one conditional the function is allowed: counting which cited marks a curator has
    # committed. It reads `rests_on`, never the status the composition reports.
    assert [ln.strip() for ln in body.splitlines() if ln.strip().startswith(("if ", "elif "))] == \
        ["if mark is not None:"]


def test_a_hypothesis_only_one_agent_stands_behind_is_refused():
    h, _, _, _ = _one_hypothesis()
    lone = {**h, "agent_ids": ["alpha"], "rests_on": h["rests_on"][:1]}
    with pytest.raises(dlg.NotJoint, match="single view with two names"):
        dlg.assert_valid_hypothesis(lone)


def test_a_hypothesis_carrying_a_status_is_refused_on_the_way_in():
    h, _, _, _ = _one_hypothesis()
    with pytest.raises(dlg.NotJoint, match="agreement is not grounding"):
        dlg.assert_valid_hypothesis({**h, STATUS_KEY: EpistemicStatus.MEASURED.value})


def test_a_contribution_with_no_mark_cites_no_measurement():
    h, _, _, _ = _one_hypothesis()
    stripped = {**h, "rests_on": [{**h["rests_on"][0], "mark_id": ""}, h["rests_on"][1]]}
    with pytest.raises(dlg.NotJoint, match="hearsay"):
        dlg.assert_valid_hypothesis(stripped)


def test_a_hypothesis_whose_marks_come_from_other_agents_is_refused():
    h, _, _, _ = _one_hypothesis()
    forged = {**h, "rests_on": [{**h["rests_on"][0], "agent_id": "gamma"}, h["rests_on"][1]]}
    with pytest.raises(dlg.NotJoint, match="agents behind its marks differ"):
        dlg.assert_valid_hypothesis(forged)


def test_one_agent_carrying_both_organs_composes_nothing():
    """A perfectly legal body — and not a dialogue. It would produce both halves of the claim from
    one place, which is a single view, and posting it as JOINT would be the system agreeing with
    itself and recording the agreement."""
    post = _post()
    solo = sa.inhabit(agent_id="solo", post_id=str(post["_id"]), region_id="r_rim",
                      organ_set=(nest.ORGAN, adj.ORGAN))
    sa.perceive(solo, post, now=STAMP)
    partner = sa.inhabit(agent_id="partner", post_id=str(post["_id"]), region_id="r_rim",
                         organ_set=(adj.ORGAN,))
    sa.perceive(partner, post, now=STAMP)

    ex = dlg.Exchange(locus=solo.locus.as_dict(), alpha_id=solo.id, beta_id=solo.id,
                      alpha_said=dlg.speak(solo), beta_said=[])
    assert dlg.compose(ex, now=STAMP) == []


def test_the_hypothesis_cites_both_marks_both_organs_and_the_shared_locus():
    h, alpha, beta, post = _one_hypothesis()
    assert h["claim"] == dlg.CLAIM_AT_THE_RIM
    assert h["node_id"] == obs_mod.node_id_for(str(post["_id"]), "r_rim") == alpha.locus.node_id
    assert sorted(h["agent_ids"]) == ["alpha", "beta"]
    assert {c["organ"] for c in h["rests_on"]} == {nest.ORGAN, adj.ORGAN}
    assert {c["mark_id"] for c in h["rests_on"]} == \
        {sa.proposed_marks(alpha)[0]["id"], sa.proposed_marks(beta)[0]["id"]}
    assert h["source"] == obs_mod.AGENT_PROPOSED_SOURCE


# ── 4. what an agent privately holds — and the departure from the card ──────

def test_a_held_joint_hypothesis_is_interpretive_not_measured():
    """THE DOCUMENTED DEPARTURE, pinned so it cannot be quietly undone.

    The card and the situatedness finding say an agent may hold a joint hypothesis as `measured`
    privately, on the private-vs-ledger decision. That decision entitles an agent to believe what
    ITS OWN ORGANS measured without waiting for a curator; it does not entitle it to promote what
    another agent told it. Half of this claim arrived by testimony, and an agent holding it as
    `measured` would be hearsay with one extra step — the step that makes it invisible.
    """
    h, alpha, _, _ = _one_hypothesis()
    entry = dlg.hold(alpha, h, now=STAMP)
    assert entry[STATUS_KEY] == EpistemicStatus.INTERPRETIVE.value
    assert entry[STATUS_KEY] != EpistemicStatus.MEASURED.value
    assert entry in alpha.memory


def test_a_held_hypothesis_shows_which_half_the_agent_is_entitled_to():
    """`contributed` vs `received` per mark, so the testimony is never anonymous inside the belief.
    Each agent contributed exactly one half and received exactly one — a symmetry that only holds
    because each carries a different organ."""
    h, alpha, beta, _ = _one_hypothesis()
    for agent in (alpha, beta):
        entry = dlg.hold(agent, h, now=STAMP)
        assert entry["contributed"] == 1 and entry["received"] == 1
        mine = {str(m["id"]) for m in sa.proposed_marks(agent)}
        for rest in entry["rests_on"]:
            expected = dlg.CONTRIBUTED if rest["mark_id"] in mine else dlg.RECEIVED
            assert rest["standing"] == expected


def test_the_private_record_never_upgrades_what_the_organs_said():
    """The episodic memory of a PERCEPTION may read `measured` (the private-vs-ledger decision);
    the memory of a COMPOSITION may not. Both live in the same list, so the distinction has to be
    visible per entry rather than per agent."""
    h, alpha, _, _ = _one_hypothesis()
    perceptions = sa.remember(alpha, now=STAMP)
    held = dlg.hold(alpha, h, now=STAMP)

    assert len(alpha.memory) == len(perceptions) + 1, "both kinds must share one memory"
    assert {e[STATUS_KEY] for e in perceptions} == {EpistemicStatus.MEASURED.value}
    assert held[STATUS_KEY] == EpistemicStatus.INTERPRETIVE.value

    # And the distinction is legible per entry rather than by position: only the composition
    # carries a hypothesis id, only the perceptions carry a percept id.
    assert all("hypothesis_id" not in e for e in perceptions)
    assert "percept_id" not in held


# ── 5. two channels: one ephemeral, one durable, and neither touches a post ──

def test_the_exchange_has_no_way_to_be_persisted():
    """Ephemeral is asserted, not documented. There is no writer for an `Exchange` and no utterance
    ever reaches the collection — the durable channel takes compositions only."""
    writers = [name for name, fn in vars(dlg).items()
               if callable(fn) and name.startswith("write_")]
    assert writers == ["write_hypothesis"], f"unexpected write path(s): {writers}"
    assert not hasattr(dlg.Exchange, "save") and not hasattr(dlg.Utterance, "save")


def test_persisting_writes_the_hypothesis_and_nothing_else():
    post = _post()
    collection = FakeCollection()
    transcript = run(dlg.run_dialogue(post=post, region_id="r_rim", persist=True,
                                      collection=collection, now=STAMP))
    assert len(collection.docs) == 1
    stored = collection.docs[0]
    assert stored["hypothesis_id"] == transcript["persisted"]["hypotheses"][0]
    assert STATUS_KEY not in stored
    assert "visual_marks" not in post and "percepts" not in post


def test_a_dry_run_validates_every_hypothesis_it_did_not_store():
    """`persist=False` must prove the same contract a stored run would, or a dry run is a rehearsal
    of a different play."""
    collection = FakeCollection()
    transcript = run(dlg.run_dialogue(post=_post(), region_id="r_rim", persist=False,
                                      collection=collection, now=STAMP))
    assert transcript["hypotheses"] and collection.docs == []
    assert transcript["persisted"]["hypotheses"] == []
    for h in transcript["hypotheses"]:
        dlg.assert_valid_hypothesis(h)


def test_the_run_leaves_the_post_byte_identical_and_commits_no_mark():
    """Suggestions-only, checked rather than claimed. The marks come back in the transcript so a
    curator can see what a commit WOULD mean; performing it is not this function's to do."""
    post = _post()
    before = repr(post)
    transcript = run(dlg.run_dialogue(post=post, region_id="r_rim", now=STAMP))

    assert repr(post) == before
    assert transcript["posts_unchanged"] is True
    assert len(transcript["proposed_marks"]) == 2
    assert not (post.get("visual_marks") or [])


def test_the_run_prints_both_readings_and_they_differ_only_in_the_mark_count():
    """The overlay is shown even though it changes nothing about the status — BECAUSE it changes
    nothing. Printing only `as_stored` would leave the reader to take the claim on faith."""
    transcript = run(dlg.run_dialogue(post=_post(), region_id="r_rim", now=STAMP))
    for pair in transcript["hydrated"]:
        assert pair["as_stored"]["marks_live"] == "0/2"
        assert pair["with_proposed_marks"]["marks_live"] == "2/2"
        assert pair["as_stored"]["ledger_status"] == \
            pair["with_proposed_marks"]["ledger_status"] == obs_mod.LEDGER_PROPOSED


def test_the_run_records_two_different_fields_before_it_composes_anything():
    """The disagreement must be readable in the transcript WITHOUT trusting the composition step
    that follows it — otherwise a broken `compose` and a staged run look the same."""
    transcript = run(dlg.run_dialogue(post=_lattice_post(), region_id="r_rim", now=STAMP))
    fields = transcript["fields"]
    assert set(fields) == {"alpha", "beta"}
    organ_of = {aid: {row["organ"] for row in rows} for aid, rows in fields.items()}
    assert organ_of["alpha"] == {nest.ORGAN} and organ_of["beta"] == {adj.ORGAN}
    assert fields["alpha"] != fields["beta"]


# ── 6. the substrate the second body rests on ───────────────────────────────

_SCANNED = [Path(__file__).resolve().parents[1] / "services" / "agents",
            Path(__file__).resolve().parents[1] / "services" / "adjacency_organ.py"]

_NARRATORS = re.compile(
    r"\b(llm_service|editor_llm_service|semantic_provider|groq|openai|anthropic|"
    r"story_block_service|vision_service|argument_planner)\b")

#: A pure organ reaches nothing outside itself. `database` would let it read a post it was not
#: handed; `requests`/`httpx` would let it ask something; `torch` would make it residency-managed
#: and this lane could not invoke it at all.
_IMPURE = re.compile(r"\b(database|requests|httpx|aiohttp|torch|transformers|motor)\b")


def test_the_dialogue_and_its_organ_cannot_ask_a_language_model():
    """The honesty floor structurally, extended to cover the new organ as well as the package. The
    dialogue is grounded exchange, not generated chat, and the guard is import-time so no runtime
    discipline is required to keep it."""
    scanned = 0
    for root in _SCANNED:
        paths = sorted(root.rglob("*.py")) if root.is_dir() else [root]
        for path in paths:
            scanned += 1
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                if not (line.startswith("import ") or line.startswith("from ")):
                    continue
                hit = _NARRATORS.search(line)
                assert hit is None, (
                    f"{path.name}:{lineno} imports {hit.group(0)!r} — two agents that can reach a "
                    f"thinker can author an agreement neither measured, which is the exact "
                    f"confabulation a dialogue makes persuasive")
    assert scanned >= 4, "the scan found nothing — a guard that scans nothing passes vacuously"


def test_the_adjacency_organ_is_pure():
    """Geometry in, measurement out. It was built precisely because every registry organ loads
    weights and is residency-managed; an impure second body would resolve RESIDENT and this lane
    would have no dialogue to run."""
    source = Path(adj.__file__).read_text()
    for lineno, line in enumerate(source.splitlines(), 1):
        if not (line.startswith("import ") or line.startswith("from ")):
            continue
        hit = _IMPURE.search(line)
        assert hit is None, f"adjacency_organ.py:{lineno} imports {hit.group(0)!r} — not pure"


def test_the_adjacency_organ_is_classified_and_inherits_the_same_documented_gap():
    """The hole the situated-agent lane found, not reopened — and the half of it that stays open,
    named here rather than left for the next lane to rediscover.

    Classified, so `guard()` no longer refuses the organ's own mask marks (an unclassified producer
    falls to `uncertain`, which is what refused `nestedness_organ` before WAVE3). Still gapped, for
    exactly the reason `test_the_epistemic_guard_cannot_express_this_producer_and_that_is_the
    _finding` gives: `permitted_statuses` is one kind per producer plus `uncertain`, and this organ
    emits two kinds derived per measurement. Its legitimate box weakening is refused.

    Widening `permitted_statuses` would change behaviour for every measured-ceiling producer in the
    system, so this lane reports the gap and does not widen it from here. When someone does, this
    test fails — the correct way for a documented limitation to expire.
    """
    assert adj.ORGAN in epistemics.classified_producers()
    assert epistemics.default_status_for(adj.ORGAN) is EpistemicStatus.MEASURED

    def guarded(region):
        mark = adj.grounding_mark(adj.measure(region, WHOLE), post_id="prim", now=STAMP)
        return epistemics.guard([{"producer": adj.ORGAN, "type": mark["type"],
                                  STATUS_KEY: mark[STATUS_KEY]}])

    guarded(RIM)                                       # the mask ceiling: accepted
    with pytest.raises(epistemics.EpistemicViolation, match="may only weaken"):
        guarded({"id": "b_in", "box": {"x": 0.10, "y": 0.10, "w": 0.10, "h": 0.10}})

    # and the ceiling is a CEILING — the organ may never promote its own output
    with pytest.raises(epistemics.EpistemicViolation):
        epistemics.declare(adj.ORGAN, EpistemicStatus.VISIBLE)


def test_a_box_basis_contact_reading_is_an_estimate_and_says_so():
    """WAVE2.5, on the organ born after it. Boundary contact off bounding boxes is a WORSE estimate
    than containment off them — a box's edge is not the shape's edge — so there is no version of
    this reading that could be `measured`."""
    boxed = adj.measure(
        {"id": "b_in", "box": {"x": 0.10, "y": 0.10, "w": 0.10, "h": 0.10}},
        {"id": "b_out", "box": {"x": 0.10, "y": 0.05, "w": 0.40, "h": 0.40}})
    assert boxed["basis"] == "box"
    assert adj.epistemic_for("box") == EpistemicStatus.INTERPRETIVE.value
    assert adj.is_admissible(boxed) is False
    mark = adj.grounding_mark(boxed, post_id="prim", now=STAMP)
    assert mark[STATUS_KEY] == EpistemicStatus.INTERPRETIVE.value


def test_the_two_bases_are_decided_in_one_place_for_both_organs():
    """One table, not two copies. The point of the ruling is that a single place says what each
    basis supports; a second organ with its own copy would be the drift it exists to end."""
    assert adj.BASIS_EPISTEMIC is nest.BASIS_EPISTEMIC
    assert adj.ADMISSIBLE_BASIS == nest.ADMISSIBLE_BASIS == "mask"


def test_an_unmeasurable_pair_is_refused_rather_than_reported_as_not_touching():
    """A zero contact fraction means "measured, and these do not meet". A refusal means "not
    measured". Collapsing the two would be a claim about the picture made from an absence of
    evidence."""
    tiny = {"id": "t", "mask_rle": _rle(0, 2, 0, 2)}
    with pytest.raises(adj.AdjacencyRefusal, match="too short"):
        adj.measure(tiny, WHOLE)
    assert adj.measure(FAR, WHOLE)["contact_fraction"] == 0.0


def test_a_region_does_not_meet_its_own_edge():
    with pytest.raises(adj.AdjacencyRefusal, match="against itself"):
        adj.measure(dict(RIM), dict(RIM))


def test_masks_on_different_rasters_fall_back_rather_than_being_resampled():
    """For a BOUNDARY organ, resampling would invent the very pixels it then counts — that is not a
    coarser measurement, it is a measurement of the resampler. The box path is the honest falloff,
    and it says `interpretive`."""
    other_raster = {"id": "r_small", "mask_rle": _rle(0, 3, 0, 3, w=5, h=5),
                    "box": {"x": 0.0, "y": 0.0, "w": 0.6, "h": 0.6}}
    whole = {**WHOLE, "box": {"x": 0.0, "y": 0.0, "w": 0.6, "h": 1.0}}
    result = adj.measure(other_raster, whole)
    assert result["basis"] == "box"


def test_every_invocable_organ_has_an_invocation():
    """The two tables in `organs.py` must cover each other. A name in `PURE_PYTHON_ORGANS` with no
    reader would raise at invoke time — which this asserts is unreachable rather than trusting the
    comment that says so."""
    post = _lattice_post()
    for name in organs.PURE_PYTHON_ORGANS:
        readings = organs.invoke(name, post=post, region_id="r_rim", now=STAMP)
        assert readings, f"{name} is invocable but measured nothing at a locus that affords both"


def test_an_agent_may_not_be_built_from_an_organ_that_does_not_exist():
    with pytest.raises(organs.OrganRefusal):
        sa.inhabit(agent_id="ghost", post_id="prim", region_id="r_rim",
                   organ_set=("proximity_organ",))
