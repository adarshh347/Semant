"""
Semant Writer · W4 — assemblage suggestion, the Tier-2 capstone.

W4 is the first time the system proposes something derived from the author's own working,
and the whole gate is one division:

    the system may propose the cluster because it has EVIDENCE;
    it may not decide what the cluster MEANS.

So the tests come in two halves. The evidential half pins that a suggestion rests on real
logged records, cites them, and is dropped rather than shown when it cannot. The authorial
half pins that the name and the meaning come from the author, that the strawman is the
author's own sentences rearranged rather than a reading of them, and that nothing enters
the ontology without an explicit commit.

And the boundary W4 must not cross: lineage is not a live blend. An assemblage renders ONE
span from its own authored intent; its members are ancestry, and ancestry does not silently
condition prose.
"""
import pytest

from backend.services import manuscript_service as ms_svc
from backend.services.writer import assemblages as asm
from backend.services.writer import dsl, instrument
from backend.services.writer import operators as op_svc
from backend.services.writer import passages as psg_svc
from backend.services.writer import revisions as rev_svc
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
    monkeypatch.setattr(asm, "writer_usage_collection", usage)
    monkeypatch.setattr(ms_svc, "manuscript_collection", manuscripts)
    monkeypatch.setattr(ms_svc, "scene_collection", scenes)
    monkeypatch.setattr(ms_svc, "scene_version_collection", versions)
    return {"operators": ops, "usage": usage, "scenes": scenes, "manuscripts": manuscripts}


@pytest.fixture
def ontology(store):
    async def build():
        for name, d in [
            ("threshold", "a crossing noticed only after it is behind them"),
            ("interiority", "what the body knows before the mind admits it"),
            ("hush", "the sound that stops just before it is named"),
            ("hinge", "the turn a scene pivots on"),
        ]:
            await op_svc.operator_registry.create(PROJECT, name, d,
                                                  rendering_intent=f"render {name} plainly")
        return await op_svc.operator_registry.by_name(PROJECT)
    return run(build())


def _stub_model(monkeypatch, reply='{"passage": "The latch gave.", "refusal": ""}'):
    async def fake(system, user):
        return (reply(system, user) if callable(reply) else reply), "stub-model"
    monkeypatch.setattr(render_svc, "_call_model", fake)


def _blocks(monkeypatch, block_text, times):
    """Actually run the loop `times` — the log is written by the real path, not hand-forged."""
    _stub_model(monkeypatch)
    for _ in range(times):
        run(studio.run_block(PROJECT, block_text, quarantine=False))


async def _suggestions(min_blocks=asm.MIN_BLOCKS):
    index = await op_svc.operator_registry.by_name(PROJECT)
    return await asm.suggest(PROJECT, index, min_blocks=min_blocks)


def suggestions(min_blocks=asm.MIN_BLOCKS):
    return run(_suggestions(min_blocks))


CLUSTER_BLOCK = "/ interiority\n/ threshold\n/ hush\n"


# ══ detection is analysis over the real log ══════════════════════════════════

def test_a_one_off_co_occurrence_is_not_an_assemblage(store, ontology, monkeypatch):
    """The whole value of the suggestion is that it only fires on a habit."""
    _blocks(monkeypatch, CLUSTER_BLOCK, times=1)
    assert suggestions() == []


def test_a_recurring_cluster_is_suggested_above_the_threshold(store, ontology, monkeypatch):
    _blocks(monkeypatch, CLUSTER_BLOCK, times=asm.MIN_BLOCKS)
    out = suggestions()
    assert out, "a cluster at the threshold should surface"
    top = out[0]
    assert {m["name"] for m in top["members"]} == {"interiority", "threshold", "hush"}
    assert top["support"] == asm.MIN_BLOCKS


def test_the_threshold_is_tunable_and_reported(store, ontology, monkeypatch):
    _blocks(monkeypatch, CLUSTER_BLOCK, times=2)
    assert suggestions(min_blocks=asm.MIN_BLOCKS) == []      # below the default
    out = suggestions(min_blocks=2)
    assert out and out[0]["evidence"]["threshold"] == asm.MIN_BLOCKS


