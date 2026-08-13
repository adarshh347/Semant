"""
HARNESS-002A — content-derived ids, so a replay is a comparison rather than an act of faith.

EVERY ID IN THE GRAPH IS A HASH OF ITS OWN CONTENT plus the inquiry id. There is no counter and no
clock in this module, and the omission is the feature: the directive requires that replaying a
frozen model output produce the same graph, and the cheapest way to break that is an id derived
from list position. A model that reorders two claims it considers equally important would then
renumber both, every reference to them, and the diff — while nothing about the graph had changed.

WHY THE INQUIRY ID IS MIXED IN. Without it, the same sentence compiled under two different
questions would be the same claim id. It is the same sentence and it is not the same claim: the
second inquiry asked something else of it, and merging them in any store keyed by id would silently
attribute one inquiry's evidence to another's claim.

WHY CONTENT AND NOT A UUID. Two compilations of one reading produce one graph. A claim the model
emits twice — which it does, because prose repeats — collapses to one node rather than to two
identical ones a reader has to notice are the same.

PURE. No clock, no randomness, no database, no network.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable, Sequence

#: Prefix per object kind. Pinned against the contract's `id_prefixes` by
#: `test_semantic_compilation_contract.py`, so a prefix renamed in one place fails in the other.
PREFIXES = {
    "graph": "sig_",
    "claim": "clm_",
    "claim_edge": "cle_",
    "observable": "obs_",
    "alternative": "alt_",
    "decision_candidate": "dec_",
    "refusal": "cref_",
    "reading_block": "rb_",
    "source_unit": "su_",
    "semantic_atom": "atm_",
    "coverage": "cov_",
    "pass_receipt": "pas_",
    "batch_plan": "plan_",
    "batch": "bat_",
    "reconciliation_round": "rnd_",
}

#: Twelve hex characters. The same width HARNESS-001A chose for `inq_`, for the same reason: long
#: enough that a collision inside one inquiry is not a thing that happens, short enough to read in
#: a terminal beside the sentence it names.
WIDTH = 12

_WHITESPACE = re.compile(r"\s+")


def normalise(text: Any) -> str:
    """The form a hash is taken over: lowercased, whitespace collapsed, trimmed.

    Deliberately shallow. It absorbs the differences that are typography — a model wrapping a
    sentence differently on a re-run — and absorbs nothing that is meaning. Stemming or punctuation
    stripping here would merge two claims that differ by a `not`.
    """
    return _WHITESPACE.sub(" ", str(text or "")).strip().lower()


def _digest(parts: Sequence[Any]) -> str:
    # NUL-joined. A separator that cannot occur in any of the parts, so ("ab", "c") and ("a", "bc")
    # cannot hash alike — the classic way a concatenated key quietly collides.
    payload = "\x00".join(normalise(p) for p in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:WIDTH]


def _mint(kind: str, parts: Iterable[Any]) -> str:
    return f"{PREFIXES[kind]}{_digest([kind, *parts])}"


def graph_id(inquiry_id: str, prompt: str) -> str:
    return _mint("graph", [inquiry_id, prompt])


def claim_id(inquiry_id: str, claim_kind: Any, text: str) -> str:
    """Keyed on KIND as well as text. The same sentence typed as an `interpretation` and as a
    `historical_or_sourced` claim is two different claims about the same words, and collapsing them
    would silently discard whichever the compiler emitted second."""
    return _mint("claim", [inquiry_id, getattr(claim_kind, "value", claim_kind), text])


def edge_id(inquiry_id: str, kind: Any, from_claim: str, to_claim: str) -> str:
    return _mint("claim_edge", [inquiry_id, getattr(kind, "value", kind), from_claim, to_claim])


def observable_id(inquiry_id: str, claim_id_: str, observable_kind: str,
                  targets: Sequence[str] = ()) -> str:
    """Targets are SORTED into the key. Two observables differing only in the order the model
    listed their targets are one observable, and a position-sensitive key would make a re-run of
    the same frozen output produce two."""
    return _mint("observable",
                 [inquiry_id, claim_id_, observable_kind, "|".join(sorted(normalise(t)
                                                                          for t in targets))])


def alternative_id(inquiry_id: str, owner_id: str, label: str) -> str:
    return _mint("alternative", [inquiry_id, owner_id, label])


def decision_id(inquiry_id: str, kind: Any, question: str) -> str:
    return _mint("decision_candidate", [inquiry_id, getattr(kind, "value", kind), question])


def refusal_id(inquiry_id: str, kind: Any, what: str) -> str:
    return _mint("refusal", [inquiry_id, getattr(kind, "value", kind), what])


def block_id(inquiry_id: str, kind: Any, text: str) -> str:
    return _mint("reading_block", [inquiry_id, getattr(kind, "value", kind), text])


# ── v2: the ledger ───────────────────────────────────────────────────────────

def source_unit_id(inquiry_id: str, kind: Any, source_ref: str, text: str) -> str:
    """Keyed on the source's IDENTITY and its text — never on its position in the ledger.

    A theorist that emits its blocks in a different order emits the same blocks, and a prompt whose
    clauses are re-split identically is the same prompt. An ordinal in this key would renumber a
    whole ledger over a reordering that changed nothing, and every atom anchor with it.
    """
    return _mint("source_unit", [inquiry_id, getattr(kind, "value", kind), source_ref, text])


def atom_id(inquiry_id: str, unit_kind: Any, text: str, source_unit_ids: Sequence[str] = ()) -> str:
    """Keyed on the kind, the text, and the SET of units it is anchored to.

    The anchors are sorted into the key for the same reason an observable's targets are: two atoms
    differing only in the order the dissector listed their sources are one atom. The kind is in the
    key because the same sentence read as a `visual_quality` and as an `interpretation` is two
    different readings of it, and collapsing them would discard whichever arrived second.
    """
    return _mint("semantic_atom", [inquiry_id, getattr(unit_kind, "value", unit_kind), text,
                                   "|".join(sorted(normalise(s) for s in source_unit_ids))])


def coverage_id(inquiry_id: str, source_unit_id_: str) -> str:
    """Keyed on the UNIT ALONE, deliberately.

    Exactly one disposition per unit is the ledger's central law, and an id that also hashed the
    disposition would let two contradictory entries coexist with different ids — the violation
    would still be caught, but one law would be enforced in two places and only one of them by
    construction.
    """
    return _mint("coverage", [inquiry_id, source_unit_id_])


def pass_id(inquiry_id: str, pass_name: Any, attempt: int = 1) -> str:
    """Keyed on the attempt, so the repair pass and the pass it repairs are two receipts."""
    return _mint("pass_receipt", [inquiry_id, getattr(pass_name, "value", pass_name), attempt])


# ── HARNESS-003E: the batch plan ─────────────────────────────────────────────

def batch_id(inquiry_id: str, pass_name: Any, primary_refs: Sequence[str]) -> str:
    """Keyed on the SET of items the batch is primary for — never on its position in the plan.

    The same reason `source_unit_id` refuses an ordinal. A sizing change that moves one atom from
    the third batch to the second should rename two batches, not renumber every one after it; and a
    plan whose ids moved on a re-run of identical input would make a replay a comparison of two
    different partitions rather than of the same one twice.
    """
    return _mint("batch", [inquiry_id, getattr(pass_name, "value", pass_name),
                           "|".join(sorted(normalise(r) for r in primary_refs))])


def round_id(inquiry_id: str, pass_name: Any, group_ids: Sequence[str]) -> str:
    """Keyed on the SET of batch groups the round compared. Two rounds over the same groups are one
    round asked twice, which is a fact worth collapsing rather than two comparisons."""
    return _mint("reconciliation_round", [inquiry_id, getattr(pass_name, "value", pass_name),
                                          "|".join(sorted(normalise(g) for g in group_ids))])


def plan_id(inquiry_id: str, pass_name: Any, batch_ids: Sequence[str]) -> str:
    return _mint("batch_plan", [inquiry_id, getattr(pass_name, "value", pass_name),
                                "|".join(normalise(b) for b in batch_ids)])


__all__ = ["PREFIXES", "WIDTH", "normalise", "graph_id", "claim_id", "edge_id", "observable_id",
           "alternative_id", "decision_id", "refusal_id", "block_id",
           "source_unit_id", "atom_id", "coverage_id", "pass_id",
           "batch_id", "round_id", "plan_id"]
