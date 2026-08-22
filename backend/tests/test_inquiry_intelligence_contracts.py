"""
INTELLIGENCE-001A — the invariants, stated as things that cannot be constructed.

Most of this file asserts a `ValidationError`. That is the point: the lane's claim is not that the
pipeline behaves well, it is that a whole class of sentence has no representation. "The person's
guess came back as an image finding" is not a bug to be caught downstream here — it is a
`UserHypothesis` with an `image_id`, and there is no such object.

The positive tests are the other half of the same claim: the ORDINARY cases must stay easy. An
interpretive observation with no ground, a question nobody can name an instrument for, a run that
finished cleanly and found nothing worth saying — each has to be expressible without a workaround,
or the schema will be routed around the first time it is inconvenient.
"""
from __future__ import annotations

import json
import re
from enum import Enum
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.schemas.inquiry_intelligence import (READABLE_SCHEMA_VERSIONS, SCHEMA_VERSION,
                                                  Ambiguity, AnswerForm, CapabilityClass,
                                                  EpistemicStatus, InquiryMap, InquiryQuestion,
                                                  MaterialOrigin, MeasurementProvenance,
                                                  ObservationState, PromptSpan, Provenance,
                                                  ProvenanceKind, RequestedComparison,
                                                  AlignmentKind, CandidateRelation, ContrastPlan,
                                                  ContrastScope, HypothesisAlignment, RelationKind,
                                                  UnresolvedReference, UserHypothesis,
                                                  VisualObservation, check_resolves,
                                                  index_observations, mint, resolve_observations,
                                                  CritiqueVerdict, ImageDiversity,
                                                  InferenceSupport, IntelligenceCounts,
                                                  IntelligenceOutcome, IntelligenceOutcomeRecord,
                                                  ParrotAssessment, RelationCritique, Relevance,
                                                  SourceCompleteness, WorkflowCompletion)
from backend.tests.fixtures import inquiry_intelligence_fixtures as F

ROOT = Path(__file__).resolve().parents[2]


# ── builders: the SHORTEST legal form of each object ─────────────────────────

def a_provenance(**kw) -> Provenance:
    return Provenance(**{"producer": "inquiry_intelligence/test",
                         "kind": ProvenanceKind.FIXTURE, **kw})


def a_hypothesis(text: str = "the two differ in how the surface is worked", **kw) -> UserHypothesis:
    return UserHypothesis(**{"hypothesis_id": mint("user_hypothesis", ["i1", text]),
                             "text": text, **kw})


def an_observation(**kw) -> VisualObservation:
    body = {"observation_id": mint("visual_observation", ["i1", "a"]),
            "image_id": "post_a", "feature": "surface treatment",
            "visible_description": "the worked area meets the unworked one along a hard line",
            "provenance": a_provenance()}
    body.update(kw)
    return VisualObservation(**body)


def a_measurement(**kw) -> MeasurementProvenance:
    return MeasurementProvenance(**{"capability_class": CapabilityClass.EXTENT,
                                    "instrument": "an-actual-segmenter",
                                    "evidence_refs": ["ev_1"], **kw})


def a_map(**kw) -> InquiryMap:
    body = {"inquiry_map_id": mint("inquiry_map", ["i1"]), "inquiry_id": "i1",
            "principal_question": "how do the two differ?", "provenance": a_provenance()}
    body.update(kw)
    return InquiryMap(**body)


# ── 1. prompt material cannot masquerade as an image observation ─────────────

@pytest.mark.parametrize("field, value", [
    ("image_id", "post_a"),
    ("image_ref", "post_a"),
    ("post_id", "post_a"),
    ("region_ref", "reg_1"),
    ("ground_ref", "gnd_1"),
    ("evidence_refs", ["ev_1"]),
    ("epistemic_status", "measured"),
    ("measurement", {"capability_class": "extent", "instrument": "x", "evidence_refs": ["e"]}),
    ("visible_description", "the surface is worked"),
])
def test_a_user_hypothesis_has_nowhere_to_put_an_image_claim(field, value):
    """The invariant in its strongest available form.

    Not "a validator rejects this" — the field DOES NOT EXIST, and `extra="forbid"` means it cannot
    be added by a parser filling a dict from a model response. Every key here is one somebody would
    plausibly reach for when trying to say the pictures agreed with the person.
    """
    with pytest.raises(ValidationError) as caught:
        a_hypothesis(**{field: value})
    assert field in str(caught.value)


def test_a_user_hypothesis_may_not_declare_any_other_origin():
    """`origin` is a Literal, not a defaulted enum. A default is something a later dict update
    overwrites; a literal is something the type refuses."""
    for other in (MaterialOrigin.IMAGE_OBSERVATION, MaterialOrigin.SEMANT_INFERENCE,
                  MaterialOrigin.EXTERNAL_SOURCE):
        with pytest.raises(ValidationError):
            a_hypothesis(origin=other)
    assert a_hypothesis().origin is MaterialOrigin.PROMPT


def test_the_map_as_a_whole_is_prompt_material():
    with pytest.raises(ValidationError):
        a_map(origin=MaterialOrigin.IMAGE_OBSERVATION)
    assert a_map().origin is MaterialOrigin.PROMPT


def test_a_hypothesis_keeps_the_persons_own_words_unmapped():
    """Open vocabulary: the person's terms are carried verbatim, not normalised into a taxonomy."""
    hypothesis = a_hypothesis(user_terms=["blunt", "wet-looking", "a bit brutal"])
    assert hypothesis.user_terms == ["blunt", "wet-looking", "a bit brutal"]


# ── 2. an observation requires a picture ─────────────────────────────────────

@pytest.mark.parametrize("bad", [{}, {"image_id": ""}, {"image_id": "   "}, {"feature": " "}])
def test_an_observation_without_a_resolvable_image_cannot_be_built(bad):
    """Missing, empty, and — the one `min_length=1` lets through — whitespace. A blank image id
    resolves to nothing at exactly the moment somebody tries to go and look at the picture."""
    body = {"observation_id": mint("visual_observation", ["i1", "a"]), "image_id": "post_a",
            "feature": "surface treatment", "visible_description": "d",
            "provenance": a_provenance()}
    body.update(bad)
    if not bad:
        body.pop("image_id")
    with pytest.raises(ValidationError):
        VisualObservation(**body)