def test_detection_calls_no_model(store, ontology, monkeypatch):
    """Detection is analysis. A model inventing clusters is exactly what this is not."""
    async def explode(system, user):
        raise AssertionError("suggestion must not call a model")

    monkeypatch.setattr(render_svc, "_call_model", explode)
    # log written by an earlier stubbed session
    _blocks(monkeypatch, CLUSTER_BLOCK, times=asm.MIN_BLOCKS)
    monkeypatch.setattr(render_svc, "_call_model", explode)
    assert suggestions()


def test_a_pair_inside_a_larger_cluster_is_not_reported_separately(store, ontology, monkeypatch):
    """One habit seen through a smaller window is not a second finding."""
    _blocks(monkeypatch, CLUSTER_BLOCK, times=asm.MIN_BLOCKS)
    out = suggestions()
    sizes = [len(s["members"]) for s in out]
    assert sizes == [3], f"expected only the maximal cluster, got {sizes}"


def test_a_requires_edge_cannot_manufacture_a_cluster(store, ontology, monkeypatch):
    """An edge the author already drew must not come back as a discovered pattern.

    `interiority requires threshold` makes the pair co-occur on every single render. Counting
    that would hand the author their own W3 declaration as an insight.
    """
    run(op_svc.operator_registry.set_relations(
        PROJECT, "interiority", [{"target": "threshold", "kind": "requires"}]))
    _blocks(monkeypatch, "/ interiority\n", times=asm.MIN_BLOCKS + 2)

    out = suggestions()
    pairs = [{m["name"] for m in s["members"]} for s in out]
    assert {"interiority", "threshold"} not in pairs


# ══ the suggestion is EVIDENTIAL — it cites, or it is not shown ══════════════

def test_a_suggestion_cites_the_blocks_it_rests_on(store, ontology, monkeypatch):
    _blocks(monkeypatch, CLUSTER_BLOCK, times=asm.MIN_BLOCKS)
    top = suggestions()[0]
    ev = top["evidence"]

    assert ev["block_count"] == asm.MIN_BLOCKS
    assert len(ev["blocks"]) == asm.MIN_BLOCKS
    for block in ev["blocks"]:
        assert block["run_id"]
        assert block["event_ids"]


def test_the_cited_evidence_corresponds_to_real_logged_records(store, ontology, monkeypatch):
    """Not a plausible-looking citation — the actual rows."""
    _blocks(monkeypatch, CLUSTER_BLOCK, times=asm.MIN_BLOCKS)
    top = suggestions()[0]

    logged = run(instrument.usage_for_project(PROJECT, limit=500))
    logged_ids = {e["id"] for e in logged}
    logged_runs = {(e.get("extra") or {}).get("run_id") for e in logged}

    for block in top["evidence"]["blocks"]:
        assert block["run_id"] in logged_runs
        for event_id in block["event_ids"]:
            assert event_id in logged_ids


def test_an_uncitable_candidate_is_dropped_rather_than_shown(store, ontology):
    """`cite()` returning None is the load-bearing case: no evidence → not shown at all."""
    assert asm.cite(["a", "b"], []) is None


def test_the_suggester_has_no_route_to_the_canon(store, ontology, monkeypatch):
    """It reads logs. It cannot accept, commit, or touch a scene."""
    _blocks(monkeypatch, CLUSTER_BLOCK, times=asm.MIN_BLOCKS)

    async def explode(*a, **k):
        raise AssertionError("the suggester must not reach canon")

    monkeypatch.setattr(psg_svc.passage_store, "accept", explode)
    monkeypatch.setattr(ms_svc.manuscript_service, "update_scene", explode)
    assert suggestions()


# ══ propose, never commit ════════════════════════════════════════════════════

def test_a_suggestion_changes_nothing_in_the_ontology(store, ontology, monkeypatch):
    _blocks(monkeypatch, CLUSTER_BLOCK, times=asm.MIN_BLOCKS)
    before = run(op_svc.operator_registry.list(PROJECT))
    suggestions()
    assert run(op_svc.operator_registry.list(PROJECT)) == before


