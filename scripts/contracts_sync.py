#!/usr/bin/env python3
"""
HARNESS-001A — keep the frontend's copy of the shared contracts byte-identical to the canonical
ones, and say plainly why a copy exists at all.

THE CANONICAL FILES ARE `contracts/*.json` AT THE REPO ROOT. The backend reads them there. The
frontend cannot: the Vercel project deploys by uploading `frontend/` as the deployment source
(created 2026-08-02 by a CLI `vercel deploy` from that directory), so anything the bundle imports
from outside `frontend/` is present on this machine and absent in production. An
`import GRAMMAR from '../../../contracts/…json'` builds green here and fails the deploy.

So the frontend imports `frontend/src/contracts/*.json`, this script writes those files, and TWO
tests — one in each language — assert the copy is byte-identical to the canonical file. Editing
either without running this script fails both suites by name. That is the whole compensation for
the duplication, and it is deliberately noisy rather than clever.

    python scripts/contracts_sync.py            # write the mirror
    python scripts/contracts_sync.py --check    # exit 1 if it has drifted

Writes nothing outside `frontend/src/contracts/`. Touches no database and makes no network call.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = REPO_ROOT / "contracts"
MIRROR_DIR = REPO_ROOT / "frontend" / "src" / "contracts"

#: The contracts the frontend bundle actually imports. A canonical contract no frontend module
#: reads does NOT belong here — mirroring it would create a second copy nobody consumes, which is
#: drift with none of the benefit.
MIRRORED = (
    "perceptual-action-grammar.v1.json",
    "attunement-lexicon.v1.json",
)

MIRROR_README = """\
# Do not edit these files.

They are byte-identical copies of `contracts/*.json` at the repo root, written by
`scripts/contracts_sync.py`. The canonical files are the ones at the root; these exist only
because the Vercel deploy uploads `frontend/` as its source, so the bundle cannot import from
outside this directory tree.

Edit `contracts/…`, then run:

    python scripts/contracts_sync.py

`contracts.parity.test.js` (here) and `test_inquiry_contracts.py` (backend) both fail by name
if these drift from the canonical files.
"""


def pairs() -> List[Tuple[Path, Path]]:
    return [(CANONICAL_DIR / name, MIRROR_DIR / name) for name in MIRRORED]


def drifted() -> List[str]:
    """Names of contracts whose mirror is missing or different. Empty means in sync."""
    out: List[str] = []
    for canonical, mirror in pairs():
        if not canonical.exists():
            out.append(f"{canonical.name} (canonical missing)")
            continue
        if not mirror.exists() or mirror.read_bytes() != canonical.read_bytes():
            out.append(canonical.name)
    return out


def sync() -> List[str]:
    """Write the mirror. Returns the names actually rewritten."""
    MIRROR_DIR.mkdir(parents=True, exist_ok=True)
    (MIRROR_DIR / "README.md").write_text(MIRROR_README, encoding="utf-8")
    written: List[str] = []
    for canonical, mirror in pairs():
        data = canonical.read_bytes()
        if not mirror.exists() or mirror.read_bytes() != data:
            mirror.write_bytes(data)
            written.append(canonical.name)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--check", action="store_true",
                    help="report drift and exit 1 instead of writing")
    args = ap.parse_args()

    if args.check:
        bad = drifted()
        if bad:
            print("contracts out of sync: " + ", ".join(bad))
            print("run: python scripts/contracts_sync.py")
            return 1
        print(f"contracts in sync ({len(MIRRORED)} files)")
        return 0

    written = sync()
    if written:
        print("wrote: " + ", ".join(written))
    else:
        print(f"already in sync ({len(MIRRORED)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
