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

import copy
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
from backend.services.perception_lab.extent_composites import alternatives as ALT
from backend.services.perception_lab.extent_composites import density as DN
from backend.services.perception_lab.extent_composites import fusion as FUS
from backend.services.perception_lab.extent_composites import grounds as GR
from backend.services.perception_lab.extent_composites import hierarchy as HI
from backend.services.perception_lab.extent_composites import partition as PT
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


# ── the scaffolding the composite producers are fed ──────────────────────────


FIXTURES = REPO_ROOT / "research" / "perception_lab" / "fixtures" / "topology_forms"

#: Lane D's committed scenes, reused rather than re-drawn. They are real `extent_set` artifacts
#: measured off real rasters, so a change in how the Extent façade records an instance reaches
#: this suite as a diff a person reads.
FOREST = "art_forms_forest"
CUBIST = "art_forms_cubist"


def scene(name: str) -> Dict[str, Any]:
    return json.loads((FIXTURES / f"extent-set.{name}.json").read_text(encoding="utf-8"))


def extents(name: str, *, basis: str = "mask", status: str = "measured") -> SRC.ExtentSource:
    doc = scene(name)
    doc["measurement"]["epistemic_basis"] = basis
    doc["measurement"]["epistemic_status"] = status
    return SRC.extent_set(doc)


def fragments(*ids: str, artifact_id: str = "art_frag", examined: int = 0) -> SRC.ExtentSource:
    """A carried `extent.fragment_set`. It cannot be an artifact and that is not a shortcut:
    no operation declares the form, so `PerceptualArtifact` refuses to carry one."""
    payload = S.ExtentFragmentSetPayload.model_validate({
        "variant": "extent_fragment_set", "unity_asserted": False,
        "regions_examined": examined or len(ids),
        "fragments": [{"fragment_id": f, "mask_rle": None, "area": 0.01,
                       "box": {"x": 0.1 * (i + 1), "y": 0.1, "w": 0.05, "h": 0.05},
                       "naming": None} for i, f in enumerate(ids)]})
    return SRC.fragment_set((artifact_id, payload))


def geometry_ground(detail: str = "the severed edges continue into each other",
                    strength: float = 0.4) -> "GR.GroundEvidence":
    return GR.GroundEvidence(kind=GroundKind.SHAPE_CONTINUITY, detail=detail,
                             attributed_to=GR.GEOMETRY, strength=strength)


def model_ground(model: str = "dinov2_affinity",
                 kind: GroundKind = GroundKind.APPEARANCE_CONTINUITY,
                 strength: float = 0.95) -> "GR.GroundEvidence":
    return GR.GroundEvidence(kind=kind, detail="pooled patch cosine",
                             attributed_to=f"{GR.MODEL_PREFIX}{model}", strength=strength)


# ── extent.fused_hypothesis ──────────────────────────────────────────────────


def test_a_grouping_of_measured_masks_is_not_a_measurement():
    """Every member is a mask somebody measured per pixel. The claim that they are one thing is a
    different kind of statement about the same pixels, and the partition caps it."""
    source = extents("cubist")
    result = FUS.produce_fused_hypothesis([FUS.ProposedFusion(
        proposal_id="upper_and_lower", member_keys=(f"{CUBIST}#form_upper", f"{CUBIST}#form_lower"),
        evidence=(geometry_ground(),))], sources=[source])
    hypothesis, = result.payload.hypotheses
    assert hypothesis.partition is S.EpistemicPartition.INTERPRETIVE_GROUPING
    assert hypothesis.epistemic_status is EpistemicStatus.INTERPRETIVE
    assert source.epistemic_status is EpistemicStatus.MEASURED, "the members were measured"
    assert result.ceiling is EpistemicStatus.INTERPRETIVE


def test_asserting_hidden_extent_is_a_different_claim_and_costs_more():
    source = extents("cubist")
    both = FUS.produce_fused_hypothesis([
        FUS.ProposedFusion("visible", (f"{CUBIST}#form_upper", f"{CUBIST}#form_lower"),
                           evidence=(geometry_ground(),)),
        FUS.ProposedFusion("behind", (f"{CUBIST}#form_upper", f"{CUBIST}#form_lower"),
                           evidence=(geometry_ground(),), asserts_hidden_extent=True),
    ], sources=[source])
    by_hidden = {h.asserts_hidden_extent: h for h in both.payload.hypotheses}
    assert by_hidden[False].epistemic_status is EpistemicStatus.INTERPRETIVE
    assert by_hidden[True].epistemic_status is EpistemicStatus.UNCERTAIN
    assert by_hidden[True].partition is S.EpistemicPartition.INFERRED_COMPLETION
    assert both.ceiling is EpistemicStatus.UNCERTAIN, (
        "a set holding one completion asserts hidden extent, and the record says so")


def test_no_weight_lifts_a_grouping_out_of_its_partition():
    source = extents("cubist")
    result = FUS.produce_fused_hypothesis([FUS.ProposedFusion(
        "certain", (f"{CUBIST}#form_upper", f"{CUBIST}#form_lower"),
        evidence=(geometry_ground(strength=1.0),), weight=1.0)], sources=[source])
    hypothesis, = result.payload.hypotheses
    assert hypothesis.weight == 1.0
    assert hypothesis.epistemic_status is EpistemicStatus.INTERPRETIVE
    lifted = result.payload.model_dump()
    lifted["hypotheses"][0]["epistemic_status"] = "measured"
    with pytest.raises(ValidationError):
        S.ExtentFusionHypothesisPayload.model_validate(lifted)


def test_a_grouping_with_no_ground_is_left_out_and_named():
    result = FUS.produce_fused_hypothesis([FUS.ProposedFusion(
        "bare", (f"{CUBIST}#form_upper", f"{CUBIST}#form_lower"))], sources=[extents("cubist")])
    assert result.payload.hypotheses == []
    assert [o.what for o in result.omissions_for("no_ground_supplied")] == ["bare"]


