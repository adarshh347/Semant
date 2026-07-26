"""
CIRCUIT-001 PLANNER-001 — the Groq planner behind the Director seam.

Everything in the default run uses a FAKE client and touches no network. The real-API tests
at the bottom are guarded by `SEMANT_GROQ_LIVE=1` and skip otherwise, so CI stays hermetic.

What is actually being tested here is not "does the model produce good plans" — it cannot be,
because the model is not deterministic. It is that **no output the model can produce is able
to cause a wrong action**: hallucinations are refused by name, disallowed params never reach a
step, a failure is visible rather than silent, and there is exactly one call per plan.
"""
from __future__ import annotations

import json
import os

import pytest

from backend.services.director import groq_planner as gp
from backend.services.director.capabilities import Resource
from backend.services.director.groq_planner import (GroqPlanner, build_prompt, get_planner,
                                                    parse_steps)
from backend.services.director.memory import build_memory
from backend.services.director.plan import (REFUSED_MISSING_INPUT, REFUSED_MISSING_PARAM,
                                            REFUSED_UNKNOWN_ACTUATOR)
from backend.services.director.planner import Director, RuleBasedPlanner


# ── fakes ────────────────────────────────────────────────────────────────────

class FakeGroq:
    """Minimal stand-in for the Groq client. Returns whatever content it is given."""

    def __init__(self, content, *, raise_on_call: Exception = None):
        self._content = content
        self._raise = raise_on_call
        self.calls = 0
        self.last_kwargs = None

        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.calls += 1
                outer.last_kwargs = kwargs
                if outer._raise:
                    raise outer._raise
                body = (outer._content if isinstance(outer._content, str)
                        else json.dumps(outer._content))
                return type("R", (), {"choices": [
                    type("C", (), {"message": type("M", (), {"content": body})()})()]})()

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


def bare_memory(**kw):
    return build_memory(image_ref="img_1", post_id="post_1", **kw)


def rich_memory(*, regions=2, marks=3, **kw):
    return build_memory(image_ref="img_1", post_id="post_1",
                        region_ids=tuple(f"reg_{i}" for i in range(regions)),
                        mark_ids=tuple(f"mark_{i}" for i in range(marks)), **kw)


def planner_with(content, **kw):
    client = FakeGroq(content)
    return GroqPlanner(client=client, **kw), client


# ── the prompt ───────────────────────────────────────────────────────────────

class TestPrompt:

    def test_the_prompt_carries_what_exists(self):
        """A planner that cannot see there are zero marks keeps proposing connect_marks."""
        p = build_prompt("trace the light", rich_memory(regions=2, marks=3))
        assert '"region": 2' in p and '"mark": 3' in p

    def test_the_prompt_ships_the_vocabulary_as_data(self):
        p = build_prompt("anything", bare_memory())
        assert '"actuator": "presence_check"' in p
        assert '"actuator": "connect_marks"' in p
        assert '"requires"' in p and '"params_you_may_set"' in p

    def test_the_prompt_states_the_curators_phrase(self):
        assert '"the folded cloth"' in build_prompt("x", bare_memory(phrase="the folded cloth"))

    def test_the_system_prompt_forbids_authoring_evidence(self):
        low = gp.SYSTEM_PROMPT.lower()
        assert "never invent" in low
        assert "geometry" in low and "confidence" in low


# ── parsing: tolerant of shape, strict about content ─────────────────────────

class TestParsing:

    def test_a_clean_response_becomes_steps(self):
        steps, notes = parse_steps({"steps": [
            {"actuator": "light_field", "params": {}, "note": "where light lives"},
            {"actuator": "shadow_field", "params": {}}]})
        assert [s.actuator for s in steps] == ["light_field", "shadow_field"]
        assert steps[0].note == "where light lives"
        assert all(s.id for s in steps)
        assert notes == []

    def test_a_hallucinated_name_is_NOT_filtered_out_here(self):
        """Guard 1. Dropping it silently would hide how often the model invents things."""
        steps, _ = parse_steps({"steps": [{"actuator": "summon_the_muse", "params": {}}]})
        assert [s.actuator for s in steps] == ["summon_the_muse"]

    def test_disallowed_params_are_dropped_and_reported(self):
        """Guard 2. The model cannot see the image; it cannot possess geometry."""
        steps, notes = parse_steps({"steps": [{"actuator": "presence_check", "params": {
            "phrase": "a cross", "geometry": {"mask": "..."}, "confidence": 0.99,
            "region_ids": ["reg_1"]}}]})
        assert steps[0].params == {"phrase": "a cross"}
        assert any("geometry" in n and "confidence" in n for n in notes)

    def test_an_unknown_actuator_keeps_no_params_at_all(self):
        steps, notes = parse_steps({"steps": [
            {"actuator": "fabricate", "params": {"mask": "..."}}]})
        assert steps[0].params == {}
        assert any("disallowed params" in n for n in notes)

    def test_shape_wobble_is_survivable(self):
        steps, notes = parse_steps({"plan": [                 # 'plan' instead of 'steps'
            {"name": "rhythm"},                               # 'name' instead of 'actuator'
            "not an object",
            {"actuator": "", "params": {}},
            {"actuator": "pressure_zone", "params": "not a dict", "note": 7}]})
        assert [s.actuator for s in steps] == ["rhythm", "pressure_zone"]
        assert steps[1].note == ""                            # non-string note ignored
        assert len(notes) == 2                                # both drops reported

    def test_a_non_object_payload_yields_nothing_and_says_so(self):
        steps, notes = parse_steps(["light_field"])
        assert steps == [] and notes

    def test_a_runaway_plan_is_capped_and_the_cap_is_reported(self):
        many = {"steps": [{"actuator": "rhythm"} for _ in range(20)]}
        steps, notes = parse_steps(many)
        assert len(steps) == gp.MAX_STEPS
        assert any("kept the first" in n for n in notes)


