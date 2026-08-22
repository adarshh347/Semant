"""
INTELLIGENCE-002C — what the composer will and will not say.

The lane's claim is that useful image interpretation can be preserved without any of it being
presented as measurement. Everything here is a way that could be false.

The tests are grouped by the rule they defend, and most of them have a NEGATIVE CONTROL beside
them, because almost every assertion in this file is of the form "the composer did not do X" and
an assertion of that shape passes just as well when the composer does nothing at all.
"""
from __future__ import annotations

import json

import pytest

from backend.services.epistemics import IMAGE_STATUSES, EpistemicStatus
from backend.services.inquiry_intelligence.composer import (AGREEMENT_EVIDENCE_KINDS,
                                                            CEILING_BY_KIND, COMPOSER_PRODUCER,
                                                            MEASURING_EVIDENCE_KINDS,
                                                            NON_PROMOTING_EVIDENCE_KINDS,
                                                            NOTHING_NAMED, PREFIXES,
                                                            SECTION_EMPTINESS, SECTION_ORDER,
                                                            SECTION_TITLES, Attribution,
                                                            Composition, ComposerProvenance,
                                                            ComposerViolation, CompositionRequest,
                                                            Demotion, DemotionReason, Line,
                                                            LineKind, Origin, RefusalKind, Section,
                                                            SectionId, Standing,
                                                            assert_never_promoted, canonical,
                                                            compose, section_id)
from backend.tests.fixtures import intelligence_composer_fixtures as fixtures

BOTH = pytest.mark.parametrize("name", fixtures.FIXTURES)


def _kinds(composition: Composition):
    return {r.kind for r in composition.refusals}


def _lines(composition: Composition, section: SectionId):
    return composition.section(section).lines


def _minimal(**overrides) -> CompositionRequest:
    """A request with one image and whatever the test needs, and nothing else."""
    payload = {"inquiry_id": "inq_t", "prompt": "a question",
               "inquiry_map": {"images": [{"image_id": "im"}], "hypotheses": []}}
    payload.update(overrides)
    return CompositionRequest(**payload)


def _observation(oid="o", status="interpretive", evidence=(), text="a sentence about the picture"):
    return {"observation_id": oid, "image_id": "im", "statement": text,
            "declared_status": status, "evidence_ids": list(evidence), "producer": "observer"}


# ── the shape of the output ──────────────────────────────────────────────────

@BOTH
def test_every_section_is_present_in_the_declared_order(name):
    composition = fixtures.compose_fixture(name)
    assert tuple(s.section for s in composition.sections) == SECTION_ORDER


def test_an_empty_inquiry_still_produces_all_six_sections_each_saying_why_it_is_empty():
    """An absent section and an empty one say different things. A composer that dropped the
    empties would make 'nothing was proposed' and 'the proposals were never read' one string."""
    composition = compose(CompositionRequest(inquiry_id="inq_e", prompt="nothing yet"))
    assert tuple(s.section for s in composition.sections) == SECTION_ORDER
    for section in composition.sections:
        if section.section is SectionId.PROPOSED:
            continue                       # the prompt itself is always a line
        assert section.lines == ()
        assert section.to_dict()["emptiness"] == SECTION_EMPTINESS[section.section]


@BOTH
def test_a_section_that_has_lines_states_no_emptiness(name):
    for section in fixtures.compose_fixture(name).sections:
        if section.lines:
            assert section.to_dict()["emptiness"] == ""


@BOTH
def test_the_titles_come_from_the_table_and_nowhere_else(name):
    for section in fixtures.compose_fixture(name).sections:
        assert section.title == SECTION_TITLES[section.section]
        assert section.section_uid == section_id(fixtures.load(name)["inquiry_id"],
                                                 section.section)


@BOTH
def test_the_prompt_is_the_first_line_of_section_one_byte_for_byte(name):
    sample = fixtures.load(name)
    first = _lines(fixtures.compose_fixture(name), SectionId.PROPOSED)[0]
    assert first.text == sample["prompt"]
    assert first.kind is LineKind.PROPOSAL
    assert first.attribution.producer == "inquirer"


def test_the_prompt_line_survives_a_map_that_extracted_no_hypothesis():
    composition = compose(_minimal(prompt="only this"))
    assert [l.text for l in _lines(composition, SectionId.PROPOSED)] == ["only this"]


# ── a user hypothesis is not an image observation ────────────────────────────

@BOTH
def test_no_proposal_ever_carries_an_image_status(name):
    for line in _lines(fixtures.compose_fixture(name), SectionId.PROPOSED):
        assert line.status is EpistemicStatus.SOURCED
        assert line.status not in IMAGE_STATUSES
        assert line.origin is Origin.USER


@BOTH
def test_a_hypothesis_that_claimed_the_picture_shows_it_records_the_demotion(name):
    """Both samples open with a hypothesis declaring an image status, because that is what a user
    hypothesis actually looks like coming out of an extractor that was not careful."""
    demoted = [l for l in _lines(fixtures.compose_fixture(name), SectionId.PROPOSED)
               if l.declared_status in IMAGE_STATUSES]
    assert demoted, "the sample no longer exercises the wall"
    for line in demoted:
        assert line.status is EpistemicStatus.SOURCED
        assert [d.reason for d in line.demotions] == [DemotionReason.NOT_FROM_THE_IMAGE]


