"""
CIRCUIT-001 ORCH-001 — the Director foundation, exercised entirely on stubs.

No model, no GPU, no network, no database. Every actuator here is a StubActuator, which is
the property that lets this suite run unattended and in CI.

Covers the six things the gate asks for: plan construction, dependency satisfaction and
refusal, workflow replay, chain provenance, refusal propagation — plus the vocabulary pin
that keeps the capability map honest against the live producer registry.
"""
from __future__ import annotations

import pytest

from backend.services.director import capabilities as caps
from backend.services.director import workflows as wf
from backend.services.director.capabilities import Requirement, Resource
from backend.services.director.execution import (EMPTY, OK, SKIPPED, UNAVAILABLE,
                                                 SKIP_INPUT_NEVER_ARRIVED,
                                                 SKIP_UPSTREAM_UNAVAILABLE,
                                                 StubActuator, execute, stub_registry)
from backend.services.director.memory import build_memory
from backend.services.director.plan import (REFUSED_MISSING_INPUT, REFUSED_MISSING_PARAM,
                                            REFUSED_UNKNOWN_ACTUATOR, Step, resolve)
from backend.services.director.planner import Director, RuleBasedPlanner, match_intent


# ── fixtures ─────────────────────────────────────────────────────────────────

def bare_memory(**kw):
    """An image and nothing else — the hardest case for a planner."""
    return build_memory(image_ref="img_1", post_id="post_1", **kw)


def rich_memory(*, regions=2, marks=3, **kw):
    return build_memory(
        image_ref="img_1", post_id="post_1",
        region_ids=tuple(f"reg_{i}" for i in range(regions)),
        mark_ids=tuple(f"mark_{i}" for i in range(marks)),
        **kw)


def step(actuator, sid=None, **params):
    return Step(actuator=actuator, params=params, id=sid or f"s:{actuator}")


# ── 1. the capability map ────────────────────────────────────────────────────

class TestCapabilityMap:

    def test_field_producer_names_match_the_live_registry(self):
        """The map must not drift from the runtime it describes.

        This is the pin that makes the whole table trustworthy: if a producer is renamed in
        `posts.py` and not here, the planner would emit a name the endpoint cannot dispatch,
        and nothing else in this suite would notice.
        """
        from backend.routers.posts import _FIELD_PRODUCERS
        for name in caps.FIELD_PRODUCER_ACTUATORS:
            assert name in _FIELD_PRODUCERS, f"'{name}' is not a live field producer"
            assert name in caps.ACTUATORS

    def test_every_actuator_requires_something(self):
        # An actuator with no requirements can fire on an empty packet — that is exactly the
        # blind call this layer exists to prevent.
        for name, a in caps.ACTUATORS.items():
            assert a.requires, f"'{name}' declares no inputs"

    def test_readings_never_produce_marks(self):
        """P8-D's distinction, enforced at Layer 3.

        If a reading produced MARK, a mark-hungry step could be satisfied by a sentence —
        the exact laundering P8-D was built to prevent, reintroduced by the planner.
        """
        for name in ("presence_check", "enumerate", "semantic_read"):
            produces = caps.ACTUATORS[name].produces
            assert Resource.MARK not in produces
            assert Resource.READING in produces

    def test_connect_marks_needs_two(self):
        req = [r for r in caps.ACTUATORS["connect_marks"].requires if r.kind is Resource.MARK]
        assert req[0].min_count == 2, "a relation between a thing and itself is not a relation"

    def test_unknown_actuator_returns_none_not_a_default(self):
        assert caps.get("brush_the_vibes") is None

    def test_producers_of_finds_the_finders(self):
        assert "find_parts" in caps.producers_of(Resource.REGION)
        assert "compose_percept" in caps.producers_of(Resource.PERCEPT)


# ── 2. working memory ────────────────────────────────────────────────────────

