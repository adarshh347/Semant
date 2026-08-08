"""
HARNESS-001B §3 — `InquiryFrame` intake, and the A→B seam.

Lane A and Lane B are being built at the same time. B accepts by SHAPE and does not import A. What
this file pins is that the intake is permissive where it must be (Lane A's representation choices)
and strict where it must be (the contract, and the prompt).

## The cross-lane test

`test_lane_a_real_frame_passes_through_the_intake_unchanged` was SKIPPED while the two lanes were
built in parallel, pointing at a GUESSED module name (`backend.services.prompt_mind`). Lane A has
landed and built `backend.services.inquiry`, with its schema in `backend.schemas.inquiry`.

The reconciliation is to correct the guess, not to add a compatibility alias: an alias would leave
two names for one thing and no reason to prefer either, and the next reader would have to find out
by grepping which one was real. The test now calls the real framer and pushes its real
`model_dump()` through this intake.
"""
from __future__ import annotations

import pytest

from backend.services.inquiry import frame_prompt
from backend.services.inquiry_engine import fixtures
from backend.services.inquiry_engine.frame import (REQUIRED_KEYS, SCHEMA_VERSION, AcceptedFrame,
                                                   FrameRefused, accept)

#: The wave's acceptance rehearsal, byte for byte. Lane A, Lane B and Lane C all use this sentence.
FOLD_PROMPT = (
    "Explore the fold-level aesthetic and style relations between Renaissance and Buddha "
    "sculptures, their common way of unfolding sensuality, where they drift apart, and what "
    "hybrid styles they could give birth to."
)
CORPUS = {"post_ids": ["fixture_renaissance_01", "fixture_buddha_01"],
          "titles": ["Piet\u00e0, marble", "Seated Buddha, Gandhara schist"]}


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


# ── 5. the cross-lane contract test, now that Lane A has landed ──────────────

def test_lane_a_real_frame_passes_through_the_intake_unchanged():
    """Lane A's real `InquiryFrame.model_dump()`, into this intake, unaltered.

    Not a fixture shaped like one: `frame_prompt` runs the deterministic framer over the shared
    attunement lexicon and the Perceptual Action Grammar, and what comes out is what Lane A hands
    anybody.
    """
    frame = frame_prompt(FOLD_PROMPT, CORPUS)
    accepted = accept(frame.model_dump())

    assert accepted.inquiry_id == frame.inquiry_id
    assert accepted.prompt == frame.prompt == FOLD_PROMPT
    assert accepted.mode == frame.mode.value
    assert accepted.raw == frame.model_dump()          # carried whole; nothing dropped


def test_the_real_frames_structured_entries_are_read_rather_than_refused():
    """Lane A emits mappings, not strings, for every list field. The intake reads them and SAYS it
    reshaped them, which is what makes the seam inspectable rather than assumed."""
    accepted = accept(frame_prompt(FOLD_PROMPT, CORPUS).model_dump())
    assert "folding" in accepted.attentions
    assert "sensuality" in accepted.epistemic_demands
    assert "sensuality" in accepted.semantic_remainder
    assert accepted.unresolved_terms
    assert any("attentions" in a for a in accepted.adjustments)


def test_the_acts_words_survive_the_seam_and_not_only_the_acts():
    """The one reconciliation this seam actually needed.

    A Perceptual Action Grammar act keeps its role and its label in `payload`, because the grammar
    declares its `enums` per payload key. Reading only the top level let every `brush_field`
    through with an empty role and an empty phrase — and `derive_goals` names a goal from
    `phrase or role`, so the words were lost exactly where they were about to be used.
    """
    accepted = accept(frame_prompt(FOLD_PROMPT, CORPUS).model_dump())
    brush = [a for a in accepted.proposed_actions if a.type == "brush_field"]
    assert brush, "the fold prompt proposes a brush_field"
    assert brush[0].role == "fold"
    assert brush[0].phrase
    connects = [a for a in accepted.proposed_actions if a.type == "connect_marks"]
    assert {a.role for a in connects} == {"similarity", "contrast"}


def test_a_real_frame_derives_a_non_empty_goal_hierarchy():
    """The point of the seam: Lane A's frame produces Lane B's goals, with no fixture between."""
    from backend.services.inquiry_engine.engine import run_inquiry

    run = run_inquiry(frame_prompt(FOLD_PROMPT, CORPUS).model_dump(), now="2026-08-08T12:00:00Z")
    assert run.frame.prompt == FOLD_PROMPT         # unrewritten, all the way down
    assert [g for g in run.goals if g.kind == "inquiry"]
    assert [g for g in run.goals if g.kind == "evidence"]
    assert run.stop_reason


def test_the_imagined_half_of_the_real_prompt_is_carried_and_never_satisfied():
    """`hybrid` is Lane A's `imagined` demand. It must arrive, be named, and stay unsatisfiable —
    dropping it is the quietest possible way to lose the hardest half of the prompt."""
    from backend.services.inquiry_engine.engine import run_inquiry

    frame = frame_prompt(FOLD_PROMPT, CORPUS)
    assert any(d.kind.value == "imagined" for d in frame.epistemic_demands)
    run = run_inquiry(frame.model_dump(), now="2026-08-08T12:00:00Z")
    assert "hybrid" in run.frame.epistemic_demands
    assert all(g.status != "satisfied" for g in run.goals)
