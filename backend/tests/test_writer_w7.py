"""
Semant Writer · W7 — the alignment reading: the honest editor.

The render loop may only compose in the author's language. This is that honesty run
backwards: the reading may only critique in the author's language. Most of this suite is
about the line between the two kinds of editor, because that line is the entire gate:

  THE TASTE WALL. The model may use its competence to MEASURE CONFORMANCE TO A TERM THE
  AUTHOR DECLARED. It may not introduce a term of its own. Enforced structurally — a flag
  that names no declared element is dropped before the author sees it, exactly as the
  style-by-reference wall is a pre-flight refusal rather than a prompt request. The lesson
  that made that necessary is in `GROUNDING.md`, and it applies here for the same reason.

  SILENCE IS A RESULT. A reading with nothing groundable to say returns `aligned`, and a
  passage with nothing declared returns `thin`. Neither is a failure and neither may be
  padded with an invented nitpick — an invented flag is worse than silence, because the
  author cannot tell it from a real one.

  IT NEVER WRITES. No prose, no rewrite, no canon. Asserted, not assumed.
"""
import pytest

from backend.services import manuscript_service as ms_svc
from backend.services.writer import alignment as align
from backend.services.writer import assemblages as asm
from backend.services.writer import instrument
from backend.services.writer import operators as op_svc
from backend.services.writer import passages as psg_svc
from backend.services.writer import readings as rdg
from backend.services.writer import render as render_svc
from backend.services.writer import studio
from backend.tests.test_writer_w1 import FakeCollection, run

PROJECT = "ms_fixture"

PASSAGE = "The latch gave before she had decided to push it. She waited."


@pytest.fixture
def store(monkeypatch):
    ops, psgs, usage, reads = FakeCollection(), FakeCollection(), FakeCollection(), FakeCollection()
    manuscripts, scenes, versions = FakeCollection(), FakeCollection(), FakeCollection()
    monkeypatch.setattr(op_svc, "writer_operator_collection", ops)
    monkeypatch.setattr(psg_svc, "writer_passage_collection", psgs)
    monkeypatch.setattr(instrument, "writer_usage_collection", usage)
    monkeypatch.setattr(asm, "writer_usage_collection", usage)
    monkeypatch.setattr(rdg, "writer_reading_collection", reads)
    monkeypatch.setattr(ms_svc, "manuscript_collection", manuscripts)
    monkeypatch.setattr(ms_svc, "scene_collection", scenes)
    monkeypatch.setattr(ms_svc, "scene_version_collection", versions)
    return {"operators": ops, "readings": reads, "scenes": scenes, "usage": usage}


@pytest.fixture
def ontology(store):
    async def build():
        await op_svc.operator_registry.create(
            PROJECT, "restraint", "what is withheld does the work",
            rendering_intent="say less than the moment wants; never name the feeling",
            negative_examples=["Her heart shattered into a thousand pieces."])
        await op_svc.operator_registry.create(
            PROJECT, "threshold", "a crossing noticed only after it is behind them",
            rendering_intent="one held moment; no summary of what it means")
        # an operator with NO declared standard — only what it is
        await op_svc.operator_registry.create(PROJECT, "bare", "just a thing it does")
        return await op_svc.operator_registry.by_name(PROJECT)
    return run(build())


def _stub(monkeypatch, reply):
    async def fake(system, user):
        out = reply(system, user) if callable(reply) else reply
        return out, "stub-model"
    monkeypatch.setattr(align, "_call_model", fake)


def provenance(operators=(("restraint", 1),), intents=(("avoid", "melodrama"),)):
    return {
        "operators": [{"name": n, "version": v, "source": "direct"} for n, v in operators],
        "intents": [{"key": k, "value": v} for k, v in intents],
    }


def read(passage=PASSAGE, prov=None, ontology_map=None):
    async def go():
        return await align.read_alignment(
            PROJECT, passage,
            provenance() if prov is None else prov,
            ontology_map if ontology_map is not None
            else await op_svc.operator_registry.by_name(PROJECT),
        )
    return run(go())


# ══ what the standard IS ═════════════════════════════════════════════════════

def test_the_standard_is_intents_and_operator_intents_and_negative_examples(store, ontology):
    elements = align.declared_elements(provenance(), ontology)
    ids = {e["id"] for e in elements}
    assert "intent:avoid" in ids
    assert "operator:restraint:intent" in ids
    assert "operator:restraint:not:0" in ids


