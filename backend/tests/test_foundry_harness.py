"""Foundry Sandbox harness tests (RESEARCH-ONLY).

Covers the invariants the harness exists to enforce: manifest validation,
required-field rejection, production-mutation refusal, run scaffolding, seed
freezing, replay making ZERO adapter calls, and generated stubs carrying their
required sections.

Validator note: ``jsonschema`` is NOT installed in this venv — the harness
reuses the minimal Draft-2020-12 validator vendored in ``rehearsal_run``. These
tests exercise that shared validator through ``foundry_run``.
"""

import copy
import json
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import foundry_run as fr  # noqa: E402
import rehearsal_adapters  # noqa: E402

SANDBOXES = fr.FOUNDRY_SANDBOXES_DIR
FS001 = os.path.join(SANDBOXES, "FS-001-creative-circulation.yaml")
FS002 = os.path.join(SANDBOXES, "FS-002-textual-dynamism.yaml")
FS003 = os.path.join(SANDBOXES, "FS-003-model-orchestration.yaml")
TEMPLATE_MANIFEST = os.path.join(fr.FOUNDRY_TEMPLATES_DIR, "sandbox-manifest.yaml")

ALL_SANDBOXES = [FS001, FS002, FS003]


@pytest.fixture()
def valid_manifest():
    return fr.load_sandbox(FS001)


@pytest.fixture()
def runs_root(tmp_path):
    return str(tmp_path / "runs")


# --------------------------------------------------------------------------- #
# 1. valid manifests validate                                                  #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("path", ALL_SANDBOXES + [TEMPLATE_MANIFEST])
def test_shipped_manifests_are_valid(path):
    """Every manifest committed to the repo must validate — including the template."""
    assert os.path.exists(path), f"missing manifest {path}"
    assert fr.validate_sandbox(fr.load_sandbox(path)) == []


def test_sandbox_schema_loads():
    schema = fr.load_sandbox_schema()
    assert schema["$id"].endswith("foundry-sandbox.schema.json")
    assert schema["properties"]["mode"]["const"] == "foundry"
    assert schema["properties"]["research_only"]["const"] is True


def test_three_first_sandboxes_cover_three_distinct_axes():
    axes = {fr.load_sandbox(p)["axis"] for p in ALL_SANDBOXES}
    assert axes == {"creative-circulation", "textual-dynamism", "model-orchestration"}


# --------------------------------------------------------------------------- #
# 2. missing required fields fail                                              #
# --------------------------------------------------------------------------- #

REQUIRED_TOP_LEVEL = [
    "sandbox_id", "axis", "research_question", "mode", "research_only",
    "allowed_inputs", "forbidden_actions", "seed_images", "seed_text_slices",
    "model_budget", "adapters", "capture_policy", "replay_policy",
    "scoring_rubric", "stop_condition", "graduation_rule",
    "product_implication_section",
]


@pytest.mark.parametrize("field", REQUIRED_TOP_LEVEL)
def test_missing_required_field_is_rejected(valid_manifest, field):
    m = copy.deepcopy(valid_manifest)
    del m[field]
    errs = fr.validate_sandbox(m)
    assert errs, f"deleting {field} should invalidate the manifest"
    assert any(field in e for e in errs), errs


def test_bad_sandbox_id_pattern_is_rejected(valid_manifest):
    m = copy.deepcopy(valid_manifest)
    m["sandbox_id"] = "creative-circulation-1"  # missing the FS-### prefix
    assert any("sandbox_id" in e for e in fr.validate_sandbox(m))


def test_unknown_axis_is_rejected(valid_manifest):
    m = copy.deepcopy(valid_manifest)
    m["axis"] = "vibes"
    assert any("axis" in e for e in fr.validate_sandbox(m))


def test_assert_valid_sandbox_raises(valid_manifest):
    m = copy.deepcopy(valid_manifest)
    del m["axis"]
    with pytest.raises(fr.FoundryError):
        fr.assert_valid_sandbox(m)