def test_a_resolvable_reference_is_stored_stripped():
    """The stripped form is what gets stored, so two references that differ only in whitespace do
    not become two images."""
    assert an_observation(image_id="  post_a  ").image_id == "post_a"


def test_an_observation_carries_the_image_origin_and_cannot_claim_the_prompts():
    assert an_observation().origin is MaterialOrigin.IMAGE_OBSERVATION
    with pytest.raises(ValidationError):
        an_observation(origin=MaterialOrigin.PROMPT)


def test_the_three_layers_are_three_fields():
    """A description, an effect and an interpretation are stored apart, so a later pass that
    promotes one into another has to do it visibly."""
    observation = an_observation(
        visible_description="the folds meet the base in a continuous curve",
        appearance_effect="reads as though the material is still moving",
        interpretive_possibility="may be aiming at animation rather than repose")
    assert observation.visible_description
    assert observation.appearance_effect != observation.visible_description
    assert observation.interpretive_possibility != observation.appearance_effect


def test_an_observed_observation_must_say_what_is_visible():
    """The checkable layer is the one that may not be empty. An observation that is only an effect
    and a possibility is an interpretation that has been given an image id."""
    with pytest.raises(ValidationError) as caught:
        an_observation(visible_description="   ",
                       interpretive_possibility="might be about grief")
    assert "visible_description" in str(caught.value)


# ── 3. looking is not measuring ──────────────────────────────────────────────

def test_a_vlm_observation_is_interpretive_by_default():
    assert an_observation().epistemic_status is EpistemicStatus.INTERPRETIVE
    assert an_observation().is_measured() is False


def test_measured_without_measurement_provenance_is_refused():
    with pytest.raises(ValidationError) as caught:
        an_observation(epistemic_status=EpistemicStatus.MEASURED)
    assert "measurement provenance" in str(caught.value)
    assert "agreement" in str(caught.value)


def test_measurement_provenance_without_the_measured_status_is_also_refused():
    """The quieter direction. Evidence attached to something still calling itself interpretive is
    evidence a reader filtering on status will never find."""
    with pytest.raises(ValidationError):
        an_observation(measurement=a_measurement())


def test_measured_becomes_expressible_the_moment_an_instrument_has_run():
    observation = an_observation(epistemic_status=EpistemicStatus.MEASURED,
                                 measurement=a_measurement())
    assert observation.is_measured()
    assert observation.measurement.evidence_refs == ["ev_1"]


def test_measurement_provenance_needs_evidence_to_point_at():
    with pytest.raises(ValidationError):
        MeasurementProvenance(capability_class=CapabilityClass.EXTENT, instrument="x",
                              evidence_refs=[])
    with pytest.raises(ValidationError):
        a_measurement(evidence_refs=["  "])


def test_nothing_becomes_measured_through_two_models_agreeing():
    """Two observations of the same feature from two providers. Both stay interpretive, and the
    schema offers no operation that combines them into anything else."""
    first = an_observation(observation_id=mint("visual_observation", ["i1", "one"]),
                           provenance=a_provenance(kind=ProvenanceKind.LIVE,
                                                   provider="p-one", model="m-one"))
    second = an_observation(observation_id=mint("visual_observation", ["i1", "two"]),
                            provenance=a_provenance(kind=ProvenanceKind.LIVE,
                                                    provider="p-two", model="m-two"))
    assert first.feature == second.feature
    assert {first.epistemic_status, second.epistemic_status} == {EpistemicStatus.INTERPRETIVE}
    with pytest.raises(ValidationError):
        an_observation(epistemic_status=EpistemicStatus.MEASURED,
                       note_that_two_models_agreed=True)


# ── 4. an interpretive observation needs no ground ───────────────────────────

def test_an_interpretive_observation_exists_without_a_region_or_a_ground():
    """The ordinary case must stay ordinary. A VLM saw something and nothing has segmented it;
    requiring a ground here would either block that path or invite a fabricated id."""
    observation = an_observation()
    assert observation.region_ref == "" and observation.ground_ref == ""
    assert observation.epistemic_status is EpistemicStatus.INTERPRETIVE


def test_ground_base_still_has_no_epistemic_status():
    """§2 of the directive, asserted where a refactor would trip over it. A ground is a MEASURED
    region; a status field on it is an invitation to store an unmeasured one."""
    from backend.schemas.soft_fields import GroundBase
    assert "epistemic_status" not in GroundBase.model_fields


# ── 5. an absence is not a negative finding ──────────────────────────────────

@pytest.mark.parametrize("state", [ObservationState.REFUSED, ObservationState.UNAVAILABLE])
def test_an_absent_observation_must_say_why(state):
    with pytest.raises(ValidationError) as caught:
        an_observation(state=state, visible_description="")
    assert "reads as evidence" in str(caught.value) or "visible_description" in str(caught.value)

    absent = an_observation(state=state, visible_description="",
                            absence_reason="the provider refused the image")
    assert absent.state is state
    assert absent.epistemic_status is not EpistemicStatus.MEASURED


@pytest.mark.parametrize("state", [ObservationState.REFUSED, ObservationState.UNAVAILABLE])
def test_nothing_was_produced_so_nothing_was_measured(state):
    with pytest.raises(ValidationError) as caught:
        an_observation(state=state, visible_description="", absence_reason="refused",
                       epistemic_status=EpistemicStatus.MEASURED, measurement=a_measurement())
    assert "nothing was measured" in str(caught.value)


# ── 6. replay, fixture and live identities stay explicit ─────────────────────

def test_a_live_provenance_must_name_its_provider_and_model():
    with pytest.raises(ValidationError) as caught:
        a_provenance(kind=ProvenanceKind.LIVE)
    assert "provider" in str(caught.value)
    assert a_provenance(kind=ProvenanceKind.LIVE, provider="p", model="m").provider == "p"


