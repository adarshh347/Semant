"""
PERCEPTUAL-ORGANS-002 Lane B — the Extent façade, and the things that must not blur.

Every test here runs against FAKE adapters, and the fakes are the point rather than a compromise:
the claims this lane makes are about what the façade does with an adapter's answer — unavailable
versus empty, a withheld name versus a discarded mask, a preserved identity versus a new one — and
those are claims about the façade. A real SAM 2.1 would prove nothing about any of them and would
turn a one-second gate into a twenty-minute one.

What is NOT faked: `mask_geometry`, `extent_metrics`, `region_provenance`, the Lane A schemas and
the canonical contract. Every artifact this file produces is validated by the real Pydantic models
and re-validated through JSON, so a shape that would fail in the frontend fails here.

The golden fixtures at the bottom write this lane's REAL output into
`contracts/fixtures/perception-lab/`, where Lane A's Python suite and the JavaScript parity suite
both pick them up from the manifest. That is the only place Lane B's product meets the frontend's
law, and it is worth the two lines of shared-file edit.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import pytest

from backend.schemas.perception_lab import (CapabilityState, EpistemicBasis, EpistemicStatus,
                                            IdentityScope, InputRef, LabelSource, LifecycleState,
                                            PerceptualArtifact, ProducerKind, ProposedStep,
                                            ProjectionKind, RefusalCode, ResolvedStep, RunOutcome,
                                            StageState)
from backend.services import mask_geometry as mg
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab import extent as E
from backend.services.perception_lab import extent_metrics as M

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "contracts" / "fixtures" / "perception-lab"
MANIFEST = FIXTURE_DIR / "manifest.json"

DIGEST = "sha256:" + "9f1c0a5b7d2e4438" * 4


# ── the smallest possible world ──────────────────────────────────────────────


def rle(bits: Sequence[int], h: int = 4, w: int = 4) -> Dict[str, Any]:
    """A 4×4 mask from sixteen bits. Small enough to reason about, real enough to round-trip."""
    return mg.rle_encode(bytearray(bits), h, w)


LEFT_HALF = rle([1, 1, 0, 0] * 4)
RIGHT_HALF = rle([0, 0, 1, 1] * 4)
LEFT_THREE = rle([1, 1, 1, 0] * 4)
CORNER = rle([1] + [0] * 15)
FULL = rle([1] * 16)


def clock(prefix: str = "2026-08-11T09"):
    counter = {"n": 0}

    def now() -> str:
        counter["n"] += 1
        return f"{prefix}:{counter['n']:02d}:00.000+00:00"
    return now


class FakeAdapter:
    """An adapter that answers exactly what a test told it to, and counts how often it was asked.

    The call counter is what proves the Direct arm and the Prompt arm reach the same runner: two
    routes into one function should show up as two calls on ONE adapter, not one call each on two.
    """

    def __init__(self, key: str = "yolo_sam2_auto", *,
                 masks: Sequence[Mapping[str, Any]] = (),
                 state: CapabilityState = CapabilityState.AVAILABLE,
                 raises: Optional[Exception] = None,
                 unavailable_midway: bool = False) -> None:
        self.key = key
        self.masks = list(masks)
        self.state = state
        self.raises = raises
        self.unavailable_midway = unavailable_midway
        self.calls: List[Dict[str, Any]] = []

    def capability(self) -> CapabilityState:
        return self.state

    def measure(self, step, ctx, params) -> E.AdapterOutput:
        self.calls.append({"operation": step.operation, "params": dict(params)})
        if self.unavailable_midway:
            raise E.AdapterUnavailable(self.key, "the checkpoint vanished between the gate and now")
        if self.raises is not None:
            raise self.raises
        instances = []
        for n, spec in enumerate(self.masks):
            mask = spec.get("mask_rle")
            instances.append({
                "instance_id": E.instance_id(ctx, step, n),
                "mask_rle": mask, "box": spec.get("box") or (mg.rle_bbox_norm(mask) if mask
                                                             else None),
                "area": M.normalized_area(mask) if mask else spec.get("area"),
                "confidence": spec.get("confidence"), "naming": spec.get("naming"),
                "region_id": None, "geometry_rev": None})
        return E.AdapterOutput(
            instances=tuple(instances), basis=E.EpistemicBasis.MASK,
            status=E.EpistemicStatus.MEASURED, basis_detail="fake per-pixel masks",
            model="fake-model", revision="fake-rev", device="cpu", duration_ms=7,
            naming_withheld=sum(1 for s in self.masks if s.get("withheld")),
            detail=f"{len(instances)} fake extents")


def ctx(**kw) -> E.ExtentContext:
    base: Dict[str, Any] = dict(
        session_id="labs_extent_b", run_id="run_b", image_bytes=b"\x89PNG-not-really",
        source_image_digest=DIGEST, natural_width=4, natural_height=4, now=clock())
    base.update(kw)
    return E.ExtentContext(**base)


def step(operation: str, *, step_id: str = "st1", params: Optional[Mapping[str, Any]] = None,
         refs: Sequence[InputRef] = ()) -> ResolvedStep:
    return ResolvedStep(step_id=step_id, organ="extent", operation=operation,
                        parameters=dict(params or {}), input_refs=list(refs),
                        authorized_by="resolver")


def artifact_from(masks: Sequence[Mapping[str, Any]], *, run_id: str = "run_a",
                  step_id: str = "sa") -> PerceptualArtifact:
    """A ready-made `extent_set` artifact, produced by the real façade over a fake adapter."""
    adapter = FakeAdapter(masks=masks)
    result = E.run(step("extent.find_all", step_id=step_id),
                   ctx(run_id=run_id, adapters={adapter.key: adapter}))
    assert result.artifacts, result
    return result.artifacts[0]


# ── mask and RLE round trips ─────────────────────────────────────────────────


def test_an_rle_survives_a_round_trip_through_the_facade_unchanged():
    """The mask is the measurement, so a byte of it lost in transit is evidence lost."""
    adapter = FakeAdapter(masks=[{"mask_rle": LEFT_HALF}])
    result = E.run(step("extent.find_all"), ctx(adapters={adapter.key: adapter}))
    carried = result.artifacts[0].measurement.payload.instances[0].mask_rle
    assert carried == LEFT_HALF
    assert mg.rle_decode(carried) == mg.rle_decode(LEFT_HALF)


def test_the_exact_set_operations_are_exact():
    assert M.iou(LEFT_HALF, LEFT_HALF) == 1.0
    assert M.iou(LEFT_HALF, RIGHT_HALF) == 0.0
    assert M.intersection_area(LEFT_HALF, LEFT_THREE) == 8
    assert M.union_area(LEFT_HALF, LEFT_THREE) == 12
    assert M.iou(LEFT_HALF, LEFT_THREE) == pytest.approx(8 / 12)
    assert M.mask_union(LEFT_HALF, RIGHT_HALF) == FULL
    assert M.mask_subtract(FULL, RIGHT_HALF) == LEFT_HALF
    assert M.mask_intersect(LEFT_HALF, LEFT_THREE) == LEFT_HALF


def test_two_masks_on_different_rasters_refuse_rather_than_resample():
    """A resampled comparison is a number about neither mask."""
    other = mg.rle_encode(bytearray([1] * 4), 2, 2)
    assert M.iou(LEFT_HALF, other) is None
    assert M.mask_union(LEFT_HALF, other) is None
    assert M.same_raster(LEFT_HALF, other) is False


def test_two_empty_masks_agree_completely():
    empty = rle([0] * 16)
    assert M.iou(empty, empty) == 1.0


def test_a_comparison_says_which_substrate_it_used():
    masked = {"instance_id": "a", "mask_rle": LEFT_HALF}
    boxed = {"instance_id": "b", "box": {"x": 0.0, "y": 0.0, "w": 0.5, "h": 1.0}}
    assert M.pair_iou(masked, masked)[1] == "mask"
    assert M.pair_iou(boxed, boxed)[1] == "box"
    assert M.pair_iou({"instance_id": "c"}, boxed) == (None, "none")


# ── the six operations, against the canonical contract ───────────────────────


def _six_results():
    """One result per declared operation, each through the real `run()`."""
    auto = FakeAdapter(masks=[{"mask_rle": LEFT_HALF, "confidence": 0.9}])
    refiner = FakeAdapter(key="sam2_refine", masks=[{"mask_rle": RIGHT_HALF, "confidence": 0.8}])
    named = FakeAdapter(key="sam3_concept", masks=[{"mask_rle": LEFT_THREE, "confidence": 0.9,
                                                    "naming": {"text": "drapery",
                                                               "source": "prompt",
                                                               "epistemic_status": "interpretive",
                                                               "confidence": 0.9}}])
    region = {"id": "reg_7", "actor": "auto", "label": "finial", "mask_rle": LEFT_HALF,
              "geometry_rev": 3, "box": mg.rle_bbox_norm(LEFT_HALF),
              "geometry_provenance": {"kind": "mask", "adapter": "sam3", "model": "facebook/sam3"}}

    left = artifact_from([{"mask_rle": LEFT_HALF}], run_id="run_l", step_id="sl")
    right = artifact_from([{"mask_rle": LEFT_THREE}], run_id="run_r", step_id="sr")
    single = artifact_from([{"mask_rle": LEFT_HALF}], run_id="run_s", step_id="ss")

    table = {}
    table["extent.find_all"] = E.run(
        step("extent.find_all"), ctx(adapters={auto.key: auto}))
    table["extent.find_named"] = E.run(
        step("extent.find_named", params={"concept": "drapery"}),
        ctx(adapters={named.key: named}))
    table["extent.refine"] = E.run(
        step("extent.refine", params={"mode": "add", "points": [[0.8, 0.5]]},
             refs=[InputRef(role="base", scope="session",
                            artifact_id=single.identity.artifact_id)]),
        ctx(adapters={refiner.key: refiner},
            artifacts={single.identity.artifact_id: single}))
    table["extent.draw"] = E.run(
        step("extent.draw", params={"tool": "mask_brush", "mask_rle": LEFT_HALF}), ctx())
    table["extent.reuse"] = E.run(
        step("extent.reuse", refs=[InputRef(role="regions", scope="canonical",
                                            region_id="reg_7", geometry_rev=3)]),
        ctx(regions={"reg_7": region}))
    table["extent.compare"] = E.run(
        step("extent.compare",
             refs=[InputRef(role="left", scope="session",
                            artifact_id=left.identity.artifact_id),
                   InputRef(role="right", scope="session",
                            artifact_id=right.identity.artifact_id)]),
        ctx(artifacts={left.identity.artifact_id: left, right.identity.artifact_id: right}))
    return table


def test_the_facade_implements_exactly_the_operations_the_contract_declares():
    """No extra operation, and no missing one. An operation the façade handled but the contract did
    not declare would be reachable only by a caller that bypassed the resolver."""
    declared = {op.key for op in D.operations_for("extent")}
    assert set(E._HANDLERS) == declared


@pytest.mark.parametrize("operation", sorted({op.key for op in D.operations_for("extent")}))
def test_every_operation_produces_a_contract_valid_artifact(operation):
    result = _six_results()[operation]
    assert result.outcome is RunOutcome.READY, result
    artifact = result.artifacts[0]
    # Round-tripped through JSON, which is the shape the frontend and the store will see.
    reloaded = PerceptualArtifact.model_validate(json.loads(artifact.model_dump_json()))
    assert reloaded == artifact
    assert reloaded.identity.operation == operation
    assert reloaded.identity.artifact_kind.value == "extent_set"
    assert reloaded.measurement.payload_variant == "extent_set"


@pytest.mark.parametrize("operation", sorted({op.key for op in D.operations_for("extent")}))
def test_every_artifact_stays_within_its_operations_declared_epistemic_ceiling(operation):
    """The contract gives each operation a ceiling and a set of allowed bases. An artifact that
    claimed more than its operation may claim would be the lab overriding its own law."""
    artifact = _six_results()[operation].artifacts[0]
    declared = D.operation(operation).epistemic
    order = {"uncertain": 0, "interpretive": 1, "visible": 2, "measured": 3}
    assert artifact.measurement.epistemic_basis.value in declared["allowed_bases"]
    assert (order[artifact.measurement.epistemic_status.value]
            <= order[declared["ceiling"]])


@pytest.mark.parametrize("operation", sorted({op.key for op in D.operations_for("extent")}))
def test_every_artifact_projects_only_what_its_operation_declares(operation):
    artifact = _six_results()[operation].artifacts[0]
    assert artifact.projection.projection_kind.value in D.operation(operation).render_projections
    assert artifact.projection.hints, "a projection with no hint at all renders as nothing"


@pytest.mark.parametrize("operation", sorted({op.key for op in D.operations_for("extent")}))
def test_every_run_receipt_is_a_contract_valid_live_run(operation):
    result = _six_results()[operation]
    run = result.as_run(ctx(), step(operation), plan_id="plan_b")
    assert run.execution_identity.value == "LIVE"
    assert run.outcome is RunOutcome.READY
    assert run.replay is None
    assert run.artifact_ids == [a.identity.artifact_id for a in result.artifacts]


# ── direct and prompt reach the same runner ──────────────────────────────────


def test_a_direct_step_and_a_planner_built_step_produce_identical_artifacts():
    """THE TEST THIS LANE EXISTS TO PASS.

    A person moving a control and a planner writing a sentence must reach the SAME runner, or the
    phase's central comparison — did the sentence choose what the person would have chosen — is
    comparing two machines instead of two intents. So: build one step directly, build the other by
    putting a deliberately over-reaching proposal through Lane A's resolver, and require the
    artifacts to be byte-identical.
    """
    direct = step("extent.find_all", step_id="same", params={"max_instances": 4})

    # The prompt arm: a planner proposes, and it proposes too much — an out-of-range cap and a
    # smuggled mask. The resolver clamps and drops; nothing else about the path differs.
    proposed = ProposedStep(step_id="same", organ="extent", operation="extent.find_all",
                            parameters={"max_instances": 4, "mask_rle": {"size": [4, 4],
                                                                         "counts": [0, 16]},
                                        "region_id": "reg_invented"})
    resolution = D.resolve_parameters(proposed.operation, proposed.parameters)
    assert resolution.ok
    assert sorted(n for n, _ in resolution.dropped) == ["mask_rle", "region_id"]
    prompted = ResolvedStep(step_id=proposed.step_id, organ=proposed.organ,
                            operation=proposed.operation, parameters=resolution.clean,
                            authorized_by="resolver")

    adapter = FakeAdapter(masks=[{"mask_rle": LEFT_HALF, "confidence": 0.9}])
    a = E.run(direct, ctx(adapters={adapter.key: adapter}))
    b = E.run(prompted, ctx(adapters={adapter.key: adapter}))

    assert a.artifacts[0].model_dump_json() == b.artifacts[0].model_dump_json()
    # ONE adapter, asked twice. Two routes into one runner is what that shows.
    assert len(adapter.calls) == 2
    assert adapter.calls[0] == adapter.calls[1]


def test_a_step_for_another_organ_is_refused_rather_than_run():
    result = E.run(ResolvedStep(step_id="x", organ="topology", operation="topology.adjacency",
                                authorized_by="resolver"), ctx())
    assert result.outcome is RunOutcome.REFUSED
    assert result.refusals[0].code is RefusalCode.ORGAN_LOCKED
    assert not result.artifacts


# ── unavailable is not empty ─────────────────────────────────────────────────


def test_an_unavailable_adapter_is_unavailable_and_produces_no_measurement():
    adapter = FakeAdapter(key="sam3_concept", state=CapabilityState.UNAVAILABLE)
    result = E.run(step("extent.find_named", params={"concept": "drapery"}),
                   ctx(adapters={adapter.key: adapter}))
    assert result.outcome is RunOutcome.UNAVAILABLE
    assert result.refusals[0].code is RefusalCode.CAPABILITY_UNAVAILABLE
    assert result.artifacts == (), "an unavailable adapter measured nothing to carry"
    assert result.stage_attempt.state is StageState.UNAVAILABLE
    assert result.stage_attempt.invoked is False
    assert adapter.calls == [], "the gate runs BEFORE the adapter, or it is not a gate"


def test_an_available_adapter_that_found_nothing_is_empty_and_says_what_it_looked_for():
    adapter = FakeAdapter(key="sam3_concept", masks=[])
    result = E.run(step("extent.find_named", params={"concept": "drapery"}),
                   ctx(adapters={adapter.key: adapter}))
    assert result.outcome is RunOutcome.EMPTY
    assert result.refusals == ()
    payload = result.artifacts[0].measurement.payload
    assert payload.instances == []
    assert payload.searched == "drapery", (
        "`searched` is the whole difference between 'there is no drapery in this picture' and "
        "'nobody looked'")
    assert result.stage_attempt.invoked is True


def test_empty_and_unavailable_do_not_share_an_outcome_a_stage_state_or_a_shape():
    available = E.run(step("extent.find_named", params={"concept": "x"}, step_id="a"),
                      ctx(adapters={"sam3_concept": FakeAdapter(key="sam3_concept", masks=[])}))
    missing = E.run(step("extent.find_named", params={"concept": "x"}, step_id="b"),
                    ctx(adapters={"sam3_concept": FakeAdapter(key="sam3_concept",
                                                              state=CapabilityState.UNAVAILABLE)}))
    assert available.outcome is not missing.outcome
    assert available.stage_attempt.state is not missing.stage_attempt.state
    assert bool(available.artifacts) and not missing.artifacts


def test_an_adapter_that_raises_is_failed_and_makes_no_claim_about_the_image():
    adapter = FakeAdapter(raises=RuntimeError("the checkpoint is corrupt"))
    result = E.run(step("extent.find_all"), ctx(adapters={adapter.key: adapter}))
    assert result.outcome is RunOutcome.FAILED
    assert result.artifacts == ()
    assert result.stage_attempt.invoked is True, "it WAS called; that is what separates this from unavailable"
    assert result.stage_attempt.duration_ms is None, "0 would report a fast failure as a measured one"
    assert result.stage_attempt.completed_at is None
    assert "corrupt" in result.stage_attempt.detail


def test_an_adapter_that_goes_missing_between_the_gate_and_the_call_is_unavailable():
    adapter = FakeAdapter(unavailable_midway=True)
    result = E.run(step("extent.find_all"), ctx(adapters={adapter.key: adapter}))
    assert result.outcome is RunOutcome.UNAVAILABLE
    assert result.stage_attempt.invoked is False


def test_the_caller_may_override_a_capability_the_adapter_would_have_claimed():
    adapter = FakeAdapter(masks=[{"mask_rle": LEFT_HALF}])
    result = E.run(step("extent.find_all"),
                   ctx(adapters={adapter.key: adapter},
                       capability_states={adapter.key: CapabilityState.UNAVAILABLE}))
    assert result.outcome is RunOutcome.UNAVAILABLE
    assert adapter.calls == []


def test_an_unavailable_first_choice_routes_to_a_second_and_records_which_ran():
    """Unavailability may route. The receipt names the adapter that actually answered."""
    sam3 = FakeAdapter(key="sam3_concept", state=CapabilityState.UNAVAILABLE)
    grounded = FakeAdapter(key="grounded_sam", masks=[{"mask_rle": LEFT_HALF}])
    result = E.run(step("extent.find_named", params={"concept": "drapery"}),
                   ctx(adapters={sam3.key: sam3, grounded.key: grounded}))
    assert result.outcome is RunOutcome.READY
    assert result.artifacts[0].provenance.adapter == "grounded_sam"
    assert result.stage_attempt.adapter == "grounded_sam"


def test_when_no_declared_adapter_is_running_the_refusal_names_every_one_it_tried():
    sam3 = FakeAdapter(key="sam3_concept", state=CapabilityState.UNAVAILABLE)
    grounded = FakeAdapter(key="grounded_sam", state=CapabilityState.UNAVAILABLE)
    result = E.run(step("extent.find_named", params={"concept": "x"}),
                   ctx(adapters={sam3.key: sam3, grounded.key: grounded}))
    assert result.refusals[0].missing == ["sam3_concept", "grounded_sam"]
    assert {row["adapter"] for row in result.refusals[0].detail["tried"]} == {"sam3_concept",
                                                                             "grounded_sam"}


# ── geometry survives a withheld name ────────────────────────────────────────


def test_a_name_below_the_floor_is_withheld_and_the_mask_is_kept():
    """The mask and the word are two claims and only one of them is in doubt."""
    naming, withheld = E._naming_from("shoulder fabric", 0.31, "prompt", E.NAMING_FLOOR)
    assert naming is None and withheld is True
    naming, withheld = E._naming_from("snake hood", 0.92, "prompt", E.NAMING_FLOOR)
    assert naming["text"] == "snake hood" and withheld is False


def test_an_extent_whose_name_was_withheld_still_carries_its_geometry():
    adapter = FakeAdapter(key="sam3_concept", masks=[
        {"mask_rle": LEFT_HALF, "confidence": 0.31, "naming": None, "withheld": True},
        {"mask_rle": RIGHT_HALF, "confidence": 0.92,
         "naming": {"text": "drapery", "source": "prompt",
                    "epistemic_status": "interpretive", "confidence": 0.92}}])
    result = E.run(step("extent.find_named", params={"concept": "drapery"}),
                   ctx(adapters={adapter.key: adapter}))
    instances = result.artifacts[0].measurement.payload.instances
    assert len(instances) == 2, "a doubtful word is not a reason to discard a measured mask"
    assert instances[0].naming is None
    assert instances[0].mask_rle == LEFT_HALF
    assert instances[1].naming.text == "drapery"
    assert "below the naming floor" in result.artifacts[0].interpretation.notes


def test_the_lab_uses_the_measured_naming_floor_rather_than_a_new_number():
    from backend.services import sam3_concept_service
    assert E.NAMING_FLOOR is sam3_concept_service.NAMING_CONFIDENCE_FLOOR


def test_a_name_is_interpretive_while_the_geometry_it_sits_on_is_measured():
    adapter = FakeAdapter(masks=[{"mask_rle": LEFT_HALF, "confidence": 0.9,
                                  "naming": {"text": "finial", "source": "adapter",
                                             "epistemic_status": "interpretive",
                                             "confidence": 0.9}}])
    artifact = E.run(step("extent.find_all"), ctx(adapters={adapter.key: adapter})).artifacts[0]
    assert artifact.measurement.epistemic_status is EpistemicStatus.MEASURED
    assert artifact.interpretation.epistemic_status is EpistemicStatus.INTERPRETIVE
    assert artifact.measurement.payload.instances[0].naming.epistemic_status \
        is EpistemicStatus.INTERPRETIVE


def test_an_unnamed_set_gets_no_label_rather_than_a_synthesized_one():
    adapter = FakeAdapter(masks=[{"mask_rle": LEFT_HALF}])
    artifact = E.run(step("extent.find_all"), ctx(adapters={adapter.key: adapter})).artifacts[0]
    assert artifact.interpretation.label is None
    assert artifact.interpretation.label_source is LabelSource.NONE
    assert artifact.interpretation.epistemic_status is EpistemicStatus.UNCERTAIN


# ── drawn, reused, and what the lab will vouch for ───────────────────────────


def test_a_drawn_extent_is_visible_on_the_manual_basis_and_has_no_adapter():
    artifact = E.run(step("extent.draw", params={"tool": "mask_brush", "mask_rle": LEFT_HALF}),
                     ctx()).artifacts[0]
    assert artifact.measurement.epistemic_basis is EpistemicBasis.MANUAL
    assert artifact.measurement.epistemic_status is EpistemicStatus.VISIBLE
    assert artifact.provenance.producer_kind is ProducerKind.HUMAN
    assert artifact.provenance.adapter is None, (
        "naming an adapter on a hand-drawn mask would make it indistinguishable from a segmented "
        "one in every later report")


def test_a_drawn_polygon_becomes_a_mask_and_a_ring_with_no_interior_refuses():
    ok = E.run(step("extent.draw", params={"tool": "polygon",
                                           "polygon": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]]}),
               ctx())
    assert ok.outcome is RunOutcome.READY
    assert mg.rle_is_valid(ok.artifacts[0].measurement.payload.instances[0].mask_rle)

    degenerate = E.run(step("extent.draw", params={"tool": "polygon",
                                                   "polygon": [[0.1, 0.1], [0.2, 0.1]]}), ctx())
    assert degenerate.outcome is RunOutcome.REFUSED
    assert degenerate.refusals[0].code is RefusalCode.INVALID_PARAMETERS


def test_a_reused_region_is_referenced_and_never_re_derived():
    region = {"id": "reg_7", "actor": "auto", "label": "finial", "mask_rle": LEFT_HALF,
              "geometry_rev": 3, "box": mg.rle_bbox_norm(LEFT_HALF),
              "geometry_provenance": {"kind": "mask", "adapter": "sam3", "model": "facebook/sam3"}}
    before = copy.deepcopy(region)
    result = E.run(step("extent.reuse",
                        refs=[InputRef(role="regions", scope="canonical", region_id="reg_7",
                                       geometry_rev=3)]),
                   ctx(regions={"reg_7": region}))
    assert region == before, (
        "`canonicalize_geometry` mutates in place and bumps geometry_rev — reuse must never call it")
    artifact = result.artifacts[0]
    assert artifact.identity.identity_scope is IdentityScope.CANONICAL
    assert [(r.region_id, r.geometry_rev) for r in artifact.identity.identity_refs] \
        == [("reg_7", 3)]
    assert artifact.measurement.payload.instances[0].geometry_rev == 3


@pytest.mark.parametrize("region,basis,status", [
    ({"id": "r", "mask_rle": LEFT_HALF, "geometry_rev": 1,
      "geometry_provenance": {"kind": "mask", "adapter": "sam3"}},
     EpistemicBasis.MASK, EpistemicStatus.MEASURED),
    ({"id": "r", "mask_rle": LEFT_HALF, "geometry_rev": 1},
     EpistemicBasis.DECLARED, EpistemicStatus.UNCERTAIN),
    ({"id": "r", "box": {"x": 0.0, "y": 0.0, "w": 0.5, "h": 1.0}, "geometry_rev": 0},
     EpistemicBasis.BOX, EpistemicStatus.INTERPRETIVE),
])
def test_reuse_vouches_for_exactly_what_the_region_can_support(region, basis, status):
    """An attributed mask is a measurement carried; an unattributed one is an abstention; a box is
    an estimate. `region_provenance.is_attributed` is the reader, not a new rule."""
    result = E.run(step("extent.reuse",
                        refs=[InputRef(role="regions", scope="canonical", region_id="r",
                                       geometry_rev=int(region["geometry_rev"]))]),
                   ctx(regions={"r": region}))
    assert result.artifacts[0].measurement.epistemic_basis is basis
    assert result.artifacts[0].measurement.epistemic_status is status


def test_a_mixed_reuse_set_takes_its_weakest_members_status():
    attributed = {"id": "a", "mask_rle": LEFT_HALF, "geometry_rev": 1,
                  "geometry_provenance": {"kind": "mask", "adapter": "sam3"}}
    orphan = {"id": "b", "mask_rle": RIGHT_HALF, "geometry_rev": 1}
    result = E.run(step("extent.reuse", refs=[
        InputRef(role="regions", scope="canonical", region_id="a", geometry_rev=1),
        InputRef(role="regions", scope="canonical", region_id="b", geometry_rev=1)]),
        ctx(regions={"a": attributed, "b": orphan}))
    assert result.artifacts[0].measurement.epistemic_status is EpistemicStatus.UNCERTAIN
    assert "weakest" in result.artifacts[0].measurement.basis_detail


def test_some_references_resolving_and_some_not_is_partial_rather_than_ready():
    region = {"id": "a", "mask_rle": LEFT_HALF, "geometry_rev": 1,
              "geometry_provenance": {"kind": "mask", "adapter": "sam3"}}
    result = E.run(step("extent.reuse", refs=[
        InputRef(role="regions", scope="canonical", region_id="a", geometry_rev=1),
        InputRef(role="regions", scope="canonical", region_id="ghost", geometry_rev=0)]),
        ctx(regions={"a": region}))
    assert result.outcome is RunOutcome.PARTIAL
    assert result.refusals[0].code is RefusalCode.UNKNOWN_REFERENCE
    assert len(result.artifacts[0].measurement.payload.instances) == 1


# ── identity, revision and lineage ───────────────────────────────────────────


def _refine(mode: str, base: PerceptualArtifact, *, refiner_mask=RIGHT_HALF):
    refiner = FakeAdapter(key="sam2_refine", masks=[{"mask_rle": refiner_mask}])
    return E.run(step("extent.refine", step_id="sref",
                      params={"mode": mode, "points": [[0.8, 0.5]]},
                      refs=[InputRef(role="base", scope="canonical",
                                     artifact_id=base.identity.artifact_id)]),
                 ctx(adapters={refiner.key: refiner},
                     artifacts={base.identity.artifact_id: base}))


def _canonical_base() -> PerceptualArtifact:
    region = {"id": "reg_7", "actor": "auto", "label": "finial", "mask_rle": LEFT_HALF,
              "geometry_rev": 3, "box": mg.rle_bbox_norm(LEFT_HALF),
              "geometry_provenance": {"kind": "mask", "adapter": "sam3"}}
    return E.run(step("extent.reuse", step_id="sreuse",
                      refs=[InputRef(role="regions", scope="canonical", region_id="reg_7",
                                     geometry_rev=3)]),
                 ctx(regions={"reg_7": region})).artifacts[0]


def test_a_refinement_preserves_the_region_identity_and_moves_the_revision():
    base = _canonical_base()
    refined = _refine("add", base).artifacts[0]
    instance = refined.measurement.payload.instances[0]
    assert instance.region_id == "reg_7", "a refinement continues the same subject"
    assert instance.geometry_rev == 4, "3 → 4, exactly once, for one refinement"
    assert [(r.region_id, r.geometry_rev) for r in refined.identity.identity_refs] == [("reg_7", 4)]
    assert refined.identity.derived_from == [base.identity.artifact_id]
    assert refined.identity.identity_scope is IdentityScope.CANONICAL


@pytest.mark.parametrize("mode,expected", [
    ("add", FULL),                  # left ∪ right
    ("subtract", LEFT_HALF),        # left − right
    ("replace", RIGHT_HALF),        # the prediction alone
])
def test_the_three_refine_modes_are_exact_set_arithmetic(mode, expected):
    refined = _refine(mode, _canonical_base()).artifacts[0]
    assert refined.measurement.payload.instances[0].mask_rle == expected


def test_a_refinement_that_erases_the_extent_is_refused_rather_than_recorded():
    base = _canonical_base()
    result = _refine("subtract", base, refiner_mask=FULL)
    assert result.outcome is RunOutcome.REFUSED
    assert "rejection, not a revision" in result.refusals[0].detail["why"]


def test_a_refinement_inherits_the_name_it_did_not_re_earn():
    refined = _refine("add", _canonical_base()).artifacts[0]
    assert refined.measurement.payload.instances[0].naming.text == "finial"


def test_a_refine_against_a_multi_extent_set_refuses_rather_than_choosing_a_subject():
    """Lane A's `InputRef` addresses an artifact, not an instance inside it. Picking the largest
    would be the lab choosing on the person's behalf and then attributing the choice to them."""
    base = artifact_from([{"mask_rle": LEFT_HALF}, {"mask_rle": RIGHT_HALF}])
    result = _refine("replace", base)
    assert result.outcome is RunOutcome.REFUSED
    assert result.refusals[0].code is RefusalCode.INVALID_PARAMETERS
    assert "Select a single extent first" in result.refusals[0].detail["why"]


