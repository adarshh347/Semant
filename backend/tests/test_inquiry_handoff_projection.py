"""
HARNESS-001B2 §3–4 — the ephemeral world, and what a mission may take from it.

The projection is the explicit bridge from global preparation to local situatedness, and it is
the place where two rulings meet:

  · a proposed measured mask MAY support an agent's private measurement (private-vs-ledger);
  · it does NOT become curator-committed, and its ledger status stays `proposed`.

Both are asserted here, because either one alone is a different and wrong system: without the
first, prepared geometry is useless to a body; without the second, running an inquiry would
quietly accept evidence.
"""
from __future__ import annotations

import copy
import importlib
import json

import pytest

from backend.services.inquiry_engine import handoff_fixtures as fx
from backend.services.inquiry_engine.adapters import SimulatorAdapter
from backend.services.inquiry_engine.goals import AgentMission, PreparationTask
from backend.services.inquiry_engine.production import ProductionDirectorAdapter
from backend.services.inquiry_engine.projection import (REGIONS_KEY, HandoffOutcome, choose_locus,
                                                        project, run_handoff)
from backend.services.inquiry_engine.world import (EXECUTION_UNAVAILABLE, MEASURED_ABSENCE,
                                                   NO_LOCUS, ORGAN_REFUSED,
                                                   POINTER_TARGET_MISSING, PostDelta,
                                                   PreparedWorldDelta)

POST = "handoff_post_a"
NOW = "2026-08-08T12:00:00Z"


@pytest.fixture
def deterministic_sam(monkeypatch):
    service = fx.FakeSam3Service()
    monkeypatch.setitem(importlib.sys.modules, "backend.services.sam3_concept_service", service)
    posts_mod = importlib.import_module("backend.routers.posts")

    async def _bytes(post_id, post):
        return b"fixture-image-bytes"

    monkeypatch.setattr(posts_mod, "_fetch_post_image_cached", _bytes)
    return service


def _task(post_ids=(POST,)):
    return PreparationTask(id="pt_1", parent_goal_id="eg_1", actuator="concept_segment",
                           params={"phrase": fx.CONCEPT}, post_ids=tuple(post_ids))


def _prepared(posts, task=None):
    return ProductionDirectorAdapter().prepare_world(
        task or _task(), posts, run_id="run_1", inquiry_id="inq_1", evidence_goal_id="eg_1",
        now=NOW)[1]


def _mission(**over):
    base = dict(id="am_1", parent_goal_id="eg_1", organ_set=("nestedness_organ",),
                question="what contains what, here?", budget=0)
    base.update(over)
    return AgentMission(**base)


# ── 1. the projection ────────────────────────────────────────────────────────

def test_proposed_regions_land_where_an_organ_will_look(deterministic_sam):
    """An organ reads `post['region_annotations']` and nothing else. That is the whole bridge."""
    posts = {POST: fx.post(POST)}
    world = project(posts, _prepared(posts))
    ids = {r["id"] for r in world.posts[POST][REGIONS_KEY]}
    assert ids == {"cseg_fold_0", "cseg_fold_1"}
    assert world.projected_region_ids[POST] == ("cseg_fold_0", "cseg_fold_1")


def test_the_source_mapping_is_never_mutated(deterministic_sam):
    posts = {POST: fx.post(POST)}
    before = copy.deepcopy(posts)
    delta = _prepared(posts)
    project(posts, delta)
    assert json.dumps(posts, sort_keys=True) == json.dumps(before, sort_keys=True)
    assert posts[POST][REGIONS_KEY] == []


def test_the_copy_is_deep_enough_that_writing_a_projected_region_cannot_reach_the_source(
        deterministic_sam):
    """A shallow copy would let an organ's canonicalisation write through into the committed post,
    which is exactly what `posts_unchanged` exists to prevent."""
    committed = fx.committed_region()
    posts = {POST: fx.post(POST, regions=[committed])}
    world = project(posts, _prepared(posts))
    world.posts[POST][REGIONS_KEY][0]["label"] = "scribbled on"
    world.posts[POST][REGIONS_KEY].append({"id": "invented"})
    assert posts[POST][REGIONS_KEY][0]["label"] == "committed"
    assert len(posts[POST][REGIONS_KEY]) == 1


