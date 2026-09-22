"""The fixed, declarative interface owned by each future field family."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True)
class FamilyForm:
    key: str
    label: str
    quantity: str
    description: str
    views: tuple[str, ...]


@dataclass(frozen=True)
class FamilyOperation:
    key: str
    label: str
    form_key: str
    producer_key: str
    parameters: Mapping[str, Mapping]
    prompt_intents: tuple[str, ...] = ()
    learned: bool = False


@dataclass(frozen=True)
class ProducedField:
    metadata: Mapping
    values: Sequence[float]
    valid: Sequence[bool]
    producer_revision: str
    model: str | None = None
    device: str | None = None


@dataclass(frozen=True)
class FamilyModule:
    family: str
    label: str
    available: bool
    reason: str
    forms: tuple[FamilyForm, ...] = ()
    operations: tuple[FamilyOperation, ...] = ()
    producers: Mapping[str, Callable] = None
    models: tuple[Mapping, ...] = ()
    dependencies: tuple[Mapping, ...] = ()
