"""R1 rehearsal-substrate tests (RESEARCH-ONLY).

Covers schema validation, invalid-event rejection, reconstructed null telemetry,
frozen-run overwrite refusal, capture/replay separation, no-production-DB-writes,
SPARK-not-promoted, ambiguous pct_/pctx_ handling, and failure/refusal as valid
terminal outcomes.

Validator note: ``jsonschema`` is NOT installed in this venv, so the runner
vendors a minimal Draft-2020-12 validator (``rehearsal_run.validate``). These
tests exercise that vendored validator.
"""

import copy
import json
import os
import re
import subprocess
import sys
import textwrap

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import rehearsal_adapters  # noqa: E402
import rehearsal_run as rr  # noqa: E402

REHEARSALS = os.path.join(
    REPO_ROOT, "vault", "Build", "Architecture Lab", "Vision pipeline", "rehearsals"
)
RUN000 = os.path.join(REHEARSALS, "runs", "000-passage-001")
MANIFEST000 = os.path.join(RUN000, "manifest.yaml")
RUN002 = os.path.join(REHEARSALS, "runs", "002-figure-ground-reversal")
MANIFEST002 = os.path.join(RUN002, "manifest.yaml")


# --------------------------------------------------------------------------- #
# 1. schema validation                                                        #
# --------------------------------------------------------------------------- #

def test_all_four_schemas_load():
    schemas = rr.load_all_schemas()
    assert set(schemas) == {"manifest", "trace", "candidate", "observation"}
    for name, schema in schemas.items():
        assert schema.get("$schema", "").endswith("2020-12/schema"), name
        assert schema["type"] == "object"


def test_passage001_manifest_validates():
    schemas = rr.load_all_schemas()
    manifest = rr.load_manifest(MANIFEST000)
    assert rr.validate(manifest, schemas["manifest"]) == []
    assert manifest["reconstructed"] is True
    assert manifest["mode"] == "imaginative"
    assert manifest["family"] == "R2 Sensitisation-and-Return"
    assert manifest["source_condition"] == "present"


def test_passage001_trace_validates():
    schemas = rr.load_all_schemas()
    trace = rr.load_json(os.path.join(RUN000, "trace.json"))
    assert rr.validate(trace, schemas["trace"]) == []


def test_synthetic_candidate_card_validates():
    schemas = rr.load_all_schemas()
    card = {
        "candidate_id": "cec-posture-field",
        "working_name": "posture-field",
        "kind": "relational_field",
        "epistemic_status": "SPARK",
        "research_only": True,
        "percept_kind": "n/a",
        "claim": "gesture extends through bodily dependencies beyond the part mask",
        "nearest_existing_construct": "Ground",
        "provenance": "reconstructed-from:PASSAGE-REHEARSAL-001.md",
    }
    assert rr.validate(card, schemas["candidate"]) == []


def test_candidate_card_research_only_must_be_true():
    schemas = rr.load_all_schemas()
    card = {
        "candidate_id": "cec-x",
        "working_name": "x",
        "kind": "relational_field",
        "epistemic_status": "SPARK",
        "research_only": False,  # violates const true
        "provenance": "p",
    }
    errs = rr.validate(card, schemas["candidate"])
    assert any("research_only" in e for e in errs)


def test_frozen_observation_schema_validates_synthetic():
    schemas = rr.load_all_schemas()
    obs = {
        "observation_id": "o1",
        "adapter": "local_file_digest",
        "request_boundary": "local_filesystem_read",
        "model": None,
        "version": "r1.local-pure.1",
        "device": "cpu",
        "cost": None,
        "latency_ms": None,
        "output": {"sha256": "deadbeef", "size_bytes": 3},
        "uncertainty": None,
        "provenance": "capture:test",
        "captured_at": None,
        "content_hash": "abc123",
    }
    assert rr.validate(obs, schemas["observation"]) == []


# --------------------------------------------------------------------------- #
# 2. invalid event / reference rejection                                      #
# --------------------------------------------------------------------------- #

def _valid_event():
    return {
        "event_id": "e0", "actor": "human", "kind": "RECEIVE",
        "parent_event": None, "source_refs": [], "target_refs": [],
        "register": "opening", "uncertainty": None, "reconstructed": True,
        "observation_ref": None, "reversibility": None, "cost": None,
        "provenance": "p", "timestamp": None,
        "timestamp_null_reason": "no telemetry",
    }


def _trace_with(event):
    return {"rehearsal_id": "t", "status": "completed", "events": [event]}


def test_event_missing_required_field_fails():
    schemas = rr.load_all_schemas()
    ev = _valid_event()
    del ev["register"]
    errs = rr.validate(_trace_with(ev), schemas["trace"])
    assert any("register" in e for e in errs)


