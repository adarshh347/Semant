"""
CIRCUIT-001 ORCH-001 — the Director: Layer 3, intention → actuator plan.

The actuators (hands) and the circulation (quarantine → review → marks → grounds → percepts)
already existed. This is the skeleton between them. Built bottom-up:

    capabilities — what each actuator needs and leaves behind (the map everything reads)
    memory       — the working packet handed to every step, so no call is context-free
    plan         — Step/Plan, and `resolve()`: the reorder-or-refuse gate

Everything here is pure python: no torch, no fetch, no database, no GPU.
"""
from .capabilities import ACTUATORS, Actuator, Requirement, Resource
from .memory import WorkingMemory, build_memory
from .plan import Plan, RefusedStep, Step, resolve

__all__ = [
    "ACTUATORS", "Actuator", "Requirement", "Resource",
    "WorkingMemory", "build_memory",
    "Plan", "RefusedStep", "Step", "resolve",
]
