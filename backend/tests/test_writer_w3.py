"""
Semant Writer · W3 — typed relations, and the one edge that acts.

W3 is the first gate where the ontology acts on its own: one operator reaching for
another. That is exactly where a writing tool would start quietly composing on the
author's behalf, so the tests here are mostly about what `requires` is NOT allowed to do.

What is pinned:
  I5   an edge target is an operator REFERENCE — undefined targets are rejected at edit
       time, and there is no way to put free text or a corpus name on an edge at all;
  I4   every operator pulled in through `requires` appears in provenance, marked pulled
       rather than direct — an audit trail that named only the typed operators would lie
       by omission;
  term the `requires` graph terminates — cycles rejected at EDIT time and defended again
       at RENDER time, because a guard on the write path assumes the write path is the
       only way data arrives;
  seq  composition stays sequential — `evokes`/`amplifies`/`contrasts`/`precedes` are
       rendering-inert, and acting on them would be the blended field Tier 3 reserves.

House style matches `test_writer_w1.py`: sync tests over async services with injected fake
Mongo collections. The model is stubbed; the live proof is `scripts/writer_w3_proof.py`.
"""
import asyncio
import copy

import pytest

from backend.services import manuscript_service as ms_svc
from backend.services.writer import dsl, instrument
from backend.services.writer import operators as op_svc
from backend.services.writer import passages as psg_svc
from backend.services.writer import revisions as rev_svc
from backend.services.writer import relations as rel
from backend.services.writer import render as render_svc
from backend.services.writer import studio
from backend.tests.test_writer_w1 import FakeCollection, run

PROJECT = "ms_fixture"


@pytest.fixture
def store(monkeypatch):
    ops, psgs, usage = FakeCollection(), FakeCollection(), FakeCollection()
    manuscripts, scenes, versions = FakeCollection(), FakeCollection(), FakeCollection()
    monkeypatch.setattr(op_svc, "writer_operator_collection", ops)
    monkeypatch.setattr(psg_svc, "writer_passage_collection", psgs)
    # W8 — Accept records an immutable version; it is ledger, not write-behind,
    # so it must be faked rather than allowed to reach the real collection.
    monkeypatch.setattr(rev_svc, "writer_passage_version_collection", FakeCollection())
    monkeypatch.setattr(instrument, "writer_usage_collection", usage)
    monkeypatch.setattr(ms_svc, "manuscript_collection", manuscripts)
    monkeypatch.setattr(ms_svc, "scene_collection", scenes)
    monkeypatch.setattr(ms_svc, "scene_version_collection", versions)
    return {"operators": ops, "passages": psgs, "usage": usage, "scenes": scenes,
            "manuscripts": manuscripts}


@pytest.fixture
def ontology(store):
    """Two operators, no edges yet."""
    async def build():
        await op_svc.operator_registry.create(
            PROJECT, "threshold", "a crossing noticed only after it is behind them")
        await op_svc.operator_registry.create(
            PROJECT, "interiority", "what the body knows before the mind admits it")
        return await op_svc.operator_registry.by_name(PROJECT)
    return run(build())


def _stub_model(monkeypatch, reply):
    async def fake(system, user):
        return (reply(system, user) if callable(reply) else reply), "stub-model"
    monkeypatch.setattr(render_svc, "_call_model", fake)


def _capture_prompt(monkeypatch, seen):
    def capture(system, user):
        seen["user"] = user
        return '{"passage": "The latch gave.", "refusal": ""}'
    _stub_model(monkeypatch, capture)


# ══ the vocabulary ═══════════════════════════════════════════════════════════

def test_the_edge_vocabulary_is_closed():
    assert rel.RELATION_KINDS == ("requires", "precedes", "evokes", "amplifies", "contrasts")
    # exactly one edge acts on rendering in v1
    assert rel.RENDERING_KINDS == frozenset({"requires"})


def test_an_unknown_kind_is_rejected():
    with pytest.raises(rel.RelationError, match="not a relation kind"):
        rel.normalise({"target": "threshold", "kind": "resembles"})


def test_a_relation_needs_a_target():
    with pytest.raises(rel.RelationError):
        rel.normalise({"kind": "requires"})


# ══ I5 — an edge is an operator reference, never free text ═══════════════════

