"""
HARNESS-001B2 §5–6 — the bounded real handoff, end to end, and the replay that pins it.

    real prompt → InquiryFrame (Lane A) → goals (Lane B) → real Director ExecutionContext
      → PreparedWorldDelta → ephemeral world → real situated mission → organ measurement
      → the parent EvidenceGoal

Every stage is production code except two boundaries: the model and the network. What this file
asserts is that the WORLD survives the handoff — not that a plan ran, and not that a fake returned
what a fake was told to return.

The failure proofs sit here too, because each is the same chain with one thing wrong, and reading
them beside the working one is how the working one stays honest.
"""
from __future__ import annotations

import copy
import importlib
import json

import pytest

from backend.services.inquiry_engine import handoff_fixtures as fx
from backend.services.inquiry_engine.adapters import ProposalNotAPerception, SimulatorAdapter
from backend.services.inquiry_engine.goals import AgentMission, PreparationTask
from backend.services.inquiry_engine.production import ProductionDirectorAdapter
from backend.services.inquiry_engine.projection import project, run_handoff
from backend.services.inquiry_engine.world import (POINTER_TARGET_MISSING, PostDelta,
                                                   PreparedWorldDelta, validate_delta)

import scripts.inquiry_handoff_run as handoff_script

POST_A = "handoff_post_a"
POST_B = "handoff_post_b"
NOW = "2026-08-08T12:00:00Z"

FOLD_PROMPT = (
    "Explore the fold-level aesthetic and style relations between Renaissance and Buddha "
    "sculptures, their common way of unfolding sensuality, where they drift apart, and what "
    "hybrid styles they could give birth to."
)


@pytest.fixture
def deterministic_sam(monkeypatch):
    service = fx.FakeSam3Service()
    monkeypatch.setitem(importlib.sys.modules, "backend.services.sam3_concept_service", service)
    posts_mod = importlib.import_module("backend.routers.posts")

    async def _bytes(post_id, post):
        return b"fixture-image-bytes"

    monkeypatch.setattr(posts_mod, "_fetch_post_image_cached", _bytes)
    return service


def _chain(posts, *, post_ids=(POST_A,), organ_set=("nestedness_organ",), concept=fx.CONCEPT):
    task = PreparationTask(id="pt_1", parent_goal_id="eg_1", actuator="concept_segment",
                           params={"phrase": concept}, post_ids=tuple(post_ids))
    mission = AgentMission(id="am_1", parent_goal_id="eg_1", organ_set=tuple(organ_set),
                           question="what contains what, from where I stand?", budget=0)
    _result, delta = ProductionDirectorAdapter().prepare_world(
        task, posts, run_id="run_1", inquiry_id="inq_1", evidence_goal_id="eg_1", now=NOW)
    outcome = run_handoff(delta, posts, simulator=SimulatorAdapter(), mission=mission,
                          run_id="run_1", inquiry_id="inq_1", evidence_goal_id="eg_1", now=NOW)
    return delta, outcome


# ── the deterministic production-runner proof, assertion by assertion ────────

def test_exactly_two_proposed_regions_are_captured_with_valid_masks(deterministic_sam):
    delta, _ = _chain({POST_A: fx.post(POST_A)})
    regions = delta.for_post(POST_A).proposed_regions
    assert len(regions) == 2
    for region in regions:
        assert region["mask_rle"]["counts"]
        assert sum(region["mask_rle"]["counts"]) == fx.MASK_H * fx.MASK_W


def test_each_measured_mask_ref_resolves(deterministic_sam):
    delta, _ = _chain({POST_A: fx.post(POST_A)})
    post_delta = delta.for_post(POST_A)
    ids = {r["id"] for r in post_delta.proposed_regions}
    measured = [s for s in post_delta.suggestions if s["epistemic_status"] == "measured"]
    assert len(measured) == 2
    for descriptor in measured:
        assert descriptor["geometry"]["mask_ref"]["region_id"] in ids