@pytest.mark.parametrize("kind", [ProvenanceKind.REPLAY, ProvenanceKind.FIXTURE,
                                  ProvenanceKind.DETERMINISTIC])
def test_a_run_that_reached_no_provider_may_not_name_one(kind):
    """A replay wearing a live face is the confusion the whole field exists to prevent."""
    with pytest.raises(ValidationError) as caught:
        a_provenance(kind=kind, provider="groq", model="some-model")
    assert "read as a live reading" in str(caught.value)


def test_local_is_its_own_identity_and_may_name_what_ran():
    """`local` is neither a provider call nor a replay — something ran, on this machine. It is
    allowed to name the model it ran, and required to name nothing."""
    assert a_provenance(kind=ProvenanceKind.LOCAL).model == ""
    assert a_provenance(kind=ProvenanceKind.LOCAL, model="a-local-weight").model == "a-local-weight"


# ── 7. the map's own shape ───────────────────────────────────────────────────

def test_an_observable_question_names_a_capability_class_and_an_interpretive_one_does_not():
    observable = InquiryQuestion(question_id=mint("inquiry_question", ["i1", "a"]),
                                 text="how far does it extend?",
                                 capability_classes=[CapabilityClass.EXTENT])
    interpretive = InquiryQuestion(question_id=mint("inquiry_question", ["i1", "b"]),
                                   text="what is it reaching for?")
    assert a_map(potentially_observable_questions=[observable],
                 interpretive_questions=[interpretive]).inquiry_id == "i1"

    with pytest.raises(ValidationError) as caught:
        a_map(potentially_observable_questions=[interpretive])
    assert "belongs in the other list" in str(caught.value)

    with pytest.raises(ValidationError) as caught:
        a_map(interpretive_questions=[observable])
    assert "move it rather than annotate it" in str(caught.value)


def test_a_map_refuses_two_things_with_the_same_id():
    twice = a_hypothesis()
    with pytest.raises(ValidationError) as caught:
        a_map(user_hypotheses=[twice, twice])
    assert "twice" in str(caught.value)


def test_a_requested_comparison_is_still_prompt_material():
    """It names images — that is a fact about the REQUEST. It reports nothing about them, and has
    no field in which it could."""
    comparison = RequestedComparison(comparison_id=mint("requested_comparison", ["i1", "a"]),
                                     text="compare the two surfaces", image_ids=["post_a", "post_b"])
    assert comparison.image_ids == ["post_a", "post_b"]
    assert "visible_description" not in RequestedComparison.model_fields
    with pytest.raises(ValidationError):
        RequestedComparison(comparison_id=mint("requested_comparison", ["i1", "b"]), text="t",
                            image_ids=["post_a", "post_a"])


def test_the_map_reports_which_images_the_person_pointed_at():
    first = RequestedComparison(comparison_id=mint("requested_comparison", ["i1", "a"]),
                                text="a vs b", image_ids=["post_a", "post_b"])
    second = RequestedComparison(comparison_id=mint("requested_comparison", ["i1", "b"]),
                                 text="b vs c", image_ids=["post_b", "post_c"])
    assert a_map(requested_comparisons=[first, second]).images_requested() == [
        "post_a", "post_b", "post_c"]


def test_an_ambiguity_is_kept_rather_than_resolved():
    ambiguity = Ambiguity(ambiguity_id=mint("ambiguity", ["i1", "a"]), text="'heavier' how?",
                          readings=["heavier in mass", "heavier in visual weight"])
    assert len(a_map(ambiguities=[ambiguity]).ambiguities[0].readings) == 2


def test_the_answer_form_is_a_shape_and_not_a_subject():
    """Every member has to be a thing one could want about anything at all — the enum is where a
    topic would hide most comfortably."""
    assert a_map().desired_answer_form is AnswerForm.UNSPECIFIED
    assert a_map(desired_answer_form=AnswerForm.COMPARISON).desired_answer_form.value == "comparison"


# ── 8. versions and ids ──────────────────────────────────────────────────────

def test_an_undeclared_schema_version_is_refused_rather_than_absorbed():
    with pytest.raises(ValidationError) as caught:
        a_map(schema_version="inquiry-intelligence.v99")
    assert "reviewed change" in str(caught.value)
    assert SCHEMA_VERSION in READABLE_SCHEMA_VERSIONS


@pytest.mark.parametrize("wrong", ["", "clm_deadbeef", "vob_deadbeef"])
def test_an_id_with_the_wrong_prefix_is_refused(wrong):
    with pytest.raises(ValidationError):
        a_hypothesis(hypothesis_id=wrong)


def test_ids_are_content_derived_and_carry_no_clock():
    """Same content, same id, in either order and at any time — which is what makes a re-run a
    comparison. The reasoning is `semantic_compilation.ids`; the prefixes are separate on purpose,
    because that module's table is pinned to the graph contract by exact equality."""
    assert mint("user_hypothesis", ["i1", "a"]) == mint("user_hypothesis", ["i1", "a"])
    assert mint("user_hypothesis", ["i1", "a"]) != mint("user_hypothesis", ["i1", "b"])
    assert mint("user_hypothesis", ["i1", "a"]) != mint("ambiguity", ["i1", "a"])
    with pytest.raises(KeyError):
        mint("not_a_declared_kind", ["x"])


def test_the_spine_prefixes_do_not_collide_with_the_graphs():
    from backend.services.semantic_compilation import ids as graph_ids
    from backend.schemas.inquiry_intelligence import PREFIXES
    assert not (set(PREFIXES.values()) & set(graph_ids.PREFIXES.values()))


# ── 9. serialization round-trips ─────────────────────────────────────────────