def test_an_operator_definition_is_not_a_standard(store, ontology):
    """A definition says what the thing IS — the basis for RENDERING it.

    Measuring prose against a definition slides back into "does this read like the idea?",
    which is taste wearing a citation.
    """
    elements = align.declared_elements(provenance(), ontology)
    declared = " ".join(e["declared"] for e in elements)
    assert "what is withheld does the work" not in declared


def test_avoid_and_toward_are_distinguished(store, ontology):
    elements = {e["id"]: e for e in align.declared_elements(provenance(), ontology)}
    assert elements["intent:avoid"]["polarity"] == "avoid"
    assert elements["operator:restraint:not:0"]["polarity"] == "avoid"
    assert elements["operator:restraint:intent"]["polarity"] == "toward"


# ══ THE TASTE WALL — enforced structurally ═══════════════════════════════════

def test_a_flag_naming_no_declared_element_is_dropped(store, ontology):
    """The model bringing a standard of its own. Dropped before the author sees it."""
    elements = align.declared_elements(provenance(), ontology)
    kept, dropped = align.ground_flags(
        [{"element": "", "span": "She waited.", "divergence": "vary your sentence length"}],
        elements, PASSAGE,
    )
    assert kept == []
    assert any("ungrounded" in d for d in dropped)


def test_a_flag_naming_an_element_that_was_never_offered_is_dropped(store, ontology):
    elements = align.declared_elements(provenance(), ontology)
    kept, dropped = align.ground_flags(
        [{"element": "craft:rhythm", "span": "She waited.", "divergence": "monotonous"}],
        elements, PASSAGE,
    )
    assert kept == []
    assert any("craft:rhythm" in d for d in dropped)


def test_a_flag_quoting_text_that_is_not_in_the_passage_is_dropped(store, ontology):
    """A flag about prose that does not exist is a flag about nothing."""
    elements = align.declared_elements(provenance(), ontology)
    kept, dropped = align.ground_flags(
        [{"element": "intent:avoid", "span": "her heart shattered",
          "divergence": "melodramatic"}],
        elements, PASSAGE,
    )
    assert kept == []
    assert any("not in the passage" in d for d in dropped)


def test_a_flag_quoting_nothing_at_all_is_dropped(store, ontology):
    """No span means the flag is a verdict on the passage as a whole.

    That is the shape a quality score takes, and the author cannot locate it to judge it.
    """
    elements = align.declared_elements(provenance(), ontology)
    kept, dropped = align.ground_flags(
        [{"element": "intent:avoid", "span": "", "divergence": "the tone is off throughout"}],
        elements, PASSAGE,
    )
    assert kept == []
    assert any("quoted nothing" in d for d in dropped)


def test_a_grounded_flag_survives_and_carries_what_it_rests_on(store, ontology):
    elements = align.declared_elements(provenance(), ontology)
    kept, dropped = align.ground_flags(
        [{"element": "intent:avoid", "span": "She waited.",
          "divergence": "this leans on the pause for feeling"}],
        elements, PASSAGE,
    )
    assert dropped == []
    assert kept[0]["element"] == "intent:avoid"
    assert kept[0]["declared"] == "melodrama"          # the author's own word
    assert kept[0]["span"] == "She waited."


def test_an_undeclared_quality_issue_is_not_raised(store, ontology, monkeypatch):
    """THE GATE CHECK. Repetitive openings that no operator or intent names.

    A generic editor would raise this and be helpful. This one may not: no declared element
    covers it, so it is not the reading's to say.
    """
    repetitive = "She waited. She waited again. She waited once more."
    _stub(monkeypatch, '{"flags": [{"element": "craft:repetition", '
                       '"span": "She waited again.", '
                       '"divergence": "three sentences open the same way"}]}')

    result = read(passage=repetitive)

    assert result.status == align.ALIGNED
    assert result.flags == ()
    assert any("ungrounded" in d for d in result.diagnostics)


def test_a_real_avoid_violation_is_flagged_citing_that_intent(store, ontology, monkeypatch):
    melodramatic = "Her heart shattered into a thousand pieces as the latch gave."
    _stub(monkeypatch, '{"flags": [{"element": "intent:avoid", '
                       '"span": "Her heart shattered into a thousand pieces", '
                       '"divergence": "this is the melodrama you said to avoid"}]}')

    result = read(passage=melodramatic)

    assert result.status == align.FLAGGED
    assert result.flags[0]["element"] == "intent:avoid"
    assert result.flags[0]["declared"] == "melodrama"


