"""
INTELLIGENCE-002A — the two passes, and whether the wall between them holds.

These are not tests of how well a model describes a picture; every reply here is committed. They
test the five guards named in `observer.py`, one section each, plus the identity vocabulary that
keeps a replay from being reported as a live reading.

The guards are tested the way the module claims them — structurally where the claim is structural.
Guard 1 is a signature assertion. Guard 4 is an assertion over the source of `align_hypotheses`,
because "this function never constructs an observation" is a property of the text of the function
and testing it by example would only show that it did not happen to today.
"""
from __future__ import annotations

import dataclasses
import inspect

import pytest

from backend.services.epistemics import EpistemicStatus
from backend.services.inquiry_intelligence import observer as O
from backend.services.inquiry_intelligence.intent import read_inquiry
from backend.services.inquiry_intelligence.observer import (BLIND_INSTRUCTION, AlignmentRelation,
                                                            AlignmentRefusalCode,
                                                            BlindObservationRequest,
                                                            BlindObservationSet, ExecutionIdentity,
                                                            ImageRef, MeasurementEvidence,
                                                            ModelIdentity, NothingRecorded,
                                                            PromptLeak, ProvenanceError,
                                                            ProviderKind, SequenceIds,
                                                            VisualObservation, align_hypotheses,
                                                            fixture_client, hosted_client,
                                                            local_client, observe_images,
                                                            replay_client)
from backend.tests.fixtures import inquiry_observation_fixtures as F


def _scene(name):
    for scene_name, prompt, images, factory in F.CLEAN_SCENES:
        if scene_name == name:
            return prompt, images, factory()
    raise AssertionError(name)


# ── identity ─────────────────────────────────────────────────────────────────

def test_the_execution_identity_mirror_still_agrees_with_the_laboratorys():
    """`observer.ExecutionIdentity` mirrors the lab's by value rather than importing it. A mirror
    nobody checks is a fork, so this is the check."""
    from backend.schemas.perception_lab import ExecutionIdentity as LabIdentity
    assert {e.value for e in ExecutionIdentity} == {e.value for e in LabIdentity}
    assert {e.name for e in ExecutionIdentity} == {e.name for e in LabIdentity}


def test_a_frozen_client_may_not_wear_live():
    with pytest.raises(ProvenanceError) as exc:
        O.FrozenClient(ModelIdentity(ExecutionIdentity.LIVE, ProviderKind.RECORDED, "x", "y"))
    assert "may not wear LIVE" in str(exc.value)


def test_a_frozen_client_may_not_name_a_provider_that_did_not_run_in_this_run():
    with pytest.raises(ProvenanceError):
        O.FrozenClient(ModelIdentity(ExecutionIdentity.REPLAY, ProviderKind.HOSTED, "x", "y"))


def test_a_transport_client_may_not_wear_replay():
    """Rule 11. Something calls out when this runs; a REPLAY badge over it is the exact lie the
    identity vocabulary exists to catch."""
    with pytest.raises(ProvenanceError) as exc:
        O.TransportClient(lambda p: {}, ModelIdentity(ExecutionIdentity.REPLAY,
                                                      ProviderKind.HOSTED, "x", "y"))
    assert "REPLAY" in str(exc.value)


def test_hosted_and_local_are_the_same_identity_and_different_facts():
    hosted = hosted_client(lambda p: {}, provider="openrouter", model="m")
    local = local_client(lambda p: {}, provider="qwen-local", model="m")
    assert hosted.identity.identity is local.identity.identity is ExecutionIdentity.LIVE
    assert hosted.identity.provider_kind is ProviderKind.HOSTED
    assert local.identity.provider_kind is ProviderKind.LOCAL


def test_replay_and_fixture_are_not_the_same_badge():
    """A replay re-shows a call that happened; a fixture was never a call. A hand-authored
    adversarial sample must not be reportable as a reading that once occurred."""
    assert replay_client({}).identity.identity is ExecutionIdentity.REPLAY
    assert fixture_client({}).identity.identity is ExecutionIdentity.FIXTURE


def test_an_identity_with_no_provider_named_is_refused():
    with pytest.raises(ProvenanceError):
        ModelIdentity(ExecutionIdentity.LIVE, ProviderKind.HOSTED, "  ", "m")