def test_every_field_survives_a_json_round_trip():
    """Not `model_dump()` — `model_dump(mode="json")` through an actual encode/decode, because the
    enums and the span tuple are exactly what a lazy dump gets away with and a stored document
    does not."""
    observation = an_observation(
        locus="along the lower edge", region_ref="reg_1", ground_ref="gnd_1",
        organization="repeating, with the interval widening downward",
        appearance_effect="reads as accelerating", interpretive_possibility="may be intentional",
        reading_block_refs=["rb_1", "rb_2"], uncertainty=0.4,
        requested_capability_classes=[CapabilityClass.EXTENT, CapabilityClass.PATTERN],
        epistemic_status=EpistemicStatus.MEASURED, measurement=a_measurement(run_ref="run_1"),
        provenance=a_provenance(kind=ProvenanceKind.LIVE, provider="p", model="m",
                                prompt_sha256="abc", note="n"))
    again = VisualObservation.model_validate(json.loads(json.dumps(
        observation.model_dump(mode="json"))))
    assert again == observation

    mapped = a_map(user_hypotheses=[a_hypothesis(spans=[PromptSpan(text="the folds", span=(0, 9),
                                                                   sentence_index=0)],
                                                 user_terms=["blunt"])],
                   user_vocabulary=["blunt", "transparent"],
                   desired_answer_form=AnswerForm.COMPARISON,
                   prompt_source_spans=[PromptSpan(text="the whole prompt")])
    assert InquiryMap.model_validate(json.loads(json.dumps(mapped.model_dump(mode="json")))) == mapped


def test_a_round_trip_of_a_dump_with_an_extra_key_is_refused():
    """The compatibility policy, exercised. A stored document that grew a key this code does not
    declare fails loudly rather than being silently narrowed on read."""
    body = an_observation().model_dump(mode="json")
    body["some_future_field"] = "arrived from a later version"
    with pytest.raises(ValidationError):
        VisualObservation.model_validate(body)


# ── 10. the alignment is a third object ──────────────────────────────────────

def a_relation(**kw):
    body = {"relation_id": mint("candidate_relation", ["i1", "a"]),
            "left_observation_id": mint("visual_observation", ["i1", "a"]),
            "right_observation_id": mint("visual_observation", ["i1", "b"]),
            "relation_kind": RelationKind.CONTRAST,
            "explanation": "the two are worked to opposite degrees of finish",
            "image_ids": ["post_a", "post_b"],
            "inquiry_relevance": "the question asked which of them is more worked",
            "provenance": a_provenance()}
    body.update(kw)
    return CandidateRelation(**body)


def a_contrast(**kw):
    body = {"contrast_id": mint("contrast_plan", ["i1", "a"]),
            "observation_ids": [mint("visual_observation", ["i1", "a"]),
                                mint("visual_observation", ["i1", "b"])],
            "image_ids": ["post_a", "post_b"],
            "comparison_dimension": "degree of finish",
            "why_it_matters": "the person's question turns on which is more worked",
            "difference_investigated": "whether one surface is left rougher than the other",
            "possible_countercondition": "both surfaces are worked identically and the difference "
                                         "is lighting",
            "provenance": a_provenance()}
    body.update(kw)
    return ContrastPlan(**body)


def two_observations(image_a="post_a", image_b="post_b"):
    return [an_observation(observation_id=mint("visual_observation", ["i1", "a"]), image_id=image_a),
            an_observation(observation_id=mint("visual_observation", ["i1", "b"]), image_id=image_b)]


def test_an_alignment_names_both_sides_and_lives_on_neither():
    """A `supported: true` on the hypothesis would make the person's sentence carry an image
    finding; the same field on the observation would make a picture carry the person's proposal.
    Neither field exists, so the relation has to be its own object."""
    assert "alignment" not in UserHypothesis.model_fields
    assert "supported" not in UserHypothesis.model_fields
    assert "hypothesis_id" not in VisualObservation.model_fields
    alignment = HypothesisAlignment(
        alignment_id=mint("hypothesis_alignment", ["i1", "a"]),
        hypothesis_id=mint("user_hypothesis", ["i1", "h"]),
        observation_id=mint("visual_observation", ["i1", "a"]),
        alignment=AlignmentKind.CHALLENGES,
        explanation="the surface the person called uniform is worked differently at the base",
        provenance=a_provenance())
    assert alignment.hypothesis_id.startswith("hyp_")
    assert alignment.observation_id.startswith("vob_")


def test_an_alignment_cannot_be_wired_backwards():
    """The prefixes are load bearing: swapping the two arguments is the mistake this catches, and
    it is a mistake no amount of care at the call site prevents forever."""
    with pytest.raises(ValidationError):
        HypothesisAlignment(alignment_id=mint("hypothesis_alignment", ["i1", "a"]),
                            hypothesis_id=mint("visual_observation", ["i1", "a"]),
                            observation_id=mint("user_hypothesis", ["i1", "h"]),
                            alignment=AlignmentKind.SUPPORTS, explanation="x",
                            provenance=a_provenance())


def test_an_alignment_has_no_status_to_launder_a_measurement_through():
    assert "epistemic_status" not in HypothesisAlignment.model_fields
    assert "measurement" not in HypothesisAlignment.model_fields


def test_the_two_negatives_are_first_class_answers():
    """A vocabulary with only supports/complicates/challenges forces every observation to take a
    side, and taking a side is how a picture becomes a witness for what the person already said."""
    for kind in (AlignmentKind.DOES_NOT_BEAR_ON, AlignmentKind.CANNOT_DETERMINE):
        alignment = HypothesisAlignment(
            alignment_id=mint("hypothesis_alignment", ["i1", kind.value]),
            hypothesis_id=mint("user_hypothesis", ["i1", "h"]),
            observation_id=mint("visual_observation", ["i1", "a"]),
            alignment=kind, explanation="the observation is about a different part of the picture",
            missing_capability_classes=[CapabilityClass.EXTENT], provenance=a_provenance())
        assert alignment.alignment is kind


# ── 11. a contrast must be falsifiable and must cross what it says it does ───

def test_a_contrast_needs_at_least_two_observations_to_contrast():
    with pytest.raises(ValidationError):
        a_contrast(observation_ids=[mint("visual_observation", ["i1", "a"])])


def test_a_cross_image_contrast_must_name_two_distinct_images():
    with pytest.raises(ValidationError) as caught:
        a_contrast(image_ids=["post_a"])
    assert "at least two distinct" in str(caught.value)