def test_the_only_ground_may_not_be_one_lane_c_admitted_as_one_ground_among_several():
    """`false-similarity`: three identical discs, two of which belong together. A cosine of 0.95
    is exactly what the trap produces, and it may not carry a fusion by itself."""
    alone = FUS.produce_fused_hypothesis([FUS.ProposedFusion(
        "resemblance_only", (f"{CUBIST}#form_upper", f"{CUBIST}#form_lower"),
        evidence=(model_ground(),))], sources=[extents("cubist")])
    assert alone.payload.hypotheses == []
    assert [o.what for o in alone.omissions_for("sole_ground_forbidden")] == ["resemblance_only"]

    beside = FUS.produce_fused_hypothesis([FUS.ProposedFusion(
        "resemblance_and_shape", (f"{CUBIST}#form_upper", f"{CUBIST}#form_lower"),
        evidence=(model_ground(), geometry_ground()))], sources=[extents("cubist")])
    assert len(beside.payload.hypotheses) == 1, "Lane C's rule is `sole`, and this one is not"
    assert len(beside.payload.hypotheses[0].grounds) == 2


def test_a_ground_from_a_model_lane_c_refused_never_reaches_the_payload():
    result = FUS.produce_fused_hypothesis([FUS.ProposedFusion(
        "smuggled", (f"{CUBIST}#form_upper", f"{CUBIST}#form_lower"),
        evidence=(geometry_ground(),
                  model_ground(model="pix2gestalt", kind=GroundKind.OCCLUSION_HYPOTHESIS)))],
        sources=[extents("cubist")])
    hypothesis, = result.payload.hypotheses
    assert [g.kind for g in hypothesis.grounds] == [GroundKind.SHAPE_CONTINUITY]
    dropped, = result.omissions_for("ground_not_admitted")
    assert "pix2gestalt" in dropped.what
    assert "never put to 'extent.fused_hypothesis'" in dropped.detail, (
        "an admission is per (model, form). pix2gestalt is a deferred candidate for the PARTITION "
        "form and is not thereby a candidate for this one — a verdict earned on one question is "
        "not a licence to answer another")


def test_a_ground_attributed_to_nothing_this_laboratory_knows_is_refused():
    result = FUS.produce_fused_hypothesis([FUS.ProposedFusion(
        "anonymous", (f"{CUBIST}#form_upper", f"{CUBIST}#form_lower"),
        evidence=(GR.GroundEvidence(kind=GroundKind.SHAPE_CONTINUITY, detail="it looks right",
                                    attributed_to="intuition"),))], sources=[extents("cubist")])
    assert result.payload.hypotheses == []
    assert result.omissions_for("ground_not_admitted")


def test_a_person_may_assert_and_may_not_thereby_measure():
    person = GR.GroundEvidence(kind=GroundKind.DEPTH_CONTINUITY, detail="I can see it is behind",
                               attributed_to=GR.HUMAN)
    vetting = GR.vet([person], form_key=FUS.FORM, subject="p")
    assert vetting.grounds == ()
    assert vetting.omitted[0].reason == "ground_not_admitted"
    allowed = GR.vet([GR.GroundEvidence(kind=GroundKind.HUMAN_ASSERTION, detail="one tree",
                                        attributed_to=GR.HUMAN)], form_key=FUS.FORM, subject="p")
    assert len(allowed.grounds) == 1


def test_a_member_no_supplied_source_holds_is_refused_rather_than_invented():
    result = FUS.produce_fused_hypothesis([FUS.ProposedFusion(
        "dangling", (f"{CUBIST}#form_upper", "art_elsewhere#ghost"),
        evidence=(geometry_ground(),))], sources=[extents("cubist")])
    assert result.payload.hypotheses == []
    assert [o.what for o in result.omissions_for("endpoint_dangling")] == ["dangling"]


def test_a_fusion_of_one_thing_with_itself_is_not_a_fusion():
    result = FUS.produce_fused_hypothesis([FUS.ProposedFusion(
        "self", (f"{CUBIST}#form", f"{CUBIST}#form"), evidence=(geometry_ground(),))],
        sources=[extents("cubist")])
    assert [o.what for o in result.omissions_for("self_pair")] == ["self"]


def test_a_box_basis_extent_set_cannot_ground_a_fusion_and_is_not_quietly_downgraded():
    """A bounding box does not show that two patches continue into each other. Composing over it
    at a lower ceiling would produce a hypothesis whose evidence is a rectangle."""
    boxes = extents("cubist", basis="box", status="interpretive")
    result = FUS.produce_fused_hypothesis([FUS.ProposedFusion(
        "boxes", (f"{CUBIST}#form_upper", f"{CUBIST}#form_lower"),
        evidence=(geometry_ground(),))], sources=[boxes])
    assert result.payload is None
    assert [o.reason for o in result.omitted] == ["basis_not_admitted"]
    assert "box" not in D.form(FUS.FORM).admissible_bases
    assert result.input_artifact_ids == (), "a source that was dropped is not an input"


def test_two_competing_groupings_of_the_same_members_both_survive():
    """Dropping the rejected grouping is how a guess becomes a fact between one panel and the
    next. `alternatives_retained` is the field that says it did not happen here."""
    result = FUS.produce_fused_hypothesis([
        FUS.ProposedFusion("one_tree", (f"{CUBIST}#form_upper", f"{CUBIST}#form_lower"),
                           evidence=(geometry_ground(),), weight=0.8),
        FUS.ProposedFusion("two_things", (f"{CUBIST}#form_upper", f"{CUBIST}#plane"),
                           evidence=(geometry_ground("the planes align"),), weight=0.2),
    ], sources=[extents("cubist")])
    assert len(result.payload.hypotheses) == 2
    assert result.payload.alternatives_retained is True
    assert [h.weight for h in result.payload.hypotheses] == [0.8, 0.2], (
        "the order is the order they were proposed in — never sorted by weight")