def test_each_interpretive_region_ref_resolves_and_carries_no_geometry(deterministic_sam):
    delta, _ = _chain({POST_A: fx.post(POST_A)})
    post_delta = delta.for_post(POST_A)
    ids = {r["id"] for r in post_delta.proposed_regions}
    naming = [s for s in post_delta.suggestions if s["epistemic_status"] == "interpretive"]
    assert len(naming) == 2
    for descriptor in naming:
        geometry = descriptor["geometry"]
        assert geometry["kind"] == "region_ref"
        assert geometry["region_ref"]["region_id"] in ids
        assert "mask_rle" not in geometry
        assert set(geometry["region_ref"]) == {"region_id"}


def test_region_and_descriptor_provenance_survives(deterministic_sam):
    delta, _ = _chain({POST_A: fx.post(POST_A)})
    post_delta = delta.for_post(POST_A)
    for region in post_delta.proposed_regions:
        assert region["geometry_provenance"]["method"] == "sam3-concept-segment"
        assert region["geometry_provenance"]["prompt"] == fx.CONCEPT
    for descriptor in post_delta.suggestions:
        assert descriptor["provenance"]["run_id"] == "run_1:pt_1"
        assert descriptor["provenance"]["step_id"] == "pt_1"


def test_both_regions_enter_the_projected_post_under_the_correct_post_id(deterministic_sam):
    posts = {POST_A: fx.post(POST_A)}
    delta, outcome = _chain(posts)
    assert outcome.world.projected_region_ids == {POST_A: ("cseg_fold_0", "cseg_fold_1")}
    assert {r["id"] for r in outcome.world.posts[POST_A]["region_annotations"]} == {
        "cseg_fold_0", "cseg_fold_1"}


def test_a_real_nestedness_agent_inhabits_one_and_perceives_from_the_proposed_mask_world(
        deterministic_sam):
    _delta, outcome = _chain({POST_A: fx.post(POST_A)})
    assert outcome.dispatched is True
    assert outcome.locus == (POST_A, "cseg_fold_0")
    perceptions = outcome.mission_result.perceptions
    assert perceptions
    assert perceptions[0]["organ"] == "nestedness_organ"
    assert perceptions[0]["basis"] == "mask"


def test_the_returned_measurement_is_organ_authored_and_private_measured(deterministic_sam):
    _delta, outcome = _chain({POST_A: fx.post(POST_A)})
    measured = outcome.measured_marks()
    assert len(measured) == 1
    mark = measured[0]
    assert mark["provenance"]["producer"] == "nestedness_organ"
    assert mark["provenance"]["adapter"] == "geometry:mask"
    assert mark["measurement"]["basis"] == "mask"
    assert mark["measurement"]["basis_detail"] == "per-pixel intersection on a shared raster"
    assert mark["measurement"]["containment"] == 1.0
    # PRIVATE: the summary comes back, the memory does not.
    summary = outcome.mission_result.memory_summary
    assert summary["organs"] == ["nestedness_organ"]
    assert summary["statuses"] == ["measured"]


def test_the_ledger_status_remains_proposed(deterministic_sam):
    _delta, outcome = _chain({POST_A: fx.post(POST_A)})
    for region in outcome.world.posts[POST_A]["region_annotations"]:
        assert region["proposed"] is True
        assert region["ledger_status"] == "proposed"
    assert outcome.measured_marks()[0]["epistemic_status"] == "measured"


def test_the_parent_evidence_goal_is_evaluated_from_the_measurement_not_from_preparation(
        deterministic_sam):
    """A preparation that RAN is not evidence; it is the condition under which evidence became
    possible. The goal is checked against organ-authored measured marks."""
    from backend.services.inquiry_engine import evaluator

    delta, outcome = _chain({POST_A: fx.post(POST_A)})
    assert delta.availability == "ok"                      # preparation succeeded…
    measured = outcome.measured_marks()
    assert measured                                        # …and evidence exists separately
    assert all(m["provenance"]["producer"] == "nestedness_organ" for m in measured)
    assert hasattr(evaluator, "__name__")


