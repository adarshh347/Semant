"""
HARNESS-002B §5 — the nine ways a response is refused, and why each is its own type.

A normal concurrency conflict is not an error in the program. Two people answering the same
question, a stale tab, a retried POST — these are the ordinary weather of a resumable session, and
a `ValueError` would put all of them in the same bucket as a genuine bug. The integration lane has
to map them to HTTP: a stale revision is a 409 the client can recover from by re-reading, an
unknown option is a 422 the client should never have sent, and a wrong-session response is neither.

WHY NINE AND NOT "INVALID RESPONSE". Each of these tells the person on the other end a different
thing to do:

    wrong_session               you are answering someone else's question
    stale_revision              this session moved; re-read it and answer again
    duplicate_response          we already have this one; nothing was lost
    no_decision_open            nothing is waiting — your answer would land nowhere
    decision_mismatch           you answered a question this session is not currently asking
    unknown_option              that option is not on this request
    free_text_not_allowed       this fork takes a choice, not a sentence
    epistemic_status_attempted  a preference tried to say how something is KNOWN
    gate_bypass                 something tried to settle an author/ledger gate without a person

Collapsing `stale_revision` into `decision_mismatch` is the one that costs most: the first is
recoverable by refreshing and the second means the client is confused about what it is looking at,
and a UI that could not tell them apart would tell the person to retry a thing that will never work.

Every conflict can become an `InteractionRefusal` for the trace, but does not do so by itself. A
refused response is not part of the session's history until somebody decides to record it —
otherwise anything that could reach the endpoint could grow the log.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.schemas.inquiry_interaction import InteractionRefusal

# ── the closed code vocabulary, mirroring `contracts/inquiry-interaction.v1.json` ────
CONFLICT_WRONG_SESSION = "wrong_session"
CONFLICT_STALE_REVISION = "stale_revision"
CONFLICT_DUPLICATE_RESPONSE = "duplicate_response"
CONFLICT_NO_DECISION_OPEN = "no_decision_open"
CONFLICT_DECISION_MISMATCH = "decision_mismatch"
CONFLICT_UNKNOWN_OPTION = "unknown_option"
CONFLICT_FREE_TEXT_NOT_ALLOWED = "free_text_not_allowed"
CONFLICT_EPISTEMIC_STATUS_ATTEMPTED = "epistemic_status_attempted"
CONFLICT_GATE_BYPASS = "gate_bypass"

CONFLICT_CODES = (
    CONFLICT_WRONG_SESSION, CONFLICT_STALE_REVISION, CONFLICT_DUPLICATE_RESPONSE,
    CONFLICT_NO_DECISION_OPEN, CONFLICT_DECISION_MISMATCH, CONFLICT_UNKNOWN_OPTION,
    CONFLICT_FREE_TEXT_NOT_ALLOWED, CONFLICT_EPISTEMIC_STATUS_ATTEMPTED, CONFLICT_GATE_BYPASS,
)


class InteractionConflict(Exception):
    """A response this session will not accept, with what it expected and what it got.

    Deliberately NOT a subclass of `ValueError`. A caller writing `except ValueError` around a
    parse would swallow a stale revision as though it were malformed input, and the client would be
    told to fix a request that was perfectly well formed and merely late.
    """
    code = "conflict"
    #: Whether the client can succeed by re-reading the session and trying again. `stale_revision`
    #: and `duplicate_response` are recoverable in different senses and both say so; an unknown
    #: option is not, and a UI that offered "retry" for it would loop.
    recoverable = False

    def __init__(self, detail: str, *, expected: Any = None, actual: Any = None,
                 refs: Optional[List[str]] = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.expected = expected
        self.actual = actual
        self.refs = list(refs or ())

    def to_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "detail": self.detail, "expected": self.expected,
                "actual": self.actual, "refs": list(self.refs),
                "recoverable": self.recoverable}

    def as_refusal(self, *, at: str = "") -> InteractionRefusal:
        """The trace form. Recording it is the caller's explicit choice — see the module note."""
        return InteractionRefusal(
            code=self.code, what=str(self.actual if self.actual is not None else ""),
            why=self.detail,
            detail=[f"expected={self.expected!r}"] if self.expected is not None else [],
            at=at)


class WrongSession(InteractionConflict):
    code = CONFLICT_WRONG_SESSION


class StaleRevision(InteractionConflict):
    """The session moved between the client reading it and answering.

    Recoverable: re-read and answer the question that is open now. The reason this is a distinct
    type rather than a generic rejection is that it is the ONLY conflict where the right advice is
    "do the same thing again".
    """
    code = CONFLICT_STALE_REVISION
    recoverable = True


class DuplicateResponse(InteractionConflict):
    """This exact response was already applied. Nothing was lost and nothing needs redoing —
    the honest answer to a retried POST, and not a failure the person should ever see."""
    code = CONFLICT_DUPLICATE_RESPONSE
    recoverable = True


class NoDecisionOpen(InteractionConflict):
    code = CONFLICT_NO_DECISION_OPEN


class DecisionMismatch(InteractionConflict):
    code = CONFLICT_DECISION_MISMATCH


class UnknownOption(InteractionConflict):
    code = CONFLICT_UNKNOWN_OPTION


class FreeTextNotAllowed(InteractionConflict):
    code = CONFLICT_FREE_TEXT_NOT_ALLOWED


class EpistemicStatusAttempted(InteractionConflict):
    """A preference tried to carry a kind of knowing.

    The one conflict here that is about honesty rather than concurrency, and the reason it is
    refused at the door rather than downstream: by the time a status has been attached to a user's
    words and stored, every reader after that point sees a well-formed object, and no later stage
    has anything left to check it against.
    """
    code = CONFLICT_EPISTEMIC_STATUS_ATTEMPTED


class GateBypass(InteractionConflict):
    """Something tried to settle an author-exclusive or ledger-accepting fork without the person.

    Reachable from exactly one direction: a surrounding auto-mode loop asking this state machine to
    resolve a pending decision on its own. That is a reasonable thing for a loop to do for every
    OTHER kind, which is precisely why the refusal has to live here rather than in the loop's own
    good intentions.
    """
    code = CONFLICT_GATE_BYPASS


class ResponseMalformed(InteractionConflict):
    """The mapping could not be read as a response at all. Not one of the nine — it is the parse
    failure that sits before them — and kept separate so a schema violation is never reported as a
    concurrency conflict."""
    code = "response_malformed"


__all__ = [
    "CONFLICT_CODES",
    "CONFLICT_WRONG_SESSION", "CONFLICT_STALE_REVISION", "CONFLICT_DUPLICATE_RESPONSE",
    "CONFLICT_NO_DECISION_OPEN", "CONFLICT_DECISION_MISMATCH", "CONFLICT_UNKNOWN_OPTION",
    "CONFLICT_FREE_TEXT_NOT_ALLOWED", "CONFLICT_EPISTEMIC_STATUS_ATTEMPTED", "CONFLICT_GATE_BYPASS",
    "InteractionConflict", "WrongSession", "StaleRevision", "DuplicateResponse", "NoDecisionOpen",
    "DecisionMismatch", "UnknownOption", "FreeTextNotAllowed", "EpistemicStatusAttempted",
    "GateBypass", "ResponseMalformed",
]