def test_geometry_and_its_provenance_survive_the_projection_unchanged(deterministic_sam):
    posts = {POST: fx.post(POST)}
    delta = _prepared(posts)
    world = project(posts, delta)
    source = {r["id"]: r for r in delta.for_post(POST).proposed_regions}
    for region in world.posts[POST][REGIONS_KEY]:
        original = source[region["id"]]
        assert region["mask_rle"] == original["mask_rle"]
        assert region["geometry_rev"] == original["geometry_rev"]
        assert region["geometry_provenance"] == original["geometry_provenance"]


def test_a_projected_region_keeps_its_ledger_status_proposed(deterministic_sam):
    """The measurement may be real and the AGREEMENT is still absent. A Region entering an agent's
    world without this would be indistinguishable from one a curator accepted."""
    posts = {POST: fx.post(POST)}
    world = project(posts, _prepared(posts))
    for region in world.posts[POST][REGIONS_KEY]:
        assert region["proposed"] is True
        assert region["ledger_status"] == "proposed"


def test_a_committed_region_is_left_exactly_as_it_was(deterministic_sam):
    committed = fx.committed_region()
    posts = {POST: fx.post(POST, regions=[committed])}
    world = project(posts, _prepared(posts))
    kept = next(r for r in world.posts[POST][REGIONS_KEY] if r["id"] == committed["id"])
    assert kept["proposed"] is False
    assert "ledger_status" not in kept
    assert len(world.posts[POST][REGIONS_KEY]) == 3


def test_a_proposal_colliding_with_a_committed_region_is_refused_not_substituted():
    """The committed Region wins. Replacing it would put an unaccepted extent under an accepted
    id, and every later reading would be about a different shape."""
    committed = fx.committed_region(region_id="cseg_fold_0")
    posts = {POST: fx.post(POST, regions=[committed])}
    conflicting = {"id": "cseg_fold_0", "mask_rle": fx.inner_rle(), "proposed": True,
                   "geometry_rev": 0}
    delta = PreparedWorldDelta(per_post=(PostDelta(POST, (conflicting,)),))
    world = project(posts, delta)
    kept = next(r for r in world.posts[POST][REGIONS_KEY] if r["id"] == "cseg_fold_0")
    assert kept["mask_rle"] == committed["mask_rle"]
    assert world.refusals
    assert world.refusals[0]["reason"] == POINTER_TARGET_MISSING
    assert "committed one stands" in world.refusals[0]["detail"]


def test_an_interpretive_naming_contributes_no_geometry_to_the_world(deterministic_sam):
    """An organ that could read a naming would be measuring a word. Only Regions become loci; the
    four descriptors are carried in the delta and none of them becomes a region annotation."""
    posts = {POST: fx.post(POST)}
    delta = _prepared(posts)
    world = project(posts, delta)
    assert len(delta.for_post(POST).suggestions) == 4
    assert len(world.posts[POST][REGIONS_KEY]) == 2
    assert world.posts[POST]["visual_marks"] == []


def test_a_delta_for_a_post_that_was_not_handed_over_is_refused_by_name(deterministic_sam):
    posts = {POST: fx.post(POST)}
    delta = _prepared(posts)
    world = project({"someone_else": fx.post("someone_else")}, delta)
    assert world.refusals
    assert world.refusals[0]["reason"] == NO_LOCUS


def test_two_posts_carrying_the_same_local_id_project_into_two_worlds(deterministic_sam):
    """The corpus identity proof, at the projection. SAM 3 mints `cseg_fold_0` on both images;
    under a global key one would shadow the other and an agent on post B would stand on post A's
    mask. Every resolution is post-qualified, so each world holds its own two."""
    posts = {POST: fx.post(POST), "post_b": fx.post("post_b")}
    delta = _prepared(posts, _task(post_ids=(POST, "post_b")))
    world = project(posts, delta)

    assert set(world.loci(POST)) == set(world.loci("post_b")) == {"cseg_fold_0", "cseg_fold_1"}
    assert len(world.posts[POST][REGIONS_KEY]) == 2
    assert len(world.posts["post_b"][REGIONS_KEY]) == 2
    # Two distinct Region objects, not one shared between the worlds — a merged projection would
    # let a write on one post's locus be visible from the other.
    a_region = next(r for r in world.posts[POST][REGIONS_KEY] if r["id"] == "cseg_fold_0")
    b_region = next(r for r in world.posts["post_b"][REGIONS_KEY] if r["id"] == "cseg_fold_0")
    assert a_region is not b_region


