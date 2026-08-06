"""
Semant Writer · W8 — revision and passage genealogy.

W1 could commit a first draft. W7 could say where it diverged from what the author declared.
This is the act between them and after them: change the declarations, render again, and keep
everything. Most of this suite is about the two things that make that act honest rather than
convenient:

  VERSIONS ARE IMMUTABLE, THE POINTER MOVES. A committed version is written once and never
  touched again. Revising APPENDS and re-points; it does not edit. The export walks scene
  blocks and a block holds one version, so a superseded version has no route into exported
  prose — a property of the shape, not of a filter someone remembered to apply.

  NO SILENT IMPROVEMENT, IN ITS STRONG FORM. A revision is a fresh render under the declared
  set, and the prior version's text is never in the prompt. So a revision under an unchanged
  declaration set produces a prompt IDENTICAL to the first render's — asserted byte for byte
  below, which is a fact about the code rather than a promise about the model's behaviour.

  PROPOSE, NEVER COMMIT — on the revision too. Dismiss leaves the current version standing
  and creates nothing.
"""
import pytest

from backend.services import manuscript_service as ms_svc
from backend.services.writer import alignment as align
from backend.services.writer import instrument
from backend.services.writer import operators as op_svc
from backend.services.writer import passages as psg_svc
from backend.services.writer import readings as rdg
from backend.services.writer import render as render_svc
from backend.services.writer import revisions as rev
from backend.services.writer.render import OK, RenderResult
from backend.tests.test_writer_w1 import FakeCollection, run

PROJECT = "ms_fixture"

V1_TEXT = "The latch gave before she had decided to push it. She waited."
V2_TEXT = "The latch gave. She stood with her hand still raised, and did not go in."


@pytest.fixture
def store(monkeypatch):
    ops, psgs, usage = FakeCollection(), FakeCollection(), FakeCollection()
    versions_c, reads = FakeCollection(), FakeCollection()
    manuscripts, scenes, snaps = FakeCollection(), FakeCollection(), FakeCollection()
    monkeypatch.setattr(op_svc, "writer_operator_collection", ops)
    monkeypatch.setattr(psg_svc, "writer_passage_collection", psgs)
    monkeypatch.setattr(instrument, "writer_usage_collection", usage)
    monkeypatch.setattr(rev, "writer_passage_version_collection", versions_c)
    monkeypatch.setattr(rdg, "writer_reading_collection", reads)
    monkeypatch.setattr(ms_svc, "manuscript_collection", manuscripts)
    monkeypatch.setattr(ms_svc, "scene_collection", scenes)
    monkeypatch.setattr(ms_svc, "scene_version_collection", snaps)
    return {"versions": versions_c, "scenes": scenes, "usage": usage, "passages": psgs}


@pytest.fixture
def book(store):
    """A manuscript with one scene, and the ontology a passage is declared under."""
    async def build():
        await op_svc.operator_registry.create(
            PROJECT, "restraint", "what is withheld does the work",
            rendering_intent="say less than the moment wants")
        await op_svc.operator_registry.create(
            PROJECT, "threshold", "a crossing noticed only after it is behind them",
            rendering_intent="one held moment")
        m = await ms_svc.manuscript_service.create_manuscript("Fixture")
        m = await ms_svc.manuscript_service.add_chapter(m["id"], "One")
        scene = await ms_svc.manuscript_service.add_scene(
            m["id"], m["chapters"][0]["id"], "Scene")
        return {"manuscript_id": m["id"], "scene_id": scene["id"]}
    return run(build())


def provenance(operators=(("restraint", 1),), intents=(("avoid", "melodrama"),)):
    return {
        "operators": [{"name": n, "version": v, "source": "direct"} for n, v in operators],
        "intents": [{"key": k, "value": v} for k, v in intents],
    }


def quarantine(text, prov, book):
    """A rendered passage in quarantine, the way the loop leaves one."""
    async def go():
        return await psg_svc.passage_store.quarantine(
            PROJECT,
            RenderResult(status=OK, text=text, provenance=prov, model="stub-model"),
            manuscript_id=book["manuscript_id"], scene_id=book["scene_id"])
    return run(go())


