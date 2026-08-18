"""
HARNESS-003F — the declared vertical-slice scope, proved.

The lane's whole risk in one sentence: a bounded run produces FEWER claims, fewer observables and
sometimes none, so a scoped result that does not announce itself reads as a thin one — and a thin
result is evidence about the images. Every test here is a way that could happen, or a way the bound
could quietly stop being a bound.

THE ONE THING NONE OF THESE PROVE is that a slice produces a good answer. It is not supposed to.
`full_coverage: false` is on the record so that improvement cannot be claimed from a smaller
question, and §8's live rehearsal is where usefulness is judged by a person.
"""
from __future__ import annotations

import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import inquiries as R
from backend.schemas.semantic_compilation import (SCOPE_DEFERRED_REASON,
                                                  SCOPE_PURPOSE_VERTICAL_FLOW, DispositionKind,
                                                  DissolutionPass, ExecutionScope,
                                                  ExecutionScopeRecord, ItemDispositionKind,
                                                  ScopeExclusion, SourceUnitKind)
from backend.services.inquiry_session import coordinator, corpus, runtime, store, view
from backend.services.inquiry_session.capability import LockedFixtureCapability
from backend.services.inquiry_session.composer import DeterministicComposer
from backend.services.inquiry_session.judge import judge
from backend.services.semantic_compilation import ledger, scope, sizing
from backend.services.semantic_compilation.architect import ARCHITECT_COMPLETION, fixed_prompt_text
from backend.tests.fixtures import inquiry_session_fixtures as F

AT = "2026-08-09T00:00:00+00:00"

#: The allowance at which the fold fixture's slice actually BITES — units deferred, atoms no
#: relation request reaches, a claim nothing is asked about — while still building a claim. Declared
#: here rather than inherited, so these tests mean the same thing on every box.
BITING_ALLOWANCE = "4500"

#: Both dissolution fixtures. The second shares no noun with the first, and every test that takes
#: this parameter is asserting the selector's behaviour is a property of STRUCTURE rather than of
#: subject — which is the claim §3 makes and the one a topic-blind selector has to earn.
FIXTURES = list(F.DISSOLUTION_FIXTURES)


@pytest.fixture
def enabled(monkeypatch):
    """The feature on, with this lane's declared bounds and the biting allowance."""
    monkeypatch.setenv(scope.ENABLED_ENV, "1")
    monkeypatch.setenv(sizing.ALLOWANCE_ENV, BITING_ALLOWANCE)
    monkeypatch.setenv(scope.MAX_RELATION_BATCHES_ENV, "1")
    monkeypatch.setenv(scope.MAX_OPERATIONALIZER_BATCHES_ENV, "2")
    monkeypatch.setenv(scope.MAX_RECONCILIATION_ROUNDS_ENV, "0")


def _run(name, *, execution_scope="full"):
    stages = F.dissolution_stages_for(name, capability=LockedFixtureCapability(), judge=judge,
                                      composer=DeterministicComposer(), clock=F.frozen_clock(AT))
    session = coordinator.new_session(
        prompt=F.dissolution_prompt_for(name), refs=F.dissolution_post_refs(name), mode="auto",
        now=AT, execution_scope=execution_scope)
    return coordinator.begin(session, stages), stages


def _scope_of(session) -> dict:
    return session.graph.get("execution_scope") or {}


def _plan(session, pass_name: DissolutionPass) -> dict:
    receipt = next((p for p in session.graph["passes"]
                    if p["pass_name"] == pass_name.value), None)
    return (receipt or {}).get("batch_plan") or {}


# ── the gate ─────────────────────────────────────────────────────────────────

def test_the_feature_defaults_off(monkeypatch):
    """No environment, no scope. A temporary contract that arrived switched on would be permanent
    by the time anybody noticed."""
    monkeypatch.delenv(scope.ENABLED_ENV, raising=False)
    assert scope.feature_enabled() is False
    with pytest.raises(scope.ScopeRefused) as raised:
        scope.parse("vertical_slice")
    assert raised.value.code == "scoped_rehearsal_disabled"
    # AND IT DOES NOT FALL BACK. The exception is the whole point: returning `FULL` here would run
    # a different inquiry from the one that was asked for and say nothing about it.
    assert scope.parse("full") is ExecutionScope.FULL


