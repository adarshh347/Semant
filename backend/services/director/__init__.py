"""
CIRCUIT-001 ORCH-001 — the Director: Layer 3, intention → actuator plan.

The actuators (hands) and the circulation (quarantine → review → marks → grounds → percepts)
already existed. This is the skeleton between them: the part that takes "trace the light" and
turns it into an ordered chain of actuator calls that will not fire blind and will not
fabricate its way past a failure.

    memory       — the working packet handed to every step, so no call is context-free
    capabilities — what each actuator needs and leaves behind (the map everything reads)
    plan         — Step/Plan, and `resolve()`: the reorder-or-refuse gate
    planner      — Director + RuleBasedPlanner, with the seam for a model-backed planner
    workflows    — named, inspectable, replayable chains (3 seeded)
    execution    — the runner: stub actuators, refusal propagation, chain provenance

Everything here is pure python: no torch, no fetch, no database, no GPU. It is exercised
entirely against stub actuators, which is what makes it testable without a model.
"""
from .capabilities import ACTUATORS, Actuator, Requirement, Resource
from .execution import (ChainProvenance, ChainResult, StepRecord, StubActuator,
                        EMPTY, OK, SKIPPED, UNAVAILABLE, execute, stub_registry)
from .memory import WorkingMemory, build_memory
from .plan import Plan, RefusedStep, Step, resolve
from .planner import Director, Intent, Planner, RuleBasedPlanner, match_intent
from .workflows import Workflow

__all__ = [
    "ACTUATORS", "Actuator", "Requirement", "Resource",
    "WorkingMemory", "build_memory",
    "Plan", "RefusedStep", "Step", "resolve",
    "Director", "Intent", "Planner", "RuleBasedPlanner", "match_intent",
    "Workflow",
    "ChainProvenance", "ChainResult", "StepRecord", "StubActuator",
    "execute", "stub_registry", "OK", "EMPTY", "SKIPPED", "UNAVAILABLE",
]
