"""
CIRCUIT-002 A1 — the Differential loop controller: inspect → re-plan → repeat.

The Director is one-shot: plan → execute → suggestions. A1 wraps it in a CLOSED LOOP that inspects
the REAL results of a round and re-plans grounded in the NEW evidence those results left in working
memory. Each round is a full Director pass; the loop's only job is to decide whether another round
is warranted and to trace what every round did.

THE BOUNDARY THAT DEFINES THIS GATE. Re-plan-on-RESULTS is allowed; re-prompt-around-a-REFUSAL is
forbidden. The controller calls `director.plan(intention, memory)` with the SAME intention every
round — it never edits the intention, and never tells the planner "step X was refused, try another
way." The only thing that changes between rounds is working memory, which advances ONLY through
real produced evidence. So a step that was refused because its input never arrived can come to run
in a later round IFF some other step actually produced that input (that is re-plan-on-results); it
never runs because the loop nagged the planner to route around the refusal (that would be
re-prompting, and there is no code path for it). A refusal ends that branch, is reported, and is
never retried by fiat.

DECIDE. A round CONTINUES only if it added NEW evidence (a new region / mark / ground / percept).
It STOPS on: a fixed point (the planner can only re-propose steps already run — nothing new to do),
a round that added nothing, a round of only refusals/empties, or the `max_rounds` backstop.
`weakest_link` stays the minimum reported confidence across ALL rounds — never a synthesized
multi-round score, which would be exactly the fabrication the chain-provenance module exists to
prevent.

ASK, RATHER THAN DEAD-END (A2, extended by A2-EXT). At a stop point — never mid-round — the loop
may emit one grounded question when the only thing between it and progress is something a person
could say. A2 read that off the closed doors, which meant it only fired when something had been
REFUSED; a planner proposing nothing at all refuses nothing, so `nothing_planned` stayed a silent
dead end. A2-EXT closes it with a deterministic rule-based diagnostic (`_diagnostic_probe`) that
tells "no actuator serves this" apart from "one does, and I lack the phrase" — without asking the
model anything a second time.

UNATTENDED-SAFE. Like the Director it wraps: it produces SUGGESTIONS only (into the execution
context's quarantine), never accepts a mark, never writes a post. It is actuator-agnostic — hand it
`stub_registry()` for a deterministic offline loop or `real_registry(ctx)` for a guarded real run.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .capabilities import Resource
from .execution import EMPTY, OK, ActuatorRunner, ChainResult, execute
from .memory import WorkingMemory
from .plan import Plan, Step, resolve
from .questions import (Proposal, Question, is_question_able,
                        missing_param_of, question_for)
from .planner import PLANNER_RULE_BASED, Director, RuleBasedPlanner

# Resources that count as EVIDENCE — the loop advances only on these. READING is a sentence about
# the image, never evidence in it; IMAGE/PHRASE are inputs the curator brought, not products.
_EVIDENCE_KINDS = (Resource.REGION, Resource.MARK, Resource.GROUND, Resource.PERCEPT)

# Verdicts / stop reasons.
CONTINUE = "continue"
STOP_FIXED_POINT = "fixed_point"          # the planner can only re-propose already-run steps
STOP_NO_NEW_EVIDENCE = "no_new_evidence"  # a round ran but left nothing new in memory
STOP_ONLY_REFUSALS = "only_refusals_or_empties"  # nothing ran to OK-with-evidence
STOP_NOTHING_PLANNED = "nothing_planned"  # the planner proposed no steps and refused none
STOP_MAX_ROUNDS = "max_rounds"            # the backstop
STOP_ONLY_CLOSED_DOORS = "only_closed_doors"  # the round proposed nothing but already-shut doors
# A2 — the terminal state that is not a dead end. The loop stopped because it needs something only
# a human can supply, and it says exactly what. Resume is A3; A2 emits and returns.
AWAITING_ANSWER = "awaiting_answer"

# A2-EXT — outcomes of the deterministic diagnostic run on the `nothing_planned` dead end. A closed
# set, because the receipt is read by machines as well as people.
PROBE_NO_SHAPE = "no_rule_based_shape"      # no actuator serves this intention at all — ask nothing
PROBE_RESOLVES = "resolves_cleanly"         # the shape runs; the empty proposal was not about a gap
PROBE_NO_ASKABLE_DOOR = "no_askable_door"   # it is refused, but for the loop's own work (input)
PROBE_QUESTION = "question_recovered"       # a missing PARAM — a human could unblock this


def _sig(step: Step) -> str:
    """A stable identity for a step by WHAT it asks, not which round asked it — so re-proposing
    the same actuator+params is recognised as already-done. Ids/notes are excluded (they vary)."""
    return json.dumps([step.actuator, step.params], sort_keys=True, default=str)


def _door_still_closed(step: Step, memory: WorkingMemory) -> bool:
    """Would this step STILL be refused, on the evidence that exists now?

    Asked by re-running the real gate on the step alone, rather than by re-implementing the
    requirement check — so "the reason still holds" means exactly what `resolve()` means by it,
    and cannot drift from it.

    A step refused for a MISSING INPUT re-opens the moment something produces that input: the
    curator found the key, the door is no longer shut. A step refused for a missing param or an
    unknown actuator never re-opens, because no amount of looking at the picture supplies it.
    """
    return bool(resolve([step], memory).refused)


def _new_evidence(before: Dict[Resource, int], after: Dict[Resource, int]) -> Dict[str, int]:
    """The evidence kinds whose count rose this round, and by how much. Empty ⇒ nothing new."""
    out: Dict[str, int] = {}
    for k in _EVIDENCE_KINDS:
        delta = after.get(k, 0) - before.get(k, 0)
        if delta > 0:
            out[k.value] = delta
    return out


def _decide(plan: Plan, chain: ChainResult, added: Dict[str, int]) -> str:
    """CONTINUE only on new evidence. Nothing else can continue the loop.

    A1-FIX: a refusal no longer appears here at all, and that is the correction.

    It used to. `if added: return CONTINUE` ran FIRST, so a round that both progressed and had a
    step refused continued — and the planner was asked again in a world where that step had just
    been refused. Measured: connect_marks refused in round 0, planner called twice more. A refusal
    that does not change what happens next is advisory, which is not what a refusal is.

    But stopping the whole loop on any refusal is the opposite error: one impossible step would
    kill every legitimate continuation beside it. So refusal handling moved OUT of the verdict and
    INTO the round itself, as closed-door suppression — a refused step is struck from all future
    rounds while its reason holds, so the planner CANNOT re-propose it. The door is shut rather
    than the building evacuated, and the verdict is left to answer the one question it should:
    did this round get anywhere?
    """
    if added:
        return CONTINUE
    lineage = chain.provenance.lineage
    only_empty = bool(lineage) and all(r.status == EMPTY for r in lineage)
    if only_empty:
        return STOP_NO_NEW_EVIDENCE          # every step ran and honestly found nothing
    return STOP_NO_NEW_EVIDENCE


def _askable_door(closed: Dict[str, Dict[str, Any]], memory: WorkingMemory,
                  labels: Optional[Sequence[str]] = None) -> Optional[Question]:
    """A2 — is the only thing standing between us and progress something a person could say?

    Called at a stop point, never during a productive round: while the loop is still making
    progress there is nothing to ask about, and interrupting to ask would be the assistant that
    talks instead of working.

    Only a MISSING PARAM qualifies (`is_question_able`). A missing-INPUT door is the loop's own
    work — it has the models to produce marks, and turning that into a question would hand the
    curator a job the machine is standing next to.
    """
    for sig, entry in sorted(closed.items()):
        if not is_question_able(entry.get("reason", "")):
            continue
        step = entry.get("step")
        if step is None:
            continue
        param = missing_param_of(step, memory)
        if not param:
            continue                    # the packet has since supplied it — nothing to ask
        q = question_for(step, memory, missing_param=param, labels=labels,
                         round_index=int(entry.get("round", 0)), step_id=sig)
        if q is not None:
            return q
    return None


def _diagnostic_probe(intention: str, memory: WorkingMemory, *,
                      labels: Optional[Sequence[str]] = None,
                      round_index: int = 0) -> Tuple[Optional[Question], Dict[str, Any]]:
    """A2-EXT — recover the signal an EMPTY proposal threw away.

    A2's ask-hook reads the closed-door list, so it only fires when something was refused. But a
    planner that proposes NOTHING refuses nothing, so there is no door, so the loop dead-ends at
    `nothing_planned` — the dead end A2 existed to remove, reached by a different road. This is
    model-specific and real: the `RuleBasedPlanner` emits `presence_check {}` and lets `resolve()`
    refuse it, so A2 fires; the `GroqPlanner` returns `[]` rather than inventing a phrase, so it
    does not.

    An empty proposal conflates two different facts:

        NO ACTUATOR SERVES THIS      an honest refusal. There is nothing to ask about, and asking
                                     anyway would be fishing.
        ONE SERVES IT, I LACK THE    a door that is shut on four words from a human — exactly what
        PHRASE                       A2 exists to ask about.

    This tells them apart by asking the RULE-BASED planner what it WOULD propose here and running
    that through the same `resolve()`. That is a deterministic function of intention + memory — no
    model, no network, nothing that could invent a phrase — so it is a diagnostic, not a second
    opinion.

    THE BOUNDARY IS INTACT. This is not re-prompting around a refusal: there was no refusal to
    route around (the model returned nothing), the intention is untouched, and the model is not
    asked again. Nothing proposed here is ever RUN — the probe's only output is a question or
    silence. `planner_calls` deliberately does not count it; the receipt carries it in its own
    field so "the planner was not called a second time about the same door" stays readable.

    Silent (question=None) unless the probe finds a step refused for a MISSING PARAM: a shape that
    resolves cleanly says the empty proposal was not about a gap at all, and a missing-INPUT
    refusal is the loop's own work rather than the curator's.
    """
    steps = RuleBasedPlanner().propose(intention, memory)
    record: Dict[str, Any] = {
        "planner": PLANNER_RULE_BASED,
        "counts_as_planner_call": False,      # a diagnostic, not a round — see planner_calls
        "proposed": [s.actuator for s in steps],
        "refused": [],
        "outcome": PROBE_NO_SHAPE,
    }
    if not steps:
        return None, record                   # nothing serves this intention — ask nothing

    stamped = [s if s.id else s.with_id(f"probe:{i}:{s.actuator}") for i, s in enumerate(steps)]
    plan = resolve(stamped, memory, intention=intention)
    record["refused"] = [r.to_dict() for r in plan.refused]
    if not plan.refused:
        record["outcome"] = PROBE_RESOLVES
        return None, record

    for r in plan.refused:
        if not is_question_able(r.reason):
            continue
        param = missing_param_of(r.step, memory)
        if not param:
            continue
        q = question_for(r.step, memory, missing_param=param, labels=labels,
                         round_index=round_index, step_id=_sig(r.step))
        if q is not None:
            record["outcome"] = PROBE_QUESTION
            record["question_from"] = r.step.actuator
            return q, record

    record["outcome"] = PROBE_NO_ASKABLE_DOOR
    return None, record


def _confirmed_volunteer(question: Question,
                         memory: WorkingMemory) -> Tuple[Optional[Question], Dict[str, Any]]:
    """A2-EXT — validate a volunteered question instead of trusting it.

    `Proposal(steps=[], question=…)` lets a planner that already knows it is stuck say so. Taken on
    faith, that is a hole in exactly the guard A2 is: a model that wants to ask can claim any
    blockage it likes, and "I need a phrase for X" is as easy to emit as a fabricated phrase would
    have been. So the loop CONFIRMS the claim the only way it trusts anything — by running the
    named actuator through `resolve()` and checking it really is refused for the param claimed.

    Unconfirmed does not mean an error is raised: the claim is recorded on the receipt and dropped,
    and the honest paths (the closed door, then the diagnostic probe) still get their turn.
    """
    record: Dict[str, Any] = {"actuator": question.actuator, "missing_param": question.missing_param,
                              "confirmed": False, "why": ""}
    if not question.is_grounded:
        record["why"] = "the question does not name an act, a param and a sentence"
        return None, record

    step = Step(actuator=question.actuator, id=question.step_id or question.actuator)
    refused = resolve([step], memory).refused
    if not refused:
        record["why"] = f"'{question.actuator}' is not blocked on this memory — nothing to ask"
        return None, record
    reason = refused[0].reason
    if not is_question_able(reason):
        record["why"] = f"'{question.actuator}' is refused for {reason}, which is not a human's to fix"
        return None, record
    param = missing_param_of(step, memory)
    if param != question.missing_param:
        record["why"] = (f"claimed a missing '{question.missing_param}'; "
                         f"'{question.actuator}' is missing {param or 'nothing'}")
        return None, record

    record["confirmed"] = True
    record["why"] = f"'{question.actuator}' really is refused for a missing {param}"
    return question, record


@dataclass(frozen=True)
class RoundRecord:
    """One turn of the loop. `chain` is None only for a round that STOPPED before executing
    (a fixed point, or a plan with nothing runnable) — every executed round carries its full
    per-step lineage so the whole loop is auditable, round by round."""
    index: int
    verdict: str
    plan: Dict[str, Any]                              # plan.to_dict()
    new_evidence: Dict[str, int] = field(default_factory=dict)
    chain: Optional[Dict[str, Any]] = None           # chain.provenance.to_dict()
    weakest_link: Optional[float] = None
    # A1-FIX audit trace. `refused` is what this round shut; `suppressed` is what the planner
    # re-proposed and was struck before it could reach the gate; `reopened` is a door a later
    # round unlocked by producing the missing prerequisite. Together these make
    # "the planner was not re-prompted around a refusal" READABLE FROM THE RECEIPT rather than
    # only provable by instrumenting a test.
    refused: Tuple[Dict[str, Any], ...] = ()
    suppressed: Tuple[Dict[str, Any], ...] = ()
    reopened: Tuple[str, ...] = ()
    closed_doors_at_start: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {"round": self.index, "verdict": self.verdict, "new_evidence": dict(self.new_evidence),
                "weakest_link": self.weakest_link,
                "refused": [dict(r) for r in self.refused],
                "suppressed": [dict(r) for r in self.suppressed],
                "reopened": list(self.reopened),
                "closed_doors_at_start": list(self.closed_doors_at_start),
                "plan": self.plan, "chain": self.chain}


@dataclass(frozen=True)
class LoopResult:
    """The trace of a whole loop: every round, why it stopped, and the final memory. Extends the
    single-round `ChainResult` to a multi-round lineage without ever collapsing the rounds into one
    synthesized score."""
    loop_id: str
    intention: str
    rounds: Tuple[RoundRecord, ...]
    stop_reason: str
    memory: WorkingMemory
    # A1-FIX: the count that makes the boundary checkable. One planner call per round, never a
    # second about the same closed door.
    planner_calls: int = 0
    closed_doors: Tuple[Dict[str, Any], ...] = ()
    # A2: set when the loop stopped needing something only a human can supply. Its presence is
    # exactly equivalent to stop_reason == AWAITING_ANSWER.
    question: Optional[Question] = None
    # A2-EXT: the deterministic diagnostic run on the `nothing_planned` dead end, kept in its OWN
    # field rather than folded into `planner_calls` — so a reader can see that the second look was
    # a rule-based probe that ran nothing, not the planner being asked again about the same door.
    # None means it never ran (there was no dead end to diagnose).
    diagnostic_probe: Optional[Dict[str, Any]] = None
    # A2-EXT: what a planner CLAIMED it was blocked on, and whether resolve() bore that out. Set
    # only when a planner volunteered a question; a rejected claim is recorded, not hidden.
    volunteer_check: Optional[Dict[str, Any]] = None

    @property
    def executed_rounds(self) -> Tuple[RoundRecord, ...]:
        return tuple(r for r in self.rounds if r.chain is not None)

    @property
    def weakest_link(self) -> Optional[float]:
        """The minimum confidence any step reported across ALL rounds — the loop is only as
        trustworthy as its least trustworthy step. None when no step reported one."""
        vals = [r.weakest_link for r in self.rounds if r.weakest_link is not None]
        return min(vals) if vals else None

    @property
    def total_new_evidence(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for r in self.rounds:
            for k, v in r.new_evidence.items():
                out[k] = out.get(k, 0) + v
        return out

    @property
    def suppressed_total(self) -> int:
        return sum(len(r.suppressed) for r in self.rounds)

    @property
    def re_proposed_closed_doors(self) -> Tuple[str, ...]:
        """Every closed door the planner tried to walk back through. Non-empty is not a failure —
        it is the record of the loop refusing to let it, which is the whole point."""
        return tuple(str(x.get("step")) for r in self.rounds for x in r.suppressed)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "intention": self.intention,
            "stop_reason": self.stop_reason,
            "planner_calls": self.planner_calls,
            "question": self.question.to_dict() if self.question else None,
            "diagnostic_probe": dict(self.diagnostic_probe) if self.diagnostic_probe else None,
            "volunteer_check": dict(self.volunteer_check) if self.volunteer_check else None,
            "closed_doors": [dict(d) for d in self.closed_doors],
            "suppressed_total": self.suppressed_total,
            "rounds_total": len(self.rounds),
            "rounds_executed": len(self.executed_rounds),
            "weakest_link": self.weakest_link,
            "total_new_evidence": self.total_new_evidence,
            "final_memory": self.memory.summary(),
            "rounds": [r.to_dict() for r in self.rounds],
        }


def run_loop(intention: str, memory: WorkingMemory,
             actuators: Dict[str, ActuatorRunner], *,
             director: Optional[Director] = None, max_rounds: int = 4,
             loop_id: str = "loop",
             labels: Optional[Sequence[str]] = None) -> LoopResult:
    """propose → resolve → execute → evolve → decide → repeat.

    `actuators` is the registry every round executes against — `stub_registry()` (offline,
    deterministic) or `real_registry(ctx)` (a guarded real run; ctx accumulates suggestions and
    bridges real region data across rounds). `director` defaults to the rule-based Director; pass
    `Director(GroqPlanner())` for the model-backed planner. The intention is fixed for the life of
    the loop — re-planning is grounded only in evolved memory, never in a reworded prompt.
    """
    director = director or Director()
    current = memory
    rounds: List[RoundRecord] = []
    executed_sigs: set = set()                         # step signatures that have actually run
    # A1-FIX — the closed doors: signature → why it was shut. A refused step is struck from every
    # later round WHILE its reason holds, so the planner cannot re-propose it. Finding the key
    # re-opens the door; re-knocking never does.
    closed: Dict[str, Dict[str, Any]] = {}
    planner_calls = 0
    volunteered: Optional[Question] = None      # a question the planner raised itself
    stop_reason = STOP_MAX_ROUNDS                       # holds if the loop exhausts its budget

    for i in range(max_rounds):
        doors_at_start = tuple(sorted(closed))

        # ── propose (ONE call per round, always against the CURRENT evidence) ──────────────
        planner_calls += 1
        # A2: a planner may return a bare list (the pre-A2 contract) or a Proposal carrying a
        # question it already knows it is blocked on. Both normalise here so no existing planner
        # has to change.
        proposal = Proposal.of(director.planner.propose(intention, current))
        volunteered = proposal.question
        stamped = [st if st.id else st.with_id(f"{loop_id}:r{i}:{n}:{st.actuator}")
                   for n, st in enumerate(proposal.steps)]

        # ── suppress closed doors BEFORE the gate sees them ───────────────────────────────
        # This is the correction. Filtering here — rather than judging refusals after the round —
        # is what makes a refused step unable to come back: it never reaches resolve(), so it can
        # never be refused a second time, and the planner can never be answered about it again.
        kept: List[Step] = []
        suppressed: List[Dict[str, Any]] = []
        reopened: List[str] = []
        for st in stamped:
            sig = _sig(st)
            if sig in closed:
                if _door_still_closed(st, current):
                    suppressed.append({"step": sig, "actuator": st.actuator,
                                       "reason": closed[sig].get("reason"),
                                       "detail": closed[sig].get("detail")})
                    continue
                # the prerequisite arrived — the door opens and the step gets its chance
                reopened.append(sig)
                closed.pop(sig, None)
            kept.append(st)

        # ── a round that only re-knocks shut doors got nowhere ────────────────────────────
        if not kept and suppressed:
            rounds.append(RoundRecord(
                index=i, verdict=STOP_ONLY_CLOSED_DOORS,
                plan=resolve([], current, intention=intention).to_dict(),
                suppressed=tuple(suppressed), reopened=tuple(reopened),
                closed_doors_at_start=doors_at_start))
            stop_reason = STOP_ONLY_CLOSED_DOORS
            break

        plan = resolve(kept, current, intention=intention)

        # ── shut the door on anything refused this round ──────────────────────────────────
        for r in plan.refused:
            closed[_sig(r.step)] = {"actuator": r.step.actuator, "reason": r.reason,
                                    "detail": r.detail, "round": i, "step": r.step}
        refused_trace = tuple({"round": i, **r.to_dict()} for r in plan.refused)

        sigs = {_sig(st) for st in plan.steps}

        # Fixed point: the planner can only re-propose steps already run — nothing new to do.
        if plan.steps and sigs <= executed_sigs:
            rounds.append(RoundRecord(
                index=i, verdict=STOP_FIXED_POINT, plan=plan.to_dict(),
                refused=refused_trace, suppressed=tuple(suppressed),
                reopened=tuple(reopened), closed_doors_at_start=doors_at_start))
            stop_reason = STOP_FIXED_POINT
            break

        # Nothing runnable survived the gate. The refusals are reported and their doors are now
        # shut; the loop ends because there is no work, not because a refusal is fatal.
        if not plan.steps:
            reason = STOP_ONLY_REFUSALS if plan.refused else STOP_NOTHING_PLANNED
            rounds.append(RoundRecord(
                index=i, verdict=reason, plan=plan.to_dict(), refused=refused_trace,
                suppressed=tuple(suppressed), reopened=tuple(reopened),
                closed_doors_at_start=doors_at_start))
            stop_reason = reason
            break

        before = current.available()
        chain = execute(plan, current, actuators, chain_id=f"{loop_id}:r{i}")
        after = chain.memory.available()
        added = _new_evidence(before, after)
        executed_sigs |= sigs
        current = chain.memory                          # re-plan next round on the EVOLVED memory

        verdict = _decide(plan, chain, added)
        rounds.append(RoundRecord(
            index=i, verdict=verdict, plan=plan.to_dict(), new_evidence=added,
            chain=chain.provenance.to_dict(), weakest_link=chain.provenance.weakest_link,
            refused=refused_trace, suppressed=tuple(suppressed), reopened=tuple(reopened),
            closed_doors_at_start=doors_at_start))
        if verdict != CONTINUE:
            stop_reason = verdict
            break

    # ── A2: ask, rather than dead-end ────────────────────────────────────────────────────
    # Applied once, at whatever stop point the loop reached. NOT while it is still working: a
    # productive loop has nothing to ask about, and interrupting to ask would be the assistant
    # that talks instead of works.
    #
    # STOP_MAX_ROUNDS is deliberately excluded. There, progress was still being made when the
    # backstop fired — so the closed door is not what is blocking us, and the honest report is
    # "I ran out of rounds", not a question implying the curator is the bottleneck.
    #
    # A2-EXT adds the third and last source of a question, in strict order of trust: a planner's
    # own claim (only once resolve() confirms it), then the closed door A2 reads, then — for the
    # dead end where nothing was proposed and so nothing was refused — a deterministic rule-based
    # diagnostic. Each falls through to the next, so a rejected claim still gets an honest answer.
    question: Optional[Question] = None
    volunteer_check: Optional[Dict[str, Any]] = None
    if volunteered is not None:
        question, volunteer_check = _confirmed_volunteer(volunteered, current)
    if question is None and stop_reason in (STOP_ONLY_CLOSED_DOORS, STOP_ONLY_REFUSALS,
                                            STOP_NOTHING_PLANNED, STOP_NO_NEW_EVIDENCE,
                                            STOP_FIXED_POINT):
        question = _askable_door(closed, current, labels)

    # A2-EXT — the one dead end A2 left open. Only where the planner proposed nothing AND nothing
    # was refused: with a closed door in hand the hook above is the right instrument, and the probe
    # would be a second opinion on a question already answered.
    probe: Optional[Dict[str, Any]] = None
    if question is None and stop_reason == STOP_NOTHING_PLANNED and not closed:
        question, probe = _diagnostic_probe(
            intention, current, labels=labels,
            round_index=rounds[-1].index if rounds else 0)

    if question is not None:
        stop_reason = AWAITING_ANSWER

    return LoopResult(loop_id=loop_id, intention=intention, rounds=tuple(rounds),
                      stop_reason=stop_reason, memory=current, planner_calls=planner_calls,
                      closed_doors=tuple({"step": k,
                                          **{kk: vv for kk, vv in v.items() if kk != "step"}}
                                         for k, v in sorted(closed.items())),
                      question=question, diagnostic_probe=probe,
                      volunteer_check=volunteer_check)
