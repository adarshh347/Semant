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

UNATTENDED-SAFE. Like the Director it wraps: it produces SUGGESTIONS only (into the execution
context's quarantine), never accepts a mark, never writes a post. It is actuator-agnostic — hand it
`stub_registry()` for a deterministic offline loop or `real_registry(ctx)` for a guarded real run.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .capabilities import Resource
from .execution import EMPTY, OK, ActuatorRunner, ChainResult, execute
from .memory import WorkingMemory
from .plan import Plan, Step, resolve
from .planner import Director

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
             loop_id: str = "loop") -> LoopResult:
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
    stop_reason = STOP_MAX_ROUNDS                       # holds if the loop exhausts its budget

    for i in range(max_rounds):
        doors_at_start = tuple(sorted(closed))

        # ── propose (ONE call per round, always against the CURRENT evidence) ──────────────
        planner_calls += 1
        proposed = director.planner.propose(intention, current)
        stamped = [st if st.id else st.with_id(f"{loop_id}:r{i}:{n}:{st.actuator}")
                   for n, st in enumerate(proposed)]

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
                                    "detail": r.detail, "round": i}
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

    return LoopResult(loop_id=loop_id, intention=intention, rounds=tuple(rounds),
                      stop_reason=stop_reason, memory=current, planner_calls=planner_calls,
                      closed_doors=tuple({"step": k, **v} for k, v in sorted(closed.items())))
