"""WAVE3 — the first situated agent: the claims, and the four places they could break.

An agent is the richest place in this system for confabulation to hide, because "I, standing here,
experienced X" is a very persuasive sentence. So these tests are not coverage of a feature; they
are the guard on four claims that would each still LOOK correct from the outside if they failed:

  1. PARTIALITY — the agent knows only what its organs measured FROM ITS LOCUS. A percept field
     that quietly widened to the whole image would look identical in every dump, and every claim
     it made would be a claim from nowhere wearing a first-person pronoun. §1.
  2. HEARSAY — a claim with no organ behind it is refused, and refused separately when it is about
     somewhere the agent is not standing. §2.
  3. THE TWO TIERS — the private record carries what the ORGAN said and the shared row reads
     `proposed`, from the SAME reading. Two flattering failures live here, each one line and each
     invisible: writing `measured` onto the ledger row, and writing `measured` into memory for a
     box-basis reading. The lane shipped the second one once — see
     `test_a_box_reading_may_not_be_recorded_as_a_measurement`. §3.
  4. NO NARRATION — the package cannot ask a language model. Asserted structurally, over the whole
     package, rather than trusted. §4.

§5 covers the substrate contracts this lane rests on and must not bend: the epistemic guard, the
percept lineage, the node id, and posts-byte-identical.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from backend.schemas.soft_fields import Percept
from backend.services import epistemics, nestedness_organ, percept_lineage
from backend.services.agents import observation as obs_mod
from backend.services.agents import organs
from backend.services.agents import situated_agent as sa
from backend.services.epistemics import STATUS_KEY, EpistemicStatus

NESTEDNESS = "nestedness_organ"
STAMP = "2026-08-05T00:00:00+00:00"


def run(coro):
    return asyncio.run(coro)


def _post(post_id="p1"):
    """A post whose god's-eye reading contains TWO nestings — and the agent may only have one.

        seg_0 (finial)  ⊂  seg_1 (spire)     ← the agent stands on seg_0; this is its world
        seg_2 (plinth)  ⊂  seg_3 (ground)    ← equally real, equally measurable, NOT its to know

    The second pair is the whole point of the fixture. `find_nested_pairs` reports both, because
    that is the reading the movement kernel needs. An agent standing on seg_0 must report one.
    """
    return {"_id": post_id, "region_annotations": [
        {"id": "seg_0", "label": "finial", "box": {"x": 0.40, "y": 0.10, "w": 0.06, "h": 0.08}},
        {"id": "seg_1", "label": "spire", "box": {"x": 0.30, "y": 0.05, "w": 0.35, "h": 0.55}},
        {"id": "seg_2", "label": "plinth", "box": {"x": 0.05, "y": 0.70, "w": 0.20, "h": 0.15}},
        {"id": "seg_3", "label": "ground", "box": {"x": 0.00, "y": 0.60, "w": 1.00, "h": 0.40}},
    ]}


def _masked_post(post_id="pm"):
    """A post where the locus and its container BOTH carry a mask on one raster.

    Needed because the box fixture above can no longer produce a `measured` reading at all: under
    the WAVE2.5 ruling a box is an estimate, so every claim off `_post()` is `interpretive`. Without
    this fixture the whole measured half of the two-tier decision would be untested — which is how
    a lane ends up proving only the case its corpus happens to have.

    A 10×10 raster: `m_outer` is the left 6×10 block, `m_inner` a 2×2 square inside it.
    """
    from backend.services import mask_geometry as mg

    def rle(x0, x1, y0, y1):
        bits = [0] * 100
        for y in range(y0, y1):
            for x in range(x0, x1):
                bits[y * 10 + x] = 1
        return mg.rle_encode(bits, 10, 10)

    return {"_id": post_id, "region_annotations": [
        {"id": "m_inner", "label": "part", "mask_rle": rle(1, 3, 1, 3)},
        {"id": "m_outer", "label": "whole", "mask_rle": rle(0, 6, 0, 10)},
    ]}


def _agent(region_id="seg_0", post=None, organ_set=(NESTEDNESS,)):
    post = post or _post()
    agent = sa.inhabit(agent_id="agent_alpha", post_id=str(post["_id"]),
                       region_id=region_id, organ_set=organ_set)
    sa.perceive(agent, post, now=STAMP)
    return agent, post


class FakeCollection:
    """Enough Motor to store an observation, and nothing that could touch a post."""

    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return type("R", (), {"inserted_id": len(self.docs)})()


# ── 1. partiality: the world is what these organs measure FROM HERE ──────────

def test_the_agent_cannot_see_a_nesting_it_is_not_standing_on():
    """THE CLAIM the whole wave rests on. The post contains two measurable nestings; an agent on
    `seg_0` gets one, and the one it does not get is not a harder measurement — it is a
    measurement about somewhere else."""
    from backend.services import nestedness_organ as organ

    post = _post()
    gods_eye = organ.find_nested_pairs(post["region_annotations"])
    pairs = {(m["inner_region_id"], m["outer_region_id"]) for m in gods_eye}
    assert ("seg_0", "seg_1") in pairs and ("seg_2", "seg_3") in pairs, \
        "fixture broken: the god's-eye sweep must find BOTH nestings for this test to mean anything"

    agent, _ = _agent("seg_0")
    seen = {(p.reading.locus_region_id, p.reading.other_region_id) for p in agent.percept_field}
    assert seen == {("seg_0", "seg_1")}
    assert all(p.reading.locus_region_id == "seg_0" for p in agent.percept_field)
    assert not any("seg_2" in pair or "seg_3" in pair for pair in seen)


def test_moving_the_locus_moves_the_world():
    """Situatedness is the pairing (locus × organ set): change either and the agent is elsewhere.
    Same post, same body, one step over — a different world, not a different view of one world."""
    on_finial, _ = _agent("seg_0")
    on_plinth, _ = _agent("seg_2")

    assert {p.reading.other_region_id for p in on_finial.percept_field} == {"seg_1"}
    assert {p.reading.other_region_id for p in on_plinth.percept_field} == {"seg_3"}


def test_a_locus_that_affords_nothing_gives_an_empty_field_not_a_refusal():
    """An empty field is a REAL ANSWER — the organs looked from here and measured nothing, which
    is a fact about the locus. `organs.invoke` raises instead when no organ looked at all, and the
    two must never collapse: one is a quiet place, the other is a blind agent."""
    post = _post()
    agent, _ = _agent("seg_3", post=post)          # the ground contains things; nothing contains it
    assert agent.percept_field == [] or all(
        p.reading.direction == "contains" for p in agent.percept_field)
    assert agent.trajectory[-1]["regions_in_reach"] == 4, \
        "the denominator must be recorded — 'measured 0' without it is not a coverage claim"


def test_an_agent_cannot_stand_where_there_is_no_region():
    agent = sa.inhabit(post_id="p1", region_id="seg_nope", organ_set=(NESTEDNESS,))
    with pytest.raises(organs.OrganRefusal, match="nothing to stand on"):
        sa.perceive(agent, _post())


def test_an_agent_cannot_perceive_a_picture_it_is_not_in():
    """The god's-eye read this module is arranged against, in its most literal form."""
    agent = sa.inhabit(post_id="p1", region_id="seg_0", organ_set=(NESTEDNESS,))
    with pytest.raises(organs.OrganRefusal, match="god's-eye"):
        sa.perceive(agent, _post("p2"))