class TestWorkingMemory:

    def test_counts_derive_from_contents(self):
        m = rich_memory(regions=2, marks=3)
        a = m.available()
        assert a[Resource.IMAGE] == 1
        assert a[Resource.REGION] == 2
        assert a[Resource.MARK] == 3

    def test_blank_phrase_does_not_satisfy_a_phrase_requirement(self):
        """A whitespace phrase is not a phrase — otherwise P8-B's fabrication returns."""
        assert bare_memory(phrase="   ").available()[Resource.PHRASE] == 0
        assert bare_memory(phrase="a cross").available()[Resource.PHRASE] == 1

    def test_evolve_returns_a_new_packet_and_leaves_the_old_one_intact(self):
        m = bare_memory()
        m2 = m.evolve((Resource.REGION,), step_id="s1")
        assert m.available()[Resource.REGION] == 0      # the snapshot still tells the truth
        assert m2.available()[Resource.REGION] == 1

    def test_projected_ids_cannot_be_mistaken_for_records(self):
        m = bare_memory().evolve((Resource.MARK,), step_id="s1")
        assert "#" in m.mark_ids[0]

    def test_readings_add_nothing_to_the_evidence_layer(self):
        m = bare_memory().evolve((Resource.READING,), step_id="s1")
        assert m.mark_ids == () and m.region_ids == ()

    def test_unreadable_is_distinct_from_empty(self):
        """'No marks' and 'could not read the marks' must never collapse."""
        m = bare_memory().with_unreadable("marks: db timeout")
        assert m.available()[Resource.MARK] == 0
        assert m.unreadable == ("marks: db timeout",)
        assert "marks: db timeout" in m.summary()["unreadable"]

    def test_constraints_travel_as_data(self):
        m = bare_memory()
        assert m.constraints["no_fabrication_on_refusal"] is True
        assert m.constraints["image_only"] is True


# ── 3. plan construction + dependency satisfaction ───────────────────────────

class TestPlanConstruction:

    def test_a_satisfiable_chain_keeps_its_requested_order(self):
        """Requested order carries intent; the resolver must not 'improve' it."""
        plan = resolve([step("light_field", "a"), step("shadow_field", "b")],
                       bare_memory(), intention="trace the light")
        assert [s.id for s in plan.steps] == ["a", "b"]
        assert plan.reordered is False
        assert plan.complete is True

    def test_a_step_needing_a_region_is_moved_after_the_step_producing_one(self):
        # Badly sequenced, not impossible — the resolver repairs it.
        plan = resolve([step("material_field", "mat"), step("find_parts", "find")],
                       bare_memory())
        assert [s.id for s in plan.steps] == ["find", "mat"]
        assert plan.reordered is True
        assert plan.refused == ()

    def test_a_step_whose_input_nothing_provides_is_refused_not_reordered(self):
        plan = resolve([step("material_field", "mat")], bare_memory())
        assert plan.steps == ()
        assert len(plan.refused) == 1
        assert plan.refused[0].reason == REFUSED_MISSING_INPUT
        assert "region" in plan.refused[0].detail

    def test_the_rest_of_the_plan_survives_one_refusal(self):
        """A refusal is not a chain abort — everything runnable still runs."""
        plan = resolve([step("rhythm", "r"), step("compose_percept", "c", draft_text="x")],
                       bare_memory())
        # rhythm produces a MARK, so compose_percept becomes satisfiable after it.
        assert [s.id for s in plan.steps] == ["r", "c"]
        assert plan.refused == ()

    def test_connect_marks_refused_on_a_single_mark(self):
        plan = resolve([step("connect_marks", "c", relation_role="motif_echo")],
                       rich_memory(marks=1))
        assert plan.steps == ()
        assert "2× mark" in plan.refused[0].detail

    def test_connect_marks_runs_on_two(self):
        plan = resolve([step("connect_marks", "c", relation_role="motif_echo")],
                       rich_memory(marks=2))
        assert len(plan.steps) == 1

    def test_an_unknown_actuator_is_refused_by_name(self):
        plan = resolve([step("enhance_the_aura", "x")], rich_memory())
        assert plan.refused[0].reason == REFUSED_UNKNOWN_ACTUATOR
        assert plan.steps == ()

    def test_an_open_vocabulary_actuator_without_a_phrase_is_refused(self):
        """The empty-query fabrication, refused before dispatch."""
        plan = resolve([step("presence_check", "p")], bare_memory())
        assert plan.refused[0].reason == REFUSED_MISSING_PARAM
        assert "phrase" in plan.refused[0].detail

    def test_a_phrase_on_the_packet_satisfies_it(self):
        plan = resolve([step("presence_check", "p")], bare_memory(phrase="a cross"))
        assert len(plan.steps) == 1

    def test_a_phrase_on_the_step_satisfies_it(self):
        plan = resolve([step("presence_check", "p", phrase="a cross")], bare_memory())
        assert len(plan.steps) == 1

    def test_a_reading_cannot_satisfy_a_mark_requirement(self):
        """The laundering check, end to end through the resolver."""
        plan = resolve([step("presence_check", "p", phrase="a cross"),
                        step("compose_percept", "c", draft_text="x")],
                       bare_memory())
        assert [s.id for s in plan.steps] == ["p"]
        assert plan.refused[0].step.id == "c"

    def test_refusals_are_reported_in_requested_order(self):
        plan = resolve([step("material_field", "first"), step("nonsense", "second")],
                       bare_memory())
        assert [r.step.id for r in plan.refused] == ["first", "second"]

    def test_resolution_terminates_on_a_fully_unsatisfiable_plan(self):
        plan = resolve([step("connect_marks", "a", relation_role="x"),
                        step("compose_percept", "b", draft_text="y")], bare_memory())
        assert plan.steps == ()
        assert len(plan.refused) == 2

    def test_plan_serialises_with_its_refusals(self):
        d = resolve([step("rhythm", "r"), step("material_field", "m")],
                    bare_memory()).to_dict()
        assert d["complete"] is False
        assert len(d["steps"]) == 1 and len(d["refused"]) == 1


