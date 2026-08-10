"""
PERCEPTUAL-ORGANS-002 Lane D — the answer, and the reason it is boring.

The laboratory says what it did and what it refused. It does not say what it saw. There is no
sentence in this file about a picture, and the mechanism that keeps it that way is not restraint:

    a response line is a TEMPLATE ID plus a FIELD DICT.

Nothing constructs free text. A line can only exist if its template is in `TEMPLATES` below, and a
field can only reach a reader if the template names it. So "the response never interprets the
image" is checkable by reading one dict rather than by reading every call site — and the test
checks it mechanically, by extracting the field names out of the format strings and asserting the
union is disjoint from the things that carry a reading.

WHAT IS DELIBERATELY UNSAYABLE HERE. `interpretation.label`, `ProposedStep.rationale`, planner
notes, and the model's own prose. The first is the organ's reading and belongs in the artifact
inspector where it is labelled as one. The rest are a planner's account of itself, and a planner's
sentence appearing in the result is how "the model said it found two figures" becomes something a
person remembers being told.

WHY TEMPLATES AT ALL, rather than the caller formatting its own strings. Because the phase gate
asks whether `LIVE`, `REPLAY` and `FIXTURE` are distinguishable, whether `empty` reads differently
from `refused`, and whether a fallback is visible — and those are properties of a fixed sentence
set, which can be inspected, rather than of a habit.

PURE. No database, no network, no model, no clock.
"""
from __future__ import annotations

from dataclasses import dataclass
from string import Formatter
from typing import Any, Dict, FrozenSet, List, Mapping, Sequence, Tuple

from backend.schemas.perception_lab import (LabPlan, LabRun, PerceptualArtifact, RunOutcome,
                                            StageState)

#: Every sentence this laboratory can say about a run. There is no sixteenth.
TEMPLATES: Mapping[str, str] = {
    "run": "{execution_identity} run {run_id}: {outcome}.",
    "organ": "{organ} organ, {mode} mode.",
    "planner": "planned by the {planner} planner.",
    "planner_fallback": "planned by the {planner} planner; the {fell_back_from} planner did not "
                        "answer, and this plan is not its work.",
    "confirmed": "this plan required confirmation before it could run, and was confirmed.",
    "replay_of": "re-shown from run {source_run_id}, recorded at {recorded_at}. Nothing was "
                 "called.",
    "extents": "{operation} via {adapter}: {count} extents, searched for {searched} "
               "({duration_ms}ms).",
    "extents_empty": "{operation} via {adapter}: searched for {searched} and found none "
                     "({duration_ms}ms).",
    "relations": "{operation} via {adapter}: {count} relations over {pairs_examined} pairs "
                 "({duration_ms}ms).",
    "relations_empty": "{operation} via {adapter}: examined {pairs_examined} pairs and found no "
                       "relation of that kind ({duration_ms}ms).",
    "field": "{operation} via {adapter}: a scalar field of {height} by {width} ({duration_ms}ms).",
    "basis": "{artifact_id} is {epistemic_status} on a {epistemic_basis} basis.",
    "not_attempted": "{operation} was not attempted: {detail}.",
    "refusal": "refused — {code}: {message}",
    "remedy": "to satisfy it: {remedy}",
    "prerequisite": "before this runs: {prerequisite}",
    "dropped": "{count} parameter(s) the operation does not declare were dropped: {names}.",
    "clamped": "{name} was clamped from {requested} to {applied} ({bound}).",
}

#: Field names, read OUT OF the templates rather than written beside them. A declaration written
#: twice is a declaration that drifts, and this one exists to be asserted against.
TEMPLATE_FIELDS: Mapping[str, FrozenSet[str]] = {
    key: frozenset(name for _, name, _, _ in Formatter().parse(text) if name)
    for key, text in TEMPLATES.items()
}

#: Everything that carries a reading of the picture or a planner's account of itself. The test
#: asserts this is disjoint from every field any template names.
UNSAYABLE: FrozenSet[str] = frozenset({
    "label", "labels", "naming", "interpretation", "notes", "note", "rationale", "why",
    "description", "prompt", "text", "reason", "summary", "confidence",
})


@dataclass(frozen=True)
class ResponseLine:
    """One sentence, and the data it was made of. Both, so a reader can check the second."""
    template_id: str
    fields: Mapping[str, Any]

    @property
    def text(self) -> str:
        return TEMPLATES[self.template_id].format(**self.fields)


