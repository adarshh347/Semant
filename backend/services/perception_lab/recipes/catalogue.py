"""
PERCEPTUAL-FORMS-001G — the recipe catalogue: seven bounded studies, read from data.

A RECIPE IS DATA, AND THE WHOLE POINT IS WHAT IT CANNOT BE. It is an ordered list of direct acts
somebody could have performed one at a time, written down so they can be performed the same way
twice. Nothing in the file branches, nothing loops, nothing reads a result in order to decide the
next step, and no language model chooses or rewrites one — a model that wanted to change a study
would have to edit `contracts/perception-lab-recipes.v1.json`, which is a diff a person reads.

THE LOADER IS THE GATE, and it refuses at import for the reason `contracts.py` gives: a Python
fallback catalogue would be a second vocabulary invented at the moment the first went missing,
indistinguishable from the real one until it disagreed. Twelve checks run over every recipe before
any of them is handed out, and every one of them is a way a recipe could have quietly stopped
being a list of direct acts:

    the operation is declared          otherwise the resolver would refuse it at run time, and the
                                       catalogue would ship a study that cannot be performed
    the parameters are declared        an undeclared key is dropped-and-recorded by the resolver;
                                       shipping one in a recipe would put a smuggling attempt in
                                       the catalogue rather than in a model's output
    the organ matches in isolation     a study that crosses organs declares `chain` and asks for
                                       confirmation. One that crosses while calling itself
                                       isolated would break the session's own lock
    the form is registered             and is one the recipe declared it required
    the renderer is declared           by one of those forms. Lane A's `unknown_projection_fails
                                       _closed`, applied to the catalogue rather than to a runtime
    the model is admitted              a step naming a candidate Lane C rejected or deferred is
                                       refused HERE, so a rejected model is unreachable from a
                                       recipe rather than merely unused by one
    the bounds hold                    a recipe whose steps exceed its own declared bounds is a
                                       bound nobody enforces
    the fixture exists                 in Lane F's control manifest, so "this study runs on that
                                       control" is checkable rather than aspirational

WHAT A RECIPE DOES NOT CARRY. A result, a threshold, a fallback, or a rule for what to do when a
step fails. The stop conditions say what an outcome MEANS; they do not say what to do next,
because the thing to do next is a person's.

PURE. No database, no network, no model, no clock, no adapter.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.perception_lab import OrganFamily, SessionMode
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab.contracts import CONTRACTS_DIR, ContractError
from backend.services.perception_lab.extent_composites import admission as A

RECIPE_FILE = "perception-lab-recipes.v1.json"
RECIPE_SCHEMA_VERSION = "perception-lab-recipes.v1"

#: Lane F's controls. A recipe naming one that is not there is a study nobody can run.
CONTROLS = ("research", "perception_lab", "benchmarks", "controls", "manifest.json")

OPERATION = "operation"
DERIVATION = "derivation"


class RecipeError(ContractError):
    """A recipe that is not a list of direct acts. Raised at load, never returned."""


@dataclass(frozen=True)
class StopCondition:
    """What an outcome MEANS. Never what to do about it — that is a person's."""
    when: str
    outcome: str
    reason: str


@dataclass(frozen=True)
class DecisionPoint:
    """A question this study cannot answer, and why it cannot.

    `why_a_person` IS REQUIRED. A decision point with no reason is a confirmation dialog, and a
    confirmation dialog is the thing a person learns to click through.
    """
    at: str
    asks: str
    why_a_person: str
    options: Tuple[str, ...]


@dataclass(frozen=True)
class RecipeStep:
    """One act. Either a declared operation, or a pure derivation over what earlier steps recorded.

    THE TWO KINDS COUNT DIFFERENTLY AND THAT IS THE REASON THEY ARE TWO KINDS. An operation may
    reach an adapter and therefore an image, and counts against `max_adapter_calls`. A derivation
    reads records that already exist and calls nothing, so a study with four derivations and one
    operation looks at the picture exactly once.
    """
    id: str
    kind: str
    why: str
    operation: Optional[str] = None
    parameters: Mapping[str, Any] = None
    produces: Optional[str] = None
    reads: Tuple[str, ...] = ()
    model: Optional[str] = None
    asks_for: Tuple[str, ...] = ()

    @property
    def is_operation(self) -> bool:
        return self.kind == OPERATION


