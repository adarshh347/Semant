"""
HARNESS-002D — the stage order, the budget, and nothing else.

THIS MODULE CONTAINS NO INTELLIGENCE. No prompt, no claim taxonomy, no capability algorithm, no
pause policy, no UI formatting. Every one of those belongs to a merged lane and a copy here would
be a second opinion that drifts. What it owns is the ORDER stages run in, the budget each is
allowed, and the recording of what each one did.

    framer      HARNESS-001A   the prompt, read, with no pixels seen
    theorist    HARNESS-002A   the images, read, interpretive at strongest
    compiler    HARNESS-002A   claims, observables, remainder
    steward     HARNESS-002B   auto-settle or pause, and word the question
    capability  this lane      one locked fixture, simulated, never evidence
    judge       this lane      a verdict per claim
    composer    this lane      a claim-bound provisional answer

## Where Lane B's session begins, and why not sooner

`open_session` takes the graph and hashes it, and there is no public way to attach one afterwards —
by design: the hash is what a decision record points at, so a reader can tell whether two decisions
were made about the same graph. A session opened before compilation would hash `{}` and every later
decision would be pinned to nothing.

So the ENVELOPE owns `framing`, `reading` and `compiling`, and Lane B's state machine owns
everything from the first fork onward. The session is persisted from the moment it is created —
before any model call — with an empty `interaction`, which reads as `framing`. A reading that fails
therefore leaves a real session saying so, rather than leaving nothing at all.

## The budget, and why it is spent on attempt

Phase 1 allows at most one theorist call, one compiler call, zero or one capability invocation, and
one synthesis per completed branch. Every one of them is spent when the stage is ENTERED, not when
it succeeds. A budget spent on success is not a budget: a failing stage would be retried forever by
any loop that treated "no output" as "not yet done".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.inquiry import InquiryMode
from backend.schemas.inquiry_session import (PostRef, SemanticInquirySession, SessionProvenance,
                                             StageEvent, StageName, StageOutcome, sha256_of)
from backend.schemas.inquiry_interaction import InteractionMode, SessionState
from backend.services.inquiry_interaction import (DeliberationPolicy, DeliberationSteward,
                                                  InteractionConflict, machine, read_response)
from backend.services.semantic_compilation import to_image_refs
from backend.services.semantic_compilation.base import CompilationRequest

from . import candidates as candidate_bridge
from . import corpus, ids

PRODUCER = "inquiry_session/coordinator-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_datetime(stamp: str) -> Optional[datetime]:
    """The stage clock's string, as the datetime the framer takes. `None` on anything unparseable —
    the framer then reads its own clock, which is the pre-existing behaviour rather than a crash."""
    try:
        return datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class Stages:
    """The declared stage interfaces. Every one is injected; none is constructed here.

    A stage left `None` is SKIPPED and says so in the ledger. That is how this lane grew — the
    capability, judge and composer arrived after the routes — and it is also how a deployment with
    no composer bound behaves: a session that stops at `ready` and states why, rather than one that
    silently produces no answer.
    """
    framer: Any = None
    theorist: Any = None
    compiler: Any = None
    #: The optional model role that may REWORD a question. The steward itself is never injected:
    #: its policy carries the interaction mode, and a steward built with `auto` and used on a
    #: `consult` session would apply the wrong policy to every fork in it. It is derived from the
    #: session instead, which makes that disagreement unrepresentable.
    formatter: Any = None
    capability: Any = None
    judge: Any = None
    composer: Any = None
    clock: Callable[[], str] = utc_now


@dataclass
class _Ledger:
    """The stage events for one advance, and the sequence that keeps their ids apart."""
    session_id: str
    events: List[StageEvent] = field(default_factory=list)
    seq: int = 0

    def record(self, stage: StageName, outcome: StageOutcome, *, at: str, revision: int = 0,
               detail: str = "", inputs: Sequence[str] = (), outputs: Sequence[str] = ()) -> None:
        self.seq += 1
        self.events.append(StageEvent(
            event_id=ids.stage_id(self.session_id, stage, outcome, self.seq),
            stage=stage, outcome=outcome, at=at, revision=revision, detail=detail,
            input_refs=[str(i) for i in inputs], output_refs=[str(o) for o in outputs]))


def new_session(*, prompt: str, refs: Sequence[PostRef], mode: str,
                session_id: Optional[str] = None, now: Optional[str] = None
                ) -> SemanticInquirySession:
    """The session as it is persisted BEFORE anything runs.

    It already carries the prompt byte for byte and the fingerprint of every post it will read. A
    session that failed during its first model call therefore still proves the corpus was untouched,
    which is the one guarantee that has to hold whether or not anything else did.
    """
    stamp = now or utc_now()
    return SemanticInquirySession(
        session_id=session_id or ids.session_id(prompt, [r.post_id for r in refs]),
        prompt=prompt,
        mode=mode,
        posts=list(refs),
        provenance=SessionProvenance(producer=PRODUCER, mode=mode, prompt_sha256=sha256_of(prompt),
                                     created_at=stamp, updated_at=stamp),
    )


# ── the stages ───────────────────────────────────────────────────────────────

def _frame(session: SemanticInquirySession, stages: Stages, ledger: _Ledger,
           at: str) -> SemanticInquirySession:
    if stages.framer is None:
        ledger.record(StageName.FRAMER, StageOutcome.SKIPPED, at=at,
                      detail="no framer was bound")
        return session
    ledger.record(StageName.FRAMER, StageOutcome.STARTED, at=at)
    context = corpus.corpus_context_for(session.posts)
    # THE CLOCK IS HANDED IN, and it is what makes a replay comparable at all. `mint_inquiry_id`
    # hashes the prompt and the moment, and every id Lane A produces downstream is derived from
    # that inquiry id — so a framer reading the wall clock itself would make a replayed session
    # differ from the original in every claim, observable, alternative and decision id, and the
    # diff would be uniformly red for a reason that has nothing to do with what changed.
    frame = stages.framer.frame(session.prompt, context, mode=InquiryMode.EXPLORE,
                                now=_as_datetime(at))
    payload = frame.model_dump(mode="json")
    ledger.record(StageName.FRAMER, StageOutcome.COMPLETED, at=at,
                  detail=frame.summary(), outputs=[frame.inquiry_id])
    return session.model_copy(update={
        "frame": payload,
        "inquiry_id": frame.inquiry_id,
        "provenance": session.provenance.model_copy(update={
            "frame_producer": frame.provenance.producer,
            "frame_hash": sha256_of(str(sorted(payload.items()))),
        }),
    })


def _read(session: SemanticInquirySession, stages: Stages, ledger: _Ledger,
          at: str) -> Tuple[SemanticInquirySession, Any]:
    """One theorist call, spent on entry. An unavailable reading is a state, not a failure."""
    images = to_image_refs(corpus.image_refs_for(session.posts))
    if stages.theorist is None:
        ledger.record(StageName.THEORIST, StageOutcome.SKIPPED, at=at,
                      detail="no scene theorist was bound")
        return session, None
    if not images:
        ledger.record(StageName.THEORIST, StageOutcome.SKIPPED, at=at,
                      detail="no readable image; a scene reading needs a scene")
        return session, None

    ledger.record(StageName.THEORIST, StageOutcome.STARTED, at=at,
                  inputs=[i.post_id for i in images])
    result = stages.theorist.read(session.prompt, images, inquiry_id=session.inquiry_id,
                                  corpus=corpus.corpus_context_for(session.posts), now=at)
    receipt = result.reading.provenance
    outcome = StageOutcome.COMPLETED if result.available else StageOutcome.UNAVAILABLE
    if result.available and not result.reading.text and not result.reading.blocks:
        outcome = StageOutcome.EMPTY
    ledger.record(StageName.THEORIST, outcome, at=at,
                  detail=f"{receipt.call_topology.value} · {receipt.call_count} call(s)",
                  outputs=[b.block_id for b in result.reading.blocks])
    return session.model_copy(update={"provenance": session.provenance.model_copy(
        update={"theorist_model": receipt.model})}), result


def _compile(session: SemanticInquirySession, reading: Any, stages: Stages, ledger: _Ledger,
             at: str) -> SemanticInquirySession:
    if stages.compiler is None:
        ledger.record(StageName.COMPILER, StageOutcome.SKIPPED, at=at,
                      detail="no semantic compiler was bound")
        return session
    ledger.record(StageName.COMPILER, StageOutcome.STARTED, at=at)
    request = CompilationRequest(
        prompt=session.prompt, inquiry_id=session.inquiry_id, inquiry_frame=dict(session.frame),
        reading=reading.reading if reading is not None else None,
        images=tuple(to_image_refs(corpus.image_refs_for(session.posts))),
        corpus=corpus.corpus_context_for(session.posts), now=at,
        inherited_refusals=reading.refusals if reading is not None else (),
        inherited_notes=reading.notes if reading is not None else ())
    graph = stages.compiler.compile(request)
    payload = graph.model_dump(mode="json", by_alias=True)
    outcome = StageOutcome.COMPLETED if graph.claims else StageOutcome.EMPTY
    if graph.provenance.compiler_kind == "unavailable":
        outcome = StageOutcome.UNAVAILABLE
    ledger.record(StageName.COMPILER, outcome, at=at, detail=graph.summary(),
                  outputs=[c.claim_id for c in graph.claims])
    return session.model_copy(update={
        "graph": payload,
        "refusals": [r.model_dump(mode="json") for r in graph.refusals],
        "gaps": _gaps_from(graph),
        "provenance": session.provenance.model_copy(update={
            "compiler_model": graph.provenance.compiler.model if graph.provenance.compiler else None,
        }),
    })


def _gaps_from(graph: Any) -> List[str]:
    """What nothing can currently serve. A claim with no observable is not a gap — it may simply be
    interpretive — so only the compiler's own notes about unserved requests are carried."""
    return [n for n in graph.notes if "no instrument" in n or "capability" in n.lower()]