def test_a_half_set_flag_gets_the_safe_answer(monkeypatch):
    for value in ("", " ", "0", "false", "no", "off", "maybe", "2"):
        monkeypatch.setenv(scope.ENABLED_ENV, value)
        assert scope.feature_enabled() is (value in ("1",)), value


def test_an_unknown_scope_is_refused_rather_than_rounded_to_full(monkeypatch):
    monkeypatch.setenv(scope.ENABLED_ENV, "1")
    with pytest.raises(scope.ScopeRefused) as raised:
        scope.parse("quarter_slice")
    assert raised.value.code == "unknown_execution_scope"
    assert "quarter_slice" in raised.value.requested


def test_outside_a_slice_there_are_no_bounds_at_all(monkeypatch):
    """`None`, not a large number. A reader of `relation_batches_allowed: null` knows nothing was
    capped; a reader of `999` has to guess whether it was a bound nobody reached."""
    monkeypatch.setenv(scope.MAX_RELATION_BATCHES_ENV, "1")
    limits = scope.configured_limits(ExecutionScope.FULL)
    assert (limits.relation_batches, limits.operationalizer_batches,
            limits.reconciliation_rounds) == (None, None, None)
    assert limits.bounded is False


def test_zero_permitted_rounds_is_a_real_value_and_not_unlimited(monkeypatch):
    monkeypatch.setenv(scope.ENABLED_ENV, "1")
    monkeypatch.setenv(scope.MAX_RECONCILIATION_ROUNDS_ENV, "0")
    limits = scope.configured_limits(ExecutionScope.VERTICAL_SLICE)
    assert limits.reconciliation_rounds == 0
    assert limits.reconciliation_rounds is not None


# ── the record ───────────────────────────────────────────────────────────────

def test_a_slice_cannot_report_full_coverage():
    with pytest.raises(ValueError, match="declares full coverage"):
        ExecutionScopeRecord(mode=ExecutionScope.VERTICAL_SLICE, full_coverage=True,
                             purpose=SCOPE_PURPOSE_VERTICAL_FLOW)


def test_a_slice_cannot_declare_another_purpose():
    with pytest.raises(ValueError, match="only purpose"):
        ExecutionScopeRecord(mode=ExecutionScope.VERTICAL_SLICE, full_coverage=False,
                             purpose="making the answer look better")


def test_an_excluded_item_without_a_reason_is_unrepresentable():
    with pytest.raises(ValueError, match="carry no reason"):
        ExecutionScopeRecord(mode=ExecutionScope.VERTICAL_SLICE, full_coverage=False,
                             purpose=SCOPE_PURPOSE_VERTICAL_FLOW,
                             deferred_source_unit_ids=["su_1"])
    ok = ExecutionScopeRecord(
        mode=ExecutionScope.VERTICAL_SLICE, full_coverage=False,
        purpose=SCOPE_PURPOSE_VERTICAL_FLOW, deferred_source_unit_ids=["su_1"],
        exclusions=[ScopeExclusion(ref="su_1", kind="source_unit", reason="deferred")])
    assert ok.scope_version == "inquiry-execution-scope.v1"


# ── the selector ─────────────────────────────────────────────────────────────

def _ledger(prompt: str, images, blocks_per_image: int = 4):
    from backend.schemas.semantic_compilation import (CallTopology, ModelReceipt, ReadingBlock,
                                                      ReadingBlockKind, SceneReading)
    blocks = [ReadingBlock(block_id=f"blk_{img}_{n}", kind=ReadingBlockKind.PART,
                           text=f"a reading block about {img}, number {n}, long enough to cost a "
                                f"few tokens and stand in for a real one.",
                           image_refs=[img])
              for img in images for n in range(blocks_per_image)]
    reading = SceneReading(text="a summary", blocks=blocks,
                           provenance=ModelReceipt(role="scene_theorist", parsed=True,
                                                   call_topology=CallTopology.PER_IMAGE_THEN_SYNTHESIS))
    return ledger.build(prompt, reading, inquiry_id="inq_scope_test")[0]


