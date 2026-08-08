"""
HARNESS-001B2 §2 — capturing real Director execution as a proposed world delta.

Everything here runs the PRODUCTION path. The only things replaced are the two boundaries a test
must not cross:

    the model      `sam3_concept_service` → a fake returning two known nested RLE masks
    the network    `posts._fetch_post_image_cached` → fixture bytes

Above those, it is `execution.execute` → `real_registry` → `RealActuatorRunner` →
`_run_concept_segment` → `instances_to_regions` → `suggestions_from_concept_segments` → the
context writes, unmodified. That is the difference between this and a fake Director result: a
fake would return descriptors somebody wrote in a test file, and these are minted by the code that
runs in production.
"""
from __future__ import annotations

import importlib

import pytest

from backend.services.director import execution as director_execution
from backend.services.inquiry_engine import handoff_fixtures as fx
from backend.services.inquiry_engine.goals import PreparationTask
from backend.services.inquiry_engine.production import AVAILABILITY_OK, ProductionDirectorAdapter
from backend.services.inquiry_engine.world import (EXECUTION_UNAVAILABLE, MEASURED_ABSENCE,
                                                   pointer_of, region_has_mask, validate_delta)

POST_A = "handoff_post_a"
POST_B = "handoff_post_b"
RUN = "run_handoff"
NOW = "2026-08-08T12:00:00Z"


@pytest.fixture
def deterministic_sam(monkeypatch):
    """The model boundary, and only the model boundary."""
    service = fx.FakeSam3Service()
    monkeypatch.setitem(importlib.sys.modules, "backend.services.sam3_concept_service", service)
    posts = importlib.import_module("backend.routers.posts")

    async def _bytes(post_id, post):
        return b"fixture-image-bytes"

    monkeypatch.setattr(posts, "_fetch_post_image_cached", _bytes)
    return service


def _task(post_ids=(POST_A,), concept: str = fx.CONCEPT) -> PreparationTask:
    return PreparationTask(id="pt_1", parent_goal_id="eg_1", title="segment the concept",
                           actuator="concept_segment", params={"phrase": concept},
                           post_ids=tuple(post_ids))


def _prepare(posts, task=None, adapter=None):
    adapter = adapter or ProductionDirectorAdapter()
    return adapter.prepare_world(task or _task(), posts, run_id=RUN, inquiry_id="inq_1",
                                 evidence_goal_id="eg_1", phrase="", now=NOW)


# ── the capture ──────────────────────────────────────────────────────────────

def test_the_real_runner_produces_two_proposed_regions_and_the_capture_keeps_them(
        deterministic_sam):
    """The lane's central claim. Both masks arrive; neither is a count."""
    posts = {POST_A: fx.post(POST_A)}
    _result, delta = _prepare(posts)

    assert delta.availability == AVAILABILITY_OK
    assert delta.proposed_region_count() == 2
    regions = delta.for_post(POST_A).proposed_regions
    assert all(region_has_mask(r) for r in regions)
    assert all(r["proposed"] is True for r in regions)
    # Minted by `instances_to_regions`, not by this test.
    assert {r["id"] for r in regions} == {"cseg_fold_0", "cseg_fold_1"}


def test_the_capture_takes_the_context_suggestions_and_not_the_result_payload(deterministic_sam):
    """Four descriptors — two per instance — because the capture reads `ctx.suggestions`.

    The payload the runner returned says `instances: 2` and carries no descriptor at all, so a
    capture that read it would report the same run as two of nothing.
    """
    posts = {POST_A: fx.post(POST_A)}
    _result, delta = _prepare(posts)
    suggestions = delta.for_post(POST_A).suggestions
    assert len(suggestions) == 4
    assert {s["producer"] for s in suggestions} == {"concept_segment", "concept_naming"}


def test_every_captured_pointer_resolves_into_the_captured_regions(deterministic_sam):
    posts = {POST_A: fx.post(POST_A)}
    _result, delta = _prepare(posts)
    assert validate_delta(delta) == []
    ids = {r["id"] for r in delta.for_post(POST_A).proposed_regions}
    for descriptor in delta.for_post(POST_A).suggestions:
        assert pointer_of(descriptor)[0] in ids


