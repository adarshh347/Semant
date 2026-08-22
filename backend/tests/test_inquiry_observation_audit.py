"""
INTELLIGENCE-002A — the observation audit, tested on a reply that lies seven ways at once.

WHAT MAKES THESE TESTS WORTH ANYTHING is the pair of them: the adversarial scene must light up,
and the three clean scenes must stay dark. An audit that fires on the adversarial fixture and also
on a well-behaved reading has detected nothing — it has a prior, and the prior is "guilty".

So every check below is tested twice: once for the finding, and once against the clean scenes,
where the standing assertion is that exactly ONE finding exists in all three of them and it is a
SUSPICION about a plant's leaves.
"""
from __future__ import annotations

import dataclasses
import inspect
import re

import pytest

from backend.services.epistemics import EpistemicStatus
from backend.services.inquiry_intelligence import observation_audit as A
from backend.services.inquiry_intelligence.intent import read_inquiry
from backend.services.inquiry_intelligence.observation_audit import (AuditCheck, AuditCode,
                                                                     Severity, audit)
from backend.services.inquiry_intelligence.observer import (AlignmentRelation, AlignmentSet,
                                                            HypothesisAlignment, ImageRef,
                                                            MeasurementEvidence, ModelIdentity,
                                                            ExecutionIdentity, ProviderKind,
                                                            ObservationProvenance,
                                                            VisualObservation, align_hypotheses,
                                                            fixture_client, observe_images)
from backend.tests.fixtures import inquiry_observation_fixtures as F

_IDENTITY = ModelIdentity(ExecutionIdentity.FIXTURE, ProviderKind.RECORDED, "committed", "test")


def _observation(**over):
    """A well-formed record, so that each test breaks exactly one thing."""
    base = dict(observation_id="obs_1", image_ref="img_1", feature="a rectangular block",
                locus="beneath the standing form", visible_organization="wider than the mass above",
                appearance_effect="reads as a support", interpretive_possibility="may be later",
                uncertainty="nothing joins the two in view",
                provenance=ObservationProvenance(_IDENTITY, "req_1"))
    base.update(over)
    return VisualObservation(**base)


def _adversarial():
    inquiry = read_inquiry(F.ADVERSARIAL_PROMPT)
    observations = observe_images(F.ADVERSARIAL_IMAGES, F.adversarial_client())
    return inquiry, observations


# ── the clean scenes stay dark ───────────────────────────────────────────────

@pytest.mark.parametrize("name,prompt,images,factory", F.CLEAN_SCENES)
def test_a_well_behaved_reading_produces_no_violation(name, prompt, images, factory):
    report = audit(observe_images(images, factory()), inquiry=read_inquiry(prompt))
    assert report.clean, [f.detail for f in report.violations]


def test_across_all_three_clean_scenes_there_is_exactly_one_finding():
    """And it is the plant's leaves. If this number moves, either the audit got noisier or a
    fixture got sloppier, and both are worth stopping for."""
    findings = []
    for _, prompt, images, factory in F.CLEAN_SCENES:
        findings.extend(audit(observe_images(images, factory()),
                              inquiry=read_inquiry(prompt)).findings)
    assert len(findings) == 1
    assert findings[0].severity is Severity.SUSPICION
    assert findings[0].code is AuditCode.PROMPT_VOCABULARY_IN_BLIND_OBSERVATION
    assert "leaves" in findings[0].evidence


# ── prompt vocabulary in a prompt-blind reading ──────────────────────────────

def test_the_persons_hypothesis_vocabulary_in_a_blind_reading_is_a_violation():
    inquiry, observations = _adversarial()
    report = audit(observations, inquiry=inquiry)
    leaks = report.by_code(AuditCode.PROMPT_VOCABULARY_IN_BLIND_OBSERVATION)
    words = {e for f in leaks if f.severity is Severity.VIOLATION for e in f.evidence}
    assert "drapery" in words and "weight" in words