def test_a_reading_about_another_region_is_refused_before_it_enters_the_field():
    """The locus constraint as a checked invariant rather than a property of how `invoke` happens
    to be written today. If `organs.invoke` ever widens, this fires."""
    agent = sa.inhabit(post_id="p1", region_id="seg_0", organ_set=(NESTEDNESS,))
    stray = organs.invoke(NESTEDNESS, post=_post(), region_id="seg_2", now=STAMP)
    assert stray, "fixture broken: seg_2 must produce a reading for this test to mean anything"
    with pytest.raises(sa.Hearsay, match="could have from here"):
        sa._perceptions_for(stray, organ=NESTEDNESS, locus=agent.locus, now=STAMP)


# ── 2. the body: what resolves, what refuses, and the difference between them ─

def test_an_agent_with_no_organs_is_not_an_agent():
    with pytest.raises(organs.OrganRefusal, match="no organs has no world"):
        sa.inhabit(post_id="p1", region_id="seg_0", organ_set=())


def test_an_unknown_organ_name_is_refused():
    with pytest.raises(organs.OrganRefusal, match="no organ named"):
        sa.inhabit(post_id="p1", region_id="seg_0", organ_set=("occipital_lobe",))


def test_a_resident_organ_is_a_real_organ_this_lane_will_not_pretend_to_invoke():
    """THE DISTINCTION worth having. `sam21_hiera_tiny` is a genuine organ role — it just loads
    weights, and this wave starts no models. Reporting it as UNKNOWN would make a correct organ
    name look like a typo; reporting it as invocable would be a lie with a percept field attached.
    """
    binding = organs.resolve("sam21_hiera_tiny")
    assert binding.resolution == organs.RESIDENT
    assert binding.invocable is False
    assert binding.role is not None and binding.role.name == "sam21_hiera_tiny"
    assert "residency-managed" in binding.detail
    with pytest.raises(organs.OrganRefusal, match="residency-managed"):
        sa.inhabit(post_id="p1", region_id="seg_0", organ_set=("sam21_hiera_tiny",))