# ── 2. choosing where to stand ───────────────────────────────────────────────

def test_the_locus_prefers_a_region_this_preparation_added(deterministic_sam):
    committed = fx.committed_region()
    posts = {POST: fx.post(POST, regions=[committed])}
    delta = _prepared(posts)
    world = project(posts, delta)
    assert choose_locus(world, delta) == (POST, "cseg_fold_0")


def test_an_explicit_locus_is_honoured(deterministic_sam):
    posts = {POST: fx.post(POST)}
    delta = _prepared(posts)
    world = project(posts, delta)
    assert choose_locus(world, delta, post_id=POST, region_id="cseg_fold_1") == (POST,
                                                                                 "cseg_fold_1")


def test_a_world_with_nothing_to_stand_on_yields_no_locus():
    delta = PreparedWorldDelta(per_post=(PostDelta(POST, ()),))
    world = project({POST: fx.post(POST)}, delta)
    assert choose_locus(world, delta) == ("", "")


# ── 3. the mission return ────────────────────────────────────────────────────

def test_a_real_agent_measures_from_the_proposed_masks(deterministic_sam):
    """THE VERTICAL PROOF, in one test: a real `nestedness_organ` agent stands on a Region that
    exists only because a preparation proposed it, and returns a per-pixel MASK measurement."""
    posts = {POST: fx.post(POST)}
    delta = _prepared(posts)
    outcome = run_handoff(delta, posts, simulator=SimulatorAdapter(), mission=_mission(),
                          run_id="run_1", inquiry_id="inq_1", evidence_goal_id="eg_1", now=NOW)

    assert outcome.dispatched is True
    assert outcome.reason == ""
    assert outcome.locus == (POST, "cseg_fold_0")
    measured = outcome.measured_marks()
    assert len(measured) == 1
    mark = measured[0]
    assert mark["provenance"]["producer"] == "nestedness_organ"
    assert mark["measurement"]["basis"] == "mask"
    assert mark["measurement"]["nested"] is True
    assert mark["measurement"]["inner_region_id"] == "cseg_fold_1"
    assert mark["measurement"]["outer_region_id"] == "cseg_fold_0"


def test_the_returned_measurement_is_organ_authored_and_never_the_directors(deterministic_sam):
    """A Director descriptor never becomes a perception. The delta carries GEOMETRY the organ may
    measure for itself; it does not carry claims the agent may believe."""
    posts = {POST: fx.post(POST)}
    delta = _prepared(posts)
    outcome = run_handoff(delta, posts, simulator=SimulatorAdapter(), mission=_mission(),
                          run_id="run_1", inquiry_id="inq_1", evidence_goal_id="eg_1", now=NOW)
    producers = {m["provenance"]["producer"] for m in outcome.organ_marks}
    assert producers == {"nestedness_organ"}
    assert "concept_segment" not in producers
    assert "concept_naming" not in producers


def test_the_ledger_status_stays_proposed_while_the_measurement_is_real(deterministic_sam):
    """Both halves of the ruling, in one assertion each. The measurement is `measured` because an
    organ computed it off a real mask; the Region is `proposed` because nobody agreed to it."""
    posts = {POST: fx.post(POST)}
    delta = _prepared(posts)
    outcome = run_handoff(delta, posts, simulator=SimulatorAdapter(), mission=_mission(),
                          run_id="run_1", inquiry_id="inq_1", evidence_goal_id="eg_1", now=NOW)
    assert outcome.measured_marks()[0]["epistemic_status"] == "measured"
    for region in outcome.world.posts[POST][REGIONS_KEY]:
        assert region["ledger_status"] == "proposed"


def test_the_source_posts_are_byte_identical_after_a_dispatched_mission(deterministic_sam):
    posts = {POST: fx.post(POST)}
    before = copy.deepcopy(posts)
    delta = _prepared(posts)
    outcome = run_handoff(delta, posts, simulator=SimulatorAdapter(), mission=_mission(),
                          run_id="run_1", inquiry_id="inq_1", evidence_goal_id="eg_1", now=NOW)
    assert outcome.posts_unchanged is True
    assert json.dumps(posts, sort_keys=True) == json.dumps(before, sort_keys=True)


