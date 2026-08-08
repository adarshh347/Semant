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


class FrameRefused(Exception):
    """A mapping that cannot be read as an inquiry frame. Raised rather than partially accepted:
    a half-read frame would produce a run whose gaps are artefacts of the intake."""


def _text_of(entry: Any) -> str:
    """The words in an entry, whatever shape Lane A wrapped them in."""
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


def _action_of(entry: Any) -> ProposedAction:
    if isinstance(entry, str):
        return ProposedAction(type=entry.strip(), raw={"type": entry.strip()})
    if isinstance(entry, Mapping):
        raw = {str(k): v for k, v in entry.items()}
        return ProposedAction(
            type=str(entry.get("type") or entry.get("action") or "").strip(),
            role=str(entry.get("role") or entry.get("field_role") or
                     entry.get("relation_role") or "").strip(),
            phrase=str(entry.get("phrase") or entry.get("text") or
                       entry.get("query") or "").strip(),
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
    epistemic_demands: Tuple[str, ...] = ()
    proposed_actions: Tuple[ProposedAction, ...] = ()
    unresolved_terms: Tuple[str, ...] = ()
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
            "epistemic_demands": list(self.epistemic_demands),
            "proposed_actions": [a.to_dict() for a in self.proposed_actions],
            "unresolved_terms": list(self.unresolved_terms),
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
            epistemic_demands=tuple(str(a) for a in d.get("epistemic_demands") or ()),
            proposed_actions=tuple(ProposedAction.from_dict(a)
                                   for a in d.get("proposed_actions") or ()),
            unresolved_terms=tuple(str(a) for a in d.get("unresolved_terms") or ()),
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

    actions_raw = mapping.get("proposed_actions")
    actions = tuple(_action_of(a) for a in actions_raw) if isinstance(actions_raw, (list, tuple)) \
        else ()
    unnamed = [i for i, a in enumerate(actions) if not a.type]
    if unnamed:
        adjustments.append(
            f"proposed_actions: {len(unnamed)} entr(ies) carried no readable action type and will "
            f"be refused by name rather than dropped")

    return AcceptedFrame(
        inquiry_id=str(mapping.get("inquiry_id") or ""),
        prompt=prompt,                       # VERBATIM. Never rewritten, expanded or clarified.
        mode=str(mapping.get("mode") or "explore"),
        attentions=_list("attentions"),
        epistemic_demands=_list("epistemic_demands"),
        proposed_actions=actions,
        unresolved_terms=_list("unresolved_terms"),
        semantic_remainder=_list("semantic_remainder"),
        provenance=dict(mapping.get("provenance") or {}),
        raw={str(k): v for k, v in mapping.items()},
        adjustments=tuple(adjustments))


__all__ = ["SCHEMA_VERSION", "REQUIRED_KEYS", "FrameRefused", "ProposedAction",
           "AcceptedFrame", "accept"]