def test_fragments_considered_is_carried_through_and_never_recounted():
    """"the fragments were considered and no grouping was supportable" and "nobody looked" arrive
    at the same empty list. This is the whole difference."""
    source = fragments("frag_a", "frag_b", examined=9)
    result = FUS.produce_fused_hypothesis([], sources=[source])
    assert result.payload.fragments_considered == 9
    assert result.payload.hypotheses == []


def test_the_same_proposal_composed_twice_gets_the_same_hypothesis_id():
    proposals = [FUS.ProposedFusion("p", (f"{CUBIST}#form_upper", f"{CUBIST}#form_lower"),
                                    evidence=(geometry_ground(),))]
    one = FUS.produce_fused_hypothesis(proposals, sources=[extents("cubist")])
    two = FUS.produce_fused_hypothesis(proposals, sources=[extents("cubist")])
    assert one.payload.model_dump() == two.payload.model_dump()


# ── extent.hypothesis_set ────────────────────────────────────────────────────


def readings() -> List["ALT.Reading"]:
    return [
        ALT.Reading("body_only", weight=0.5, member_keys=(f"{CUBIST}#form",),
                    evidence=(geometry_ground("the figure alone"),)),
        ALT.Reading("body_and_shadow", weight=0.5,
                    member_keys=(f"{CUBIST}#form", f"{CUBIST}#plane"),
                    evidence=(geometry_ground("the dark shape is cast by it"),)),
    ]


def test_competing_readings_are_held_open_and_the_record_cannot_resolve_itself():
    result = ALT.produce_hypothesis_set("is the shadow part of the figure?", readings(),
                                        sources=[extents("cubist")])
    assert len(result.payload.alternatives) == 2
    assert "chosen" not in result.payload.model_dump()
    assert "winner" not in S.ExtentHypothesisSetPayload.model_fields


def test_an_unresolved_alternative_is_uncertain_however_measured_its_extents_are():
    source = extents("cubist")
    result = ALT.produce_hypothesis_set("which reading?", readings(), sources=[source])
    assert source.epistemic_status is EpistemicStatus.MEASURED
    assert result.ceiling is EpistemicStatus.UNCERTAIN
    assert D.form(ALT.FORM).admissible_partitions == ("unresolved_alternative",)


def test_alternatives_are_ordered_by_id_and_never_by_weight():
    """A reader that takes the first element takes a winner, whatever the field it was sorted on
    is called."""
    heavy = [ALT.Reading("a_light", weight=0.1, member_keys=(f"{CUBIST}#form",)),
             ALT.Reading("b_heavy", weight=0.9, member_keys=(f"{CUBIST}#plane",))]
    result = ALT.produce_hypothesis_set("q", heavy, sources=[extents("cubist")])
    ids = [a.alternative_id for a in result.payload.alternatives]
    assert ids == sorted(ids), "the order is the derived id, which carries no ranking"
    weights = [a.weight for a in result.payload.alternatives]
    assert set(weights) == {0.1, 0.9}
    heaviest = max(result.payload.alternatives, key=lambda a: a.weight)
    assert (heaviest is result.payload.alternatives[0]) == (
        heaviest.alternative_id == ids[0]), (
        "which alternative lands first is decided by the id and by nothing else")


def test_weights_that_happen_to_sum_to_one_are_not_thereby_probabilities():
    result = ALT.produce_hypothesis_set("q", readings(), sources=[extents("cubist")])
    assert sum(a.weight for a in result.payload.alternatives) == 1.0
    assert result.payload.weights_are_probabilities is False


def test_declaring_probabilities_that_do_not_sum_to_one_is_refused_rather_than_validated_away():
    lopsided = [ALT.Reading("a", weight=0.9, member_keys=(f"{CUBIST}#form",)),
                ALT.Reading("b", weight=0.9, member_keys=(f"{CUBIST}#plane",))]
    result = ALT.produce_hypothesis_set("q", lopsided, sources=[extents("cubist")],
                                        weights_are_probabilities=True)
    assert result.payload.weights_are_probabilities is False
    assert any(r.code is RefusalCode.INVALID_PARAMETERS for r in result.refusals)


def test_one_surviving_reading_is_a_hard_mask_and_is_refused_here():
    result = ALT.produce_hypothesis_set("q", [readings()[0]], sources=[extents("cubist")])
    assert result.payload.alternatives == []
    assert result.payload.alternatives_considered == 1
    assert [o.reason for o in result.omissions_for("single_reading")] == ["single_reading"]
    assert any(r.code is RefusalCode.UNSUPPORTED_FORM for r in result.refusals)


def test_a_reading_that_names_nothing_is_a_weight_about_nothing():
    result = ALT.produce_hypothesis_set("q", readings() + [ALT.Reading("empty", weight=0.3)],
                                        sources=[extents("cubist")])
    assert len(result.payload.alternatives) == 2
    assert result.payload.alternatives_considered == 3
    assert [o.what for o in result.omissions_for("endpoint_dangling")] == ["empty"]


# ── both forms are deferred, and every producer says so ──────────────────────


@pytest.mark.parametrize("build", [
    lambda: FUS.produce_fused_hypothesis(
        [FUS.ProposedFusion("p", (f"{CUBIST}#form_upper", f"{CUBIST}#form_lower"),
                            evidence=(GR.GroundEvidence(kind=GroundKind.SHAPE_CONTINUITY,
                                                        detail="d"),))],
        sources=[extents("cubist")]),
    lambda: ALT.produce_hypothesis_set("q", readings(), sources=[extents("cubist")]),
])
def test_a_deferred_form_carries_its_payload_and_its_verdict_and_is_not_writable(build):
    """The shape is what this phase settles; the deferral is what it does not soften. A caller
    that wants to mint an artifact has to step over `producible` to do it."""
    result = build()
    assert result.payload is not None
    assert result.producible is False
    assert result.writable_payload is None
    assert any(r.code is RefusalCode.FORM_NOT_PRODUCIBLE for r in result.refusals)


