"""
PERCEPTUAL-ORGANS-002 Lane A — reading the Perception Lab contract, and refusing to run without it.

The canonical file is `contracts/perception-lab.v1.json` at the repo root. This module finds it,
loads it once, and hands out plain data plus two cheap indexes. It does not interpret it:
`definitions.py` builds the typed registry, `backend/schemas/perception_lab.py` builds the records.

WHY THE INDEXES LIVE HERE AND NOT IN `definitions.py`. The record schemas need one thing from the
registry — "is this a real operation, and whose?" — in order to fail closed on an undeclared
operation key. If they imported the rich registry they would import the thing that imports them.
So the two flat dictionaries a validator needs sit at the bottom of the stack, and the typed
registry is built on top:

    contracts.py  ←  backend/schemas/perception_lab.py  ←  definitions.py

WHY A HARD FAILURE ON A MISSING FILE. Same reason as `services/inquiry/contracts.py`, which this
follows deliberately rather than inventing a second loader idiom: a Python fallback table would be
a second vocabulary invented at the moment the first went missing, indistinguishable from the real
one until it disagreed. The loader raises at import.

PURE. No database, no network, no model.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Tuple

#: `backend/services/perception_lab/contracts.py` → repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_DIR = REPO_ROOT / "contracts"

LAB_FILE = "perception-lab.v1.json"
LAB_SCHEMA_VERSION = "perception-lab.v1"


class ContractError(RuntimeError):
    """The lab contract is missing, unreadable, or not the version this code enforces."""


@lru_cache(maxsize=None)
def load(filename: str, expect_version: str) -> Dict[str, Any]:
    """The contract, as plain data. Cached — this file does not change inside a process."""
    path = CONTRACTS_DIR / filename
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError(
            f"cannot read the Perception Lab contract at {path}. This is not recoverable: the "
            f"closed organ, operation, outcome and refusal vocabularies live in that file, and a "
            f"fallback invented here would look exactly like the real one until it disagreed."
        ) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContractError(f"{path} is not valid JSON: {exc}") from exc
    found = data.get("schema_version")
    if found != expect_version:
        raise ContractError(
            f"{path} declares schema_version {found!r}; this code enforces {expect_version!r}. "
            f"A contract may be versioned forward, but its readers move with it."
        )
    return data


def lab_contract() -> Dict[str, Any]:
    return load(LAB_FILE, LAB_SCHEMA_VERSION)


@lru_cache(maxsize=None)
def organ_index() -> Dict[str, bool]:
    """`{family: enabled}` for all eight families, in contract order."""
    return {str(o["family"]): bool(o["enabled"]) for o in lab_contract()["organs"]}


@lru_cache(maxsize=None)
def operation_index() -> Dict[str, str]:
    """`{operation_key: organ_family}` across every enabled organ's closed registry.

    A key absent from here is `unsupported_operation`. There is no second place to look.
    """
    out: Dict[str, str] = {}
    for organ in lab_contract()["organs"]:
        for op in organ.get("operations", ()):
            out[str(op["key"])] = str(organ["family"])
    return out


@lru_cache(maxsize=None)
def closed_set(name: str) -> Tuple[str, ...]:
    """One closed set, as a tuple. Raises rather than returning () for an undeclared name."""
    sets = lab_contract()["closed_sets"]
    if name not in sets:
        raise ContractError(f"{name!r} is not a closed set in {LAB_FILE}")
    return tuple(str(v) for v in sets[name])