# ── the deliberation ─────────────────────────────────────────────────────────

def _open_interaction(session: SemanticInquirySession, stages: Stages, ledger: _Ledger,
                      at: str) -> SemanticInquirySession:
    """Lane B's session, opened once there is a graph to open it ABOUT."""
    state = machine.open_session(
        session_id=session.session_id, mode=InteractionMode(session.mode), at=at,
        inquiry_id=session.inquiry_id, graph=dict(session.graph),
        graph_id=str(session.graph.get("graph_id") or ""))
    state = machine.advance(state, SessionState.COMPILING, at=at,
                            reason="the graph is compiled; forks may now be offered")
    return session.model_copy(update={
        "interaction": machine.to_dict(state),
        "revision": state.revision,
        "provenance": session.provenance.model_copy(update={"graph_hash": state.graph.graph_hash}),
    })


def _deliberate(session: SemanticInquirySession, stages: Stages, ledger: _Ledger,
                at: str) -> SemanticInquirySession:
    """Offer every fork the compiler declared. Lane B settles or pauses; this lane does neither."""
    state = machine.from_dict(session.interaction)
    servable = servable_classes(stages)
    forks = candidate_bridge.from_graph(session.graph, servable_classes=servable)
    if not forks:
        ledger.record(StageName.STEWARD, StageOutcome.EMPTY, at=at,
                      detail="the compiler declared no fork; nothing needed deciding")
        return session

    ledger.record(StageName.STEWARD, StageOutcome.STARTED, at=at,
                  inputs=[f["candidate_id"] for f in forks])
    state = machine.offer(state, forks, steward=steward_for(session, stages), at=at)
    paused = state.state is SessionState.AWAITING_USER
    ledger.record(StageName.STEWARD,
                  StageOutcome.COMPLETED if not paused else StageOutcome.EMPTY,
                  at=at, revision=state.revision,
                  detail=("a person is being asked" if paused
                          else "every fork was settled without asking"),
                  outputs=[r.decision_id for r in state.requests])
    return session.model_copy(update={"interaction": machine.to_dict(state),
                                      "revision": state.revision})


