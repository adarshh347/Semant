"""
PERCEPTUAL-ORGANS-002 Lane D — contract-shaped fake organs, and the reference implementation.

Lane D is built and merged before Lanes B and C, so it develops against these. They are not stubs:
they produce real `ExtentSetPayload`, `TopologyRelationSetPayload` and `NegativeSpaceFieldPayload`
records that validate against Lane A's schemas, they respect the basis ceilings, and they read
their inputs out of `AdapterCall.inputs` rather than making endpoints up. A fake that returned
`None` would let the conductor be written against a shape the real adapters cannot produce, and
the integration would then be a rewrite wearing the word "wiring".

THEY ARE ALSO THE SPEC. Lane F reading `adapters.py` learns the protocol; Lane F reading this
learns what a conforming implementation looks like — where the endpoints come from, why the box
basis reports `interpretive`, which state an empty search returns, and that the adapter never
stamps its own duration.

WHAT THEY DELIBERATELY DO NOT DO. Look at an image, open a file, mint an artifact id, or time
themselves. Neither will the real ones: those are the conductor's, and a fake that did any of
them would have made the seam wrong in exactly the place it is hardest to move later.

`calls` is a public list of every `AdapterCall` received. The Direct/Prompt equivalence proof
reads it: both arms reach ONE adapter object and leave two records that compare equal.

PURE. No database, no network, no model, no clock.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from backend.schemas.perception_lab import (ArtifactInterpretation, ArtifactMeasurement,
                                            ArtifactProjection, Box, CoordinateSystem,
                                            EpistemicBasis, EpistemicStatus, ExtentInstance,
                                            ExtentSetPayload, IdentityScope, InstanceNaming,
                                            LabelSource, NegativeSpaceFieldPayload, ProjectionKind,
                                            RelationEndpoint, RelationKind, StageState,
                                            TopologyRelation, TopologyRelationSetPayload)
from backend.schemas.perception_lab import BASIS_CEILINGS
from backend.services.perception_lab.adapters import AdapterCall, AdapterOutcome

#: What a fake reports about itself, so a run receipt has the same shape it will have in Lane F.
DEVICE = "cpu"
REVISION = "fake-1"


def _rle(index: int) -> Dict[str, Any]:
    """A COCO-shaped RLE that is syntactically real and semantically arbitrary.

    `mask_rle` is `Dict[str, Any]` in the schema, so nothing here validates the counts. It is
    shaped correctly anyway: a fixture that looked wrong would train a reader to skip past the
    field that carries the measurement.
    """
    return {"size": [16, 16], "counts": [index * 8, 24, 232 - index * 8]}


def _box(index: int) -> Box:
    x = min(0.05 + 0.2 * index, 0.7)
    return Box(x=round(x, 3), y=0.1, w=0.2, h=0.4)


@dataclass
class FakeExtentAdapter:
    """One extent organ, as the contract describes one.

    `instances` is how many it finds; zero is a MEASURED EMPTINESS and returns `StageState.EMPTY`
    with a payload that still says what was searched for. That distinction is the whole reason
    `ExtentSetPayload.searched` has no default.
    """
    name: str = "yolo_sam2_auto"
    organ: str = "extent"
    operations: Tuple[str, ...] = ("extent.find_all",)
    instances: int = 2
    model: Optional[str] = "fake/extent-1"
    basis: EpistemicBasis = EpistemicBasis.MASK
    calls: List[AdapterCall] = field(default_factory=list)
    fail_with: Optional[str] = None

    def invoke(self, call: AdapterCall) -> AdapterOutcome:
        self.calls.append(call)
        if self.fail_with:
            return AdapterOutcome(state=StageState.FAILED, detail=self.fail_with, model=self.model,
                                  device=DEVICE, revision=REVISION)
        call.cancel.raise_if_cancelled()

        searched = str(call.parameters.get("concept") or "every instance")
        limit = int(call.parameters.get("max_instances") or self.instances)
        found = min(self.instances, max(limit, 0))
        instances = [
            ExtentInstance(
                instance_id=f"{call.step_id}_i{n}", mask_rle=_rle(n), box=_box(n),
                area=round(0.08 * (n + 1), 3), confidence=round(0.9 - 0.1 * n, 3),
                # Geometry and naming are two epistemic statuses on one instance — CONCEPT-SEG-001's
                # discipline. A wrong name can be rejected without discarding a correct mask.
                naming=InstanceNaming(text=searched, source=LabelSource.PROMPT,
                                      epistemic_status=EpistemicStatus.INTERPRETIVE,
                                      confidence=0.62)
                if call.parameters.get("concept") else None)
            for n in range(found)]

        payload = ExtentSetPayload(variant="extent_set", searched=searched, instances=instances)
        return AdapterOutcome(
            state=StageState.COMPLETED if instances else StageState.EMPTY,
            measurement=ArtifactMeasurement(
                payload_variant="extent_set", payload=payload,
                coordinate_system=CoordinateSystem.MASK_RLE_HW,
                epistemic_status=BASIS_CEILINGS[self.basis], epistemic_basis=self.basis,
                basis_detail=f"{self.name} instance masks on the source raster"),
            projection=ArtifactProjection(projection_kind=ProjectionKind.MASK_FILL,
                                          hints={"opacity": 0.45, "palette_role": "figure"}),
            interpretation=ArtifactInterpretation(
                label=searched if call.parameters.get("concept") else None,
                label_source=LabelSource.PROMPT if call.parameters.get("concept")
                else LabelSource.NONE,
                epistemic_status=EpistemicStatus.INTERPRETIVE),
            model=self.model, revision=REVISION, device=DEVICE, peak_memory_mb=128.0,
            detail=f"{len(instances)} instances")


@dataclass
class FakeManualAdapter(FakeExtentAdapter):
    """`extent.draw`. A person's hand, so the ceiling is `visible` and there is no model.

    The conductor turns this into `producer_kind: human` with NO adapter named, because a
    hand-drawn artifact that named an adapter would be indistinguishable from a segmented one in
    every later report — `ArtifactProvenance` refuses that record outright.
    """
    name: str = "human"
    operations: Tuple[str, ...] = ("extent.draw",)
    model: Optional[str] = None
    basis: EpistemicBasis = EpistemicBasis.MANUAL


@dataclass
class FakeTopologyAdapter:
    """One topology organ. Endpoints come from the artifacts it was HANDED, never invented.

    The basis is read from the step's parameters, and the epistemic status from
    `BASIS_CEILINGS` — so a box-basis containment reports `interpretive` here and cannot be talked
    into `measured` anywhere downstream. That is the WAVE2.5 ruling arriving through the fake
    rather than being asserted about it.
    """
    name: str = "adjacency_organ"
    organ: str = "topology"
    operations: Tuple[str, ...] = ("topology.adjacency",)
    model: Optional[str] = "fake/topology-1"
    relate: bool = True
    calls: List[AdapterCall] = field(default_factory=list)
    fail_with: Optional[str] = None

    _KINDS = {
        "topology.containment": RelationKind.NESTED_WITHIN,
        "topology.adjacency": RelationKind.MEETS,
        "topology.overlap": RelationKind.OVERLAPS,
        "topology.disjoint": RelationKind.DISJOINT,
        "topology.all_pairs": RelationKind.MEETS,
        "topology.occlusion": RelationKind.IN_FRONT_OF,
    }

    def invoke(self, call: AdapterCall) -> AdapterOutcome:
        self.calls.append(call)
        if self.fail_with:
            return AdapterOutcome(state=StageState.FAILED, detail=self.fail_with)
        call.cancel.raise_if_cancelled()
        if call.operation == "topology.negative_space":
            return self._negative_space(call)
        return self._relations(call)

    # -- relations --

    def _relations(self, call: AdapterCall) -> AdapterOutcome:
        members = self._members(call)
        pairs = [(a, b) for i, a in enumerate(members) for b in members[i + 1:]]
        basis = (EpistemicBasis.DEPTH_ARTIFACT if call.operation == "topology.occlusion"
                 else EpistemicBasis(str(call.parameters.get("basis") or "mask")))
        kind = self._KINDS[call.operation]

        relations = [
            TopologyRelation(
                relation_id=f"{call.step_id}_r{n}", kind=kind, source=a, target=b,
                directed=kind in (RelationKind.NESTED_WITHIN, RelationKind.CONTAINS,
                                  RelationKind.IN_FRONT_OF),
                basis=basis, epistemic_status=BASIS_CEILINGS[basis],
                measurements={"contact_ratio": 0.14, "separation": 0.0})
            for n, (a, b) in enumerate(pairs)] if self.relate else []

        payload = TopologyRelationSetPayload(
            variant="topology_relation_set", pairs_examined=len(pairs), relations=relations,
            bounded_to=len(members) if call.operation == "topology.all_pairs" else None)
        return AdapterOutcome(
            # `relations: []` with `pairs_examined: 2` is a MEASURED emptiness — the pairs were
            # compared and none stood in the asked-for relation. It is `empty`, not `refused`.
            state=StageState.COMPLETED if relations else StageState.EMPTY,
            measurement=ArtifactMeasurement(
                payload_variant="topology_relation_set", payload=payload,
                coordinate_system=CoordinateSystem.MASK_RLE_HW,
                epistemic_status=BASIS_CEILINGS[basis], epistemic_basis=basis,
                basis_detail=f"{basis.value} basis; {self.name}"),
            projection=ArtifactProjection(projection_kind=ProjectionKind.CONTACT_BAND,
                                          hints={"stroke_weight": 2, "emphasis": "contact"}),
            interpretation=ArtifactInterpretation(label=None, label_source=LabelSource.NONE,
                                                  epistemic_status=EpistemicStatus.UNCERTAIN),
            model=self.model, revision=REVISION, device=DEVICE, peak_memory_mb=64.0,
            detail=f"{len(relations)} relations over {len(pairs)} pairs")

    def _members(self, call: AdapterCall) -> List[RelationEndpoint]:
        """One endpoint per supplied extent, read out of the artifacts the conductor resolved.

        A fake that minted `art_left`/`art_right` would pass every test in this lane and hide the
        one thing worth proving: that the conductor hands the adapter the artifacts its declared
        input roles resolved to, in the roles it declared them.
        """
        out: List[RelationEndpoint] = []
        for role in ("source", "target", "members", "figure"):
            for artifact in call.all(role):
                payload = artifact.measurement.payload
                instance_id = (payload.instances[0].instance_id
                               if payload is not None and getattr(payload, "instances", None)
                               else f"{artifact.identity.artifact_id}_i0")
                out.append(RelationEndpoint(artifact_id=artifact.identity.artifact_id,
                                            instance_id=instance_id,
                                            scope=IdentityScope.SESSION))
        return out

    # -- negative space --

    def _negative_space(self, call: AdapterCall) -> AdapterOutcome:
        figures = call.all("figure")
        ids = [f"{a.identity.artifact_id}_i0" for a in figures] or [f"{call.step_id}_i0"]
        payload = NegativeSpaceFieldPayload(
            variant="negative_space_field", figure_instance_ids=ids,
            max_distance_used=float(call.parameters.get("max_distance") or 0.25),
            field_shape=[16, 16], statistics={"mean": 0.31, "max": 0.98})
        return AdapterOutcome(
            state=StageState.COMPLETED,
            measurement=ArtifactMeasurement(
                payload_variant="negative_space_field", payload=payload,
                coordinate_system=CoordinateSystem.MASK_RLE_HW,
                epistemic_status=EpistemicStatus.MEASURED, epistemic_basis=EpistemicBasis.MASK,
                basis_detail="distance transform over the mask complement"),
            projection=ArtifactProjection(projection_kind=ProjectionKind.SCALAR_WASH,
                                          hints={"opacity": 0.6, "legend": "distance"}),
            interpretation=ArtifactInterpretation(label=None, label_source=LabelSource.NONE,
                                                  epistemic_status=EpistemicStatus.UNCERTAIN),
            model=self.model, revision=REVISION, device=DEVICE, detail="scalar field")


def extent_registry(**kw) -> Any:
    """A registry with the whole fake extent organ in it, for tests that want one line."""
    from backend.services.perception_lab.adapters import AdapterRegistry
    return (AdapterRegistry()
            .register(FakeExtentAdapter(name="yolo_sam2_auto",
                                        operations=("extent.find_all",), **kw))
            .register(FakeExtentAdapter(name="sam3_concept",
                                        operations=("extent.find_named",), **kw))
            .register(FakeExtentAdapter(name="sam2_refine", operations=("extent.refine",), **kw))
            .register(FakeExtentAdapter(name="lab_compare", operations=("extent.compare",), **kw))
            .register(FakeManualAdapter()))


def full_registry(**kw) -> Any:
    """Both fake organs, every enabled operation. What a conductor test runs against."""
    registry = extent_registry(**kw)
    registry.register(FakeExtentAdapter(name="canonical_region",
                                        operations=("extent.reuse",), **kw))
    registry.register(FakeTopologyAdapter(name="nestedness_organ",
                                          operations=("topology.containment",)))
    registry.register(FakeTopologyAdapter(name="adjacency_organ",
                                          operations=("topology.adjacency",)))
    registry.register(FakeTopologyAdapter(name="mask_arithmetic",
                                          operations=("topology.overlap", "topology.disjoint",
                                                      "topology.all_pairs")))
    registry.register(FakeTopologyAdapter(name="distance_transform",
                                          operations=("topology.negative_space",)))
    registry.register(FakeTopologyAdapter(name="occlusion_organ",
                                          operations=("topology.occlusion",)))
    return registry


__all__ = ["FakeExtentAdapter", "FakeManualAdapter", "FakeTopologyAdapter", "extent_registry",
           "full_registry", "DEVICE", "REVISION"]
