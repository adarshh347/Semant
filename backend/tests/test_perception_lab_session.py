"""
PERCEPTUAL-ORGANS-002 Lane D — session context, and what a follow-up is allowed to mean.

The laboratory's conversational claim is small and exact: a person may say "that mask" and "do
those two touch?" and be understood. The claim underneath it is the one being tested here — that
the understanding comes from ids the person selected, and from nothing else.

The interesting tests are the ones where the sentence is unchanged and the answer changes because
the SELECTION changed. That is the whole difference between a laboratory and a chat.
"""
from __future__ import annotations

import pytest

from backend.schemas.perception_lab import (LabSource, OrganFamily, RefusalCode, SessionMode)
from backend.services.perception_lab import resolver as R
from backend.services.perception_lab.clock import FrozenClock, SequentialIds
from backend.services.perception_lab.planners import RulesPlanner
from backend.services.perception_lab.session import SessionMachine, SessionView, declared_ids

from .test_perception_lab_resolver import AVAILABLE

SOURCE = LabSource(origin="post", post_id="post_finial", image_digest="sha256:9f1c0a5b7d2e4438",
                   natural_width=1600, natural_height=1200)


def machine(organ=OrganFamily.EXTENT, mode=SessionMode.ISOLATION, clock=None) -> SessionMachine:
    return SessionMachine.open(source=SOURCE, organ=organ, mode=mode,
                               clock=clock or FrozenClock(), ids=SequentialIds())


def plan_for(prompt: str, view: SessionView):
    proposal = RulesPlanner(ids=SequentialIds()).plan(prompt, view)
    return R.resolve(proposal, view, capabilities=AVAILABLE, clock=FrozenClock(),
                     ids=SequentialIds()).plan


def cited(plan):
    return [r.artifact_id for s in plan.proposed_steps for r in s.input_refs]


def codes(plan):
    return [r.code for r in plan.refusals]


# ── opening ──────────────────────────────────────────────────────────────────

def test_a_new_session_declares_nothing_and_therefore_resolves_nothing():
    view = machine().view()
    assert view.artifact_ids == ()
    assert view.region_ids == ()
    assert declared_ids(machine().session) == ()


def test_a_session_cannot_be_opened_on_an_organ_this_phase_has_not_enabled():
    with pytest.raises(Exception):
        machine(organ=OrganFamily.DEPTH)


def test_every_transition_replaces_the_record_rather_than_editing_it():
    m = machine()
    before = m.session
    m.select("art_1")
    assert before.selected_artifact_ids == []
    assert m.session.selected_artifact_ids == ["art_1"]
    assert before is not m.session


def test_a_transition_moves_updated_at_and_leaves_created_at_alone():
    clock = FrozenClock()
    m = machine(clock=clock)
    created = m.session.created_at
    clock.advance(5000)
    m.select("art_1")
    assert m.session.created_at == created
    assert m.session.updated_at != created


# ── what "that" and "those two" are allowed to mean ──────────────────────────

def test_selection_order_is_the_order_a_pair_question_reads():
    m = machine(OrganFamily.TOPOLOGY)
    m.select("art_a", "art_b")
    assert cited(plan_for("do those two touch?", m.view())) == ["art_a", "art_b"]


def test_the_active_artifact_leads_and_is_not_repeated():
    m = machine(OrganFamily.TOPOLOGY)
    m.select("art_a", "art_b")
    m.activate("art_b")
    assert m.view().artifact_ids == ("art_b", "art_a")
    assert cited(plan_for("do those two touch?", m.view())) == ["art_b", "art_a"]


def test_selecting_the_same_artifact_twice_does_not_make_it_a_pair():
    """A relation between an artifact and itself measures perfectly and answers nothing."""
    m = machine(OrganFamily.TOPOLOGY)
    m.select("art_a", "art_a")
    assert m.session.selected_artifact_ids == ["art_a"]
    plan = plan_for("do those two touch?", m.view())
    assert codes(plan) == [RefusalCode.MISSING_EXTENT_INPUTS]


def test_activating_an_artifact_also_selects_it():
    """An active id reachable from one field and invisible in the other is a reference nobody
    can audit."""
    m = machine()
    m.activate("art_a")
    assert m.session.selected_artifact_ids == ["art_a"]
    assert m.view().artifact_ids == ("art_a",)


def test_that_mask_means_the_active_artifact_and_the_plan_says_which():
    m = machine()
    m.select("art_a", "art_b")
    m.activate("art_b")
    assert cited(plan_for("refine that mask", m.view())) == ["art_b"]


def test_the_same_sentence_answers_differently_when_the_selection_changes():
    """The difference between a laboratory and a chat, in one test."""
    m = machine(OrganFamily.TOPOLOGY)
    m.select("art_a", "art_b")
    first = cited(plan_for("do those two overlap?", m.view()))
    m.clear_selection()
    m.select("art_c", "art_d")
    second = cited(plan_for("do those two overlap?", m.view()))
    assert first == ["art_a", "art_b"]
    assert second == ["art_c", "art_d"]


# ── the deselection invariant ────────────────────────────────────────────────

def test_a_deselected_artifact_is_not_implicitly_reused():
    m = machine(OrganFamily.TOPOLOGY)
    m.select("art_a", "art_b", "art_c")
    m.deselect("art_a")
    assert cited(plan_for("do those two touch?", m.view())) == ["art_b", "art_c"]
    assert "art_a" not in declared_ids(m.session)


def test_deselecting_the_active_artifact_clears_it_rather_than_leaving_it_reachable():
    """Without this, the person's removal would be recorded and then disobeyed."""
    m = machine()
    m.select("art_a", "art_b")
    m.activate("art_a")
    m.deselect("art_a")
    assert m.session.active_artifact_id is None
    assert cited(plan_for("refine that mask", m.view())) == ["art_b"]