def test_the_same_word_from_an_observable_question_is_a_suspicion_and_not_a_violation():
    """THE WHOLE SEVERITY SPLIT. The person asks about leaves; the observer says leaves, because
    that is what they are. Nothing leaked, and nothing about the WORD could tell you that."""
    prompt, images, factory = [s[1:] for s in F.CLEAN_SCENES if s[0] == "plant"][0]
    report = audit(observe_images(images, factory()), inquiry=read_inquiry(prompt))
    leaks = report.by_code(AuditCode.PROMPT_VOCABULARY_IN_BLIND_OBSERVATION)
    assert leaks and all(f.severity is Severity.SUSPICION for f in leaks)


def test_a_word_the_person_only_used_in_an_instruction_is_not_anybodys_theory():
    """"Look at these two images" — an observer saying "images" has leaked nothing."""
    inquiry = read_inquiry("Look at these two images. Describe the images.")
    report = audit([_observation(feature="images", visible_organization="two images")],
                   inquiry=inquiry)
    assert not report.by_code(AuditCode.PROMPT_VOCABULARY_IN_BLIND_OBSERVATION)


def test_leakage_is_caught_across_a_plural_or_a_participle():
    inquiry = read_inquiry("I think the folding is what carries it.")
    report = audit([_observation(visible_organization="a run of folds")], inquiry=inquiry)
    assert report.by_code(AuditCode.PROMPT_VOCABULARY_IN_BLIND_OBSERVATION)


def test_short_shared_words_are_noise_and_are_not_reported():
    """"top" is shared by the prompt and the reading and means nothing. Below four characters a
    coincidence is the likeliest explanation, and a report full of them is a report nobody reads."""
    inquiry = read_inquiry("I think the top is odd.")
    report = audit([_observation(locus="the top edge", interpretive_possibility="")],
                   inquiry=inquiry)
    assert not report.by_code(AuditCode.PROMPT_VOCABULARY_IN_BLIND_OBSERVATION)


def test_a_finding_names_the_field_the_leak_landed_in():
    inquiry = read_inquiry("I think the drapery carries it.")
    report = audit([_observation(appearance_effect="the drapery is doing the work")],
                   inquiry=inquiry)
    assert report.findings[0].field_name == "appearance_effect"


# ── speculation and history presented as description ─────────────────────────

def test_attributed_intent_in_the_field_read_as_what_the_picture_shows_is_a_violation():
    inquiry, observations = _adversarial()
    report = audit(observations, inquiry=inquiry)
    speculation = report.by_code(AuditCode.SPECULATION_AS_DESCRIPTION)
    assert any(f.field_name == "visible_organization" and f.severity is Severity.VIOLATION
               for f in speculation)


def test_a_dated_claim_in_a_description_is_a_violation():
    inquiry, observations = _adversarial()
    report = audit(observations, inquiry=inquiry)
    history = report.by_code(AuditCode.HISTORICAL_CLAIM_AS_DESCRIPTION)
    assert history and all(f.severity is Severity.VIOLATION for f in history)
    assert any("17th century" in e for f in history for e in f.evidence)


def test_the_same_sentence_is_perfectly_good_in_the_field_built_to_hold_it():
    """"It may have been added later" is not a forbidden sentence. It is a violation in
    `visible_organization` and correct content in `interpretive_possibility`, and the difference
    between those two facts is the only reason the fields are separate."""
    sentence = "originally it was probably intended to read as a later addition"
    bad = audit([_observation(visible_organization=sentence)])
    good = audit([_observation(interpretive_possibility=sentence)])
    assert bad.by_code(AuditCode.HISTORICAL_CLAIM_AS_DESCRIPTION)
    assert not good.by_code(AuditCode.HISTORICAL_CLAIM_AS_DESCRIPTION)
    assert not good.by_code(AuditCode.SPECULATION_AS_DESCRIPTION)


def test_uncertainty_may_hedge_because_hedging_is_what_it_is_for():
    assert audit([_observation(uncertainty="probably, though I may be wrong")]).clean


@pytest.mark.parametrize("text", ["the artist intended a plain support",
                                  "its maker chose a rough finish",
                                  "the designer wanted a break here"])
def test_attributed_agency_is_caught_by_grammar_and_not_by_a_list_of_makers(text):
    """Rule 5. The pattern is an article, a noun and a verb of intention — so it catches an
    artist, a maker and a designer without this codebase naming any of them."""
    report = audit([_observation(visible_organization=text)])
    assert report.by_code(AuditCode.SPECULATION_AS_DESCRIPTION)


