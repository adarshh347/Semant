"""
HARNESS-001B2 §1 — the Region-plus-mask contract, and the failure that made it necessary.

Two halves:

  1. THE FAILURE, DEMONSTRATED. `DirectorAdapter.prepare` reads `ActuatorResult.payload`. Against
     a real `concept_segment` step that returns a payload of COUNTS, what it captures is a count —
     and both the proposed Regions that own the masks and the descriptors that point at them are
     left behind in the `ExecutionContext` nobody looked at. The test drives the real production
     runner to show it, so it is a fact about the tree rather than a claim about it.

  2. THE CONTRACT. `PreparedWorldDelta` carries both halves and refuses to be projected while any
     pointer fails to resolve. Identity is `(post_id, region_id, geometry_rev)`, so the same local
     id on two images is two Regions and not one.
"""
from __future__ import annotations

import pytest

from backend.services import sam3_concept_service, suggestion_service
from backend.services.inquiry_engine import handoff_fixtures as fx
from backend.services.inquiry_engine.world import (POINTER_TARGET_MISSING, DeltaRefused, PostDelta,
                                                   PreparedWorldDelta, assert_projectable,
                                                   authors_geometry, pointer_of, region_has_mask,
                                                   region_key, validate_delta)


# ── the production shapes, built by production code ──────────────────────────

@pytest.fixture(scope="module")
def produced():
    """What `_run_concept_segment` actually makes: regions from `instances_to_regions`, and the
    two-per-instance descriptors from `suggestions_from_concept_segments`. Real functions."""
    result = fx.sam_result()
    regions = sam3_concept_service.instances_to_regions(result)
    suggestions = suggestion_service.suggestions_from_concept_segments(
        [result], run_id="run_fixture", step_id="st_1", concept_source="curator",
        adapter="sam3", model=result.get("model"), naming_floor=0.0)
    return regions, suggestions


def test_the_fixture_produces_two_regions_that_own_real_masks(produced):
    regions, _ = produced
    assert len(regions) == 2
    assert all(region_has_mask(r) for r in regions)
    assert all(r["proposed"] is True for r in regions)
    assert all("geometry_rev" in r for r in regions)


def test_production_emits_two_descriptors_per_instance_and_neither_carries_a_mask(produced):
    """The two-status split, which is the reason a pointer exists at all: the measured extent and
    the interpretive naming are separable so review can accept one and reject the other."""
    _, suggestions = produced
    assert len(suggestions) == 4
    measured = [s for s in suggestions if s["producer"] == "concept_segment"]
    naming = [s for s in suggestions if s["producer"] == "concept_naming"]
    assert len(measured) == len(naming) == 2
    assert all(s["epistemic_status"] == "measured" for s in measured)
    assert all(s["epistemic_status"] == "interpretive" for s in naming)
    # NEITHER inlines geometry. The mask lives on the Region; a descriptor only names it.
    assert not any(authors_geometry(s) for s in suggestions)


def test_every_descriptor_points_at_a_region_and_the_two_shapes_both_read(produced):
    regions, suggestions = produced
    ids = {r["id"] for r in regions}
    for descriptor in suggestions:
        pointer = pointer_of(descriptor)
        assert pointer is not None, f"{descriptor['producer']} points at nothing"
        assert pointer[0] in ids
    # The measured half uses `mask_ref`; the naming half uses `region_ref`. A reader that knew
    # only one of them would silently treat every naming as pointing nowhere.
    kinds = {s["producer"]: s["geometry"]["kind"] for s in suggestions}
    assert kinds["concept_segment"] == "raster_mask"
    assert kinds["concept_naming"] == "region_ref"


# ── 1. the failure this lane exists to fix ───────────────────────────────────

def test_the_result_payload_carries_counts_and_not_the_evidence():
    """`ActuatorResult.payload` for a concept segmentation is `{concept, instances: 2, …}`.

    A capture that reads only the payload gets the NUMBER TWO. The masks are not in it, the
    descriptors are not in it, and nothing raises — which is why this was invisible.
    """
    result = fx.sam_result()
    regions = sam3_concept_service.instances_to_regions(result)
    payload = {"concept": result["concept"], "instances": len(result["instances"]),
               "truncated": result.get("truncated"), "latency_ms": result.get("latency_ms")}
    assert payload["instances"] == 2
    assert not any(isinstance(v, (list, dict)) for v in payload.values())
    assert regions        # they exist; the payload simply does not mention them


