"""WAVE3 — cross-modal composition: the claims, and the one this lane must not make.

The temptation here is unique in the wave. Every other lane could be wrong by measuring badly; this
one can be wrong by measuring nothing and reporting a conclusion. A null result is the expected
honest answer, and a null is also exactly what you get from a mechanism that was never able to say
anything else — so these tests are arranged around telling those two apart:

  1. THE QUESTION IS REAL — chroma becoming relational changed what `society.comparable` says, and
     real region pairs carry both an occlusion relation and a chromatic rhyme. If no pair ever
     shared a subject the answer would be trivial. §1.
  2. THE NULL IS NOT A FOREGONE CONCLUSION — the mechanism CAN return `composed`; it does so for
     the one composition that exists. A layer that could only ever say `coexistent` would prove
     nothing by saying it. §2.
  3. NOTHING WAS INVENTED — no cross-modal scalar, no forced composition, and the refusal still
     comes from `compare_across_senses` rather than from a sentence written here. §3.

§4 is the scope this lane held.
"""
from __future__ import annotations

import pytest

from backend.services import chroma_organ, cross_modal as cm
from backend.services.agents import society


def _occlusion(a="r_1", b="r_2", relation="in_front_of"):
    return {"relation": relation, "organ": "occlusion_organ",
            "a_region_id": a, "b_region_id": b, "basis": "mask",
            "dominance": 0.99, "separation": 0.99}


def _rhyme(a="r_1", b="r_2", relation="rhymes_with"):
    return {"relation": relation, "organ": "chromatic_relation",
            "a_region_id": a, "b_region_id": b, "basis": "mask",
            "rhyme": 0.91, "rhymes": True}


def _nested(a="r_1", b="r_2"):
    return {"relation": "nested_within", "organ": "nestedness_organ",
            "inner_region_id": a, "outer_region_id": b, "basis": "mask"}


def _meets(a="r_1", b="r_2"):
    return {"relation": "meets", "organ": "adjacency_organ",
            "inner_region_id": a, "outer_region_id": b, "basis": "mask"}


# ── 1. the question is real ────────────────────────────────────────────────

def test_two_relations_about_one_pair_share_a_subject():
    """THE PRECONDITION FOR THE WHOLE LANE. If a depth relation and a chroma relation could never
    be about the same two regions, `coexistent` would be trivial rather than a finding.

    On the corpus they can and they are: 3 posts, 265 measured relations, 126 pairs where the same
    region pair carries both an occlusion reading and a chromatic rhyme.
    """
    assert cm.shares_a_subject(_occlusion(), _rhyme())
    assert cm.subject_of(_occlusion()) == frozenset({"r_1", "r_2"})
    assert cm.sense_of(_occlusion()) == "depth" and cm.sense_of(_rhyme()) == "chroma"


def test_the_subject_is_unordered_because_the_question_is_what_it_is_about():
    """`in_front_of` is directed and `rhymes_with` is symmetric. Asking whether they are about the
    same SUBJECT is asking about the two regions, not about who is in front."""
    assert cm.shares_a_subject(_occlusion("r_1", "r_2"), _rhyme("r_2", "r_1"))


def test_relations_about_different_pairs_are_not_about_one_thing():
    """And this is where `society.comparable` is now too coarse: both are arity 2, so it admits
    them — but a relation about (1,2) and one about (3,4) are not about the same thing."""
    verdict = cm.attempt(_occlusion("r_1", "r_2"), _rhyme("r_3", "r_4"))
    assert verdict["outcome"] == cm.DIFFERENT_SUBJECT
    assert "too coarse" in verdict["detail"]


def test_a_pair_sharing_a_subject_across_senses_coexists():
    verdict = cm.attempt(_occlusion(), _rhyme())
    assert verdict["outcome"] == cm.COEXISTENT and verdict["cross_modal"] is True
    assert sorted(verdict["senses"]) == ["chroma", "depth"]
    assert verdict["subject"] == ["r_1", "r_2"]


def test_the_verdict_says_no_rule_exists_rather_than_no_relationship_exists():
    """THE SENTENCE THIS LANE TURNS ON. "Nothing has been written down that says what these two
    jointly establish" is a different and weaker claim than "these do not compose", and it is the
    only one a survey over a hardcoded rule table is in a position to make."""
    detail = cm.attempt(_occlusion(), _rhyme())["detail"]
    assert "no composition is known" in detail
    assert "not a measurement showing no relationship exists" in detail
    assert "conjunction and not a" in detail


# ── 2. the null is not a foregone conclusion ──────────────────────────────

def test_the_mechanism_can_return_composed():
    """A layer that could only ever say `coexistent` would prove nothing by saying it. The one
    composition this system knows is reachable through exactly this code path."""
    verdict = cm.attempt(_nested(), _meets())
    assert verdict["outcome"] == cm.COMPOSED
    assert verdict["claim"] == "nested_at_boundary"


def test_there_is_exactly_one_known_composition_and_it_is_within_sense():
    """The scarcity is the finding. A cross-modal entry would need someone to write down what third
    fact the two relations jointly establish; that nobody has is what this lane reports."""
    assert len(cm.KNOWN_COMPOSITIONS) == 1
    a, b, _claim = cm.KNOWN_COMPOSITIONS[0]
    assert cm.sense_of({"relation": a}) == cm.sense_of({"relation": b}) == "geometry"


