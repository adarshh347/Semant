"""
HARNESS-002B §2 — when a person is asked, proved on two subject matters that share no vocabulary.

THE FIXTURE PAIR IS PART OF THE TEST. A municipal water survey and a warehouse stock
reconciliation. If the policy had a branch that depended on the repository's running example, one
of these two would behave differently from the other, and asserting the same rule on both is what
makes "domain-neutral" a check rather than a claim.

The rule this file exists to hold: the interesting cases are the ones where auto mode DOES NOT
choose. A policy that chooses well is ordinary; a policy that declines to choose for a stated,
distinguishable reason is the whole deliverable.
"""
from __future__ import annotations

import pytest

from backend.schemas.inquiry_interaction import DecisionKind, InteractionMode
from backend.services.inquiry_interaction import candidates as cand
from backend.services.inquiry_interaction import fixtures as fx
from backend.services.inquiry_interaction import policy as pol

MODES = (InteractionMode.AUTO, InteractionMode.CONSULT, InteractionMode.STEP)


def verdict(raw, mode):
    return pol.DeliberationPolicy(mode=mode).verdict(cand.read(raw))


# ── the classification comes from the contract, totally ──────────────────────

def test_every_declared_kind_is_classified_by_the_contract():
    """A kind the contract does not classify would default to something, and the plausible default
    ('material', ask about it) is wrong in the one direction that matters: an unclassified
    `accept_to_ledger` treated as material is paused in consult and PASSED in auto."""
    table = pol.pause_class_of()
    assert set(table) == set(DecisionKind)
    assert set(table.values()) <= set(pol.PAUSE_CLASSES)


def test_the_two_gates_are_the_always_pause_class_and_nothing_else_is():
    gates = {k for k, v in pol.pause_class_of().items() if v == pol.CLASS_ALWAYS_PAUSE}
    assert gates == {DecisionKind.AUTHOR_ACTION, DecisionKind.ACCEPT_TO_LEDGER}
    assert all(pol.is_gate(k) for k in gates)
    assert not any(pol.is_gate(k) for k in set(DecisionKind) - gates)


# ── auto mode: chooses when it may, and says why when it may not ─────────────

def test_auto_takes_a_single_recommended_reversible_option_and_records_the_alternatives():
    v = verdict(fx.survey_scope_candidate(), InteractionMode.AUTO)
    assert v.outcome == pol.OUTCOME_AUTO
    assert v.option_id == "opt_eastern"
    # The road not taken is on the record. An auto decision without its alternatives is
    # indistinguishable from a fork that never existed.
    assert v.alternatives == ("opt_district",)
    assert "reversible" in v.reason


def test_auto_refuses_a_tie_rather_than_taking_the_first_option():
    """THE CASE THIS MODULE IS ARRANGED AROUND. Two equally recommended options; the list order
    would answer it, and a preference decided by list order is one nobody stated, nobody can
    review and nobody can even see."""
    v = verdict(fx.survey_tie_candidate(), InteractionMode.AUTO)
    assert v.outcome == pol.OUTCOME_UNRESOLVED
    assert v.option_id == ""
    assert "list order" in v.reason
    assert "opt_peak" in v.reason and "opt_seasonal" in v.reason


def test_auto_refuses_an_option_that_never_declared_whether_it_can_be_undone():
    v = verdict(fx.survey_undeclared_candidate(), InteractionMode.AUTO)
    assert v.outcome == pol.OUTCOME_UNRESOLVED
    assert "undeclared reversibility is not a yes" in v.reason


def test_auto_refuses_when_nothing_is_recommended_and_says_so_differently_from_a_tie():
    """Two ways of not choosing, and the reasons must not read the same: 'they cannot agree' and
    'nobody put one forward' send a reader to different places."""
    none = verdict(fx.inventory_disambiguation_candidate(), InteractionMode.AUTO)
    tie = verdict(fx.survey_tie_candidate(), InteractionMode.AUTO)
    assert none.outcome == tie.outcome == pol.OUTCOME_UNRESOLVED
    assert "none of the" in none.reason
    assert none.reason != tie.reason


def test_auto_never_opens_a_user_wait_except_at_a_gate():
    """Auto mode's promise: no interruption. Everything it cannot settle becomes unresolved."""
    ordinary = [fx.survey_scope_candidate(), fx.survey_tie_candidate(),
                fx.survey_cost_candidate(), fx.survey_undeclared_candidate(),
                fx.inventory_disambiguation_candidate(), fx.inventory_review_candidate()]
    assert all(verdict(c, InteractionMode.AUTO).outcome != pol.OUTCOME_PAUSE for c in ordinary)


# ── the gates: every mode, including auto ────────────────────────────────────

@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("raw", [fx.survey_ledger_candidate, fx.inventory_author_candidate],
                         ids=["accept_to_ledger", "author_action"])
