"""
Writer ledger audit — ATLAS-WRITER-MASS-BUILD-001D.

Prints the integrity report for the Writer's collections against the configured database:
duplicate rows under an identity that is now unique, operations that died mid-transition,
scenes where two blocks claim one id, and blocks whose pointer names a version that does
not exist. REPORT ONLY. It creates no index and discards no row — which of two duplicate
operators a book's provenance meant is a decision for the author, made by hand, and then
`ensure_indexes` runs clean on the next start.

    python -m scripts.writer_ledger_audit            # the report
    python -m scripts.writer_ledger_audit --indexes  # also attempt index creation (non-strict)

Exit status is 1 when anything is found, so a deploy step can refuse to proceed on it.
"""
from __future__ import annotations

import asyncio
import json
import sys


async def main(argv: list) -> int:
    from backend.services.writer import ledger

    report = await ledger.integrity_report()
    if "--indexes" in argv:
        report["indexes"] = await ledger.ensure_indexes(strict=False)
    print(ledger.format_report(report))
    if "--json" in argv:
        print(json.dumps(report, default=str, indent=2))
    if report["ok"]:
        print("Writer ledger: clean.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