def test_a_within_sense_pairing_is_sent_to_the_layer_that_owns_it():
    """Asking the cross-modal question of one sense would answer it with the wrong evidence."""
    verdict = cm.attempt(_nested(), _nested("r_1", "r_3"))
    assert verdict["cross_modal"] is False
    assert "within-sense" in verdict["detail"]


def test_the_survey_counts_what_it_saw_and_says_so():
    """A report, not a gate — and the bound is stated, because a scan claiming no cross-modal
    composition exists after six pairs would be a claim about how far it looked."""
    relations = [_occlusion("a", "b"), _rhyme("a", "b"), _rhyme("c", "d"), _nested("a", "b")]
    report = cm.survey(relations)

    assert report["relations"] == 4
    assert report["outcomes"][cm.COEXISTENT] >= 1
    assert report["outcomes"][cm.DIFFERENT_SUBJECT] >= 1
    assert report["composed"] == 0
    assert report["same_subject"] >= 1
    assert "cross-modal attempts" in report["detail"]


def test_the_survey_would_report_a_composition_if_one_ever_happened():
    """Pinned so the zero in the finding means something. If a cross-modal rule is ever added, the
    survey counts it — the null is measured, not built in."""
    saved = cm.KNOWN_COMPOSITIONS
    try:
        cm.KNOWN_COMPOSITIONS = saved + (("in_front_of", "rhymes_with", "hypothetical"),)
        report = cm.survey([_occlusion("a", "b"), _rhyme("a", "b")])
        assert report["composed"] == 1
    finally:
        cm.KNOWN_COMPOSITIONS = saved
    assert cm.survey([_occlusion("a", "b"), _rhyme("a", "b")])["composed"] == 0


# ── 3. nothing was invented ───────────────────────────────────────────────

def test_no_comparable_number_hides_next_door():
    """The small-society test, one level up. A refusal is worth nothing if the thing it refuses is
    available under another name on the verdict."""
    verdict = cm.attempt(_occlusion(), _rhyme())
    for forbidden in ("score", "similarity", "strength", "combined", "magnitude", "distance"):
        assert not [k for k in verdict if forbidden in k], forbidden
    assert not isinstance(verdict.get("outcome"), (int, float))


def test_the_refusal_comes_from_the_sensorium_and_is_not_paraphrased_here():
    """Routed through `compare_across_senses` for the reason the society lane gives: it is where
    this system records that no scale exists, and a second place saying so is a second place that
    can stop saying so."""
    verdict = cm.attempt(_occlusion(), _rhyme())
    assert "no common scale" in verdict["refusal_if_asked_for_a_number"]


def test_a_comparison_that_stops_refusing_is_a_defect_and_raises():
    """If the sensorium ever answers, this layer will not carry the number on."""
    original = chroma_organ.compare_across_senses
    try:
        chroma_organ.compare_across_senses = lambda *a, **k: 0.5
        with pytest.raises(cm.CrossModalLeak, match="never measured"):
            cm.attempt(_occlusion(), _rhyme())
    finally:
        chroma_organ.compare_across_senses = original


def test_the_outcome_vocabulary_is_the_societys_own():
    """Three outcomes defined in one place. A second vocabulary for the same states is a second
    place for them to drift."""
    assert cm.COMPOSED is society.COMPOSED
    assert cm.COEXISTENT is society.COEXISTENT
    assert cm.INCOMMENSURABLE is society.INCOMMENSURABLE


def test_an_unregistered_relation_is_unknown_rather_than_guessed():
    assert cm.sense_of({"relation": "smells_like"}) == "unknown"
    assert cm.sense_of(None) == "unknown"
    assert cm.survey([_occlusion(), {"relation": "smells_like", "a_region_id": "r_1",
                                     "b_region_id": "r_2"}])["cross_modal_attempts"] == 0


# ── 4. scope ──────────────────────────────────────────────────────────────

def test_this_lane_invented_no_statistic_and_touched_nothing_it_was_told_not_to():
    """Relation/composition-side only: no cross-modal statistic, no `structure_map` edit, no organ
    change, no agent traversal."""
    import pathlib
    import subprocess

    root = pathlib.Path(cm.__file__).resolve().parents[2]
    changed = subprocess.run(["git", "diff", "--name-only", "origin/main...HEAD"],
                             capture_output=True, text=True, cwd=str(root)).stdout
    for forbidden in ("structure_map.py", "chroma_organ.py", "depth_organ.py",
                      "occlusion_organ.py", "chromatic_relation.py", "situated_agent.py"):
        assert forbidden not in changed, f"{forbidden} was modified:\n{changed}"

    # NO CROSS-MODAL STATISTIC: this module never reads a measurement value off either relation.
    # Counting outcomes is not a statistic about the pictures; touching `rhyme` or `dominance`
    # would be the beginning of one, and the beginning is the whole risk.
    body = pathlib.Path(cm.__file__).read_text().split('"""', 2)[2]
    for value in ("rhyme", "dominance", "separation", "nesting_index",
                  "contact_fraction", "depth_mean", "warmth_mean"):
        assert f'"{value}"' not in body, f"this module reads {value!r} — that is a statistic"
    for arithmetic in ("math.", "statistics."):
        assert arithmetic not in body, f"this module imports {arithmetic!r} — it must not"