def test_dismissing_changes_nothing_and_stops_the_nagging(store, ontology, monkeypatch):
    _blocks(monkeypatch, CLUSTER_BLOCK, times=asm.MIN_BLOCKS)
    top = suggestions()[0]
    before = run(op_svc.operator_registry.list(PROJECT))

    run(asm.dismiss(PROJECT, [m["name"] for m in top["members"]], top["support"]))

    assert run(op_svc.operator_registry.list(PROJECT)) == before
    assert suggestions() == [], "a dismissed cluster must not re-nag on the next look"


def test_a_dismissed_cluster_returns_only_on_substantially_more_evidence(store, ontology,
                                                                        monkeypatch):
    """Do-not-nag is not never-again: a habit that really deepens may be raised once more."""
    _blocks(monkeypatch, CLUSTER_BLOCK, times=asm.MIN_BLOCKS)
    top = suggestions()[0]
    run(asm.dismiss(PROJECT, [m["name"] for m in top["members"]], top["support"]))

    _blocks(monkeypatch, CLUSTER_BLOCK, times=1)
    assert suggestions() == []                    # not yet

    _blocks(monkeypatch, CLUSTER_BLOCK, times=asm.MIN_BLOCKS * asm.RESURFACE_FACTOR)
    assert suggestions(), "much more evidence may raise it again"


# ══ the strawman is the author's own words, rearranged ═══════════════════════

def test_the_strawman_is_composed_from_the_members_definitions(store, ontology, monkeypatch):
    _blocks(monkeypatch, CLUSTER_BLOCK, times=asm.MIN_BLOCKS)
    top = suggestions()[0]
    intent = top["strawman"]["rendering_intent"]

    # every fragment is a member's own sentence
    for member in top["members"]:
        own = member["rendering_intent"] or member["definition"]
        assert own in intent

    # and it says what it is, so the author is never misled about its status
    assert "your words" in top["strawman"]["source"]


def test_the_strawman_adds_no_reading_of_its_own():
    """No model call, and no vocabulary about what a cluster 'should' mean."""
    out = asm.strawman([
        {"name": "a", "rendering_intent": "one held moment"},
        {"name": "b", "definition": "what the body knows"},
    ])
    assert out["rendering_intent"] == "a: one held moment; b: what the body knows"
    for invented in ("evokes", "atmosphere", "tension", "represents", "symbol", "theme"):
        assert invented not in out["rendering_intent"].lower()


# ══ authoring — the meaning is the author's ══════════════════════════════════

def test_authoring_stores_kind_members_with_versions_and_the_authors_intent(store, ontology):
    op = run(op_svc.operator_registry.create_assemblage(
        PROJECT, "the_held_crossing", ["interiority", "threshold", "hush"],
        rendering_intent="the body arrives before the mind does, and the room goes quiet",
        definition="the crossing she only notices once the room has gone quiet behind her"))

    assert op["kind"] == asm.ASSEMBLAGE_KIND
    assert op["rendering_intent"] == \
        "the body arrives before the mind does, and the room goes quiet"
    assert [m["name"] for m in op["members"]] == ["interiority", "threshold", "hush"]
    # lineage records the members AS THEY STOOD
    assert all(m["version"] == 1 for m in op["members"])


def test_an_assemblage_needs_a_definition_as_well_as_an_intent(store, ontology):
    """The W4 live gate echoed the intent back as the passage. This is why.

    `definition` used to default to `rendering_intent`, so the operator reached the prompt
    saying one sentence twice and carrying nothing else. A thin operator renders thinly, and
    an instruction repeated is the likeliest thing for a model to hand straight back.
    """
    with pytest.raises(op_svc.OperatorError, match="needs a definition as well as"):
        run(op_svc.operator_registry.create_assemblage(
            PROJECT, "thin", ["interiority", "threshold"],
            rendering_intent="the body arrives before the mind does"))


def test_an_assemblage_saying_the_same_thing_twice_is_refused(store, ontology):
    same = "the body arrives before the mind does"
    with pytest.raises(op_svc.OperatorError, match="same text for its definition"):
        run(op_svc.operator_registry.create_assemblage(
            PROJECT, "echo", ["interiority", "threshold"],
            rendering_intent=same, definition=same))


