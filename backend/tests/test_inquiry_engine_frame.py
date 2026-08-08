"""
HARNESS-001B §3 — `InquiryFrame` intake, and the A→B seam.

Lane A and Lane B are being built at the same time. B accepts by SHAPE and does not import A. What
this file pins is that the intake is permissive where it must be (Lane A's representation choices)
and strict where it must be (the contract, and the prompt).

## The cross-lane test

`test_lane_a_real_frame_passes_through_the_intake_unchanged` is SKIPPED until Lane A merges, and it
skips out loud with a reason rather than being absent. A test that does not exist yet is invisible;
a skip is in the summary line where a reader can see the shape of what is not covered.
"""
from __future__ import annotations

import importlib.util

import pytest

from backend.services.inquiry_engine import fixtures
from backend.services.inquiry_engine.frame import (REQUIRED_KEYS, SCHEMA_VERSION, AcceptedFrame,
                                                   FrameRefused, accept)

HAS_LANE_A = importlib.util.find_spec("backend.services.prompt_mind") is not None
LANE_A_SKIP = ("Lane A (`feat/prompt-decision-mind`) has not merged. Until it does, Lane B accepts "
               "`inquiry-frame.v1` by shape and does not import Lane A — the board's rule for "
               "building the two in parallel.")


# ── 1. what intake refuses ───────────────────────────────────────────────────

def test_a_frame_from_a_different_contract_is_refused_rather_than_read_leniently():
    frame = {**fixtures.control_frame(), "schema_version": "inquiry-frame.v2"}
    with pytest.raises(FrameRefused, match="schema_version"):
        accept(frame)


@pytest.mark.parametrize("missing", REQUIRED_KEYS)
def test_every_pinned_key_is_required_as_a_key(missing):
    """Required as KEYS, not as non-empty values: an empty `unresolved_terms` is the claim that
    nothing was left unresolved, and a missing one is a frame that cannot make that claim."""
    frame = {k: v for k, v in fixtures.control_frame().items() if k != missing}
    with pytest.raises(FrameRefused):
        accept(frame)


def test_an_empty_proposed_actions_list_is_accepted_because_it_is_a_real_answer():
    frame = {**fixtures.control_frame(), "proposed_actions": []}
    accepted = accept(frame)
    assert accepted.proposed_actions == ()


def test_a_frame_with_no_prompt_is_refused_because_nothing_downstream_could_be_checked():
    frame = {**fixtures.control_frame(), "prompt": "   "}
    with pytest.raises(FrameRefused, match="no prompt"):
        accept(frame)


def test_a_non_mapping_is_refused_by_name():
    with pytest.raises(FrameRefused, match="must be a mapping"):
        accept(["schema_version", SCHEMA_VERSION])          # type: ignore[arg-type]


# ── 2. the prompt is preserved byte for byte ─────────────────────────────────

def test_the_prompt_is_carried_verbatim_and_never_rewritten():
    """Every refusal downstream is only checkable against what was actually asked."""
    raw = fixtures.fold_frame()
    accepted = accept(raw)
    assert accepted.prompt == raw["prompt"]
    assert accepted.raw["prompt"] == raw["prompt"]
    assert accepted.to_dict()["prompt"] == raw["prompt"]


# ── 3. the intake adapter owns representation adjustment ─────────────────────

def test_structured_entries_are_read_and_the_adjustment_is_recorded_rather_than_silent():
    """Lane A may emit strings or mappings for the list fields. Both are read; the reshaping is
    said out loud so the seam is inspectable rather than assumed."""
    frame = {**fixtures.control_frame(),
             "attentions": [{"text": "nestedness"}, {"phrase": "adjacency"}],
             "unresolved_terms": [{"term": "fold curvature"}]}
    accepted = accept(frame)
    assert accepted.attentions == ("nestedness", "adjacency")
    assert accepted.unresolved_terms == ("fold curvature",)
    assert any("attentions" in a for a in accepted.adjustments)
    assert any("unresolved_terms" in a for a in accepted.adjustments)


def test_a_frame_already_in_the_expected_shape_needs_no_adjustment():
    """The negative control for the test above: prove `adjustments` is not always non-empty, or it
    would say nothing when it fires."""
    assert accept(fixtures.control_frame()).adjustments == ()


def test_an_action_with_no_readable_type_is_carried_and_refused_by_name_not_dropped():
    """A dropped proposal is invisible in the run; an unnamed one is a fact about the frame."""
    frame = {**fixtures.control_frame(), "proposed_actions": [{"role": "fold"}]}
    accepted = accept(frame)
    assert len(accepted.proposed_actions) == 1
    assert accepted.proposed_actions[0].type == ""
    assert any("no readable action type" in a for a in accepted.adjustments)


def test_extra_keys_are_carried_rather_than_rejected():
    """A frame richer than the minimum is Lane A doing its job."""
    frame = {**fixtures.control_frame(), "confidence_notes": ["a"], "lane_a_version": 3}
    accepted = accept(frame)
    assert accepted.raw["confidence_notes"] == ["a"]
    assert accepted.raw["lane_a_version"] == 3


# ── 4. the accepted frame round-trips ────────────────────────────────────────

def test_an_accepted_frame_survives_its_own_serialization():
    accepted = accept(fixtures.fold_frame())
    assert AcceptedFrame.from_dict(accepted.to_dict()) == accepted


# ── 5. the cross-lane contract test, waiting for Lane A ──────────────────────

@pytest.mark.skipif(not HAS_LANE_A, reason=LANE_A_SKIP)
def test_lane_a_real_frame_passes_through_the_intake_unchanged():
    """After Lane A merges: its real `InquiryFrame.model_dump()` goes into this intake unchanged.

    If the shapes differ, the fix is a normaliser in `frame.py` and nothing downstream moves — the
    intake adapter, not either engine, owns any representation adjustment.
    """
    from backend.services.prompt_mind import InquiryFrame      # type: ignore  # noqa: F401
    raise AssertionError(
        "Lane A has merged: replace this body with a real frame built by Lane A, passed through "
        "`accept()` unchanged, and assert the derived goal hierarchy is non-empty.")
