"""
Semant Writer · W5 — the portable ontology.

W5 lifts the author's language above one manuscript. The evidence base widens from a
project's ontology to the AUTHOR'S, across their books — still their own declarations, so
still grounded. Two guardrails make that safe, and this suite is mostly about them:

  SINGLE AUTHOR (I5 across authors). An operator another person declared may not render
  into your canon. Refused at import, and refused again at render as a backstop.

  PINNED VERSIONS (I4, durable). Provenance keeps resolving through promote, import, edit,
  publish and pull. `test_writer_w5_provenance.py` proves the baseline before any of this
  exists; here it is re-checked across the library operations themselves.

And the design decision the whole gate turns on: import is a LINKED COPY, not a live
reference. Editing an imported operator in Book B changes neither the library nor Book A —
no spooky action. The tests below state that as behaviour, because it is the difference
between a portable language and a language that quietly rewrites books the author is not
currently looking at.
"""
import copy

import pytest

from backend.services import manuscript_service as ms_svc
from backend.services.writer import assemblages as asm
from backend.services.writer import dsl, instrument
from backend.services.writer import library as lib
from backend.services.writer import operators as op_svc
from backend.services.writer import passages as psg_svc
from backend.services.writer import render as render_svc
from backend.services.writer import studio
from backend.tests.test_writer_w1 import FakeCollection, run

AUTHOR = "adarsh"
OTHER = "someone-else"
BOOK_A = "ms_book_a"
BOOK_B = "ms_book_b"


@pytest.fixture
def store(monkeypatch):
    ops, psgs, usage, libc = FakeCollection(), FakeCollection(), FakeCollection(), FakeCollection()
    manuscripts, scenes, versions = FakeCollection(), FakeCollection(), FakeCollection()
    monkeypatch.setattr(op_svc, "writer_operator_collection", ops)
    monkeypatch.setattr(psg_svc, "writer_passage_collection", psgs)
    monkeypatch.setattr(instrument, "writer_usage_collection", usage)
    monkeypatch.setattr(asm, "writer_usage_collection", usage)
    monkeypatch.setattr(lib, "writer_library_collection", libc)
    monkeypatch.setattr(ms_svc, "manuscript_collection", manuscripts)
    monkeypatch.setattr(ms_svc, "scene_collection", scenes)
    monkeypatch.setattr(ms_svc, "scene_version_collection", versions)
    return {"operators": ops, "library": libc, "manuscripts": manuscripts, "scenes": scenes}


@pytest.fixture
def books(store):
    """Two manuscripts by the same author, each with a scene."""
    async def build():
        out = {}
        for pid, title in [(BOOK_A, "Book A"), (BOOK_B, "Book B")]:
            m = await ms_svc.manuscript_service.create_manuscript(title, author=AUTHOR)
            m = await ms_svc.manuscript_service.add_chapter(m["id"], "One")
            sc = await ms_svc.manuscript_service.add_scene(m["id"], m["chapters"][0]["id"], "Scene")
            out[pid] = {"manuscript_id": m["id"], "scene_id": sc["id"]}
        return out
    return run(build())


@pytest.fixture
def book_a_ontology(store):
    async def build():
        await op_svc.operator_registry.create(
            BOOK_A, "threshold", "a crossing noticed only after it is behind them",
            rendering_intent="one held moment", author=AUTHOR)
        await op_svc.operator_registry.create(
            BOOK_A, "interiority", "what the body knows before the mind admits it",
            rendering_intent="only what the body does", author=AUTHOR)
        return await op_svc.operator_registry.by_name(BOOK_A)
    return run(build())


def _stub(monkeypatch, reply='{"passage": "The latch gave.", "refusal": ""}'):
    async def fake(system, user):
        return reply, "stub-model"
    monkeypatch.setattr(render_svc, "_call_model", fake)


