"""HARNESS-001C — the single-actuator lab, proved on fakes.

NO MODEL, NO GPU, NO NETWORK. A fake SAM service and a fake planner client stand in for the
instruments, so the whole harness — firewall, all four arms, schemas, artifacts — runs in the
ordinary PR gate. The live SAM 3 run is a separate, reported thing; it is not what makes these
tests pass, and a green suite here is explicitly NOT a claim that the organ works.

WHAT IS BEING TESTED IS THE LAB, NOT THE ORGAN. Every assertion below is about whether the
harness records honestly: whether it refuses what it should, records what it refuses,
distinguishes empty from unavailable from error, and declines to certify a mask it cannot
check. A lab that measured a good organ badly would look identical to one that measured a bad
organ well, from the outside, which is why these come first.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import single_actuator_lab as lab                                        # noqa: E402
from single_actuator_lab_support import (arms, contract, firewall as fw,  # noqa: E402
                                         observe, planner as lab_planner, report, scoring,
                                         visuals)

LOCK = "concept_segment"


# ── fakes ─────────────────────────────────────────────────────────────────────────────────────

def _mask(h, w, r0, r1, c0, c1):
    from backend.services.mask_geometry import rle_encode_mask
    grid = [[1 if (r0 <= r < r1 and c0 <= c < c1) else 0 for c in range(w)] for r in range(h)]
    return rle_encode_mask(grid)


class FakeSam:
    """Stands in for `sam3_concept_service`. Its whole job is to be SCRIPTABLE: the lab must
    behave differently for a concept found, a concept absent, an organ down and an organ that
    raises, and those four are the things a real model will not produce on demand."""

    CHECKPOINT = "facebook/sam3"
    MODEL_TAG = "sam3"
    PREPROCESSING_VERSION = "sam3-pcs-v1"
    DEFAULT_CONF = 0.25
    DEFAULT_IMGSZ = 1024
    NAMING_CONFIDENCE_FLOOR = 0.50
    WEIGHTS_ENV = "SAM3_WEIGHTS"

    def __init__(self, instances=None, *, available=True, raises=False, weights=True):
        self._instances = instances if instances is not None else []
        self._available = available
        self._raises = raises
        self._weights = weights
        self.calls = 0
        self.loaded = False

    # availability surface
    def weights_path(self):
        return "/lab/fake/sam3.pt" if self._weights else None

    def is_available(self):
        return self._available and self._weights

    def device(self):
        return "cpu"

    def load(self, **kwargs):
        was = self.loaded
        self.loaded = True
        return 0.0 if was else 12.5

    def unload(self):
        self.loaded = False

    # the organ
    def segment_concept(self, image, concept, **kwargs):
        self.calls += 1
        if self._raises:
            raise RuntimeError("fake organ exploded")
        return {"concept": concept, "instances": [dict(i) for i in self._instances],
                "truncated": False, "latency_ms": 42.0, "device": "cpu",
                "model": self.CHECKPOINT}

    def instances_to_regions(self, result, *, prefix="cseg"):
        from backend.services import sam3_concept_service as real
        return real.instances_to_regions(result, prefix=prefix)


class FakePlanner:
    """A Groq-shaped client. `.chat.completions.create` returns whatever JSON it was handed."""

    def __init__(self, payload):
        self._payload = payload
        self.calls = 0
        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.calls += 1
                outer.last_kwargs = kwargs

                class _Msg:
                    content = json.dumps(outer._payload)

                class _Choice:
                    message = _Msg()

                class _Out:
                    choices = [_Choice()]

                return _Out()

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


@pytest.fixture
def image(tmp_path):
    """A real image file on disk, so digests and overlays are real rather than mocked."""
    from PIL import Image
    path = tmp_path / "fixture.png"
    Image.new("RGB", (64, 48), (40, 40, 48)).save(path)
    return str(path)


def _manifest(tmp_path, image_path, **over):
    base = {
        "schema_version": contract.MANIFEST_VERSION,
        "lab_id": "test-lab",
        "run_id": "run-" + over.pop("run", "a"),
        "actuator_lock": LOCK,
        "mode": "organ_direct",
        "call_budget": 1,
        "image": {"source": "local_fixture", "path": image_path,
                  "sha256": contract.sha256_file(image_path)},
        "prompt": None,
        "control_phrase": "drapery fold",
        "allowed_params": ["phrase"],
        "warm_or_cold": "warm",
        "repeat_count": 1,
        "expected_condition": "positive",
        "review": {"protocol": "human_visual", "gold_mask_path": None, "questions": []},
    }
    base.update(over)
    path = tmp_path / f"{base['run_id']}.json"
    path.write_text(json.dumps(base))
    return str(path)


@pytest.fixture
def patched(monkeypatch):
    """Install a fake organ everywhere the lab and the production runner reach for one."""
    def _install(sam: FakeSam):
        import backend.services.sam3_concept_service as real
        for name in ("weights_path", "is_available", "device", "load", "unload",
                     "segment_concept"):
            monkeypatch.setattr(real, name, getattr(sam, name))
        monkeypatch.setattr(arms, "_svc", lambda: real)
        # The environment receipt probes torch/ultralytics for `runtime_available`; on a light
        # CI box neither is installed and every arm would report `runtime_absent`. The fake
        # organ needs no runtime, so the probe is pinned rather than the arms being taught to
        # skip it — teaching the arms would remove the check from the real runs too.
        original = contract.environment_receipt
        monkeypatch.setattr(contract, "environment_receipt",
                            lambda m: {**original(m), "runtime_available": True,
                                       "weights_present": sam.weights_path() is not None,
                                       "device": "cpu"})
        return real
    return _install


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 1. The firewall — built before the instrument, so it is tested before the instrument
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_the_catalogue_shown_to_a_planner_holds_exactly_one_actuator():
    catalogue = fw.Firewall(LOCK).catalogue()
    assert len(catalogue) == 1
    assert catalogue[0]["actuator"] == LOCK


def test_a_second_actuator_is_refused_even_when_the_planner_asks_for_it():
    """The planted-second-actuator test. `semantic_read` is a REAL production actuator with a
    real runner, so this is not a straw man: the lock is the only thing standing between the
    lab and a second capability that would work perfectly well if allowed."""
    f = fw.Firewall(LOCK)
    auth = f.authorize("semantic_read", {"question": "what is here?"})
    assert auth.allowed is False
    assert auth.refusal.reason == fw.NOT_LOCKED
    assert f.requested_unlocked() == ["semantic_read"]
    # and it cannot be reached by going around `authorize`
    with pytest.raises(fw.FirewallViolation):
        f.invoke("semantic_read", "actuator", lambda: "ran")
    assert f.attempts == []


def test_an_invented_actuator_is_refused_by_name_not_silently_dropped():
    f = fw.Firewall(LOCK)
    auth = f.authorize("segment_the_vibes", {})
    assert auth.refusal.reason == fw.UNKNOWN_ACTUATOR
    # Recorded rather than filtered: how often the mind invents capabilities is the observable,
    # and a tidy proposal with the hallucination removed would destroy the measurement.
    assert [r.actuator for r in f.refusals] == ["segment_the_vibes"]


def test_the_call_budget_is_spent_by_attempting_not_by_succeeding():
    f = fw.Firewall(LOCK, call_budget=1)

    def _boom():
        raise RuntimeError("organ died")

    _, attempt = f.invoke(LOCK, "organ", _boom)
    assert attempt.outcome == "error"
    assert f.authorize(LOCK, {"phrase": "x"}).refusal.reason == fw.BUDGET_EXHAUSTED
    with pytest.raises(fw.FirewallViolation):
        f.invoke(LOCK, "organ", lambda: "second")
    assert len(f.attempts) == 1


def test_params_are_intersected_with_the_production_declaration():
    """A manifest cannot widen the actuator, and the actuator cannot widen an old manifest."""
    f = fw.Firewall(LOCK, allowed_params=["phrase", "region_ids"])
    assert f.allowed_param_keys() == ("phrase",)      # region_ids is not declared → gone
    auth = f.authorize(LOCK, {"phrase": "fold", "geometry": [[0, 0]], "confidence": 0.99})
    assert auth.allowed and auth.params == {"phrase": "fold"}
    assert auth.dropped == ["confidence", "geometry"]
    assert f.dropped_params[0]["keys"] == ["confidence", "geometry"]


def test_lock_held_is_computed_from_what_ran_not_from_what_was_configured():
    f = fw.Firewall(LOCK)
    assert f.lock_held is True and f.attempts == []
    f.invoke(LOCK, "organ", lambda: "ok")
    assert f.lock_held is True
    # A lock that reported itself held would be reporting its own intentions; this reads the
    # record of what actually reached an instrument.
    f.attempts.append(fw.Attempt(2, 1, "semantic_read", "actuator"))
    assert f.lock_held is False and f.leaked is True


def test_database_writes_are_instrumented_and_raise():
    f = fw.Firewall(LOCK)
    instrumented = f.guard_database()
    try:
        assert instrumented > 0, "the guard found no write methods — it would pass vacuously"
        import backend.database as db
        with pytest.raises(fw.FirewallViolation):
            db.post_collection.update_one({"_id": "x"}, {"$set": {"a": 1}})
        assert f.db_writes == [{"collection": "post_collection", "method": "update_one"}]
    finally:
        f.release_database()
    # released cleanly: the real method is back
    import backend.database as db
    assert not getattr(db.post_collection.update_one, "__name__", "") == "_refuse"


def test_replay_mode_cannot_invoke_anything():
    f = fw.Firewall(LOCK, replay=True)
    with pytest.raises(fw.FirewallViolation):
        f.invoke(LOCK, "organ", lambda: "ran")
    assert f.attempts == []
    assert f.refusals[0].reason == fw.REPLAY_FORBIDS


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 2. Schemas
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_every_committed_manifest_validates():
    names = sorted(n for n in os.listdir(contract.MANIFEST_DIR) if n.endswith((".yaml", ".yml")))
    assert names, "no committed manifests to validate"
    for name in names:
        path = os.path.join(contract.MANIFEST_DIR, name)
        assert lab.validate_manifest(path) == [], name


def test_a_manifest_locking_an_unknown_actuator_is_refused(tmp_path, image):
    path = _manifest(tmp_path, image, actuator_lock="segment_the_vibes")
    errors = lab.validate_manifest(path)
    assert errors and "not in the production capability table" in errors[0]


def test_a_direct_mode_without_a_control_phrase_is_refused(tmp_path, image):
    path = _manifest(tmp_path, image, control_phrase=None)
    assert any("requires a control_phrase" in e for e in lab.validate_manifest(path))


def test_an_orchestrated_manifest_without_a_prompt_is_refused(tmp_path, image):
    path = _manifest(tmp_path, image, mode="prompt_orchestrated", prompt=None)
    assert any("requires a prompt" in e for e in lab.validate_manifest(path))


def test_an_image_whose_checksum_moved_aborts_the_run(tmp_path, image):
    m = json.loads(open(_manifest(tmp_path, image)).read())
    m["image"]["sha256"] = "0" * 64
    with pytest.raises(contract.ManifestError, match="checksum mismatch"):
        contract.resolve_image(m)


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 3. Arm A — organ_direct, and the empty / unavailable / error distinction
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_organ_direct_captures_a_positive_result(tmp_path, image, patched):
    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 10, 30, 12, 40),
                      "confidence": 0.81}]))
    out = lab.capture(_manifest(tmp_path, image), runs_root=str(tmp_path / "runs"))
    trace, score = out["trace"], out["score"]

    assert trace["organ_observation"]["status"] == "ok"
    assert trace["organ_observation"]["instance_count"] == 1
    assert score["measured"]["invocation_count"] == 1
    assert score["measured"]["lock_held"] is True
    assert score["verdict"]["attribution"] == scoring.ORGAN_SUCCEEDED
    assert contract.validate(trace, "trace") == []
    assert contract.validate(score, "score") == []
    # Arm A touches no wrapper, so there is nothing to observe there. Null, not an empty
    # object pretending a conversion happened.
    assert trace["actuator_observation"] is None


def test_empty_unavailable_and_error_are_three_different_outcomes(tmp_path, image, patched):
    """Collapsing any two would make a negative control indistinguishable from a lab with no
    model installed — which is the difference between a finding and a missing dependency."""
    patched(FakeSam([]))
    empty = lab.capture(_manifest(tmp_path, image, run="empty"),
                        runs_root=str(tmp_path / "runs"))
    assert empty["trace"]["organ_observation"]["status"] == "empty"
    assert empty["score"]["verdict"]["attribution"] == scoring.EMPTY_AMBIGUOUS

    patched(FakeSam([], weights=False))
    down = lab.capture(_manifest(tmp_path, image, run="down"), runs_root=str(tmp_path / "runs"))
    assert down["trace"]["organ_observation"]["status"] == "unavailable"
    assert down["score"]["measured"]["availability"] == "weights_absent"
    assert down["score"]["verdict"]["attribution"] == scoring.ORGAN_UNAVAILABLE
    # An organ that never ran spent no budget.
    assert down["score"]["measured"]["invocation_count"] == 0

    patched(FakeSam([], raises=True))
    broke = lab.capture(_manifest(tmp_path, image, run="err"), runs_root=str(tmp_path / "runs"))
    assert broke["trace"]["organ_observation"]["status"] == "error"
    assert broke["score"]["verdict"]["attribution"] == scoring.ORGAN_ERROR
    assert "fake organ exploded" in broke["trace"]["organ_observation"]["error"]


def test_a_negative_control_that_returns_nothing_is_a_pass_not_a_failure(tmp_path, image,
                                                                        patched):
    patched(FakeSam([]))
    out = lab.capture(_manifest(tmp_path, image, expected_condition="negative",
                                control_phrase="bicycle"),
                      runs_root=str(tmp_path / "runs"))
    assert out["score"]["verdict"]["attribution"] == scoring.NEGATIVE_AS_EXPECTED
    assert out["score"]["verdict"]["harness"] == "clean"


def test_capture_refuses_to_overwrite_a_frozen_run(tmp_path, image, patched):
    patched(FakeSam([]))
    path = _manifest(tmp_path, image)
    lab.capture(path, runs_root=str(tmp_path / "runs"))
    with pytest.raises(SystemExit, match="frozen run"):
        lab.capture(path, runs_root=str(tmp_path / "runs"))


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 4. Arm B — the production wrapper, and the two statuses it must preserve
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_actuator_direct_preserves_the_measured_mask_and_the_interpretive_label(
        tmp_path, image, patched):
    """SF-004 §5.3, checked end to end through the real runner: one SAM result is TWO claims,
    and the extent must arrive `measured` while the words arrive `interpretive`."""
    from backend.services.epistemics import EpistemicStatus
    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 5, 25, 5, 30), "confidence": 0.88}]))
    out = lab.capture(_manifest(tmp_path, image, mode="actuator_direct"),
                      runs_root=str(tmp_path / "runs"))
    actuator = out["trace"]["actuator_observation"]
    assert actuator is not None

    producers = {d["producer"]: d for d in actuator["descriptors"]}
    assert producers["concept_segment"]["status"] == EpistemicStatus.MEASURED.value
    assert producers["concept_segment"]["label"] == ""          # the words are the other claim
    assert producers["concept_naming"]["status"] == EpistemicStatus.INTERPRETIVE.value
    assert producers["concept_naming"]["label"] == "drapery fold"
    # The naming REFERENCES the extent; it never authors geometry of its own.
    assert producers["concept_naming"]["geometry_kind"] == "region_ref"
    assert producers["concept_segment"]["geometry_kind"] == "raster_mask"
    assert out["score"]["measured"]["two_status_preserved"] is True


def test_a_naming_below_the_floor_is_withheld_while_its_extent_survives(tmp_path, image,
                                                                       patched):
    """A measurement does not become false because the word attached to it is doubtful."""
    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 5, 25, 5, 30), "confidence": 0.31}]))
    out = lab.capture(_manifest(tmp_path, image, mode="actuator_direct", run="lowconf"),
                      runs_root=str(tmp_path / "runs"))
    conv = out["trace"]["actuator_observation"]["conversion"]
    assert conv["measured_descriptors"] == 1
    assert conv["interpretive_descriptors"] == 0
    assert conv["naming_withheld"] == 1
    assert conv["dropped"] == 0 and conv["survived"] is True
    # Still `preserved`: the contract is being honoured, not violated, by withholding.
    assert out["score"]["measured"]["two_status_preserved"] is True


def test_conversion_loss_is_attributed_to_the_wrapper(tmp_path, image, patched):
    """The arm's whole reason to exist. An instance with no mask cannot become a region, and
    the resulting gap must land on the WRAPPER rather than on the organ or the phrase."""
    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 5, 25, 5, 30), "confidence": 0.9},
                     {"index": 1, "mask_rle": None, "confidence": 0.9}]))
    out = lab.capture(_manifest(tmp_path, image, mode="actuator_direct", run="lossy"),
                      runs_root=str(tmp_path / "runs"))
    # `instances_to_regions` skips the maskless instance, so the organ half of this arm sees one.
    assert out["trace"]["organ_observation"]["instance_count"] == 1
    assert out["score"]["verdict"]["attribution"] == scoring.ORGAN_SUCCEEDED

    observation = observe.actuator_observation(
        None, regions=[], descriptors=[], instance_count=3)
    assert observation["conversion"]["dropped"] == 3
    assert observation["conversion"]["survived"] is False
    trace = dict(out["trace"], actuator_observation=observation)
    score = scoring.build_score(trace, json.loads(open(
        _manifest(tmp_path, image, mode="actuator_direct", run="probe")).read()))
    assert score["verdict"]["attribution"] == scoring.WRAPPER_DROPPED


def test_an_image_changed_during_the_run_is_caught_and_reported_as_a_violation(
        tmp_path, image, patched, monkeypatch):
    """The before/after digest has to be a real check, not a ceremony.

    Mutation testing found it was a ceremony: setting `digest_after = digest_before` broke no
    test, because nothing in the suite ever disturbed the image. So the organ is made to
    scribble on the fixture mid-call — the one moment a run holds the file open — and the
    violation must surface rather than the run reading clean.
    """
    from PIL import Image
    sam = FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 4, 20, 4, 30), "confidence": 0.9}])
    real = patched(sam)
    original = sam.segment_concept

    def _scribble(img, concept, **kwargs):
        Image.new("RGB", (64, 48), (255, 0, 255)).save(image)
        return original(img, concept, **kwargs)

    monkeypatch.setattr(real, "segment_concept", _scribble)
    out = lab.capture(_manifest(tmp_path, image, run="tamper"),
                      runs_root=str(tmp_path / "runs"))
    inv = out["trace"]["invariance"]
    assert inv["image_unchanged"] is False
    assert inv["image_sha256_before"] != inv["image_sha256_after"]
    assert out["score"]["verdict"]["harness"] == "violated"
    assert out["score"]["verdict"]["attribution"] == scoring.HARNESS_VIOLATION
    assert any("image changed" in v for v in out["score"]["measured"]["violations"])


def test_two_status_is_false_when_only_one_kind_of_claim_arrives(tmp_path, image, patched):
    """The check must be able to say no. A wrapper that emitted the extent and dropped the
    naming outright — no withholding, no floor, just gone — is a contract violation, and it
    looks exactly like a low-confidence withholding unless the two are told apart."""
    from backend.services.epistemics import EpistemicStatus
    measured_only = {"conversion": {"measured_descriptors": 1, "interpretive_descriptors": 0,
                                    "naming_withheld": 0,
                                    "statuses_seen": [EpistemicStatus.MEASURED.value]}}
    assert observe.two_status_preserved(measured_only) is False

    withheld = {"conversion": {"measured_descriptors": 1, "interpretive_descriptors": 0,
                               "naming_withheld": 1,
                               "statuses_seen": [EpistemicStatus.MEASURED.value]}}
    assert observe.two_status_preserved(withheld) is True

    interpretive_only = {"conversion": {"measured_descriptors": 1,
                                        "interpretive_descriptors": 1, "naming_withheld": 0,
                                        "statuses_seen": [EpistemicStatus.INTERPRETIVE.value]}}
    assert observe.two_status_preserved(interpretive_only) is False

    # Nothing produced preserves nothing and violates nothing.
    assert observe.two_status_preserved(None) is None
    assert observe.two_status_preserved({"conversion": {"measured_descriptors": 0}}) is None


def test_the_lab_post_is_not_mutated_and_no_database_write_is_attempted(tmp_path, image,
                                                                       patched):
    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 5, 25, 5, 30), "confidence": 0.9}]))
    out = lab.capture(_manifest(tmp_path, image, mode="actuator_direct", run="inv"),
                      runs_root=str(tmp_path / "runs"))
    inv = out["trace"]["invariance"]
    assert inv["database_writes_attempted"] == []
    assert inv["post_mutated"] is False
    assert inv["post_sha256_before"] == inv["post_sha256_after"]
    assert inv["image_unchanged"] is True
    assert inv["image_sha256_before"] == inv["image_sha256_after"]
    assert inv["actuators_called"] == [LOCK] and inv["lock_held"] is True


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 5. Arm C — the locked planner
# ══════════════════════════════════════════════════════════════════════════════════════════════

ORCHESTRATED = {"mode": "prompt_orchestrated",
                "prompt": "Explore the fold-level aesthetic relations between Renaissance and "
                          "Buddha sculptures and what hybrids they could give birth to."}


def test_prompt_orchestrated_extracts_one_phrase_and_runs_it(tmp_path, image, patched):
    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 8, 28, 8, 36), "confidence": 0.77}]))
    client = FakePlanner({"steps": [{"actuator": LOCK, "params": {"phrase": "drapery fold"},
                                     "note": "the only visible fold-bearing thing"}]})
    out = lab.capture(_manifest(tmp_path, image, run="orch", **ORCHESTRATED),
                      runs_root=str(tmp_path / "runs"), planner_client=client)
    decision = out["trace"]["decision_receipt"]
    assert decision["selected_phrase"] == "drapery fold"
    assert decision["phrase_source"] == "planner"
    assert out["score"]["measured"]["planner_valid"] is True
    assert client.calls == 1, "one call, no re-prompt loop"
    # The catalogue the planner was actually shown is frozen in the trace, so 'it only had one
    # tool' is checkable after the fact rather than asserted in prose.
    assert len(decision["catalogue_shown"]) == 1


def test_the_planner_sees_only_the_locked_actuator(tmp_path, image, patched):
    patched(FakeSam([]))
    client = FakePlanner({"steps": []})
    lab.capture(_manifest(tmp_path, image, run="cat", **ORCHESTRATED),
                runs_root=str(tmp_path / "runs"), planner_client=client)
    sent = client.last_kwargs["messages"][-1]["content"]
    assert LOCK in sent
    for other in ("semantic_read", "find_similar", "compose_percept", "historical_source"):
        assert other not in sent, f"{other} leaked into the planner's catalogue"


def test_a_planner_reaching_for_another_actuator_is_refused_and_recorded(tmp_path, image,
                                                                        patched):
    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 8, 28, 8, 36), "confidence": 0.7}]))
    client = FakePlanner({"steps": [
        {"actuator": "semantic_read", "params": {"question": "compare the two traditions"}},
        {"actuator": LOCK, "params": {"phrase": "drapery fold"}},
        {"actuator": "compose_percept", "params": {}},
    ]})
    out = lab.capture(_manifest(tmp_path, image, run="reach", **ORCHESTRATED),
                      runs_root=str(tmp_path / "runs"), planner_client=client)
    score, decision = out["score"], out["trace"]["decision_receipt"]

    assert score["measured"]["planner_requested_unlocked"] == ["compose_percept",
                                                               "semantic_read"]
    assert score["measured"]["planner_valid"] is False
    # Refused, and yet the locked step still ran: the lock narrows, it does not abort.
    assert decision["selected_phrase"] == "drapery fold"
    assert score["measured"]["invocation_count"] == 1
    assert score["measured"]["actuator_leakage"] is False
    reasons = {r["actuator"]: r["reason"] for r in decision["refused_actions"]}
    assert reasons["semantic_read"] == fw.NOT_LOCKED
    assert reasons["compose_percept"] == fw.NOT_LOCKED


def test_every_surplus_step_is_refused_rather_than_trimmed(tmp_path, image, patched):
    """A planner that asked for four calls when it had one is a finding ABOUT THE PLANNER. A
    lab that silently kept the first would have measured its own trimming."""
    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 8, 28, 8, 36), "confidence": 0.7}]))
    client = FakePlanner({"steps": [{"actuator": LOCK, "params": {"phrase": "drapery fold"}},
                                    {"actuator": LOCK, "params": {"phrase": "robe folds"}},
                                    {"actuator": LOCK, "params": {"phrase": "face"}}]})
    out = lab.capture(_manifest(tmp_path, image, run="surplus", **ORCHESTRATED),
                      runs_root=str(tmp_path / "runs"), planner_client=client)
    refused = [r for r in out["trace"]["decision_receipt"]["refused_actions"]
               if r["reason"] == fw.BUDGET_EXHAUSTED]
    assert len(refused) == 2
    assert out["score"]["measured"]["invocation_count"] == 1
    assert out["score"]["measured"]["budget_respected"] is True


def test_a_planner_authoring_geometry_has_it_dropped_and_recorded(tmp_path, image, patched):
    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 8, 28, 8, 36), "confidence": 0.7}]))
    client = FakePlanner({"steps": [{"actuator": LOCK, "params": {
        "phrase": "drapery fold", "mask_rle": {"size": [1, 1], "counts": [1]},
        "region_id": "cseg_fake_0", "confidence": 0.99}}]})
    out = lab.capture(_manifest(tmp_path, image, run="geom", **ORCHESTRATED),
                      runs_root=str(tmp_path / "runs"), planner_client=client)
    dropped = out["trace"]["decision_receipt"]["dropped_params"]
    keys = sorted(k for entry in dropped for k in entry["keys"])
    assert keys == ["confidence", "mask_rle", "region_id"]
    assert out["trace"]["decision_receipt"]["selected_phrase"] == "drapery fold"


def test_an_unavailable_planner_never_falls_back_to_the_control_phrase(tmp_path, image,
                                                                      patched, monkeypatch):
    """The single most misleading thing this lab could do. Substituting the human's phrase
    would report a capability the system does not have.

    The key is emptied rather than the client faked, because the code path under test is the
    one that decides there is no client at all. Emptying it also keeps this test off the
    network: a `.env` with a live key is normal on a developer's machine, and without this the
    suite would quietly start calling Groq.
    """
    from backend.config import settings
    monkeypatch.setattr(settings, "GROQ_API_KEY", "", raising=False)

    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 8, 28, 8, 36), "confidence": 0.9}]))
    out = lab.capture(_manifest(tmp_path, image, run="noplanner", control_phrase="drapery fold",
                                **ORCHESTRATED),
                      runs_root=str(tmp_path / "runs"), planner_client=None)
    prompt = out["trace"]["prompt_receipt"]
    assert prompt["planner_status"] == "unavailable"
    assert out["trace"]["decision_receipt"]["selected_phrase"] is None
    assert out["score"]["measured"]["invocation_count"] == 0
    assert out["score"]["verdict"]["attribution"] == scoring.PLANNER_UNAVAILABLE
    # The control phrase is in the manifest and was deliberately not used.
    assert prompt["control_phrase"] == "drapery fold"
    # AND the organ half says `unavailable`, not `empty`. Mutation testing found this: the
    # attribution is computed from the planner receipt, so it stayed correct even when the arm
    # stopped distinguishing the two — and the ORGAN observation quietly began reporting that
    # it had run and found nothing, when it had never been asked anything at all. That is the
    # empty/unavailable collapse this lab exists to prevent, displaced one field over.
    assert out["trace"]["organ_observation"]["status"] == "unavailable"


def test_a_declining_planner_leaves_the_organ_reported_as_empty_not_unavailable(
        tmp_path, image, patched):
    """The other side of the same distinction. Here the planner WAS available and chose not to
    act, so nothing about the organ is unavailable — it simply was never given a phrase."""
    patched(FakeSam([]))
    out = lab.capture(_manifest(tmp_path, image, run="declined-organ", **ORCHESTRATED),
                      runs_root=str(tmp_path / "runs"), planner_client=FakePlanner({"steps": []}))
    assert out["trace"]["prompt_receipt"]["planner_status"] == "empty"
    assert out["trace"]["organ_observation"]["status"] == "empty"
    assert out["score"]["measured"]["invocation_count"] == 0


def test_a_planner_that_declines_is_not_a_failure(tmp_path, image, patched):
    patched(FakeSam([]))
    client = FakePlanner({"steps": []})
    out = lab.capture(_manifest(tmp_path, image, run="declined", **ORCHESTRATED),
                      runs_root=str(tmp_path / "runs"), planner_client=client)
    assert out["trace"]["prompt_receipt"]["planner_status"] == "empty"
    assert out["score"]["verdict"]["attribution"] == scoring.PLANNER_NOTHING
    assert out["score"]["measured"]["planner_valid"] is True   # declining is valid behaviour


def test_the_deterministic_framer_says_that_it_ran(tmp_path, image, patched):
    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 8, 28, 8, 36), "confidence": 0.7}]))
    out = lab.capture(_manifest(tmp_path, image, run="frozen", **ORCHESTRATED),
                      runs_root=str(tmp_path / "runs"), deterministic=True)
    assert out["trace"]["prompt_receipt"]["planner_status"] == "deterministic_framer"
    assert out["trace"]["decision_receipt"]["phrase_source"] == "deterministic_framer"
    assert out["trace"]["decision_receipt"]["selected_phrase"] == "drapery fold"


def test_the_orchestrated_phrase_failing_is_attributed_to_the_phrase(tmp_path, image, patched):
    patched(FakeSam([]))
    client = FakePlanner({"steps": [{"actuator": LOCK, "params": {"phrase": "sensuality"}}]})
    out = lab.capture(_manifest(tmp_path, image, run="phrasefail", **ORCHESTRATED),
                      runs_root=str(tmp_path / "runs"), planner_client=client)
    assert out["score"]["verdict"]["attribution"] == scoring.PHRASE_FAILED
    assert "paired control run" in out["score"]["verdict"]["attribution_detail"]


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 6. Arm D — replay
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_replay_makes_zero_calls_and_is_deterministic(tmp_path, image, patched):
    sam = FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 6, 26, 6, 34), "confidence": 0.8},
                   {"index": 1, "mask_rle": _mask(48, 64, 28, 44, 20, 52), "confidence": 0.6}])
    patched(sam)
    out = lab.capture(_manifest(tmp_path, image, run="replayme"),
                      runs_root=str(tmp_path / "runs"))
    before = sam.calls
    assert before == 1

    first = lab.replay(out["run_path"])
    second = lab.replay(out["run_path"])
    assert sam.calls == before, "replay called the organ"
    assert first["live_calls"] == 0
    assert first["divergences"] == []
    assert first["trace"]["replay"]["live_calls"] == 0
    assert first["trace"]["organ_observation"] == second["trace"]["organ_observation"]
    assert first["trace"]["invariance"]["actuators_called"] == []
    assert contract.validate(first["trace"], "trace") == []
    assert contract.validate(first["score"], "score") == []
    # Rebuilt from the observation FILES, not copied from the trace, or the check is circular.
    assert first["trace"]["organ_observation"]["instance_count"] == 2


def test_replay_reports_a_divergence_rather_than_smoothing_it(tmp_path, image, patched):
    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 6, 26, 6, 34), "confidence": 0.8}]))
    out = lab.capture(_manifest(tmp_path, image, run="tampered"),
                      runs_root=str(tmp_path / "runs"))
    obs = os.path.join(out["run_path"], "observations", "instance-000.json")
    payload = contract.read_json(obs)
    payload["mask_rle_sha256"] = "deadbeef"
    contract.write_json(obs, payload)

    replayed = lab.replay(out["run_path"])
    assert replayed["divergences"], "a tampered observation replayed as if nothing happened"
    assert replayed["trace"]["replay"]["matches_source"] is False


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 7. The line the lab exists to hold
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_a_confident_well_formed_mask_is_never_called_correct(tmp_path, image, patched):
    """Maximum confidence, perfect RLE, sane bounds, one clean instance. The score must STILL
    say `not_established`, because SF-004-R2 watched exactly this shape of result be a mask of
    the background."""
    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 4, 44, 4, 60), "confidence": 1.0}]))
    out = lab.capture(_manifest(tmp_path, image, run="confident"),
                      runs_root=str(tmp_path / "runs"))
    score = out["score"]
    assert score["measured"]["all_masks_well_formed"] is True
    assert score["verdict"]["semantic_correctness"] == "not_established"
    assert score["review"]["status"] == "pending"
    for field in ("concept_binding", "coverage", "boundary_quality", "iou_vs_gold",
                  "empty_means", "false_positives", "false_negatives"):
        assert score["review"][field] is None, f"the harness filled in {field}"


def test_no_automated_signal_can_reach_the_review_half(tmp_path, image, patched):
    """A structural check, not a behavioural one: `build_score` must not write a review field
    from anything it measured, whatever the numbers happen to be."""
    import inspect
    source = inspect.getsource(scoring.build_score)
    review_block = source.split('"review": {', 1)[1].split('"verdict"', 1)[0]
    for line in review_block.splitlines():
        if ":" not in line or line.strip().startswith("#"):
            continue
        key, _, value = line.partition(":")
        if key.strip().strip('"') in ("status", "protocol", "gold_mask_present", "notes"):
            continue
        assert "None" in value, f"review field {key.strip()} is computed: {line.strip()}"


def test_the_harness_reports_a_violation_rather_than_hiding_it():
    trace = {
        "actuator_lock": LOCK, "mode": "organ_direct",
        "invocations": [{"call_budget": 1}, {"call_budget": 1}],
        "organ_observation": {"status": "ok", "concept": "fold", "instance_count": 1},
        "actuator_observation": None, "prompt_receipt": {}, "decision_receipt": {},
        "invariance": {"image_unchanged": False, "lock_held": False,
                       "actuators_called": ["concept_segment", "semantic_read"],
                       "database_writes_attempted": [
                           {"collection": "post_collection", "method": "insert_one"}],
                       "post_mutated": True},
        "environment": {"weights_present": True, "runtime_available": True},
        "lab_id": "t", "run_id": "r",
    }
    score = scoring.build_score(trace, {"expected_condition": "positive", "call_budget": 1,
                                        "review": {"protocol": "human_visual"}})
    assert score["verdict"]["harness"] == "violated"
    assert score["verdict"]["attribution"] == scoring.HARNESS_VIOLATION
    assert score["measured"]["invariants_held"] is False
    assert len(score["measured"]["violations"]) == 5


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 8. Artifacts and comparison
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_an_overlay_and_a_contact_sheet_are_generated(tmp_path, image, patched):
    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 4, 20, 4, 30), "confidence": 0.9},
                     {"index": 1, "mask_rle": _mask(48, 64, 24, 44, 32, 60), "confidence": 0.5}]))
    out = lab.capture(_manifest(tmp_path, image, run="art"), runs_root=str(tmp_path / "runs"))
    run_path = out["run_path"]
    for name in ("trace.json", "score.json", "review.md", "overlay.png", "contact-sheet.png"):
        assert os.path.exists(os.path.join(run_path, name)), name
    assert out["trace"]["artifacts"]["overlay"] == "overlay.png"
    # The masks live in observations/, once. The trace carries digests.
    assert os.path.exists(os.path.join(run_path, "observations", "masks.json"))
    # Digests and bounds, never the geometry itself: exactly one copy of every mask exists on
    # disk. (`mask_rle_sha256` contains the substring, so the check is for RLE structure.)
    frozen = json.dumps(out["trace"]["organ_observation"])
    assert '"counts"' not in frozen and '"mask_rle":' not in frozen
    assert '"mask_rle_sha256"' in frozen


def test_an_empty_result_gets_no_overlay(tmp_path, image, patched):
    """Rather than a copy of the original masquerading as one."""
    patched(FakeSam([]))
    out = lab.capture(_manifest(tmp_path, image, run="noart"), runs_root=str(tmp_path / "runs"))
    assert out["trace"]["artifacts"]["overlay"] is None
    assert not os.path.exists(os.path.join(out["run_path"], "overlay.png"))


def test_the_review_sheet_leaves_its_judgements_empty(tmp_path, image, patched):
    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 4, 20, 4, 30), "confidence": 0.99}]))
    out = lab.capture(_manifest(tmp_path, image, run="sheet"), runs_root=str(tmp_path / "runs"))
    text = open(os.path.join(out["run_path"], "review.md")).read()
    assert "TO BE FILLED IN" in text
    assert "not_established" in text
    assert "concept_binding :" in text
    assert "- [ ]" in text                      # unchecked boxes, not prefilled answers


def test_compare_attributes_an_empty_orchestrated_run_to_the_phrase(tmp_path, image, patched):
    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 4, 20, 4, 30), "confidence": 0.9}]))
    control = lab.capture(_manifest(tmp_path, image, run="c-ctrl"),
                          runs_root=str(tmp_path / "runs"))
    patched(FakeSam([]))
    client = FakePlanner({"steps": [{"actuator": LOCK, "params": {"phrase": "sensuality"}}]})
    orch = lab.capture(_manifest(tmp_path, image, run="c-orch", pair_with="run-c-ctrl",
                                 **ORCHESTRATED),
                       runs_root=str(tmp_path / "runs"), planner_client=client)

    comparison = lab.compare([control["run_path"], orch["run_path"]])
    assert comparison["same_image"] is True
    joined = " ".join(comparison["findings"])
    assert "the PHRASE failed, not the organ" in joined
    assert "semantic correctness is not established" in joined
    rendered = report.render_compare(comparison)
    assert "never concluded here" in rendered


def test_compare_attributes_only_against_the_declared_pair(tmp_path, image, patched):
    """Found on the real matrix. Comparing an orchestrated run against every direct run in the
    set produced two contradictory attributions of the SAME run — 'the PHRASE failed' when
    lined up beside a control that found things, and 'this points at the ORGAN' when lined up
    beside one that did not. The pairing has to be declared before the numbers are known."""
    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 4, 20, 4, 30), "confidence": 0.9}]))
    lab.capture(_manifest(tmp_path, image, run="p-face", control_phrase="face"),
                runs_root=str(tmp_path / "runs"))
    patched(FakeSam([]))
    lab.capture(_manifest(tmp_path, image, run="p-fold", control_phrase="drapery fold"),
                runs_root=str(tmp_path / "runs"))
    client = FakePlanner({"steps": [{"actuator": LOCK, "params": {"phrase": "folded drapery"}}]})
    lab.capture(_manifest(tmp_path, image, run="p-orch", pair_with="run-p-fold",
                          **ORCHESTRATED),
                runs_root=str(tmp_path / "runs"), planner_client=client)

    runs = [str(tmp_path / "runs" / r) for r in ("run-p-face", "run-p-fold", "run-p-orch")]
    findings = " ".join(lab.compare(runs)["findings"])
    # Its declared pair also measured nothing, so organ-or-absence is the honest reading.
    assert "both measured nothing" in findings
    # And the unrelated `face` control does NOT get used to blame the phrase.
    assert "the PHRASE failed" not in findings
    assert "'face'" in findings          # still reported, as a wording difference on one image


def test_compare_says_so_when_an_orchestrated_run_has_no_paired_control(tmp_path, image,
                                                                       patched):
    patched(FakeSam([]))
    client = FakePlanner({"steps": [{"actuator": LOCK, "params": {"phrase": "sensuality"}}]})
    lab.capture(_manifest(tmp_path, image, run="lonely", **ORCHESTRATED),
                runs_root=str(tmp_path / "runs"), planner_client=client)
    findings = " ".join(lab.compare([str(tmp_path / "runs" / "run-lonely")])["findings"])
    assert "no paired control in this set" in findings
    assert "not attributable" in findings


def test_findings_are_not_repeated(tmp_path, image, patched):
    patched(FakeSam([]))
    paths = []
    for n in ("r1", "r2", "r3"):
        out = lab.capture(_manifest(tmp_path, image, run=n, control_phrase="drapery fold"),
                          runs_root=str(tmp_path / "runs"))
        paths.append(out["run_path"])
    findings = lab.compare(paths)["findings"]
    assert len(findings) == len(set(findings)), "a finding repeated reads as more evidence"


def test_the_effective_imgsz_is_recorded_as_absent_rather_than_echoing_the_request():
    """Ultralytics rounds imgsz up to a multiple of the model stride inside the inference call
    and does not write it back, so this seam cannot read the effective size. Reporting the
    request under that name would look like a confirmation the rounding did not happen."""
    effective, note = contract.imgsz_receipt()
    assert effective is None
    assert "1036" in note and "predictor.args" in note


def test_compare_refuses_to_attribute_across_different_images(tmp_path, image, patched):
    from PIL import Image
    other = tmp_path / "other.png"
    Image.new("RGB", (64, 48), (200, 30, 30)).save(other)

    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 4, 20, 4, 30), "confidence": 0.9}]))
    a = lab.capture(_manifest(tmp_path, image, run="d-a"), runs_root=str(tmp_path / "runs"))
    b = lab.capture(_manifest(tmp_path, str(other), run="d-b"),
                    runs_root=str(tmp_path / "runs"))
    comparison = lab.compare([a["run_path"], b["run_path"]])
    assert comparison["same_image"] is False
    assert any("NOT on the same image" in f for f in comparison["findings"])


def test_validate_checks_a_frozen_run(tmp_path, image, patched):
    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 4, 20, 4, 30), "confidence": 0.9}]))
    out = lab.capture(_manifest(tmp_path, image, run="val"), runs_root=str(tmp_path / "runs"))
    results = lab.validate_run(out["run_path"])
    assert set(results) == {"trace", "score", "manifest"}
    assert all(errors == [] for errors in results.values())


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 9. Repeats and mask arithmetic
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_repeats_use_a_fresh_budget_of_one_each_and_report_stability(tmp_path, image, patched):
    sam = FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 4, 20, 4, 30), "confidence": 0.9}])
    patched(sam)
    out = lab.capture(_manifest(tmp_path, image, run="rep", repeat_count=3),
                      runs_root=str(tmp_path / "runs"))
    stability = out["trace"]["organ_observation"]["repeat_stability"]
    assert stability["repeats"] == 3
    assert stability["identical_mask_hashes"] is True
    assert sam.calls == 3
    # Phrase stability is NOT claimed here: the planner runs once per capture by design.
    assert stability["phrase_stable"] is None
    for repeat in out["trace"]["organ_observation"]["repeats"]:
        assert repeat["invocations"][0]["call_budget"] == 1


def test_iou_is_computed_by_merging_runs_and_matches_a_hand_case():
    a = _mask(10, 10, 0, 5, 0, 10)      # 50 px
    b = _mask(10, 10, 3, 8, 0, 10)      # 50 px, 20 shared
    assert observe.rle_iou(a, b) == pytest.approx(20 / 80)
    assert observe.rle_iou(a, a) == pytest.approx(1.0)
    disjoint = _mask(10, 10, 8, 10, 0, 10)
    assert observe.rle_iou(a, disjoint) is None or observe.rle_iou(a, disjoint) == 0.0
    assert observe.max_pairwise_iou([a, b, disjoint]) == pytest.approx(20 / 80)


def test_near_duplicate_instances_are_visible_in_the_score(tmp_path, image, patched):
    """Three instances that are nearly the same mask are one finding reported three times, and
    a reader seeing only `instance_count: 3` would take it for coverage."""
    patched(FakeSam([{"index": 0, "mask_rle": _mask(48, 64, 4, 24, 4, 34), "confidence": 0.9},
                     {"index": 1, "mask_rle": _mask(48, 64, 4, 24, 4, 33), "confidence": 0.8},
                     {"index": 2, "mask_rle": _mask(48, 64, 30, 44, 40, 60), "confidence": 0.7}]))
    out = lab.capture(_manifest(tmp_path, image, run="dupes"),
                      runs_root=str(tmp_path / "runs"))
    assert out["score"]["measured"]["instance_count"] == 3
    assert out["score"]["measured"]["max_pairwise_iou"] > 0.9


def test_a_malformed_mask_is_reported_not_silently_dropped():
    stats = observe.mask_stats({"size": [4, 4], "counts": [3]})   # runs do not sum to 16
    assert stats["well_formed"] is False
    assert stats["area_px"] == 0
