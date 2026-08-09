"""
HARNESS-003A §4 — the dissector accounts for everything it was given, or says it did not.

The pass exists because the rehearsal's compiler turned an abundant reading into a barren graph and
nothing could say what had happened to the prose. So every test here is a way that could happen
again: a unit nobody mentions, an atom anchored to a unit that does not exist, a disposition that
covers nothing, or a truncated batch reported as a short success.
"""
from __future__ import annotations

import pathlib

import pytest

from backend.schemas.semantic_compilation import (AtomAuthor, AtomKind, DispositionKind,
                                                  ModelReceipt, PassOutcome, ReadingBlock,
                                                  ReadingBlockKind, SceneReading)
from backend.services.semantic_compilation import dissector as D
from backend.services.semantic_compilation import ledger

INQUIRY = "inq_000000000001"
PROMPT = "the first thing has one quality and that makes it read a certain way. the second differs"


def a_ledger(prompt=PROMPT, *blocks):
    reading = SceneReading(text="the theorist's summary", blocks=list(blocks),
                           provenance=ModelReceipt(role="scene_theorist")) if blocks else None
    units, _ = ledger.build(prompt, reading, inquiry_id=INQUIRY)
    return units


def a_block(block_id="rb_a", text="a part is present", images=("img_1",)):
    return ReadingBlock(block_id=block_id, kind=ReadingBlockKind.PART, text=text,
                        image_refs=list(images))


def atom_row(ref, text, unit, kind="visual_quality", **kw):
    row = {"ref": ref, "text": text, "unit_kind": kind,
           "source_unit_ids": [unit.source_unit_id], "quotes": [unit.exact_quote]}
    row.update(kw)
    return row


def cover(unit, refs, disposition="represented_by", reason=""):
    return {"source_unit_id": unit.source_unit_id, "disposition": disposition,
            "refs": list(refs), "reason": reason}


def dissolve(payloads, units=None, prompt=PROMPT):
    units = units if units is not None else a_ledger()
    pass_ = D.FrozenSemanticDissector(payloads)
    atoms, coverage, refusals, receipt = pass_.dissolve(units, prompt=prompt, inquiry_id=INQUIRY)
    return units, atoms, coverage, refusals, receipt


def full_payload(units):
    atoms = [atom_row(f"a{i}", f"atom for unit {i}", u) for i, u in enumerate(units)]
    return {"atoms": atoms,
            "coverage": [cover(u, [f"a{i}"]) for i, u in enumerate(units)]}


# ── the happy path, and what it must contain ─────────────────────────────────

def test_a_complete_dissection_covers_every_unit_and_says_so():
    units, atoms, coverage, refusals, receipt = dissolve([full_payload(a_ledger())])
    assert receipt.outcome is PassOutcome.COMPLETED
    assert {c.source_unit_id for c in coverage} == {u.source_unit_id for u in units}
    assert len(atoms) == len(units)
    assert refusals == []
    assert receipt.outputs == len(atoms)


def test_one_source_unit_becomes_several_atoms_without_being_summarised():
    """The pass's whole job. A unit saying two things becomes two atoms, and only one of them could
    ever be observed."""
    units = a_ledger()
    payload = {"atoms": [
        atom_row("a1", "the first thing has one quality", units[0], kind="visual_quality"),
        atom_row("a2", "that quality makes it read a certain way", units[0],
                 kind="causal_hypothesis"),
        atom_row("a3", "the second differs", units[1], kind="comparison"),
    ], "coverage": [cover(units[0], ["a1", "a2"]), cover(units[1], ["a3"])]}
    _, atoms, coverage, _, receipt = dissolve([payload], units)
    assert receipt.outcome is PassOutcome.COMPLETED
    assert {a.unit_kind for a in atoms} == {AtomKind.VISUAL_QUALITY, AtomKind.CAUSAL_HYPOTHESIS,
                                            AtomKind.COMPARISON}
    assert len(coverage[0].refs) == 2