def test_an_alignment_that_supports_a_hypothesis_leaves_the_hypothesis_exactly_as_it_was():
    """The negative control for the wall in the direction nothing else tests: evidence about the
    picture must not travel back up the alignment and improve the sentence the inquirer wrote."""
    with_alignments = fixtures.compose_fixture("moorings")
    without = fixtures.compose_fixture("moorings", alignments=[])
    assert ([l.to_dict() for l in _lines(with_alignments, SectionId.PROPOSED)]
            == [l.to_dict() for l in _lines(without, SectionId.PROPOSED)])
    assert _lines(with_alignments, SectionId.SUGGESTED) != _lines(without, SectionId.SUGGESTED)


@BOTH
def test_an_alignment_that_contradicts_is_composed_and_not_quietly_dropped(name):
    stances = [l.stance for l in _lines(fixtures.compose_fixture(name), SectionId.SUGGESTED)
               if l.kind is LineKind.ALIGNMENT]
    assert "contradicts" in stances


@BOTH
def test_an_alignment_is_capped_at_interpretive_however_it_was_declared(name):
    for line in _lines(fixtures.compose_fixture(name), SectionId.SUGGESTED):
        if line.kind is LineKind.ALIGNMENT:
            assert line.status is EpistemicStatus.INTERPRETIVE


def test_an_alignment_against_a_hypothesis_nobody_proposed_is_refused_and_dropped():
    composition = fixtures.compose_fixture("moorings")
    assert RefusalKind.DANGLING_HYPOTHESIS in _kinds(composition)
    texts = [l.text for l in _lines(composition, SectionId.SUGGESTED)]
    assert fixtures.load("moorings")["alignments"][2]["statement"] not in texts


def test_that_refusal_goes_away_when_the_hypothesis_is_there():
    """The negative control. A refusal that fires whatever the input is, is reading nothing."""
    sample = fixtures.load("moorings")
    imap = json.loads(json.dumps(sample["inquiry_map"]))
    imap["hypotheses"].append({"hypothesis_id": "h_weather", "statement": "a blow was forecast"})
    composition = fixtures.compose_fixture("moorings", inquiry_map=imap)
    assert RefusalKind.DANGLING_HYPOTHESIS not in _kinds(composition)


@BOTH
def test_section_five_never_restates_a_proposal(name):
    """`sourced` never was interpretive. Calling a proposal a residue would put the inquirer's own
    sentence on the image scale by the back door."""
    composition = fixtures.compose_fixture(name)
    proposals = {l.line_id for l in _lines(composition, SectionId.PROPOSED)}
    for line in _lines(composition, SectionId.INTERPRETIVE):
        assert line.restates not in proposals


# ── a reading is interpretive until a capability measured it ─────────────────

def test_a_measurement_from_a_live_capability_reaches_measured():
    composition = compose(_minimal(
        observations=[_observation(status="measured", evidence=["e"])],
        evidence=[{"evidence_id": "e", "kind": "measurement", "capability": "width"}],
        capabilities={"width": True}))
    line = _lines(composition, SectionId.SUGGESTED)[0]
    assert line.status is EpistemicStatus.MEASURED
    assert line.attribution.measured_by == ("width",)
    assert line.is_backed


def test_an_extent_from_a_live_capability_reaches_visible():
    composition = compose(_minimal(
        observations=[_observation(status="visible", evidence=["e"])],
        evidence=[{"evidence_id": "e", "kind": "extent", "capability": "segmenter"}],
        capabilities={"segmenter": True}))
    assert _lines(composition, SectionId.SUGGESTED)[0].status is EpistemicStatus.VISIBLE


def test_the_same_sentence_with_a_reading_behind_it_settles_interpretive():
    """The one that matters. Identical claim, identical confidence, different evidence kind."""
    composition = compose(_minimal(
        observations=[_observation(status="measured", evidence=["e"])],
        evidence=[{"evidence_id": "e", "kind": "reading", "capability": "observer"}],
        capabilities={"observer": True}))
    line = _lines(composition, SectionId.SUGGESTED)[0]
    assert line.status is EpistemicStatus.INTERPRETIVE
    assert line.attribution.measured_by == ()
    assert line.attribution.discounted_evidence == ("e",)
    assert line.demotions[-1].reason is DemotionReason.A_READING_IS_NOT_A_MEASUREMENT


def test_a_claim_with_no_evidence_at_all_settles_interpretive():
    composition = compose(_minimal(observations=[_observation(status="measured")]))
    line = _lines(composition, SectionId.SUGGESTED)[0]
    assert line.status is EpistemicStatus.INTERPRETIVE
    assert line.demotions[-1].reason is DemotionReason.NO_MEASURING_CAPABILITY


