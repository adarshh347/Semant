"""
PERCEPTUAL-FORMS-001G — the composite Extent forms, and what a composition may not quietly do.

WHAT THIS MODULE HOLDS TO. `test_perception_lab_forms.py` proves the grammar cannot express
certain lies. `test_perception_lab_extent_forms.py` proves the exact substrates are exact. This
proves the layer between them: that a grouping never becomes a measurement, that inferred pixels
never become visible ones, that a hierarchy never confuses "inside" with "part of", that a density
field never lets a bandwidth read as a population, that alternatives survive, and — the one this
lane adds that no earlier lane could — that a model Lane C refused cannot reach any of them.

THE ADMISSION TABLE IS CHECKED AGAINST LANE C'S OWN PROSE. Seven verdicts live as data in
`admission.py` and seven rows live in `research/perception_lab/model_trials/FINDINGS.md`, and a
test parses the second and fails on any disagreement. A gate whose ruling could drift from the
evidence that produced it is not a gate.

PURE. No database, no network, no model, no adapter, no image.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import pytest
from pydantic import ValidationError

from backend.schemas import perception_lab as S
from backend.schemas.perception_lab import (EpistemicBasis, EpistemicStatus, GroundKind,
                                            RefusalCode)
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab.extent_composites import admission as A
from backend.services.perception_lab.extent_composites import sources as SRC
from backend.services.perception_lab.topology_forms import production as P

REPO_ROOT = Path(__file__).resolve().parents[2]
TRIALS = REPO_ROOT / "research" / "perception_lab" / "model_trials"

#: The five forms this lane composes. Four of them are `deferred` in the merged contract and one
#: is `experimental`, and every producer here reports that rather than working around it.
COMPOSITE_FORMS = ("extent.fused_hypothesis", "extent.visible_inferred_partition",
                   "extent.hierarchy", "extent.density_field", "extent.hypothesis_set")


# ── the admission table ──────────────────────────────────────────────────────


def _matrix_rows() -> List[Dict[str, str]]:
    """Lane C's verdict table, parsed out of the prose it was written in."""
    text = (TRIALS / "FINDINGS.md").read_text(encoding="utf-8")
    rows: List[Dict[str, str]] = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) != 6 or not cells[1].startswith("`extent."):
            continue
        verdict = cells[3]
        word = "ADOPT AS EXPERIMENTAL" if "ADOPT AS EXPERIMENTAL" in verdict else \
            "REJECT" if "REJECT" in verdict else "DEFER" if "DEFER" in verdict else \
            "ADOPT" if "ADOPT" in verdict else "?"
        rows.append({"form": cells[1].strip("`"), "candidate": cells[2],
                     "verdict": word.lower().replace(" ", "_"),
                     "ground_only": "as one ground only" in verdict})
    return rows


def test_the_admission_table_is_lane_c_s_and_not_a_second_opinion():
    """Seven verdicts as data, seven rows as prose, and no arrangement in which they differ.

    This is the whole reason the table is worth having. A verdict transcribed once and then
    maintained separately is a verdict that will disagree with its evidence on some later edit,
    and the disagreement would be invisible — both halves would look authoritative.
    """
    rows = _matrix_rows()
    assert len(rows) == len(A.ADMISSIONS) == 7
    from_prose = sorted((r["form"], r["verdict"], r["ground_only"]) for r in rows)
    from_data = sorted((a.form_key, a.verdict.value, a.role is A.Role.GROUND)
                       for a in A.ADMISSIONS)
    assert from_prose == from_data


def test_every_admitted_candidate_has_a_recorded_run_behind_it():
    """A verdict with no trial under it is an opinion. Lane C committed eighteen run records; each
    admitted or rejected candidate must appear in at least one, naming the form it was put to."""
    for entry in A.ADMISSIONS:
        runs = sorted((TRIALS / "runs").glob(f"{entry.model_key}.*.json"))
        if entry.verdict is A.Verdict.DEFER:
            continue                      # deferred means never run; that is the point of it
        assert runs, f"{entry.model_key} carries a verdict and no recorded run"
        record = json.loads(runs[0].read_text(encoding="utf-8"))
        assert entry.form_key in record["candidate"]["forms"], entry.model_key


def test_a_deferred_candidate_was_never_run_and_says_which_kind_of_missing_it_is():
    for entry in A.ADMISSIONS:
        if entry.verdict is not A.Verdict.DEFER:
            continue
        assert entry.deferred_because in ("resources", "no_weights")
        with pytest.raises(A.ModelNotAdmitted) as caught:
            A.admitted(entry.model_key, entry.form_key, role=A.Role.PRODUCER)
        assert caught.value.refusal.detail["deferred_because"] == entry.deferred_because


def test_reject_and_defer_are_two_different_noes():
    """Running `sam2_logits` again changes nothing; running `amodal_sam` is exactly what would.
    A refusal that collapsed them would tell a person to do the wrong next thing."""
    rejected = A.admissions_for("extent.soft_field")
    with pytest.raises(A.ModelNotAdmitted) as reject:
        A.admitted("sam2_logits", "extent.soft_field", role=A.Role.PRODUCER)
    with pytest.raises(A.ModelNotAdmitted) as defer:
        A.admitted("amodal_sam", "extent.visible_inferred_partition", role=A.Role.PRODUCER)
    assert reject.value.refusal.detail["verdict"] == "reject"
    assert defer.value.refusal.detail["verdict"] == "defer"
    assert reject.value.refusal.remedy != defer.value.refusal.remedy
    assert any(a.verdict is A.Verdict.REJECT for a in rejected)


