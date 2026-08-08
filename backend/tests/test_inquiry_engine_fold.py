"""
HARNESS-001B §7 — the DIFFICULT FOLD REHEARSAL: the wave's acceptance prompt, and its honest result.

    "Explore the fold-level aesthetic and style relations between Renaissance and Buddha sculptures,
     their common way of unfolding sensuality, where they drift apart, and what hybrid styles they
     could give birth to."

The board's expected honest result at this wave, for Lane B:

    B turns that into evidence goals, resolves present abilities, and explicitly reports that the
    current sensorium can inspect segmentation/depth/adjacency/nestedness but has no dedicated
    fold-curvature/surface-normal organ. The inquiry is partially investigable, not falsely
    complete.

Four kinds of clause live in one prompt and the run must keep all four apart. Collapsing any two is
the failure, and each collapse has its own test below:

    fold / drapery extent      measurable          → a preparation
    fold curvature / normals   NO instrument       → a capability gap, naming what is missing
    sensuality                 interpretive        → the curator's, never a model's
    hybrid styles              imagined            → refused as evidence, and NOT called a gap

**No prose answer is fabricated in this lane.** There is no composition step, no article, and no
sentence about Renaissance drapery anywhere in the output — a test at the bottom asserts it.
"""
from __future__ import annotations

import json

import pytest

from backend.services.inquiry_engine import capability as cap
from backend.services.inquiry_engine import engine as eng
from backend.services.inquiry_engine import fixtures
from backend.services.inquiry_engine.adapters import FakeDirectorAdapter, SimulatorAdapter
from backend.services.inquiry_engine.events import (EV_CAPABILITY_GAP, EV_CAPABILITY_RESOLVED,
                                                    OUTCOME_ANSWERABLE,
                                                    OUTCOME_PARTIALLY_ANSWERABLE)
from backend.services.inquiry_engine.goals import (CLAUSE_IMAGINED, CLAUSE_INTERPRETIVE,
                                                   KIND_EVIDENCE, STATUS_CAPABILITY_GAP,
                                                   STATUS_REFUSED, STATUS_SATISFIED,
                                                   STATUS_UNRESOLVED)

STAMP = fixtures.STAMP

#: What a `concept_segment` suggestion looks like: a DESCRIPTOR carrying its own stamped status.
#: Nothing here invents geometry — this is the shape a curator would be shown to accept or reject.
FOLD_SUGGESTION = {
    "id": None, "type": "region_mask", "role": "fold", "producer": "concept_segment",
    "epistemic_status": "measured", "label": "fold",
    "provenance": {"producer": "concept_segment", "adapter": "fixture:concept_segment"},
}


@pytest.fixture()
def fold_run():
    return eng.run_inquiry(
        fixtures.fold_frame(), posts=fixtures.fold_world(), now=STAMP,
        post_id="post_renaissance", region_id="drapery",
        simulator=SimulatorAdapter(),
        director=FakeDirectorAdapter(suggestions=[FOLD_SUGGESTION], ran=True))


def _by_phrase(run):
    return {g.phrase: g for g in run.goals if g.kind == KIND_EVIDENCE}


# ── 1. the measurable half is resolvable ─────────────────────────────────────

def test_segmentation_work_is_resolvable_where_the_instrument_exists(fold_run):
    goals = _by_phrase(fold_run)
    extent = goals["fold"]
    assert extent.need == "extent_of_a_named_thing"
    assert extent.status == STATUS_SATISFIED
    resolutions = {e.goal_id: e.payload for e in fold_run.events_of(EV_CAPABILITY_RESOLVED)}
    assert resolutions[extent.id]["kind"] == cap.DIRECTOR_PREPARATION


def test_the_measured_stand_in_for_a_brushed_fold_says_it_is_not_the_curators_act(fold_run):
    """The directive's rule, at run level: proposing `concept_segment("fold")` is legitimate, and it
    must never read as a silent execution of the hand-drawn field."""
    extent = _by_phrase(fold_run)["fold"]
    payload = next(e.payload for e in fold_run.events_of(EV_CAPABILITY_RESOLVED)
                   if e.goal_id == extent.id)
    assert payload["interpretive_naming"] is True
    joined = " ".join(payload["caveats"])
    assert "CURATOR-AUTHORED" in joined and "does not execute it" in joined


def test_comparison_work_is_resolvable_because_compare_views_exists(fold_run):
    compare = _by_phrase(fold_run)["compare"]
    payload = next(e.payload for e in fold_run.events_of(EV_CAPABILITY_RESOLVED)
                   if e.goal_id == compare.id)
    assert payload["kind"] == cap.DIRECTOR_PREPARATION
    assert "compare_views" in payload["actuators"]


# ── 2. the gap, named ────────────────────────────────────────────────────────

def test_the_missing_fold_measurement_becomes_a_capability_gap_and_names_what_is_absent(fold_run):
    curvature = _by_phrase(fold_run)["fold curvature"]
    assert curvature.status == STATUS_CAPABILITY_GAP

    gaps = [g for g in fold_run.gaps if g.need == "fold_morphology"]
    assert len(gaps) == 1
    unmet = gaps[0].unmet[0]
    assert "fold-curvature" in unmet and "surface-normal" in unmet
    assert fold_run.events_of(EV_CAPABILITY_GAP)