def commit_v1(book, text=V1_TEXT, prov=None):
    """A committed passage at v1 — the thing a revision has as a parent."""
    psg = quarantine(text, prov or provenance(), book)
    accepted = run(psg_svc.passage_store.accept(psg["id"], scene_id=book["scene_id"]))
    scene = run(ms_svc.manuscript_service.get_scene(book["scene_id"]))
    block = next(b for b in scene["blocks"] if b["id"] == accepted["block_id"])
    return {"passage": psg, "block": block, "block_id": block["id"],
            "lineage_id": block["lineage_id"]}


def export(book):
    return run(ms_svc.manuscript_service.export_manuscript(book["manuscript_id"]))["content"]


# ══ the declared set and the diff — the WHY of the genealogy ════════════════

def test_the_declared_set_is_operators_and_intents_and_nothing_else():
    """Not the text, the model or the timestamps — a diff over those reports noise."""
    declared = rev.declared_set({
        **provenance(), "model": "gpt", "rendered_at": "2026-01-01", "run_id": "r1",
    })
    assert declared == {"operators": {"restraint": 1}, "intents": {"avoid": "melodrama"}}


def test_the_diff_names_what_the_author_changed():
    before = rev.declared_set(provenance(
        operators=(("restraint", 1),), intents=(("avoid", "melodrama"),)))
    after = rev.declared_set(provenance(
        operators=(("threshold", 2),), intents=(("goal", "she does not go in"),)))
    diff = rev.declaration_diff(before, after)

    assert diff["operators_added"] == ["threshold"]
    assert diff["operators_removed"] == ["restraint"]
    assert diff["intents_added"] == ["goal"]
    assert diff["intents_removed"] == ["avoid"]


def test_a_reversioned_operator_is_not_reported_as_a_swap():
    """v1 → v2 is the SAME declaration whose meaning the author edited.

    Flattening it into removed+added would lose the fact that makes the prose read
    differently — that the operator itself changed under it.
    """
    diff = rev.declaration_diff(
        rev.declared_set(provenance(operators=(("restraint", 1),))),
        rev.declared_set(provenance(operators=(("restraint", 2),))),
    )
    assert diff["operators_added"] == [] and diff["operators_removed"] == []
    assert diff["operators_reversioned"] == [{"name": "restraint", "from": 1, "to": 2}]


def test_a_changed_intent_value_carries_both_sides():
    diff = rev.declaration_diff(
        rev.declared_set(provenance(intents=(("avoid", "melodrama"),))),
        rev.declared_set(provenance(intents=(("avoid", "summary"),))),
    )
    assert diff["intents_changed"] == [{"key": "avoid", "from": "melodrama", "to": "summary"}]
    assert rev.diff_is_empty(diff) is False


def test_an_unchanged_declaration_set_diffs_to_nothing():
    diff = rev.declaration_diff(
        rev.declared_set(provenance()), rev.declared_set(provenance()))
    assert rev.diff_is_empty(diff) is True


# ══ NO SILENT IMPROVEMENT (gate step 4) ═════════════════════════════════════

def test_a_revision_prompt_is_the_render_prompt_byte_for_byte(store, book):
    """THE GATE CHECK, in its strong form.

    A revision is a fresh render under the declared set. Nothing about the fact that a
    revision is happening reaches the model — so under an unchanged declaration set the
    prompt is not merely 'materially the same', it is the same string.
    """
    ontology = run(op_svc.operator_registry.by_name(PROJECT))
    operators = [ontology["restraint"]]
    orchestration = {"avoid": "melodrama"}

    first = render_svc.build_render_prompt(operators, orchestration)
    again = rev.revision_prompt(operators, orchestration)

    assert again == first


def test_the_prior_version_text_never_enters_the_prompt(store, book):
    """Handing the model what it wrote makes it an editor of prose. It is a renderer."""
    ontology = run(op_svc.operator_registry.by_name(PROJECT))
    prompt = rev.revision_prompt([ontology["restraint"]], {"avoid": "melodrama"})
    blob = prompt["system"] + prompt["user"]
    assert V1_TEXT not in blob
    assert "She waited" not in blob