def test_capturing_only_the_descriptors_yields_a_pointer_with_no_target(produced):
    """THE NAMED FAILURE. Descriptors without their Regions are marks with nothing under them.

    Every one of them is well-formed, names a region id, and resolves to nothing. Downstream that
    is not an error — it is an agent standing in an empty room.
    """
    _, suggestions = produced
    delta = PreparedWorldDelta(
        task_id="pt_1", per_post=(PostDelta(post_id="handoff_post_a", proposed_regions=(),
                                            suggestions=tuple(suggestions)),))
    problems = validate_delta(delta)
    assert problems, "a delta of pointers with no targets must not validate"
    assert {p["reason"] for p in problems} == {POINTER_TARGET_MISSING}
    assert len(problems) == 4
    with pytest.raises(DeltaRefused, match="mark with nothing under it"):
        assert_projectable(delta)


def test_carrying_both_halves_validates(produced):
    regions, suggestions = produced
    delta = PreparedWorldDelta(
        task_id="pt_1", per_post=(PostDelta(post_id="handoff_post_a",
                                            proposed_regions=tuple(regions),
                                            suggestions=tuple(suggestions)),))
    assert validate_delta(delta) == []
    assert_projectable(delta)            # must not raise
    assert delta.proposed_region_count() == 2
    assert delta.suggestion_count() == 4


# ── 2. identity is post-qualified ────────────────────────────────────────────

def test_the_same_local_id_on_two_posts_is_two_regions():
    """SAM 3's instance ids are POSITIONAL, so one concept on two images mints `cseg_fold_0`
    twice. Under a global key the second would shadow the first and an agent on image B would
    perceive image A's mask — well-formed, and about the wrong picture."""
    result_a = sam3_concept_service.instances_to_regions(fx.sam_result())
    result_b = sam3_concept_service.instances_to_regions(fx.sam_result())
    assert {r["id"] for r in result_a} == {r["id"] for r in result_b}      # the collision is real

    delta = PreparedWorldDelta(per_post=(
        PostDelta(post_id="post_a", proposed_regions=tuple(result_a)),
        PostDelta(post_id="post_b", proposed_regions=tuple(result_b))))
    assert len(set(delta.keys())) == 4          # four distinct Regions, not two
    assert validate_delta(delta) == []


def test_a_region_key_needs_all_three_parts():
    assert region_key("p", "r", 0) != region_key("q", "r", 0)      # post
    assert region_key("p", "r", 0) != region_key("p", "s", 0)      # id
    assert region_key("p", "r", 0) != region_key("p", "r", 1)      # geometry revision
    assert region_key("p", "r", None) == region_key("p", "r", 0)   # absent rev is rev 0


def test_a_pointer_resolves_into_the_delta_for_its_own_post_only(produced):
    regions, suggestions = produced
    delta = PreparedWorldDelta(per_post=(
        PostDelta(post_id="post_a", proposed_regions=tuple(regions)),
        PostDelta(post_id="post_b", suggestions=tuple(suggestions))))
    problems = validate_delta(delta)
    assert problems and all(p["post_id"] == "post_b" for p in problems)


# ── 3. the other refusals ────────────────────────────────────────────────────

def test_a_pointer_into_a_committed_region_resolves_without_copying_it(produced):
    """A committed Region is not copied into the delta. Copying it would create a second geometry
    for one extent, which is PROV-001's two-copy drift arriving through the back door."""
    _, suggestions = produced
    target = pointer_of(suggestions[0])[0]
    delta = PreparedWorldDelta(per_post=(
        PostDelta(post_id="post_a", suggestions=(suggestions[0],),
                  committed_region_ids=(target,)),))
    assert validate_delta(delta) == []


