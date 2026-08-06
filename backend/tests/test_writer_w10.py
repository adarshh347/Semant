"""
Semant Writer · W10 — depth registers: the author's own cognitive layers.

THE AUTHOR'S-LADDER RULE is the gate, and it has two halves that this suite spends most of
its length on:

  NO FABRICATED DEPTH (render). `// register: X` foregrounds the author's operators tagged
  X and can do nothing else. Asked to work at a layer nothing of theirs carries, the render
  REFUSES. The tempting alternative — proceed and quietly ignore the note — is worse than
  refusing, because the author would read the result as prose written at their register
  when nothing about it was.

  NO INTERPRETATION (read). The depth view is derived from provenance: which register each
  operator carried when it fired. There is no model call on that path, no classifier, and a
  span the author typed carries no register at all rather than an inferred one.

And the guard that makes both possible: THE VOCABULARY STARTS EMPTY. There is no default
ladder, because whatever shipped as a default would become what most authors keep — so the
default would BE the imposed taxonomy, however reasonable it read.
"""
import pytest

from backend.services import manuscript_service as ms_svc
from backend.services.writer import instrument
from backend.services.writer import operators as op_svc
from backend.services.writer import passages as psg_svc
from backend.services.writer import recall as rc_svc
from backend.services.writer import registers as reg
from backend.services.writer import render as render_svc
from backend.services.writer import revisions as rev_svc
from backend.services.writer.dsl import ORCHESTRATION_KEYS, find_orchestration_leak, parse_block
from backend.services.writer.render import OK, REFUSED, RenderResult
from backend.tests.test_writer_w1 import FakeCollection, run

PROJECT = "ms_fixture"

#: The author's own ladder — deliberately NOT the classic one, so nothing can pass by
#: accidentally agreeing with a default.
LADDER = [
    {"name": "weather", "description": "what the room is doing"},
    {"name": "interior", "description": "what she will not say to herself"},
    {"name": "inheritance", "description": "what the house has decided for them"},
]


@pytest.fixture
def store(monkeypatch):
    ops, psgs, usage = FakeCollection(), FakeCollection(), FakeCollection()
    regs, versions_c = FakeCollection(), FakeCollection()
    manuscripts, scenes, snaps = FakeCollection(), FakeCollection(), FakeCollection()
    monkeypatch.setattr(op_svc, "writer_operator_collection", ops)
    monkeypatch.setattr(psg_svc, "writer_passage_collection", psgs)
    monkeypatch.setattr(instrument, "writer_usage_collection", usage)
    monkeypatch.setattr(reg, "writer_register_collection", regs)
    monkeypatch.setattr(rev_svc, "writer_passage_version_collection", versions_c)
    monkeypatch.setattr(rc_svc, "writer_passage_version_collection", versions_c)
    monkeypatch.setattr(ms_svc, "manuscript_collection", manuscripts)
    monkeypatch.setattr(ms_svc, "scene_collection", scenes)
    monkeypatch.setattr(ms_svc, "scene_version_collection", snaps)
    return {"registers": regs, "versions": versions_c, "usage": usage}


@pytest.fixture
def book(store):
    async def build():
        m = await ms_svc.manuscript_service.create_manuscript("Fixture")
        m = await ms_svc.manuscript_service.add_chapter(m["id"], "One")
        scene = await ms_svc.manuscript_service.add_scene(
            m["id"], m["chapters"][0]["id"], "The kitchen")
        return {"manuscript_id": m["id"], "scene_id": scene["id"]}
    return run(build())


@pytest.fixture
def ladder(store):
    run(reg.declare(PROJECT, LADDER))
    return LADDER


def declare_operator(name, definition, register="", **kw):
    return run(op_svc.operator_registry.create(
        PROJECT, name, definition, register=register, **kw))


def stub(monkeypatch, reply='{"passage": "The frost held.", "refusal": ""}'):
    seen = {}

    async def fake(system, user):
        seen["system"], seen["user"] = system, user
        return reply, "stub-model"
    monkeypatch.setattr(render_svc, "_call_model", fake)
    return seen


