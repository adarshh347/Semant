#!/usr/bin/env python3
"""
Build (or inspect) the retina index from the live `region_embeddings` collection.

    python scripts/retina_build.py                      # full rebuild, then report
    python scripts/retina_build.py --limit 500          # a sample (partial index)
    python scripts/retina_build.py --space "dinov2_vits14|identity|dino-v1|384"
    python scripts/retina_build.py --status             # what is indexed now; build nothing
    python scripts/retina_build.py --probe <embedding_id>   # candidate-quality spot check

This is the measurement instrument for the lane's deliverable — index size, build time and the
"are the neighbours visibly related?" check all come out of here, against the real corpus
rather than the fixture.

Mongo is the source of truth. This only ever replaces the derived copy, so it is safe to run
repeatedly; it writes nothing back and touches no post. Needs the usual `.env` (MONGO_DETAILS).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import retina                                       # noqa: E402
from backend.services.retina.store import RetinaStore                     # noqa: E402


def _mb(n) -> str:
    return f"{(n or 0) / (1024 * 1024):.1f} MB"


def _print_index(report: dict) -> None:
    totals = report.get("totals") or {}
    print(f"\n  path            {report.get('path')}")
    print(f"  built_at        {report.get('built_at')}")
    print(f"  rows            {totals.get('rows')} in {totals.get('spaces')} space(s)")
    print(f"  build time      {totals.get('build_seconds')}s")
    print(f"  index size      {_mb(totals.get('index_bytes'))}")
    if report.get("partial") or report.get("truncated"):
        print(f"  ⚠ PARTIAL       partial={report.get('partial')} "
              f"truncated={report.get('truncated')} — this index covers a FRACTION of the corpus")

    print("\n  spaces")
    for space, e in sorted((report.get("spaces") or {}).items()):
        legacy = "  [legacy — unspaced source rows]" if e.get("legacy") else ""
        print(f"    {space}")
        print(f"      {e.get('rows')} rows · {e.get('dim')}-d · {e.get('model') or '?'}"
              f" · role={e.get('role') or '-'}{legacy}")
        print(f"      table={e.get('table')} fingerprint={str(e.get('fingerprint'))[:16]}…")

    skipped = {r: n for r, n in (report.get("skipped") or {}).items() if n}
    print(f"\n  skipped         {totals.get('skipped', sum(skipped.values()))}"
          f" of {totals.get('scanned', '?')} scanned")
    for reason, n in sorted(skipped.items(), key=lambda kv: -kv[1]):
        print(f"      {reason:<18} {n}")
    for ex in (report.get("skipped_examples") or [])[:5]:
        print(f"      e.g. {ex.get('reason'):<16} {ex.get('embedding_id') or '(no id)'}")


def _probe(store: RetinaStore, embedding_id: str, k: int) -> None:
    """The candidate-quality spot check: are a region's nearest neighbours visibly related?

    Prints ids and scores only — judging whether the neighbours actually look alike is a human
    step, and this tool deliberately does not pretend to do it.
    """
    print(f"\n  probe  {embedding_id}")
    try:
        got = retina.retrieve_candidates(embedding_id=embedding_id, k=k, store=store)
    except retina.RetinaError as e:
        print(f"    {type(e).__name__}: {e}")
        alts = getattr(e, "alternatives", None)
        for a in (alts or [])[:5]:
            print(f"      alternative: {a}")
        return
    if not got:
        print("    (looked; nothing returned)")
        return
    print(f"    space  {got[0]['space']}")
    for c in got:
        print(f"    {c['score']:>7.4f}  post={c['post_id']}  region={c['region_id']}"
              f"  rev={c['geometry_rev']}  route={c['route']}")
    print("\n    These are CANDIDATES — vector-space neighbours, not relations and not")
    print("    measurements. Grounding decides truth; the retina only narrows the search.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=None,
                    help="index at most N source rows (produces a PARTIAL index)")
    ap.add_argument("--space", action="append", dest="spaces", default=None,
                    help="rebuild only this space key (repeatable; PARTIAL)")
    ap.add_argument("--path", default=None, help=f"index location (default: {retina.default_db_path()})")
    ap.add_argument("--status", action="store_true", help="report what is indexed; build nothing")
    ap.add_argument("--probe", default=None, metavar="EMBEDDING_ID",
                    help="after building, show this embedding's nearest neighbours")
    ap.add_argument("-k", type=int, default=8, help="neighbours to show for --probe (default 8)")
    ap.add_argument("--json", action="store_true", help="emit the raw report as JSON")
    args = ap.parse_args()

    if not retina.is_available():
        print(f"✗ {retina.unavailable_reason()}", file=sys.stderr)
        return 2

    store = RetinaStore(args.path) if args.path else RetinaStore()

    if args.status:
        report = retina.index_status(store)
        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            print(f"\nretina · {report['status']}")
            if report["status"] in ("not_built", "unavailable"):
                print(f"  {report.get('reason')}")
            else:
                _print_index(report)
    else:
        scope = []
        if args.limit:
            scope.append(f"limit={args.limit}")
        if args.spaces:
            scope.append(f"spaces={args.spaces}")
        print(f"building retina from region_embeddings{' (' + ', '.join(scope) + ')' if scope else ''} …")
        report = asyncio.run(retina.index_rebuild(store=store, limit=args.limit, spaces=args.spaces))
        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            print(f"\nretina · {report['status']}")
            _print_index(report)
            if report.get("dropped_tables"):
                print(f"\n  dropped         {report['dropped_tables']}")

    if args.probe:
        _probe(store, args.probe, args.k)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
