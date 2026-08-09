"""
HARNESS-003A §2 — the source ledger loses nothing and invents nothing.

The ledger is the object every later pass is AUDITED against, so its two properties have to hold on
any input rather than on the inputs somebody thought of: every span points at the words it claims
to, and every character of the prompt is either inside exactly one clause or is a separator between
two of them.

The prompts here are deliberately awkward — run-ons, comma splices, double hyphens, no capitals,
unicode dashes — because a splitter tested only on well-formed sentences is a splitter tested on
prose nobody types.
"""
from __future__ import annotations

import pytest

from backend.schemas.semantic_compilation import (ReadingBlock, ReadingBlockKind, SceneReading,
                                                  SourceUnitKind, ModelReceipt)
from backend.services.semantic_compilation import ledger

INQUIRY = "inq_000000000001"

AWKWARD = (
    "even folding through the things can have different styles the way they affect perception. "
    "in the first one it feels so hard somehow, very blunt, very sharp edges of the parts, "
    "whereas in the second, that is a damn different treatment--the maker has cut them in such a "
    "manner that it creates the effect of thinness; a bit similar is the third one but yeah "
    "shares slight bluntness with the first"
)

PROMPTS = [
    AWKWARD,
    "One sentence, and no terminator",
    "  leading and trailing whitespace  ",
    "a; b; c",
    "unicode — dashes – everywhere",
    "trailing punctuation....",
    "!!!",
    "a" * 400,
]


def a_reading(*blocks) -> SceneReading:
    return SceneReading(
        text="the theorist's own summary paragraph, which is NOT a source unit",
        blocks=list(blocks),
        provenance=ModelReceipt(role="scene_theorist"))


def a_block(block_id, text, kind=ReadingBlockKind.PART, images=()) -> ReadingBlock:
    return ReadingBlock(block_id=block_id, kind=kind, text=text, image_refs=list(images))


# ── the two properties, on every prompt ──────────────────────────────────────

@pytest.mark.parametrize("prompt", PROMPTS)
def test_every_span_points_at_exactly_the_words_it_quotes(prompt):
    for unit in ledger.prompt_units(prompt, inquiry_id=INQUIRY):
        start, end = unit.span
        assert prompt[start:end] == unit.exact_quote
        assert unit.exact_quote == unit.exact_quote.strip()


@pytest.mark.parametrize("prompt", PROMPTS)
def test_the_clauses_reassemble_into_the_prompt_byte_for_byte(prompt):
    """The loses-nothing property. Every character is inside one clause or is a separator."""
    units = ledger.prompt_units(prompt, inquiry_id=INQUIRY)
    assert ledger.reassemble(prompt, units) == prompt


@pytest.mark.parametrize("prompt", PROMPTS)
def test_no_two_clause_spans_overlap(prompt):
    spans = sorted(u.span for u in ledger.prompt_units(prompt, inquiry_id=INQUIRY))
    for (_, end), (next_start, _) in zip(spans, spans[1:]):
        assert end <= next_start


def test_the_awkward_prompt_separates_into_the_observations_it_contains():
    """The rehearsal prompt's shape: several distinct observations, no capitals, a double hyphen
    doing the work of a full stop. One unit for the whole thing would hand the dissector a
    paragraph and hand the audit one thing to cover."""
    units = ledger.prompt_units(AWKWARD, inquiry_id=INQUIRY)
    assert len(units) >= 4, [u.exact_quote for u in units]
    assert all(u.kind is SourceUnitKind.PROMPT_CLAUSE for u in units)
    assert all(u.is_user_authored for u in units)


def test_a_double_hyphen_is_a_boundary_because_writers_use_it_as_one():
    units = ledger.prompt_units("first thing entirely--second thing entirely", inquiry_id=INQUIRY)
    assert [u.exact_quote for u in units] == ["first thing entirely", "second thing entirely"]


def test_a_short_fragment_joins_the_previous_clause_rather_than_becoming_a_unit():
    """A three-word aside made into a unit is a unit the dissector can only mark remainder, which
    reads downstream as an epistemic limit rather than as a splitting artifact."""
    units = ledger.prompt_units("a full clause of real content here. yes.", inquiry_id=INQUIRY)
    assert len(units) == 1
    assert units[0].exact_quote.endswith("yes")


def test_a_prompt_of_only_punctuation_yields_no_units_rather_than_an_empty_one():
    assert ledger.prompt_units("!!!", inquiry_id=INQUIRY) == []


# ── reading blocks ───────────────────────────────────────────────────────────

def test_each_reading_block_becomes_one_unit_keeping_its_id_and_images():
    reading = a_reading(a_block("rb_a", "the first block", images=["img_1"]),
                        a_block("rb_b", "the second block", kind=ReadingBlockKind.COMPARISON))
    units = ledger.reading_units(reading, inquiry_id=INQUIRY)
    assert [u.source_ref for u in units] == ["rb_a", "rb_b"]
    assert [u.exact_quote for u in units] == ["the first block", "the second block"]
    assert units[0].image_refs == ["img_1"]
    assert units[1].block_kind == "comparison"
    assert all(u.span is None for u in units)
    assert not any(u.is_user_authored for u in units)