def render(block):
    directive = parse_block(block).directives[0]
    return run(render_svc.render_directive(PROJECT, directive))


# ══ NO IMPOSED TAXONOMY (gate step 1) ══════════════════════════════════════

def test_a_fresh_project_has_no_registers_at_all(store):
    """THE GUARD. Whatever shipped as a default would become what most authors keep."""
    assert run(reg.vocabulary(PROJECT)) == []
    assert run(reg.names(PROJECT)) == []


def test_the_classic_ladder_is_a_proposal_and_stores_nothing(store):
    proposed = reg.propose_template()

    assert proposed["committed"] is False
    assert [r["name"] for r in proposed["registers"]] == [
        "surface", "psychological", "philosophical"]
    # offering it changed nothing
    assert run(reg.vocabulary(PROJECT)) == []


def test_the_template_is_fully_editable_before_it_is_committed(store):
    proposed = reg.propose_template()
    edited = [
        {"name": "weather", "description": "renamed entirely"},
        {"name": "philosophical", "description": "kept but re-described"},
    ]
    run(reg.declare(PROJECT, edited))

    assert [r["name"] for r in run(reg.vocabulary(PROJECT))] == ["weather", "philosophical"]
    assert run(reg.vocabulary(PROJECT))[1]["description"] == "kept but re-described"
    # and the template constant is untouched by having been edited
    assert [r["name"] for r in reg.propose_template()["registers"]] == [
        r["name"] for r in proposed["registers"]]


def test_the_order_is_the_authors_and_is_stored_as_given(store):
    run(reg.declare(PROJECT, LADDER))
    stored = run(reg.vocabulary(PROJECT))
    assert [r["name"] for r in stored] == ["weather", "interior", "inheritance"]
    assert [r["order"] for r in stored] == [0, 1, 2]

    # reordering is just declaring the new order
    run(reg.declare(PROJECT, list(reversed(LADDER))))
    assert [r["name"] for r in run(reg.vocabulary(PROJECT))] == [
        "inheritance", "interior", "weather"]