def test_a_producer_that_declared_less_than_its_evidence_supports_keeps_its_own_word():
    """A composer may weaken a producer's claim and never strengthen it — not even when the
    evidence would have carried the stronger one."""
    composition = compose(_minimal(
        observations=[_observation(status="interpretive", evidence=["e"])],
        evidence=[{"evidence_id": "e", "kind": "measurement", "capability": "width"}],
        capabilities={"width": True}))
    line = _lines(composition, SectionId.SUGGESTED)[0]
    assert line.status is EpistemicStatus.INTERPRETIVE
    assert line.attribution.measured_by == ("width",)   # the measurement is still on the record
    assert not line.is_backed


@pytest.mark.parametrize("kind", sorted(MEASURING_EVIDENCE_KINDS))
def test_each_measuring_evidence_kind_grants_exactly_what_the_table_says(kind):
    composition = compose(_minimal(
        observations=[_observation(status="visible", evidence=["e"])],
        evidence=[{"evidence_id": "e", "kind": kind, "capability": "cap"}],
        capabilities={"cap": True}))
    assert _lines(composition, SectionId.SUGGESTED)[0].status is MEASURING_EVIDENCE_KINDS[kind]


@pytest.mark.parametrize("kind", NON_PROMOTING_EVIDENCE_KINDS)
def test_no_non_promoting_evidence_kind_lifts_anything(kind):
    composition = compose(_minimal(
        observations=[_observation(status="measured", evidence=["e"])],
        evidence=[{"evidence_id": "e", "kind": kind, "capability": "cap"}],
        capabilities={"cap": True}))
    line = _lines(composition, SectionId.SUGGESTED)[0]
    assert line.status is EpistemicStatus.INTERPRETIVE
    assert line.attribution.measured_by == ()


def test_an_evidence_kind_nobody_has_heard_of_grants_nothing():
    """Default-deny. A table that admitted unknown kinds would promote everything the first time a
    producer invented one."""
    composition = compose(_minimal(
        observations=[_observation(status="measured", evidence=["e"])],
        evidence=[{"evidence_id": "e", "kind": "vibe", "capability": "cap"}],
        capabilities={"cap": True}))
    assert _lines(composition, SectionId.SUGGESTED)[0].status is EpistemicStatus.INTERPRETIVE


# ── nothing becomes measured through agreement ───────────────────────────────

@pytest.mark.parametrize("kind", AGREEMENT_EVIDENCE_KINDS)
def test_every_named_appeal_to_concurrence_is_refused_under_a_claim_of_measurement(kind):
    composition = compose(_minimal(
        observations=[_observation(status="measured", evidence=["e"])],
        evidence=[{"evidence_id": "e", "kind": kind, "capability": "panel"}],
        capabilities={"panel": True}))
    assert RefusalKind.AGREEMENT_OFFERED_AS_MEASUREMENT in _kinds(composition)
    line = _lines(composition, SectionId.SUGGESTED)[0]
    assert line.status is EpistemicStatus.INTERPRETIVE
    assert line.demotions[-1].reason is DemotionReason.AGREEMENT_IS_NOT_MEASUREMENT


@pytest.mark.parametrize("how_many", [1, 2, 3, 5, 12, 25])
def test_any_number_of_observers_saying_the_same_thing_produces_that_many_readings_and_no_finding(
        how_many):
    """The sequence this module exists to make unsayable: six sentences under a heading becoming a
    finding, and a seventh saying 'they all agree' becoming a fact."""
    composition = compose(_minimal(
        observations=[_observation(oid="o{}".format(i), status="measured",
                                   text="the same sentence, from observer {}".format(i))
                      for i in range(how_many)]))
    lines = _lines(composition, SectionId.SUGGESTED)
    assert len(lines) == how_many
    assert {l.status for l in lines} == {EpistemicStatus.INTERPRETIVE}
    assert composition.backed() == ()


def test_ten_copies_of_one_concurrence_are_worth_no_more_than_one():
    composition = compose(_minimal(
        observations=[_observation(status="measured",
                                   evidence=["e{}".format(i) for i in range(10)])],
        evidence=[{"evidence_id": "e{}".format(i), "kind": "agreement", "capability": "panel"}
                  for i in range(10)],
        capabilities={"panel": True}))
    line = _lines(composition, SectionId.SUGGESTED)[0]
    assert line.status is EpistemicStatus.INTERPRETIVE
    assert len(line.attribution.discounted_evidence) == 10
    assert line.attribution.measured_by == ()


def test_concurrence_beside_a_real_measurement_does_not_subtract_from_it_either():
    composition = compose(_minimal(
        observations=[_observation(status="measured", evidence=["e_vote", "e_real"])],
        evidence=[{"evidence_id": "e_vote", "kind": "agreement", "capability": "panel"},
                  {"evidence_id": "e_real", "kind": "measurement", "capability": "width"}],
        capabilities={"panel": True, "width": True}))
    line = _lines(composition, SectionId.SUGGESTED)[0]
    assert line.status is EpistemicStatus.MEASURED
    assert line.attribution.measured_by == ("width",)
    assert line.attribution.discounted_evidence == ("e_vote",)


# ── a capability that does not exist measured nothing ────────────────────────

