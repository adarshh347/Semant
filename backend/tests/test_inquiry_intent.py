"""
INTELLIGENCE-002A — the inquiry reader: does the map still say what the person said?

Three things are being tested, and only the third is about classification quality.

  1. THE MAP QUOTES. Every span slices back to the exact characters it claims. This is the
     property the whole section rests on, so it is tested on the fixtures, on a tampered map, and
     on the model seam separately.
  2. THE MAP HAS NOWHERE TO PUT AN OBSERVATION. Tested structurally over the contracts, not by
     hoping nobody adds a field.
  3. THE READING IS HONEST ABOUT BEING PARTIAL. A question it cannot place becomes an ambiguity
     rather than a guess, and the direction it falls in is fixed.
"""
from __future__ import annotations

import dataclasses
import inspect
import re

import pytest

from backend.services.inquiry_intelligence import intent
from backend.services.inquiry_intelligence.intent import (Ambiguity, AmbiguityKind, ElementKind,
                                                          InquiryMap, InquiryReadError,
                                                          SourceSpan, SpanProposal, Stance,
                                                          read_inquiry)
from backend.tests.fixtures.inquiry_observation_fixtures import (ARCHITECTURE_PROMPT, PLANT_PROMPT,
                                                                 SCULPTURE_PROMPT)

ALL_PROMPTS = (SCULPTURE_PROMPT, ARCHITECTURE_PROMPT, PLANT_PROMPT)


# ── the map quotes ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("prompt", ALL_PROMPTS)
def test_the_prompt_is_carried_byte_identically(prompt):
    assert read_inquiry(prompt).prompt == prompt


@pytest.mark.parametrize("prompt", ALL_PROMPTS)
def test_every_span_slices_back_to_the_characters_it_claims(prompt):
    """The property `__post_init__` enforces, checked from the outside as well.

    A constructor guard that is only ever exercised by the constructor is a guard nobody has
    watched fail. This walks every element of a real map and does the slice itself.
    """
    m = read_inquiry(prompt)
    for span in m._all_spans():
        assert prompt[span.start:span.end] == span.text


def test_a_span_that_does_not_match_the_prompt_is_refused_at_construction():
    prompt = "The base is plain."
    with pytest.raises(InquiryReadError) as exc:
        InquiryMap(prompt=prompt, sentences=(SourceSpan(0, 8, "The vase"),), hypotheses=(),
                   vocabulary=(), comparisons=(), observable_questions=(),
                   interpretive_questions=(), instructions=(), ambiguities=())
    assert "does not restate" in str(exc.value)


def test_a_span_running_past_the_end_of_the_prompt_is_refused():
    with pytest.raises(InquiryReadError):
        InquiryMap(prompt="short", sentences=(SourceSpan(0, 99, "short"),), hypotheses=(),
                   vocabulary=(), comparisons=(), observable_questions=(),
                   interpretive_questions=(), instructions=(), ambiguities=())


def test_a_prompt_is_text_and_nothing_else():
    with pytest.raises(InquiryReadError):
        read_inquiry({"prompt": "not a string"})


def test_leading_whitespace_is_not_trimmed_because_every_offset_depends_on_it():
    prompt = "   I think the base is later.\n\n  Is it?"
    m = read_inquiry(prompt)
    assert m.prompt == prompt
    assert m.hypotheses[0].claim == "I think the base is later."
    assert prompt[m.hypotheses[0].span.start:m.hypotheses[0].span.end] == "I think the base is later."


# ── the map has nowhere to put an observation ────────────────────────────────

def test_no_contract_in_the_reader_has_a_field_that_could_hold_an_observation():
    """Guard, structural. Rule 7: a user hypothesis is not an image observation.

    Checked over the annotations rather than by convention, so adding `observations: tuple` to
    `InquiryMap` fails here rather than being noticed in review or not.
    """
    banned = re.compile(r"observation|percept|artifact|measurement|mask|extent", re.I)
    for name, obj in vars(intent).items():
        if not dataclasses.is_dataclass(obj) or not isinstance(obj, type):
            continue
        for f in dataclasses.fields(obj):
            assert not banned.search(f.name), f"{name}.{f.name} could carry a picture-fact"
            assert not banned.search(str(f.type)), f"{name}.{f.name} is typed on a picture-fact"