def test_nothing_in_the_system_ranks_one_register_above_another(store, ladder):
    """`order` is the author's ladder, recorded. It is never compared.

    Scans the CODE with docstrings and comments stripped — the module explains this rule
    at length in prose, and a plain text scan would trip on the explanation rather than on
    a violation.
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(reg))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = body[1:] or [ast.Pass()]
    code = ast.unparse(ast.fix_missing_locations(tree)).lower()

    for smell in ("deeper", "shallower", "depth_score", "is_deeper", "profundity"):
        assert smell not in code, f"the module reasons about {smell}"

    # and no ordering comparison between two registers anywhere in it
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and any(
            isinstance(op, (ast.Lt, ast.Gt, ast.LtE, ast.GtE)) for op in node.ops
        ):
            rendered = ast.unparse(node).lower()
            assert "order" not in rendered, f"registers are being ranked: {rendered}"


def test_a_register_name_must_be_carriable_by_the_dsl(store):
    with pytest.raises(reg.RegisterError, match="cannot be a register name"):
        run(reg.declare(PROJECT, [{"name": "the deep one"}]))
    with pytest.raises(reg.RegisterError, match="declared twice"):
        run(reg.declare(PROJECT, [{"name": "interior"}, {"name": "Interior"}]))
    with pytest.raises(reg.RegisterError, match="has no name"):
        run(reg.declare(PROJECT, [{"description": "nameless"}]))


def test_an_empty_vocabulary_is_a_legal_declaration(store):
    """Having no depth axis is a real answer, not an unfinished state."""
    run(reg.declare(PROJECT, LADDER))
    run(reg.declare(PROJECT, []))
    assert run(reg.vocabulary(PROJECT)) == []


# ══ GROUNDED REGISTER REFERENCES (gate step 2) ═════════════════════════════

def test_an_operator_can_be_tagged_with_a_declared_register(store, ladder):
    op = declare_operator("frost", "cold as the house's opinion", register="weather")
    assert op["register"] == "weather"


def test_tagging_with_an_undeclared_register_is_rejected(store, ladder):
    """A register is a REFERENCE, like a `requires` target — never free text."""
    with pytest.raises(op_svc.OperatorError):
        declare_operator("frost", "cold", register="philosophical")


def test_tagging_before_any_register_is_declared_says_so(store):
    with pytest.raises(op_svc.OperatorError, match="have not declared any"):
        declare_operator("frost", "cold", register="interior")


def test_retagging_an_operator_bumps_its_version(store, ladder):
    """Retagging changes what the operator IS — provenance must be able to tell them apart."""
    declare_operator("frost", "cold", register="weather")
    updated = run(op_svc.operator_registry.update(
        PROJECT, "frost", {"register": "interior"}))

    assert updated["version"] == 2
    assert updated["register"] == "interior"
    assert updated["history"][0]["register"] == "weather"


def test_an_operator_with_no_register_stays_valid(store, ladder):
    """An operator that predates the ladder is not retroactively assigned a depth."""
    op = declare_operator("plain", "just a thing it does")
    assert op["register"] == ""


def test_a_register_still_in_use_cannot_be_dropped(store, ladder):
    declare_operator("frost", "cold", register="weather")
    with pytest.raises(reg.RegisterError, match="still carry"):
        run(reg.declare(PROJECT, [{"name": "interior"}, {"name": "inheritance"}]))
    # retag first, then it drops cleanly
    run(op_svc.operator_registry.update(PROJECT, "frost", {"register": "interior"}))
    run(reg.declare(PROJECT, [{"name": "interior"}, {"name": "inheritance"}]))
    assert run(reg.names(PROJECT)) == ["interior", "inheritance"]


def test_the_operator_schema_round_trips_the_register_field():
    """`register` shadows a metaclass name; assert instance access is unaffected."""
    from backend.schemas.writer import OperatorCreate, OperatorUpdate

    created = OperatorCreate(name="x", definition="d", register="interior")
    assert created.register == "interior"
    assert created.model_dump()["register"] == "interior"
    assert OperatorUpdate(register="weather").model_dump(exclude_none=True) == {
        "register": "weather"}


# ══ //register IS ORCHESTRATION (gate step 3) ══════════════════════════════

def test_register_is_an_orchestration_key(store):
    assert "register" in ORCHESTRATION_KEYS


def test_register_orchestration_foregrounds_the_authors_tagged_operators(
        store, ladder, monkeypatch):
    declare_operator("frost", "cold as the house's opinion",
                     rendering_intent="one image of cold", register="weather")
    declare_operator("withheld", "what she will not say",
                     rendering_intent="say less than the moment wants", register="interior")
    seen = stub(monkeypatch)

    result = render("// register: interior\n/ frost(the kitchen) + withheld(the letter)")

    assert result.status == OK
    # the prompt POINTS AT THE AUTHOR'S OPERATOR, and adds no idea of what depth means
    assert "`withheld`" in seen["user"]
    assert "interior" in seen["user"]
    for invented in ("more philosophical", "deeper", "profound", "weightier",
                     "add depth", "layers of meaning"):
        assert invented not in seen["user"].lower()


def test_the_prompt_never_glosses_what_a_register_means(store, ladder, monkeypatch):
    """The register's meaning lives in the operators tagged with it, which are already
    in the prompt in full. Any gloss here would be the system's idea of the layer."""
    declare_operator("withheld", "what she will not say", register="interior")
    seen = stub(monkeypatch)
    render("// register: interior\n/ withheld(the letter)")

    # the author's DESCRIPTION of the register is not smuggled in as an instruction either
    assert "what she will not say to herself" not in seen["user"]


