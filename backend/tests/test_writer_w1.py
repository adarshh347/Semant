"""
Semant Writer · W1 — the executable-document loop.

Covers the six honesty invariants as behaviour, not as intentions:

  1. model proposes / author commits — a render is born `committed: False`; only `accept`
     changes that, and it is the only path into a scene;
  2. refusal is a return value — an undefined operator and a contradictory orchestration
     both come back as REFUSED with a reason, and neither produces prose;
  3. two memories — dismissing a passage costs canon nothing;
  4. provenance — every passage names its operators (with versions) and `//` intents, and
     the committed block keeps them;
  5. the author's-ontology wall — the render prompt is built ONLY from the author's own
     words, and an undeclared operator never reaches the model;
  6. the `/` ÷ `//` wall — orchestration never reaches a committed passage.

House style: sync tests driving async service code via ``asyncio.run`` with injected fake
async Mongo collections (cf. test_manuscript_ws0a.py). No live Mongo, no network, no
models — the one model-shaped test stubs the Groq call so a refusal and a leak can be
forced deterministically. The LIVE proof against Groq is `scripts/writer_w1_proof.py`.
"""
import asyncio
import copy
import re

import pytest

from backend.services import manuscript_service as ms_svc
from backend.services.writer import dsl, instrument
from backend.services.writer import operators as op_svc
from backend.services.writer import passages as psg_svc
from backend.services.writer import render as render_svc
from backend.services.writer import studio
from backend.services.writer.render import REFUSED, RenderResult


# ── fake async Mongo collection (supports exactly the ops the services use) ───
class _UpdateResult:
    def __init__(self, matched, modified):
        self.matched_count = matched
        self.modified_count = modified


class _DeleteResult:
    def __init__(self, deleted):
        self.deleted_count = deleted


class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, field, direction=1):
        self._docs = sorted(
            self._docs,
            key=lambda d: (d.get(field) is None, d.get(field)),
            reverse=direction < 0,
        )
        return self

    def __aiter__(self):
        async def gen():
            for d in self._docs:
                yield copy.deepcopy(d)
        return gen()


def _match(doc, query):
    for k, v in (query or {}).items():
        if isinstance(v, dict) and "$in" in v:
            if doc.get(k) not in v["$in"]:
                return False
        elif isinstance(v, dict) and "$elemMatch" in v:
            # Enough of `$elemMatch` for a compare-and-set on an array element — the shape
            # `readings.decide` uses to make "a decision is made once" atomic.
            items = doc.get(k)
            if not isinstance(items, list) or not any(
                isinstance(i, dict) and all(i.get(ik) == iv for ik, iv in v["$elemMatch"].items())
                for i in items
            ):
                return False
        elif doc.get(k) != v:
            return False
    return True


_POSITIONAL = re.compile(r"^(?P<array>\w+)\.\$\[(?P<ident>\w+)\]\.(?P<field>\w+)$")


def _apply_set(doc, changes, array_filters):
    """`$set`, including `array.$[f].field` paths against `array_filters`."""
    by_ident = {}
    for af in array_filters or []:
        for key, value in af.items():
            ident, _, field = key.partition(".")
            by_ident.setdefault(ident, {})[field] = value

    for path, value in changes.items():
        m = _POSITIONAL.match(path)
        if not m:
            doc[path] = value
            continue
        criteria = by_ident.get(m["ident"], {})
        for item in doc.get(m["array"]) or []:
            if isinstance(item, dict) and all(item.get(k) == v for k, v in criteria.items()):
                item[m["field"]] = value


