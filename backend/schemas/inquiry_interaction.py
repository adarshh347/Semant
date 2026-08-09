"""
HARNESS-002B — the typed shape of a moment where a person's decision changes the inquiry.

WHAT THIS IS. The contract for deliberation: a concrete fork, the options it offers, what each
option would change downstream, the reply, and the append-only record of who chose. It is the
missing half of an inquiry that can otherwise only ever proceed or stop.

WHAT IT IS NOT, and every model below is shaped by this:

  · It is not the Director's `Question`. That type names a verified-missing execution PARAM which
    a person can supply so a blocked run resumes — narrow, proven, and deliberately not widened
    here. Semantic deliberation is choosing an interpretation, a scope, an operationalisation, a
    judgement of a result or a direction, and none of those is a missing phrase.
  · It is not evidence, and nothing here can become evidence. A person's direction changes WHICH
    goals are pursued; it never changes what anything is known BY. `DecisionResponse` and
    `UserAmendment` both refuse a provenance carrying an epistemic status, because provenance is
    the one free-form dict on either object and therefore the only place a status could arrive.
  · It is not the semantic graph. Claims and observables are referenced BY ID and never restated,
    so this lane holds no opinion about their shape and cannot drift from whoever owns it.

THE TWO FIELDS THAT ARE EASIEST TO GET WRONG.

  `DecisionOption.reversible` is `Optional[bool]` and the None is load-bearing. An option that
  never declared whether it can be undone is NOT thereby reversible, and auto mode refuses to
  choose it. A default of True would make every under-specified candidate silently auto-chosen —
  the direction of a default is where an engine's honesty actually lives.

  `revision` counts accepted TURNS, not events. One response appends several events (the response,
  its record, perhaps an amendment) and increments `revision` exactly once, so the number a client
  holds and the number it must send back are about the same thing: how many times this session has
  been moved by someone.

STRICT. Every model forbids unknown fields. A key nobody declared is exactly how a status, a
capability name or a fabricated option would arrive.
"""
from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "inquiry-interaction.v1"


# ── the closed vocabularies ──────────────────────────────────────────────────

class InteractionMode(str, Enum):
    """How much of the deliberation the person wants to be part of.

    Not a verbosity setting. `auto` still stops at author/ledger gates, and `step` is a research
    instrument — it exposes every declared fork so a person debugging the chain can see the ones a
    policy would have taken silently.
    """
    AUTO = "auto"
    CONSULT = "consult"
    STEP = "step"


class SessionState(str, Enum):
    """Where the session is. Twelve, and the ones that look redundant are not:

    `ready` is "nothing is blocking, work may be commissioned"; `complete` is "an answer exists";
    `exhausted` is "no answer exists and nothing further will be tried" — the distinction the goal
    engine already keeps between `satisfied` and `exhausted`, held at session scale.
    `refused` is a law saying no; `error` is machinery failing. Collapsing those two would let a
    crash read as a principled refusal.
    """
    FRAMING = "framing"
    READING = "reading"
    COMPILING = "compiling"
    AWAITING_USER = "awaiting_user"
    READY = "ready"
    EXECUTING = "executing"
    JUDGING = "judging"
    COMPOSING = "composing"
    COMPLETE = "complete"
    EXHAUSTED = "exhausted"
    REFUSED = "refused"
    ERROR = "error"


#: States from which nothing further happens. A session parked in one of these does not take
#: candidates or responses; offering it either is a caller bug and is refused by name.
TERMINAL_STATES: Tuple[SessionState, ...] = (
    SessionState.COMPLETE, SessionState.EXHAUSTED, SessionState.REFUSED, SessionState.ERROR,
)


class DecisionKind(str, Enum):
    """What the person is being asked to settle.

    Nine rather than "a question", because the KIND is what decides whether to ask at all: the
    pause classification in `contracts/inquiry-interaction.v1.json` is keyed on exactly this, and a
    free-text kind would be a policy nobody could review.
    """
    DISAMBIGUATE_CLAIM = "disambiguate_claim"
    CHOOSE_SCOPE = "choose_scope"
    CHOOSE_OPERATIONALIZATION = "choose_operationalization"
    AUTHORIZE_COST = "authorize_cost"
    REVIEW_RESULT = "review_result"
    STEER_INQUIRY = "steer_inquiry"
    REVIEW_SYNTHESIS = "review_synthesis"
    AUTHOR_ACTION = "author_action"
    ACCEPT_TO_LEDGER = "accept_to_ledger"


