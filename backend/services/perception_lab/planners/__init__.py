"""
PERCEPTUAL-ORGANS-002 Lane D — the three arms, and the one thing they all are.

    DirectPlanner   a control was pressed. One typed command, no language at all.
    RulesPlanner    a closed phrase table over the prompt. Deterministic, offline, testable.
    ModelPlanner    structured output from a language model, behind the identical resolver.

Every one of them returns a `resolver.Proposal` and nothing else. None of them can execute, mint
an artifact, author geometry, choose an organ, or reach an adapter — not because each was written
carefully, but because a `Proposal` is the only thing they can build and a `Proposal` cannot do
any of those things.

The seam is `backend/services/inquiry/base.py`'s, one level down: the same argument that a
deterministic framer and a model framer differ in the SOURCE of a proposal and in nothing else.
"""
from backend.services.perception_lab.planners.base import (DirectCommand, LabPlanner, StepBuilder,
                                                           bind_pair, bind_single)
from backend.services.perception_lab.planners.direct import DirectPlanner
from backend.services.perception_lab.planners.rules import RulesPlanner

__all__ = ["DirectCommand", "LabPlanner", "StepBuilder", "bind_pair", "bind_single",
           "DirectPlanner", "RulesPlanner"]