def test_every_reader_contract_is_frozen():
    """A mutable map is a map something can add an observation to after it was validated."""
    for name, obj in vars(intent).items():
        if dataclasses.is_dataclass(obj) and isinstance(obj, type):
            assert obj.__dataclass_params__.frozen, f"{name} is not frozen"


def test_the_map_has_no_open_metadata_dict_to_grow_one_in():
    assert not any(f.name in {"extra", "metadata", "meta", "context", "notes"}
                   for f in dataclasses.fields(InquiryMap))


# ── hypotheses ───────────────────────────────────────────────────────────────

def test_a_hypothesis_keeps_the_persons_words_and_their_degree_of_commitment():
    m = read_inquiry(SCULPTURE_PROMPT)
    h = m.hypotheses[0]
    assert h.claim == "I think the drapery is what carries the weight of this figure."
    assert h.stance is Stance.HEDGED
    assert "i think" in h.markers


def test_a_flat_assertion_is_not_softened_into_a_hedge():
    m = read_inquiry("The base is a later addition.")
    assert m.hypotheses[0].stance is Stance.ASSERTED
    assert m.hypotheses[0].markers == ()


def test_something_the_person_was_told_is_marked_as_told_and_not_as_theirs():
    """`reported` is not a nicety. A claim from a museum label and a claim from the person are
    different things to put to a picture, and flattening them loses which is which."""
    m = read_inquiry("According to the label the base is 17th century.")
    assert m.hypotheses[0].stance is Stance.REPORTED


def test_a_hedged_claim_is_never_flattened_into_an_assertion():
    m = read_inquiry("The drapery is probably later.")
    assert m.hypotheses[0].stance is Stance.HEDGED


# ── questions ────────────────────────────────────────────────────────────────

def test_a_counting_question_is_observable_and_says_which_marker_placed_it():
    m = read_inquiry(SCULPTURE_PROMPT)
    q = m.observable_questions[0]
    assert q.question == "How many separate folds are visible on the left side?"
    assert "how many" in q.markers


def test_a_why_question_is_interpretive():
    m = read_inquiry(SCULPTURE_PROMPT)
    assert any(q.question.startswith("Why does") for q in m.interpretive_questions)


def test_a_question_with_no_marker_of_either_kind_falls_interpretive_and_says_so():
    """THE ASYMMETRY. Filing it observable would assert that looking settles it — a claim made by
    a module that has never seen a picture. Filing it interpretive merely under-claims."""
    m = read_inquiry("Is it symmetrical?")
    assert len(m.interpretive_questions) == 1
    assert not m.observable_questions
    assert any(a.kind is AmbiguityKind.EPISTEMIC_KIND_UNCLEAR for a in m.ambiguities)


def test_a_question_carrying_both_families_is_flagged_rather_than_resolved():
    m = read_inquiry("How many of the openings are there, and why do they matter?")
    assert not m.observable_questions
    unclear = [a for a in m.ambiguities if a.kind is AmbiguityKind.EPISTEMIC_KIND_UNCLEAR]
    assert unclear and "both kinds" in unclear[0].note


def test_an_instruction_carrying_a_wh_clause_is_read_as_the_question_it_is():
    m = read_inquiry("Tell me how many bays there are.")
    assert [q.question for q in m.observable_questions] == ["Tell me how many bays there are."]


def test_an_instruction_is_not_mistaken_for_a_claim_the_person_made():
    m = read_inquiry("Look at these two images.")
    assert not m.hypotheses
    assert len(m.instructions) == 1


# ── comparisons ──────────────────────────────────────────────────────────────

def test_a_two_sided_comparison_keeps_both_sides_verbatim():
    m = read_inquiry("Compare the base and the crown.")
    c = m.comparisons[0]
    assert c.sides == ("the base", "the crown")
    assert c.complete


def test_a_between_and_comparison_is_read():
    m = read_inquiry("What is the difference between the upper band and the lower band?")
    assert m.comparisons[0].sides == ("the upper band", "the lower band")


def test_a_comparative_with_both_sides_is_not_reported_as_incomplete():
    """`heavier than the other one` names what it is being compared with. Reporting it incomplete
    told the person their clearest sentence was the vague one."""
    m = read_inquiry("Why does the lower half feel heavier than the upper?")
    assert m.comparisons[0].complete
    assert not any(a.kind is AmbiguityKind.INCOMPLETE_COMPARISON for a in m.ambiguities)