def promote(name, project=BOOK_A):
    async def go():
        return await lib.promote(AUTHOR, project, name,
                                 await op_svc.operator_registry.by_name(project))
    return run(go())


# ══ the single-author guard (I5 across authors) ══════════════════════════════

def test_the_guard_refuses_only_on_a_known_mismatch():
    """Absence is "nobody has said yet", not evidence of a foreign hand.

    Every operator and manuscript written before W5 has no author. A guard that refused on
    absence would refuse every existing project's every render.
    """
    assert lib.author_guard("", "") is None
    assert lib.author_guard(AUTHOR, "") is None
    assert lib.author_guard("", AUTHOR) is None
    assert lib.author_guard(AUTHOR, AUTHOR) is None
    assert lib.author_guard(OTHER, AUTHOR) is not None


def test_a_foreign_authored_operator_refuses_at_render(store, books, monkeypatch):
    """THE W5 gate check. Someone else's declaration may not make prose in your book."""
    run(op_svc.operator_registry.create(
        BOOK_A, "borrowed", "a crossing", rendering_intent="theirs", author=OTHER))

    async def explode(system, user):
        raise AssertionError("a foreign-authored operator must not reach the model")

    monkeypatch.setattr(render_svc, "_call_model", explode)
    directive = dsl.parse_block("/ borrowed\n").directives[0]
    result = run(render_svc.render_directive(
        BOOK_A, directive, manuscript_id=books[BOOK_A]["manuscript_id"]))

    assert result.status == render_svc.REFUSED
    assert result.text == ""
    assert "not yours to render from" in result.refusal
    assert OTHER in result.refusal


def test_the_authors_own_operator_still_renders(store, books, book_a_ontology, monkeypatch):
    _stub(monkeypatch)
    directive = dsl.parse_block("/ threshold\n").directives[0]
    result = run(render_svc.render_directive(
        BOOK_A, directive, manuscript_id=books[BOOK_A]["manuscript_id"]))
    assert result.status == "ok"


def test_an_unattributed_operator_still_renders(store, books, monkeypatch):
    """Migration safety: pre-W5 data has no author and must keep working."""
    run(op_svc.operator_registry.create(BOOK_A, "legacy", "written before W5"))
    _stub(monkeypatch)
    directive = dsl.parse_block("/ legacy\n").directives[0]
    result = run(render_svc.render_directive(
        BOOK_A, directive, manuscript_id=books[BOOK_A]["manuscript_id"]))
    assert result.status == "ok"


# ══ promote ══════════════════════════════════════════════════════════════════

def test_promote_lifts_an_operator_with_its_lineage(store, books, book_a_ontology):
    out = promote("threshold")
    entry = run(lib.get(AUTHOR, "threshold"))

    assert entry["author"] == AUTHOR
    assert entry["version"] == 1
    assert entry["definition"] == "a crossing noticed only after it is behind them"
    assert entry["source"]["project_id"] == BOOK_A
    assert entry["source"]["project_version"] == 1
    assert out["root"] == "threshold"


def test_book_a_is_untouched_by_promoting(store, books, book_a_ontology, monkeypatch):
    before = run(op_svc.operator_registry.list(BOOK_A))
    promote("threshold")
    assert run(op_svc.operator_registry.list(BOOK_A)) == before

    _stub(monkeypatch)
    directive = dsl.parse_block("/ threshold\n").directives[0]
    assert run(render_svc.render_directive(
        BOOK_A, directive, manuscript_id=books[BOOK_A]["manuscript_id"])).status == "ok"


def test_promoting_without_an_author_is_refused(store, books, book_a_ontology):
    async def go():
        return await lib.promote("", BOOK_A, "threshold",
                                 await op_svc.operator_registry.by_name(BOOK_A))
    with pytest.raises(lib.LibraryError, match="needs an author"):
        run(go())


# ══ transitive closure ═══════════════════════════════════════════════════════

