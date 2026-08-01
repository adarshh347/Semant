"""
CIRCUIT-001 ORCH-001 — running a plan, and refusing at the level of the chain.

The producers already fail closed individually: P6-D refuses a rhythm field on flat input,
P8-C refuses a mark CLIP will not verify, and both report `status: empty` at HTTP 200 rather
than inventing something. This module raises that discipline from the step to the CHAIN.

THE PROBLEM IT SOLVES. Individual honesty does not compose. `trace_light` is light, then
shadow, then a reading of both. If the shadow step is UNAVAILABLE and the chain runs on, the
reading is produced from half the evidence — and, being a well-formed reading, it looks
exactly like one produced from all of it. Nothing downstream can tell the difference. The
partial input is invisible in the output, which is the precise shape of a fabrication even
though no single component lied.

So: **a step whose inputs went missing is SKIPPED, never run on what happens to be lying
around.** The chain reports what it could not do, and the result carries that gap where a
reader cannot miss it.

THREE NON-SUCCESS OUTCOMES, kept distinct because they mean genuinely different things:

  UNAVAILABLE — the actuator could not run (model down, no GPU). Transient. Retry is sensible.
  EMPTY       — it ran and honestly found nothing. NOT an error; a real answer. Retry is not
                sensible, and reporting it as a failure would teach a curator to distrust the
                one behaviour worth trusting most.
  SKIPPED     — never attempted, because an input it needed never arrived.

Collapsing any two of these into "failed" loses information the curator needs to decide what
to do next, which is the only reason to report a failure at all.

STUBS. `StubActuator` returns canned results and can be told to be unavailable. No model, no
GPU, no network — the whole layer is testable without firing anything, which is what lets
this gate run unattended.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

from .capabilities import Actuator, Resource, get as get_actuator
from .memory import WorkingMemory
from .plan import Plan, Step, availability_for

# Step outcomes.
OK = "ok"
UNAVAILABLE = "unavailable"
EMPTY = "empty"
SKIPPED = "skipped"
ERROR = "error"

# Why a step was skipped.
SKIP_UPSTREAM_UNAVAILABLE = "upstream_unavailable"
SKIP_INPUT_NEVER_ARRIVED = "input_never_arrived"


@dataclass(frozen=True)
class ActuatorResult:
    """What one actuator hands back.

    `confidence` is Optional and None is meaningful: "this actuator does not report a
    confidence" (a deterministic geometry operator) is not the same as low confidence, and
    a default of 0.0 would make every pure-python step look maximally untrustworthy.
    """
    status: str = OK
    produced: Tuple[Resource, ...] = ()
    confidence: Optional[float] = None
    model: Optional[str] = None
    adapter: Optional[str] = None
    detail: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.status == OK


class ActuatorRunner(Protocol):
    """Anything that can execute a step. Real producers and stubs share this shape."""

    def __call__(self, step: Step, memory: WorkingMemory) -> ActuatorResult:
        ...


class StubActuator:
    """A canned actuator. The whole point of this gate being unattended-safe.

    `unavailable=True` makes it refuse every call, which is how refusal propagation is
    tested without needing a model to actually be down.
    """

    def __init__(self, name: str, *, unavailable: bool = False, empty: bool = False,
                 confidence: Optional[float] = 0.9, model: Optional[str] = None,
                 payload: Optional[Dict[str, Any]] = None, produced_count: int = 1):
        self.name = name
        self.unavailable = unavailable
        self.empty = empty
        self.confidence = confidence
        self.model = model or f"stub::{name}"
        self.payload = payload or {}
        self.produced_count = produced_count
        self.calls: List[Step] = []          # what it was actually asked to do
        self.memories: List[WorkingMemory] = []   # the packet each call was handed

    def __call__(self, step: Step, memory: WorkingMemory) -> ActuatorResult:
        self.calls.append(step)
        self.memories.append(memory)
        actuator = get_actuator(step.actuator)
        produces = actuator.produces if actuator else ()
        if self.unavailable:
            return ActuatorResult(status=UNAVAILABLE, produced=(), confidence=None,
                                  model=self.model, adapter=self.name,
                                  detail=f"stub '{self.name}' is unavailable")
        if self.empty:
            # Ran honestly, found nothing. Produces NOTHING — which is what makes a
            # downstream step depending on it skip rather than run on stale evidence.
            return ActuatorResult(status=EMPTY, produced=(), confidence=None,
                                  model=self.model, adapter=self.name,
                                  detail=f"stub '{self.name}' found nothing")
        return ActuatorResult(status=OK,
                              produced=tuple(produces) * max(1, self.produced_count),
                              confidence=self.confidence, model=self.model,
                              adapter=self.name, payload=dict(self.payload))


def stub_registry(*, unavailable: Sequence[str] = (), empty: Sequence[str] = (),
                  confidence: Optional[float] = 0.9) -> Dict[str, StubActuator]:
    """A stub for every known actuator, with named ones told to refuse."""
    from .capabilities import known
    out: Dict[str, StubActuator] = {}
    for name in known():
        out[name] = StubActuator(name, unavailable=name in unavailable,
                                 empty=name in empty, confidence=confidence)
    return out


# ── chain provenance ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StepRecord:
    """One link of the lineage. Enough to reconstruct what happened, per step.

    `inputs_used` records the memory COUNTS the step actually saw, not the ids — a reading
    that turns out wrong is usually wrong because it ran on two marks when the curator
    assumed five, and that is the fact worth freezing.
    """
    step_id: str
    actuator: str
    status: str
    position: int
    confidence: Optional[float] = None
    model: Optional[str] = None
    adapter: Optional[str] = None
    detail: str = ""
    inputs_used: Dict[str, int] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    skip_reason: str = ""
    blocked_by: Tuple[str, ...] = ()     # step ids whose failure caused this skip
    # SURFACE-002: wall-clock around the DISPATCH, and None for a step that never reached one.
    # A skipped or unrouted step has no duration to report, and writing 0 would say "instant"
    # where the truth is "never ran" — the same conflation `confidence: None` exists to avoid.
    latency_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "step_id": self.step_id, "actuator": self.actuator, "status": self.status,
            "position": self.position, "confidence": self.confidence,
            "model": self.model, "adapter": self.adapter, "detail": self.detail,
            "inputs_used": dict(self.inputs_used), "params": dict(self.params),
            "latency_ms": self.latency_ms,
        }
        if self.skip_reason:
            d["skip_reason"] = self.skip_reason
            d["blocked_by"] = list(self.blocked_by)
        return d


@dataclass(frozen=True)
class ChainProvenance:
    """Provenance widened from one producer to a whole chain.

    A per-producer receipt answers "which model made this mark". A reading resting on five
    actuators needs to answer "which five, on what, and how sure was the weakest" — so the
    lineage is the full ordered record, and the summary fields are derived from it rather
    than tracked separately (they cannot drift that way).
    """
    chain_id: str
    intention: str
    workflow: Optional[str]
    planner: str
    lineage: Tuple[StepRecord, ...] = ()
    refused: Tuple[Dict[str, Any], ...] = ()     # from plan-time refusal

    # ── derived ──
    @property
    def ran(self) -> Tuple[StepRecord, ...]:
        return tuple(r for r in self.lineage if r.status in (OK, EMPTY))

    @property
    def complete(self) -> bool:
        """Every step the curator asked for actually ran and produced something.

        EMPTY counts against completeness — the chain is intact but the evidence is not, and
        a percept resting on an empty light field rests on less than it appears to.
        """
        return (not self.refused
                and all(r.status == OK for r in self.lineage))

    @property
    def weakest_link(self) -> Optional[float]:
        """Lowest confidence among steps that reported one, or None.

        A chain is only as trustworthy as its least trustworthy step, and averaging would
        let four confident steps bury one that was guessing. None when NO step reported a
        confidence — an invented number would be the one fabrication this whole module
        exists to prevent.
        """
        values = [r.confidence for r in self.lineage if r.confidence is not None]
        return min(values) if values else None

    def gaps(self) -> List[Dict[str, str]]:
        """Everything this chain could NOT do. What a reader must not be able to miss."""
        out: List[Dict[str, str]] = []
        for r in self.lineage:
            if r.status == OK:
                continue
            out.append({"step_id": r.step_id, "actuator": r.actuator,
                        "status": r.status,
                        "why": r.detail or r.skip_reason or r.status})
        for ref in self.refused:
            out.append({"step_id": str(ref.get("step_id", "")),
                        "actuator": str(ref.get("actuator", "")),
                        "status": "refused",
                        "why": str(ref.get("detail", ""))})
        return out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "intention": self.intention,
            "workflow": self.workflow,
            "planner": self.planner,
            "complete": self.complete,
            "weakest_link": self.weakest_link,
            "steps_total": len(self.lineage) + len(self.refused),
            "steps_ok": sum(1 for r in self.lineage if r.status == OK),
            "steps_empty": sum(1 for r in self.lineage if r.status == EMPTY),
            "steps_unavailable": sum(1 for r in self.lineage if r.status == UNAVAILABLE),
            "steps_skipped": sum(1 for r in self.lineage if r.status == SKIPPED),
            "steps_refused": len(self.refused),
            "lineage": [r.to_dict() for r in self.lineage],
            "refused": [dict(r) for r in self.refused],
            "gaps": self.gaps(),
        }


@dataclass(frozen=True)
class ChainResult:
    """The outcome of running a plan: final memory, per-step results, chain provenance."""
    provenance: ChainProvenance
    memory: WorkingMemory
    results: Tuple[ActuatorResult, ...] = ()

    @property
    def complete(self) -> bool:
        return self.provenance.complete

    def to_dict(self) -> Dict[str, Any]:
        return {"provenance": self.provenance.to_dict(), "memory": self.memory.summary()}


# ── the runner ───────────────────────────────────────────────────────────────

def execute(plan: Plan, memory: WorkingMemory,
            actuators: Dict[str, ActuatorRunner], *,
            chain_id: str = "chain") -> ChainResult:
    """Run a resolved plan, propagating refusal instead of fabricating around it.

    Re-checks requirements against REAL memory before every step. The plan proved the order
    is satisfiable when everything succeeds; this proves each step's inputs exist at the
    moment it would run. Those differ exactly when something upstream failed, which is the
    case this function exists for.
    """
    lineage: List[StepRecord] = []
    results: List[ActuatorResult] = []
    current = memory

    # Which resource kinds a failed step would have produced, and which step that was.
    # This is what turns "a requirement is unmet" into "unmet BECAUSE step 2 was down" —
    # the difference between a shrug and an explanation.
    failed_producers: Dict[Resource, List[str]] = {}

    for position, step in enumerate(plan.steps):
        actuator = get_actuator(step.actuator)
        if actuator is None:                      # resolve() should have caught this
            lineage.append(StepRecord(
                step_id=step.id, actuator=step.actuator, status=ERROR, position=position,
                detail=f"unknown actuator '{step.actuator}' reached execution"))
            continue

        # Same phrase rule as the resolver — a step that planned as runnable must not be
        # skipped at dispatch for an input it was carrying all along.
        available = availability_for(step, current.available())
        unmet = [r for r in actuator.requires if not r.satisfied_by(available)]
        if unmet:
            blockers: List[str] = []
            for req in unmet:
                blockers.extend(failed_producers.get(req.kind, []))
            reason = (SKIP_UPSTREAM_UNAVAILABLE if blockers else SKIP_INPUT_NEVER_ARRIVED)
            missing = ", ".join(r.describe() for r in unmet)
            detail = (f"needs {missing}; "
                      + (f"not produced because {', '.join(sorted(set(blockers)))} did not run"
                         if blockers else "it never arrived"))
            lineage.append(StepRecord(
                step_id=step.id, actuator=step.actuator, status=SKIPPED, position=position,
                inputs_used={k.value: v for k, v in available.items()},
                params=dict(step.params), detail=detail,
                skip_reason=reason, blocked_by=tuple(sorted(set(blockers)))))
            # A skipped step produces nothing, so anything depending on IT must also skip —
            # recorded here so the chain reports the root cause rather than the symptom.
            for kind in actuator.produces:
                failed_producers.setdefault(kind, []).append(step.id)
            continue

        runner = actuators.get(step.actuator)
        if runner is None:
            lineage.append(StepRecord(
                step_id=step.id, actuator=step.actuator, status=UNAVAILABLE, position=position,
                inputs_used={k.value: v for k, v in available.items()},
                params=dict(step.params),
                detail=f"no runner registered for '{step.actuator}'"))
            for kind in actuator.produces:
                failed_producers.setdefault(kind, []).append(step.id)
            continue

        # The step is handed the CURRENT packet — this is the "never fires blind" rule
        # actually taking effect, not merely being asserted in a docstring.
        started = time.perf_counter()
        result = runner(step, current)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        results.append(result)
        lineage.append(StepRecord(
            step_id=step.id, actuator=step.actuator, status=result.status, position=position,
            confidence=result.confidence, model=result.model, adapter=result.adapter,
            detail=result.detail,
            inputs_used={k.value: v for k, v in available.items()},
            params=dict(step.params), latency_ms=elapsed_ms))

        if result.succeeded and result.produced:
            current = current.evolve(result.produced, step_id=step.id)
        else:
            # UNAVAILABLE and EMPTY both leave nothing behind. Downstream steps needing what
            # this would have produced will skip, naming this step.
            for kind in actuator.produces:
                failed_producers.setdefault(kind, []).append(step.id)

    provenance = ChainProvenance(
        chain_id=chain_id, intention=plan.intention, workflow=plan.workflow,
        planner=plan.planner, lineage=tuple(lineage),
        refused=tuple(r.to_dict() for r in plan.refused))
    return ChainResult(provenance=provenance, memory=current, results=tuple(results))
