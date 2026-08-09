"""
HARNESS-002B §1 — the contract and the strict types, and the parity between them.

A contract that lives in JSON and a code path that restates it are two vocabularies which agree
until somebody edits one. Every closed set below is asserted equal in both places, in both
directions — a set the code has and the contract does not is as much a divergence as the reverse,
and only one of the two directions is the one people remember to test.
"""
from __future__ import annotations

import json
import pathlib

import pytest
from pydantic import ValidationError

from backend.schemas import inquiry_interaction as sc

CONTRACT = pathlib.Path(__file__).resolve().parents[2] / "contracts" / "inquiry-interaction.v1.json"
STAMP = "2026-01-01T00:00:00+00:00"


@pytest.fixture(scope="module")
def contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _option(**over):
    base = {"option_id": "opt_a", "label": "A", "consequence": "does a"}
    base.update(over)
    return sc.DecisionOption(**base)


def _request(**over):
    base = {"decision_id": "dec_1", "session_id": "inqs_1", "revision": 1,
            "kind": sc.DecisionKind.CHOOSE_SCOPE, "question": "a or b?",
            "why_now": "they measure different things", "created_at": STAMP,
            "options": [_option(), _option(option_id="opt_b", label="B", consequence="does b")]}
    base.update(over)
    return sc.DecisionRequest(**base)


# ── the contract exists and is the version this code enforces ────────────────

def test_the_contract_is_present_and_pinned(contract):
    assert contract["schema_version"] == sc.SCHEMA_VERSION


def test_every_closed_set_matches_the_enum_in_both_directions(contract):
    """Parity, both ways. A code-only value is a vocabulary the frontend cannot render; a
    contract-only value is one the backend will refuse at runtime with no test having said so."""
    pairs = [
        ("interaction_modes", sc.InteractionMode),
        ("session_states", sc.SessionState),
        ("decision_kinds", sc.DecisionKind),
        ("response_kinds", sc.ResponseKind),
        ("amendment_relations", sc.AmendmentRelation),
        ("actors", sc.Actor),
        ("event_kinds", sc.EventKind),
    ]
    for key, enum in pairs:
        declared = set(contract["closed_sets"][key])
        in_code = {member.value for member in enum}
        assert declared == in_code, (
            f"{key}: contract-only={sorted(declared - in_code)} "
            f"code-only={sorted(in_code - declared)}")


def test_the_contract_names_the_actor_the_goal_engines_log_uses(contract):
    """The two logs sit beside each other, so the person has to be the same person in both. The
    mapping is stated rather than assumed, because `user` and `curator` reading as obviously the
    same is exactly how two ids for one actor survive a review."""
    from backend.services.inquiry_engine import events as ev
    mapping = contract["engine_actor_of"]
    assert mapping["user"] == ev.ACTOR_CURATOR
    assert set(mapping) == {m.value for m in sc.Actor}
    assert set(mapping.values()) <= {ev.ACTOR_ENGINE, ev.ACTOR_DIRECTOR, ev.ACTOR_AGENT,
                                     ev.ACTOR_CURATOR}


def test_the_contract_states_the_tie_rule_rather_than_leaving_it_to_the_code(contract):
    """The one rule most likely to be quietly relaxed by whoever next needs auto mode to be
    smoother. It is in the contract so that relaxing it is a visible diff."""
    on_tie = contract["auto_choice_conditions"]["on_tie"].lower()
    assert "never choose by list order" in on_tie
    assert "unresolved" in on_tie


# ── ids are derived, not minted ──────────────────────────────────────────────

def test_ids_are_a_function_of_their_content_and_nothing_else():
    """Replay is a required proof, and an id drawn from a clock or a uuid would make two runs of
    one session differ in the field a reader uses to line them up."""
    a = sc.decision_id("inqs_1", 3, "cnd_x")
    b = sc.decision_id("inqs_1", 3, "cnd_x")
    assert a == b and a.startswith("dec_")
    assert sc.decision_id("inqs_1", 4, "cnd_x") != a
    assert sc.decision_id("inqs_2", 3, "cnd_x") != a


def test_a_graph_hash_ignores_key_order_and_notices_a_value():
    assert sc.graph_hash({"a": 1, "b": 2}) == sc.graph_hash({"b": 2, "a": 1})
    assert sc.graph_hash({"a": 1}) != sc.graph_hash({"a": 2})


# ── strictness ───────────────────────────────────────────────────────────────

def test_an_undeclared_field_is_refused_rather_than_ignored():
    with pytest.raises(ValidationError):
        _request(epistemic_status="measured")


def test_an_option_that_never_declared_reversibility_is_not_thereby_reversible():
    """THE DEFAULT THAT DECIDES EVERYTHING. `None` is not `True`, and `auto_eligible` reads it as
    a block. A default of True here would auto-choose every under-specified candidate."""
    undeclared = _option(recommended=True)
    assert undeclared.reversible is None
    assert undeclared.auto_eligible is False
    assert _option(recommended=True, reversible=True).auto_eligible is True