# ── the guards, end to end through the Director ──────────────────────────────

class TestHonestyGuards:

    def test_a_hallucinated_actuator_is_refused_by_name(self):
        planner, _ = planner_with({"steps": [
            {"actuator": "enhance_the_aura", "params": {}},
            {"actuator": "rhythm", "params": {}}]})
        plan = Director(planner).plan("do something", bare_memory())
        assert [s.actuator for s in plan.steps] == ["rhythm"]
        assert plan.refused[0].reason == REFUSED_UNKNOWN_ACTUATOR
        assert "enhance_the_aura" in plan.refused[0].detail

    def test_an_unsatisfiable_chain_is_refused_not_run(self):
        planner, _ = planner_with({"steps": [
            {"actuator": "connect_marks", "params": {"relation_role": "motif_echo"}}]})
        plan = Director(planner).plan("connect them", bare_memory())
        assert plan.steps == ()
        assert plan.refused[0].reason == REFUSED_MISSING_INPUT

    def test_the_model_cannot_smuggle_geometry_into_a_step(self):
        planner, _ = planner_with({"steps": [{"actuator": "negative_space", "params": {
            "geometry": {"kind": "raster_mask"}, "mask_ref": "reg_1"}}]})
        plan = Director(planner).plan("the empty space", rich_memory())
        assert plan.steps[0].params == {}
        assert any("disallowed params" in n for n in plan.notes)

    def test_the_model_cannot_fake_a_phrase_it_was_not_given(self):
        """An open-vocab actuator with no phrase is refused, model or not."""
        planner, _ = planner_with({"steps": [{"actuator": "presence_check", "params": {}}]})
        plan = Director(planner).plan("is there a cross", bare_memory())
        assert plan.refused[0].reason == REFUSED_MISSING_PARAM

    def test_exactly_one_call_per_plan_even_when_everything_is_refused(self):
        """Guard 3. Looping until something passes searches for a chain that RUNS, not one
        that is true — the fabrication this layer exists to prevent, arriving from the top."""
        planner, client = planner_with({"steps": [
            {"actuator": "connect_marks", "params": {"relation_role": "x"}},
            {"actuator": "invented_thing", "params": {}}]})
        plan = Director(planner).plan("go", bare_memory())
        assert client.calls == 1
        assert planner.calls == 1
        assert plan.steps == () and len(plan.refused) == 2

    def test_a_badly_ordered_model_chain_is_reordered_not_refused(self):
        planner, _ = planner_with({"steps": [
            {"actuator": "material_field", "params": {}},
            {"actuator": "find_parts", "params": {}}]})
        plan = Director(planner).plan("what is it made of", bare_memory())
        assert [s.actuator for s in plan.steps] == ["find_parts", "material_field"]
        assert plan.reordered is True and plan.refused == ()

    def test_a_reading_still_cannot_satisfy_a_mark_requirement(self):
        planner, _ = planner_with({"steps": [
            {"actuator": "presence_check", "params": {"phrase": "a cross"}},
            {"actuator": "compose_percept", "params": {"draft_text": "x"}}]})
        plan = Director(planner).plan("read it", bare_memory())
        assert [s.actuator for s in plan.steps] == ["presence_check"]
        assert plan.refused[0].step.actuator == "compose_percept"


# ── failure is visible ───────────────────────────────────────────────────────