def test_a_transport_client_carries_no_provider_sdk_and_calls_what_it_is_handed():
    seen = []
    client = hosted_client(lambda payload: seen.append(payload) or {"observations": []},
                           provider="openrouter", model="m")
    client.observe(BlindObservationRequest(ImageRef("i", "s")))
    assert seen[0]["role"] == "blind_observer"
    assert seen[0]["image"]["image_id"] == "i"


# ── guard 1: there is no parameter for the prompt ────────────────────────────

def test_the_blind_pass_has_no_parameter_that_could_carry_the_prompt():
    params = inspect.signature(observe_images).parameters
    assert set(params) == {"images", "client", "ids"}
    assert not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def test_the_blind_request_can_hold_nothing_but_an_image_and_the_fixed_instruction():
    assert {f.name for f in dataclasses.fields(BlindObservationRequest)} == {"image", "instruction"}


# ── guard 2: the request is sealed ───────────────────────────────────────────

def test_the_instruction_is_not_the_callers_to_choose():
    with pytest.raises(PromptLeak) as exc:
        BlindObservationRequest(ImageRef("i", "s"),
                                instruction="The user thinks the drapery carries the weight.")
    assert "not the caller's to choose" in str(exc.value)


def test_the_sealed_instruction_names_no_subject_matter():
    """Rule 5, at the one seam where a topic would reach a model on every single call."""
    lowered = BLIND_INSTRUCTION.lower()
    for topic in ("fold", "drapery", "sculpt", "architect", "facade", "plant", "leaf", "column"):
        assert topic not in lowered


@pytest.mark.parametrize("bad", ["a paragraph\nof the person's question", "x" * 600])
def test_an_image_reference_that_is_really_a_paragraph_is_refused(bad):
    """The second channel. An id is an identifier; a multi-line or enormous one is prose riding
    into the prompt-blind pass under a field name nobody reads twice."""
    with pytest.raises(PromptLeak):
        ImageRef("img", bad)


def test_an_image_reference_needs_an_id():
    with pytest.raises(PromptLeak):
        ImageRef("   ", "posts/1.jpg")


def test_an_image_reference_field_must_be_text():
    with pytest.raises(PromptLeak):
        ImageRef("img", {"source": "posts/1.jpg"})


# ── the blind pass ───────────────────────────────────────────────────────────

def test_each_image_is_asked_about_on_its_own():
    """One call per image, and each request carries only its own image.

    Not a batching preference. An image described alongside three others is described in their
    company, and a resemblance the run later reports would have been partly manufactured by the
    request that produced it.
    """
    seen = []

    class _Recorder:
        identity = ModelIdentity(ExecutionIdentity.FIXTURE, ProviderKind.RECORDED, "c", "c")

        def observe(self, request):
            seen.append(request)
            return {"observations": []}

    images = F.ARCHITECTURE_IMAGES
    observe_images(images, _Recorder())
    assert len(seen) == len(images)
    assert [r.image.image_id for r in seen] == [i.image_id for i in images]
    assert all(r.instruction == BLIND_INSTRUCTION for r in seen)


@pytest.mark.parametrize("name", ["sculpture", "architecture", "plant"])
def test_a_clean_scene_produces_observations_with_all_six_content_fields(name):
    _, images, client = _scene(name)
    result = observe_images(images, client)
    assert result.observations and not result.failures
    for o in result.observations:
        assert o.feature and o.locus and o.visible_organization and o.appearance_effect
        assert o.image_ref in {i.image_id for i in images}


def test_observations_are_stamped_with_the_image_that_was_actually_being_read():
    """The model's own attribution is kept but does not win. An observation that could be moved
    onto another image by the model saying so is not evidence about any image."""
    result = observe_images(F.ADVERSARIAL_IMAGES, F.adversarial_client())
    moved = [o for o in result.observations if o.observation_id == "adv_obs_5"][0]
    assert moved.image_ref == "adv_1"
    assert moved.claimed_image_ref == "adv_2"


def test_two_images_under_one_id_are_refused():
    with pytest.raises(PromptLeak) as exc:
        observe_images([ImageRef("same", "a.jpg"), ImageRef("same", "b.jpg")],
                       F.sculpture_client())
    assert "appears twice" in str(exc.value)