# ── 4. the Director / intention matching ─────────────────────────────────────

class TestDirector:

    def test_light_intention_matches_the_light_chain(self):
        assert match_intent("trace the light").key == "trace_light"

    def test_counting_beats_presence_on_a_shared_word(self):
        """'how many' must not route to the presence check on an incidental 'any'."""
        assert match_intent("how many figures are there").key == "count"

    def test_an_unrecognised_intention_refuses_rather_than_guessing(self):
        assert match_intent("make it more beautiful") is None
        plan = Director().plan("make it more beautiful", rich_memory())
        assert plan.steps == ()
        assert plan.notes and "no way of looking matches" in plan.notes[0]

    def test_the_director_plans_a_real_chain(self):
        plan = Director().plan("trace the light", rich_memory())
        assert [s.actuator for s in plan.steps] == ["light_field", "shadow_field", "semantic_read"]
        assert plan.workflow == "trace_light"

    def test_the_same_chain_partially_refuses_on_a_bare_image(self):
        """semantic_read needs a region; on a bare image it is honestly dropped."""
        plan = Director().plan("trace the light", bare_memory())
        assert [s.actuator for s in plan.steps] == ["light_field", "shadow_field"]
        assert plan.refused[0].step.actuator == "semantic_read"
        assert plan.complete is False

    def test_material_intention_orders_the_finder_first(self):
        plan = Director().plan("what is this made of", bare_memory())
        assert [s.actuator for s in plan.steps][0] == "find_parts"

    def test_every_step_the_director_emits_carries_an_id(self):
        plan = Director().plan("weigh the composition", rich_memory())
        assert all(s.id for s in plan.steps)

    def test_a_custom_planner_slots_in_at_the_seam(self):
        """The Groq seam, proven with a fake: any planner, same guard."""
        class FakePlanner:
            name = "fake_llm"

            def propose(self, intention, memory):
                # A model doing exactly what models do: a plausible hallucination plus a
                # real step it has no inputs for, with no ids.
                return [Step(actuator="summon_the_muse"),
                        Step(actuator="connect_marks", params={"relation_role": "x"}),
                        Step(actuator="rhythm")]

        plan = Director(FakePlanner()).plan("anything", bare_memory())
        assert plan.planner == "fake_llm"
        assert [s.actuator for s in plan.steps] == ["rhythm"]
        reasons = {r.reason for r in plan.refused}
        assert REFUSED_UNKNOWN_ACTUATOR in reasons      # the hallucination
        assert REFUSED_MISSING_INPUT in reasons         # the unsatisfiable real step
        assert all(s.id for s in plan.steps)            # ids stamped despite the planner