class ResponseKind(str, Enum):
    """What the person did with the fork.

    `reject_all` and `skip` are different and the difference is consequential: rejecting says none
    of these is right and the fork stays unsettled; skipping says not now and leaves it deferred.
    A composer that could not tell them apart would report a refusal as a postponement.
    """
    SELECT_OPTION = "select_option"
    REJECT_ALL = "reject_all"
    SKIP = "skip"
    REDIRECT = "redirect"
    AMEND = "amend"


class AmendmentRelation(str, Enum):
    """How a user-authored successor stands to the object it references. It never overwrites it."""
    REPLACES = "replaces"
    SUPPLEMENTS = "supplements"
    DISPUTES = "disputes"


class Actor(str, Enum):
    """WHO did it. Four, and the separation is the point: a reader must be able to see that the
    thing which chose is not always the person, and that the thing which WORDED the question is
    neither the thing that found the fork nor the thing that answered it."""
    USER = "user"
    POLICY = "policy"
    STEWARD = "steward"
    ENGINE = "engine"


class EventKind(str, Enum):
    """The closed transition vocabulary. `decision_unresolved` is the one worth reading twice: it
    is what auto mode emits at a tie, and it exists so that "nobody chose" is a recorded outcome
    rather than the absence of a record."""
    SESSION_OPENED = "session_opened"
    PHASE_ADVANCED = "phase_advanced"
    CANDIDATE_OFFERED = "candidate_offered"
    CANDIDATE_REFUSED = "candidate_refused"
    DECISION_REQUESTED = "decision_requested"
    DECISION_AUTO_RESOLVED = "decision_auto_resolved"
    DECISION_UNRESOLVED = "decision_unresolved"
    RESPONSE_RECEIVED = "response_received"
    RESPONSE_REFUSED = "response_refused"
    AMENDMENT_RECORDED = "amendment_recorded"
    FORMATTER_REFUSED = "formatter_refused"
    SESSION_CLOSED = "session_closed"


#: Keys that would smuggle a kind of knowing into a preference. Checked on every free-form
#: `provenance` mapping a person can reach, because that dict is the only place on a response or
#: an amendment where an unlisted key is legal at all.
STATUS_KEYS = frozenset({
    "epistemic_status", "status", "ledger_status", "measured", "visible", "basis",
    "confidence", "score", "usable_as_evidence", "evidence",
})


class _Strict(BaseModel):
    """Unknown fields are refused, not ignored."""
    model_config = ConfigDict(extra="forbid")


def _refuse_status_keys(value: Mapping[str, Any], *, where: str) -> Dict[str, Any]:
    found = sorted(set(value) & STATUS_KEYS)
    if found:
        raise ValueError(
            f"{where} carries {found}. A person's direction changes which goals are pursued; it "
            f"never changes what anything is known by. A status arriving on a preference is the "
            f"one laundering path this object has, and it is closed here rather than downstream.")
    return dict(value)


# ── deterministic ids ────────────────────────────────────────────────────────