def test_evidence_resting_on_a_declared_gap_is_discounted_and_refused():
    composition = compose(_minimal(
        observations=[_observation(status="measured", evidence=["e"])],
        evidence=[{"evidence_id": "e", "kind": "measurement", "capability": "surface_age"}],
        capability_gaps=[{"gap_id": "g", "capability": "surface_age"}]))
    line = _lines(composition, SectionId.SUGGESTED)[0]
    assert line.status is EpistemicStatus.INTERPRETIVE
    assert line.demotions[-1].reason is DemotionReason.CAPABILITY_IS_A_GAP
    assert RefusalKind.EVIDENCE_FROM_ABSENT_CAPABILITY in _kinds(composition)


def test_the_same_evidence_with_the_gap_removed_is_admitted():
    """The negative control for the one above: the refusal reads the gap list, not the word."""
    composition = compose(_minimal(
        observations=[_observation(status="measured", evidence=["e"])],
        evidence=[{"evidence_id": "e", "kind": "measurement", "capability": "surface_age"}]))
    assert _lines(composition, SectionId.SUGGESTED)[0].status is EpistemicStatus.MEASURED


def test_evidence_resting_on_a_capability_the_matrix_reports_down_is_discounted_and_refused():
    composition = compose(_minimal(
        observations=[_observation(status="measured", evidence=["e"])],
        evidence=[{"evidence_id": "e", "kind": "measurement", "capability": "depth"}],
        capabilities={"depth": False}))
    line = _lines(composition, SectionId.SUGGESTED)[0]
    assert line.demotions[-1].reason is DemotionReason.CAPABILITY_IS_DOWN
    assert RefusalKind.EVIDENCE_FROM_ABSENT_CAPABILITY in _kinds(composition)


def test_a_matrix_that_omits_a_capability_treats_it_as_down():
    composition = compose(_minimal(
        observations=[_observation(status="measured", evidence=["e"])],
        evidence=[{"evidence_id": "e", "kind": "measurement", "capability": "depth"}],
        capabilities={"width": True}))
    assert _lines(composition, SectionId.SUGGESTED)[0].status is EpistemicStatus.INTERPRETIVE


def test_no_matrix_at_all_does_not_mean_every_capability_is_down():
    """An unreported matrix would otherwise discount every real measurement in the system the
    first time a caller forgot to pass one. `proofs` runs this branch end to end."""
    assert fixtures.load("proofs")["capabilities"] == {}
    backed = fixtures.compose_fixture("proofs").backed()
    assert backed and {l.status for l in backed} == {EpistemicStatus.MEASURED}


def test_a_measurement_that_names_no_capability_is_refused():
    composition = compose(_minimal(
        observations=[_observation(status="measured", evidence=["e"])],
        evidence=[{"evidence_id": "e", "kind": "measurement"}]))
    assert RefusalKind.EVIDENCE_FROM_ABSENT_CAPABILITY in _kinds(composition)
    assert _lines(composition, SectionId.SUGGESTED)[0].status is EpistemicStatus.INTERPRETIVE


def test_cited_evidence_that_does_not_exist_is_refused_rather_than_ignored():
    composition = compose(_minimal(observations=[_observation(evidence=["e_nowhere"])]))
    assert RefusalKind.DANGLING_EVIDENCE in _kinds(composition)


# ── the wall, and the invariant that guards it ───────────────────────────────

def test_a_claim_from_outside_the_image_filed_as_an_observation_keeps_its_status_and_is_refused():
    composition = compose(_minimal(observations=[_observation(status="sourced")]))
    line = _lines(composition, SectionId.SUGGESTED)[0]
    assert line.status is EpistemicStatus.SOURCED
    assert line.attribution.measured_by == ()
    assert RefusalKind.SOURCED_CLAIM_ABOUT_THE_IMAGE in _kinds(composition)


def test_it_cannot_be_lifted_off_the_wall_by_evidence_either():
    composition = compose(_minimal(
        observations=[_observation(status="sourced", evidence=["e"])],
        evidence=[{"evidence_id": "e", "kind": "measurement", "capability": "width"}],
        capabilities={"width": True}))
    assert _lines(composition, SectionId.SUGGESTED)[0].status is EpistemicStatus.SOURCED


@BOTH
def test_no_recorded_demotion_anywhere_is_a_promotion(name):
    assert_never_promoted(fixtures.compose_fixture(name))     # raises if it is


@BOTH
def test_no_line_settles_stronger_than_it_was_declared(name):
    for line in fixtures.compose_fixture(name).lines():
        if line.declared_status is None or line.status is EpistemicStatus.SOURCED:
            continue
        assert line.status is not EpistemicStatus.VISIBLE or line.declared_status is \
            EpistemicStatus.VISIBLE


def test_the_invariant_can_actually_fail():
    """The negative control for `assert_never_promoted`. A guard that never fires is
    indistinguishable from a guard pointed at nothing."""
    line = Line(line_id="iln_x", kind=LineKind.OBSERVATION, text="t",
                status=EpistemicStatus.MEASURED, origin=Origin.IMAGE, attribution=Attribution(),
                declared_status=EpistemicStatus.INTERPRETIVE)
    bad = Composition(composition_uid="icm_x", inquiry_id="i", prompt="p", sections=(
        Section(section=SectionId.SUGGESTED, section_uid="isc_x", title="t", lines=(line,)),))
    with pytest.raises(ComposerViolation):
        assert_never_promoted(bad)