@dataclass(frozen=True)
class Recipe:
    """One bounded study, as declared."""
    key: str
    label: str
    question: str
    organ: OrganFamily
    mode: SessionMode
    required_forms: Tuple[str, ...]
    prerequisites: Tuple[str, ...]
    steps: Tuple[RecipeStep, ...]
    bounds: Mapping[str, int]
    stop_conditions: Tuple[StopCondition, ...]
    expected_renderers: Tuple[str, ...]
    decision_points: Tuple[DecisionPoint, ...]
    fixtures: Tuple[str, ...]

    @property
    def asks_for(self) -> Mapping[str, Tuple[str, ...]]:
        """What a person has to supply, per step. The catalogue for a runtime's prompts.

        A CONCEPT IS SOMEBODY'S WORD AND A DRAWN MASK IS THEIR HAND. A recipe fixes the shape of
        an act and never the content of those, because a stored concept would make every run of
        the study ask the same question of every picture, and a stored mask would be geometry
        authored by a file.
        """
        return {s.id: s.asks_for for s in self.steps if s.asks_for}

    @property
    def operations(self) -> Tuple[RecipeStep, ...]:
        return tuple(s for s in self.steps if s.is_operation)

    @property
    def derivations(self) -> Tuple[RecipeStep, ...]:
        return tuple(s for s in self.steps if not s.is_operation)

    @property
    def model_calls(self) -> Tuple[RecipeStep, ...]:
        """The operation steps that could reach a model.

        EVERY OPERATION REACHES AN ADAPTER, INCLUDING `extent.draw`. A person drawing a mask goes
        through the same registry, the same observer and the same run record — that is what makes
        a hand-drawn extent comparable with a segmented one. What a manual step does NOT do is run
        a model, and that is the budget that is scarce. So the bound counts model calls and says
        so; a bound named after adapters would have been counting a person's hand against a GPU.
        """
        return tuple(s for s in self.operations if not D.operation(str(s.operation)).manual)

    @property
    def crosses_organs(self) -> bool:
        return len({D.operation(s.operation).organ for s in self.operations}) > 1

    def step(self, step_id: str) -> RecipeStep:
        for candidate in self.steps:
            if candidate.id == step_id:
                return candidate
        raise RecipeError(f"{self.key!r} has no step {step_id!r}")


def _raw() -> Dict[str, Any]:
    path = CONTRACTS_DIR / RECIPE_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RecipeError(
            f"cannot read the recipe catalogue at {path}. There is no fallback catalogue: a "
            f"Python table invented here would be a second set of studies, indistinguishable "
            f"from the real ones until it disagreed.") from exc
    if data.get("schema_version") != RECIPE_SCHEMA_VERSION:
        raise RecipeError(
            f"the recipe catalogue declares {data.get('schema_version')!r} and this code enforces "
            f"{RECIPE_SCHEMA_VERSION!r}")
    return data


def _step(raw: Mapping[str, Any], recipe_key: str) -> RecipeStep:
    kind = str(raw.get("kind"))
    if kind not in (OPERATION, DERIVATION):
        raise RecipeError(f"{recipe_key}: step {raw.get('id')!r} is a {kind!r}, and the two kinds "
                          f"are {OPERATION!r} and {DERIVATION!r}")
    return RecipeStep(
        id=str(raw["id"]), kind=kind, why=str(raw["why"]),
        operation=raw.get("operation"), parameters=dict(raw.get("parameters") or {}),
        produces=raw.get("produces"), reads=tuple(str(r) for r in raw.get("reads", ())),
        model=raw.get("model"),
        asks_for=tuple(str(a) for a in raw.get("asks_for", ())))


