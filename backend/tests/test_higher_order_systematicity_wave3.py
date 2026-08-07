"""
WAVE3 — higher-order systematicity, and the proof that its judge is out of its reach.

The measurement lives in `scripts/higher_order_systematicity.py` (Mongo, 129,564 pairs, a 25-minute
adjacency sweep). What belongs here is the machinery and — above all — **the externality of the
criterion**, because that is the claim everything else rests on and it is the one that has already
failed once in this project's history.

  1. **the ancestor chain** — bounded, cycle-guarded, riding on the skeleton so higher-order
     structure is readable from two skeletons with no new argument and no call-site change.
  2. **the higher-order term** — the same component arithmetic one level up, blended by a weight
     that is off by default.
  3. **THE SCAN.** `structure_map` must not be able to consult the criterion it is judged by. This
     is asserted by reading the module's imports and its text, not by intention.

Why the scan matters more than it looks: #155 judged a gate with a criterion built from the same
three numbers and rated it **+84.5**; against an external criterion the same gate scored **−23.5**,
backwards. And the criterion #155/#156 used calls `structure_map` one level up — external in its
inputs, not in its functional form. This lane's criterion is measured by a different organ and
never touches the scoring function; the scan is what keeps that true.
"""
import ast
import pathlib

import pytest

from backend.services import structure_map as sm

MODULE = pathlib.Path(sm.__file__)


def skeleton(region_id="r", *, depth=1, siblings=0, descendants=0, parent="p", ancestors=()):
    return {"region_id": region_id, "relation": sm.RELATION_NESTED_WITHIN, "parent_id": parent,
            "depth": depth, "sibling_count": siblings, "descendant_count": descendants,
            "has_relation": bool(parent), "sibling_ids": [], "descendant_ids": [],
            "ancestors": list(ancestors), "region_count": 8}


def rung(region_id, *, depth=1, siblings=0, descendants=0, parent=""):
    return {"region_id": region_id, "parent_id": parent, "depth": depth,
            "sibling_count": siblings, "descendant_count": descendants}


def nesting(*pairs):
    """`measurements` in the organ's shape, tightest-first via `scale_ratio`."""
    return [{"inner_region_id": inner, "outer_region_id": outer, "scale_ratio": ratio}
            for inner, outer, ratio in pairs]


# ── 1. the ancestor chain ────────────────────────────────────────────────────────────────────

def test_the_skeleton_carries_the_containment_chain_above_it():
    """Riding on the skeleton is what lets `systematicity` read higher-order structure without a
    second argument — the kernel keeps handing over two skeletons exactly as it always did."""
    regions = [{"id": r} for r in ("part", "whole", "frame")]
    measurements = nesting(("part", "whole", 0.6), ("part", "frame", 0.2),
                           ("whole", "frame", 0.5))
    skel = sm.relational_structure(regions, "part", measurements=measurements)
    assert [a["region_id"] for a in skel["ancestors"]] == ["whole", "frame"]
    assert skel["ancestors"][0]["descendant_count"] == 1     # whole holds part
    assert skel["ancestors"][1]["descendant_count"] == 2     # frame holds part and whole


def test_the_chain_is_bounded():
    """The third or fourth container of anything in this corpus is the frame, and every frame maps
    to every other frame — an agreement that says nothing and would dominate a deep average."""
    ids = [f"r{i}" for i in range(8)]
    regions = [{"id": r} for r in ids]
    measurements = nesting(*[(ids[i], ids[i + 1], 0.5) for i in range(len(ids) - 1)])
    skel = sm.relational_structure(regions, "r0", measurements=measurements)
    assert len(skel["ancestors"]) == sm.MAX_HIGHER_ORDER_DEPTH == 2


def test_a_containment_cycle_terminates_the_chain_rather_than_looping():
    """The organ should never emit A-in-B and B-in-A, and a guard that costs one set lookup is
    cheaper than trusting it to."""
    regions = [{"id": "a"}, {"id": "b"}]
    skel = sm.relational_structure(regions, "a",
                                   measurements=nesting(("a", "b", 0.5), ("b", "a", 0.5)))
    assert [a["region_id"] for a in skel["ancestors"]] == ["b"]


def test_a_region_with_no_container_has_an_empty_chain():
    skel = sm.relational_structure([{"id": "a"}], "a", measurements=[])
    assert skel["ancestors"] == []
    assert skel["has_relation"] is False