def test_a_demotion_recorded_backwards_also_fails():
    line = Line(line_id="iln_y", kind=LineKind.OBSERVATION, text="t",
                status=EpistemicStatus.INTERPRETIVE, origin=Origin.IMAGE,
                attribution=Attribution(),
                demotions=(Demotion(EpistemicStatus.INTERPRETIVE, EpistemicStatus.MEASURED,
                                    DemotionReason.NO_MEASURING_CAPABILITY),))
    bad = Composition(composition_uid="icm_y", inquiry_id="i", prompt="p", sections=(
        Section(section=SectionId.SUGGESTED, section_uid="isc_y", title="t", lines=(line,)),))
    with pytest.raises(ComposerViolation):
        assert_never_promoted(bad)


@BOTH
def test_the_kind_ceilings_hold_for_every_line(name):
    for line in fixtures.compose_fixture(name).lines():
        ceiling = CEILING_BY_KIND[line.kind]
        if line.status is EpistemicStatus.SOURCED or ceiling is EpistemicStatus.SOURCED:
            continue
        assert line.status in IMAGE_STATUSES
        order = [EpistemicStatus.VISIBLE, EpistemicStatus.MEASURED,
                 EpistemicStatus.INTERPRETIVE, EpistemicStatus.UNCERTAIN]
        assert order.index(line.status) >= order.index(ceiling)


# ── section 4: four fates, and the third is not a soft second ────────────────

def test_all_four_standings_are_exercised_by_the_samples():
    seen = set()
    for name in fixtures.FIXTURES:
        seen |= {l.standing for l in _lines(fixtures.compose_fixture(name), SectionId.SURVIVED)}
    assert seen == {s.value for s in Standing}


@BOTH
def test_survivors_are_only_the_ones_a_critique_upheld(name):
    composition = fixtures.compose_fixture(name)
    assert composition.survivors()
    assert all(l.standing == Standing.SUSTAINED.value for l in composition.survivors())
    assert len(composition.survivors()) < len(_lines(composition, SectionId.SURVIVED))


@BOTH
def test_a_relation_nobody_critiqued_is_not_a_survivor_and_is_capped_at_interpretive(name):
    uncritiqued = [l for l in _lines(fixtures.compose_fixture(name), SectionId.SURVIVED)
                   if l.standing == Standing.UNCRITIQUED.value]
    assert uncritiqued
    for line in uncritiqued:
        assert line not in fixtures.compose_fixture(name).survivors()
        assert line.status is EpistemicStatus.INTERPRETIVE
        assert any(d.reason is DemotionReason.NOTHING_CRITIQUED_IT for d in line.demotions)


def test_a_relation_its_own_critique_would_not_vouch_for_is_refused_and_settles_uncertain():
    line = [l for l in _lines(fixtures.compose_fixture("moorings"), SectionId.SURVIVED)
            if l.standing == Standing.WITHHELD.value][0]
    assert line.status is EpistemicStatus.UNCERTAIN
    assert line.attribution.measured_by == ("slack_geometry",)   # the measurement is still named
    assert RefusalKind.CONTRADICTED_ACCEPTANCE in _kinds(fixtures.compose_fixture("moorings"))


def test_a_refuted_relation_is_refused_and_settles_uncertain():
    line = [l for l in _lines(fixtures.compose_fixture("proofs"), SectionId.SURVIVED)
            if l.standing == Standing.REFUTED.value][0]
    assert line.status is EpistemicStatus.UNCERTAIN
    assert RefusalKind.CONTRADICTED_ACCEPTANCE in _kinds(fixtures.compose_fixture("proofs"))


def test_changing_that_critique_to_a_sustaining_one_removes_the_refusal():
    """The negative control: the contradiction is read off the verdict, not off the relation."""
    sample = fixtures.load("proofs")
    critiques = json.loads(json.dumps(sample["critiques"]))
    critiques[1]["verdict"] = "sustained"
    composition = fixtures.compose_fixture("proofs", critiques=critiques)
    assert RefusalKind.CONTRADICTED_ACCEPTANCE not in _kinds(composition)
    assert len(composition.survivors()) == 2


@BOTH
def test_a_rejected_relation_is_shown_rather_than_dropped(name):
    rejected = [l for l in _lines(fixtures.compose_fixture(name), SectionId.SURVIVED)
                if l.standing == Standing.REJECTED.value]
    assert rejected
    for line in rejected:
        assert line.status is EpistemicStatus.UNCERTAIN
        assert any(d.reason is DemotionReason.IT_WAS_NOT_ACCEPTED for d in line.demotions)


def test_an_unreadable_verdict_withholds_rather_than_sustains():
    composition = compose(_minimal(
        accepted_relations=[{"relation_id": "r", "statement": "a claim",
                             "declared_status": "interpretive"}],
        critiques=[{"critique_id": "c", "relation_id": "r", "verdict": "hmm"}]))
    line = _lines(composition, SectionId.SURVIVED)[0]
    assert line.standing == Standing.WITHHELD.value
    assert composition.survivors() == ()


