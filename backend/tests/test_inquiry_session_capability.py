"""
HARNESS-002D §4/§5 — the one simulated point in Phase 1, and the judge that cannot be fooled by it.

Every test here is a way the stand-in could stop being visibly a stand-in, or the verdict it feeds
could quietly become a finding.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.schemas.inquiry_session import (CapabilityReceipt, ClaimVerdictOutcome, ExecutionMode,
                                             ReceiptStatus, SUPPORTED_VERDICTS,
                                             SemanticInquirySession)
from backend.services.inquiry_session import coordinator, judge as J
from backend.services.inquiry_session.capability import (CapabilityBudgetSpent,
                                                         LockedFixtureCapability,
                                                         SERVABLE_CLASSES, SIMULATION_NOTICE)
from backend.tests.fixtures import inquiry_session_fixtures as F

AT = "2026-08-09T00:00:00+00:00"


def an_observable(**kw):
    base = {"observable_id": "obs_1", "claim_id": "clm_1", "observable_kind": "extent_of",
            "targets": ["the named thing"], "capability_classes": ["extent"],
            "ground_forms": ["region"], "alternatives": []}
    base.update(kw)
    return base


def run(name, mode="consult", option_index=0, **bound):
    """The whole chain over one fixture, answered if it pauses. No network, no database."""
    stages = F.stages_for(name, capability=bound.pop("capability", LockedFixtureCapability()),
                          judge=bound.pop("judge", J.judge), **bound)
    session = coordinator.new_session(prompt=F.prompt_for(name), refs=F.post_refs(name),
                                      mode=mode, now=AT)
    session = coordinator.begin(session, stages)
    if session.awaiting_user:
        request = coordinator.machine.from_dict(session.interaction).open_decision
        session = coordinator.resume(session, {
            "response_id": "r1", "session_id": session.session_id,
            "decision_id": request.decision_id, "expected_revision": session.revision,
            "kind": "select_option", "option_id": request.options[option_index].option_id,
            "at": AT}, stages)
    return session, stages


# ── the receipt says what it is ──────────────────────────────────────────────

@pytest.mark.parametrize("name", F.FIXTURES)
def test_the_one_receipt_declares_itself_a_simulation_in_every_field_that_can(name):
    session, _ = run(name)
    assert len(session.capability_receipts) == 1, "Phase 1 allows exactly zero or one"
    receipt = session.capability_receipts[0]
    assert receipt.execution_mode is ExecutionMode.FIXTURE
    assert receipt.status is ReceiptStatus.SIMULATED
    assert receipt.usable_as_evidence is False
    assert receipt.attempted is True
    assert SIMULATION_NOTICE in receipt.detail
    assert receipt.payload["notice"] == SIMULATION_NOTICE


@pytest.mark.parametrize("name", F.FIXTURES)
def test_every_coordinate_says_on_its_face_that_it_came_from_a_hash(name):
    """The notice on the receipt is one place. This is the other: beside the numbers themselves,
    where somebody reading the numbers will see it without having scrolled back."""
    session, _ = run(name)
    proposals = session.capability_receipts[0].payload["proposals"]
    assert proposals
    for proposal in proposals:
        assert proposal["simulated"] is True
        assert proposal["confidence"] is None, "a stand-in that reported a confidence invented the "\
                                               "one field a reader uses to decide how much to believe it"
        assert proposal["region"]["measured"] is False
        assert "not from any image" in proposal["region"]["derived_from"]


def test_a_fixture_receipt_that_claimed_to_be_evidence_cannot_be_constructed():
    with pytest.raises(ValidationError, match="usable as evidence"):
        CapabilityReceipt(receipt_id="capr_x", request_ref="obs_1", capability="locate_phrase",
                          execution_mode=ExecutionMode.FIXTURE, status=ReceiptStatus.SIMULATED,
                          usable_as_evidence=True)


def test_a_fixture_receipt_cannot_call_itself_live():
    with pytest.raises(ValidationError, match="may not contradict"):
        CapabilityReceipt(receipt_id="capr_x", request_ref="obs_1", capability="locate_phrase",
                          execution_mode=ExecutionMode.FIXTURE, status=ReceiptStatus.LIVE)


# ── one attempt, spent on the attempt ────────────────────────────────────────

def test_the_adapter_spends_its_attempt_on_the_attempt_and_refuses_a_second():
    adapter = LockedFixtureCapability()
    adapter.invoke(session_id="inqs_1", observable=an_observable(), at=AT)
    assert adapter.attempts_left == 0
    with pytest.raises(CapabilityBudgetSpent):
        adapter.invoke(session_id="inqs_1", observable=an_observable(), at=AT)


def test_the_attempt_is_spent_even_when_nothing_could_run():
    """A budget decremented only on success is not a budget: a failing instrument would be retried
    forever by any loop reading "no output" as "not yet done"."""
    adapter = LockedFixtureCapability()
    receipt = adapter.invoke(session_id="inqs_1", at=AT,
                             observable=an_observable(capability_classes=["depth"]))
    assert receipt.status is ReceiptStatus.CAPABILITY_GAP
    assert receipt.attempted is False, "nothing was attempted against an instrument that is not there"
    assert adapter.attempts_left == 0, "the attempt was not spent"


@pytest.mark.parametrize("name", F.FIXTURES)
def test_a_resumed_session_does_not_spend_a_second_attempt(name):
    """THE FIREWALL IS THE SESSION. A fresh adapter is built per request, so its counter resets;
    the receipt already on the session does not."""
    session, stages = run(name)
    first = list(session.capability_receipts)
    assert len(first) == 1

    # A brand-new adapter with a full budget — exactly what a second HTTP request builds.
    again = coordinator.Stages(capability=LockedFixtureCapability(), judge=J.judge,
                               clock=stages.clock)
    ledger = coordinator._Ledger(session.session_id, seq=len(session.stages))
    resumed = coordinator._execute(session, again, ledger, AT)

    assert [r.receipt_id for r in resumed.capability_receipts] == [r.receipt_id for r in first]
    assert again.capability.attempts_left == 1, "the fresh adapter was asked to run at all"
    skipped = [e for e in ledger.events
               if e.stage.value == "capability" and e.outcome.value == "skipped"]
    assert skipped and "already spent" in skipped[-1].detail


@pytest.mark.parametrize("name", F.FIXTURES)
def test_a_finished_session_is_not_advanced_again_at_all(name):
    """The outer guard. A terminal session takes no further stages, so the firewall above is the
    second line rather than the only one."""
    session, stages = run(name)
    assert session.state in ("complete", "exhausted")
    assert coordinator._continue(session, stages) is session


def test_an_unsettled_fork_commissions_nothing_at_all():
    """Rejecting every option is an answer, and the answer is "none of these". Running one anyway
    would be choosing on the person's behalf after they declined to choose."""
    name = F.FIXTURES[0]
    stages = F.stages_for(name, capability=LockedFixtureCapability(), judge=J.judge)
    session = coordinator.new_session(prompt=F.prompt_for(name), refs=F.post_refs(name),
                                      mode="consult", now=AT)
    session = coordinator.begin(session, stages)
    request = coordinator.machine.from_dict(session.interaction).open_decision
    session = coordinator.resume(session, {
        "response_id": "r1", "session_id": session.session_id,
        "decision_id": request.decision_id, "expected_revision": session.revision,
        "kind": "reject_all", "at": AT}, stages)

    assert session.capability_receipts == []
    skipped = [e for e in session.stages
               if e.stage.value == "capability" and e.outcome.value == "skipped"]
    assert skipped and "on anybody's behalf" in skipped[-1].detail