def test_a_deselected_id_cited_anyway_is_refused_by_name():
    from backend.schemas.perception_lab import IdentityScope, InputRef, PlannerIdentity, \
        ProposedStep
    m = machine(OrganFamily.TOPOLOGY)
    m.select("art_a", "art_b")
    m.deselect("art_a")
    step = ProposedStep(step_id="s1", organ=OrganFamily.TOPOLOGY, operation="topology.adjacency",
                        input_refs=[InputRef(role="source", scope=IdentityScope.SESSION,
                                             artifact_id="art_a"),
                                    InputRef(role="target", scope=IdentityScope.SESSION,
                                             artifact_id="art_b")])
    plan = R.resolve(R.Proposal(planner=PlannerIdentity.DIRECT, steps=(step,)), m.view(),
                     capabilities=AVAILABLE, clock=FrozenClock(), ids=SequentialIds()).plan
    assert codes(plan) == [RefusalCode.UNKNOWN_REFERENCE]
    assert plan.refusals[0].missing == ["art_a"]


def test_a_follow_up_with_nothing_selected_refuses_and_says_what_the_word_needed():
    m = machine(OrganFamily.TOPOLOGY)
    proposal = RulesPlanner(ids=SequentialIds()).plan("do those two touch?", m.view())
    plan = R.resolve(proposal, m.view(), capabilities=AVAILABLE, clock=FrozenClock(),
                     ids=SequentialIds()).plan
    assert codes(plan) == [RefusalCode.MISSING_EXTENT_INPUTS]
    assert any("'those two'" in n and "0 declared artifact" in n for n in proposal.notes)


def test_a_prompt_that_points_at_nothing_never_reaches_for_the_store():
    """There is no field on `LabSession` in which a planner could record what it thinks was meant,
    and no method here that searches for a plausible recent artifact."""
    m = machine()
    assert not hasattr(m, "most_recent")
    assert not any(name.startswith("guess") or "recent" in name for name in dir(m))
    assert "plan_id" in {f for f in type(m.session).model_fields["prompt_turns"]
                         .annotation.__args__[0].model_fields}


# ── switching organs and modes ───────────────────────────────────────────────

def test_switching_organs_keeps_the_selection_because_topology_consumes_it():
    m = machine(OrganFamily.EXTENT)
    m.select("art_a", "art_b")
    m.select_organ(OrganFamily.TOPOLOGY)
    assert m.view().artifact_ids == ("art_a", "art_b")
    plan = plan_for("do those two touch?", m.view())
    assert [s.operation for s in plan.resolved_steps] == ["topology.adjacency"]


def test_the_lock_is_re_applied_against_the_new_organ_and_not_remembered_from_the_old_one():
    m = machine(OrganFamily.TOPOLOGY)
    m.select("art_a", "art_b")
    assert plan_for("do those two touch?", m.view()).resolved_steps
    m.select_organ(OrganFamily.EXTENT)
    assert codes(plan_for("do those two touch?", m.view())) == [RefusalCode.ORGAN_LOCKED]


def test_switching_to_chain_mode_changes_the_refusal_into_a_visible_offer():
    m = machine(OrganFamily.TOPOLOGY)
    assert codes(plan_for("do those two touch?", m.view())) == \
        [RefusalCode.MISSING_EXTENT_INPUTS]
    m.set_mode(SessionMode.CHAIN)
    chained = plan_for("do those two touch?", m.view())
    assert [s.operation for s in chained.resolved_steps] == ["extent.find_all"]
    assert chained.requires_confirmation is True


# ── canonical regions ────────────────────────────────────────────────────────

def test_active_regions_replace_rather_than_accumulate():
    m = machine()
    m.activate_regions(["reg_1", "reg_2"])
    m.activate_regions(["reg_3"])
    assert m.session.active_region_ids == ["reg_3"]
    assert m.view().knows_region("reg_1") is False


# ── the ledger of the sitting ────────────────────────────────────────────────

def test_a_turn_records_the_words_and_the_plan_and_nothing_the_machine_understood():
    m = machine()
    turn = m.record_turn("mask every face")
    assert set(turn.model_dump()) == {"turn_id", "text", "at", "plan_id"}
    m.attach_plan(turn.turn_id, "plan_7")
    assert m.session.prompt_turns[0].plan_id == "plan_7"
    assert m.session.prompt_turns[0].text == "mask every face"


def test_runs_and_reviews_are_recorded_once():
    m = machine()
    m.record_run("run_1")
    m.record_run("run_1")
    m.record_review("rev_1")
    m.record_review("rev_1")
    assert m.session.run_ids == ["run_1"]
    assert m.session.review_ids == ["rev_1"]


def test_a_machine_with_no_id_factory_refuses_to_invent_one():
    from backend.schemas.perception_lab import LabSession
    session = LabSession(session_id="labs_1", source=SOURCE, selected_organ=OrganFamily.EXTENT,
                         mode=SessionMode.ISOLATION, created_at="2026-08-10T09:00:00Z",
                         updated_at="2026-08-10T09:00:00Z")
    m = SessionMachine(session, clock=FrozenClock())
    with pytest.raises(RuntimeError):
        m.record_turn("mask every face")


def test_the_view_carries_only_what_the_resolver_may_decide_from():
    """No prompt turns, no run history, no timestamps — nothing a resolver could reason from."""
    fields = set(SessionView.__dataclass_fields__)
    assert fields == {"session_id", "selected_organ", "mode", "active_artifact_id",
                      "active_region_ids", "selected_artifact_ids", "selected_instance_refs"}