def steward_for(session: SemanticInquirySession, stages: Stages) -> DeliberationSteward:
    """The steward for THIS session's mode. Derived, never injected — see `Stages.formatter`."""
    return DeliberationSteward(policy=DeliberationPolicy(mode=InteractionMode(session.mode)),
                               formatter=stages.formatter)


def servable_classes(stages: Stages) -> Tuple[str, ...]:
    """What the bound capability adapter can stand in for. Empty when none is bound, which makes
    every option undeclared and every fork a pause — the correct behaviour for a deployment that
    cannot even simulate the route being chosen."""
    adapter = stages.capability
    return tuple(getattr(adapter, "servable_classes", ()) or ()) if adapter is not None else ()


# ── the drivers ──────────────────────────────────────────────────────────────

def begin(session: SemanticInquirySession, stages: Stages) -> SemanticInquirySession:
    """Frame, read, compile, deliberate — then stop at the first honest boundary.

    Every stage is entered at most once. The function returns a session that is either waiting on a
    person, ready for work, or finished; it never returns one that is mid-stage, because a session
    persisted mid-stage would be resumable into a phase nothing had recorded leaving.
    """
    at = stages.clock()
    ledger = _Ledger(session.session_id)

    session = _frame(session, stages, ledger, at)
    session, reading = _read(session, stages, ledger, at)
    session = _compile(session, reading, stages, ledger, at)
    session = session.model_copy(update={"stages": [*session.stages, *ledger.events]})

    if not session.graph.get("claims"):
        return _finish(session, SessionState.EXHAUSTED, at,
                       "nothing was compiled, so there is nothing to investigate and nothing to "
                       "compose. That is a result, not a failure.", stages)

    session = _open_interaction(session, stages, ledger, at)
    session = _deliberate(session, stages, ledger, at)
    session = session.model_copy(update={"stages": [*session.stages,
                                                    *ledger.events[len(session.stages):]]})
    return _continue(session, stages)


