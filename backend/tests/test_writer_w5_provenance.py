"""
Semant Writer · W5 §9 step 1 — provenance durability, BEFORE the library is built on top.

The W5 directive puts this first and says: if it fails, stop. The reason is that W5 makes
the ontology portable, and portability is safe exactly as long as every committed passage
can still name the exact operator version that made it. A migration that quietly broke
version resolution would leave prose in the canon whose audit trail no longer resolves —
and nothing built afterwards could repair it, because the information would be gone.

WHAT THIS FOUND. Until W5 there was no resolver at all. Provenance recorded `name@version`
faithfully from W1 onward, but no code could turn that pin back into the operator body, so
"what wrote this paragraph?" had an answer the system could not produce. `history` held the
material; nothing read it. So step 1 is not only a check — it is the check plus the
resolver it needs, and these tests pin both.

Each test below reconstructs a real W1–W4 flow and then resolves every provenance record it
produced. No fixture shortcuts: the provenance under test is the provenance the actual paths
write.
"""
import pytest

from backend.services import manuscript_service as ms_svc
from backend.services.writer import assemblages as asm
from backend.services.writer import dsl, instrument
from backend.services.writer import operators as op_svc
from backend.services.writer import passages as psg_svc
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
    monkeypatch.setattr(instrument, "writer_usage_collection", usage)
    monkeypatch.setattr(asm, "writer_usage_collection", usage)
    monkeypatch.setattr(ms_svc, "manuscript_collection", manuscripts)
    monkeypatch.setattr(ms_svc, "scene_collection", scenes)
    monkeypatch.setattr(ms_svc, "scene_version_collection", versions)
    return {"operators": ops, "passages": psgs, "scenes": scenes}


@pytest.fixture
def scene(store):
    async def build():
        m = await ms_svc.manuscript_service.create_manuscript("Book A")
        m = await ms_svc.manuscript_service.add_chapter(m["id"], "One")
        sc = await ms_svc.manuscript_service.add_scene(m["id"], m["chapters"][0]["id"], "Scene one")
        return m["id"], sc["id"]
    return run(build())


def _stub(monkeypatch, reply='{"passage": "The latch gave.", "refusal": ""}'):
    async def fake(system, user):
        return reply, "stub-model"
    monkeypatch.setattr(render_svc, "_call_model", fake)


def resolve(provenance):
    return run(op_svc.operator_registry.resolve_provenance(PROJECT, provenance))


# ══ the resolver itself ══════════════════════════════════════════════════════

def test_the_current_version_resolves(store):
    op = run(op_svc.operator_registry.create(PROJECT, "threshold", "a crossing noticed late"))
    body = run(op_svc.operator_registry.resolve_version(PROJECT, "threshold", op["version"]))
    assert body["definition"] == "a crossing noticed late"


def test_an_older_version_resolves_to_what_it_actually_said(store):
    """The point of pinning a version: v1 must keep meaning what v1 meant."""
    run(op_svc.operator_registry.create(PROJECT, "threshold", "a crossing noticed late"))
    run(op_svc.operator_registry.update(PROJECT, "threshold", {"definition": "rewritten"}))
    run(op_svc.operator_registry.update(PROJECT, "threshold", {"definition": "rewritten again"}))

    v1 = run(op_svc.operator_registry.resolve_version(PROJECT, "threshold", 1))
    v2 = run(op_svc.operator_registry.resolve_version(PROJECT, "threshold", 2))
    v3 = run(op_svc.operator_registry.resolve_version(PROJECT, "threshold", 3))

    assert v1["definition"] == "a crossing noticed late"
    assert v2["definition"] == "rewritten"
    assert v3["definition"] == "rewritten again"
    # stable identity travels with every version
    assert v1["name"] == v2["name"] == v3["name"] == "threshold"
    assert v1["id"] == v3["id"]


def test_an_unresolvable_version_returns_none_rather_than_the_nearest_thing(store):
    run(op_svc.operator_registry.create(PROJECT, "threshold", "a crossing noticed late"))
    assert run(op_svc.operator_registry.resolve_version(PROJECT, "threshold", 9)) is None
    assert run(op_svc.operator_registry.resolve_version(PROJECT, "ekstasis", 1)) is None


def test_a_relations_edit_is_a_resolvable_version(store):
    """W3 bumps the version on an edge edit — that version has to resolve too."""
    run(op_svc.operator_registry.create(PROJECT, "threshold", "a crossing"))
    run(op_svc.operator_registry.create(PROJECT, "interiority", "what the body knows"))
    run(op_svc.operator_registry.set_relations(
        PROJECT, "interiority", [{"target": "threshold", "kind": "requires"}]))

    v1 = run(op_svc.operator_registry.resolve_version(PROJECT, "interiority", 1))
    v2 = run(op_svc.operator_registry.resolve_version(PROJECT, "interiority", 2))
    assert v1["relations"] == []
    assert v2["relations"] == [{"target": "threshold", "kind": "requires"}]


# ══ every W1–W4 provenance record still resolves ═════════════════════════════

def test_w1_a_committed_passage_resolves_its_operators(store, scene, monkeypatch):
    manuscript_id, scene_id = scene
    run(op_svc.operator_registry.create(PROJECT, "threshold", "a crossing noticed late"))
    _stub(monkeypatch)

    out = run(studio.run_block(PROJECT, "// goal: cross it\n/ threshold\n",
                               manuscript_id=manuscript_id, scene_id=scene_id))
    run(psg_svc.passage_store.accept(out["results"][0]["passage_id"]))

    block = run(ms_svc.manuscript_service.get_scene(scene_id))["blocks"][0]
    check = resolve(block["provenance"])
    assert check["missing"] == []
    assert check["resolved"][0]["definition"] == "a crossing noticed late"


