"""
PERCEPTUAL-FORMS-001A — the perceptual-form grammar, and the twenty-five things it must not allow.

WHY A SECOND TEST MODULE. `test_perception_lab_contracts.py` proves the vocabulary is ONE thing
across three runtimes. This proves the grammar built on top of it cannot say the specific
falsehoods it exists to prevent — that a blurred mask is a probability, that a set of fragments is
an object, that pixels nobody saw are visible, that a relation whose condition was dropped is a
measurement. Those are not parity failures. They are claims, and each one gets a test that makes
it.

EVERY TEST IS BOUND TO A DECLARED OBLIGATION. The contract's `form_grammar.test_obligations` is a
catalogue of twenty-five ids, and every registered form lists the ones it is held to.
`OBLIGATIONS` below maps each id to the test that discharges it, and
`test_every_declared_obligation_is_discharged_by_a_named_test` fails in both directions — an
obligation nothing tests, and a test claiming an obligation nobody declared. A form's declared
test obligations are otherwise a list of nice intentions.

THE MUTATION DISCIPLINE IS THE SAME ONE THE CONTRACT SUITE USES. Each law is shown catching a
specific break, because a law nothing fails on is a comment.

PURE. No database, no network, no model, no adapter. Reads the contract, the models and the
committed payload corpus, and nothing else.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from backend.schemas import perception_lab as S
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab.contracts import (CONTRACTS_DIR, form_index,
                                                       legacy_form_index, lab_contract)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = CONTRACTS_DIR / "fixtures" / "perception-lab"
MANIFEST = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
FORM_PAYLOADS = MANIFEST["form_payloads"]["by_form"]
JS_CONTRACT = (REPO_ROOT / "frontend" / "src" / "perceptionLab" / "contract"
               / "perceptionLabContract.js")

C = lab_contract()
FORMS = C["perceptual_forms"]

#: The records that existed before this grammar did, and must go on meaning what they meant.
#: Named rather than globbed: a witness that could quietly leave the list is not a witness.
PRE_GRAMMAR_ARTIFACTS = (
    "artifact.extent-set.json",
    "artifact.extent-set-manual.json",
    "artifact.extent-set-empty.json",
    "artifact.topology-relation-set.json",
    "artifact.topology-relation-set-box-basis.json",
    "artifact.negative-space-field.json",
    "artifact.refusal-missing-depth.json",
)


def fixture(name: str) -> Dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def payload_of(form_key: str) -> Dict[str, Any]:
    return fixture(FORM_PAYLOADS[form_key]["file"])


def artifact(**overrides: Any) -> Dict[str, Any]:
    """A valid `extent.hard_mask` artifact, as a mutable dict to break in specific ways."""
    doc = fixture("artifact.extent-set.json")
    for path, value in overrides.items():
        block, _, field = path.partition("__")
        doc[block][field] = value
    return doc


def refuses(doc: Dict[str, Any], pattern: str) -> None:
    """The mutation, and the sentence it must be refused with."""
    with pytest.raises(ValidationError) as exc:
        S.PerceptualArtifact.model_validate(doc)
    assert re.search(pattern, str(exc.value)), \
        f"refused, but not for the declared reason. Wanted /{pattern}/, got:\n{exc.value}"


# ── the obligations, and the tests that discharge them ───────────────────────

OBLIGATIONS = {
    "form_registry_is_closed":
        "test_an_unknown_form_raises_rather_than_returning_a_stub",
    "form_declares_producers_renderers_tests":
        "test_every_form_declares_a_producer_a_renderer_a_receipt_and_an_obligation",
    "absence_examined_field_is_required":
        "test_every_form_names_a_field_that_proves_something_looked",
    "payload_matches_declared_variant":
        "test_a_form_a_kind_and_a_payload_that_disagree_do_not_validate",
    "renderer_is_never_the_measurement":
        "test_no_payload_can_carry_the_drawing_of_itself",
    "parity_across_runtimes":
        "test_the_javascript_registers_the_same_nineteen_forms_and_the_same_ceilings",
    "legacy_records_remain_readable":
        "test_every_record_written_before_the_grammar_still_validates_and_still_means_it",
    "scalar_field_is_not_a_binary_mask":
        "test_a_scalar_field_cannot_be_supplied_or_stored_where_a_hard_mask_is_wanted",
    "blurred_mask_is_not_calibrated":
        "test_a_blurred_mask_may_not_declare_itself_calibrated",
    "inferred_pixels_are_not_visible":
        "test_the_inferred_part_of_a_partition_can_never_be_visible_or_measured",
    "fragment_set_asserts_no_unity":
        "test_a_fragment_set_has_no_field_in_which_fusion_could_be_claimed",
    "hypothesis_is_not_kept_by_confidence":
        "test_a_hypothesis_cannot_be_kept_or_promoted_at_any_confidence",
    "transition_cites_both_revisions":
        "test_a_transition_pins_both_endpoints_before_and_after",
    "conditional_relation_retains_its_hypothesis":
        "test_a_conditional_relation_whose_condition_was_dropped_does_not_validate",
    "derivation_declares_its_inputs":
        "test_a_derivation_that_names_no_input_derived_from_nothing",
    "partition_ceiling_caps_the_status":
        "test_the_partition_caps_the_claim_no_matter_how_good_the_basis_is",
    "rings_declare_their_winding":
        "test_a_ring_declares_which_side_is_inside_and_a_boundary_encloses_something",
    "holes_are_tied_to_an_outer_extent":
        "test_a_hole_names_the_extent_it_is_a_hole_of",
    "large_raster_carries_digest_and_coordinates":
        "test_a_raster_behind_a_pointer_carries_a_digest_a_shape_and_a_coordinate_system",
    "hierarchy_nodes_cite_revisions":
        "test_a_hierarchy_node_cites_a_revision_and_a_parent_chain_never_reaches_itself",
    "graph_edges_cite_endpoints":
        "test_every_edge_names_two_nodes_the_record_holds",
    "an_artifact_names_the_operation_that_produces_its_form":
        "test_an_artifact_may_not_name_an_operation_that_does_not_declare_its_kind",
    "a_deferred_form_is_never_written":
        "test_a_deferred_form_never_reaches_an_artifact",
    "every_form_payload_has_a_committed_example":
        "test_every_registered_form_has_a_payload_that_validates_and_says_it_looked",
    "unknown_projection_fails_closed":
        "test_a_projection_the_form_does_not_declare_is_refused_rather_than_drawn",
}


def test_every_declared_obligation_is_discharged_by_a_named_test():
    """Fails in both directions, and the second direction is the useful one.

    An obligation nothing tests is a promise in a JSON file. A test claiming an obligation nobody
    declared is a test measuring something this contract does not require, which is how a suite
    starts drifting away from the document it is supposed to enforce.
    """
    declared = set(C["form_grammar"]["test_obligations"])
    assert set(OBLIGATIONS) == declared, {
        "declared and untested": sorted(declared - set(OBLIGATIONS)),
        "tested and undeclared": sorted(set(OBLIGATIONS) - declared),
    }
    here = set(globals())
    missing = sorted(name for name in OBLIGATIONS.values() if name not in here)
    assert not missing, f"{missing} are named as discharging an obligation and do not exist"
    claimed = {o for f in FORMS for o in f["test_obligations"]}
    assert claimed == declared, \
        f"catalogue entries no form is held to: {sorted(declared - claimed)}"


# ── the registry ─────────────────────────────────────────────────────────────

def test_an_unknown_form_raises_rather_than_returning_a_stub():
    """FAIL CLOSED, the same way `operation()` does. A caller handed a stub renders a control."""
    assert list(D.forms()) == list(C["closed_sets"]["perceptual_forms"])
    assert len(D.forms()) == 19
    with pytest.raises(D.UnknownForm) as exc:
        D.form("extent.fog")
    assert "not a registered perceptual form" in str(exc.value)
    with pytest.raises(D.UnknownForm):
        D.form("")


@pytest.mark.parametrize("key", [f["key"] for f in FORMS])
def test_every_form_declares_a_producer_a_renderer_a_receipt_and_an_obligation(key):
    """A form that declares none of these is a word in a registry, not a capability."""
    form = D.form(key)
    assert form.producer_classes, "a form nothing could ever write is a word"
    assert set(form.producer_classes) <= set(C["closed_sets"]["producer_classes"])
    assert form.renderer_projections, "a measurement nobody can look at cannot be reviewed"
    for projection in form.renderer_projections:
        assert projection.kind in C["closed_sets"]["projection_kinds"]
        assert projection.mode in C["closed_sets"]["renderer_modes"]
    assert set(form.manual_tools) <= set(C["closed_sets"]["manual_tool_kinds"])
    assert set(form.comparison_methods) <= set(C["closed_sets"]["comparison_methods"])
    assert form.required_provenance
    assert set(form.required_provenance) <= set(S.ArtifactProvenance.model_fields)
    assert form.test_obligations, "a law nothing fails on is a comment"
    assert form.organ in ("extent", "topology")
    assert form.absence.empty_means


def test_forms_and_operations_are_two_registries_with_different_arities():
    """Not derived from each other, in either direction — which is the point of having both."""
    by_operation = {}
    for key, form in D.forms().items():
        for op in form.produced_by_operations:
            by_operation.setdefault(op, []).append(key)
    # one operation, several forms is expressible; today none does it, and the shape allows it
    assert all(len(v) == 1 for v in by_operation.values())
    # several operations, one form is the ordinary case
    assert len(D.form("extent.hard_mask").produced_by_operations) == 6
    # and a form with no operation at all is the case this phase depends on
    orphans = [k for k, f in D.forms().items() if not f.has_producer]
    assert len(orphans) == 16
    assert len(D.operations()) == 13


# ── absence, and the field that proves something looked ──────────────────────

@pytest.mark.parametrize("key", [f["key"] for f in FORMS])
def test_every_form_names_a_field_that_proves_something_looked(key):
    """`pairs_examined` generalised to all nineteen. An empty answer must be tellable from none."""
    form = D.form(key)
    model = S.FORM_PAYLOAD_MODELS[form.payload_variant]
    field = model.model_fields[form.absence.examined_field]
    assert field.is_required(), (
        f"{model.__name__}.{form.absence.examined_field} has a default, which answers 'did "
        f"anything look?' on behalf of a producer that never did")


def test_a_payload_with_no_count_is_not_an_empty_measurement():
    with pytest.raises(ValidationError):
        S.TopologyContactLocusPayload(variant="topology_contact_locus")
    measured_empty = S.TopologyContactLocusPayload(variant="topology_contact_locus",
                                                   pairs_examined=6)
    assert measured_empty.loci == [] and measured_empty.pairs_examined == 6


# ── the six blocks, under a form ─────────────────────────────────────────────

def test_a_form_a_kind_and_a_payload_that_disagree_do_not_validate():
    doc = artifact()
    doc["identity"]["form"] = "topology.pair_relation"
    refuses(doc, r"carried by artifact kind")

    doc = artifact()
    doc["identity"]["form"] = "extent.boundary_rings"
    refuses(doc, r"carried by artifact kind 'extent_boundary'")

    doc = artifact()
    doc["measurement"]["payload_variant"] = "extent_boundary"
    refuses(doc, r"payload_variant")


def test_no_payload_can_carry_the_drawing_of_itself():
    """A renderer is never the measurement, and the check is structural rather than reviewed."""
    forbidden = set(S.PROJECTION_HINT_KEYS) | {"projection_kind", "hints"}
    for variant, model in S.FORM_PAYLOAD_MODELS.items():
        stray = set(model.model_fields) & forbidden
        assert not stray, f"{model.__name__} carries {sorted(stray)}"
    # and every declared projection says whether the payload contains it
    direct = D.form("topology.contact_locus").projection("contact_band")
    derived = D.form("topology.pair_relation").projection("contact_band")
    assert direct.is_direct and not derived.is_direct, (
        "the same band is recorded by one form and recomputed for the other, and the registry is "
        "where a reader finds out which they are holding")


def test_every_operation_draws_only_what_its_form_declares_it_can():
    """The renderer registry and the form registry cannot drift apart."""
    for organ in C["organs"]:
        for op in organ.get("operations", ()):
            for kind in op["produces"]:
                form = D.form_for_artifact_kind(kind)
                if form is None:
                    continue
                drawable = {p.kind for p in form.renderer_projections}
                stray = set(op.get("render_projections", ())) - drawable
                assert not stray, f"{op['key']} draws {sorted(stray)}, {form.key} does not declare it"


def test_a_projection_the_form_does_not_declare_is_refused_rather_than_drawn():
    doc = artifact()
    doc["projection"]["projection_kind"] = "swatch"
    refuses(doc, r"is not one of them")

    doc = artifact()
    doc["projection"]["projection_kind"] = "not_a_projection"
    refuses(doc, r"projection_kind")

    # `none` is always allowed: an artifact that is not drawn tells no lie about how it looks.
    doc = artifact()
    doc["projection"]["projection_kind"] = "none"
    assert S.PerceptualArtifact.model_validate(doc)


# ── the states, and what may be written ──────────────────────────────────────

def test_a_deferred_form_never_reaches_an_artifact():
    doc = artifact()
    doc["identity"]["artifact_kind"] = "extent_soft_field"
    doc["identity"]["form"] = "extent.soft_field"
    doc["measurement"]["payload_variant"] = "extent_soft_field"
    doc["measurement"]["payload"] = payload_of("extent.soft_field")
    refuses(doc, r"produces|deferred")

    # The organ gate refuses it first, so the DEFERRED gate is put under the microscope on its own:
    # the kind is granted to the organ for the length of the test, which is exactly the edit a lane
    # that wanted to enable fog would make — and the answer is still no.
    extent = next(o for o in lab_contract()["organs"] if o["family"] == "extent")
    extent["produces_artifact_kinds"].append("extent_soft_field")
    try:
        refuses(doc, r"registered and deferred")
    finally:
        extent["produces_artifact_kinds"].remove("extent_soft_field")

    refusal = D.check_form_producible("extent.soft_field", operation_key="extent.find_all")
    assert refusal.code is S.RefusalCode.FORM_NOT_PRODUCIBLE
    assert "deferred" in refusal.message


def test_an_artifact_may_not_name_an_operation_that_does_not_declare_its_kind():
    """The gate that actually decides today, and the one that opens by itself.

    Sixteen forms have no operation, so sixteen have no artifact. The lane that enables one adds
    an operation declaring the kind — and this gate stops objecting, with no edit here.
    """
    doc = artifact()
    doc["identity"]["operation"] = "extent.compare"       # declared, and produces extent_set
    assert S.PerceptualArtifact.model_validate(doc)

    doc = artifact()
    doc["identity"]["organ_family"] = "topology"
    doc["identity"]["operation"] = "topology.negative_space"
    refuses(doc, r"produces|belongs to")

    experimental = D.form("extent.boundary_rings")
    assert experimental.state == "experimental" and not experimental.has_producer
    assert experimental.producible, "experimental means it needs a declaration, not a strategy"


def test_the_state_never_disagrees_with_the_operation_table():
    for key, form in D.forms().items():
        assert bool(form.produced_by_operations) == (form.state == "enabled"), key
    assert sum(1 for f in D.forms().values() if f.state == "enabled") == 3


# ── the partition: what act produced the claim ───────────────────────────────

def test_the_partition_caps_the_claim_no_matter_how_good_the_basis_is():
    """A perfect mask basis, and still an assertion about pixels nobody saw."""
    assert S.BASIS_CEILINGS[S.EpistemicBasis.MASK] is S.EpistemicStatus.MEASURED
    with pytest.raises(ValidationError) as exc:
        S.ArtifactMeasurement(
            payload_variant="extent_set", coordinate_system="mask_rle_hw",
            epistemic_status="measured", epistemic_basis="mask",
            partition="inferred_completion",
            payload={"variant": "extent_set", "searched": "the hidden legs"})
    assert "inferred_completion measurement" in str(exc.value)
    assert "uncertain" in str(exc.value)

    ok = S.ArtifactMeasurement(
        payload_variant="extent_set", coordinate_system="mask_rle_hw",
        epistemic_status="uncertain", epistemic_basis="mask", partition="inferred_completion",
        payload={"variant": "extent_set", "searched": "the hidden legs"})
    assert ok.epistemic_status is S.EpistemicStatus.UNCERTAIN

    # the composing runtime's third cap: never stronger than the weakest input
    assert D.derived_ceiling("topology.containment_tree", basis="mask",
                             partition="exact_derivation",
                             input_statuses=["measured", "interpretive"]) == "interpretive"
    assert D.derived_ceiling("topology.containment_tree", basis="mask",
                             partition="exact_derivation") == "measured"


def test_a_derivation_that_names_no_input_derived_from_nothing():
    # `extent.hard_mask` admits only `visible_measured`, so the admissibility gate would refuse
    # first and this rule would never be reached. Admitting the partition for the length of the
    # test is what puts the rule itself under the microscope rather than the order of the gates.
    declaration = form_index()["extent.hard_mask"]
    declaration["admissible_partitions"].append("exact_derivation")
    try:
        doc = artifact()
        doc["measurement"]["partition"] = "exact_derivation"
        doc["identity"]["input_refs"] = []
        refuses(doc, r"cites no input")
    finally:
        declaration["admissible_partitions"].remove("exact_derivation")

    doc = artifact()
    doc["measurement"]["partition"] = "visible_measured"
    doc["identity"]["input_refs"] = []
    assert S.PerceptualArtifact.model_validate(doc), \
        "a direct measurement of the image derives from no artifact, and that is not a defect"


def test_a_partition_the_form_does_not_admit_is_refused():
    doc = artifact()
    doc["measurement"]["partition"] = "unresolved_alternative"
    doc["measurement"]["epistemic_status"] = "uncertain"
    refuses(doc, r"admits the partitions")


def test_the_inferred_part_of_a_partition_can_never_be_visible_or_measured():
    payload = copy.deepcopy(payload_of("extent.visible_inferred_partition"))
    assert S.ExtentPartitionPayload.model_validate(payload)
    for status in ("measured", "visible"):
        broken = copy.deepcopy(payload)
        broken["regions"][1]["epistemic_status"] = status
        with pytest.raises(ValidationError) as exc:
            S.ExtentPartitionPayload.model_validate(broken)
        assert "Pixels nobody saw" in str(exc.value)
    # and the unknown part abstains entirely
    broken = copy.deepcopy(payload)
    broken["regions"][2]["epistemic_status"] = "interpretive"
    with pytest.raises(ValidationError):
        S.ExtentPartitionPayload.model_validate(broken)


# ── grouping, fusion and hypotheses ──────────────────────────────────────────

def test_a_fragment_set_has_no_field_in_which_fusion_could_be_claimed():
    payload = copy.deepcopy(payload_of("extent.fragment_set"))
    assert S.ExtentFragmentSetPayload.model_validate(payload).unity_asserted is False
    with pytest.raises(ValidationError):
        S.ExtentFragmentSetPayload.model_validate({**payload, "unity_asserted": True})
    with pytest.raises(ValidationError):
        S.ExtentFragmentSetPayload.model_validate({**payload, "is_one_object": True})
    assert "unity" not in str(set(S.ExtentSetPayload.model_fields))


def test_a_fusion_hypothesis_enumerates_its_grounds_and_stays_below_measured():
    payload = copy.deepcopy(payload_of("extent.fused_hypothesis"))
    assert S.ExtentFusionHypothesisPayload.model_validate(payload)

    no_grounds = copy.deepcopy(payload)
    no_grounds["hypotheses"][0]["grounds"] = []
    with pytest.raises(ValidationError):
        S.ExtentFusionHypothesisPayload.model_validate(no_grounds)

    promoted = copy.deepcopy(payload)
    promoted["hypotheses"][0]["epistemic_status"] = "measured"
    with pytest.raises(ValidationError) as exc:
        S.ExtentFusionHypothesisPayload.model_validate(promoted)
    assert "inferred_completion hypothesis" in str(exc.value)

    relabelled = copy.deepcopy(payload)
    relabelled["hypotheses"][0]["partition"] = "visible_measured"
    with pytest.raises(ValidationError) as exc:
        S.ExtentFusionHypothesisPayload.model_validate(relabelled)
    assert "the members being measured does not make the grouping measured" in str(exc.value)


def test_a_hypothesis_cannot_be_kept_or_promoted_at_any_confidence():
    """Exercised through the gate, with a form temporarily marked as carrying one.

    Every hypothesis-carrying form is deferred today, so the deferred gate would fire first and
    this rule would never be reached by a fixture. Marking `extent.hard_mask` as hypothesis-
    carrying for the length of the test is what puts the gate itself under the microscope rather
    than the ordering of the gates.
    """
    registry = form_index()
    declaration = registry["extent.hard_mask"]
    declaration["carries_hypothesis"] = True
    try:
        for status in ("kept", "promoted"):
            doc = artifact()
            doc["lifecycle"]["status"] = status
            refuses(doc, r"carries a hypothesis and may not be")
        for status in ("proposed", "edited", "rejected"):
            doc = artifact()
            doc["lifecycle"]["status"] = status
            assert S.PerceptualArtifact.model_validate(doc)
    finally:
        declaration["carries_hypothesis"] = False
    assert S.PerceptualArtifact.model_validate(artifact())

    # and confidence changes nothing: the weight lives on the alternative, not on the lifecycle
    payload = copy.deepcopy(payload_of("extent.hypothesis_set"))
    payload["alternatives"][0]["weight"] = 0.99
    assert S.ExtentHypothesisSetPayload.model_validate(payload)
    assert "chosen" not in S.ExtentHypothesisSetPayload.model_fields
    assert "resolved" not in S.ExtentHypothesisSetPayload.model_fields


def test_one_alternative_is_not_an_alternative_set():
    payload = copy.deepcopy(payload_of("extent.hypothesis_set"))
    payload["alternatives"] = payload["alternatives"][:1]
    with pytest.raises(ValidationError) as exc:
        S.ExtentHypothesisSetPayload.model_validate(payload)
    assert "preserved ambiguity" in str(exc.value)


# ── fields, and what their numbers mean ──────────────────────────────────────

def test_a_scalar_field_cannot_be_supplied_or_stored_where_a_hard_mask_is_wanted():
    """Three ways it is stopped, because one would be a convention rather than a shape."""
    # 1. There is nowhere in a soft field to put a mask, and nowhere in an instance to put a field.
    assert "mask_rle" not in S.ExtentSoftFieldPayload.model_fields
    assert "mask_rle" not in S.ScalarFieldSpec.model_fields
    with pytest.raises(ValidationError):
        S.ExtentInstance(instance_id="inst_1", field={"field_shape": [2, 2]})

    # 2. The registry refuses the supply, and it is NOT `unknown_reference`.
    refusal = D.check_input_forms("extent.boundary_rings", ["extent.soft_field"],
                                  operation_key="extent.refine")
    assert refusal.code is S.RefusalCode.UNSUPPORTED_FORM
    assert refusal.detail["accepted"] == ["extent.hard_mask"]
    assert D.check_input_forms("extent.boundary_rings", ["extent.hard_mask"]) is None

    # 3. A form that accepts nothing accepts nothing — it looks at the image.
    assert D.form("extent.hard_mask").accepted_input_forms == ()
    assert D.check_input_forms("extent.hard_mask", ["extent.hard_mask"]) is not None


def test_a_blurred_mask_may_not_declare_itself_calibrated():
    base = copy.deepcopy(payload_of("extent.soft_field"))
    assert S.ExtentSoftFieldPayload.model_validate(base)

    blurred = copy.deepcopy(base)
    blurred["field"]["derivation"] = "blur_of_binary_mask"
    with pytest.raises(ValidationError) as exc:
        S.ExtentSoftFieldPayload.model_validate(blurred)
    assert "read downstream as a probability" in str(exc.value)

    # the honest version of the same field
    blurred["field"]["calibration"] = {"state": "nominal", "method": None, "reference": None,
                                       "units": "distance from a decided edge, in cells"}
    assert S.ExtentSoftFieldPayload.model_validate(blurred)

    # and `calibrated` without a method or a reference is a word
    for missing in ("method", "reference"):
        bare = copy.deepcopy(base)
        bare["field"]["calibration"][missing] = None
        with pytest.raises(ValidationError) as exc:
            S.ExtentSoftFieldPayload.model_validate(bare)
        assert "calibrated AGAINST" in str(exc.value)


def test_a_raster_behind_a_pointer_carries_a_digest_a_shape_and_a_coordinate_system():
    spec = {"field_shape": [64, 64], "coordinate_system": "mask_rle_hw",
            "value_range": [0.0, 1.0], "derivation": "distance_transform",
            "calibration": {"state": "nominal"},
            "data_ref": {"uri": "semant://fields/f_1", "digest": "sha256:abcd1234",
                         "media_type": "application/octet-stream", "bytes": 4096}}
    assert S.ScalarFieldSpec.model_validate(spec)

    no_digest = copy.deepcopy(spec)
    del no_digest["data_ref"]["digest"]
    with pytest.raises(ValidationError):
        S.ScalarFieldSpec.model_validate(no_digest)

    no_coordinates = copy.deepcopy(spec)
    del no_coordinates["coordinate_system"]
    with pytest.raises(ValidationError):
        S.ScalarFieldSpec.model_validate(no_coordinates)

    both = copy.deepcopy(spec)
    both["inline_values"] = [0.0] * 4096
    with pytest.raises(ValidationError) as exc:
        S.ScalarFieldSpec.model_validate(both)
    assert "exactly one of inline_values / data_ref" in str(exc.value)

    neither = copy.deepcopy(spec)
    del neither["data_ref"]
    with pytest.raises(ValidationError):
        S.ScalarFieldSpec.model_validate(neither)

    wrong_length = copy.deepcopy(spec)
    del wrong_length["data_ref"]
    wrong_length["inline_values"] = [0.1, 0.2]
    with pytest.raises(ValidationError) as exc:
        S.ScalarFieldSpec.model_validate(wrong_length)
    assert "needs 4096 values" in str(exc.value)


def test_a_density_field_keeps_counts_samples_and_smoothing_apart():
    base = copy.deepcopy(payload_of("extent.density_field"))
    assert S.ExtentDensityFieldPayload.model_validate(base)

    miscounted = copy.deepcopy(base)
    miscounted["members_counted"] = 9
    with pytest.raises(ValidationError) as exc:
        S.ExtentDensityFieldPayload.model_validate(miscounted)
    assert "members are listed" in str(exc.value)

    mislabelled = copy.deepcopy(base)
    mislabelled["field"]["derivation"] = "direct_probability"
    with pytest.raises(ValidationError) as exc:
        S.ExtentDensityFieldPayload.model_validate(mislabelled)
    assert "two different rasters" in str(exc.value)

    bare_smoothing = copy.deepcopy(base)
    bare_smoothing["smoothing"] = {"applied": True, "method": None, "bandwidth": None}
    with pytest.raises(ValidationError):
        S.ExtentDensityFieldPayload.model_validate(bare_smoothing)


# ── boundaries, holes, hierarchies and graphs ────────────────────────────────

def test_a_ring_declares_which_side_is_inside_and_a_boundary_encloses_something():
    base = copy.deepcopy(payload_of("extent.boundary_rings"))
    parsed = S.ExtentBoundaryPayload.model_validate(base)
    assert {r.winding for r in parsed.boundaries[0].rings} == {S.RingWinding.OUTER,
                                                               S.RingWinding.INNER}

    guessed = copy.deepcopy(base)
    del guessed["boundaries"][0]["rings"][0]["winding"]
    with pytest.raises(ValidationError):
        S.ExtentBoundaryPayload.model_validate(guessed)

    holes_only = copy.deepcopy(base)
    holes_only["boundaries"][0]["rings"][0]["winding"] = "inner"
    with pytest.raises(ValidationError) as exc:
        S.ExtentBoundaryPayload.model_validate(holes_only)
    assert "encloses nothing" in str(exc.value)

    miscounted = copy.deepcopy(base)
    miscounted["rings_traced"] = 7
    with pytest.raises(ValidationError) as exc:
        S.ExtentBoundaryPayload.model_validate(miscounted)
    assert "not a summary that may drift" in str(exc.value)


def test_a_hole_names_the_extent_it_is_a_hole_of():
    base = copy.deepcopy(payload_of("extent.hole_set"))
    parsed = S.ExtentHoleSetPayload.model_validate(base)
    assert parsed.holes[0].outer.instance_id == "inst_1"
    assert parsed.holes[0].enclosed is True

    orphan = copy.deepcopy(base)
    del orphan["holes"][0]["outer"]
    with pytest.raises(ValidationError):
        S.ExtentHoleSetPayload.model_validate(orphan)

    undecided = copy.deepcopy(base)
    del undecided["holes"][0]["enclosed"]
    with pytest.raises(ValidationError):
        S.ExtentHoleSetPayload.model_validate(undecided)

    shapeless = copy.deepcopy(base)
    shapeless["holes"][0]["mask_rle"] = None
    shapeless["holes"][0]["rings"] = []
    with pytest.raises(ValidationError) as exc:
        S.ExtentHoleSetPayload.model_validate(shapeless)
    assert "claim without a shape" in str(exc.value)


def test_a_hierarchy_node_cites_a_revision_and_a_parent_chain_never_reaches_itself():
    base = copy.deepcopy(payload_of("extent.hierarchy"))
    parsed = S.ExtentHierarchyPayload.model_validate(base)
    assert parsed.nodes[0].instance.geometry_rev == 0
    assert parsed.root_node_ids == ["palace"]

    unpinned = copy.deepcopy(base)
    del unpinned["nodes"][0]["instance"]["geometry_rev"]
    with pytest.raises(ValidationError):
        S.ExtentHierarchyPayload.model_validate(unpinned)

    cyclic = copy.deepcopy(base)
    cyclic["nodes"][0]["parent_node_id"] = "fountain"
    cyclic["root_node_ids"] = []
    with pytest.raises(ValidationError) as exc:
        S.ExtentHierarchyPayload.model_validate(cyclic)
    assert "cycle" in str(exc.value)

    dangling = copy.deepcopy(base)
    dangling["nodes"][1]["parent_node_id"] = "not_a_node"
    with pytest.raises(ValidationError) as exc:
        S.ExtentHierarchyPayload.model_validate(dangling)
    assert "this record does not hold" in str(exc.value)

    both_identities = copy.deepcopy(base)
    both_identities["nodes"][0]["region"] = {"region_id": "reg_1", "geometry_rev": 0,
                                             "scope": "canonical"}
    with pytest.raises(ValidationError) as exc:
        S.ExtentHierarchyPayload.model_validate(both_identities)
    assert "exactly one of instance / region" in str(exc.value)


def test_every_edge_names_two_nodes_the_record_holds():
    base = copy.deepcopy(payload_of("topology.adjacency_graph"))
    assert S.TopologyAdjacencyGraphPayload.model_validate(base)

    stray = copy.deepcopy(base)
    stray["edges"][0]["target_node_id"] = "pier_9"
    with pytest.raises(ValidationError) as exc:
        S.TopologyAdjacencyGraphPayload.model_validate(stray)
    assert "does not hold" in str(exc.value)

    loop = copy.deepcopy(base)
    loop["edges"][0]["target_node_id"] = loop["edges"][0]["source_node_id"]
    with pytest.raises(ValidationError) as exc:
        S.TopologyAdjacencyGraphPayload.model_validate(loop)
    assert "not a relation between two extents" in str(exc.value)

    # the same rule for the tree
    tree = copy.deepcopy(payload_of("topology.containment_tree"))
    assert S.TopologyContainmentTreePayload.model_validate(tree)
    tree["nodes"][1]["parent_node_id"] = "nowhere"
    with pytest.raises(ValidationError):
        S.TopologyContainmentTreePayload.model_validate(tree)


# ── transitions and conditional relations ────────────────────────────────────

def test_a_transition_pins_both_endpoints_before_and_after():
    base = copy.deepcopy(payload_of("topology.transition"))
    parsed = S.TopologyTransitionPayload.model_validate(base)
    transition = parsed.transitions[0]
    assert transition.before.source.geometry_rev == 0
    assert transition.after.source.geometry_rev == 1
    assert transition.before.target.geometry_rev == transition.after.target.geometry_rev

    unpinned = copy.deepcopy(base)
    del unpinned["transitions"][0]["before"]["source"]["geometry_rev"]
    with pytest.raises(ValidationError):
        S.TopologyTransitionPayload.model_validate(unpinned)

    unchanged = copy.deepcopy(base)
    unchanged["transitions"][0]["after"]["source"]["geometry_rev"] = 0
    with pytest.raises(ValidationError) as exc:
        S.TopologyTransitionPayload.model_validate(unchanged)
    assert "measured twice, not a transition" in str(exc.value)

    two_pairs = copy.deepcopy(base)
    two_pairs["transitions"][0]["after"]["source"]["instance_id"] = "inst_9"
    with pytest.raises(ValidationError) as exc:
        S.TopologyTransitionPayload.model_validate(two_pairs)
    assert "not two pairs" in str(exc.value)

    mislabelled = copy.deepcopy(base)
    mislabelled["transitions"][0]["change"] = "unchanged"
    with pytest.raises(ValidationError) as exc:
        S.TopologyTransitionPayload.model_validate(mislabelled)
    assert "the record says unchanged" in str(exc.value)


def test_a_conditional_relation_whose_condition_was_dropped_does_not_validate():
    base = copy.deepcopy(payload_of("topology.uncertain_relation_set"))
    assert S.TopologyUncertainRelationsPayload.model_validate(base)

    orphaned = copy.deepcopy(base)
    orphaned["relations"][0]["conditioned_on"] = "alt_nobody_declared"
    with pytest.raises(ValidationError) as exc:
        S.TopologyUncertainRelationsPayload.model_validate(orphaned)
    assert "dropped condition reads as a measurement" in str(exc.value)

    unconditioned = copy.deepcopy(base)
    del unconditioned["relations"][0]["conditioned_on"]
    with pytest.raises(ValidationError):
        S.TopologyUncertainRelationsPayload.model_validate(unconditioned)

    promoted = copy.deepcopy(base)
    promoted["relations"][0]["epistemic_status"] = "measured"
    with pytest.raises(ValidationError) as exc:
        S.TopologyUncertainRelationsPayload.model_validate(promoted)
    assert "may not be measured" in str(exc.value)

    no_hypothesis = copy.deepcopy(base)
    no_hypothesis["hypotheses"] = []
    with pytest.raises(ValidationError):
        S.TopologyUncertainRelationsPayload.model_validate(no_hypothesis)


# ── the payload corpus, and the records that came before it ──────────────────

@pytest.mark.parametrize("key", [f["key"] for f in FORMS])
def test_every_registered_form_has_a_payload_that_validates_and_says_it_looked(key):
    entry = FORM_PAYLOADS[key]
    form = D.form(key)
    assert entry["variant"] == form.payload_variant
    payload = S.FORM_PAYLOAD_MODELS[form.payload_variant].model_validate(fixture(entry["file"]))
    assert payload.variant == form.payload_variant
    assert getattr(payload, form.absence.examined_field) is not None


@pytest.mark.parametrize("name", PRE_GRAMMAR_ARTIFACTS)
def test_every_record_written_before_the_grammar_still_validates_and_still_means_it(name):
    """The read direction, on records nobody has touched. This is the whole compatibility claim."""
    doc = fixture(name)
    assert "form" not in doc["identity"], \
        f"{name} was back-filled, and a back-filled witness proves nothing about old records"
    assert "partition" not in doc["measurement"]
    parsed = S.PerceptualArtifact.model_validate(doc)
    assert parsed.identity.form is None
    assert parsed.measurement.partition is None
    if parsed.identity.artifact_kind is S.ArtifactKind.REFUSAL:
        assert parsed.effective_form is None, "a refusal is in no perceptual form"
        assert parsed.form_declaration is None
    else:
        expected = legacy_form_index()[parsed.identity.artifact_kind.value]
        assert parsed.effective_form is S.PerceptualForm(expected)
        assert parsed.form_declaration["key"] == expected


def test_the_legacy_table_covers_exactly_the_kinds_that_predate_the_grammar():
    assert set(legacy_form_index()) == {"extent_set", "topology_relation_set",
                                        "negative_space_field"}
    for kind, key in legacy_form_index().items():
        assert D.form(key).artifact_kind == kind
        assert D.form(key).state == "enabled"


def test_a_new_kind_may_not_leave_its_form_unstated():
    doc = artifact()
    doc["identity"]["artifact_kind"] = "extent_boundary"
    doc["measurement"]["payload_variant"] = "extent_boundary"
    doc["measurement"]["payload"] = payload_of("extent.boundary_rings")
    refuses(doc, r"must declare its `identity.form`")


# ── the two runtimes ─────────────────────────────────────────────────────────

def test_the_javascript_registers_the_same_nineteen_forms_and_the_same_ceilings():
    """Read out of the JS source rather than executed, so this suite needs no node.

    The JS suite proves the same thing from the other side by running the validators. What is
    checked here is that the JavaScript reaches for the CONTRACT's tables rather than retyping
    them — a retyped ceiling is a ceiling that can be softened in one runtime only.
    """
    js = JS_CONTRACT.read_text(encoding="utf-8")
    for name in ("perceptual_forms", "form_states", "producer_classes", "epistemic_partitions",
                 "renderer_modes", "comparison_methods", "field_derivations",
                 "calibration_states", "ground_kinds", "ring_windings", "partition_parts",
                 "transition_changes"):
        assert f"set('{name}')" in js, f"the JS mirror does not read `{name}` from the contract"
    assert "CONTRACT.perceptual_forms" in js
    assert "CONTRACT.form_grammar.epistemic_partitions.ceilings" in js
    assert "CONTRACT.form_grammar.compatibility.legacy_form_for_kind" in js
    for symbol in ("validateFormPayload", "checkInputForms", "checkFormProducible",
                   "effectiveForm", "derivedCeiling", "formHasProducer"):
        assert f"function {symbol}" in js or f"const {symbol}" in js, \
            f"the JS mirror does not export {symbol}"
    # no ceiling table retyped as a literal on the JavaScript side
    assert not re.search(r"inferred_completion:\s*'", js), (
        "a partition ceiling is written as a literal in JavaScript; it must be read from the "
        "contract, or it can be softened in one runtime only")


def test_the_partition_ceilings_are_the_contract_s_and_not_a_second_copy():
    declared = C["form_grammar"]["epistemic_partitions"]["ceilings"]
    for partition, ceiling in S.PARTITION_CEILINGS.items():
        assert declared[partition.value] == ceiling.value
    assert S.INFERRING_PARTITIONS == {S.EpistemicPartition.INFERRED_COMPLETION,
                                      S.EpistemicPartition.UNRESOLVED_ALTERNATIVE}
    for partition in S.INFERRING_PARTITIONS:
        assert S.PARTITION_CEILINGS[partition] is S.EpistemicStatus.UNCERTAIN


def test_the_form_registry_reaches_the_generated_record_schemas():
    """`perceptual-artifact.schema.json` is what a runtime with no Pydantic validates against."""
    schema = json.loads((REPO_ROOT / "research" / "perception_lab" / "schemas"
                         / "perceptual-artifact.schema.json").read_text(encoding="utf-8"))
    text = json.dumps(schema)
    for key in C["closed_sets"]["perceptual_forms"]:
        assert key in text, f"{key} does not appear in the generated artifact schema"
    for variant in C["closed_sets"]["payload_variants"]:
        assert variant in text