def resume(session: SemanticInquirySession, response: Mapping[str, Any],
           stages: Stages) -> SemanticInquirySession:
    """Apply a person's answer to the OPEN decision and carry on from where it stopped.

    Raises the typed `InteractionConflict` Lane B produces. Nothing is caught here: the route maps
    each of the nine to its status code, and a coordinator that swallowed one would have to invent
    a reply for a person whose answer was never applied.
    """
    at = stages.clock()
    state = machine.from_dict(session.interaction)
    state = machine.respond(state, read_response(response),
                            steward=steward_for(session, stages), at=at)
    session = session.model_copy(update={"interaction": machine.to_dict(state),
                                         "revision": state.revision})
    return _continue(session, stages)


# ── the selection a settled fork made ────────────────────────────────────────

def selection_for(session: SemanticInquirySession) -> Tuple[Optional[Dict[str, Any]],
                                                            Optional[Dict[str, Any]]]:
    """(observable, alternative) — the operational route a settled decision actually chose.

    Found through the DECISION's `affected_refs`, which name the observable the fork was about, and
    then matched to one of that observable's alternatives BY LABEL. The label is the link because
    ids cannot be: Lane A mints `alternative_id` from `(inquiry, OWNER, label)` and the owner is the
    decision in one place and the observable in the other, so the same choice has two ids by
    construction and only the observable's copy carries capability classes.

    Returns `(None, None)` when nothing was chosen — an unresolved, rejected or deferred fork. That
    is not a failure to find a selection; it is the absence of one, and nothing should run.
    """
    if not session.interaction:
        return None, None
    state = machine.from_dict(session.interaction)
    observables = {str(o.get("observable_id") or ""): o
                   for o in (session.graph.get("observables") or ())
                   if isinstance(o, Mapping)}

    for record in state.records:
        if not record.chosen_option_id:
            continue
        request = state.request(record.decision_id)
        if request is None:
            continue
        option = request.option(record.chosen_option_id)
        if option is None:
            continue
        wanted = ids.normalise(option.label)
        for ref in request.affected_refs:
            observable = observables.get(str(ref))
            if observable is None:
                continue
            for alternative in observable.get("alternatives") or ():
                if not isinstance(alternative, Mapping):
                    continue
                label = " ".join(str(alternative.get("label") or "").split()).strip().lower()
                if ids.normalise(label) == wanted:
                    return dict(observable), dict(alternative)
            # The fork named this observable and no alternative matched the chosen label. The
            # observable is still the thing that was chosen ABOUT, so it is returned without one.
            return dict(observable), None
    return None, None