def test_a_relation_accepted_and_rejected_at_once_is_refused_and_treated_as_rejected():
    relation = {"relation_id": "r", "statement": "a claim", "declared_status": "interpretive"}
    composition = compose(_minimal(accepted_relations=[relation], rejected_relations=[relation]))
    assert RefusalKind.DUPLICATE_ID in _kinds(composition)
    assert [l.standing for l in _lines(composition, SectionId.SURVIVED)] == \
        [Standing.REJECTED.value]


def test_a_critique_of_a_relation_nobody_proposed_is_refused():
    composition = fixtures.compose_fixture("moorings")
    assert RefusalKind.DANGLING_RELATION in _kinds(composition)
    assert RefusalKind.DANGLING_RELATION not in _kinds(fixtures.compose_fixture("proofs"))


# ── section 3: what is dropped and what is kept ──────────────────────────────

@BOTH
def test_a_choice_is_never_a_finding(name):
    for line in _lines(fixtures.compose_fixture(name), SectionId.COMPARED):
        assert line.status is EpistemicStatus.INTERPRETIVE
        assert line.origin is Origin.SYSTEM


def test_a_plan_declaring_a_measurement_is_demoted_for_being_a_choice():
    line = [l for l in _lines(fixtures.compose_fixture("moorings"), SectionId.COMPARED)
            if l.declared_status is EpistemicStatus.MEASURED][0]
    assert any(d.reason is DemotionReason.A_CHOICE_IS_NOT_A_FINDING for d in line.demotions)


def test_a_plan_with_one_broken_citation_survives_with_the_citation_stripped():
    """The rule everywhere here: an item is dropped when it cannot be stated without inventing
    something, and kept beside a refusal when it can. The choice was made; the citation broke."""
    composition = fixtures.compose_fixture("moorings")
    plan = fixtures.load("moorings")["contrast_plans"][1]
    line = [l for l in _lines(composition, SectionId.COMPARED) if l.text == plan["statement"]][0]
    assert "o_never" not in line.attribution.source_ids
    assert "o_n2" in line.attribution.source_ids
    assert RefusalKind.DANGLING_OBSERVATION in _kinds(composition)


def test_an_observation_anchored_to_no_image_is_refused_and_dropped():
    """It cannot be stated: a reading of nothing in particular has no picture to attribute it to."""
    composition = fixtures.compose_fixture("moorings")
    assert RefusalKind.UNANCHORED_OBSERVATION in _kinds(composition)
    loose = fixtures.load("moorings")["observations"][-1]["statement"]
    assert loose not in [l.text for l in composition.lines()]


def test_an_observation_that_declared_nothing_is_refused_and_kept_at_uncertain():
    composition = fixtures.compose_fixture("moorings")
    assert RefusalKind.UNDECLARED_STATUS in _kinds(composition)
    line = [l for l in _lines(composition, SectionId.SUGGESTED) if l.declared_status is None][0]
    assert line.status is EpistemicStatus.UNCERTAIN


@BOTH
def test_a_sixth_kind_of_knowing_is_refused_once_and_not_twice(name):
    composition = fixtures.compose_fixture(name)
    assert RefusalKind.UNKNOWN_STATUS in _kinds(composition)
    unknown = [r for r in composition.refusals if r.kind is RefusalKind.UNKNOWN_STATUS]
    undeclared = [r for r in composition.refusals if r.kind is RefusalKind.UNDECLARED_STATUS]
    assert not {r.subject_id for r in unknown} & {r.subject_id for r in undeclared}


# ── section 5: derived, never authored ───────────────────────────────────────

@BOTH
def test_every_unbacked_line_above_has_exactly_one_residue_and_every_backed_line_has_none(name):
    composition = fixtures.compose_fixture(name)
    upstream = [l for s in (SectionId.SUGGESTED, SectionId.COMPARED, SectionId.SURVIVED)
                for l in _lines(composition, s)]
    restated = [l.restates for l in _lines(composition, SectionId.INTERPRETIVE)]
    assert len(restated) == len(set(restated))
    assert set(restated) == {l.line_id for l in upstream if not l.is_backed}
    assert not set(restated) & {l.line_id for l in upstream if l.is_backed}


@BOTH
def test_a_residue_repeats_its_original_byte_for_byte_and_keeps_its_origin_and_status(name):
    composition = fixtures.compose_fixture(name)
    for residue in _lines(composition, SectionId.INTERPRETIVE):
        original = composition.line(residue.restates)
        assert original is not None
        assert residue.text == original.text
        assert residue.status is original.status
        assert residue.origin is original.origin
        assert residue.declared_status is original.declared_status
        assert residue.attribution == original.attribution


@BOTH
def test_a_residue_explains_itself_only_in_the_closed_vocabulary(name):
    """A composer writing its own prose about why a claim is weak would be the one unattributed
    voice in the output."""
    allowed = {r.value for r in DemotionReason}
    for residue in _lines(fixtures.compose_fixture(name), SectionId.INTERPRETIVE):
        assert residue.because in allowed


