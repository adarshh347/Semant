"""
HARNESS-002D — the stage order, the budget, and nothing else.

## Who records that a stage started

NOT these functions, since HARNESS-003B. `steps.start` writes the `started` attempt and persists it
BEFORE the stage is entered, which is the whole point of the checkpoint: a stage body that recorded
its own start would do so inside the same call it is about to block in, and a process that died
there would leave nothing behind. Each body below therefore records exactly ONE attempt — its
ending — and `steps.run` carries the driver's `started_at` onto it so the duration is real.

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
                                             StageName, StageOutcome, sha256_of)
from backend.schemas.inquiry_stage import (AttemptExecutionMode, StageAttempt,
                                           StageAttemptOutcome, SubstageEvent,
                                           duration_ms_between)
from backend.schemas.inquiry_interaction import InteractionMode, SessionState
from backend.services.inquiry_interaction import (DeliberationPolicy, DeliberationSteward,
                                                  InteractionConflict, machine, read_response)
from backend.services.semantic_compilation import to_image_refs
from backend.services.semantic_compilation.base import CompilationRequest

from . import candidates as candidate_bridge
from . import corpus, ids, outcomes

PRODUCER = "inquiry_session/coordinator-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def has_interaction(session: SemanticInquirySession) -> bool:
    """Whether Lane B's state machine was ever opened on this session.

    NOT `bool(session.interaction)`. A session that compiled nothing never opens one, and `_finish`
    writes a two-key STUB — `{"state": "exhausted", "revision": 0}` — so the envelope still reports
    a state rather than an empty mapping a reader would have to interpret. That stub is truthy and
    it is not a state machine. The live rehearsal is where the difference surfaced, as a pydantic
    error about a missing `session_id` several frames away from the thing that wrote it.
    """
    return bool(session.interaction.get("session_id"))


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
    #: An injected substage observer, offered to any stage that DECLARES it wants one.
    #:
    #: The declaration is `wants_substage_observer = True` on the stage object — an explicit opt-in
    #: rather than signature introspection. Guessing whether a callee accepts a keyword by reading
    #: its parameters is a check whose evidence is the shape of a function rather than a statement
    #: of intent, and it fails silently in exactly the case that matters: a stage that grew a
    #: `**kwargs` would start receiving an observer nobody meant it to have.
    #:
    #: Left None here. Lane D binds a richer one; until then the coordinator records the floor it
    #: holds itself — how many inputs were selected, and the topology the stage declared.
    observer: Optional[Callable[..., None]] = None
    clock: Callable[[], str] = utc_now


#: v1 `StageOutcome` → the v2 attempt vocabulary. Declared as a table rather than a cast, because
#: the two enums overlap by seven values and diverge by four, and a bare `StageAttemptOutcome(v)`
#: would work today and break silently the moment either enum grew a value the other lacked.
_OUTCOME_OF: Dict[str, StageAttemptOutcome] = {
    StageOutcome.STARTED.value: StageAttemptOutcome.STARTED,
    StageOutcome.COMPLETED.value: StageAttemptOutcome.COMPLETED,
    StageOutcome.EMPTY.value: StageAttemptOutcome.EMPTY,
    StageOutcome.UNAVAILABLE.value: StageAttemptOutcome.UNAVAILABLE,
    StageOutcome.REFUSED.value: StageAttemptOutcome.REFUSED,
    StageOutcome.SKIPPED.value: StageAttemptOutcome.SKIPPED,
    StageOutcome.ERROR.value: StageAttemptOutcome.ERROR,
}


def attempt_outcome(outcome: Any) -> StageAttemptOutcome:
    if isinstance(outcome, StageAttemptOutcome):
        return outcome
    key = getattr(outcome, "value", outcome)
    if key not in _OUTCOME_OF:
        raise KeyError(f"no attempt outcome declared for stage outcome {key!r}")
    return _OUTCOME_OF[key]


@dataclass
class _Ledger:
    """The stage attempts for one advance, and the sequence that keeps their ids apart.

    `record` keeps the call shape the seven stage functions already use and grows the fields a
    live stage stream needs. Every timestamp is handed in; nothing here reads a clock.
    """
    session_id: str
    events: List[StageAttempt] = field(default_factory=list)
    seq: int = 0
    #: Substage progress reported from inside the stage currently running, drained onto its
    #: terminal attempt. A list rather than a callback into the attempt itself, because the attempt
    #: does not exist yet while the stage is producing them.
    substages: List[SubstageEvent] = field(default_factory=list)

    def observe(self, label: str, *, index: Optional[int] = None, total: Optional[int] = None,
                at: Optional[str] = None, refs: Sequence[str] = (), detail: str = "",
                outcome: str = "") -> None:
        """The injected observer's landing point. Anything a stage reports about its own insides."""
        self.substages.append(SubstageEvent(
            substage_id=ids.stage_id(self.session_id, "substage", label,
                                     len(self.substages) + 1),
            label=str(label), index=index, total=total, at=at, outcome=outcome,
            refs=[str(r) for r in refs], detail=detail))

    def record(self, stage: StageName, outcome: Any, *, at: str, revision: int = 0,
               detail: str = "", inputs: Sequence[str] = (), outputs: Sequence[str] = (),
               started_at: Optional[str] = None, role: str = "", model: Optional[str] = None,
               provider: Optional[str] = None,
               execution_mode: AttemptExecutionMode = AttemptExecutionMode.NONE,
               input_counts: Optional[Mapping[str, int]] = None,
               output_counts: Optional[Mapping[str, int]] = None,
               call_topology: str = "", planned_calls: Optional[int] = None,
               actual_calls: Optional[int] = None,
               truncation_source: Any = None,
               receipts: Sequence[str] = (), gaps: Sequence[str] = (),
               refusals: Sequence[str] = (),
               provenance: Optional[Mapping[str, Any]] = None) -> StageAttempt:
        self.seq += 1
        resolved = attempt_outcome(outcome)
        terminal = resolved is not StageAttemptOutcome.STARTED
        completed_at = at if terminal else None
        # A duration exists only where BOTH ends were observed. A stage that never recorded a start
        # — a `skipped`, say — has no duration, and writing 0 there would report an instant stage
        # where there was one that never ran.
        duration = duration_ms_between(started_at, completed_at) if started_at else None
        attempt = StageAttempt(
            attempt_id=ids.stage_id(self.session_id, stage, resolved.value, self.seq),
            stage=stage, outcome=resolved, sequence=self.seq,
            revision=revision,
            queued_at=at if not terminal else (started_at or at),
            started_at=started_at, completed_at=completed_at, duration_ms=duration,
            role=role, model=model, provider=provider, execution_mode=execution_mode,
            input_refs=[str(i) for i in inputs], output_refs=[str(o) for o in outputs],
            input_counts={str(k): int(v) for k, v in (input_counts or {}).items()},
            output_counts={str(k): int(v) for k, v in (output_counts or {}).items()},
            call_topology=str(call_topology or ""), planned_calls=planned_calls,
            actual_calls=actual_calls,
            substages=list(self.substages) if terminal else [],
            truncation_source=(truncation_source if truncation_source is not None
                               else StageAttempt.model_fields["truncation_source"].default),
            summary=detail, receipt_refs=[str(r) for r in receipts],
            gap_refs=[str(g) for g in gaps], refusal_refs=[str(r) for r in refusals],
            provenance=dict(provenance or {}))
        if terminal:
            self.substages = []
        self.events.append(attempt)
        return attempt


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

    started_at = at
    # THE DECLARED FLOOR, recorded before the call and independent of whether the stage reports
    # anything about its own insides. 002R's rehearsal watched four images being read as one opaque
    # wait; the count of what was selected is a fact this coordinator holds itself, so it is on the
    # ledger whether or not a theorist ever learns to narrate.
    ledger.observe(f"reading {len(images)} selected image(s)", index=0, total=len(images), at=at,
                   refs=[i.post_id for i in images])
    result = _read_with_observer(stages, session, images, at, ledger)
    receipt = result.reading.provenance
    finished_at = stages.clock()
    truncation = outcomes.detect_truncation(receipt, producer=stages.theorist)
    outcome = outcomes.outcome_for(
        produced=bool(result.reading.text or result.reading.blocks),
        truncation=truncation, adequacy=outcomes.declared_adequacy(result.reading),
        unavailable=not result.available)
    ledger.record(StageName.THEORIST, outcome, at=finished_at, started_at=started_at,
                  detail=f"{receipt.call_topology.value} · {receipt.call_count} call(s)"
                         + (f" · {truncation.detail}" if truncation.truncated else ""),
                  outputs=[b.block_id for b in result.reading.blocks],
                  inputs=[i.post_id for i in images], role=receipt.role or "scene_theorist",
                  model=receipt.model, provider=receipt.provider,
                  execution_mode=AttemptExecutionMode.LIVE,
                  input_counts={"images": len(images)},
                  output_counts={"reading blocks": len(result.reading.blocks)},
                  call_topology=receipt.call_topology.value, actual_calls=receipt.call_count,
                  truncation_source=truncation.source,
                  refusals=[r.what for r in (result.refusals or ())],
                  provenance={"truncation": truncation.detail})
    return session.model_copy(update={
        # PERSISTED HERE, not left in memory for the compiler to receive as an argument. A
        # checkpointed chain runs the compiler from the store, possibly in a later process; a
        # reading that lived only in a local variable would have to be bought again.
        "reading": {"reading": result.reading.model_dump(mode="json"),
                    "refusals": [r.model_dump(mode="json") for r in (result.refusals or ())],
                    "notes": list(result.notes or ()),
                    "available": bool(result.available)},
        "provenance": session.provenance.model_copy(
            update={"theorist_model": receipt.model})}), result


