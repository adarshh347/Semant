"""
Semant Writer · W9 — recall and cite: the manuscript's memory of itself.

Two rules carry this gate, and most of the suite is about them:

  THE VERBATIM RULE. Recall RETRIEVES. It returns the author's own committed sentences,
  byte for byte, or nothing at all. A recall that summarised would be fabrication wearing
  the author's canon — asserting as settled what the prose may have left ambiguous, in the
  voice of their own book, where they have no way to catch it. Enforced structurally: the
  module imports no model client, and a test below reads its source to say so.

  CITE ONLY COMMITTED CANON (I3). A citation may reach into the ledger and never into the
  session. Grounding new prose on an unaccepted render would rest canon on something the
  author might still dismiss — leaving committed prose citing a passage that exists
  nowhere.

And the quieter one that keeps both honest: recall and cite never touch canon. Recall
produces no prose, a cited render is quarantined like any other, and no prior text is ever
inserted into the manuscript by anything here.
"""
import pytest

from backend.services import manuscript_service as ms_svc
from backend.services.writer import instrument
from backend.services.writer import operators as op_svc
from backend.services.writer import passages as psg_svc
from backend.services.writer import recall as rc
from backend.services.writer import render as render_svc
from backend.services.writer import revisions as rev_svc
from backend.services.writer import studio
from backend.services.writer.dsl import parse_block
from backend.services.writer.render import OK, REFUSED, RenderResult
from backend.tests.test_writer_w1 import FakeCollection, run

PROJECT = "ms_fixture"

COLD_ROOM = "The room had gone cold in the night. She did not light the fire."
THE_SISTER = "Her sister wrote once a year, at Easter, and never asked to visit."
THE_LATCH = "The latch gave before she had decided to push it."


@pytest.fixture
def store(monkeypatch):
    ops, psgs, usage, versions_c = (FakeCollection(), FakeCollection(),
                                    FakeCollection(), FakeCollection())
    manuscripts, scenes, snaps = FakeCollection(), FakeCollection(), FakeCollection()
    monkeypatch.setattr(op_svc, "writer_operator_collection", ops)
    monkeypatch.setattr(psg_svc, "writer_passage_collection", psgs)
    monkeypatch.setattr(instrument, "writer_usage_collection", usage)
    monkeypatch.setattr(rev_svc, "writer_passage_version_collection", versions_c)
    monkeypatch.setattr(rc, "writer_passage_version_collection", versions_c)
    monkeypatch.setattr(ms_svc, "manuscript_collection", manuscripts)
    monkeypatch.setattr(ms_svc, "scene_collection", scenes)
    monkeypatch.setattr(ms_svc, "scene_version_collection", snaps)
    return {"versions": versions_c, "usage": usage, "passages": psgs}


@pytest.fixture
def book(store):
    async def build():
        await op_svc.operator_registry.create(
            PROJECT, "restraint", "what is withheld does the work",
            rendering_intent="say less than the moment wants")
        m = await ms_svc.manuscript_service.create_manuscript("Fixture")
        m = await ms_svc.manuscript_service.add_chapter(m["id"], "Chapter one")
        scene = await ms_svc.manuscript_service.add_scene(
            m["id"], m["chapters"][0]["id"], "The kitchen")
        return {"manuscript_id": m["id"], "scene_id": scene["id"]}
    return run(build())


def provenance(operators=(("restraint", 1),), intents=()):
    return {
        "operators": [{"name": n, "version": v, "source": "direct"} for n, v in operators],
        "intents": [{"key": k, "value": v} for k, v in intents],
    }


def quarantine(text, book, prov=None):
    async def go():
        return await psg_svc.passage_store.quarantine(
            PROJECT,
            RenderResult(status=OK, text=text, provenance=prov or provenance(),
                         model="stub-model"),
            manuscript_id=book["manuscript_id"], scene_id=book["scene_id"])
    return run(go())


