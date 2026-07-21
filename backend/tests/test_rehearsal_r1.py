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


def test_only_local_file_digest_is_allowlisted():
    assert set(rehearsal_adapters.ALLOWLIST) == {"local_file_digest"}
    forbidden = {"sam", "sam2", "yolo", "segformer", "dinov2",
                 "fashionclip", "fashion_clip", "semantic", "llm"}
    assert forbidden.isdisjoint(set(rehearsal_adapters.ALLOWLIST))


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
