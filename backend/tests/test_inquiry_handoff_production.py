"""
HARNESS-001B2 §2 & §5 — the DETERMINISTIC PRODUCTION-RUNNER PROOF.

The directive is precise about what this may not be: *"This is not a fake Director result: the
production runner must perform `instances_to_regions`, suggestion conversion and context writes."*

So SAM 3's `segment_concept` is monkeypatched to return two known nested RLE masks, and everything
above it is the real thing — `real_actuators._run_concept_segment`, `plan.resolve`,
`execution.execute`, `sam3_concept_service.instances_to_regions`,
`suggestion_service.suggestions_from_concept_segments`, and the context writes.

A fake Director returns an answer. This runs the machinery that produces one, and the difference is
the whole point of the lane: the failure being fixed lives in the gap between what the machinery
writes and what the return value carries.
"""
from __future__ import annotations

import pytest

from backend.services import mask_geometry as mg
from backend.services import sam3_concept_service as sam3
from backend.services.director import capabilities as director_caps
from backend.services.inquiry_engine.goals import KIND_PREPARATION, PreparationTask
from backend.services.inquiry_engine.production import (ProductionDirectorAdapter, capture,
                                                        delta_of)
from backend.services.inquiry_engine.world import (GEOMETRY_NAMING, GEOMETRY_RASTER,
                                                   EXECUTION_UNAVAILABLE, MEASURED_ABSENCE,
                                                   validate_delta)
from backend.services.movement_kernel import posts_fingerprint

N = 16
STAMP = "2026-08-08T00:00:00+00:00"


def _rle(x0, x1, y0, y1):
    bits = [0] * (N * N)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * N + x] = 1
    return mg.rle_encode(bits, N, N)


#: Two NESTED masks — the inner strictly inside the outer — so the situated agent in the vertical
#: proof has a real containment to measure. A fixture whose masks did not nest would make the whole
#: chain run and measure nothing, which is indistinguishable from a broken handoff.
INNER = (5, 11, 6, 12)
OUTER = (2, 14, 2, 15)


@pytest.fixture()
def fake_sam3(monkeypatch):
    """The ONLY thing faked. Everything above it is production."""
    calls = []

    def _segment_concept(image, concept, **kwargs):
        calls.append({"concept": concept, "kwargs": kwargs})
        return {"concept": concept, "device": "cpu", "model": "sam3-fixture",
                "latency_ms": 11.0, "truncated": False,
                "instances": [{"mask_rle": _rle(*INNER), "confidence": 0.91, "index": 0},
                              {"mask_rle": _rle(*OUTER), "confidence": 0.84, "index": 1}]}

    monkeypatch.setattr(sam3, "segment_concept", _segment_concept)
    monkeypatch.setattr(sam3, "load", lambda **_: None)
    # THE CAPABILITY PROBE IS PART OF THE PRODUCTION PATH, not something to route around.
    # `RealActuatorRunner` asks `sam3_concept_service.is_available()` — weights on disk plus the
    # runtime importing — BEFORE it dispatches, and without weights it correctly reports the
    # actuator UNAVAILABLE and never calls the model. Patching the probe is what makes this a
    # deterministic run of the real runner rather than a test of the availability gate; the gate
    # itself has its own test below, with the probe left alone.
    monkeypatch.setattr(sam3, "is_available", lambda: True)

    async def _fetch(post_id, post):
        return b"\x89PNG-not-really"

    import backend.routers.posts as posts_router
    monkeypatch.setattr(posts_router, "_fetch_post_image_cached", _fetch)
    return calls


@pytest.fixture()
def posts():
    return {"post_renaissance": {"_id": "post_renaissance",
                                 "photo_url": "https://example.invalid/r.jpg",
                                 "region_annotations": []},
            "post_buddha": {"_id": "post_buddha",
                            "photo_url": "https://example.invalid/b.jpg",
                            "region_annotations": []}}


def _task(post_ids=("post_renaissance",), phrase="fold"):
    return PreparationTask(id="pt_fold", kind=KIND_PREPARATION, actuator="concept_segment",
                           params={"phrase": phrase}, post_ids=tuple(post_ids),
                           title="concept_segment")


def _prepare(posts, task=None, **kwargs):
    adapter = ProductionDirectorAdapter(**kwargs)
    result = adapter.prepare(task or _task(), posts, run_id="run_b2", inquiry_id="inq_b2",
                             evidence_goal_id="eg_fold", phrase="fold", now=STAMP)
    return adapter, result