class FakeCollection:
    def __init__(self):
        self.docs = {}

    async def insert_one(self, doc):
        self.docs[doc["_id"]] = copy.deepcopy(doc)
        return type("R", (), {"inserted_id": doc["_id"]})()

    async def find_one(self, query, projection=None):
        for d in self.docs.values():
            if _match(d, query):
                return copy.deepcopy(d)
        return None

    def find(self, query=None, projection=None):
        return _Cursor([copy.deepcopy(d) for d in self.docs.values() if _match(d, query)])

    async def update_one(self, query, update, upsert=False, array_filters=None):
        for d in self.docs.values():
            if _match(d, query):
                _apply_set(d, update.get("$set", {}), array_filters)
                return _UpdateResult(1, 1)
        return _UpdateResult(0, 0)

    async def delete_one(self, query):
        for _id, d in list(self.docs.items()):
            if _match(d, query):
                del self.docs[_id]
                return _DeleteResult(1)
        return _DeleteResult(0)

    async def delete_many(self, query):
        hits = [i for i, d in self.docs.items() if _match(d, query)]
        for i in hits:
            del self.docs[i]
        return _DeleteResult(len(hits))


def run(coro):
    return asyncio.run(coro)


PROJECT = "ms_fixture"


@pytest.fixture
def store(monkeypatch):
    """Every collection the Writer touches, plus WS-0A's canon, faked and injected."""
    ops, psgs, usage = FakeCollection(), FakeCollection(), FakeCollection()
    manuscripts, scenes, versions = FakeCollection(), FakeCollection(), FakeCollection()

    monkeypatch.setattr(op_svc, "writer_operator_collection", ops)
    monkeypatch.setattr(psg_svc, "writer_passage_collection", psgs)
    monkeypatch.setattr(instrument, "writer_usage_collection", usage)
    monkeypatch.setattr(ms_svc, "manuscript_collection", manuscripts)
    monkeypatch.setattr(ms_svc, "scene_collection", scenes)
    monkeypatch.setattr(ms_svc, "scene_version_collection", versions)

    return {
        "operators": ops, "passages": psgs, "usage": usage,
        "manuscripts": manuscripts, "scenes": scenes,
    }


@pytest.fixture
def fixture_manuscript(store):
    """A scratch manuscript with one chapter and one empty scene. Never a real work."""
    async def build():
        m = await ms_svc.manuscript_service.create_manuscript("Fixture manuscript")
        m = await ms_svc.manuscript_service.add_chapter(m["id"], "Chapter one")
        ch = m["chapters"][0]["id"]
        scene = await ms_svc.manuscript_service.add_scene(m["id"], ch, "Scene one")
        return m["id"], scene["id"]
    return run(build())


@pytest.fixture
def threshold_operator(store):
    async def build():
        return await op_svc.operator_registry.create(
            PROJECT, "threshold",
            definition="a crossing the character notices only after it is behind them",
            rendering_intent="one held moment, no summary of what it means",
            examples=["The latch gave before she decided to push."],
            negative_examples=["She stepped through the door, changed forever."],
        )
    return run(build())


def _stub_model(monkeypatch, reply):
    """Replace the Groq call. `reply` is the raw model string, or a callable(system,user)."""
    async def fake(system, user):
        out = reply(system, user) if callable(reply) else reply
        return out, "stub-model"
    monkeypatch.setattr(render_svc, "_call_model", fake)


# ══ the DSL: the `/` ÷ `//` wall (invariant 6, inbound) ══════════════════════

def test_parse_splits_the_two_layers_and_keeps_order():
    parsed = dsl.parse_block(
        "// goal: reach the threshold\n"
        "/ threshold(the door)\n"
        "He waited.\n"
        "/ threshold + interiority\n"
    )
    assert [d.line for d in parsed.directives] == [2, 4]
    assert parsed.directives[0].operator_names == ("threshold",)
    assert parsed.directives[0].operators[0].argument == "the door"
    assert parsed.directives[1].operator_names == ("threshold", "interiority")
    assert [n.key for n in parsed.notes] == ["goal"]
    assert [p.text for p in parsed.prose if p.text.strip()] == ["He waited."]


def test_orchestration_scope_is_positional_not_block_wide():
    """A note conditions what FOLLOWS it. A directive cannot pick up later staging."""
    parsed = dsl.parse_block(
        "/ alpha\n"
        "// voice: close third\n"
        "/ beta\n"
        "// voice: first person\n"
        "/ gamma\n"
    )
    first, second, third = parsed.directives
    assert dsl.active_orchestration(first) == {}
    assert dsl.active_orchestration(second) == {"voice": "close third"}
    # a later note with the same key SUPERSEDES the earlier one
    assert dsl.active_orchestration(third) == {"voice": "first person"}