# --------------------------------------------------------------------------- #
# 3. production mutation flags / paths are rejected                            #
# --------------------------------------------------------------------------- #

def test_research_only_false_is_rejected(valid_manifest):
    m = copy.deepcopy(valid_manifest)
    m["research_only"] = False
    errs = fr.validate_sandbox(m)
    assert any("research_only" in e for e in errs), errs


def test_non_foundry_mode_is_rejected(valid_manifest):
    m = copy.deepcopy(valid_manifest)
    m["mode"] = "instrumented"
    assert any("mode" in e for e in fr.validate_sandbox(m))


@pytest.mark.parametrize("dropped", list(fr.REQUIRED_FORBIDDEN))
def test_dropping_a_baseline_forbidden_action_is_rejected(valid_manifest, dropped):
    """forbidden_actions must stay a SUPERSET of the baseline."""
    m = copy.deepcopy(valid_manifest)
    m["forbidden_actions"] = [f for f in m["forbidden_actions"] if f != dropped]
    errs = fr.validate_sandbox(m)
    assert any(dropped in e for e in errs), errs


@pytest.mark.parametrize("bad_path", [
    "mongodb://localhost:27017/semant",
    "backend/routers/posts.py",
    "backend/main.py",
    "frontend/src/components/RegionSurface.jsx",
    "region_embeddings",
    ".env",
])
def test_production_paths_in_allowed_inputs_are_rejected(valid_manifest, bad_path):
    m = copy.deepcopy(valid_manifest)
    m["allowed_inputs"] = list(m["allowed_inputs"]) + [bad_path]
    errs = fr.validate_sandbox(m)
    assert any("production path marker" in e for e in errs), errs


def test_production_path_in_seed_ref_is_rejected(valid_manifest):
    m = copy.deepcopy(valid_manifest)
    m["seed_images"] = list(m["seed_images"]) + [
        {"ref": "backend/models/post.py", "role": "smuggled"}
    ]
    errs = fr.validate_sandbox(m)
    assert any("production path marker" in e for e in errs), errs


def test_unapproved_live_calls_are_rejected(valid_manifest):
    """A budget cannot spend live calls without explicit approval."""
    m = copy.deepcopy(valid_manifest)
    m["model_budget"]["max_live_calls"] = 3
    m["model_budget"]["approved"] = False
    m["adapters"] = ["groq_vlm_probe"]
    errs = fr.validate_sandbox(m)
    assert any("approved: true" in e for e in errs), errs


def test_live_calls_without_adapters_are_rejected(valid_manifest):
    m = copy.deepcopy(valid_manifest)
    m["model_budget"]["max_live_calls"] = 1
    m["model_budget"]["approved"] = True
    m["adapters"] = []
    errs = fr.validate_sandbox(m)
    assert any("no adapters" in e for e in errs), errs


def test_non_allowlisted_adapter_is_rejected(valid_manifest):
    m = copy.deepcopy(valid_manifest)
    m["adapters"] = ["gpt5_omniscient_probe"]
    errs = fr.validate_sandbox(m)
    assert any("not allowlisted" in e for e in errs), errs


def test_declared_adapters_exist_in_shared_allowlist():
    """The foundry must not drift from the rehearsal adapter allowlist."""
    for path in ALL_SANDBOXES:
        for a in fr.load_sandbox(path)["adapters"]:
            assert a in rehearsal_adapters.ALLOWLIST


def test_replay_policy_cannot_permit_adapter_calls(valid_manifest):
    m = copy.deepcopy(valid_manifest)
    m["replay_policy"]["adapter_calls_permitted"] = 2
    errs = fr.validate_sandbox(m)
    assert any("adapter_calls_permitted" in e for e in errs), errs