# ── 1. the production runner really ran ──────────────────────────────────────

def test_the_real_concept_segment_runner_executes_and_not_a_fake_result(fake_sam3, posts):
    """If this is a fake Director result, `segment_concept` was never called and the proof is
    about a stand-in rather than about the machinery."""
    _adapter, result = _prepare(posts)
    assert [c["concept"] for c in fake_sam3] == ["fold"]
    assert result.ran is True
    assert result.records and result.records[0]["actuator"] == "concept_segment"
    assert result.records[0]["status"] == "ok"


def test_the_task_passes_through_the_same_plan_resolve_every_planner_uses(fake_sam3, posts):
    """It is an adapter, not a second planner. An actuator that does not exist is refused by the
    existing gate, in the existing vocabulary."""
    _adapter, result = _prepare(posts, _task()._base_dict() and PreparationTask(
        id="pt_x", kind=KIND_PREPARATION, actuator="segment_the_sublime",
        params={"phrase": "fold"}, post_ids=("post_renaissance",)))
    assert result.ran is False
    assert any(r.get("reason") == "unknown_actuator" for r in result.refusals)


# ── 2. exactly two Regions with valid masks, captured ────────────────────────

def test_exactly_two_proposed_regions_are_captured_with_their_masks(fake_sam3, posts):
    adapter, _result = _prepare(posts)
    delta = adapter.last_delta
    post = delta.post("post_renaissance")
    assert len(post.proposed_regions) == 2
    for region in post.proposed_regions:
        assert region.has_mask, "a captured region lost its mask"
        assert region.as_region()["mask_rle"]
        assert region.proposed is True


def test_the_masks_that_arrive_are_the_masks_that_were_measured(fake_sam3, posts):
    """Not merely 'a mask' — the geometry has to survive byte for byte, or the world an agent
    perceives from is a different world from the one the model measured."""
    adapter, _result = _prepare(posts)
    got = {mg.rle_area(r.as_region()["mask_rle"])
           for r in adapter.last_delta.post("post_renaissance").proposed_regions}
    want = {(INNER[1] - INNER[0]) * (INNER[3] - INNER[2]),
            (OUTER[1] - OUTER[0]) * (OUTER[3] - OUTER[2])}
    assert got == want


def test_every_measured_mask_ref_resolves_to_a_captured_region(fake_sam3, posts):
    adapter, _result = _prepare(posts)
    post = adapter.last_delta.post("post_renaissance")
    ids = set(post.region_ids())
    refs = post.measured_refs()
    assert refs, "no measured extent descriptor was captured"
    for region_id, _rev in refs:
        assert region_id in ids, f"{region_id} is a pointer with no target"


def test_every_naming_region_ref_resolves_and_carries_no_geometry(fake_sam3, posts):
    adapter, _result = _prepare(posts)
    post = adapter.last_delta.post("post_renaissance")
    ids = set(post.region_ids())
    namings = [s for s in post.suggestions if s["geometry"]["kind"] == GEOMETRY_NAMING]
    assert namings, "the interpretive naming half was lost"
    for descriptor in namings:
        assert descriptor["geometry"]["region_ref"]["region_id"] in ids
        assert "mask_ref" not in descriptor["geometry"]
        assert descriptor["epistemic_status"] == "interpretive"


def test_the_measured_and_interpretive_halves_are_both_present_and_distinct(fake_sam3, posts):
    """SAM 3 gives one object two statuses at once. A transport that flattened them would undo
    the whole point of `suggestions_from_concept_segments`."""
    adapter, _result = _prepare(posts)
    post = adapter.last_delta.post("post_renaissance")
    statuses = {s["producer"]: s["epistemic_status"] for s in post.suggestions}
    assert statuses["concept_segment"] == "measured"
    assert statuses["concept_naming"] == "interpretive"
    assert len([s for s in post.suggestions if s["geometry"]["kind"] == GEOMETRY_RASTER]) == 2


# ── 3. provenance survives ───────────────────────────────────────────────────

def test_region_and_descriptor_run_and_step_provenance_survive(fake_sam3, posts):
    adapter, _result = _prepare(posts)
    post = adapter.last_delta.post("post_renaissance")
    for descriptor in post.suggestions:
        assert descriptor["provenance"]["run_id"] == "run_b2"
        assert descriptor["provenance"]["step_id"] == "pt_fold"
    for region in post.proposed_regions:
        prov = region.as_region().get("geometry_provenance") or {}
        assert prov.get("method") == "sam3-concept-segment"
        assert prov.get("prompt") == "fold"


