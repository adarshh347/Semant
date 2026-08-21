"""
PERCEPTUAL-ORGANS-002 Lane A — the Perception Lab contract, and the parity that keeps it one thing.

The backend half of the cross-language gate. Its twin is
`frontend/src/perceptionLab/contract/perceptionLab.parity.test.js`, and between them they close
the loop the same way `test_inquiry_contracts.py` does for the action grammar:

    JS resolver  → committed fixture → recomputed HERE by the Python resolver
    Python gates → committed fixture → recomputed THERE by the JavaScript gates

Neither direction goes through a third validator, because a third validator is the thing a shared
contract exists to prevent. Both fixtures are committed, and both regenerate visibly with
UPDATE_PARITY_FIXTURES=1.

The mutation tests are the other half of the file. Each one BREAKS a specific law and asserts the
break is caught, because a law nothing fails on is a comment.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from backend.schemas import perception_lab as S
from backend.services import epistemics
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab.contracts import (CONTRACTS_DIR, LAB_FILE,
                                                       LAB_SCHEMA_VERSION, ContractError,
                                                       lab_contract, load)

REPO_ROOT = Path(__file__).resolve().parents[2]
MIRROR_DIR = REPO_ROOT / "frontend" / "src" / "contracts"
FIXTURE_DIR = CONTRACTS_DIR / "fixtures" / "perception-lab"
MANIFEST = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
SYNC_SCRIPT = REPO_ROOT / "scripts" / "contracts_sync.py"
SCHEMA_SCRIPT = REPO_ROOT / "scripts" / "perception_lab_schemas.py"

#: Written by the JS suite, recomputed here. See the module docstring.
JS_RESOLVER_FIXTURE = FIXTURE_DIR / "js-resolver.parameters.json"
#: Written here, recomputed by the JS suite.
PY_GATES_FIXTURE = FIXTURE_DIR / "py-gates.refusals.json"

C = lab_contract()


def _fixture(name: str) -> Dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _artifact(name: str = "artifact.extent-set.json") -> Dict[str, Any]:
    return _fixture(name)


# ── the contract loads, at the version this code enforces ────────────────────

def test_the_contract_loads_at_the_declared_version():
    assert S.SCHEMA_VERSION == LAB_SCHEMA_VERSION == "perception-lab.v1"
    assert C["schema_version"] == LAB_SCHEMA_VERSION


def test_a_contract_at_the_wrong_version_is_refused_rather_than_read():
    with pytest.raises(ContractError) as exc:
        load(LAB_FILE, "perception-lab.v2")
    assert "v2" in str(exc.value)


def test_a_missing_contract_raises_rather_than_falling_back():
    # There is no fallback registry, deliberately. One would be a second organ vocabulary invented
    # at the moment the first went missing, indistinguishable from the real one until it disagreed.
    with pytest.raises(ContractError):
        load("no-such-contract.v1.json", "anything")


# ── the frontend mirror ──────────────────────────────────────────────────────

def test_the_frontend_mirror_is_byte_identical_to_the_canonical_contract():
    """The mirror exists ONLY because the Vercel deploy uploads `frontend/` as its source."""
    canonical = (CONTRACTS_DIR / LAB_FILE).read_bytes()
    mirror = MIRROR_DIR / LAB_FILE
    fix = "run python scripts/contracts_sync.py"
    assert mirror.exists(), f"frontend/src/contracts/{LAB_FILE} is missing — {fix}"
    assert mirror.read_bytes() == canonical, \
        f"frontend/src/contracts/{LAB_FILE} has drifted from contracts/{LAB_FILE} — {fix}"


def test_the_sync_script_reports_the_tree_as_in_sync():
    result = subprocess.run([sys.executable, str(SYNC_SCRIPT), "--check"],
                            capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_generated_record_schemas_are_in_sync():
    result = subprocess.run([sys.executable, str(SCHEMA_SCRIPT), "--check"],
                            capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert result.returncode == 0, result.stdout + result.stderr


# ── the closed sets are the contract's, not retyped ──────────────────────────

@pytest.mark.parametrize("set_name,enum_cls", [
    ("organ_families", S.OrganFamily), ("session_modes", S.SessionMode),
    ("planner_identities", S.PlannerIdentity), ("execution_identities", S.ExecutionIdentity),
    ("run_outcomes", S.RunOutcome), ("stage_states", S.StageState),
    ("lifecycle_states", S.LifecycleState), ("review_verdicts", S.ReviewVerdict),
    ("epistemic_bases", S.EpistemicBasis), ("artifact_kinds", S.ArtifactKind),
    ("identity_scopes", S.IdentityScope), ("producer_kinds", S.ProducerKind),
    ("capability_states", S.CapabilityState), ("coordinate_systems", S.CoordinateSystem),
    ("label_sources", S.LabelSource), ("refusal_codes", S.RefusalCode),
    ("projection_kinds", S.ProjectionKind), ("manual_tool_kinds", S.ManualToolKind),
    ("relation_kinds", S.RelationKind),
])
def test_every_python_enum_equals_its_closed_set(set_name, enum_cls):
    assert tuple(C["closed_sets"][set_name]) == tuple(m.value for m in enum_cls)


def test_the_epistemic_vocabulary_is_the_existing_one_and_not_a_second_copy():
    """The lab does not own `EpistemicStatus`. It reuses it, and this is where that is proved."""
    assert S.EpistemicStatus is epistemics.EpistemicStatus
    assert tuple(C["closed_sets"]["epistemic_statuses"]) \
        == tuple(m.value for m in epistemics.EpistemicStatus)


def test_the_mask_and_box_ceilings_are_the_wave25_ruling_verbatim():
    """A box containment of 1.000 is a reading. That ruling is `epistemics.SUBSTRATE_CEILING`'s,
    and the lab may not soften it by declaring a different ceiling for the same substrate."""
    for basis, ceiling in epistemics.SUBSTRATE_CEILING.items():
        assert C["epistemics"]["basis_ceilings"][basis] == ceiling.value
        assert S.BASIS_CEILINGS[S.EpistemicBasis(basis)] is ceiling


def test_a_contract_whose_closed_set_moved_fails_at_import_not_in_a_validator():
    # The compensation for declaring the enums twice. Simulated by asking the assertion helper to
    # compare against a set that has drifted.
    import backend.schemas.perception_lab as mod
    original = mod.closed_set
    try:
        mod.closed_set = lambda name: (("nonsense",) if name == "run_outcomes" else original(name))
        with pytest.raises(ContractError) as exc:
            mod._assert_parity()
        assert "run_outcomes" in str(exc.value)
    finally:
        mod.closed_set = original
    mod._assert_parity()          # and the real tree still passes


# ── eight organs, two of them enabled ────────────────────────────────────────

def test_all_eight_organ_families_are_registered():
    assert len(D.organs()) == 8
    assert set(D.organs()) == {"extent", "topology", "colour", "illumination",
                               "surface_pattern", "orientation_flow", "depth", "surface_form"}


def test_exactly_extent_and_topology_are_enabled():
    assert [o.family for o in D.enabled_organs()] == ["extent", "topology"]
    assert set(S.ENABLED_ORGAN_FAMILIES) == {"extent", "topology"}


def test_a_deferred_organ_declares_no_capability_it_does_not_have():
    """The emptiness IS the deliverable. A deferred organ with adapters would be a catalogue entry
    a person could click, and clicking it would be the first lie the laboratory told."""
    for organ in D.organs().values():
        if organ.enabled:
            continue
        assert organ.availability == "deferred"
        assert organ.operations == ()
        assert organ.adapters == ()
        assert organ.manual_tools == ()
        assert organ.render_projections == ()
        assert organ.prompt_examples == ()
        assert organ.produces_artifact_kinds == ()
        assert organ.epistemic_ceiling is None, \
            "a disabled organ declaring an epistemic ceiling is claiming a quality of evidence " \
            "it has no producer for"


def test_an_enabled_organ_declares_a_ceiling_and_a_question():
    for organ in D.enabled_organs():
        assert organ.epistemic_ceiling in {m.value for m in S.EpistemicStatus}
        assert organ.question.endswith("?")
        assert organ.operations, "an enabled organ with no operations is a switch with no wire"


def test_the_enabled_set_and_the_organ_flags_must_be_moved_together():
    declared = set(C["closed_sets"]["enabled_organ_families"])
    from_flags = {o["family"] for o in C["organs"] if o["enabled"]}
    assert declared == from_flags


# ── unknown organs, operations and parameters fail closed ────────────────────

def test_an_unknown_organ_raises_rather_than_returning_a_stub():
    with pytest.raises(D.UnknownOrgan):
        D.organ("echolocation")


def test_an_unknown_operation_raises_rather_than_returning_a_stub():
    with pytest.raises(D.UnknownOperation):
        D.operation("extent.imagine")


def test_an_unknown_operation_refuses_as_unsupported_not_as_organ_locked():
    ref = D.check_organ_lock("extent.imagine", selected_organ="extent",
                             mode=S.SessionMode.ISOLATION)
    assert ref is not None and ref.code is S.RefusalCode.UNSUPPORTED_OPERATION


def test_an_operation_of_another_organ_refuses_as_organ_locked_in_isolation():
    ref = D.check_organ_lock("topology.adjacency", selected_organ="extent",
                             mode=S.SessionMode.ISOLATION)
    assert ref is not None and ref.code is S.RefusalCode.ORGAN_LOCKED
    assert ref.detail["operation_organ"] == "topology"


def test_the_same_crossing_is_permitted_in_chain_mode():
    assert D.check_organ_lock("topology.adjacency", selected_organ="extent",
                              mode=S.SessionMode.CHAIN) is None


def test_an_undeclared_parameter_is_dropped_and_recorded_rather_than_refused():
    """The record is the point. A model planner caught trying to hand the runner a mask it
    invented should be VISIBLE having tried."""
    res = D.resolve_parameters("extent.find_all",
                               {"max_instances": 4, "mask_rle": {"size": [1, 1], "counts": []}})
    assert res.ok
    assert res.clean == {"max_instances": 4}
    assert [n for n, _ in res.dropped] == ["mask_rle"]


def test_a_declared_parameter_of_the_wrong_type_refuses():
    res = D.resolve_parameters("extent.find_all", {"max_instances": "lots"})
    assert res.refusal is not None
    assert res.refusal.code is S.RefusalCode.INVALID_PARAMETERS


def test_a_bounded_parameter_is_clamped_and_the_clamp_is_recorded():
    res = D.resolve_parameters("extent.find_all", {"max_instances": 9000})
    assert res.ok and res.clean == {"max_instances": 64}
    assert res.clamped == [("max_instances", 9000, 64, "maximum=64")]


def test_a_missing_required_parameter_refuses():
    assert D.resolve_parameters("extent.find_named", {}).refusal.code \
        is S.RefusalCode.INVALID_PARAMETERS


def test_an_enum_parameter_outside_its_declaration_refuses():
    res = D.resolve_parameters("extent.find_named",
                               {"concept": "drapery", "adapter": "clairvoyance"})
    assert res.refusal is not None


def test_no_parameter_anywhere_declares_a_default():
    """A default here would be the contract answering a question the person did not answer, and
    the answer would then be recorded on the run as though someone had chosen it."""
    for op in D.operations().values():
        for p in op.parameters:
            assert p.default is None, f"{op.key}.{p.name} declares a default"


# ── topology declares its inputs, and occlusion declares its dependency ──────

def test_every_topology_operation_declares_a_required_extent_input():
    for op in D.operations_for("topology"):
        required = [i for i in op.inputs if i.required and "extent_set" in i.artifact_kinds]
        assert required, f"{op.key} does not declare where its extents come from"


def test_no_topology_operation_may_invoke_the_extent_organ():
    for op in D.operations_for("topology"):
        assert "extent" in op.must_not_invoke
        assert "depth" in op.must_not_invoke


def test_topology_with_no_extents_refuses_rather_than_measuring_nothing():
    ref = D.check_inputs("topology.containment", [], for_execution=True)
    assert ref is not None and ref.code is S.RefusalCode.MISSING_EXTENT_INPUTS


def test_occlusion_declares_a_depth_input_that_is_optional_to_plan_and_required_to_run():
    op = D.operation("topology.occlusion")
    depth = op.input_for("depth")
    assert depth is not None
    assert depth.artifact_kinds == ("depth_field",)
    assert depth.required is False, "a person may compose the request before they have a field"
    assert depth.required_for_execution is True
    assert depth.refusal_when_missing is S.RefusalCode.MISSING_DEPTH_ARTIFACT
    assert op.dependency_declaration["may_invoke"] is False


def test_occlusion_plans_without_depth_and_refuses_to_run_without_it():
    endpoints = [S.InputRef(role="source", scope="session", artifact_id="a"),
                 S.InputRef(role="target", scope="session", artifact_id="b")]
    assert D.check_inputs("topology.occlusion", endpoints, for_execution=False) is None
    ref = D.check_inputs("topology.occlusion", endpoints, for_execution=True)
    assert ref is not None and ref.code is S.RefusalCode.MISSING_DEPTH_ARTIFACT


def test_no_enabled_organ_can_produce_a_depth_field():
    """Naming a dependency is not satisfying it. `depth_field` is referenceable and unmintable."""
    assert "depth_field" in {m.value for m in S.ArtifactKind}
    assert "depth_field" not in D.producible_artifact_kinds()
    assert D.organ("depth").declares_artifact_kinds == ("depth_field",)
    assert D.organ("depth").produces_artifact_kinds == ()


def test_an_artifact_claiming_to_be_a_produced_depth_field_does_not_validate():
    art = _artifact()
    art["identity"]["artifact_kind"] = "depth_field"
    art["measurement"]["payload_variant"] = "depth_field"
    with pytest.raises(ValidationError):
        S.PerceptualArtifact.model_validate(art)


# ── the isolation lock, in the plan ──────────────────────────────────────────

def test_an_isolation_plan_whose_resolved_step_changes_organ_does_not_validate():
    plan = _fixture("plan.direct-extent-find-all.json")
    plan["resolved_steps"][0]["organ"] = "topology"
    plan["resolved_steps"][0]["operation"] = "topology.adjacency"
    # Otherwise the step's own parameter check fires first and this would pass for the wrong
    # reason — a mutation test that catches a different bug is a mutation test that proves nothing.
    plan["resolved_steps"][0]["parameters"] = {}
    plan["resolved_steps"][0]["input_refs"] = [
        {"role": "source", "scope": "session", "artifact_id": "a"},
        {"role": "target", "scope": "session", "artifact_id": "b"},
    ]
    with pytest.raises(ValidationError) as exc:
        S.LabPlan.model_validate(plan)
    assert "isolation" in str(exc.value)


def test_an_isolation_plan_may_carry_a_crossing_PROPOSAL_only_with_its_refusal():
    plan = _fixture("plan.model-organ-locked.json")
    S.LabPlan.model_validate(plan)                       # the honest version validates
    plan["refusals"] = []                                # drop the refusal, keep the crossing
    with pytest.raises(ValidationError) as exc:
        S.LabPlan.model_validate(plan)
    assert "organ_locked" in str(exc.value)


def test_a_proposed_step_has_no_field_in_which_to_claim_authority():
    """The mechanism is the ABSENCE of the field, so this asserts the absence."""
    assert "authorized_by" not in S.ProposedStep.model_fields
    with pytest.raises(ValidationError):
        S.ProposedStep(step_id="s", organ="extent", operation="extent.find_all",
                       authorized_by="resolver")


def test_a_resolved_step_can_name_only_the_resolver_as_its_authority():
    with pytest.raises(ValidationError):
        S.ResolvedStep(step_id="s", organ="extent", operation="extent.find_all",
                       authorized_by="planner")


def test_a_resolved_step_carrying_an_undeclared_parameter_does_not_validate():
    with pytest.raises(ValidationError) as exc:
        S.ResolvedStep(step_id="s", organ="extent", operation="extent.find_all",
                       parameters={"region_id": "reg_7"}, authorized_by="resolver")
    assert "region_id" in str(exc.value)


def test_a_chain_that_crosses_organs_must_ask_first():
    plan = _fixture("plan.chain-extent-to-topology.json")
    plan["requires_confirmation"] = False
    with pytest.raises(ValidationError) as exc:
        S.LabPlan.model_validate(plan)
    assert "confirmation" in str(exc.value)


def test_a_rules_fallback_may_not_wear_the_models_name():
    plan = _fixture("plan.rules-fallback.json")
    assert plan["planner"] == "rules" and plan["planner_fell_back_from"] == "model"
    plan["planner_fell_back_from"] = "rules"
    with pytest.raises(ValidationError):
        S.LabPlan.model_validate(plan)


def test_a_session_cannot_select_a_deferred_organ():
    session = _fixture("session.extent-isolation.json")
    session["selected_organ"] = "depth"
    with pytest.raises(ValidationError) as exc:
        S.LabSession.model_validate(session)
    assert "not enabled" in str(exc.value)


# ── the six blocks, and what may not collapse into what ──────────────────────

def test_the_artifact_blocks_are_exactly_the_ones_the_contract_declares():
    declared = C["records"]["PerceptualArtifact"]["blocks"]
    assert set(declared) == set(S.PerceptualArtifact.model_fields)
    for block, fields in declared.items():
        assert list(S.ARTIFACT_BLOCK_MODELS[block].model_fields) == fields, \
            f"the {block} block's fields have drifted from the contract"


def test_identity_and_projection_share_no_field_name():
    """An artifact is not its colour. "The red one" becoming a way to refer to an artifact is how
    a display attribute quietly becomes an identity."""
    assert not (set(S.ArtifactIdentity.model_fields) & set(S.ArtifactProjection.model_fields))


def test_a_projection_hint_may_not_carry_geometry():
    with pytest.raises(ValidationError) as exc:
        S.ArtifactProjection(projection_kind="mask_fill",
                             hints={"opacity": 0.4, "mask_rle": {"size": [1, 1], "counts": []}})
    assert "mask_rle" in str(exc.value)


def test_the_artifact_carries_no_review_and_no_review_ids():
    """A `reviews` field on an artifact is how `correct` starts being read as a property of the
    measurement."""
    fields = set(S.PerceptualArtifact.model_fields)
    assert not any("review" in f or "verdict" in f for f in fields)
    art = _artifact()
    art["review"] = {"verdict": "correct"}
    with pytest.raises(ValidationError):
        S.PerceptualArtifact.model_validate(art)


def test_measurement_and_interpretation_carry_separate_statuses_with_different_ranges():
    assert S.MEASUREMENT_STATUSES != S.INTERPRETATION_STATUSES
    assert S.EpistemicStatus.MEASURED in S.MEASUREMENT_STATUSES
    assert S.EpistemicStatus.MEASURED not in S.INTERPRETATION_STATUSES


def test_a_measurement_may_not_be_sourced():
    art = _artifact()
    art["measurement"]["epistemic_status"] = "sourced"
    with pytest.raises(ValidationError):
        S.PerceptualArtifact.model_validate(art)


def test_an_interpretation_may_not_be_measured():
    art = _artifact()
    art["interpretation"]["epistemic_status"] = "measured"
    with pytest.raises(ValidationError):
        S.PerceptualArtifact.model_validate(art)


def test_a_box_basis_measurement_may_not_claim_to_be_measured():
    """The finial in the sky, in one assertion."""
    art = _artifact("artifact.topology-relation-set-box-basis.json")
    art["measurement"]["epistemic_status"] = "measured"
    with pytest.raises(ValidationError) as exc:
        S.PerceptualArtifact.model_validate(art)
    assert "box" in str(exc.value)


def test_a_box_basis_relation_may_not_claim_to_be_measured_either():
    art = _artifact("artifact.topology-relation-set-box-basis.json")
    art["measurement"]["payload"]["relations"][0]["epistemic_status"] = "measured"
    with pytest.raises(ValidationError):
        S.PerceptualArtifact.model_validate(art)


def test_the_three_axes_share_no_member():
    """Lifecycle, verdict and epistemic status are three closed sets. If they shared a member, a
    UI could render one where the other belonged and nobody would notice."""
    lifecycle = {m.value for m in S.LifecycleState}
    verdict = {m.value for m in S.ReviewVerdict}
    epistemic = {m.value for m in S.EpistemicStatus}
    assert not (lifecycle & epistemic)
    assert not (verdict & epistemic)
    # `partial` is a verdict AND an outcome, which is deliberate and different: a person may judge
    # a measurement partially right, and a run may partly succeed. They are not the same axis, and
    # nothing reads one as the other — but lifecycle and verdict must never collide.
    assert not (lifecycle & verdict)


def test_a_review_carries_no_epistemic_or_lifecycle_status():
    fields = set(S.LabReview.model_fields)
    assert "epistemic_status" not in fields and "status" not in fields
    review = _fixture("review.correct.json")
    review["epistemic_status"] = "measured"
    with pytest.raises(ValidationError):
        S.LabReview.model_validate(review)


def test_saying_correct_changes_nothing_about_the_artifact():
    """The review fixture is `wrong` about an artifact that is already `interpretive` and already
    `rejected`. Nothing in either record can move the other, and that is the whole point."""
    review = S.LabReview.model_validate(_fixture("review.wrong.json"))
    art = S.PerceptualArtifact.model_validate(
        _artifact("artifact.topology-relation-set-box-basis.json"))
    assert review.artifact_id == art.identity.artifact_id
    assert review.verdict is S.ReviewVerdict.WRONG
    assert art.measurement.epistemic_status is S.EpistemicStatus.INTERPRETIVE
    assert art.lifecycle.status is S.LifecycleState.REJECTED


# ── cross-organ and malformed payloads ───────────────────────────────────────

def test_an_extent_artifact_holding_a_topology_payload_does_not_validate():
    art = _artifact()
    art["identity"]["artifact_kind"] = "topology_relation_set"
    with pytest.raises(ValidationError):
        S.PerceptualArtifact.model_validate(art)


def test_an_extent_organ_may_not_have_produced_a_topology_artifact():
    art = _artifact("artifact.topology-relation-set.json")
    art["identity"]["organ_family"] = "extent"
    with pytest.raises(ValidationError) as exc:
        S.PerceptualArtifact.model_validate(art)
    assert "extent" in str(exc.value)


def test_an_artifact_naming_an_undeclared_operation_does_not_validate():
    art = _artifact()
    art["identity"]["operation"] = "extent.divine"
    with pytest.raises(ValidationError):
        S.PerceptualArtifact.model_validate(art)


def test_a_disabled_organ_cannot_have_produced_an_artifact():
    art = _artifact()
    art["identity"]["organ_family"] = "colour"
    with pytest.raises(ValidationError):
        S.PerceptualArtifact.model_validate(art)


def test_a_measurement_carries_exactly_one_of_payload_and_data_ref():
    art = _artifact()
    art["measurement"]["data_ref"] = {"uri": "x://y", "digest": "sha256:aaaabbbb",
                                      "media_type": "application/json"}
    with pytest.raises(ValidationError):
        S.PerceptualArtifact.model_validate(art)
    art["measurement"]["payload"] = None
    S.PerceptualArtifact.model_validate(art)             # one carrier is fine


def test_an_unknown_key_anywhere_in_a_lab_record_stops_at_the_door():
    art = _artifact()
    art["identity"]["confidence"] = 0.9
    with pytest.raises(ValidationError):
        S.PerceptualArtifact.model_validate(art)


def test_a_canonical_relation_endpoint_without_a_revision_does_not_validate():
    """A relation that cites `reg_7` without saying which revision cannot be told to have gone
    stale, and a stale relation that cannot be detected is worse than no relation."""
    with pytest.raises(ValidationError):
        S.RelationEndpoint(artifact_id="a", instance_id="i", scope="canonical",
                           region_id="reg_7")


# ── absence: five nothings that may not stand in for each other ──────────────

def test_an_empty_relation_set_that_examined_nothing_is_not_a_measurement():
    with pytest.raises(ValidationError) as exc:
        S.TopologyRelationSetPayload(variant="topology_relation_set", pairs_examined=0,
                                     relations=[])
    assert "absence of measurement" in str(exc.value)


def test_an_empty_relation_set_that_examined_pairs_IS_a_measurement():
    payload = S.TopologyRelationSetPayload(variant="topology_relation_set", pairs_examined=4,
                                           relations=[])
    assert payload.pairs_examined == 4


def test_an_extent_set_must_say_what_it_looked_for():
    with pytest.raises(ValidationError):
        S.ExtentSetPayload(variant="extent_set", searched="", instances=[])


def test_a_refused_run_carries_the_refusal_that_caused_it():
    run = _fixture("run.live-refused-missing-depth.json")
    run["refusals"] = []
    with pytest.raises(ValidationError):
        S.LabRun.model_validate(run)


def test_an_unavailable_run_names_what_is_not_running():
    run = _fixture("run.live-unavailable.json")
    run["refusals"][0]["code"] = "invalid_parameters"
    with pytest.raises(ValidationError) as exc:
        S.LabRun.model_validate(run)
    assert "indistinguishable from having found nothing" in str(exc.value)


def test_a_ready_or_empty_run_may_not_also_carry_a_refusal():
    run = _fixture("run.live-empty.json")
    run["refusals"] = [_fixture("run.live-unavailable.json")["refusals"][0]]
    with pytest.raises(ValidationError):
        S.LabRun.model_validate(run)


def test_a_ready_run_that_produced_no_artifact_does_not_validate():
    run = _fixture("run.live-ready.json")
    run["artifact_ids"] = []
    with pytest.raises(ValidationError):
        S.LabRun.model_validate(run)


def test_a_run_whose_source_moved_underneath_it_must_say_so():
    run = _fixture("run.live-ready.json")
    run["source_digest_after"] = "sha256:0000dead0000beef"
    with pytest.raises(ValidationError) as exc:
        S.LabRun.model_validate(run)
    assert "measurement of neither image" in str(exc.value)


def test_the_contract_lists_the_fields_that_may_not_default():
    # The list is prose, but it names real fields, and this asserts the important ones are in fact
    # required rather than merely described as required.
    assert S.LabRun.model_fields["outcome"].is_required()
    assert S.LabRun.model_fields["execution_identity"].is_required()
    assert S.ArtifactMeasurement.model_fields["epistemic_status"].is_required()
    assert S.ArtifactMeasurement.model_fields["epistemic_basis"].is_required()
    assert S.ArtifactLifecycle.model_fields["status"].is_required()
    assert S.TopologyRelationSetPayload.model_fields["pairs_examined"].is_required()
    assert S.StageAttempt.model_fields["invoked"].is_required()
    assert C["absence_semantics"]["no_fabricating_defaults"]


# ── replay cannot recompute ──────────────────────────────────────────────────

def test_a_replay_run_declares_a_source_and_an_uncallable_adapter():
    run = S.LabRun.model_validate(_fixture("run.replay-extent.json"))
    assert run.replay is not None
    assert run.replay.adapter_callable is False
    assert run.replay.source_run_id == "run_live_ready"


def test_replay_provenance_cannot_be_written_as_callable():
    """`Literal[False]` — "this replay may call an adapter" is not a sentence that can be typed."""
    with pytest.raises(ValidationError):
        S.ReplayProvenance(source_run_id="r", recorded_at="2026-08-10T09:00:00Z",
                           adapter_callable=True)


def test_a_replay_run_that_invoked_an_adapter_does_not_validate():
    run = _fixture("run.replay-extent.json")
    run["stage_attempts"][0]["invoked"] = True
    with pytest.raises(ValidationError) as exc:
        S.LabRun.model_validate(run)
    assert "Only LIVE may call an adapter" in str(exc.value)


def test_a_fixture_run_that_invoked_an_adapter_does_not_validate_either():
    """Otherwise FIXTURE becomes a badge a live call could wear."""
    run = _fixture("run.fixture-topology.json")
    run["stage_attempts"][0]["invoked"] = True
    with pytest.raises(ValidationError):
        S.LabRun.model_validate(run)


def test_a_replay_run_without_its_source_does_not_validate():
    run = _fixture("run.replay-extent.json")
    run["replay"] = None
    with pytest.raises(ValidationError):
        S.LabRun.model_validate(run)


def test_a_live_run_may_not_carry_replay_provenance():
    run = _fixture("run.live-ready.json")
    run["replay"] = _fixture("run.replay-extent.json")["replay"]
    with pytest.raises(ValidationError):
        S.LabRun.model_validate(run)


def test_naming_an_adapter_is_not_calling_one():
    """The unavailable and fixture runs both NAME an adapter with `invoked: false`. If the schema
    derived invocation from the adapter field, neither honest record could be written."""
    for name in ("run.live-unavailable.json", "run.fixture-topology.json",
                 "run.replay-extent.json"):
        run = S.LabRun.model_validate(_fixture(name))
        assert run.stage_attempts[0].adapter
        assert run.stage_attempts[0].invoked is False


# ── the fixtures ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("record,name", [
    (record, name) for record, names in MANIFEST["records"].items() for name in names
])
def test_every_committed_fixture_validates_against_its_model(record, name):
    S.RECORD_MODELS[record].model_validate(_fixture(name))


def test_the_fixtures_cover_every_run_outcome():
    outcomes = {_fixture(n)["outcome"] for n in MANIFEST["records"]["LabRun"]}
    assert outcomes == {m.value for m in S.RunOutcome}


def test_the_fixtures_cover_every_execution_identity():
    identities = {_fixture(n)["execution_identity"] for n in MANIFEST["records"]["LabRun"]}
    assert identities == {m.value for m in S.ExecutionIdentity}


def test_the_fixtures_cover_every_variant_a_producer_may_write():
    """Every variant that CAN be written has a committed example; the deferred ones cannot.

    PERCEPTUAL-FORMS-001A widened `payload_variants` from four to twenty, and the corpus is not
    expected to cover the nine `deferred` forms — an artifact declaring one does not validate, so
    a fixture of it could not exist. The set this asserts against is therefore what the form
    registry says is producible, which is the same test with the registry's own answer in it.
    """
    variants = {_fixture(n)["measurement"]["payload_variant"]
                for n in MANIFEST["records"]["PerceptualArtifact"]}
    enabled = {f["payload_variant"] for f in C["perceptual_forms"] if f["state"] == "enabled"}
    assert enabled <= variants, (
        f"no committed fixture for {sorted(enabled - variants)}. A form a producer writes today "
        f"and no example anywhere is a shape two lanes will implement differently.")
    deferred = {f["payload_variant"] for f in C["perceptual_forms"] if f["state"] == "deferred"}
    assert not (variants & deferred), (
        f"a fixture claims the deferred form(s) {sorted(variants & deferred)}, which nothing in "
        f"this phase produces")


def test_the_fixtures_cover_every_planner_identity():
    planners = {_fixture(n)["planner"] for n in MANIFEST["records"]["LabPlan"]}
    assert planners == {m.value for m in S.PlannerIdentity}


def test_the_manifest_lists_every_fixture_file_on_disk():
    listed = {n for names in MANIFEST["records"].values() for n in names}
    on_disk = {p.name for p in FIXTURE_DIR.glob("*.json")} - {
        "manifest.json", JS_RESOLVER_FIXTURE.name, PY_GATES_FIXTURE.name,
        # Not a record fixture but a cross-language answer sheet, like the two above. Checked by
        # `test_perception_lab_instance_refs.py`.
        "js-instance-refs.json"}
    assert listed == on_disk


# ── the form payload corpus ──────────────────────────────────────────────────
#
# PERCEPTUAL-FORMS-001A. One committed payload per registered form. THESE ARE PAYLOADS, NOT
# ARTIFACTS: sixteen of the nineteen forms have an empty `produced_by_operations`, so no artifact
# of them can exist yet, and a full fixture for those sixteen would have to name an operation that
# never ran. The payload alone claims nothing about who made it, and it is the part the next lane
# must not reinvent.

FORM_PAYLOADS = MANIFEST["form_payloads"]["by_form"]


@pytest.mark.parametrize("form_key,entry", sorted(FORM_PAYLOADS.items()))
def test_every_committed_form_payload_validates_against_its_model(form_key, entry):
    model = S.FORM_PAYLOAD_MODELS[entry["variant"]]
    payload = model.model_validate(_fixture(entry["file"]))
    assert payload.variant == entry["variant"]
    examined = D.form(form_key).absence.examined_field
    assert getattr(payload, examined) is not None, (
        f"{entry['file']} does not carry {examined!r}, which is what tells an empty answer from "
        f"an absent one")


def test_the_payload_corpus_covers_every_registered_form():
    assert list(FORM_PAYLOADS) == list(C["closed_sets"]["perceptual_forms"]), (
        "a form with no committed payload is a shape two lanes will read differently, and a "
        "payload for something that is not a form is a shape nothing names")


# ── the fields the frontend reads ────────────────────────────────────────────

def _resolve(model: type, path: str):
    """Walk a dotted path through nested Pydantic models. Returns None when it does not resolve."""
    current = model
    for key in path.split("."):
        fields = getattr(current, "model_fields", None)
        if not fields or key not in fields:
            return None
        annotation = fields[key].annotation
        current = annotation
        # Unwrap Optional[...] / Union[...] to the first model in it, which is all these paths need.
        args = getattr(annotation, "__args__", ())
        if args:
            current = next((a for a in args if hasattr(a, "model_fields")), annotation)
    return current


@pytest.mark.parametrize("record,path", [
    (record, path) for record, paths in C["frontend_consumed_fields"].items() if record != "why"
    for path in paths
])
def test_every_frontend_consumed_field_exists_on_the_model(record, path):
    """DELETING OR RENAMING A CONSUMED FIELD BREAKS THIS TEST, in this language, by name.

    That is the whole reason the list is in the contract rather than in the frontend: a backend
    that drops a field the Lab UI reads should fail a Python test, not blank a panel in production.
    """
    assert _resolve(S.RECORD_MODELS[record], path) is not None, (
        f"{record}.{path} is declared in frontend_consumed_fields and does not exist on "
        f"{S.RECORD_MODELS[record].__name__}. Either restore the field or remove it from the "
        f"contract — and if you remove it, the Lab UI that reads it has to move too.")


def test_a_renamed_consumed_field_is_caught():
    # The mutation, made explicit: the resolver that backs the test above must say "no" for a path
    # that does not exist, or the test above proves nothing.
    assert _resolve(S.PerceptualArtifact, "provenance.adaptor") is None
    assert _resolve(S.PerceptualArtifact, "provenance.adapter") is not None


def test_the_consumed_fields_are_declared_for_every_record():
    declared = set(C["frontend_consumed_fields"]) - {"why"}
    assert declared == set(S.RECORD_MODELS)


# ── the laws, claimed by both runtimes ───────────────────────────────────────

def test_python_claims_every_law_the_contract_declares():
    declared = [law["id"] for law in C["laws"]]
    assert sorted(declared) == sorted(D.ENFORCED_LAWS), (
        "a law in the contract that Python does not claim is a law nothing enforces. Add the "
        "enforcement, then add the id to `definitions.ENFORCED_LAWS`.")


def test_the_javascript_claims_every_law_too():
    """Read out of the JS source rather than executed, so this suite needs no node."""
    js = (REPO_ROOT / "frontend" / "src" / "perceptionLab" / "contract"
          / "perceptionLabContract.js").read_text(encoding="utf-8")
    block = re.search(r"ENFORCED_LAWS = Object\.freeze\(\[(.*?)\]\)", js, re.S)
    assert block, "perceptionLabContract.js no longer exports ENFORCED_LAWS"
    claimed = set(re.findall(r"'([a-z_]+)'", block.group(1)))
    assert claimed == {law["id"] for law in C["laws"]}


def test_every_refusal_code_is_declared_with_what_it_is_not():
    for code in S.RefusalCode:
        entry = C["refusals"][code.value]
        assert entry["distinguished_from"], \
            f"{code.value} does not say what it must not be confused with, which is the only " \
            f"reason there are nine of these rather than one"
        assert entry["remedy"]


def test_every_message_template_has_a_refusal_or_is_used_by_one():
    for code in S.RefusalCode:
        assert code.value in C["messages"]


# ── the two-runtime loop ─────────────────────────────────────────────────────

def test_the_js_resolvers_output_is_reproduced_by_the_python_resolver():
    """The check with no substitute: a JavaScript-built clamp meets the Python law.

    The cases live in the fixture the JS suite writes, so a case added there is automatically
    recomputed here. Regenerate with:

        UPDATE_PARITY_FIXTURES=1 npx vitest run src/perceptionLab/contract
    """
    if not JS_RESOLVER_FIXTURE.exists():
        pytest.skip(f"{JS_RESOLVER_FIXTURE.name} not generated yet — run the vitest suite")
    data = json.loads(JS_RESOLVER_FIXTURE.read_text(encoding="utf-8"))
    assert data["cases"], "an empty case list proves nothing"
    for case in data["cases"]:
        got = D.resolve_parameters(case["operation"], case["params"])
        want = case["result"]
        where = f"{case['name']} ({case['operation']})"
        assert got.clean == want["clean"], where
        assert [{"name": n, "reason": r} for n, r in got.dropped] == want["dropped"], where
        assert [{"name": n, "requested": rq, "applied": ap, "bound": b}
                for n, rq, ap, b in got.clamped] == want["clamped"], where
        if want["refusal"] is None:
            assert got.refusal is None, where
        else:
            assert got.refusal is not None, where
            assert got.refusal.code.value == want["refusal"]["code"], where
            assert got.refusal.message == want["refusal"]["message"], where


def test_the_python_gates_fixture_is_current():
    """The mirror image: refusals Python built, committed for the JS suite to reproduce."""
    cases = _python_gate_cases()
    rendered = json.dumps({
        "generated_by": "backend/tests/test_perception_lab_contracts.py",
        "how_to_regenerate": ("UPDATE_PARITY_FIXTURES=1 python -m pytest "
                             "backend/tests/test_perception_lab_contracts.py"),
        "cases": cases,
    }, indent=2) + "\n"
    import os
    if os.environ.get("UPDATE_PARITY_FIXTURES"):
        PY_GATES_FIXTURE.write_text(rendered, encoding="utf-8")
    assert PY_GATES_FIXTURE.exists(), (
        f"{PY_GATES_FIXTURE.name} is missing — regenerate with UPDATE_PARITY_FIXTURES=1")
    assert PY_GATES_FIXTURE.read_text(encoding="utf-8") == rendered, (
        f"{PY_GATES_FIXTURE.name} has drifted from what the Python gates produce — regenerate "
        f"with UPDATE_PARITY_FIXTURES=1 and check the JS suite still agrees")


def _python_gate_cases():
    """The gate outcomes both runtimes must agree on, as plain data."""
    def dump(record):
        return None if record is None else json.loads(record.model_dump_json())

    endpoints = [S.InputRef(role="source", scope="session", artifact_id="art_a"),
                 S.InputRef(role="target", scope="session", artifact_id="art_b")]
    return [
        {"name": "an operation of another organ, in isolation",
         "gate": "organ_lock", "operation": "topology.adjacency",
         "selected_organ": "extent", "mode": "isolation",
         "refusal": dump(D.check_organ_lock("topology.adjacency", selected_organ="extent",
                                            mode=S.SessionMode.ISOLATION))},
        {"name": "the same crossing, in chain mode",
         "gate": "organ_lock", "operation": "topology.adjacency",
         "selected_organ": "extent", "mode": "chain",
         "refusal": dump(D.check_organ_lock("topology.adjacency", selected_organ="extent",
                                            mode=S.SessionMode.CHAIN))},
        {"name": "an operation nobody declared",
         "gate": "organ_lock", "operation": "extent.divine",
         "selected_organ": "extent", "mode": "isolation",
         "refusal": dump(D.check_organ_lock("extent.divine", selected_organ="extent",
                                            mode=S.SessionMode.ISOLATION))},
        {"name": "topology with no extents",
         "gate": "inputs", "operation": "topology.containment", "refs": [],
         "for_execution": True,
         "refusal": dump(D.check_inputs("topology.containment", [], for_execution=True))},
        {"name": "occlusion planned without a depth field",
         "gate": "inputs", "operation": "topology.occlusion",
         "refs": [json.loads(r.model_dump_json()) for r in endpoints], "for_execution": False,
         "refusal": dump(D.check_inputs("topology.occlusion", endpoints, for_execution=False))},
        {"name": "occlusion RUN without a depth field",
         "gate": "inputs", "operation": "topology.occlusion",
         "refs": [json.loads(r.model_dump_json()) for r in endpoints], "for_execution": True,
         "refusal": dump(D.check_inputs("topology.occlusion", endpoints, for_execution=True))},
        {"name": "an adapter that is not running here",
         "gate": "capability", "operation": "extent.find_named", "adapter": "sam3_concept",
         "states": {"sam3_concept": "unavailable"},
         "refusal": dump(D.check_capability(
             "extent.find_named", adapter="sam3_concept",
             states={"sam3_concept": S.CapabilityState.UNAVAILABLE}))},
        {"name": "an adapter nobody has looked at yet is not a refusal",
         "gate": "capability", "operation": "extent.find_all", "adapter": None, "states": {},
         "refusal": dump(D.check_capability("extent.find_all", adapter=None, states={}))},
    ]