def commit(text, book):
    psg = quarantine(text, book)
    accepted = run(psg_svc.passage_store.accept(psg["id"], scene_id=book["scene_id"]))
    return {"passage_id": psg["id"], **accepted}


def do_recall(query, **kw):
    return run(rc.recall(PROJECT, query, **kw))


def ledger():
    """Every stored version, keyed the way `verbatim_violations` wants it."""
    async def go():
        spans = await rc.committed_spans(PROJECT, include_historical=True)
        return {(s["lineage_id"], s["version"]): s["text"] for s in spans}
    return run(go())


# ══ THE VERBATIM RULE (gate step 1) ═════════════════════════════════════════

def test_recall_returns_the_authors_own_words_byte_for_byte(store, book):
    commit(COLD_ROOM, book)
    commit(THE_SISTER, book)

    result = do_recall("cold room fire")

    assert result["spans"], "the query should match the passage about the cold room"
    assert result["spans"][0]["text"] == COLD_ROOM      # byte-equal, not merely similar
    assert rc.verbatim_violations(result["spans"], ledger()) == []


def test_no_returned_span_is_ever_altered(store, book):
    """Every hit, against the ledger it came from. This is the assertion §2 turns on."""
    for text in (COLD_ROOM, THE_SISTER, THE_LATCH):
        commit(text, book)

    for query in ("cold", "sister Easter", "latch push", "room she"):
        result = do_recall(query, limit=10)
        assert rc.verbatim_violations(result["spans"], ledger()) == [], query


def test_a_long_passage_comes_back_whole_and_unclipped(store, book):
    """No ellipsis, no snippet window. A '…' this module added would be a sentence
    boundary the author did not write."""
    long_prose = " ".join(
        f"She counted the {n}th stair and did not stop counting." for n in range(1, 40))
    commit(long_prose, book)

    result = do_recall("counted stair stop")
    assert result["spans"][0]["text"] == long_prose
    assert "…" not in result["spans"][0]["text"]
    assert "..." not in result["spans"][0]["text"]


def test_whitespace_and_cadence_survive_recall(store, book):
    """The two-tier cadence is meaning in this editor; normalising it would be an edit."""
    cadenced = "She waited.\nThe latch gave.\n\nShe did not go in."
    commit(cadenced, book)

    result = do_recall("latch waited")
    assert result["spans"][0]["text"] == cadenced


def test_the_recall_module_cannot_summarise_because_it_cannot_call_a_model(store):
    """THE STRUCTURAL GUARD. A summary cannot leak out of a module with nothing to
    summarise with, and adding one means first adding an import this test forbids."""
    import ast
    import inspect

    # The IMPORTS, not the prose. The module docstring names what it refuses to reach for,
    # so a plain text scan would trip on the explanation rather than on a violation.
    tree = ast.parse(inspect.getsource(rc))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(f"{node.module}.{a.name}" for a in node.names)

    for forbidden in ("llm_service", "role_registry", "groq", "render"):
        assert not any(forbidden in name for name in imported), (
            f"the recall path imports {forbidden}")

    # and nothing model-shaped is reachable through the module at runtime
    for forbidden in ("llm_service", "role_registry", "build_render_prompt", "_call_model"):
        assert not hasattr(rc, forbidden)


def test_a_recall_result_carries_no_synthesis_field(store, book):
    """No `summary`, no `establishes`, no `overview` — there is nowhere to put one."""
    commit(COLD_ROOM, book)
    result = do_recall("cold")
    for forbidden in ("summary", "synthesis", "established", "establishes", "overview",
                      "gist", "digest"):
        assert forbidden not in result
        assert all(forbidden not in span for span in result["spans"])


# ══ empty is an honest answer (gate step 2) ═════════════════════════════════