def test_w1_provenance_survives_a_later_edit_to_the_operator(store, scene, monkeypatch):
    """THE case this whole check exists for.

    The author renders, accepts, then sharpens the operator. The committed passage still
    says it was made by v1, and v1 must still be producible — otherwise the audit trail
    silently becomes a claim about an operator that no longer exists in that form.
    """
    manuscript_id, scene_id = scene
    run(op_svc.operator_registry.create(PROJECT, "threshold", "a crossing noticed late"))
    _stub(monkeypatch)
    out = run(studio.run_block(PROJECT, "/ threshold\n",
                               manuscript_id=manuscript_id, scene_id=scene_id))
    run(psg_svc.passage_store.accept(out["results"][0]["passage_id"]))

    run(op_svc.operator_registry.update(
        PROJECT, "threshold", {"definition": "a crossing felt in the body"}))

    block = run(ms_svc.manuscript_service.get_scene(scene_id))["blocks"][0]
    assert block["provenance"]["operators"][0]["version"] == 1
    check = resolve(block["provenance"])
    assert check["missing"] == []
    # v1, not the sharpened text
    assert check["resolved"][0]["definition"] == "a crossing noticed late"


def test_w3_a_pulled_operator_resolves_and_keeps_its_mark(store, scene, monkeypatch):
    manuscript_id, scene_id = scene
    run(op_svc.operator_registry.create(PROJECT, "threshold", "a crossing noticed late"))
    run(op_svc.operator_registry.create(PROJECT, "interiority", "what the body knows"))
    run(op_svc.operator_registry.set_relations(
        PROJECT, "interiority", [{"target": "threshold", "kind": "requires"}]))
    _stub(monkeypatch)

    out = run(studio.run_block(PROJECT, "/ interiority\n",
                               manuscript_id=manuscript_id, scene_id=scene_id))
    run(psg_svc.passage_store.accept(out["results"][0]["passage_id"]))

    block = run(ms_svc.manuscript_service.get_scene(scene_id))["blocks"][0]
    check = resolve(block["provenance"])
    assert check["missing"] == []
    marks = {r["name"]: r["source"] for r in check["resolved"]}
    assert marks == {"interiority": "direct", "threshold": "pulled_via_requires"}


def test_w4_an_assemblage_render_resolves(store, scene, monkeypatch):
    manuscript_id, scene_id = scene
    for n, d in [("threshold", "a crossing"), ("interiority", "what the body knows"),
                 ("hush", "the sound that stops")]:
        run(op_svc.operator_registry.create(PROJECT, n, d))
    run(op_svc.operator_registry.create_assemblage(
        PROJECT, "the_held_crossing", ["interiority", "threshold", "hush"],
        rendering_intent="the body arrives before the mind does"))
    _stub(monkeypatch)

    out = run(studio.run_block(PROJECT, "/ the_held_crossing\n",
                               manuscript_id=manuscript_id, scene_id=scene_id))
    run(psg_svc.passage_store.accept(out["results"][0]["passage_id"]))

    block = run(ms_svc.manuscript_service.get_scene(scene_id))["blocks"][0]
    check = resolve(block["provenance"])
    assert check["missing"] == []
    assert check["resolved"][0]["name"] == "the_held_crossing"


def test_every_provenance_record_in_a_mixed_session_resolves(store, scene, monkeypatch):
    """The gate's step 1, as one sweep: a session using every W1–W4 path.

    Renders, accepts, an operator edit, an edge edit that bumps a version, an assemblage —
    then resolve EVERY committed block's provenance and assert nothing is missing.
    """
    manuscript_id, scene_id = scene
    for n, d in [("threshold", "a crossing"), ("interiority", "what the body knows"),
                 ("hush", "the sound that stops")]:
        run(op_svc.operator_registry.create(PROJECT, n, d))
    _stub(monkeypatch)

    # W1 — a plain render, accepted
    a = run(studio.run_block(PROJECT, "/ threshold\n",
                             manuscript_id=manuscript_id, scene_id=scene_id))
    run(psg_svc.passage_store.accept(a["results"][0]["passage_id"]))

    # W3 — an edge, then a render that pulls
    run(op_svc.operator_registry.set_relations(
        PROJECT, "interiority", [{"target": "threshold", "kind": "requires"}]))
    b = run(studio.run_block(PROJECT, "/ interiority\n",
                             manuscript_id=manuscript_id, scene_id=scene_id))
    run(psg_svc.passage_store.accept(b["results"][0]["passage_id"]))

    # the author sharpens an operator AFTER both passages are canon
    run(op_svc.operator_registry.update(PROJECT, "threshold", {"definition": "sharpened"}))

    # W4 — an assemblage, rendered and accepted
    run(op_svc.operator_registry.create_assemblage(
        PROJECT, "the_held_crossing", ["interiority", "hush"],
        rendering_intent="mine, in my words"))
    c = run(studio.run_block(PROJECT, "/ the_held_crossing\n",
                             manuscript_id=manuscript_id, scene_id=scene_id))
    run(psg_svc.passage_store.accept(c["results"][0]["passage_id"]))

    blocks = run(ms_svc.manuscript_service.get_scene(scene_id))["blocks"]
    assert len(blocks) == 3

    for block in blocks:
        check = resolve(block["provenance"])
        assert check["missing"] == [], (
            f"a committed passage can no longer name what made it: {check['missing']}"
        )
        assert check["resolved"], "provenance resolved to nothing at all"

    # and the first passage still resolves to the PRE-sharpening definition
    first = resolve(blocks[0]["provenance"])["resolved"][0]
    assert first["definition"] == "a crossing"
