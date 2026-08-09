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


#: Which semantic compiler a deployment binds. `council` is the v2 dissolution pipeline; `legacy`
#: is the v1 one-call compiler, kept runnable so a stored v1 session can be reproduced rather than
#: only parsed.
COMPILER_COUNCIL = "council"
COMPILER_LEGACY = "legacy"


def _variant() -> str:
    raw = str(os.getenv("SEMANT_INQUIRY_COMPILER", COMPILER_COUNCIL)).strip().lower()
    return raw if raw in (COMPILER_COUNCIL, COMPILER_LEGACY) else COMPILER_COUNCIL


def _compiler_for(variant: str):
    from backend.services.semantic_compilation.compiler import ModelSemanticCompiler

    from .dissolution_binding import DissolutionCompiler
    return ModelSemanticCompiler() if variant == COMPILER_LEGACY else DissolutionCompiler()


def build_stages(*, capability=None, judge=None, composer=None) -> Stages:
    """The production binding.

    `SEMANT_INQUIRY_LIVE_MODELS=0` unbinds the two model stages, which is how a local rehearsal runs
    the whole chain with no provider configured: the session records `skipped` for both and stops
    with nothing compiled — an honest empty rather than a fabricated reading.
    """
    from backend.services.inquiry import get_framer
    from backend.services.semantic_compilation.compiler import ModelSemanticCompiler
    from backend.services.semantic_compilation.theorist import ModelSceneTheorist

    from .dissolution_binding import DissolutionCompiler

    from .capability import LockedFixtureCapability
    from .composer import DeterministicComposer, ModelSynthesisComposer
    from .judge import judge as judge_claims

    live = _enabled("SEMANT_INQUIRY_LIVE_MODELS")
    return Stages(
        framer=get_framer("deterministic"),
        theorist=ModelSceneTheorist() if live else None,
        # THE COUNCIL, by default. 003A replaced the one-call compiler 002R failed on, and until
        # this line it was merged and unreachable from `/inquiry`.
        #
        # `SEMANT_INQUIRY_COMPILER=legacy` still binds the v1 one-call compiler. Not a fallback and
        # never automatic — nothing selects it on an error — but a way to reproduce a stored v1
        # session's shape on purpose, which is the difference between a version being readable and
        # a version being runnable.
        compiler=(_compiler_for(_variant()) if live else None),
        # The optional question-reformatter. Left unbound: Lane B's `DeterministicFormatter` is
        # fully capable, and a model that rewords a question is the one model call in this chain
        # whose only effect is on what a person reads. Binding it is a deliberate later act.
        formatter=None,
        # A NEW adapter per call, deliberately. Its one-attempt counter is per-instance and is not
        # the firewall — the session's existing receipt is — but a shared instance would spend a
        # global budget on whichever inquiry happened to be first.
        capability=capability if capability is not None else LockedFixtureCapability(),
        judge=judge if judge is not None else judge_claims,
        # The deterministic composer is not a stub and not a fallback: it produces every binding
        # the model one has to, and it is what a deployment with no provider answers with. The
        # model composer is bound only where the other two model stages are, so an answer written
        # by a model never sits on top of a chain that had no model in it.
        composer=composer if composer is not None else (
            ModelSynthesisComposer() if live else DeterministicComposer()),
    )


__all__ = ["build_stages", "COMPILER_COUNCIL", "COMPILER_LEGACY"]
