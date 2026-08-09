"""
HARNESS-002B §3 — the question-forming brain, and the wall around the model that may word it.

WHAT THIS ROLE DOES. It turns a fork somebody else found into a concise question where every option
says what downstream work changes. That is all. It does not decide whether to ask (the policy
does), it does not find forks (the compiler does), and it invents no option, no capability, no
claim and no evidence.

WHY THE DETERMINISTIC FORMATTER IS THE REAL ONE. It is fully capable and it is what CI runs. A
model formatter is an OPTIONAL improvement in wording, bound later by the integration lane, and the
system must be exactly as correct without it. Building the deterministic path as a stub to be
replaced would make the tests a rehearsal for a configuration nobody runs.

THE WALL. A model formatter may rephrase a question and its options. It may not:

    add an option          — a choice nobody upstream declared is a capability invented at the
                             moment of asking, and the person cannot tell it apart from a real one
    drop an option         — silently narrowing someone's choices while appearing to present them
    lose an affected ref   — the record would then point at fewer graph objects than the decision
                             actually changes, and the causal chain would be short by one link
    add a field            — every other field on a request (kind, blocking, candidate, provenance)
                             is either policy or provenance, and neither is a wording matter

A formatter that does any of these is REFUSED BY NAME onto the session, and the deterministic
request is used instead. Refused rather than repaired: a partially-accepted model output would
leave a request that is neither what the model said nor what the deterministic path would have
produced, and no reader could tell which parts came from where.

The enforcement is structural rather than textual. The formatter's return is checked against a
closed key set, so it cannot assert an epistemic status or name a capability — there is no key it
could put one in. A scan of its prose for forbidden words would be the weaker check that looks
stronger, and this repository has already paid for that mistake four times.

PURE. No database, no network, no model, no clock it was not handed. The model formatter is a
PROTOCOL here; whoever binds one supplies it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Protocol, Tuple

from backend.schemas.inquiry_interaction import (Actor, DecisionKind, DecisionOption,
                                                 DecisionRequest, InteractionMode,
                                                 InteractionRefusal, decision_id)
from backend.services.inquiry_interaction.candidates import DecisionCandidate
from backend.services.inquiry_interaction.policy import DeliberationPolicy, PolicyVerdict

# ── refusal codes, mirroring the contract ────────────────────────────────────
REFUSAL_ADDED_FIELD = "formatter_added_field"
REFUSAL_ADDED_OPTION = "formatter_added_option"
REFUSAL_DROPPED_OPTION = "formatter_dropped_option"
REFUSAL_LOST_REF = "formatter_lost_ref"
REFUSAL_EMPTIED_QUESTION = "formatter_emptied_question"

#: The only keys a formatter may return. Closed, because "may only reword" has to be a shape and
#: not an instruction — an instruction is something a model can be talked out of.
FORMATTER_FIELDS: Tuple[str, ...] = ("question", "why_now", "affected_refs", "options")

#: And the only keys it may return per option. `option_id` is present so ids can be MATCHED, never
#: so they can be changed: a formatter returning an id not in the draft is adding an option.
FORMATTER_OPTION_FIELDS: Tuple[str, ...] = ("option_id", "label", "consequence")

DETERMINISTIC = "deterministic"

#: Why each kind of fork is worth a person's attention, in one sentence, when the producing lane
#: did not supply its own. Domain-neutral by construction — no sentence here names an image, a
#: discipline or a subject matter, because a `why_now` that assumed a domain would read as
#: nonsense the first time this ran on anything else.
WHY_NOW: Dict[DecisionKind, str] = {
    DecisionKind.DISAMBIGUATE_CLAIM:
        "the two readings point at different objects, so everything asked of the evidence after "
        "this depends on which one is meant",
    DecisionKind.CHOOSE_SCOPE:
        "scope decides how much is examined and at what grain; the answer changes both the cost "
        "and what the result is a result ABOUT",
    DecisionKind.CHOOSE_OPERATIONALIZATION:
        "these are different instruments for the same claim, and they do not fail in the same "
        "ways — the choice decides what a negative result would mean",
    DecisionKind.AUTHORIZE_COST:
        "the work below this point is bounded but not free, and the bound is worth stating before "
        "it is spent",
    DecisionKind.REVIEW_RESULT:
        "a result came back that the system can describe but not judge; what happens next depends "
        "on whether it answers the question that was asked",
    DecisionKind.STEER_INQUIRY:
        "there is more than one worthwhile direction from here and no ground for preferring one, "
        "so continuing without asking would be picking silently",
    DecisionKind.REVIEW_SYNTHESIS:
        "the composed answer is about to stand as the inquiry's result, and its remainder and "
        "refusals are part of what is being agreed to",
    DecisionKind.AUTHOR_ACTION:
        "this act is the author's to make under the action grammar; nothing else may make it on "
        "their behalf",
    DecisionKind.ACCEPT_TO_LEDGER:
        "acceptance is the only path into the shared ledger, and it is not reversible by the same "
        "means it was made",
}


class RequestFormatter(Protocol):
    """The seam a model role binds to later.

    Returns a MAPPING rather than a `DecisionRequest`, deliberately. A formatter that returned the
    finished object would be trusted to have preserved the fields it must not touch, and the check
    would then have to compare two full requests and guess which differences were intentional.
    Returning a partial mapping makes "may only reword" the shape of the return value.

    An empty mapping means "no change" and is the honest way for a formatter to decline.
    """

    name: str

    def format(self, draft: DecisionRequest, *,
               candidate: DecisionCandidate) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class DeterministicFormatter:
    """The CI implementation, and the fallback whenever a model formatter is refused.

    It returns nothing because the draft is already right: the wording work happened in
    `_question` and `_why_now`, which are deterministic functions of the candidate. This class
    exists so the injected-formatter path is exercised by the default configuration rather than
    only by tests of the exception.
    """
    name: str = DETERMINISTIC

    def format(self, draft: DecisionRequest, *,
               candidate: DecisionCandidate) -> Mapping[str, Any]:
        return {}


def _question(candidate: DecisionCandidate) -> str:
    """The producing lane's question, kept. This role words a fork; it does not restate it.

    A steward that rewrote a supplied question would be paraphrasing the only sentence in the chain
    whose wording somebody deliberately chose.
    """
    return candidate.question.strip()


def _why_now(candidate: DecisionCandidate) -> str:
    """What changes downstream. Never "to be sure" and never "for confirmation".

    The declared `why_now` wins; the table is the floor. A fork with no stated consequence still
    gets a sentence about its KIND, which is checkable, rather than a hedge, which is not.
    """
    stated = candidate.why_now.strip()
    if stated:
        return stated
    return WHY_NOW[candidate.kind]


def _affected(candidate: DecisionCandidate) -> List[str]:
    """Every ref the fork touches: the candidate's own, plus every ref its options would change.

    The union rather than the declared list, because an option that changes an object the candidate
    did not list is exactly the case where a downstream reader would miss a consequence — and the
    union is computable here without reading into the graph at all.
    """
    refs: List[str] = list(candidate.affected_refs)
    for option in candidate.options:
        for ref in option.affects_refs:
            if ref not in refs:
                refs.append(ref)
    return refs


@dataclass(frozen=True)
class FormattedRequest:
    """The request, plus the refusals collected while forming it. Both, always — a refusal returned
    separately from the object it was about is a refusal somebody forgets to look at."""
    request: DecisionRequest
    refusals: Tuple[InteractionRefusal, ...] = ()


def _check(returned: Mapping[str, Any], draft: DecisionRequest, *,
           formatter: str, at: str) -> Tuple[Dict[str, Any], List[InteractionRefusal]]:
    """Validate a formatter's return against the draft. Returns (accepted, refusals).

    Refusals are non-empty exactly when `accepted` is unusable — there is no partial acceptance,
    for the reason in the module note.
    """
    refusals: List[InteractionRefusal] = []
    extra = sorted(set(returned) - set(FORMATTER_FIELDS))
    if extra:
        refusals.append(InteractionRefusal(
            code=REFUSAL_ADDED_FIELD, what=", ".join(extra), at=at,
            why=(f"formatter {formatter!r} returned {extra}, which it may not set. A formatter "
                 f"words a question; kind, blocking, provenance and the preserved candidate are "
                 f"policy and provenance, and neither is a wording matter."),
            detail=[f"allowed={list(FORMATTER_FIELDS)}"]))
        return {}, refusals

    accepted: Dict[str, Any] = {}

    if "question" in returned or "why_now" in returned:
        for field in ("question", "why_now"):
            if field not in returned:
                continue
            text = str(returned.get(field) or "").strip()
            if not text:
                refusals.append(InteractionRefusal(
                    code=REFUSAL_EMPTIED_QUESTION, what=field, at=at,
                    why=(f"formatter {formatter!r} returned an empty {field}. A question with no "
                         f"text is a pause the person cannot act on, and a session would sit at "
                         f"`awaiting_user` showing them nothing.")))
                return {}, refusals
            accepted[field] = text

    if "affected_refs" in returned:
        got = [str(r) for r in (returned.get("affected_refs") or ())]
        if set(got) != {str(r) for r in draft.affected_refs}:
            lost = sorted(set(draft.affected_refs) - set(got))
            added = sorted(set(got) - set(draft.affected_refs))
            refusals.append(InteractionRefusal(
                code=REFUSAL_LOST_REF, what=", ".join(lost or added), at=at,
                why=(f"formatter {formatter!r} changed the affected refs. The record would then "
                     f"point at a different set of graph objects than the decision actually "
                     f"changes, and the causal chain would be wrong by exactly that difference."),
                detail=[f"lost={lost}", f"added={added}"]))
            return {}, refusals
        accepted["affected_refs"] = got

    if "options" in returned:
        supplied = returned.get("options") or ()
        by_id: Dict[str, Dict[str, Any]] = {}
        for entry in supplied:
            if not isinstance(entry, Mapping):
                refusals.append(InteractionRefusal(
                    code=REFUSAL_ADDED_OPTION, what=str(entry)[:80], at=at,
                    why=f"formatter {formatter!r} returned a non-mapping option"))
                return {}, refusals
            over = sorted(set(entry) - set(FORMATTER_OPTION_FIELDS))
            if over:
                refusals.append(InteractionRefusal(
                    code=REFUSAL_ADDED_FIELD, what=", ".join(over), at=at,
                    why=(f"formatter {formatter!r} set {over} on an option. Whether an option is "
                         f"recommended, reversible, authorial or ledger-accepting is what the "
                         f"policy reads to decide if a person is needed at all — a formatter that "
                         f"could set them could talk the system out of asking."),
                    detail=[f"allowed={list(FORMATTER_OPTION_FIELDS)}"]))
                return {}, refusals
            by_id[str(entry.get("option_id") or "")] = dict(entry)

        drafted = {o.option_id for o in draft.options}
        if set(by_id) != drafted:
            invented = sorted(set(by_id) - drafted)
            dropped = sorted(drafted - set(by_id))
            refusals.append(InteractionRefusal(
                code=REFUSAL_ADDED_OPTION if invented else REFUSAL_DROPPED_OPTION,
                what=", ".join(invented or dropped), at=at,
                why=(f"formatter {formatter!r} returned a different set of options than it was "
                     f"given. An invented option is a capability nobody declared, offered to a "
                     f"person who cannot tell it from a real one; a dropped option narrows their "
                     f"choices while appearing to present them."),
                detail=[f"invented={invented}", f"dropped={dropped}"]))
            return {}, refusals
        accepted["options"] = by_id

    return accepted, refusals


@dataclass(frozen=True)
class DeliberationSteward:
    """Forms the request for one candidate. Holds no session state — the machine does."""
    policy: DeliberationPolicy
    formatter: Optional[RequestFormatter] = None

    @property
    def formatter_name(self) -> str:
        return getattr(self.formatter, "name", DETERMINISTIC) if self.formatter else DETERMINISTIC

    def draft(self, candidate: DecisionCandidate, *, session_id: str, revision: int, at: str,
              parent_event_id: str = "") -> DecisionRequest:
        """The deterministic request. Fully capable on its own; see the module note."""
        return DecisionRequest(
            decision_id=decision_id(session_id, revision, candidate.candidate_id),
            session_id=session_id,
            revision=revision,
            kind=candidate.kind,
            question=_question(candidate),
            why_now=_why_now(candidate),
            affected_refs=_affected(candidate),
            options=[o.model_copy(deep=True) for o in candidate.options],
            allow_free_text=candidate.allow_free_text,
            blocking=candidate.blocking,
            formatter=DETERMINISTIC,
            candidate=dict(candidate.raw),
            actor=Actor.STEWARD,
            parent_event_id=parent_event_id,
            created_at=at,
            provenance={"candidate_id": candidate.candidate_id,
                        "mode": self.policy.mode.value,
                        **dict(candidate.provenance)})

    def form(self, candidate: DecisionCandidate, *, session_id: str, revision: int, at: str,
             parent_event_id: str = "") -> FormattedRequest:
        """The request as the person will see it, plus any formatter refusal."""
        draft = self.draft(candidate, session_id=session_id, revision=revision, at=at,
                           parent_event_id=parent_event_id)
        if self.formatter is None:
            return FormattedRequest(request=draft)

        name = self.formatter_name
        try:
            returned = self.formatter.format(draft, candidate=candidate)
        except Exception as exc:                       # noqa: BLE001
            # A formatter that raised is a formatter that did not word the question. The
            # deterministic request stands and the failure is on the session rather than in a log
            # nobody reads — a wording step is never allowed to take a session down.
            return FormattedRequest(request=draft, refusals=(InteractionRefusal(
                code=REFUSAL_EMPTIED_QUESTION, what=name, at=at,
                why=f"formatter {name!r} raised {type(exc).__name__}: {exc}"),))

        if not isinstance(returned, Mapping):
            return FormattedRequest(request=draft, refusals=(InteractionRefusal(
                code=REFUSAL_ADDED_FIELD, what=type(returned).__name__, at=at,
                why=f"formatter {name!r} returned {type(returned).__name__}, not a mapping"),))

        accepted, refusals = _check(returned, draft, formatter=name, at=at)
        if refusals:
            return FormattedRequest(request=draft, refusals=tuple(refusals))
        if not accepted:
            return FormattedRequest(request=draft)

        options = draft.options
        if "options" in accepted:
            by_id = accepted["options"]
            options = []
            for option in draft.options:
                said = by_id.get(option.option_id) or {}
                # Only the two wording fields are taken. `recommended`, `reversible`, `authorial`
                # and `accepts_to_ledger` come from the draft unchanged, so a formatter cannot
                # change what the policy reads.
                options.append(option.model_copy(update={
                    "label": str(said.get("label") or option.label).strip() or option.label,
                    "consequence": (str(said.get("consequence") or option.consequence).strip()
                                    or option.consequence)}))

        worded = draft.model_copy(update={
            "question": accepted.get("question", draft.question),
            "why_now": accepted.get("why_now", draft.why_now),
            "affected_refs": accepted.get("affected_refs", list(draft.affected_refs)),
            "options": options,
            "formatter": name})
        return FormattedRequest(request=worded)

    def verdict(self, candidate: DecisionCandidate) -> PolicyVerdict:
        return self.policy.verdict(candidate)


__all__ = ["DeliberationSteward", "RequestFormatter", "DeterministicFormatter", "FormattedRequest",
           "FORMATTER_FIELDS", "FORMATTER_OPTION_FIELDS", "WHY_NOW", "DETERMINISTIC",
           "REFUSAL_ADDED_FIELD", "REFUSAL_ADDED_OPTION", "REFUSAL_DROPPED_OPTION",
           "REFUSAL_LOST_REF", "REFUSAL_EMPTIED_QUESTION"]