def test_the_delta_names_the_task_and_the_goal_it_was_prepared_for(fake_sam3, posts):
    adapter, result = _prepare(posts)
    delta = adapter.last_delta
    assert (delta.task_id, delta.evidence_goal_id, delta.run_id) == ("pt_fold", "eg_fold", "run_b2")
    assert delta_of(result).to_dict() == delta.to_dict()


# ── 4. the capture is a DIFF, not a dump ─────────────────────────────────────

def test_a_curators_committed_region_is_not_reported_as_something_preparation_proposed(
        fake_sam3, posts):
    """`build_context` seeds the context with committed regions so a step can use one. Reporting
    `ctx.regions` wholesale would hand back the curator's own geometry as a proposal."""
    posts["post_renaissance"]["region_annotations"] = [
        {"id": "curator_drapery", "label": "drapery", "mask_rle": _rle(3, 6, 3, 6),
         "geometry_rev": 0}]
    adapter, _result = _prepare(posts)
    post = adapter.last_delta.post("post_renaissance")
    assert "curator_drapery" not in post.region_ids()
    assert len(post.proposed_regions) == 2
    # …and it is still known to the delta, so a `mask_ref` at it would resolve.
    assert "curator_drapery" in post.committed_region_ids


def test_capture_is_a_pure_function_of_the_context_and_its_before_state():
    """The negative control for the diff: with nothing added, nothing is reported."""
    class _Ctx:
        regions = [{"id": "a", "geometry_rev": 0}]
        suggestions = []

    delta = capture(_Ctx(), post_id="p1", before_regions=list(_Ctx.regions),
                    before_suggestions=0)
    assert delta.proposed_regions == ()
    assert delta.suggestions == ()
    assert delta.committed_region_ids == ("a",)


def test_a_re_canonicalised_region_is_a_new_capture_and_not_an_unchanged_one():
    """Identity by `(id, geometry_rev)`. Keying on the id alone would report a region repointed at
    different pixels as something that was already there."""
    class _Ctx:
        regions = [{"id": "a", "geometry_rev": 1, "mask_rle": _rle(0, 4, 0, 4)}]
        suggestions = []

    delta = capture(_Ctx(), post_id="p1", before_regions=[{"id": "a", "geometry_rev": 0}],
                    before_suggestions=0)
    assert [r.id for r in delta.proposed_regions] == ["a"]


# ── 5. corpus identity ───────────────────────────────────────────────────────

def test_the_same_concept_on_two_posts_produces_ids_that_cannot_collide(fake_sam3, posts):
    """The directive's corpus identity proof. SAM's local ids are positional, so both posts get
    `cseg_fold_0`; every resolution is post-qualified, so nothing collides."""
    adapter, _result = _prepare(posts, _task(post_ids=("post_renaissance", "post_buddha")))
    delta = adapter.last_delta
    assert len(delta.per_post) == 2

    left = set(delta.post("post_renaissance").region_ids())
    right = set(delta.post("post_buddha").region_ids())
    assert left == right, "the fixture no longer reproduces the positional-id collision"
    assert delta.region_count == 4

    keys = {r.key for post in delta.per_post for r in post.proposed_regions}
    assert len(keys) == 4, "two posts' regions collapsed onto one identity"
    assert all(k[0] in ("post_renaissance", "post_buddha") for k in keys)


def test_no_frontend_style_suggestion_key_is_used_as_world_identity(fake_sam3, posts):
    """`source_ref` is `"{concept}|{index}"` — positional within a run, and labelled as such by
    `suggestion_service`. Nothing in the world may resolve on it."""
    adapter, _result = _prepare(posts, _task(post_ids=("post_renaissance", "post_buddha")))
    delta = adapter.last_delta
    refs = [s.get("source_ref") for post in delta.per_post for s in post.suggestions]
    assert refs and len(set(refs)) < len(refs), "the fixture no longer reproduces the ambiguity"
    # …and the world's own identity is unaffected by it.
    assert len({r.key for post in delta.per_post for r in post.proposed_regions}) == 4


# ── 6. the failure paths stay decomposed ─────────────────────────────────────