# ── what the adapter will and will not stand in for ──────────────────────────

def test_the_adapter_names_what_it_serves_and_refuses_the_rest_as_a_gap():
    adapter = LockedFixtureCapability()
    assert set(SERVABLE_CLASSES) == {"extent", "geometry"}
    for served in SERVABLE_CLASSES:
        assert adapter.serves([served])
    for unserved in ("pattern", "scalar_field", "vector_field", "depth", "colour",
                     "semantic_reading", "external_source", "topology"):
        assert not adapter.serves([unserved])
        receipt = adapter.__class__().invoke(
            session_id="inqs_1", at=AT, observable=an_observable(capability_classes=[unserved]))
        assert receipt.status is ReceiptStatus.CAPABILITY_GAP
        assert "nothing to run" in receipt.detail


def test_the_chosen_route_decides_what_runs_not_the_observables_whole_union():
    """An observable declares every class that could bear on its claim; the fork picks one. Reading
    the union would refuse a route the person explicitly chose because a DIFFERENT route off the
    same observable needs an instrument nothing has."""
    observable = an_observable(capability_classes=["geometry", "vector_field"])
    alternative = {"alternative_id": "alt_1", "label": "the geometry route",
                   "capability_classes": ["geometry"]}
    receipt = LockedFixtureCapability().invoke(session_id="inqs_1", observable=observable,
                                               alternative=alternative, at=AT)
    assert receipt.status is ReceiptStatus.SIMULATED