def test_a_hedge_in_a_description_is_a_suspicion_rather_than_a_violation():
    report = audit([_observation(visible_organization="perhaps eight of them")])
    findings = report.by_code(AuditCode.SPECULATION_AS_DESCRIPTION)
    assert findings and findings[0].severity is Severity.SUSPICION


# ── measured status without evidence ─────────────────────────────────────────

def test_a_status_of_measured_with_nothing_measuring_is_a_violation():
    report = audit([_observation(epistemic_status=EpistemicStatus.MEASURED)])
    assert report.by_code(AuditCode.MEASURED_WITHOUT_EVIDENCE)
    assert not report.clean


def test_visible_is_also_a_grounded_status_and_also_needs_something_behind_it():
    """Rule 8. A model saying "there is a column" has not pointed at an extent."""
    report = audit([_observation(epistemic_status=EpistemicStatus.VISIBLE)])
    assert report.by_code(AuditCode.MEASURED_WITHOUT_EVIDENCE)


def test_agreement_named_as_the_instrument_is_caught_on_the_bypass_path_too():
    """Rule 9. The constructor refuses it; this is the record that got past the constructor —
    hand-built, or replaced — which is the path `epistemics.guard()` exists for as well."""
    evidence = MeasurementEvidence("mask_geometry", "count", 11.0, "channels", "artifact_9")
    object.__setattr__(evidence, "capability", "model_agreement")
    report = audit([_observation(
        epistemic_status=EpistemicStatus.MEASURED,
        provenance=ObservationProvenance(_IDENTITY, "req_1", evidence))])
    findings = report.by_code(AuditCode.MEASURED_WITHOUT_EVIDENCE)
    assert findings and "Agreement is a fact about models" in findings[0].detail


def test_the_models_own_claim_of_measurement_is_surfaced_even_though_it_was_refused():
    """The observer already recorded it interpretive. A model that keeps claiming measurement is
    still worth knowing about, so the claim is a SUSPICION rather than nothing at all."""
    inquiry, observations = _adversarial()
    report = audit(observations, inquiry=inquiry)
    claims = [f for f in report.by_code(AuditCode.MEASURED_WITHOUT_EVIDENCE)
              if f.severity is Severity.SUSPICION]
    assert claims and "measured" in claims[0].evidence


def test_a_real_measurement_is_not_flagged():
    report = audit([_observation(
        epistemic_status=EpistemicStatus.MEASURED,
        provenance=ObservationProvenance(
            _IDENTITY, "req_1",
            MeasurementEvidence("mask_geometry", "area", 210.0, "px", "artifact_9")))])
    assert not report.by_code(AuditCode.MEASURED_WITHOUT_EVIDENCE)


def test_knowledge_from_outside_the_image_in_a_prompt_blind_reading_is_a_violation():
    """Either the status is wrong or the blinding was, and both need somebody to look."""
    report = audit([_observation(epistemic_status=EpistemicStatus.SOURCED)])
    findings = report.by_code(AuditCode.MEASURED_WITHOUT_EVIDENCE)
    assert findings and "blinding" in findings[0].detail


# ── missing and hallucinated references ──────────────────────────────────────

def test_an_observation_with_no_image_behind_it_is_a_violation():
    """Unreachable through `observe_images`, which stamps the ref. Reachable by any record that
    arrived from somewhere else, which is why the check exists."""
    report = audit([_observation(image_ref="  ")])
    assert report.by_code(AuditCode.MISSING_IMAGE_REF)


def test_an_observation_naming_an_image_that_was_never_observed_is_a_violation():
    report = audit([_observation(image_ref="img_9")], declared_images=[ImageRef("img_1", "a.jpg")])
    assert report.by_code(AuditCode.HALLUCINATED_IMAGE_REF)


def test_a_model_attributing_a_reading_to_another_image_is_reported_even_though_it_lost():
    inquiry, observations = _adversarial()
    report = audit(observations, inquiry=inquiry)
    findings = report.by_code(AuditCode.HALLUCINATED_IMAGE_REF)
    assert findings and "adv_2" in findings[0].evidence


