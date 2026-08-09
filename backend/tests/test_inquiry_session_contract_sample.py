"""
HARNESS-002D §7 — the checked-in contract samples are what the backend actually produces.

The samples in `contracts/samples/` are the seam between this lane and the frontend, and the
frontend's parity suite imports them directly. That only means anything if they cannot be edited by
hand and cannot go stale: a sample nobody regenerates is a third opinion about the wire shape, and
it is the one that agrees with whichever half was written last.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "contracts" / "samples"


def _script():
    spec = importlib.util.spec_from_file_location(
        "inquiry_contract_sample", ROOT / "scripts" / "inquiry_contract_sample.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_checked_in_samples_are_byte_identical_to_a_fresh_build():
    fresh = _script().samples()
    for name, body in fresh.items():
        path = SAMPLES / name
        assert path.exists(), f"{name} is missing; run scripts/inquiry_contract_sample.py"
        assert path.read_text(encoding="utf-8") == body, (
            f"contracts/samples/{name} has drifted from the backend. Run "
            f"`python scripts/inquiry_contract_sample.py` and commit the result — the frontend "
            f"parity suite reads this file, and a stale one makes that suite agree with nothing.")


def test_generating_twice_produces_the_same_bytes():
    """Determinism, which is what makes the drift check above a real comparison rather than noise.

    It is not free: the framer mints its inquiry id from the prompt AND the moment, and every id
    the compiler derives downstream is keyed on that. The coordinator hands the framer the stage
    clock for exactly this reason.
    """
    script = _script()
    assert script.samples() == script.samples()


@pytest.mark.parametrize("name", ["awaiting-user", "complete", "auto-complete"])
def test_each_sample_is_the_state_it_is_named_for(name):
    body = json.loads((SAMPLES / f"inquiry-session.{name}.json").read_text(encoding="utf-8"))
    expected = {"awaiting-user": "awaiting_user", "complete": "complete",
                "auto-complete": "complete"}[name]
    assert body["state"] == expected
    assert body["mode"] == ("auto" if name == "auto-complete" else "consult")


def test_no_sample_contains_an_evidence_object_or_an_evidence_grade_receipt():
    """The samples are also the thing a person reads to see what Phase 1 sends. One carrying a
    usable receipt would teach the wrong shape to whoever writes the next client."""
    for path in SAMPLES.glob("inquiry-session.*.json"):
        body = json.loads(path.read_text(encoding="utf-8"))
        assert body["evidence"] == [], path.name
        for receipt in body["capability_receipts"]:
            assert receipt["execution_mode"] == "fixture"
            assert receipt["status"] == "simulated"
            assert receipt["usable_as_evidence"] is False
        for section in (body.get("synthesis") or {}).get("sections", []):
            assert section["status"] not in ("measured", "visible")
            assert section["evidence_refs"] == []