def test_model_orchestration_sandbox_ships_blocked():
    """FS-003 must be committed unable to spend — its budget is zero and unapproved."""
    m = fr.load_sandbox(FS003)
    assert m["model_budget"]["max_live_calls"] == 0
    assert m["model_budget"]["approved"] is False


# --------------------------------------------------------------------------- #
# 4. init creates the expected structure                                       #
# --------------------------------------------------------------------------- #

def test_init_creates_expected_structure(runs_root):
    state = fr.init_run(FS001, runs_root=runs_root)
    rdir = fr.run_dir_for(state["run_id"], runs_root)
    assert os.path.isdir(rdir)
    assert os.path.isdir(os.path.join(rdir, "observations"))
    assert os.path.isfile(os.path.join(rdir, fr.RUN_STATE_FILE))

    assert state["sandbox_id"] == "FS-001-creative-circulation"
    assert state["axis"] == "creative-circulation"
    assert state["mode"] == "foundry"
    assert state["research_only"] is True
    assert state["status"] == "initialised"
    assert len(state["manifest_sha256"]) == 64
    # No wall-clock invention — the substrate's honesty rule.
    assert state["created_at"] is None
    assert state["created_at_null_reason"]


def test_init_refuses_to_overwrite_without_force(runs_root):
    fr.init_run(FS001, runs_root=runs_root)
    with pytest.raises(FileExistsError):
        fr.init_run(FS001, runs_root=runs_root)
    fr.init_run(FS001, runs_root=runs_root, force=True)  # explicit re-init is allowed


def test_init_refuses_an_invalid_manifest(tmp_path, runs_root, valid_manifest):
    m = copy.deepcopy(valid_manifest)
    m["research_only"] = False
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(m))
    with pytest.raises(fr.FoundryError):
        fr.init_run(str(bad), runs_root=runs_root)
    # and it must not have left a directory behind
    assert not os.path.exists(fr.run_dir_for(m["sandbox_id"], runs_root))


def test_init_writes_nothing_outside_the_runs_root(runs_root):
    state = fr.init_run(FS001, runs_root=runs_root)
    rdir = fr.run_dir_for(state["run_id"], runs_root)
    for path in [p for p, _, _ in os.walk(runs_root)]:
        assert os.path.abspath(path).startswith(os.path.abspath(runs_root))
    assert os.path.abspath(rdir).startswith(os.path.abspath(runs_root))


# --------------------------------------------------------------------------- #
# 5. seed freezing                                                             #
# --------------------------------------------------------------------------- #

def test_freeze_records_hashes_for_present_seeds(runs_root):
    state = fr.init_run(FS001, runs_root=runs_root)
    rdir = fr.run_dir_for(state["run_id"], runs_root)
    payload = fr.freeze_seeds(FS001, rdir)

    assert payload["seed_count"] == len(payload["seeds"])
    assert payload["present_count"] >= 1, "FS-001 points at real fixtures"
    for seed in payload["seeds"]:
        if seed["status"] == "present":
            assert len(seed["sha256"]) == 64
            assert seed["size_bytes"] > 0
        else:
            assert seed["sha256"] is None
    assert os.path.isfile(os.path.join(rdir, fr.SEEDS_FILE))
    assert fr.load_run_state(rdir)["seeds_frozen"] is True


def test_freeze_records_missing_seeds_without_crashing(tmp_path, runs_root, valid_manifest):
    m = copy.deepcopy(valid_manifest)
    m["seed_images"] = [{"ref": "vault/does/not/exist.png", "role": "absent"}]
    m["seed_text_slices"] = []
    mp = tmp_path / "m.json"
    mp.write_text(json.dumps(m))
    state = fr.init_run(str(mp), runs_root=runs_root)
    rdir = fr.run_dir_for(state["run_id"], runs_root)

    payload = fr.freeze_seeds(str(mp), rdir)
    assert payload["missing_count"] == 1
    assert payload["seeds"][0]["status"] == "missing"

    with pytest.raises(fr.FoundryError):
        fr.freeze_seeds(str(mp), rdir, strict=True)