# ── authorship is derived, never taken ───────────────────────────────────────

def test_an_atom_from_the_persons_clause_is_theirs_whatever_the_model_says():
    units = a_ledger()
    payload = {"atoms": [atom_row("a1", "their hypothesis", units[0],
                                  kind="causal_hypothesis", author="semantic_dissector")],
               "coverage": [cover(units[0], ["a1"]),
                            cover(units[1], [], "semantic_remainder", "nothing captured it")]}
    _, atoms, _, refusals, _ = dissolve([payload], units)
    assert atoms[0].author is AtomAuthor.USER
    assert any(r.kind.value == "user_statement_reattributed" for r in refusals)


def test_an_atom_from_a_reading_block_is_the_dissectors():
    units = a_ledger(PROMPT, a_block())
    block = units[-1]
    payload = {"atoms": [atom_row("a1", "a part is present", block, kind="entity")],
               "coverage": [cover(units[0], [], "semantic_remainder", "not dissolved"),
                            cover(units[1], [], "semantic_remainder", "not dissolved"),
                            cover(block, ["a1"])]}
    _, atoms, _, _, _ = dissolve([payload], units)
    assert atoms[0].author is AtomAuthor.SEMANTIC_DISSECTOR
    assert atoms[0].image_refs == ["img_1"], "an atom inherits its unit's images"


def test_an_atom_spanning_the_person_and_the_reading_is_the_dissectors():
    units = a_ledger(PROMPT, a_block())
    payload = {"atoms": [{"ref": "a1", "text": "they correspond", "unit_kind": "comparison",
                          "source_unit_ids": [units[0].source_unit_id,
                                              units[-1].source_unit_id]}],
               "coverage": [cover(units[0], ["a1"]),
                            cover(units[1], [], "semantic_remainder", "nothing captured it"),
                            cover(units[-1], ["a1"])]}
    _, atoms, _, _, _ = dissolve([payload], units)
    assert atoms[0].author is AtomAuthor.SEMANTIC_DISSECTOR


# ── anchors ──────────────────────────────────────────────────────────────────

def test_an_atom_anchored_to_an_invented_unit_is_refused_and_dropped():
    units = a_ledger()
    payload = {"atoms": [{"ref": "a1", "text": "invented", "unit_kind": "entity",
                          "source_unit_ids": ["su_nothing"]}],
               "coverage": [cover(u, [], "semantic_remainder", "nothing captured it")
                            for u in units]}
    _, atoms, _, refusals, _ = dissolve([payload], units)
    assert atoms == []
    kinds = {r.kind.value for r in refusals}
    assert "atom_source_not_in_ledger" in kinds and "unanchored_atom" in kinds


def test_an_atom_keeping_one_good_anchor_survives_and_the_bad_one_is_refused():
    units = a_ledger()
    payload = {"atoms": [{"ref": "a1", "text": "half anchored", "unit_kind": "entity",
                          "source_unit_ids": [units[0].source_unit_id, "su_nothing"]}],
               "coverage": [cover(units[0], ["a1"]),
                            cover(units[1], [], "refused", "not reached")]}
    _, atoms, _, refusals, _ = dissolve([payload], units)
    assert atoms[0].source_unit_ids == [units[0].source_unit_id]
    assert any(r.kind.value == "atom_source_not_in_ledger" for r in refusals)


def test_an_unknown_atom_kind_is_refused_by_name_rather_than_filed_under_unknown():
    units = a_ledger()
    payload = {"atoms": [atom_row("a1", "x", units[0], kind="vibe")],
               "coverage": [cover(u, [], "refused", "not reached") for u in units]}
    _, atoms, _, refusals, _ = dissolve([payload], units)
    assert atoms == []
    assert [r.what for r in refusals if r.kind.value == "unknown_atom_kind"] == ["vibe"]