def test_a_query_matching_nothing_returns_empty_not_a_guess(store, book):
    commit(COLD_ROOM, book)
    result = do_recall("submarine periscope bathysphere")

    assert result["spans"] == []
    assert "Nothing in your manuscript matches" in result["empty_reason"]


def test_an_empty_manuscript_says_so_rather_than_inventing_a_past(store, book):
    result = do_recall("anything at all")
    assert result["spans"] == []
    assert "no committed prose" in result["empty_reason"]


def test_an_empty_query_recalls_nothing(store, book):
    commit(COLD_ROOM, book)
    assert do_recall("")["spans"] == []
    assert do_recall("   the and of  ")["spans"] == []   # stopwords only


# ══ what is searchable: committed, current, project-scoped ═════════════════

def test_a_quarantined_render_is_not_recallable(store, book):
    """It is session memory. Recall reads the ledger."""
    quarantine("A quarantined sentence about a lighthouse.", book)
    assert do_recall("lighthouse")["spans"] == []


def test_a_dismissed_render_is_not_recallable(store, book):
    psg = quarantine("A dismissed sentence about a lighthouse.", book)
    run(psg_svc.passage_store.dismiss(psg["id"]))
    assert do_recall("lighthouse")["spans"] == []


def test_recall_targets_current_versions_by_default(store, book):
    """A superseded version is prose the author has already replaced."""
    first = commit("The hallway smelled of turpentine.", book)
    psg = quarantine("The hallway smelled of woodsmoke.", book,
                     provenance(intents=(("goal", "warmer"),)))
    run(psg_svc.passage_store.accept_revision(
        psg["id"], lineage_id=first["lineage_id"], scene_id=book["scene_id"],
        block_id=first["block_id"]))

    result = do_recall("hallway smelled")
    texts = [s["text"] for s in result["spans"]]
    assert "The hallway smelled of woodsmoke." in texts
    assert "The hallway smelled of turpentine." not in texts


def test_a_historical_version_is_recallable_only_on_request(store, book):
    first = commit("The hallway smelled of turpentine.", book)
    psg = quarantine("The hallway smelled of woodsmoke.", book,
                     provenance(intents=(("goal", "warmer"),)))
    run(psg_svc.passage_store.accept_revision(
        psg["id"], lineage_id=first["lineage_id"], scene_id=book["scene_id"],
        block_id=first["block_id"]))

    result = do_recall("hallway turpentine", include_historical=True)
    texts = [s["text"] for s in result["spans"]]
    assert "The hallway smelled of turpentine." in texts
    assert rc.verbatim_violations(result["spans"], ledger()) == []


def test_recall_is_scoped_to_this_project(store, book):
    commit(COLD_ROOM, book)

    async def elsewhere():
        return await rc.recall("some_other_manuscript", "cold room fire")
    assert run(elsewhere())["spans"] == []


def test_a_span_says_where_it_sits(store, book):
    commit(COLD_ROOM, book)
    span = do_recall("cold room")["spans"][0]

    assert span["location"]["scene_title"] == "The kitchen"
    assert span["location"]["chapter_title"] == "Chapter one"
    assert span["lineage_id"] and span["version"] == 1


def test_relevance_puts_the_matching_passage_first(store, book):
    commit(COLD_ROOM, book)
    commit(THE_SISTER, book)
    commit(THE_LATCH, book)

    assert do_recall("sister Easter visit")["spans"][0]["text"] == THE_SISTER
    assert do_recall("latch decided push")["spans"][0]["text"] == THE_LATCH


def test_the_ranker_is_pure_and_replaceable(store):
    """Isolated on purpose: a vector backend swaps in here without touching the
    verbatim path."""
    spans = [{"text": COLD_ROOM, "lineage_id": "a"}, {"text": THE_SISTER, "lineage_id": "b"}]
    scored = rc.score_spans("sister Easter", spans)
    assert scored[0][1]["lineage_id"] == "b"
    assert rc.score_spans("", spans) == []
    assert rc.score_spans("sister", []) == []