PROMPT_A = ("the first reads as blunt; the second is carved so the cloth looks transparent -- the "
            "third shares some of that bluntness. what makes the difference")
PROMPT_B = ("the tracery in the first spins from a hub; the second holds its glass in a flatter "
            "web -- the nave beyond runs the light the other way. why do they differ")


@pytest.mark.parametrize("prompt", [PROMPT_A, PROMPT_B])
def test_the_same_input_selects_the_same_ids(prompt):
    units = _ledger(prompt, ["img_a", "img_b", "img_c"])
    first = scope.select_units(units, room_tokens=340)
    second = scope.select_units(list(units), room_tokens=340)
    assert [u.source_unit_id for u in first.selected] == [u.source_unit_id for u in second.selected]
    assert [e.reason for e in first.exclusions] == [e.reason for e in second.exclusions]
    # CONTENT-DERIVED, not positional: shuffling the ledger cannot change which unit is which, and
    # the ids are what a replay compares.
    assert all(u.source_unit_id for u in first.selected)


def test_the_selection_does_not_depend_on_the_subject():
    """The generality claim in the only form it can take: two prompts sharing no noun, one
    selector, the same SHAPE of answer."""
    a = scope.select_units(_ledger(PROMPT_A, ["x1", "x2", "x3"]), room_tokens=340)
    b = scope.select_units(_ledger(PROMPT_B, ["y1", "y2", "y3"]), room_tokens=340)
    # Same number of image groups reached, same policy on the person's own clauses.
    assert a.group_count == b.group_count
    assert (sum(1 for u in a.selected if u.is_user_authored) > 0
            and sum(1 for u in b.selected if u.is_user_authored) > 0)


def test_prompt_authored_units_are_never_silently_lost():
    """§3.1. The person's own words are the one thing in the ledger nothing else can supply, and a
    scope that spent its room on the reading would rehearse the model talking to itself."""
    units = _ledger(PROMPT_A, ["img_a", "img_b", "img_c"], blocks_per_image=8)
    clauses = [u for u in units if u.kind is SourceUnitKind.PROMPT_CLAUSE]
    assert len(clauses) >= 3
    picked = scope.select_units(units, room_tokens=400)
    assert {u.source_unit_id for u in clauses} <= {u.source_unit_id for u in picked.selected}
    # And where one genuinely does not fit, it is DEFERRED WITH A REASON rather than dropped.
    tiny = scope.select_units(units, room_tokens=40)
    assert {e.ref for e in tiny.exclusions} == {u.source_unit_id for u in tiny.deferred}
    assert all(e.reason.startswith(SCOPE_DEFERRED_REASON) for e in tiny.exclusions)


def test_selected_material_spans_the_images_where_capacity_permits():
    """§3.3. The ledger is the prompt, then image 1's blocks, then image 2's — so a budget filled
    in ledger order is a budget spent entirely on the first picture, and every relation this
    council exists to find is a comparison."""
    units = _ledger(PROMPT_A, ["img_a", "img_b", "img_c"])
    picked = scope.select_units(units, room_tokens=420)
    groups = {scope.group_of(u) for u in picked.selected if scope.group_of(u) != scope.PROMPT_GROUP}
    assert len(groups) >= 2, groups
    # THE COMPARISON WITH LEDGER ORDER, made explicit: taking units in ledger order until the same
    # budget ran out would have reached fewer pictures.
    naive, spent = [], 0
    for unit in units:
        cost = scope.projected_tokens(unit)
        if spent + cost <= 420:
            naive.append(unit)
            spent += cost
    naive_groups = {scope.group_of(u) for u in naive if scope.group_of(u) != scope.PROMPT_GROUP}
    assert len(groups) >= len(naive_groups)