def test_backing_a_line_removes_its_residue():
    """The negative control for the whole section: it is derived, so it moves when the inputs do."""
    without = compose(_minimal(observations=[_observation(status="measured")]))
    assert len(_lines(without, SectionId.INTERPRETIVE)) == 1
    with_evidence = compose(_minimal(
        observations=[_observation(status="measured", evidence=["e"])],
        evidence=[{"evidence_id": "e", "kind": "measurement", "capability": "width"}],
        capabilities={"width": True}))
    assert _lines(with_evidence, SectionId.INTERPRETIVE) == ()


# ── section 6: what would have to exist ──────────────────────────────────────

def test_a_capability_that_exists_and_was_not_used_is_marked_present():
    line = [l for l in _lines(fixtures.compose_fixture("moorings"), SectionId.MEASURABLE)
            if l.standing == "present"]
    assert line and line[0].subjects == ("extent_measure",)
    assert line[0].blocks


def test_a_capability_the_gap_list_names_is_marked_absent():
    standings = {l.standing for l in _lines(fixtures.compose_fixture("moorings"),
                                            SectionId.MEASURABLE)}
    assert "absent" in standings


def test_with_no_matrix_an_ungapped_capability_is_undeclared_rather_than_guessed_either_way():
    line = [l for l in _lines(fixtures.compose_fixture("proofs"), SectionId.MEASURABLE)
            if l.standing == "undeclared"]
    assert line and line[0].subjects == ("seam_locator",)


@BOTH
def test_a_gap_nothing_in_this_inquiry_needed_is_still_named_with_no_blocks(name):
    orphan = [l for l in _lines(fixtures.compose_fixture(name), SectionId.MEASURABLE)
              if not l.blocks and l.subjects]
    assert len(orphan) == 1


@BOTH
def test_the_residues_nothing_names_a_capability_for_are_collected_and_said_so(name):
    composition = fixtures.compose_fixture(name)
    stranded = [l for l in _lines(composition, SectionId.MEASURABLE) if l.standing == "unnamed"]
    assert len(stranded) == 1
    assert stranded[0].text == NOTHING_NAMED
    assert stranded[0].subjects == ()
    named = {b for l in _lines(composition, SectionId.MEASURABLE) if l.standing != "unnamed"
             for b in l.blocks}
    assert not set(stranded[0].blocks) & named


@BOTH
def test_the_composer_never_invents_a_capability_name(name):
    """The failure this lane exists to prevent, arriving one level up: a plausible-sounding
    capability composed into the answer because none was supplied."""
    sample = fixtures.load(name)
    declared = {c for g in sample["capability_gaps"] for c in [g["capability"]]}
    declared |= {c for o in sample["observables"] for c in o["capability_classes"]}
    declared |= set(sample["capabilities"])
    for line in _lines(fixtures.compose_fixture(name), SectionId.MEASURABLE):
        for capability in line.subjects:
            assert capability in declared


@BOTH
def test_every_block_a_gap_names_is_a_line_that_exists(name):
    composition = fixtures.compose_fixture(name)
    residues = {l.line_id for l in _lines(composition, SectionId.INTERPRETIVE)}
    for line in _lines(composition, SectionId.MEASURABLE):
        assert set(line.blocks) <= residues


# ── refusals ─────────────────────────────────────────────────────────────────

def test_the_two_samples_do_not_produce_the_same_refusals():
    """If the refusals were remembered rather than derived, the twin would report the twin's."""
    a = _kinds(fixtures.compose_fixture("moorings"))
    b = _kinds(fixtures.compose_fixture("proofs"))
    assert a != b and b < a and len(a) == 9 and len(b) == 4


@BOTH
def test_a_refusal_is_recorded_once_however_many_times_its_cause_is_cited(name):
    composition = fixtures.compose_fixture(name)
    assert len({r.refusal_uid for r in composition.refusals}) == len(composition.refusals)


@BOTH
def test_every_refusal_names_something(name):
    for refusal in fixtures.compose_fixture(name).refusals:
        assert refusal.subject_id and refusal.detail


# ── the composer speaks in nobody else's voice ───────────────────────────────

@BOTH
def test_every_line_repeats_a_sentence_that_arrived_or_the_one_sentence_the_composer_authors(name):
    """Rule 10's spirit at the sentence level. A composer that paraphrased its inputs would be a
    producer with no provenance of its own, and the paraphrase is where a hedge goes missing."""
    raw = json.dumps(fixtures.load(name))
    authored = {NOTHING_NAMED}
    for line in fixtures.compose_fixture(name).lines():
        if line.text in authored:
            continue
        assert json.dumps(line.text)[1:-1] in raw, line.text


@BOTH
def test_the_composer_authors_exactly_one_sentence(name):
    texts = [l.text for l in fixtures.compose_fixture(name).lines()]
    raw = json.dumps(fixtures.load(name))
    authored = {t for t in texts if json.dumps(t)[1:-1] not in raw}
    assert authored == {NOTHING_NAMED}