def test_a_model_nobody_evaluated_is_refused_as_firmly_as_one_that_failed():
    with pytest.raises(A.ModelNotAdmitted) as caught:
        A.admitted("segment_anything_3", "extent.fused_hypothesis", role=A.Role.GROUND)
    refusal = caught.value.refusal
    assert refusal.detail["verdict"] is None
    assert refusal.detail["considered"] == ["dinov2_affinity", "depth_anything_v2_small"]


@pytest.mark.parametrize("form_key, why", [
    ("extent.visible_inferred_partition", "two deferred candidates and no admitted one"),
    ("extent.density_field", "one rejected candidate; the form needs no model"),
])
def test_a_form_with_no_admitted_producer_gets_no_substitute(form_key, why):
    """The failure this gate exists for. A substituted producer's output is shaped exactly like
    the requested one's, so the substitution is invisible in the artifact and visible only in the
    wrongness."""
    with pytest.raises(A.ModelNotAdmitted) as caught:
        A.producer_for(form_key)
    refusal = caught.value.refusal
    assert refusal.code is RefusalCode.CAPABILITY_UNAVAILABLE
    assert set(refusal.detail["verdicts"]) == {a.model_key for a in A.admissions_for(form_key)}
    assert "substituted" in refusal.message, why


def test_a_ground_model_may_not_be_used_as_a_producer():
    """DINOv2 measures how alike two fragments LOOK. Admitting it to WRITE a fusion would let
    resemblance author unity, which is the exact thing `false-twins` was built to catch."""
    with pytest.raises(A.ModelNotAdmitted) as caught:
        A.admitted("dinov2_affinity", "extent.fused_hypothesis", role=A.Role.PRODUCER)
    assert caught.value.refusal.detail["admitted_role"] == "ground"
    assert caught.value.refusal.detail["requested_role"] == "producer"


def test_an_admitted_model_vouching_for_evidence_it_does_not_measure_is_refused():
    """Depth Anything supplies occlusion ordering. A ground claiming `shape_continuity` on its
    authority would be a depth model asserting geometry."""
    ok = A.ground_admission("depth_anything_v2_small", GroundKind.OCCLUSION_HYPOTHESIS,
                            "extent.fused_hypothesis")
    assert ok.sole_ground_forbidden
    with pytest.raises(A.ModelNotAdmitted) as caught:
        A.ground_admission("depth_anything_v2_small", GroundKind.SHAPE_CONTINUITY,
                           "extent.fused_hypothesis")
    assert caught.value.refusal.detail["requested_kind"] == "shape_continuity"


def test_both_adopted_grounds_are_forbidden_from_standing_alone():
    for key in ("dinov2_affinity", "depth_anything_v2_small"):
        entry = A.admitted(key, "extent.fused_hypothesis", role=A.Role.GROUND)
        assert entry.sole_ground_forbidden, f"{key} may never be the only ground"


BANNED_IMPORTS = ("torch", "transformers", "cv2", "numpy", "PIL", "motor", "pymongo", "fastapi",
                  "backend.routers", "backend.database", "backend.services.perception_lab.extent",
                  "backend.services.perception_lab.orchestrator",
                  "backend.services.perception_lab.mongo_store",
                  "backend.services.perception_lab.adapters")


def imported_names(path) -> List[str]:
    """Every module an `import` statement in this file names.

    PARSED, NOT GREPPED. A docstring saying "this does not import torch" is not an import, and a
    substring search that cannot tell the two apart is a test that fails on its own prose — or,
    worse, one that gets softened until it passes and then catches nothing.
    """
    import ast
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.append(node.module)
    return out


def test_the_gate_holds_no_model_and_cannot_be_made_to():
    """The isolation claim, read off the import graph rather than promised in a docstring."""
    import pathlib
    package = pathlib.Path(A.__file__).parent
    for path in sorted(package.glob("*.py")):
        for name in imported_names(path):
            root = name.split(".")[0]
            for banned in BANNED_IMPORTS:
                assert not (name == banned or name.startswith(banned + ".")
                            or root == banned), f"{path.name} imports {name}"


# ── the composite forms are the ones the registry declares ───────────────────


@pytest.mark.parametrize("form_key", COMPOSITE_FORMS)
def test_every_composite_form_is_registered_and_none_of_them_has_a_producer_yet(form_key):
    definition = D.form(form_key)
    assert definition.organ == "extent"
    assert not definition.has_producer, (
        "no operation declares any of these, which is why this lane returns payloads and "
        "verdicts rather than artifacts naming an operation that never ran")


def test_the_omission_vocabulary_is_one_list_and_this_lane_extended_it():
    """A reader counting what a laboratory left out should have one vocabulary to count in.
    Two closed lists that each call themselves closed drift on the first edit, and the omission a
    reader most wants is the one that fell between them."""
    for reason in ("producer_unavailable", "ground_not_admitted", "sole_ground_forbidden",
                   "no_ground_supplied", "part_not_supplied", "not_geometrically_contained",
                   "semantic_link_undeclared", "single_reading"):
        assert reason in P.OMISSION_REASONS
    with pytest.raises(ValueError):
        P.Omission(what="x", reason="omitted_for_other_reasons", detail="")
