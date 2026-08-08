"""
HARNESS-001B §4 — capability resolution: six outcomes, three vocabularies, and the rows that are
deliberately not a lookup.

The failure this file exists to catch is the flatten. One enum over "things the system can do" would
make `brush_field(fold)` and `concept_segment("fold")` the same row, and a run would then execute a
curator's hand-authored act silently — the single most consequential fabrication available at this
seam.
"""
from __future__ import annotations

import pytest

from backend.services.agents import organs as agent_organs
from backend.services.director import capabilities as director_caps
from backend.services.inquiry_engine import capability as cap
from backend.services.inquiry_engine.frame import ProposedAction
from backend.services.inquiry_engine.goals import (CLAUSE_IMAGINED, CLAUSE_INTERPRETIVE,
                                                   CLAUSE_MEASURED, CLAUSE_SOURCED)


# ── 1. the six outcomes exist and are reachable ──────────────────────────────

def test_all_six_outcomes_are_reachable_and_none_is_a_default():
    """Six declared outcomes with one unreachable is five outcomes and a comment."""
    reached = {
        cap.resolve_need("comparison_across_images").kind,
        cap.resolve_need("nestedness_here", locus=True).kind,
        cap.resolve_need("interpretive_judgement").kind,
        cap.resolve_need("depth_here", locus=True).kind,
        cap.resolve_need("fold_morphology").kind,
        cap.resolve_need("speculation").kind,
    }
    assert reached == set(cap.RESOLUTIONS)


# ── 2. the three vocabularies are not flattened ──────────────────────────────

def test_a_brushed_fold_is_never_silently_executed_as_a_segmentation():
    """The directive's own example. A resolver MAY propose `concept_segment("fold")` when the
    phrase is explicit — as a DISTINCT preparation, carrying that this is model measurement plus an
    interpretive naming."""
    resolution = cap.resolve_action(
        ProposedAction(type="brush_field", role="fold", phrase="fold", source="user"))
    assert resolution.kind == cap.DIRECTOR_PREPARATION
    assert resolution.actuators == ("concept_segment",)
    assert resolution.interpretive_naming is True
    joined = " ".join(resolution.caveats)
    assert "CURATOR-AUTHORED" in joined
    assert "does not execute it" in joined
    assert "interpretive naming" in joined


def test_a_brushed_field_with_no_phrase_waits_for_a_hand_rather_than_guessing_a_query():
    resolution = cap.resolve_action(ProposedAction(type="brush_field", role="", phrase=""))
    assert resolution.kind == cap.HUMAN_ACTION
    assert resolution.unmet == ("phrase",)


def test_a_challenge_becomes_a_curators_act_and_never_a_model_authored_mutation():
    resolution = cap.resolve_action(
        ProposedAction(type="challenge_percept", source="model_suggested"))
    assert resolution.kind == cap.HUMAN_ACTION
    assert resolution.law == cap.LAW_MODEL_MAY_NOT_AUTHOR


def test_composition_before_evidence_is_refused_and_after_evidence_is_preparation():
    """`compose_percept` is synthesis AFTER evidence, not preparation before it — and the check is
    live, against how much evidence has actually returned."""
    before = cap.resolve_action(ProposedAction(type="compose_percept"), evidence_returned=0)
    assert before.kind == cap.REFUSED
    assert before.law == cap.LAW_SYNTHESIS_BEFORE_EVIDENCE

    after = cap.resolve_action(ProposedAction(type="compose_percept"), evidence_returned=3)
    assert after.kind == cap.DIRECTOR_PREPARATION
    assert after.actuators == ("compose_percept",)


def test_nestedness_and_adjacency_are_organ_bound_missions_not_public_action_aliases():
    for need in ("nestedness_here", "adjacency_here", "chroma_here"):
        resolution = cap.resolve_need(need, locus=True)
        assert resolution.kind == cap.AGENT_MISSION, need
        assert resolution.organs, need
        assert not resolution.actuators, need


def test_a_world_action_without_a_locus_is_not_dispatched():
    """'movement/meeting are world actions available only after a locus and grounded horizon
    exist.' With no locus there is no position, and every reading would be about somewhere else."""
    resolution = cap.resolve_need("nestedness_here", locus=False)
    assert resolution.kind == cap.HUMAN_ACTION
    assert resolution.unmet == ("a locus",)


def test_an_unknown_act_and_an_unknown_need_are_refused_visibly_by_name():
    act = cap.resolve_action(ProposedAction(type="summon_the_muse"))
    assert act.kind == cap.REFUSED and act.law == cap.LAW_UNKNOWN_INSTRUMENT
    assert "summon_the_muse" in act.unmet

    need = cap.resolve_need("measure_the_ineffable")
    assert need.kind == cap.REFUSED and need.law == cap.LAW_UNKNOWN_INSTRUMENT
    assert "measure_the_ineffable" in need.why


# ── 3. gap vs unavailable vs law ─────────────────────────────────────────────

def test_the_fold_gap_names_the_missing_instrument_and_the_ones_that_do_exist():
    """The wave's own acceptance criterion: the run must say the sensorium can inspect
    segmentation/depth/adjacency/nestedness and has no dedicated fold-curvature organ."""
    resolution = cap.resolve_need("fold_morphology")
    assert resolution.kind == cap.CAPABILITY_GAP
    unmet = resolution.unmet[0]
    assert "surface-normal" in unmet
    for present in ("concept_segment", "depth_organ", "adjacency_organ", "nestedness_organ"):
        assert present in unmet, f"the gap does not say that {present} exists"