@dataclass(frozen=True)
class LabResponse:
    lines: Tuple[ResponseLine, ...]

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def template_ids(self) -> Tuple[str, ...]:
        return tuple(line.template_id for line in self.lines)

    def of(self, template_id: str) -> Tuple[ResponseLine, ...]:
        return tuple(line for line in self.lines if line.template_id == template_id)


class _Writer:
    def __init__(self) -> None:
        self.lines: List[ResponseLine] = []

    def say(self, template_id: str, **fields: Any) -> None:
        unknown = set(fields) - TEMPLATE_FIELDS[template_id]
        if unknown:
            raise KeyError(f"template {template_id!r} names no field {sorted(unknown)}")
        self.lines.append(ResponseLine(template_id=template_id, fields=dict(fields)))


def respond(run: LabRun, plan: LabPlan,
            artifacts: Sequence[PerceptualArtifact] = ()) -> LabResponse:
    """One run, said out loud, in the fixed sentences above and no others."""
    w = _Writer()
    w.say("run", execution_identity=run.execution_identity.value, run_id=run.run_id,
          outcome=run.outcome.value)
    w.say("organ", organ=plan.selected_organ.value, mode=plan.mode.value)

    if plan.planner_fell_back_from is not None:
        w.say("planner_fallback", planner=plan.planner.value,
              fell_back_from=plan.planner_fell_back_from.value)
    else:
        w.say("planner", planner=plan.planner.value)

    if plan.requires_confirmation:
        w.say("confirmed")
    if run.replay is not None:
        w.say("replay_of", source_run_id=run.replay.source_run_id,
              recorded_at=run.replay.recorded_at)

    by_step = {a.identity.step_id: a for a in artifacts}
    for attempt in run.stage_attempts:
        artifact = by_step.get(attempt.step_id)
        if attempt.state in (StageState.SKIPPED, StageState.REFUSED, StageState.UNAVAILABLE,
                             StageState.FAILED):
            w.say("not_attempted", operation=attempt.operation,
                  detail=attempt.detail or attempt.state.value)
            continue
        if artifact is None:
            continue
        _say_measurement(w, attempt, artifact)

    for artifact in artifacts:
        w.say("basis", artifact_id=artifact.identity.artifact_id,
              epistemic_status=artifact.measurement.epistemic_status.value,
              epistemic_basis=artifact.measurement.epistemic_basis.value)

    for prerequisite in plan.prerequisites:
        w.say("prerequisite", prerequisite=prerequisite)

    for refusal in run.refusals:
        w.say("refusal", code=refusal.code.value, message=refusal.message)
        if refusal.remedy:
            w.say("remedy", remedy=refusal.remedy)

    if plan.dropped_parameters:
        names = sorted({d.name for d in plan.dropped_parameters})
        w.say("dropped", count=len(plan.dropped_parameters), names=", ".join(names))
    for clamp in plan.clamped_parameters:
        w.say("clamped", name=clamp.name, requested=clamp.requested, applied=clamp.applied,
              bound=clamp.bound)

    return LabResponse(lines=tuple(w.lines))


def _say_measurement(w: _Writer, attempt, artifact: PerceptualArtifact) -> None:
    payload = artifact.measurement.payload
    if payload is None:
        return
    common = {"operation": attempt.operation, "adapter": attempt.adapter or "a person",
              "duration_ms": attempt.duration_ms if attempt.duration_ms is not None else 0}
    if payload.variant == "extent_set":
        key = "extents" if payload.instances else "extents_empty"
        w.say(key, searched=payload.searched,
              **({"count": len(payload.instances)} if payload.instances else {}), **common)
    elif payload.variant == "topology_relation_set":
        key = "relations" if payload.relations else "relations_empty"
        w.say(key, pairs_examined=payload.pairs_examined,
              **({"count": len(payload.relations)} if payload.relations else {}), **common)
    elif payload.variant == "negative_space_field":
        w.say("field", height=payload.field_shape[0], width=payload.field_shape[1], **common)


def outcome_reads_as(run: LabRun) -> str:
    """The one-word difference between the five nothings, for a caller that wants only that."""
    return {RunOutcome.READY: "ready", RunOutcome.EMPTY: "measured emptiness",
            RunOutcome.UNAVAILABLE: "adapter not running here", RunOutcome.REFUSED: "a law said no",
            RunOutcome.PARTIAL: "some stages produced and some did not",
            RunOutcome.FAILED: "no claim is made"}[run.outcome]


__all__ = ["TEMPLATES", "TEMPLATE_FIELDS", "UNSAYABLE", "ResponseLine", "LabResponse", "respond",
           "outcome_reads_as"]