# ── the remaining stages ─────────────────────────────────────────────────────

def _execute(session: SemanticInquirySession, stages: Stages, ledger: _Ledger,
             at: str) -> SemanticInquirySession:
    """Zero or one capability invocation, depending on what was decided. Never two.

    THE FIREWALL IS THE SESSION, not the adapter's counter. A fresh adapter is built per request,
    so an instance counter resets across a pause; the receipt already on the session does not. This
    check is the one that survives a restart, a redeploy and a second process.
    """
    if stages.capability is None:
        ledger.record(StageName.CAPABILITY, StageOutcome.SKIPPED, at=at,
                      detail="no capability adapter is bound to this deployment")
        return session
    if session.capability_receipts:
        ledger.record(StageName.CAPABILITY, StageOutcome.SKIPPED, at=at,
                      detail=f"this session has already spent its one attempt on receipt "
                             f"{session.capability_receipts[0].receipt_id}",
                      inputs=[r.receipt_id for r in session.capability_receipts])
        return session

    observable, alternative = selection_for(session)
    if observable is None:
        ledger.record(StageName.CAPABILITY, StageOutcome.SKIPPED, at=at,
                      detail="no fork was settled on an operational route, so nothing was "
                             "commissioned. Nothing was chosen on anybody's behalf.")
        return session

    ledger.record(StageName.CAPABILITY, StageOutcome.STARTED, at=at,
                  inputs=[str(observable.get("observable_id") or "")])
    receipt = stages.capability.invoke(
        session_id=session.session_id, observable=observable, alternative=alternative,
        images=corpus.image_refs_for(session.posts), at=at)
    outcome = {"simulated": StageOutcome.COMPLETED, "live": StageOutcome.COMPLETED,
               "empty": StageOutcome.EMPTY, "refused": StageOutcome.REFUSED,
               "unavailable": StageOutcome.UNAVAILABLE,
               "capability_gap": StageOutcome.EMPTY}.get(receipt.status.value, StageOutcome.EMPTY)
    ledger.record(StageName.CAPABILITY, outcome, at=at,
                  detail=f"{receipt.capability} · {receipt.execution_mode.value} · "
                         f"{receipt.status.value}",
                  outputs=[receipt.receipt_id])
    return session.model_copy(update={
        "capability_receipts": [*session.capability_receipts, receipt],
        "selected_observable_ref": str(observable.get("observable_id") or ""),
    })


def _judge(session: SemanticInquirySession, stages: Stages, ledger: _Ledger,
           at: str) -> SemanticInquirySession:
    if stages.judge is None:
        ledger.record(StageName.JUDGE, StageOutcome.SKIPPED, at=at,
                      detail="no evidence judge is bound to this deployment")
        return session
    ledger.record(StageName.JUDGE, StageOutcome.STARTED, at=at)
    verdicts = stages.judge(session)
    outcome = StageOutcome.COMPLETED if verdicts else StageOutcome.EMPTY
    counts = {}
    for v in verdicts:
        counts[v.outcome.value] = counts.get(v.outcome.value, 0) + 1
    ledger.record(StageName.JUDGE, outcome, at=at,
                  detail=" · ".join(f"{k} {n}" for k, n in sorted(counts.items())) or "no claims",
                  outputs=[v.verdict_id for v in verdicts])
    return session.model_copy(update={"verdicts": list(verdicts)})


def _compose(session: SemanticInquirySession, stages: Stages, ledger: _Ledger,
             at: str) -> SemanticInquirySession:
    """One synthesis per completed branch. The composer refuses rather than inventing a reference."""
    ledger.record(StageName.COMPOSER, StageOutcome.STARTED, at=at,
                  inputs=[v.verdict_id for v in session.verdicts])
    synthesis = stages.composer.compose(session, at=at)
    if synthesis is None or not synthesis.sections:
        ledger.record(StageName.COMPOSER, StageOutcome.EMPTY, at=at,
                      detail="the composer wrote nothing it could bind to a claim")
        return session
    ledger.record(StageName.COMPOSER, StageOutcome.COMPLETED, at=at,
                  detail=f"{len(synthesis.sections)} section(s)",
                  outputs=[s.section_id for s in synthesis.sections])
    return session.model_copy(update={
        "synthesis": synthesis,
        "provenance": session.provenance.model_copy(update={
            "composer_model": str((synthesis.provenance or {}).get("model") or "") or None}),
    })