def test_the_selection_is_returned_interleaved_rather_than_in_ledger_order():
    """§4's "place prompt-anchored and cross-image atoms together in the one relation batch".

    THE DEFECT THE FIRST LIVE REHEARSAL FOUND, and it was in this function's return statement. The
    selector round-robins across images and then used to re-sort the answer into ledger order —
    tidier, and it threw away the whole point: the ledger is the prompt, then image 1's blocks, then
    image 2's, so a re-sorted selection hands the dissector the prompt, then one picture, then the
    next, and a bounded architect fills its ONE permitted request from the front.

    Live, that produced 21 atoms in front of the model and every one of them from the PROMPT. No
    image atom reached the architect at all, so no cross-image relation was structurally possible.

    So the order is asserted, not the membership: prompt clauses first, then the images ROTATING.
    """
    units = _ledger(PROMPT_A, ["img_a", "img_b", "img_c"])
    picked = scope.select_units(units, room_tokens=500)
    groups = [scope.group_of(u) for u in picked.selected]
    prompt_run = [g for g in groups if g == scope.PROMPT_GROUP]
    assert groups[:len(prompt_run)] == prompt_run, groups

    images = groups[len(prompt_run):]
    assert len(set(images)) >= 2, images
    # NO IMAGE APPEARS TWICE BEFORE ANOTHER HAS APPEARED ONCE. That is the rotation, and it is what
    # makes a batch filled from the front span more than one picture.
    seen = []
    for index, key in enumerate(images):
        if key in seen:
            assert set(images[:index]) == set(seen), images
            break
        seen.append(key)
    assert len(seen) >= 2, images


def test_a_unit_is_deferred_whole_and_never_truncated():
    units = _ledger(PROMPT_A, ["img_a", "img_b"])
    picked = scope.select_units(units, room_tokens=300)
    quotes = {u.source_unit_id: u.exact_quote for u in units}
    for unit in picked.selected:
        assert unit.exact_quote == quotes[unit.source_unit_id]
    for unit in picked.deferred:
        assert unit.exact_quote == quotes[unit.source_unit_id]


def test_scope_py_is_inside_the_topic_vocabulary_scan():
    """§7. The tree already scans production sources for the rehearsal's own nouns — it caught a
    noun in this module's docstring the first time it ran. This asserts the scan POINTS at it, so a
    later refactor cannot move the selector out from under the guard without saying so."""
    from backend.tests.test_semantic_dissolution_fixtures import _production_sources
    names = {p.name for p in _production_sources()}
    assert "scope.py" in names, sorted(names)


# ── the pipeline, end to end ─────────────────────────────────────────────────

@pytest.mark.parametrize("name", FIXTURES)
def test_full_mode_is_byte_compatible_with_the_default(name):
    """The default path is untouched.

    THE COMPARISON IS THE GRAPH, not the session: `session_id` is minted per session and every
    stage-attempt id derives from it, so two runs of identical inputs legitimately differ there and
    always have. What must not differ is the COMPILATION — every unit, atom, claim, edge,
    observable, coverage entry, pass receipt and batch plan — with the additive scope key set aside.

    And the scope record on a full run must SAY `full` / `full_coverage: true` rather than be
    absent: "compiled before this contract existed" and "ran unbounded, and something checked" are
    different facts and a reader who cannot tell them apart can use neither.
    """
    default, _ = _run(name)
    declared, _ = _run(name, execution_scope="full")

    def graph_of(session):
        body = copy.deepcopy(session.graph)
        body.pop("execution_scope", None)
        return body

    assert graph_of(default) == graph_of(declared)
    # THE BOUND KEYWORDS WERE NEVER PASSED. `_bounds` yields an empty mapping outside a slice, so a
    # full run makes the same call it always made, argument for argument — which is what keeps every
    # frozen council and replay adapter that satisfies this seam working untouched.
    assert scope.configured_limits(ExecutionScope.FULL).bounded is False

    record = _scope_of(declared)
    assert record["mode"] == "full"
    assert record["full_coverage"] is True
    assert record["relation_batches_allowed"] is None
    assert record["exclusions"] == []


