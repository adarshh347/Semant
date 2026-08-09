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
    frame = stages.framer.frame(session.prompt, context, mode=InquiryMode.EXPLORE)
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


def _continue(session: SemanticInquirySession, stages: Stages) -> SemanticInquirySession:
    """From wherever the session now is, to the next boundary.

    Phase 1's remaining stages — capability, judge, composer — are added by later commits. Until
    one is bound it is SKIPPED and says so, and the session stops at `ready` rather than pretending
    to have finished.
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
    session = session.model_copy(update={"interaction": machine.to_dict(state),
                                         "revision": state.revision})

    for stage, bound in ((StageName.CAPABILITY, stages.capability),
                         (StageName.JUDGE, stages.judge),
                         (StageName.COMPOSER, stages.composer)):
        if bound is None:
            ledger.record(stage, StageOutcome.SKIPPED, at=at,
                          detail=f"no {stage.value} was bound to this deployment")
    session = session.model_copy(update={"stages": [*session.stages, *ledger.events]})

    if stages.composer is None:
        return _finish(session, SessionState.EXHAUSTED, at,
                       "the chain reached `ready` and no composer is bound, so no answer was "
                       "written. Nothing was invented in its place.", stages)
    return session


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


__all__ = ["PRODUCER", "Stages", "utc_now", "new_session", "servable_classes", "steward_for", "begin", "resume",
           "InteractionConflict", "read_response", "SessionState", "machine"]