def test_something_that_is_not_an_image_reference_is_refused():
    with pytest.raises(PromptLeak):
        observe_images(["posts/1.jpg"], F.sculpture_client())


def test_a_frozen_client_will_not_invent_a_reply_for_an_image_it_has_no_record_of():
    with pytest.raises(NothingRecorded):
        F.sculpture_client().observe(BlindObservationRequest(ImageRef("unknown", "x.jpg")))


def test_one_unreadable_image_does_not_take_the_other_readings_with_it():
    """The useful answer to "one of three was unreadable" is the other two plus that sentence."""
    images = F.ARCHITECTURE_IMAGES + (ImageRef("facade_c", "posts/facade_c.jpg"),)
    result = observe_images(images, F.architecture_client())
    assert len(result.observations) == 2
    assert len(result.failures) == 1 and "facade_c" in result.failures[0]


def test_a_missing_record_becomes_a_named_failure_and_never_an_empty_reading():
    """"nothing was recorded" and "the model saw nothing" are two different facts, and only one
    of them is about the picture."""
    result = observe_images([ImageRef("nope", "x.jpg")], F.sculpture_client())
    assert result.observations == () and result.failures
    assert "no reply is recorded" in result.failures[0]


def test_a_reply_with_no_observations_key_is_a_failure_rather_than_a_silent_zero():
    client = fixture_client({"i": {"readings": []}})
    result = observe_images([ImageRef("i", "x.jpg")], client)
    assert not result.observations and "no 'observations' key" in result.failures[0]


def test_a_reply_missing_a_field_still_parses_so_that_the_audit_can_see_it():
    """DELIBERATELY PERMISSIVE. A parser that raised on a missing `locus` would mean the audit's
    missing-field findings could never fire on a real reply."""
    client = fixture_client({"i": {"observations": [{"feature": "a block"}]}})
    result = observe_images([ImageRef("i", "x.jpg")], client)
    assert result.observations[0].feature == "a block"
    assert result.observations[0].locus == ""


def test_ids_are_deterministic_so_two_runs_of_one_record_can_be_diffed():
    a = observe_images(F.SCULPTURE_IMAGES, F.sculpture_client(), ids=SequenceIds("run"))
    b = observe_images(F.SCULPTURE_IMAGES, F.sculpture_client(), ids=SequenceIds("run"))
    assert [o.observation_id for o in a.observations] == [o.observation_id for o in b.observations]


def test_the_blind_set_says_it_read_the_images_one_at_a_time():
    assert observe_images(F.SCULPTURE_IMAGES, F.sculpture_client()).per_image is True


# ── guard 5: nothing here is measured ────────────────────────────────────────

def test_a_reading_is_interpretive_even_when_the_model_calls_it_measured():
    """Rule 8. And the claim is kept, not erased — a parser that quietly rewrote 'measured' to
    'interpretive' would keep the audit green forever while the model went on claiming it."""
    result = observe_images(F.ADVERSARIAL_IMAGES, F.adversarial_client())
    claimed = [o for o in result.observations if o.observation_id == "adv_obs_3"][0]
    assert claimed.epistemic_status is EpistemicStatus.INTERPRETIVE
    assert claimed.claimed_status == "measured"


def test_agreement_is_not_a_measuring_capability():
    """Rule 9, at the constructor. 'Three models concurred' is a fact about the models."""
    with pytest.raises(ProvenanceError) as exc:
        MeasurementEvidence("model_agreement", "count", 11.0, "channels", "run_1")
    assert "not measurement" in str(exc.value)


@pytest.mark.parametrize("capability", ["consensus", "Majority", "self-consistency", "ensemble",
                                        "cross_model"])
def test_every_name_agreement_travels_under_is_refused(capability):
    with pytest.raises(ProvenanceError):
        MeasurementEvidence(capability, "count", 1.0, "x", "run_1")


def test_a_measurement_with_no_artifact_behind_it_is_refused():
    with pytest.raises(ProvenanceError):
        MeasurementEvidence("mask_geometry", "area", 1.0, "px", "  ")


def test_an_agreement_measurement_in_a_reply_does_not_lift_the_reading_out_of_interpretive():
    result = observe_images(F.ADVERSARIAL_IMAGES, F.adversarial_client())
    lifted = [o for o in result.observations if o.observation_id == "adv_obs_3"][0]
    assert lifted.provenance.measurement is None
    assert lifted.epistemic_status is EpistemicStatus.INTERPRETIVE