# ══ CITE ONLY COMMITTED CANON (gate step 4) ════════════════════════════════

def test_citing_committed_prose_resolves_to_its_exact_text(store, book):
    committed = commit(COLD_ROOM, book)
    resolved = run(rc.resolve_citations(
        PROJECT, [{"lineage_id": committed["lineage_id"]}]))

    assert len(resolved) == 1
    assert resolved[0]["text"] == COLD_ROOM
    assert resolved[0]["version"] == 1


def test_citing_a_quarantined_passage_is_refused(store, book):
    """I3 at the cite door — the whole point of step 4."""
    quarantine("An unaccepted sentence.", book)
    with pytest.raises(rc.RecallError, match="no committed version"):
        run(rc.resolve_citations(PROJECT, [{"lineage_id": "lin_not_committed"}]))


def test_citing_a_dismissed_passage_is_refused(store, book):
    psg = quarantine("A sentence that will be dismissed.", book)
    run(psg_svc.passage_store.dismiss(psg["id"]))
    with pytest.raises(rc.RecallError, match="no committed version"):
        run(rc.resolve_citations(PROJECT, [{"lineage_id": psg["id"]}]))


def test_one_bad_citation_refuses_the_whole_list(store, book):
    """No silent partial success: a citation list the author cannot trust to be complete
    is not an audit trail."""
    good = commit(COLD_ROOM, book)
    with pytest.raises(rc.RecallError):
        run(rc.resolve_citations(PROJECT, [
            {"lineage_id": good["lineage_id"]}, {"lineage_id": "lin_nonexistent"}]))


def test_a_citation_must_name_a_passage(store, book):
    with pytest.raises(rc.RecallError, match="must name the passage"):
        run(rc.resolve_citations(PROJECT, [{"version": 1}]))


def test_citing_another_projects_passage_is_refused(store, book):
    committed = commit(COLD_ROOM, book)

    async def elsewhere():
        return await rc.resolve_citations(
            "some_other_manuscript", [{"lineage_id": committed["lineage_id"]}])
    with pytest.raises(rc.RecallError):
        run(elsewhere())


def test_a_pinned_version_resolves_to_that_version(store, book):
    first = commit("The hallway smelled of turpentine.", book)
    psg = quarantine("The hallway smelled of woodsmoke.", book,
                     provenance(intents=(("goal", "warmer"),)))
    run(psg_svc.passage_store.accept_revision(
        psg["id"], lineage_id=first["lineage_id"], scene_id=book["scene_id"],
        block_id=first["block_id"]))

    pinned = run(rc.resolve_citations(
        PROJECT, [{"lineage_id": first["lineage_id"], "version": 1}]))
    assert pinned[0]["text"] == "The hallway smelled of turpentine."

    unpinned = run(rc.resolve_citations(PROJECT, [{"lineage_id": first["lineage_id"]}]))
    assert unpinned[0]["text"] == "The hallway smelled of woodsmoke."


# ══ the cited render (gate steps 3, 5, 7) ══════════════════════════════════

def _stub_render(monkeypatch, reply='{"passage": "She let the cold stand.", "refusal": ""}'):
    seen = {}

    async def fake(system, user):
        seen["system"], seen["user"] = system, user
        return reply, "stub-model"
    monkeypatch.setattr(render_svc, "_call_model", fake)
    return seen


def _directive(text="/ restraint(the cold)"):
    return parse_block(text).directives[0]


def test_the_cited_text_enters_the_prompt_verbatim(store, book, monkeypatch):
    committed = commit(COLD_ROOM, book)
    cited = run(rc.resolve_citations(PROJECT, [{"lineage_id": committed["lineage_id"]}]))
    seen = _stub_render(monkeypatch)

    run(render_svc.render_directive(PROJECT, _directive(), cited=cited))

    assert COLD_ROOM in seen["user"]
    assert f"{committed['lineage_id']}@v1" in seen["user"]