def test_promote_brings_the_requires_closure(store, books, book_a_ontology):
    run(op_svc.operator_registry.set_relations(
        BOOK_A, "interiority", [{"target": "threshold", "kind": "requires"}]))
    out = promote("interiority")

    # dependencies come first, so nothing is ever written pointing at a missing operator
    assert out["closure"] == ["threshold", "interiority"]
    assert run(lib.get(AUTHOR, "threshold")) is not None


def test_promote_brings_assemblage_members(store, books, book_a_ontology):
    run(op_svc.operator_registry.create_assemblage(
        BOOK_A, "the_held_crossing", ["interiority", "threshold"],
        rendering_intent="mine, in my words", author=AUTHOR))
    out = promote("the_held_crossing")

    assert set(out["closure"]) == {"interiority", "threshold", "the_held_crossing"}
    assert out["closure"][-1] == "the_held_crossing"


def test_promote_refuses_and_names_a_missing_dependency(store, books, book_a_ontology):
    """Half a declared context is not a smaller ontology, it is a broken one."""
    run(op_svc.operator_registry.set_relations(
        BOOK_A, "interiority", [{"target": "threshold", "kind": "requires"}]))

    # an ontology view in which the dependency is absent — a partial project, or a caller
    # that resolved less than the whole of it
    partial = {"interiority": run(op_svc.operator_registry.get(BOOK_A, "interiority"))}
    with pytest.raises(lib.LibraryError, match="`threshold`"):
        run(lib.promote(AUTHOR, BOOK_A, "interiority", partial))

    # and nothing was written — a refused promote is not a partial promote
    assert run(lib.list_entries(AUTHOR)) == []


def test_import_refuses_when_the_library_lacks_a_dependency(store, books, book_a_ontology):
    promote("threshold")
    run(op_svc.operator_registry.set_relations(
        BOOK_A, "interiority", [{"target": "threshold", "kind": "requires"}]))
    promote("interiority")

    # remove the dependency from the library, as a partial library would look
    run(store["library"].delete_one({"author": AUTHOR, "name": "threshold"}))

    with pytest.raises(op_svc.OperatorError, match="`threshold`"):
        run(op_svc.operator_registry.import_from_library(BOOK_B, AUTHOR, "interiority"))


def test_closure_terminates_on_a_cycle_in_the_data():
    cyclic = {
        "a": {"name": "a", "relations": [{"target": "b", "kind": "requires"}]},
        "b": {"name": "b", "relations": [{"target": "a", "kind": "requires"}]},
    }
    ordered, missing = lib.closure("a", cyclic)
    assert missing == []
    assert set(ordered) == {"a", "b"}


def test_associative_edges_are_not_dependencies():
    """`evokes` is rendering-inert, so an operator renders perfectly without it."""
    ontology = {
        "a": {"name": "a", "relations": [{"target": "b", "kind": "evokes"}]},
        "b": {"name": "b", "relations": []},
    }
    ordered, missing = lib.closure("a", ontology)
    assert ordered == ["a"]
    assert missing == []


# ══ import — the linked copy ═════════════════════════════════════════════════

def test_import_makes_a_linked_copy_with_its_lineage(store, books, book_a_ontology):
    promote("threshold")
    run(op_svc.operator_registry.import_from_library(BOOK_B, AUTHOR, "threshold"))

    copy_b = run(op_svc.operator_registry.get(BOOK_B, "threshold"))
    assert copy_b["definition"] == "a crossing noticed only after it is behind them"
    assert copy_b["author"] == AUTHOR
    ref = copy_b["library_ref"]
    assert ref["author"] == AUTHOR and ref["name"] == "threshold" and ref["version"] == 1


