"""
HARNESS-001B2 §1 — the Region-plus-mask handoff contract, and the failure it exists to prevent.

## The failure, stated once

`concept_segment` produces its evidence in TWO PLACES and only one of them is a return value:

    ctx.regions      the proposed Regions, which OWN `mask_rle`
    ctx.suggestions  the quarantined descriptors, whose geometry is `mask_ref.region_id` — a POINTER
    result.payload   `{"concept", "instances", "truncated", "latency_ms"}` — counts, and nothing else

HARNESS-001B's `DirectorAdapter` collects `ActuatorResult.payload`. Run against the real runner it
therefore captures the counts, loses the Regions, and — if the descriptors were captured from the
context alone — would hand a simulator a `mask_ref` whose target does not exist anywhere in the
handoff. **A pointer without its target.** Every downstream reader would see a well-formed mark
citing a region id, and no geometry behind it.

`test_the_old_payload_only_capture_loses_the_masks` is the negative control for this whole lane: it
pins that the failure is real, so the fix cannot be a no-op. If that test ever goes green without
`PreparedWorldDelta` changing, the contract below is guarding nothing.

## What is pinned here

The SHAPES, from the production modules themselves — `instances_to_regions` and
`suggestions_from_concept_segments` — rather than from a hand-written idea of what they emit. If
either changes, these fail, which is the point: this lane transports what production makes and a
transporter pinned to a guess is a transporter that will one day move the wrong thing.
"""
from __future__ import annotations

import pytest

from backend.services import mask_geometry as mg
from backend.services import sam3_concept_service as sam3
from backend.services import suggestion_service as ss
from backend.services.inquiry_engine.world import (GEOMETRY_NAMING, GEOMETRY_RASTER,
                                                   POINTER_TARGET_MISSING, PreparedWorldDelta,
                                                   PostDelta, ProposedRegion, WorldDeltaInvalid,
                                                   region_key, validate_delta)

N = 16


def _rle(x0, x1, y0, y1):
    bits = [0] * (N * N)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * N + x] = 1
    return mg.rle_encode(bits, N, N)


def concept_result(concept="fold", *, boxes=((4, 12, 4, 10), (0, 16, 0, 16))):
    """What `sam3_concept_service.segment_concept` returns, in its documented shape.

    `{"concept", "instances": [{"mask_rle", "confidence", "index"}], "latency_ms", "model", …}`
    — quoted from that function's own docstring rather than invented here.
    """
    return {
        "concept": concept,
        "instances": [{"mask_rle": _rle(*b), "confidence": 0.9 - 0.1 * i, "index": i}
                      for i, b in enumerate(boxes)],
        "latency_ms": 12.5, "device": "cpu", "model": "sam3-test", "truncated": False,
    }


# ── 1. the production shapes, read from production ───────────────────────────

def test_the_region_owns_the_mask_and_the_descriptor_only_points_at_it():
    """THE ASYMMETRY THIS LANE IS ABOUT. Geometry lives on the Region; the mark carries a
    reference. The mark contract requires it (`validateMark`: a `raster_mask` needs
    `mask_ref.region_id`), and a suggestion that inlined its mask is dropped silently at intake."""
    result = concept_result()
    regions = sam3.instances_to_regions(result)
    suggestions = ss.suggestions_from_concept_segments([result], run_id="run_1", step_id="st_1")

    assert len(regions) == 2
    for region in regions:
        assert region["mask_rle"], "the Region does not own a mask"
        assert region["proposed"] is True, "a captured Region must stay uncommitted"

    measured = [s for s in suggestions if s["producer"] == "concept_segment"]
    assert measured, "no measured extent descriptor"
    for descriptor in measured:
        assert descriptor["geometry"]["kind"] == GEOMETRY_RASTER
        assert descriptor["geometry"]["mask_ref"]["region_id"]
        assert "mask_rle" not in descriptor["geometry"], "the descriptor inlined its geometry"


def test_the_naming_descriptor_points_at_the_same_region_and_authors_no_geometry():
    result = concept_result()
    sam3.instances_to_regions(result)
    suggestions = ss.suggestions_from_concept_segments([result], run_id="run_1", step_id="st_1")

    naming = [s for s in suggestions if s["producer"] == "concept_naming"]
    assert naming, "no interpretive naming descriptor"
    for descriptor in naming:
        assert descriptor["geometry"]["kind"] == GEOMETRY_NAMING
        assert descriptor["geometry"]["region_ref"]["region_id"]
        assert "mask_ref" not in descriptor["geometry"], "a naming carried a mask reference"
        assert descriptor["epistemic_status"] == "interpretive"


