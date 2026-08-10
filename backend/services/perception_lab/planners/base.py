"""
PERCEPTUAL-ORGANS-002 Lane D — the one way a step gets proposed.

All three planners build their steps through `StepBuilder`, and that is not a convenience. Two
laws are enforced here rather than asked of each planner in turn:

  1. THE ORGAN OF A STEP COMES FROM THE OPERATION REGISTRY, NEVER FROM THE PLANNER. A planner
     names an operation key; `contracts.operation_index()` says whose it is. So there is no code
     path — direct, rules or model — in which a component that wants to run a topology operation
     can write `organ: extent` on it and see what happens. The resolver checks this again from the
     other side, and the two checks are for two different callers: this one for the planners in
     this package, that one for anything else that ever builds a `ProposedStep`.

  2. AN UNKNOWN OPERATION BECOMES A REFUSAL WITH THE NAME IN IT, NOT A DROPPED LINE. This is
     `inquiry/model.py` guard 1 exactly: how often a planner invents a capability is the only
     observable that says whether to trust it, and a parser that quietly skips the invented key
     destroys that number. `extent.imagine` comes back as `unsupported_operation: extent.imagine`.

WHAT A PLANNER MAY NOT AUTHOR, and why it is absent rather than forbidden:

  · GEOMETRY. `extent.draw` takes a `mask_rle` or a `polygon`, and no planner in this package
    proposes it. A prompt cannot say where a mask is; a planner that emitted one would be
    inventing the measurement instead of asking for it. The Direct arm can reach `extent.draw`
    because there a PERSON drew the thing and the parameters are their hand, not a guess.

  · IDENTITY. Every input ref is built by `bind_single`/`bind_pair` out of `SessionView`, so the
    only ids a planner can put on a step are ids the session already declared. There is no code
    here that constructs an artifact id from a string a model returned.

PURE. No database, no network, no clock. `ids` is injected.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Protocol, Sequence, Tuple, runtime_checkable

from backend.schemas.perception_lab import (InputRef, OrganFamily, ProposedStep, RefusalCode,
                                            RefusalRecord)
from backend.services.perception_lab.clock import IdFactory
from backend.services.perception_lab.contracts import operation_index
from backend.services.perception_lab.definitions import _message as contract_message
from backend.services.perception_lab.definitions import operation
from backend.services.perception_lab.session import SessionView


@dataclass(frozen=True)
class DirectCommand:
    """A control that was pressed, as data. The Direct arm's whole input.

    Deliberately NOT a prompt with a flag on it. The Direct arm exists to establish the organ
    without testing language translation, and a shape that could carry a sentence is a shape
    somebody eventually puts a sentence in.
    """
    operation: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    input_refs: Tuple[InputRef, ...] = ()


@runtime_checkable
class LabPlanner(Protocol):
    """Reads an intention. Proposes closed commands. Executes nothing.

    `plan()` returns a `resolver.Proposal`. The return type is not annotated here because
    `resolver` imports nothing from this package and this package importing `resolver` for a type
    would close a cycle over a name used once.
    """

    name: str
    identity: Any

    def plan(self, request: Any, session: SessionView) -> Any:
        ...


class StepBuilder:
    """Collects the steps and refusals of one planning call.

    One instance per `plan()` call, so step ids restart at `step_1` for every request and a test
    can name what it expects without counting every step the process ever built.
    """

    def __init__(self, selected_organ: OrganFamily, ids: IdFactory):
        self.selected_organ = selected_organ
        self._ids = ids
        self.steps: List[ProposedStep] = []
        self.refusals: List[RefusalRecord] = []
        self.notes: List[str] = []

    def propose(self, op_key: str, *, parameters: Optional[Mapping[str, Any]] = None,
                input_refs: Sequence[InputRef] = (),
                rationale: Optional[str] = None) -> Optional[ProposedStep]:
        """One step, with its organ read off the registry.

        Returns None and records a refusal when the key is not declared. Callers do not check the
        return value for control flow — they append what they get and let the resolver see the
        rest — but it is returned so a planner that wants to reference the step it just made can.
        """
        owner = operation_index().get(op_key)
        if owner is None:
            self.refusals.append(RefusalRecord(
                code=RefusalCode.UNSUPPORTED_OPERATION, organ=self.selected_organ,
                operation=op_key,
                message=contract_message("unsupported_operation", operation=op_key,
                                         organ=self.selected_organ.value),
                missing=[],
                remedy="choose a declared operation of this organ",
                detail={"invented": op_key}))
            return None
        step = ProposedStep(
            step_id=self._ids.mint("step"), organ=OrganFamily(owner), operation=op_key,
            parameters=dict(parameters or {}), input_refs=list(input_refs), rationale=rationale)
        self.steps.append(step)
        return step

    def refuse(self, refusal: RefusalRecord) -> None:
        self.refusals.append(refusal)

    def note(self, text: str) -> None:
        self.notes.append(text)


# ── binding references, which is the only way a planner may cite anything ────


def bind_single(session: SessionView, role: str) -> Tuple[InputRef, ...]:
    """The one thing a follow-up means, or nothing at all.

    "that mask" is `SessionView.references[0]` and nothing else — the active artifact, narrowed to
    the instance inside it if the person selected one. When nothing is declared this returns empty
    and the step goes to the resolver with no inputs, which refuses `missing_extent_inputs` — the
    honest answer. Searching the store for the most recent plausible artifact would be right most
    of the time, and the times it was wrong would look exactly like the times it was right.

    DESELECTION IS WHAT MAKES THIS TRUSTWORTHY. `references` is derived from the session's fields
    on every call rather than remembered, so a mask that was deselected is not bound by the next
    prompt — there is no cached intention here for it to survive in.
    """
    return tuple(session.artifact_ref(role, a, i) for a, i in session.references[:1])


def bind_pair(session: SessionView, roles: Tuple[str, str]) -> Tuple[InputRef, ...]:
    """The two things a pair question means: active first, then selected, in session order.

    Both endpoints may be instances of ONE artifact — "do those two touch?" about two masks in
    one extent set is the ordinary case, and before instance refs existed it was unaskable.

    Fewer than two available yields fewer than two refs rather than repeating one. A relation
    between something and itself is not what "do those two touch" asked, and it would measure
    perfectly and answer nothing.
    """
    picked = session.references[:2]
    if len(picked) < 2:
        return ()
    return tuple(session.artifact_ref(role, a, i) for role, (a, i) in zip(roles, picked))


def bind_many(session: SessionView, role: str, limit: int) -> Tuple[InputRef, ...]:
    """Every declared reference, up to the operation's declared maximum."""
    return tuple(session.artifact_ref(role, a, i) for a, i in session.references[:limit])


def input_limit(op_key: str, role: str) -> int:
    """The declared `max` for a role, so a planner clamps to the contract rather than a constant."""
    spec = operation(op_key).input_for(role)
    return spec.max if spec is not None else 0


__all__ = ["DirectCommand", "LabPlanner", "StepBuilder", "bind_single", "bind_pair", "bind_many",
           "input_limit"]
