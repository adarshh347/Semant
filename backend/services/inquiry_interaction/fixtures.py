"""
HARNESS-002B — two domain-neutral fixtures, and why neither of them is about a picture.

THE POINT OF THE PAIR. The deliberation policy must not depend on visual-art vocabulary, and the
cheapest way to prove that is to exercise it on two subject matters that share no words with each
other or with the repository's running example. One is a municipal water survey; the other is a
warehouse stock reconciliation. Neither names an image, a sculpture, a fold or a building, and the
policy code contains no branch that could tell them apart.

WHAT A FIXTURE IS HERE. The opaque mapping a semantic compiler would emit — a decision candidate
with its options and their consequences. This lane does not produce candidates and does not know
their producer's schema; these are shaped to the board's pinned seam and nothing here asserts they
are the compiler's final spelling.

Every option states a `consequence` in the terms of its own domain, because an option whose
consequence is generic ("proceeds with the analysis") is the shape of a fixture written to make
tests pass rather than to stand in for the thing.
"""
from __future__ import annotations

from typing import Any, Dict, List

#: The single timestamp these fixtures are built at. Handed in rather than read, so a test that
#: compares two constructions is comparing the constructions.
STAMP = "2026-01-01T00:00:00+00:00"


# ── fixture one: a municipal water survey ────────────────────────────────────

def survey_graph() -> Dict[str, Any]:
    """The opaque graph snapshot. This lane never reads inside it; it is here so a test can prove
    a session amended three of its objects and left it byte-identical."""
    return {
        "schema_version": "semantic-inquiry-graph.v1",
        "graph_id": "sig_survey",
        "inquiry_id": "inq_survey",
        "prompt": "Has the nitrate level in the eastern wells changed since the new drainage?",
        "claims": [
            {"claim_id": "clm_nitrate", "text": "nitrate concentration rose in the eastern wells",
             "claim_kind": "attribute"},
            {"claim_id": "clm_drainage", "text": "the new drainage caused the change",
             "claim_kind": "causal_hypothesis"},
        ],
        "observables": [
            {"observable_id": "obs_series", "claim_ref": "clm_nitrate"},
        ],
    }


def survey_scope_candidate() -> Dict[str, Any]:
    """A scope fork with one recommended, reversible option. MATERIAL: consult pauses, auto takes
    it, step pauses."""
    return {
        "candidate_id": "cnd_survey_scope",
        "kind": "choose_scope",
        "question": "Compare the eastern wells only, or every well in the district?",
        "why_now": ("the district set is eleven times larger; a district comparison answers a "
                    "different question and takes eleven times as long to answer it"),
        "affected_refs": ["clm_nitrate", "obs_series"],
        "allow_free_text": True,
        "summaries": {"clm_nitrate": "nitrate concentration rose in the eastern wells",
                      "obs_series": "a per-well concentration series over the drainage works"},
        "options": [
            {"option_id": "opt_eastern", "label": "Eastern wells only",
             "consequence": ("reads the four eastern wells; the result speaks about the wells the "
                             "claim names and about nothing else"),
             "recommended": True, "reversible": True, "affects_refs": ["obs_series"]},
            {"option_id": "opt_district", "label": "Every well in the district",
             "consequence": ("reads forty-four wells; the eastern rise becomes comparable to a "
                             "district baseline, and the claim's own subject becomes one line in it"),
             "reversible": True, "affects_refs": ["obs_series", "clm_nitrate"]},
        ],
    }


def survey_tie_candidate() -> Dict[str, Any]:
    """Two options recommended equally. Auto mode must leave this unresolved rather than take the
    first — the tie is the whole reason this fixture exists."""
    return {
        "candidate_id": "cnd_survey_tie",
        "kind": "choose_operationalization",
        "question": "Measure the change as a seasonal mean or as a peak-to-peak difference?",
        "why_now": ("the two summaries disagree about wet years; whichever is chosen decides what "
                    "a null result would mean"),
        "affected_refs": ["obs_series"],
        "options": [
            {"option_id": "opt_seasonal", "label": "Seasonal mean",
             "consequence": "averages within each season; a single wet month stops dominating",
             "recommended": True, "reversible": True},
            {"option_id": "opt_peak", "label": "Peak-to-peak",
             "consequence": "compares extremes; a single wet month becomes the signal",
             "recommended": True, "reversible": True},
        ],
    }


def survey_cost_candidate() -> Dict[str, Any]:
    """A DEFERRABLE fork: consult passes it with a record, step still stops."""
    return {
        "candidate_id": "cnd_survey_cost",
        "kind": "authorize_cost",
        "question": "Re-read the archived samples as well as the current ones?",
        "why_now": "the archive read is bounded but not free — about four minutes of instrument time",
        "affected_refs": ["obs_series"],
        "options": [
            {"option_id": "opt_current", "label": "Current samples only",
             "consequence": "returns in seconds; the series starts at the drainage works",
             "recommended": True, "reversible": True},
            {"option_id": "opt_archive", "label": "Include the archive",
             "consequence": "adds four minutes and eleven years of prior readings",
             "reversible": True},
        ],
    }


