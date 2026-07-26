"""
CIRCUIT-001 ORCH-001 — workflows: named chains, saved and replayable.

A workflow is a way of looking that someone found worth keeping. `trace_light` is not a
macro for saving keystrokes — it is the claim that light, its withholding, and a reading of
both belong together, and that looking at them separately misses what they say jointly.

FIRST-CLASS means three specific things, and a workflow that lacks any of them is just a
list:

  INSPECTABLE — `describe()` renders the chain, its steps, what each needs and leaves
  behind, WITHOUT running it or touching a model. A curator can see what a workflow would
  do before it does it, and so can a reviewer reading a bug report.

  REPLAYABLE — `plan_for()` on the same memory yields an identical plan. Step ids are
  derived from the workflow name and position, never from a clock or a counter, so two
  replays are byte-comparable. That property is what makes a recorded run reproducible
  rather than merely re-runnable.

  ADAPTIVE, WITHOUT LYING — a workflow does not assume its inputs exist. It goes through
  the same `resolve()` as everything else, so replaying `weigh_composition` against an
  image with no marks yields a plan whose `compose_percept` is honestly refused rather
  than fired on nothing.

The seeds below come from the capability map's own archetypes. They are deliberately few:
three real chains that were reasoned about beat a dozen guessed ones, and the registry
takes new entries without any code change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .capabilities import ACTUATORS, Resource, get as get_actuator
from .memory import WorkingMemory
from .plan import Plan, Step, resolve

WORKFLOW_VERSION = 1


@dataclass(frozen=True)
class Workflow:
    """A named, ordered chain of actuator calls with a stated reason for existing."""
    name: str
    title: str
    why: str                                        # what this way of looking is FOR
    steps: Tuple[Tuple[str, Dict[str, Any]], ...]   # (actuator, params) in intended order
    version: int = WORKFLOW_VERSION

    def to_steps(self) -> List[Step]:
        """Materialise as Steps with DETERMINISTIC ids — the basis of replay.

        `{name}:{position}:{actuator}` carries no time and no randomness, so the same
        workflow always produces the same ids and two runs can be diffed directly.
        """
        out: List[Step] = []
        for i, (actuator, params) in enumerate(self.steps):
            out.append(Step(actuator=actuator, params=dict(params),
                            id=f"{self.name}:{i}:{actuator}"))
        return out

    def plan_for(self, memory: WorkingMemory) -> Plan:
        """Resolve this chain against a real memory. Same gate as any other plan."""
        return resolve(self.to_steps(), memory,
                       intention=self.title, workflow=self.name, planner="workflow")

    def describe(self) -> Dict[str, Any]:
        """Inspect without running. Unknown actuators surface here rather than at dispatch."""
        rows: List[Dict[str, Any]] = []
        for i, (name, params) in enumerate(self.steps):
            actuator = get_actuator(name)
            rows.append({
                "position": i,
                "actuator": name,
                "known": actuator is not None,
                "summary": actuator.summary if actuator else "",
                "requires": [r.describe() for r in actuator.requires] if actuator else [],
                "produces": [p.value for p in actuator.produces] if actuator else [],
                "params": dict(params),
            })
        return {"name": self.name, "title": self.title, "why": self.why,
                "version": self.version, "steps": rows}


# ── the seeds ────────────────────────────────────────────────────────────────

TRACE_LIGHT = Workflow(
    name="trace_light",
    title="Trace the light",
    why=("Light and shadow are one fact seen twice. Brushing both, then asking for a reading "
         "of what was brushed, keeps the reading resting on gathered evidence instead of on "
         "the model's first impression of the picture."),
    steps=(
        ("light_field", {}),
        ("shadow_field", {}),
        # Needs a REGION, which neither field above produces. On a bare image this is
        # refused — correctly. It runs when the curator has already found parts, which is
        # exactly when a reading has something to rest on.
        ("semantic_read", {"question": "How does the light fall, and what does it withhold?"}),
    ),
)

MOTIF_AND_ECHOES = Workflow(
    name="motif_and_echoes",
    title="Find the motif and its echoes",
    why=("A motif is only a motif if it recurs. This finds the named thing, looks for it "
         "again elsewhere, and then asks for the relation to be named — the third step is "
         "what turns two similar marks into a claim about the picture."),
    steps=(
        ("grounded_sam_find_parts", {}),   # phrase comes from the packet — the curator's words
        ("find_similar", {}),
        ("connect_marks", {"relation_role": "motif_echo"}),
    ),
)

WEIGH_COMPOSITION = Workflow(
    name="weigh_composition",
    title="Weigh the composition",
    why=("Where the picture concentrates, where it empties, and how it repeats — three "
         "cheap CPU reads that together describe the distribution of attention. Composed "
         "last, so the percept rests on all three rather than on whichever ran first."),
    steps=(
        ("pressure_zone", {}),
        ("rhythm", {}),
        # Needs a region; refused on a bare image, runs once parts exist.
        ("negative_space", {}),
        ("compose_percept", {"draft_text": ""}),
    ),
)

_SEEDS: Tuple[Workflow, ...] = (TRACE_LIGHT, MOTIF_AND_ECHOES, WEIGH_COMPOSITION)

REGISTRY: Dict[str, Workflow] = {w.name: w for w in _SEEDS}


def get(name: str) -> Optional[Workflow]:
    """Look up a workflow, or None. None is a refusal — never a silent empty chain."""
    return REGISTRY.get(name)


def names() -> Tuple[str, ...]:
    return tuple(REGISTRY.keys())


def catalog() -> List[Dict[str, Any]]:
    """Every workflow, inspectable. What a future surfacing gate would render."""
    return [w.describe() for w in REGISTRY.values()]


def register(workflow: Workflow, *, overwrite: bool = False) -> Workflow:
    """Add a workflow at runtime.

    Refuses to overwrite silently: a chain replaced under the same name would make every
    recorded replay of the old one unreproducible while still claiming that name.
    """
    if workflow.name in REGISTRY and not overwrite:
        raise ValueError(f"workflow '{workflow.name}' already exists; pass overwrite=True")
    unknown = [a for a, _ in workflow.steps if a not in ACTUATORS]
    if unknown:
        raise ValueError(f"workflow '{workflow.name}' names unknown actuators: {unknown}")
    REGISTRY[workflow.name] = workflow
    return workflow