def test_an_imported_operator_renders_grounded_and_names_its_lineage(
    store, books, book_a_ontology, monkeypatch
):
    promote("threshold")
    run(op_svc.operator_registry.import_from_library(BOOK_B, AUTHOR, "threshold"))
    _stub(monkeypatch)

    directive = dsl.parse_block("/ threshold\n").directives[0]
    result = run(render_svc.render_directive(
        BOOK_B, directive, manuscript_id=books[BOOK_B]["manuscript_id"]))

    assert result.status == "ok"
    stamp = result.provenance["operators"][0]
    assert stamp["name"] == "threshold"
    assert stamp["source"] == "direct"
    assert stamp["library_ref"]["version"] == 1        # which library version made this
    assert stamp["author"] == AUTHOR


def test_import_brings_the_closure_in_dependency_order(store, books, book_a_ontology):
    run(op_svc.operator_registry.set_relations(
        BOOK_A, "interiority", [{"target": "threshold", "kind": "requires"}]))
    promote("interiority")

    out = run(op_svc.operator_registry.import_from_library(BOOK_B, AUTHOR, "interiority"))
    assert out["closure"] == ["threshold", "interiority"]
    imported = run(op_svc.operator_registry.get(BOOK_B, "interiority"))
    assert imported["relations"] == [{"target": "threshold", "kind": "requires"}]
    assert run(op_svc.operator_registry.get(BOOK_B, "threshold")) is not None


def test_importing_a_foreign_authored_entry_is_refused(store, books, book_a_ontology):
    promote("threshold")
    with pytest.raises(op_svc.OperatorError, match="not in `someone-else`'s library"):
        run(op_svc.operator_registry.import_from_library(BOOK_B, OTHER, "threshold"))


# ══ NO SPOOKY ACTION — the load-bearing property ═════════════════════════════

def test_editing_an_import_touches_neither_the_library_nor_the_other_book(
    store, books, book_a_ontology
):
    """The whole reason import is a copy and not a live reference.

    A live reference would mean sharpening this operator while writing Book B silently
    changes what Book A's committed prose claims to have been made from.
    """
    promote("threshold")
    run(op_svc.operator_registry.import_from_library(BOOK_B, AUTHOR, "threshold"))

    library_before = copy.deepcopy(run(lib.get(AUTHOR, "threshold")))
    book_a_before = copy.deepcopy(run(op_svc.operator_registry.get(BOOK_A, "threshold")))

    run(op_svc.operator_registry.update(
        BOOK_B, "threshold", {"definition": "sharpened only for Book B"}))

    assert run(lib.get(AUTHOR, "threshold")) == library_before
    assert run(op_svc.operator_registry.get(BOOK_A, "threshold")) == book_a_before
    # and the project copy versions independently
    assert run(op_svc.operator_registry.get(BOOK_B, "threshold"))["version"] == 2


# ══ publish / pull — sync is explicit, both ways ═════════════════════════════

def test_publish_creates_a_new_library_version_and_keeps_the_old_one(
    store, books, book_a_ontology
):
    promote("threshold")
    run(op_svc.operator_registry.import_from_library(BOOK_B, AUTHOR, "threshold"))
    run(op_svc.operator_registry.update(BOOK_B, "threshold", {"definition": "improved in B"}))

    async def go():
        return await lib.publish(AUTHOR, BOOK_B, "threshold",
                                 await op_svc.operator_registry.get(BOOK_B, "threshold"))
    entry = run(go())

    assert entry["version"] == 2
    assert entry["definition"] == "improved in B"
    # old versions are NEVER discarded — committed passages pin them
    v1 = run(lib.resolve_version(AUTHOR, "threshold", 1))
    assert v1["definition"] == "a crossing noticed only after it is behind them"