# ── 5. workflows: inspectable + replayable ───────────────────────────────────

class TestWorkflows:

    def test_three_are_seeded(self):
        assert set(wf.names()) == {"trace_light", "motif_and_echoes", "weigh_composition"}

    def test_every_seeded_step_names_a_known_actuator(self):
        for w in wf.REGISTRY.values():
            for row in w.describe()["steps"]:
                assert row["known"], f"{w.name} names unknown actuator {row['actuator']}"

    def test_describe_does_not_run_anything(self):
        d = wf.get("trace_light").describe()
        assert d["why"]
        assert [r["actuator"] for r in d["steps"]] == ["light_field", "shadow_field", "semantic_read"]
        assert d["steps"][2]["requires"] == ["image", "region"]

    def test_replay_is_byte_identical_on_the_same_memory(self):
        m = rich_memory()
        assert wf.get("weigh_composition").plan_for(m).to_dict() == \
               wf.get("weigh_composition").plan_for(m).to_dict()

    def test_step_ids_are_deterministic_and_carry_no_clock(self):
        ids = [s.id for s in wf.get("trace_light").to_steps()]
        assert ids == ["trace_light:0:light_field", "trace_light:1:shadow_field",
                       "trace_light:2:semantic_read"]

    def test_replay_adapts_honestly_to_a_poorer_memory(self):
        """Same workflow, less evidence: fewer steps and a stated refusal, never a fake run."""
        rich = wf.get("weigh_composition").plan_for(rich_memory())
        bare = wf.get("weigh_composition").plan_for(bare_memory())
        assert rich.complete is True
        assert bare.complete is False
        assert "negative_space" in [r.step.actuator for r in bare.refused]

    def test_motif_workflow_needs_the_curators_phrase(self):
        assert wf.get("motif_and_echoes").plan_for(rich_memory()).refused[0].reason == \
               REFUSED_MISSING_PARAM
        assert wf.get("motif_and_echoes").plan_for(
            rich_memory(phrase="the folded cloth")).complete is True

    def test_register_refuses_a_silent_overwrite(self):
        with pytest.raises(ValueError, match="already exists"):
            wf.register(wf.get("trace_light"))

    def test_register_refuses_unknown_actuators(self):
        bad = wf.Workflow(name="bad", title="t", why="w", steps=(("vibe_check", {}),))
        with pytest.raises(ValueError, match="unknown actuators"):
            wf.register(bad)

    def test_a_new_workflow_registers_and_plans(self):
        added = wf.Workflow(name="tmp_depth", title="Depth", why="test",
                            steps=(("background_recession", {}), ("atmosphere_field", {})))
        try:
            wf.register(added)
            assert wf.get("tmp_depth").plan_for(bare_memory()).complete is True
        finally:
            wf.REGISTRY.pop("tmp_depth", None)

    def test_the_planner_and_the_workflow_agree(self):
        """A table row and the chain it summons must not drift apart."""
        m = rich_memory()
        assert [s.actuator for s in Director().plan("trace the light", m).steps] == \
               [s.actuator for s in wf.get("trace_light").plan_for(m).steps]


# ── 6. execution on stubs ────────────────────────────────────────────────────