def test_a_thinker_is_not_an_organ():
    """An agent perceiving through a thinker would be narrating, and the refusal says so."""
    binding = organs.resolve("dissector")
    assert binding.resolution == organs.UNKNOWN and binding.invocable is False
    assert "does not measure" in binding.detail


# ── 3. hearsay: a claim must trace to an organ ───────────────────────────────

def test_a_claim_no_organ_measured_is_refused_as_hearsay():
    agent, _ = _agent("seg_0")
    with pytest.raises(sa.Hearsay, match="hearsay, not admissible"):
        sa.attest(agent, {"relation": "nested_within", "direction": "within",
                          "other_region_id": "seg_3"})


def test_a_true_claim_about_somewhere_else_is_still_refused():
    """seg_2 ⊂ seg_3 is TRUE and the organ would measure it. It is refused anyway, because a
    first-person report about somewhere the agent is not is a report from nowhere."""
    agent, _ = _agent("seg_0")
    with pytest.raises(sa.Hearsay, match="report from nowhere"):
        sa.attest(agent, {"region_id": "seg_2", "relation": "nested_within",
                          "direction": "within", "other_region_id": "seg_3"})


def test_a_measured_claim_is_attested_and_becomes_one_proposed_observation():
    agent, _ = _agent("seg_0")
    claim = {"relation": "nested_within", "direction": "within", "other_region_id": "seg_1"}

    assert sa.attest(agent, claim).reading.other_region_id == "seg_1"
    entry = sa.observe(agent, claim, now=STAMP)
    assert entry["agent_id"] == "agent_alpha"
    assert entry["node_id"] == "vm_p1:seg_0"
    assert entry["source"] == obs_mod.AGENT_PROPOSED_SOURCE


def test_hearsay_produces_no_observation_at_all():
    """Refused, not weakened. A hearsay claim that came back tagged `uncertain` would be a
    supported way to publish one."""
    agent, _ = _agent("seg_0")
    with pytest.raises(sa.Hearsay):
        sa.observe(agent, {"other_region_id": "seg_3"}, now=STAMP)


# ── 4. the two tiers: measured privately, proposed publicly ──────────────────

def test_the_private_record_reads_what_the_organ_measured_not_what_the_agent_wants():
    """The yes-half of the decision, and the WAVE2.5 correction to it in one test.

    An agent lives on what its organs measured — but it does not get to decide what its eyes said.
    On a mask basis the record reads `measured`; on a box basis it reads `interpretive`, because a
    box is an estimate of an extent and a mask is a measurement of one.
    """
    masked, _ = _agent("m_inner", post=_masked_post())
    measured = sa.remember(masked, now=STAMP)
    assert measured and all(e[STATUS_KEY] == EpistemicStatus.MEASURED.value for e in measured)
    assert measured[0]["basis"] == "mask" and measured[0]["admissible"] is True

    boxed, _ = _agent("seg_0")
    estimated = sa.remember(boxed, now=STAMP)
    assert estimated and all(
        e[STATUS_KEY] == EpistemicStatus.INTERPRETIVE.value for e in estimated)
    assert estimated[0]["basis"] == "box" and estimated[0]["admissible"] is False

    assert boxed.memory == estimated and masked.memory == measured


