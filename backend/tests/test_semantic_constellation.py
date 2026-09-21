import copy
import json

import pytest
from pydantic import ValidationError

from backend.schemas.inquiry_session import SemanticInquirySession, canonical
from backend.schemas.semantic_constellation import (
    AnchorInput, ThoughtInput, ReviewWrite, SemanticConstellations,
)
from backend.services.inquiry_session import constellations as C, store, view, steps, driver
from backend.services.inquiry_session.coordinator import Stages
from backend.tests.fixtures import semantic_constellation_fixtures as F
from backend.tests.fixtures.inquiry_session_fixtures import FakeCollection


@pytest.mark.parametrize("name", F.CASES)
def test_capture_before_compilation_then_inspect_same_output(name):
    session = F.session_for(name, compiled=False)
    captured = C.capture(session, F.thought_for(session), at=F.STAMP)
    before = next(iter(C.latest(captured).values()))
    assert before.timing == "before_compilation" and before.inspection is None
    assert before.anchors[0].author == "user"
    graph = F.session_for(name).graph
    compiled = captured.model_copy(update={"graph": graph})
    inspected = C.reconcile(compiled, at=F.STAMP)
    after = C.latest(inspected)[before.constellation_id]
    assert after.revision == 2 and after.previous_revision == 1
    assert after.constellation_id == before.constellation_id
    assert after.inspection.candidate_count == len(graph["claims"])
    assert after.confirmed_claim_refs == [] and after.judgment.value == "not_assessed"
    assert inspected.semantic_constellations.history[0] == before
    assert C.reconcile(inspected, at=F.STAMP) == inspected
    assert graph == inspected.graph  # isolated and constellation inspection use identical output
    assert canonical(C.reconcile(compiled, at=F.STAMP)) == canonical(inspected)


def test_retrospective_and_edit_history_do_not_claim_early_capture():
    session = F.session_for()
    s = C.capture(session, F.thought_for(session), at=F.STAMP)
    row = next(iter(C.latest(s).values()))
    assert row.timing == "retrospective"
    thought = F.thought_for(session).model_copy(update={"organising_question": "A revised question?"})
    revised = C.capture(s, thought, at=F.STAMP, constellation_id=row.constellation_id,
                        expected_revision=row.revision)
    assert len(C.latest(revised)) == 1
    assert revised.semantic_constellations.history[:2] == s.semantic_constellations.history
    assert C.latest(revised)[row.constellation_id].revision == row.revision + 2


@pytest.mark.parametrize("changes", [
    {"source_id": "missing"}, {"origin": "model_reading"},
    {"exact_text": "X" * len(F.CASES["flower"][0])},
])
def test_exact_source_validation(changes):
    s = F.session_for(compiled=False)
    thought = F.thought_for(s)
    anchor = thought.anchors[0].model_copy(update=changes)
    with pytest.raises(ValueError, match="exact source"):
        C.capture(s, thought.model_copy(update={"anchors": [anchor]}), at=F.STAMP)


def test_model_reading_only_after_it_exists_and_keeps_attribution():
    s = F.session_for(compiled=False)
    text = "An independently attributed provisional interpretation."
    thought = F.thought_for(s).model_copy(update={"anchors": [AnchorInput(
        origin="model_reading", source_id="rb_x", span=(0, len(text)), exact_text=text)]})
    with pytest.raises(ValueError):
        C.capture(s, thought, at=F.STAMP)
    s = s.model_copy(update={"reading": {"reading": {"blocks": [
        {"block_id": "rb_x", "text": text, "image_refs": ["image_x"]}]}}})
    row = next(iter(C.latest(C.capture(s, thought, at=F.STAMP)).values()))
    assert row.anchors[0].author == "scene_theorist"
    assert row.anchors[0].image_refs == ["image_x"]
    assert row.timing == "before_compilation"


def test_model_question_needs_confirmation_and_strict_contract():
    s = F.session_for(compiled=False)
    body = F.thought_for(s).model_dump()
    body.update(authorship={"kind": "model", "actor": "test-model"}, confirmed_by=None)
    with pytest.raises(ValueError, match="human-confirmed"):
        C.capture(s, ThoughtInput(**body), at=F.STAMP)
    with pytest.raises(ValidationError):
        ThoughtInput(**body, measured=True)
    with pytest.raises(ValidationError):
        AnchorInput(origin="user_prompt", source_id="prompt", span=(-1, 1), exact_text="ab")


def inspected(s):
    out = C.capture(s, F.thought_for(s), at=F.STAMP)
    return out, next(iter(C.latest(out).values()))


def test_inferred_ancestry_missing_refs_cycles_and_no_lexical_guessing():
    s = F.session_for("branching")
    direct, second, inferred = s.graph["claims"]
    inferred["inferred_from"].extend(["absent", inferred["claim_id"]])
    direct["atom_refs"].append("absent_atom")
    s.graph["claims"].append({"claim_id": "unrelated", "text": direct["text"], "atom_refs": []})
    _, row = inspected(s)
    match = next(c for c in row.inspection.candidates if c.claim_ref == inferred["claim_id"])
    assert match.inference_refs == sorted([direct["claim_id"], second["claim_id"]])
    assert "unrelated" not in {c.claim_ref for c in row.inspection.candidates}
    assert any(x.startswith("inference_cycle:") for x in row.inspection.missing_links)
    assert "missing_claim:absent" in row.inspection.missing_links
    assert any("absent_atom" in x for x in row.inspection.missing_links)