@pytest.mark.parametrize("name", FIXTURES)
def test_a_slice_cannot_report_full_coverage_end_to_end(name, enabled):
    session, _ = _run(name, execution_scope="vertical_slice")
    record = _scope_of(session)
    assert record["mode"] == "vertical_slice"
    assert record["full_coverage"] is False
    assert record["purpose"] == SCOPE_PURPOSE_VERTICAL_FLOW
    assert record["selection_producer"] == scope.PRODUCER
    assert record["allowance_tokens"] == int(BITING_ALLOWANCE)


@pytest.mark.parametrize("name", FIXTURES)
def test_the_declared_bounds_are_the_ones_that_were_spent(name, enabled):
    """§4's numbers, on the record and in the plans. One relation request, at most two
    operationalization requests, no reconciliation round at all."""
    session, _ = _run(name, execution_scope="vertical_slice")
    record = _scope_of(session)
    assert record["relation_batches_allowed"] == 1
    assert record["relation_batches_sent"] <= 1
    assert record["operationalizer_batches_allowed"] == 2
    assert record["operationalizer_batches_sent"] <= 2
    assert record["reconciliation_rounds_allowed"] == 0
    assert record["reconciliation_rounds_sent"] == 0

    relation = _plan(session, DissolutionPass.RELATION_ARCHITECT)
    if relation:
        assert relation["batches_sent"] <= 1
        # THE PARTITION IS NOT SHORTENED. Bounding the work is done by REPORTING what was not done,
        # so the plan still holds every batch it would have sent — and every atom in the ones it
        # did not is disposed a few tests down.
        assert len(relation["batches"]) >= relation["batches_sent"]


@pytest.mark.parametrize("name", FIXTURES)
def test_every_deferred_source_unit_is_retained_with_a_reason(name, enabled):
    session, _ = _run(name, execution_scope="vertical_slice")
    graph, record = session.graph, _scope_of(session)
    units = {u["source_unit_id"] for u in graph["source_units"]}
    deferred = set(record["deferred_source_unit_ids"])
    # STILL IN THE LEDGER. Nothing is deleted; a deferred unit keeps its id.
    assert deferred <= units
    coverage = {c["source_unit_id"]: c for c in graph["coverage"]}
    for unit_id in deferred:
        entry = coverage[unit_id]
        assert entry["disposition"] == DispositionKind.REFUSED.value
        # `refused`, never `semantic_remainder`: remainder is content nothing MEASURES, and this is
        # content nothing was ASKED about.
        assert entry["reason"].startswith(SCOPE_DEFERRED_REASON)


@pytest.mark.parametrize("name", FIXTURES)
def test_no_repair_is_aimed_at_a_deliberately_deferred_unit(name, enabled):
    """A targeted repair over a deferred unit would spend the allowance re-asking a question the
    run had already declared it was not asking."""
    session, _ = _run(name, execution_scope="vertical_slice")
    deferred = set(_scope_of(session)["deferred_source_unit_ids"])
    repair = next((p for p in session.graph["passes"]
                   if p["pass_name"] == DissolutionPass.TARGETED_REPAIR.value), None)
    if repair is None or not deferred:
        return
    for note in session.graph["notes"]:
        for unit_id in deferred:
            assert unit_id not in note or "deferred" in note


@pytest.mark.parametrize("name", FIXTURES)
def test_every_atom_and_claim_is_explicitly_disposed(name, enabled):
    """§7. Silence is not a disposition. An atom no relation request reached and a claim nothing was
    asked about are both `not_investigated` WITH A REASON, which is a decision a reader can point
    at — as against absence, which is a pass that lost track of its input."""
    session, _ = _run(name, execution_scope="vertical_slice")
    graph = session.graph
    for pass_name, key in ((DissolutionPass.RELATION_ARCHITECT, "semantic_atoms"),
                           (DissolutionPass.EPISTEMIC_OPERATIONALIZER, "claims")):
        plan = _plan(session, pass_name)
        if not plan:
            continue
        ids = {x["atom_id" if key == "semantic_atoms" else "claim_id"] for x in graph[key]}
        disposed = {d["ref"] for d in plan["dispositions"]}
        assert ids <= disposed, sorted(ids - disposed)
        for entry in plan["dispositions"]:
            if entry["disposition"] in (ItemDispositionKind.NOT_INVESTIGATED.value,
                                        ItemDispositionKind.REFUSED.value):
                assert entry["reason"].strip()