def test_a_box_reading_may_not_be_recorded_as_a_measurement():
    """THE PATHOLOGY THIS LANE SHIPPED ONCE, kept as a regression.

    The first version of `remember` wrote `EpistemicStatus.MEASURED` itself, and the first real run
    recorded *'golden finial nested within Sky'* at index 0.995 as a measurement. The finial is in
    FRONT of the sky; a bounding box in a 2D projection cannot tell `inside` from `in front of`,
    and the sky's box contains everything under it (WAVE2.5).

    An agent is the worst place in the system for that error, because the sentence arrives in the
    first person. So the status is COPIED off the mark and `_verify_marks` refuses any mark that
    outruns its own geometry.
    """
    agent, _ = _agent("seg_0")
    perception = agent.percept_field[0]
    assert perception.reading.basis == "box"
    assert perception.epistemic_status == EpistemicStatus.INTERPRETIVE.value
    assert perception.reading.admissible is False

    forged = sa.Perception(
        organ=perception.organ, percept=perception.percept, grounds=perception.grounds,
        reading=organs.OrganReading(
            **{**vars(perception.reading),
               "mark": {**perception.mark, STATUS_KEY: EpistemicStatus.MEASURED.value}}))
    with pytest.raises(sa.MarkMisstated, match="outruns its own geometry|supports"):
        sa._verify_marks([forged])


def test_the_shared_row_stores_no_status_and_reads_proposed():
    """The no-half, and it is STRUCTURAL: there is no field on the row that could say `measured`,
    so the ledger's answer cannot drift from the ledger's evidence."""
    agent, post = _agent("seg_0")
    observations = sa.report(agent, now=STAMP)
    assert observations

    for entry in observations:
        assert STATUS_KEY not in entry
        hydrated = obs_mod.hydrate_observation(entry, {"p1": post})
        assert hydrated["ledger_status"] == obs_mod.LEDGER_PROPOSED
        assert hydrated["live"] is False and hydrated["epistemic"] is None


def test_the_same_reading_reads_measured_privately_and_proposed_publicly():
    """THE DECISION, in one assertion. Both come from one organ reading, so the difference between
    them is not a difference in evidence — it is the human act nobody has performed.

    On the MASK fixture, because this is the claim about the measured tier and the box corpus
    cannot make it any more."""
    post = _masked_post()
    agent, _ = _agent("m_inner", post=post)
    private = sa.remember(agent, now=STAMP)[0]
    public = obs_mod.hydrate_observation(sa.report(agent, now=STAMP)[0], {"pm": post})

    assert private["mark_id"] == public["mark_id"]                 # the same evidence
    assert private[STATUS_KEY] == EpistemicStatus.MEASURED.value   # …read one way privately
    assert public["ledger_status"] == obs_mod.LEDGER_PROPOSED      # …and another publicly


def test_committing_the_mark_is_what_moves_the_ledger():
    """The gap between the two readings is exactly one curator's act, and nothing else closes it.

    And the tier the commit reveals is the one the GEOMETRY earned, not the strongest available:
    committing a box-basis mark exposes `interpretive`, never `measured`. A curator's acceptance
    makes a claim durable; it cannot make an estimate into a measurement.
    """
    for post, post_id, region, expected in (
            (_masked_post(), "pm", "m_inner", EpistemicStatus.MEASURED.value),
            (_post(), "p1", "seg_0", EpistemicStatus.INTERPRETIVE.value)):
        agent, _ = _agent(region, post=post)
        entry = sa.report(agent, now=STAMP)[0]
        marks = sa.proposed_marks(agent)

        as_stored = obs_mod.hydrate_observation(entry, {post_id: post})
        as_committed = obs_mod.hydrate_observation(
            entry, sa.overlay_posts({post_id: post}, marks))

        assert as_stored["ledger_status"] == obs_mod.LEDGER_PROPOSED
        assert as_committed["ledger_status"] == expected
        assert as_committed["live"] is True


def test_an_observation_may_not_carry_a_status_of_its_own():
    """The one-line flattering failure, refused at the door."""
    agent, _ = _agent("seg_0")
    entry = dict(sa.report(agent, now=STAMP)[0])
    entry[STATUS_KEY] = EpistemicStatus.MEASURED.value

    with pytest.raises(obs_mod.ObservationRefused, match="comes from the mark it cites"):
        obs_mod.assert_valid_observation(entry)


def test_an_observation_with_no_mark_is_hearsay_with_a_timestamp():
    agent, _ = _agent("seg_0")
    entry = {**sa.report(agent, now=STAMP)[0], "mark_id": ""}
    with pytest.raises(obs_mod.ObservationRefused, match="hearsay with a timestamp"):
        obs_mod.assert_valid_observation(entry)


# ── 5. the substrate contracts this lane rests on ────────────────────────────

def test_every_mark_carries_exactly_what_its_basis_supports():
    """The check this lane runs before publishing anything: per MEASUREMENT, not per producer."""
    for post, region in ((_masked_post(), "m_inner"), (_post(), "seg_0")):
        agent, _ = _agent(region, post=post)
        sa._verify_marks(agent.percept_field)                 # raises if a mark outruns its basis
        for perception in agent.percept_field:
            assert perception.epistemic_status == \
                nestedness_organ.epistemic_for(perception.reading.basis)