def test_the_gap_says_which_instruments_DO_exist_so_it_is_not_read_as_blindness(fold_run):
    """The board asks for exactly this: the sensorium can inspect segmentation, depth, adjacency and
    nestedness — and none of those measures how a surface turns."""
    unmet = [g for g in fold_run.gaps if g.need == "fold_morphology"][0].unmet[0]
    for instrument in ("concept_segment", "depth_organ", "adjacency_organ", "nestedness_organ"):
        assert instrument in unmet


def test_depth_alone_is_not_pretended_to_settle_fold_morphology(fold_run):
    """The directive names this trap outright. A monocular depth field orders regions front to back;
    it is not the local normal a fold's morphology is a claim about."""
    unmet = [g for g in fold_run.gaps if g.need == "fold_morphology"][0].unmet[0]
    assert "front to back" in unmet
    assert "does not yield the local normal" in unmet


# ── 3. sensuality stays interpretive, hybrid stays imagined ──────────────────

def test_sensuality_remains_interpretive_and_is_never_answered_by_a_model(fold_run):
    sensuality = _by_phrase(fold_run)["sensuality"]
    assert sensuality.status == STATUS_UNRESOLVED
    payload = next(e.payload for e in fold_run.events_of(EV_CAPABILITY_RESOLVED)
                   if e.goal_id == sensuality.id)
    assert payload["kind"] == cap.HUMAN_ACTION
    assert payload["demands"] == CLAUSE_INTERPRETIVE
    assert "curator" in payload["why"]


def test_hybrid_remains_imagined_and_is_explicitly_not_reported_as_a_capability_gap(fold_run):
    """A speculation reported as a gap would put a fabricated engineering task on the board — build
    the instrument that measures what does not exist yet."""
    hybrid = _by_phrase(fold_run)["hybrid"]
    assert hybrid.status == STATUS_REFUSED
    payload = next(e.payload for e in fold_run.events_of(EV_CAPABILITY_RESOLVED)
                   if e.goal_id == hybrid.id)
    assert payload["kind"] == cap.REFUSED
    assert payload["law"] == cap.LAW_SPECULATION_IS_NOT_EVIDENCE
    assert payload["demands"] == CLAUSE_IMAGINED
    assert all(g.need != "speculation" for g in fold_run.gaps)


def test_composition_is_refused_because_it_was_proposed_before_any_evidence(fold_run):
    composition = next(g for g in fold_run.goals
                       if g.kind == KIND_EVIDENCE and "compose_percept" in (g.question or ""))
    assert composition.status == STATUS_REFUSED
    payload = next(e.payload for e in fold_run.events_of(EV_CAPABILITY_RESOLVED)
                   if e.goal_id == composition.id)
    assert payload["law"] == cap.LAW_SYNTHESIS_BEFORE_EVIDENCE


# ── 4. the run's own verdict ─────────────────────────────────────────────────

def test_the_run_is_partially_answerable_and_stops_on_the_gap(fold_run):
    assert fold_run.outcome == OUTCOME_PARTIALLY_ANSWERABLE
    assert fold_run.outcome != OUTCOME_ANSWERABLE
    assert fold_run.stop_reason == "capability_gap"


def test_the_run_is_never_falsely_satisfied_even_with_a_generous_director(fold_run):
    """A Director that returns something for every task is the most flattering environment this run
    could have, and it still must not come back answerable."""
    assert fold_run.outcome != OUTCOME_ANSWERABLE
    unsettled = [g for g in fold_run.goals if g.kind == KIND_EVIDENCE
                 and g.status != STATUS_SATISFIED]
    assert unsettled, "every evidence goal was reported settled on the hardest prompt in the wave"


def test_no_prose_answer_is_fabricated_anywhere_in_the_run(fold_run):
    """The end of this lane is not article generation. There is no composed sentence about
    Renaissance drapery in the output, and there is nowhere to put one."""
    payload = json.dumps(fold_run.to_dict())
    for word in ("sculptor", "baroque", "serene", "graceful", "the artist"):
        assert word not in payload.lower(), f"a composed reading leaked into the run: {word!r}"
    # The prompt itself is carried verbatim and is the ONE place the subject matter appears as prose.
    assert payload.count(fixtures.fold_frame()["prompt"]) >= 1


def test_with_no_director_at_all_the_run_is_exhausted_and_says_execution_was_unavailable():
    """The same frame in an unwired environment. Unavailable infrastructure produces an explicit
    stop reason, never a quieter version of the same run."""
    run = eng.run_inquiry(fixtures.fold_frame(), posts=fixtures.fold_world(), now=STAMP,
                          post_id="post_renaissance", region_id="drapery",
                          simulator=SimulatorAdapter())
    assert run.outcome == "exhausted"
    assert run.stop_reason == "execution_unavailable"
    # And the gap is STILL reported: a missing instrument is not contingent on the wiring.
    assert [g.need for g in run.gaps] == ["fold_morphology"]