def test_every_surviving_flag_references_a_provenance_element(store, ontology, monkeypatch):
    """Mixed reply: one grounded, two not. Only the grounded one reaches the author."""
    _stub(monkeypatch, '{"flags": ['
                       '{"element": "operator:restraint:intent", "span": "She waited.", '
                       ' "divergence": "names the feeling"}, '
                       '{"element": "style:verbs", "span": "The latch gave", '
                       ' "divergence": "stronger verb here"}, '
                       '{"span": "She waited.", "divergence": "show do not tell"}]}')

    result = read()
    assert len(result.flags) == 1
    assert result.flags[0]["element"] == "operator:restraint:intent"
    assert all(f["element"] for f in result.flags)


def test_the_prompt_contributes_no_evaluative_vocabulary_of_its_own(store, ontology):
    elements = align.declared_elements(provenance(), ontology)
    prompt = align.build_reading_prompt(PASSAGE, elements)

    # the author's own words are there
    assert "melodrama" in prompt["user"]
    assert "say less than the moment wants" in prompt["user"]

    # and the builder adds no standard of its own
    user = prompt["user"].lower()
    for invented in ("vivid", "concise", "elegant", "compelling", "stronger", "improve"):
        assert invented not in user


def test_the_system_prompt_forbids_bringing_a_term_and_permits_silence():
    system = align.build_reading_prompt("x", [])["system"]
    assert "not bringing terms of your own" in system
    assert "SILENCE IS A CORRECT AND VALUED ANSWER" in system
    assert "Do not suggest a replacement" in system


# ══ refusal as silence ═══════════════════════════════════════════════════════

def test_a_passage_that_honours_everything_returns_aligned(store, ontology, monkeypatch):
    _stub(monkeypatch, '{"flags": []}')
    result = read()
    assert result.status == align.ALIGNED
    assert result.flags == ()
    assert "nothing here diverges" in result.detail


def test_a_thin_passage_says_so_rather_than_inventing_advice(store, ontology, monkeypatch):
    """Operators that say what they are but not what they should do, and no staging."""
    async def explode(system, user):
        raise AssertionError("a thin passage must not reach the model")

    monkeypatch.setattr(align, "_call_model", explode)
    result = read(prov=provenance(operators=(("bare", 1),), intents=()))

    assert result.status == align.THIN
    assert result.flags == ()
    assert "Little declared intent" in result.detail


def test_a_passage_with_no_provenance_is_not_critiqued_at_all(store, ontology, monkeypatch):
    """SCOPE. Prose the author typed themselves is measured against nothing.

    Critiquing it against operators it was never made from would be the system inventing a
    yardstick and attributing it to the author.
    """
    async def explode(system, user):
        raise AssertionError("an unprovenanced span must not reach the model")

    monkeypatch.setattr(align, "_call_model", explode)
    result = read(prov={})

    assert result.status == align.NO_PROVENANCE
    assert result.flags == ()
    assert "no declared standard" in result.detail


def test_a_passage_is_measured_only_against_its_own_operators(store, ontology, monkeypatch):
    """`threshold` exists in the project but did not make this passage."""
    seen = {}

    def capture(system, user):
        seen["user"] = user
        return '{"flags": []}'

    _stub(monkeypatch, capture)
    read(prov=provenance(operators=(("restraint", 1),), intents=()))

    assert "say less than the moment wants" in seen["user"]
    assert "one held moment" not in seen["user"]


# ══ it never writes ══════════════════════════════════════════════════════════

def test_the_result_carries_no_prose(store, ontology, monkeypatch):
    """There is no `text` on an AlignmentResult, and a rewrite cannot be smuggled in."""
    _stub(monkeypatch, '{"flags": [{"element": "intent:avoid", "span": "She waited.", '
                       '"divergence": "x", "rewrite": "She stood very still."}]}')
    result = read()
    assert not hasattr(result, "text")
    assert "rewrite" not in result.flags[0]


def test_a_full_reading_session_leaves_canon_byte_identical(store, ontology, monkeypatch):
    async def build():
        m = await ms_svc.manuscript_service.create_manuscript("Fixture")
        m = await ms_svc.manuscript_service.add_chapter(m["id"], "One")
        await ms_svc.manuscript_service.add_scene(
            m["id"], m["chapters"][0]["id"], "Scene",
            blocks=[{"id": "b1", "type": "paragraph",
                     "content": "<p>The latch gave before she had decided to push it.</p>",
                     "color": None, "origin": "user_confirmed"}])
        return m["id"]

    manuscript_id = run(build())
    before = run(ms_svc.manuscript_service.export_manuscript(manuscript_id))["content"]

    _stub(monkeypatch, '{"flags": [{"element": "intent:avoid", "span": "She waited.", '
                       '"divergence": "leans on the pause"}]}')
    result = read()
    reading = run(rdg.store(PROJECT, result, manuscript_id=manuscript_id))
    run(rdg.decide(reading["id"], reading["flags"][0]["id"], rdg.DISMISSED))

    after = run(ms_svc.manuscript_service.export_manuscript(manuscript_id))["content"]
    assert after == before