def test_refine_arithmetic_across_rasters_refuses_rather_than_resampling():
    base = _canonical_base()
    other = mg.rle_encode(bytearray([1] * 4), 2, 2)
    result = _refine("add", base, refiner_mask=other)
    assert result.outcome is RunOutcome.REFUSED
    assert "different rasters" in result.refusals[0].detail["why"]


def test_ids_are_deterministic_so_two_identical_runs_are_comparable():
    a = artifact_from([{"mask_rle": LEFT_HALF}], run_id="run_x", step_id="s")
    b = artifact_from([{"mask_rle": LEFT_HALF}], run_id="run_x", step_id="s")
    assert a.identity.artifact_id == b.identity.artifact_id == "art_run_x_s"
    assert [i.instance_id for i in a.measurement.payload.instances] == ["ext_run_x_s_00"]
    assert a.model_dump_json() == b.model_dump_json()


def test_ids_are_dense_after_filtering_so_no_gap_reads_as_a_removal():
    adapter = FakeAdapter(masks=[{"mask_rle": CORNER}, {"mask_rle": LEFT_HALF},
                                 {"mask_rle": RIGHT_HALF}])
    result = E.run(step("extent.find_all", params={"min_area": 0.2}),
                   ctx(adapters={adapter.key: adapter}))
    ids = [i.instance_id for i in result.artifacts[0].measurement.payload.instances]
    assert ids == ["ext_run_b_st1_00", "ext_run_b_st1_01"]
    assert result.artifacts[0].measurement.payload.dropped_below_min_area == 1