def test_the_epistemic_guard_cannot_express_this_producer_and_that_is_the_finding():
    """THE HOLE THIS LANE FOUND, and the shape WAVE2.5 gave it.

    `nestedness_organ` was in NEITHER classification table, so `guard()` refused its own output —
    a producer nobody classified may claim only `uncertain`, and Lane M never routed a mark through
    the guard, so nothing surfaced it. This lane classifies it (`_DEFAULTS`), which states the
    organ's CEILING and fixes the mask path.

    It cannot fix the whole of it, and this test pins WHY rather than hiding it.
    `permitted_statuses` returns `{classification, uncertain}` — one kind per producer, plus the
    right to be unsure. WAVE2.5 made this organ emit TWO kinds, derived per measurement, and no
    single entry admits both. `interpretive` is a weakening of `measured` and the module's own
    principle would allow it; the implementation allows only `uncertain`, because until this ruling
    nothing weakened along another axis.

    Widening `permitted_statuses` changes behaviour for every measured-ceiling producer in the
    system, so it is reported rather than done from here. When it is widened, this test fails —
    which is the correct way for a documented limitation to expire.
    """
    assert epistemics.default_status_for(NESTEDNESS) is EpistemicStatus.MEASURED

    def guarded(basis):
        mark = nestedness_organ.grounding_mark(
            {"inner_region_id": "a", "outer_region_id": "b", "basis": basis}, post_id="p")
        return epistemics.guard([{"producer": NESTEDNESS, "type": mark["type"],
                                  STATUS_KEY: mark[STATUS_KEY]}])

    guarded("mask")                                    # the ceiling path: accepted
    with pytest.raises(epistemics.EpistemicViolation, match="may only weaken"):
        guarded("box")                                 # the legitimate weakening: refused

    # and the ceiling is still a CEILING — the organ may never promote its own output
    with pytest.raises(epistemics.EpistemicViolation):
        epistemics.declare(NESTEDNESS, EpistemicStatus.VISIBLE)


def test_an_agent_percept_is_neither_an_expression_percept_nor_a_draft():
    """SF-001B's census measured `post.percepts` clean — 12 rows, all expression percepts, zero
    draft-shaped — and SF-002 typed one object on the strength of it. An agent's percept must not
    be mistakable for either lineage, or a field that census proved clean acquires a third
    occupant that reads like the first."""
    agent, _ = _agent("seg_0")
    for perception in agent.percept_field:
        row = perception.percept.model_dump(mode="json")
        assert percept_lineage.classify_percept_row(row) == percept_lineage.UNKNOWN
        assert not percept_lineage.is_expression_percept(row)
        assert not percept_lineage.is_draft_shaped(row)
        assert row["kind"] == sa.AGENT_PERCEPT_KIND and row["id"].startswith("apc_")


def test_an_agent_percept_round_trips_through_the_soft_field_schema():
    """SF-002's success criterion, applied to what this lane mints: a round trip drops nothing and
    adds nothing. `actor` is the one to watch — it is deliberately never set, and a schema that
    filled it in would have an agent claiming a human authorship it does not have."""
    agent, _ = _agent("seg_0")
    for perception in agent.percept_field:
        first = perception.percept.model_dump(mode="json")
        again = Percept.model_validate(first).model_dump(mode="json")
        assert again == first
        assert "actor" not in first
        assert "created_at" not in first or first["created_at"]     # never an explicit null

        for ground in perception.grounds:
            g = ground.model_dump(mode="json")
            assert g["ground_type"] == "region" and g["detector"] == NESTEDNESS
            assert g["actor"] == "auto" and g["region_id"] in ("seg_0", "seg_1")


