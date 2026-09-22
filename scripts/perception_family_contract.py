#!/usr/bin/env python3
"""Render exactly one fixed family's contract into its own owned file.

Usage: python scripts/perception_family_contract.py colour [--check]
This command never writes the shared Lab vocabulary or another family's file.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.services.perception_lab.families.registry import REGISTRY, FAMILY_KEYS  # noqa: E402


def document(family: str) -> dict:
    slot = REGISTRY[family]
    return {
        "schema_version": "perception-lab-family.v1",
        "family": slot.family,
        "label": slot.label,
        "available": slot.available,
        "reason": slot.reason,
        "forms": [dict(key=f.key, label=f.label, quantity=f.quantity,
                       description=f.description, views=list(f.views)) for f in slot.forms],
        "operations": [dict(key=o.key, label=o.label, form_key=o.form_key,
                            producer_key=o.producer_key, parameters=o.parameters,
                            prompt_intents=list(o.prompt_intents), learned=o.learned)
                       for o in slot.operations],
        "producer_keys": sorted(slot.producers or {}),
        "models": list(slot.models),
        "dependencies": list(slot.dependencies),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("family", choices=FAMILY_KEYS)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = ROOT / "contracts" / "perception-lab-families" / f"{args.family}.json"
    rendered = json.dumps(document(args.family), indent=2, sort_keys=True) + "\n"
    if args.check:
        if not path.exists() or path.read_text() != rendered:
            print(f"family contract drift: {path}")
            return 1
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