def _digest(*parts: Any) -> str:
    """A stable 12-hex handle over the parts, JSON-canonicalised.

    Deterministic rather than minted, because replay is a required proof: an id drawn from a clock
    or a uuid would make two runs of one session differ in the one field a reader uses to line them
    up, and the byte-comparison would then have to exclude exactly the field it exists to check.
    """
    blob = json.dumps(list(parts), sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def decision_id(session_id: str, revision: int, candidate_id: str) -> str:
    return f"dec_{_digest('decision', session_id, revision, candidate_id)}"


def record_id(session_id: str, revision: int, decision: str, outcome: str) -> str:
    return f"decr_{_digest('record', session_id, revision, decision, outcome)}"


def amendment_id(session_id: str, revision: int, target_ref: str, text: str) -> str:
    return f"amd_{_digest('amendment', session_id, revision, target_ref, text)}"


def event_id(session_id: str, seq: int, kind: str) -> str:
    return f"iev_{_digest('event', session_id, seq, kind)}"


def graph_hash(snapshot: Mapping[str, Any]) -> str:
    """A handle for the graph this session deliberated over, so a record can point at it without
    copying it — and so an amendment can be checked against the snapshot it did not change."""
    blob = json.dumps(snapshot, sort_keys=True, default=str, separators=(",", ":"))
    return f"sig_{hashlib.sha256(blob.encode('utf-8')).hexdigest()[:16]}"


# ── the objects ──────────────────────────────────────────────────────────────

class DecisionOption(_Strict):
    """One thing the person could choose, and what choosing it would change.

    `consequence` is required and is the field that makes an option a choice rather than a label.
    "Segment at part level" says nothing; "segment at part level — 12 regions per image instead of
    3, and the comparison runs per part" is answerable by someone who is not holding the codebase
    in their head.
    """
    option_id: str
    label: str
    consequence: str = Field(..., description="what downstream work changes if this is chosen")
    recommended: bool = False
    reversible: Optional[bool] = Field(
        default=None,
        description="whether choosing this can be undone. None means UNDECLARED, which auto mode "
                    "treats as blocking — not as a yes.")
    authorial: bool = Field(
        default=False, description="only a person may author this act (action grammar)")
    accepts_to_ledger: bool = Field(
        default=False, description="choosing this would put something into the shared ledger")
    affects_refs: List[str] = Field(
        default_factory=list, description="graph object ids this option would change")
    detail: str = ""

    @property
    def auto_eligible(self) -> bool:
        """Whether a policy may take this one without the person. All four, ANDed, and
        `reversible is True` rather than truthiness so that None fails."""
        return (self.recommended and self.reversible is True
                and not self.authorial and not self.accepts_to_ledger)


class DecisionRequest(_Strict):
    """A concrete fork, worded. Exactly what a person is shown and exactly what they may answer.

    `candidate` holds the ORIGINAL opaque mapping this was formed from, verbatim. It is not
    decoration: this lane treats the semantic graph as opaque, so the candidate is the only record
    of what the producing lane actually said, and a reader who suspects the steward of paraphrasing
    can check it against the thing it paraphrased.
    """
    schema_version: str = SCHEMA_VERSION
    decision_id: str
    session_id: str
    revision: int = Field(..., description="the session revision this request was formed at")
    kind: DecisionKind
    question: str
    why_now: str = Field(..., description="what changes downstream — never 'to be sure'")
    affected_refs: List[str] = Field(default_factory=list)
    options: List[DecisionOption] = Field(default_factory=list)
    allow_free_text: bool = True
    blocking: bool = True
    formatter: str = Field(default="deterministic",
                           description="which formatter worded this: deterministic | a role name")
    candidate: Dict[str, Any] = Field(
        default_factory=dict, description="the producing lane's original mapping, preserved")
    actor: Actor = Actor.STEWARD
    parent_event_id: str = ""
    created_at: str = Field(..., description="handed by the caller; this lane reads no clock")
    provenance: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("schema_version")
    @classmethod
    def _pinned(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}, got {value!r}")
        return value

    @model_validator(mode="after")
    def _a_fork_has_more_than_one_way(self) -> "DecisionRequest":
        ids = [o.option_id for o in self.options]
        if len(ids) != len(set(ids)):
            raise ValueError("two options share an option_id; a reply naming one would be "
                             "ambiguous and the ambiguity would be resolved by list order")
        if not self.options and not self.allow_free_text:
            raise ValueError(
                "a request with no options and no free text is not a question — there is nothing "
                "the person could say that this object would accept")
        return self

    def option(self, option_id: str) -> Optional[DecisionOption]:
        for opt in self.options:
            if opt.option_id == option_id:
                return opt
        return None

    @property
    def recommended_options(self) -> List[DecisionOption]:
        return [o for o in self.options if o.recommended]


class UserAmendment(_Strict):
    """A user-authored successor to a graph object. Append-only, attributed, and epistemically
    inert.

    The rule this type exists to hold: a person saying "that is not a portico, it is a loggia" adds
    a claim authored by a person. It does not edit the model's claim, and it does not make either
    one measured. Both halves matter — silently rewriting the model's text would erase the
    disagreement, and promoting the person's text would make assertion a way of producing evidence.
    """
    amendment_id: str
    session_id: str
    decision_id: str = ""
    target_ref: str = Field(..., description="the graph object this stands beside")
    text: str = Field(..., description="the person's words, byte for byte")
    relation: AmendmentRelation = AmendmentRelation.SUPPLEMENTS
    actor: Actor = Field(default=Actor.USER, frozen=True)
    at: str
    provenance: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("actor")
    @classmethod
    def _only_a_person(cls, value: Actor) -> Actor:
        # There is no other legal value. The field exists so the absence of an alternative is
        # visible in the data rather than implied by a docstring.
        if value is not Actor.USER:
            raise ValueError("an amendment is authored by the person and by nobody else; a "
                             "policy-authored 'amendment' would be the machine editing the graph "
                             "while wearing the user's attribution")
        return value

    @field_validator("provenance")
    @classmethod
    def _no_status(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return _refuse_status_keys(value, where="an amendment's provenance")

    @field_validator("text")
    @classmethod
    def _has_words(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("an amendment with no text records that somebody typed nothing")
        return value


class DecisionResponse(_Strict):
    """What the person sent back.

    `expected_revision` is the optimistic lock. It is required rather than optional because the
    alternative — a response with no expectation, accepted whenever it arrives — is how a reply to
    a question the session has already moved past gets applied to a different question.
    """
    schema_version: str = SCHEMA_VERSION
    response_id: str
    session_id: str
    decision_id: str
    expected_revision: int
    kind: ResponseKind
    option_id: str = ""
    free_text: str = ""
    amendment_target: str = Field(
        default="", description="for kind=amend: which graph object the text stands beside")
    amendment_relation: AmendmentRelation = AmendmentRelation.SUPPLEMENTS
    actor: Actor = Field(default=Actor.USER, frozen=True)
    at: str
    provenance: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("schema_version")
    @classmethod
    def _pinned(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}, got {value!r}")
        return value

    @field_validator("actor")
    @classmethod
    def _only_a_person(cls, value: Actor) -> Actor:
        if value is not Actor.USER:
            raise ValueError("a response is the person's. A policy that wanted to answer its own "
                             "question would be an auto decision, which has its own record type "
                             "and its own visibility rules")
        return value

    @field_validator("provenance")
    @classmethod
    def _no_status(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return _refuse_status_keys(value, where="a response's provenance")

    @model_validator(mode="after")
    def _says_what_it_needs_to(self) -> "DecisionResponse":
        if self.kind is ResponseKind.SELECT_OPTION and not self.option_id:
            raise ValueError("select_option names no option")
        if self.kind is ResponseKind.REDIRECT and not self.free_text.strip():
            raise ValueError("redirect carries no text — a redirection with no direction")
        if self.kind is ResponseKind.AMEND:
            if not self.free_text.strip():
                raise ValueError("amend carries no text")
            if not self.amendment_target:
                raise ValueError("amend names no target — an amendment standing beside nothing "
                                 "cannot be read back to what it amends")
        return self


class DecisionRecord(_Strict):
    """WHO settled a fork, HOW, and what was not chosen.

    This is the object that makes auto mode honest. `alternatives` is the list the chooser did not
    take and `reason` is why it took the one it did; without both, an automatic decision is
    indistinguishable from a fork that never existed, and "the system decided" becomes unauditable
    precisely where it is most consequential.
    """
    record_id: str
    session_id: str
    decision_id: str
    kind: DecisionKind
    mode: InteractionMode
    outcome: str = Field(..., description="auto_resolved | answered | unresolved | deferred | rejected")
    actor: Actor
    chosen_option_id: str = ""
    alternatives: List[str] = Field(default_factory=list)
    reason: str = Field(..., description="why this outcome, in a sentence a reviewer can check")
    response_id: str = ""
    amendment_ids: List[str] = Field(default_factory=list)
    revision: int = 0
    at: str
    candidate: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)


class InteractionRefusal(_Strict):
    """Something that was produced and did not become part of the session, and why.

    Kept rather than dropped, for the reason the frame keeps its refusals: the refusal rate is the
    only observable that says whether a formatter or a candidate producer can be trusted, and a
    silent drop hides exactly the cases you would want to count.
    """
    code: str
    what: str = Field(..., description="the offending name or value, verbatim")
    why: str
    detail: List[str] = Field(default_factory=list)
    at: str = ""


class InteractionEvent(_Strict):
    """One transition. Carries the full typed object it is about, in `payload`.

    Full rather than a reference, because `replay` folds the event list back into the state and a
    log that only pointed at objects held elsewhere would not be replayable on its own — it would
    be an index into a thing that has to survive separately.
    """
    seq: int
    event_id: str
    session_id: str
    kind: EventKind
    revision: int
    actor: Actor
    at: str
    decision_id: str = ""
    refs: List[str] = Field(default_factory=list)
    reason: str = ""
    parent_event_id: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)


class GraphRef(_Strict):
    """The semantic graph, held at arm's length.

    `snapshot` is an opaque mapping. This lane never reads inside it, never validates it against a
    schema it does not own, and — the load-bearing part — never writes to it. Amendments reference
    `snapshot` by id and are stored beside it, so a test can assert the snapshot is byte-identical
    after a session that amended three of its objects.
    """
    graph_id: str = ""
    inquiry_id: str = ""
    graph_hash: str = ""
    snapshot: Dict[str, Any] = Field(default_factory=dict)


class InquiryInteractionState(_Strict):
    """One deliberation, whole, as plain serialisable data.

    NO PERSISTENCE. This lane opens no collection and writes no row: the state is a VALUE, and a
    caller that wants it stored calls `model_dump()`. Which store carries it is the integration
    lane's decision, and the goal engine's reconciliation (`inquiry_engine/__init__.py`) already
    names `runs` via `run_store` as the recommendation for its sibling object.

    Append-only by construction: every list here is only ever extended, and there is no method that
    removes or rewrites an entry.
    """
    schema_version: str = SCHEMA_VERSION
    session_id: str
    inquiry_id: str = ""
    mode: InteractionMode = InteractionMode.CONSULT
    state: SessionState = SessionState.FRAMING
    #: The phase a pause happened FROM, so an answered session returns where it stopped rather than
    #: to a default. Empty unless `state is AWAITING_USER`.
    paused_from: Optional[SessionState] = None
    revision: int = 0
    graph: GraphRef = Field(default_factory=GraphRef)
    open_decision_id: str = ""
    #: Candidates offered and not yet settled, in the order they arrived, as the producing lane's
    #: original mappings. A queue rather than one slot because step mode stops at EVERY declared
    #: fork: with a single slot, offering three candidates and pausing at the first would drop the
    #: other two, and the mode's whole promise is that nothing was passed silently.
    pending: List[Dict[str, Any]] = Field(default_factory=list)
    events: List[InteractionEvent] = Field(default_factory=list)
    requests: List[DecisionRequest] = Field(default_factory=list)
    responses: List[DecisionResponse] = Field(default_factory=list)
    records: List[DecisionRecord] = Field(default_factory=list)
    amendments: List[UserAmendment] = Field(default_factory=list)
    refusals: List[InteractionRefusal] = Field(default_factory=list)
    deferred: List[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    @field_validator("schema_version")
    @classmethod
    def _pinned(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}, got {value!r}")
        return value

    @model_validator(mode="after")
    def _awaiting_means_something_is_open(self) -> "InquiryInteractionState":
        """The invariant that keeps a session answerable exactly when it says it is.

        `run_store.is_answerable` holds the same rule one layer down — waiting AND having the state
        to continue from, because either alone is a session that would answer into a void.
        """
        if self.state is SessionState.AWAITING_USER and not self.open_decision_id:
            raise ValueError("state is awaiting_user with no open decision — a session that says "
                             "it is waiting and names nothing to answer cannot be answered, and "
                             "would sit there looking live")
        if self.state is not SessionState.AWAITING_USER and self.open_decision_id:
            raise ValueError(f"an open decision {self.open_decision_id!r} while the state is "
                             f"{self.state.value!r}; a decision nobody is waiting on would be "
                             f"answerable after the session had already moved past it")
        # `paused_from` is the same invariant from the other side, and it is enforced rather than
        # documented because it is what an answered session RESUMES INTO. A session waiting with no
        # recorded origin would resume to the default phase; one carrying a stale origin while not
        # waiting would send the next pause's answer back to the wrong place. Neither raises
        # anywhere else — they simply put the session somewhere nobody chose.
        if self.state is SessionState.AWAITING_USER and self.paused_from is None:
            raise ValueError("state is awaiting_user with no `paused_from`; an answered session "
                             "would resume into a default phase rather than the one it stopped in")
        if self.state is not SessionState.AWAITING_USER and self.paused_from is not None:
            raise ValueError(f"`paused_from` is {self.paused_from.value!r} while the state is "
                             f"{self.state.value!r}; a pause origin outliving its pause would be "
                             f"read by the next one")
        return self

    # ── reading ──
    def request(self, decision: str) -> Optional[DecisionRequest]:
        for req in self.requests:
            if req.decision_id == decision:
                return req
        return None

    @property
    def open_decision(self) -> Optional[DecisionRequest]:
        return self.request(self.open_decision_id) if self.open_decision_id else None

    def record_for(self, decision: str) -> Optional[DecisionRecord]:
        for rec in self.records:
            if rec.decision_id == decision:
                return rec
        return None

    def next_seq(self) -> int:
        return len(self.events)


__all__ = [
    "SCHEMA_VERSION", "STATUS_KEYS", "TERMINAL_STATES",
    "InteractionMode", "SessionState", "DecisionKind", "ResponseKind", "AmendmentRelation",
    "Actor", "EventKind",
    "DecisionOption", "DecisionRequest", "DecisionResponse", "DecisionRecord", "UserAmendment",
    "InteractionEvent", "InteractionRefusal", "GraphRef", "InquiryInteractionState",
    "decision_id", "record_id", "amendment_id", "event_id", "graph_hash",
]