def test_no_min_area_means_no_count_rather_than_a_count_of_zero():
    adapter = FakeAdapter(masks=[{"mask_rle": LEFT_HALF}])
    result = E.run(step("extent.find_all"), ctx(adapters={adapter.key: adapter}))
    assert result.artifacts[0].measurement.payload.dropped_below_min_area is None, (
        "0 would claim a filter ran and found nothing to drop")


# ── comparison metrics ───────────────────────────────────────────────────────


def _compare(left: PerceptualArtifact, right: PerceptualArtifact, **params):
    return E.run(step("extent.compare", step_id="scmp", params=params,
                      refs=[InputRef(role="left", scope="session",
                                     artifact_id=left.identity.artifact_id),
                            InputRef(role="right", scope="session",
                                     artifact_id=right.identity.artifact_id)]),
                 ctx(artifacts={left.identity.artifact_id: left,
                                right.identity.artifact_id: right}))


def test_a_repeat_of_the_same_run_compares_as_identical():
    left = artifact_from([{"mask_rle": LEFT_HALF}, {"mask_rle": CORNER}], run_id="r1", step_id="s")
    right = artifact_from([{"mask_rle": LEFT_HALF}, {"mask_rle": CORNER}], run_id="r2", step_id="s")
    comparison = _compare(left, right).artifacts[0].measurement.payload.comparison
    assert E.is_identical(comparison) is True
    assert E.mean_agreement(comparison) == 1.0
    assert E.changed_geometry(comparison) == []


