"""
HARNESS-002D — what this deployment actually binds into the stage order.

ONE PLACE, so a route never constructs a stage. The coordinator declares seven seams and injects
none of them; this module is where a running server decides which implementation sits behind each,
and it is the only module in the lane that knows a model exists.

WHY IT IS NOT A CONFIG FILE. Two of the bindings are conditional on a fact that can change between
one request and the next — whether the role's provider is reachable. A config file that named
`ModelSceneTheorist` would be right about the intention and silent about the outcome; the adapters
themselves answer `is_available()` and return an UNAVAILABLE reading rather than raising, so the
binding is unconditional and the honesty is downstream where it belongs.

THE FIXTURE STAGES ARE NOT A FALLBACK. `Stages` left `None` is SKIPPED and says so in the ledger.
Nothing here substitutes a frozen payload for a live call — a deployment whose theorist cannot
reach its provider produces a session that states that, which is the whole reason the workbench
distinguishes `unavailable` from `empty`.
"""
from __future__ import annotations

import os
from typing import Optional

from .coordinator import Stages


def _enabled(name: str, default: str = "1") -> bool:
    return str(os.getenv(name, default)).strip().lower() not in ("0", "false", "no", "off", "")


def build_stages(*, capability=None, judge=None, composer=None) -> Stages:
    """The production binding.

    `SEMANT_INQUIRY_LIVE_MODELS=0` unbinds the two model stages, which is how a local rehearsal runs
    the whole chain with no provider configured: the session records `skipped` for both and stops
    with nothing compiled — an honest empty rather than a fabricated reading.
    """
    from backend.services.inquiry import get_framer
    from backend.services.semantic_compilation.compiler import ModelSemanticCompiler
    from backend.services.semantic_compilation.theorist import ModelSceneTheorist

    from .capability import LockedFixtureCapability
    from .judge import judge as judge_claims

    live = _enabled("SEMANT_INQUIRY_LIVE_MODELS")
    return Stages(
        framer=get_framer("deterministic"),
        theorist=ModelSceneTheorist() if live else None,
        compiler=ModelSemanticCompiler() if live else None,
        # The optional question-reformatter. Left unbound: Lane B's `DeterministicFormatter` is
        # fully capable, and a model that rewords a question is the one model call in this chain
        # whose only effect is on what a person reads. Binding it is a deliberate later act.
        formatter=None,
        # A NEW adapter per call, deliberately. Its one-attempt counter is per-instance and is not
        # the firewall — the session's existing receipt is — but a shared instance would spend a
        # global budget on whichever inquiry happened to be first.
        capability=capability if capability is not None else LockedFixtureCapability(),
        judge=judge if judge is not None else judge_claims,
        composer=composer,
    )


__all__ = ["build_stages"]