def test_an_observation_with_no_provenance_is_a_violation():
    report = audit([_observation(provenance=None)])
    findings = report.by_code(AuditCode.MISSING_SOURCE_REF)
    assert findings and findings[0].severity is Severity.VIOLATION


def test_provenance_with_no_request_id_is_a_suspicion():
    report = audit([_observation(provenance=ObservationProvenance(_IDENTITY, "  "))])
    findings = report.by_code(AuditCode.MISSING_SOURCE_REF)
    assert findings and findings[0].severity is Severity.SUSPICION


# ── duplication ──────────────────────────────────────────────────────────────

def test_the_same_noticing_filed_twice_is_a_violation():
    """Two records of one noticing read downstream as two independent noticings, which is how a
    single reading becomes its own corroboration."""
    inquiry, observations = _adversarial()
    report = audit(observations, inquiry=inquiry)
    findings = report.by_code(AuditCode.DUPLICATE_OBSERVATION)
    assert findings and "adv_obs_3" in findings[0].evidence


def test_two_observations_sharing_an_id_are_a_violation():
    report = audit([_observation(), _observation(feature="something else")])
    assert report.by_code(AuditCode.DUPLICATE_OBSERVATION_ID)


def test_two_readings_of_the_same_feature_on_different_images_are_not_duplicates():
    """The architecture scene names the same feature on both facades, honestly."""
    _, images, factory = [s[1:] for s in F.CLEAN_SCENES if s[0] == "architecture"][0]
    report = audit(observe_images(images, factory()))
    assert not report.by_code(AuditCode.DUPLICATE_OBSERVATION)


def test_two_empty_observations_are_not_reported_as_duplicates_of_each_other():
    report = audit([_observation(observation_id="a", feature="", locus="",
                                 visible_organization=""),
                    _observation(observation_id="b", feature="", locus="",
                                 visible_organization="")])
    assert not report.by_code(AuditCode.DUPLICATE_OBSERVATION)


# ── hallucinated ids in alignments ───────────────────────────────────────────

def test_an_alignment_citing_an_observation_nobody_produced_is_caught_here_too():
    """Deliberately redundant with `align_hypotheses`. This catches an `AlignmentSet` assembled
    some other way — by hand, or by a lane that has not read the aligner."""
    observations = observe_images(F.SCULPTURE_IMAGES, F.sculpture_client())
    handmade = AlignmentSet((HypothesisAlignment("a1", "hyp_1", AlignmentRelation.SUPPORTS,
                                                 ("sculpt_obs_1", "invented")),))
    report = audit(observations, alignments=handmade, inquiry=read_inquiry(F.SCULPTURE_PROMPT))
    findings = report.by_code(AuditCode.HALLUCINATED_OBSERVATION_ID)
    assert findings and "invented" in findings[0].evidence


def test_an_alignment_answering_a_claim_the_person_never_made_is_caught():
    observations = observe_images(F.SCULPTURE_IMAGES, F.sculpture_client())
    handmade = AlignmentSet((HypothesisAlignment("a1", "hyp_9", AlignmentRelation.SUPPORTS,
                                                 ("sculpt_obs_1",)),))
    report = audit(observations, alignments=handmade, inquiry=read_inquiry(F.SCULPTURE_PROMPT))
    assert report.by_code(AuditCode.HALLUCINATED_HYPOTHESIS_ID)


def test_a_real_alignment_set_passes_the_id_check():
    prompt, images, factory = [s[1:] for s in F.CLEAN_SCENES if s[0] == "architecture"][0]
    client = factory()
    inquiry, observations = read_inquiry(prompt), observe_images(images, client)
    alignments = align_hypotheses(inquiry, observations, client)
    report = audit(observations, alignments=alignments, inquiry=inquiry)
    assert AuditCheck.ID_INTEGRITY in report.checks_run
    assert report.clean


# ── the report does not overclaim ────────────────────────────────────────────

def test_clean_and_complete_are_two_different_claims():
    """A `clean` report that skipped its most important check must not read like one that passed
    it. One boolean covering both would let exactly that happen."""
    report = audit([_observation()])
    assert report.clean and not report.complete
    skipped = {c for c, _ in report.checks_skipped}
    assert AuditCheck.PROMPT_LEAKAGE in skipped