def reading_of(session: SemanticInquirySession) -> Optional[Any]:
    """The theorist's own output, rebuilt from the session rather than received as an argument.

    THE CHECKPOINT SEAM. Before HARNESS-003B the compiler was handed the live `ReadingResult` the
    theorist had just returned, which is only possible while both run inside one call. A stepped
    chain runs the compiler from the store — perhaps in another process, certainly after a write —
    so the reading has to be reconstructable from persisted bytes or the step is not resumable at
    all. Returns None when nothing was read, which is the same thing the argument used to be.
    """
    from backend.schemas.semantic_compilation import CompilerRefusal, SceneReading

    stored = session.reading or {}
    payload = stored.get("reading")
    if not isinstance(payload, Mapping) or not payload:
        return None
    refusals = tuple(CompilerRefusal.model_validate(dict(r))
                     for r in (stored.get("refusals") or ()) if isinstance(r, Mapping))
    return _StoredReading(reading=SceneReading.model_validate(dict(payload)),
                          refusals=refusals,
                          notes=tuple(str(n) for n in (stored.get("notes") or ())),
                          available=bool(stored.get("available")))


@dataclass(frozen=True)
class _StoredReading:
    """A `ReadingResult` rebuilt from the store. Same four fields the compiler reads, and no
    behaviour — a class rather than a tuple so a caller cannot get the order wrong."""
    reading: Any
    refusals: Tuple[Any, ...] = ()
    notes: Tuple[str, ...] = ()
    available: bool = False