def _continue(session: SemanticInquirySession, stages: Stages) -> SemanticInquirySession:
    """From wherever the session now is, to the next boundary.

    Each remaining stage is entered at most once per advance and is SKIPPED with a reason when
    nothing is bound — a deployment missing a composer stops at an honest `exhausted` rather than
    silently producing no answer.
    """
    at = stages.clock()
    state = machine.from_dict(session.interaction)
    if state.state is SessionState.AWAITING_USER:
        return session
    if state.state in (SessionState.COMPLETE, SessionState.EXHAUSTED, SessionState.REFUSED,
                       SessionState.ERROR):
        return session

    ledger = _Ledger(session.session_id, seq=len(session.stages))
    state = machine.advance(state, SessionState.READY, at=at,
                            reason="every fork is settled; work may be commissioned")

    state = machine.advance(state, SessionState.EXECUTING, at=at,
                            reason="commissioning at most one capability request")
    session = _apply(session, state, ledger)
    session = _execute(session, stages, ledger, at)

    state = machine.advance(machine.from_dict(session.interaction), SessionState.JUDGING, at=at,
                            reason="deciding what each claim now rests on")
    session = _apply(session, state, ledger)
    session = _judge(session, stages, ledger, at)

    if stages.composer is None:
        ledger.record(StageName.COMPOSER, StageOutcome.SKIPPED, at=at,
                      detail="no synthesis composer is bound to this deployment")
        session = session.model_copy(update={"stages": [*session.stages, *ledger.events]})
        return _finish(session, SessionState.EXHAUSTED, at,
                       "every claim has a verdict and no composer is bound, so no answer was "
                       "written. Nothing was invented in its place.", stages)

    state = machine.advance(machine.from_dict(session.interaction), SessionState.COMPOSING, at=at,
                            reason="binding an answer to the claims it rests on")
    session = _apply(session, state, ledger)
    session = _compose(session, stages, ledger, at)
    session = session.model_copy(update={"stages": [*session.stages, *ledger.events]})
    return _finish(session, SessionState.COMPLETE, at,
                   "the chain closed: every claim carries a verdict and every sentence of the "
                   "answer names what it rests on.", stages)


def _apply(session: SemanticInquirySession, state: Any,
           ledger: _Ledger) -> SemanticInquirySession:
    """Carry a Lane B transition onto the envelope. Kept apart so no stage writes the state itself.

    The ledger's sequence follows the session's stage count so two advances in one request cannot
    mint the same event id.
    """
    ledger.seq = max(ledger.seq, len(session.stages) + len(ledger.events))
    return session.model_copy(update={"interaction": machine.to_dict(state),
                                      "revision": state.revision})


def _finish(session: SemanticInquirySession, to: SessionState, at: str, why: str,
            stages: Stages) -> SemanticInquirySession:
    """Close the session, or record that it never opened one to close."""
    if not session.interaction:
        return session.model_copy(update={"stop_reason": why,
                                          "interaction": {"state": to.value, "revision": 0}})
    state = machine.from_dict(session.interaction)
    if state.state is SessionState.AWAITING_USER:
        return session
    if state.state not in (SessionState.COMPLETE, SessionState.EXHAUSTED, SessionState.REFUSED,
                           SessionState.ERROR):
        state = machine.close(state, to, at=at, reason=why)
    return session.model_copy(update={"interaction": machine.to_dict(state),
                                      "revision": state.revision, "stop_reason": why})


__all__ = ["PRODUCER", "Stages", "utc_now", "new_session", "servable_classes", "steward_for",
           "selection_for", "begin", "resume", "InteractionConflict", "read_response",
           "SessionState", "machine"]