def test_a_ground_that_does_not_declare_its_type_stops_being_a_region_ground():
    """THE TRAP THIS LANE FELL INTO, kept as a test rather than a comment.

    `SoftFieldModel` emits only what was SET, deliberately — "the schema will not quietly speak on
    its behalf". So a `RegionGround` constructed without passing `ground_type` dumps with no
    discriminator, and the union re-validates it as an `UndeclaredGround`: the object survives every
    round trip intact while silently ceasing to be a region ground, and `resolveGround` would treat
    it as an unknown type rather than following its `region_id`.

    This is Lane G's declare-and-set rule in SF-002's clothing, and it is caught here rather than
    trusted because the failure is invisible — nothing is dropped, nothing raises, and the dict
    still has every key a reader would look for.
    """
    from pydantic import TypeAdapter

    from backend.schemas.soft_fields import Ground, RegionGround, UndeclaredGround

    unset = RegionGround(id="agnd_x", actor="auto", region_id="seg_0").model_dump(mode="json")
    assert "ground_type" not in unset
    assert isinstance(TypeAdapter(Ground).validate_python(unset), UndeclaredGround)

    # what this lane actually mints
    agent, _ = _agent("seg_0")
    for ground in agent.percept_field[0].grounds:
        dumped = ground.model_dump(mode="json")
        assert dumped["ground_type"] == "region"
        assert isinstance(TypeAdapter(Ground).validate_python(dumped), RegionGround)


def test_the_node_id_is_the_one_the_movement_kernel_uses():
    """Two names for one place would split every retrieval that touched it, and nothing downstream
    would report the split. Asserted against the kernel's own construction rather than restated."""
    from backend.services import movement_kernel as mk
    assert obs_mod.node_id_for("p1", "seg_0") == mk._node_id("p1", "seg_0")


def test_a_full_run_leaves_every_post_byte_identical():
    """Suggestions-only, checked rather than claimed."""
    post = _post()
    transcript = run(sa.run_agent(post=post, region_id="seg_0", agent_id="agent_alpha",
                                  now=STAMP))
    assert transcript["posts_unchanged"] is True
    assert transcript["proposed_marks"]
    assert "visual_marks" not in post
    assert transcript["hydrated"][0]["as_stored"]["ledger_status"] == obs_mod.LEDGER_PROPOSED
    # box geometry, so committing the mark would reveal an ESTIMATE — never `measured`
    assert transcript["hydrated"][0]["with_proposed_marks"]["ledger_status"] == \
        EpistemicStatus.INTERPRETIVE.value


def test_persisting_writes_observations_and_touches_no_post():
    post = _post()
    collection = FakeCollection()
    transcript = run(sa.run_agent(post=post, region_id="seg_0", persist=True,
                                  collection=collection, atlas_id="atlas_wave3", now=STAMP))

    assert len(collection.docs) == len(transcript["observations"]) == 1
    assert collection.docs[0]["atlas_id"] == "atlas_wave3"
    assert STATUS_KEY not in collection.docs[0]
    assert transcript["posts_unchanged"] is True and "visual_marks" not in post


# ── 6. no narration: asserted over the package, not promised in a docstring ──

_PACKAGE = Path(__file__).resolve().parents[1] / "services" / "agents"

#: Anything that could put a sentence in an agent's mouth. Import-level, because a module that
#: cannot import a client cannot call one — no runtime discipline required.
_NARRATORS = re.compile(
    r"\b(llm_service|editor_llm_service|semantic_provider|groq|openai|anthropic|"
    r"story_block_service|vision_service|argument_planner)\b")


def test_the_agents_package_cannot_ask_a_language_model():
    """THE HONESTY FLOOR, structurally. "A claim without an organ behind it is hearsay" is enforced
    by `attest` at runtime and by this at import time: there is nothing in the package that could
    generate a claim in the first place.

    A wider net than needed on purpose — `groq`, `openai` and the thinker services are all named,
    so the guard catches a new client as readily as an existing one.
    """
    scanned = 0
    for path in sorted(_PACKAGE.rglob("*.py")):
        scanned += 1
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if not (line.startswith("import ") or line.startswith("from ")):
                continue
            hit = _NARRATORS.search(line)
            assert hit is None, (
                f"{path.name}:{lineno} imports {hit.group(0)!r} — a situated agent may perceive "
                f"only what its organs MEASURED. A module that can reach a thinker can author a "
                f"first-person sentence nobody measured, which is the confabulation this whole "
                f"wave is arranged against.")
    assert scanned >= 3, "the scan found nothing — a guard that scans nothing passes vacuously"


def test_the_only_status_the_package_writes_is_the_organs_own():
    """`measured` appears in exactly one place in the agent's own data path — the episodic record,
    copied off the mark. Anywhere else would be this lane deciding what kind of knowing something
    is, which is the organ's job and nobody else's."""
    agent, _ = _agent("seg_0")
    written = sa.remember(agent, now=STAMP)
    for entry, perception in zip(written, agent.percept_field):
        assert entry[STATUS_KEY] == perception.mark[STATUS_KEY]