class TestFallback:

    def test_an_api_error_falls_back_to_rules_and_SAYS_SO(self):
        planner = GroqPlanner(client=FakeGroq(None, raise_on_call=RuntimeError("boom")))
        plan = Director(planner).plan("trace the light", rich_memory())
        assert [s.actuator for s in plan.steps][:2] == ["light_field", "shadow_field"]
        assert any("groq planner failed" in n for n in plan.notes)
        assert any("fell back to rule_based" in n for n in plan.notes)

    def test_unparseable_json_falls_back_and_says_so(self):
        planner = GroqPlanner(client=FakeGroq("not json at all"))
        plan = Director(planner).plan("trace the light", rich_memory())
        assert plan.steps
        assert any("fell back" in n for n in plan.notes)

    def test_no_client_is_unavailable_not_a_crash(self):
        planner = GroqPlanner(client=None)
        planner._client_resolved = True          # simulate "resolved, and there is none"
        plan = Director(planner).plan("trace the light", rich_memory())
        assert plan.steps
        assert any("unavailable" in n for n in plan.notes)

    def test_an_empty_proposal_is_reported_in_the_language_of_the_planner_that_ran(self):
        """'No way of looking matches' names KEYWORD MATCHING — a lie about a model that read
        the intention and judged nothing serves it. Same outcome, different fact."""
        planner, _ = planner_with({"steps": []})
        groq_plan = Director(planner).plan("what does it mean", bare_memory())
        rule_plan = Director(RuleBasedPlanner()).plan("what does it mean", bare_memory())
        assert "groq planner found nothing" in " ".join(groq_plan.notes)
        assert "no way of looking matches" not in " ".join(groq_plan.notes)
        assert "no way of looking matches" in " ".join(rule_plan.notes)

    def test_an_empty_model_proposal_is_respected_not_overruled(self):
        """'None of these serve that' is an answer. Falling back would overrule an honest
        refusal with a keyword guess — and the keyword guess would win, wrongly."""
        planner, client = planner_with({"steps": []})
        plan = Director(planner).plan("trace the light", rich_memory())
        assert plan.steps == ()
        assert client.calls == 1
        assert any("proposed no steps" in n for n in plan.notes)
        assert not any("fell back" in n for n in plan.notes)

    def test_the_receipt_names_which_planner_ran(self):
        planner, _ = planner_with({"steps": [{"actuator": "rhythm", "params": {}}]})
        plan = Director(planner).plan("rhythm please", bare_memory())
        assert plan.planner == "groq"
        assert any("planner: groq" in n for n in plan.notes)


class TestSelection:

    def test_get_planner_selects_and_defaults_safely(self):
        assert get_planner("groq").name == "groq"
        assert get_planner("rule_based").name == "rule_based"
        assert get_planner("nonsense").name == "rule_based"   # unknown → rules, not an error

    def test_the_rule_based_planner_is_untouched_by_this_gate(self):
        plan = Director(RuleBasedPlanner()).plan("trace the light", rich_memory())
        assert [s.actuator for s in plan.steps] == \
               ["light_field", "shadow_field", "semantic_read"]
        assert plan.workflow == "trace_light"

    def test_a_groq_plan_is_not_credited_to_a_rule_workflow(self):
        """A model chain containing 'light' did not come from `trace_light`; labelling it so
        would put a false lineage on the receipt."""
        planner, _ = planner_with({"steps": [{"actuator": "light_field", "params": {}}]})
        plan = Director(planner).plan("trace the light", rich_memory())
        assert plan.workflow is None


# ── real API (guarded; skipped in CI) ────────────────────────────────────────

LIVE = os.getenv("SEMANT_GROQ_LIVE") == "1"
live_only = pytest.mark.skipif(not LIVE, reason="needs SEMANT_GROQ_LIVE=1 and a GROQ_API_KEY")


@live_only
class TestLiveGroq:

    def test_a_real_intention_yields_a_resolvable_chain(self):
        planner = GroqPlanner()
        assert planner.is_available(), "GROQ_API_KEY not configured"
        plan = Director(planner).plan("trace the light", rich_memory())
        assert plan.planner == "groq"
        assert not any("fell back" in n for n in plan.notes), plan.notes
        assert plan.steps, f"no runnable steps: {plan.to_dict()}"

    def test_the_real_model_only_ever_names_known_actuators_or_is_refused(self):
        """Not an assertion that it never hallucinates — an assertion that when it does, the
        guard catches it rather than the step executing."""
        from backend.services.director.capabilities import known
        planner = GroqPlanner()
        plan = Director(planner).plan("find the motif and its echoes",
                                      rich_memory(phrase="the folded cloth"))
        for s in plan.steps:
            assert s.actuator in known()          # nothing unknown ever survives resolve()
        for r in plan.refused:
            assert r.reason in (REFUSED_UNKNOWN_ACTUATOR, REFUSED_MISSING_INPUT,
                                REFUSED_MISSING_PARAM)

    def test_a_forced_hallucination_from_the_real_pipeline_is_refused(self):
        """Uses the real parse path with a hallucinated name, proving the refusal is in the
        shared code and not in the fake."""
        planner, _ = planner_with({"steps": [{"actuator": "paint_the_feeling", "params": {}}]})
        plan = Director(planner).plan("anything", rich_memory())
        assert plan.steps == ()
        assert plan.refused[0].reason == REFUSED_UNKNOWN_ACTUATOR

    def test_the_real_model_is_called_exactly_once(self):
        planner = GroqPlanner()
        Director(planner).plan("weigh the composition", bare_memory())
        assert planner.calls == 1