def test_a_single_image_contrast_is_a_legitimate_and_different_claim():
    single = a_contrast(scope=ContrastScope.SINGLE_IMAGE, image_ids=["post_a"])
    assert single.scope is ContrastScope.SINGLE_IMAGE
    with pytest.raises(ValidationError):
        a_contrast(scope=ContrastScope.SINGLE_IMAGE, image_ids=["post_a", "post_b"])


def test_a_contrast_that_cannot_say_what_would_embarrass_it_is_refused():
    """The load-bearing requirement in this model. A comparison with no countercondition is a
    description of an expected result, and it will find that result."""
    with pytest.raises(ValidationError):
        a_contrast(possible_countercondition="")
    with pytest.raises(ValidationError):
        a_contrast(possible_countercondition="   ")


def test_the_comparison_dimension_is_open_vocabulary():
    for dimension in ["degree of finish", "how the interval changes downward",
                      "whether the divisions repeat", "какой-то другой признак"]:
        assert a_contrast(comparison_dimension=dimension).comparison_dimension == dimension
    assert not hasattr(__import__("backend.schemas.inquiry_intelligence", fromlist=["x"]),
                       "ComparisonDimension"), "a dimension enum would close the vocabulary"


def test_priority_is_bounded_rather_than_free():
    assert a_contrast(priority=1).priority == 1
    for bad in (0, 6):
        with pytest.raises(ValidationError):
            a_contrast(priority=bad)


# ── 12. a relation stands between two things ────────────────────────────────

def test_a_relation_cannot_relate_an_observation_to_itself():
    same = mint("visual_observation", ["i1", "a"])
    with pytest.raises(ValidationError) as caught:
        a_relation(left_observation_id=same, right_observation_id=same)
    assert "relates" in str(caught.value) and "itself" in str(caught.value)


def test_a_relation_cannot_claim_to_cross_pictures_on_one_picture():
    with pytest.raises(ValidationError) as caught:
        a_relation(image_ids=["post_a"])
    assert "at least two" in str(caught.value)
    assert a_relation(scope=ContrastScope.SINGLE_IMAGE, image_ids=["post_a"]).image_ids == ["post_a"]


def test_a_relation_is_interpretive_until_something_measured_it():
    assert a_relation().epistemic_status is EpistemicStatus.INTERPRETIVE
    with pytest.raises(ValidationError) as caught:
        a_relation(epistemic_status=EpistemicStatus.MEASURED)
    assert "measurement provenance" in str(caught.value)
    assert a_relation(epistemic_status=EpistemicStatus.MEASURED,
                      measurement=a_measurement()).is_cross_image() is True


def test_a_relation_points_at_hypotheses_as_hypotheses():
    assert a_relation(hypothesis_refs=[mint("user_hypothesis", ["i1", "h"])]).hypothesis_refs
    with pytest.raises(ValidationError):
        a_relation(hypothesis_refs=[mint("visual_observation", ["i1", "a"])])


def test_a_relation_carries_its_own_counterevidence():
    """The proposer knows what it set aside. An empty list is not "unopposed" — it is "the proposer
    did not look", and the critic is told to read it that way."""
    assert a_relation().counterevidence == []
    assert a_relation(counterevidence=["the lighting differs between the two"]).counterevidence


# ── 13. references resolve, or say which one did not ────────────────────────

def test_a_dangling_reference_is_its_own_kind_of_failure():
    with pytest.raises(UnresolvedReference) as caught:
        resolve_observations([mint("visual_observation", ["i1", "missing"])], two_observations())
    assert "names no observation" in str(caught.value)


def test_resolution_is_all_or_nothing():
    """Returning what it could find would let a caller compute over a subset and report the whole."""
    refs = [mint("visual_observation", ["i1", "a"]), mint("visual_observation", ["i1", "gone"])]
    with pytest.raises(UnresolvedReference):
        resolve_observations(refs, two_observations())


def test_a_relation_that_declares_two_images_and_resolves_to_one_is_caught():
    """THE INVARIANT THAT COUNTING CANNOT REACH. Both observations are about the same picture, and
    `image_ids` lists two — the exact shape a cross-image claim takes when nothing crossed."""
    both_on_one = two_observations(image_a="post_a", image_b="post_a")
    relation = a_relation(image_ids=["post_a", "post_b"])
    with pytest.raises(UnresolvedReference) as caught:
        check_resolves(relation, both_on_one)
    assert "when nothing crossed" in str(caught.value)


def test_a_relation_whose_observations_really_do_cross_resolves():
    assert check_resolves(a_relation(), two_observations()) == ["post_a", "post_b"]


def test_a_contrast_resolves_by_the_same_rule():
    assert check_resolves(a_contrast(), two_observations()) == ["post_a", "post_b"]
    with pytest.raises(UnresolvedReference):
        check_resolves(a_contrast(), two_observations(image_a="post_a", image_b="post_a"))


def test_two_observations_with_one_id_are_refused_before_anything_resolves():
    duplicate = two_observations()[0]
    with pytest.raises(ValueError):
        index_observations([duplicate, duplicate])


# ── 14. the critic cannot rubber-stamp ───────────────────────────────────────

def a_critique(**kw):
    body = {"critique_id": mint("relation_critique", ["i1", "a"]),
            "relation_id": mint("candidate_relation", ["i1", "a"]),
            "verdict": CritiqueVerdict.ACCEPTED,
            "prompt_parroting": ParrotAssessment.NOT_PARROTING,
            "source_completeness": SourceCompleteness.COMPLETE,
            "image_diversity": ImageDiversity.CROSS_IMAGE,
            "inquiry_relevance": Relevance.RELEVANT,
            "unsupported_inference": InferenceSupport.SUPPORTED,
            "explanation": "both observations resolve, and the difference is not one the prompt "
                           "already named",
            "provenance": a_provenance()}
    body.update(kw)
    return RelationCritique(**body)


def test_a_fully_assessed_relation_can_be_accepted():
    assert a_critique().accepted() is True


