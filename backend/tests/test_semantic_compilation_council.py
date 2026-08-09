"""
HARNESS-003A §5/§6 — the relation architect and the epistemic operationalizer.

The two passes downstream of the dissection, and the two ways they could quietly undo it: an
architect that flattens four distinct atoms into one comfortable sentence about how things compare,
and an operationalizer that lets a measurement close an interpretation.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from backend.schemas.inquiry import DemandKind
from backend.schemas.semantic_compilation import (AtomAuthor, AtomKind, ClaimKind, ClaimStatus,
                                                  ImageScope, ModelReceipt, PassOutcome,
                                                  ReadingBlock, ReadingBlockKind, SceneReading,
                                                  SourceType)
from backend.services.semantic_compilation import architect as A
from backend.services.semantic_compilation import dissector as D
from backend.services.semantic_compilation import ledger
from backend.services.semantic_compilation import operationalizer as O

INQUIRY = "inq_000000000001"
PROMPT = "the first thing has one quality and that makes it read a certain way. the second differs"


def a_ledger(*blocks):
    reading = SceneReading(text="the theorist's summary", blocks=list(blocks),
                           provenance=ModelReceipt(role="scene_theorist")) if blocks else None
    units, _ = ledger.build(PROMPT, reading, inquiry_id=INQUIRY)
    return units


def dissolved(units, kinds=("visual_quality", "causal_hypothesis", "comparison")):
    """Atoms over the ledger, one per unit, with the kinds a caller asks for."""
    atoms = [{"ref": f"a{i}", "text": f"atom {i}", "unit_kind": kinds[i % len(kinds)],
              "source_unit_ids": [u.source_unit_id]} for i, u in enumerate(units)]
    payload = {"atoms": atoms,
               "coverage": [{"source_unit_id": u.source_unit_id, "disposition": "represented_by",
                             "refs": [f"a{i}"]} for i, u in enumerate(units)]}
    return D.FrozenSemanticDissector([payload]).dissolve(units, prompt=PROMPT,
                                                         inquiry_id=INQUIRY)[0]


def assemble(payload, atoms=None, units=None):
    units = units if units is not None else a_ledger()
    atoms = atoms if atoms is not None else dissolved(units)
    return A.FrozenRelationArchitect(payload).assemble(atoms, units, inquiry_id=INQUIRY)


def claim_row(ref, text, atom, kind="attribute", **kw):
    row = {"ref": ref, "text": text, "kind": kind, "atom_ids": [atom.atom_id]}
    row.update(kw)
    return row


# ── the architect builds only from atoms ─────────────────────────────────────

def test_a_claim_names_the_atoms_it_was_built_from():
    units = a_ledger()
    atoms = dissolved(units)
    claims, _, _, _, receipt = assemble(
        {"claims": [claim_row("c1", "the thing has that quality", atoms[0])]}, atoms, units)
    assert receipt.outcome in (PassOutcome.COMPLETED, PassOutcome.THIN)
    assert claims[0].atom_refs == [atoms[0].atom_id]


def test_a_claims_source_pointers_are_derived_from_its_atoms_never_asked_for():
    """Asking would let a pass that had drifted from its atoms still produce a plausible anchor."""
    units = a_ledger(ReadingBlock(block_id="rb_a", kind=ReadingBlockKind.PART,
                                  text="a part is present", image_refs=["img_1"]))
    atoms = dissolved(units)
    block_atom = next(a for a in atoms if a.author is AtomAuthor.SEMANTIC_DISSECTOR)
    claims, _, _, _, _ = assemble(
        {"claims": [claim_row("c1", "a part is present", block_atom, kind="entity")]},
        atoms, units)
    pointer = claims[0].sources[0]
    assert pointer.source_type is SourceType.SCENE_READING
    assert pointer.source_id == "rb_a"
    assert pointer.text == "a part is present"
    assert "source" not in A.build_prompt(atoms, {u.source_unit_id: u for u in units}).lower() \
        or "source_id" not in A.build_prompt(atoms, {u.source_unit_id: u for u in units})


def test_a_claim_anchored_to_a_prompt_clause_carries_its_computed_span():
    units = a_ledger()
    atoms = dissolved(units)
    claims, _, _, _, _ = assemble({"claims": [claim_row("c1", "x", atoms[0])]}, atoms, units)
    pointer = claims[0].sources[0]
    assert pointer.source_type is SourceType.PROMPT
    assert PROMPT[pointer.span[0]:pointer.span[1]] == pointer.text


def test_a_claim_built_from_an_invented_atom_is_refused():
    units = a_ledger()
    atoms = dissolved(units)
    claims, _, refusals, _, _ = assemble(
        {"claims": [{"ref": "c1", "text": "invented", "kind": "entity",
                     "atom_ids": ["atm_nothing"]}]}, atoms, units)
    assert claims == []
    kinds = {r.kind.value for r in refusals}
    assert "dangling_reference" in kinds and "unanchored_claim" in kinds


def test_the_architect_is_shown_atoms_and_never_an_image_or_the_source_prose():
    units = a_ledger(ReadingBlock(block_id="rb_a", kind=ReadingBlockKind.PART,
                                  text="a long paragraph of theorist prose about the picture",
                                  image_refs=["img_1"]))
    atoms = dissolved(units)
    body = A.build_prompt(atoms, {u.source_unit_id: u for u in units})
    assert "http" not in body and "image_url" not in body
    assert "a long paragraph of theorist prose" not in body, \
        "the source prose is the thing this pass must not read"


def test_the_default_atom_to_claim_mapping_is_used_when_no_kind_is_given():
    units = a_ledger()
    atoms = dissolved(units, kinds=("visual_quality",))
    claims, _, _, _, _ = assemble(
        {"claims": [{"ref": "c1", "text": "x", "atom_ids": [atoms[0].atom_id]}]}, atoms, units)
    assert claims[0].claim_kind is ClaimKind.ATTRIBUTE


def test_departing_from_the_default_is_recorded_rather_than_refused_or_silent():
    """The default is a default; the architect may know better. What it may not do is depart from
    it invisibly."""
    units = a_ledger()
    atoms = dissolved(units, kinds=("visual_quality",))
    claims, _, refusals, notes, _ = assemble(
        {"claims": [claim_row("c1", "x", atoms[0], kind="interpretation")]}, atoms, units)
    assert claims[0].claim_kind is ClaimKind.INTERPRETATION
    assert refusals == []
    assert any("default to 'attribute'" in n for n in notes)


# ── the architect preserves distinctions ─────────────────────────────────────

def test_a_quality_its_effect_and_a_comparison_stay_three_claims():
    """The failure this pass is written against: four atoms becoming one comfortable sentence."""
    units = a_ledger()
    atoms = dissolved(units, kinds=("visual_quality", "causal_hypothesis", "comparison"))
    payload = {"claims": [
        claim_row("c1", "the thing has that quality", atoms[0], kind="attribute",
                  demand="measurable"),
        claim_row("c2", "the quality produces the effect", atoms[1], kind="causal_hypothesis"),
    ], "edges": [{"kind": "supports", "from": "c1", "to": "c2", "why": "the quality is the cause"}]}
    claims, edges, _, _, receipt = assemble(payload, atoms, units)
    assert {c.claim_kind for c in claims} == {ClaimKind.ATTRIBUTE, ClaimKind.CAUSAL_HYPOTHESIS}
    assert claims[0].epistemic_demand is DemandKind.MEASURABLE
    # The demand table does the separating: the effect may not be asked of an instrument.
    assert claims[1].epistemic_demand is DemandKind.INTERPRETIVE
    assert len(edges) == 1


def test_a_causal_hypothesis_asking_to_be_measured_is_corrected_downward_and_recorded():
    units = a_ledger()
    atoms = dissolved(units)
    claims, _, refusals, _, _ = assemble(
        {"claims": [claim_row("c1", "x causes y", atoms[0], kind="causal_hypothesis",
                              demand="measurable")]}, atoms, units)
    assert claims[0].epistemic_demand is DemandKind.INTERPRETIVE
    assert any(r.kind.value == "measured_status_claimed" for r in refusals)


def test_a_comparison_may_not_be_scoped_to_one_image():
    units = a_ledger()
    atoms = dissolved(units)
    claims, _, refusals, _, _ = assemble(
        {"claims": [claim_row("c1", "they differ", atoms[0], kind="comparison",
                              image_scope="one_image")]}, atoms, units)
    assert claims[0].image_scope is ImageScope.CORPUS
    assert any(r.kind.value == "image_scope_corrected" for r in refusals)


def test_a_claim_may_not_start_measured():
    units = a_ledger()
    atoms = dissolved(units)
    claims, _, refusals, _, _ = assemble(
        {"claims": [claim_row("c1", "x", atoms[0], status="measured")]}, atoms, units)
    assert claims[0].status is ClaimStatus.UNCERTAIN
    assert any(r.kind.value == "measured_status_claimed" for r in refusals)


def test_an_atom_no_claim_used_is_reported_rather_than_deleted():
    units = a_ledger()
    atoms = dissolved(units)
    claims, _, _, notes, _ = assemble({"claims": [claim_row("c1", "x", atoms[0])]}, atoms, units)
    assert A.orphaned_atoms(atoms, claims) == [a.atom_id for a in atoms[1:]]
    assert any("not built into any claim" in n for n in notes)


def test_an_inference_whose_parents_all_vanished_goes_with_them():
    units = a_ledger()
    atoms = dissolved(units)
    payload = {"claims": [
        {"ref": "c1", "text": "invented parent", "kind": "vibe", "atom_ids": [atoms[0].atom_id]},
        {"ref": "c2", "text": "follows from it", "kind": "interpretation", "inferred_from": ["c1"]},
    ]}
    claims, _, refusals, _, _ = assemble(payload, atoms, units)
    assert claims == []
    assert any(r.kind.value == "inference_without_parent" for r in refusals)


# ── the architect's outcomes ─────────────────────────────────────────────────

def test_relational_atoms_with_no_edge_drawn_is_thin_and_says_why():
    """`thin` is a judgement about what the atoms implied, not a threshold on the claim count."""
    units = a_ledger()
    atoms = dissolved(units, kinds=("comparison", "causal_hypothesis", "relation"))
    claims, edges, _, _, receipt = assemble(
        {"claims": [claim_row("c1", "x", a, kind="interpretation") for a in atoms],
         "edges": []}, atoms, units)
    assert edges == []
    assert receipt.outcome is PassOutcome.THIN
    assert "drew no edge" in receipt.detail


def test_no_atoms_at_all_is_empty_rather_than_thin():
    units = a_ledger()
    claims, _, _, notes, receipt = A.FrozenRelationArchitect({}).assemble(
        [], units, inquiry_id=INQUIRY)
    assert receipt.outcome is PassOutcome.EMPTY
    assert claims == []


def test_an_unavailable_architect_builds_nothing_and_says_nothing_was_attempted():
    units = a_ledger()
    atoms = dissolved(units)
    pass_ = A.RelationArchitect(client=None)
    pass_._client_resolved = True
    claims, _, refusals, _, receipt = pass_.assemble(atoms, units, inquiry_id=INQUIRY)
    assert receipt.outcome is PassOutcome.UNAVAILABLE
    assert claims == []
    assert any(r.kind.value == "pass_unavailable" for r in refusals)


# ── the operationalizer ──────────────────────────────────────────────────────

def a_graph(kind="attribute", demand="measurable"):
    units = a_ledger()
    atoms = dissolved(units)
    claims, edges, _, _, _ = assemble(
        {"claims": [claim_row("c1", "the thing has that quality", atoms[0], kind=kind,
                              demand=demand, subject="the thing")]}, atoms, units)
    return claims, edges


def observable_row(claim, **kw):
    row = {"ref": "o1", "claim": claim.claim_id, "kind": "extent_of", "targets": ["the thing"],
           "capability_classes": ["extent"], "ground_forms": ["region"],
           "success_when": "one region is returned"}
    row.update(kw)
    return row


def operationalize(payload, claims=None, edges=None):
    if claims is None:
        claims, edges = a_graph()
    return O.FrozenEpistemicOperationalizer(payload).operationalize(
        claims, edges or [], inquiry_id=INQUIRY)


def test_an_observable_requests_a_capability_class_and_names_no_tool():
    claims, edges = a_graph()
    obs, _, rem, _, _, receipt = operationalize(
        {"observables": [observable_row(claims[0])],
         "semantic_remainder": [{"term": "how it reads", "why": "no instrument returns a "
                                 "perception"}]}, claims, edges)
    assert receipt.outcome is PassOutcome.COMPLETED
    assert [c.value for c in obs[0].capability_classes] == ["extent"]
    assert rem[0].term == "how it reads"


def test_an_observable_serving_an_interpretation_must_say_what_stays_interpretive():
    """A measurement contributes to an interpretation; it does not exhaust it. An interpretation
    with a satisfied observable and no residue reads downstream as a settled question."""
    claims, edges = a_graph(kind="interpretation", demand="interpretive")
    obs, _, _, refusals, _, _ = operationalize(
        {"observables": [observable_row(claims[0], remains_interpretive="")]}, claims, edges)
    assert obs == []
    assert any(r.kind.value == "remainder_claimed_measurable" for r in refusals)


def test_the_same_observable_with_a_stated_residue_is_accepted():
    claims, edges = a_graph(kind="interpretation", demand="interpretive")
    obs, _, _, _, _, _ = operationalize(
        {"observables": [observable_row(claims[0],
                                        remains_interpretive="whether it reads that way")],
         "semantic_remainder": [{"term": "how it reads", "why": "no instrument"}]}, claims, edges)
    assert obs[0].remains_interpretive == "whether it reads that way"


def test_a_sourced_claim_routed_to_an_image_capability_is_refused():
    claims, edges = a_graph(kind="historical_or_sourced", demand="sourced")
    obs, _, _, refusals, _, _ = operationalize(
        {"observables": [observable_row(claims[0])]}, claims, edges)
    assert obs == []
    assert any(r.kind.value == "sourced_claim_asked_of_an_organ" for r in refusals)


def test_a_fork_with_one_branch_is_dropped_because_it_trains_people_to_click_through():
    claims, edges = a_graph()
    _, decisions, _, _, notes, _ = operationalize(
        {"observables": [observable_row(claims[0])],
         "decisions": [{"kind": "choose_operationalization", "question": "which?",
                        "why_now": "it changes the cost", "affects": [claims[0].claim_id],
                        "options": [{"label": "only one"}]}],
         "semantic_remainder": [{"term": "t", "why": "w"}]}, claims, edges)
    assert decisions == []
    assert any("trains a person to click through" in n for n in notes)


def test_a_fork_with_two_real_branches_and_a_consequence_is_raised():
    claims, edges = a_graph()
    _, decisions, _, _, _, _ = operationalize(
        {"observables": [observable_row(claims[0])],
         "decisions": [{"kind": "choose_operationalization",
                        "question": "measure it whole, or measure the parts and count them?",
                        "why_now": "the second costs more and tests the premise",
                        "affects": [claims[0].claim_id],
                        "options": [{"label": "whole", "consequence": "one region, quickly"},
                                    {"label": "parts", "consequence": "several regions, more cost"}]}],
         "semantic_remainder": [{"term": "t", "why": "w"}]}, claims, edges)
    assert len(decisions) == 1
    assert decisions[0].affected_refs == [claims[0].claim_id]
    assert len(decisions[0].options) == 2


def test_a_remainder_term_that_is_also_measurable_is_refused():
    claims, edges = a_graph()
    _, _, remainder, refusals, _, _ = operationalize(
        {"observables": [observable_row(claims[0])],
         "semantic_remainder": [{"term": "the thing", "why": "contradiction"}]}, claims, edges)
    assert remainder == []
    assert any(r.kind.value == "remainder_claimed_measurable" for r in refusals)


def test_measurable_claims_with_no_observable_is_thin_and_nothing_is_invented():
    """Reported rather than padded. Manufacturing an observable to avoid `thin` is the one thing
    the directive names as forbidden here."""
    claims, edges = a_graph()
    obs, _, _, _, _, receipt = operationalize(
        {"observables": [], "semantic_remainder": [{"term": "t", "why": "w"}]}, claims, edges)
    assert obs == []
    assert receipt.outcome is PassOutcome.THIN
    assert "ask to be measured and no observable" in receipt.detail


def test_an_interpretive_graph_with_no_remainder_is_thin():
    claims, edges = a_graph(kind="interpretation", demand="interpretive")
    _, _, _, _, _, receipt = operationalize(
        {"observables": [observable_row(claims[0], remains_interpretive="a reading")],
         "semantic_remainder": []}, claims, edges)
    assert receipt.outcome is PassOutcome.THIN
    assert "no semantic remainder" in receipt.detail


def test_an_interpretive_graph_with_a_remainder_and_no_observable_is_complete():
    """A wholly interpretive graph with nothing to measure is a correct answer, not a thin one —
    which is why the outcome reads the demands rather than counting observables."""
    claims, edges = a_graph(kind="interpretation", demand="interpretive")
    _, _, _, _, _, receipt = operationalize(
        {"observables": [],
         "semantic_remainder": [{"term": "how it reads", "why": "no instrument"}]}, claims, edges)
    assert receipt.outcome is PassOutcome.COMPLETED


def test_the_operationalizer_is_shown_the_graph_and_never_an_image():
    claims, edges = a_graph()
    body = O.build_prompt(claims, edges)
    assert "http" not in body and "image_url" not in body
    assert claims[0].claim_id in body


#: Concrete instruments. A pass that could reach one would turn "nothing can do this" into a
#: planning error rather than a visible gap.
#: Deliberately specific. `organ` alone would match `sourced_claim_asked_of_an_organ`, which is a
#: REFUSAL KIND — the name of the rule that keeps a sourced claim away from an instrument. A scan
#: that flagged the guard as the violation would be the second-worst outcome after no scan at all.
_INSTRUMENTS = ("concept_segment", "sam3", "dinov2", "segmentation_service", "actuator",
                "agent_organ", "world_action", "director")


def _imported_names(module) -> set:
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def test_neither_pass_can_reach_a_tool_an_actuator_or_an_organ():
    """Matched against IMPORTS and attribute access, never prose: the operationalizer's own prompt
    forbids naming an actuator, and a scan that counted that would force the instruction out of the
    file whose whole job is to carry it."""
    for module in (A, O):
        names = _imported_names(module)
        for name in names:
            for token in _INSTRUMENTS:
                assert token not in name.lower(), f"{module.__name__} reaches {name!r}"


def test_that_instrument_scan_can_fail(tmp_path):
    decoy = tmp_path / "decoy.py"
    decoy.write_text("from backend.services import segmentation_service\n", encoding="utf-8")
    tree = ast.parse(decoy.read_text(encoding="utf-8"))
    names = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert any(t in n.lower() for n in names for t in _INSTRUMENTS)


def test_the_operationalizers_prompt_forbids_naming_an_instrument():
    """The other polarity, and the one prose is the right place for. The rule has to be IN the
    prompt, because the model is the thing that would otherwise name a tool."""
    assert "never name a model, a tool, an actuator or an organ" in O.SYSTEM_PROMPT.lower()
    assert "capability class, never a tool" in O.SYSTEM_PROMPT.lower()


def test_the_only_capability_vocabulary_either_pass_can_emit_is_the_contracts():
    from backend.services.semantic_compilation import contracts
    from backend.schemas.semantic_compilation import CapabilityClass
    assert {c.value for c in CapabilityClass} == set(contracts.closed_set("capability_classes"))


def test_neither_pass_retries():
    for module in (A, O):
        tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
        assert not [n for n in ast.walk(tree) if isinstance(n, ast.While)
                    and not _is_fixpoint(n)], f"{module.__name__} has a retry loop"


def _is_fixpoint(node) -> bool:
    """The architect's parent resolution is a fixpoint, not a retry: it makes no call."""
    return not any(isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "invoke"
                   for n in ast.walk(node))