def test_the_same_request_produces_the_same_numbers_twice():
    """Deterministic, so a replay comparison is a real check rather than one that has to exclude
    this payload."""
    a = LockedFixtureCapability().invoke(session_id="inqs_1", observable=an_observable(), at=AT)
    b = LockedFixtureCapability().invoke(session_id="inqs_1", observable=an_observable(), at="later")
    assert a.payload == b.payload
    assert a.receipt_id == b.receipt_id


def test_two_different_sessions_do_not_share_a_receipt_id():
    a = LockedFixtureCapability().invoke(session_id="inqs_1", observable=an_observable(), at=AT)
    b = LockedFixtureCapability().invoke(session_id="inqs_2", observable=an_observable(), at=AT)
    assert a.receipt_id != b.receipt_id


# ── the judge ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", F.FIXTURES)
def test_every_claim_gets_a_verdict_including_the_ones_nobody_looked_at(name):
    session, _ = run(name)
    claims = [c["claim_id"] for c in session.graph["claims"]]
    assert sorted(v.claim_ref for v in session.verdicts) == sorted(claims)


@pytest.mark.parametrize("name", F.FIXTURES)
def test_no_claim_is_ever_supported_in_phase_one(name):
    session, _ = run(name)
    assert not [v for v in session.verdicts if v.outcome in SUPPORTED_VERDICTS]
    assert session.evidence == []


@pytest.mark.parametrize("name", F.FIXTURES)
def test_the_receipt_moves_its_claim_from_nobody_asked_to_nothing_came_back(name):
    """The one thing a simulated receipt is allowed to change, and the exact size of the change."""
    session, _ = run(name)
    receipt = session.capability_receipts[0]
    observable = next(o for o in session.graph["observables"]
                      if o["observable_id"] == receipt.request_ref)
    verdict = session.verdict_for(observable["claim_id"])
    assert verdict.outcome is ClaimVerdictOutcome.UNRESOLVED
    assert receipt.receipt_id in verdict.receipt_refs
    assert verdict.evidence_refs == []
    assert "declared simulation" in verdict.why


def test_a_verdict_claiming_support_with_no_evidence_cannot_be_constructed():
    from backend.schemas.inquiry_session import ClaimVerdict
    with pytest.raises(ValidationError, match="cites no evidence"):
        ClaimVerdict(verdict_id="vrd_1", claim_ref="clm_1",
                     outcome=ClaimVerdictOutcome.SUPPORTED_BY_EVIDENCE, why="because")


def test_an_interpretive_claim_stays_interpretive_however_much_ran():
    """A claim asking to be read rather than measured is not the weaker for having no measurement.
    A receipt against it does not move it, because the receipt was never the kind of thing that
    could have settled it."""
    graph = {"claims": [{"claim_id": "clm_1", "epistemic_demand": "interpretive"}],
             "observables": [an_observable()]}
    verdict = J.judge_claim(graph["claims"][0], session_id="inqs_1", graph=graph,
                            receipts=[LockedFixtureCapability().invoke(
                                session_id="inqs_1", observable=an_observable(), at=AT)],
                            evidence=[])
    assert verdict.outcome is ClaimVerdictOutcome.INTERPRETIVE_ONLY


def test_a_claim_with_no_observable_is_not_investigated_rather_than_unresolved():
    graph = {"claims": [{"claim_id": "clm_1", "epistemic_demand": "measurable"}], "observables": []}
    verdict = J.judge_claim(graph["claims"][0], session_id="inqs_1", graph=graph,
                            receipts=[], evidence=[])
    assert verdict.outcome is ClaimVerdictOutcome.NOT_INVESTIGATED
    assert "nothing to ask" in verdict.why