def test_a_skipped_check_says_why_in_a_sentence_a_person_can_act_on():
    report = audit([_observation()])
    reasons = dict(report.checks_skipped)
    assert "leakage" in reasons[AuditCheck.PROMPT_LEAKAGE]
    assert "no alignments" in reasons[AuditCheck.ID_INTEGRITY]


def test_with_everything_supplied_nothing_is_skipped():
    prompt, images, factory = [s[1:] for s in F.CLEAN_SCENES if s[0] == "architecture"][0]
    client = factory()
    inquiry, observations = read_inquiry(prompt), observe_images(images, client)
    report = audit(observations, alignments=align_hypotheses(inquiry, observations, client),
                   inquiry=inquiry)
    assert report.complete and report.clean


def test_a_bare_sequence_without_declared_images_says_the_ref_check_was_narrowed():
    """The check still runs — an empty ref is still caught — but it cannot tell a reference to an
    image nobody supplied from a valid one, and it says which half it did."""
    report = audit([_observation()])
    assert AuditCheck.IMAGE_REFS in report.checks_run
    assert any(c is AuditCheck.IMAGE_REFS for c, _ in report.checks_skipped)


def test_a_blind_set_brings_its_own_declared_images_so_the_check_runs_in_full():
    report = audit(observe_images(F.SCULPTURE_IMAGES, F.sculpture_client()))
    assert not any(c is AuditCheck.IMAGE_REFS for c, _ in report.checks_skipped)


def test_violations_come_first_so_the_first_line_of_a_report_is_the_worst_one():
    inquiry, observations = _adversarial()
    findings = audit(observations, inquiry=inquiry).findings
    severities = [f.severity is Severity.VIOLATION for f in findings]
    assert severities == sorted(severities, reverse=True)


def test_the_report_counts_what_it_read():
    inquiry, observations = _adversarial()
    report = audit(observations, inquiry=inquiry)
    assert report.observation_count == len(observations.observations)


# ── the auditor cannot become a way in ───────────────────────────────────────

def test_nothing_the_audit_returns_can_carry_an_observation():
    """The auditor is the one prompt-aware thing that touches blind readings. That is only safe
    because it reports and cannot amend: there is no path by which the prompt reaches an
    observation through here."""
    banned = re.compile(r"VisualObservation|BlindObservationSet", re.I)
    for cls in (A.AuditFinding, A.AuditReport):
        for f in dataclasses.fields(cls):
            assert not banned.search(str(f.type)), f"{cls.__name__}.{f.name}"


def test_the_audit_does_not_construct_or_replace_an_observation():
    """Over the source, with the docstrings stripped — the module talks about observations
    constantly and the claim is about what it CALLS, not what it says."""
    text = re.sub(r'"""(?:.|\n)*?"""', "", inspect.getsource(A))
    assert "VisualObservation(" not in text
    assert "dataclasses.replace" not in text
    assert "object.__setattr__" not in text


def test_every_audit_contract_is_frozen():
    for name, obj in vars(A).items():
        if dataclasses.is_dataclass(obj) and isinstance(obj, type):
            assert obj.__dataclass_params__.frozen, f"{name} is not frozen"


# ── rule 5: no topic in the tables ───────────────────────────────────────────

def test_the_marker_tables_name_no_rehearsal_topic():
    """Spine rule 5, checked over the executable tables rather than over the prose that explains
    them. What the audit matches is grammar — intention verbs, dating, hedges — and a table that
    started naming materials, periods or body parts would make this section work well on the
    rehearsals and nowhere else."""
    topics = ("fold", "drapery", "cloth", "sculpt", "statue", "architect", "facade", "column",
              "arch", "plant", "leaf", "leaves", "petal", "stem", "marble", "bronze", "gothic",
              "baroque", "renaissance", "classical", "medieval")
    tables = (A.INTENT_MARKERS, A.HISTORICAL_MARKERS, tuple(A._FIELD_POLICY.keys()),
              (A._AGENCY_INTENT.pattern, A._HISTORICAL_DATING.pattern))
    blob = " ".join(str(x) for table in tables for x in table).lower()
    for topic in topics:
        assert topic not in blob, f"{topic!r} is subject matter, in a table that decides findings"