class TestExecution:

    def test_a_clean_chain_runs_every_step(self):
        plan = Director().plan("trace the light", rich_memory())
        result = execute(plan, rich_memory(), stub_registry())
        assert [r.status for r in result.provenance.lineage] == [OK, OK, OK]
        assert result.complete is True

    def test_every_step_is_handed_the_packet(self):
        """The 'never fires blind' rule, observed rather than asserted."""
        stubs = stub_registry()
        plan = Director().plan("trace the light", rich_memory())
        execute(plan, rich_memory(), stubs)
        seen = stubs["light_field"].memories[0]
        assert seen.image_ref == "img_1"
        assert seen.available()[Resource.REGION] == 2

    def test_later_steps_see_what_earlier_steps_produced(self):
        stubs = stub_registry()
        plan = resolve([step("find_parts", "f"), step("material_field", "m")], bare_memory())
        execute(plan, bare_memory(), stubs)
        assert stubs["material_field"].memories[0].available()[Resource.REGION] == 1

    def test_produced_evidence_lands_in_the_final_memory(self):
        plan = resolve([step("find_parts", "f")], bare_memory())
        result = execute(plan, bare_memory(), stub_registry())
        assert result.memory.available()[Resource.REGION] == 1


class TestRefusalPropagation:

    def test_an_unavailable_step_does_not_stop_an_independent_one(self):
        plan = Director().plan("trace the light", rich_memory())
        result = execute(plan, rich_memory(), stub_registry(unavailable=["light_field"]))
        by_id = {r.actuator: r for r in result.provenance.lineage}
        assert by_id["light_field"].status == UNAVAILABLE
        assert by_id["shadow_field"].status == OK      # independent, still runs

    def test_a_dependent_step_is_skipped_not_run_on_stale_evidence(self):
        """The core of the gate: no fabricating past a hole."""
        stubs = stub_registry(unavailable=["find_parts"])
        plan = resolve([step("find_parts", "f"), step("material_field", "m")], bare_memory())
        result = execute(plan, bare_memory(), stubs)
        rec = result.provenance.lineage[1]
        assert rec.status == SKIPPED
        assert rec.skip_reason == SKIP_UPSTREAM_UNAVAILABLE
        assert rec.blocked_by == ("f",)
        assert stubs["material_field"].calls == []     # it was never even called

    def test_the_skip_names_every_step_that_would_have_supplied_the_input(self):
        """A skip caused by a skip must report the failure, not just the symptom.

        WIRE-002 made `find_parts` produce MARK as well as REGION, so when it goes down BOTH it
        and the step after it are steps that would have supplied compose_percept's mark — and
        naming both is strictly better than naming only the nearest one, which reads as though
        the material_field step were the origin of the problem."""
        stubs = stub_registry(unavailable=["find_parts"])
        plan = resolve([step("find_parts", "f"), step("material_field", "m"),
                        step("compose_percept", "c", draft_text="x")], bare_memory())
        result = execute(plan, bare_memory(), stubs)
        statuses = [r.status for r in result.provenance.lineage]
        assert statuses == [UNAVAILABLE, SKIPPED, SKIPPED]
        blocked = result.provenance.lineage[2].blocked_by
        assert "f" in blocked and "m" in blocked          # the root AND the intermediate

    def test_an_empty_result_is_not_an_error_but_still_blocks_dependents(self):
        """EMPTY is an honest answer AND a real gap. Both facts survive."""
        stubs = stub_registry(empty=["find_parts"])
        plan = resolve([step("find_parts", "f"), step("material_field", "m")], bare_memory())
        result = execute(plan, bare_memory(), stubs)
        assert result.provenance.lineage[0].status == EMPTY
        assert result.provenance.lineage[1].status == SKIPPED
        assert stubs["material_field"].calls == []

    def test_a_missing_runner_is_unavailable_not_a_crash(self):
        plan = resolve([step("rhythm", "r")], bare_memory())
        result = execute(plan, bare_memory(), {})       # nothing registered
        assert result.provenance.lineage[0].status == UNAVAILABLE

    def test_nothing_is_produced_by_a_failed_chain(self):
        stubs = stub_registry(unavailable=["find_parts"])
        plan = resolve([step("find_parts", "f"), step("material_field", "m")], bare_memory())
        result = execute(plan, bare_memory(), stubs)
        assert result.memory.available()[Resource.REGION] == 0
        assert result.memory.available()[Resource.MARK] == 0