def test_a_paraphrased_quote_is_kept_and_marked_rather_than_deleted():
    """Deleting it would hide that the dissector paraphrased; keeping it unmarked would let a UI
    highlight words the source does not contain."""
    units = a_ledger()
    payload = {"atoms": [atom_row("a1", "x", units[0], quotes=["words that are not in the unit"])],
               "coverage": [cover(units[0], ["a1"]),
                            cover(units[1], [], "refused", "not reached")]}
    _, atoms, _, _, _ = dissolve([payload], units)
    assert atoms[0].quotes == ["words that are not in the unit"]
    assert atoms[0].provenance["quotes_not_found"] == ["words that are not in the unit"]


# ── coverage ─────────────────────────────────────────────────────────────────

def test_a_unit_the_dissector_never_mentions_is_coverage_failed_not_remainder():
    """Silence is an omission. Remainder is a judgement with a reason, and calling one the other
    reports a pass that failed as an epistemic limit — the most flattering possible mistake."""
    units = a_ledger()
    payload = {"atoms": [atom_row("a1", "x", units[0])], "coverage": [cover(units[0], ["a1"])]}
    _, _, coverage, refusals, receipt = dissolve([payload], units)
    assert receipt.outcome is PassOutcome.COVERAGE_FAILED
    assert "1 of 2 source unit(s) received no disposition" in receipt.detail
    assert [r.what for r in refusals if r.kind.value == "source_unit_uncovered"] == \
           [units[1].source_unit_id]
    assert {c.source_unit_id for c in coverage} == {units[0].source_unit_id}


def test_represented_by_atoms_that_were_all_refused_leaves_the_unit_uncovered():
    """One unit's atoms were all refused; another's survived. The first is uncovered rather than
    quietly represented by nothing."""
    units = a_ledger()
    payload = {"atoms": [atom_row("a1", "x", units[0], kind="vibe"),
                         atom_row("a2", "y", units[1])],
               "coverage": [cover(units[0], ["a1"]), cover(units[1], ["a2"])]}
    _, atoms, coverage, refusals, receipt = dissolve([payload], units)
    assert len(atoms) == 1
    assert receipt.outcome is PassOutcome.COVERAGE_FAILED
    assert units[0].source_unit_id not in {c.source_unit_id for c in coverage}
    assert any("wearing the covered case's name" in r.why for r in refusals)


def test_a_dissection_where_no_atom_survives_is_empty_rather_than_coverage_failed():
    """`empty` is the more fundamental description and comes first: `coverage_failed` implies some
    coverage exists, and understating "nothing survived" would send a reader to the wrong place."""
    units = a_ledger()
    payload = {"atoms": [atom_row("a1", "x", units[0], kind="vibe")],
               "coverage": [cover(units[0], ["a1"]),
                            cover(units[1], [], "refused", "not reached")]}
    _, atoms, _, _, receipt = dissolve([payload], units)
    assert atoms == []
    assert receipt.outcome is PassOutcome.EMPTY


def test_a_unit_disposed_of_twice_keeps_the_first_and_records_the_second():
    units = a_ledger()
    payload = {"atoms": [atom_row("a1", "x", units[0])],
               "coverage": [cover(units[0], ["a1"]),
                            cover(units[0], [], "semantic_remainder", "also this"),
                            cover(units[1], [], "refused", "not reached")]}
    _, _, coverage, refusals, receipt = dissolve([payload], units)
    assert receipt.outcome is PassOutcome.COMPLETED
    assert len([c for c in coverage if c.source_unit_id == units[0].source_unit_id]) == 1
    assert coverage[0].disposition is DispositionKind.REPRESENTED_BY
    assert any(r.kind.value == "source_unit_double_covered" for r in refusals)


