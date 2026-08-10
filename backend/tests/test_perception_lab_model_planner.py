"""
PERCEPTUAL-ORGANS-002 Lane D — the model arm, and the five guards it is allowed no exception to.

Every test here uses a fake client. There is no network in this file and there will not be one:
a suite that needed a key would stop running on the machine where a regression is most likely to
be introduced.
"""
from __future__ import annotations

import json

import pytest

from backend.schemas.perception_lab import (OrganFamily, PlannerIdentity, RefusalCode, SessionMode)
from backend.services.perception_lab import resolver as R
from backend.services.perception_lab.clock import FrozenClock, SequentialIds
from backend.services.perception_lab.planners import ModelPlanner, RulesPlanner
from backend.services.perception_lab.planners import model as M

from .test_perception_lab_resolver import AVAILABLE, extent_session, topology_session


class FakeClient:
    """Shaped like the Groq client, and it counts. `payload` may be a dict, a raw string, or an
    exception instance to raise."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0
        self.last_messages = None

        outer = self

        class _Completions:
            def create(self, *, messages, model, response_format=None, **_):
                outer.calls += 1
                outer.last_messages = messages
                outer.last_model = model
                if isinstance(outer.payload, Exception):
                    raise outer.payload
                content = outer.payload if isinstance(outer.payload, str) \
                    else json.dumps(outer.payload)
                return type("C", (), {"choices": [type("H", (), {
                    "message": type("M", (), {"content": content})()})()]})()

        self.chat = type("Chat", (), {"completions": _Completions()})()


def planner(payload, **kw) -> ModelPlanner:
    ids = SequentialIds()
    return ModelPlanner(FakeClient(payload), model="test/planner-1",
                        fallback=RulesPlanner(ids), ids=ids, **kw)


def plan_of(proposal, session):
    return R.resolve(proposal, session, capabilities=AVAILABLE, clock=FrozenClock(),
                     ids=SequentialIds()).plan


def ops(proposal):
    return [s.operation for s in proposal.steps]


def codes(obj):
    return [r.code for r in obj.refusals]


# ── the happy path ───────────────────────────────────────────────────────────

def test_a_model_proposal_becomes_a_typed_step_and_resolves():
    p = planner({"steps": [{"operation": "extent.find_named",
                            "parameters": {"concept": "drapery"},
                            "why": "the person named a thing to look for"}]})
    proposal = p.plan("find the drapery", extent_session())
    assert proposal.planner is PlannerIdentity.MODEL
    assert proposal.fell_back_from is None
    assert ops(proposal) == ["extent.find_named"]
    plan = plan_of(proposal, extent_session())
    assert plan.resolved_steps[0].parameters == {"concept": "drapery"}
    assert plan.resolved_steps[0].authorized_by == "resolver"


def test_the_models_reason_is_quoted_as_a_rationale_and_not_rewritten_as_a_finding():
    p = planner({"steps": [{"operation": "extent.find_all", "why": "the person asked for all"}]})
    assert p.plan("mask everything", extent_session()).steps[0].rationale == \
        "the person asked for all"


def test_the_organ_of_a_step_is_read_off_the_registry_not_taken_from_the_model():
    """The model is not asked which organ, and there is no field in which its answer would land."""
    p = planner({"steps": [{"operation": "topology.adjacency", "organ": "extent"}]})
    step = p.plan("do those two touch?", topology_session()).steps[0]
    assert step.organ is OrganFamily.TOPOLOGY


# ── guard 1: hallucinated operations are refused by name ─────────────────────

def test_an_invented_operation_is_refused_by_name_rather_than_dropped():
    p = planner({"steps": [{"operation": "extent.hallucinate_everything"},
                           {"operation": "extent.find_all"}]})
    proposal = p.plan("do something clever", extent_session())
    assert ops(proposal) == ["extent.find_all"]
    assert codes(proposal) == [RefusalCode.UNSUPPORTED_OPERATION]
    assert proposal.refusals[0].detail["invented"] == "extent.hallucinate_everything"


def test_the_two_operations_a_model_may_not_author_are_absent_from_its_catalogue():
    catalogue = json.dumps(M._catalogue())
    assert "extent.draw" not in catalogue
    assert "extent.reuse" not in catalogue
    assert "extent.find_all" in catalogue and "topology.occlusion" in catalogue


def test_naming_a_withheld_operation_refuses_before_any_step_is_built():
    """Withholding it from the catalogue is not enough, and this is the test that says why.

    `extent.draw` DECLARES `polygon`, so a resolver handed such a step would accept the geometry:
    declared, well typed, and indistinguishable downstream from a person's hand. The catalogue
    stops an honest model; this stops one that guessed the name.
    """
    p = planner({"steps": [{"operation": "extent.draw",
                            "parameters": {"tool": "polygon",
                                           "polygon": [[0.1, 0.1], [0.9, 0.9]]}}]})
    proposal = p.plan("draw the figure for me", extent_session())
    assert proposal.steps == ()
    assert codes(proposal) == [RefusalCode.INVALID_PARAMETERS]
    assert "may not author extent.draw" in proposal.refusals[0].detail["why"]
    plan = plan_of(proposal, extent_session())
    assert plan.resolved_steps == []
    assert plan.dropped_parameters == []          # no step was ever built to drop them from


def test_geometry_a_model_supplied_is_removed_even_where_the_operation_declares_it():
    """`extent.refine` DECLARES `points` and `box` — a person clicks them — so the resolver has
    every reason to accept them. Who supplied them is the thing only this planner knows."""
    p = planner({"steps": [{"operation": "extent.refine",
                            "parameters": {"mode": "add", "points": [[0.4, 0.6]],
                                           "box": {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.3}},
                            "inputs": [{"role": "base", "artifact_id": "art_1"}]}]})
    proposal = p.plan("refine that mask around the hand", extent_session())
    assert proposal.steps[0].parameters == {"mode": "add"}
    assert codes(proposal) == [RefusalCode.INVALID_PARAMETERS]
    assert proposal.refusals[0].detail["removed"] == ["box", "points"]
    plan = plan_of(proposal, extent_session())
    assert plan.resolved_steps[0].parameters == {"mode": "add"}


def test_no_geometry_a_model_supplied_can_reach_a_resolved_step_of_any_operation():
    """The property the two previous tests protect, stated over every operation at once."""
    geometry = {"mask_rle": {"size": [4, 4], "counts": [0, 16]},
                "polygon": [[0.1, 0.1], [0.9, 0.9]], "box": {"x": 0.0, "y": 0.0, "w": 1.0,
                                                             "h": 1.0},
                "points": [[0.5, 0.5]]}
    seen = 0
    for op_key in R.declared_operations():
        session = extent_session() if op_key.startswith("extent.") else topology_session()
        # Every declared input role filled from the session, so a step dies at the geometry guard
        # rather than surviving on a missing-input refusal and passing this test by accident.
        from backend.services.perception_lab.definitions import operation as _op
        inputs = [{"role": spec.role, "artifact_id": "art_1"} for spec in _op(op_key).inputs
                  for _ in range(max(spec.min, 1))]
        p = planner({"steps": [{"operation": op_key, "parameters": dict(geometry),
                                "inputs": inputs}]})
        plan = plan_of(p.plan("do it", session), session)
        for step in plan.resolved_steps:
            seen += 1
            assert not (set(step.parameters) & set(geometry)), \
                f"{op_key} carried planner-supplied geometry into a resolved step"
    assert seen, "no operation resolved at all; this test proved nothing"


# ── guard 2: invented ids are proposed, then refused by name ─────────────────

def test_an_invented_artifact_id_is_refused_by_the_resolver_naming_the_id():
    p = planner({"steps": [{"operation": "topology.adjacency",
                            "inputs": [{"role": "source", "artifact_id": "art_1"},
                                       {"role": "target", "artifact_id": "art_whatever"}]}]})
    plan = plan_of(p.plan("do those two touch?", topology_session()), topology_session())
    assert plan.resolved_steps == []
    assert codes(plan) == [RefusalCode.UNKNOWN_REFERENCE]
    assert plan.refusals[0].missing == ["art_whatever"]


def test_an_invented_id_is_not_downgraded_into_a_missing_input():
    """Dropping the bad ref would produce `missing_extent_inputs` — the wrong diagnosis, and one
    that blames the person for what the planner did."""
    p = planner({"steps": [{"operation": "topology.adjacency",
                            "inputs": [{"role": "source", "artifact_id": "art_nope"},
                                       {"role": "target", "artifact_id": "art_nope_2"}]}]})
    plan = plan_of(p.plan("do those two touch?", topology_session()), topology_session())
    assert codes(plan) == [RefusalCode.UNKNOWN_REFERENCE]
    assert RefusalCode.MISSING_EXTENT_INPUTS not in codes(plan)


def test_a_model_cited_region_is_refused_because_it_has_no_revision_to_cite():
    p = planner({"steps": [{"operation": "topology.containment",
                            "inputs": [{"role": "source", "region_id": "reg_7"}]}]})
    proposal = p.plan("is it inside", topology_session())
    assert codes(proposal) == [RefusalCode.UNKNOWN_REFERENCE]
    assert "geometry_rev" in proposal.refusals[0].remedy


def test_the_ids_the_model_is_shown_are_only_the_ones_the_session_declared():
    p = planner({"steps": []})
    p.plan("anything", extent_session())
    sent = p._client.last_messages[1]["content"]
    assert '"art_1"' in sent and '"art_2"' in sent
    assert "art_3" not in sent


# ── guard 3: exactly one call ────────────────────────────────────────────────

def test_there_is_exactly_one_model_call_per_plan_even_when_everything_refuses():
    p = planner({"steps": [{"operation": "nonsense.one"}, {"operation": "nonsense.two"}]})
    p.plan("do the impossible", extent_session())
    assert p.calls == 1
    assert p._client.calls == 1


# ── guard 4: a fallback wears its own name ───────────────────────────────────

@pytest.mark.parametrize("payload", [
    RuntimeError("upstream is down"),
    "this is not json at all",
])
def test_an_unreachable_model_falls_back_and_the_plan_says_so(payload):
    p = planner(payload)
    proposal = p.plan("find the drapery", extent_session())
    assert proposal.planner is PlannerIdentity.RULES
    assert proposal.fell_back_from is PlannerIdentity.MODEL
    assert ops(proposal) == ["extent.find_named"]
    plan = plan_of(proposal, extent_session())
    assert plan.planner is PlannerIdentity.RULES
    assert plan.planner_fell_back_from is PlannerIdentity.MODEL


def test_a_planner_with_no_client_is_unavailable_rather_than_a_crash():
    p = ModelPlanner(client=None, model="test/planner-1", fallback=RulesPlanner(SequentialIds()),
                     ids=SequentialIds())
    p._client_resolved = True                       # no lazy import, no key, no network
    proposal = p.plan("find the drapery", extent_session())
    assert proposal.fell_back_from is PlannerIdentity.MODEL
    assert p.calls == 0
    assert any("unavailable" in n for n in proposal.notes)


def test_a_planner_with_no_bound_model_falls_back_naming_the_role():
    p = ModelPlanner(FakeClient({"steps": []}), model=None,
                     fallback=RulesPlanner(SequentialIds()), ids=SequentialIds())
    proposal = p.plan("find the drapery", extent_session())
    assert proposal.fell_back_from is PlannerIdentity.MODEL
    assert any(M.ROLE in n for n in proposal.notes)


def test_a_fallback_cannot_claim_to_have_fallen_back_from_itself():
    from pydantic import ValidationError

    from backend.schemas.perception_lab import LabPlan
    with pytest.raises(ValidationError):
        LabPlan(plan_id="p", session_id="s", planner=PlannerIdentity.RULES,
                planner_fell_back_from=PlannerIdentity.RULES, selected_organ=OrganFamily.EXTENT,
                mode=SessionMode.ISOLATION, requires_confirmation=False,
                created_at="2026-08-10T09:00:00Z")


def test_one_fallback_does_not_make_every_later_plan_look_like_a_fallback():
    ids = SequentialIds()
    p = ModelPlanner(FakeClient(RuntimeError("down")), model="m",
                     fallback=RulesPlanner(ids), ids=ids)
    p.plan("find the drapery", extent_session())
    p._client.payload = {"steps": [{"operation": "extent.find_all"}]}
    again = p.plan("mask everything", extent_session())
    assert again.planner is PlannerIdentity.MODEL
    assert again.fell_back_from is None
    assert p.last_notes[0].startswith("planner: model")


# ── guard 5: honest silence is not overruled ─────────────────────────────────

def test_a_model_that_proposes_nothing_is_not_replaced_by_a_keyword_guess():
    """The prompt WOULD have matched the deterministic table. The model said no, and that stands."""
    p = planner({"steps": [], "notes": ["nothing in the catalogue reads this prompt"]})
    proposal = p.plan("find the drapery", extent_session())
    assert proposal.steps == ()
    assert proposal.planner is PlannerIdentity.MODEL
    assert proposal.fell_back_from is None
    assert any("nothing in the catalogue" in n for n in proposal.notes)


def test_a_non_object_payload_uses_nothing_from_it():
    p = planner(["not", "an", "object"])
    proposal = p.plan("find the drapery", extent_session())
    assert proposal.steps == ()
    assert proposal.planner is PlannerIdentity.MODEL
    assert any("non-object payload" in n for n in proposal.notes)


# ── the model is still just a planner ────────────────────────────────────────

def test_the_model_cannot_change_the_organ_in_isolation_mode():
    p = planner({"steps": [{"operation": "topology.adjacency",
                            "inputs": [{"role": "source", "artifact_id": "art_1"},
                                       {"role": "target", "artifact_id": "art_2"}]}]})
    plan = plan_of(p.plan("do those two touch?", extent_session()), extent_session())
    assert plan.resolved_steps == []
    assert codes(plan) == [RefusalCode.ORGAN_LOCKED]


def test_the_model_cannot_grant_confirmation_or_authorization():
    p = planner({"steps": [{"operation": "topology.all_pairs",
                            "requires_confirmation": False,
                            "authorized_by": "resolver",
                            "inputs": [{"role": "members", "artifact_id": "art_1"},
                                       {"role": "members", "artifact_id": "art_2"}]}]})
    plan = plan_of(p.plan("which of these touch?", topology_session()), topology_session())
    assert plan.requires_confirmation is True       # the OPERATION declares it; the model did not
    assert plan.resolved_steps[0].authorized_by == "resolver"


def test_more_steps_than_a_request_can_hold_are_cut_and_the_cut_is_stated():
    p = planner({"steps": [{"operation": "extent.find_all"} for _ in range(9)]})
    proposal = p.plan("do everything", extent_session())
    assert len(proposal.steps) == M.MAX_STEPS
    assert any("kept the first 4" in n for n in proposal.notes)


def test_the_system_prompt_forbids_the_two_things_a_planner_could_fabricate():
    assert "CANNOT SEE THE IMAGE" in M.SYSTEM_PROMPT
    assert "Never invent an id" in M.SYSTEM_PROMPT
