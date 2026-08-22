# Perceptual recipes — the catalogue, and what Lane H needs to show it

PERCEPTUAL-FORMS-001G. Seven bounded studies, declared in
`contracts/perception-lab-recipes.v1.json`, loaded by `catalogue.py`, expanded into direct acts by
`expand.py`. This file is the handover: what the catalogue holds, and what a runtime and a
frontend have to add before a person can run one.

## The catalogue

| key | organ · mode | direct operations | derivations | model calls | controls |
|---|---|---|---|---|---|
| `boundary-and-void` | extent · isolation | `extent.find_all` | `extent.boundary_rings`, `extent.hole_set` | 1 | solid-mask, donut, nested-holes |
| `fragment-continuity` | extent · isolation | `extent.find_named` | `extent.fragment_set`, `extent.fused_hypothesis` | 1 | disconnected-fragments, false-similarity |
| `visible-versus-inferred` | extent · isolation | `extent.find_named`, `extent.draw` | `extent.visible_inferred_partition` | 1 | partition |
| `courtyard-hierarchy` | extent · **chain** | `extent.find_all`, `topology.all_pairs` | `topology.containment_tree`, `extent.hierarchy` | 2 | containment-tree, nested-holes |
| `piazza-negative-space` | extent · **chain** | `extent.find_named`, `topology.negative_space` | `extent.fragment_set`, `extent.density_field` | 2 | density-peaks, soft-fringe |
| `topology-sensitivity` | topology · isolation | `topology.all_pairs` ×2 | `topology.transition` | 2 | one-pixel-transition, adjacency-graph |
| `ambiguous-form-hypothesis` | extent · isolation | `extent.find_named` ×2 | `extent.hypothesis_set` | 2 | competing-extents, false-similarity |

Every recipe declares the seven things a recipe is — required forms, ordered operations,
prerequisites, bounds, stop conditions, expected renderers, human decision points — and the loader
refuses one that is missing any of them.

**Two step kinds, and they cost differently.** An `operation` becomes a `DirectCommand` and goes
through the Direct planner and the resolver. A `derivation` reads recorded artifacts and calls
nothing; `expand.derivations()` returns them for a runtime to perform against `extent_forms` and
`extent_composites`. Every operation reaches an adapter — including `extent.draw`, because a
person's hand goes through the same registry, observer and run record — so the scarce budget is
`max_model_calls`, which counts the non-manual ones only.

## What a runtime has to add

1. **Perform the derivations.** `expand.plan()` returns a `Resolution` covering the operation
   steps only. The mapping from a derivation's `produces` to its producer is not in this package
   (a test in `test_perception_lab_recipes.py` holds the mapping total):

   | form | producer |
   |---|---|
   | `extent.boundary_rings` | `extent_forms.boundary_rings` |
   | `extent.hole_set` | `extent_forms.hole_set` |
   | `extent.fragment_set` | `extent_forms.fragment_set` |
   | `extent.fused_hypothesis` | `extent_composites.produce_fused_hypothesis` |
   | `extent.visible_inferred_partition` | `extent_composites.produce_visible_inferred_partition` |
   | `extent.hierarchy` | `extent_composites.produce_extent_hierarchy` |
   | `extent.density_field` | `extent_composites.produce_density_field` |
   | `extent.hypothesis_set` | `extent_composites.produce_hypothesis_set` |
   | `topology.containment_tree` | `topology_forms.produce_containment_tree` |
   | `topology.transition` | `topology_forms.produce_transition` |

2. **Honour `producible`.** Four of the five composite forms are `deferred` in the merged
   contract. Every producer returns a `FormProduction` whose `writable_payload` is `None` when the
   form may not be written, and whose `refusals` carry `form_not_producible`. A runtime that minted
   an artifact from `payload` rather than from `writable_payload` would write a deferred form.

3. **Collect what the recipe asks a person for.** `Recipe.asks_for` is `{step_id: (parameter,)}` —
   `concept` on four steps, `mask_rle` on one. Pass them to `expand.commands(recipe, session,
   bindings)`. A binding for anything the step did not ask about is refused.

4. **Check before spending.** `expand.check(recipe, session, capabilities=…)` returns a
   `Readiness` naming unproducible forms, unavailable operations and mode conflicts. Four of the
   seven cannot write their final record today; discovering that at the last step means every
   model call was already spent.

## What Lane H needs on the surface

**Renderers.** Every renderer a recipe expects is already declared by one of its required forms
and implemented in Lane E's registry — the loader refuses a recipe that promises one no form
declares. The union across the seven is: `mask_fill`, `mask_outline`, `ring_outline`, `hole_fill`,
`fragment_cluster`, `hypothesis_stack`, `partition_tricolor`, `scalar_wash`, `density_contours`,
`hierarchy_tree`, `relation_graph`, `transition_diff`, `before_after`, `ab_overlay`. **No new
renderer kind is needed.**

**What is not yet drawable, and is the one real gap.** Nothing in Lane E draws a *study*: the
sequence of acts, which step is running, which produced what, and where the run stopped. That is
a recipe-level surface, not a form-level one, and it is Lane H's.

**API shape this package implies** (none of it exists yet; this package has no routes):

- `GET /recipes` — the catalogue, projected. Needs: key, label, question, organ, mode,
  prerequisites, bounds, stop conditions, decision points, `asks_for`, fixtures.
- `GET /recipes/{key}/readiness?session_id=` — `Readiness`, so the button can be disabled with a
  reason rather than merely disabled.
- `POST /sessions/{id}/recipes/{key}` with `{bindings}` — plan and return the plan for a person to
  look at BEFORE anything runs. A chain study returns `requires_confirmation: true`.
- `POST /sessions/{id}/plans/{plan_id}/execute` — the existing execute path, unchanged.
- The derivations need a step of their own on the wire; they are not in `resolved_steps` and a
  surface that showed only resolved steps would show two thirds of a study.

**Three things the surface must not do**, each because a producer here already refuses it:

- never present a decision point as a confirmation dialog — every one carries `why_a_person`, and
  the loader refuses a decision point without it;
- never order alternatives by weight — `produce_hypothesis_set` orders by derived id precisely so
  that nothing in the record reads as a winner, and a UI that re-sorted would put the winner back;
- never draw an omission as an absence — `FormProduction.omitted` names what was left out and
  why, and a study that showed only what it kept would read as complete.

## Limits this lane reports rather than works around

- `ProducerKind` has no value for an exact derivation (`adapter`, `human`, `fixture`, `replay`).
  The lane that mints artifacts for these forms will have to answer it.
- `Ground` has no field for the WITNESS. `grounds.py` checks the attribution where the record is
  built and puts it in `detail` as prose; a payload read alone cannot tell a model's cosine from a
  per-pixel adjacency count.
- `HierarchyNode` has no field distinguishing geometric containment from asserted part/whole, so
  the distinction lives in `basis` (`mask` versus `manual`) and `occupancy_of_parent` is left null
  on an asserted link.
- `fakes.full_registry()` does not cover `topology.all_pairs` under `nestedness_organ`, which the
  contract declares first for that operation. The recipe suite registers a conforming fake locally.