@pytest.mark.parametrize("name", FIXTURES)
def test_a_model_that_proposed_nothing_is_not_reported_as_a_bound(name, enabled):
    """The distinction this record got wrong on its first draft, and the reason it is structural.

    `not_investigated` has two causes: the model was ASKED and proposed nothing, and a declared
    bound meant NOBODY asked. Both are honest dispositions and both belong on the pass's plan. Only
    the second is something the scope did — and a record that listed the first would report a
    model's silence as a bound this run imposed, which is the same laundering as calling a deferred
    unit `semantic_remainder`, in the opposite direction.

    So: on a FULL run, where the operationalizer routinely proposes nothing for some claim, the
    scope record's exclusions must be empty even though the plan's are not.
    """
    session, _ = _run(name)
    plan = _plan(session, DissolutionPass.EPISTEMIC_OPERATIONALIZER)
    uninvestigated = [d for d in plan.get("dispositions", [])
                      if d["disposition"] == ItemDispositionKind.NOT_INVESTIGATED.value]
    assert uninvestigated, "this fixture no longer exercises the case; pick another"
    assert _scope_of(session)["exclusions"] == []
    assert _scope_of(session)["claims_not_investigated"] == []
    # And every one of them is still named on the PASS, with its own reason. Nothing was hidden;
    # it was attributed to the mind that made the decision.
    assert all(d["reason"].strip() for d in uninvestigated)


@pytest.mark.parametrize("name", FIXTURES)
def test_the_record_names_every_uninvestigated_item_individually(name, enabled):
    """A count tells a reader the size of the gap and not where it is."""
    session, _ = _run(name, execution_scope="vertical_slice")
    record = _scope_of(session)
    named = {e["ref"] for e in record["exclusions"]}
    for key in ("deferred_source_unit_ids", "atoms_not_investigated", "claims_not_investigated"):
        assert set(record[key]) <= named, key
    assert all(e["reason"].strip() for e in record["exclusions"])


@pytest.mark.parametrize("name", FIXTURES)
def test_the_scope_reaches_the_wire_and_the_session(name, enabled):
    session, stages = _run(name, execution_scope="vertical_slice")
    body = view.session_view(session, servable_classes=coordinator.servable_classes(stages),
                             deployment=runtime.deployment(stages))
    assert body["execution_scope"]["mode"] == "vertical_slice"
    assert body["execution_scope"]["full_coverage"] is False
    assert body["execution_scope"]["recorded"] is True
    assert body["graph"]["execution_scope"] is not None
    # AND IT ROUND-TRIPS THROUGH PERSISTENCE. The envelope is embedded whole in the document, so
    # this is the same object a reload produces.
    from backend.schemas.inquiry_session import SemanticInquirySession
    again = SemanticInquirySession.model_validate(session.model_dump(mode="json"))
    assert again.execution_scope == "vertical_slice"
    assert (view.session_view(again, deployment=None)["execution_scope"]["exclusions"]
            == body["execution_scope"]["exclusions"])


def test_a_session_that_never_compiled_still_declares_its_scope(enabled):
    """The state the badge most has to survive. `recorded: false` and `full_coverage: false`."""
    session = coordinator.new_session(prompt="a question", refs=F.dissolution_post_refs(FIXTURES[0]),
                                      mode="auto", now=AT, execution_scope="vertical_slice")
    body = view.session_view(session, deployment=None)
    assert body["execution_scope"]["mode"] == "vertical_slice"
    assert body["execution_scope"]["recorded"] is False
    assert body["execution_scope"]["full_coverage"] is False


# ── the route ────────────────────────────────────────────────────────────────