def test_the_prompt_asks_for_consistency_not_imitation(store, book, monkeypatch):
    """Committed prose is grounding, not a style reference — it would be the author's own
    voice arriving through a door that was not built for it."""
    committed = commit(COLD_ROOM, book)
    cited = run(rc.resolve_citations(PROJECT, [{"lineage_id": committed["lineage_id"]}]))
    prompt = render_svc.build_render_prompt(
        [run(op_svc.operator_registry.get(PROJECT, "restraint"))],
        {}, cited=rc.as_grounding(cited))

    assert "STAY CONSISTENT" in prompt["user"]
    assert "do not contradict it" in prompt["user"].lower()
    assert "take it as a style to imitate" in prompt["user"]


def test_a_cited_render_is_quarantined_and_writes_nothing(store, book, monkeypatch):
    """Gate step 3 — grounding a render on canon does not put anything into canon."""
    committed = commit(COLD_ROOM, book)
    before = run(ms_svc.manuscript_service.export_manuscript(book["manuscript_id"]))["content"]
    _stub_render(monkeypatch)

    result = run(studio.run_block(
        PROJECT, "/ restraint(the cold)",
        manuscript_id=book["manuscript_id"], scene_id=book["scene_id"],
        cited=run(rc.resolve_citations(PROJECT, [{"lineage_id": committed["lineage_id"]}]))))

    rendered = result["results"][0]
    assert rendered["status"] == OK
    assert rendered["passage_id"]
    assert run(psg_svc.passage_store.get(rendered["passage_id"]))["committed"] is False
    assert run(ms_svc.manuscript_service.export_manuscript(
        book["manuscript_id"]))["content"] == before


def test_provenance_records_which_passages_it_rested_on(store, book, monkeypatch):
    """I4 — gate step 7."""
    committed = commit(COLD_ROOM, book)
    cited = run(rc.resolve_citations(PROJECT, [{"lineage_id": committed["lineage_id"]}]))
    _stub_render(monkeypatch)

    result = run(render_svc.render_directive(PROJECT, _directive(), cited=cited))
    stamps = result.provenance["cited"]

    assert stamps == [{"lineage_id": committed["lineage_id"], "version": 1,
                       "passage_id": committed["passage_id"]}]


def test_a_cited_and_accepted_passage_keeps_its_citations(store, book, monkeypatch):
    committed = commit(COLD_ROOM, book)
    cited = run(rc.resolve_citations(PROJECT, [{"lineage_id": committed["lineage_id"]}]))
    _stub_render(monkeypatch)

    result = run(studio.run_block(
        PROJECT, "/ restraint(the cold)",
        manuscript_id=book["manuscript_id"], scene_id=book["scene_id"], cited=cited))
    accepted = run(psg_svc.passage_store.accept(
        result["results"][0]["passage_id"], scene_id=book["scene_id"]))

    version = run(rev_svc.version_store.resolve(accepted["lineage_id"], 1))
    assert version["provenance"]["cited"][0]["lineage_id"] == committed["lineage_id"]
    # and the passage it cited still resolves to the exact prose it rested on
    still = run(rc.resolve_citations(PROJECT, [{"lineage_id": committed["lineage_id"]}]))
    assert still[0]["text"] == COLD_ROOM


def test_an_uncited_render_records_an_empty_citation_list(store, book, monkeypatch):
    _stub_render(monkeypatch)
    result = run(render_svc.render_directive(PROJECT, _directive()))
    assert result.provenance["cited"] == []


# ══ the ontology wall still holds (gate step 5) ════════════════════════════