def test_provenance_records_the_active_register(store, ladder, monkeypatch):
    declare_operator("withheld", "what she will not say", register="interior")
    stub(monkeypatch)
    result = render("// register: interior\n/ withheld(the letter)")

    assert result.provenance["registers"] == ["interior"]
    assert result.provenance["intents"] == [{"key": "register", "value": "interior"}]


def test_provenance_stamps_the_register_each_operator_carried_when_it_fired(
        store, ladder, monkeypatch):
    """Stamped, not looked up: retagging later must not rewrite the book's history."""
    declare_operator("withheld", "what she will not say", register="interior")
    stub(monkeypatch)
    result = render("// register: interior\n/ withheld(the letter)")

    assert result.provenance["operators"][0]["register"] == "interior"

    run(op_svc.operator_registry.update(PROJECT, "withheld", {"register": "weather"}))
    assert result.provenance["operators"][0]["register"] == "interior"


def test_more_than_one_register_can_be_foregrounded(store, ladder, monkeypatch):
    declare_operator("frost", "cold", register="weather")
    declare_operator("withheld", "unsaid", register="interior")
    stub(monkeypatch)
    result = render("// register: weather, interior\n/ frost(x) + withheld(y)")

    assert result.provenance["registers"] == ["weather", "interior"]


def test_register_never_reaches_the_page(store, ladder, monkeypatch):
    """I6 — it is a `//` note, so the existing wall covers it."""
    declare_operator("withheld", "unsaid", register="interior")
    stub(monkeypatch,
         '{"passage": "register: interior\\nThe frost held.", "refusal": ""}')
    result = render("// register: interior\n/ withheld(the letter)")

    assert "register:" not in result.text
    assert "interior" not in result.text
    assert result.diagnostics


def test_a_register_line_is_detected_as_a_leak(store, ladder):
    notes = parse_block("// register: interior\n/ x").directives[0].orchestration
    assert find_orchestration_leak("register: interior", notes)


# ══ NO FABRICATED DEPTH (gate step 4 — the point) ══════════════════════════

def test_a_register_with_no_operators_carrying_it_REFUSES(store, ladder, monkeypatch):
    """THE GATE CHECK. Proceeding and ignoring the note would be worse than refusing:
    the author would read the result as prose written at their register."""
    declare_operator("frost", "cold", register="weather")

    async def explode(system, user):
        raise AssertionError("a register nothing carries must refuse before the model")
    monkeypatch.setattr(render_svc, "_call_model", explode)

    result = render("// register: inheritance\n/ frost(the kitchen)")

    assert result.status == REFUSED
    assert "inheritance" in result.refusal
    assert "none of the operators" in result.refusal


def test_the_refusal_says_how_to_make_it_work(store, ladder, monkeypatch):
    declare_operator("frost", "cold", register="weather")
    monkeypatch.setattr(render_svc, "_call_model", None)
    result = render("// register: inheritance\n/ frost(the kitchen)")

    assert "Tag an operator with it" in result.refusal
    assert "bumps its version" in result.refusal


def test_an_undeclared_register_at_render_refuses(store, ladder, monkeypatch):
    declare_operator("frost", "cold", register="weather")
    monkeypatch.setattr(render_svc, "_call_model", None)
    result = render("// register: philosophical\n/ frost(the kitchen)")

    assert result.status == REFUSED
    assert "names no register you declared" in result.refusal
    assert "weather" in result.refusal          # it says what they DO have


def test_a_register_with_no_vocabulary_at_all_refuses(store, monkeypatch):
    declare_operator("frost", "cold")
    monkeypatch.setattr(render_svc, "_call_model", None)
    result = render("// register: interior\n/ frost(the kitchen)")

    assert result.status == REFUSED
    assert "the ladder is yours" in result.refusal


