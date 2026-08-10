#!/usr/bin/env python3
"""
PERCEPTUAL-ORGANS-002 Lane A — write the Perception Lab's JSON Schemas for readers outside Python.

WHAT THESE ARE FOR, and what they are NOT. `contracts/perception-lab.v1.json` is the canonical
VOCABULARY — organs, operations, closed sets, laws. These files are the canonical RECORD SHAPES,
generated from the Pydantic models so that a rehearsal harness, a notebook, or a language with no
Pydantic can validate a `LabRun` without reimplementing one.

They are GENERATED, and generated files that are committed drift. The compensation is the same
one `scripts/contracts_sync.py` uses and it is deliberately noisy rather than clever:

    python scripts/perception_lab_schemas.py            # write them
    python scripts/perception_lab_schemas.py --check    # exit 1 if they have drifted

and `backend/tests/test_perception_lab_contracts.py` runs `--check` by name. A field added to a
model and not regenerated here fails the suite.

They live under `research/` for the reason `research/rehearsals/schemas/` does: anything the test
suite reads must be in the repository, and the vault is not versioned.

Writes nothing outside `research/perception_lab/schemas/`. No database, no network.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.schemas.perception_lab import RECORD_MODELS  # noqa: E402

SCHEMA_DIR = REPO_ROOT / "research" / "perception_lab" / "schemas"

README = """\
# Perception Lab record schemas (generated)

JSON Schema (draft 2020-12) for the five Perception Lab records, generated from
`backend/schemas/perception_lab.py` by `scripts/perception_lab_schemas.py`.

Do not edit them. Edit the Pydantic models, then run:

    python scripts/perception_lab_schemas.py

`backend/tests/test_perception_lab_contracts.py` runs `--check` and fails by name if these drift.

The canonical VOCABULARY — organ families, operations, closed sets, refusal codes, laws — is
`contracts/perception-lab.v1.json`, not these files. These are record SHAPES only.
"""


def _filename(name: str) -> str:
    """`LabSession` → `lab-session.schema.json`."""
    out: List[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i:
            out.append("-")
        out.append(ch.lower())
    return "".join(out) + ".schema.json"


def rendered() -> Dict[str, str]:
    """`{filename: text}` for every record schema, plus the README."""
    files: Dict[str, str] = {"README.md": README}
    for name, model in RECORD_MODELS.items():
        schema = model.model_json_schema(mode="serialization")
        schema = {"$schema": "https://json-schema.org/draft/2020-12/schema",
                  "$id": f"semant:perception-lab/{_filename(name)}",
                  **schema}
        files[_filename(name)] = json.dumps(schema, indent=2, sort_keys=False) + "\n"
    return files


def drifted() -> List[str]:
    out: List[str] = []
    for name, text in rendered().items():
        path = SCHEMA_DIR / name
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            out.append(name)
    return out


def write() -> List[str]:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    for name, text in rendered().items():
        path = SCHEMA_DIR / name
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
            written.append(name)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").strip().split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="report drift and exit 1 instead of writing")
    args = ap.parse_args()

    if args.check:
        bad = drifted()
        if bad:
            print("perception lab schemas out of sync: " + ", ".join(bad))
            print("run: python scripts/perception_lab_schemas.py")
            return 1
        print(f"perception lab schemas in sync ({len(rendered())} files)")
        return 0

    written = write()
    print(("wrote: " + ", ".join(written)) if written
          else f"already in sync ({len(rendered())} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
