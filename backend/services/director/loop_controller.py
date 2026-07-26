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
from .plan import Plan, Step
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


def _sig(step: Step) -> str:
    """A stable identity for a step by WHAT it asks, not which round asked it — so re-proposing
    the same actuator+params is recognised as already-done. Ids/notes are excluded (they vary)."""
    return json.dumps([step.actuator, step.params], sort_keys=True, default=str)


def _new_evidence(before: Dict[Resource, int], after: Dict[Resource, int]) -> Dict[str, int]:
    """The evidence kinds whose count rose this round, and by how much. Empty ⇒ nothing new."""
    out: Dict[str, int] = {}
    for k in _EVIDENCE_KINDS:
        delta = after.get(k, 0) - before.get(k, 0)
        if delta > 0:
            out[k.value] = delta
    return out


def _decide(plan: Plan, chain: ChainResult, added: Dict[str, int]) -> str:
    """CONTINUE only on new evidence; otherwise say WHY the loop stops."""
    if added:
        return CONTINUE
    lineage = chain.provenance.lineage
    ran_ok = any(r.status == OK for r in lineage)
    only_empty = bool(lineage) and all(r.status == EMPTY for r in lineage)
    if plan.refused or any(r.status not in (OK, EMPTY) for r in lineage) or only_empty:
        # some branch refused/was unavailable/skipped, or every step honestly found nothing —
        # a refusal ends here (never re-prompted), and an empty round is a real answer, not a retry.
        return STOP_ONLY_REFUSALS
    if ran_ok:
        # steps ran OK but produced no evidence (e.g. only readings) — no ground to re-plan on.
        return STOP_NO_NEW_EVIDENCE
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

    def to_dict(self) -> Dict[str, Any]:
        return {"round": self.index, "verdict": self.verdict, "new_evidence": dict(self.new_evidence),
                "weakest_link": self.weakest_link, "plan": self.plan, "chain": self.chain}


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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "intention": self.intention,
            "stop_reason": self.stop_reason,
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
    stop_reason = STOP_MAX_ROUNDS                       # holds if the loop exhausts its budget

    for i in range(max_rounds):
        plan = director.plan(intention, current)
        sigs = {_sig(s) for s in plan.steps}

        # Fixed point: the planner can only re-propose steps already run — there is nothing new to
        # do, so stop BEFORE a pointless round rather than spin. (`<=` : every proposed step is
        # one we have already executed.)
        if plan.steps and sigs <= executed_sigs:
            rounds.append(RoundRecord(index=i, verdict=STOP_FIXED_POINT, plan=plan.to_dict()))
            stop_reason = STOP_FIXED_POINT
            break

        # Nothing runnable: report the refusals (a refusal is a result, not an error) or, if the
        # planner simply proposed nothing, say so. Either way the loop ends — never re-prompted.
        if not plan.steps:
            reason = STOP_ONLY_REFUSALS if plan.refused else STOP_NOTHING_PLANNED
            rounds.append(RoundRecord(index=i, verdict=reason, plan=plan.to_dict()))
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
            chain=chain.provenance.to_dict(), weakest_link=chain.provenance.weakest_link))
        if verdict != CONTINUE:
            stop_reason = verdict
            break

    return LoopResult(loop_id=loop_id, intention=intention, rounds=tuple(rounds),
                      stop_reason=stop_reason, memory=current)