# ── extent.hierarchy ─────────────────────────────────────────────────────────


def forest() -> SRC.ExtentSource:
    return SRC.extent_set(scene("forest"))


def link(child: str, parent: Optional[str] = None, **kw) -> "HI.ProposedLink":
    return HI.ProposedLink(f"{FOREST}#{child}",
                           None if parent is None else f"{FOREST}#{parent}", **kw)


def asserted(text: str = "the wall encloses the court") -> "GR.GroundEvidence":
    return GR.GroundEvidence(kind=GroundKind.HUMAN_ASSERTION, detail=text,
                             attributed_to=GR.HUMAN)


def by_instance(result) -> Dict[str, Any]:
    return {n.instance.instance_id: n for n in result.payload.nodes}


def test_a_measured_nesting_carries_the_fraction_of_the_parent_it_occupies():
    result = HI.produce_extent_hierarchy(
        [link("court"), link("fountain", "court"), link("basin", "fountain")],
        sources=[forest()])
    nodes = by_instance(result)
    assert nodes["court"].parent_node_id is None
    assert nodes["fountain"].occupancy_of_parent == 0.112782
    assert nodes["basin"].occupancy_of_parent == 0.133333
    assert all(n.basis is EpistemicBasis.MASK for n in result.payload.nodes)
    assert result.ceiling is EpistemicStatus.MEASURED


def test_geometric_containment_and_semantic_part_whole_are_two_different_links():
    """A pigeon standing in a courtyard is contained by it and is not part of it. The wall around
    the court is part of it and is not inside it. `basis` is where the distinction lives."""
    result = HI.produce_extent_hierarchy(
        [link("court"), link("fountain", "court"),
         link("wall", "court", kind=HI.LinkKind.SEMANTIC, asserted_by=asserted())],
        sources=[forest()])
    nodes = by_instance(result)
    assert nodes["fountain"].basis is EpistemicBasis.MASK
    assert nodes["wall"].basis is EpistemicBasis.MANUAL
    assert result.ceiling is EpistemicStatus.INTERPRETIVE, (
        "one asserted link makes the whole tree an interpretive grouping")


def test_a_semantic_link_carries_no_occupancy_even_where_the_masks_would_support_one():
    """A fraction beside an asserted parentage would make the assertion look measured, and
    `HierarchyNode` has no field saying which of the two the number belongs to."""
    result = HI.produce_extent_hierarchy(
        [link("court"), link("fountain", "court", kind=HI.LinkKind.SEMANTIC,
                             asserted_by=asserted("the fountain belongs to the court"))],
        sources=[forest()])
    assert by_instance(result)["fountain"].occupancy_of_parent is None
    measured = HI.produce_extent_hierarchy([link("court"), link("fountain", "court")],
                                           sources=[forest()])
    assert by_instance(measured)["fountain"].occupancy_of_parent == 0.112782


def test_a_part_whole_link_that_names_nobody_is_a_containment_claim_without_a_measurement():
    result = HI.produce_extent_hierarchy(
        [link("court"), link("wall", "court", kind=HI.LinkKind.SEMANTIC)], sources=[forest()])
    assert "wall" not in by_instance(result)
    assert [o.reason for o in result.omissions_for("semantic_link_undeclared")] == \
        ["semantic_link_undeclared"]


def test_a_proposed_parent_that_does_not_contain_the_child_is_refused_per_pixel():
    """The courtyard's wall surrounds the court; it is not inside it. No tolerance, no
    almost-contained, and the refusal is recorded rather than the link being quietly kept."""
    result = HI.produce_extent_hierarchy([link("court"), link("wall", "court")],
                                          sources=[forest()])
    assert "wall" not in by_instance(result)
    stated, = result.omissions_for("not_geometrically_contained")
    assert stated.what == f"{FOREST}#wall<-{FOREST}#court"


def test_a_node_whose_parent_was_excluded_is_excluded_and_says_so():
    """Re-rooting it would invent a level nobody proposed; dropping it quietly would make a
    partial tree read as a complete one."""
    result = HI.produce_extent_hierarchy(
        [link("court"), link("wall", "court"), link("niche", "wall")], sources=[forest()])
    assert set(by_instance(result)) == {"court"}
    assert len(result.omissions_for("orphaned_by_exclusion")) == 1


def test_a_cycle_is_reported_and_never_broken_by_dropping_an_edge():
    """A geometric cycle cannot arise off one raster — containment is checked per pixel and two
    masks cannot each contain the other. An ASSERTED cycle can, and does: a person says the
    fountain is part of the basin and the basin is part of the fountain, and the links disagree.
    """
    result = HI.produce_extent_hierarchy(
        [link("fountain", "basin", kind=HI.LinkKind.SEMANTIC, asserted_by=asserted("a")),
         link("basin", "fountain", kind=HI.LinkKind.SEMANTIC, asserted_by=asserted("b"))],
        sources=[forest()])
    assert result.payload.nodes == []
    assert len(result.omissions_for("containment_cycle")) == 2, (
        "the whole loop goes; deleting the edge that happened to be walked last would produce a "
        "tree that validates and that nobody chose")


def test_two_masks_cannot_each_contain_the_other_so_a_geometric_cycle_never_forms():
    """The precondition for the test above, asserted rather than assumed."""
    result = HI.produce_extent_hierarchy(
        [link("fountain", "basin"), link("basin", "fountain")], sources=[forest()])
    assert len(result.omissions_for("not_geometrically_contained")) == 1
    assert result.omissions_for("containment_cycle") == ()


def test_a_second_parent_for_one_node_is_a_second_tree_and_is_refused():
    result = HI.produce_extent_hierarchy(
        [link("court"), link("fountain", "court"), link("fountain", "basin")],
        sources=[forest()])
    assert by_instance(result)["fountain"].parent_node_id is not None
    assert len(result.omissions_for("duplicate")) == 1