def test_a_capability_gap_is_not_investigated_and_says_retrying_will_not_help():
    graph = {"claims": [{"claim_id": "clm_1", "epistemic_demand": "measurable"}],
             "observables": [an_observable(capability_classes=["depth"])]}
    receipt = LockedFixtureCapability().invoke(
        session_id="inqs_1", at=AT, observable=an_observable(capability_classes=["depth"]))
    verdict = J.judge_claim(graph["claims"][0], session_id="inqs_1", graph=graph,
                            receipts=[receipt], evidence=[])
    assert verdict.outcome is ClaimVerdictOutcome.NOT_INVESTIGATED
    assert "nothing was attempted" in verdict.why


def test_the_three_evidence_outcomes_are_implemented_and_not_merely_declared():
    """Unreachable in Phase 1 because nothing mints evidence. Written and tested anyway: an outcome
    that exists only in an enum is one nobody has checked the logic for, and Phase 2's first act is
    to make one of them reachable."""
    graph = {"claims": [{"claim_id": "clm_1", "epistemic_demand": "measurable"}],
             "observables": [an_observable()]}

    def verdict_with(stance):
        return J.judge_claim(graph["claims"][0], session_id="inqs_1", graph=graph, receipts=[],
                             evidence=[{"evidence_id": "evd_1", "claim_refs": ["clm_1"],
                                        "usable_as_evidence": True, "stance": stance}]).outcome

    assert verdict_with("supports") is ClaimVerdictOutcome.SUPPORTED_BY_EVIDENCE
    assert verdict_with("complicates") is ClaimVerdictOutcome.PARTIALLY_SUPPORTED
    assert verdict_with("refutes") is ClaimVerdictOutcome.CONTRADICTED


def test_evidence_that_is_not_usable_does_not_support_anything():
    graph = {"claims": [{"claim_id": "clm_1", "epistemic_demand": "measurable"}],
             "observables": [an_observable()]}
    verdict = J.judge_claim(graph["claims"][0], session_id="inqs_1", graph=graph, receipts=[],
                            evidence=[{"evidence_id": "evd_1", "claim_refs": ["clm_1"],
                                       "usable_as_evidence": False, "stance": "supports"}])
    assert verdict.outcome not in SUPPORTED_VERDICTS


def test_an_evidence_object_minted_from_a_fixture_receipt_cannot_be_put_on_a_session():
    """The envelope's own guard, in the other direction from the receipt's. Neither is redundant:
    a receipt cannot see the evidence list."""
    session, _ = run(F.FIXTURES[0])
    receipt = session.capability_receipts[0]
    payload = session.model_dump(mode="json")
    payload["evidence"] = [{"evidence_id": "evd_1", "claim_refs": ["clm_1"],
                            "receipt_ref": receipt.receipt_id}]
    with pytest.raises(ValidationError, match="cannot become"):
        SemanticInquirySession.model_validate(payload)


# ── the whole chain, both modes ──────────────────────────────────────────────

@pytest.mark.parametrize("name", F.FIXTURES)
def test_auto_mode_settles_the_fork_itself_now_that_a_route_can_be_simulated(name):
    """The `unresolved` of the previous commit becomes `auto_resolved` here, and the reason is
    structural: an option whose whole downstream consequence is one simulated receipt is reversible,
    and that is declared narrowly and stamped with who declared it."""
    session, _ = run(name, mode="auto")
    records = coordinator.machine.from_dict(session.interaction).records
    assert [r.outcome for r in records] == ["auto_resolved"]
    assert records[0].actor.value == "policy"
    assert "reversible" in records[0].reason
    assert len(session.capability_receipts) == 1


@pytest.mark.parametrize("name", F.FIXTURES)
def test_both_modes_reach_the_same_receipt_and_the_same_verdicts(name):
    """The mode changes who decided, not what the machinery is."""
    consult, _ = run(name, mode="consult")
    auto, _ = run(name, mode="auto")
    assert [r.status for r in consult.capability_receipts] == \
           [r.status for r in auto.capability_receipts]
    assert J.tally(consult.verdicts) == J.tally(auto.verdicts)


@pytest.mark.parametrize("name", F.FIXTURES)
def test_the_five_barren_stage_outcomes_stay_distinguishable(name):
    session, _ = run(name)
    outcomes = {e.outcome.value for e in session.stages}
    assert "completed" in outcomes
    # Nothing collapsed `skipped`, `empty`, `unavailable` and `refused` into one word on the way.
    assert outcomes <= {"started", "completed", "empty", "unavailable", "refused", "skipped",
                        "error"}
