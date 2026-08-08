"""
HARNESS-001B2 §3 & §4 — the ephemeral projection, and the mission that perceives from it.

The bridge from global preparation to local situatedness. What is checked here is that the world
SURVIVES the crossing: the Region owning `mask_rle` travels with every `mask_ref`, the geometry
becomes something an organ can measure from, and none of it becomes committed on the way.
"""
from __future__ import annotations

import pytest

from backend.services import mask_geometry as mg
from backend.services import nestedness_organ as nest
from backend.services import sam3_concept_service as sam3
from backend.services import suggestion_service as ss
from backend.services.agents import situated_agent as sa
from backend.services.inquiry_engine import adapters as ad
from backend.services.inquiry_engine.goals import KIND_MISSION, KIND_PREPARATION, AgentMission
from backend.services.inquiry_engine.handoff import choose_locus, evidence_provenance
from backend.services.inquiry_engine.world import (GEOMETRY_NAMING, PostDelta, PreparedWorldDelta,
                                                   ProjectionRefused, ProposedRegion,
                                                   locus_available, project_post, project_world)
from backend.services.movement_kernel import posts_fingerprint

N = 16
STAMP = "2026-08-08T00:00:00+00:00"
INNER = (5, 11, 6, 12)
OUTER = (2, 14, 2, 15)


def _rle(x0, x1, y0, y1):
    bits = [0] * (N * N)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * N + x] = 1
    return mg.rle_encode(bits, N, N)


def _concept_result(concept="fold"):
    return {"concept": concept, "device": "cpu", "model": "sam3-fixture", "latency_ms": 9.0,
            "truncated": False,
            "instances": [{"mask_rle": _rle(*INNER), "confidence": 0.91, "index": 0},
                          {"mask_rle": _rle(*OUTER), "confidence": 0.84, "index": 1}]}


@pytest.fixture()
def delta():
    """A delta of the shape production makes, built through the production converters."""
    result = _concept_result()
    regions = sam3.instances_to_regions(result)
    suggestions = ss.suggestions_from_concept_segments([result], run_id="run_b2", step_id="pt_fold")
    return PreparedWorldDelta(
        task_id="pt_fold", evidence_goal_id="eg_fold", run_id="run_b2", step_id="pt_fold",
        per_post=(PostDelta(post_id="post_renaissance",
                            proposed_regions=tuple(ProposedRegion.of(r) for r in regions),
                            suggestions=tuple(suggestions)),))


@pytest.fixture()
def posts():
    return {"post_renaissance": {"_id": "post_renaissance", "photo_url": "u",
                                 "region_annotations": []},
            "post_buddha": {"_id": "post_buddha", "photo_url": "u2", "region_annotations": []}}


# ── 1. the projection never touches the source ───────────────────────────────

def test_the_source_post_is_never_mutated_by_a_projection(delta, posts):
    before = posts_fingerprint(posts)
    project_world(posts, delta)
    assert posts_fingerprint(posts) == before
    assert posts["post_renaissance"]["region_annotations"] == []


def test_the_projection_is_a_deep_copy_and_editing_it_cannot_reach_the_source(delta, posts):
    projected = project_post(posts["post_renaissance"], delta, post_id="post_renaissance")
    projected["region_annotations"][0]["mask_rle"] = {"tampered": True}
    assert posts["post_renaissance"]["region_annotations"] == []


# ── 2. the Region travels with its mask ──────────────────────────────────────

def test_the_proposed_regions_enter_the_projected_post_with_their_masks(delta, posts):
    """THE RULE OF THE LANE. A `mask_ref` in the suggestions is worth nothing unless the Region it
    points at is in the world an organ reads."""
    projected = project_post(posts["post_renaissance"], delta, post_id="post_renaissance")
    regions = {str(r["id"]): r for r in projected["region_annotations"]}
    assert len(regions) == 2
    for descriptor in delta.per_post[0].suggestions:
        geometry = descriptor["geometry"]
        ref = (geometry.get("mask_ref") or geometry.get("region_ref") or {}).get("region_id")
        assert ref in regions, f"{ref} points at nothing in the projected world"
    for region in regions.values():
        assert region["mask_rle"], "a region arrived in the world without its mask"


def test_both_regions_land_under_the_correct_post_id(delta, posts):
    projected = project_world(posts, delta)
    assert projected["post_renaissance"]["projection"]["added_regions"] == 2
    assert projected["post_buddha"]["projection"]["added_regions"] == 0
    assert projected["post_buddha"]["region_annotations"] == []


