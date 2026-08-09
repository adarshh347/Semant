"""
HARNESS-002D — Lane A's decision candidates, read as Lane B's forks.

THE THREE LANES NAMED OVERLAPPING VOCABULARIES IN PARALLEL and only one of them had a contract.
Lane B's nine decision kinds are declared in `contracts/inquiry-interaction.v1.json` and its pause
CLASSIFICATION IS KEYED ON THE KIND — so the kind is not a label, it is the policy. Lane A's four
and Lane C's six were each guessed from the board's single worked example. Lane B's are canonical
and this module is the translation, in one place, tested in both directions.

    choose_operationalization   →  choose_operationalization
    choose_image_scope          →  choose_scope
    resolve_ambiguous_term      →  disambiguate_claim
    confirm_author_exclusive_act→  author_action

A kind outside the four is NOT mapped to a neighbour. It is passed through verbatim so that Lane B
refuses it by name — its own rule, and the third instance of the read-don't-derive defect the
HARNESS-001B2 finding named.

## The reversibility gap, and why this lane may close it

Lane B's central finding: `DecisionOption.reversible` is `Optional[bool]`, and `None` — the
producing lane never said — is treated as blocking. *"Fix the producer, not the policy."*

**Lane A's `OperationalAlternative` has no `reversible` field at all.** Every candidate a semantic
compiler produces therefore arrives undeclared, and auto mode can never settle one. That is the
policy working exactly as designed, and it means Phase 1 has no auto vertical unless somebody
declares reversibility somewhere.

This lane declares it, and the justification is structural rather than an opinion about Lane A's
option. In Phase 1 the entire downstream consequence of choosing an operationalization is that ONE
LOCKED FIXTURE ADAPTER produces a simulated receipt: nothing is written, nothing is accepted, no
post changes, and the session is append-only history. A choice whose only effect is a stand-in is
reversible by construction.

So the rule is narrow and checkable:

  · `reversible=True` only when the candidate's kind is not a gate AND every one of the option's
    capability classes is one the locked fixture adapter serves;
  · otherwise the field stays absent, and Lane B's policy pauses exactly as it should;
  · and the declaration is stamped into the candidate's `provenance` naming THIS lane, so a reader
    of the record can see that the reversibility was asserted at the execution boundary rather
    than by the compiler that proposed the option.

Declaring it silently would be the thing Lane B forbids. Declaring it, narrowly, with the reason
attached, is the fix it asks for.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

#: Lane A's `DecisionKind` → Lane B's. Semantically exact; nothing is approximated.
KIND_MAP: Dict[str, str] = {
    "choose_operationalization": "choose_operationalization",
    "choose_image_scope": "choose_scope",
    "resolve_ambiguous_term": "disambiguate_claim",
    "confirm_author_exclusive_act": "author_action",
}

#: Kinds only a person may settle, whatever anything else declares. Restated from Lane B's contract
#: rather than imported, because this module must be able to refuse to declare reversibility for
#: one even if the contract file is unreadable — and `policy.is_gate` would raise in that case.
GATE_KINDS = frozenset({"author_action", "accept_to_ledger"})

PROVENANCE_PRODUCER = "inquiry_session/candidates-v1"

REVERSIBLE_WHY = (
    "declared reversible by the Phase 1 integration, not by the compiler: the whole downstream "
    "consequence of this choice is one locked fixture capability producing a simulated receipt. "
    "Nothing is written, nothing is accepted, and no post changes."
)


def _consequence_of(alternative: Mapping[str, Any]) -> str:
    """Lane B refuses an option that states no consequence, and it is right to: an option that does
    not say what it changes is a label, and a person picking between labels is being consulted in
    appearance only.

    Lane A's `consequence` defaults to `""`. Rather than invent one, this falls back to the
    alternative's own `description` and then gives up — a candidate whose options say nothing is
    refused by Lane B, by name, and that refusal lands on the session where a reader can see it.
    """
    for key in ("consequence", "description"):
        value = str(alternative.get(key) or "").strip()
        if value:
            return value
    return ""


def _option(alternative: Mapping[str, Any], *, servable: bool, gate: bool) -> Dict[str, Any]:
    option: Dict[str, Any] = {
        "option_id": str(alternative.get("alternative_id") or alternative.get("option_id") or ""),
        "label": str(alternative.get("label") or "").strip(),
        "consequence": _consequence_of(alternative),
        "recommended": bool(alternative.get("recommended")),
        "detail": ", ".join(str(c) for c in alternative.get("capability_classes") or ()),
    }
    if servable and not gate:
        option["reversible"] = True
    return option


def alternatives_index(graph: Mapping[str, Any]) -> Dict[str, List[str]]:
    """Normalised option label → the capability classes the OBSERVABLE declares for it.

    A decision's options and an observable's alternatives are the same choice written twice, and
    only the observable's copy carries capability classes. They cannot be matched by id: Lane A
    mints `alternative_id` from `(inquiry, OWNER, label)`, and the owner is the decision in one case
    and the observable in the other — so the same choice has two ids by construction.

    The label is the only link, and it is a real one rather than a guess: the compiler emits one
    label for one alternative and writes it into both places. A label that matches nothing leaves
    the option undeclared, which pauses — the safe direction.
    """
    index: Dict[str, List[str]] = {}
    for observable in graph.get("observables") or ():
        if not isinstance(observable, Mapping):
            continue
        for alternative in observable.get("alternatives") or ():
            if not isinstance(alternative, Mapping):
                continue
            label = " ".join(str(alternative.get("label") or "").split()).strip().lower()
            if label:
                index.setdefault(label, [str(c) for c in
                                         alternative.get("capability_classes") or ()])
    return index


def as_candidate(decision: Mapping[str, Any], *, servable_classes: Sequence[str],
                 summaries: Optional[Mapping[str, str]] = None,
                 classes_by_label: Optional[Mapping[str, Sequence[str]]] = None) -> Dict[str, Any]:
    """One Lane A `DecisionCandidate` mapping → one Lane B candidate mapping.

    `servable_classes` is what the locked capability adapter can actually stand in for. An option
    asking for something outside it is left undeclared, so the policy pauses — which is correct:
    choosing a route this phase cannot even simulate is not a reversible choice, it is a choice to
    get nothing.
    """
    raw_kind = str(decision.get("kind") or "")
    kind = KIND_MAP.get(raw_kind, raw_kind)
    gate = kind in GATE_KINDS
    servable = set(str(c) for c in servable_classes)

    by_label = {str(k): [str(c) for c in v] for k, v in (classes_by_label or {}).items()}
    options: List[Dict[str, Any]] = []
    for alternative in decision.get("options") or decision.get("alternatives") or ():
        if not isinstance(alternative, Mapping):
            continue
        label = " ".join(str(alternative.get("label") or "").split()).strip().lower()
        classes = {str(c) for c in alternative.get("capability_classes") or ()} \
            or set(by_label.get(label, ()))
        options.append(_option(alternative, gate=gate,
                               servable=bool(classes) and classes <= servable))

    return {
        "candidate_id": str(decision.get("decision_id") or decision.get("candidate_id") or ""),
        "kind": kind,
        "question": str(decision.get("question") or ""),
        "why_now": str(decision.get("why_now") or ""),
        "options": options,
        "affected_refs": [str(r) for r in decision.get("affected_refs") or ()],
        "allow_free_text": bool(decision.get("allow_free_text", True)),
        "blocking": bool(decision.get("blocking", False)),
        "summaries": dict(summaries or {}),
        "provenance": {
            "producer": PROVENANCE_PRODUCER,
            "compiler_kind": raw_kind,
            "kind_translated": raw_kind != kind,
            # Stamped whenever this lane asserted reversibility, so the record shows WHO said it.
            **({"reversible_declared_by": PROVENANCE_PRODUCER, "reversible_why": REVERSIBLE_WHY}
               if any("reversible" in o for o in options) else {}),
        },
    }


def from_graph(graph: Mapping[str, Any], *, servable_classes: Sequence[str]) -> List[Dict[str, Any]]:
    """Every decision candidate in a semantic inquiry graph, as Lane B forks.

    `summaries` is built from the graph's own claims and observables — the producing lane knows
    what its claim says, and a steward that had to summarise a claim itself would be interpreting
    it. Lane B's `DecisionCandidate.summaries` exists for exactly this.
    """
    summaries: Dict[str, str] = {}
    for claim in graph.get("claims") or ():
        if isinstance(claim, Mapping) and claim.get("claim_id"):
            summaries[str(claim["claim_id"])] = str(claim.get("text") or "")
    for observable in graph.get("observables") or ():
        if isinstance(observable, Mapping) and observable.get("observable_id"):
            summaries[str(observable["observable_id"])] = str(
                observable.get("observable_kind") or "")
    by_label = alternatives_index(graph)
    return [as_candidate(d, servable_classes=servable_classes, summaries=summaries,
                         classes_by_label=by_label)
            for d in graph.get("decision_candidates") or () if isinstance(d, Mapping)]


__all__ = ["KIND_MAP", "GATE_KINDS", "PROVENANCE_PRODUCER", "REVERSIBLE_WHY", "alternatives_index", "as_candidate",
           "from_graph"]