def test_every_mode_pauses_at_an_author_or_ledger_gate(mode, raw):
    """Proved on both fixtures, so the rule is not carried by one domain's wording. Both gates
    offer a recommended, reversible option — the gate must win over eligibility, and a policy that
    checked eligibility first would pass exactly the two forks that are the person's alone."""
    v = verdict(raw(), mode)
    assert v.outcome == pol.OUTCOME_PAUSE
    assert v.pause_class == pol.CLASS_ALWAYS_PAUSE
    assert "gate" in v.reason


def test_the_ledger_gate_offers_an_option_that_would_otherwise_qualify():
    """The negative control for the test above: if the gate fixture had no eligible option, the
    pause would prove nothing about whether the gate rule ran at all."""
    accept = cand.read(fx.survey_ledger_candidate()).option("opt_accept")
    assert accept.recommended and accept.reversible is True
    assert accept.accepts_to_ledger is True


# ── consult mode: material pauses, deferrable passes with a record ───────────

@pytest.mark.parametrize("raw", [fx.survey_scope_candidate, fx.survey_tie_candidate,
                                 fx.inventory_disambiguation_candidate,
                                 fx.inventory_review_candidate])
def test_consult_pauses_at_every_material_fork(raw):
    v = verdict(raw(), InteractionMode.CONSULT)
    assert v.outcome == pol.OUTCOME_PAUSE
    assert v.pause_class == pol.CLASS_MATERIAL


def test_consult_passes_a_deferrable_fork_with_a_record_rather_than_interrupting():
    """'It does not ask questions merely because uncertainty exists.' A bounded reversible cost
    with one recommended option is not a fork worth a person's attention."""
    v = verdict(fx.survey_cost_candidate(), InteractionMode.CONSULT)
    assert v.outcome == pol.OUTCOME_AUTO
    assert v.option_id == "opt_current"
    assert v.pause_class == pol.CLASS_DEFERRABLE


def test_consult_pauses_at_a_deferrable_fork_whose_option_does_not_qualify():
    """The same kind, the other way. What decides is the option, not the classification alone."""
    raw = fx.survey_cost_candidate()
    raw["options"][0].pop("reversible")
    v = verdict(raw, InteractionMode.CONSULT)
    assert v.outcome == pol.OUTCOME_PAUSE
    assert "no option qualified" in v.reason


# ── step mode: every declared fork ───────────────────────────────────────────

@pytest.mark.parametrize("raw", [fx.survey_scope_candidate, fx.survey_cost_candidate,
                                 fx.survey_tie_candidate, fx.survey_undeclared_candidate,
                                 fx.inventory_disambiguation_candidate,
                                 fx.inventory_review_candidate])
def test_step_pauses_at_every_candidate_including_ones_the_others_would_pass(raw):
    v = verdict(raw(), InteractionMode.STEP)
    assert v.outcome == pol.OUTCOME_PAUSE
    assert "every declared fork" in v.reason


# ── the policy is deterministic and stateless ────────────────────────────────

@pytest.mark.parametrize("mode", MODES)
def test_the_same_candidate_yields_the_same_verdict_every_time(mode):
    raw = fx.survey_scope_candidate()
    first = verdict(raw, mode)
    for _ in range(5):
        assert verdict(fx.survey_scope_candidate(), mode) == first


def test_the_verdict_does_not_depend_on_the_order_options_were_listed():
    """If it did, the tie rule would be the only place list order was refused while every other
    path quietly depended on it."""
    raw = fx.survey_scope_candidate()
    flipped = dict(raw, options=list(reversed(raw["options"])))
    a = verdict(raw, InteractionMode.AUTO)
    b = verdict(flipped, InteractionMode.AUTO)
    assert a.outcome == b.outcome and a.option_id == b.option_id


# ── reading a candidate: the kind is READ, never inferred ────────────────────

def test_an_unknown_kind_is_refused_by_name_rather_than_mapped_to_a_neighbour():
    raw = dict(fx.survey_scope_candidate(), kind="choose_the_scope")
    with pytest.raises(cand.CandidateUnreadable, match="not one of") as exc:
        cand.read(raw)
    assert exc.value.code == cand.REFUSAL_CANDIDATE_KIND_UNKNOWN


def test_a_missing_kind_is_refused_and_does_not_default_to_an_ordinary_fork():
    raw = fx.survey_ledger_candidate()
    raw.pop("kind")
    with pytest.raises(cand.CandidateUnreadable, match="read and never guessed"):
        cand.read(raw)


def test_the_kind_is_not_inferred_from_the_question_text():
    """The HARNESS-001B2 defect, in its next available costume: a kind re-derived from wording
    instead of read. There, `fold` matched inside `unfolding` and a clause the framer had refused
    to operationalise arrived downstream as MEASURED, with nothing raising. Here, a question full
    of ledger language on a declared `choose_scope` must stay `choose_scope` — and, the half that
    would actually hurt, the reverse must not be talked out of its gate."""
    scope = cand.read(dict(fx.survey_scope_candidate(),
                           question="Accept this into the shared ledger as the authored record?"))
    assert scope.kind is DecisionKind.CHOOSE_SCOPE
    assert verdict(dict(fx.survey_scope_candidate(),
                        question="Accept this into the ledger?"),
                   InteractionMode.AUTO).outcome == pol.OUTCOME_AUTO

    gate = dict(fx.survey_ledger_candidate(), question="Which wells should the series cover?")
    assert cand.read(gate).kind is DecisionKind.ACCEPT_TO_LEDGER
    assert verdict(gate, InteractionMode.AUTO).outcome == pol.OUTCOME_PAUSE