def test_the_chain_does_not_change_the_skeletons_own_counts():
    """A regression guard for the refactor that introduced it: `_counts_for` now backs both the
    skeleton and every rung, and the skeleton's numbers must be exactly what they were."""
    regions = [{"id": r} for r in ("part", "whole", "frame", "sib")]
    measurements = nesting(("part", "whole", 0.6), ("part", "frame", 0.2),
                           ("whole", "frame", 0.5), ("sib", "whole", 0.4))
    skel = sm.relational_structure(regions, "part", measurements=measurements)
    assert skel["parent_id"] == "whole"
    assert skel["depth"] == 2
    assert skel["sibling_count"] == 1 and skel["sibling_ids"] == ["sib"]
    assert skel["descendant_count"] == 0


# ── 2. the higher-order term ─────────────────────────────────────────────────────────────────

def test_higher_order_scores_the_containers_by_the_same_rule_one_level_up():
    source = skeleton("a", ancestors=[rung("A1", depth=1, siblings=2, descendants=3)])
    target = skeleton("b", ancestors=[rung("B1", depth=1, siblings=2, descendants=3)])
    verdict = sm.higher_order_agreement(source, target)
    assert verdict["depth"] == 1 and verdict["score"] == 1.0

    mismatched = skeleton("c", ancestors=[rung("C1", depth=4, siblings=0, descendants=0)])
    assert sm.higher_order_agreement(source, mismatched)["score"] < 1.0


def test_a_chain_that_ends_is_not_scored_as_disagreement():
    """The `present` discipline, one level up: a rung only one chain has is an absence of evidence
    about something that does not exist, not evidence against the mapping."""
    source = skeleton("a", ancestors=[rung("A1"), rung("A2")])
    target = skeleton("b", ancestors=[rung("B1")])
    verdict = sm.higher_order_agreement(source, target)
    assert verdict["depth"] == 1                      # only the shared rung is scored
    assert verdict["source_depth"] == 2 and verdict["target_depth"] == 1


def test_no_shared_rung_means_the_pairs_own_agreement_is_the_score():
    source, target = skeleton("a"), skeleton("b")
    assert sm.higher_order_agreement(source, target)["score"] is None
    verdict = sm.systematicity(source, target, higher_order_weight=0.9)
    assert verdict["score"] == verdict["first_order_score"]


def test_the_weight_blends_and_is_off_by_default():
    """THE CLAIM THAT KEEPS THIS HONEST. The term is built, measured and OFF: the sweep did not
    support turning it on, and shipping it enabled would be asserting a result the data refused."""
    assert sm.HIGHER_ORDER_WEIGHT == 0.0
    source = skeleton("a", depth=2, ancestors=[rung("A1", depth=1, siblings=4)])
    target = skeleton("b", depth=2, ancestors=[rung("B1", depth=1, siblings=0)])

    off = sm.systematicity(source, target)
    assert off["score"] == off["first_order_score"]
    assert off["higher_order_weight"] == 0.0

    on = sm.systematicity(source, target, higher_order_weight=0.5)
    expected = 0.5 * on["first_order_score"] + 0.5 * on["higher_order"]["score"]
    assert on["score"] == pytest.approx(expected, abs=1e-6)


def test_the_weight_is_clamped_rather_than_trusted():
    source = skeleton("a", ancestors=[rung("A1")])
    target = skeleton("b", ancestors=[rung("B1")])
    assert sm.systematicity(source, target, higher_order_weight=5.0)["higher_order_weight"] == 1.0
    assert sm.systematicity(source, target, higher_order_weight=-2)["higher_order_weight"] == 0.0


def test_structure_map_passes_the_weight_through_to_the_gate():
    source = skeleton("a", depth=2, siblings=2, parent="pa",
                      ancestors=[rung("A1", depth=1, siblings=9)])
    target = skeleton("b", depth=2, siblings=2, parent="pb",
                      ancestors=[rung("B1", depth=1, siblings=0)])
    verdict = sm.structure_map(source, target, higher_order_weight=0.8)
    assert verdict["systematicity"]["higher_order_weight"] == 0.8
    assert verdict["systematicity"]["score"] < verdict["systematicity"]["first_order_score"]


# ── 3. THE SCAN — the judge is out of the score's reach ──────────────────────────────────────

CRITERION_ORGAN = "adjacency_organ"


def test_structure_map_cannot_import_the_organ_that_judges_it():
    """THE EXTERNALITY PROOF, and the reason this lane can claim anything at all.

    The fresh criterion — does each part MEET its own container? — is measured by
    `adjacency_organ`. If `structure_map` could read it, the validator would be inside the thing
    being validated, which is precisely how #155's circular criterion rated a backwards gate at
    +84.5. Asserted against the module's imports rather than against anyone's intention.
    """
    tree = ast.parse(MODULE.read_text())
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(CRITERION_ORGAN in name for name in imported), imported
    assert not any("adjacency" in name.lower() for name in imported), imported