def test_a_comparison_missing_its_second_side_is_flagged():
    m = read_inquiry("The left one is heavier than.")
    assert not m.comparisons[0].complete
    assert any(a.kind is AmbiguityKind.INCOMPLETE_COMPARISON for a in m.ambiguities)


# ── ambiguity ────────────────────────────────────────────────────────────────

def test_a_pronoun_with_nothing_behind_it_is_an_unresolved_reference():
    m = read_inquiry("Is it symmetrical?")
    assert any(a.kind is AmbiguityKind.UNRESOLVED_REFERENCE and a.span.text == "it"
               for a in m.ambiguities)


def test_a_demonstrative_with_its_noun_right_there_is_a_determiner_and_not_flagged():
    m = read_inquiry("Look at these two images.")
    assert not any(a.kind is AmbiguityKind.UNRESOLVED_REFERENCE for a in m.ambiguities)


def test_a_deictic_image_reference_is_flagged_because_the_reader_has_no_images():
    m = read_inquiry("Is the second one later?")
    assert any(a.kind is AmbiguityKind.UNBOUND_IMAGE_REFERENCE for a in m.ambiguities)


def test_how_many_is_a_count_question_and_not_an_unscoped_quantifier():
    m = read_inquiry("How many folds are there?")
    assert not any(a.kind is AmbiguityKind.UNSCOPED_QUANTIFIER for a in m.ambiguities)


def test_a_vague_quantifier_in_a_claim_is_flagged():
    m = read_inquiry("Most of the surface is later.")
    assert any(a.kind is AmbiguityKind.UNSCOPED_QUANTIFIER for a in m.ambiguities)


@pytest.mark.parametrize("prompt", ALL_PROMPTS)
def test_ambiguity_ids_are_unique_and_ordered_by_position(prompt):
    m = read_inquiry(prompt)
    ids = [a.ambiguity_id for a in m.ambiguities]
    assert len(ids) == len(set(ids))
    assert [a.span.start for a in m.ambiguities] == sorted(a.span.start for a in m.ambiguities)


# ── vocabulary ───────────────────────────────────────────────────────────────

def test_the_vocabulary_is_open_and_keeps_a_word_no_table_could_have_held():
    """Rule 6. Nothing is looked up; content words are what is left after the function words go."""
    m = read_inquiry("I think the sgraffito register is doing the work.")
    assert "sgraffito" in {t.term for t in m.vocabulary}


def test_a_term_carries_which_kind_of_element_the_person_used_it_in():
    """The audit's severity split rests entirely on this field."""
    m = read_inquiry(SCULPTURE_PROMPT)
    by_term = {t.term: t.origins for t in m.vocabulary}
    assert ElementKind.HYPOTHESIS in by_term["drapery"]
    assert ElementKind.OBSERVABLE_QUESTION in by_term["folds"]
    assert ElementKind.HYPOTHESIS not in by_term["folds"]


def test_a_quoted_phrase_is_kept_whole_rather_than_shredded_into_tokens():
    m = read_inquiry('I think the "load bearing bit" is later.')
    assert "load bearing bit" in {t.term for t in m.vocabulary}


def test_function_words_and_task_verbs_are_not_the_persons_vocabulary():
    m = read_inquiry("Compare the base and the crown.")
    terms = {t.term for t in m.vocabulary}
    assert "compare" not in terms and "the" not in terms and "and" not in terms


def test_every_vocabulary_span_slices_back_to_its_surface():
    m = read_inquiry(SCULPTURE_PROMPT)
    for term in m.vocabulary:
        for span in term.spans:
            assert SCULPTURE_PROMPT[span.start:span.end] == span.text


# ── the model seam ───────────────────────────────────────────────────────────

class _Reader:
    def __init__(self, proposals, identity="fake-reader"):
        self._proposals = proposals
        self._identity = identity
        self.seen = []

    @property
    def identity(self):
        return self._identity

    def propose(self, prompt):
        self.seen.append(prompt)
        return self._proposals