def test_every_node_cites_a_revision_and_one_that_cannot_is_left_out():
    result = HI.produce_extent_hierarchy([link("court")], sources=[forest()])
    node, = result.payload.nodes
    assert node.instance.geometry_rev == 1
    unpinned = copy.deepcopy(scene("forest"))
    for instance in unpinned["measurement"]["payload"]["instances"]:
        instance["geometry_rev"] = None
        instance["region_id"] = None
    unpinned["identity"]["identity_refs"] = []
    unpinned["identity"]["identity_scope"] = "session"
    bare = HI.produce_extent_hierarchy([link("court")], sources=[SRC.extent_set(unpinned)])
    assert bare.payload.nodes == []
    assert [o.reason for o in bare.omissions_for("revision_missing")] == ["revision_missing"]


def test_pairs_examined_counts_the_parentages_put_forward_including_the_failures():
    result = HI.produce_extent_hierarchy(
        [link("court"), link("wall", "court"), link("fountain", "court")], sources=[forest()])
    assert result.payload.pairs_examined == 3
    assert len(result.payload.nodes) == 2


def test_the_hierarchy_is_the_one_form_of_the_five_that_may_actually_be_written():
    result = HI.produce_extent_hierarchy([link("court")], sources=[forest()])
    assert result.producible is True
    assert result.writable_payload is not None
    assert D.form(HI.FORM).state == "experimental"


# ── extent.visible_inferred_partition ────────────────────────────────────────


def instance_mask(source: SRC.ExtentSource, instance_id: str) -> Dict[str, Any]:
    return {m.instance_id: m for m in source.members}[instance_id].mask_rle


def part(kind: S.PartitionPart, mask=None, **kw) -> "PT.SuppliedPart":
    return PT.SuppliedPart(kind, mask_rle=mask, **kw)


def test_the_three_parts_carry_three_statuses_and_the_inferred_one_is_never_visible():
    source = forest()
    result = PT.produce_visible_inferred_partition(
        f"{FOREST}#court",
        [part(S.PartitionPart.VISIBLE, instance_mask(source, "basin")),
         part(S.PartitionPart.INFERRED, instance_mask(source, "niche"))],
        sources=[source])
    statuses = {r.part: r.epistemic_status for r in result.payload.regions}
    assert statuses[S.PartitionPart.VISIBLE] is EpistemicStatus.MEASURED
    assert statuses[S.PartitionPart.INFERRED] is EpistemicStatus.UNCERTAIN
    lifted = result.payload.model_dump()
    lifted["regions"][1]["epistemic_status"] = "measured"
    with pytest.raises(ValidationError):
        S.ExtentPartitionPayload.model_validate(lifted)


def test_the_statuses_this_producer_picks_are_a_subset_of_the_ones_the_schema_allows():
    """A second copy of a rule is a second chance to disagree with it, so the copy is checked in
    the only direction that is safe: everything this producer picks must validate, and nothing the
    schema forbids may appear in the copy.

    THE COPY IS DELIBERATELY NARROWER ON THE INFERRED PART. The schema permits `interpretive` OR
    `uncertain` there, because a person reading a partly hidden figure may be doing something
    weaker than completing it. This producer only ever completes, and Lane C's rule for every
    amodal output is that it is `uncertain` — so `interpretive` stays available to a manual
    author and is never written here.
    """
    def region(kind, status):
        return PT.PartitionRegion(part=kind, epistemic_status=status, coverage=0.1,
                                  mask_rle={"size": [2, 2], "counts": [0, 1, 3]})
    for kind, allowed in PT.ALLOWED.items():
        for status in allowed:
            assert region(kind, status).epistemic_status is status
    assert EpistemicStatus.INTERPRETIVE not in PT.ALLOWED[S.PartitionPart.INFERRED]
    assert region(S.PartitionPart.INFERRED, EpistemicStatus.INTERPRETIVE), (
        "the schema allows it; this producer does not use it")
    for forbidden in (EpistemicStatus.MEASURED, EpistemicStatus.VISIBLE):
        with pytest.raises(ValidationError):
            region(S.PartitionPart.INFERRED, forbidden)
        assert forbidden not in PT.ALLOWED[S.PartitionPart.INFERRED]


def test_a_pixel_in_two_parts_refuses_the_whole_partition_rather_than_half_of_it():
    """A reader drawing the tricolour would paint it in whichever key their loop reached last, so
    a hallucinated leg would appear in the same colour as a photographed one. Every part of the
    answer is contaminated by that ambiguity, so there is no partial answer worth returning."""
    source = forest()
    mask = instance_mask(source, "basin")
    result = PT.produce_visible_inferred_partition(
        f"{FOREST}#court",
        [part(S.PartitionPart.VISIBLE, mask), part(S.PartitionPart.INFERRED, mask)],
        sources=[source])
    assert result.payload is None
    refusal, = [r for r in result.refusals if r.code is RefusalCode.INVALID_PARAMETERS]
    assert refusal.detail["parts"] == ["visible", "inferred"]
    assert refusal.detail["shared_pixels"] > 0


def test_parts_on_another_raster_are_refused_before_they_can_pass_the_overlap_check():
    """`intersection_area` returns None on a raster mismatch rather than resampling, so two parts
    on two rasters would pass the overlap check by being incomparable."""
    source = forest()
    result = PT.produce_visible_inferred_partition(
        f"{FOREST}#court", [part(S.PartitionPart.VISIBLE, {"size": [2, 2], "counts": [0, 1, 3]})],
        sources=[source])
    assert result.payload is None
    refusal, = [r for r in result.refusals if r.code is RefusalCode.INVALID_PARAMETERS]
    assert refusal.detail["part_raster"] == [2, 2] and refusal.detail["extent_raster"] == [40, 60]