def _executable_vocabulary(path: pathlib.Path) -> set:
    """Every identifier, attribute and string literal in a module's RUNNING code.

    Docstrings and comments are excluded on purpose. `structure_map` *discusses* the other organ at
    length — #155 recorded that one floor does not cover both — and a grep-shaped scan would be
    testing the prose. This asks what the code can actually reach.
    """
    tree = ast.parse(path.read_text())
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))

    words = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            words.add(node.id)
        elif isinstance(node, ast.Attribute):
            words.add(node.attr)
        elif isinstance(node, ast.alias):
            words.add(node.name)
        elif isinstance(node, ast.ImportFrom):
            words.add(node.module or "")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstrings:
            words.add(node.value)
    return words


def test_structure_map_never_names_a_contact_measurement_in_code():
    """Belt and braces: no attribute access, no string key and no dynamic import could reach the
    criterion either. Checked against the module's executable vocabulary, not its prose."""
    words = _executable_vocabulary(MODULE)
    for forbidden in ("adjacency", "contact", "contact_fraction", "boundary_pixels",
                      "RELATION_MEETS", "find_adjacent_pairs"):
        assert not any(forbidden.lower() in w.lower() for w in words), forbidden


def test_the_only_organ_structure_map_knows_is_the_one_that_produced_its_skeletons():
    """It imports a relation NAME from the nestedness organ and nothing else — no measurement, no
    threshold, no function. The skeleton it reasons over is handed in already measured."""
    tree = ast.parse(MODULE.read_text())
    organ_imports = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                     and "organ" in (n.module or "")]
    assert len(organ_imports) == 1
    assert [a.name for a in organ_imports[0].names] == ["RELATION_NESTED_WITHIN"]


def _criteria_module():
    import importlib.util
    path = MODULE.parents[2] / "scripts" / "higher_order_systematicity.py"
    spec = importlib.util.spec_from_file_location("higher_order_systematicity", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_criterion_that_needs_siblings_is_entangled_with_a_component_of_the_score():
    """THE TRAP THIS LANE FOUND IN ITS OWN CRITERION, pinned so it is not re-proposed.

    `contact_with_sibling` reads a region's `sibling_ids`, so it can NEVER hold for a pair whose
    siblings are absent on both sides — and 'siblings absent on both sides' is exactly what makes
    the siblings component non-live. It is measured by the other organ and it is still not
    independent of the score, because the score is built from the same counts.

    On the corpus it holds for 0.0% of the 894 single-live pairs against a 45.4% base. That is not
    a weak signal; it is a structural impossibility, and it disqualifies the criterion.
    """
    criteria = _criteria_module()
    lonely = skeleton("a", siblings=0)
    lonely["sibling_ids"] = []
    contacts = {"post": {("a", "anything"), ("a", "p")}}
    assert criteria.touches_a_sibling(contacts, "post", lonely) is False

    with_siblings = skeleton("a", siblings=1)
    with_siblings["sibling_ids"] = ["b"]
    assert criteria.touches_a_sibling({"post": {("a", "b")}}, "post", with_siblings) is True


def test_the_criteria_require_the_property_on_BOTH_sides():
    """Positive agreement only. "Neither part touches anything" is a shared absence, and crediting
    it is the exact mistake `present` was introduced to stop — a criterion may not repeat it."""
    criteria = _criteria_module()
    contacts = {"pa": {("a", "pa_parent")}, "pb": set()}
    a = skeleton("a", parent="pa_parent")
    b = skeleton("b", parent="pb_parent")
    assert criteria.touches_its_container(contacts, "pa", a) is True
    assert criteria.touches_its_container(contacts, "pb", b) is False
    # The pair-level criterion is the AND of the two sides — see `score_pairs`.
    assert not (criteria.touches_its_container(contacts, "pa", a)
                and criteria.touches_its_container(contacts, "pb", b))


def test_a_region_with_no_container_cannot_satisfy_the_container_criterion():
    criteria = _criteria_module()
    orphan = skeleton("a", parent="")
    assert criteria.touches_its_container({"p": {("a", "b")}}, "p", orphan) is False


def test_the_criterion_does_not_run_the_scoring_function_it_judges():
    """The flaw in the criterion #155 and #156 used, named so it is not repeated. That one called
    `structure_map` one level up — external in its INPUTS, not in its FUNCTIONAL FORM — so a rule
    favouring structure-poor skeletons also favoured structure-poor parents and could validate
    itself. This lane's criterion reads an adjacency contact and calls nothing here.
    """
    script = MODULE.parents[2] / "scripts" / "higher_order_systematicity.py"
    tree = ast.parse(script.read_text())
    criterion = next(n for n in ast.walk(tree)
                     if isinstance(n, ast.FunctionDef) and n.name == "touches_its_container")
    called = {ast.unparse(n.func) for n in ast.walk(criterion) if isinstance(n, ast.Call)}
    assert not any(name.startswith("sm.") for name in called), called
