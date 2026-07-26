"""
CIRCUIT-001 ORCH-001 — the Director: an intention becomes a plan.

This is Layer 3's entry point. Above it sits a curator saying "trace the light"; below it
sit actuators that know nothing about intentions. This module is the translation, and it is
rule-based on purpose.

WHY RULES FIRST, WITH A SEAM RATHER THAN A MODEL. The hard part of planning is not
generating candidate chains — it is REFUSING the ones whose inputs do not exist. That
machinery (`plan.resolve`) is what a language model most needs and least provides: an LLM
asked to plan will happily emit `connect_marks` on an image with one mark. So the discipline
is built and tested against rules, where every output is inspectable, and the model is
allowed in only through a door that already has the guard on it.

THE SEAM, CONCRETELY. `Planner` is a protocol with one method. `RuleBasedPlanner` implements
it. A future `GroqPlanner` implements the same method and returns the same `List[Step]` — and
`Director.plan()` passes ANY planner's output through the identical `resolve()` call. A
hallucinated actuator name is refused as `unknown_actuator`; a badly-ordered chain is
reordered; a chain needing evidence that does not exist is refused. The model gets to
propose. It does not get to dispatch. That asymmetry is the entire design.

MATCHING IS DELIBERATELY DUMB. Keyword scoring over a small intent table, first-best wins,
no stemming, no embeddings. A cleverer matcher would be harder to predict and would obscure
the part that actually matters here — that an unmatched intention REFUSES rather than
guessing a plausible chain. Getting a confident wrong plan is worse than getting none.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

from . import workflows
from .capabilities import get as get_actuator
from .memory import WorkingMemory
from .plan import Plan, Step, resolve

PLANNER_RULE_BASED = "rule_based"
PLANNER_WORKFLOW = "workflow"


class Planner(Protocol):
    """The seam. One method, so a model-backed planner is a drop-in.

    A planner PROPOSES steps. It never resolves, never validates, never dispatches — those
    belong to the Director, which applies them uniformly to every planner's output.
    """
    name: str

    def propose(self, intention: str, memory: WorkingMemory) -> List[Step]:
        ...


# ── the intent table ─────────────────────────────────────────────────────────
# Each row: trigger keywords → a chain. Chains reference seeded workflows where one fits,
# so a named workflow and the intention that summons it cannot drift apart.

@dataclass(frozen=True)
class Intent:
    key: str
    keywords: Tuple[str, ...]
    workflow: Optional[str] = None            # delegate to a named chain
    steps: Tuple[Tuple[str, Dict[str, Any]], ...] = ()   # or spell one out
    why: str = ""


INTENTS: Tuple[Intent, ...] = (
    Intent(
        key="trace_light",
        keywords=("light", "lighting", "shadow", "illuminate", "lit", "glow", "dark"),
        workflow="trace_light",
        why="Light asked about alone still needs its shadow to mean anything.",
    ),
    Intent(
        key="motif_and_echoes",
        keywords=("motif", "echo", "echoes", "recur", "repeat", "again", "elsewhere", "similar"),
        workflow="motif_and_echoes",
        why="Recurrence is the claim; finding one instance is only the setup.",
    ),
    Intent(
        key="weigh_composition",
        keywords=("composition", "weight", "balance", "pressure", "rhythm", "empty",
                  "negative", "space", "arrange"),
        workflow="weigh_composition",
        why="Distribution of attention, read three cheap ways and composed once.",
    ),
    Intent(
        key="check_presence",
        keywords=("is there", "any", "present", "contains", "does it have", "check"),
        steps=(("presence_check", {}),),
        why="A yes/no about the picture — and an honest no when it is not there.",
    ),
    Intent(
        key="count",
        keywords=("how many", "count", "number of", "enumerate"),
        steps=(("enumerate", {}),),
        why="Counts what verifies, not what the detector guessed.",
    ),
    Intent(
        key="read_material",
        keywords=("material", "surface", "texture", "stone", "cloth", "fabric", "made of"),
        steps=(("find_parts", {}), ("material_field", {}),
               ("semantic_read", {"question": "What is this made of, and where does it recur?"})),
        why="Material needs an extent to be material OF — find parts first.",
    ),
    Intent(
        key="read_depth",
        keywords=("depth", "distance", "far", "behind", "recede", "recession", "atmosphere"),
        steps=(("background_recession", {}), ("atmosphere_field", {})),
        why="How far back the picture goes, and the haze that says so.",
    ),
)


def _score(intention: str, intent: Intent) -> int:
    """Count matching keywords. Multi-word triggers are matched as phrases.

    Longer triggers score their word count, so "how many" beats a bare "any" — otherwise a
    counting question would route to the presence check on an incidental word.
    """
    text = f" {(intention or '').strip().lower()} "
    total = 0
    for kw in intent.keywords:
        if kw in text:
            total += len(kw.split())
    return total


def match_intent(intention: str) -> Optional[Intent]:
    """Best-scoring intent, or None. None means REFUSE — never a default chain.

    Ties break toward the earlier row, which is why the compound ways of looking are listed
    before the single-shot ones: given an ambiguous phrase, the chain that gathers evidence
    is a better failure than the one that fires a single opinion.
    """
    best: Optional[Intent] = None
    best_score = 0
    for intent in INTENTS:
        s = _score(intention, intent)
        if s > best_score:
            best, best_score = intent, s
    return best


class RuleBasedPlanner:
    """Keyword-matched intentions → chains from the capability map."""
    name = PLANNER_RULE_BASED

    def propose(self, intention: str, memory: WorkingMemory) -> List[Step]:
        intent = match_intent(intention)
        if intent is None:
            return []                      # refusal, expressed as an empty proposal
        if intent.workflow:
            wf = workflows.get(intent.workflow)
            if wf is None:                 # a table row naming a deleted workflow
                return []
            return wf.to_steps()
        return [Step(actuator=a, params=dict(p), id=f"{intent.key}:{i}:{a}")
                for i, (a, p) in enumerate(intent.steps)]


class Director:
    """Turns an intention into a resolved, runnable plan.

    The Director owns the guard. Whatever planner it is given, the output passes through
    `resolve()` before it is a plan — so swapping the rule-based planner for a model-backed
    one cannot weaken the refusal discipline, only change what gets proposed.
    """

    def __init__(self, planner: Optional[Planner] = None):
        self.planner: Planner = planner or RuleBasedPlanner()

    def plan(self, intention: str, memory: WorkingMemory) -> Plan:
        proposed = self.planner.propose(intention, memory)
        if not proposed:
            # An unrecognised intention is a refusal with a reason, not an empty plan
            # pretending to be a successful one with nothing in it.
            return Plan(intention=intention, steps=(), refused=(),
                        planner=self.planner.name,
                        notes=(f"no way of looking matches '{intention}'; "
                               f"nothing was planned and nothing was run",))
        # Ids are guaranteed here rather than trusted from the planner: a model-backed
        # planner will omit them, and provenance keys on them.
        stamped = [s if s.id else s.with_id(f"{self.planner.name}:{i}:{s.actuator}")
                   for i, s in enumerate(proposed)]
        intent = match_intent(intention)
        plan = resolve(stamped, memory, intention=intention,
                       workflow=intent.workflow if intent else None,
                       planner=self.planner.name)
        if intent and intent.why:
            plan = Plan(intention=plan.intention, steps=plan.steps, refused=plan.refused,
                        workflow=plan.workflow, planner=plan.planner,
                        reordered=plan.reordered, notes=(intent.why,))
        return plan

    def plan_workflow(self, name: str, memory: WorkingMemory) -> Plan:
        """Replay a named workflow. Same guard, different source of steps."""
        wf = workflows.get(name)
        if wf is None:
            return Plan(intention=f"workflow:{name}", steps=(), refused=(),
                        planner=PLANNER_WORKFLOW,
                        notes=(f"no workflow named '{name}'",))
        return wf.plan_for(memory)


# ── where Groq plugs in ──────────────────────────────────────────────────────
#
# class GroqPlanner:
#     """A model proposes the chain; the Director still refuses what cannot run.
#
#     Implementation notes for whoever builds this, in the order they will bite:
#
#     1. The prompt must carry `memory.summary()` — counts, phrase, constraints, unreadable
#        — so the model plans against what EXISTS. A planner that cannot see there are zero
#        marks will keep proposing `connect_marks`, and every one of those is a wasted call.
#     2. Constrain output to `capabilities.known()`. Send the actual list; do not describe
#        it in prose. An actuator name is a closed vocabulary and should be typed as one.
#     3. Return `List[Step]` and NOTHING else. No confidence, no ordering guarantees, no
#        commentary — `resolve()` handles ordering and the executor handles results.
#     4. Do NOT catch refusals and re-prompt around them in a loop. A refused plan is
#        information for the curator, and a model that retries until something passes is a
#        model that will eventually find a chain that runs and means nothing.
#     5. Failure of the API is UNAVAILABLE, which means fall back to `RuleBasedPlanner` and
#        SAY SO in `plan.notes` — never silently, or nobody will notice the model is down.
#     """
#     name = "groq"
#     def propose(self, intention: str, memory: WorkingMemory) -> List[Step]: ...
