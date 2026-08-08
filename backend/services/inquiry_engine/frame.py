"""
HARNESS-001B §3 — `InquiryFrame` intake, built to be parallel-safe.

Lane A produces an `InquiryFrame`. This lane consumes it BY SHAPE, and must not import Lane A until
Lane A merges — the two sessions are running at the same time. So the contract here is the minimum
shape pinned in `HARNESS-001-three-lane-board.md` and nothing more:

    schema_version="inquiry-frame.v1", inquiry_id, prompt, mode, attentions, epistemic_demands,
    proposed_actions, unresolved_terms, semantic_remainder, provenance

## The intake adapter owns representation adjustment. Not either engine.

That sentence in the directive is the whole reason this module is separate from `engine.py`. Lane A
will emit *something* for `attentions` — bare strings, or `{"text": …}`, or `{"phrase": …, "span":
…}` — and B cannot know which while both are being built. So every list field is normalised HERE,
permissively, and the ORIGINAL is kept verbatim on the accepted frame. When Lane A merges, the
cross-lane test passes `InquiryFrame.model_dump()` through this function unchanged; if the shape
differs from the guess, the fix is a normaliser in this file and nothing downstream moves.

Extra keys are carried, never rejected. A frame richer than the minimum is Lane A doing its job.

## What intake refuses

Only what makes the frame unreadable: a wrong `schema_version`, a missing required key, an empty
prompt. It does NOT refuse an empty `proposed_actions` — a prompt that yields no grammar-valid act
is a real and interesting frame, and the honest run over it produces no evidence goals and stops
`exhausted` rather than inventing work.

THE PROMPT IS PRESERVED BYTE FOR BYTE. Nothing here rewrites, expands or "clarifies" it. A refusal
downstream is only checkable against what was actually asked.

PURE. No database, no network, no model, no clock it was not handed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Tuple

SCHEMA_VERSION = "inquiry-frame.v1"

#: The ten keys the board pins. Required as KEYS, not as non-empty values — an empty
#: `unresolved_terms` is a claim ("nothing was left unresolved"), and a missing one is a frame that
#: cannot make that claim. Those differ, and only the second is refused.
REQUIRED_KEYS: Tuple[str, ...] = (
    "schema_version", "inquiry_id", "prompt", "mode", "attentions", "epistemic_demands",
    "proposed_actions", "unresolved_terms", "semantic_remainder", "provenance",
)

#: Keys a mapping entry may carry the text under, tried in order. Wider than any one guess about
#: Lane A on purpose: an intake that refused an unexpected spelling would stall this lane on
#: another lane's naming choice.
_TEXT_KEYS: Tuple[str, ...] = ("text", "phrase", "term", "value", "name", "label", "clause")

#: Lane A's `DemandKind` → this engine's clause mode. RECONCILED AGAINST THE MERGED TREE, and the
#: first row is the one that matters:
#:
#:   `measurable` is not `measured`, and Lane A says so on purpose — nothing has run, so the frame
#:   states a CAPACITY where this engine states a CLAIM. The demand asks for measured evidence; the
#:   criterion demanding it is what the evaluator later checks against what an organ actually
#:   returned. Mapping the two is the whole job of this table.
#:
#:   `unresolved` has no counterpart here at all, and that absence is Lane A's own finding: "no
#:   producer exists" is a capability gap declared UPSTREAM. It is transported, not re-adjudicated —
#:   see `Demand.declares_gap`.
DEMAND_KIND_TO_CLAUSE: Dict[str, str] = {
    "measurable": "measured",
    "interpretive": "interpretive",
    "sourced": "sourced",
    "imagined": "imagined",
}

#: The `DemandKind` that is a gap rather than a clause.
DEMAND_KIND_UNRESOLVED = "unresolved"


class FrameRefused(Exception):
    """A mapping that cannot be read as an inquiry frame. Raised rather than partially accepted:
    a half-read frame would produce a run whose gaps are artefacts of the intake."""


def _plain(value: Any) -> Any:
    """An enum member down to its value; anything else unchanged.

    `InquiryFrame.model_dump()` — the plain call, which is what Lane A hands over and what the
    directive says to pass unaltered — leaves `mode` as an `InquiryMode` member, not a string.
    `InquiryMode` subclasses `str`, so `str(member)` is `'InquiryMode.EXPLORE'` and NOT `'explore'`:
    the coercion looks like it worked and produces a mode nothing downstream can match. Only
    `model_dump(mode="json")` flattens it, and requiring that of the caller would put the seam's
    representation problem in the caller's hands.
    """
    return getattr(value, "value", value)


def _text_of(entry: Any) -> str:
    """The words in an entry, whatever shape Lane A wrapped them in."""
    entry = _plain(entry)
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, Mapping):
        for key in _TEXT_KEYS:
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _texts(raw: Any) -> Tuple[str, ...]:
    if not isinstance(raw, (list, tuple)):
        return ()
    out = [_text_of(e) for e in raw]
    return tuple(t for t in out if t)


@dataclass(frozen=True)
class Demand:
    """One `epistemic_demands` entry, with the KIND Lane A declared rather than one guessed here.

    The first version of this intake flattened a demand to its words and re-derived the kind by
    matching the term against this engine's own need table. Against Lane A's real output that was
    not merely lossy, it was WRONG IN THE DANGEROUS DIRECTION: Lane A marks "way of unfolding" as
    `unresolved` ("names a MANNER … no act in the grammar and no organ in the sensorium is scoped to
    a manner"), and substring matching found `fold` inside `unfolding` and produced a MEASURED
    criterion. A clause the framer explicitly refused to operationalise became one this engine would
    report having produced.

    So the kind is READ. `why` is Lane A's own reason and is carried verbatim, because when the
    demand is a gap it is Lane A's finding that is being transported and a paraphrase would make it
    look like this engine's conclusion.
    """
    text: str
    kind: str = ""
    clause: str = ""
    why: str = ""

    @property
    def declares_gap(self) -> bool:
        """Lane A said no producer exists. Not a weak measurement — the absence of an instrument."""
        return self.kind == DEMAND_KIND_UNRESOLVED

    @property
    def mode(self) -> str:
        """The clause mode, or empty when Lane A declared none and the caller must decide."""
        return DEMAND_KIND_TO_CLAUSE.get(self.kind, "")

    def to_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "kind": self.kind, "clause": self.clause, "why": self.why}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Demand":
        return cls(text=str(d.get("text") or ""), kind=str(d.get("kind") or ""),
                   clause=str(d.get("clause") or ""), why=str(d.get("why") or ""))


def _demand_of(entry: Any) -> Demand:
    """One demand, with its kind read through `_plain`.

    `_plain` is not optional here, and it is the SAME defect it was written for one field over.
    `model_dump()` — the plain call the directive says to pass unaltered — leaves `kind` as a
    `DemandKind` member, and `DemandKind` subclasses `str`, so `str(member)` is
    `'DemandKind.INTERPRETIVE'` rather than `'interpretive'`. The coercion looks like it worked and
    yields a kind matching nothing in `DEMAND_KIND_TO_CLAUSE`, so every demand would fall silently
    through to the re-derived guess this type exists to replace.
    """
    if isinstance(entry, str):
        return Demand(text=entry.strip())
    if isinstance(entry, Mapping):
        return Demand(text=_text_of(entry), kind=str(_plain(entry.get("kind")) or "").strip(),
                      clause=str(_plain(entry.get("clause")) or "").strip(),
                      why=str(_plain(entry.get("why")) or "").strip())
    return Demand(text="")


@dataclass(frozen=True)
class Term:
    """One `unresolved_terms` entry: the word, and Lane A's reason nothing can operationalise it.

    `why` is the load-bearing half. Lane A has already done the work of saying WHY "fold-level"
    cannot be acted on ("names a LEVEL OF ANALYSIS rather than a thing in a picture"); an intake
    that kept only the word would make this engine re-derive a worse version of that reason, or
    report the term as an unknown instrument — which reads as a table error here rather than as a
    finding there.
    """
    text: str
    why: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "why": self.why}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Term":
        return cls(text=str(d.get("text") or ""), why=str(d.get("why") or ""))


def _term_of(entry: Any) -> Term:
    if isinstance(entry, str):
        return Term(text=entry.strip())
    if isinstance(entry, Mapping):
        return Term(text=_text_of(entry), why=str(_plain(entry.get("why")) or "").strip())
    return Term(text="")


@dataclass(frozen=True)
class ProposedAction:
    """One grammar-valid act Lane A proposed, normalised to (type, role, phrase) + the original.

    `raw` is kept because the capability resolver reports the ACT it refused, and reporting a
    normalisation of it would make the refusal describe something the curator never saw.
    """
    type: str
    role: str = ""
    phrase: str = ""
    target: str = ""
    source: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "role": self.role, "phrase": self.phrase,
                "target": self.target, "source": self.source, "raw": dict(self.raw)}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "ProposedAction":
        return cls(type=str(d.get("type") or ""), role=str(d.get("role") or ""),
                   phrase=str(d.get("phrase") or ""), target=str(d.get("target") or ""),
                   source=str(d.get("source") or ""), raw=dict(d.get("raw") or {}))


#: Where a Perceptual Action Grammar act keeps its role and its words. The grammar declares its
#: `enums` per PAYLOAD key (`payload.field_role`, `payload.relation_role`), so the payload is the
#: real home of both; the top level is tried first only so a caller that flattens an act by hand
#: keeps working.
_ROLE_KEYS: Tuple[str, ...] = ("role", "field_role", "trace_role", "relation_role", "mode",
                               "challenge_type", "requested_reading_type")
_PHRASE_KEYS: Tuple[str, ...] = ("phrase", "text", "query", "label", "draft_text")


def _first_of(sources: Tuple[Mapping[str, Any], ...], keys: Tuple[str, ...]) -> str:
    for source in sources:
        for key in keys:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _action_of(entry: Any) -> ProposedAction:
    """One act, normalised to (type, role, phrase) + the original.

    IT LOOKS IN THE PAYLOAD, and that is the whole A→B reconciliation. Reading only the top level
    made every real `brush_field` arrive with an empty role and an empty phrase, and
    `derive_goals` names a goal from `action.phrase or action.role`: the acts survived the seam
    and the words inside them did not, so a goal derived from "brush the fold" was
    indistinguishable from one derived from an act that said nothing at all.
    """
    if isinstance(entry, str):
        return ProposedAction(type=entry.strip(), raw={"type": entry.strip()})
    if isinstance(entry, Mapping):
        raw = {str(k): v for k, v in entry.items()}
        payload = entry.get("payload")
        sources: Tuple[Mapping[str, Any], ...] = (
            (entry, payload) if isinstance(payload, Mapping) else (entry,))
        return ProposedAction(
            type=str(entry.get("type") or entry.get("action") or "").strip(),
            role=_first_of(sources, _ROLE_KEYS),
            phrase=_first_of(sources, _PHRASE_KEYS),
            target=str(entry.get("target") or "").strip(),
            source=str(entry.get("source") or "").strip(),
            raw=raw)
    return ProposedAction(type="", raw={})


@dataclass(frozen=True)
class AcceptedFrame:
    """A frame this lane can run on, plus the mapping it came from, unaltered.

    `raw` is the whole point of the pairing. The `InquiryRun` carries it verbatim, so a reader can
    check every derived goal against the frame that produced it — and, when Lane A lands, diff the
    real frame against what this intake made of it.
    """
    inquiry_id: str
    prompt: str
    mode: str
    attentions: Tuple[str, ...] = ()
    epistemic_demands: Tuple[Demand, ...] = ()
    proposed_actions: Tuple[ProposedAction, ...] = ()
    unresolved_terms: Tuple[Term, ...] = ()
    semantic_remainder: Tuple[str, ...] = ()
    provenance: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)
    #: What the intake had to reshape to read this frame. Empty on a frame that already matched.
    #: Non-empty is not an error — it is the adjustment this module exists to own, said out loud so
    #: the A→B seam is inspectable rather than assumed.
    adjustments: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "inquiry_id": self.inquiry_id,
            "prompt": self.prompt,
            "mode": self.mode,
            "attentions": list(self.attentions),
            "epistemic_demands": [d.to_dict() for d in self.epistemic_demands],
            "proposed_actions": [a.to_dict() for a in self.proposed_actions],
            "unresolved_terms": [t.to_dict() for t in self.unresolved_terms],
            "semantic_remainder": list(self.semantic_remainder),
            "provenance": dict(self.provenance),
            "raw": dict(self.raw),
            "adjustments": list(self.adjustments),
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "AcceptedFrame":
        return cls(
            inquiry_id=str(d.get("inquiry_id") or ""),
            prompt=str(d.get("prompt") or ""),
            mode=str(d.get("mode") or ""),
            attentions=tuple(str(a) for a in d.get("attentions") or ()),
            epistemic_demands=tuple(Demand.from_dict(a)
                                    for a in d.get("epistemic_demands") or ()),
            proposed_actions=tuple(ProposedAction.from_dict(a)
                                   for a in d.get("proposed_actions") or ()),
            unresolved_terms=tuple(Term.from_dict(a) for a in d.get("unresolved_terms") or ()),
            semantic_remainder=tuple(str(a) for a in d.get("semantic_remainder") or ()),
            provenance=dict(d.get("provenance") or {}),
            raw=dict(d.get("raw") or {}),
            adjustments=tuple(str(a) for a in d.get("adjustments") or ()))


def accept(mapping: Mapping[str, Any]) -> AcceptedFrame:
    """A validated mapping → a frame this lane can run on. The A→B seam, in one function.

    Refuses only what makes the frame unreadable. Everything else is normalised and recorded.
    """
    if not isinstance(mapping, Mapping):
        raise FrameRefused(
            f"an inquiry frame must be a mapping; got {type(mapping).__name__}. Lane B accepts any "
            f"validated mapping of the pinned shape and does not import Lane A.")

    version = str(mapping.get("schema_version") or "")
    if version != SCHEMA_VERSION:
        raise FrameRefused(
            f"schema_version {version!r} — this intake reads {SCHEMA_VERSION!r} and nothing else. "
            f"A frame from a different contract read leniently would produce goals derived from "
            f"fields that mean something else.")

    missing = [k for k in REQUIRED_KEYS if k not in mapping]
    if missing:
        raise FrameRefused(
            f"the frame is missing {missing}. These are KEYS, not values: an empty "
            f"`unresolved_terms` is the claim that nothing was left unresolved, and a missing one "
            f"is a frame that cannot make that claim.")

    prompt = str(mapping.get("prompt") or "")
    if not prompt.strip():
        raise FrameRefused(
            "the frame carries no prompt. Everything this lane refuses downstream is only checkable "
            "against what was actually asked, so a run with nothing to check against is refused "
            "here rather than reported as an inquiry into nothing.")

    adjustments: List[str] = []

    def _list(key: str) -> Tuple[str, ...]:
        raw = mapping.get(key)
        texts = _texts(raw)
        if isinstance(raw, (list, tuple)) and any(not isinstance(e, str) for e in raw):
            adjustments.append(f"{key}: read the words out of {len(raw)} structured entr(ies)")
        return texts

    def _typed(key: str, build):
        raw = mapping.get(key)
        if not isinstance(raw, (list, tuple)):
            return ()
        if any(not isinstance(e, str) for e in raw):
            adjustments.append(f"{key}: read the words out of {len(raw)} structured entr(ies)")
        return tuple(v for v in (build(e) for e in raw) if v.text)

    actions_raw = mapping.get("proposed_actions")
    actions = tuple(_action_of(a) for a in actions_raw) if isinstance(actions_raw, (list, tuple)) \
        else ()
    unnamed = [i for i, a in enumerate(actions) if not a.type]
    if unnamed:
        adjustments.append(
            f"proposed_actions: {len(unnamed)} entr(ies) carried no readable action type and will "
            f"be refused by name rather than dropped")
    roled = [a for a in actions if a.role and not isinstance(a.raw.get("role"), str)]
    if roled:
        adjustments.append(
            f"proposed_actions: read the role out of `payload` for {len(roled)} act(s) — the "
            f"grammar's own wire shape nests it there")

    demands = _typed("epistemic_demands", _demand_of)
    declared = [d for d in demands if d.kind]
    if declared:
        adjustments.append(
            f"epistemic_demands: {len(declared)} of {len(demands)} carried a declared kind, which "
            f"is READ rather than re-derived from the term")

    return AcceptedFrame(
        inquiry_id=str(mapping.get("inquiry_id") or ""),
        prompt=prompt,                       # VERBATIM. Never rewritten, expanded or clarified.
        mode=str(_plain(mapping.get("mode")) or "explore"),
        attentions=_list("attentions"),
        epistemic_demands=demands,
        proposed_actions=actions,
        unresolved_terms=_typed("unresolved_terms", _term_of),
        semantic_remainder=_list("semantic_remainder"),
        provenance=dict(mapping.get("provenance") or {}),
        raw={str(k): v for k, v in mapping.items()},
        adjustments=tuple(adjustments))


__all__ = ["SCHEMA_VERSION", "REQUIRED_KEYS", "DEMAND_KIND_TO_CLAUSE", "DEMAND_KIND_UNRESOLVED",
           "FrameRefused", "ProposedAction", "Demand", "Term", "AcceptedFrame", "accept"]