@pytest.fixture
def wired(monkeypatch):
    posts = F.dissolution_post_docs(FIXTURES[0])
    sessions = F.FakeCollection()
    monkeypatch.setattr(store, "_collection", lambda collection=None: sessions)

    _real_resolve = corpus.resolve

    async def _resolve(post_ids, *, collection=None):
        return await _real_resolve(post_ids, collection=F.FakeCollection(list(posts.values())))

    monkeypatch.setattr(corpus, "resolve", _resolve)
    monkeypatch.setattr(R, "_stages", lambda: F.dissolution_stages_for(
        FIXTURES[0], capability=LockedFixtureCapability(), judge=judge,
        composer=DeterministicComposer()))

    app = FastAPI()
    app.include_router(R.router, prefix="/api/v1/inquiries")
    with TestClient(app) as client:
        yield client


def _body(**over):
    body = {"prompt": F.dissolution_prompt_for(FIXTURES[0]), "mode": "consult",
            "image_ids": [r.post_id for r in F.dissolution_post_refs(FIXTURES[0])]}
    body.update(over)
    return body


def test_a_disabled_scoped_request_is_refused_visibly(wired, monkeypatch):
    monkeypatch.delenv(scope.ENABLED_ENV, raising=False)
    res = wired.post("/api/v1/inquiries", json=_body(execution_scope="vertical_slice"))
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert detail["error"] == "scoped_rehearsal_disabled"
    # THE REQUEST'S OWN WORD, ECHOED BACK, and the flag named. A refusal a person cannot act on is
    # a refusal they will read as a bug.
    assert detail["requested_execution_scope"] == "vertical_slice"
    assert detail["feature_flag"] == scope.ENABLED_ENV
    assert "vertical_slice" in detail["execution_scopes"]


def test_a_disabled_request_creates_no_session_at_all(wired, monkeypatch):
    """It is not run as `full` and it is not run at all. A fallback here would answer a different
    question from the one that was asked and say nothing about it."""
    monkeypatch.delenv(scope.ENABLED_ENV, raising=False)
    wired.post("/api/v1/inquiries", json=_body(execution_scope="vertical_slice"))
    listing = wired.get("/api/v1/inquiries").json()
    assert listing["sessions"] == []


def test_an_unknown_scope_is_refused_by_the_route(wired, monkeypatch):
    monkeypatch.setenv(scope.ENABLED_ENV, "1")
    res = wired.post("/api/v1/inquiries", json=_body(execution_scope="quarter_slice"))
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "unknown_execution_scope"


def test_the_listing_declares_what_this_deployment_serves(wired, monkeypatch):
    monkeypatch.delenv(scope.ENABLED_ENV, raising=False)
    off = wired.get("/api/v1/inquiries").json()["features"]["scoped_rehearsal"]
    assert off["available"] is False
    assert off["flag"] == scope.ENABLED_ENV
    monkeypatch.setenv(scope.ENABLED_ENV, "1")
    on = wired.get("/api/v1/inquiries").json()["features"]["scoped_rehearsal"]
    assert on["available"] is True
    assert "vertical_slice" in on["scopes"]


def test_an_ordinary_request_still_needs_no_scope_field(wired):
    res = wired.post("/api/v1/inquiries", json=_body())
    assert res.status_code == 202
    assert res.json()["execution_scope"]["mode"] == "full"


def test_a_scoped_request_is_accepted_and_says_so_immediately(wired, monkeypatch, enabled):
    res = wired.post("/api/v1/inquiries", json=_body(execution_scope="vertical_slice"))
    assert res.status_code == 202
    body = res.json()
    # BEFORE ANY MODEL RUNS. The 202 already carries the badge, which is what makes it survive a
    # session that never gets further.
    assert body["execution_scope"]["mode"] == "vertical_slice"
    assert body["execution_scope"]["full_coverage"] is False


# ── the invariants this lane may not move ────────────────────────────────────