def test_a_relation_with_missing_sources_cannot_be_accepted():
    """The directive's own wording. A critic that accepts a relation whose sources are not all
    there has accepted something nobody can go back and check."""
    for incomplete in (SourceCompleteness.MISSING, SourceCompleteness.PARTIAL):
        with pytest.raises(ValidationError) as caught:
            a_critique(source_completeness=incomplete)
        assert "source_completeness" in str(caught.value)


@pytest.mark.parametrize("field, value", [
    ("source_completeness", SourceCompleteness.UNASSESSED),
    ("unsupported_inference", InferenceSupport.UNASSESSED),
    ("prompt_parroting", ParrotAssessment.UNASSESSED),
    ("inquiry_relevance", Relevance.UNASSESSED),
])
def test_unassessed_blocks_acceptance_as_firmly_as_a_negative(field, value):
    """The rubber-stamp shape: everything accepted, nothing examined. It is what an automated
    critic drifts toward under load, so it is refused by construction rather than by review."""
    with pytest.raises(ValidationError) as caught:
        a_critique(**{field: value})
    assert "rubber stamp" in str(caught.value)


def test_parroting_the_prompt_blocks_acceptance_and_echoing_it_does_not():
    """A model handed a question and some pictures will restate the question about the pictures,
    fluently and emptily. Using the person's vocabulary while adding something is not that."""
    with pytest.raises(ValidationError):
        a_critique(prompt_parroting=ParrotAssessment.PARROTS_PROMPT)
    assert a_critique(prompt_parroting=ParrotAssessment.ECHOES_PROMPT).accepted()


def test_an_irrelevant_relation_cannot_be_accepted_however_good_it_is():
    with pytest.raises(ValidationError):
        a_critique(inquiry_relevance=Relevance.IRRELEVANT)
    assert a_critique(inquiry_relevance=Relevance.TANGENTIAL).accepted()


def test_a_missing_capability_is_recorded_and_does_not_block_acceptance():
    """Most relations worth keeping are interpretive and always will be. A critic that refused
    everything until an instrument existed would be a capability tracker, not a critic."""
    critique = a_critique(missing_capability_classes=[CapabilityClass.DEPTH])
    assert critique.accepted() and critique.missing_capability_classes == [CapabilityClass.DEPTH]


def test_the_unaccepting_verdicts_need_no_assessments_at_all():
    """A critic that could not reject without first filling in four fields would accept by
    default, which is the failure the gate exists to prevent, arriving from the other side."""
    for verdict in (CritiqueVerdict.REVISE, CritiqueVerdict.REJECTED, CritiqueVerdict.UNRESOLVED):
        critique = a_critique(verdict=verdict, prompt_parroting=ParrotAssessment.UNASSESSED,
                              source_completeness=SourceCompleteness.UNASSESSED,
                              inquiry_relevance=Relevance.UNASSESSED,
                              unsupported_inference=InferenceSupport.UNASSESSED)
        assert critique.accepted() is False


def test_a_critique_cannot_be_wired_to_something_that_is_not_a_relation():
    with pytest.raises(ValidationError):
        a_critique(relation_id=mint("visual_observation", ["i1", "a"]))


def test_a_speculative_reading_is_named_rather_than_removed():
    critique = a_critique(speculative_or_historical_warning="the dating is asserted, not sourced")
    assert critique.speculative_or_historical_warning


# ── 15. finishing and finding something are two axes ────────────────────────

def an_outcome(**kw):
    body = {"outcome_id": mint("intelligence_outcome", ["i1"]), "inquiry_id": "i1",
            "comparative": True, "workflow": WorkflowCompletion.COMPLETED,
            "outcome": IntelligenceOutcome.UNDERPERFORMED,
            "explanation": "every relation restated the question",
            "provenance": a_provenance()}
    body.update(kw)
    return IntelligenceOutcomeRecord(**body)


def test_a_clean_run_that_found_nothing_is_expressible():
    """The most likely result this system produces has to have a name. A vocabulary in which a
    finished run is a successful one cannot express it."""
    record = an_outcome(counts=IntelligenceCounts(observations=40, relations=12,
                                                  accepted_relations=0))
    assert record.finished() is True
    assert record.was_useful() is False


def test_a_comparative_inquiry_with_no_accepted_cross_image_relation_is_not_useful():
    """§7 of the directive, and the specific shape this system fails in: plenty of observations,
    plenty of sentences, nothing that ever crossed from one picture to another."""
    with pytest.raises(ValidationError) as caught:
        an_outcome(outcome=IntelligenceOutcome.USEFUL_RELATIONS, comparative=True,
                   counts=IntelligenceCounts(observations=40, relations=12, accepted_relations=9,
                                             accepted_cross_image_relations=0))
    assert "none of which crosses" in str(caught.value)
    assert "underperformed" in str(caught.value)


def test_the_same_counts_are_useful_once_one_relation_actually_crosses():
    record = an_outcome(outcome=IntelligenceOutcome.USEFUL_RELATIONS, comparative=True,
                        counts=IntelligenceCounts(observations=40, relations=12,
                                                  accepted_relations=9,
                                                  accepted_cross_image_relations=1))
    assert record.was_useful()


def test_a_single_image_inquiry_is_not_held_to_the_cross_image_rule():
    """The rule is about COMPARATIVE questions. A question about one picture that produced an
    accepted relation within it is a success, and forcing it to fail would teach the pipeline to
    declare every inquiry non-comparative."""
    assert an_outcome(comparative=False, outcome=IntelligenceOutcome.USEFUL_RELATIONS,
                      counts=IntelligenceCounts(relations=3, accepted_relations=2)).was_useful()


def test_useful_requires_something_a_critic_let_through():
    with pytest.raises(ValidationError) as caught:
        an_outcome(comparative=False, outcome=IntelligenceOutcome.USEFUL_RELATIONS,
                   counts=IntelligenceCounts(relations=12, accepted_relations=0))
    assert "what a critic let through" in str(caught.value)


def test_a_failed_workflow_cannot_report_useful_relations():
    with pytest.raises(ValidationError) as caught:
        an_outcome(workflow=WorkflowCompletion.FAILED,
                   outcome=IntelligenceOutcome.USEFUL_RELATIONS, comparative=False,
                   counts=IntelligenceCounts(relations=2, accepted_relations=1))
    assert "there was no whole run" in str(caught.value)