def test_a_cited_render_with_style_by_reference_still_refuses(store, book, monkeypatch):
    """I5 — cite adds grounding, it does not open a bypass."""
    committed = commit(COLD_ROOM, book)
    cited = run(rc.resolve_citations(PROJECT, [{"lineage_id": committed["lineage_id"]}]))

    async def explode(system, user):
        raise AssertionError("style-by-reference must refuse before the model is reached")
    monkeypatch.setattr(render_svc, "_call_model", explode)

    directive = parse_block(
        "// voice: like Tolstoy\n/ restraint(the cold)").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive, cited=cited))

    assert result.status == REFUSED
    assert "Tolstoy" in result.refusal
    # the citation is still on the record — what the author asked for is part of it
    assert result.provenance["cited"][0]["lineage_id"] == committed["lineage_id"]


def test_an_undefined_operator_still_refuses_even_when_citing(store, book, monkeypatch):
    committed = commit(COLD_ROOM, book)
    cited = run(rc.resolve_citations(PROJECT, [{"lineage_id": committed["lineage_id"]}]))

    async def explode(system, user):
        raise AssertionError("an undefined operator must refuse before the model")
    monkeypatch.setattr(render_svc, "_call_model", explode)

    directive = parse_block("/ nonexistent(x)").directives[0]
    assert run(render_svc.render_directive(
        PROJECT, directive, cited=cited)).status == REFUSED


def test_orchestration_still_cannot_leak_from_a_cited_render(store, book, monkeypatch):
    """I6 — the cited grounding does not become a new door for staging either."""
    committed = commit(COLD_ROOM, book)
    cited = run(rc.resolve_citations(PROJECT, [{"lineage_id": committed["lineage_id"]}]))
    _stub_render(monkeypatch,
                 '{"passage": "goal: she does not go in\\nShe let the cold stand.", '
                 '"refusal": ""}')

    directive = parse_block(
        "// goal: she does not go in\n/ restraint(the cold)").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive, cited=cited))

    assert "goal:" not in result.text
    assert result.diagnostics


# ══ canon untouched (gate step 6) ══════════════════════════════════════════

def test_recall_produces_no_prose_and_moves_nothing(store, book):
    commit(COLD_ROOM, book)
    commit(THE_SISTER, book)
    before = run(ms_svc.manuscript_service.export_manuscript(book["manuscript_id"]))["content"]
    ontology_before = run(op_svc.operator_registry.list(PROJECT))
    versions_before = run(rc.committed_spans(PROJECT, include_historical=True))

    for query in ("cold", "sister", "nothing at all like this", ""):
        do_recall(query, limit=10)

    after = run(ms_svc.manuscript_service.export_manuscript(book["manuscript_id"]))["content"]
    assert after == before
    assert run(op_svc.operator_registry.list(PROJECT)) == ontology_before
    assert run(rc.committed_spans(PROJECT, include_historical=True)) == versions_before


def test_recalled_prose_never_appears_twice_in_the_book(store, book):
    """No auto-insertion — recall is read-only w.r.t. canon."""
    commit(COLD_ROOM, book)
    do_recall("cold room fire", limit=10)

    export = run(ms_svc.manuscript_service.export_manuscript(
        book["manuscript_id"]))["content"]
    assert export.count(COLD_ROOM) == 1


# ══ instrumentation (§8 — log now, analyse later) ══════════════════════════

def test_a_recall_is_logged_with_its_query_and_hit_count(store, book):
    commit(COLD_ROOM, book)
    do_recall("cold room fire")

    events = run(instrument.usage_for_project(PROJECT, limit=200))
    recalled = next(e for e in events if e["event"] == rc.RECALLED)
    assert recalled["extra"]["query"] == "cold room fire"
    assert recalled["extra"]["hits"] == 1
    assert recalled["extra"]["searched"] >= 1


def test_a_recall_that_found_nothing_is_logged_too(store, book):
    commit(COLD_ROOM, book)
    do_recall("bathysphere")

    events = run(instrument.usage_for_project(PROJECT, limit=200))
    recalled = next(e for e in events if e["event"] == rc.RECALLED)
    assert recalled["extra"]["hits"] == 0
