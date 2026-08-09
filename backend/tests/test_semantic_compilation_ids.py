"""
HARNESS-002A — ids are content-derived, and the replay guarantee rests on it.

The directive requires that replaying a frozen model output not mint a different graph. Every test
here is one way an id could stop being a function of content, and each is a way a replay diff would
fill with noise while nothing about the graph had changed.
"""
from __future__ import annotations

from backend.schemas.semantic_compilation import ClaimEdgeKind, ClaimKind, DecisionKind
from backend.services.semantic_compilation import ids

INQUIRY = "inq_000000000001"
OTHER = "inq_ffffffffffff"
TEXT = "the parts gather toward a centre"


def test_the_same_content_mints_the_same_id_every_time():
    assert ids.claim_id(INQUIRY, ClaimKind.ENTITY, TEXT) == \
        ids.claim_id(INQUIRY, ClaimKind.ENTITY, TEXT)


def test_every_id_carries_its_prefix():
    assert ids.graph_id(INQUIRY, "p").startswith("sig_")
    assert ids.claim_id(INQUIRY, ClaimKind.ENTITY, TEXT).startswith("clm_")
    assert ids.edge_id(INQUIRY, ClaimEdgeKind.SUPPORTS, "a", "b").startswith("cle_")
    assert ids.observable_id(INQUIRY, "clm_a", "extent").startswith("obs_")
    assert ids.alternative_id(INQUIRY, "obs_1", "measure").startswith("alt_")
    assert ids.decision_id(INQUIRY, DecisionKind.CHOOSE_IMAGE_SCOPE, "which?").startswith("dec_")
    assert ids.refusal_id(INQUIRY, "unknown_claim_kind", "vibe").startswith("cref_")
    assert ids.block_id(INQUIRY, "part", TEXT).startswith("rb_")


def test_the_same_sentence_under_two_inquiries_is_two_claims():
    """It is the same sentence and it is not the same claim: the second inquiry asked something
    else of it, and merging them would attribute one inquiry's evidence to another's claim."""
    assert ids.claim_id(INQUIRY, ClaimKind.ENTITY, TEXT) != \
        ids.claim_id(OTHER, ClaimKind.ENTITY, TEXT)


def test_the_same_sentence_typed_two_ways_is_two_claims():
    assert ids.claim_id(INQUIRY, ClaimKind.ENTITY, TEXT) != \
        ids.claim_id(INQUIRY, ClaimKind.INTERPRETATION, TEXT)


def test_typography_does_not_change_an_id_and_meaning_does():
    assert ids.claim_id(INQUIRY, ClaimKind.ENTITY, "  The Parts\n gather ") == \
        ids.claim_id(INQUIRY, ClaimKind.ENTITY, "the parts gather")
    assert ids.claim_id(INQUIRY, ClaimKind.ENTITY, "the parts gather") != \
        ids.claim_id(INQUIRY, ClaimKind.ENTITY, "the parts do not gather")


def test_an_observable_is_the_same_observable_whatever_order_its_targets_arrived_in():
    assert ids.observable_id(INQUIRY, "clm_a", "extent", ["nave", "apse"]) == \
        ids.observable_id(INQUIRY, "clm_a", "extent", ["apse", "nave"])


def test_an_observable_serving_a_different_claim_is_a_different_observable():
    assert ids.observable_id(INQUIRY, "clm_a", "extent") != \
        ids.observable_id(INQUIRY, "clm_b", "extent")


def test_an_edge_is_directed():
    assert ids.edge_id(INQUIRY, ClaimEdgeKind.SUPPORTS, "clm_a", "clm_b") != \
        ids.edge_id(INQUIRY, ClaimEdgeKind.SUPPORTS, "clm_b", "clm_a")


def test_an_edge_of_a_different_kind_between_the_same_pair_is_a_different_edge():
    assert ids.edge_id(INQUIRY, ClaimEdgeKind.SUPPORTS, "clm_a", "clm_b") != \
        ids.edge_id(INQUIRY, ClaimEdgeKind.CHALLENGES, "clm_a", "clm_b")


def test_the_separator_cannot_be_forged_out_of_the_parts():
    """A NUL join, so ('ab','c') and ('a','bc') cannot hash alike — the classic way a concatenated
    key collides without anyone noticing."""
    assert ids.claim_id(INQUIRY, ClaimKind.ENTITY, "ab c") != \
        ids.claim_id(INQUIRY, ClaimKind.ENTITY, "a bc")
    assert ids.alternative_id(INQUIRY, "obs_ab", "c") != ids.alternative_id(INQUIRY, "obs_a", "bc")


def test_an_enum_and_its_value_mint_the_same_id():
    """The parser holds enums and a replay may hold plain strings from JSON. If those disagreed,
    a graph reloaded from disk and recompiled would differ in every id."""
    assert ids.claim_id(INQUIRY, ClaimKind.ENTITY, TEXT) == ids.claim_id(INQUIRY, "entity", TEXT)
    assert ids.edge_id(INQUIRY, ClaimEdgeKind.SUPPORTS, "a", "b") == \
        ids.edge_id(INQUIRY, "supports", "a", "b")


def test_ids_are_the_declared_width():
    assert len(ids.claim_id(INQUIRY, ClaimKind.ENTITY, TEXT)) == len("clm_") + ids.WIDTH
