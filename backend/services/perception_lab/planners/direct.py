"""
PERCEPTUAL-ORGANS-002 Lane D — the Direct arm: a control was pressed.

The smallest planner there can be, and its smallness is the deliverable. The Direct arm exists so
that a person can establish whether an organ WORKS without also testing whether language reached
it, and the way it does that is by having no language in it. A `DirectCommand` is an operation key
and the parameters a control produced.

WHY IT IS A PLANNER AT ALL, rather than a path that skips to the resolver. Because the phase gate
compares the arms. "Direct and prompted commands reach the same runner" is only checkable if both
arms produce the same kind of object and go through the same gates; a Direct path that bypassed
the resolver would be a second runner with a second set of rules, and the comparison would be
between a laboratory and a shortcut.

So a Direct command is clamped, refused and recorded exactly like a model's proposal. A person who
presses Find All with `max_instances: 900` gets the same `maximum=64` clamp on their plan that the
model would have got, and the number on the run is the number that ran.

THE ONE THING THIS ARM CAN REACH THAT THE PROMPT ARMS CANNOT. `extent.draw`, with a `mask_rle` or
a `polygon` in it — because here a PERSON drew the thing. The parameters are their hand. A prompt
planner proposing the same operation would be authoring geometry from words, which is the failure
the whole contract is arranged against.

PURE. No database, no network, no model, no clock. `ids` is injected.
"""
from __future__ import annotations

from typing import Optional, Sequence

from backend.schemas.perception_lab import PlannerIdentity
from backend.services.perception_lab.clock import IdFactory, SequentialIds
from backend.services.perception_lab.planners.base import DirectCommand, StepBuilder
from backend.services.perception_lab.resolver import Proposal
from backend.services.perception_lab.session import SessionView


class DirectPlanner:
    """One typed command per control press. No language, no inference, no defaults."""

    name = "direct"
    identity = PlannerIdentity.DIRECT

    def __init__(self, ids: Optional[IdFactory] = None):
        self._ids = ids if ids is not None else SequentialIds()

    def plan(self, request: DirectCommand, session: SessionView) -> Proposal:
        return self.plan_many([request], session)

    def plan_many(self, commands: Sequence[DirectCommand], session: SessionView) -> Proposal:
        """Several controls in one plan — how a person composes a chain by hand.

        The steps stay in the order they were given. A planner that reordered them would be
        deciding the shape of the person's experiment, and the whole point of the Direct arm is
        that it decides nothing.
        """
        builder = StepBuilder(session.selected_organ, self._ids)
        for command in commands:
            builder.propose(command.operation, parameters=command.parameters,
                            input_refs=command.input_refs,
                            rationale="a control was pressed")
        return Proposal(planner=self.identity, steps=tuple(builder.steps),
                        refusals=tuple(builder.refusals), notes=tuple(builder.notes))


__all__ = ["DirectPlanner"]
