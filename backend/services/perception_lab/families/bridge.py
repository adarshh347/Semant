"""A fixed bridge from any admitted family slot into the existing Lab conductor."""
from __future__ import annotations

from dataclasses import dataclass

from backend.schemas.perception_lab import (
    ArtifactInterpretation, ArtifactMeasurement, ArtifactProjection, CapabilityState,
    CoordinateSystem, EpistemicBasis, EpistemicStatus, LabelSource, ProjectionKind,
    SampleGridPayload, StageState)
from backend.services.perception_lab.adapters import AdapterCall, AdapterOutcome
from backend.services.perception_lab.field_data import encode_grid
from backend.services.perception_lab.image_preparation import prepare_image
from backend.services.perception_lab.model_lease import learned_model_lease

from .base import FamilyModule, ProducedField


@dataclass
class FamilyBridge:
    slot: FamilyModule
    producer_key: str
    operations: tuple[str, ...]
    image_bytes: bytes
    assets: object = None

    @property
    def name(self):
        return self.producer_key

    @property
    def organ(self):
        return self.slot.family

    def capability(self):
        # Admission is declarative. Listing capabilities never imports a model.
        if not self.slot.available or any(not item.get("admitted") for item in
                                          (*self.slot.models, *self.slot.dependencies)):
            return CapabilityState.UNAVAILABLE
        return CapabilityState.AVAILABLE

    def invoke(self, call: AdapterCall) -> AdapterOutcome:
        if call.step is None or call.step.authorized_by != "resolver":
            raise ValueError("family producer requires the resolved Lab step")
        operation = next((op for op in self.slot.operations if op.key == call.operation), None)
        if operation is None or operation.producer_key != self.producer_key:
            raise ValueError("family operation/producer mismatch")
        call.cancel.raise_if_cancelled()
        prepared = prepare_image(self.image_bytes)
        if prepared.source_digest != call.source.image_digest:
            raise ValueError("prepared image differs from LabSource digest")
        producer = self.slot.producers[self.producer_key]
        if operation.learned:
            with learned_model_lease(family=self.slot.family, timeout=0):
                produced = producer(prepared, dict(call.parameters), call.inputs, call.cancel)
        else:
            produced = producer(prepared, dict(call.parameters), call.inputs, call.cancel)
        if not isinstance(produced, ProducedField):
            raise ValueError("family producer returned no typed field")
        if produced.metadata.get("source_digest") != call.source.image_digest:
            raise ValueError("field metadata has wrong source digest")
        assets = self.assets
        if assets is None:
            # Small inline fields work without an asset writer. Large ones refuse
            # instead of reaching a database from the conductor's import closure.
            writer = None
        else:
            writer = assets.put
        manifest, field_ref = encode_grid(produced.metadata, produced.values, produced.valid,
                                          put_asset=writer)
        payload = SampleGridPayload(form_key=operation.form_key, manifest=manifest,
                                    field_ref=field_ref)
        basis = EpistemicBasis.MODEL_ESTIMATE if operation.learned else EpistemicBasis.IMAGE_SIGNAL
        status = EpistemicStatus.UNCERTAIN if operation.learned else EpistemicStatus.MEASURED
        projection = (ProjectionKind.VECTOR_FIELD if produced.metadata["kind"] in
                      {"directed_vector_2d", "axial_orientation_2d", "normal_camera_3d"}
                      else ProjectionKind.SCALAR_WASH)
        return AdapterOutcome(
            state=StageState.COMPLETED,
            measurement=ArtifactMeasurement(
                payload_variant="sample_grid", payload=payload,
                coordinate_system=CoordinateSystem.PIXEL_XY_TOPLEFT,
                epistemic_status=status, epistemic_basis=basis,
                basis_detail="Typed field on a prepared image; preview does not replace values."),
            projection=ArtifactProjection(projection_kind=projection),
            interpretation=ArtifactInterpretation(
                label=None, label_source=LabelSource.NONE,
                epistemic_status=EpistemicStatus.UNCERTAIN),
            model=produced.model, revision=produced.producer_revision,
            device=produced.device,
            detail=f"field hash {manifest['measurement_hash']}; source {prepared.source_digest}")