def test_the_refusal_is_recorded_and_nothing_is_rendered(store, ladder, monkeypatch):
    declare_operator("frost", "cold", register="weather")
    monkeypatch.setattr(render_svc, "_call_model", None)
    result = render("// register: inheritance\n/ frost(the kitchen)")

    assert result.text == ""
    # what the author asked for is on the record even though it refused
    assert result.provenance["registers"] == ["inheritance"]


def test_a_pulled_operator_can_satisfy_the_register(store, ladder, monkeypatch):
    """W3's `requires` operators participate in the render, so they count."""
    declare_operator("withheld", "unsaid", register="interior")
    declare_operator("frost", "cold", register="weather",
                     relations=[{"kind": "requires", "target": "withheld"}])
    stub(monkeypatch)

    result = render("// register: interior\n/ frost(the kitchen)")
    assert result.status == OK


def test_no_register_note_means_business_as_usual(store, ladder, monkeypatch):
    declare_operator("frost", "cold", register="weather")
    stub(monkeypatch)
    result = render("/ frost(the kitchen)")

    assert result.status == OK
    assert result.provenance["registers"] == []


# ══ NO INTERPRETATION AT READ (gate step 5 — the other point) ══════════════

def commit(text, book, provenance):
    async def go():
        psg = await psg_svc.passage_store.quarantine(
            PROJECT, RenderResult(status=OK, text=text, provenance=provenance,
                                  model="stub-model"),
            manuscript_id=book["manuscript_id"], scene_id=book["scene_id"])
        return await psg_svc.passage_store.accept(psg["id"], scene_id=book["scene_id"])
    return run(go())


def prov(*stamps):
    return {"operators": [{"name": n, "version": 1, "source": "direct", "register": r}
                          for n, r in stamps],
            "intents": []}


def test_the_depth_view_is_derived_from_provenance_alone(store, ladder, book):
    commit("The frost held the window.", book, prov(("frost", "weather")))
    commit("She did not say it.", book, prov(("withheld", "interior")))

    spans = run(rc_svc.committed_spans(PROJECT))
    view = run(reg.depth_view(PROJECT, spans))

    by_register = view["by_register"]
    assert len(by_register["weather"]) == 1
    assert len(by_register["interior"]) == 1
    assert by_register["inheritance"] == []


def test_the_depth_view_makes_no_model_call(store, ladder, book, monkeypatch):
    """THE GATE CHECK. A generated reading of what the book means at a layer would be
    fabrication on the axis where it is hardest to catch."""
    import ast
    import inspect

    commit("The frost held.", book, prov(("frost", "weather")))

    async def explode(system, user):
        raise AssertionError("the depth view must not reach a model")
    monkeypatch.setattr(render_svc, "_call_model", explode)

    spans = run(rc_svc.committed_spans(PROJECT))
    run(reg.depth_view(PROJECT, spans))    # would raise if it called

    tree = ast.parse(inspect.getsource(reg))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    for forbidden in ("llm_service", "role_registry", "groq", "render"):
        assert not any(forbidden in name for name in imported), forbidden


def test_a_hand_typed_span_carries_no_inferred_register(store, ladder, book):
    """No classifier, no heuristic. Prose with no operator behind it has no depth data."""
    commit("She had written this sentence herself.", book, {"operators": [], "intents": []})

    spans = run(rc_svc.committed_spans(PROJECT))
    view = run(reg.depth_view(PROJECT, spans))

    assert view["spans"][0]["registers"] == []
    assert len(view["untagged"]) == 1
    assert all(not v for v in view["by_register"].values())


def test_the_view_shows_registers_in_the_authors_ladder_order(store, ladder, book):
    commit("Both at once.", book, prov(("withheld", "interior"), ("frost", "weather")))

    view = run(reg.depth_view(PROJECT, run(rc_svc.committed_spans(PROJECT))))
    # declared weather → interior → inheritance, so weather leads regardless of firing order
    assert view["spans"][0]["registers"] == ["weather", "interior"]