def test_an_unavailable_runtime_is_not_a_capability_gap():
    """'unavailable model differs from measured absence.' The instrument exists; a restarted model
    answers this. Folding the two would tell a curator to stop asking an answerable question."""
    down = cap.resolve_need("extent_of_a_named_thing", phrase="fold",
                            capabilities_up=frozenset())
    assert down.kind == cap.DIRECTOR_PREPARATION
    assert down.actuators
    assert any("UNAVAILABLE, not absent" in c for c in down.caveats)

    up = cap.resolve_need("extent_of_a_named_thing", phrase="fold",
                          capabilities_up=frozenset({"concept_segmenter", "grounding_detector"}))
    assert up.kind == cap.DIRECTOR_PREPARATION
    assert not up.caveats


def test_availability_is_unknown_rather_than_assumed_when_the_caller_does_not_say():
    state = cap.actuator_availability(("concept_segment",))
    assert state["state"] == "unknown"
    assert "down" not in state


def test_speculation_is_refused_by_a_law_and_is_explicitly_not_a_gap():
    """No instrument is missing, because this was never a measurement question. Reporting it as a
    gap would put a fabricated engineering task on the board."""
    resolution = cap.resolve_need("speculation")
    assert resolution.kind == cap.REFUSED
    assert resolution.law == cap.LAW_SPECULATION_IS_NOT_EVIDENCE
    assert resolution.demands == CLAUSE_IMAGINED
    assert resolution.kind != cap.CAPABILITY_GAP


def test_an_interpretive_clause_goes_to_the_curator_and_not_to_a_model():
    resolution = cap.resolve_need("interpretive_judgement")
    assert resolution.kind == cap.HUMAN_ACTION
    assert resolution.demands == CLAUSE_INTERPRETIVE
    assert "curator" in resolution.why


def test_depth_is_a_composite_because_the_organ_reads_a_field_a_model_produces():
    resolution = cap.resolve_need("depth_here", locus=True)
    assert resolution.kind == cap.COMPOSITE
    assert resolution.actuators == ("background_recession",)
    assert resolution.organs == ("depth_organ",)
    assert any("not optional" in c for c in resolution.caveats)


# ── 4. the tables it reads are the LIVE ones ─────────────────────────────────

def test_every_actuator_a_need_names_exists_in_the_live_director_catalogue():
    """A need pointing at a deleted actuator would resolve as a gap, which is the honest outcome —
    and also a table error nobody would notice. This is the check that notices."""
    for key, need in cap.NEEDS.items():
        for name in (*need.actuators, *need.prepares_first):
            assert director_caps.get(name) is not None, f"{key} names absent actuator {name!r}"


def test_every_organ_a_need_names_resolves_against_the_live_binding_table():
    for key, need in cap.NEEDS.items():
        for name in need.organs:
            binding = agent_organs.resolve(name)
            assert binding.resolution != agent_organs.UNKNOWN, \
                f"{key} names {name!r}, which is not an organ: {binding.detail}"


def test_a_deleted_actuator_would_be_reported_as_a_gap_rather_than_planned():
    """The negative control for the check above: prove the resolver actually notices absence."""
    state = cap.actuator_availability(("a_finder_that_was_removed",))
    assert state["exists"] == []
    assert state["absent"] == ["a_finder_that_was_removed"]


def test_a_residency_managed_organ_is_a_caveat_and_not_a_gap():
    """`organs.resolve` calls a roster organ REAL-but-not-invocable-here. Collapsing that into
    UNKNOWN would make a correct organ name look like a typo."""
    state = cap.organ_availability(("depth_anything_v2_small",))
    assert state["resident"] == ["depth_anything_v2_small"]
    assert state["unknown"] == []


# ── 5. term routing refuses rather than guessing ─────────────────────────────

@pytest.mark.parametrize("term,expected", [
    ("fold curvature", "fold_morphology"),
    ("surface normal", "fold_morphology"),
    ("sensuality", "interpretive_judgement"),
    ("hybrid", "speculation"),
    ("compare", "comparison_across_images"),
    ("nestedness", "nestedness_here"),
])
def test_a_curators_term_routes_to_the_need_that_actually_serves_it(term, expected):
    assert cap.need_for_term(term) == expected


def test_the_longest_match_wins_so_a_fold_is_not_a_fold_curvature():
    """'fold' is a measurable extent; 'fold curvature' is the gap. A shorter match winning would
    report the hardest question in the wave as answered."""
    assert cap.need_for_term("fold") == "extent_of_a_named_thing"
    assert cap.need_for_term("fold curvature") == "fold_morphology"


def test_an_unmatched_term_returns_none_rather_than_the_nearest_looking_need():
    assert cap.need_for_term("the ineffable quality of Tuesday") is None


def test_the_three_special_acts_are_absent_from_the_plain_lookup():
    """If any of these appeared in `_ACTION_NEEDS`, a caller shortcutting through `need_for_action`
    would erase the rule that makes them special."""
    for act in ("brush_field", "challenge_percept", "compose_percept"):
        assert cap.need_for_action(act) is None