def test_changed_geometry_is_detected_and_named():
    left = artifact_from([{"mask_rle": LEFT_HALF}], run_id="r1", step_id="s")
    right = artifact_from([{"mask_rle": LEFT_THREE}], run_id="r2", step_id="s")
    comparison = _compare(left, right).artifacts[0].measurement.payload.comparison
    assert E.is_identical(comparison) is False
    assert E.mean_agreement(comparison) == pytest.approx(8 / 12)
    assert len(E.changed_geometry(comparison)) == 1


def test_an_extent_only_one_side_saw_is_reported_on_the_side_that_saw_it():
    left = artifact_from([{"mask_rle": LEFT_HALF}, {"mask_rle": CORNER}], run_id="r1", step_id="s")
    right = artifact_from([{"mask_rle": LEFT_HALF}], run_id="r2", step_id="s")
    comparison = _compare(left, right).artifacts[0].measurement.payload.comparison
    assert comparison.only_in_left == ["ext_r1_s_01"]
    assert comparison.only_in_right == []


def test_nothing_matching_reports_no_mean_rather_than_zero():
    left = artifact_from([{"mask_rle": LEFT_HALF}], run_id="r1", step_id="s")
    right = artifact_from([{"mask_rle": RIGHT_HALF}], run_id="r2", step_id="s")
    comparison = _compare(left, right).artifacts[0].measurement.payload.comparison
    assert comparison.correspondences == []
    assert E.mean_agreement(comparison) is None, (
        "two sets that agreed about nothing did not agree badly")