def test_double_slash_is_never_read_as_a_directive():
    parsed = dsl.parse_block("// avoid: weather openings\n/ threshold\n")
    assert len(parsed.directives) == 1
    assert parsed.directives[0].operator_names == ("threshold",)
    assert [n.value for n in parsed.notes] == ["weather openings"]


def test_slashes_inside_prose_stay_prose():
    """Only a line that OPENS with the notation is notation."""
    parsed = dsl.parse_block("She read it at http://example.com/threshold and laughed.\n")
    assert not parsed.directives and not parsed.notes
    assert len(parsed.prose) == 1


def test_unknown_orchestration_key_is_retained_but_inert():
    parsed = dsl.parse_block("// mood: gentle\n/ threshold\n")
    assert parsed.notes[0].key == "mood" and parsed.notes[0].known is False
    assert dsl.active_orchestration(parsed.directives[0]) == {}
    assert any("not an orchestration key" in d for d in parsed.diagnostics)


def test_create_gesture_defines_and_renders_nothing():
    parsed = dsl.parse_block("#create interiority: what the body knows first\n")
    assert parsed.creates[0].name == "interiority"
    assert parsed.creates[0].description == "what the body knows first"
    assert parsed.directives == ()


# ══ the leak check (invariant 6, outbound) ═══════════════════════════════════

def test_leak_check_catches_notation_restatement_and_narration():
    notes = [dsl.OrchestrationNote(line=1, key="goal", value="reach the threshold")]
    assert dsl.find_orchestration_leak("// goal: reach the threshold", notes)
    assert dsl.find_orchestration_leak("/ threshold", notes)
    assert dsl.find_orchestration_leak("Reach the threshold.", notes)      # verbatim echo
    assert dsl.find_orchestration_leak("goal: get her through the door", notes)  # narrated


def test_leak_check_permits_prose_that_merely_fulfils_the_goal():
    """The wall is about notation and restatement — never about shared vocabulary."""
    notes = [dsl.OrchestrationNote(line=1, key="goal", value="reach the threshold")]
    prose = "The threshold was cold under her feet, and she was across it before she knew."
    assert dsl.find_orchestration_leak(prose, notes) == []


def test_strip_orchestration_removes_only_the_leaking_lines():
    notes = [dsl.OrchestrationNote(line=1, key="voice", value="close third")]
    clean, reasons = dsl.strip_orchestration(
        "// voice: close third\nShe waited by the door.\nvoice: close third\n", notes
    )
    assert clean == "She waited by the door."
    assert len(reasons) == 2


# ══ the operator registry (the ledger) ═══════════════════════════════════════

def test_propose_does_not_store_and_create_does(store):
    proposal = op_svc.operator_registry.propose("threshold", "a crossing noticed late")
    assert proposal["committed"] is False
    assert run(op_svc.operator_registry.get(PROJECT, "threshold")) is None

    created = run(op_svc.operator_registry.create(PROJECT, "threshold", "a crossing noticed late"))
    assert created["version"] == 1
    assert run(op_svc.operator_registry.get(PROJECT, "threshold"))["name"] == "threshold"


def test_operator_without_a_definition_is_refused(store):
    with pytest.raises(op_svc.OperatorError):
        run(op_svc.operator_registry.create(PROJECT, "hollow", "   "))
    with pytest.raises(op_svc.OperatorError):
        op_svc.operator_registry.propose("2bad name", "something")


def test_update_bumps_version_and_keeps_history(store, threshold_operator):
    updated = run(op_svc.operator_registry.update(
        PROJECT, "threshold", {"definition": "a crossing felt in the body"}
    ))
    assert updated["version"] == 2
    assert updated["history"][0]["version"] == 1
    assert "notices only after" in updated["history"][0]["definition"]


def test_operators_are_project_scoped(store, threshold_operator):
    assert run(op_svc.operator_registry.get("another_project", "threshold")) is None


# ══ the author's-ontology wall (invariant 5) ═════════════════════════════════