def survey_undeclared_candidate() -> Dict[str, Any]:
    """One recommended option that never says whether it can be undone. Auto mode must NOT take
    it — the fixture for "undeclared reversibility is not a yes"."""
    return {
        "candidate_id": "cnd_survey_undeclared",
        "kind": "choose_scope",
        "question": "Narrow the series to the two wells nearest the outfall?",
        "why_now": "a narrower series is quicker and answers about fewer wells",
        "affected_refs": ["obs_series"],
        "options": [
            {"option_id": "opt_narrow", "label": "Two nearest wells",
             "consequence": "drops nine wells from the series",
             "recommended": True},
            {"option_id": "opt_keep", "label": "Keep all eleven",
             "consequence": "keeps the series as declared", "reversible": True},
        ],
    }


def survey_ledger_candidate() -> Dict[str, Any]:
    """An ACCEPT_TO_LEDGER gate. Every mode pauses, including auto, and the recommended-reversible
    option is present precisely so the test proves the gate wins over eligibility."""
    return {
        "candidate_id": "cnd_survey_accept",
        "kind": "accept_to_ledger",
        "question": "Accept the eastern-well series as the district's record for this quarter?",
        "why_now": "acceptance is the only path into the shared record and is not undone the same way",
        "affected_refs": ["obs_series"],
        "options": [
            {"option_id": "opt_accept", "label": "Accept",
             "consequence": "the series becomes the quarter's record of the eastern wells",
             "recommended": True, "reversible": True, "accepts_to_ledger": True},
            {"option_id": "opt_hold", "label": "Hold",
             "consequence": "the series stays a proposal and nothing enters the record",
             "reversible": True},
        ],
    }


# ── fixture two: a warehouse stock reconciliation ────────────────────────────

def inventory_graph() -> Dict[str, Any]:
    return {
        "schema_version": "semantic-inquiry-graph.v1",
        "graph_id": "sig_inventory",
        "inquiry_id": "inq_inventory",
        "prompt": "Why does the bay-three count disagree with the manifest?",
        "claims": [
            {"claim_id": "clm_shortfall", "text": "bay three is short by eleven units",
             "claim_kind": "attribute"},
        ],
        "observables": [{"observable_id": "obs_recount", "claim_ref": "clm_shortfall"}],
    }


def inventory_disambiguation_candidate() -> Dict[str, Any]:
    """A MATERIAL disambiguation with no recommendation at all. Auto leaves it unresolved for a
    different reason than the tie does, and the two reasons must not read the same."""
    return {
        "candidate_id": "cnd_inventory_which",
        "kind": "disambiguate_claim",
        "question": "Does 'bay three' mean the aisle or the loading dock of that number?",
        "why_now": ("the two hold different stock under the same label, so every count after this "
                    "is a count of a different thing"),
        "affected_refs": ["clm_shortfall", "obs_recount"],
        "summaries": {"clm_shortfall": "bay three is short by eleven units"},
        "options": [
            {"option_id": "opt_aisle", "label": "The aisle",
             "consequence": "recounts 240 pallet positions in the racking",
             "reversible": True},
            {"option_id": "opt_dock", "label": "The loading dock",
             "consequence": "recounts 18 staged pallets awaiting despatch",
             "reversible": True},
        ],
    }


def inventory_author_candidate() -> Dict[str, Any]:
    """An AUTHOR_ACTION gate in the second domain, so the gate rule is proved twice with no shared
    vocabulary between the proofs."""
    return {
        "candidate_id": "cnd_inventory_author",
        "kind": "author_action",
        "question": "Record a written shrinkage note against bay three?",
        "why_now": "a shrinkage note is signed by a person and is read as their statement",
        "affected_refs": ["clm_shortfall"],
        "options": [
            {"option_id": "opt_note", "label": "Write the note",
             "consequence": "attaches a signed shrinkage note to the bay's record",
             "recommended": True, "reversible": True, "authorial": True},
        ],
        "allow_free_text": True,
    }


def inventory_review_candidate() -> Dict[str, Any]:
    return {
        "candidate_id": "cnd_inventory_review",
        "kind": "review_result",
        "question": "The recount returned nine units, not eleven. Does that settle the shortfall?",
        "why_now": ("the machine can report the number and cannot judge whether it answers the "
                    "question that was asked"),
        "affected_refs": ["clm_shortfall", "obs_recount"],
        "options": [
            {"option_id": "opt_settles", "label": "It settles it",
             "consequence": "the shortfall claim is treated as addressed and nothing more is counted",
             "reversible": True},
            {"option_id": "opt_recount", "label": "Count again",
             "consequence": "a second recount runs against the same manifest",
             "reversible": True},
        ],
    }


def survey_batch() -> List[Dict[str, Any]]:
    """Three candidates in one offer, so a mode's behaviour across a BATCH is provable: step must
    stop at each in turn, and auto must settle all three without a wait."""
    return [survey_scope_candidate(), survey_cost_candidate(), survey_tie_candidate()]


__all__ = [
    "STAMP",
    "survey_graph", "survey_scope_candidate", "survey_tie_candidate", "survey_cost_candidate",
    "survey_undeclared_candidate", "survey_ledger_candidate", "survey_batch",
    "inventory_graph", "inventory_disambiguation_candidate", "inventory_author_candidate",
    "inventory_review_candidate",
]