def test_a_duplicate_pointing_at_itself_is_refused():
    units = a_ledger()
    payload = {"atoms": [atom_row("a1", "x", units[1])],
               "coverage": [cover(units[0], [units[0].source_unit_id], "duplicate_of"),
                            cover(units[1], ["a1"])]}
    _, _, _, refusals, receipt = dissolve([payload], units)
    assert receipt.outcome is PassOutcome.COVERAGE_FAILED
    assert any(r.kind.value == "duplicate_points_at_itself" for r in refusals)


def test_a_real_duplicate_is_accepted_and_names_its_original():
    units = a_ledger()
    payload = {"atoms": [atom_row("a1", "x", units[1])],
               "coverage": [cover(units[0], [units[1].source_unit_id], "duplicate_of"),
                            cover(units[1], ["a1"])]}
    _, _, coverage, _, receipt = dissolve([payload], units)
    assert receipt.outcome is PassOutcome.COMPLETED
    duplicate = next(c for c in coverage if c.disposition is DispositionKind.DUPLICATE_OF)
    assert duplicate.refs == [units[1].source_unit_id]


def test_remainder_with_no_reason_gets_one_saying_none_was_given():
    units = a_ledger()
    payload = {"atoms": [atom_row("a1", "x", units[0])],
               "coverage": [cover(units[0], ["a1"]),
                            cover(units[1], [], "semantic_remainder", "")]}
    _, _, coverage, _, _ = dissolve([payload], units)
    remainder = next(c for c in coverage if c.disposition is DispositionKind.SEMANTIC_REMAINDER)
    assert "gave no reason" in remainder.reason


def test_an_unknown_disposition_leaves_the_unit_uncovered_rather_than_guessing():
    units = a_ledger()
    payload = {"atoms": [atom_row("a1", "x", units[0])],
               "coverage": [cover(units[0], ["a1"]), cover(units[1], [], "handled", "")]}
    _, _, _, refusals, receipt = dissolve([payload], units)
    assert receipt.outcome is PassOutcome.COVERAGE_FAILED
    assert any(r.kind.value == "unknown_disposition" for r in refusals)


# ── the outcome vocabulary ───────────────────────────────────────────────────

def test_an_unavailable_dissector_produces_no_atoms_and_says_nothing_was_attempted():
    units = a_ledger()
    pass_ = D.SemanticDissector(client=None)
    pass_._client_resolved = True
    atoms, coverage, refusals, receipt = pass_.dissolve(units, prompt=PROMPT, inquiry_id=INQUIRY)
    assert receipt.outcome is PassOutcome.UNAVAILABLE
    assert atoms == [] and coverage == []
    assert any(r.kind.value == "pass_unavailable" for r in refusals)
    assert any("nothing rule-based was substituted" in r.why.lower() for r in refusals)


def test_a_dissector_that_returns_nothing_usable_is_empty_rather_than_coverage_failed():
    units = a_ledger()
    _, atoms, _, _, receipt = dissolve([{"atoms": [], "coverage": []}], units)
    assert atoms == []
    assert receipt.outcome is PassOutcome.EMPTY


def test_a_truncated_batch_beats_coverage_failed_because_it_explains_it():
    """An uncovered unit under a length stop is explained by the length stop. Reporting
    `coverage_failed` would send a reader looking for a prompt bug."""
    units = a_ledger()

    class _Truncated(D.FrozenSemanticDissector):
        def invoke(self, user_prompt, *, inquiry_id, attempt=1, inputs=0):
            result = super().invoke(user_prompt, inquiry_id=inquiry_id, attempt=attempt,
                                    inputs=inputs)
            return result.__class__(result.payload,
                                    result.receipt.model_copy(update={
                                        "outcome": PassOutcome.TRUNCATED,
                                        "finish_reasons": ["length"]}),
                                    result.refusals)

    payload = {"atoms": [atom_row("a1", "x", units[0])], "coverage": [cover(units[0], ["a1"])]}
    _, _, _, receipt = _Truncated([payload]).dissolve(units, prompt=PROMPT, inquiry_id=INQUIRY)
    assert receipt.outcome is PassOutcome.TRUNCATED
    assert receipt.truncated is True
    assert "uncovered as a result" in receipt.detail


