"""
HARNESS-001A — the Perceptual Action Grammar, enforced in Python.

The frontend already has 28 tests for its half (`perceptualActions.test.js`). These are the
Python half, and they are not a translation of those: they test the three things that only
matter now that a SECOND runtime enforces the grammar, and that a model — not a lexicon — is
allowed to propose into it.

  1. FAIL CLOSED means the same thing here. `normalize_action` returns None, never a partial.
  2. THE PAYLOAD CLAMP is the wall between a model that cannot see and evidence it cannot have.
  3. THE LAWS ARE THE CONTRACT'S. Both runtimes read the same `when` clauses by the same ids.
"""
from __future__ import annotations

import pytest

from backend.services.inquiry import grammar


def _ok(**over):
    action = {"id": "act_1", "type": "brush_field", "label": "Brush fold", "intent": "",
              "source": "system", "status": "proposed", "requiresConfirmation": True,
              "target": "image", "createdAt": 0.0,
              "payload": {"field_role": "fold", "label": "folding"},
              "warnings": [], "provenance": {}}
    action.update(over)
    return action


# ── fail closed ──────────────────────────────────────────────────────────────

def test_a_valid_action_validates():
    assert grammar.validate_action(_ok()).valid


@pytest.mark.parametrize("raw", [None, "brush_field", 42, [], {"type": "brush_field"}])
def test_normalize_returns_none_rather_than_a_partial_object(raw):
    """A caller that gets a dict back may put it in an InquiryFrame and hand it to Lane B. A
    half-valid action consumed as real is exactly what the grammar exists to prevent."""
    assert grammar.normalize_action(raw) is None


def test_an_unknown_action_type_is_refused_by_name():
    verdict = grammar.validate_action(_ok(type="segment_folds"))
    assert not verdict.valid
    assert "segment_folds" in verdict.errors[0]


def test_an_unknown_role_is_an_error_and_never_a_coercion():
    verdict = grammar.validate_action(_ok(payload={"field_role": "sensuality_field",
                                                   "label": "x"}))
    assert not verdict.valid
    assert any("sensuality_field" in e for e in verdict.errors)


def test_a_missing_required_payload_key_refuses_the_action():
    assert not grammar.validate_action(_ok(payload={"field_role": "fold"})).valid


def test_a_payload_with_no_role_is_refused_rather_than_crashing_the_label():
    # A crash is not failing closed. `default_label` must be total so the action reaches
    # validation and is refused there.
    assert grammar.default_label("brush_field", {}) == "Brush a field"
    assert grammar.normalize_action({"type": "brush_field", "payload": {}}) is None


def test_requires_confirmation_is_the_specs_and_never_the_callers():
    action = grammar.normalize_action(_ok(requiresConfirmation=False), action_id="act_1")
    assert action["requiresConfirmation"] is True


def test_a_caller_cannot_declare_its_own_action_applied_through_an_unknown_status():
    assert not grammar.validate_action(_ok(status="committed")).valid


# ── the clamp ────────────────────────────────────────────────────────────────

def test_the_clamp_drops_geometry_and_records_that_it_did():
    kept, dropped = grammar.clamp_payload("brush_field", {
        "field_role": "fold", "label": "folding",
        "mask_rle": "0" * 40, "bbox": [0, 0, 10, 10], "confidence": 0.97, "region_id": "r_1"})
    assert kept == {"field_role": "fold", "label": "folding"}
    assert dropped == ["bbox", "confidence", "mask_rle", "region_id"]


def test_an_unknown_action_keeps_nothing_from_its_payload():
    """It is about to be refused by name anyway, and carrying its invented params forward would
    put model-authored data into a refusal record where a reader might mistake it for real."""
    kept, dropped = grammar.clamp_payload("segment_folds", {"prompt": "folds", "mask": "…"})
    assert kept == {}
    assert dropped == ["mask", "prompt"]


def test_normalize_clamps_by_default_so_geometry_cannot_ride_in():
    action = grammar.normalize_action(
        {"type": "brush_field", "payload": {"field_role": "fold", "label": "f",
                                            "mask_rle": "…", "confidence": 1.0}},
        action_id="act_1")
    assert set(action["payload"]) == {"field_role", "label"}


# ── the laws ─────────────────────────────────────────────────────────────────

def test_a_model_may_not_author_a_challenge():
    """P1 addendum §3.1 — the human's veto over the circuit, and the one rule here that is not
    about shape. Enforced from the contract, by id, in both runtimes."""
    payload = {"percept_ref": "draft", "challenge_type": "alternative_reading"}
    system = grammar.normalize_action({"type": "challenge_percept", "source": "system",
                                       "payload": payload}, action_id="a")
    model = grammar.normalize_action({"type": "challenge_percept", "source": "model_suggested",
                                      "payload": payload}, action_id="a")
    assert system is not None
    assert model is None
    assert not grammar.model_may_author("challenge_percept")


def test_a_dispatch_claim_is_refused_and_not_quietly_corrected():
    """A silently-reset dispatch flag is how a dispatch happens."""
    verdict = grammar.validate_action(_ok(
        type="ask_model_reading", target="operation", label="Ask the model to read this",
        payload={"requested_reading_type": "counter", "dispatch": {"sent": True}}))
    assert not verdict.valid
    assert any("dispatch.sent" in e for e in verdict.errors)


def test_an_ask_model_reading_carries_its_own_admission():
    verdict = grammar.validate_action(_ok(
        type="ask_model_reading", target="operation", label="Ask the model to read this",
        payload={"requested_reading_type": "counter"}))
    assert verdict.valid
    assert "Proposed only — no model call is made." in verdict.warnings


def test_an_act_needing_a_mark_says_so_on_itself():
    assert "Needs a mark from you on the image." in grammar.validate_action(_ok()).warnings
    assert grammar.action_needs_geometry(_ok())


def test_ask_model_reading_can_never_be_applied():
    assert "ask_model_reading" in grammar.NEVER_APPLIES


def test_an_out_of_vocabulary_insertion_mode_is_refused_twice_and_that_is_deliberate():
    # Once by the enum and once by the named law. Both messages exist in the contract and both
    # are shown: the enum says the value is outside a vocabulary, the law says which values.
    verdict = grammar.validate_action(_ok(
        type="start_manuscript", target="manuscript", label="Start a description",
        payload={"mode": "description", "insertion_mode": "saved"}))
    assert not verdict.valid
    assert len([e for e in verdict.errors if "insertion_mode" in e]) == 2


# ── labels ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("type_,payload,expected", [
    ("find_parts", {}, "Find parts"),
    ("brush_field", {"field_role": "fold"}, "Brush fold"),
    ("trace_direction", {"trace_role": "gaze_address"}, "Trace gaze / address"),
    ("connect_marks", {"relation_role": "contrast"}, "Connect — contrast"),
    ("start_manuscript", {"mode": "art_critique"}, "Start a critique"),
    ("start_manuscript", {}, "Start a passage"),
])
def test_default_labels_come_from_the_contracts_templates(type_, payload, expected):
    assert grammar.default_label(type_, payload) == expected


def test_validate_action_list_keeps_the_good_and_reports_the_bad():
    kept, rejected = grammar.validate_action_list([_ok(), _ok(type="not_a_thing")])
    assert len(kept) == 1
    assert rejected[0]["index"] == 1
    assert rejected[0]["errors"]
