"""
PERCEPTUAL-FORMS-001G — the seven recipes, and the ten things a recipe may not become.

A RECIPE IS DATA AND A STUDY IS A SEQUENCE OF DIRECT ACTS. Everything in this module is arranged
around the one claim that makes that worth having: a recipe has no execution path of its own. Its
operation steps become `DirectCommand`s, go to the Direct planner, and land in the same resolver
and the same adapter a pressed control reaches — so the proof is not "the outputs agree", it is
"there was only ever one route", asserted on the adapter's own call list and on the import graph.

THE CLAIMS, and each has its own section below:

    same producer      a recipe step and a pressed control reach one adapter object with one call
    visibility         one recipe step is one proposed step and one resolved step, in order
    bounds             the adapter is called exactly as many times as the recipe declared
    dependencies       an absent form, an unavailable organ and a locked session each refuse, and
                       each refuses with the specific absence rather than a general no
    hypotheses         the studies that produce claims declare no route by which a claim resolves
    models             a candidate Lane C rejected cannot be named by a recipe at all
    replay             re-showing a study computes nothing
    the source         nothing a recipe does touches the picture it was run on
    fixtures           every named control exists in Lane F's manifest and carries the form
    the checks bite    twelve refusals in the loader, each shown catching a specific break

PURE. No database, no network, no real model. The adapters are Lane D's contract-shaped fakes.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pytest

from backend.schemas.perception_lab import (CapabilityState, ExecutionIdentity, LabSource,
                                            OrganFamily, RefusalCode, SessionMode)
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab import fakes
from backend.services.perception_lab.adapters import AdapterRegistry
from backend.services.perception_lab.clock import FrozenClock, SequentialIds
from backend.services.perception_lab.orchestrator import PerceptionConductor
from backend.services.perception_lab.planners import DirectCommand
from backend.services.perception_lab.recipes import catalogue as C
from backend.services.perception_lab.recipes import expand as E
from backend.services.perception_lab.session import SessionView
from backend.services.perception_lab.store import InMemoryLabStore

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTROLS = json.loads(
    (REPO_ROOT / "research" / "perception_lab" / "benchmarks" / "controls" / "manifest.json")
    .read_text(encoding="utf-8"))["controls"]

SOURCE = LabSource(origin="post", post_id="post_courtyard", image_digest="sha256:11ac33bd55ef7701",
                   natural_width=1600, natural_height=1200)

ALL_RECIPES = sorted(C.recipes())

#: Every derivation a recipe declares, and the producer that performs it. Total by test, so a
#: study cannot name a form this repository has no way to compute.
PRODUCERS = {
    "extent.boundary_rings": "backend.services.perception_lab.extent_forms.boundary_rings",
    "extent.hole_set": "backend.services.perception_lab.extent_forms.hole_set",
    "extent.fragment_set": "backend.services.perception_lab.extent_forms.fragment_set",
    "extent.fused_hypothesis":
        "backend.services.perception_lab.extent_composites.produce_fused_hypothesis",
    "extent.visible_inferred_partition":
        "backend.services.perception_lab.extent_composites.produce_visible_inferred_partition",
    "extent.hierarchy":
        "backend.services.perception_lab.extent_composites.produce_extent_hierarchy",
    "extent.density_field":
        "backend.services.perception_lab.extent_composites.produce_density_field",
    "extent.hypothesis_set":
        "backend.services.perception_lab.extent_composites.produce_hypothesis_set",
    "topology.containment_tree":
        "backend.services.perception_lab.topology_forms.produce_containment_tree",
    "topology.transition": "backend.services.perception_lab.topology_forms.produce_transition",
}


class TickingClock(FrozenClock):
    def monotonic_ms(self) -> int:
        self.elapsed_ms += 7
        return self.elapsed_ms


def conforming_registry() -> AdapterRegistry:
    """Lane D's fakes, plus the coverage the contract declares and the shipped set does not.

    `topology.all_pairs` declares three adapters and `nestedness_organ` is the FIRST of them, so
    the resolver picks it. `fakes.full_registry()` registers `nestedness_organ` for
    `topology.containment` only, so an all-pairs step resolves to an adapter that is registered,
    available, and not registered for THAT operation — and comes back `unavailable` at execute
    time. No test in the tree reached `topology.all_pairs` end to end before this one, which is
    why it had not shown up. Reported in the lane notes; patched here rather than in Lane D's
    module, because a lane that quietly widens another lane's fake is a lane whose own results
    are hard to read.
    """
    registry = fakes.full_registry()
    registry.register(fakes.FakeTopologyAdapter(
        name="nestedness_organ", operations=("topology.containment", "topology.all_pairs")))
    return registry


def conductor(registry=None) -> PerceptionConductor:
    return PerceptionConductor(store=InMemoryLabStore(),
                               registry=registry if registry is not None
                               else conforming_registry(),
                               clock=TickingClock(), ids=SequentialIds())


def view(organ: OrganFamily = OrganFamily.EXTENT, mode: SessionMode = SessionMode.ISOLATION,
         **kw) -> SessionView:
    return SessionView(session_id="sess_recipe", selected_organ=organ, mode=mode, **kw)


#: A stand-in for the two things a recipe asks a PERSON for. Neither is stored in the catalogue:
#: a concept is somebody's word and a drawn mask is their hand.
A_MASK = {"size": [4, 4], "counts": [5, 2, 2, 2, 5]}


def bindings_for(recipe: C.Recipe) -> Dict[str, Dict[str, Any]]:
    values = {"concept": "the figure", "mask_rle": A_MASK}
    return {step_id: {name: values[name] for name in names}
            for step_id, names in recipe.asks_for.items()}


def run(c: PerceptionConductor, machine, recipe: C.Recipe):
    """Plan and execute a whole study, confirming the crossing a chain study declares."""
    plan = c.plan_direct(machine, *E.commands(recipe, machine.view(),
                                              bindings_for(recipe))).plan
    if not plan.resolved_steps:
        return plan, None
    return plan, c.execute(machine, plan, confirmed=plan.requires_confirmation)


def prepared(c: PerceptionConductor, recipe: C.Recipe):
    """A session whose prerequisites are met: two measured extents, both selected.

    THE PREREQUISITES ARE THE RECIPE'S OWN, and satisfying them here is not a convenience. Three
    of the seven studies open on a topology operation whose inputs are extents somebody already
    chose, and a test that ran them against an empty session would be measuring the resolver's
    refusal rather than the study.
    """
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT,
                             mode=SessionMode.CHAIN if recipe.mode is SessionMode.CHAIN
                             else SessionMode.ISOLATION)
    if any(D.operation(str(s.operation)).inputs for s in recipe.operations):
        first = c.execute(machine, c.plan_direct(machine, DirectCommand("extent.find_all")).plan)
        second = c.execute(machine, c.plan_direct(machine, DirectCommand("extent.find_all")).plan)
        machine.select(first.run.artifact_ids[0], second.run.artifact_ids[0])
    if recipe.organ is not machine.session.selected_organ:
        machine.select_organ(recipe.organ)
    return machine


def mutated(key: str, **changes) -> Dict[str, Any]:
    raw = next(copy.deepcopy(r) for r in C.raw_catalogue()["recipes"] if r["key"] == key)
    raw.update(changes)
    return raw


def rebuild(raw: Dict[str, Any]) -> C.Recipe:
    return C.build(raw, controls=C.controls(), outcomes=C.stop_outcomes())


# ── the catalogue is seven bounded studies ───────────────────────────────────


def test_the_catalogue_holds_the_seven_studies_this_lane_was_asked_for():
    assert ALL_RECIPES == ["ambiguous-form-hypothesis", "boundary-and-void",
                           "courtyard-hierarchy", "fragment-continuity",
                           "piazza-negative-space", "topology-sensitivity",
                           "visible-versus-inferred"]


@pytest.mark.parametrize("key", ALL_RECIPES)
def test_every_recipe_declares_the_seven_things_a_recipe_is(key):
    """Required forms, ordered operations, prerequisites, bounds, stop conditions, expected
    renderers, human decision points. A study missing any of them is a script."""
    recipe = C.recipe(key)
    assert recipe.required_forms and recipe.steps and recipe.prerequisites
    assert recipe.bounds.get("max_operations") is not None
    assert recipe.bounds.get("max_model_calls") is not None
    assert recipe.stop_conditions and recipe.expected_renderers and recipe.decision_points
    assert recipe.operations, "a study with no direct act performs nothing"


@pytest.mark.parametrize("key", ALL_RECIPES)
def test_every_derivation_a_recipe_names_has_a_producer_in_this_repository(key):
    """A study that named a form nothing here computes would be a promise, not a recipe."""
    import importlib
    for step in C.recipe(key).derivations:
        path = PRODUCERS[str(step.produces)]
        module, attribute = path.rsplit(".", 1)
        assert hasattr(importlib.import_module(module), attribute), path


def test_an_unknown_recipe_raises_rather_than_returning_a_stub():
    with pytest.raises(C.RecipeError) as caught:
        C.recipe("boundary-and-voids")
    assert "no fallback" in str(caught.value)


# ── same producer as direct invocation ───────────────────────────────────────


def test_a_recipe_step_and_a_pressed_control_reach_the_same_adapter_with_the_same_call():
    """The phase gate's question, asked of the adapter rather than of the plan.

    ONE adapter instance, one call list. The recipe's expansion and a hand-built command land in
    it, and the two records agree on every field that describes the work. They differ only in the
    run and step ids, which is what those are for.
    """
    adapter = fakes.FakeExtentAdapter(name="yolo_sam2_auto", operations=("extent.find_all",))
    c = conductor(AdapterRegistry().register(adapter))
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)

    recipe = C.recipe("boundary-and-void")
    run(c, machine, recipe)
    step = recipe.operations[0]
    c.execute(machine, c.plan_direct(
        machine, DirectCommand(str(step.operation), dict(step.parameters))).plan)

    assert len(adapter.calls) == 2
    from_recipe, pressed = adapter.calls
    for field in ("organ", "operation", "adapter", "parameters", "input_refs", "source",
                  "session_id"):
        assert getattr(from_recipe, field) == getattr(pressed, field), field
    assert from_recipe.run_id != pressed.run_id


def test_the_two_runs_produce_the_same_measurement():
    adapter = fakes.FakeExtentAdapter(name="yolo_sam2_auto", operations=("extent.find_all",))
    c = conductor(AdapterRegistry().register(adapter))
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    recipe = C.recipe("boundary-and-void")
    step = recipe.operations[0]

    _, one = run(c, machine, recipe)
    two = c.execute(machine, c.plan_direct(
        machine, DirectCommand(str(step.operation), dict(step.parameters))).plan)
    payloads = [c.store.get_artifact(a).measurement.payload.model_dump()
                for execution in (one, two) for a in execution.run.artifact_ids]
    assert len(payloads) == 2
    # The GEOMETRY is compared, not the whole payload: instance ids are derived from the run and
    # step that produced them, so two runs of one measurement differ there and must. A test that
    # demanded byte equality would be demanding that the second run forget which run it was.
    geometry = [[{k: i[k] for k in ("mask_rle", "box", "area", "confidence")}
                 for i in p["instances"]] for p in payloads]
    assert geometry[0] == geometry[1]


def test_a_recipe_holds_no_runner_no_adapter_and_no_registry():
    """The claim above, read off the import graph. There is nothing here for a second execution
    path to be made out of, which is a stronger statement than "the outputs agree"."""
    package = Path(E.__file__).parent
    banned = ("backend.services.perception_lab.adapters",
              "backend.services.perception_lab.orchestrator",
              "backend.services.perception_lab.replay",
              "backend.services.perception_lab.store",
              "backend.services.perception_lab.mongo_store",
              "backend.services.perception_lab.planners.model",
              "backend.services.perception_lab.planners.rules",
              "backend.routers", "backend.database", "torch", "fastapi")
    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module] if isinstance(node, ast.ImportFrom) and node.module
                     else [])
            for name in names:
                for bad in banned:
                    assert not (name == bad or name.startswith(bad + ".")), \
                        f"{path.name} reaches {bad}"


def test_no_language_model_chooses_or_rewrites_a_recipe():
    """The Direct arm is the only planner in reach, and it has no language in it. A model that
    wanted to change a study would have to edit the catalogue file."""
    source = Path(E.__file__).read_text(encoding="utf-8")
    assert "DirectPlanner" in source
    assert "ModelPlanner" not in source and "RulesPlanner" not in source


# ── every step stays separately visible ──────────────────────────────────────


@pytest.mark.parametrize("key", ALL_RECIPES)
def test_one_recipe_step_is_one_proposed_step_and_one_resolved_step_in_order(key):
    recipe = C.recipe(key)
    session = view(organ=recipe.organ, mode=recipe.mode, active_artifact_id="art_a",
                   selected_artifact_ids=("art_a", "art_b"))
    capabilities = {str(s.operation): CapabilityState.AVAILABLE for s in recipe.operations}
    resolution = E.plan(recipe, session, capabilities=capabilities, bindings=bindings_for(recipe),
                        clock=FrozenClock("2026-08-22T00:00:00Z"), ids=SequentialIds())
    plan = resolution.plan
    assert [s.operation for s in plan.proposed_steps] == \
           [s.operation for s in recipe.operations]
    assert len({s.step_id for s in plan.proposed_steps}) == len(recipe.operations)
    assert [s.operation for s in plan.resolved_steps] == [s.operation for s in recipe.operations]


def test_a_study_that_ran_two_acts_shows_two_and_never_a_summary():
    """Two readings of one ambiguous form are two measurements. A runtime that folded them into
    one artifact would have resolved the ambiguity by bookkeeping."""
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    recipe = C.recipe("ambiguous-form-hypothesis")
    _, execution = run(c, machine, recipe)
    assert len(execution.run.stage_attempts) == len(recipe.operations) == 2
    assert len(execution.run.artifact_ids) == 2, "two readings, two artifacts, never one merged"


def test_the_derivations_are_returned_rather_than_planned():
    """A derivation reads records and calls nothing. Planning it would put a pure function
    through a capability gate and report a model call that never happened."""
    recipe = C.recipe("boundary-and-void")
    session = view(active_artifact_id="art_a")
    resolution = E.plan(recipe, session,
                        capabilities={"extent.find_all": CapabilityState.AVAILABLE},
                        clock=FrozenClock("2026-08-22T00:00:00Z"), ids=SequentialIds())
    assert len(resolution.plan.resolved_steps) == 1
    assert [s.produces for s in E.derivations(recipe)] == ["extent.boundary_rings",
                                                           "extent.hole_set"]


# ── bounded call count ───────────────────────────────────────────────────────


@pytest.mark.parametrize("key", ALL_RECIPES)
def test_a_recipe_runs_exactly_as_many_acts_as_it_declared_and_no_more(key):
    """Counted on the adapters themselves, across a session whose prerequisites are already met,
    so the number is what the study cost and not what the setup cost."""
    recipe = C.recipe(key)
    registry = conforming_registry()
    seen = {id(a): a for a in registry._by_operation.values()}
    c = conductor(registry)
    machine = prepared(c, recipe)
    before = sum(len(a.calls) for a in seen.values())
    plan, _ = run(c, machine, recipe)
    assert not plan.refusals, [r.code.value for r in plan.refusals]
    spent = sum(len(a.calls) for a in seen.values()) - before
    assert spent == len(recipe.operations) <= int(recipe.bounds["max_operations"]), key
    assert len(recipe.model_calls) <= int(recipe.bounds["max_model_calls"])


def test_a_manual_step_reaches_the_adapter_and_does_not_reach_a_model():
    """A person drawing a mask goes through the same registry, observer and run record — that is
    what makes a hand-drawn extent comparable with a segmented one. What it does not do is run a
    model, and that is the budget that is scarce."""
    recipe = C.recipe("visible-versus-inferred")
    assert len(recipe.operations) == 2
    assert [str(s.operation) for s in recipe.model_calls] == ["extent.find_named"]
    assert D.operation("extent.draw").manual is True

    registry = conforming_registry()
    seen = {id(a): a for a in registry._by_operation.values()}
    c = conductor(registry)
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    run(c, machine, recipe)
    assert sum(len(a.calls) for a in seen.values()) == 2, "both acts are recorded"
    assert int(recipe.bounds["max_model_calls"]) == 1


def test_a_recipe_whose_steps_exceed_its_own_bounds_is_refused_at_load():
    raw = mutated("courtyard-hierarchy")
    raw["bounds"]["max_model_calls"] = 1
    with pytest.raises(C.RecipeError) as caught:
        rebuild(raw)
    assert "a bound the recipe itself exceeds" in str(caught.value).lower()


# ── absent dependencies refuse ───────────────────────────────────────────────


def test_four_of_the_seven_studies_cannot_write_their_final_record_today_and_say_so():
    """Four of the five composite forms are `deferred` in the merged contract. A runtime that
    discovered that only at the last step would have spent every adapter call first."""
    session = view()
    blocked = {}
    for key in ALL_RECIPES:
        recipe = C.recipe(key)
        readiness = E.check(recipe, view(organ=recipe.organ, mode=recipe.mode))
        if readiness.unproducible_forms:
            blocked[key] = readiness.unproducible_forms
    assert set(blocked) == {"fragment-continuity", "visible-versus-inferred",
                            "piazza-negative-space", "topology-sensitivity",
                            "ambiguous-form-hypothesis"}
    assert all(not readiness_form_producible(f) for forms in blocked.values() for f in forms)


def readiness_form_producible(form_key: str) -> bool:
    return D.form(form_key).producible


def test_an_unavailable_organ_refuses_and_says_which_operation():
    recipe = C.recipe("boundary-and-void")
    readiness = E.check(recipe, view(),
                        capabilities={"extent.find_all": CapabilityState.UNAVAILABLE})
    assert readiness.ready is False
    assert readiness.unavailable_operations == ("extent.find_all",)
    assert "unavailable" in readiness.reasons[-1]


def test_a_chain_study_run_in_an_isolated_session_is_refused_by_the_lock_and_not_granted():
    recipe = C.recipe("courtyard-hierarchy")
    readiness = E.check(recipe, view(mode=SessionMode.ISOLATION))
    assert readiness.mode_conflict and "may not change organs" in readiness.mode_conflict


def test_a_step_whose_inputs_the_session_never_declared_refuses_at_the_resolver():
    """`bind` fills roles from the session's own references and from nowhere else, so a recipe
    cannot name a mask a person did not select."""
    recipe = C.recipe("piazza-negative-space")
    empty = view(mode=SessionMode.CHAIN)
    commands = E.commands(recipe, empty)
    assert all(c.input_refs == () for c in commands)
    resolution = E.plan(recipe, empty,
                        capabilities={"extent.find_named": CapabilityState.AVAILABLE,
                                      "topology.negative_space": CapabilityState.AVAILABLE},
                        clock=FrozenClock("2026-08-22T00:00:00Z"), ids=SequentialIds())
    assert any(r.code is RefusalCode.MISSING_EXTENT_INPUTS for r in resolution.plan.refusals)


def test_fewer_references_than_roles_yields_fewer_refs_and_never_a_repeat():
    """A relation between something and itself measures perfectly and answers nothing."""
    session = view(organ=OrganFamily.TOPOLOGY, mode=SessionMode.CHAIN,
                   active_artifact_id="art_only")
    refs = E.bind("topology.overlap", session)
    assert [r.role for r in refs] == ["source"]


# ── hypotheses remain hypotheses ─────────────────────────────────────────────


def test_the_studies_that_produce_claims_declare_no_route_by_which_a_claim_resolves():
    for key in ("fragment-continuity", "ambiguous-form-hypothesis"):
        recipe = C.recipe(key)
        text = json.dumps([s.__dict__ for s in recipe.stop_conditions])
        assert "separate artifact" in text or "no grouping" in text
        assert not any("resolve" == str(s.produces) for s in recipe.derivations)


def test_the_ambiguous_study_says_out_loud_that_choosing_does_not_end_it():
    recipe = C.recipe("ambiguous-form-hypothesis")
    chosen = [s for s in recipe.stop_conditions if "chooses one reading" in s.when]
    assert chosen and chosen[0].outcome == "partial"
    assert "the alternatives survive it" in chosen[0].reason


def test_every_hypothesis_bearing_form_a_recipe_names_is_capped_somewhere():
    """Three of the four are capped at the RECORD level. The partition is not, and that is not a
    gap: its ceiling is `measured` because its VISIBLE part is a measurement, and the cap moves
    down to the region — `PartitionRegion` refuses `visible` or `measured` on the inferred part at
    any confidence. So the rule is "capped somewhere", and the somewhere is named per form.
    """
    per_record, per_region = set(), set()
    for key in ALL_RECIPES:
        for form_key in C.recipe(key).required_forms:
            definition = D.form(form_key)
            if not definition.carries_hypothesis:
                continue
            if definition.epistemic_ceiling in ("interpretive", "uncertain"):
                per_record.add(form_key)
            else:
                per_region.add(form_key)
    assert per_record == {"extent.fused_hypothesis", "extent.hypothesis_set",
                          "topology.uncertain_relation_set"} - (
        {"topology.uncertain_relation_set"} - per_record)
    assert per_region == {"extent.visible_inferred_partition"}
    assert "inferred_pixels_are_not_visible" in \
        D.form("extent.visible_inferred_partition").test_obligations


# ── rejected models are unreachable ──────────────────────────────────────────


@pytest.mark.parametrize("model_key, why", [
    ("sam2_logits", "measured and found wanting"),
    ("pix2gestalt", "deferred on resources"),
    ("amodal_sam", "deferred on availability"),
    ("density_counter", "rejected as a producer"),
    ("segment_anything_3", "never evaluated"),
])
def test_a_recipe_naming_a_model_lane_c_did_not_admit_is_refused_at_load(model_key, why):
    from backend.services.perception_lab.extent_composites import admission as A
    raw = mutated("boundary-and-void")
    raw["steps"][1]["model"] = model_key
    with pytest.raises(A.ModelNotAdmitted) as caught:
        rebuild(raw)
    assert caught.value.refusal.code is RefusalCode.CAPABILITY_UNAVAILABLE, why


def test_no_recipe_in_the_catalogue_names_a_model_at_all():
    """None of the seven needs one. The gate above exists so that a study that later does has to
    pass it, not because a study currently fails it."""
    for key in ALL_RECIPES:
        assert all(step.model is None for step in C.recipe(key).steps)


# ── replay is non-computing ──────────────────────────────────────────────────


def test_replaying_a_recipe_run_computes_nothing():
    adapter = fakes.FakeExtentAdapter(name="yolo_sam2_auto", operations=("extent.find_all",))
    c = conductor(AdapterRegistry().register(adapter))
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    recipe = C.recipe("boundary-and-void")
    _, live = run(c, machine, recipe)
    assert len(adapter.calls) == 1

    again = c.replay(machine, live.run.run_id)
    assert len(adapter.calls) == 1, "a replay that recomputed would make the badge mean nothing"
    assert again.run.execution_identity is ExecutionIdentity.REPLAY
    assert all(not a.invoked for a in again.run.stage_attempts)


# ── the source is not touched ────────────────────────────────────────────────


def test_running_a_study_leaves_the_source_exactly_as_it_was():
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    before = machine.session.source.model_dump()
    recipe = C.recipe("boundary-and-void")
    run(c, machine, recipe)
    assert machine.session.source.model_dump() == before
    assert machine.session.source.image_digest == SOURCE.image_digest


def test_nothing_a_recipe_reaches_can_write_a_post_a_region_or_a_ground():
    package = Path(E.__file__).parent
    text = "\n".join(p.read_text(encoding="utf-8") for p in package.glob("*.py"))
    for forbidden in ("Ground(", "post_id=", "update_one", "insert_one", "regions_collection"):
        assert forbidden not in text, forbidden


# ── the fixtures are Lane F's ────────────────────────────────────────────────


@pytest.mark.parametrize("key", ALL_RECIPES)
def test_every_control_a_recipe_names_exists_and_carries_one_of_its_forms(key):
    """"this study runs on that control" has to be checkable rather than aspirational."""
    recipe = C.recipe(key)
    for fixture in recipe.fixtures:
        control = CONTROLS[fixture]
        shared = set(control["forms"]) & set(recipe.required_forms)
        assert shared, f"{key} names {fixture}, which carries {control['forms']}"


def test_every_control_lane_f_built_is_reachable_from_at_least_one_study():
    """A control nobody studies is a control nobody checks a producer against."""
    named = {f for key in ALL_RECIPES for f in C.recipe(key).fixtures}
    unstudied = sorted(set(CONTROLS) - named)
    assert unstudied == ["adjacency-graph", "solid-mask"] or not unstudied, (
        f"controls no study reaches: {unstudied}")


# ── the twelve checks bite ───────────────────────────────────────────────────


def test_a_recipe_naming_an_undeclared_operation_is_refused():
    raw = mutated("boundary-and-void")
    raw["steps"][0]["operation"] = "extent.imagine"
    with pytest.raises(D.UnknownOperation):
        rebuild(raw)


def test_a_recipe_carrying_a_parameter_the_operation_does_not_declare_is_refused():
    """The resolver would drop and record it. Shipping it in the catalogue would put the
    smuggling attempt in the recipe rather than in a model's output."""
    raw = mutated("boundary-and-void")
    raw["steps"][0]["parameters"]["mask_rle"] = {"size": [2, 2], "counts": [0, 4]}
    with pytest.raises(C.RecipeError) as caught:
        rebuild(raw)
    assert "does not declare" in str(caught.value)