def test_a_proposal_has_no_text_field_so_paraphrase_is_unsayable():
    """THE GUARD. A model that could hand back the words would hand back its own; this one can
    only point, and `read_inquiry` does the slicing."""
    assert {f.name for f in dataclasses.fields(SpanProposal)} == {"start", "end", "kind", "note"}


def test_the_reader_slices_the_prompt_itself_so_a_proposal_cannot_smuggle_words_in():
    prompt = "The base is plain."
    m = read_inquiry(prompt, _Reader([SpanProposal(0, 8, ElementKind.HYPOTHESIS)]))
    added = [h for h in m.hypotheses if h.span.start == 0 and h.span.end == 8]
    assert added and added[0].claim == "The base"


def test_proposals_are_additive_and_never_remove_what_the_deterministic_pass_found():
    prompt = "I think the base is later. How many bays are there?"
    without = read_inquiry(prompt)
    with_model = read_inquiry(prompt, _Reader([SpanProposal(2, 7, ElementKind.HYPOTHESIS)]))
    assert len(with_model.hypotheses) == len(without.hypotheses) + 1
    assert {h.claim for h in without.hypotheses} <= {h.claim for h in with_model.hypotheses}
    assert len(with_model.observable_questions) == len(without.observable_questions)


def test_a_proposal_outside_the_prompt_is_dropped_and_named():
    """A reader that silently discarded a fifth of what the model said would be indistinguishable
    from one the model agreed with."""
    m = read_inquiry("Short.", _Reader([SpanProposal(90, 99, ElementKind.HYPOTHESIS)]))
    assert m.dropped_proposals and "outside the prompt" in m.dropped_proposals[0]
    assert not m.hypotheses or all(h.span.end <= 6 for h in m.hypotheses)


def test_a_reversed_or_empty_proposal_is_dropped():
    m = read_inquiry("The base is plain.", _Reader([SpanProposal(9, 4, ElementKind.HYPOTHESIS),
                                                    SpanProposal(3, 4, ElementKind.HYPOTHESIS)]))
    assert len(m.dropped_proposals) == 2


def test_a_duplicate_proposal_does_not_double_an_element():
    prompt = "I think the base is later."
    m = read_inquiry(prompt, _Reader([SpanProposal(0, len(prompt), ElementKind.HYPOTHESIS)]))
    assert len(m.hypotheses) == 1


def test_a_reader_that_raises_is_recorded_and_the_deterministic_reading_survives():
    class _Angry:
        identity = "angry"

        def propose(self, prompt):
            raise RuntimeError("no")

    m = read_inquiry("I think the base is later.", _Angry())
    assert m.hypotheses and m.dropped_proposals
    assert "RuntimeError" in m.dropped_proposals[0]


def test_the_map_records_whose_reading_it_is_and_none_is_a_different_claim_from_unknown():
    assert read_inquiry("The base is plain.").model_reader is None
    assert read_inquiry("The base is plain.", _Reader([])).model_reader == "fake-reader"


def test_a_proposal_of_a_kind_that_is_not_a_kind_is_dropped_rather_than_coerced():
    m = read_inquiry("The base is plain.", _Reader(["not a proposal"]))
    assert m.dropped_proposals and "not a SpanProposal" in m.dropped_proposals[0]


def test_an_ambiguity_proposal_lands_as_an_ambiguity_carrying_the_models_note():
    m = read_inquiry("The base is plain.", _Reader([SpanProposal(4, 8, ElementKind.AMBIGUITY,
                                                                 "which base")]))
    assert any(a.kind is AmbiguityKind.EPISTEMIC_KIND_UNCLEAR and "which base" in a.note
               for a in m.ambiguities)


# ── segmentation ─────────────────────────────────────────────────────────────

def test_newlines_separate_sentences_that_carry_no_terminal_punctuation():
    m = read_inquiry("I think the base is later\nHow many bays are there")
    assert len(m.sentences) == 2
    assert len(m.hypotheses) == 1 and len(m.observable_questions) == 1


def test_reading_is_deterministic():
    assert read_inquiry(SCULPTURE_PROMPT) == read_inquiry(SCULPTURE_PROMPT)


def test_an_empty_prompt_produces_an_empty_map_rather_than_raising():
    m = read_inquiry("")
    assert m.prompt == "" and not m.sentences and not m.hypotheses
