"""
PERCEPTUAL-FORMS-001G — turning a recipe into direct acts, through the machinery that already
exists.

THERE IS NO SECOND EXECUTION PATH, AND THAT IS THE DELIVERABLE. A recipe's operation steps become
`DirectCommand`s — the same object a pressed control produces — and go to `DirectPlanner`, whose
proposal goes to the same `resolver.resolve` with the same five gates. So "a recipe reaches the
same low-level producer as direct invocation" is not a property that has to be maintained by
anybody: it is the only arrangement this module can produce, because it holds no runner, no
adapter and no registry, and there is nothing here for a second path to be made out of.

WHAT THAT BUYS, CONCRETELY. A recipe cannot skip the organ lock, cannot smuggle a parameter the
operation does not declare, cannot cite an id the session has not declared, cannot reach an
unavailable adapter, and cannot mark its own steps authorized — because every one of those is
refused by a gate this module does not own and cannot reach past. A recipe that tried would
produce a plan with a refusal on it, exactly as a person pressing the same control would.

EVERY STEP STAYS SEPARATELY VISIBLE. One recipe step becomes one `ProposedStep` and one
`ResolvedStep`, in the order the recipe declares, each with its own id and its own refusals.
Nothing is merged, nothing is folded into a summary, and a study that ran three acts shows three.
Collapsing them would make the middle of a study unobservable, which is the whole reason the
laboratory exists.

THE REFERENCES COME FROM THE SESSION AND FROM NOWHERE ELSE. Roles are read off the operation
registry and filled from `SessionView.references` in session order — the same source, in the same
order, that `planners.base.bind_single` and `bind_pair` use. There is no code here that builds an
artifact id out of a string in the catalogue, so a recipe cannot name a mask a person did not
select.

DERIVATIONS ARE NOT PLANNED. A derivation step reads records that already exist and calls nothing,
so it has no `ResolvedStep` and no adapter call; `derivations()` returns them for a runtime to
perform against the composite producers in `extent_composites` and `extent_forms`. Planning them
would put a pure function through a capability gate and report a model call that never happened.

PURE. No database, no network, no model, no adapter, no registry. Clock and ids are injected.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.perception_lab import CapabilityState, InputRef, LabPlan, OrganFamily
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab.clock import Clock, IdFactory
from backend.services.perception_lab.planners.base import DirectCommand
from backend.services.perception_lab.planners.direct import DirectPlanner
from backend.services.perception_lab.recipes.catalogue import Recipe, RecipeError, RecipeStep
from backend.services.perception_lab.resolver import Resolution, resolve
from backend.services.perception_lab.session import SessionView


def bind(op_key: str, session: SessionView) -> Tuple[InputRef, ...]:
    """The references an operation's declared roles take, in session order.

    ROLES ARE READ OFF THE REGISTRY RATHER THAN LISTED HERE. `planners/rules.py` carries a
    hand-written table because it also decides WHICH operation a sentence meant; a recipe already
    names the operation, so the roles follow from the contract and a table here would be a second
    copy that drifts the first time an operation gains an input.

    FEWER REFERENCES THAN ROLES YIELDS FEWER REFS, NEVER A REPEAT. The resolver refuses
    `missing_extent_inputs`, which is the honest answer; filling the second role with the first
    reference would measure a relation between something and itself perfectly and answer nothing.
    """
    definition = D.operation(op_key)
    available = list(session.references)
    refs: List[InputRef] = []
    for spec in definition.inputs:
        take = available[:spec.max] if spec.max > 1 else available[:1]
        for artifact_id, instance_id in take:
            refs.append(session.artifact_ref(spec.role, artifact_id, instance_id))
        available = available[len(take):]
    return tuple(refs)


Bindings = Mapping[str, Mapping[str, Any]]


def commands(recipe: Recipe, session: SessionView,
             bindings: Optional[Bindings] = None) -> Tuple[DirectCommand, ...]:
    """The recipe's operation steps, as the objects a pressed control produces.

    IN THE ORDER THE RECIPE DECLARES. A planner that reordered them would be deciding the shape of
    somebody's experiment, and a recipe exists precisely so the shape is decided once and written
    down.

    `bindings` FILLS ONLY WHAT THE RECIPE ASKED A PERSON FOR. A concept is somebody's word and a
    drawn mask is their hand; the catalogue lists those per step in `asks_for` and fixes
    everything else. A binding for a parameter the step did not ask about is REFUSED rather than
    merged, because a caller that can overwrite a fixed parameter can turn one study into
    another while it still reports the first study's name.
    """
    supplied = {str(k): dict(v) for k, v in (bindings or {}).items()}
    unknown_steps = sorted(set(supplied) - {s.id for s in recipe.steps})
    if unknown_steps:
        raise RecipeError(f"{recipe.key}: bindings name the steps {unknown_steps}, which it has "
                          f"no steps for")
    out: List[DirectCommand] = []
    for step in recipe.operations:
        given = supplied.pop(step.id, {})
        extra = sorted(set(given) - set(step.asks_for))
        if extra:
            raise RecipeError(
                f"{recipe.key}: step {step.id!r} was handed {extra}, and asks a person only for "
                f"{list(step.asks_for)}. A caller that can overwrite a fixed parameter can turn "
                f"one study into another while it still reports the first study's name.")
        out.append(DirectCommand(operation=str(step.operation),
                                 parameters={**dict(step.parameters or {}), **given},
                                 input_refs=bind(str(step.operation), session)))
    return tuple(out)


def derivations(recipe: Recipe) -> Tuple[RecipeStep, ...]:
    """The steps that read records and call nothing. Not planned, and not hidden either."""
    return recipe.derivations


def plan(recipe: Recipe, session: SessionView, *, capabilities: Mapping[str, CapabilityState],
         clock: Clock, ids: IdFactory, bindings: Optional[Bindings] = None,
         plan_id: Optional[str] = None) -> Resolution:
    """One recipe, through the Direct arm and the resolver, into a plan a person can look at.

    THE SESSION'S ORGAN AND MODE ARE THE SESSION'S. This does not set them from the recipe: a
    study declared `chain` run inside a session locked to `isolation` must be refused by the lock,
    not quietly granted by the thing that wants to run. `check(recipe, session)` is available for
    a caller that wants to know BEFORE building a plan, and it is deliberately separate — a check
    that ran automatically here would make the refusal disappear into an exception nobody records.
    """
    proposal = DirectPlanner(ids=ids).plan_many(commands(recipe, session, bindings), session)
    return resolve(proposal, session, capabilities=capabilities, clock=clock, ids=ids,
                   plan_id=plan_id)


@dataclass(frozen=True)
class Readiness:
    """Whether a study can be run here, and every reason it cannot. Never a partial yes."""
    recipe_key: str
    ready: bool
    unmet_prerequisites: Tuple[str, ...] = ()
    unproducible_forms: Tuple[str, ...] = ()
    unavailable_operations: Tuple[str, ...] = ()
    mode_conflict: Optional[str] = None

    @property
    def reasons(self) -> Tuple[str, ...]:
        out = list(self.unmet_prerequisites)
        out += [f"{f}: not producible in this deployment" for f in self.unproducible_forms]
        out += [f"{o}: unavailable" for o in self.unavailable_operations]
        if self.mode_conflict:
            out.append(self.mode_conflict)
        return tuple(out)


def check(recipe: Recipe, session: SessionView, *,
          capabilities: Mapping[str, CapabilityState] = None) -> Readiness:
    """Every reason this study cannot run here, gathered before anything is planned.

    ABSENT DEPENDENCIES REFUSE, and they refuse with the specific absence rather than with a
    general no. Four of the five composite forms are `deferred` in the merged contract, so four of
    the seven studies cannot write their final record today — and a runtime that discovered that
    only at the last step would have spent every adapter call first.

    `unproducible_forms` IS NOT AN ERROR AND IS NOT AN EXCUSE TO SKIP THE STUDY. The steps before
    the deferred one are real measurements worth having, which is why this reports rather than
    raises: the decision to run four fifths of a study belongs to whoever is sitting at it.
    """
    unavailable: List[str] = []
    for step in recipe.operations:
        state = (capabilities or {}).get(str(step.operation))
        if state is not None and state is not CapabilityState.AVAILABLE:
            unavailable.append(str(step.operation))
    unproducible = [f for f in recipe.required_forms if not D.form(f).producible]
    conflict = None
    if recipe.crosses_organs and session.mode is not recipe.mode:
        conflict = (f"{recipe.key} crosses the organ boundary and declares {recipe.mode.value}; "
                    f"this session is {session.mode.value}. A prompt may not change organs and "
                    f"neither may a recipe.")
    elif session.selected_organ is not recipe.organ and recipe.mode.value == "isolation":
        conflict = (f"{recipe.key} is a {recipe.organ.value} study and this session is locked to "
                    f"{session.selected_organ.value}")
    return Readiness(
        recipe_key=recipe.key,
        ready=not (unavailable or unproducible or conflict),
        unproducible_forms=tuple(unproducible),
        unavailable_operations=tuple(unavailable),
        mode_conflict=conflict)


__all__ = ["Bindings", "Readiness", "bind", "check", "commands", "derivations", "plan"]