def test_missing_source_and_edge_endpoints_are_explicit():
    s = F.session_for()
    s.graph["semantic_atoms"][0]["source_unit_ids"].append("absent_unit")
    s.graph["claim_edges"][0]["to_claim"] = "absent_claim"
    _, row = inspected(s)
    assert any("absent_unit" in x for x in row.inspection.missing_links)
    assert any(x.startswith("missing_edge_endpoint:") for x in row.inspection.missing_links)


@pytest.mark.parametrize("count", [0, 1, 9, 20])
def test_sparse_and_oversized_candidates_are_not_silently_truncated(count):
    s = F.session_for()
    base = s.graph["claims"][0]
    s.graph["claims"] = [{**base, "claim_id": f"clm_{i}"} for i in range(count)]
    s.graph["claim_edges"] = []
    _, row = inspected(s)
    assert row.inspection.candidate_count == count
    assert len(row.inspection.candidates) == count
    assert row.inspection.narrowing_required == (count > 8)
    if not count:
        assert "zero_matching_claims" in row.inspection.missing_links


def test_neighbours_are_separate_and_edge_direction_survives():
    s = F.session_for()
    s.graph["claims"][1]["atom_refs"] = []
    _, row = inspected(s)
    neighbours = [c for c in row.inspection.candidates if c.reason == "immediate_graph_neighbour"]
    assert len(neighbours) == 1
    assert neighbours[0].via_edge_refs == [s.graph["claim_edges"][0]["edge_id"]]
    assert s.graph["claim_edges"][0]["from_claim"] == neighbours[0].claim_ref


def review_body(row, **changes):
    return ReviewWrite(expected_checkpoint=0, expected_constellation_revision=row.revision,
        graph_hash=row.inspection.graph.graph_hash, actor="test-human", **changes)


def test_human_review_is_separate_and_does_not_promote_claims():
    s, row = inspected(F.session_for())
    graph = copy.deepcopy(s.graph)
    refs = [c.claim_ref for c in row.inspection.candidates]
    body = review_body(row, confirmed_claim_refs=refs,
        confirmed_edge_refs=row.inspection.candidate_edge_refs,
        judgment={"value": "partly_preserved", "note": "The connective thought is absent.",
                  "recovered_thought": "The intended connection", "next_investigation": "Compare groupings"})
    reviewed = C.review(s, row.constellation_id, body, at=F.STAMP)
    result = C.latest(reviewed)[row.constellation_id]
    assert result.judgment.assessed_by == "test-human"
    assert result.judgment.at == F.STAMP
    assert reviewed.graph == graph
    assert reviewed.evidence == []
    assert s.semantic_constellations.history == reviewed.semantic_constellations.history[:-1]


def test_stale_graph_never_rebinds_and_cannot_be_reviewed():
    s, row = inspected(F.session_for())
    s.graph["claims"][0]["text"] += " changed"
    result = C.reconcile(s, at=F.STAMP)
    assert C.latest(result)[row.constellation_id] == row
    assert C.projection(result)["current"][0]["graph_stale"]
    with pytest.raises(ValueError, match="stale"):
        C.review(result, row.constellation_id, review_body(row), at=F.STAMP)


@pytest.mark.parametrize("changes", [
    {"confirmed_claim_refs": ["foreign"]},
    {"confirmed_edge_refs": ["foreign"]},
    {"judgment": {"value": "lost", "note": ""}},
])
def test_review_rejects_foreign_refs_and_unattributed_judgments(changes):
    s, row = inspected(F.session_for())
    with pytest.raises(ValueError):
        C.review(s, row.constellation_id, review_body(row, **changes), at=F.STAMP)


def test_reading_legacy_does_not_write_or_assert_no_thought():
    raw = F.session_for(compiled=False).model_dump()
    raw.pop("semantic_constellations")
    raw["schema_version"] = "semantic-inquiry-session.v1"
    original = copy.deepcopy(raw)
    loaded = SemanticInquirySession.model_validate(raw)
    assert raw == original and loaded.schema_version.endswith("v1")
    assert C.projection(loaded)["recorded"] is False
    assert C.projection(loaded)["current"] == []


@pytest.mark.asyncio
async def test_persistence_export_and_reopening_keep_every_revision():
    s, row = inspected(F.session_for())
    col = FakeCollection()
    await store.create(s, collection=col)
    reopened = await store.load(s.session_id, collection=col)
    assert reopened == s
    wire = view.session_view(reopened)
    assert wire["semantic_constellations"]["history"] == s.semantic_constellations.model_dump(mode="json")["history"]
    assert json.loads(json.dumps(wire))["semantic_constellations"]["current"][0]["constellation_id"] == row.constellation_id