def test_requires_an_undefined_operator_is_rejected_at_edit_time(store, ontology):
    with pytest.raises(op_svc.OperatorError if False else rel.RelationError, match="not an operator"):
        run(op_svc.operator_registry.set_relations(
            PROJECT, "interiority", [{"target": "ekstasis", "kind": "requires"}]))


def test_an_edge_cannot_carry_a_corpus_or_free_text(store, ontology):
    """I5 by construction: there is no shape of edge whose target is prose.

    `requires "like Tolstoy"` is not a thing that can be stored — the target is looked up
    in the ontology, so a style reference cannot enter through an edge the way it could
    through a `//voice` note.
    """
    for target in ("like Tolstoy", "a 19th-century Russian novel", "noir"):
        with pytest.raises(rel.RelationError, match="not an operator"):
            run(op_svc.operator_registry.set_relations(
                PROJECT, "interiority", [{"target": target, "kind": "requires"}]))


def test_an_operator_cannot_relate_to_itself(store, ontology):
    with pytest.raises(rel.RelationError, match="cannot relate to itself"):
        run(op_svc.operator_registry.set_relations(
            PROJECT, "interiority", [{"target": "interiority", "kind": "requires"}]))


# ══ storing edges, and the version bump ══════════════════════════════════════

def test_setting_relations_bumps_the_version(store, ontology):
    """Relations are part of the operator's identity, not metadata beside it."""
    before = run(op_svc.operator_registry.get(PROJECT, "interiority"))
    assert before["version"] == 1

    after = run(op_svc.operator_registry.set_relations(
        PROJECT, "interiority", [{"target": "threshold", "kind": "requires"}]))

    assert after["version"] == 2
    assert after["relations"] == [{"target": "threshold", "kind": "requires"}]
    # and the prior body is retained, so a passage citing v1 stays readable
    assert after["history"][0]["version"] == 1
    assert after["history"][0]["relations"] == []


def test_a_duplicate_edge_is_stored_once(store, ontology):
    out = run(op_svc.operator_registry.set_relations(PROJECT, "interiority", [
        {"target": "threshold", "kind": "requires"},
        {"target": "threshold", "kind": "requires"},
    ]))
    assert len(out["relations"]) == 1


def test_relations_are_project_scoped(store, ontology):
    run(op_svc.operator_registry.set_relations(
        PROJECT, "interiority", [{"target": "threshold", "kind": "requires"}]))
    assert run(op_svc.operator_registry.get("another_project", "interiority")) is None


# ══ termination — cycles rejected twice ══════════════════════════════════════

def test_a_direct_cycle_is_rejected_at_edit_time(store, ontology):
    run(op_svc.operator_registry.set_relations(
        PROJECT, "interiority", [{"target": "threshold", "kind": "requires"}]))

    with pytest.raises(rel.RelationError, match="would close a cycle"):
        run(op_svc.operator_registry.set_relations(
            PROJECT, "threshold", [{"target": "interiority", "kind": "requires"}]))


def test_a_transitive_cycle_is_rejected_at_edit_time(store, ontology):
    run(op_svc.operator_registry.create(PROJECT, "hinge", "the turn a scene pivots on"))
    run(op_svc.operator_registry.set_relations(
        PROJECT, "interiority", [{"target": "threshold", "kind": "requires"}]))
    run(op_svc.operator_registry.set_relations(
        PROJECT, "threshold", [{"target": "hinge", "kind": "requires"}]))

    # hinge → interiority would close interiority → threshold → hinge → interiority
    with pytest.raises(rel.RelationError, match="would close a cycle"):
        run(op_svc.operator_registry.set_relations(
            PROJECT, "hinge", [{"target": "interiority", "kind": "requires"}]))


def test_a_batch_cannot_smuggle_in_a_cycle(store, ontology):
    """Each edge is checked against the set accepted so far, not just the stored set."""
    run(op_svc.operator_registry.create(PROJECT, "hinge", "the turn a scene pivots on"))
    run(op_svc.operator_registry.set_relations(
        PROJECT, "threshold", [{"target": "hinge", "kind": "requires"}]))
    with pytest.raises(rel.RelationError, match="would close a cycle"):
        run(op_svc.operator_registry.set_relations(PROJECT, "hinge", [
            {"target": "interiority", "kind": "requires"},
            {"target": "threshold", "kind": "requires"},   # closes it via the first
        ]))


