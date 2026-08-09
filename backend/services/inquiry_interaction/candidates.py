"""
HARNESS-002B §2 — reading a decision candidate without pretending to own the graph it came from.

The semantic compiler is being built in a parallel lane. Its schema is not merged and importing it
would couple this state machine to a shape that is still moving. So a candidate arrives here as an
OPAQUE MAPPING, is read for exactly the fields deliberation needs, and is preserved verbatim.

THE FIELD THAT IS READ AND NEVER DERIVED. `kind` is taken from what the producing lane DECLARED. It
is never inferred from the question's wording, and that is not a stylistic preference — it is the
lesson of the previous wave written down as code. In HARNESS-001B2 an epistemic demand's kind was
re-derived by substring match instead of read, `fold` matched inside `unfolding`, and a clause the
framer had explicitly refused to operationalise arrived downstream as a MEASURED criterion. Nothing
raised. The same defect here would silently reclassify an `accept_to_ledger` gate as an ordinary
fork, and auto mode would then settle it without a person — the single most consequential thing
this lane exists to prevent.

So: an absent or unknown `kind` is REFUSED BY NAME. It does not fall back to `steer_inquiry`, which
would be the harmless-looking default that turns an unreadable gate into a passable one.

WHAT `raw` IS FOR. The whole original mapping, kept on the candidate and copied onto every request
and record. This lane paraphrases a candidate into a question; `raw` is what a reader compares the
paraphrase against. A record that carried only the paraphrase would make the steward unfalsifiable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from backend.schemas.inquiry_interaction import DecisionKind, DecisionOption, InteractionRefusal

# ── refusal codes, mirroring the contract ────────────────────────────────────
REFUSAL_CANDIDATE_UNREADABLE = "candidate_unreadable"
REFUSAL_CANDIDATE_KIND_UNKNOWN = "candidate_kind_unknown"

#: The keys this lane reads. Everything else in the mapping is carried in `raw` and ignored — the
#: producing lane may say more than deliberation needs, and refusing extra keys would make every
#: addition on its side a break on ours.
READ_KEYS = ("candidate_id", "id", "kind", "question", "why_now", "affected_refs", "options",
             "allow_free_text", "blocking", "summaries", "provenance")


class CandidateUnreadable(Exception):
    """A mapping that cannot be treated as a decision candidate.

    Raised rather than skipped. A candidate silently dropped would remove a fork from the session
    with no trace, and the difference between "there was nothing to decide" and "there was
    something and we could not read it" is the difference between a finished inquiry and a
    truncated one.
    """

    def __init__(self, detail: str, *, code: str, what: str = "") -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.what = what

    def as_refusal(self, *, at: str = "") -> InteractionRefusal:
        return InteractionRefusal(code=self.code, what=self.what, why=self.detail, at=at)


@dataclass(frozen=True)
class DecisionCandidate:
    """A fork somebody upstream declared, read into the fields deliberation needs.

    `summaries` maps a graph ref to a one-line description of it. It is how the steward can name
    what a fork is ABOUT without reading into the graph: the producing lane knows what its own
    claim says, and a steward that had to summarise the claim itself would be interpreting it.
    """
    candidate_id: str
    kind: DecisionKind
    question: str
    why_now: str
    options: Tuple[DecisionOption, ...] = ()
    affected_refs: Tuple[str, ...] = ()
    allow_free_text: bool = True
    blocking: bool = True
    summaries: Mapping[str, str] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict)

    @property
    def recommended(self) -> Tuple[DecisionOption, ...]:
        return tuple(o for o in self.options if o.recommended)

    def option(self, option_id: str) -> Optional[DecisionOption]:
        for opt in self.options:
            if opt.option_id == option_id:
                return opt
        return None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _option(data: Any, *, index: int, candidate_id: str) -> DecisionOption:
    if not isinstance(data, Mapping):
        raise CandidateUnreadable(
            f"candidate {candidate_id!r} option #{index} is {type(data).__name__}, not a mapping",
            code=REFUSAL_CANDIDATE_UNREADABLE, what=candidate_id)
    option_id = _text(data.get("option_id") or data.get("id"))
    if not option_id:
        raise CandidateUnreadable(
            f"candidate {candidate_id!r} option #{index} has no option_id. A reply names an option "
            f"by id; an option without one could only be selected by its position in a list.",
            code=REFUSAL_CANDIDATE_UNREADABLE, what=candidate_id)
    consequence = _text(data.get("consequence"))
    if not consequence:
        raise CandidateUnreadable(
            f"candidate {candidate_id!r} option {option_id!r} states no consequence. An option "
            f"that does not say what it changes is a label, and a person asked to pick between "
            f"labels is being consulted in appearance only.",
            code=REFUSAL_CANDIDATE_UNREADABLE, what=option_id)
    reversible = data.get("reversible")
    return DecisionOption(
        option_id=option_id,
        label=_text(data.get("label")) or option_id,
        consequence=consequence,
        recommended=bool(data.get("recommended")),
        # None stays None. See `DecisionOption.reversible` — undeclared is not a yes.
        reversible=None if reversible is None else bool(reversible),
        authorial=bool(data.get("authorial")),
        accepts_to_ledger=bool(data.get("accepts_to_ledger")),
        affects_refs=[str(r) for r in (data.get("affects_refs") or ())],
        detail=_text(data.get("detail")))


def read(data: Any) -> DecisionCandidate:
    """One opaque mapping → one candidate, or a refusal that names what was wrong."""
    if not isinstance(data, Mapping):
        raise CandidateUnreadable(
            f"a decision candidate must be a mapping, got {type(data).__name__}",
            code=REFUSAL_CANDIDATE_UNREADABLE, what=str(data)[:80])

    candidate_id = _text(data.get("candidate_id") or data.get("id"))
    if not candidate_id:
        raise CandidateUnreadable(
            "a decision candidate has no id. Ids are what a record, a request and a response all "
            "point at; a candidate without one cannot be referred to after it is settled.",
            code=REFUSAL_CANDIDATE_UNREADABLE, what="")

    declared = _text(data.get("kind"))
    if not declared:
        raise CandidateUnreadable(
            f"candidate {candidate_id!r} declares no kind. The kind decides whether a person is "
            f"asked at all, so it is read and never guessed: an unreadable gate defaulted to an "
            f"ordinary fork is a gate auto mode would pass.",
            code=REFUSAL_CANDIDATE_KIND_UNKNOWN, what=candidate_id)
    try:
        kind = DecisionKind(declared)
    except ValueError as exc:
        raise CandidateUnreadable(
            f"candidate {candidate_id!r} declares kind {declared!r}, which is not one of "
            f"{[k.value for k in DecisionKind]}. Refused by name rather than mapped to the nearest "
            f"neighbour — a kind nobody declared is a policy nobody reviewed.",
            code=REFUSAL_CANDIDATE_KIND_UNKNOWN, what=declared) from exc

    question = _text(data.get("question"))
    if not question:
        raise CandidateUnreadable(
            f"candidate {candidate_id!r} carries no question. This lane words a fork somebody else "
            f"found; it does not invent the fork, so there is nothing here to ask about.",
            code=REFUSAL_CANDIDATE_UNREADABLE, what=candidate_id)

    options = tuple(_option(o, index=i, candidate_id=candidate_id)
                    for i, o in enumerate(data.get("options") or ()))
    seen = [o.option_id for o in options]
    if len(seen) != len(set(seen)):
        raise CandidateUnreadable(
            f"candidate {candidate_id!r} repeats an option id: {sorted(seen)}",
            code=REFUSAL_CANDIDATE_UNREADABLE, what=candidate_id)

    allow_free_text = data.get("allow_free_text")
    return DecisionCandidate(
        candidate_id=candidate_id,
        kind=kind,
        question=question,
        why_now=_text(data.get("why_now")),
        options=options,
        affected_refs=tuple(str(r) for r in (data.get("affected_refs") or ())),
        allow_free_text=True if allow_free_text is None else bool(allow_free_text),
        blocking=True if data.get("blocking") is None else bool(data.get("blocking")),
        summaries={str(k): str(v) for k, v in (data.get("summaries") or {}).items()},
        provenance=dict(data.get("provenance") or {}),
        # Verbatim, deep enough to survive the round trip a record makes it take.
        raw=dict(data))


def read_all(items: Sequence[Any]) -> Tuple[Tuple[DecisionCandidate, ...],
                                            Tuple[InteractionRefusal, ...]]:
    """Read a batch, keeping the refusals rather than letting an unreadable one abort the good ones.

    Both halves are returned because both are needed: a session that dropped four readable
    candidates because the third was malformed would be as wrong as one that dropped the third
    without saying so.
    """
    good: list = []
    bad: list = []
    for item in items:
        try:
            good.append(read(item))
        except CandidateUnreadable as exc:
            bad.append(exc.as_refusal())
    return tuple(good), tuple(bad)


__all__ = ["DecisionCandidate", "CandidateUnreadable", "read", "read_all", "READ_KEYS",
           "REFUSAL_CANDIDATE_UNREADABLE", "REFUSAL_CANDIDATE_KIND_UNKNOWN"]
