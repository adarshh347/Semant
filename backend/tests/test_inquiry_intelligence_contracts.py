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
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.schemas.inquiry_intelligence import (READABLE_SCHEMA_VERSIONS, SCHEMA_VERSION,
                                                  Ambiguity, AnswerForm, CapabilityClass,
                                                  EpistemicStatus, InquiryMap, InquiryQuestion,
                                                  MaterialOrigin, MeasurementProvenance,
                                                  ObservationState, PromptSpan, Provenance,
                                                  ProvenanceKind, RequestedComparison,
                                                  UserHypothesis, VisualObservation, mint)

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