def test_event_bad_kind_fails():
    schemas = rr.load_all_schemas()
    ev = _valid_event()
    ev["kind"] = "TELEPORT"
    errs = rr.validate(_trace_with(ev), schemas["trace"])
    assert any("enum" in e for e in errs)


def test_event_null_timestamp_without_reason_fails():
    schemas = rr.load_all_schemas()
    ev = _valid_event()
    del ev["timestamp_null_reason"]  # timestamp is null → reason required
    errs = rr.validate(_trace_with(ev), schemas["trace"])
    assert any("timestamp_null_reason" in e for e in errs)


def test_event_additional_property_fails():
    schemas = rr.load_all_schemas()
    ev = _valid_event()
    ev["smuggled"] = "x"
    errs = rr.validate(_trace_with(ev), schemas["trace"])
    assert any("smuggled" in e for e in errs)


# --------------------------------------------------------------------------- #
# 3. reconstructed null telemetry                                             #
# --------------------------------------------------------------------------- #

def test_passage001_every_event_reconstructed_with_null_telemetry():
    trace = rr.load_json(os.path.join(RUN000, "trace.json"))
    assert trace["reconstructed"] is True
    assert len(trace["events"]) >= 8
    for ev in trace["events"]:
        assert ev["reconstructed"] is True, ev["event_id"]
        assert ev["observation_ref"] is None, ev["event_id"]
        assert ev["timestamp"] is None, ev["event_id"]
        assert ev.get("timestamp_null_reason"), ev["event_id"]
        assert ev["cost"] is None, ev["event_id"]


# --------------------------------------------------------------------------- #
# 4. frozen-run overwrite refusal                                             #
# --------------------------------------------------------------------------- #

def test_capture_into_existing_frozen_run_raises(tmp_path):
    runs_root = str(tmp_path / "runs")
    # Freeze a run by capturing once.
    r1 = rr.run(MANIFEST000, mode="capture", runs_root=runs_root,
                capture_targets=[MANIFEST000])
    assert rr._is_frozen(r1.run_dir)
    # Second capture into the same frozen id must raise.
    with pytest.raises(FileExistsError):
        rr.run(MANIFEST000, mode="capture", runs_root=runs_root,
               capture_targets=[MANIFEST000])
    # ...unless force_new_id is set.
    r2 = rr.run(MANIFEST000, mode="capture", runs_root=runs_root,
                force_new_id=True, capture_targets=[MANIFEST000])
    assert r2.rehearsal_id != r1.rehearsal_id


# --------------------------------------------------------------------------- #
# 5. capture / replay separation (spy on the allowlisted adapter)             #
# --------------------------------------------------------------------------- #

@pytest.fixture
def adapter_spy(monkeypatch):
    calls = {"n": 0}
    real = rehearsal_adapters.local_file_digest

    def spy(path):
        calls["n"] += 1
        return real(path)

    monkeypatch.setitem(rehearsal_adapters.ALLOWLIST, "local_file_digest", spy)
    return calls


def test_capture_calls_adapter_replay_does_not(tmp_path, adapter_spy):
    runs_root = str(tmp_path / "runs")
    cap = rr.run(MANIFEST000, mode="capture", runs_root=runs_root,
                 capture_targets=[MANIFEST000, MANIFEST000])
    assert cap.adapter_calls == 2
    assert adapter_spy["n"] == 2
    assert len(cap.observations) == 2

    adapter_spy["n"] = 0
    rep = rr.run(MANIFEST000, mode="replay", runs_root=runs_root)
    assert rep.adapter_calls == 0
    assert adapter_spy["n"] == 0  # REPLAY makes ZERO adapter calls
    assert rep.trace["rehearsal_id"] == "000-passage-001"


def test_replay_of_passage001_reproduces_trace():
    # The frozen reconstructed run replays deterministically with no adapter use.
    rep = rr.run(MANIFEST000, mode="replay")
    assert rep.adapter_calls == 0
    assert rep.status == "completed"
    assert len(rep.trace["events"]) == 14


def test_non_allowlisted_adapter_raises():
    with pytest.raises(rehearsal_adapters.AdapterNotAllowed):
        rehearsal_adapters.get_adapter("sam2_refiner")
    with pytest.raises(rehearsal_adapters.AdapterNotAllowed):
        rr.capture_observation("dinov2_encode", "o", "prov", path=MANIFEST000)


def test_allowlist_is_exactly_the_approved_adapters():
    # R1 allowed ONLY the pure local digest. R2 deliberately adds ONE bounded
    # sensory adapter (a single Groq VLM call, frozen on capture). The set stays
    # pinned so a third adapter cannot be added silently.
    assert set(rehearsal_adapters.ALLOWLIST) == {"local_file_digest", "groq_vlm_probe"}
    forbidden = {"sam", "sam2", "yolo", "segformer", "dinov2",
                 "fashionclip", "fashion_clip", "semantic", "llm"}
    assert forbidden.isdisjoint(set(rehearsal_adapters.ALLOWLIST))