def test_an_assemblage_with_both_is_stored(store, ontology):
    op = run(op_svc.operator_registry.create_assemblage(
        PROJECT, "the_held_crossing", ["interiority", "threshold"],
        rendering_intent="let the quiet land after the crossing, never before",
        definition="the crossing she notices only once the room has gone quiet behind her"))
    assert op["definition"] != op["rendering_intent"]
    assert op["kind"] == asm.ASSEMBLAGE_KIND


def test_an_operator_that_says_one_thing_twice_is_warned_about(store, ontology, monkeypatch):
    """A WARNING for plain operators, not a refusal — it is the author's ontology.

    Operators predating the rule are still renderable; they just say so in the diagnostics,
    where the author can act on it.
    """
    same = "one held moment, no summary"
    run(op_svc.operator_registry.create(PROJECT, "thin_one", same, rendering_intent=same))
    _stub_model(monkeypatch)

    directive = dsl.parse_block("/ thin_one\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    assert result.status == "ok"          # rendered, not refused
    assert any("says the same thing" in d for d in result.diagnostics)


def test_a_well_formed_operator_draws_no_warning(store, ontology, monkeypatch):
    _stub_model(monkeypatch)
    directive = dsl.parse_block("/ threshold\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))
    assert not any("says the same thing" in d for d in result.diagnostics)


def test_an_assemblage_without_the_authors_intent_is_refused(store, ontology):
    with pytest.raises(op_svc.OperatorError, match="in your own words"):
        run(op_svc.operator_registry.create_assemblage(
            PROJECT, "hollow", ["interiority", "threshold"], rendering_intent="   "))


def test_a_corpus_string_cannot_be_a_member(store, ontology):
    """I5 by construction: members are operator references, looked up in the ontology."""
    for bogus in ("like Tolstoy", "noir", "a 19th-century Russian novel"):
        with pytest.raises(op_svc.OperatorError, match="not an operator"):
            run(op_svc.operator_registry.create_assemblage(
                PROJECT, "borrowed", ["interiority", bogus],
                rendering_intent="mine, in my words",
        definition="what this compression is, in my writing"))


def test_an_assemblage_needs_at_least_two_members(store, ontology):
    with pytest.raises(op_svc.OperatorError, match="at least two members"):
        run(op_svc.operator_registry.create_assemblage(
            PROJECT, "lonely", ["interiority"], rendering_intent="mine", definition="what it is"))


def test_an_authored_cluster_stops_being_suggested(store, ontology, monkeypatch):
    _blocks(monkeypatch, CLUSTER_BLOCK, times=asm.MIN_BLOCKS)
    top = suggestions()[0]
    run(op_svc.operator_registry.create_assemblage(
        PROJECT, "the_held_crossing", [m["name"] for m in top["members"]],
        rendering_intent="mine, in my words",
        definition="what this compression is, in my writing"))
    assert suggestions() == []


# ══ rendering — one span from the authored intent; lineage is not an input ═══

def test_an_assemblage_renders_one_span_from_its_own_intent(store, ontology, monkeypatch):
    seen = {}

    def capture(system, user):
        seen["user"] = user
        return '{"passage": "The room went quiet.", "refusal": ""}'

    _stub_model(monkeypatch, capture)
    run(op_svc.operator_registry.create_assemblage(
        PROJECT, "the_held_crossing", ["interiority", "threshold", "hush"],
        rendering_intent="the body arrives before the mind does, and the room goes quiet",
        definition="the crossing she only notices once the room has gone quiet behind her"))

    directive = dsl.parse_block("/ the_held_crossing\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    assert result.status == "ok"
    assert "the body arrives before the mind does" in seen["user"]
    # provenance names the assemblage, directly
    assert [o["name"] for o in result.provenance["operators"]] == ["the_held_crossing"]
    assert result.provenance["operators"][0]["source"] == "direct"


def test_lineage_is_not_a_render_input(store, ontology, monkeypatch):
    """THE BOUNDARY. Members are ancestry; ancestry does not silently condition prose.

    If lineage fed the prompt, three operators would be conditioning one span as a fused
    field — and provenance could no longer say which produced which part of the passage.
    That answer is the audit trail the whole project rests on, which is why the blended
    version is Tier 3.
    """
    seen = {}

    def capture(system, user):
        seen["user"] = user
        return '{"passage": "The room went quiet.", "refusal": ""}'

    _stub_model(monkeypatch, capture)
    run(op_svc.operator_registry.create_assemblage(
        PROJECT, "the_held_crossing", ["interiority", "threshold", "hush"],
        rendering_intent="mine, in my words",
        definition="what this compression is, in my writing"))

    directive = dsl.parse_block("/ the_held_crossing\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    # the members' own definitions are absent from the prompt
    for member_definition in ("what the body knows before the mind admits it",
                              "a crossing noticed only after it is behind them",
                              "the sound that stops just before it is named"):
        assert member_definition not in seen["user"]

    # and absent from provenance as render inputs
    assert result.provenance["pulled_operators"] == []
    assert [o["name"] for o in result.provenance["operators"]] == ["the_held_crossing"]


def test_the_author_can_still_wire_a_member_with_requires(store, ontology, monkeypatch):
    """W3 consistency: if the author WANTS a member present, they draw the edge by hand."""
    seen = {}

    def capture(system, user):
        seen["user"] = user
        return '{"passage": "The room went quiet.", "refusal": ""}'

    _stub_model(monkeypatch, capture)
    run(op_svc.operator_registry.create_assemblage(
        PROJECT, "the_held_crossing", ["interiority", "threshold", "hush"],
        rendering_intent="mine, in my words",
        definition="what this compression is, in my writing"))
    run(op_svc.operator_registry.set_relations(
        PROJECT, "the_held_crossing", [{"target": "hush", "kind": "requires"}]))

    directive = dsl.parse_block("/ the_held_crossing\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    assert "the sound that stops just before it is named" in seen["user"]
    sources = {o["name"]: o["source"] for o in result.provenance["operators"]}
    assert sources["the_held_crossing"] == "direct"
    assert sources["hush"] == "pulled_via_requires"
    # and the members NOT wired stay out
    assert "what the body knows before the mind admits it" not in seen["user"]


# ══ I1/I3 — none of this is canon ════════════════════════════════════════════

def test_no_assemblage_activity_touches_the_manuscript(store, ontology, monkeypatch):
    async def build():
        m = await ms_svc.manuscript_service.create_manuscript("Fixture")
        m = await ms_svc.manuscript_service.add_chapter(m["id"], "One")
        await ms_svc.manuscript_service.add_scene(
            m["id"], m["chapters"][0]["id"], "Scene one",
            blocks=[{"id": "b1", "type": "paragraph",
                     "content": "<p>She crossed before she decided to.</p>",
                     "color": None, "origin": "human"}])
        return m["id"]

    manuscript_id = run(build())
    before = run(ms_svc.manuscript_service.export_manuscript(manuscript_id))["content"]

    _blocks(monkeypatch, CLUSTER_BLOCK, times=asm.MIN_BLOCKS)
    top = suggestions()[0]
    run(asm.dismiss(PROJECT, [m["name"] for m in top["members"]], top["support"]))
    run(op_svc.operator_registry.create_assemblage(
        PROJECT, "the_held_crossing", ["interiority", "threshold"],
        rendering_intent="mine, in my words",
        definition="what this compression is, in my writing"))

    after = run(ms_svc.manuscript_service.export_manuscript(manuscript_id))["content"]
    assert after == before


# ══ instrumentation keeps accruing (the Tier-3 seed corpus) ══════════════════

def test_the_authors_decisions_are_logged(store, ontology, monkeypatch):
    _blocks(monkeypatch, CLUSTER_BLOCK, times=asm.MIN_BLOCKS)
    run(asm.dismiss(PROJECT, ["interiority", "threshold"], 3))
    run(asm.record_authored(PROJECT, "the_held_crossing", ["interiority", "threshold"]))

    events = {e["event"] for e in run(instrument.usage_for_project(PROJECT, limit=500))}
    assert asm.DISMISSED in events
    assert asm.AUTHORED in events