# ── batching, budget and no silent retry ─────────────────────────────────────

def test_the_ledger_is_dissolved_in_bounded_batches():
    """A request that cannot overflow is one that cannot be truncated into a plausible prefix."""
    reading_blocks = [a_block(f"rb_{i}", f"block number {i} of prose") for i in range(14)]
    units = a_ledger(PROMPT, *reading_blocks)
    pass_ = D.FrozenSemanticDissector([full_payload(b) for b in
                                       _batches(units, D.DEFAULT_BUDGET.batch_size)])
    _, _, _, receipt = pass_.dissolve(units, prompt=PROMPT, inquiry_id=INQUIRY), None, None, None
    assert pass_.calls == len(_batches(units, D.DEFAULT_BUDGET.batch_size))
    assert pass_.calls > 1


def _batches(items, size):
    return [list(items[i:i + size]) for i in range(0, len(items), size)]


def test_the_dissector_declares_a_completion_budget_rather_than_taking_the_default():
    assert D.DEFAULT_BUDGET.max_completion_tokens > 0
    assert D.SemanticDissector().budget is D.DEFAULT_BUDGET


def test_nothing_in_this_pass_retries():
    """A retry loop hides a marginal prompt behind a good average: the pass that needed three
    attempts and the one that worked first time produce identical output.

    Checked on the AST rather than the text: both modules DISCUSS retrying in their docstrings, and
    a scan that counted prose would force the explanation out of the file that most needs it.
    """
    import ast
    from backend.services.semantic_compilation import passes
    for module in (D, passes):
        tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.While):
                assert False, f"{module.__name__} contains a while loop"
            if isinstance(node, ast.For) and isinstance(node.iter, ast.Call) \
                    and getattr(node.iter.func, "id", "") == "range":
                assert False, f"{module.__name__} loops over a range — check it is not a retry"


def test_that_retry_scan_can_fail(tmp_path):
    """The negative control. A scan that ignores prose could also be ignoring everything."""
    import ast
    decoy = tmp_path / "decoy.py"
    decoy.write_text("for attempt in range(3):\n    pass\n", encoding="utf-8")
    tree = ast.parse(decoy.read_text(encoding="utf-8"))
    assert any(isinstance(n, ast.For) and getattr(getattr(n.iter, "func", None), "id", "") == "range"
               for n in ast.walk(tree))


def test_a_frozen_payload_list_that_runs_out_is_empty_rather_than_repeated():
    """Serving the last payload again would make a batch look answered by a response written for
    different inputs."""
    reading_blocks = [a_block(f"rb_{i}", f"block number {i} of prose") for i in range(14)]
    units = a_ledger(PROMPT, *reading_blocks)
    pass_ = D.FrozenSemanticDissector([full_payload(units[:2])])
    _, _, _, receipt = pass_.dissolve(units, prompt=PROMPT, inquiry_id=INQUIRY)
    assert receipt.outcome is PassOutcome.COVERAGE_FAILED


# ── determinism and boundaries ───────────────────────────────────────────────

def test_dissolving_the_same_payload_twice_produces_the_same_ids():
    units = a_ledger()
    first = dissolve([full_payload(units)], units)[1]
    second = dissolve([full_payload(units)], units)[1]
    assert [a.atom_id for a in first] == [a.atom_id for a in second]


def test_a_geometry_key_anywhere_in_the_payload_is_refused_before_anything_is_built():
    units = a_ledger()
    payload = full_payload(units)
    payload["atoms"][0]["bbox"] = [0, 0, 1, 1]
    _, _, _, refusals, _ = dissolve([payload], units)
    assert any(r.kind.value == "geometry_in_a_reading" and "bbox" in r.what for r in refusals)