def test_an_option_that_is_authorial_or_ledger_accepting_is_never_auto_eligible():
    assert _option(recommended=True, reversible=True, authorial=True).auto_eligible is False
    assert _option(recommended=True, reversible=True,
                   accepts_to_ledger=True).auto_eligible is False


def test_two_options_sharing_an_id_are_refused():
    """A reply names an option by id. Two options with one id would be disambiguated by list
    order — the same silent tie-break the policy refuses one layer up."""
    with pytest.raises(ValidationError, match="option_id"):
        _request(options=[_option(), _option(label="B")])


def test_a_request_with_no_options_and_no_free_text_is_not_a_question():
    with pytest.raises(ValidationError, match="not a question"):
        _request(options=[], allow_free_text=False)


# ── the honesty guards on the two user-authored objects ──────────────────────

@pytest.mark.parametrize("key", sorted(sc.STATUS_KEYS))
def test_a_response_provenance_cannot_carry_an_epistemic_status(key):
    with pytest.raises(ValidationError, match="never changes what anything is known by"):
        sc.DecisionResponse(response_id="rsp_1", session_id="inqs_1", decision_id="dec_1",
                            expected_revision=1, kind=sc.ResponseKind.SELECT_OPTION,
                            option_id="opt_a", at=STAMP, provenance={key: "measured"})


def test_a_response_provenance_that_carries_no_status_is_accepted():
    """The negative control: prove the guard admits what it should, or 'it refused' says nothing
    about what it refuses ON."""
    ok = sc.DecisionResponse(response_id="rsp_1", session_id="inqs_1", decision_id="dec_1",
                             expected_revision=1, kind=sc.ResponseKind.SELECT_OPTION,
                             option_id="opt_a", at=STAMP,
                             provenance={"client": "workbench", "latency_ms": 12})
    assert ok.provenance["client"] == "workbench"


@pytest.mark.parametrize("key", sorted(sc.STATUS_KEYS))
def test_an_amendment_provenance_cannot_carry_an_epistemic_status(key):
    with pytest.raises(ValidationError):
        sc.UserAmendment(amendment_id="amd_1", session_id="inqs_1", target_ref="clm_1",
                         text="not a portico", at=STAMP, provenance={key: "visible"})


def test_an_amendment_cannot_be_authored_by_anything_but_the_person():
    """A policy-authored 'amendment' would be the machine editing the graph while wearing the
    user's attribution — the one thing this object exists to make impossible."""
    for actor in (sc.Actor.POLICY, sc.Actor.STEWARD, sc.Actor.ENGINE):
        with pytest.raises(ValidationError):
            sc.UserAmendment(amendment_id="amd_1", session_id="inqs_1", target_ref="clm_1",
                             text="not a portico", at=STAMP, actor=actor)


def test_an_amendment_has_no_field_an_epistemic_status_could_travel_in():
    """Structural rather than behavioural. The guard above refuses a status in provenance; this
    asserts there is no OTHER field it could have gone in, which is the claim that actually
    matters and the one a new field would silently break."""
    fields = set(sc.UserAmendment.model_fields)
    assert not (fields & sc.STATUS_KEYS), f"a status could travel in {sorted(fields & sc.STATUS_KEYS)}"
    assert fields == {"amendment_id", "session_id", "decision_id", "target_ref", "text",
                      "relation", "actor", "at", "provenance"}


def test_a_response_must_say_what_it_needs_to():
    for bad in (
        {"kind": sc.ResponseKind.SELECT_OPTION},                       # names no option
        {"kind": sc.ResponseKind.REDIRECT},                            # no direction
        {"kind": sc.ResponseKind.AMEND, "free_text": "x"},             # no target
        {"kind": sc.ResponseKind.AMEND, "amendment_target": "clm_1"},  # no text
    ):
        with pytest.raises(ValidationError):
            sc.DecisionResponse(response_id="rsp_1", session_id="inqs_1", decision_id="dec_1",
                                expected_revision=1, at=STAMP, **bad)


# ── the state invariant ──────────────────────────────────────────────────────

def test_awaiting_user_with_nothing_open_is_refused():
    """A session that says it is waiting and names nothing to answer cannot be answered, and would
    sit there looking live. `run_store.is_answerable` holds the same rule one layer down."""
    with pytest.raises(ValidationError, match="cannot be answered"):
        sc.InquiryInteractionState(session_id="inqs_1", state=sc.SessionState.AWAITING_USER)


def test_an_open_decision_while_not_waiting_is_refused():
    with pytest.raises(ValidationError, match="answerable after the session"):
        sc.InquiryInteractionState(session_id="inqs_1", state=sc.SessionState.READY,
                                   open_decision_id="dec_1")


def test_a_state_round_trips_with_no_field_loss():
    state = sc.InquiryInteractionState(session_id="inqs_1", inquiry_id="inq_1",
                                       mode=sc.InteractionMode.STEP, created_at=STAMP)
    dumped = state.model_dump(mode="json")
    assert sc.InquiryInteractionState(**dumped).model_dump(mode="json") == dumped