def test_a_partition_with_no_visible_part_contradicts_the_extent_it_partitions():
    source = forest()
    result = PT.produce_visible_inferred_partition(
        f"{FOREST}#court", [part(S.PartitionPart.INFERRED, instance_mask(source, "niche"))],
        sources=[source])
    assert result.payload is None
    assert any(r.code is RefusalCode.MISSING_EXTENT_INPUTS for r in result.refusals)


def test_the_unknown_part_is_a_real_third_part_and_its_absence_is_recorded():
    source = forest()
    result = PT.produce_visible_inferred_partition(
        f"{FOREST}#court", [part(S.PartitionPart.VISIBLE, instance_mask(source, "basin"))],
        sources=[source])
    missing = {o.what for o in result.omissions_for("part_not_supplied")}
    assert missing == {"inferred", "unknown"}
    assert "not the same as absent" in \
        [o.detail for o in result.omissions_for("part_not_supplied") if o.what == "unknown"][0]


def test_coverage_is_measured_off_the_mask_and_never_taken_from_the_caller():
    """A supplied coverage beside a supplied mask is two numbers that can disagree, and the schema
    checks their sum without being able to check either."""
    source = forest()
    result = PT.produce_visible_inferred_partition(
        f"{FOREST}#court",
        [PT.SuppliedPart(S.PartitionPart.VISIBLE, mask_rle=instance_mask(source, "basin"),
                         coverage=0.99)], sources=[source])
    region, = result.payload.regions
    assert region.coverage == 0.006667, "the mask says 0.0067; the caller said 0.99"


def test_cells_partitioned_is_the_raster_and_not_the_number_of_parts():
    source = forest()
    result = PT.produce_visible_inferred_partition(
        f"{FOREST}#court", [part(S.PartitionPart.VISIBLE, instance_mask(source, "basin"))],
        sources=[source])
    assert result.payload.cells_partitioned == 40 * 60


def test_partitioning_something_nobody_saw_is_a_question_with_no_answer():
    weak = extents("forest", basis="mask", status="uncertain")
    result = PT.produce_visible_inferred_partition(
        f"{FOREST}#court", [part(S.PartitionPart.VISIBLE, instance_mask(weak, "basin"))],
        sources=[weak])
    assert result.payload is None
    assert any(r.detail.get("input_status") == "uncertain" for r in result.refusals)


def test_no_model_produces_this_form_and_the_refusal_names_both_deferred_candidates():
    with pytest.raises(A.ModelNotAdmitted) as caught:
        A.producer_for(PT.FORM)
    assert caught.value.refusal.detail["verdicts"] == {"pix2gestalt": "defer",
                                                       "amodal_sam": "defer"}


# ── extent.density_field ─────────────────────────────────────────────────────


PIERS = "art_forms_piers"


def piers() -> SRC.ExtentSource:
    return SRC.extent_set(scene("piers"))


def all_keys(source: SRC.ExtentSource) -> List[str]:
    return list(source.keys())


def test_the_count_is_known_rather_than_estimated_which_is_what_the_model_could_not_do():
    source = piers()
    result = DN.produce_density_field(all_keys(source), sources=[source], field_shape=[4, 4])
    assert result.payload.counts_are_exact is True
    assert result.payload.members_counted == 5 == result.payload.samples_taken
    assert len(result.payload.members) == 5
    with pytest.raises(A.ModelNotAdmitted) as caught:
        A.producer_for(DN.FORM)
    assert caught.value.refusal.detail["verdicts"] == {"density_counter": "reject"}


def test_a_count_and_a_member_list_that_disagree_do_not_validate():
    source = piers()
    result = DN.produce_density_field(all_keys(source), sources=[source], field_shape=[4, 4])
    drifted = result.payload.model_dump()
    drifted["members_counted"] = 4
    with pytest.raises(ValidationError):
        S.ExtentDensityFieldPayload.model_validate(drifted)


@pytest.mark.parametrize("bandwidth", [0.5, 1.0, 2.0, 8.0])
def test_smoothing_moves_mass_and_does_not_make_it(bandwidth):
    """The arithmetic version of "a bandwidth choice may not read as a population". A truncated
    Gaussian loses whatever falls off the frame, so every kernel is renormalized over the cells it
    actually reaches — one member is worth one member wherever it stands."""
    source = piers()
    smoothed = DN.produce_density_field(all_keys(source), sources=[source], field_shape=[6, 6],
                                        kernel=DN.Kernel(DN.GAUSSIAN, bandwidth))
    assert smoothed.payload.field.statistics["sum"] == 5.0
    assert smoothed.payload.members_counted == 5


def test_a_wider_bandwidth_flattens_the_peak_without_changing_the_count():
    source = piers()
    tight = DN.produce_density_field(all_keys(source), sources=[source], field_shape=[6, 6],
                                     kernel=DN.Kernel(DN.GAUSSIAN, 0.5))
    wide = DN.produce_density_field(all_keys(source), sources=[source], field_shape=[6, 6],
                                    kernel=DN.Kernel(DN.GAUSSIAN, 4.0))
    assert tight.payload.field.statistics["peak"] > wide.payload.field.statistics["peak"]
    assert tight.payload.members_counted == wide.payload.members_counted
    assert tight.payload.smoothing.bandwidth == 0.5
    assert wide.payload.smoothing.bandwidth == 4.0


def test_smoothing_costs_the_calibration_because_the_numbers_stop_being_counts():
    source = piers()
    raw = DN.produce_density_field(all_keys(source), sources=[source], field_shape=[4, 4])
    assert raw.payload.field.calibration.state is S.CalibrationState.CALIBRATED
    assert raw.payload.field.calibration.units == DN.UNITS
    assert raw.payload.field.calibration.method and raw.payload.field.calibration.reference
    assert set(raw.payload.field.inline_values) <= {0.0, 1.0, 2.0, 3.0, 4.0, 5.0}

    smoothed = DN.produce_density_field(all_keys(source), sources=[source], field_shape=[4, 4],
                                        kernel=DN.Kernel(DN.GAUSSIAN, 1.0))
    assert smoothed.payload.field.calibration.state is S.CalibrationState.NOMINAL
    assert smoothed.payload.field.calibration.units is None