def test_deciding_a_flag_changes_no_ontology(store, ontology, monkeypatch):
    before = run(op_svc.operator_registry.list(PROJECT))
    _stub(monkeypatch, '{"flags": [{"element": "operator:restraint:intent", '
                       '"span": "She waited.", "divergence": "x"}]}')
    result = read()
    reading = run(rdg.store(PROJECT, result))
    run(rdg.decide(reading["id"], reading["flags"][0]["id"], rdg.ACTED))

    assert run(op_svc.operator_registry.list(PROJECT)) == before


# ══ the reading is itself audited ════════════════════════════════════════════

def test_a_reading_records_what_it_measured_against_and_which_model(store, ontology,
                                                                    monkeypatch):
    _stub(monkeypatch, '{"flags": []}')
    result = read()
    reading = run(rdg.store(PROJECT, result))

    assert reading["model"] == "stub-model"
    ids = {e["id"] for e in reading["measured_against"]}
    assert "intent:avoid" in ids and "operator:restraint:intent" in ids


def test_a_flag_carries_the_operator_and_version_it_cited(store, ontology, monkeypatch):
    _stub(monkeypatch, '{"flags": [{"element": "operator:restraint:intent", '
                       '"span": "She waited.", "divergence": "names the feeling"}]}')
    result = read()
    flag = result.flags[0]
    assert flag["operator"] == "restraint"
    assert flag["operator_version"] == 1
    assert flag["element_kind"] == "operator_intent"


def test_the_reader_has_its_own_role_apart_from_the_renderer():
    """Rebinding the model that WRITES the prose must not change the one that JUDGES it."""
    from backend.services import role_registry

    assert align.ROLE == "alignment_reader"
    assert role_registry.get(align.ROLE) is not None
    role_registry.bind("manuscript_renderer", "some/other-model")
    try:
        assert role_registry.model_for(align.ROLE) != "some/other-model"
    finally:
        role_registry.unbind("manuscript_renderer")


# ══ propose-not-commit, and the calibration signal ══════════════════════════

def test_a_flag_starts_open_and_a_decision_is_made_once(store, ontology, monkeypatch):
    _stub(monkeypatch, '{"flags": [{"element": "intent:avoid", "span": "She waited.", '
                       '"divergence": "x"}]}')
    reading = run(rdg.store(PROJECT, read()))
    assert reading["flags"][0]["state"] == rdg.OPEN

    run(rdg.decide(reading["id"], reading["flags"][0]["id"], rdg.DISMISSED))
    with pytest.raises(rdg.ReadingError, match="already dismissed"):
        run(rdg.decide(reading["id"], reading["flags"][0]["id"], rdg.ACTED))


def test_the_authors_response_is_logged_with_the_operator_it_cited(store, ontology,
                                                                   monkeypatch):
    """§5 — the first honest signal of which operators are working."""
    _stub(monkeypatch, '{"flags": [{"element": "operator:restraint:intent", '
                       '"span": "She waited.", "divergence": "names the feeling"}]}')
    reading = run(rdg.store(PROJECT, read()))
    run(rdg.decide(reading["id"], reading["flags"][0]["id"], rdg.ACTED))

    events = run(instrument.usage_for_project(PROJECT, limit=200))
    acted = next(e for e in events if e["event"] == align.FLAG_ACTED)
    assert acted["operators"] == ["restraint"]
    assert acted["extra"]["element"] == "operator:restraint:intent"


def test_the_reading_itself_is_logged_with_the_operators_it_flagged(store, ontology,
                                                                    monkeypatch):
    _stub(monkeypatch, '{"flags": [{"element": "operator:restraint:intent", '
                       '"span": "She waited.", "divergence": "x"}]}')
    read()
    events = run(instrument.usage_for_project(PROJECT, limit=200))
    reading_event = next(e for e in events if e["event"] == align.READ)
    assert reading_event["extra"]["flagged_operators"] == ["restraint"]
    assert reading_event["extra"]["flags"] == 1