@pytest.mark.parametrize("outcome", [IntelligenceOutcome.TRUNCATED, IntelligenceOutcome.ERROR,
                                     IntelligenceOutcome.REFUSED,
                                     IntelligenceOutcome.CAPABILITY_GAP,
                                     IntelligenceOutcome.PROMPT_DOMINATED,
                                     IntelligenceOutcome.UNDERPERFORMED])
def test_every_other_outcome_survives_a_failed_workflow(outcome):
    assert an_outcome(workflow=WorkflowCompletion.FAILED, outcome=outcome).outcome is outcome


def test_the_two_axes_are_independent_in_both_directions():
    """completed+underperformed and partial+useful are both real, and a single `status` field
    could express neither."""
    assert an_outcome(workflow=WorkflowCompletion.COMPLETED,
                      outcome=IntelligenceOutcome.UNDERPERFORMED).finished()
    partly = an_outcome(workflow=WorkflowCompletion.PARTIAL, comparative=False,
                        outcome=IntelligenceOutcome.USEFUL_RELATIONS,
                        counts=IntelligenceCounts(relations=2, accepted_relations=1))
    assert partly.was_useful() and not partly.finished()


def test_the_counts_must_be_arithmetically_possible():
    for bad in ({"relations": 2, "accepted_relations": 3},
                {"relations": 5, "accepted_relations": 2, "accepted_cross_image_relations": 3},
                {"observations": 1, "measured_observations": 2},
                {"observations": 1, "refused_observations": 2}):
        with pytest.raises(ValidationError):
            IntelligenceCounts(**bad)


def test_insufficient_observations_cannot_be_blamed_for_accepted_relations():
    with pytest.raises(ValidationError):
        an_outcome(outcome=IntelligenceOutcome.INSUFFICIENT_OBSERVATIONS,
                   counts=IntelligenceCounts(relations=3, accepted_relations=2,
                                             accepted_cross_image_relations=1))


# ── 16. four subjects, one set of contracts ─────────────────────────────────

@pytest.mark.parametrize("name", F.FIXTURES)
def test_a_fixture_loads_through_the_real_models(name):
    loaded = F.load(name)
    assert loaded.name == name
    assert loaded.observations and loaded.relations and loaded.critiques


@pytest.mark.parametrize("name", F.FIXTURES)
def test_a_fixture_round_trips_without_dropping_a_field(name):
    """The stored document is the thing under test. A fixture built in memory proves nothing about
    what survives an encode and a decode, which is the only form these objects will ever be in by
    the time anybody reads them."""
    body = F.raw(name)
    loaded = F.load(name)
    assert loaded.inquiry_map.model_dump(mode="json") == body["inquiry_map"]
    assert [o.model_dump(mode="json") for o in loaded.observations] == body["observations"]
    assert [a.model_dump(mode="json") for a in loaded.alignments] == body["alignments"]
    assert [c.model_dump(mode="json") for c in loaded.contrasts] == body["contrasts"]
    assert [r.model_dump(mode="json") for r in loaded.relations] == body["relations"]
    assert [c.model_dump(mode="json") for c in loaded.critiques] == body["critiques"]
    assert loaded.outcome.model_dump(mode="json") == body["outcome"]


@pytest.mark.parametrize("name", F.FIXTURES)
def test_every_reference_in_a_fixture_resolves(name):
    """Not "the ids look plausible" — every contrast and every relation is resolved against the
    observations that fixture actually carries, and the declared images must equal the resolved
    ones."""
    loaded = F.load(name)
    known = {o.observation_id for o in loaded.observations}
    for item in (*loaded.contrasts, *loaded.relations):
        check_resolves(item, loaded.observations)
    for alignment in loaded.alignments:
        assert alignment.observation_id in known
        assert alignment.hypothesis_id in loaded.inquiry_map.hypothesis_ids()
    for critique in loaded.critiques:
        loaded.relation(critique.relation_id)


@pytest.mark.parametrize("name", F.FIXTURES)
def test_a_fixtures_counts_are_the_objects_it_actually_carries(name):
    """The outcome cannot lie about the run it summarises. This is the arithmetic the record's own
    validator cannot do — it never sees the objects, only the numbers."""
    loaded, counts = F.load(name), F.load(name).outcome.counts
    assert counts.observations == len(loaded.observations)
    assert counts.relations == len(loaded.relations)
    assert counts.alignments == len(loaded.alignments)
    assert counts.contrasts == len(loaded.contrasts)
    assert counts.hypotheses == len(loaded.inquiry_map.user_hypotheses)
    assert counts.refused_observations == len(
        [o for o in loaded.observations if o.state is not ObservationState.OBSERVED])
    assert counts.accepted_relations == len(loaded.accepted_critiques())
    crossing = [c for c in loaded.accepted_critiques()
                if len(check_resolves(loaded.relation(c.relation_id), loaded.observations)) >= 2]
    assert counts.accepted_cross_image_relations == len(crossing)


@pytest.mark.parametrize("name", F.FIXTURES)
def test_a_critics_image_diversity_claim_is_true_of_the_observations(name):
    """The critic says `cross_image`; resolution says whether it is. A claim nobody checks against
    the objects is the claim that drifts first."""
    loaded = F.load(name)
    for critique in loaded.critiques:
        if critique.image_diversity is ImageDiversity.CROSS_IMAGE:
            resolved = check_resolves(loaded.relation(critique.relation_id), loaded.observations)
            assert len(resolved) >= 2, (critique.critique_id, resolved)


@pytest.mark.parametrize("name", F.FIXTURES)
def test_nothing_in_any_fixture_is_measured(name):
    """No instrument has run in any of these. Every observation and every relation is interpretive,
    and the fixtures would be dishonest in exactly the way the schema exists to prevent if one of
    them quietly were not."""
    loaded = F.load(name)
    for observation in loaded.observations:
        assert observation.epistemic_status is not EpistemicStatus.MEASURED
        assert observation.measurement is None
    for relation in loaded.relations:
        assert relation.epistemic_status is EpistemicStatus.INTERPRETIVE
    assert loaded.outcome.counts.measured_observations == 0