def test_the_threshold_actually_used_is_recorded_whether_or_not_it_was_chosen():
    left = artifact_from([{"mask_rle": LEFT_HALF}], run_id="r1", step_id="s")
    right = artifact_from([{"mask_rle": LEFT_THREE}], run_id="r2", step_id="s")
    assert _compare(left, right).artifacts[0].measurement.payload.comparison \
        .iou_threshold_used == E.DEFAULT_IOU_THRESHOLD
    strict = _compare(left, right, iou_threshold=0.9)
    comparison = strict.artifacts[0].measurement.payload.comparison
    assert comparison.iou_threshold_used == 0.9
    assert comparison.correspondences == [], "8/12 does not clear 0.9"


def test_duplicates_within_a_set_are_flagged_and_neither_instance_is_removed():
    nearly = rle([1, 1, 0, 0] * 3 + [1, 0, 0, 0])
    adapter = FakeAdapter(masks=[{"mask_rle": LEFT_HALF}, {"mask_rle": nearly}])
    result = E.run(step("extent.find_all"), ctx(adapters={adapter.key: adapter}))
    payload = result.artifacts[0].measurement.payload
    assert len(payload.duplicates) == 1
    assert len(payload.instances) == 2, "a duplicate warning is evidence, not a deletion"
    assert "NOT removed" in result.stage_attempt.detail