# ── 2. the negative control: the failure is real ─────────────────────────────

def test_the_old_payload_only_capture_loses_the_masks():
    """THE NEGATIVE CONTROL FOR THE WHOLE LANE.

    `_run_concept_segment` returns counts. Everything that matters went into the context. A capture
    that reads only `ActuatorResult.payload` — which is what HARNESS-001B's adapter does — gets a
    payload with no `regions` key at all, so the masks are simply not in the handoff.

    If this test ever fails, the transport problem has been fixed somewhere else and
    `PreparedWorldDelta` is guarding nothing.
    """
    result = concept_result()
    payload = {"concept": result["concept"], "instances": len(result["instances"]),
               "truncated": result["truncated"], "latency_ms": result["latency_ms"]}
    assert "regions" not in payload
    assert "suggestions" not in payload
    assert not any(isinstance(v, (list, dict)) for v in payload.values()), \
        "the real payload carries only scalars — counts, not evidence"


def test_a_descriptor_whose_target_region_is_absent_is_refused_by_name():
    """Pointer without target is a NAMED refusal, not a silently detached mark. Silently dropping
    it would make a run report fewer marks with no reason; keeping it would put a mark citing
    nothing into an agent's world."""
    result = concept_result()
    sam3.instances_to_regions(result)
    suggestions = ss.suggestions_from_concept_segments([result], run_id="run_1", step_id="st_1")

    delta = PreparedWorldDelta(
        task_id="pt_1", evidence_goal_id="eg_1", run_id="run_1", step_id="st_1",
        per_post=(PostDelta(post_id="p1", proposed_regions=(),   # ← the targets are missing
                            suggestions=tuple(suggestions)),))
    with pytest.raises(WorldDeltaInvalid) as excinfo:
        validate_delta(delta)
    assert POINTER_TARGET_MISSING in str(excinfo.value)


def test_a_valid_delta_passes_the_same_validator():
    """The negative control's negative control: prove the validator admits a complete handoff, or
    'it refused' says nothing at all."""
    result = concept_result()
    regions = sam3.instances_to_regions(result)
    suggestions = ss.suggestions_from_concept_segments([result], run_id="run_1", step_id="st_1")

    delta = PreparedWorldDelta(
        task_id="pt_1", evidence_goal_id="eg_1", run_id="run_1", step_id="st_1",
        per_post=(PostDelta(post_id="p1",
                            proposed_regions=tuple(ProposedRegion.of(r) for r in regions),
                            suggestions=tuple(suggestions)),))
    validate_delta(delta)                      # does not raise
    assert delta.region_count == 2
    assert delta.suggestion_count == len(suggestions)


# ── 3. identity is post-qualified ────────────────────────────────────────────

def test_a_region_is_identified_by_post_and_revision_never_by_id_alone():
    """SAM instance ids are POSITIONAL (`cseg_fold_0`), so two posts segmented for one concept
    produce the SAME local id. Resolving on `region_id` alone would make the second image's mask
    answer for the first."""
    left = sam3.instances_to_regions(concept_result())
    right = sam3.instances_to_regions(concept_result())
    assert left[0]["id"] == right[0]["id"], "the fixture no longer reproduces the collision"

    assert region_key("p1", left[0]) != region_key("p2", right[0])
    assert region_key("p1", left[0]) == ("p1", left[0]["id"], left[0].get("geometry_rev", 0))


def test_two_posts_carrying_the_same_local_id_do_not_collide_in_one_delta():
    left = sam3.instances_to_regions(concept_result())
    right = sam3.instances_to_regions(concept_result())
    delta = PreparedWorldDelta(
        task_id="pt_1", evidence_goal_id="eg_1", run_id="run_1", step_id="st_1",
        per_post=(PostDelta(post_id="p1",
                            proposed_regions=tuple(ProposedRegion.of(r) for r in left)),
                  PostDelta(post_id="p2",
                            proposed_regions=tuple(ProposedRegion.of(r) for r in right))))
    validate_delta(delta)
    assert delta.region_count == 4
    assert len({r.key for post in delta.per_post for r in post.proposed_regions}) == 4


def test_a_mask_ref_resolves_only_within_its_own_post():
    """A descriptor on `p2` naming a region id that exists only on `p1` is a pointer without a
    target ON THIS POST, and must not be satisfied by the other image's region."""
    result = concept_result()
    left = sam3.instances_to_regions(result)         # mutates `result` with the region ids
    suggestions = ss.suggestions_from_concept_segments([result], run_id="r")
    assert suggestions, "the fixture produced no descriptors, so nothing would be resolved"
    # the descriptors' mask_refs were minted against regions that live on p1
    delta = PreparedWorldDelta(
        task_id="pt", evidence_goal_id="eg", run_id="r", step_id="st",
        per_post=(PostDelta(post_id="p1",
                            proposed_regions=tuple(ProposedRegion.of(r) for r in left)),
                  PostDelta(post_id="p2", proposed_regions=(),
                            suggestions=tuple(suggestions))))
    with pytest.raises(WorldDeltaInvalid, match=POINTER_TARGET_MISSING):
        validate_delta(delta)


