"""One explicit registry; fixed imports, no discovery and no model loading."""
from __future__ import annotations

from . import colour, depth, illumination, orientation_flow, surface_form, surface_pattern
from .base import FamilyModule

FAMILY_KEYS = ("colour", "illumination", "surface_pattern", "orientation_flow", "depth", "surface_form")
SLOTS = (colour.MODULE, illumination.MODULE, surface_pattern.MODULE,
         orientation_flow.MODULE, depth.MODULE, surface_form.MODULE)


def checked_slots(slots: tuple[FamilyModule, ...] = SLOTS) -> dict[str, FamilyModule]:
    if tuple(slot.family for slot in slots) != FAMILY_KEYS:
        raise ValueError("family slots must be the six fixed keys in registry order")
    seen_forms, seen_ops, seen_producers = set(), set(), set()
    for slot in slots:
        if not slot.label or not slot.reason or not isinstance(slot.available, bool):
            raise ValueError(f"malformed family declaration {slot.family}")
        if not slot.available and (slot.forms or slot.operations or slot.producers or slot.models):
            raise ValueError(f"unavailable family {slot.family} declares live producers or forms")
        forms = {form.key for form in slot.forms}
        producers = set(slot.producers or {})
        if len(forms) != len(slot.forms) or len(producers) != len(slot.producers or {}):
            raise ValueError(f"duplicate family-local declaration in {slot.family}")
        if slot.available and (not forms or not slot.operations or not producers):
            raise ValueError(f"available family {slot.family} has no complete instrument")
        for form in slot.forms:
            if not form.key.startswith(slot.family + ".") or not form.views or not form.quantity:
                raise ValueError(f"malformed form {form.key}")
            if form.key in seen_forms:
                raise ValueError(f"duplicate form {form.key}")
            seen_forms.add(form.key)
        for op in slot.operations:
            if (not op.key.startswith(slot.family + ".") or op.form_key not in forms
                    or op.producer_key not in producers or op.key in seen_ops
                    or any(not intent or len(intent) > 160 for intent in op.prompt_intents)):
                raise ValueError(f"malformed or duplicate operation {op.key}")
            if op.learned and not slot.models:
                raise ValueError(f"learned operation {op.key} has no admitted model declaration")
            seen_ops.add(op.key)
        for key, producer in (slot.producers or {}).items():
            if not key.startswith(slot.family + ".") or not callable(producer) or key in seen_producers:
                raise ValueError(f"malformed or duplicate producer {key}")
            seen_producers.add(key)
        for model in slot.models:
            if (not all(model.get(k) for k in ("key", "revision", "license", "checkpoint_digest"))
                    or type(model.get("admitted")) is not bool):
                raise ValueError(f"incomplete model declaration in {slot.family}")
        for dependency in slot.dependencies:
            if (not all(dependency.get(k) for k in ("package", "version", "license"))
                    or type(dependency.get("admitted")) is not bool):
                raise ValueError(f"incomplete dependency declaration in {slot.family}")
        if slot.available and any(not declaration["admitted"] for declaration in
                                  (*slot.models, *slot.dependencies)):
            raise ValueError(f"unadmitted model or dependency in {slot.family}")
    return {slot.family: slot for slot in slots}


REGISTRY = checked_slots()


def validate_field_artifact(artifact) -> None:
    family = artifact.identity.organ_family.value
    slot = REGISTRY.get(family)
    if slot is None or not slot.available:
        raise ValueError(f"{family} is not an available field family")
    payload = artifact.measurement.payload
    op = next((item for item in slot.operations if item.key == artifact.identity.operation), None)
    if op is None or payload is None or payload.form_key != op.form_key:
        raise ValueError("sample grid operation/form does not match its family slot")
    if payload.manifest["metadata"]["source_digest"] != artifact.provenance.source_image_digest:
        raise ValueError("sample grid source digest differs from artifact provenance")
