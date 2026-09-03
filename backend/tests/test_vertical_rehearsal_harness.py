"""
ATLAS-WRITER-MASS-BUILD-001L — the harness's own floor.

The rehearsal itself needs mongod, Chromium and a built frontend, and runs as its own gate
(`scripts/vertical_rehearsal.py`; `.github/workflows/vertical-rehearsal.yml`). What is proved HERE
is the part that must hold before that command is worth running: the corpus is deterministic and
never a production post, the diff the audit prints is a real field-level diff, the summary a run
leaves behind validates against its schema, and the harness refuses to serve outside the harness.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))      # `rehearsal_run` imports its adapters top-level

from scripts.vertical_rehearsal_support import corpus as C  # noqa: E402
from scripts.vertical_rehearsal_support import ledger as L  # noqa: E402
import rehearsal_run  # noqa: E402

VERTICAL = ROOT / "research" / "rehearsals" / "vertical"
SCHEMA = json.loads((VERTICAL / "schemas" / "vertical-summary.schema.json").read_text())


# ── the corpus ────────────────────────────────────────────────────────────────────────────────

def test_the_corpus_renders_the_same_bytes_twice(tmp_path):
    rows = C.core_manifest()
    a = C.render_all(rows, tmp_path / "a")
    b = C.render_all(rows, tmp_path / "b")
    assert a == b
    assert len(a) == len(rows) == 10


def test_every_mark_is_the_line_the_renderer_drew():
    """The audit knows the marks by construction: the mark geometry IS the drawn line."""
    for row in C.core_manifest():
        for m in range(int(row["marks"])):
            mark = C.mark_for(int(row["seed"]), m)
            assert mark["geometry"]["kind"] == "path"
            assert mark["status"] == "committed" and mark["source"] == "user_confirmed"
            assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in mark["geometry"]["points"])


def test_a_fixture_post_is_stamped_and_never_a_production_post():
    doc = C.post_document(C.core_manifest()[0], "http://127.0.0.1:1/img")
    assert doc["photo_public_id"] == C.FIXTURE_PUBLIC_ID
    assert doc["fixture"]["harness"] == "ATLAS-WRITER-MASS-BUILD-001L"
    assert doc["photo_url"].startswith("http://127.0.0.1:1/")
    assert doc["visual_marks"] and doc["region_annotations"]


def test_the_unreadable_row_points_at_an_image_that_does_not_exist():
    row = next(r for r in C.core_manifest() if not r["readable"])
    doc = C.post_document(row, "http://127.0.0.1:1")
    assert "missing-" in doc["photo_url"]


def test_the_performance_corpus_is_sixty():
    assert len(C.perf_manifest()) == 60


def test_the_real_photo_profile_is_unavailable_when_unset(monkeypatch):
    monkeypatch.delenv("SEMANT_VERTICAL_REAL_PHOTOS", raising=False)
    assert C.real_photo_profile() is None


# ── the ledger ────────────────────────────────────────────────────────────────────────────────

def test_a_canonical_hash_ignores_key_order_and_sees_a_changed_value():
    a = {"x": 1, "marks": [{"id": "m1"}]}
    b = {"marks": [{"id": "m1"}], "x": 1}
    assert L.digest(a) == L.digest(b)
    assert L.digest(a) != L.digest({**a, "x": 2})


def test_the_diff_is_field_level_and_names_removed_list_items():
    before = {"visual_marks": [{"id": "a"}, {"id": "b"}], "updated_at": 1}
    after = {"visual_marks": [{"id": "a"}], "updated_at": 2}
    diff = L.field_diff(before, after)
    paths = {(d["path"], d["kind"]) for d in diff}
    assert ("visual_marks[1]", "removed") in paths
    assert ("updated_at", "changed") in paths
    assert ("visual_marks[0].id", "changed") not in paths


def test_the_evidence_record_serialises_whatever_it_is_handed():
    ev = L.Evidence()
    ev.record_id("s", oid=object())
    ev.refusal("s", reason="x", writes=0)
    out = ev.to_dict()
    assert isinstance(out["ids"]["s"]["oid"], str)
    assert out["refusals"][0]["reason"] == "x"
    json.dumps(out)


# ── the summary ───────────────────────────────────────────────────────────────────────────────

def _committed_summaries():
    return sorted((VERTICAL / "runs").glob("*/summary.json"))


@pytest.mark.parametrize("path", _committed_summaries() or [None])
def test_every_committed_run_summary_validates_against_the_schema(path):
    if path is None:
        pytest.skip("no committed run record yet")
    summary = json.loads(path.read_text())
    errors = rehearsal_run.validate(summary, SCHEMA)
    assert not errors, errors
    assert summary["gate"]["status"] in ("pass", "blocked", "fail")
    # an assertion is never green by default: every non-pass row names its evidence
    for a in summary["assertions"]:
        assert a["evidence"], a


def test_a_committed_run_links_every_failed_stage_to_a_lane():
    for path in _committed_summaries():
        s = json.loads(path.read_text())
        for st in s["stages"]:
            if st["status"] in ("fail", "unavailable"):
                assert st["lane"] or "harness" in st["detail"].lower() or st["name"].startswith("profile."), st


def test_the_schema_rejects_a_summary_that_claims_a_pass_with_no_assertions():
    bogus = {"harness": "ATLAS-WRITER-MASS-BUILD-001L", "run_id": "x", "mode": "offline",
             "profile": "default", "base": {"commit": "c", "branch": "b"},
             "stack": {"fakes": "all", "boot_seconds": {}, "backend_restarts": 0},
             "stages": [], "assertions": [], "gate": {"status": "pass", "failed_stages": [],
                                                     "unavailable_stages": [], "lanes_preventing_full_pass": []},
             "hashes": {"before": {}, "after": {}, "changed": []},
             "evidence": {k: [] for k in ("receipts", "refusals", "operations", "hash_timeline",
                                          "expected_writes", "unexpected", "screenshots", "timings")} | {"ids": {}}}
    assert rehearsal_run.validate(bogus, SCHEMA), "ten assertions are the floor"


# ── the command ───────────────────────────────────────────────────────────────────────────────

def test_the_entry_refuses_to_serve_outside_the_harness():
    env = {k: v for k, v in os.environ.items() if k != "SEMANT_VERTICAL_HARNESS"}
    proc = subprocess.run([sys.executable, "-c",
                           "import scripts.vertical_rehearsal_support.app_entry"],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode != 0
    assert "SEMANT_VERTICAL_HARNESS" in (proc.stderr + proc.stdout)


def test_list_stages_names_the_whole_circuit():
    proc = subprocess.run([sys.executable, "scripts/vertical_rehearsal.py", "--list-stages"],
                          cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    names = {line.split()[0] for line in proc.stdout.splitlines() if line.strip()}
    for needed in ("walk.save_open", "atlas.canvas", "atlas.light_table", "differential", "relation",
                   "plan", "draft", "draft.accept", "writer", "movement", "profile.lost_response",
                   "profile.restart_mid", "profile.stale_tab", "profile.unavailable_model",
                   "profile.unreadable_image", "profile.injected_writes", "a11y", "performance"):
        assert needed in names


def test_budgets_are_declared_for_every_measure_the_profile_takes():
    budgets = json.loads((VERTICAL / "budgets.json").read_text())
    for k in ("initial_hydration", "pan", "zoom", "mode_switch", "notes_save"):
        assert k in budgets["ms"] and budgets["ms"][k] > 0
    assert budgets["memory_mb"]["js_heap_after_interaction"] > 0


@pytest.mark.skipif(os.environ.get("SEMANT_VERTICAL") != "1",
                    reason="the full rehearsal needs mongod, Chromium and a built frontend; "
                           "set SEMANT_VERTICAL=1 to run it here")
def test_the_full_offline_rehearsal_runs(tmp_path):
    proc = subprocess.run([sys.executable, "scripts/vertical_rehearsal.py", "--out", str(tmp_path),
                           "--run-id", "pytest"], cwd=ROOT, capture_output=True, text=True, timeout=1800)
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert not rehearsal_run.validate(summary, SCHEMA)
    assert proc.returncode in (0, 1, 2), proc.stdout[-2000:]