def test_a_real_measuring_capability_does_lift_it():
    client = fixture_client({"i": {"observations": [
        {"feature": "a void", "locus": "upper band",
         "measurement": {"capability": "mask_geometry", "quantity": "area", "value": 210.0,
                         "units": "px", "artifact_ref": "artifact_9"}}]}})
    o = observe_images([ImageRef("i", "x.jpg")], client).observations[0]
    assert o.epistemic_status is EpistemicStatus.MEASURED
    assert o.provenance.measurement.capability == "mask_geometry"


# ── guard 3 and 4: alignment ─────────────────────────────────────────────────

def test_alignment_will_only_accept_a_set_the_blind_pass_built():
    """Guard 3. Only `observe_images` constructs a `BlindObservationSet`, which is what makes the
    ordering of the two passes enforceable rather than conventional."""
    prompt, images, client = _scene("architecture")
    with pytest.raises(PromptLeak) as exc:
        align_hypotheses(read_inquiry(prompt), [VisualObservation("o", "i", "f", "l", "v", "a",
                                                                  "p", "u")], client)
    assert "BlindObservationSet" in str(exc.value)


def test_the_alignment_pass_never_constructs_an_observation():
    """Guard 4, over the source. "It did not happen in this test" is a weaker claim than "the call
    is not in the function", and the second is the one the module docstring makes."""
    source = inspect.getsource(align_hypotheses)
    assert "VisualObservation(" not in source
    assert "BlindObservationSet(" not in source


def test_no_field_of_an_alignment_can_hold_an_observation():
    for f in dataclasses.fields(O.HypothesisAlignment):
        assert "VisualObservation" not in str(f.type)
    assert {f.name for f in dataclasses.fields(O.HypothesisAlignment)} >= {"observation_ids"}


def test_a_real_alignment_relates_the_two_without_adding_to_either():
    prompt, images, client = _scene("architecture")
    inquiry = read_inquiry(prompt)
    observations = observe_images(images, client)
    result = align_hypotheses(inquiry, observations, client)
    assert not result.refusals
    assert {a.relation for a in result.alignments} == {AlignmentRelation.COMPLICATES,
                                                       AlignmentRelation.CANNOT_DETERMINE}
    for a in result.alignments:
        assert a.hypothesis_id in inquiry.hypothesis_ids
        assert set(a.observation_ids) <= observations.ids


def test_an_alignment_citing_an_observation_nobody_produced_is_refused_not_created():
    """The difference between "the model referred to something that does not exist" and "the model
    found a new thing" is the whole of this pass."""
    prompt, images, client = _scene("architecture")
    observations = observe_images(images, client)
    liar = fixture_client(alignments={"*": {"alignments": [
        {"hypothesis_id": "hyp_1", "relation": "supports",
         "observation_ids": ["facade_a_obs_1", "invented_obs"]}]}})
    result = align_hypotheses(read_inquiry(prompt), observations, liar)
    assert not result.alignments
    assert result.refusals[0].code is AlignmentRefusalCode.UNKNOWN_OBSERVATION
    assert "invented_obs" in result.refusals[0].detail


def test_the_three_grounded_relations_cannot_rest_on_nothing():
    """You cannot support, complicate or challenge a hypothesis out of nothing. The two relations
    for having nothing are the two that say so."""
    prompt, images, client = _scene("architecture")
    observations = observe_images(images, client)
    liar = fixture_client(alignments={"*": {"alignments": [
        {"hypothesis_id": "hyp_1", "relation": r, "observation_ids": []}
        for r in ("supports", "complicates", "challenges")]}})
    result = align_hypotheses(read_inquiry(prompt), observations, liar)
    assert not result.alignments
    assert {r.code for r in result.refusals} == {AlignmentRefusalCode.UNGROUNDED_RELATION}


def test_the_two_ungrounded_relations_are_allowed_to_cite_nothing():
    prompt, images, client = _scene("architecture")
    observations = observe_images(images, client)
    honest = fixture_client(alignments={"*": {"alignments": [
        {"hypothesis_id": "hyp_1", "relation": "does_not_bear_on", "observation_ids": []},
        {"hypothesis_id": "hyp_1", "relation": "cannot_determine", "observation_ids": []}]}})
    result = align_hypotheses(read_inquiry(prompt), observations, honest)
    assert len(result.alignments) == 2 and not result.refusals