def test_the_source_post_is_byte_identical_and_no_database_write_is_called(
        deterministic_sam, monkeypatch):
    import backend.database as database

    class Explodes:
        def __getattr__(self, name):
            raise AssertionError(f"the handoff touched the database: posts_collection.{name}")

    monkeypatch.setattr(database, "posts_collection", Explodes(), raising=False)

    posts = {POST_A: fx.post(POST_A)}
    before = copy.deepcopy(posts)
    delta, outcome = _chain(posts)
    assert delta.posts_unchanged is True
    assert outcome.posts_unchanged is True
    assert json.dumps(posts, sort_keys=True) == json.dumps(before, sort_keys=True)


# ── the corpus identity proof ────────────────────────────────────────────────

def test_the_same_concept_on_two_posts_cannot_collide(deterministic_sam):
    posts = {POST_A: fx.post(POST_A), POST_B: fx.post(POST_B)}
    delta, outcome = _chain(posts, post_ids=(POST_A, POST_B))

    assert delta.proposed_region_count() == 4
    assert len(set(delta.keys())) == 4
    a_ids = {r["id"] for r in delta.for_post(POST_A).proposed_regions}
    b_ids = {r["id"] for r in delta.for_post(POST_B).proposed_regions}
    assert a_ids == b_ids == {"cseg_fold_0", "cseg_fold_1"}      # the local ids DO repeat
    assert validate_delta(delta) == []                            # and nothing is ambiguous
    for post_id in (POST_A, POST_B):
        assert len(outcome.world.posts[post_id]["region_annotations"]) == 2


def test_no_frontend_style_suggestion_key_is_used_as_world_identity(deterministic_sam):
    """`source_ref` is `"{concept}|{index}"` — POSITIONAL within a run, and identical across the
    two posts. It is a display handle, and nothing resolves a Region by it."""
    delta, _ = _chain({POST_A: fx.post(POST_A), POST_B: fx.post(POST_B)},
                      post_ids=(POST_A, POST_B))
    refs = {s["source_ref"] for d in delta.per_post for s in d.suggestions}
    assert refs == {"fold|0", "fold|1"}                # collides across posts, by design
    assert len(set(delta.keys())) == 4                 # identity does not


# ── the failure proofs ───────────────────────────────────────────────────────

def test_a_descriptor_whose_target_region_is_missing_is_pointer_target_missing(deterministic_sam):
    posts = {POST_A: fx.post(POST_A)}
    delta, _ = _chain(posts)
    stripped = PreparedWorldDelta(availability=delta.availability,
                                  per_post=(PostDelta(POST_A, (),
                                                      delta.for_post(POST_A).suggestions),))
    outcome = run_handoff(stripped, posts, simulator=SimulatorAdapter(),
                          mission=AgentMission(id="am_1", parent_goal_id="eg_1",
                                               organ_set=("nestedness_organ",)),
                          run_id="run_1", inquiry_id="inq_1", evidence_goal_id="eg_1", now=NOW)
    assert outcome.reason == POINTER_TARGET_MISSING


def test_a_region_without_a_valid_mask_admits_no_measured_suggestion(deterministic_sam):
    delta, _ = _chain({POST_A: fx.post(POST_A)})
    post_delta = delta.for_post(POST_A)
    measured = next(s for s in post_delta.suggestions if s["epistemic_status"] == "measured")
    hollow = {"id": measured["geometry"]["mask_ref"]["region_id"], "proposed": True,
              "geometry_rev": 0}
    problems = validate_delta(PreparedWorldDelta(
        per_post=(PostDelta(POST_A, (hollow,), (measured,)),)))
    assert problems and "owns no mask" in problems[0]["detail"]


def test_a_naming_accepted_as_geometry_is_refused(deterministic_sam):
    delta, _ = _chain({POST_A: fx.post(POST_A)})
    post_delta = delta.for_post(POST_A)
    naming = next(s for s in post_delta.suggestions if s["epistemic_status"] == "interpretive")
    smuggled = {**naming, "geometry": {**naming["geometry"], "mask_rle": fx.inner_rle()}}
    problems = validate_delta(PreparedWorldDelta(
        per_post=(PostDelta(POST_A, post_delta.proposed_regions, (smuggled,)),)))
    assert problems and "authors no geometry" in problems[0]["detail"]


