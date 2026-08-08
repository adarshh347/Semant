"""
HARNESS-001B2 §5 — the bounded real handoff, end to end, and the replay.

    real InquiryFrame          `backend.services.inquiry.frame_prompt`, deterministic framer
      → InquiryGoal / EvidenceGoal
      → real Director ExecutionContext, real `_run_concept_segment`
      → PreparedWorldDelta with complete Regions AND the descriptors pointing into them
      → ephemeral projected post
      → real situated agent, real `nestedness_organ`
      → organ-authored evidence

Only SAM 3's model call is a fixture. Everything else on that path is the code that runs in
production, which is the difference between proving the bridge and proving a stand-in.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib

import pytest

from backend.services import mask_geometry as mg
from backend.services import nestedness_organ as nest
from backend.services import sam3_concept_service as sam3
from backend.services.epistemics import STATUS_KEY
from backend.services.inquiry import frame_prompt
from backend.services.inquiry_engine import engine as eng
from backend.services.inquiry_engine.frame import accept
from backend.services.inquiry_engine.goals import (KIND_MISSION, KIND_PREPARATION, AgentMission,
                                                   PreparationTask)
from backend.services.inquiry_engine.handoff import evidence_provenance, run_handoff
from backend.services.inquiry_engine.production import ProductionDirectorAdapter
from backend.services.inquiry_engine.world import (EXECUTION_UNAVAILABLE, NO_LOCUS,
                                                   POINTER_TARGET_MISSING, PostDelta,
                                                   PreparedWorldDelta, ProposedRegion)
from backend.services.movement_kernel import posts_fingerprint

N = 16
STAMP = "2026-08-08T00:00:00+00:00"
INNER = (5, 11, 6, 12)
OUTER = (2, 14, 2, 15)

NESTED_PROMPT = ("Segment every fold in this sculpture and tell me which one sits inside which, "
                 "measured on the masks.")


def _rle(x0, x1, y0, y1):
    bits = [0] * (N * N)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * N + x] = 1
    return mg.rle_encode(bits, N, N)


@pytest.fixture()
def fake_sam3(monkeypatch):
    """ONLY the model. `_run_concept_segment`, `instances_to_regions`, the suggestion conversion
    and every context write are production."""
    def _segment_concept(image, concept, **kwargs):
        return {"concept": concept, "device": "fixture", "model": "sam3-fixture",
                "latency_ms": 0.0, "truncated": False,
                "instances": [{"mask_rle": _rle(*INNER), "confidence": 0.91, "index": 0},
                              {"mask_rle": _rle(*OUTER), "confidence": 0.84, "index": 1}]}

    monkeypatch.setattr(sam3, "segment_concept", _segment_concept)
    monkeypatch.setattr(sam3, "load", lambda **_: None)
    monkeypatch.setattr(sam3, "is_available", lambda: True)

    import backend.routers.posts as posts_router

    async def _fetch(post_id, post):
        return b"fixture-bytes"
    monkeypatch.setattr(posts_router, "_fetch_post_image_cached", _fetch)


@pytest.fixture()
def posts():
    return {"post_renaissance": {"_id": "post_renaissance", "photo_url": "https://x.invalid/r.jpg",
                                 "title": "Pietà", "region_annotations": []},
            "post_buddha": {"_id": "post_buddha", "photo_url": "https://x.invalid/b.jpg",
                            "title": "Seated Buddha", "region_annotations": []}}


def _vertical(posts, *, prompt=NESTED_PROMPT, region_id="", director=None):
    """The whole chain, from a real prompt to a returned organ mark."""
    frame = frame_prompt(prompt, {"post_ids": list(posts)})
    accepted = accept(frame.model_dump())
    inquiry, goals, _notes = eng.derive(accepted, ids=eng._Ids(run_id="handoff"),
                                        post_id="post_renaissance")
    target = next(g for g in goals if g.need == "extent_of_a_named_thing")
    task = PreparationTask(id="pt_concept", kind=KIND_PREPARATION, actuator="concept_segment",
                           params={"phrase": target.phrase}, post_ids=("post_renaissance",),
                           parent_goal_id=target.id)
    mission = AgentMission(id="am_nested", kind=KIND_MISSION, post_id="post_renaissance",
                           region_id=region_id, organ_set=(nest.ORGAN,),
                           parent_goal_id=target.id)
    handoff = run_handoff(task, mission, posts, run_id="handoff", inquiry_id=frame.inquiry_id,
                          evidence_goal_id=target.id,
                          director=director or ProductionDirectorAdapter(),
                          phrase=target.phrase, now=STAMP)
    return frame, inquiry, target, handoff


# ── 1. the vertical closes ───────────────────────────────────────────────────

def test_the_whole_chain_closes_from_a_real_frame_to_an_organ_authored_mark(fake_sam3, posts):
    """THE PROOF THE LANE EXISTS FOR."""
    _frame, _inquiry, _goal, handoff = _vertical(posts)

    assert handoff.usable is True
    assert handoff.delta.region_count == 2
    assert handoff.mission.dispatched is True
    assert handoff.reasons == ()

    marks = handoff.mission.marks
    assert marks, "no organ mark came back"
    mark = marks[0]
    assert mark["provenance"]["producer"] == nest.ORGAN         # the ORGAN authored it
    assert mark[STATUS_KEY] == "measured"                       # on its own word
    assert mark["measurement"]["basis"] == "mask"               # from real geometry


def test_the_concept_handed_to_the_finder_is_the_curators_word_and_not_a_ui_label(fake_sam3,
                                                                                  posts):
    """`phrase` falls back to a grammar `label` — "Brush fold" — and that would become the
    segmentation query, with the regions named `cseg_Brush_fold_0` and nothing failing anywhere."""
    _frame, _inquiry, goal, handoff = _vertical(posts)
    assert goal.phrase == "fold"
    assert all(r.id.startswith("cseg_fold_") for r in handoff.delta.per_post[0].proposed_regions)


def test_the_measurement_is_of_the_two_masks_the_model_actually_proposed(fake_sam3, posts):
    """Not merely 'a nesting' — the containment has to be BETWEEN the two prepared regions, or the
    agent measured something the preparation did not put there."""
    _frame, _inquiry, _goal, handoff = _vertical(posts)
    prepared = {r.id for r in handoff.delta.per_post[0].proposed_regions}
    reading = handoff.mission.perceptions[0]
    assert reading["locus_region_id"] in prepared
    assert reading["other_region_id"] in prepared
    assert reading["relation"] == "nested_within"


def test_the_parent_evidence_goal_is_evaluated_from_that_measurement(fake_sam3, posts):
    """Goal evaluation operates on RETURNED ORGAN EVIDENCE, not on preparation completion."""
    from backend.services.inquiry_engine import evaluator as ev
    from backend.services.inquiry_engine.events import Evidence
    from backend.services.inquiry_engine.goals import Criterion, EvidenceGoal, KIND_EVIDENCE

    _frame, _inquiry, _goal, handoff = _vertical(posts)
    criterion = Criterion(id="c1", clause="containment is measured on masks",
                          demands="measured", relation="nested_within", basis="mask",
                          produced_by=(nest.ORGAN,))
    goal = EvidenceGoal(id="eg_nested", kind=KIND_EVIDENCE, criteria=(criterion,))
    evidence = [Evidence.of_mark(m, evidence_id=f"evd_{i}", goal_id="eg_nested")
                for i, m in enumerate(handoff.mission.marks)]

    verdict = ev.evaluate(goal, evidence)
    ev.assert_not_satisfied_without_evidence(verdict)
    assert verdict.status == "satisfied"
    assert verdict.clauses[0].evidence_ids


def test_evidence_cites_the_mission_and_the_preparation_that_made_its_locus(fake_sam3, posts):
    _frame, _inquiry, goal, handoff = _vertical(posts)
    cited = evidence_provenance(handoff)
    assert cited["mission_id"] == "am_nested"
    assert cited["preparation_task_id"] == "pt_concept"
    assert cited["evidence_goal_id"] == goal.id
    assert cited["locus"]["region_id"].startswith("cseg_fold_")


# ── 2. the source posts and the database are untouched ───────────────────────

def test_the_source_posts_are_byte_identical_after_the_whole_vertical(fake_sam3, posts):
    before = posts_fingerprint(posts)
    _vertical(posts)
    assert posts_fingerprint(posts) == before


def test_no_database_write_method_is_called_anywhere_on_the_path(fake_sam3, posts, monkeypatch):
    """Structural AND behavioural. The scan below has a negative control; this one is the real
    check — a write method that fires makes the test fail with the call in the message."""
    calls = []

    class _Tripwire:
        def __getattr__(self, name):
            def _boom(*a, **kw):
                calls.append(name)
                raise AssertionError(f"a run called {name}() on a collection")
            return _boom

    import backend.database as db
    for attr in ("post_collection", "run_collection", "agent_observation_collection",
                 "region_embeddings_collection"):
        if hasattr(db, attr):
            monkeypatch.setattr(db, attr, _Tripwire(), raising=False)

    _vertical(posts)
    assert calls == []


def test_the_handoff_modules_reference_no_collection_and_the_scan_can_fail():
    """The structural half, with its negative control — a scan that matches nothing is
    indistinguishable from a scan pointed at the wrong directory."""
    from backend.services import run_store

    package = pathlib.Path(eng.__file__).parent
    scanned = 0
    for path in sorted(package.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        scanned += 1
        for token in ("insert_one", "update_one", "delete_one", "get_collection"):
            assert token not in source, f"{path.name} references {token!r}"
    assert scanned >= 10, f"the scan only saw {scanned} module(s)"

    # The control: `run_store` DOES write, so a scanner that finds nothing there is broken.
    control = pathlib.Path(run_store.__file__).read_text(encoding="utf-8")
    assert "insert_one" in control and "update_one" in control


# ── 3. the failure paths stay decomposed ─────────────────────────────────────

def test_a_descriptor_with_a_missing_target_never_reaches_a_mission(posts):
    """`pointer_target_missing`, and the mission is NOT dispatched: an agent perceiving from a
    half-built world would return real readings of a world nobody made."""
    class _Broken(ProductionDirectorAdapter):
        def prepare(self, task, posts, **kwargs):
            from backend.services import suggestion_service as ss
            result = {"concept": "fold", "instances": [
                {"mask_rle": _rle(*INNER), "confidence": 0.9, "index": 0}]}
            sam3.instances_to_regions(result)
            suggestions = ss.suggestions_from_concept_segments([result], run_id="r")
            from backend.services.inquiry_engine.world import validate_delta
            validate_delta(PreparedWorldDelta(          # regions withheld → the pointer dangles
                task_id=task.id, evidence_goal_id="eg", run_id="r", step_id=task.id,
                per_post=(PostDelta(post_id="post_renaissance", proposed_regions=(),
                                    suggestions=tuple(suggestions)),)))

    task = PreparationTask(id="pt", kind=KIND_PREPARATION, actuator="concept_segment",
                           params={"phrase": "fold"}, post_ids=("post_renaissance",))
    mission = AgentMission(id="am", kind=KIND_MISSION, post_id="post_renaissance",
                           region_id="", organ_set=(nest.ORGAN,))
    handoff = run_handoff(task, mission, posts, run_id="r", inquiry_id="i",
                          evidence_goal_id="eg", director=_Broken(), phrase="fold", now=STAMP)
    assert handoff.reasons == (POINTER_TARGET_MISSING,)
    assert handoff.mission is None
    assert handoff.usable is False


def test_an_unavailable_model_produces_no_projection_and_says_execution_unavailable(posts):
    """No SAM 3 weights on this machine, probe left alone. The real availability gate fires."""
    _frame, _inquiry, _goal, handoff = _vertical(posts)
    assert handoff.delta is not None and handoff.delta.region_count == 0
    assert EXECUTION_UNAVAILABLE in handoff.reasons
    assert handoff.mission is None
    assert handoff.usable is False


def test_a_locus_that_resolves_to_nothing_is_no_locus_and_not_an_organ_refusal(fake_sam3, posts):
    _frame, _inquiry, _goal, handoff = _vertical(posts, region_id="a_region_nobody_made")
    assert NO_LOCUS in handoff.reasons
    assert handoff.mission is None
    assert handoff.delta.region_count == 2, "the preparation succeeded; only the locus was wrong"


def test_the_six_reasons_are_never_flattened_before_the_stop_event():
    from backend.services.inquiry_engine.world import HANDOFF_REASONS
    assert set(HANDOFF_REASONS) == {"measured_absence", "planner_empty", "execution_unavailable",
                                    "pointer_target_missing", "no_locus", "organ_refused"}
    assert "no_new_evidence" not in HANDOFF_REASONS


def test_a_goal_does_not_alter_any_organ_mark(fake_sam3, posts):
    """The bright line, carried through the new path: the same projected world measured with and
    without an inquiry behind it yields byte-identical marks."""
    from backend.services.agents import situated_agent as sa
    from backend.services.inquiry_engine.world import project_world

    _frame, _inquiry, _goal, handoff = _vertical(posts)
    through_goal = [{k: v for k, v in m.items() if k != "id"} for m in handoff.mission.marks]

    projected = project_world(posts, handoff.delta)
    agent = sa.inhabit(agent_id="plain", post_id="post_renaissance",
                       region_id=handoff.locus[1], organ_set=(nest.ORGAN,))
    sa.perceive(agent, projected["post_renaissance"], now=STAMP)
    direct = [{k: v for k, v in p.mark.items() if k != "id"} for p in agent.percept_field]

    assert direct, "the comparison would be vacuous"
    assert json.dumps(direct, sort_keys=True) == json.dumps(through_goal, sort_keys=True)


# ── 4. the local script, and replay ──────────────────────────────────────────

def _script():
    spec = importlib.util.spec_from_file_location(
        "inquiry_handoff_run",
        pathlib.Path(__file__).resolve().parents[2] / "scripts" / "inquiry_handoff_run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)                    # type: ignore[union-attr]
    return module


@pytest.mark.parametrize("fixture", ["nested", "fold"])
def test_the_script_runs_each_fixture_and_emits_the_whole_chain(tmp_path, fixture):
    module = _script()
    out = tmp_path / f"{fixture}.json"
    assert module.main(["--fixture", fixture, "--summary", "--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    for key in ("frame", "goals", "handoff", "evidence_provenance", "stop_reason"):
        assert key in payload, f"the run does not report {key}"
    assert payload["handoff"]["posts_unchanged"] is True


def test_two_default_runs_are_byte_identical_apart_from_environment_fields():
    """Replay. The ids are content-derived, the stamp is the fixture's, and the only fields allowed
    to move are the ones that measure the machine rather than the run."""
    module = _script()
    first = module._scrub(module.run("nested", live=False))
    second = module._scrub(module.run("nested", live=False))
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_the_exclusions_are_three_named_classes_and_no_wider():
    """Lane A's rule for its own byte-stability helper, applied here: *exclude exactly these and
    nothing else — excluding more would let a real drift hide inside the exclusion list.*"""
    from backend.schemas.inquiry import VOLATILE_FIELDS

    module = _script()
    assert set(module.ENV_FIELDS) == {"latency_ms", "device"}
    assert module.VOLATILE_FIELDS == VOLATILE_FIELDS            # imported, not restated
    assert set(module.MINTED_ID_PREFIXES) == {"vm_nest_", "apc_", "agnd_", "aobs_"}


def test_the_deterministic_region_ids_are_NOT_excluded():
    """The exclusion that would have been easy and wrong. A proposed region's id is `cseg_fold_0`,
    deterministic, and load-bearing for the whole identity rule — dropping every `id` would hide
    exactly the drift this replay exists to catch."""
    module = _script()
    scrubbed = json.dumps(module._scrub(module.run("nested", live=False)))
    assert "cseg_fold_0" in scrubbed and "cseg_fold_1" in scrubbed


def test_the_unscrubbed_run_really_does_contain_what_is_excluded():
    """The negative control for the exclusion: if the scrub removed nothing, 'identical apart from
    these' would be a claim about an empty set."""
    module = _script()
    raw = json.dumps(module.run("nested", live=False))
    scrubbed = json.dumps(module._scrub(module.run("nested", live=False)))
    for token in ("latency_ms", "inquiry_id", "vm_nest_"):
        assert token in raw, f"the fixture no longer produces {token}"
        assert token not in scrubbed, f"{token} survived the scrub"


def test_live_mode_reports_unavailable_rather_than_substituting_the_fixture():
    """The one substitution the directive names outright. A fake reported as live would be
    undetectable in the output."""
    module = _script()
    if sam3.is_available():
        pytest.skip("SAM 3 weights are present on this machine; the unavailable path cannot run")
    payload = module.run("nested", live=True)
    assert payload["available"] is False
    assert payload["stop_reason"] == "execution_unavailable"
    assert "handoff" not in payload, "a live run with no weights produced a handoff anyway"