def test_the_view_returns_the_authors_prose_unaltered(store, ladder, book):
    """W9's verbatim rule holds here too: this view shows prose, it never describes it."""
    text = "The frost held.\nShe did not say it.\n\nThe letter stayed on the dresser."
    commit(text, book, prov(("frost", "weather")))

    view = run(reg.depth_view(PROJECT, run(rc_svc.committed_spans(PROJECT))))
    assert view["spans"][0]["text"] == text


def test_the_view_carries_no_reading_of_any_layer(store, ladder, book):
    commit("The frost held.", book, prov(("frost", "weather")))
    view = run(reg.depth_view(PROJECT, run(rc_svc.committed_spans(PROJECT))))

    keys = set(view) | {k for s in view["spans"] for k in s}
    for forbidden in ("reading", "interpretation", "meaning", "analysis", "summary",
                      "theme", "score"):
        assert forbidden not in keys


def test_registers_in_reads_only_what_was_stamped(store):
    assert reg.registers_in(prov(("a", "weather"), ("b", ""))) == ["weather"]
    assert reg.registers_in({}) == []
    assert reg.registers_in({"operators": ["not a dict"]}) == []


# ══ the walls still hold (gate steps 6, 7) ═════════════════════════════════

def test_a_register_render_with_style_by_reference_still_refuses(store, ladder, monkeypatch):
    """I5 — the depth axis opens no bypass."""
    declare_operator("withheld", "unsaid", register="interior")

    async def explode(system, user):
        raise AssertionError("style-by-reference must refuse before the model")
    monkeypatch.setattr(render_svc, "_call_model", explode)

    result = render("// register: interior\n// voice: like Tolstoy\n/ withheld(the letter)")

    assert result.status == REFUSED
    assert "Tolstoy" in result.refusal


def test_a_register_named_like_a_genre_is_still_the_authors_word(store, monkeypatch):
    """`register` is exempt from the style heuristic because DECLARING is what grounds it.

    An author who names a layer `noir` because that is what the layer IS to them must not
    be told they cannot use their own declared word.
    """
    run(reg.declare(PROJECT, [{"name": "noir", "description": "the way the house lies"}]))
    declare_operator("shadow", "what the lamp does not reach", register="noir")
    stub(monkeypatch)

    result = render("// register: noir\n/ shadow(the hallway)")
    assert result.status == OK

    # but the same word in `//voice` is still an import, and still refuses
    monkeypatch.setattr(render_svc, "_call_model", None)
    assert render("// voice: noir\n/ shadow(the hallway)").status == REFUSED


def test_declaring_and_tagging_and_viewing_write_no_prose(store, ladder, book):
    """I1 — gate step 7."""
    commit("The frost held.", book, prov(("frost", "weather")))
    before = run(ms_svc.manuscript_service.export_manuscript(
        book["manuscript_id"]))["content"]

    run(reg.declare(PROJECT, list(reversed(LADDER))))
    declare_operator("withheld", "unsaid", register="interior")
    run(op_svc.operator_registry.update(PROJECT, "withheld", {"register": "weather"}))
    run(reg.depth_view(PROJECT, run(rc_svc.committed_spans(PROJECT))))

    after = run(ms_svc.manuscript_service.export_manuscript(
        book["manuscript_id"]))["content"]
    assert after == before


def test_a_register_render_is_quarantined_like_any_other(store, ladder, book, monkeypatch):
    declare_operator("withheld", "unsaid", register="interior")
    stub(monkeypatch)
    before = run(ms_svc.manuscript_service.export_manuscript(
        book["manuscript_id"]))["content"]

    from backend.services.writer import studio
    result = run(studio.run_block(
        PROJECT, "// register: interior\n/ withheld(the letter)",
        manuscript_id=book["manuscript_id"], scene_id=book["scene_id"]))

    passage = run(psg_svc.passage_store.get(result["results"][0]["passage_id"]))
    assert passage["committed"] is False
    assert run(ms_svc.manuscript_service.export_manuscript(
        book["manuscript_id"]))["content"] == before