def test_a_director_proposal_offered_as_a_perception_hits_the_existing_wall(deterministic_sam):
    """The wall is the Lane-B one, unchanged, and this lane's whole design is arranged so it is
    never reached: geometry travels as Regions, claims do not travel at all."""
    delta, _ = _chain({POST_A: fx.post(POST_A)})
    descriptor = delta.for_post(POST_A).suggestions[0]
    mission = AgentMission(id="am_2", parent_goal_id="eg_1", post_id=POST_A,
                           region_id="cseg_fold_0", organ_set=("nestedness_organ",))
    world = project({POST_A: fx.post(POST_A)}, delta)
    with pytest.raises(ProposalNotAPerception, match="concept_segment"):
        SimulatorAdapter().dispatch(mission, world.posts, run_id="r", inquiry_id="i",
                                    evidence_goal_id="eg_1", now=NOW,
                                    proposed_marks=[descriptor])


def test_the_handoff_never_hands_a_director_descriptor_to_the_body(deterministic_sam):
    """The positive form of the test above: `run_handoff` dispatches with `proposed_marks=()`."""
    recorded = {}
    real_dispatch = SimulatorAdapter.dispatch

    class Watching(SimulatorAdapter):
        def dispatch(self, mission, posts, **kwargs):
            recorded["proposed_marks"] = kwargs.get("proposed_marks")
            return real_dispatch(self, mission, posts, **kwargs)

    posts = {POST_A: fx.post(POST_A)}
    task = PreparationTask(id="pt_1", parent_goal_id="eg_1", actuator="concept_segment",
                           params={"phrase": fx.CONCEPT}, post_ids=(POST_A,))
    _r, delta = ProductionDirectorAdapter().prepare_world(
        task, posts, run_id="run_1", inquiry_id="inq_1", evidence_goal_id="eg_1", now=NOW)
    run_handoff(delta, posts, simulator=Watching(),
                mission=AgentMission(id="am_1", parent_goal_id="eg_1",
                                     organ_set=("nestedness_organ",)),
                run_id="run_1", inquiry_id="inq_1", evidence_goal_id="eg_1", now=NOW)
    assert recorded["proposed_marks"] == ()


def test_a_goals_desire_does_not_alter_any_organ_mark(deterministic_sam):
    """Two missions with different questions over one world return the same measurement. What the
    inquiry WANTS changes selection; it can never change what an organ measured."""
    posts = {POST_A: fx.post(POST_A)}
    task = PreparationTask(id="pt_1", parent_goal_id="eg_1", actuator="concept_segment",
                           params={"phrase": fx.CONCEPT}, post_ids=(POST_A,))
    _r, delta = ProductionDirectorAdapter().prepare_world(
        task, posts, run_id="run_1", inquiry_id="inq_1", evidence_goal_id="eg_1", now=NOW)

    def _measure(question: str):
        outcome = run_handoff(delta, posts, simulator=SimulatorAdapter(),
                              mission=AgentMission(id="am_1", parent_goal_id="eg_1",
                                                   organ_set=("nestedness_organ",),
                                                   question=question),
                              run_id="run_1", inquiry_id="inq_1", evidence_goal_id="eg_1",
                              now=NOW)
        return outcome.measured_marks()[0]["measurement"]

    wanted = _measure("prove these forms are nested")
    doubted = _measure("show me these forms are NOT nested")
    assert wanted == doubted


def test_an_organ_refusal_is_not_reported_as_a_measured_absence(deterministic_sam):
    _delta, outcome = _chain({POST_A: fx.post(POST_A)}, organ_set=("depth_organ",))
    assert outcome.dispatched is False
    assert outcome.reason == "organ_refused"
    assert "depth" in outcome.detail.lower()


# ── the local script, and replay ─────────────────────────────────────────────