def test_an_alignment_answering_a_claim_nobody_made_is_refused():
    prompt, images, client = _scene("architecture")
    observations = observe_images(images, client)
    liar = fixture_client(alignments={"*": {"alignments": [
        {"hypothesis_id": "hyp_77", "relation": "supports",
         "observation_ids": ["facade_a_obs_1"]}]}})
    result = align_hypotheses(read_inquiry(prompt), observations, liar)
    assert result.refusals[0].code is AlignmentRefusalCode.UNKNOWN_HYPOTHESIS


def test_a_sixth_relation_is_refused_rather_than_mapped_onto_the_nearest_of_the_five():
    prompt, images, client = _scene("architecture")
    observations = observe_images(images, client)
    liar = fixture_client(alignments={"*": {"alignments": [
        {"hypothesis_id": "hyp_1", "relation": "proves",
         "observation_ids": ["facade_a_obs_1"]}]}})
    result = align_hypotheses(read_inquiry(prompt), observations, liar)
    assert result.refusals[0].code is AlignmentRefusalCode.UNKNOWN_RELATION


def test_refusals_are_kept_so_a_hallucinating_pass_cannot_look_like_a_clean_one():
    """A pass that dropped its four bad alignments would report six clean ones and read better
    than a pass that had not hallucinated at all."""
    inquiry = read_inquiry(F.ADVERSARIAL_PROMPT)
    observations = observe_images(F.ADVERSARIAL_IMAGES, F.adversarial_client())
    result = align_hypotheses(inquiry, observations, F.adversarial_client())
    assert not result.alignments
    assert {r.code for r in result.refusals} == {
        AlignmentRefusalCode.UNKNOWN_OBSERVATION, AlignmentRefusalCode.UNKNOWN_HYPOTHESIS,
        AlignmentRefusalCode.UNGROUNDED_RELATION, AlignmentRefusalCode.UNKNOWN_RELATION}
    assert all(r.offered for r in result.refusals)


def test_a_malformed_alignment_reply_is_a_refusal_and_not_an_empty_success():
    prompt, images, client = _scene("architecture")
    observations = observe_images(images, client)
    result = align_hypotheses(read_inquiry(prompt), observations,
                              fixture_client(alignments={"*": {"nope": []}}))
    assert result.refusals[0].code is AlignmentRefusalCode.MALFORMED


def test_an_unrecorded_alignment_is_a_refusal_and_never_a_computed_one():
    prompt, images, client = _scene("architecture")
    observations = observe_images(images, client)
    result = align_hypotheses(read_inquiry(prompt), observations, fixture_client({}))
    assert not result.alignments and result.refusals[0].code is AlignmentRefusalCode.MALFORMED


def test_an_alignment_records_which_model_related_the_two():
    prompt, images, client = _scene("architecture")
    observations = observe_images(images, client)
    result = align_hypotheses(read_inquiry(prompt), observations, client)
    assert result.alignments[0].provenance.model.identity is ExecutionIdentity.FIXTURE
    assert result.alignments[0].provenance.model.model == "architecture-scene"


def test_the_alignment_request_carries_observation_ids_and_not_a_way_to_add_one():
    prompt, images, client = _scene("architecture")
    observations = observe_images(images, client)
    payload = O.AlignmentRequest(read_inquiry(prompt), observations.observations).payload()
    assert {o["observation_id"] for o in payload["observations"]} == set(observations.ids)
    assert payload["relations"] == [r.value for r in AlignmentRelation]


# ── shape ────────────────────────────────────────────────────────────────────

def test_every_observer_contract_is_frozen():
    for name, obj in vars(O).items():
        if dataclasses.is_dataclass(obj) and isinstance(obj, type):
            assert obj.__dataclass_params__.frozen, f"{name} is not frozen"


def test_the_five_relations_are_five():
    assert len(AlignmentRelation) == 5
    assert O.GROUNDED_RELATIONS == {AlignmentRelation.SUPPORTS, AlignmentRelation.COMPLICATES,
                                    AlignmentRelation.CHALLENGES}