def test_no_polish_instruction_is_present_in_any_prompt(store, book):
    """The tripwire: an added 'tighten this' fails here rather than shipping."""
    ontology = run(op_svc.operator_registry.by_name(PROJECT))
    for prompt in (
        render_svc.build_render_prompt([ontology["restraint"]], {"avoid": "melodrama"}),
        rev.revision_prompt([ontology["restraint"]], {"avoid": "melodrama"}),
        rev.revision_prompt([ontology["restraint"]], {}),
    ):
        assert rev.polish_leaks(prompt) == []


def test_the_polish_tripwire_actually_fires():
    """A guard that cannot fail is not a guard."""
    assert rev.polish_leaks({"system": "", "user": "now tighten the prose and improve it"})


# ══ immutable versions, a moving pointer (gate steps 1, 2, 5) ═══════════════

def test_a_first_accept_lands_as_version_one_of_a_lineage(store, book):
    v1 = commit_v1(book)
    assert v1["block"]["version"] == 1
    history = run(rev.version_store.history(v1["lineage_id"]))
    assert [v["version"] for v in history] == [1]
    assert history[0]["text"] == V1_TEXT
    assert history[0]["revised_from"] == ""


def test_a_quarantined_revision_does_not_move_the_pointer(store, book):
    """Gate step 1 — proposed, not applied."""
    v1 = commit_v1(book)
    quarantine(V2_TEXT, provenance(intents=(("goal", "she does not go in"),)), book)

    scene = run(ms_svc.manuscript_service.get_scene(book["scene_id"]))
    block = next(b for b in scene["blocks"] if b["id"] == v1["block_id"])
    assert block["version"] == 1
    assert block["content"] == V1_TEXT
    assert len(run(rev.version_store.history(v1["lineage_id"]))) == 1


