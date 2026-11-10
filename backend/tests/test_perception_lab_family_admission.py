"""Runtime readiness is per producer, not a blanket promise about a family."""
from dataclasses import replace

import pytest

from backend.schemas.perception_lab import CapabilityState
from backend.services.perception_lab.families import illumination, surface_pattern, registry
from backend.services.perception_lab.families.bridge import FamilyBridge


def bridge(slot, producer):
    return FamilyBridge(slot, producer, tuple(op.key for op in slot.operations
                                             if op.producer_key == producer), b"")


def test_unadmitted_shading_does_not_disable_luminance():
    registry.checked_slots()
    luminance = bridge(illumination.MODULE, "illumination.luminance_producer")
    shading = bridge(illumination.MODULE, "illumination.shading_producer")
    assert luminance.capability() == CapabilityState.AVAILABLE
    assert shading.capability() == CapabilityState.UNAVAILABLE
    assert "permission" in shading.capability_reason()


def test_missing_cpu_package_disables_only_producer_not_registry(monkeypatch):
    monkeypatch.setattr(surface_pattern.cpu, "is_available", lambda: False)
    registry.checked_slots()
    adapter = bridge(surface_pattern.MODULE, surface_pattern.PRODUCER)
    assert adapter.capability() == CapabilityState.UNAVAILABLE
    assert "OpenCV" in adapter.capability_reason()


def test_invalid_dependency_owner_cannot_escape_gate():
    model = {**illumination.MODULE.models[0], "producer_keys": ["colour.someone_else"]}
    broken = replace(illumination.MODULE, models=(model,))
    with pytest.raises(ValueError, match="producer keys"):
        registry.checked_slots(tuple(broken if s.family == broken.family else s for s in registry.SLOTS))


def test_family_identity_distinguishes_code_from_model_and_offers_remedy():
    from backend.services.perception_lab.producers import adapter_identity
    assert adapter_identity("illumination.luminance_producer").kind == "code"
    assert adapter_identity(surface_pattern.PRODUCER).model is None
    shading = adapter_identity("illumination.shading_producer")
    assert shading.kind == "model"
    assert shading.model == "intrinsic-paper-weights"
    assert "permission" in shading.remedy