# --------------------------------------------------------------------------- #
# 6. replay makes ZERO adapter calls                                           #
# --------------------------------------------------------------------------- #

def test_replay_does_not_call_live_adapters(runs_root, monkeypatch):
    """Booby-trap every allowlisted adapter; replay must still succeed."""
    state = fr.init_run(FS001, runs_root=runs_root)
    rdir = fr.run_dir_for(state["run_id"], runs_root)

    def explode(*_a, **_k):  # pragma: no cover - must never run
        raise AssertionError("replay invoked a live adapter")

    for name in list(rehearsal_adapters.ALLOWLIST):
        monkeypatch.setitem(rehearsal_adapters.ALLOWLIST, name, explode)
    monkeypatch.setattr(rehearsal_adapters, "get_adapter", explode)

    result = fr.replay(rdir)
    assert result.adapter_calls == 0
    assert result.status == "replayed"
    assert result.observations == []


def test_replay_validates_frozen_observations(runs_root):
    state = fr.init_run(FS001, runs_root=runs_root)
    rdir = fr.run_dir_for(state["run_id"], runs_root)
    obs_path = os.path.join(rdir, "observations", "bogus.json")
    with open(obs_path, "w") as fh:
        json.dump({"not": "an observation"}, fh)
    with pytest.raises(Exception):
        fr.replay(rdir)


def test_replay_requires_an_initialised_run(tmp_path):
    with pytest.raises(FileNotFoundError):
        fr.replay(str(tmp_path))


def test_replay_reads_a_real_frozen_observation(runs_root):
    """A genuine R2 observation must replay through the foundry path unchanged."""
    src = os.path.join(
        os.path.dirname(fr.FOUNDRY_ROOT), "runs", "010-sameness-assertion-arm-e",
        "observations", "010-sameness-assertion-arm-e-obs0.json",
    )
    if not os.path.exists(src):
        pytest.skip("R2 run 010 observation not present")
    state = fr.init_run(FS001, runs_root=runs_root)
    rdir = fr.run_dir_for(state["run_id"], runs_root)
    with open(src) as fh:
        obs = json.load(fh)
    with open(os.path.join(rdir, "observations", "obs0.json"), "w") as fh:
        json.dump(obs, fh)

    result = fr.replay(rdir)
    assert result.adapter_calls == 0
    assert result.observations == ["obs0.json"]


# --------------------------------------------------------------------------- #
# 7. generated stubs carry their required sections                             #
# --------------------------------------------------------------------------- #

REQUIRED_SECTIONS = {
    "score.md": ["## 2. Evidence", "## 3. Reading", "## 4. Opening",
                 "## 5. Resistance", "## 6. Scoring rubric", "## 8. Withheld"],
    "critique.md": ["## 2. Deflationary reading", "## 4. Method corrections",
                    "## 5. What would kill this finding"],
    "sparks.md": ["## Spark register", "## Withheld", "## Unresolved questions"],
    "horizon-brief.md": ["## 2. What axis moved", "## 3. What product pressure appeared",
                         "## 4. What repeated pattern emerged", "## 5. What should be studied",
                         "## 6. What should NOT be built yet"],
    "product-implications.md": ["## 2. Nearest existing construct",
                                "## 5. Deliberately NOT concluded",
                                "## 8. Graduation status"],
}


def test_summarize_writes_all_stubs_with_required_sections(runs_root):
    state = fr.init_run(FS001, runs_root=runs_root)
    rdir = fr.run_dir_for(state["run_id"], runs_root)
    written = fr.summarize(FS001, rdir)

    assert sorted(written) == sorted(fr.SUMMARY_TEMPLATES)
    for name, sections in REQUIRED_SECTIONS.items():
        text = open(os.path.join(rdir, name)).read()
        for section in sections:
            assert section in text, f"{name} missing {section!r}"
        # placeholders must be substituted, not shipped raw
        assert "{{SANDBOX_ID}}" not in text
        assert "{{AXIS}}" not in text
        assert state["run_id"] in text
    assert fr.load_run_state(rdir)["summarized"] is True


