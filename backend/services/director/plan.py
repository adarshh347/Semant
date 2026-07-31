"""
CIRCUIT-001 ORCH-001 — the plan, and the dependency resolution that makes it honest.

A plan is an ORDERED list of actuator steps. This module is the part that guarantees the
order is runnable: it walks the requested steps against projected working memory and either
places each one at a point where its inputs exist, or REFUSES it outright.

THE CENTRAL RULE: never fire blind. A step whose inputs do not exist is not "attempted and
failed" — it is not attempted. The distinction is not pedantic. `material_field` handed no
region does not error cleanly; it silently falls back to the whole image and returns a
confident field that answers a question nobody asked. Refusing before dispatch is the only
way that cannot happen.

TWO OUTCOMES, KEPT SEPARATE:

  REORDERED — the step's inputs do not exist YET, but an earlier-requested step produces
  them. "material_field then find_parts" is a fine intention badly sequenced; the resolver
  fixes the sequence rather than punishing the curator for word order.

  REFUSED — nothing in this plan can ever satisfy the step. `connect_marks` on an image with
  one mark and no mark-producing step is not a scheduling problem, and no amount of
  reordering will make it one. It is dropped with a reason naming the missing input.

The algorithm is a stable topological placement by resource availability, not by explicit
edges: repeatedly scan the pending steps in requested order and emit the first whose
requirements the projected memory satisfies; add what it produces; repeat. When a full pass
places nothing, everything still pending is unsatisfiable — that is the refusal set, and it
is detected as a FIXED POINT rather than a cycle-count guess, so it cannot loop forever.

Stability is deliberate: among steps that are all currently runnable, requested order wins.
A planner's ordering carries intent (light before shadow reads differently from shadow
before light) and the resolver has no business improving on it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .capabilities import Actuator, Requirement, Resource, get as get_actuator
from .memory import WorkingMemory

# Refusal reason codes. Closed set — a caller may branch on these, and a free-text reason
# that varies with phrasing is not something anyone can branch on.
REFUSED_UNKNOWN_ACTUATOR = "unknown_actuator"
REFUSED_MISSING_INPUT = "missing_input"
REFUSED_MISSING_PARAM = "missing_param"


@dataclass(frozen=True)
class Step:
    """One requested actuator call. Inert — holds no result and cannot run itself."""
    actuator: str
    params: Dict[str, Any] = field(default_factory=dict)
    # Stable identity for provenance and replay. Assigned by the planner, not the clock,
    # so the same workflow on the same memory produces the same plan byte-for-byte.
    id: str = ""
    note: str = ""              # why the planner asked for this, in its own words

    def with_id(self, step_id: str) -> "Step":
        return Step(actuator=self.actuator, params=dict(self.params), id=step_id, note=self.note)


@dataclass(frozen=True)
class RefusedStep:
    """A step that will not run, and precisely why. Part of the plan, not an error."""
    step: Step
    reason: str                 # one of the REFUSED_* codes
    detail: str                 # human-readable: which input, which param

    def to_dict(self) -> Dict[str, Any]:
        return {"step_id": self.step.id, "actuator": self.step.actuator,
                "reason": self.reason, "detail": self.detail}


@dataclass(frozen=True)
class Plan:
    """An ordered, runnable sequence — plus an explicit record of what was dropped.

    `refused` is a first-class field rather than a log line. A plan that quietly contains
    three of the five things asked for is a plan that lies by omission; anything reporting
    on this plan has the refusals in hand and cannot fail to mention them.
    """
    intention: str
    steps: Tuple[Step, ...] = ()
    refused: Tuple[RefusedStep, ...] = ()
    workflow: Optional[str] = None      # set when the plan came from a named workflow
    planner: str = "rule_based"
    reordered: bool = False             # requested order != final order
    notes: Tuple[str, ...] = ()

    @property
    def runnable(self) -> bool:
        return bool(self.steps)

    @property
    def complete(self) -> bool:
        """True when everything asked for survived. A partial plan is honest, not complete."""
        return not self.refused

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intention": self.intention,
            "workflow": self.workflow,
            "planner": self.planner,
            "reordered": self.reordered,
            "complete": self.complete,
            "steps": [{"step_id": s.id, "actuator": s.actuator,
                       "params": dict(s.params), "note": s.note} for s in self.steps],
            "refused": [r.to_dict() for r in self.refused],
            "notes": list(self.notes),
        }


def _missing_param(actuator: Actuator, step: Step, memory: WorkingMemory) -> Optional[str]:
    """A required param the step does not carry.

    Only params backing a declared PHRASE requirement are enforced — those are the ones
    whose absence causes a fabrication rather than a bad-but-honest result. The phrase may
    arrive on the step OR on the packet (the curator typed it into the workspace), and
    either is legitimate.
    """
    needs_phrase = any(r.kind is Resource.PHRASE for r in actuator.requires)
    if needs_phrase and "phrase" in actuator.param_keys:
        on_step = str(step.params.get("phrase") or "").strip()
        on_memory = str(memory.phrase or "").strip()
        if not on_step and not on_memory:
            return "phrase"
    return None


def availability_for(step: Step, memory_available: Dict[Resource, int]) -> Dict[Resource, int]:
    """Memory's resources PLUS whatever the step carries in its own params.

    A phrase can arrive two ways — typed into the workspace (on the packet) or written into
    the step by a planner — and both are the curator's words. Checking only the packet would
    refuse `presence_check(phrase="a cross")` on an image whose packet has no phrase, which
    is a perfectly answerable request.

    Only PHRASE works this way. Evidence resources cannot be conjured by a param: a step
    claiming to bring its own marks would be exactly the fabrication route this layer closes.
    """
    available = dict(memory_available)
    if str(step.params.get("phrase") or "").strip():
        available[Resource.PHRASE] = max(available.get(Resource.PHRASE, 0), 1)
    return available


def _unmet(actuator: Actuator, available: Dict[Resource, int]) -> List[Requirement]:
    return [r for r in actuator.requires if not r.satisfied_by(available)]


def resolve(steps: Sequence[Step], memory: WorkingMemory, *,
            intention: str = "", workflow: Optional[str] = None,
            planner: str = "rule_based") -> Plan:
    """Order what can run; refuse what cannot. The gate between a wish and a plan.

    Every path into execution goes through here — including, when it arrives, the language
    model planner. That is the point of putting it in one function: a hallucinated actuator
    name and a badly-sequenced human request are refused by the same code.
    """
    pending: List[Tuple[int, Step]] = []
    refused: List[RefusedStep] = []

    # Pass 1 — reject what is unknown before reasoning about order. An actuator that does
    # not exist has no requirements to reason about.
    for i, step in enumerate(steps):
        actuator = get_actuator(step.actuator)
        if actuator is None:
            refused.append(RefusedStep(
                step=step, reason=REFUSED_UNKNOWN_ACTUATOR,
                detail=f"no actuator named '{step.actuator}'"))
            continue
        missing = _missing_param(actuator, step, memory)
        if missing:
            refused.append(RefusedStep(
                step=step, reason=REFUSED_MISSING_PARAM,
                detail=f"'{step.actuator}' needs a {missing} and none was given"))
            continue
        pending.append((i, step))

    # Pass 2 — place steps by projected availability, to a fixed point.
    projected = memory
    ordered: List[Step] = []
    while pending:
        available = projected.available()
        placed_index: Optional[int] = None
        for slot, (_, step) in enumerate(pending):
            actuator = get_actuator(step.actuator)
            assert actuator is not None            # pass 1 removed the unknowns
            if not _unmet(actuator, availability_for(step, available)):
                placed_index = slot
                break
        if placed_index is None:
            break                                  # fixed point: nothing else can ever run
        _, step = pending.pop(placed_index)
        actuator = get_actuator(step.actuator)
        assert actuator is not None
        ordered.append(step)
        projected = projected.evolve(actuator.projected_produces(),
                                     step_id=step.id or step.actuator)

    # Whatever is still pending is unsatisfiable by this plan, on this memory.
    final_available = projected.available()
    for _, step in pending:
        actuator = get_actuator(step.actuator)
        assert actuator is not None
        unmet = _unmet(actuator, availability_for(step, final_available))
        detail = ", ".join(r.describe() for r in unmet)
        refused.append(RefusedStep(
            step=step, reason=REFUSED_MISSING_INPUT,
            detail=f"'{step.actuator}' needs {detail} and nothing in this plan provides it"))

    # Did we change the order? Compare surviving steps against their requested positions.
    requested_order = [s.id for i, s in enumerate(steps)
                       if any(o.id == s.id for o in ordered)]
    reordered = requested_order != [s.id for s in ordered]

    # Refusals come back in requested order, not discovery order — the two passes above
    # would otherwise report a plan's problems in an order that has nothing to do with how
    # the curator wrote it.
    position = {id(s): i for i, s in enumerate(steps)}
    refused.sort(key=lambda r: position.get(id(r.step), 0))

    return Plan(intention=intention, steps=tuple(ordered), refused=tuple(refused),
                workflow=workflow, planner=planner, reordered=reordered)