def test_a_413_is_still_never_retried():
    """A 413 says the request itself is too large; re-sending it unchanged fails identically
    forever. The scope may reduce work — it may not turn an unsendable request into patience."""
    from backend.services.semantic_compilation import pacing

    class _TooLarge(Exception):
        status_code = 413

    class _Congested(Exception):
        status_code = 429

    assert pacing.is_capacity_refusal(_TooLarge()) is False
    assert pacing.is_capacity_refusal(_Congested()) is True


def test_a_429_re_sends_identical_bytes():
    """`ProviderPacer.send` takes a THUNK and the request dict is built once, outside it — so
    identical-bytes is a property of the signature rather than a promise."""
    from backend.services.semantic_compilation import pacing

    built = []
    request = {"model": "m", "messages": [{"role": "user", "content": "the same bytes"}]}

    class _Congested(Exception):
        status_code = 429
        response = None

    attempts = {"n": 0}

    def send():
        built.append(copy.deepcopy(request))
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise _Congested()
        return "ok"

    pacer = pacing.ProviderPacer(interval_seconds=0.0, max_attempts=5, budget_seconds=60.0,
                                sleep=lambda _s: None)
    pacer.open_budget()
    result = pacer.send(send)
    assert result.value == "ok"
    assert len(built) == 3
    assert built[0] == built[1] == built[2]


@pytest.mark.parametrize("name", FIXTURES)
def test_a_scoped_run_touches_no_post(name, enabled):
    """The guarantee that has to hold whether or not anything else did."""
    before = {r.post_id: r.fingerprint for r in F.dissolution_post_refs(name)}
    session, _ = _run(name, execution_scope="vertical_slice")
    after = {p.post_id: p.fingerprint for p in session.posts}
    assert before == after


@pytest.mark.parametrize("name", FIXTURES)
def test_a_scoped_run_is_replayable_from_its_own_ids(name, enabled):
    """Two runs of the same input select the same ids and dispose of the same things. That is what
    makes a scoped run a comparison rather than an act of faith."""
    first, _ = _run(name, execution_scope="vertical_slice")
    second, _ = _run(name, execution_scope="vertical_slice")
    a, b = _scope_of(first), _scope_of(second)
    for key in ("selected_source_unit_ids", "deferred_source_unit_ids", "selected_atom_ids",
                "atoms_not_investigated", "selected_claim_ids", "claims_not_investigated"):
        assert a[key] == b[key], key
    # And the exclusions carry the same reasons, not merely the same refs: the reason is the field
    # a person acts on, and two runs that named the same gaps differently would be two accounts.
    assert [(e["ref"], e["reason"]) for e in a["exclusions"]] \
        == [(e["ref"], e["reason"]) for e in b["exclusions"]]


@pytest.mark.parametrize("name", FIXTURES)
def test_a_scoped_run_over_frozen_payloads_makes_no_live_call(name, enabled):
    """A scope may reduce what is asked. It may not turn a replay into a live call, and it may not
    fabricate a provider for the requests it did not make.

    The same assertion `test_a_replay_makes_no_live_call` makes over an unbounded council, on the
    bounded path — because the bound touches the loop those receipts come out of.
    """
    session, _ = _run(name, execution_scope="vertical_slice")
    for receipt in session.graph["passes"]:
        assert not receipt["provider"], receipt["pass_name"]
        assert not receipt["prompt_tokens"], receipt["pass_name"]


@pytest.mark.parametrize("name", FIXTURES)
def test_a_bounded_pass_may_not_call_itself_completed(name, enabled):
    """003E's rule, inherited rather than restated: a pass carrying an unexamined pair or an
    uninvestigated item is not `completed`. The bound is a new way to produce one, and it must reach
    the same verdict."""
    from backend.schemas.semantic_compilation import PassOutcome

    session, _ = _run(name, execution_scope="vertical_slice")
    for receipt in session.graph["passes"]:
        plan = receipt.get("batch_plan") or {}
        sent = plan.get("batches_sent")
        if sent is None:
            continue
        sendable = [b for b in plan.get("batches", []) if b.get("sendable") is not False]
        if len(sendable) > sent:
            assert receipt["outcome"] != PassOutcome.COMPLETED.value, receipt["pass_name"]