def test_the_outcome_serialises(deterministic_sam):
    posts = {POST: fx.post(POST)}
    outcome = run_handoff(_prepared(posts), posts, simulator=SimulatorAdapter(),
                          mission=_mission(), run_id="run_1", inquiry_id="inq_1",
                          evidence_goal_id="eg_1", now=NOW)
    payload = outcome.to_dict()
    assert payload["dispatched"] is True
    assert payload["measured_marks"] == 1
    assert payload["locus"] == {"post_id": POST, "region_id": "cseg_fold_0"}
    json.dumps(payload, default=str)          # must not raise


# ── 4. the decomposed reasons ────────────────────────────────────────────────

def test_a_pointer_with_no_target_stops_the_mission_by_name(deterministic_sam):
    posts = {POST: fx.post(POST)}
    delta = _prepared(posts)
    stripped = PreparedWorldDelta(
        availability=delta.availability,
        per_post=(PostDelta(POST, (), delta.for_post(POST).suggestions),))
    outcome = run_handoff(stripped, posts, simulator=SimulatorAdapter(), mission=_mission(),
                          run_id="run_1", inquiry_id="inq_1", evidence_goal_id="eg_1", now=NOW)
    assert outcome.dispatched is False
    assert outcome.reason == POINTER_TARGET_MISSING
    assert "nothing under it" in outcome.detail


def test_a_measured_absence_is_not_reported_as_an_unavailable_instrument(monkeypatch):
    service = fx.EmptySam3Service()
    monkeypatch.setitem(importlib.sys.modules, "backend.services.sam3_concept_service", service)
    posts_mod = importlib.import_module("backend.routers.posts")

    async def _bytes(post_id, post):
        return b"x"
    monkeypatch.setattr(posts_mod, "_fetch_post_image_cached", _bytes)

    posts = {POST: fx.post(POST)}
    outcome = run_handoff(_prepared(posts), posts, simulator=SimulatorAdapter(),
                          mission=_mission(), run_id="run_1", inquiry_id="inq_1",
                          evidence_goal_id="eg_1", now=NOW)
    assert outcome.dispatched is False
    assert outcome.reason == MEASURED_ABSENCE


def test_an_unavailable_instrument_projects_no_region_and_says_so(monkeypatch):
    service = fx.UnavailableSam3Service()
    monkeypatch.setitem(importlib.sys.modules, "backend.services.sam3_concept_service", service)
    posts = {POST: fx.post(POST)}
    outcome = run_handoff(_prepared(posts), posts, simulator=SimulatorAdapter(),
                          mission=_mission(), run_id="run_1", inquiry_id="inq_1",
                          evidence_goal_id="eg_1", now=NOW)
    assert outcome.dispatched is False
    assert outcome.reason == EXECUTION_UNAVAILABLE
    assert outcome.world is None          # nothing was projected at all


def test_an_organ_that_refuses_the_locus_is_reported_as_a_refusal_not_as_a_quiet_place(
        deterministic_sam):
    """`chroma_organ` reads the signal and none was handed to this invocation. "The organ refused"
    and "the organ measured nothing" are different facts about a locus."""
    posts = {POST: fx.post(POST)}
    delta = _prepared(posts)
    outcome = run_handoff(delta, posts, simulator=SimulatorAdapter(),
                          mission=_mission(organ_set=("chroma_organ",)),
                          run_id="run_1", inquiry_id="inq_1", evidence_goal_id="eg_1", now=NOW)
    assert outcome.dispatched is False
    assert outcome.reason == ORGAN_REFUSED
    assert outcome.detail


def test_the_six_reasons_are_never_flattened_here():
    """§4: do not collapse to `no_new_evidence` until the top-level stop event. This module is not
    that event, so every reason it can emit is one of the six named ones."""
    from backend.services.inquiry_engine import world as world_mod
    emitted = {MEASURED_ABSENCE, EXECUTION_UNAVAILABLE, POINTER_TARGET_MISSING, NO_LOCUS,
               ORGAN_REFUSED}
    assert emitted <= set(world_mod.DELTA_REFUSALS)
    assert HandoffOutcome(False, "").reason == ""
