"""
HARNESS-002B §4/§5 — the append-only interaction state machine.

Every function here is PURE: it takes a state and returns a new one. Nothing mutates its argument,
nothing reads a clock, nothing touches a database, a network or a model. A session is a VALUE, and
this module is the total set of ways one may change.

## Append-only in the strongest available sense

There is no function that removes or rewrites an event, a request, a record, a response or an
amendment. `replay()` is the proof rather than the promise: it folds the event list back into a
state and a test asserts the result is byte-identical to the original. A log that only pointed at
objects held elsewhere would pass a weaker version of that test while being unreplayable on its own.

## Revision counts turns, not events

One response appends several events — the response, its record, possibly an amendment — and moves
`revision` exactly once. That is what makes the optimistic lock meaningful to a client: the number
it holds and the number it must send back are about the same thing, how many times this session has
been moved by somebody. A revision that counted events would change under a client's feet for
reasons the client has no way to observe.

## Only a response leaves `awaiting_user`

A paused session records the phase it paused FROM and returns there when answered. `advance()`
refuses to move a session that is waiting, because a phase advance that stepped over an open
decision would answer it by walking away — and the trace would show a question asked and no
question answered, with the run having proceeded regardless.

## The pending queue

Candidates offered and not yet settled are held in order. Step mode stops at every one of them, and
with a single open slot the second and third candidates of a batch would be dropped at the first
pause. The queue is what makes "pauses at every candidate" a property of the session rather than of
how the caller happened to batch its offers.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.inquiry_interaction import (STATUS_KEYS, TERMINAL_STATES, Actor,
                                                 AmendmentRelation, DecisionRecord,
                                                 DecisionRequest, DecisionResponse,
                                                 EventKind, GraphRef, InquiryInteractionState,
                                                 InteractionEvent, InteractionMode,
                                                 InteractionRefusal, ResponseKind, SessionState,
                                                 UserAmendment, amendment_id, event_id, graph_hash,
                                                 record_id)
from backend.services.inquiry_interaction import candidates as cand
from backend.services.inquiry_interaction import policy as pol
from backend.services.inquiry_interaction.conflicts import (DecisionMismatch, DuplicateResponse,
                                                            EpistemicStatusAttempted,
                                                            FreeTextNotAllowed, GateBypass,
                                                            NoDecisionOpen, ResponseMalformed,
                                                            StaleRevision, UnknownOption,
                                                            WrongSession)
from backend.services.inquiry_interaction.steward import DeliberationSteward

# ── record outcomes ──────────────────────────────────────────────────────────
#: Five, and `unresolved` is not `rejected`. Nobody chose vs the person chose none of these — the
#: first is the machine declining to guess, the second is a considered no, and a composer that
#: could not tell them apart would report one as the other.
OUTCOME_AUTO_RESOLVED = "auto_resolved"
OUTCOME_ANSWERED = "answered"
OUTCOME_UNRESOLVED = "unresolved"
OUTCOME_DEFERRED = "deferred"
OUTCOME_REJECTED = "rejected"

RECORD_OUTCOMES: Tuple[str, ...] = (OUTCOME_AUTO_RESOLVED, OUTCOME_ANSWERED, OUTCOME_UNRESOLVED,
                                    OUTCOME_DEFERRED, OUTCOME_REJECTED)


class SessionMisuse(Exception):
    """A caller asked for a transition this session cannot make.

    Not an `InteractionConflict`: the nine conflicts are the ordinary weather of a resumable
    session (a stale tab, a retried POST) and this is a program doing something it should not.
    Keeping them apart is what lets the integration lane map one to 409 and the other to 500.
    """


def _event(state: InquiryInteractionState, *, kind: EventKind, actor: Actor, at: str,
           revision: int, decision: str = "", refs: Optional[Sequence[str]] = None,
           reason: str = "", parent: str = "",
           payload: Optional[Mapping[str, Any]] = None) -> InteractionEvent:
    seq = state.next_seq()
    return InteractionEvent(
        seq=seq, event_id=event_id(state.session_id, seq, kind.value),
        session_id=state.session_id, kind=kind, revision=revision, actor=actor, at=at,
        decision_id=decision, refs=[str(r) for r in (refs or ())], reason=reason,
        parent_event_id=parent, payload=dict(payload or {}))


def _appended(current: InquiryInteractionState, event: InteractionEvent,
              **changes: Any) -> InquiryInteractionState:
    """A new state with the event appended and the named fields changed. The single write path.

    The first parameter is `current` rather than `state` because `state` is itself one of the
    fields a caller changes, and a positional/keyword collision there would be a `TypeError` at
    exactly the transitions that matter most.
    """
    data = current.model_dump()
    data["events"] = [*data["events"], event.model_dump()]
    data["updated_at"] = event.at
    data["revision"] = event.revision
    data.update(changes)
    return InquiryInteractionState(**data)


# ── opening ──────────────────────────────────────────────────────────────────

def open_session(*, session_id: str, mode: InteractionMode, at: str, inquiry_id: str = "",
                 graph: Optional[Mapping[str, Any]] = None,
                 graph_id: str = "") -> InquiryInteractionState:
    """A new session at `framing`, with the graph held at arm's length.

    The snapshot is stored as given and hashed. The hash is what a record points at, so a reader
    can tell whether two decisions were made about the same graph without this lane ever having to
    read inside it.
    """
    if not session_id:
        raise SessionMisuse("a session needs an id; every record, request and response points at "
                            "one and an unnamed session cannot be resumed")
    if not at:
        raise SessionMisuse("a session needs a timestamp handed to it — this lane reads no clock, "
                            "so a state with no `at` would have no order at all")
    snapshot = dict(graph or {})
    ref = GraphRef(graph_id=graph_id or str(snapshot.get("graph_id") or ""),
                   inquiry_id=inquiry_id or str(snapshot.get("inquiry_id") or ""),
                   graph_hash=graph_hash(snapshot), snapshot=snapshot)
    empty = InquiryInteractionState(
        session_id=session_id, inquiry_id=ref.inquiry_id, mode=mode,
        state=SessionState.FRAMING, graph=ref, created_at=at, updated_at=at)
    event = _event(empty, kind=EventKind.SESSION_OPENED, actor=Actor.ENGINE, at=at, revision=0,
                   reason=f"session opened in {mode.value} mode",
                   payload={"mode": mode.value, "inquiry_id": ref.inquiry_id,
                            "graph": ref.model_dump()})
    return _appended(empty, event)


# ── phases ───────────────────────────────────────────────────────────────────

def advance(state: InquiryInteractionState, to: SessionState, *, at: str,
            reason: str = "") -> InquiryInteractionState:
    """Move to a declared phase. Refused while a decision is open — see the module note."""
    if state.state is SessionState.AWAITING_USER:
        raise SessionMisuse(
            f"cannot advance to {to.value!r} while decision {state.open_decision_id!r} is open. A "
            f"phase advance that stepped over an open decision would answer it by walking away, "
            f"and the trace would show a question asked and never answered while the run carried "
            f"on regardless.")
    if state.state in TERMINAL_STATES:
        raise SessionMisuse(f"session is {state.state.value!r}; nothing further happens to it")
    event = _event(state, kind=EventKind.PHASE_ADVANCED, actor=Actor.ENGINE, at=at,
                   revision=state.revision + 1,
                   reason=reason or f"{state.state.value} → {to.value}",
                   payload={"from": state.state.value, "to": to.value})
    return _appended(state, event, state=to.value)


def close(state: InquiryInteractionState, to: SessionState, *, at: str,
          reason: str = "") -> InquiryInteractionState:
    """End the session in one of the four terminal states."""
    if to not in TERMINAL_STATES:
        raise SessionMisuse(f"{to.value!r} is not terminal; use `advance`")
    if state.state is SessionState.AWAITING_USER:
        raise SessionMisuse(
            f"cannot close a session waiting on decision {state.open_decision_id!r}; a question "
            f"abandoned mid-session is not the same as one answered, and only one of them is a "
            f"result")
    event = _event(state, kind=EventKind.SESSION_CLOSED, actor=Actor.ENGINE, at=at,
                   revision=state.revision + 1, reason=reason or f"closed {to.value}",
                   payload={"to": to.value})
    return _appended(state, event, state=to.value)


# ── offering candidates ──────────────────────────────────────────────────────

def offer(state: InquiryInteractionState, items: Sequence[Any], *,
          steward: DeliberationSteward, at: str) -> InquiryInteractionState:
    """Queue candidates and settle as many as the policy allows, stopping at the first pause.

    One turn, so one revision, however many candidates it settles. The alternative — a revision per
    candidate — would make the number a client holds depend on how the producing lane batched its
    output, which is not something the client can see.
    """
    if state.state is SessionState.AWAITING_USER:
        raise SessionMisuse(
            f"cannot offer new candidates while decision {state.open_decision_id!r} is open; the "
            f"person is looking at a question whose answer may change what the next fork even is")
    if state.state in TERMINAL_STATES:
        raise SessionMisuse(f"session is {state.state.value!r}; it takes no further candidates")

    revision = state.revision + 1
    raws = [dict(item) if isinstance(item, Mapping) else item for item in items]
    event = _event(state, kind=EventKind.CANDIDATE_OFFERED, actor=Actor.ENGINE, at=at,
                   revision=revision, reason=f"{len(raws)} candidate(s) offered",
                   payload={"candidates": raws})
    moved = _appended(state, event, pending=[*state.pending, *raws])
    return _drain(moved, steward=steward, at=at, revision=revision)


def _drain(state: InquiryInteractionState, *, steward: DeliberationSteward, at: str,
           revision: int) -> InquiryInteractionState:
    """Settle pending candidates in order until one pauses or the queue empties.

    Order is the order they were offered, and nothing here reorders by confidence, cost or
    recommendation strength. A queue sorted by any of those would make which fork a person sees
    first a judgement nobody declared.
    """
    while state.pending and state.state is not SessionState.AWAITING_USER \
            and state.state not in TERMINAL_STATES:
        raw = state.pending[0]
        try:
            candidate = cand.read(raw)
        except cand.CandidateUnreadable as exc:
            refusal = exc.as_refusal(at=at)
            event = _event(state, kind=EventKind.CANDIDATE_REFUSED, actor=Actor.ENGINE, at=at,
                           revision=revision, reason=refusal.why,
                           payload={"refusal": refusal.model_dump()})
            state = _appended(state, event, pending=list(state.pending[1:]),
                              refusals=[*[r.model_dump() for r in state.refusals],
                                        refusal.model_dump()])
            continue

        formed = steward.form(candidate, session_id=state.session_id, revision=revision, at=at,
                              parent_event_id=state.events[-1].event_id if state.events else "")
        request = formed.request
        for refusal in formed.refusals:
            event = _event(state, kind=EventKind.FORMATTER_REFUSED, actor=Actor.ENGINE, at=at,
                           revision=revision, decision=request.decision_id, reason=refusal.why,
                           payload={"refusal": refusal.model_dump()})
            state = _appended(state, event,
                              refusals=[*[r.model_dump() for r in state.refusals],
                                        refusal.model_dump()])

        verdict = steward.verdict(candidate)
        pausing = verdict.outcome == pol.OUTCOME_PAUSE
        event = _event(state, kind=EventKind.DECISION_REQUESTED, actor=Actor.STEWARD, at=at,
                       revision=revision, decision=request.decision_id,
                       refs=request.affected_refs, reason=verdict.reason,
                       payload={"request": request.model_dump(mode="json"),
                                "pause_class": verdict.pause_class,
                                "paused": pausing,
                                "paused_from": state.state.value if pausing else ""})
        requests = [*[r.model_dump(mode="json") for r in state.requests],
                    request.model_dump(mode="json")]

        if pausing:
            return _appended(state, event, requests=requests,
                             open_decision_id=request.decision_id,
                             paused_from=state.state.value,
                             state=SessionState.AWAITING_USER.value)

        state = _appended(state, event, requests=requests)

        if verdict.outcome == pol.OUTCOME_AUTO:
            outcome, kind, actor = OUTCOME_AUTO_RESOLVED, EventKind.DECISION_AUTO_RESOLVED, \
                Actor.POLICY
        else:
            outcome, kind, actor = OUTCOME_UNRESOLVED, EventKind.DECISION_UNRESOLVED, Actor.POLICY

        record = DecisionRecord(
            record_id=record_id(state.session_id, revision, request.decision_id, outcome),
            session_id=state.session_id, decision_id=request.decision_id, kind=candidate.kind,
            mode=steward.policy.mode, outcome=outcome, actor=actor,
            chosen_option_id=verdict.option_id, alternatives=list(verdict.alternatives),
            reason=verdict.reason, revision=revision, at=at, candidate=dict(candidate.raw),
            provenance={"pause_class": verdict.pause_class})
        event = _event(state, kind=kind, actor=actor, at=at, revision=revision,
                       decision=request.decision_id, refs=request.affected_refs,
                       reason=verdict.reason, payload={"record": record.model_dump(mode="json")})
        state = _appended(state, event, pending=list(state.pending[1:]),
                          records=[*[r.model_dump(mode="json") for r in state.records],
                                   record.model_dump(mode="json")])
    return state


# ── responding ───────────────────────────────────────────────────────────────

def read_response(data: Mapping[str, Any]) -> DecisionResponse:
    """A mapping off the wire → a typed response, with the honesty check before construction.

    The status check runs FIRST and by key rather than being left to the schema, so the failure
    arrives as `EpistemicStatusAttempted` — a distinct, mappable thing — rather than as one more
    line in a validation error the integration lane would have to pattern-match a message out of.
    """
    if not isinstance(data, Mapping):
        raise ResponseMalformed(f"a response must be a mapping, got {type(data).__name__}")
    found = sorted(set(dict(data.get("provenance") or {})) & STATUS_KEYS)
    if found:
        raise EpistemicStatusAttempted(
            f"the response's provenance carries {found}. A person's direction changes which goals "
            f"are pursued; it never changes what anything is known by. Once a status is attached "
            f"to a preference and stored, every reader after that point sees a well-formed object "
            f"and nothing downstream has anything left to check it against.",
            expected="a provenance with no epistemic status", actual=found)
    try:
        return DecisionResponse(**dict(data))
    except Exception as exc:                            # noqa: BLE001 — pydantic ValidationError
        raise ResponseMalformed(f"the mapping is not a valid response: {exc}") from exc


def _reason_for(response: DecisionResponse, request: DecisionRequest) -> Tuple[str, str, str]:
    """(outcome, chosen_option_id, reason)."""
    if response.kind is ResponseKind.SELECT_OPTION:
        option = request.option(response.option_id)
        return (OUTCOME_ANSWERED, response.option_id,
                f"the person chose {response.option_id!r}: "
                f"{option.consequence if option else ''}")
    if response.kind is ResponseKind.REJECT_ALL:
        return (OUTCOME_REJECTED, "",
                "the person rejected every declared option; the fork stays unsettled and no "
                "option was taken on their behalf")
    if response.kind is ResponseKind.SKIP:
        return (OUTCOME_DEFERRED, "",
                "the person deferred this fork; it is recorded as outstanding rather than "
                "resolved, and nothing below it was decided by the postponement")
    if response.kind is ResponseKind.REDIRECT:
        return (OUTCOME_ANSWERED, "",
                "the person redirected the inquiry in their own words; the direction is kept "
                "verbatim as a user-authored object and changes which goals are pursued, not what "
                "anything is known by")
    return (OUTCOME_ANSWERED, "",
            "the person amended a referenced object; the original is unchanged and the amendment "
            "stands beside it, attributed to them")


def respond(state: InquiryInteractionState, response: DecisionResponse, *,
            steward: DeliberationSteward, at: str) -> InquiryInteractionState:
    """Apply a response, or raise the one typed conflict that says why not.

    The checks run in this order deliberately. Session identity first, because a response for
    another session should be turned away before this one reveals anything about what it is
    waiting for. Duplicate next, because a retried POST is not a failure and should not be reported
    as a mismatch. Then whether anything is open, then whether it is THIS decision, then whether
    the client's view of the session is current.
    """
    if response.session_id != state.session_id:
        raise WrongSession(
            f"response {response.response_id!r} is for session {response.session_id!r}",
            expected=state.session_id, actual=response.session_id)

    if any(r.response_id == response.response_id for r in state.responses):
        raise DuplicateResponse(
            f"response {response.response_id!r} was already applied; nothing was lost and nothing "
            f"needs redoing",
            expected="an unseen response_id", actual=response.response_id)

    if state.state is not SessionState.AWAITING_USER or not state.open_decision_id:
        raise NoDecisionOpen(
            f"session is {state.state.value!r} and waits on nothing; this answer would land "
            f"nowhere",
            expected=SessionState.AWAITING_USER.value, actual=state.state.value)

    if response.decision_id != state.open_decision_id:
        raise DecisionMismatch(
            f"this session is asking {state.open_decision_id!r}, not {response.decision_id!r}",
            expected=state.open_decision_id, actual=response.decision_id)

    if response.expected_revision != state.revision:
        raise StaleRevision(
            f"the session is at revision {state.revision} and the response expects "
            f"{response.expected_revision}; re-read it and answer the question that is open now",
            expected=state.revision, actual=response.expected_revision)

    request = state.open_decision
    assert request is not None                          # the state invariant guarantees it

    if response.kind is ResponseKind.SELECT_OPTION and request.option(response.option_id) is None:
        raise UnknownOption(
            f"option {response.option_id!r} is not on decision {request.decision_id!r}",
            expected=[o.option_id for o in request.options], actual=response.option_id,
            refs=list(request.affected_refs))

    if response.free_text.strip() and not request.allow_free_text:
        raise FreeTextNotAllowed(
            f"decision {request.decision_id!r} does not take free text; it offers "
            f"{[o.option_id for o in request.options]}",
            expected="one of the declared options", actual=response.free_text[:80],
            refs=list(request.affected_refs))

    revision = state.revision + 1
    outcome, chosen, reason = _reason_for(response, request)

    event = _event(state, kind=EventKind.RESPONSE_RECEIVED, actor=Actor.USER, at=at,
                   revision=revision, decision=request.decision_id, refs=request.affected_refs,
                   reason=reason, parent=request.parent_event_id,
                   payload={"response": response.model_dump(mode="json")})
    resumed = state.paused_from or SessionState.READY
    state = _appended(
        state, event,
        responses=[*[r.model_dump(mode="json") for r in state.responses],
                   response.model_dump(mode="json")],
        open_decision_id="", paused_from=None,
        state=(resumed.value if isinstance(resumed, SessionState) else str(resumed)),
        pending=list(state.pending[1:]),
        deferred=([*state.deferred, request.decision_id]
                  if outcome == OUTCOME_DEFERRED else list(state.deferred)))

    made: List[UserAmendment] = []
    if response.kind in (ResponseKind.REDIRECT, ResponseKind.AMEND):
        target = (response.amendment_target if response.kind is ResponseKind.AMEND
                  else request.decision_id)
        amendment = UserAmendment(
            amendment_id=amendment_id(state.session_id, revision, target, response.free_text),
            session_id=state.session_id, decision_id=request.decision_id, target_ref=target,
            text=response.free_text, relation=response.amendment_relation, actor=Actor.USER, at=at,
            provenance={"response_id": response.response_id,
                        "graph_hash": state.graph.graph_hash})
        made.append(amendment)
        event = _event(state, kind=EventKind.AMENDMENT_RECORDED, actor=Actor.USER, at=at,
                       revision=revision, decision=request.decision_id, refs=[target],
                       reason=(f"a user-authored object now stands beside {target!r}; the original "
                               f"is unchanged and neither is thereby measured"),
                       payload={"amendment": amendment.model_dump(mode="json")})
        state = _appended(state, event,
                          amendments=[*[a.model_dump(mode="json") for a in state.amendments],
                                      amendment.model_dump(mode="json")])

    record = DecisionRecord(
        record_id=record_id(state.session_id, revision, request.decision_id, outcome),
        session_id=state.session_id, decision_id=request.decision_id, kind=request.kind,
        mode=steward.policy.mode, outcome=outcome, actor=Actor.USER, chosen_option_id=chosen,
        alternatives=[o.option_id for o in request.options if o.option_id != chosen],
        reason=reason, response_id=response.response_id,
        amendment_ids=[a.amendment_id for a in made], revision=revision, at=at,
        candidate=dict(request.candidate),
        provenance={"response_kind": response.kind.value})
    state = _appended(
        state,
        _event(state, kind=EventKind.RESPONSE_RECEIVED, actor=Actor.USER, at=at, revision=revision,
               decision=request.decision_id, refs=request.affected_refs, reason=reason,
               payload={"record": record.model_dump(mode="json")}),
        records=[*[r.model_dump(mode="json") for r in state.records],
                 record.model_dump(mode="json")])

    return _drain(state, steward=steward, at=at, revision=revision)


def resolve_without_user(state: InquiryInteractionState, *, option_id: str, reason: str,
                         steward: DeliberationSteward, at: str) -> InquiryInteractionState:
    """Settle the open decision from a surrounding auto-mode loop, or refuse the gate.

    This is the one entry point from which `gate_bypass` is reachable, and it exists precisely so
    that it is: an auto-mode loop draining its pending decisions is a reasonable thing to write for
    every kind EXCEPT the two gates, so the refusal has to live here rather than in the loop's own
    good intentions.
    """
    if state.state is not SessionState.AWAITING_USER or not state.open_decision_id:
        raise NoDecisionOpen(f"session is {state.state.value!r} and waits on nothing",
                             expected=SessionState.AWAITING_USER.value, actual=state.state.value)
    request = state.open_decision
    assert request is not None
    if pol.is_gate(request.kind):
        raise GateBypass(
            f"decision {request.decision_id!r} is a {request.kind.value} gate and may not be "
            f"settled without the person, in any mode. Authoring a public act and accepting into "
            f"the shared ledger are the person's alone.",
            expected="a response from the person", actual=request.kind.value,
            refs=list(request.affected_refs))
    option = request.option(option_id)
    if option is None:
        raise UnknownOption(f"option {option_id!r} is not on decision {request.decision_id!r}",
                            expected=[o.option_id for o in request.options], actual=option_id)

    revision = state.revision + 1
    record = DecisionRecord(
        record_id=record_id(state.session_id, revision, request.decision_id,
                            OUTCOME_AUTO_RESOLVED),
        session_id=state.session_id, decision_id=request.decision_id, kind=request.kind,
        mode=steward.policy.mode, outcome=OUTCOME_AUTO_RESOLVED, actor=Actor.POLICY,
        chosen_option_id=option_id,
        alternatives=[o.option_id for o in request.options if o.option_id != option_id],
        reason=reason, revision=revision, at=at, candidate=dict(request.candidate),
        provenance={"pause_class": pol.pause_class(request.kind)})
    event = _event(state, kind=EventKind.DECISION_AUTO_RESOLVED, actor=Actor.POLICY, at=at,
                   revision=revision, decision=request.decision_id, refs=request.affected_refs,
                   reason=reason, payload={"record": record.model_dump(mode="json"),
                                           "resolved_from_pause": True})
    resumed = state.paused_from or SessionState.READY
    state = _appended(state, event, open_decision_id="", paused_from=None,
                      state=(resumed.value if isinstance(resumed, SessionState) else str(resumed)),
                      pending=list(state.pending[1:]),
                      records=[*[r.model_dump(mode="json") for r in state.records],
                               record.model_dump(mode="json")])
    return _drain(state, steward=steward, at=at, revision=revision)


def note_refusal(state: InquiryInteractionState, refusal: InteractionRefusal, *,
                 at: str) -> InquiryInteractionState:
    """Record a refused response on the trace. EXPLICIT, and never automatic.

    A rejected answer that left no trace would make the session look as though it had never been
    offered one — the Director's rule for its own `Answer`. But recording every refusal
    automatically would let anything that can reach the endpoint grow the log, so the caller
    decides, and the decision is visible in its code rather than buried here.
    """
    event = _event(state, kind=EventKind.RESPONSE_REFUSED, actor=Actor.ENGINE, at=at,
                   revision=state.revision, reason=refusal.why,
                   payload={"refusal": refusal.model_dump()})
    return _appended(state, event,
                     refusals=[*[r.model_dump() for r in state.refusals], refusal.model_dump()])


# ── serialization and replay ─────────────────────────────────────────────────

def to_dict(state: InquiryInteractionState) -> Dict[str, Any]:
    return state.model_dump(mode="json")


def from_dict(data: Mapping[str, Any]) -> InquiryInteractionState:
    return InquiryInteractionState(**dict(data))


def replay(events: Sequence[Any]) -> InquiryInteractionState:
    """Fold an event list back into the state it produced.

    Nothing here reads a snapshot of the state from a payload — each event carries the semantic
    content of what it did, and this function re-derives everything else. That is what makes the
    replay proof worth having: a log that carried its own answer would pass the comparison while
    proving nothing about whether the events were sufficient.
    """
    typed = [e if isinstance(e, InteractionEvent) else InteractionEvent(**dict(e))
             for e in events]
    if not typed:
        raise SessionMisuse("an empty event list replays to no session at all")
    head = typed[0]
    if head.kind is not EventKind.SESSION_OPENED:
        raise SessionMisuse(f"the first event is {head.kind.value!r}, not session_opened; a "
                            f"history that does not start at the beginning is a fragment")

    graph = GraphRef(**dict(head.payload.get("graph") or {}))
    state = InquiryInteractionState(
        session_id=head.session_id, inquiry_id=str(head.payload.get("inquiry_id") or ""),
        mode=InteractionMode(str(head.payload.get("mode") or InteractionMode.CONSULT.value)),
        state=SessionState.FRAMING, graph=graph, created_at=head.at, updated_at=head.at,
        revision=head.revision, events=[head])

    # `mode="json"` throughout, so every enum below is the plain string it serialises to. A python
    # dump would hand back `SessionState.COMPILING` members, and `str()` of a str-mixin enum member
    # is its repr rather than its value — a defect that would show up only as a state name nobody
    # declared, four transitions later.
    data = state.model_dump(mode="json")
    for event in typed[1:]:
        data["events"] = [*data["events"], event.model_dump(mode="json")]
        data["updated_at"] = event.at
        data["revision"] = event.revision
        payload = event.payload

        if event.kind is EventKind.PHASE_ADVANCED:
            data["state"] = str(payload.get("to") or data["state"])

        elif event.kind is EventKind.SESSION_CLOSED:
            data["state"] = str(payload.get("to") or data["state"])

        elif event.kind is EventKind.CANDIDATE_OFFERED:
            data["pending"] = [*data["pending"], *(payload.get("candidates") or ())]

        elif event.kind is EventKind.CANDIDATE_REFUSED:
            data["pending"] = list(data["pending"][1:])
            data["refusals"] = [*data["refusals"], dict(payload.get("refusal") or {})]

        elif event.kind is EventKind.FORMATTER_REFUSED:
            data["refusals"] = [*data["refusals"], dict(payload.get("refusal") or {})]

        elif event.kind is EventKind.DECISION_REQUESTED:
            data["requests"] = [*data["requests"], dict(payload.get("request") or {})]
            if payload.get("paused"):
                data["open_decision_id"] = event.decision_id
                data["paused_from"] = str(payload.get("paused_from") or "")
                data["state"] = SessionState.AWAITING_USER.value

        elif event.kind in (EventKind.DECISION_AUTO_RESOLVED, EventKind.DECISION_UNRESOLVED):
            data["records"] = [*data["records"], dict(payload.get("record") or {})]
            data["pending"] = list(data["pending"][1:])
            if payload.get("resolved_from_pause"):
                # `resolve_without_user` settled a pause, so the session leaves `awaiting_user`
                # here rather than at a response.
                data["state"] = str(data["paused_from"] or SessionState.READY.value)
                data["open_decision_id"] = ""
                data["paused_from"] = None

        elif event.kind is EventKind.RESPONSE_RECEIVED:
            if "response" in payload:
                data["responses"] = [*data["responses"], dict(payload["response"])]
                data["open_decision_id"] = ""
                data["state"] = str(data["paused_from"] or SessionState.READY.value)
                data["paused_from"] = None
                data["pending"] = list(data["pending"][1:])
            if "record" in payload:
                record = dict(payload["record"])
                data["records"] = [*data["records"], record]
                if record.get("outcome") == OUTCOME_DEFERRED:
                    data["deferred"] = [*data["deferred"], str(record.get("decision_id") or "")]

        elif event.kind is EventKind.AMENDMENT_RECORDED:
            data["amendments"] = [*data["amendments"], dict(payload.get("amendment") or {})]

        elif event.kind is EventKind.RESPONSE_REFUSED:
            data["refusals"] = [*data["refusals"], dict(payload.get("refusal") or {})]

    return InquiryInteractionState(**data)


__all__ = [
    "SessionMisuse", "RECORD_OUTCOMES",
    "OUTCOME_AUTO_RESOLVED", "OUTCOME_ANSWERED", "OUTCOME_UNRESOLVED", "OUTCOME_DEFERRED",
    "OUTCOME_REJECTED",
    "open_session", "advance", "close", "offer", "respond", "read_response",
    "resolve_without_user", "note_refusal", "to_dict", "from_dict", "replay",
]