class TestChainProvenance:

    def test_lineage_traces_every_step_of_a_five_step_chain(self):
        """The gate's own example: a result resting on five actuators traces all five."""
        steps = [step("find_parts", "s0"), step("material_field", "s1"),
                 step("rhythm", "s2"), step("pressure_zone", "s3"),
                 step("compose_percept", "s4", draft_text="x")]
        plan = resolve(steps, bare_memory(), intention="read it fully")
        result = execute(plan, bare_memory(), stub_registry(), chain_id="ch_1")
        prov = result.provenance
        assert len(prov.lineage) == 5
        assert [r.actuator for r in prov.lineage] == \
               ["find_parts", "material_field", "rhythm", "pressure_zone", "compose_percept"]
        assert all(r.model for r in prov.lineage)
        assert prov.complete is True

    def test_each_link_records_the_inputs_it_actually_saw(self):
        steps = [step("find_parts", "s0"), step("material_field", "s1")]
        result = execute(resolve(steps, bare_memory()), bare_memory(), stub_registry())
        assert result.provenance.lineage[0].inputs_used["region"] == 0
        assert result.provenance.lineage[1].inputs_used["region"] == 1

    def test_weakest_link_is_the_minimum_not_the_average(self):
        stubs = stub_registry()
        stubs["light_field"] = StubActuator("light_field", confidence=0.31)
        stubs["shadow_field"] = StubActuator("shadow_field", confidence=0.95)
        plan = Director().plan("trace the light", rich_memory())
        result = execute(plan, rich_memory(), stubs)
        assert result.provenance.weakest_link == pytest.approx(0.31)

    def test_no_confidence_anywhere_yields_none_not_zero(self):
        """An invented number is the one fabrication this module exists to prevent."""
        stubs = {n: StubActuator(n, confidence=None) for n in caps.known()}
        plan = resolve([step("rhythm", "r")], bare_memory())
        assert execute(plan, bare_memory(), stubs).provenance.weakest_link is None

    def test_a_chain_with_a_hole_is_not_complete(self):
        plan = Director().plan("trace the light", rich_memory())
        result = execute(plan, rich_memory(), stub_registry(unavailable=["shadow_field"]))
        assert result.complete is False

    def test_an_empty_step_costs_completeness(self):
        """A percept resting on an empty field rests on less than it appears to."""
        plan = Director().plan("trace the light", rich_memory())
        result = execute(plan, rich_memory(), stub_registry(empty=["light_field"]))
        assert result.complete is False

    def test_gaps_name_everything_the_chain_could_not_do(self):
        plan = Director().plan("trace the light", bare_memory())   # semantic_read refused
        result = execute(plan, bare_memory(), stub_registry(unavailable=["shadow_field"]))
        gaps = {g["actuator"]: g["status"] for g in result.provenance.gaps()}
        assert gaps["shadow_field"] == UNAVAILABLE
        assert gaps["semantic_read"] == "refused"

    def test_plan_time_refusals_reach_the_chain_receipt(self):
        """A refusal decided before dispatch must not vanish from the result."""
        plan = Director().plan("trace the light", bare_memory())
        d = execute(plan, bare_memory(), stub_registry()).provenance.to_dict()
        assert d["steps_refused"] == 1
        assert d["steps_total"] == 3
        assert d["complete"] is False

    def test_the_receipt_serialises_whole(self):
        plan = Director().plan("weigh the composition", rich_memory())
        d = execute(plan, rich_memory(), stub_registry(), chain_id="ch_9").to_dict()
        assert d["provenance"]["chain_id"] == "ch_9"
        assert d["provenance"]["workflow"] == "weigh_composition"
        assert d["provenance"]["planner"] == "rule_based"
        assert len(d["provenance"]["lineage"]) == len(plan.steps)
        assert "counts" in d["memory"]

    def test_confidence_stays_on_the_step_and_never_becomes_a_chain_number(self):
        """Contract §6, widened: the chain reports a weakest link, not a synthesised score."""
        plan = Director().plan("trace the light", rich_memory())
        d = execute(plan, rich_memory(), stub_registry()).provenance.to_dict()
        assert "confidence" not in d                  # no chain-level confidence exists
        assert all("confidence" in link for link in d["lineage"])