def test_accepting_a_revision_appends_a_version_and_moves_the_pointer(store, book):
    """Gate step 2."""
    v1 = commit_v1(book)
    psg = quarantine(V2_TEXT, provenance(intents=(("goal", "she does not go in"),)), book)

    result = run(psg_svc.passage_store.accept_revision(
        psg["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
        block_id=v1["block_id"]))

    assert result["version"]["version"] == 2
    assert result["version"]["revised_from"] == f"{v1['lineage_id']}@v1"
    assert result["declaration_diff"]["intents_added"] == ["goal"]
    assert result["declaration_diff"]["intents_removed"] == ["avoid"]

    scene = run(ms_svc.manuscript_service.get_scene(book["scene_id"]))
    block = next(b for b in scene["blocks"] if b["id"] == v1["block_id"])
    assert block["version"] == 2
    assert block["content"] == V2_TEXT


def test_the_superseded_version_is_retained_untouched(store, book):
    """Gate steps 2 and 5 — the whole canon rule in one assertion."""
    v1 = commit_v1(book)
    before = run(rev.version_store.resolve(v1["lineage_id"], 1))

    psg = quarantine(V2_TEXT, provenance(intents=(("goal", "x"),)), book)
    run(psg_svc.passage_store.accept_revision(
        psg["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
        block_id=v1["block_id"]))

    after = run(rev.version_store.resolve(v1["lineage_id"], 1))
    assert after == before
    assert after["text"] == V1_TEXT
    assert after["provenance"]["intents"] == [{"key": "avoid", "value": "melodrama"}]


def test_a_superseded_version_still_resolves_with_its_original_provenance(store, book):
    """Gate step 7 — W5's resolver, temporal half.

    The operator can go on changing underneath; v1 still names the version that fired.
    """
    v1 = commit_v1(book)
    psg = quarantine(V2_TEXT, provenance(operators=(("restraint", 2),)), book)
    run(psg_svc.passage_store.accept_revision(
        psg["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
        block_id=v1["block_id"]))

    # the author keeps editing the operator afterwards
    run(op_svc.operator_registry.update(
        PROJECT, "restraint", {"rendering_intent": "something else entirely"}))

    historical = run(rev.version_store.resolve(v1["lineage_id"], 1))
    assert historical["provenance"]["operators"] == [
        {"name": "restraint", "version": 1, "source": "direct"}]
    resolution = run(op_svc.operator_registry.resolve_provenance(
        PROJECT, historical["provenance"]))
    assert resolution["missing"] == []
    assert resolution["resolved"][0]["rendering_intent"] == "say less than the moment wants"


def test_no_version_is_ever_deleted(store, book):
    """Gate step 5 — three revisions, four versions, all present."""
    v1 = commit_v1(book)
    for i, text in enumerate(["second", "third", "fourth"], start=2):
        psg = quarantine(text, provenance(intents=((f"note{i}", "x"),)), book)
        run(psg_svc.passage_store.accept_revision(
            psg["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
            block_id=v1["block_id"]))

    history = run(rev.version_store.history(v1["lineage_id"]))
    assert [v["version"] for v in history] == [1, 2, 3, 4]
    assert [v["text"] for v in history] == [V1_TEXT, "second", "third", "fourth"]


# ══ export is current versions only (gate step 5) ═══════════════════════════

def test_the_export_holds_the_current_version_and_no_other(store, book):
    v1 = commit_v1(book)
    psg = quarantine(V2_TEXT, provenance(intents=(("goal", "x"),)), book)
    run(psg_svc.passage_store.accept_revision(
        psg["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
        block_id=v1["block_id"]))

    text = export(book)
    assert V2_TEXT in text
    assert V1_TEXT not in text
    assert "She waited" not in text


def test_export_is_byte_identical_to_the_set_of_current_versions(store, book):
    """Gate step 8's export clause, stated as an equality rather than an absence."""
    first = commit_v1(book, text="Alpha one.")
    second = commit_v1(book, text="Beta one.")

    psg = quarantine("Alpha two.", provenance(intents=(("goal", "x"),)), book)
    run(psg_svc.passage_store.accept_revision(
        psg["id"], lineage_id=first["lineage_id"], scene_id=book["scene_id"],
        block_id=first["block_id"]))

    scene = run(ms_svc.manuscript_service.get_scene(book["scene_id"]))
    currents = [b["content"] for b in scene["blocks"]]
    assert currents == ["Alpha two.", "Beta one."]

    text = export(book)
    for current in currents:
        assert current in text
    assert "Alpha one." not in text


# ══ propose, never commit — on the revision (gate step 3) ═══════════════════

def test_dismissing_a_revision_leaves_the_current_version_standing(store, book):
    v1 = commit_v1(book)
    psg = quarantine(V2_TEXT, provenance(intents=(("goal", "x"),)), book)

    run(psg_svc.passage_store.dismiss(psg["id"], "not what I meant"))

    scene = run(ms_svc.manuscript_service.get_scene(book["scene_id"]))
    block = next(b for b in scene["blocks"] if b["id"] == v1["block_id"])
    assert block["version"] == 1 and block["content"] == V1_TEXT
    assert len(run(rev.version_store.history(v1["lineage_id"]))) == 1
    assert V1_TEXT in export(book)


def test_a_revision_is_decided_once(store, book):
    v1 = commit_v1(book)
    psg = quarantine(V2_TEXT, provenance(intents=(("goal", "x"),)), book)
    run(psg_svc.passage_store.accept_revision(
        psg["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
        block_id=v1["block_id"]))

    with pytest.raises(psg_svc.PassageError, match="already accepted"):
        run(psg_svc.passage_store.accept_revision(
            psg["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
            block_id=v1["block_id"]))


def test_a_revision_still_refuses_a_passage_that_leaks_orchestration(store, book):
    """The revision door is the SAME door: invariant 6 is re-checked here too."""
    v1 = commit_v1(book)
    leaking = quarantine(
        "goal: she does not go in\nShe stood in the doorway.",
        provenance(intents=(("goal", "she does not go in"),)), book)

    with pytest.raises(psg_svc.PassageError, match="orchestration would reach"):
        run(psg_svc.passage_store.accept_revision(
            leaking["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
            block_id=v1["block_id"]))

    assert len(run(rev.version_store.history(v1["lineage_id"]))) == 1


def test_a_revision_needs_a_parent(store, book):
    psg = quarantine(V2_TEXT, provenance(), book)
    with pytest.raises(rev.RevisionError, match="no committed version"):
        run(psg_svc.passage_store.accept_revision(
            psg["id"], lineage_id="lin_nothing", scene_id=book["scene_id"],
            block_id="blk_nothing"))


# ══ preparing a revision, and adopting pre-W8 prose ═════════════════════════

def test_prepare_reports_what_the_block_was_declared_under(store, book):
    v1 = commit_v1(book)
    prepared = run(rev.prepare(PROJECT, book["scene_id"], v1["block_id"]))

    assert prepared["current_version"] == 1
    assert prepared["current_text"] == V1_TEXT
    assert prepared["declared"] == {"operators": {"restraint": 1},
                                    "intents": {"avoid": "melodrama"}}
    assert prepared["adopted"] is False


def test_a_block_committed_before_w8_is_adopted_without_inventing_history(store, book):
    """A pre-W8 block has ONE version — the prose on the page — and gains no fictions."""
    async def legacy():
        scene = await ms_svc.manuscript_service.get_scene(book["scene_id"])
        blocks = list(scene.get("blocks", []))
        blocks.append({"id": "blk_legacy", "type": "paragraph", "content": "Older prose.",
                       "color": None, "origin": "user_confirmed",
                       "provenance": provenance()})
        await ms_svc.manuscript_service.update_scene(book["scene_id"], {"blocks": blocks})
    run(legacy())

    prepared = run(rev.prepare(PROJECT, book["scene_id"], "blk_legacy"))
    assert prepared["adopted"] is True
    assert prepared["current_version"] == 1
    assert [v["version"] for v in prepared["history"]] == [1]
    assert prepared["history"][0]["text"] == "Older prose."
    assert prepared["history"][0]["revised_from"] == ""


def test_adopting_is_idempotent(store, book):
    v1 = commit_v1(book)
    run(rev.prepare(PROJECT, book["scene_id"], v1["block_id"]))
    run(rev.prepare(PROJECT, book["scene_id"], v1["block_id"]))
    assert len(run(rev.version_store.history(v1["lineage_id"]))) == 1


# ══ closing the W7 loop (gate step 6) ═══════════════════════════════════════

def _reading(flags):
    return {"id": "rdg_1", "status": "flagged" if flags else "aligned", "flags": flags}


def revise_answering_flag(book, v1, text=V2_TEXT):
    psg = quarantine(text, provenance(intents=(("avoid", "melodrama and summary"),)), book)
    return run(psg_svc.passage_store.accept_revision(
        psg["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
        block_id=v1["block_id"],
        in_response_to={"flag_id": "flg_1", "element": "intent:avoid",
                        "reading_id": "rdg_0"}))


def test_the_genealogy_records_which_flag_a_revision_answered(store, book):
    v1 = commit_v1(book)
    result = revise_answering_flag(book, v1)
    assert result["version"]["in_response_to"]["flag_id"] == "flg_1"
    assert result["version"]["in_response_to"]["element"] == "intent:avoid"


def test_a_cleared_divergence_is_recorded(store, book):
    v1 = commit_v1(book)
    result = revise_answering_flag(book, v1)

    closed = run(rev.close_loop(result["version"]["id"], _reading([])))
    assert closed["loop_outcome"]["outcome"] == rev.CLEARED
    assert closed["loop_outcome"]["element"] == "intent:avoid"


def test_a_divergence_that_survived_the_revision_is_ALSO_recorded(store, book):
    """The honest half. A loop that logged only its successes would tell the calibration
    signal that revision always works — the most flattering possible lie about the tools."""
    v1 = commit_v1(book)
    result = revise_answering_flag(book, v1)

    closed = run(rev.close_loop(result["version"]["id"], _reading(
        [{"id": "flg_9", "element": "intent:avoid", "span": "x", "divergence": "still"}])))
    assert closed["loop_outcome"]["outcome"] == rev.STILL_PRESENT


def test_the_loop_matches_on_the_ELEMENT_not_the_flag_id(store, book):
    """A new reading makes new flag ids. Matching on id would report `cleared` always."""
    v1 = commit_v1(book)
    result = revise_answering_flag(book, v1)

    # a DIFFERENT element still flagged is not the divergence that was answered
    closed = run(rev.close_loop(result["version"]["id"], _reading(
        [{"id": "flg_9", "element": "operator:restraint:intent", "span": "x",
          "divergence": "other"}])))
    assert closed["loop_outcome"]["outcome"] == rev.CLEARED


def test_closing_a_loop_that_was_never_opened_is_refused(store, book):
    v1 = commit_v1(book)
    psg = quarantine(V2_TEXT, provenance(intents=(("goal", "x"),)), book)
    plain = run(psg_svc.passage_store.accept_revision(
        psg["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
        block_id=v1["block_id"]))

    with pytest.raises(rev.RevisionError, match="no loop to close"):
        run(rev.close_loop(plain["version"]["id"], _reading([])))


def test_closing_the_loop_changes_no_prose_and_no_version(store, book):
    v1 = commit_v1(book)
    result = revise_answering_flag(book, v1)
    before_text = export(book)
    before_v1 = run(rev.version_store.resolve(v1["lineage_id"], 1))

    run(rev.close_loop(result["version"]["id"], _reading([])))

    assert export(book) == before_text
    assert run(rev.version_store.resolve(v1["lineage_id"], 1)) == before_v1
    v2 = run(rev.version_store.resolve(v1["lineage_id"], 2))
    assert v2["text"] == V2_TEXT
    assert v2["declaration_diff"] == result["declaration_diff"]


# ══ the genealogy is logged (§8 — capture now, analyse later) ═══════════════

def test_a_revision_logs_its_diff_and_its_parent(store, book):
    v1 = commit_v1(book)
    psg = quarantine(V2_TEXT, provenance(intents=(("goal", "x"),)), book)
    run(psg_svc.passage_store.accept_revision(
        psg["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
        block_id=v1["block_id"]))

    events = run(instrument.usage_for_project(PROJECT, limit=200))
    revised = next(e for e in events if e["event"] == rev.REVISED)
    assert revised["extra"]["version"] == 2
    assert revised["extra"]["revised_from"] == f"{v1['lineage_id']}@v1"
    assert revised["extra"]["declaration_diff"]["intents_added"] == ["goal"]


def test_a_revision_under_unchanged_declarations_is_logged_as_such(store, book):
    """Allowed — the author may want the same declarations rendered again — and RECORDED,
    because a corpus of those is the sharpest evidence of an operator that is too vague."""
    v1 = commit_v1(book)
    psg = quarantine(V2_TEXT, provenance(), book)
    run(psg_svc.passage_store.accept_revision(
        psg["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
        block_id=v1["block_id"]))

    events = run(instrument.usage_for_project(PROJECT, limit=200))
    revised = next(e for e in events if e["event"] == rev.REVISED)
    assert revised["extra"]["declarations_unchanged"] is True


def test_the_loop_outcome_is_logged_with_the_operator_it_concerned(store, book):
    v1 = commit_v1(book)
    result = revise_answering_flag(book, v1)
    run(rev.close_loop(result["version"]["id"], _reading([])))

    events = run(instrument.usage_for_project(PROJECT, limit=200))
    closed = next(e for e in events if e["event"] == rev.LOOP_CLOSED)
    assert closed["extra"]["outcome"] == rev.CLEARED
    assert closed["extra"]["element"] == "intent:avoid"
    assert closed["operators"] == ["restraint"]


# ══ W1–W7 still hold ════════════════════════════════════════════════════════

def test_a_first_accept_still_appends_rather_than_replacing(store, book):
    """W8 must not have turned Accept into an overwrite."""
    commit_v1(book, text="First.")
    commit_v1(book, text="Second.")
    scene = run(ms_svc.manuscript_service.get_scene(book["scene_id"]))
    assert [b["content"] for b in scene["blocks"]] == ["First.", "Second."]


def test_revising_writes_no_operator(store, book):
    v1 = commit_v1(book)
    before = run(op_svc.operator_registry.list(PROJECT))
    psg = quarantine(V2_TEXT, provenance(intents=(("goal", "x"),)), book)
    run(psg_svc.passage_store.accept_revision(
        psg["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
        block_id=v1["block_id"]))
    assert run(op_svc.operator_registry.list(PROJECT)) == before