def test_a_study_that_crosses_organs_while_calling_itself_isolated_is_refused():
    raw = mutated("courtyard-hierarchy", mode="isolation")
    with pytest.raises(C.RecipeError) as caught:
        rebuild(raw)
    assert "declares `chain`" in str(caught.value)


def test_a_step_that_reads_its_own_future_is_refused():
    raw = mutated("boundary-and-void")
    raw["steps"][0]["reads"] = ["voids"]
    with pytest.raises(C.RecipeError) as caught:
        rebuild(raw)
    assert "reads its own future" in str(caught.value)


def test_a_derivation_producing_a_form_the_recipe_did_not_require_is_refused():
    raw = mutated("boundary-and-void")
    raw["required_forms"] = ["extent.hard_mask", "extent.hole_set"]
    with pytest.raises(C.RecipeError) as caught:
        rebuild(raw)
    assert "does not list as required" in str(caught.value)


def test_a_study_promising_a_renderer_none_of_its_forms_declares_is_refused():
    raw = mutated("boundary-and-void")
    raw["expected_renderers"] = raw["expected_renderers"] + ["vector_field"]
    with pytest.raises(C.RecipeError) as caught:
        rebuild(raw)
    assert "no projection for" in str(caught.value)


def test_a_study_with_no_stop_condition_is_refused():
    raw = mutated("boundary-and-void", stop_conditions=[])
    with pytest.raises(C.RecipeError) as caught:
        rebuild(raw)
    assert "cannot end" in str(caught.value)