def test_r2_run_002_replays_without_touching_any_adapter(monkeypatch):
    # The frozen A1 run is the first rehearsal holding REAL model output. Its whole
    # value depends on replay being reproducible from disk: if replay could re-call
    # the VLM, the "observations" would not be frozen evidence at all.
    def boom(*a, **k):
        raise AssertionError("replay invoked an adapter")

    for name in list(rehearsal_adapters.ALLOWLIST):
        monkeypatch.setitem(rehearsal_adapters.ALLOWLIST, name, boom)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    res = rr.run(MANIFEST002, mode="replay")
    assert res.adapter_calls == 0
    assert res.status == "completed"
    # 1 local digest + 2 frozen VLM probes, and an event per observation plus RECEIVE.
    assert len(res.observations) == 3
    assert len(res.trace["events"]) == 4


def test_r2_frozen_vlm_observations_carry_real_telemetry():
    # Guards against the observation writer silently recording null latency/model
    # for a real remote call, which would make the run unauditable.
    obs_dir = os.path.join(RUN002, "observations")
    vlm = []
    for fn in sorted(os.listdir(obs_dir)):
        obs = json.load(open(os.path.join(obs_dir, fn)))
        if obs["adapter"] == "groq_vlm_probe":
            vlm.append(obs)
    assert len(vlm) == 2, "A1 declared a 2-call budget"
    for obs in vlm:
        assert obs["model"] == "qwen/qwen3.6-27b"
        assert isinstance(obs["latency_ms"], (int, float)) and obs["latency_ms"] > 0
        assert obs["cost"]["token_usage"]["total_tokens"] > 0
        assert obs["output"]["reasoning_effort"] == "none"
        assert obs["output"]["finish_reason"] == "stop"
        # A truncated reasoning block would mean the captured answer is unusable.
        assert obs["output"]["emitted_think_block"] is False
        assert obs["output"]["answer_text"].strip()


# --------------------------------------------------------------------------- #
# 5b. mode-specific score indexes (R2-A1R)                                     #
# --------------------------------------------------------------------------- #

SCORE002 = os.path.join(RUN002, "instrumented-score.json")
VSCORE001 = os.path.join(
    REHEARSALS, "runs", "001-eyes-of-stone", "virtual-score.json")


def _instrumented_schema():
    return rr.load_schema("instrumented_score")


def _virtual_schema_or_skip():
    try:
        return rr.load_schema("virtual_score")
    except FileNotFoundError:  # protocol file is authored outside this branch
        pytest.skip("virtual-rehearsal-score.schema.json not present")


RUN002F = os.path.join(REHEARSALS, "runs", "002F-single-object-followup")


def test_002f_followup_score_validates_and_replays_clean(monkeypatch):
    assert rr.validate(
        json.load(open(os.path.join(RUN002F, "instrumented-score.json"))),
        rr.load_schema("instrumented_score")) == []

    def boom(*a, **k):
        raise AssertionError("replay invoked an adapter")

    for name in list(rehearsal_adapters.ALLOWLIST):
        monkeypatch.setitem(rehearsal_adapters.ALLOWLIST, name, boom)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    res = rr.run(os.path.join(RUN002F, "manifest.yaml"), mode="replay")
    assert res.adapter_calls == 0 and len(res.observations) == 3


def test_completed_run_needs_no_stall_reason():
    # The stall/refusal requirement must not fire on runs that reached a result.
    score = json.load(open(os.path.join(RUN002F, "instrumented-score.json")))
    assert score["status"] == "completed"
    assert score["stall_or_refusal"] is None
    assert rr.validate(score, rr.load_schema("instrumented_score")) == []


def test_core_schema_loading_does_not_require_score_schemas():
    # Score indexes are optional; a run must still execute without them.
    assert "virtual_score" not in rr.load_all_schemas()
    assert "instrumented_score" not in rr.load_all_schemas()


def test_a1_instrumented_score_validates():
    assert rr.validate(json.load(open(SCORE002)), _instrumented_schema()) == []


def test_imaginative_virtual_score_still_validates_unchanged():
    # The instrumented schema was added ALONGSIDE the virtual one; adding it must
    # not have perturbed imaginative indexing.
    schema = _virtual_schema_or_skip()
    if not os.path.exists(VSCORE001):
        pytest.skip("001-eyes-of-stone virtual-score.json not present")
    assert rr.validate(json.load(open(VSCORE001)), schema) == []


