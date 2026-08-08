"""
HARNESS-001A — reading the shared contracts, and refusing to run without them.

The canonical files are `contracts/*.json` at the repo root. This module finds them, loads them
once, and hands them out. It does not interpret them; `grammar.py` and `lexicon.py` do that.

TWO THINGS WORTH STATING.

WHY A HARD FAILURE ON A MISSING FILE. A contract that cannot be read is not a degraded mode. The
whole point of moving the closed sets out of JavaScript was that one law governs two runtimes; a
Python fallback table would be a third vocabulary invented at the moment the first one went
missing, and it would be indistinguishable from the real thing until it disagreed. So the loader
raises, and the caller finds out at import rather than three layers down inside a validator that
silently accepted an action nobody declared.

WHY THE SCHEMA VERSION IS CHECKED HERE. Every consumer asserts the version it was written
against. A contract bumped to `.v2` without its readers moving is exactly the failure the version
string exists to catch, and catching it at load is cheaper than catching it in a parity test.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

#: `backend/services/inquiry/contracts.py` → repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_DIR = REPO_ROOT / "contracts"

GRAMMAR_FILE = "perceptual-action-grammar.v1.json"
LEXICON_FILE = "attunement-lexicon.v1.json"

GRAMMAR_SCHEMA_VERSION = "perceptual-action-grammar.v1"
LEXICON_SCHEMA_VERSION = "attunement-lexicon.v1"


class ContractError(RuntimeError):
    """A contract is missing, unreadable, or not the version this code enforces."""


@lru_cache(maxsize=None)
def load(filename: str, expect_version: str) -> Dict[str, Any]:
    """The contract, as plain data. Cached — these files do not change inside a process."""
    path = CONTRACTS_DIR / filename
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError(
            f"cannot read the shared contract at {path}. This is not recoverable: the closed "
            f"action vocabulary lives in that file and inventing a fallback here would create a "
            f"second grammar that looks like the first until it disagrees."
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


def grammar_contract() -> Dict[str, Any]:
    return load(GRAMMAR_FILE, GRAMMAR_SCHEMA_VERSION)


def lexicon_contract() -> Dict[str, Any]:
    return load(LEXICON_FILE, LEXICON_SCHEMA_VERSION)
