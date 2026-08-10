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


# ── what this deployment IS (HARNESS-003D) ───────────────────────────────────
#
# The 002R rehearsal was run against a replay server on purpose, and the session record said so —
# `call_topology: "replay"`, `call_count: 0` — in a receipt three panels down. That is the right
# fact in the wrong place: a screenshot of a replay is indistinguishable from a screenshot of a live
# run to anyone who does not open the provenance, and a rehearsal that ratifies a phase on the
# strength of a replay is exactly the failure the horizontal-phase skill's `never display a
# simulation as measurement` exists to prevent.
#
# So it is a badge, beside the state, in every response.

#: The three the directive names, plus the one it does not: a view built without stages cannot say.
#: `undeclared` is NOT a fourth kind of deployment — it is the absence of the answer, and it renders
#: as that rather than as anything a reader could mistake for a live run.
DEPLOYMENT_LIVE = "live"
DEPLOYMENT_REPLAY = "replay"
DEPLOYMENT_FIXTURE = "fixture"
DEPLOYMENT_UNDECLARED = "undeclared"

#: Producer `name`s that mean a real provider call. Read off the bound adapter rather than from an
#: env flag: `SEMANT_INQUIRY_LIVE_MODELS=1` states an INTENTION, and a deployment whose key is
#: missing would then badge itself LIVE while every model stage reported `unavailable`.
_LIVE_PRODUCERS = ("model", "council")
#: …and the ones that mean a frozen payload runs through the production parser.
_REPLAY_PRODUCERS = ("replay", "fixture")

#: The two stages the badge is ABOUT. The composer writes prose over a graph that already exists and
#: the capability is a declared simulation in every deployment, so neither changes what a reader is
#: looking at when they ask "was this read, or replayed?".
_BADGED_STAGES = ("theorist", "compiler")


def _producer_kind(stage) -> str:
    if stage is None:
        return ""
    name = str(getattr(stage, "name", "") or "").strip().lower()
    if name in _REPLAY_PRODUCERS:
        return DEPLOYMENT_REPLAY
    if name in _LIVE_PRODUCERS:
        return DEPLOYMENT_LIVE
    return ""


def deployment(stages: Optional[Stages]) -> dict:
    """What produced this session: `live`, `replay`, `fixture` — or that nobody said.

    THE WEAKER CLAIM WINS. A deployment with a live theorist and a frozen compiler is `replay`, not
    `live`: what the person is reading is not all live, and a badge naming the stronger half would
    be true about one stage and misleading about the session. It is the same rule the workbench
    applies to a fixture receipt that arrives claiming to be usable.

    `reachable` is a SEPARATE question from the kind. A live-bound deployment whose provider is
    down is still a live deployment — it will produce `unavailable` stages and say so — and
    collapsing that into `fixture` would tell a reader that frozen payloads were used when nothing
    was used at all.
    """
    if stages is None:
        return {
            "kind": DEPLOYMENT_UNDECLARED, "declared": False, "reachable": None, "stages": {},
            "detail": "this response was built without a stage binding, so nothing here can say "
                      "whether the session was read live or replayed. It is not a claim that it "
                      "was live.",
        }

    kinds = {name: _producer_kind(getattr(stages, name)) for name in _BADGED_STAGES}
    bound = [k for k in kinds.values() if k]
    if DEPLOYMENT_REPLAY in bound:
        kind = DEPLOYMENT_REPLAY
        detail = ("at least one model stage replays a frozen payload through the production "
                  "parser. Nothing on this session was read from a provider on this run.")
    elif bound:
        kind = DEPLOYMENT_LIVE
        detail = "the model stages call a real provider."
    else:
        kind = DEPLOYMENT_FIXTURE
        detail = ("no model stage is bound. Every stage that would have called one is `skipped` "
                  "and this session compiles nothing — an honest empty rather than a stand-in.")

    reachable = None
    if kind == DEPLOYMENT_LIVE:
        checks = [getattr(getattr(stages, name), "is_available", None) for name in _BADGED_STAGES
                  if kinds[name] == DEPLOYMENT_LIVE]
        answers = [bool(check()) for check in checks if callable(check)]
        reachable = all(answers) if answers else None
        if answers and not reachable:
            detail += (" The provider could not be reached, so the model stages will report "
                       "`unavailable`. Nothing is substituted in their place.")

    return {"kind": kind, "declared": True, "reachable": reachable,
            "stages": {name: (kinds[name] or "unbound") for name in _BADGED_STAGES},
            "detail": detail}


__all__ = ["build_stages", "deployment", "COMPILER_COUNCIL", "COMPILER_LEGACY",
           "DEPLOYMENT_LIVE", "DEPLOYMENT_REPLAY", "DEPLOYMENT_FIXTURE", "DEPLOYMENT_UNDECLARED"]