def test_instrumented_run_cannot_be_mislabeled_as_imaginative():
    score = json.load(open(SCORE002))
    # a) mode is pinned within the instrumented schema
    score["mode"] = "imaginative"
    assert rr.validate(score, _instrumented_schema()), "mode must be pinned"
    # b) and an instrumented score cannot masquerade as a virtual one
    schema = _virtual_schema_or_skip()
    assert rr.validate(json.load(open(SCORE002)), schema), \
        "instrumented score must not validate against the imaginative schema"


def test_imaginative_score_cannot_validate_as_instrumented():
    _virtual_schema_or_skip()
    if not os.path.exists(VSCORE001):
        pytest.skip("001-eyes-of-stone virtual-score.json not present")
    assert rr.validate(json.load(open(VSCORE001)), _instrumented_schema()), \
        "an imaginative score must not validate as instrumented"


def test_verified_replay_proof_requires_zero_live_calls():
    schema = _instrumented_schema()
    score = json.load(open(SCORE002))
    assert score["replay_proof"]["verified"] is True
    assert score["replay_live_call_count"] == 0
    # Claiming a verified replay while recording live calls is incoherent.
    score["replay_live_call_count"] = 1
    assert rr.validate(score, schema)
    # But an UNVERIFIED replay may honestly record a nonzero count — the schema
    # must not make a violation unrecordable.
    score["replay_proof"] = {"verified": False, "method": "spy detected a live call"}
    assert rr.validate(score, schema) == []


def test_stall_must_state_a_reason_and_cite_evidence():
    schema = _instrumented_schema()
    score = json.load(open(SCORE002))
    assert score["status"] == "stalled"
    del score["stall_or_refusal"]
    assert rr.validate(score, schema), "a stall with no stated reason must not validate"


def test_declared_live_calls_must_carry_telemetry():
    schema = _instrumented_schema()
    score = json.load(open(SCORE002))
    score["model_calls"] = []
    assert rr.validate(score, schema), \
        "claiming live calls while listing none must not validate"


def test_production_mutation_claim_requires_evidence():
    schema = _instrumented_schema()
    score = json.load(open(SCORE002))
    assert score["production_mutation"]["mutated"] is False
    del score["production_mutation"]["evidence_ref"]
    assert rr.validate(score, schema), \
        "an unevidenced no-mutation claim must not validate"


def test_every_allowlisted_adapter_declares_provenance_meta():
    # An adapter with no ADAPTER_META entry would silently write null model /
    # "unknown" boundary into a frozen observation.
    for name in rehearsal_adapters.ALLOWLIST:
        meta = rehearsal_adapters.adapter_meta(name)
        assert meta.get("request_boundary"), name
        assert meta.get("version"), name


def test_vlm_adapter_requires_a_key_and_makes_no_call_without_one(monkeypatch):
    # Guards the REPLAY invariant's weak point: the sensory adapter must fail
    # loudly on a missing key rather than silently returning empty output.
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        rehearsal_adapters.groq_vlm_probe(MANIFEST000, "probe")


# --------------------------------------------------------------------------- #
# 6. no production DB writes                                                   #
# --------------------------------------------------------------------------- #

def test_runner_modules_never_import_backend_or_mongo():
    for mod in (rr, rehearsal_adapters):
        src = open(mod.__file__).read()
        assert "import pymongo" not in src, mod.__file__
        assert "import motor" not in src, mod.__file__
        assert "backend.database" not in src, mod.__file__
        assert re.search(r"\bfrom backend\b", src) is None, mod.__file__
        assert re.search(r"\bimport backend\b", src) is None, mod.__file__