def test_the_two_statuses_survive_the_capture_separately(deterministic_sam):
    posts = {POST_A: fx.post(POST_A)}
    _result, delta = _prepare(posts)
    by_status = {}
    for s in delta.for_post(POST_A).suggestions:
        by_status.setdefault(s["epistemic_status"], []).append(s)
    assert len(by_status["measured"]) == 2
    assert len(by_status["interpretive"]) == 2
    assert all(s["geometry"]["kind"] == "raster_mask" for s in by_status["measured"])
    assert all(s["geometry"]["kind"] == "region_ref" for s in by_status["interpretive"])
    # The naming carries the words; the extent deliberately does not.
    assert all(s["label"] == fx.CONCEPT for s in by_status["interpretive"])
    assert all(s["label"] == "" for s in by_status["measured"])


def test_run_and_step_provenance_survives_onto_both_regions_and_descriptors(deterministic_sam):
    posts = {POST_A: fx.post(POST_A)}
    _result, delta = _prepare(posts)
    assert delta.run_id == RUN
    assert delta.task_id == "pt_1"
    assert delta.evidence_goal_id == "eg_1"
    assert delta.step_ids
    for descriptor in delta.for_post(POST_A).suggestions:
        provenance = descriptor["provenance"]
        assert provenance["run_id"] == f"{RUN}:pt_1"
        assert provenance.get("step_id")
    for region in delta.for_post(POST_A).proposed_regions:
        # The DRAWER survives — `canonicalize_geometry` stamped who cut the mask.
        assert region["geometry_provenance"]["method"] == "sam3-concept-segment"


def test_the_production_records_carry_the_model_and_the_adapter(deterministic_sam):
    posts = {POST_A: fx.post(POST_A)}
    _result, delta = _prepare(posts)
    assert delta.production_records
    record = delta.production_records[0]
    assert record["actuator"] == "concept_segment"
    assert record["status"] == director_execution.OK
    assert record["post_id"] == POST_A


# ── the diff, not the whole list ─────────────────────────────────────────────

def test_a_committed_region_is_not_reported_as_something_this_preparation_proposed(
        deterministic_sam):
    """The context is SEEDED with committed Regions so a downstream step can read one. Returning
    the whole list would show a curator a mask they accepted last week as new work."""
    committed = fx.committed_region()
    posts = {POST_A: fx.post(POST_A, regions=[committed])}
    _result, delta = _prepare(posts)

    proposed = delta.for_post(POST_A)
    assert committed["id"] not in {r["id"] for r in proposed.proposed_regions}
    assert len(proposed.proposed_regions) == 2
    # It is still RESOLVABLE, without being copied — copying it would create a second geometry
    # for one extent.
    assert committed["id"] in proposed.committed_region_ids


def test_a_recut_mask_under_an_old_id_shows_up_as_added(deterministic_sam):
    """Identity, not position. A Region whose `geometry_rev` moved is a different extent under the
    same name, and a diff keyed on id alone would call it unchanged."""
    stale = fx.committed_region(region_id="cseg_fold_0")
    stale["geometry_rev"] = 99
    posts = {POST_A: fx.post(POST_A, regions=[stale])}
    _result, delta = _prepare(posts)
    added = {r["id"] for r in delta.for_post(POST_A).proposed_regions}
    assert "cseg_fold_0" in added


# ── corpus identity ──────────────────────────────────────────────────────────

def test_the_same_local_id_on_two_posts_does_not_collide(deterministic_sam):
    """SAM 3 mints `cseg_fold_0` on both images. Every resolution is post-qualified, so the delta
    holds four Regions and no frontend-style suggestion key is used as world identity."""
    posts = {POST_A: fx.post(POST_A), POST_B: fx.post(POST_B)}
    _result, delta = _prepare(posts, task=_task(post_ids=(POST_A, POST_B)))

    assert delta.post_ids() == (POST_A, POST_B)
    assert delta.proposed_region_count() == 4
    assert len(set(delta.keys())) == 4
    assert ({r["id"] for r in delta.for_post(POST_A).proposed_regions}
            == {r["id"] for r in delta.for_post(POST_B).proposed_regions})
    assert validate_delta(delta) == []


def test_a_pointer_resolves_only_within_its_own_post(deterministic_sam):
    posts = {POST_A: fx.post(POST_A), POST_B: fx.post(POST_B)}
    _result, delta = _prepare(posts, task=_task(post_ids=(POST_A, POST_B)))
    for post_delta in delta.per_post:
        ids = {r["id"] for r in post_delta.proposed_regions}
        for descriptor in post_delta.suggestions:
            assert pointer_of(descriptor)[0] in ids