@pytest.mark.parametrize("name", F.FIXTURES)
def test_every_observation_is_about_a_picture_the_person_pointed_at(name):
    loaded = F.load(name)
    requested = set(loaded.inquiry_map.images_requested())
    for observation in loaded.observations:
        assert observation.image_id in requested, (observation.observation_id, requested)


@pytest.mark.parametrize("name", F.FIXTURES)
def test_every_fixture_keeps_the_persons_words_as_the_persons(name):
    loaded = F.load(name)
    for hypothesis in loaded.inquiry_map.user_hypotheses:
        assert hypothesis.origin is MaterialOrigin.PROMPT
        dumped = hypothesis.model_dump(mode="json")
        assert not ({"image_id", "region_ref", "ground_ref", "epistemic_status", "measurement"}
                    & set(dumped))


# ── 17. the adversarial case: the pictures disagree with the person ─────────

def test_the_system_can_tell_the_person_they_are_wrong():
    """A system that can only agree with its user has no way to be useful to them.

    Note what does NOT happen: the hypothesis is not amended, not annotated and not downgraded. It
    sits in the map exactly as typed, and the disagreement lives in a third object beside it.
    """
    loaded = F.load("contradicted-hypothesis")
    hypothesis = loaded.inquiry_map.user_hypotheses[0]
    challenges = [a for a in loaded.alignments if a.alignment is AlignmentKind.CHALLENGES]
    assert challenges, "the adversarial fixture must contain an actual challenge"
    assert all(a.hypothesis_id == hypothesis.hypothesis_id for a in challenges)
    assert hypothesis.text == F.raw("contradicted-hypothesis")["inquiry_map"]["user_hypotheses"][0]["text"]
    assert loaded.accepted_critiques(), "the contradiction was accepted, not merely proposed"
    assert loaded.outcome.was_useful()


def test_an_inquiry_can_both_support_and_challenge_one_hypothesis():
    """Two pictures, one claim, opposite bearings. Nothing reconciles them into a score."""
    loaded = F.load("contradicted-hypothesis")
    kinds = {a.alignment for a in loaded.alignments}
    assert AlignmentKind.SUPPORTS in kinds and AlignmentKind.CHALLENGES in kinds


def test_a_finished_run_can_still_be_prompt_dominated():
    """The other end of the same axis: the machinery completed, the critic refused the one relation
    it produced for restating the question, and the record says so rather than reporting a
    success."""
    loaded = F.load("rose-window-organization")
    assert loaded.outcome.finished() is True
    assert loaded.outcome.was_useful() is False
    assert loaded.outcome.outcome is IntelligenceOutcome.PROMPT_DOMINATED
    assert loaded.critiques[0].prompt_parroting is ParrotAssessment.PARROTS_PROMPT
    assert [o for o in loaded.observations if o.state is ObservationState.REFUSED]


# ── 18. the contracts do not know what any of this is about ─────────────────

PRODUCTION_SOURCES = [Path("backend/schemas/inquiry_intelligence.py")]


def _scannable() -> list:
    return [(p, (ROOT / p).read_text(encoding="utf-8").lower()) for p in PRODUCTION_SOURCES]


def _mentions(text: str, noun: str) -> bool:
    """Whole words only.

    A substring scan reports `rose` inside `prose` and `rim` inside `trimmed`, which is not a
    theoretical concern — both occur in this module, and a scan that cried wolf on them would be
    switched off within a week. The tree's existing scan in `test_semantic_dissolution_fixtures`
    is substring-based and gets away with it because none of its nouns embed in ordinary English.
    """
    return re.search(rf"\b{re.escape(noun)}\b", text) is not None


def test_no_contract_source_names_any_fixtures_subject():
    nouns = F.topic_nouns()
    assert len(nouns) >= 15, "the scan is pointed at too little vocabulary"
    sources = _scannable()
    assert sources and all(text for _, text in sources), "the scan is pointed at nothing"
    offences = [f"{path}: {noun}" for path, text in sources for noun in nouns
                if _mentions(text, noun)]
    assert not offences, offences


def test_the_scan_would_catch_a_planted_noun():
    """The negative control. A guard nobody has seen fail is a guard nobody knows is running."""
    for noun in ("drapery", "nave", "frond", "vessel", "sculpture"):
        assert _mentions(f"a field describing the {noun} in question", noun)
    assert not _mentions("one prose field holding all three", "rose")
    assert not _mentions("whitespace collapsed and trimmed", "rim")


def test_the_four_subjects_share_no_vocabulary():
    """The generality claim in the only form it can take. If two fixtures shared subject words, a
    module that had learned one of them would still pass."""
    subjects = {k: set(v) for k, v in F.TOPIC_NOUNS.items() if not k.startswith("_")}
    for left in subjects:
        for right in subjects:
            if left < right:
                assert not (subjects[left] & subjects[right]), (left, right)


def test_no_enum_in_the_contracts_names_a_subject():
    """Every closed set, member by member. An enum is where a topic hides most comfortably, because
    it looks like vocabulary rather than like a decision about what can be said."""
    import backend.schemas.inquiry_intelligence as module
    nouns = F.topic_nouns()
    for attribute in vars(module).values():
        if isinstance(attribute, type) and issubclass(attribute, Enum):
            for member in attribute:
                for noun in nouns:
                    assert not _mentions(str(member.value).lower(), noun), (attribute, member)


def test_the_open_fields_really_are_open():
    """The counterpart of the enum scan: the fields that carry a subject are plain strings, and a
    later `Literal` or enum on any of them would close the vocabulary."""
    from backend.schemas.inquiry_intelligence import ContrastPlan, VisualObservation
    for model, field in ((VisualObservation, "feature"), (VisualObservation, "locus"),
                         (ContrastPlan, "comparison_dimension"), (UserHypothesis, "text")):
        annotation = model.model_fields[field].annotation
        assert annotation is str, (model.__name__, field, annotation)