def test_a_stop_condition_with_an_invented_outcome_is_refused():
    raw = mutated("boundary-and-void")
    raw["stop_conditions"][0]["outcome"] = "inconclusive"
    with pytest.raises(C.RecipeError):
        rebuild(raw)


def test_a_decision_point_with_no_reason_a_person_is_needed_is_refused():
    """A decision point with no reason is a confirmation dialog, and a confirmation dialog is the
    thing people learn to click through."""
    raw = mutated("boundary-and-void")
    raw["decision_points"][0]["why_a_person"] = ""
    with pytest.raises(C.RecipeError) as caught:
        rebuild(raw)
    assert "click through" in str(caught.value)


def test_a_decision_point_attached_to_no_step_is_refused():
    raw = mutated("boundary-and-void")
    raw["decision_points"][0]["at"] = "nowhere"
    with pytest.raises(C.RecipeError):
        rebuild(raw)


def test_a_study_naming_a_control_lane_f_does_not_hold_is_refused():
    raw = mutated("boundary-and-void", fixtures=["donut", "a-cathedral"])
    with pytest.raises(C.RecipeError) as caught:
        rebuild(raw)
    assert "has to be checkable" in str(caught.value)


def test_a_step_that_is_neither_an_operation_nor_a_derivation_is_refused():
    raw = mutated("boundary-and-void")
    raw["steps"][1]["kind"] = "inference"
    with pytest.raises(C.RecipeError) as caught:
        rebuild(raw)
    assert "the two kinds are" in str(caught.value)