def test_backend_not_pulled_into_sys_modules_by_runner(tmp_path):
    # A full capture+replay cycle must not import backend.database / pymongo /
    # motor. Run in a CLEAN subprocess so the check is order-independent — inside
    # the pytest process `backend.database` may already be loaded by other tests,
    # which would falsely fail an absolute `not in sys.modules` assertion.
    runs_root = str(tmp_path / "runs")
    code = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {SCRIPTS_DIR!r})
        import rehearsal_run as rr
        m = {MANIFEST000!r}
        rr.run(m, mode="capture", runs_root={runs_root!r}, capture_targets=[m])
        rr.run(m, mode="replay", runs_root={runs_root!r})
        bad = sorted(x for x in sys.modules
                     if x == "backend.database" or x.startswith("backend.database")
                     or x.split(".")[0] in {{"pymongo", "motor"}})
        print("BAD=" + ",".join(bad))
    """)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         cwd=REPO_ROOT)
    assert out.returncode == 0, out.stderr
    assert "BAD=" in out.stdout and out.stdout.strip().splitlines()[-1] == "BAD=", out.stdout + out.stderr


def test_capture_writes_only_under_runs_root(tmp_path):
    runs_root = str(tmp_path / "runs")
    res = rr.run(MANIFEST000, mode="capture", runs_root=runs_root,
                 capture_targets=[MANIFEST000])
    # Everything written lives under runs_root (on-disk only, no Mongo).
    assert res.run_dir.startswith(runs_root)
    assert os.path.exists(os.path.join(res.run_dir, "trace.json"))
    obs_dir = os.path.join(res.run_dir, "observations")
    assert os.path.isdir(obs_dir)
    assert len(os.listdir(obs_dir)) == 1


# --------------------------------------------------------------------------- #
# 7. SPARK not silently promoted                                              #
# --------------------------------------------------------------------------- #

def _load_sparks_statuses():
    text = open(os.path.join(RUN000, "sparks.md")).read()
    # Every table row that names a spark carries an explicit status token.
    statuses = re.findall(r"\|\s*(SPARK|CANDIDATE|TRIAL|SUPPORTED|GRADUATED|DEMOTED|RETIRED)\s*\|", text)
    return statuses


def test_all_passage001_sparks_are_spark_level():
    statuses = _load_sparks_statuses()
    assert len(statuses) >= 11
    assert all(s == "SPARK" for s in statuses), set(statuses)


def test_importing_passage001_emits_no_candidate_cards():
    # No candidate-card JSON/YAML is written into the run dir on import.
    files = os.listdir(RUN000)
    assert "candidates.json" not in files
    assert not any(f.startswith("cec-") for f in files)
    # sparks.md must be a bullet/table list, not a candidate-card store.
    text = open(os.path.join(RUN000, "sparks.md")).read()
    assert "candidate_id:" not in text


# --------------------------------------------------------------------------- #
# 8. ambiguous pct_ / pctx_ handling                                          #
# --------------------------------------------------------------------------- #

def test_classify_percept_id():
    assert rr.classify_percept_id("pct_opus_r12") == "attention_percept"
    assert rr.classify_percept_id("pctx_mrpi3rjk_0") == "expression_percept"
    # bare / ambiguous
    assert rr.classify_percept_id("pct_") == "unknown"
    assert rr.classify_percept_id("pctx_") == "unknown"
    assert rr.classify_percept_id("percept_1") == "unknown"
    assert rr.classify_percept_id("") == "unknown"
    with pytest.raises(TypeError):
        rr.classify_percept_id(None)


# --------------------------------------------------------------------------- #
# 9. failure / refusal as valid terminal outcomes                             #
# --------------------------------------------------------------------------- #

def test_refused_run_writes_terminal_event_without_raising(tmp_path):
    runs_root = str(tmp_path / "runs")
    res = rr.run(MANIFEST000, mode="capture", runs_root=runs_root,
                 refuse_reason="technical silence constraint: no organ available")
    assert res.status == "refused"
    trace = rr.load_json(os.path.join(res.run_dir, "trace.json"))
    assert trace["status"] == "refused"
    terminal = trace["events"][-1]
    assert terminal["terminal"] is True
    assert terminal["outcome"] == "refused"
    # And the written refusal trace still validates against the schema.
    schemas = rr.load_all_schemas()
    assert rr.validate(trace, schemas["trace"]) == []


def test_make_terminal_event_stalled_validates():
    schemas = rr.load_all_schemas()
    ev = rr.make_terminal_event("e9", "system", "stalled",
                                "ran out of budget", None)
    assert rr.validate(_trace_with(ev), schemas["trace"]) == []
    assert ev["outcome"] == "stalled"


# --------------------------------------------------------------------------- #
# 10. vendored validator sanity (guards against false-green schema checks)    #
# --------------------------------------------------------------------------- #

def test_vendored_validator_rejects_wrong_types():
    schemas = rr.load_all_schemas()
    manifest = rr.load_manifest(MANIFEST000)
    bad = copy.deepcopy(manifest)
    bad["mode"] = "production"  # not in enum
    assert any("enum" in e for e in rr.validate(bad, schemas["manifest"]))
    bad2 = copy.deepcopy(manifest)
    bad2["reconstructed"] = "yes"  # wrong type
    assert rr.validate(bad2, schemas["manifest"]) != []


RUN003 = os.path.join(REHEARSALS, "runs", "003-sensory-disagreement")


def test_003_a2_score_validates_and_replays_clean(monkeypatch):
    assert rr.validate(
        json.load(open(os.path.join(RUN003, "instrumented-score.json"))),
        rr.load_schema("instrumented_score")) == []

    def boom(*a, **k):
        raise AssertionError("replay invoked an adapter")

    for name in list(rehearsal_adapters.ALLOWLIST):
        monkeypatch.setitem(rehearsal_adapters.ALLOWLIST, name, boom)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    res = rr.run(os.path.join(RUN003, "manifest.yaml"), mode="replay")
    assert res.adapter_calls == 0 and len(res.observations) == 3


def test_003_manifest_records_reproduction_vs_depiction():
    # Amendment carried from 002F: this field decided A1's outcome and must be
    # stated on every subsequent run.
    man = rr.load_manifest(os.path.join(RUN003, "manifest.yaml"))
    assert man["reproduction_vs_depiction"] in {"reproduction", "depiction"}
    assert man["constraints"]["no_named_refusal_token"] is True
    assert man["constraints"]["model_budget"] == 2


def test_003_stayed_within_its_declared_call_budget():
    score = json.load(open(os.path.join(RUN003, "instrumented-score.json")))
    assert score["live_model_call_count"] <= score["model_call_budget"]
    for call in score["model_calls"]:
        assert call["finish_reason"] == "stop"
        assert call["emitted_think_block"] is False


# --------------------------------------------------------------------------- #
# 7. detached-ground sweep helper (R2-A2S)                                     #
# --------------------------------------------------------------------------- #

import detached_ground_sweep as dgs  # noqa: E402


def _resolve(ground, regions=(), grounds=()):
    return dgs.resolve_ground(ground, {r: r for r in regions}, {g: g for g in grounds})


def test_region_ground_detaches_only_when_its_region_is_gone():
    g = {"ground_type": "region", "region_id": "fine_0"}
    assert _resolve(g, regions=["fine_0"])["detached"] is False
    out = _resolve(g, regions=["arch_0"])
    assert out["detached"] is True and out["missing"] == ["fine_0"]
    assert out["kind"] == "reference"


def test_geometry_bearing_grounds_are_never_detached():
    # This is the invariant the sweep's headline finding rests on: field/frame
    # survived the same re-dissect that stranded the region grounds.
    for gtype in ("field", "path", "boundary", "frame"):
        out = _resolve({"ground_type": gtype}, regions=[])
        assert out["detached"] is False, gtype
        assert out["kind"] == "geometry", gtype


def test_composite_detaches_only_when_no_member_and_no_raw_points():
    # Mirrors resolveGround: a composite with ANY surviving member, or with raw
    # points of its own, is not detached. Treating it like a region ground would
    # over-count.
    base = {"ground_type": "constellation", "member_ids": ["g1", "g2"]}
    assert _resolve(base, grounds=["g1"])["detached"] is False
    assert _resolve(base, grounds=[])["detached"] is True
    with_points = {**base, "points": [[0.1, 0.1]]}
    assert _resolve(with_points, grounds=[])["detached"] is False
    # A composite with no members at all is not detached either.
    assert _resolve({"ground_type": "relation", "member_ids": []})["detached"] is False


def test_sweep_helper_is_pure_and_needs_no_database():
    # resolve_ground must be callable with plain dicts so the port can be tested
    # without touching production data.
    assert dgs.resolve_ground({"ground_type": "frame"}, {}, {}) == {
        "kind": "geometry", "detached": False, "missing": []}


# --------------------------------------------------------------------------- #
# 8. A3 additions: reuse_frozen + multi-image probes                           #
# --------------------------------------------------------------------------- #

RUN004 = os.path.join(REHEARSALS, "runs", "004-gesture-and-address")


def test_004_a3_score_validates_and_replays_clean(monkeypatch):
    assert rr.validate(
        json.load(open(os.path.join(RUN004, "instrumented-score.json"))),
        rr.load_schema("instrumented_score")) == []

    def boom(*a, **k):
        raise AssertionError("replay invoked an adapter")

    for name in list(rehearsal_adapters.ALLOWLIST):
        monkeypatch.setitem(rehearsal_adapters.ALLOWLIST, name, boom)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    res = rr.run(os.path.join(RUN004, "manifest.yaml"), mode="replay")
    assert res.adapter_calls == 0 and len(res.observations) == 3


def test_004_manifest_records_reproduction_per_image():
    # A3 mixes a painting reproduction with two photographs, so the field had to
    # move from run-level to per-image.
    man = rr.load_manifest(os.path.join(RUN004, "manifest.yaml"))
    imgs = man["seed_constellation"]["images"]
    assert len(imgs) == 3
    for im in imgs:
        assert im["reproduction_vs_depiction"] in {"reproduction", "depiction"}
    assert man["image_order"] == ["img-01", "img-02", "img-03"]
    assert man["constraints"]["no_named_refusal_token"] is True


def test_004_multi_image_observation_records_every_image_in_order():
    obs = json.load(open(os.path.join(
        RUN004, "observations", "004-gesture-and-address-obs2.json")))
    out = obs["output"]
    # Position is meaningful — the prompt addresses IMAGE 1/2/3 by index.
    assert out["image_count"] == 3
    assert len(out["images"]) == 3
    for img in out["images"]:
        assert img["sha256"] and img["bytes"] > 0
    assert out["image_path"] == out["images"][0]["path"]


def test_reuse_frozen_adopts_an_existing_observation_without_calling(tmp_path):
    # The budget-honesty path: a probe step may adopt an already-frozen
    # observation instead of re-calling the provider.
    runs_root = str(tmp_path / "runs")
    first = rr.run(MANIFEST000, mode="capture", runs_root=runs_root,
                   capture_targets=[MANIFEST000])
    assert first.adapter_calls == 1
    # Wipe the trace so the dir is no longer frozen, keeping the observation.
    os.remove(os.path.join(first.run_dir, "trace.json"))

    def boom(*a, **k):
        raise AssertionError("reuse_frozen must not invoke an adapter")

    saved = rehearsal_adapters.ALLOWLIST["local_file_digest"]
    rehearsal_adapters.ALLOWLIST["local_file_digest"] = boom
    try:
        res = rr.run(MANIFEST000, mode="capture", runs_root=runs_root,
                     probes=[{"adapter": "local_file_digest", "reuse_frozen": True,
                              "source_refs": ["x"]}])
    finally:
        rehearsal_adapters.ALLOWLIST["local_file_digest"] = saved
    assert res.adapter_calls == 0
    assert len(res.observations) == 1
    ev = [e for e in res.trace["events"] if e["kind"] == "CALL_ORGAN"][0]
    assert ev["provenance"].endswith(":reused_frozen")


def test_reuse_frozen_refuses_to_invent_a_missing_observation(tmp_path):
    runs_root = str(tmp_path / "runs")
    with pytest.raises(FileNotFoundError):
        rr.run(MANIFEST000, mode="capture", runs_root=runs_root,
               probes=[{"adapter": "local_file_digest", "reuse_frozen": True}])


RUN005 = os.path.join(REHEARSALS, "runs", "005-surface-becoming-structure")


def test_005_a4_score_validates_and_replays_clean(monkeypatch):
    assert rr.validate(
        json.load(open(os.path.join(RUN005, "instrumented-score.json"))),
        rr.load_schema("instrumented_score")) == []

    def boom(*a, **k):
        raise AssertionError("replay invoked an adapter")

    for name in list(rehearsal_adapters.ALLOWLIST):
        monkeypatch.setitem(rehearsal_adapters.ALLOWLIST, name, boom)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    res = rr.run(os.path.join(RUN005, "manifest.yaml"), mode="replay")
    assert res.adapter_calls == 0 and len(res.observations) == 3


def test_005_ran_at_native_resolution_without_anthropomorphic_priming():
    # A4's value as a spark-06 test depends on BOTH: the image was not degraded,
    # and neither prompt mentioned faces/eyes/gaze/bodies.
    man = rr.load_manifest(os.path.join(RUN005, "manifest.yaml"))
    assert man["constraints"]["no_anthropomorphic_priming"] is True
    assert man["reproduction_vs_depiction"] == "depiction"
    img = man["seed_constellation"]["images"][0]
    assert img["dimensions"] == "453x680"  # under the 768 probe cap => unscaled

    # Whole words only: R8 cannot avoid the word "surface", which contains "face".
    primes = ("face", "faces", "eye", "eyes", "gaze", "gazing", "body", "bodies",
              "head", "heads", "watching", "looking at us")
    obs_dir = os.path.join(RUN005, "observations")
    prompts = []
    for fn in sorted(os.listdir(obs_dir)):
        obs = json.load(open(os.path.join(obs_dir, fn)))
        if obs["adapter"] == "groq_vlm_probe":
            prompts.append(obs["output"]["prompt"].lower())
    assert len(prompts) == 2
    for prompt in prompts:
        for word in primes:
            assert re.search(rf"\b{re.escape(word)}\b", prompt) is None, \
                f"prompt primed anthropomorphism with {word!r}"


RUN006 = os.path.join(REHEARSALS, "runs", "006-narrative-overreach")


def test_006_a5_score_validates_and_replays_clean(monkeypatch):
    assert rr.validate(
        json.load(open(os.path.join(RUN006, "instrumented-score.json"))),
        rr.load_schema("instrumented_score")) == []

    def boom(*a, **k):
        raise AssertionError("replay invoked an adapter")

    for name in list(rehearsal_adapters.ALLOWLIST):
        monkeypatch.setitem(rehearsal_adapters.ALLOWLIST, name, boom)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    res = rr.run(os.path.join(RUN006, "manifest.yaml"), mode="replay")
    assert res.adapter_calls == 0 and len(res.observations) == 3


def test_006_stage_2_was_stateless_and_third_party_attributed():
    # The whole design depends on these. If stage 2 had carried stage 1's
    # transcript it would measure self-consistency pressure, not the sentence.
    man = rr.load_manifest(os.path.join(RUN006, "manifest.yaml"))
    assert man["constraints"]["stage_2_must_be_stateless"] is True
    assert man["constraints"]["no_iconographic_identification"] is True

    obs_dir = os.path.join(RUN006, "observations")
    prompts = []
    for fn in sorted(os.listdir(obs_dir)):
        obs = json.load(open(os.path.join(obs_dir, fn)))
        if obs["adapter"] == "groq_vlm_probe":
            prompts.append(obs["output"]["prompt"])
    assert len(prompts) == 2
    stage1, stage2 = prompts
    # Stage 1 must not contain the authored sentence at all.
    assert "grief" not in stage1.lower()
    assert "radiates" not in stage1.lower()
    # Stage 2 attributes the sentence to a third party, not the user or assistant.
    assert stage2.lower().startswith("someone has written this")
    assert "rotunda" in stage2.lower() and "nave" not in stage2.lower()
    # Neither prompt asks for an attribution.
    for p in prompts:
        for word in ("who made", "sculptor", "artist", "identify", "title of"):
            assert word not in p.lower()


def test_006_records_the_byte_identical_twin_and_checks_both():
    # A stray write could land on either document; checking only the named one
    # would miss it.
    pre = json.load(open(os.path.join(RUN006, "pre-state.json")))
    post = json.load(open(os.path.join(RUN006, "post-state.json")))
    assert set(pre) == set(post) == {
        "695be817a9ea58f1b6aef5fa", "695be817a9ea58f1b6aef5fb"}
    a, b = pre["695be817a9ea58f1b6aef5fa"], pre["695be817a9ea58f1b6aef5fb"]
    assert a["sha256"] == b["sha256"], "the twin is supposed to be byte-identical"
    assert a["cloudinary"] != b["cloudinary"], "but a distinct Cloudinary asset"
    for oid in pre:
        for key in ("regions", "grounds", "percepts", "text_blocks"):
            assert post[oid][key] == pre[oid][key], f"{oid}.{key} changed"


RUN007 = os.path.join(REHEARSALS, "runs", "007-anthropomorphism-ab")


def test_007_ab_score_validates_and_replays_clean(monkeypatch):
    assert rr.validate(
        json.load(open(os.path.join(RUN007, "instrumented-score.json"))),
        rr.load_schema("instrumented_score")) == []

    def boom(*a, **k):
        raise AssertionError("replay invoked an adapter")

    for name in list(rehearsal_adapters.ALLOWLIST):
        monkeypatch.setitem(rehearsal_adapters.ALLOWLIST, name, boom)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    res = rr.run(os.path.join(RUN007, "manifest.yaml"), mode="replay")
    assert res.adapter_calls == 0 and len(res.observations) == 3


def test_007_ab_isolated_exactly_one_variable():
    # The whole finding depends on this: identical stimulus, identical budget,
    # and the word "address" present in ONE arm only.
    obs_dir = os.path.join(RUN007, "observations")
    probes = []
    for fn in sorted(os.listdir(obs_dir)):
        obs = json.load(open(os.path.join(obs_dir, fn)))
        if obs["adapter"] == "groq_vlm_probe":
            probes.append(obs["output"])
    assert len(probes) == 2
    a, b = probes
    # same stimulus, byte-for-byte
    assert a["image_sha256"] == b["image_sha256"]
    assert a["model"] == b["model"]
    assert a["reasoning_effort"] == b["reasoning_effort"] == "none"
    # the variable, present in exactly one arm
    assert "address" in a["prompt"].lower()
    assert "address" not in b["prompt"].lower()
    # neither arm primed anthropomorphism (whole words; "surface" contains "face")
    primes = ("face", "faces", "eye", "eyes", "gaze", "body", "head", "watching")
    for p in (a["prompt"].lower(), b["prompt"].lower()):
        for word in primes:
            assert re.search(rf"\b{re.escape(word)}\b", p) is None, \
                f"prompt primed anthropomorphism with {word!r}"


def test_007_ab_manifest_preregistered_all_four_outcome_cells():
    # A null result had to be declared CONFOUNDED in advance, so the finding
    # could not be retrofitted to whatever came back.
    man = rr.load_manifest(os.path.join(RUN007, "manifest.yaml"))
    grid = man["design"]["interpretation_grid"]
    assert set(grid) == {"a_face_b_none", "a_face_b_face",
                         "a_none_b_none", "a_none_b_face"}
    assert "CONFOUNDED" in grid["a_none_b_none"].upper()
    assert man["design"]["variable_isolated"].strip().upper().startswith("PROMPT FRAME")