def _check(recipe: Recipe, *, controls: Sequence[str], outcomes: Sequence[str]) -> None:
    """Twelve refusals, each naming a way a recipe stops being a list of direct acts."""
    seen: List[str] = []
    for step in recipe.steps:
        if step.id in seen:
            raise RecipeError(f"{recipe.key}: two steps share the id {step.id!r}")
        for source in step.reads:
            if source not in seen:
                raise RecipeError(
                    f"{recipe.key}: step {step.id!r} reads {source!r}, which does not come before "
                    f"it. A step that reads its own future is not an ordered list of acts.")
        seen.append(step.id)

        if step.is_operation:
            definition = D.operation(str(step.operation))    # raises on an undeclared key
            declared = {p.name for p in definition.parameters}
            extra = sorted(set(step.parameters) - declared)
            if extra:
                raise RecipeError(
                    f"{recipe.key}: step {step.id!r} carries {extra}, which {step.operation!r} "
                    f"does not declare. The resolver would drop and record them; shipping them in "
                    f"the catalogue would put the smuggling attempt in the recipe.")
            unasked = sorted(set(step.asks_for) - declared)
            if unasked:
                raise RecipeError(
                    f"{recipe.key}: step {step.id!r} asks a person for {unasked}, which "
                    f"{step.operation!r} does not declare as a parameter.")
            overlap = sorted(set(step.asks_for) & set(step.parameters))
            if overlap:
                raise RecipeError(
                    f"{recipe.key}: step {step.id!r} both fixes and asks for {overlap}. A "
                    f"parameter the recipe already decided is not one a person is being asked "
                    f"about, and showing them a control that changes nothing is worse than "
                    f"showing them none.")
            missing_required = sorted(
                {p.name for p in definition.parameters if p.required}
                - set(step.parameters) - set(step.asks_for))
            if missing_required:
                raise RecipeError(
                    f"{recipe.key}: step {step.id!r} neither fixes nor asks for "
                    f"{missing_required}, "
                    f"which {step.operation!r} requires. The step would be refused by the "
                    f"resolver every time it ran.")
            if recipe.mode is SessionMode.ISOLATION \
                    and definition.organ != recipe.organ.value:
                raise RecipeError(
                    f"{recipe.key}: step {step.id!r} is a {definition.organ} operation in a study "
                    f"locked to {recipe.organ.value}. A study that crosses organs declares "
                    f"`chain` and asks for confirmation.")
        else:
            if not step.produces:
                raise RecipeError(f"{recipe.key}: derivation {step.id!r} produces nothing")
            D.form(str(step.produces))                        # raises on an unregistered form
            if step.produces not in recipe.required_forms:
                raise RecipeError(
                    f"{recipe.key}: step {step.id!r} produces {step.produces!r}, which the recipe "
                    f"does not list as required. A study's required forms are what a reader "
                    f"checks availability against.")
        if step.model is not None:
            form_key = step.produces or (D.operation(str(step.operation)).produces_forms[0]
                                         if step.is_operation else "")
            A.admitted(str(step.model), str(form_key), role=A.Role.PRODUCER)

    for form_key in recipe.required_forms:
        D.form(form_key)

    declared_renderers = {p.kind for f in recipe.required_forms
                          for p in D.form(f).renderer_projections}
    unknown = sorted(set(recipe.expected_renderers) - declared_renderers)
    if unknown:
        raise RecipeError(
            f"{recipe.key}: expects the renderers {unknown}, which none of its required forms "
            f"declares. A study cannot promise a drawing the form has no projection for.")

    counted = {"max_operations": len(recipe.operations),
               "max_model_calls": len(recipe.model_calls)}
    for bound, actual in counted.items():
        limit = recipe.bounds.get(bound)
        if limit is None:
            raise RecipeError(f"{recipe.key}: declares no {bound}. An unbounded study is a study "
                              f"whose cost nobody agreed to.")
        if actual > int(limit):
            raise RecipeError(
                f"{recipe.key}: has {actual} steps counting against {bound} and declares "
                f"{limit}. A bound the recipe itself exceeds is a bound nobody enforces.")

    for condition in recipe.stop_conditions:
        if condition.outcome not in outcomes:
            raise RecipeError(
                f"{recipe.key}: stop condition outcome {condition.outcome!r} is not one of "
                f"{list(outcomes)}")
    if not recipe.stop_conditions:
        raise RecipeError(f"{recipe.key}: declares no stop condition. A study that cannot end is "
                          f"not bounded by anything a reader can see.")

    for point in recipe.decision_points:
        recipe.step(point.at)
        if not point.why_a_person:
            raise RecipeError(
                f"{recipe.key}: decision point at {point.at!r} gives no reason a person is "
                f"needed. A decision point with no reason is a confirmation dialog, and a "
                f"confirmation dialog is the thing people learn to click through.")

    missing = sorted(set(recipe.fixtures) - set(controls))
    if missing:
        raise RecipeError(
            f"{recipe.key}: names the controls {missing}, which Lane F's manifest does not hold. "
            f"'this study runs on that control' has to be checkable.")