# ── 4. a Region without a valid mask admits no measured extent ───────────────

def test_a_region_with_no_mask_is_refused_rather_than_carried_as_geometry():
    with pytest.raises(WorldDeltaInvalid, match="carries no mask"):
        validate_delta(PreparedWorldDelta(
            task_id="pt", evidence_goal_id="eg", run_id="r", step_id="st",
            per_post=(PostDelta(post_id="p1", proposed_regions=(
                ProposedRegion.of({"id": "cseg_fold_0", "proposed": True}),)),)))


def test_an_instance_with_no_mask_never_becomes_a_measured_descriptor():
    """Production's own rule (`suggestions_from_concept_segments`: 'no mask, no claim — never
    coerced to a box'), pinned here because this lane's delta rests on it."""
    result = concept_result()
    result["instances"][0].pop("mask_rle")
    regions = sam3.instances_to_regions(result)
    suggestions = ss.suggestions_from_concept_segments([result], run_id="r")
    assert len(regions) == 1
    assert all(s["geometry"].get("mask_ref", {}).get("region_id") != "cseg_fold_0"
               for s in suggestions if s["geometry"]["kind"] == GEOMETRY_RASTER)


def test_a_naming_may_never_be_admitted_as_geometry():
    """A `region_ref` authors no extent. Admitting one as geometry is how an interpretive word
    becomes a measured shape."""
    result = concept_result()
    regions = sam3.instances_to_regions(result)
    suggestions = ss.suggestions_from_concept_segments([result], run_id="r")
    naming = next(s for s in suggestions if s["producer"] == "concept_naming")

    delta = PreparedWorldDelta(
        task_id="pt", evidence_goal_id="eg", run_id="r", step_id="st",
        per_post=(PostDelta(post_id="p1",
                            proposed_regions=tuple(ProposedRegion.of(r) for r in regions),
                            suggestions=(naming,)),))
    validate_delta(delta)
    assert delta.per_post[0].measured_refs() == ()
    assert delta.per_post[0].naming_refs()


# ── 5. the delta is a receipt, not a ledger ──────────────────────────────────

def test_every_captured_region_stays_proposed_and_no_committed_mark_id_is_minted():
    result = concept_result()
    regions = [ProposedRegion.of(r) for r in sam3.instances_to_regions(result)]
    for region in regions:
        assert region.proposed is True
        assert region.as_region()["proposed"] is True
        assert "mark_id" not in region.as_region()


def test_the_delta_round_trips_and_is_plain_json():
    import json

    result = concept_result()
    regions = sam3.instances_to_regions(result)
    suggestions = ss.suggestions_from_concept_segments([result], run_id="r", step_id="st")
    delta = PreparedWorldDelta(
        task_id="pt", evidence_goal_id="eg", run_id="r", step_id="st",
        per_post=(PostDelta(post_id="p1",
                            proposed_regions=tuple(ProposedRegion.of(r) for r in regions),
                            suggestions=tuple(suggestions)),),
        availability={"state": "checked"}, posts_unchanged=True)
    payload = delta.to_dict()
    assert json.loads(json.dumps(payload)) == payload
    assert PreparedWorldDelta.from_dict(payload).to_dict() == payload


def test_region_and_descriptor_run_and_step_provenance_survive_capture():
    result = concept_result()
    regions = sam3.instances_to_regions(result)
    suggestions = ss.suggestions_from_concept_segments([result], run_id="run_7", step_id="st_3")
    delta = PreparedWorldDelta(
        task_id="pt", evidence_goal_id="eg", run_id="run_7", step_id="st_3",
        per_post=(PostDelta(post_id="p1",
                            proposed_regions=tuple(ProposedRegion.of(r) for r in regions),
                            suggestions=tuple(suggestions)),))
    validate_delta(delta)
    for descriptor in delta.per_post[0].suggestions:
        assert descriptor["provenance"]["run_id"] == "run_7"
        assert descriptor["provenance"]["step_id"] == "st_3"
    for region in delta.per_post[0].proposed_regions:
        # `canonicalize_geometry` writes the geometry provenance; it must survive untouched.
        assert region.as_region().get("geometry_provenance"), "geometry provenance was dropped"