def test_an_option_without_a_consequence_is_refused():
    """An option that does not say what it changes is a label, and a person asked to pick between
    labels is being consulted in appearance only."""
    raw = fx.survey_scope_candidate()
    raw["options"][0].pop("consequence")
    with pytest.raises(cand.CandidateUnreadable, match="consulted in appearance only"):
        cand.read(raw)


def test_a_candidate_offering_nothing_and_taking_no_text_is_refused_at_the_door():
    """`DecisionRequest` refuses to be built from this, so catching it here is the difference
    between one refused candidate and a validation error mid-drain that takes every later
    candidate in the batch down with it."""
    raw = dict(fx.survey_scope_candidate(), options=[], allow_free_text=False)
    with pytest.raises(cand.CandidateUnreadable, match="nothing a person could say"):
        cand.read(raw)


def test_a_candidate_with_no_options_but_free_text_is_still_a_question():
    """The negative control: what makes the refusal above about the PAIR rather than about having
    no options, which is legitimate — 'what should I do instead?' is a real fork."""
    raw = dict(fx.survey_scope_candidate(), options=[], allow_free_text=True)
    assert cand.read(raw).options == ()


def test_read_refuses_everything_the_request_type_would_have_refused():
    """The claim that makes the drain loop safe: `read` is the validation boundary, and a candidate
    it accepts can always be formed into a request. Checked against the request type's own rules
    rather than by listing them again — a rule added there and not here would reopen exactly the
    crash the fix closed."""
    for raw in (dict(fx.survey_scope_candidate(), options=[], allow_free_text=False),
                dict(fx.survey_scope_candidate(), question=""),
                dict(fx.survey_scope_candidate(),
                     options=[fx.survey_scope_candidate()["options"][0]] * 2)):
        with pytest.raises(cand.CandidateUnreadable):
            cand.read(raw)


def test_the_preserved_mapping_does_not_move_when_the_producer_reuses_its_own_object():
    """`raw` is what a paraphrase is checked against. A shallow copy shares every nested list with
    the caller, so a producer that reused and mutated its candidate would retroactively change what
    this lane recorded it as having said."""
    raw = fx.survey_scope_candidate()
    read = cand.read(raw)
    raw["options"][0]["consequence"] = "something else entirely"
    raw["affected_refs"].append("clm_invented")
    assert read.raw["options"][0]["consequence"].startswith("reads the four eastern wells")
    assert "clm_invented" not in read.raw["affected_refs"]


def test_the_original_mapping_is_preserved_verbatim_on_the_candidate():
    """This lane paraphrases; `raw` is what the paraphrase can be checked against. Without it the
    steward would be unfalsifiable."""
    raw = dict(fx.survey_scope_candidate(), some_field_this_lane_does_not_read=["a", "b"])
    read = cand.read(raw)
    assert read.raw == raw
    assert read.raw["some_field_this_lane_does_not_read"] == ["a", "b"]


def test_a_batch_keeps_the_readable_ones_and_the_refusals_both():
    """A session that dropped four readable candidates because the third was malformed would be as
    wrong as one that dropped the third without saying so."""
    good, bad = cand.read_all([fx.survey_scope_candidate(), {"id": "x", "kind": "nope"},
                               fx.inventory_review_candidate()])
    assert [c.candidate_id for c in good] == ["cnd_survey_scope", "cnd_inventory_review"]
    assert [r.code for r in bad] == [cand.REFUSAL_CANDIDATE_KIND_UNKNOWN]


# ── the two fixtures really are domain-neutral ───────────────────────────────

def test_neither_fixture_uses_the_repositorys_running_example_vocabulary():
    """The check that makes the pair worth having. If a policy branch depended on the visual-art
    example, these fixtures could not exercise it — so they must not contain it."""
    import json
    blob = json.dumps([fx.survey_graph(), fx.survey_batch(), fx.survey_ledger_candidate(),
                       fx.inventory_graph(), fx.inventory_disambiguation_candidate(),
                       fx.inventory_author_candidate(),
                       fx.inventory_review_candidate()]).lower()
    for word in ("fold", "sculpture", "ottoman", "pantheon", "ajanta", "drapery", "region",
                 "mask", "percept", "image", "renaissance", "buddha"):
        assert word not in blob, f"the fixtures name {word!r}"


def test_the_two_fixtures_share_no_subject_vocabulary_with_each_other():
    import json
    survey = json.dumps([fx.survey_graph(), fx.survey_batch()]).lower()
    inventory = json.dumps([fx.inventory_graph(),
                            fx.inventory_disambiguation_candidate()]).lower()
    for word in ("well", "nitrate", "drainage", "district"):
        assert word in survey and word not in inventory
    for word in ("pallet", "manifest", "shortfall", "bay"):
        assert word in inventory and word not in survey