# ── availability is a word ───────────────────────────────────────────────────

def test_a_run_that_measured_nothing_reports_measured_absence(monkeypatch):
    """It ran, it looked, the concept is not there. An ANSWER, and not the same fact as an
    instrument that never started."""
    service = fx.EmptySam3Service()
    monkeypatch.setitem(importlib.sys.modules, "backend.services.sam3_concept_service", service)
    posts_mod = importlib.import_module("backend.routers.posts")

    async def _bytes(post_id, post):
        return b"fixture-image-bytes"
    monkeypatch.setattr(posts_mod, "_fetch_post_image_cached", _bytes)

    _result, delta = _prepare({POST_A: fx.post(POST_A)})
    assert delta.availability == MEASURED_ABSENCE
    assert delta.proposed_region_count() == 0
    assert not delta.has_usable_region()


def test_an_unavailable_instrument_reports_execution_unavailable_and_projects_no_region(
        monkeypatch):
    service = fx.UnavailableSam3Service()
    monkeypatch.setitem(importlib.sys.modules, "backend.services.sam3_concept_service", service)
    _result, delta = _prepare({POST_A: fx.post(POST_A)})
    assert delta.availability == EXECUTION_UNAVAILABLE
    assert delta.proposed_region_count() == 0
    assert delta.refusals


def test_a_task_naming_no_post_reports_planner_empty():
    _result, delta = _prepare({})
    assert delta.availability != AVAILABILITY_OK
    assert delta.per_post == ()


# ── suggestions only ─────────────────────────────────────────────────────────

def test_the_source_posts_are_byte_identical_afterwards(deterministic_sam):
    """Checked, not claimed. The delta's `posts_unchanged` is a fingerprint comparison."""
    import copy
    import json

    posts = {POST_A: fx.post(POST_A), POST_B: fx.post(POST_B)}
    before = copy.deepcopy(posts)
    _result, delta = _prepare(posts, task=_task(post_ids=(POST_A, POST_B)))

    assert delta.posts_unchanged is True
    assert json.dumps(posts, sort_keys=True) == json.dumps(before, sort_keys=True)
    assert posts[POST_A]["region_annotations"] == []
    assert posts[POST_A]["visual_marks"] == []


def test_no_database_write_method_is_called(deterministic_sam, monkeypatch):
    """The lane commits nothing. Any write would go through the posts collection, so the
    collection itself is replaced with something that raises on every attribute."""
    import backend.database as database

    class Explodes:
        def __getattr__(self, name):
            raise AssertionError(f"the handoff touched the database: posts_collection.{name}")

    monkeypatch.setattr(database, "posts_collection", Explodes(), raising=False)
    _result, delta = _prepare({POST_A: fx.post(POST_A)})
    assert delta.proposed_region_count() == 2


def test_the_adapter_satisfies_the_same_protocol_the_engine_already_calls(deterministic_sam):
    """`prepare()` returns a `PreparationResult`, so this drops into `run_inquiry` wherever the
    injected-registry adapter does — and the older adapter is KEPT, not replaced."""
    from backend.services.inquiry_engine.adapters import DirectorAdapter, PreparationResult

    adapter = ProductionDirectorAdapter()
    result = adapter.prepare(_task(), {POST_A: fx.post(POST_A)}, run_id=RUN, inquiry_id="inq_1",
                             evidence_goal_id="eg_1", now=NOW)
    assert isinstance(result, PreparationResult)
    assert result.ran is True
    assert len(result.suggestions) == 4
    assert adapter.last_delta is not None
    assert DirectorAdapter is not ProductionDirectorAdapter


def test_the_execution_context_loop_is_closed_after_every_post(deterministic_sam):
    """A borrowed loop left open leaks a file descriptor per post, and a corpus run would leak
    one per image."""
    import asyncio

    posts = {POST_A: fx.post(POST_A), POST_B: fx.post(POST_B)}
    created = []
    real_new_loop = asyncio.new_event_loop

    def _tracking():
        loop = real_new_loop()
        created.append(loop)
        return loop

    original = asyncio.new_event_loop
    asyncio.new_event_loop = _tracking
    try:
        _prepare(posts, task=_task(post_ids=(POST_A, POST_B)))
    finally:
        asyncio.new_event_loop = original
    assert created, "the capture builds an ExecutionContext, which owns a loop"
    assert all(loop.is_closed() for loop in created)