def test_duplicates_in_a_comparison_are_reported_per_side_not_across_it():
    left = artifact_from([{"mask_rle": LEFT_HALF}], run_id="r1", step_id="s")
    right = artifact_from([{"mask_rle": LEFT_HALF}], run_id="r2", step_id="s")
    payload = _compare(left, right).artifacts[0].measurement.payload
    assert payload.duplicates == [], (
        "the two sides matching is a CORRESPONDENCE; reporting it as a duplicate would invert "
        "what the word means")
    assert [i.instance_id[:2] for i in payload.instances] == ["L:", "R:"]


def test_comparing_a_box_only_set_refuses_because_the_number_would_be_about_neither():
    boxed = E.run(step("extent.find_all", step_id="sbox"),
                  ctx(run_id="rbox", adapters={"yolo_sam2_auto": FakeAdapter(masks=[
                      {"mask_rle": None, "box": {"x": 0.0, "y": 0.0, "w": 0.5, "h": 1.0},
                       "area": 0.5}])})).artifacts[0]
    masked = artifact_from([{"mask_rle": LEFT_HALF}], run_id="r2", step_id="s")
    result = _compare(boxed, masked)
    assert result.outcome is RunOutcome.REFUSED
    assert result.refusals[0].code is RefusalCode.INVALID_PARAMETERS
    assert "exact mask arithmetic" in result.refusals[0].detail["why"]