def test_render_time_resolution_terminates_on_a_cycle_already_in_the_data():
    """The edit-time guard assumes the write path is the only way data arrives. It is not.

    A cycle reaching the collection by any other route — a direct edit, a restored backup,
    a future import — must not hang the render loop.
    """
    cyclic = {
        "a": {"name": "a", "relations": [{"target": "b", "kind": "requires"}]},
        "b": {"name": "b", "relations": [{"target": "a", "kind": "requires"}]},
    }
    pulled, diagnostics = rel.resolve_requires(["a"], cyclic)
    assert pulled == ["b"]                      # finite
    assert any("cycle" in d for d in diagnostics)


def test_a_diamond_is_not_mistaken_for_a_cycle():
    """`a→b`, `a→c`, `b→c` revisits `c` legitimately. Reporting it would cry wolf."""
    diamond = {
        "a": {"name": "a", "relations": [
            {"target": "b", "kind": "requires"}, {"target": "c", "kind": "requires"}]},
        "b": {"name": "b", "relations": [{"target": "c", "kind": "requires"}]},
        "c": {"name": "c", "relations": []},
    }
    pulled, diagnostics = rel.resolve_requires(["a"], diamond)
    assert sorted(pulled) == ["b", "c"]
    assert pulled.count("c") == 1          # pulled once, not twice
    assert diagnostics == []


def test_a_deep_chain_is_bounded():
    deep = {
        f"op{i}": {"name": f"op{i}", "relations": [{"target": f"op{i+1}", "kind": "requires"}]}
        for i in range(rel.MAX_REQUIRES_DEPTH + 5)
    }
    pulled, diagnostics = rel.resolve_requires(["op0"], deep)
    assert len(pulled) <= rel.MAX_REQUIRES_DEPTH + 1
    assert any("deeper than" in d for d in diagnostics)


# ══ I4 — requires feeds rendering, and provenance says so ════════════════════