def test_a_post_the_preparation_did_not_touch_says_so_rather_than_looking_broken(delta, posts):
    projected = project_world(posts, delta)
    assert "added nothing" in projected["post_buddha"]["projection"]["detail"]


# ── 3. proposed stays proposed ───────────────────────────────────────────────

def test_the_projected_geometry_is_live_for_the_mission_and_uncommitted_everywhere_else(delta,
                                                                                        posts):
    projected = project_post(posts["post_renaissance"], delta, post_id="post_renaissance")
    for region in projected["region_annotations"]:
        assert region["proposed"] is True
        assert region["ledger_status"] == "proposed"
    assert projected["projection"]["ephemeral"] is True


def test_an_interpretive_naming_never_becomes_a_region_an_organ_could_stand_on(delta, posts):
    """A naming is a word about an extent. In `region_annotations` it would be a shape."""
    projected = project_post(posts["post_renaissance"], delta, post_id="post_renaissance")
    namings = [s for s in projected["proposed_suggestions"]
               if s["geometry"]["kind"] == GEOMETRY_NAMING]
    assert namings, "the naming half was dropped by the projection"
    naming_ids = {s["geometry"]["region_ref"]["region_id"] for s in namings}
    region_ids = {str(r["id"]) for r in projected["region_annotations"]}
    # It points at a region that IS there — and contributes none of its own.
    assert naming_ids <= region_ids
    assert len(projected["region_annotations"]) == 2


def test_geometry_provenance_and_revision_survive_the_projection(delta, posts):
    """UNCHANGED, not zero. `canonicalize_geometry` bumps `geometry_rev` when it derives a mask
    identity, so a captured concept region arrives at rev 1 — and the descriptors cite rev 1 too,
    which is why the validator's revision check passes. Asserting a literal here would pin an
    implementation detail of that function instead of the property that matters."""
    captured = {r.id: r for r in delta.per_post[0].proposed_regions}
    projected = project_post(posts["post_renaissance"], delta, post_id="post_renaissance")
    assert projected["region_annotations"], "nothing was projected"
    for region in projected["region_annotations"]:
        assert region["geometry_provenance"]["method"] == "sam3-concept-segment"
        assert region["geometry_provenance"]["prompt"] == "fold"
        assert region["geometry_rev"] == captured[str(region["id"])].geometry_rev
    # …and the descriptors' own references still agree with it, or the pointer would be stale.
    for region_id, rev in delta.per_post[0].measured_refs():
        assert rev == captured[region_id].geometry_rev


# ── 4. conflicts with committed geometry are refused ─────────────────────────

def test_a_proposal_may_not_replace_a_committed_region_of_the_same_id(delta, posts):
    """Same id, different geometry: the committed one stands. A preparation that repointed a
    curator's region at new pixels would be an accept path wearing a receipt's clothes."""
    proposed_id = delta.per_post[0].proposed_regions[0].id
    posts["post_renaissance"]["region_annotations"] = [
        {"id": proposed_id, "mask_rle": _rle(0, 3, 0, 3), "geometry_rev": 0}]
    with pytest.raises(ProjectionRefused, match="committed"):
        project_post(posts["post_renaissance"], delta, post_id="post_renaissance")


def test_an_identical_proposal_is_not_a_conflict_and_is_not_duplicated(delta, posts):
    """The negative control: prove the collision check admits the benign case."""
    first = delta.per_post[0].proposed_regions[0]
    posts["post_renaissance"]["region_annotations"] = [first.as_region()]
    projected = project_post(posts["post_renaissance"], delta, post_id="post_renaissance")
    ids = [str(r["id"]) for r in projected["region_annotations"]]
    assert ids.count(first.id) == 1
    assert len(ids) == 2


# ── 5. a real organ measures from the projected world ────────────────────────

def test_a_real_nestedness_agent_measures_containment_from_the_proposed_masks(delta, posts):
    """The vertical, at its narrowest: geometry a MODEL proposed, measured by a pure-python ORGAN,
    from a locus inside an ephemeral world."""
    projected = project_world(posts, delta)
    inner_id = delta.per_post[0].proposed_regions[0].id

    agent = sa.inhabit(agent_id="a1", post_id="post_renaissance", region_id=inner_id,
                       organ_set=(nest.ORGAN,))
    perceptions = sa.perceive(agent, projected["post_renaissance"], now=STAMP)

    assert perceptions, "the organ measured nothing in a world built from two nested masks"
    nesting = [p for p in perceptions if p.reading.relation == "nested_within"]
    assert nesting, "the nesting the fixture was built to contain was not measured"
    assert nesting[0].reading.basis == "mask"
    assert nesting[0].epistemic_status == "measured"