@BOTH
def test_a_gap_with_no_prose_of_its_own_still_says_something_traceable(name):
    composition = compose(fixtures.request_for(
        name, capability_gaps=[{"gap_id": "g", "capability": "cap", "needed_for": []}]))
    orphan = [l for l in _lines(composition, SectionId.MEASURABLE) if l.subjects == ("cap",)][0]
    assert "cap" in orphan.text


# ── ids, determinism, serialisation ──────────────────────────────────────────

@BOTH
def test_every_line_id_in_a_composition_is_unique(name):
    lines = fixtures.compose_fixture(name).lines()
    assert len({l.line_id for l in lines}) == len(lines)


@BOTH
def test_ids_carry_the_prefix_for_their_kind(name):
    composition = fixtures.compose_fixture(name)
    assert composition.composition_uid.startswith(PREFIXES["composition"])
    for section in composition.sections:
        assert section.section_uid.startswith(PREFIXES["section"])
        for line in section.lines:
            assert line.line_id.startswith(PREFIXES["line"])
    for refusal in composition.refusals:
        assert refusal.refusal_uid.startswith(PREFIXES["refusal"])


def test_reordering_the_observations_renames_nothing():
    """Ids are hashes of content, so a model that emits two readings in the other order does not
    renumber the composition and every reference in it."""
    sample = fixtures.load("moorings")
    forward = fixtures.compose_fixture("moorings")
    backward = fixtures.compose_fixture("moorings",
                                        observations=list(reversed(sample["observations"])))
    assert {l.line_id for l in forward.lines()} == {l.line_id for l in backward.lines()}


def test_the_two_samples_share_no_line_id():
    """Ids are keyed on the inquiry as well as the content, so two inquiries never collide even
    where they would say the same words."""
    a = {l.line_id for l in fixtures.compose_fixture("moorings").lines()}
    b = {l.line_id for l in fixtures.compose_fixture("proofs").lines()}
    assert not a & b


@BOTH
def test_two_replays_of_one_sample_are_identical(name):
    assert (fixtures.compose_fixture(name, now="2026-08-22T10:00:00+00:00").to_dict()
            == fixtures.compose_fixture(name, now="2026-08-22T10:00:00+00:00").to_dict())


@BOTH
def test_the_only_thing_a_different_clock_changes_is_the_declared_volatile_field(name):
    a = fixtures.compose_fixture(name, now="2026-08-22T10:00:00+00:00")
    b = fixtures.compose_fixture(name, now="2026-08-22T23:59:59+00:00")
    assert a.to_dict() != b.to_dict()
    assert a.provenance.composed_at != b.provenance.composed_at
    assert canonical(a) == canonical(b)


@BOTH
def test_a_composition_with_no_clock_invents_no_time(name):
    assert fixtures.compose_fixture(name).provenance.composed_at == ""


@BOTH
def test_a_composition_round_trips_through_json(name):
    data = fixtures.compose_fixture(name, now="t").to_dict()
    assert json.loads(json.dumps(data)) == data
    assert data["provenance"]["producer"] == COMPOSER_PRODUCER


@BOTH
def test_canonical_drops_the_timestamp_and_nothing_else(name):
    composition = fixtures.compose_fixture(name, now="t")
    full, trimmed = composition.to_dict(), canonical(composition)
    assert set(full) == set(trimmed)
    assert set(full["provenance"]) - set(trimmed["provenance"]) == {"composed_at"}


# ── the seam to INTELLIGENCE-001A ────────────────────────────────────────────

class _Model:
    """The shape a typed contract model has: attributes, not keys."""

    def __init__(self, payload):
        for key, value in payload.items():
            setattr(self, key, _typed(value))


def _typed(value):
    if isinstance(value, dict):
        return _Model(value)
    if isinstance(value, list):
        return [_typed(v) for v in value]
    return value


@BOTH
def test_the_same_inputs_as_objects_compose_to_the_same_thing(name):
    """The composer imports no contract model and reads every input through one accessor, so the
    frozen JSON and 001A's typed models are the same input. This is what makes that a fact rather
    than an intention."""
    sample = fixtures.load(name)
    payload = {k: _typed(v) for k, v in sample.items() if k not in fixtures.COMMENTARY_KEYS}
    payload["capabilities"] = sample["capabilities"]      # a matrix stays a mapping
    as_objects = compose(CompositionRequest(**payload))
    assert canonical(as_objects) == canonical(fixtures.compose_fixture(name))


def test_an_observable_that_names_no_capability_is_marked_unnamed_and_not_absent():
    """'Nothing can measure this' and 'nobody said what would' are different claims, and only one
    of them is something the composer was told."""
    composition = compose(_minimal(
        observations=[_observation(status="interpretive")],
        observables=[{"observable_id": "ob", "of": "o",
                      "statement": "the thing that would settle it"}]))
    lines = _lines(composition, SectionId.MEASURABLE)
    line = [l for l in lines if l.text.startswith("the thing")][0]
    assert line.standing == "unnamed"
    assert line.subjects == ()
    assert line.blocks == (_lines(composition, SectionId.INTERPRETIVE)[0].line_id,)
