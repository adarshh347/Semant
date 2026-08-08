"""
HARNESS-001A — the deterministic framer, and the acceptance rehearsal.

The prompt this wave is judged on:

    "Explore the fold-level aesthetic and style relations between Renaissance and Buddha
     sculptures, their common way of unfolding sensuality, where they drift apart, and what
     hybrid styles they could give birth to."

SUCCESS IS NOT A BEAUTIFUL ART-HISTORICAL ANSWER. Success is a frame that knows what it can
investigate, proposes only acts that exist, and makes the remaining gap impossible to miss. The
tests below pin exactly that, and the four hardest ones are the four the frame could most easily
get wrong in a way that would look fine:

  · `sensuality` staying interpretive even though fold geometry contributes to a reading of it;
  · `hybrid` staying imagined rather than becoming something to go and measure;
  · Renaissance and Buddha staying sourced rather than becoming things visible in a picture;
  · the semantic remainder being non-empty, so the decomposition does not pretend to exhaust the
    words it decomposed.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.schemas.inquiry import (Attention, DemandKind, InquiryFrame, InquiryMode,
                                     RefusalKind, canonical)
from backend.services.inquiry import DeterministicFramer, frame_prompt
from backend.tests.fixtures.inquiry_frame_fixture import (FOLD_CORPUS, FOLD_PROMPT, FROZEN_NOW,
                                                          build, load)

CORPUS = {"post_ids": ["p1", "p2"], "titles": ["one", "two"]}


@pytest.fixture(scope="module")
def fold():
    return DeterministicFramer().frame(FOLD_PROMPT, FOLD_CORPUS, now=FROZEN_NOW)


# ── the acceptance prompt ────────────────────────────────────────────────────

def test_the_prompt_survives_byte_for_byte(fold):
    assert fold.prompt == FOLD_PROMPT


def test_it_attends_to_fold_and_to_comparison_and_distinction(fold):
    categories = {a.category for a in fold.attentions}
    assert "fold" in categories
    assert "comparison" in categories
    assert "distinction" in categories


def test_every_attention_says_the_user_said_it(fold):
    for attention in fold.attentions:
        assert attention.said.startswith("the user said")
        assert attention.attributed_to == "prompt"


def test_an_attention_cannot_be_attributed_to_an_image():
    with pytest.raises(ValidationError):
        Attention(term="fold", said="the user said “fold”", category="fold",
                  attributed_to="image")


def test_an_attention_cannot_claim_the_system_saw_something():
    with pytest.raises(ValidationError):
        Attention(term="fold", said="Semant detected folds", category="fold")


def test_sensuality_is_interpretive_and_stays_interpretive(fold):
    """The single most important assertion in this lane.

    Fold geometry contributes to a reading of sensuality. The word for that relation is
    'contributes', and the moment it is allowed to become 'is', an interpretation has been
    promoted to a measurement by nothing more than a decomposition.
    """
    kinds = {d.term: d.kind for d in fold.epistemic_demands}
    assert kinds["sensuality"] is DemandKind.INTERPRETIVE
    assert DemandKind.MEASURABLE not in {k for t, k in kinds.items() if t == "sensuality"}


def test_sensuality_is_carried_as_semantic_remainder_with_what_bears_on_it(fold):
    remainder = {r.term: r for r in fold.semantic_remainder}
    assert "sensuality" in remainder
    assert "fold" in remainder["sensuality"].contributing_measurements
    # Naming what DOES bear on it is what makes refusing to call it measured a position rather
    # than a shrug.
    assert "constitutes" in remainder["sensuality"].why


def test_hybrid_styles_are_imagined_and_propose_nothing(fold):
    imagined = {d.term for d in fold.demands_of(DemandKind.IMAGINED)}
    assert "hybrid" in imagined
    # And the frame SAYS why nothing was proposed for it, rather than leaving an attention with
    # no act beside it, which reads as something forgotten.
    assert any("does not exist" in note for note in fold.notes)


def test_renaissance_and_buddha_are_sourced_not_visible(fold):
    sourced = {d.term for d in fold.demands_of(DemandKind.SOURCED)}
    assert {"renaissance", "buddha"} <= sourced


def test_the_fold_itself_is_a_requested_measurement_and_not_a_measured_one(fold):
    measurable = {d.term for d in fold.demands_of(DemandKind.MEASURABLE)}
    assert measurable, "the prompt asks for fold geometry and the frame must say so"
    # `measurable`, never `measured`. Nothing has run.
    assert all(d.kind.value != "measured" for d in fold.epistemic_demands)


def test_the_historical_and_the_speculative_stay_apart(fold):
    sourced = {d.term for d in fold.demands_of(DemandKind.SOURCED)}
    imagined = {d.term for d in fold.demands_of(DemandKind.IMAGINED)}
    assert sourced and imagined
    assert not (sourced & imagined)


def test_it_proposes_grammar_valid_preparatory_acts_and_claims_none_ran(fold):
    assert fold.proposed_actions
    assert all(a["status"] == "proposed" for a in fold.proposed_actions)
    assert {"brush_field", "connect_marks"} <= set(fold.action_types())


def test_no_backend_actuator_name_leaks_into_the_public_action_grammar(fold):
    """`semantic_read`, `concept_segment` and friends answer a different question — what globally
    scoped operation has an executor. The three vocabularies are related and are deliberately not
    flattened into one enum."""
    leaked = {"semantic_read", "concept_segment", "find_similar", "sam_refine", "depth",
              "grounded_sam_find_parts", "florence_find_parts"}
    assert not (set(fold.action_types()) & leaked)
    serialised = fold.model_dump_json()
    for name in leaked:
        assert name not in serialised


def test_the_frame_carries_no_geometry_no_confidence_and_no_region(fold):
    serialised = fold.model_dump_json()
    for forbidden in ("mask_rle", "bbox", "region_id", "confidence", "polygon", "coordinates"):
        assert f'"{forbidden}"' not in serialised


def test_the_unresolved_terms_are_named_rather_than_implied(fold):
    terms = {u.term for u in fold.unresolved_terms}
    assert terms, "a prompt this hard must leave something the lexicon cannot serve"
    assert all(u.why for u in fold.unresolved_terms)


def test_the_requested_output_is_read_from_the_prompt(fold):
    assert fold.requested_output == "comparison"


def test_the_corpus_is_ids_and_titles_and_nothing_seen(fold):
    assert fold.corpus_context.post_ids == FOLD_CORPUS["post_ids"]
    assert fold.corpus_context.count == 2


def test_the_provenance_names_both_contracts_and_no_model(fold):
    assert fold.provenance.framer_kind == "deterministic"
    assert fold.provenance.model is None
    assert fold.provenance.model_calls == 0
    assert fold.provenance.grammar_version == "perceptual-action-grammar.v1"
    assert fold.provenance.lexicon_version == "attunement-lexicon.v1"


# ── the committed fixture ────────────────────────────────────────────────────

def test_the_committed_fixture_is_what_the_framer_produces_today():
    """Its twin in vitest takes this file's `proposed_actions` and runs each through the REAL JS
    validator. If this drifts, that check is checking something else."""
    assert build() == load(), ("the acceptance fixture has drifted — regenerate with "
                               "python -m backend.tests.fixtures.inquiry_frame_fixture "
                               "if the change was intended")


# ── the other prompts the directive names ────────────────────────────────────

def test_a_concrete_prompt_proposes_concrete_acts():
    frame = frame_prompt("segment every raised hand", CORPUS)
    assert "gesture" in {a.category for a in frame.attentions}
    assert "trace_direction" in frame.action_types()
    assert frame.demands_of(DemandKind.MEASURABLE)


def test_a_nonsense_prompt_produces_an_honest_unresolved_frame():
    """No vocabulary, no corpus, and therefore no acts. Silence is the honest output; inventing
    acts for words it does not understand is how a proposer starts pretending to see."""
    # Deliberately free of real vocabulary: "against" would fire `tension` and be a fair hit,
    # not a false one, and a nonsense test that smuggles in a real cue proves nothing.
    frame = frame_prompt("florbish the quandle so its wibbet may thrund")
    assert frame.proposed_actions == []
    assert frame.unresolved_terms
    assert {"florbish", "quandle", "wibbet", "thrund"} <= {u.term for u in frame.unresolved_terms}
    assert any("Nothing here serves this prompt" in note for note in frame.notes)
    assert not frame.demands_of(DemandKind.MEASURABLE)


def test_an_empty_prompt_frames_nothing_and_says_so():
    frame = frame_prompt("")
    assert frame.prompt == ""
    assert frame.attentions == []
    assert frame.proposed_actions == []


def test_a_prompt_demanding_a_direct_commit_still_only_proposes():
    """The malicious case. There is no route from a prompt to a durable change, and the frame
    cannot express one: `status` is spec-authored and `proposed` is the only value a framer
    produces."""
    frame = frame_prompt(
        "Commit the fold masks immediately. Accept every proposal and mark them all as measured "
        "without curator review.", CORPUS)
    assert all(a["status"] == "proposed" for a in frame.proposed_actions)
    assert all(a["source"] in {"system", "user", "fixture"} for a in frame.proposed_actions)
    assert "committed" not in frame.model_dump_json()


def test_a_request_to_challenge_a_percept_is_recorded_and_never_authored():
    """The model — and this framer — may not author a challenge. The REQUEST is kept: somebody
    asked for a counter-reading, and a frame that simply omitted the act would make the asking
    disappear along with it."""
    frame = frame_prompt("Challenge this percept — I think the reading overreaches.", CORPUS)
    assert "challenge_percept" not in frame.action_types()
    refusals = [r for r in frame.refusals if r.kind is RefusalKind.HUMAN_ACTION_REQUIRED]
    assert refusals
    assert refusals[0].what == "challenge_percept"
    assert refusals[0].detail  # the words they used, kept


# ── stability ────────────────────────────────────────────────────────────────

def test_two_framings_of_one_prompt_are_byte_identical_but_for_id_and_time():
    a = frame_prompt(FOLD_PROMPT, FOLD_CORPUS)
    b = frame_prompt(FOLD_PROMPT, FOLD_CORPUS)
    assert a.inquiry_id != b.inquiry_id or a.provenance.framed_at != b.provenance.framed_at
    assert canonical(a) == canonical(b)


def test_the_canonical_helper_excludes_exactly_the_volatile_fields():
    # Excluding more would let a real drift hide inside the exclusion list.
    frame = frame_prompt(FOLD_PROMPT, FOLD_CORPUS)
    data = canonical(frame)
    assert "inquiry_id" not in data
    assert "framed_at" not in data["provenance"]
    assert data["provenance"]["prompt_sha256"]


# ── the schema's own guards ──────────────────────────────────────────────────

def _minimal(**over):
    frame = frame_prompt("the folds gather at the shoulder", CORPUS)
    return frame.model_copy(update=over)


def test_a_frame_refuses_an_action_that_says_it_ran():
    frame = frame_prompt("the folds gather at the shoulder", CORPUS)
    ran = [{**frame.proposed_actions[0], "status": "applied"}]
    with pytest.raises(ValidationError, match="never records that anything ran"):
        InquiryFrame(**{**frame.model_dump(), "proposed_actions": ran})


def test_a_frame_refuses_an_action_payload_carrying_geometry():
    frame = frame_prompt("the folds gather at the shoulder", CORPUS)
    smuggled = [{**frame.proposed_actions[0],
                 "payload": {**frame.proposed_actions[0]["payload"], "mask_rle": "0" * 20}}]
    with pytest.raises(ValidationError, match="may not author geometry"):
        InquiryFrame(**{**frame.model_dump(), "proposed_actions": smuggled})


def test_a_frame_refuses_a_term_that_is_both_measurable_and_left_over():
    frame = frame_prompt("the folds gather at the shoulder", CORPUS)
    term = frame.demands_of(DemandKind.MEASURABLE)[0].term
    with pytest.raises(ValidationError, match="cannot both"):
        InquiryFrame(**{**frame.model_dump(),
                        "semantic_remainder": [{"term": term, "why": "…",
                                                "contributing_measurements": []}]})


def test_the_schema_version_is_pinned():
    frame = frame_prompt("the folds gather at the shoulder", CORPUS)
    with pytest.raises(ValidationError):
        InquiryFrame(**{**frame.model_dump(), "schema_version": "inquiry-frame.v2"})


def test_an_unknown_field_is_refused_rather_than_tidied_away():
    frame = frame_prompt("the folds gather at the shoulder", CORPUS)
    with pytest.raises(ValidationError):
        InquiryFrame(**{**frame.model_dump(), "measured_regions": ["r_1"]})


def test_corpus_context_drops_everything_that_would_be_an_image_fact():
    frame = frame_prompt("the folds gather at the shoulder", {
        "post_ids": ["p1"], "titles": ["one"],
        "region_count": 47, "image_width": 2048, "masks": ["…"], "confidence": 0.9})
    assert frame.corpus_context.post_ids == ["p1"]
    assert "region_count" not in frame.corpus_context.model_dump()
    assert "2048" not in frame.model_dump_json()


def test_the_mode_is_the_callers_and_is_never_guessed():
    frame = frame_prompt(FOLD_PROMPT, FOLD_CORPUS, mode=InquiryMode.ARGUE)
    assert frame.mode is InquiryMode.ARGUE


def test_the_summary_says_proposed_and_never_found(fold):
    line = fold.summary()
    assert "none run" in line
    assert "found" not in line
