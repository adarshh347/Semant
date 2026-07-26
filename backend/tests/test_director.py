"""
CIRCUIT-001 ORCH-001 — capability map, working memory, and dependency resolution.

No model, no GPU, no network, no database: this layer is a table plus a frozen dataclass,
which is what lets the whole Director be tested unattended.
"""
from __future__ import annotations

from backend.services.director import capabilities as caps
from backend.services.director.capabilities import Resource
from backend.services.director.memory import build_memory
from backend.services.director.plan import (REFUSED_MISSING_INPUT, REFUSED_MISSING_PARAM,
                                            REFUSED_UNKNOWN_ACTUATOR, Step, resolve)


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