# ── malformed references and clamps fail closed ──────────────────────────────


def test_an_invented_artifact_reference_is_unknown_reference_not_an_empty_result():
    result = E.run(step("extent.compare",
                        refs=[InputRef(role="left", scope="session", artifact_id="art_invented"),
                              InputRef(role="right", scope="session", artifact_id="art_also")]),
                   ctx())
    assert result.outcome is RunOutcome.REFUSED
    assert {r.code for r in result.refusals} == {RefusalCode.UNKNOWN_REFERENCE}
    assert not result.artifacts


def test_a_topology_style_step_missing_its_declared_inputs_refuses_before_any_adapter():
    adapter = FakeAdapter(key="sam2_refine", masks=[{"mask_rle": LEFT_HALF}])
    result = E.run(step("extent.refine", params={"mode": "replace", "points": [[0.5, 0.5]]}),
                   ctx(adapters={adapter.key: adapter}))
    assert result.outcome is RunOutcome.REFUSED
    assert result.refusals[0].code is RefusalCode.MISSING_EXTENT_INPUTS
    assert adapter.calls == []


def test_a_refinement_with_neither_points_nor_a_box_refuses():
    result = _refine_without_prompt()
    assert result.outcome is RunOutcome.REFUSED
    assert "points or a box" in result.refusals[0].detail["why"]


def _refine_without_prompt():
    base = _canonical_base()
    refiner = FakeAdapter(key="sam2_refine", masks=[{"mask_rle": RIGHT_HALF}])
    return E.run(step("extent.refine", params={"mode": "replace"},
                      refs=[InputRef(role="base", scope="canonical",
                                     artifact_id=base.identity.artifact_id)]),
                 ctx(adapters={refiner.key: refiner},
                     artifacts={base.identity.artifact_id: base}))


def test_an_undeclared_parameter_never_reaches_a_resolved_step():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ResolvedStep(step_id="s", organ="extent", operation="extent.find_all",
                     parameters={"mask_rle": {"size": [1, 1], "counts": []}},
                     authorized_by="resolver")


def test_the_resolver_clamps_a_cap_and_the_facade_honours_the_clamped_value():
    resolution = D.resolve_parameters("extent.find_all", {"max_instances": 9000})
    assert resolution.clean == {"max_instances": 64}
    adapter = FakeAdapter(masks=[{"mask_rle": LEFT_HALF}] * 3)
    result = E.run(step("extent.find_all", params={"max_instances": 2}),
                   ctx(adapters={adapter.key: adapter}))
    assert len(result.artifacts[0].measurement.payload.instances) == 2
    assert "beyond the cap" in result.stage_attempt.detail


def test_an_operation_this_organ_does_not_declare_is_unsupported():
    result = E.run(ResolvedStep.model_construct(
        step_id="s", organ=E.OrganFamily.EXTENT, operation="extent.divine", parameters={},
        input_refs=[], adapter=None, authorized_by="resolver", prerequisites_checked=[]), ctx())
    assert result.refusals[0].code is RefusalCode.UNSUPPORTED_OPERATION


# ── nothing is written, and nothing moves ────────────────────────────────────


def test_the_source_image_is_byte_identical_after_every_operation():
    """A measurement of an image that moved is a measurement of neither image."""
    image = b"\x89PNG\r\n\x1a\n-pretend-this-is-a-real-picture"
    before = hashlib.sha256(image).hexdigest()
    region = {"id": "reg_7", "mask_rle": LEFT_HALF, "geometry_rev": 1,
              "geometry_provenance": {"kind": "mask", "adapter": "sam3"}}
    base = artifact_from([{"mask_rle": LEFT_HALF}], run_id="rb", step_id="sb")
    adapters = {k: FakeAdapter(key=k, masks=[{"mask_rle": RIGHT_HALF}])
                for k in ("yolo_sam2_auto", "sam3_concept", "sam2_refine")}
    common = dict(image_bytes=image, adapters=adapters, regions={"reg_7": region},
                  artifacts={base.identity.artifact_id: base})

    for operation, params, refs in [
        ("extent.find_all", {}, ()),
        ("extent.find_named", {"concept": "drapery"}, ()),
        ("extent.draw", {"tool": "mask_brush", "mask_rle": LEFT_HALF}, ()),
        ("extent.reuse", {}, (InputRef(role="regions", scope="canonical", region_id="reg_7",
                                       geometry_rev=1),)),
        ("extent.refine", {"mode": "replace", "points": [[0.5, 0.5]]},
         (InputRef(role="base", scope="session", artifact_id=base.identity.artifact_id),)),
    ]:
        E.run(step(operation, params=params, refs=refs), ctx(**common))
        assert hashlib.sha256(image).hexdigest() == before, f"{operation} touched the image"