@pytest.mark.asyncio
async def test_opt_in_prompt_and_compiler_pause_then_resume_without_rerunning():
    s = F.session_for(compiled=False).model_copy(update={
        "semantic_constellations": SemanticConstellations(preparation="prompt")})
    col = FakeCollection()
    await store.create(s, collection=col)
    stages = Stages(clock=lambda: F.STAMP)
    report = await driver.drive(s.session_id, stages, collection=col)
    assert not report.stages_run
    s = await store.load(s.session_id, collection=col)
    s = C.continue_preparation(C.capture(s, F.thought_for(s), at=F.STAMP))
    await store.save(s, collection=col)
    report = await driver.drive(s.session_id, stages, collection=col)
    assert report.stages_run == ("framer", "theorist")
    s = await store.load(s.session_id, collection=col)
    assert s.semantic_constellations.preparation == "compiler"
    assert s.state == "awaiting_user" and not C.compiler_entered(s)
    await store.save(C.continue_preparation(s), collection=col)
    report = await driver.drive(s.session_id, stages, collection=col)
    assert report.stages_run[0] == "compiler" and "theorist" not in report.stages_run


def test_default_execution_is_unchanged_and_unconfirmed_cannot_continue():
    s = F.session_for(compiled=False)
    assert steps.plan(s).stage.value == "framer"
    paused = s.model_copy(update={"semantic_constellations": SemanticConstellations(preparation="prompt")})
    with pytest.raises(ValueError, match="confirm"):
        C.continue_preparation(paused)


@pytest.mark.asyncio
async def test_driver_terminal_preserves_intervening_human_edit():
    s = F.session_for(compiled=False)
    col = FakeCollection()
    await store.create(s, collection=col)
    held = await driver.claim(s.session_id, "driver_test", at=F.STAMP, collection=col)
    from backend.schemas.inquiry_stage import StageName
    tap = driver._LiveProgress(held, StageName.COMPILER, collection=col)
    edited = C.capture(held, F.thought_for(s), at=F.STAMP)
    edited = edited.model_copy(update={"checkpoint": held.checkpoint + 1})
    await store.save(edited, expected_checkpoint=held.checkpoint, collection=col)
    result = held.model_copy(update={"graph": F.session_for().graph})
    await tap.settle(result, driver_id="driver_test")
    stored = await store.load(s.session_id, collection=col)
    assert len(stored.semantic_constellations.history) == 2
    assert stored.semantic_constellations.history[0] == edited.semantic_constellations.history[0]
    assert C.latest(stored)[next(iter(C.latest(stored)))].inspection is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("moment", ["release", "stage_start", "stage_terminal"])
async def test_human_edit_during_compare_and_set_is_retained(monkeypatch, moment):
    s = F.session_for(compiled=False)
    col = FakeCollection()
    await store.create(s, collection=col)
    real_save = store.save
    injected = []

    async def racing_save(value, **kwargs):
        held = bool((value.driver or {}).get("lease_id"))
        attempts = value.stages
        target = ((moment == "release" and not held) or
                  (moment == "stage_start" and attempts and attempts[-1].outcome.value == "started") or
                  (moment == "stage_terminal" and attempts and attempts[-1].outcome.value == "skipped"))
        if target and not injected:
            current = await store.load(s.session_id, collection=col)
            edit = C.capture(current, F.thought_for(current), at=F.STAMP)
            edit = edit.model_copy(update={"checkpoint": current.checkpoint + 1})
            await real_save(edit, expected_checkpoint=current.checkpoint, collection=col)
            injected.append(edit.semantic_constellations.history[0])
        return await real_save(value, **kwargs)

    monkeypatch.setattr(store, "save", racing_save)
    await driver.drive(s.session_id, Stages(clock=lambda: F.STAMP), collection=col)
    stored = await store.load(s.session_id, collection=col)
    assert injected and stored.semantic_constellations.history[0] == injected[0]
    assert not stored.driver["lease_id"]
    assert not stored.error


def test_upstream_loss_is_named_without_auto_grading():
    s, row = inspected(F.session_for())
    orphan = s.graph["semantic_atoms"][-1]["atom_id"]
    assert f"atom_without_claim:{orphan}" in row.inspection.missing_links
    assert row.judgment.value == "not_assessed"


def test_strict_stored_record_rejects_forged_status_and_membership():
    _, row = inspected(F.session_for())
    for change in ({"confirmed_by": None}, {"confirmed_claim_refs": ["foreign"]}):
        with pytest.raises(ValidationError):
            type(row).model_validate({**row.model_dump(), **change})


def test_blank_actor_and_confirmation_are_not_human_provenance():
    s = F.session_for(compiled=False)
    raw = F.thought_for(s).model_dump()
    with pytest.raises(ValidationError):
        ThoughtInput.model_validate({**raw, "confirmed_by": "  "})
    with pytest.raises(ValidationError):
        ThoughtInput.model_validate({**raw, "authorship": {"actor": "  "}})