def controls() -> Tuple[str, ...]:
    """Lane F's twelve, by key. Read rather than repeated, so a control that is renamed there
    fails here instead of silently ceasing to be the thing a study was checked against."""
    from backend.services.perception_lab.contracts import REPO_ROOT
    return tuple(json.loads((REPO_ROOT.joinpath(*CONTROLS)).read_text(encoding="utf-8"))
                 ["controls"])


def build(raw: Mapping[str, Any], *, controls: Sequence[str],
          outcomes: Sequence[str]) -> Recipe:
    """One recipe, typed and checked. Public so the twelve refusals can be shown to bite.

    A validator nothing fails on is a comment, and the only way to fail these is to hand the
    builder a recipe that breaks one — which is what the suite does, one mutation at a time.
    """
    recipe = Recipe(
        key=str(raw["key"]), label=str(raw["label"]), question=str(raw["question"]),
        organ=OrganFamily(raw["organ"]), mode=SessionMode(raw["mode"]),
        required_forms=tuple(str(f) for f in raw["required_forms"]),
        prerequisites=tuple(str(p) for p in raw["prerequisites"]),
        steps=tuple(_step(step, str(raw["key"])) for step in raw["steps"]),
        bounds={str(k): int(v) for k, v in raw["bounds"].items()},
        stop_conditions=tuple(StopCondition(str(c["when"]), str(c["outcome"]), str(c["reason"]))
                              for c in raw["stop_conditions"]),
        expected_renderers=tuple(str(r) for r in raw["expected_renderers"]),
        decision_points=tuple(DecisionPoint(str(d["at"]), str(d["asks"]),
                                            str(d.get("why_a_person", "")),
                                            tuple(str(o) for o in d.get("options", ())))
                              for d in raw["decision_points"]),
        fixtures=tuple(str(f) for f in raw["fixtures"]))
    _check(recipe, controls=controls, outcomes=outcomes)
    return recipe


@lru_cache(maxsize=None)
def _catalogue() -> Dict[str, Recipe]:
    data = _raw()
    known = controls()
    outcomes = list(data["stop_outcomes"])
    out: Dict[str, Recipe] = {}
    for raw in data["recipes"]:
        recipe = build(raw, controls=known, outcomes=outcomes)
        if recipe.key in out:
            raise RecipeError(f"recipe {recipe.key!r} is declared twice")
        out[recipe.key] = recipe
    return out


def recipes() -> Mapping[str, Recipe]:
    """All seven, in catalogue order."""
    return _catalogue()


def recipe(key: str) -> Recipe:
    """FAIL CLOSED. An unknown key raises rather than returning a stub, for the reason
    `definitions.operation()` does: a caller that got an object back might render a control for
    it, and a study that does not exist would look exactly like one that does."""
    try:
        return _catalogue()[str(key)]
    except KeyError:
        raise RecipeError(
            f"{key!r} is not a declared recipe. The seven are {sorted(_catalogue())}, and there "
            f"is no fallback.") from None


def stop_outcomes() -> Tuple[str, ...]:
    return tuple(_raw()["stop_outcomes"])


def raw_catalogue() -> Dict[str, Any]:
    """The file as written, for a caller that wants to mutate a copy and watch a check bite."""
    return _raw()


__all__ = ["CONTROLS", "DERIVATION", "DecisionPoint", "OPERATION", "RECIPE_FILE",
           "RECIPE_SCHEMA_VERSION", "Recipe", "RecipeError", "RecipeStep", "StopCondition",
           "build", "controls", "raw_catalogue", "recipe", "recipes", "stop_outcomes"]