def test_publishing_does_not_reach_into_another_project(store, books, book_a_ontology):
    """PROPOSE-ACCEPT across projects: a library version is available, never pushed."""
    promote("threshold")
    run(op_svc.operator_registry.import_from_library(BOOK_B, AUTHOR, "threshold"))
    run(op_svc.operator_registry.update(BOOK_B, "threshold", {"definition": "improved in B"}))
    book_a_before = copy.deepcopy(run(op_svc.operator_registry.get(BOOK_A, "threshold")))

    async def go():
        return await lib.publish(AUTHOR, BOOK_B, "threshold",
                                 await op_svc.operator_registry.get(BOOK_B, "threshold"))
    run(go())

    assert run(op_svc.operator_registry.get(BOOK_A, "threshold")) == book_a_before


def test_a_published_version_reaches_another_project_only_on_an_explicit_pull(
    store, books, book_a_ontology
):
    """PROPOSE-ACCEPT across books, end to end: publish makes available, pull accepts.

    Book B improves the operator and publishes. Book A keeps rendering exactly what it had
    until the author goes there and asks — which is the whole difference between a portable
    language and one that rewrites books nobody is looking at.
    """
    promote("threshold")
    run(op_svc.operator_registry.import_from_library(BOOK_B, AUTHOR, "threshold"))
    # Book A takes the library copy too, so it has a `library_ref` to pull against
    run(op_svc.operator_registry.delete(BOOK_A, "threshold"))
    run(op_svc.operator_registry.import_from_library(BOOK_A, AUTHOR, "threshold"))

    run(op_svc.operator_registry.update(BOOK_B, "threshold", {"definition": "improved in B"}))

    async def publish_b():
        return await lib.publish(AUTHOR, BOOK_B, "threshold",
                                 await op_svc.operator_registry.get(BOOK_B, "threshold"))
    run(publish_b())

    # nothing happened to Book A
    assert run(op_svc.operator_registry.get(BOOK_A, "threshold"))["definition"] == \
        "a crossing noticed only after it is behind them"

    # ...until the author asks for it
    out = run(op_svc.operator_registry.pull_from_library(BOOK_A, AUTHOR, "threshold"))
    assert out["changed"] is True
    assert run(op_svc.operator_registry.get(BOOK_A, "threshold"))["definition"] == "improved in B"


def test_pull_is_a_no_op_when_already_current(store, books, book_a_ontology):
    promote("threshold")
    run(op_svc.operator_registry.import_from_library(BOOK_B, AUTHOR, "threshold"))
    out = run(op_svc.operator_registry.pull_from_library(BOOK_B, AUTHOR, "threshold"))
    assert out["changed"] is False


def test_pull_brings_a_newer_version_down_when_asked(store, books, book_a_ontology):
    promote("threshold")
    run(op_svc.operator_registry.import_from_library(BOOK_B, AUTHOR, "threshold"))

    # a newer library version arrives from somewhere else
    run(op_svc.operator_registry.update(BOOK_A, "threshold", {"definition": "sharpened in A"}))

    async def publish_a():
        return await lib.publish(AUTHOR, BOOK_A, "threshold",
                                 await op_svc.operator_registry.get(BOOK_A, "threshold"))
    run(publish_a())

    before = run(op_svc.operator_registry.get(BOOK_B, "threshold"))
    assert before["definition"] == "a crossing noticed only after it is behind them"

    out = run(op_svc.operator_registry.pull_from_library(BOOK_B, AUTHOR, "threshold"))
    assert out["changed"] is True
    after = run(op_svc.operator_registry.get(BOOK_B, "threshold"))
    assert after["definition"] == "sharpened in A"
    assert after["library_ref"]["version"] == 2


def test_publishing_to_an_unpromoted_operator_is_refused(store, books, book_a_ontology):
    async def go():
        return await lib.publish(AUTHOR, BOOK_A, "threshold",
                                 await op_svc.operator_registry.get(BOOK_A, "threshold"))
    with pytest.raises(lib.LibraryError, match="promote it before publishing"):
        run(go())


# ══ I4 durable across the library operations ════════════════════════════════