def test_the_dissector_is_never_handed_an_image():
    """One further remove from the pixels than the theorist. An atom anchored to a unit that does
    not contain it is the failure that follows from looking."""
    units = a_ledger(PROMPT, a_block())
    body = D.build_prompt(units, prompt=PROMPT, batch=units)
    assert "image_url" not in body and "http" not in body
    assert "img_1" in body, "the image REFS are shown; the images are not"


def test_the_prompt_is_shown_whole_as_context_and_cannot_be_anchored_to():
    units = a_ledger()
    body = D.build_prompt(units, prompt=PROMPT, batch=units[:1])
    assert PROMPT in body
    assert "You may not anchor an atom to this" in body
    assert units[1].source_unit_id not in body, "a unit outside the batch carries no id"


# ── representation is derived from the anchors, not restated ─────────────────

def test_a_unit_with_an_atom_is_represented_without_the_model_saying_so():
    """FOUND BY THE LIVE RUN. Asking the model to restate `represented_by` for every unit made it
    spend its completion budget on ids it had already written on each atom: five of six batches ran
    out mid-`coverage`, so 121 real atoms arrived with zero dispositions and the audit reported the
    whole ledger uncovered.

    Deriving it is also STRONGER. Whether a unit has an atom is a fact about the output; a restated
    disposition is an opinion about it, and only the opinion can disagree with the anchors.
    """
    units = a_ledger()
    payload = {"atoms": [atom_row("a1", "x", units[0]), atom_row("a2", "y", units[1])],
               "coverage": []}
    _, atoms, coverage, refusals, receipt = dissolve([payload], units)
    assert receipt.outcome is PassOutcome.COMPLETED
    assert {c.source_unit_id for c in coverage} == {u.source_unit_id for u in units}
    assert all(c.disposition is DispositionKind.REPRESENTED_BY for c in coverage)
    assert all("derived from the atoms" in c.reason for c in coverage)
    assert refusals == []


def test_the_model_still_says_what_happened_to_a_unit_it_produced_no_atom_for():
    """The half that cannot be derived. A unit with no atom is duplicate, remainder or refused, and
    only the dissector can say which."""
    units = a_ledger()
    payload = {"atoms": [atom_row("a1", "x", units[0])],
               "coverage": [cover(units[1], [], "semantic_remainder", "nothing captured it")]}
    _, _, coverage, _, receipt = dissolve([payload], units)
    assert receipt.outcome is PassOutcome.COMPLETED
    kinds = {c.source_unit_id: c.disposition for c in coverage}
    assert kinds[units[0].source_unit_id] is DispositionKind.REPRESENTED_BY
    assert kinds[units[1].source_unit_id] is DispositionKind.SEMANTIC_REMAINDER


def test_atoms_beat_a_contradicting_disposition_and_the_contradiction_is_recorded():
    """A unit called remainder that also has an atom is the dissector disagreeing with itself. The
    atoms are a fact about the output and the disposition is an opinion about it."""
    units = a_ledger()
    payload = {"atoms": [atom_row("a1", "x", units[0]), atom_row("a2", "y", units[1])],
               "coverage": [cover(units[0], [], "semantic_remainder", "nothing captured it")]}
    _, _, coverage, refusals, _ = dissolve([payload], units)
    first = next(c for c in coverage if c.source_unit_id == units[0].source_unit_id)
    assert first.disposition is DispositionKind.REPRESENTED_BY
    assert any(r.kind.value == "source_unit_double_covered" and "the atoms win" in r.why
               for r in refusals)


def test_the_prompt_asks_only_for_the_dispositions_that_cannot_be_derived():
    units = a_ledger()
    body = D.build_prompt(units, prompt=PROMPT, batch=units)
    assert "any you emit no atom for" in body
    assert "represented_by" not in body.split("Return JSON")[1], \
        "the model is no longer asked to restate what the anchors already say"
    assert "needs no entry" in D.SYSTEM_PROMPT
    assert "represented_by" not in D.SYSTEM_PROMPT