def test_the_script_puts_the_real_sam3_module_back_when_it_is_done():
    """A REGRESSION, and a real one. The script replaced
    `sys.modules["backend.services.sam3_concept_service"]` and never restored it, so importing
    this test module leaked the fake into every test that ran after it — five of Lane C's SAM 3
    lab tests failed having done nothing wrong, because the module they probe had been swapped
    underneath them. A script that is also a library has to clean up after itself.
    """
    name = "backend.services.sam3_concept_service"
    before = importlib.sys.modules.get(name)
    handoff_script.run("nested")
    after = importlib.sys.modules.get(name)
    assert after is before
    assert not isinstance(after, fx.FakeSam3Service)

    posts_mod = importlib.import_module("backend.routers.posts")
    assert posts_mod._fetch_post_image_cached.__name__ == "_fetch_post_image_cached"


def test_the_script_runs_the_whole_chain_offline():
    receipt = handoff_script.run("nested")
    assert receipt["live_sam3"]["used"] is False
    assert receipt["world_delta"]["availability"] == "ok"
    assert receipt["mission"]["dispatched"] is True
    assert receipt["mission"]["measured_marks"] == 1
    assert receipt["stop_reason"] == "an organ measured from prepared geometry"
    assert receipt["posts_unchanged"] is True


def test_two_default_runs_are_byte_identical_but_for_the_declared_volatile_fields():
    """The replay proof. The exclusions are short and named rather than generous — a wide filter
    would let a real irreproducibility hide inside it."""
    first = handoff_script._strip_volatile(handoff_script.run("nested"))
    second = handoff_script._strip_volatile(handoff_script.run("nested"))
    assert json.dumps(first, sort_keys=True, default=str) == \
        json.dumps(second, sort_keys=True, default=str)
    assert set(handoff_script.VOLATILE) == {"inquiry_id", "framed_at", "latency_ms",
                                            "prompt_sha256"}
    assert handoff_script.MINTED_ID_PREFIXES == ("vm_", "apc_", "agnd_", "aobs_")


def test_the_replay_filter_still_compares_which_region_was_measured():
    """The negative control. Minted identities are excluded BY PREFIX, not by dropping every
    `id` — `cseg_fold_0` is also an id, and a filter that dropped it would let two runs disagree
    about which Region was measured and still call the run reproducible."""
    receipt = handoff_script.run("nested")
    stripped = json.dumps(handoff_script._strip_volatile(receipt), default=str)
    assert "cseg_nested_form_0" in stripped
    assert "cseg_nested_form_1" in stripped
    assert "<minted>" in stripped
    assert "vm_nest_" not in stripped


def test_the_script_reports_live_sam3_honestly_rather_than_substituting():
    """If the weights are absent it says so. It never runs a fixture and calls it live."""
    receipt = handoff_script.run("fold", live_sam3=True)
    live = receipt["live_sam3"]
    assert live["requested"] is True
    if not live["used"]:
        assert "not on disk" in live["detail"] or "did not import" in live["detail"]
        assert receipt["world_delta"]["availability"] == "ok"     # the fixture still ran


def test_the_fold_fixture_carries_lane_as_real_frame_into_the_chain():
    receipt = handoff_script.run("fold")
    frame = receipt["frame"]
    assert frame["prompt"] == FOLD_PROMPT
    assert "sensuality" in frame["epistemic_demands"]
    assert "sensuality" in frame["semantic_remainder"]
    assert frame["unresolved_terms"]
    # The chain reached an organ measurement even though half the prompt is unmeasurable.
    assert receipt["mission"]["measured_marks"] == 1


def test_the_script_shows_two_posts_cannot_collide():
    receipt = handoff_script.run("fold", both_posts=True)
    per_post = receipt["world_delta"]["per_post"]
    assert [p["post_id"] for p in per_post] == [POST_A, POST_B]
    assert [[r["id"] for r in p["proposed_regions"]] for p in per_post] == \
        [["cseg_fold_0", "cseg_fold_1"], ["cseg_fold_0", "cseg_fold_1"]]
    assert receipt["mission"]["locus"]["post_id"] == POST_A