def test_summarize_renders_the_rubric_from_the_manifest(runs_root):
    state = fr.init_run(FS001, runs_root=runs_root)
    rdir = fr.run_dir_for(state["run_id"], runs_root)
    fr.summarize(FS001, rdir)
    score = open(os.path.join(rdir, "score.md")).read()
    for dim in fr.load_sandbox(FS001)["scoring_rubric"]["dimensions"]:
        assert dim["name"] in score
    assert "{{RUBRIC_ROWS}}" not in score


def test_summarize_does_not_clobber_written_research(runs_root):
    state = fr.init_run(FS001, runs_root=runs_root)
    rdir = fr.run_dir_for(state["run_id"], runs_root)
    fr.summarize(FS001, rdir)
    score_path = os.path.join(rdir, "score.md")
    with open(score_path, "w") as fh:
        fh.write("REAL RESEARCH FINDINGS")

    again = fr.summarize(FS001, rdir)
    assert "score.md" not in again
    assert open(score_path).read() == "REAL RESEARCH FINDINGS"

    fr.summarize(FS001, rdir, force=True)
    assert "REAL RESEARCH" not in open(score_path).read()


def test_every_stub_declares_research_only(runs_root):
    state = fr.init_run(FS001, runs_root=runs_root)
    rdir = fr.run_dir_for(state["run_id"], runs_root)
    fr.summarize(FS001, rdir)
    for name in fr.SUMMARY_TEMPLATES:
        assert "RESEARCH-ONLY" in open(os.path.join(rdir, name)).read()


# --------------------------------------------------------------------------- #
# 8. the harness does not couple to production                                 #
# --------------------------------------------------------------------------- #

def test_harness_imports_nothing_from_backend():
    source = open(os.path.join(SCRIPTS_DIR, "foundry_run.py")).read()
    assert "import backend" not in source
    assert "from backend" not in source
    # pymongo/motor may appear ONLY as strings in the deny list, never as imports.
    for token in ("import pymongo", "import motor", "from pymongo", "from motor"):
        assert token not in source


def test_v1_has_no_capture_command():
    """CAPTURE is deliberately not implemented in v1 — no live-call path exists."""
    parser = fr._build_parser()
    actions = [a for a in parser._actions if hasattr(a, "choices") and a.choices]
    commands = set()
    for a in actions:
        if isinstance(a.choices, dict):
            commands |= set(a.choices)
    assert commands == {"validate", "init", "freeze", "replay", "summarize"}
    assert "capture" not in commands


# --------------------------------------------------------------------------- #
# 9. CLI end-to-end                                                            #
# --------------------------------------------------------------------------- #

def _cli(*args, expect=0):
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "foundry_run.py"), *args],
        capture_output=True, text=True,
    )
    assert proc.returncode == expect, proc.stderr or proc.stdout
    return proc


def test_cli_validate_ok_and_failing(tmp_path, valid_manifest):
    out = _cli("validate", FS001).stdout
    assert json.loads(out)["valid"] is True

    m = copy.deepcopy(valid_manifest)
    m["research_only"] = False
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(m))
    out = _cli("validate", str(bad), expect=1).stdout
    payload = json.loads(out)
    assert payload["valid"] is False and payload["errors"]


def test_cli_full_lifecycle(tmp_path):
    runs_root = str(tmp_path / "runs")
    _cli("init", FS001, "--runs-root", runs_root)
    _cli("freeze", FS001, "--runs-root", runs_root)
    _cli("summarize", FS001, "--runs-root", runs_root)
    rdir = os.path.join(runs_root, "FS-001-creative-circulation")
    out = json.loads(_cli("replay", rdir).stdout)
    assert out["adapter_calls"] == 0
    assert out["status"] == "replayed"