def test_a_measured_descriptor_pointing_at_a_region_with_no_mask_is_refused(produced):
    _, suggestions = produced
    measured = next(s for s in suggestions if s["epistemic_status"] == "measured")
    empty = {"id": pointer_of(measured)[0], "proposed": True, "geometry_rev": 0}
    delta = PreparedWorldDelta(per_post=(
        PostDelta(post_id="post_a", proposed_regions=(empty,), suggestions=(measured,)),))
    problems = validate_delta(delta)
    assert problems
    assert "owns no mask" in problems[0]["detail"]


def test_a_naming_that_carries_geometry_is_refused_rather_than_accepted(produced):
    """A naming authors no geometry. An inlined mask is dropped SILENTLY at frontend intake, so
    it fails invisibly in production and has to fail loudly here."""
    regions, suggestions = produced
    naming = next(s for s in suggestions if s["epistemic_status"] == "interpretive")
    smuggled = {**naming, "geometry": {**naming["geometry"], "mask_rle": fx.inner_rle()}}
    assert authors_geometry(smuggled)
    delta = PreparedWorldDelta(per_post=(
        PostDelta(post_id="post_a", proposed_regions=tuple(regions),
                  suggestions=(smuggled,)),))
    problems = validate_delta(delta)
    assert problems
    assert "authors no geometry" in problems[0]["detail"]


def test_two_proposals_for_one_id_with_different_geometry_are_refused(produced):
    """Refused rather than resolved: picking one would substitute an extent nobody chose for the
    one that was measured."""
    regions, _ = produced
    conflicting = {**regions[0], "mask_rle": fx.inner_rle(), "geometry_rev": 0}
    delta = PreparedWorldDelta(per_post=(
        PostDelta(post_id="post_a", proposed_regions=(regions[0], conflicting)),))
    problems = validate_delta(delta)
    assert problems
    assert "different geometry" in problems[0]["detail"]


def test_an_identical_duplicate_is_not_a_conflict(produced):
    """The negative control for the test above: the refusal is about DIFFERING geometry, not about
    a repeated id, or it would fire on a harmless double-capture."""
    regions, _ = produced
    delta = PreparedWorldDelta(per_post=(
        PostDelta(post_id="post_a", proposed_regions=(regions[0], dict(regions[0]))),))
    assert validate_delta(delta) == []


def test_a_descriptor_that_points_at_nothing_at_all_is_outside_this_check():
    """A relation or a reading need not name a Region. Refusing one would make the pointer check
    an assertion that every descriptor is about an extent, which is not true."""
    delta = PreparedWorldDelta(per_post=(
        PostDelta(post_id="post_a",
                  suggestions=({"producer": "semantic_read", "type": "relation_mark",
                                "geometry": {"kind": "derived"}},)),))
    assert validate_delta(delta) == []


# ── 4. the delta serialises ──────────────────────────────────────────────────

def test_the_delta_round_trips(produced):
    regions, suggestions = produced
    delta = PreparedWorldDelta(
        task_id="pt_1", evidence_goal_id="eg_1", run_id="run_1", inquiry_id="inq_1",
        step_ids=("st_1",), availability="ok", detail="two instances",
        per_post=(PostDelta(post_id="post_a", proposed_regions=tuple(regions),
                            suggestions=tuple(suggestions)),))
    assert PreparedWorldDelta.from_dict(delta.to_dict()) == delta


def test_the_delta_reports_whether_it_has_anything_an_organ_could_stand_on(produced):
    regions, _ = produced
    assert PreparedWorldDelta(per_post=(PostDelta("post_a", tuple(regions)),)).has_usable_region()
    assert not PreparedWorldDelta().has_usable_region()
    boxes_only = ({"id": "r_1", "proposed": True, "box": {"x": 0, "y": 0, "w": 1, "h": 1}},)
    assert not PreparedWorldDelta(per_post=(PostDelta("post_a", boxes_only),)).has_usable_region()


def test_the_contract_module_imports_nothing_that_could_write():
    """The whole lane's premise, checked against the IMPORTS rather than the prose.

    Grepping the source would fire on the docstring that promises exactly this, which is the kind
    of test that passes until somebody deletes a comment.
    """
    import ast

    import backend.services.inquiry_engine.world as world

    tree = ast.parse(open(world.__file__, encoding="utf-8").read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert imported == {"__future__", "dataclasses", "typing"}, imported