def test_provenance_resolves_after_a_full_library_session(store, books, book_a_ontology,
                                                          monkeypatch):
    """A passage committed in Book B still names what made it after publish/edit/pull."""
    _stub(monkeypatch)
    promote("threshold")
    run(op_svc.operator_registry.import_from_library(BOOK_B, AUTHOR, "threshold"))

    b = books[BOOK_B]
    out = run(studio.run_block(BOOK_B, "/ threshold\n",
                               manuscript_id=b["manuscript_id"], scene_id=b["scene_id"]))
    run(psg_svc.passage_store.accept(out["results"][0]["passage_id"]))

    # then the author churns the ontology around it
    run(op_svc.operator_registry.update(BOOK_B, "threshold", {"definition": "sharpened"}))

    async def publish_b():
        return await lib.publish(AUTHOR, BOOK_B, "threshold",
                                 await op_svc.operator_registry.get(BOOK_B, "threshold"))
    run(publish_b())
    run(op_svc.operator_registry.pull_from_library(BOOK_B, AUTHOR, "threshold"))

    block = run(ms_svc.manuscript_service.get_scene(b["scene_id"]))["blocks"][0]
    check = run(op_svc.operator_registry.resolve_provenance(BOOK_B, block["provenance"]))
    assert check["missing"] == []
    # and it resolves to the version that actually made it, not the current one
    assert check["resolved"][0]["definition"] == "a crossing noticed only after it is behind them"


# ══ I1/I3 — canon untouched by every library operation ══════════════════════

def test_no_library_operation_touches_canon(store, books, book_a_ontology, monkeypatch):
    a, b = books[BOOK_A], books[BOOK_B]
    run(ms_svc.manuscript_service.update_scene(a["scene_id"], {"blocks": [
        {"id": "b1", "type": "paragraph", "content": "<p>She crossed before she decided to.</p>",
         "color": None, "origin": "human"}]}))

    before_a = run(ms_svc.manuscript_service.export_manuscript(a["manuscript_id"]))["content"]
    before_b = run(ms_svc.manuscript_service.export_manuscript(b["manuscript_id"]))["content"]

    run(op_svc.operator_registry.set_relations(
        BOOK_A, "interiority", [{"target": "threshold", "kind": "requires"}]))
    promote("interiority")
    run(op_svc.operator_registry.import_from_library(BOOK_B, AUTHOR, "interiority"))
    run(op_svc.operator_registry.update(BOOK_B, "threshold", {"definition": "edited in B"}))

    async def publish_b():
        return await lib.publish(AUTHOR, BOOK_B, "threshold",
                                 await op_svc.operator_registry.get(BOOK_B, "threshold"))
    run(publish_b())
    run(op_svc.operator_registry.pull_from_library(BOOK_B, AUTHOR, "threshold"))

    assert run(ms_svc.manuscript_service.export_manuscript(a["manuscript_id"]))["content"] == before_a
    assert run(ms_svc.manuscript_service.export_manuscript(b["manuscript_id"]))["content"] == before_b


# ══ instrumentation ══════════════════════════════════════════════════════════

def test_every_library_operation_is_logged(store, books, book_a_ontology):
    promote("threshold")
    run(op_svc.operator_registry.import_from_library(BOOK_B, AUTHOR, "threshold"))
    run(op_svc.operator_registry.update(BOOK_B, "threshold", {"definition": "improved"}))

    async def publish_b():
        return await lib.publish(AUTHOR, BOOK_B, "threshold",
                                 await op_svc.operator_registry.get(BOOK_B, "threshold"))
    run(publish_b())
    run(op_svc.operator_registry.pull_from_library(BOOK_B, AUTHOR, "threshold"))

    events = {e["event"] for e in run(instrument.usage_for_project(BOOK_A, limit=500))}
    events |= {e["event"] for e in run(instrument.usage_for_project(BOOK_B, limit=500))}
    assert {lib.PROMOTED, lib.IMPORTED, lib.PUBLISHED, lib.PULLED} <= events