def test_requires_pulls_the_definition_into_the_same_span(store, ontology, monkeypatch):
    seen = {}
    _capture_prompt(monkeypatch, seen)
    run(op_svc.operator_registry.set_relations(
        PROJECT, "interiority", [{"target": "threshold", "kind": "requires"}]))

    directive = dsl.parse_block("/ interiority\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    assert result.status == "ok"
    # the required operator's own words are in the prompt
    assert "a crossing noticed only after it is behind them" in seen["user"]
    # and it is framed as GROUNDING for one span, not as a second thing to render
    assert "GROUNDING THE AUTHOR HAS DECLARED" in seen["user"]
    assert "one passage" in seen["user"]


def test_provenance_marks_pulled_apart_from_direct(store, ontology, monkeypatch):
    """The author typed only `/interiority`. Provenance must name what else shaped it."""
    _stub_model(monkeypatch, '{"passage": "The latch gave.", "refusal": ""}')
    run(op_svc.operator_registry.set_relations(
        PROJECT, "interiority", [{"target": "threshold", "kind": "requires"}]))

    directive = dsl.parse_block("/ interiority\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    by_name = {o["name"]: o for o in result.provenance["operators"]}
    assert by_name["interiority"]["source"] == "direct"
    assert by_name["threshold"]["source"] == "pulled_via_requires"
    assert result.provenance["pulled_operators"] == ["threshold"]
    assert result.provenance["requested_operators"] == ["interiority"]
    # both are author-defined, so both carry a version
    assert all(o["version"] for o in result.provenance["operators"])


def test_requires_resolves_transitively_and_marks_every_hop(store, ontology, monkeypatch):
    _stub_model(monkeypatch, '{"passage": "The latch gave.", "refusal": ""}')
    run(op_svc.operator_registry.create(PROJECT, "hinge", "the turn a scene pivots on"))
    run(op_svc.operator_registry.set_relations(
        PROJECT, "interiority", [{"target": "threshold", "kind": "requires"}]))
    run(op_svc.operator_registry.set_relations(
        PROJECT, "threshold", [{"target": "hinge", "kind": "requires"}]))

    directive = dsl.parse_block("/ interiority\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    assert result.provenance["pulled_operators"] == ["threshold", "hinge"]
    sources = {o["name"]: o["source"] for o in result.provenance["operators"]}
    assert sources == {
        "interiority": "direct",
        "threshold": "pulled_via_requires",
        "hinge": "pulled_via_requires",
    }


def test_a_dangling_requires_edge_diagnoses_rather_than_failing_the_span(store, ontology,
                                                                        monkeypatch):
    """The author's DIRECT request is still renderable; the broken edge is never silent."""
    _stub_model(monkeypatch, '{"passage": "The latch gave.", "refusal": ""}')
    # bypass edit-time validation, as a stale ontology or a hand edit would
    run(store["operators"].update_one(
        {"project_id": PROJECT, "name": "interiority"},
        {"$set": {"relations": [{"target": "ekstasis", "kind": "requires"}]}}))

    directive = dsl.parse_block("/ interiority\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    assert result.status == "ok"
    assert result.provenance["pulled_operators"] == []
    assert any("is not defined" in d for d in result.diagnostics)


def test_pulled_operators_are_recorded_for_later_tiers(store, ontology, monkeypatch):
    """W4's assemblage detection reads exactly this."""
    _stub_model(monkeypatch, '{"passage": "The latch gave.", "refusal": ""}')
    run(op_svc.operator_registry.set_relations(
        PROJECT, "interiority", [{"target": "threshold", "kind": "requires"}]))
    directive = dsl.parse_block("/ interiority\n").directives[0]
    run(render_svc.render_directive(PROJECT, directive))

    events = run(instrument.usage_for_project(PROJECT))
    rendered = next(e for e in events if e["event"] == "render")
    assert rendered["extra"]["pulled_operators"] == ["threshold"]


# ══ sequential composition — every other edge is inert ═══════════════════════

@pytest.mark.parametrize("kind", ["evokes", "amplifies", "contrasts", "precedes"])
def test_a_non_requires_edge_does_not_touch_the_render(store, ontology, monkeypatch, kind):
    """Acting on an associative edge would be the blended field Tier 3 reserves.

    Its cost is not aesthetic: two operators conditioning one span as a field makes
    provenance unable to say which produced which part of the prose, and that is the
    audit trail `GROUNDING.md` rests on.
    """
    seen = {}
    _capture_prompt(monkeypatch, seen)
    run(op_svc.operator_registry.set_relations(
        PROJECT, "interiority", [{"target": "threshold", "kind": kind}]))

    directive = dsl.parse_block("/ interiority\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    # absent from the prompt
    assert "a crossing noticed only after it is behind them" not in seen["user"]
    assert "GROUNDING THE AUTHOR HAS DECLARED" not in seen["user"]
    # and absent from provenance
    assert result.provenance["pulled_operators"] == []
    assert [o["name"] for o in result.provenance["operators"]] == ["interiority"]


def test_precedes_does_not_reorder_directives(store, ontology, monkeypatch):
    """`precedes` is advisory in the graph. The author's written order is the order."""
    _stub_model(monkeypatch, '{"passage": "The latch gave.", "refusal": ""}')
    run(op_svc.operator_registry.set_relations(
        PROJECT, "interiority", [{"target": "threshold", "kind": "precedes"}]))

    out = run(studio.run_block(PROJECT, "/ interiority\n/ threshold\n", quarantine=False))
    assert [r["operators"] for r in out["results"]] == [["interiority"], ["threshold"]]


# ══ I1/I3 — the ontology is not the canon ════════════════════════════════════

def test_editing_relations_never_touches_the_manuscript(store, ontology):
    """The graph is a view over the ledger. Editing it cannot move a word of canon."""
    async def build():
        m = await ms_svc.manuscript_service.create_manuscript("Fixture")
        m = await ms_svc.manuscript_service.add_chapter(m["id"], "One")
        scene = await ms_svc.manuscript_service.add_scene(
            m["id"], m["chapters"][0]["id"], "Scene one",
            blocks=[{"id": "b1", "type": "paragraph",
                     "content": "<p>She crossed before she decided to.</p>",
                     "color": None, "origin": "human"}])
        return m["id"], scene["id"]

    manuscript_id, scene_id = run(build())
    before = run(ms_svc.manuscript_service.export_manuscript(manuscript_id))["content"]

    run(op_svc.operator_registry.set_relations(
        PROJECT, "interiority", [{"target": "threshold", "kind": "requires"}]))
    run(op_svc.operator_registry.set_relations(
        PROJECT, "threshold", [{"target": "interiority", "kind": "evokes"}]))

    after = run(ms_svc.manuscript_service.export_manuscript(manuscript_id))["content"]
    assert after == before
    assert run(ms_svc.manuscript_service.get_scene(scene_id))["blocks"][0]["content"] == \
        "<p>She crossed before she decided to.</p>"