def test_a_smoothed_field_naming_a_derivation_that_does_no_smoothing_does_not_validate():
    source = piers()
    result = DN.produce_density_field(all_keys(source), sources=[source], field_shape=[4, 4],
                                      kernel=DN.Kernel(DN.GAUSSIAN, 1.0))
    assert result.payload.field.derivation is S.FieldDerivation.KERNEL_DENSITY
    lying = result.payload.model_dump()
    lying["field"]["derivation"] = "blur_of_binary_mask"
    with pytest.raises(ValidationError):
        S.ExtentDensityFieldPayload.model_validate(lying)


def test_smoothing_that_was_applied_names_its_method_and_its_bandwidth():
    with pytest.raises(ValidationError):
        S.SmoothingDeclaration(applied=True, method="gaussian", bandwidth=None)
    with pytest.raises(ValidationError):
        S.SmoothingDeclaration(applied=False, method="gaussian", bandwidth=1.0)


def test_counts_samples_and_smoothing_stay_three_separate_declarations():
    """A single `density` number answers none of the three questions they answer."""
    source = piers()
    result = DN.produce_density_field(all_keys(source) + ["art_elsewhere#ghost"],
                                      sources=[source], field_shape=[4, 4])
    assert result.payload.members_counted == 5
    assert result.payload.samples_taken == 5
    assert result.payload.smoothing.applied is False
    assert [o.what for o in result.omissions_for("endpoint_dangling")] == ["art_elsewhere#ghost"]


def test_a_field_with_no_cells_has_nowhere_to_count_into():
    source = piers()
    result = DN.produce_density_field(all_keys(source), sources=[source], field_shape=[0, 4])
    assert result.payload is None
    assert any(r.code is RefusalCode.INVALID_PARAMETERS for r in result.refusals)


def test_a_box_basis_source_is_admitted_here_and_drops_the_ceiling_rather_than_being_refused():
    """`extent.density_field` admits `box`, unlike `extent.fused_hypothesis`. The centre of a box
    and the centre of area of the mask inside it are different points, so the field is honest and
    coarser — and the ceiling says which."""
    boxes = extents("piers", basis="box", status="interpretive")
    result = DN.produce_density_field(all_keys(boxes), sources=[boxes], field_shape=[4, 4])
    assert result.payload is not None
    assert result.basis is EpistemicBasis.BOX
    assert result.ceiling is EpistemicStatus.INTERPRETIVE
    assert "box" in D.form(DN.FORM).admissible_bases


def test_the_same_members_counted_twice_produce_the_same_field():
    source = piers()
    one = DN.produce_density_field(all_keys(source), sources=[source], field_shape=[5, 5],
                                   kernel=DN.Kernel(DN.GAUSSIAN, 1.5))
    two = DN.produce_density_field(all_keys(source), sources=[source], field_shape=[5, 5],
                                   kernel=DN.Kernel(DN.GAUSSIAN, 1.5))
    assert one.payload.model_dump() == two.payload.model_dump()


# ── against Lane F's controls, whose answers are known by construction ───────


CONTROL_DIR = REPO_ROOT / "research" / "perception_lab" / "benchmarks" / "controls"
CONTROLS = json.loads((CONTROL_DIR / "manifest.json").read_text(encoding="utf-8"))["controls"]


def control_source(name: str, *, artifact_id: str = "art_control") -> SRC.ExtentSource:
    """One of Lane F's twelve, as an `extent_set` artifact these producers can read.

    THE MASKS ARE LANE F'S AND THE ENVELOPE IS LANE D'S. Built by replacing the payload of a
    committed artifact rather than typed out, so a change to the artifact envelope shows up in one
    place — and so the numbers below are checked against a control whose truth is known BY
    CONSTRUCTION rather than against whatever this producer happened to return.
    """
    control = CONTROLS[name]
    doc = copy.deepcopy(scene("forest"))
    doc["identity"]["artifact_id"] = artifact_id
    doc["identity"]["identity_refs"] = []
    doc["identity"]["identity_scope"] = "session"
    doc["measurement"]["payload"] = {
        "variant": "extent_set", "searched": control["what"],
        "instances": [{"instance_id": key, "mask_rle": rle, "box": None, "area": None,
                       "confidence": None, "naming": None, "region_id": None, "geometry_rev": 1}
                      for key, rle in control["instances"].items()],
        "dropped_below_min_area": None, "duplicates": [], "comparison": None}
    doc["provenance"]["source_image_digest"] = control["digest"]
    return SRC.extent_set(doc)


def test_the_containment_tree_control_comes_back_with_the_tree_it_was_drawn_with():
    """Lane F drew five rectangles whose nesting is known. This computes the same tree from the
    pixels, including the two roots — a forest, not a tree. A producer that forced a single root
    would have invented a container."""
    source = control_source("containment-tree")
    truth = CONTROLS["containment-tree"]["truth"]
    links = [HI.ProposedLink(f"art_control#{n['node_id']}",
                             None if n["parent_node_id"] is None
                             else f"art_control#{n['parent_node_id']}")
             for n in truth["nodes"]]
    result = HI.produce_extent_hierarchy(links, sources=[source])
    nodes = {n.instance.instance_id: n for n in result.payload.nodes}
    assert set(nodes) == {n["node_id"] for n in truth["nodes"]}
    by_id = {n.node_id: n.instance.instance_id for n in result.payload.nodes}
    parents = {k: (by_id[v.parent_node_id] if v.parent_node_id else None)
               for k, v in nodes.items()}
    assert parents == {n["node_id"]: n["parent_node_id"] for n in truth["nodes"]}
    assert len(result.payload.root_node_ids) == len(truth["root_node_ids"]) == 2