def _wants_observer(stage: Any) -> bool:
    """Whether this stage has DECLARED that it reports its own insides."""
    return bool(getattr(stage, "wants_substage_observer", False))


def _read_with_observer(stages: Stages, session: SemanticInquirySession, images: Any, at: str,
                        ledger: "_Ledger") -> Any:
    """Call the theorist, handing it an observer only if it said it wants one.

    The coordinator learns nothing about what a scene theorist is made of by doing this — it hands
    over a callable and receives whatever the stage chooses to report. A runner that had to import
    the semantic compiler to discover its per-image progress could not be reused for the next stage,
    and would break every time that lane refactored.
    """
    call = dict(inquiry_id=session.inquiry_id,
                corpus=corpus.corpus_context_for(session.posts), now=at)
    if _wants_observer(stages.theorist):
        sink = stages.observer or ledger.observe
        call["on_substage"] = sink
    return stages.theorist.read(session.prompt, images, **call)


def _compile(session: SemanticInquirySession, reading: Any, stages: Stages, ledger: _Ledger,
             at: str) -> SemanticInquirySession:
    if stages.compiler is None:
        ledger.record(StageName.COMPILER, StageOutcome.SKIPPED, at=at,
                      detail="no semantic compiler was bound")
        return session
    blocks = len(((session.reading.get("reading") or {}).get("blocks")) or ())
    started_at = at
    request = CompilationRequest(
        prompt=session.prompt, inquiry_id=session.inquiry_id, inquiry_frame=dict(session.frame),
        reading=reading.reading if reading is not None else None,
        images=tuple(to_image_refs(corpus.image_refs_for(session.posts))),
        corpus=corpus.corpus_context_for(session.posts), now=at,
        inherited_refusals=reading.refusals if reading is not None else (),
        inherited_notes=reading.notes if reading is not None else ())
    graph = stages.compiler.compile(request)
    payload = graph.model_dump(mode="json", by_alias=True)
    finished_at = stages.clock()
    receipt = graph.provenance.compiler
    truncation = outcomes.detect_truncation(receipt, producer=stages.compiler)
    outcome = outcomes.outcome_for(
        produced=bool(graph.claims), truncation=truncation,
        adequacy=outcomes.declared_adequacy(payload),
        unavailable=graph.provenance.compiler_kind == "unavailable")
    ledger.record(StageName.COMPILER, outcome, at=finished_at, started_at=started_at,
                  detail=graph.summary() + (f" · {truncation.detail}" if truncation.truncated
                                            else ""),
                  outputs=[c.claim_id for c in graph.claims], role="semantic_compiler",
                  model=receipt.model if receipt else None,
                  provider=receipt.provider if receipt else None,
                  execution_mode=AttemptExecutionMode.LIVE,
                  input_counts={"reading blocks": blocks},
                  output_counts={"claims": len(graph.claims),
                                 "observables": len(graph.observables),
                                 "remainder": len(graph.semantic_remainder)},
                  call_topology=receipt.call_topology.value if receipt else "",
                  actual_calls=receipt.call_count if receipt else None,
                  truncation_source=truncation.source,
                  refusals=[r.what for r in graph.refusals],
                  provenance={"truncation": truncation.detail,
                              "compiler_kind": graph.provenance.compiler_kind})
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

    NOW A LOOP OVER `steps`, and the delegation is the HARNESS-003B change. The order, the budget
    and every stage body are unchanged; what moved is that each stage is entered from persisted
    state rather than from where control flow happens to be, so the same sequence can be driven one
    checkpoint at a time by `driver.py` and watched while it runs.

    Kept as a function because it is the honest synchronous form of the chain: a test that wants a
    finished session should not have to stand up an event loop and a store to get one.
    """
    from . import steps
    return steps.advance_all(session, stages)


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
    if not has_interaction(session):
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
    if not has_interaction(session):
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


__all__ = ["PRODUCER", "Stages", "utc_now", "has_interaction", "new_session", "servable_classes",
           "steward_for",
           "selection_for", "begin", "resume", "InteractionConflict", "read_response",
           "SessionState", "machine"]