def test_the_theorists_summary_paragraph_is_not_a_source_unit():
    """Dissolving both the summary and the blocks it summarises produces atoms that duplicate each
    other with nothing saying they are the same content."""
    reading = a_reading(a_block("rb_a", "the first block"))
    units, _ = ledger.build("a prompt about something", reading, inquiry_id=INQUIRY)
    assert not any("summary paragraph" in u.exact_quote for u in units)


def test_an_empty_block_is_not_a_unit():
    reading = a_reading(a_block("rb_a", "   "), a_block("rb_b", "real content here"))
    assert [u.source_ref for u in ledger.reading_units(reading, inquiry_id=INQUIRY)] == ["rb_b"]


# ── the whole ledger ─────────────────────────────────────────────────────────

def test_the_ledger_holds_the_prompt_and_the_blocks_and_says_which_is_which():
    reading = a_reading(a_block("rb_a", "a block of reading prose"))
    units, notes = ledger.build(AWKWARD, reading, inquiry_id=INQUIRY)
    kinds = {u.kind for u in units}
    assert kinds == {SourceUnitKind.PROMPT_CLAUSE, SourceUnitKind.READING_BLOCK}
    assert notes == []
    assert len(ledger.user_unit_ids(units)) == len(
        [u for u in units if u.kind is SourceUnitKind.PROMPT_CLAUSE])


def test_a_repeated_block_becomes_one_unit_and_the_merge_is_reported():
    reading = a_reading(a_block("rb_a", "the same words"), a_block("rb_a", "the same words"))
    units, notes = ledger.build("a prompt about something", reading, inquiry_id=INQUIRY)
    assert len([u for u in units if u.kind is SourceUnitKind.READING_BLOCK]) == 1
    assert any("merged into one" in n for n in notes)


def test_a_missing_reading_is_reported_rather_than_left_to_be_noticed():
    units, notes = ledger.build("a prompt about something real", None, inquiry_id=INQUIRY)
    assert all(u.is_user_authored for u in units)
    assert any("no scene reading" in n for n in notes)


def test_a_reading_with_no_blocks_is_a_different_note_from_no_reading_at_all():
    units, notes = ledger.build("a prompt about something real", a_reading(), inquiry_id=INQUIRY)
    assert any("carried no blocks" in n for n in notes)
    assert not any("no scene reading" in n for n in notes)


def test_an_oversized_ledger_is_truncated_loudly_rather_than_quietly():
    """A silently truncated ledger would make the coverage audit pass by having less to cover."""
    reading = a_reading(*[a_block(f"rb_{i}", f"block number {i} with content")
                          for i in range(ledger.MAX_UNITS + 20)])
    units, notes = ledger.build("a prompt about something real", reading, inquiry_id=INQUIRY)
    assert len(units) == ledger.MAX_UNITS
    assert any("are kept and the rest are reported" in n for n in notes)


# ── determinism and identity ─────────────────────────────────────────────────

def test_building_the_same_ledger_twice_produces_the_same_ids():
    reading = a_reading(a_block("rb_a", "a block of reading prose"))
    first, _ = ledger.build(AWKWARD, reading, inquiry_id=INQUIRY)
    second, _ = ledger.build(AWKWARD, reading, inquiry_id=INQUIRY)
    assert [u.source_unit_id for u in first] == [u.source_unit_id for u in second]


def test_the_same_words_under_two_inquiries_are_two_units():
    reading = a_reading(a_block("rb_a", "a block of reading prose"))
    mine, _ = ledger.build(AWKWARD, reading, inquiry_id=INQUIRY)
    theirs, _ = ledger.build(AWKWARD, reading, inquiry_id="inq_000000000002")
    assert not {u.source_unit_id for u in mine} & {u.source_unit_id for u in theirs}


# ── what a model is shown ────────────────────────────────────────────────────

def test_the_dissector_is_never_shown_a_character_offset():
    """A model shown the offsets will echo them back, and an echoed offset is indistinguishable
    from a computed one once it is in the payload."""
    units, _ = ledger.build(AWKWARD, a_reading(a_block("rb_a", "prose")), inquiry_id=INQUIRY)
    for row in ledger.digest_for_prompt(units):
        assert "span" not in row and "start" not in row and "end" not in row


def test_the_digest_says_who_authored_every_unit():
    units, _ = ledger.build(AWKWARD, a_reading(a_block("rb_a", "prose")), inquiry_id=INQUIRY)
    authors = {row["author"] for row in ledger.digest_for_prompt(units)}
    assert authors == {"user", "scene_theorist"}


def test_the_ledger_module_reaches_no_model_and_no_clock():
    """Structural. The ledger is what every pass is audited against; a model in it would let one
    mind decide both what the sources were and whether it had covered them."""
    import pathlib
    source = pathlib.Path(ledger.__file__).read_text(encoding="utf-8")
    for token in ("groq", "llm_service", "openai", "requests", "datetime", "time.time",
                  "random"):
        assert token not in source, f"the ledger reaches {token!r}"