def test_render_prompt_is_built_only_from_the_authors_words(store, threshold_operator):
    """Every style-bearing line in the prompt must be text the author typed."""
    prompt = render_svc.build_render_prompt(
        [threshold_operator], {"voice": "close third, past tense"}
    )
    user = prompt["user"]
    for authored in (
        "a crossing the character notices only after it is behind them",
        "one held moment, no summary of what it means",
        "The latch gave before she decided to push.",
        "She stepped through the door, changed forever.",
        "close third, past tense",
    ):
        assert authored in user

    # and the builder contributes no style of its own
    assert "lyrical" not in user.lower()
    assert "vivid" not in user.lower()
    assert "literary" not in user.lower()


def test_system_prompt_states_the_wall_and_the_refusal_escape_hatch():
    system = render_svc.build_render_prompt([], {})["system"]
    assert "ONLY basis" in system
    assert "REFUSE" in system
    assert "has not declared" in system
    assert "STYLE BY REFERENCE IS AN IMPORT" in system


def test_undefined_operator_refuses_before_any_model_is_called(store, monkeypatch):
    """Invariant 5's hardest edge: an undeclared operator never reaches the model."""
    called = []

    async def explode(system, user):
        called.append(1)
        raise AssertionError("the model must not be called for an undefined operator")

    monkeypatch.setattr(render_svc, "_call_model", explode)
    directive = dsl.parse_block("/ undeclared\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    assert result.status == REFUSED
    assert result.text == ""
    assert "undefined operator" in result.refusal
    assert "#create undeclared" in result.refusal
    assert called == []


def test_style_by_reference_refuses_before_the_model(store, threshold_operator, monkeypatch):
    """`//voice: like a 19th-century Russian novel` imports a corpus that is not the author's.

    Measured behaviour, not a hypothetical: the model complies with this when only the
    prompt forbids it, so the refusal has to be structural. See `_STYLE_BY_REFERENCE`.
    """
    async def explode(system, user):
        raise AssertionError("style by reference must be refused before the model is called")

    monkeypatch.setattr(render_svc, "_call_model", explode)
    directive = dsl.parse_block(
        "// voice: the ornate omniscience of a 19th-century Russian novel\n/ threshold\n"
    ).directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    assert result.status == REFUSED
    assert result.text == ""
    assert "lives in my priors" in result.refusal
    # the refusal is GENERATIVE — it routes to #create rather than dead-ending
    assert "#create" in result.refusal
    assert "in your words" in result.refusal


def test_a_bare_surname_is_refused_too(store, threshold_operator, monkeypatch):
    """`// voice: like Tolstoy` — the meaning lives in the priors, not the author's book."""
    async def explode(system, user):
        raise AssertionError("a bare corpus reference must not reach the model")

    monkeypatch.setattr(render_svc, "_call_model", explode)
    directive = dsl.parse_block("// voice: like Tolstoy, but shorter\n/ threshold\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    assert result.status == REFUSED
    assert "#create tolstoy_voice" in result.refusal   # it names the operator to author


def test_a_voice_described_in_the_authors_own_words_renders(store, threshold_operator, monkeypatch):
    """The other half of the wall: describing a quality is the author's language, and passes."""
    _stub_model(monkeypatch, '{"passage": "The latch gave.", "refusal": ""}')
    directive = dsl.parse_block(
        "// voice: close third, past tense, short declaratives\n/ threshold\n"
    ).directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    assert result.status == "ok"
    assert result.text == "The latch gave."


def test_avoiding_a_reference_is_not_importing_one(store, threshold_operator, monkeypatch):
    """`// avoid: noir` tells the model what NOT to sound like — it imports nothing."""
    _stub_model(monkeypatch, '{"passage": "The latch gave.", "refusal": ""}')
    directive = dsl.parse_block("// avoid: noir pastiche\n/ threshold\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    assert result.status == "ok"


def test_contradictory_orchestration_refuses_with_the_conflict(store, threshold_operator, monkeypatch):
    async def explode(system, user):
        raise AssertionError("a structural contradiction is settled before the model")

    monkeypatch.setattr(render_svc, "_call_model", explode)
    directive = dsl.parse_block("// avoid: threshold\n/ threshold\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    assert result.status == REFUSED
    assert "contradictory orchestration" in result.refusal
    assert result.text == ""


def test_a_model_refusal_comes_back_as_a_reason_not_as_filler(store, threshold_operator, monkeypatch):
    _stub_model(monkeypatch, '{"passage": "", "refusal": "the goal and the voice cannot both hold"}')
    directive = dsl.parse_block("// goal: silence\n/ threshold\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    assert result.status == REFUSED
    assert result.refusal == "the goal and the voice cannot both hold"
    assert result.text == ""


# ══ render → quarantine → accept (invariants 1, 3, 4, 6) ═════════════════════

def test_render_carries_operator_versions_and_intents(store, threshold_operator, monkeypatch):
    _stub_model(monkeypatch, '{"passage": "The latch gave.", "refusal": ""}')
    directive = dsl.parse_block("// goal: cross it\n/ threshold\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    assert result.status == "ok" and result.text == "The latch gave."
    assert result.provenance["operators"] == [
        # `source` is W3's marking: this one was typed by the author, not pulled by an edge.
        # `library_ref`/`author` are W5's: null here because this operator was defined in
        # this project rather than carried in from the author's library.
        {"name": "threshold", "version": 1, "id": threshold_operator["id"],
         "source": "direct", "library_ref": None, "author": None}
    ]
    assert result.provenance["pulled_operators"] == []
    assert result.provenance["intents"] == [{"key": "goal", "value": "cross it"}]
    assert result.provenance["directive_line"] == 2


def test_a_rendered_passage_is_quarantined_not_committed(store, threshold_operator,
                                                         fixture_manuscript, monkeypatch):
    manuscript_id, scene_id = fixture_manuscript
    _stub_model(monkeypatch, '{"passage": "The latch gave.", "refusal": ""}')

    out = run(studio.run_block(
        PROJECT, "// goal: cross it\n/ threshold\n",
        manuscript_id=manuscript_id, scene_id=scene_id,
    ))
    passage_id = out["results"][0]["passage_id"]
    passage = run(psg_svc.passage_store.get(passage_id))

    assert passage["committed"] is False
    assert passage["status"] == "quarantined"
    # and the manuscript has NOT grown
    assert run(ms_svc.manuscript_service.get_scene(scene_id))["blocks"] == []


def test_accept_is_the_only_thing_that_grows_the_manuscript(store, threshold_operator,
                                                            fixture_manuscript, monkeypatch):
    manuscript_id, scene_id = fixture_manuscript
    _stub_model(monkeypatch, '{"passage": "The latch gave before she decided.", "refusal": ""}')

    out = run(studio.run_block(
        PROJECT, "// goal: cross it\n/ threshold\n",
        manuscript_id=manuscript_id, scene_id=scene_id,
    ))
    passage_id = out["results"][0]["passage_id"]

    accepted = run(psg_svc.passage_store.accept(passage_id))
    scene = run(ms_svc.manuscript_service.get_scene(scene_id))

    assert len(scene["blocks"]) == 1
    block = scene["blocks"][0]
    assert block["content"] == "The latch gave before she decided."
    # the model proposed, the author accepted — NOT `model_suggested`, which means quarantined
    assert block["origin"] == "user_confirmed"
    assert block["provenance"]["operators"][0]["name"] == "threshold"
    assert block["provenance"]["intents"] == [{"key": "goal", "value": "cross it"}]
    assert block["provenance"]["passage_id"] == passage_id
    assert run(psg_svc.passage_store.get(passage_id))["committed"] is True
    assert accepted["block_id"] == block["id"]


def test_dismiss_drops_the_passage_and_canon_never_moves(store, threshold_operator,
                                                         fixture_manuscript, monkeypatch):
    manuscript_id, scene_id = fixture_manuscript
    _stub_model(monkeypatch, '{"passage": "The latch gave.", "refusal": ""}')
    out = run(studio.run_block(
        PROJECT, "/ threshold\n", manuscript_id=manuscript_id, scene_id=scene_id
    ))
    passage_id = out["results"][0]["passage_id"]

    dismissed = run(psg_svc.passage_store.dismiss(passage_id, "not this one"))
    assert dismissed["status"] == "dismissed" and dismissed["committed"] is False
    assert run(ms_svc.manuscript_service.get_scene(scene_id))["blocks"] == []


def test_a_decision_is_made_once(store, threshold_operator, fixture_manuscript, monkeypatch):
    manuscript_id, scene_id = fixture_manuscript
    _stub_model(monkeypatch, '{"passage": "The latch gave.", "refusal": ""}')
    out = run(studio.run_block(
        PROJECT, "/ threshold\n", manuscript_id=manuscript_id, scene_id=scene_id
    ))
    passage_id = out["results"][0]["passage_id"]

    run(psg_svc.passage_store.accept(passage_id))
    with pytest.raises(psg_svc.PassageError):
        run(psg_svc.passage_store.accept(passage_id))
    with pytest.raises(psg_svc.PassageError):
        run(psg_svc.passage_store.dismiss(passage_id))


# ══ invariant 6, end to end: no `//` reaches a committed passage ═════════════

def test_orchestration_leaking_from_the_model_is_stripped_before_quarantine(
    store, threshold_operator, fixture_manuscript, monkeypatch
):
    manuscript_id, scene_id = fixture_manuscript
    # a model that both restates the staging AND emits notation
    _stub_model(monkeypatch, (
        '{"passage": "// goal: cross it\\ngoal: cross it\\nThe latch gave before she decided.", '
        '"refusal": ""}'
    ))
    out = run(studio.run_block(
        PROJECT, "// goal: cross it\n/ threshold\n",
        manuscript_id=manuscript_id, scene_id=scene_id,
    ))
    entry = out["results"][0]
    assert entry["status"] == "ok"
    assert entry["text"] == "The latch gave before she decided."
    assert len(entry["diagnostics"]) == 2

    run(psg_svc.passage_store.accept(entry["passage_id"]))
    committed = run(ms_svc.manuscript_service.get_scene(scene_id))["blocks"][0]["content"]
    assert "//" not in committed
    assert "goal:" not in committed


def test_a_passage_that_is_nothing_but_orchestration_becomes_a_refusal(
    store, threshold_operator, monkeypatch
):
    _stub_model(monkeypatch, '{"passage": "// goal: cross it", "refusal": ""}')
    directive = dsl.parse_block("// goal: cross it\n/ threshold\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    assert result.status == REFUSED
    assert result.text == ""
    assert "orchestration restated" in result.refusal


def test_accept_refuses_a_passage_that_still_carries_orchestration(
    store, threshold_operator, fixture_manuscript, monkeypatch
):
    """The door re-checks, so the guarantee holds against a passage W1 did not render."""
    manuscript_id, scene_id = fixture_manuscript
    _stub_model(monkeypatch, '{"passage": "The latch gave.", "refusal": ""}')
    out = run(studio.run_block(
        PROJECT, "// goal: cross it\n/ threshold\n",
        manuscript_id=manuscript_id, scene_id=scene_id,
    ))
    passage_id = out["results"][0]["passage_id"]

    # forge a leak straight into the store, bypassing render
    run(store["passages"].update_one(
        {"_id": passage_id}, {"$set": {"text": "// goal: cross it\nThe latch gave."}}
    ))
    with pytest.raises(psg_svc.PassageError, match="orchestration would reach the manuscript"):
        run(psg_svc.passage_store.accept(passage_id))

    assert run(ms_svc.manuscript_service.get_scene(scene_id))["blocks"] == []


# ══ the whole block: the loop ════════════════════════════════════════════════

def test_run_block_walks_directives_in_order_mixing_renders_and_refusals(
    store, threshold_operator, fixture_manuscript, monkeypatch
):
    manuscript_id, scene_id = fixture_manuscript
    _stub_model(monkeypatch, '{"passage": "The latch gave.", "refusal": ""}')

    out = run(studio.run_block(
        PROJECT,
        "// goal: cross it\n"
        "// voice: close third\n"
        "/ threshold\n"
        "/ undeclared\n"
        "#create interiority: what the body knows first\n",
        manuscript_id=manuscript_id, scene_id=scene_id,
    ))

    assert out["rendered"] == 1 and out["refused"] == 1
    assert out["results"][0]["status"] == "ok"
    assert out["results"][0]["orchestration"] == {"goal": "cross it", "voice": "close third"}
    assert out["results"][1]["status"] == REFUSED

    # `#create` in a block PROPOSES; it does not author
    assert out["proposals"][0]["proposal"]["name"] == "interiority"
    assert run(op_svc.operator_registry.get(PROJECT, "interiority")) is None


def test_continuity_feeds_committed_prose_into_the_next_render(
    store, threshold_operator, fixture_manuscript, monkeypatch
):
    manuscript_id, scene_id = fixture_manuscript
    seen = {}

    def capture(system, user):
        seen["user"] = user
        return '{"passage": "The latch gave.", "refusal": ""}'

    _stub_model(monkeypatch, capture)
    run(ms_svc.manuscript_service.update_scene(scene_id, {"blocks": [
        {"id": "b1", "type": "paragraph", "content": "<p>She had been standing there for an hour.</p>",
         "color": None, "origin": "human"}
    ]}))
    run(studio.run_block(PROJECT, "/ threshold\n", manuscript_id=manuscript_id, scene_id=scene_id))

    assert "She had been standing there for an hour." in seen["user"]


# ══ W3 §1 — block scope: a satisfied directive does not re-render ════════════

def test_block_scope_runs_only_pending_directives(store, threshold_operator,
                                                  fixture_manuscript, monkeypatch):
    """Accepting one directive's card must not make the next Render propose it again.

    Without this the author accepts a passage, renders the block for the NEXT directive,
    and is handed a second proposal for prose that is already canon — work they finished,
    coming back as a card they have to dismiss.
    """
    manuscript_id, scene_id = fixture_manuscript
    run(op_svc.operator_registry.create(PROJECT, "interiority", "what the body knows first"))
    _stub_model(monkeypatch, '{"passage": "The latch gave.", "refusal": ""}')

    block = "// goal: cross it\n/ threshold\n/ interiority\n"

    # first pass: everything is pending
    first = run(studio.run_block(PROJECT, block, manuscript_id=manuscript_id, scene_id=scene_id))
    assert [r["directive_index"] for r in first["results"]] == [0, 1]
    assert first["rendered"] == 2

    run(psg_svc.passage_store.accept(first["results"][0]["passage_id"]))

    # second pass: directive 0 is satisfied, so only directive 1 is asked for
    second = run(studio.run_block(
        PROJECT, block, manuscript_id=manuscript_id, scene_id=scene_id, only_directives=[1],
    ))
    assert second["skipped"] == 1
    assert second["rendered"] == 1
    assert second["results"][0]["status"] == studio.SKIPPED
    assert second["results"][0]["passage_id"] is None
    assert "already satisfied" in second["results"][0]["detail"]
    assert second["results"][1]["directive_index"] == 1
    assert second["results"][1]["status"] == "ok"


def test_a_skipped_directive_is_not_a_refusal(store, threshold_operator, monkeypatch):
    """`skipped` and `refused` are different answers and must not be conflated."""
    _stub_model(monkeypatch, '{"passage": "The latch gave.", "refusal": ""}')
    out = run(studio.run_block(PROJECT, "/ threshold\n", only_directives=[], quarantine=False))
    assert out["results"][0]["status"] == studio.SKIPPED
    assert out["refused"] == 0
    assert out["results"][0]["refusal"] == ""


def test_block_scope_keeps_orchestration_scope_positional(store, threshold_operator, monkeypatch):
    """A skipped directive is WALKED, not filtered out — `//` scope is positional.

    Dropping the line before parsing would re-stage every directive after it.
    """
    seen = {}

    def capture(system, user):
        seen["user"] = user
        return '{"passage": "The latch gave.", "refusal": ""}'

    _stub_model(monkeypatch, capture)
    run(op_svc.operator_registry.create(PROJECT, "interiority", "what the body knows first"))

    out = run(studio.run_block(
        PROJECT,
        "/ threshold\n"
        "// voice: close third\n"
        "/ interiority\n",
        only_directives=[1],
        quarantine=False,
    ))
    # directive 1 still sees the note that sits above it, and only that note
    assert out["results"][1]["orchestration"] == {"voice": "close third"}
    assert "close third" in seen["user"]


def test_running_the_whole_block_is_still_available(store, threshold_operator, monkeypatch):
    """`only_directives=None` is the explicit re-run-everything action."""
    _stub_model(monkeypatch, '{"passage": "The latch gave.", "refusal": ""}')
    out = run(studio.run_block(PROJECT, "/ threshold\n/ threshold\n", quarantine=False))
    assert out["rendered"] == 2 and out["skipped"] == 0


# ══ instrumentation (record now, reason later) ═══════════════════════════════

def test_usage_records_renders_refusals_accepts_and_co_occurrence(
    store, threshold_operator, fixture_manuscript, monkeypatch
):
    manuscript_id, scene_id = fixture_manuscript
    run(op_svc.operator_registry.create(PROJECT, "interiority", "what the body knows first"))
    _stub_model(monkeypatch, '{"passage": "The latch gave.", "refusal": ""}')

    out = run(studio.run_block(
        PROJECT, "// goal: cross it\n/ threshold + interiority\n/ undeclared\n",
        manuscript_id=manuscript_id, scene_id=scene_id,
    ))
    run(psg_svc.passage_store.accept(out["results"][0]["passage_id"]))

    events = run(instrument.usage_for_project(PROJECT))
    kinds = {e["event"] for e in events}
    assert {"render", "refusal", "accept"} <= kinds

    rendered = next(e for e in events if e["event"] == "render")
    assert rendered["operators"] == ["threshold", "interiority"]
    assert rendered["operator_pairs"] == ["interiority|threshold"]   # co-occurrence, day one
    assert rendered["intent_keys"] == ["goal"]


def test_instrumentation_failure_never_breaks_a_render(store, threshold_operator, monkeypatch):
    """Write-behind means write-behind: a dead stats collection is invisible upstream."""
    class Dead:
        async def insert_one(self, doc):
            raise RuntimeError("usage collection is unreachable")

    monkeypatch.setattr(instrument, "writer_usage_collection", Dead())
    _stub_model(monkeypatch, '{"passage": "The latch gave.", "refusal": ""}')
    directive = dsl.parse_block("/ threshold\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    assert result.status == "ok" and result.text == "The latch gave."


# ══ ROLES-001: the renderer is its own job ═══════════════════════════════════

def test_the_renderer_resolves_its_own_role_not_the_archivists():
    """Rebinding corpus summarisation must not change how the author's book reads.

    Before ROLES-001 this call site read `llm_service.model`, which resolves to the
    `archivist` role — so the two jobs shared a binding by accident. They are separate
    roles now, and this pins that: rebinding one moves only one.
    """
    from backend.services import role_registry

    assert render_svc.ROLE == "manuscript_renderer"
    assert role_registry.get(render_svc.ROLE) is not None

    role_registry.bind("archivist", "some/other-model")
    try:
        assert role_registry.model_for(render_svc.ROLE) != "some/other-model"
    finally:
        role_registry.unbind("archivist")

    role_registry.bind(render_svc.ROLE, "a/renderer-model")
    try:
        assert role_registry.model_for(render_svc.ROLE) == "a/renderer-model"
    finally:
        role_registry.unbind(render_svc.ROLE)


# ══ the model being down is not a refusal ════════════════════════════════════

def test_missing_groq_key_is_unavailable_not_a_refusal(store, threshold_operator, monkeypatch):
    """A transient runtime gap and a statement about the work must stay distinguishable."""
    monkeypatch.setattr(render_svc.llm_service, "client", None, raising=False)
    directive = dsl.parse_block("/ threshold\n").directives[0]
    result = run(render_svc.render_directive(PROJECT, directive))

    assert result.status == "unavailable"
    assert result.status != REFUSED
    assert "GROQ_API_KEY" in result.refusal
