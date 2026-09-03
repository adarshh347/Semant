"""
PERCEPTUAL-FORMS-001G — perceptual recipes: bounded studies, composed of direct acts.

A RECIPE IS DATA AND A STUDY IS A SEQUENCE OF DIRECT ACTS. Seven of them live in
`contracts/perception-lab-recipes.v1.json`, each declaring the seven things a recipe is: the forms
it requires, the ordered operations it performs, its prerequisites, its bounds, the conditions
under which it stops, the renderers it expects, and the points at which a person has to decide.

THERE IS NO SECOND EXECUTION PATH, and that is the whole deliverable. An operation step becomes a
`DirectCommand` — the object a pressed control produces — and goes to the Direct planner and the
same resolver, so every gate a person's control passes through, a recipe passes through. This
package holds no runner, no adapter and no registry; there is nothing here for a second path to be
made out of.

NO MODEL CHOOSES OR REWRITES A RECIPE. The Direct arm is the only planner in reach and it has no
language in it. A model that wanted to change a study would have to edit the catalogue file, which
is a diff a person reads.

A DERIVATION IS NOT PLANNED. Steps that read recorded artifacts and call nothing are returned for
a runtime to perform against `extent_forms` and `extent_composites`. Planning them would put a
pure function through a capability gate and report a model call that never happened.

PURE. No database, no network, no model, no adapter. Clock and ids are injected.
"""
from __future__ import annotations

from backend.services.perception_lab.recipes.catalogue import (DERIVATION, DecisionPoint,
                                                               OPERATION, Recipe, RecipeError,
                                                               RecipeStep, StopCondition, build,
                                                               controls, raw_catalogue, recipe,
                                                               recipes, stop_outcomes)
from backend.services.perception_lab.recipes.expand import (Bindings, Readiness, bind, check,
                                                            commands, derivations, plan)

__all__ = [
    "Bindings", "DERIVATION", "DecisionPoint", "OPERATION", "Readiness", "Recipe", "RecipeError",
    "RecipeStep", "StopCondition", "bind", "build", "check", "commands", "controls",
    "derivations", "plan", "raw_catalogue", "recipe", "recipes", "stop_outcomes",
]