def test_the_occupancy_fractions_are_the_ones_lane_f_recorded():
    """The number the form exists for — how much of the courtyard IS garden — checked against a
    control that was drawn to have those fractions."""
    source = control_source("containment-tree")
    truth = CONTROLS["containment-tree"]["truth"]
    links = [HI.ProposedLink(f"art_control#{n['node_id']}",
                             None if n["parent_node_id"] is None
                             else f"art_control#{n['parent_node_id']}")
             for n in truth["nodes"]]
    result = HI.produce_extent_hierarchy(links, sources=[source])
    measured = {n.instance.instance_id: n.occupancy_of_parent
                for n in result.payload.nodes if n.occupancy_of_parent is not None}
    assert measured == truth["occupancy_of_parent"]


def test_the_false_similarity_control_refuses_the_grouping_appearance_would_give():
    """Three identical discs, two of which belong together. Lane F recorded both the legitimate
    grouping and the one an appearance threshold produces; this shows the producer keeping the
    first and refusing the second on the ground Lane C's verdict names."""
    source = control_source("false-similarity")
    truth = CONTROLS["false-similarity"]["truth"]
    legitimate = truth["legitimate_groupings"][0]["groups"][0]
    wrong = truth["similarity_would_give"][0]

    kept = FUS.produce_fused_hypothesis([FUS.ProposedFusion(
        "baseline", tuple(f"art_control#{k}" for k in legitimate),
        evidence=(geometry_ground("A and B rest on one baseline"),))], sources=[source])
    assert len(kept.payload.hypotheses) == 1
    assert [r.instance_id for r in kept.payload.hypotheses[0].members] == legitimate

    refused = FUS.produce_fused_hypothesis([FUS.ProposedFusion(
        "all_three_look_alike", tuple(f"art_control#{k}" for k in wrong),
        evidence=(model_ground(strength=0.947),))], sources=[source])
    assert refused.payload.hypotheses == []
    assert [o.what for o in refused.omissions_for("sole_ground_forbidden")] == \
        ["all_three_look_alike"]


def test_the_partition_control_keeps_the_three_parts_and_their_three_statuses():
    """A figure behind a bar, running off the frame. The inferred part is exact because the figure
    was drawn before the bar covered it; the unknown part is settled by nothing."""
    source = control_source("partition")
    truth = CONTROLS["partition"]["truth"]
    masks = {m.instance_id: m.mask_rle for m in source.members}
    result = PT.produce_visible_inferred_partition(
        "art_control#inst_visible",
        [part(S.PartitionPart.VISIBLE, masks["inst_visible"]),
         part(S.PartitionPart.INFERRED, masks["inst_inferred"]),
         part(S.PartitionPart.UNKNOWN, masks["inst_unknown"])],
        sources=[source])
    coverage = {r.part.value: r.coverage for r in result.payload.regions}
    assert coverage == {k: v["area_fraction"] for k, v in truth["parts"].items()}
    assert round(sum(coverage.values()), 6) == truth["coverage_sums_to"]
    statuses = {r.part.value: r.epistemic_status.value for r in result.payload.regions}
    assert statuses["visible"] == truth["parts"]["visible"]["epistemic_status"]
    assert statuses["inferred"] == statuses["unknown"] == "uncertain"


def test_the_density_control_counts_the_marks_lane_f_drew_by_splitting_them_first():
    """The piazza study's chain, end to end: one mask holding twenty-five marks, split into pieces
    by Lane B's exact fragment producer, counted by this lane's density field. The count is the
    count Lane F drew, and smoothing does not change it."""
    from backend.services.perception_lab import extent_forms as LB
    source = control_source("density-peaks")
    truth = CONTROLS["density-peaks"]["truth"]
    marks = {m.instance_id: m for m in source.members}["inst_marks"]

    pieces = LB.fragment_set(
        [LB.source_extent("art_control", {"instance_id": "inst_marks",
                                          "mask_rle": marks.mask_rle, "geometry_rev": 1})],
        source_image_digest=CONTROLS["density-peaks"]["digest"], measure_separation=False)
    assert len(pieces.payload.fragments) == truth["true_count"] == 25

    fragments = SRC.fragment_set(("art_marks", pieces.payload))
    keys = list(fragments.keys())
    raw = DN.produce_density_field(keys, sources=[fragments], field_shape=[8, 8])
    assert raw.payload.members_counted == 25
    assert raw.payload.field.statistics["sum"] == 25.0
    smoothed = DN.produce_density_field(keys, sources=[fragments], field_shape=[8, 8],
                                        kernel=DN.Kernel(DN.GAUSSIAN, 1.0))
    assert smoothed.payload.field.statistics["sum"] == 25.0
    assert smoothed.payload.field.calibration.state is S.CalibrationState.NOMINAL


def test_the_competing_extents_control_keeps_both_readings_and_names_no_winner():
    source = control_source("competing-extents")
    truth = CONTROLS["competing-extents"]["truth"]
    result = ALT.produce_hypothesis_set(
        "is the shadow part of the figure?",
        [ALT.Reading(r["reading_id"], weight=0.5,
                     member_keys=(f"art_control#{r['instance']}",),
                     evidence=(geometry_ground(r["why"]),))
         for r in truth["legitimate_readings"]],
        sources=[source])
    assert len(result.payload.alternatives) == len(truth["legitimate_readings"]) == 2
    assert result.ceiling is EpistemicStatus.UNCERTAIN
    assert "chosen" not in result.payload.model_dump()
    assert result.payload.weights_are_probabilities is False


def test_every_control_this_lane_computes_against_declares_the_form_it_was_used_for():
    """A control checked against a form it was not built for proves nothing about either."""
    used = {"containment-tree": "extent.hierarchy",
            "false-similarity": "extent.fused_hypothesis",
            "partition": "extent.visible_inferred_partition",
            "density-peaks": "extent.density_field",
            "competing-extents": "extent.hypothesis_set"}
    for control, form_key in used.items():
        assert form_key in CONTROLS[control]["forms"], control
