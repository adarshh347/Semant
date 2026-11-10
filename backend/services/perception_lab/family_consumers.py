"""Bounded pure family readings, consumed through the existing derivation route."""
from __future__ import annotations

import json

from backend.services.perception_lab.field_data import FieldError

MAX_RESULT_BYTES = 4 * 1024 * 1024
REVISION = "family-field-consumers.v1"


def consume(family, operation, grid, points, parameters):
    from backend.services.perception_lab.families.registry import REGISTRY

    slot = REGISTRY.get(family)
    handler = (slot.consumers or {}).get(operation) if slot and slot.available else None
    if not handler or not operation.startswith(family + "."):
        raise FieldError("This saved field has no declared consumer with that name.")
    if not isinstance(parameters, dict) or len(json.dumps(parameters)) > 16384:
        raise FieldError("Consumer parameters exceed the bounded request.")
    result = handler(grid, points, parameters)
    try:
        encoded = json.dumps(result, allow_nan=False, separators=(",", ":"))
    except (ValueError, TypeError) as exc:
        raise FieldError("Consumer returned non-finite or unsupported data.") from exc
    if not isinstance(result, dict) or len(encoded.encode("utf-8")) > MAX_RESULT_BYTES:
        raise FieldError("Consumer result exceeds the bounded saved reading.")
    return result