def test_a_post_and_its_regions_come_back_untouched():
    """The lab reads a post's regions. `canonicalize_geometry` mutates in place, so "reads" has to
    be proved rather than asserted."""
    post = {"_id": "post_finial", "title": "Finial",
            "region_annotations": [
                {"id": "reg_7", "actor": "auto", "label": "finial", "mask_rle": LEFT_HALF,
                 "geometry_rev": 3, "box": mg.rle_bbox_norm(LEFT_HALF),
                 "geometry_provenance": {"kind": "mask", "adapter": "sam3"}}],
            "visual_marks": [{"id": "mark_1"}]}
    before = json.dumps(post, sort_keys=True)
    regions = {r["id"]: r for r in post["region_annotations"]}

    base = E.run(step("extent.reuse", step_id="s1",
                      refs=[InputRef(role="regions", scope="canonical", region_id="reg_7",
                                     geometry_rev=3)]),
                 ctx(regions=regions)).artifacts[0]
    refiner = FakeAdapter(key="sam2_refine", masks=[{"mask_rle": RIGHT_HALF}])
    E.run(step("extent.refine", step_id="s2", params={"mode": "add", "points": [[0.8, 0.5]]},
               refs=[InputRef(role="base", scope="canonical",
                              artifact_id=base.identity.artifact_id)]),
          ctx(adapters={refiner.key: refiner}, artifacts={base.identity.artifact_id: base},
              regions=regions))

    assert json.dumps(post, sort_keys=True) == before
    assert post["region_annotations"][0]["geometry_rev"] == 3, "the corpus revision did not move"


def test_neither_lane_module_imports_anything_that_could_write():
    """A static read of the imports, because "it does not write" is a claim about every path
    through the file and not only the ones a test happened to take."""
    forbidden = ("backend.database", "motor", "pymongo", "backend.routers", "backend.main")
    for name in ("extent.py", "extent_metrics.py"):
        source = (REPO_ROOT / "backend" / "services" / "perception_lab" / name).read_text()
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        for bad in forbidden:
            assert not any(mod == bad or mod.startswith(bad + ".") for mod in imported), \
                f"{name} imports {bad}"


def test_importing_the_facade_pulls_in_no_database_module():
    """The static check above misses transitive imports; this one does not. A subprocess, because
    the rest of the suite has certainly imported the database by now."""
    code = ("import sys;"
            "import backend.services.perception_lab.extent as e;"
            "bad=[m for m in sys.modules if m in ('backend.database','motor','pymongo')"
            " or m.startswith('backend.routers')];"
            "print(bad); sys.exit(1 if bad else 0)")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                            cwd=str(REPO_ROOT))
    assert result.returncode == 0, f"the façade dragged in {result.stdout.strip()}"


def test_the_facade_never_promotes_and_has_no_lifecycle_beyond_proposed():
    """Promotion is an explicit human act in Lane F. Nothing this organ produces may arrive
    already `kept` or `promoted`."""
    for result in _six_results().values():
        for artifact in result.artifacts:
            assert artifact.lifecycle.status is LifecycleState.PROPOSED


# ── golden fixtures: this lane's real output, in the shared corpus ───────────


def _golden() -> Dict[str, str]:
    """`{filename: text}` for the fixtures Lane A's suites validate. Deterministic by construction:
    fixed run id, fixed step id, fixed clock, fake adapter."""
    adapter = FakeAdapter(masks=[
        {"mask_rle": LEFT_HALF, "confidence": 0.91,
         "naming": {"text": "finial", "source": "adapter", "epistemic_status": "interpretive",
                    "confidence": 0.91}},
        {"mask_rle": RIGHT_HALF, "confidence": 0.34, "withheld": True}])
    context = E.ExtentContext(
        session_id="labs_extent_1", run_id="run_lane_b", image_bytes=b"",
        source_image_digest="sha256:9f1c0a5b7d2e4438", natural_width=4, natural_height=4,
        adapters={adapter.key: adapter}, now=clock("2026-08-11T11"))
    resolved = step("extent.find_all", step_id="step_find_all")
    result = E.run(resolved, context)
    assert result.outcome is RunOutcome.READY

    run = result.as_run(context, resolved, plan_id="plan_lane_b")
    # `ensure_ascii=False` so an em-dash in a `basis_detail` stays an em-dash. These files sit
    # beside Lane A's hand-written ones and a reader should not be able to tell which is which.
    def dump(model):
        return json.dumps(json.loads(model.model_dump_json()), indent=2,
                          ensure_ascii=False) + "\n"
    return {"artifact.extent-set-lane-b.json": dump(result.artifacts[0]),
            "run.live-extent-lane-b.json": dump(run)}


def test_the_golden_fixtures_match_what_the_facade_produces_today():
    """These files are the ONLY place Lane B's real output meets the JavaScript law: Lane A's
    manifest carries them, so `test_perception_lab_contracts.py` validates them in Python and
    `perceptionLab.parity.test.js` validates them in the browser's runtime.

    Regenerate an intentional change with:

        UPDATE_PARITY_FIXTURES=1 python -m pytest backend/tests/test_perception_lab_extent.py
    """
    rendered = _golden()
    if os.environ.get("UPDATE_PARITY_FIXTURES"):
        for name, text in rendered.items():
            (FIXTURE_DIR / name).write_text(text, encoding="utf-8")
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for record, name in (("PerceptualArtifact", "artifact.extent-set-lane-b.json"),
                             ("LabRun", "run.live-extent-lane-b.json")):
            if name not in manifest["records"][record]:
                manifest["records"][record].append(name)
        MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    listed = {n for names in manifest["records"].values() for n in names}
    for name, text in rendered.items():
        path = FIXTURE_DIR / name
        assert path.exists(), f"{name} is missing — regenerate with UPDATE_PARITY_FIXTURES=1"
        assert path.read_text(encoding="utf-8") == text, (
            f"{name} has drifted from what the Extent façade produces — regenerate with "
            f"UPDATE_PARITY_FIXTURES=1 and check the Lane A suites still pass")
        assert name in listed, f"{name} is on disk and not in the manifest"


def test_the_golden_artifact_is_the_shape_lane_e_will_render():
    artifact = PerceptualArtifact.model_validate(
        json.loads((FIXTURE_DIR / "artifact.extent-set-lane-b.json").read_text()))
    payload = artifact.measurement.payload
    assert len(payload.instances) == 2
    assert payload.instances[0].naming.text == "finial"
    assert payload.instances[1].naming is None, "the withheld name, kept withheld"
    assert payload.instances[1].mask_rle is not None, "and its geometry, kept"
    assert artifact.measurement.epistemic_status is EpistemicStatus.MEASURED
    assert artifact.interpretation.epistemic_status is EpistemicStatus.INTERPRETIVE
    assert artifact.projection.projection_kind is ProjectionKind.MASK_FILL