def test_a_concept_that_is_not_in_the_picture_is_a_measured_absence_not_an_error(monkeypatch,
                                                                                 posts):
    """`EMPTY` is a real answer — "that concept is not in this picture" — and must not arrive as
    the same reason as a model being down."""
    monkeypatch.setattr(sam3, "load", lambda **_: None)
    monkeypatch.setattr(sam3, "is_available", lambda: True)
    monkeypatch.setattr(sam3, "segment_concept",
                        lambda image, concept, **kw: {"concept": concept, "instances": [],
                                                      "model": "sam3-fixture", "latency_ms": 3.0})
    import backend.routers.posts as posts_router

    async def _fetch(post_id, post):
        return b"x"
    monkeypatch.setattr(posts_router, "_fetch_post_image_cached", _fetch)

    adapter, result = _prepare(posts)
    assert result.ran is True                      # it ran; it found nothing
    assert adapter.last_delta.region_count == 0
    assert any(r.get("reason") == MEASURED_ABSENCE for r in result.refusals)
    assert not any(r.get("reason") == EXECUTION_UNAVAILABLE for r in result.refusals)


def test_an_unavailable_model_produces_no_projected_region_and_says_why(posts):
    """The REAL availability gate, with the probe left alone: no SAM 3 weights on this machine, so
    `is_available()` is False, the runner reports UNAVAILABLE, and the model is never called. The
    delta is empty for a stated reason rather than quietly."""
    adapter, result = _prepare(posts)
    assert result.ran is False
    assert adapter.last_delta.region_count == 0
    assert any(r.get("reason") == EXECUTION_UNAVAILABLE for r in result.refusals)
    assert any("unavailable" in str(r.get("detail", "")).lower() for r in result.refusals)


def test_an_unregistered_runner_produces_no_projected_region_and_says_why(posts):
    """The other way execution goes missing: no runner registered at all."""
    adapter, result = _prepare(posts, registry_factory=lambda ctx: {})
    assert result.ran is False
    assert adapter.last_delta.region_count == 0
    assert any(r.get("reason") == EXECUTION_UNAVAILABLE for r in result.refusals)


def test_a_task_with_no_phrase_is_refused_before_any_model_is_called(fake_sam3, posts):
    """`concept_segment` requires a phrase and `plan.resolve` refuses without one — the same guard
    that stops an open-vocabulary finder fabricating on an empty query."""
    task = PreparationTask(id="pt_nophrase", kind=KIND_PREPARATION, actuator="concept_segment",
                           params={}, post_ids=("post_renaissance",))
    # NO PHRASE ON THE PACKET EITHER. A phrase legitimately arrives two ways — on the step, or
    # typed into the workspace and carried on the packet (`plan.availability_for`) — so the goal's
    # phrase has to be empty as well, or this would be asserting that a curator's own words are
    # ignored.
    adapter = ProductionDirectorAdapter()
    result = adapter.prepare(task, posts, run_id="run_b2", inquiry_id="inq_b2",
                             evidence_goal_id="eg_fold", phrase="", now=STAMP)
    assert result.ran is False
    assert fake_sam3 == [], "a model was called for a task that should never have dispatched"
    assert any(r.get("reason") == "missing_param" for r in result.refusals)


# ── 7. it commits nothing ────────────────────────────────────────────────────

def test_a_production_preparation_leaves_every_post_byte_identical(fake_sam3, posts):
    before = posts_fingerprint(posts)
    _adapter, result = _prepare(posts, _task(post_ids=("post_renaissance", "post_buddha")))
    assert posts_fingerprint(posts) == before
    assert result.posts_unchanged is True


def test_no_captured_region_is_committed_and_no_mark_id_is_minted(fake_sam3, posts):
    adapter, _result = _prepare(posts)
    for post in adapter.last_delta.per_post:
        for region in post.proposed_regions:
            assert region.as_region()["proposed"] is True
        for descriptor in post.suggestions:
            assert descriptor.get("id") is None, "a quarantined descriptor was given an id"


def test_the_delta_validates_before_it_can_be_handed_anywhere(fake_sam3, posts):
    adapter, _result = _prepare(posts)
    validate_delta(adapter.last_delta)             # does not raise


def test_the_production_adapter_is_a_sibling_and_not_a_silent_replacement():
    """Two adapters, both implementing `prepare`, kept apart on purpose. A test that thought it was
    running stubs and was firing SAM 3 would be slow, non-deterministic, and would look like a
    passing test the whole time."""
    from backend.services.inquiry_engine.adapters import DirectorAdapter

    assert DirectorAdapter is not ProductionDirectorAdapter
    assert hasattr(DirectorAdapter, "prepare") and hasattr(ProductionDirectorAdapter, "prepare")
    assert "concept_segment" in director_caps.known()