def test_an_invalid_decision_state_is_refused(store, ontology, monkeypatch):
    _stub(monkeypatch, '{"flags": [{"element": "intent:avoid", "span": "She waited.", '
                       '"divergence": "x"}]}')
    reading = run(rdg.store(PROJECT, read()))
    with pytest.raises(rdg.ReadingError):
        run(rdg.decide(reading["id"], reading["flags"][0]["id"], "fixed"))


# ══ the model being down is not a verdict ═══════════════════════════════════

def test_an_unconfigured_model_is_unavailable_not_aligned(store, ontology, monkeypatch):
    """`aligned` means measured and clean. It must never mean "could not look"."""
    monkeypatch.setattr(align.llm_service, "client", None, raising=False)
    result = read()
    assert result.status != align.ALIGNED
    assert result.status == "unavailable"


@pytest.mark.parametrize("reply", [
    "this is not json at all",
    '["flags"]',                       # JSON, but not an object
    '{"notes": "looks fine to me"}',   # an object, but no list of flags
    '{"flags": "none"}',               # a `flags` key that is not a list
])
def test_a_reply_that_cannot_be_read_is_an_error_not_aligned(store, ontology, monkeypatch,
                                                             reply):
    """The same rule as an unreachable model, one layer in.

    Zero PARSED flags and zero FOUND flags are different facts. Reporting an unreadable
    reply as `aligned` would put the most reassuring answer behind the least reliable
    moment, and the author would have no way to tell it from a real clean reading.
    """
    _stub(monkeypatch, reply)
    result = read()
    assert result.status != align.ALIGNED
    assert result.status == "error"
    assert result.flags == ()
    assert result.diagnostics


# ══ malformed provenance is skipped, not raised on ══════════════════════════

@pytest.mark.parametrize("prov", [
    {"intents": ["avoid melodrama"], "operators": [{"name": "restraint", "version": 1}]},
    {"intents": [{"key": "avoid", "value": "melodrama"}], "operators": ["restraint"]},
    {"intents": "avoid melodrama", "operators": None},
    "not a provenance record at all",
])
def test_malformed_provenance_does_not_crash_the_reading(store, ontology, prov):
    """A read-only diagnostic must not 500 on a request that changes nothing."""
    elements = align.declared_elements(prov, ontology)
    assert all(isinstance(e, dict) and e["id"] and e["declared"] for e in elements)


def test_a_malformed_stamp_is_skipped_and_the_good_ones_still_measured(store, ontology):
    elements = align.declared_elements(
        {"intents": [{"key": "avoid", "value": "melodrama"}, "junk", None],
         "operators": [{"name": "restraint", "version": 1}, "junk"]},
        ontology,
    )
    ids = {e["id"] for e in elements}
    assert "intent:avoid" in ids and "operator:restraint:intent" in ids


def test_a_second_decision_on_the_same_flag_loses(store, ontology, monkeypatch):
    """Compare-and-set, not check-then-write — one judgement, one calibration record."""
    _stub(monkeypatch, '{"flags": [{"element": "intent:avoid", "span": "She waited.", '
                       '"divergence": "x"}]}')
    reading = run(rdg.store(PROJECT, read()))
    flag_id = reading["flags"][0]["id"]

    run(rdg.decide(reading["id"], flag_id, rdg.DISMISSED))
    with pytest.raises(rdg.ReadingError, match="already dismissed"):
        run(rdg.decide(reading["id"], flag_id, rdg.ACTED))

    after = run(rdg.get(reading["id"]))
    assert after["flags"][0]["state"] == rdg.DISMISSED
    events = run(instrument.usage_for_project(PROJECT, limit=200))
    decisions = [e for e in events
                 if e["event"] in (align.FLAG_DISMISSED, align.FLAG_ACTED)]
    assert len(decisions) == 1


def test_deciding_one_flag_leaves_the_others_alone(store, ontology, monkeypatch):
    """The write updates ONE element rather than replacing the array."""
    _stub(monkeypatch, '{"flags": ['
                       '{"element": "intent:avoid", "span": "She waited.", "divergence": "a"}, '
                       '{"element": "operator:restraint:intent", "span": "The latch gave", '
                       ' "divergence": "b"}]}')
    reading = run(rdg.store(PROJECT, read()))
    first, second = reading["flags"][0]["id"], reading["flags"][1]["id"]

    run(rdg.decide(reading["id"], first, rdg.ACTED))
    run(rdg.decide(reading["id"], second, rdg.DISMISSED))

    states = {f["id"]: f["state"] for f in run(rdg.get(reading["id"]))["flags"]}
    assert states == {first: rdg.ACTED, second: rdg.DISMISSED}