def test_the_organ_authored_the_mark_and_the_ledger_still_reads_proposed(delta, posts):
    """The private-measured / ledger-proposed ruling, at the seam. The agent's own record says
    `measured` because its organ measured; nothing has been committed, so the shared row does not."""
    projected = project_world(posts, delta)
    inner_id = delta.per_post[0].proposed_regions[0].id
    mission = AgentMission(id="am_1", kind=KIND_MISSION, post_id="post_renaissance",
                           region_id=inner_id, organ_set=(nest.ORGAN,))
    outcome = ad.SimulatorAdapter().dispatch(mission, projected, run_id="run_b2",
                                             inquiry_id="inq", evidence_goal_id="eg_fold",
                                             now=STAMP)
    assert outcome.dispatched is True
    assert outcome.marks, "the mission returned no organ mark"
    for mark in outcome.marks:
        assert mark["provenance"]["producer"] == nest.ORGAN
        assert mark["epistemic_status"] == "measured"
    for observation in outcome.observations:
        # The ledger row stores NO status; `hydrate_observation` derives one, and until a curator
        # commits the mark that is `proposed`.
        assert "epistemic_status" not in observation


def test_a_director_proposal_still_cannot_enter_as_a_perception(delta, posts):
    """The HARNESS-001B wall, unchanged by the projection. A proposed Region may be somewhere to
    stand; a Director DESCRIPTOR may never be something the agent measured."""
    projected = project_world(posts, delta)
    descriptor = delta.per_post[0].suggestions[0]
    mission = AgentMission(id="am_1", kind=KIND_MISSION, post_id="post_renaissance",
                           region_id=delta.per_post[0].proposed_regions[0].id,
                           organ_set=(nest.ORGAN,))
    with pytest.raises(ad.ProposalNotAPerception):
        ad.SimulatorAdapter().dispatch(mission, projected, run_id="r", inquiry_id="i",
                                       evidence_goal_id="eg", now=STAMP,
                                       proposed_marks=[descriptor])


# ── 6. the locus ─────────────────────────────────────────────────────────────

def test_the_locus_must_resolve_in_the_projected_post(delta, posts):
    projected = project_world(posts, delta)
    assert locus_available(projected["post_renaissance"],
                           delta.per_post[0].proposed_regions[0].id) is True
    assert locus_available(projected["post_renaissance"], "a_region_nobody_made") is False


def test_an_explicit_locus_is_never_second_guessed(delta):
    assert choose_locus(delta, post_id="post_buddha", region_id="chosen") == \
           ("post_buddha", "chosen")


def test_with_no_explicit_locus_the_first_captured_region_is_taken_in_capture_order(delta):
    """Not 'the largest' or 'the most confident': those are selections dressed as defaults, and a
    run whose locus moved with a confidence score would not be replayable."""
    assert choose_locus(delta) == ("post_renaissance",
                                   delta.per_post[0].proposed_regions[0].id)


def test_a_committed_region_is_a_valid_locus_too(delta, posts):
    posts["post_buddha"]["region_annotations"] = [
        {"id": "curator_drapery", "mask_rle": _rle(3, 7, 3, 7), "geometry_rev": 0}]
    projected = project_world(posts, delta)
    assert locus_available(projected["post_buddha"], "curator_drapery") is True


# ── 7. evidence cites both halves ────────────────────────────────────────────

def test_evidence_cites_the_mission_and_the_preparation_that_made_the_locus_exist(delta, posts):
    """A measurement on a proposed mask is only checkable if a reader can get from the mark back to
    the segmentation that produced the extent."""
    from backend.services.inquiry_engine.handoff import HandoffResult

    projected = project_world(posts, delta)
    mission = AgentMission(id="am_1", kind=KIND_MISSION, post_id="post_renaissance",
                           region_id=delta.per_post[0].proposed_regions[0].id,
                           organ_set=(nest.ORGAN,))
    outcome = ad.SimulatorAdapter().dispatch(mission, projected, run_id="run_b2", inquiry_id="i",
                                             evidence_goal_id="eg_fold", now=STAMP)
    handoff = HandoffResult(task_id="pt_fold", evidence_goal_id="eg_fold", delta=delta,
                            mission=outcome,
                            locus=("post_renaissance",
                                   delta.per_post[0].proposed_regions[0].id))
    cited = evidence_provenance(handoff)
    assert cited["mission_id"] == "am_1"
    assert cited["preparation_task_id"] == "pt_fold"
    assert cited["world_delta"]["run_id"] == "run_b2"
    assert cited["geometry_origin"] == "proposed_by_preparation"
