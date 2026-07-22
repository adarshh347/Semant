"""Detached-ground corpus sweep (R2-A2S) — STRICTLY READ-ONLY.

Follow-up to rehearsal run 003 (A2), which found that percept `pctx_mrqp950d_0`
("the upper head") cites two Grounds whose Regions no longer exist, because a
re-dissect replaced the post's `fine_*` region set with an `arch_*` one. Grounds
carrying their own geometry (`field`, `frame`) survived the same event.

This script answers ONE question across the whole corpus: is that a one-post
accident or a standing property of re-dissection?

READ-ONLY CONTRACT
    Issues only `find`. Never updates, inserts, deletes, or repairs anything —
    including the detached grounds it reports. Repair is explicitly out of scope
    (it would be a production mutation, and no repair has been designed).

DETACHMENT DEFINITION
    Mirrors `frontend/src/differential/grounds.js :: resolveGround` exactly,
    which is the authority. Three cases, and getting the third wrong would
    inflate the count:

      1. `region` ground  -> detached when `region_id` does not resolve against
         the post's current regions.
      2. composite (`constellation` / `relation`) -> detached ONLY when it has
         `member_ids`, no member survives, AND it carries no raw `points`.
      3. `field` / `path` / `boundary` / `frame` -> NEVER detached; they carry
         their own geometry and are immune to re-dissection.

Usage:
    python scripts/detached_ground_sweep.py [--json OUT.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mirrors grounds.js. Composite types reference sibling grounds by id; the rest
# of the spatial types carry their own geometry.
COMPOSITE_TYPES = {"constellation", "relation"}
GEOMETRY_BEARING = {"field", "path", "boundary", "frame"}


def resolve_ground(ground: Dict[str, Any], regions_by_id: Dict[str, Any],
                   grounds_by_id: Dict[str, Any]) -> Dict[str, Any]:
    """Port of grounds.js resolveGround. Returns {kind, detached, missing}."""
    gtype = ground.get("ground_type")

    if gtype == "region":
        rid = ground.get("region_id")
        ok = rid in regions_by_id
        return {"kind": "reference", "detached": not ok,
                "missing": [] if ok else [rid]}

    if gtype in COMPOSITE_TYPES:
        member_ids = ground.get("member_ids") or []
        surviving = [m for m in member_ids if m in grounds_by_id]
        has_points = bool(ground.get("points"))
        detached = bool(member_ids) and not surviving and not has_points
        return {"kind": "composite", "detached": detached,
                "missing": [m for m in member_ids if m not in grounds_by_id]}

    # field / path / boundary / frame — own geometry, never detached.
    return {"kind": "geometry", "detached": False, "missing": []}


async def sweep() -> Dict[str, Any]:
    from backend.database import post_collection  # noqa: E402

    totals = Counter()
    rows: List[Dict[str, Any]] = []

    # Projection keeps this cheap and makes the read-only intent obvious.
    cursor = post_collection.find(
        {}, {"region_annotations": 1, "grounds": 1, "percepts": 1})

    async for post in cursor:
        totals["posts"] += 1
        regions = post.get("region_annotations") or []
        grounds = post.get("grounds") or []
        percepts = post.get("percepts") or []
        if not grounds and not percepts:
            continue
        totals["posts_with_annotation"] += 1

        regions_by_id = {r.get("id"): r for r in regions}
        grounds_by_id = {g.get("id"): g for g in grounds}

        resolved: Dict[str, Any] = {}
        for g in grounds:
            r = resolve_ground(g, regions_by_id, grounds_by_id)
            resolved[g.get("id")] = r
            totals["grounds"] += 1
            totals[f"grounds_{r['kind']}"] += 1
            if r["detached"]:
                totals[f"detached_{r['kind']}"] += 1
                totals["detached_grounds"] += 1

        post_detached_percepts = []
        for p in percepts:
            totals["percepts"] += 1
            gids = p.get("ground_ids") or []
            if not gids:
                totals["percepts_citing_no_ground"] += 1
                continue
            totals["percepts_citing_grounds"] += 1
            det = [gid for gid in gids
                   if gid in resolved and resolved[gid]["detached"]]
            absent = [gid for gid in gids if gid not in resolved]
            if det or absent:
                totals["percepts_with_detached"] += 1
                fully = len(det) + len(absent) == len(gids)
                if fully:
                    totals["percepts_fully_unevidenced"] += 1
                post_detached_percepts.append({
                    "percept_id": p.get("id"),
                    "expression": (p.get("expression") or "")[:120],
                    "cited_grounds": len(gids),
                    "detached_grounds": [
                        {"ground_id": gid,
                         "ground_type": grounds_by_id[gid].get("ground_type"),
                         "missing_region_ids": resolved[gid]["missing"]}
                        for gid in det],
                    "grounds_absent_entirely": absent,
                    "fully_unevidenced": fully,
                })

        # Detached grounds NOT cited by any percept still evidence the mechanism —
        # they simply have not harmed a curator statement yet. Reporting only the
        # percept-cited ones would understate how often re-dissection strands
        # evidence.
        cited_ids = {gid for p in percepts for gid in (p.get("ground_ids") or [])}
        uncited_detached = [
            {"ground_id": gid,
             "ground_type": grounds_by_id[gid].get("ground_type"),
             "missing_region_ids": r["missing"]}
            for gid, r in resolved.items()
            if r["detached"] and gid not in cited_ids]
        totals["detached_but_uncited"] += len(uncited_detached)

        if post_detached_percepts or uncited_detached:
            rows.append({
                "post_id": str(post["_id"]),
                "current_region_ids": [r.get("id") for r in regions],
                "surviving_geometry_grounds": [
                    {"ground_id": g.get("id"), "ground_type": g.get("ground_type")}
                    for g in grounds
                    if g.get("ground_type") in GEOMETRY_BEARING],
                "percepts": post_detached_percepts,
                "detached_but_uncited_grounds": uncited_detached,
            })
            totals["posts_affected"] += 1
            if post_detached_percepts:
                totals["posts_with_harmed_percepts"] += 1

    return {"totals": dict(totals), "affected_posts": rows}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", dest="out", default=None,
                    help="write the full evidence record to this path")
    args = ap.parse_args()

    result = asyncio.run(sweep())
    t = result["totals"]

    print("=== Detached-ground corpus sweep (READ-ONLY) ===")
    print(f"posts scanned                : {t.get('posts', 0)}")
    print(f"  with grounds or percepts   : {t.get('posts_with_annotation', 0)}")
    print(f"  AFFECTED (any detachment)  : {t.get('posts_affected', 0)}")
    print(f"  with harmed percepts       : {t.get('posts_with_harmed_percepts', 0)}")
    print()
    print(f"grounds total                : {t.get('grounds', 0)}")
    print(f"  reference-based (region)   : {t.get('grounds_reference', 0)}"
          f"   detached: {t.get('detached_reference', 0)}")
    print(f"  composite                  : {t.get('grounds_composite', 0)}"
          f"   detached: {t.get('detached_composite', 0)}")
    print(f"  geometry-bearing           : {t.get('grounds_geometry', 0)}"
          f"   detached: {t.get('detached_geometry', 0)} (immune by construction)")
    print()
    print(f"percepts total               : {t.get('percepts', 0)}")
    print(f"  citing >=1 ground          : {t.get('percepts_citing_grounds', 0)}")
    print(f"  citing no ground at all    : {t.get('percepts_citing_no_ground', 0)}")
    print(f"  WITH DETACHED EVIDENCE     : {t.get('percepts_with_detached', 0)}")
    print(f"  FULLY UNEVIDENCED          : {t.get('percepts_fully_unevidenced', 0)}")
    print(f"\ndetached but uncited by any percept: {t.get('detached_but_uncited', 0)}")

    ref = t.get("grounds_reference", 0)
    if ref:
        pct = 100.0 * t.get("detached_reference", 0) / ref
        print(f"\nreference-ground detachment rate: {pct:.1f}%")

    for row in result["affected_posts"]:
        print(f"\n--- post {row['post_id']}")
        print(f"    current regions: {row['current_region_ids']}")
        for p in row["percepts"]:
            flag = "FULLY UNEVIDENCED" if p["fully_unevidenced"] else "partial"
            print(f"    percept {p['percept_id']} [{flag}] "
                  f"{len(p['detached_grounds'])}/{p['cited_grounds']} detached"
                  f"  {p['expression']!r}")
            for d in p["detached_grounds"]:
                print(f"        {d['ground_id']} ({d['ground_type']}) "
                      f"-> missing {d['missing_region_ids']}")
        for d in row.get("detached_but_uncited_grounds", []):
            print(f"    {d['ground_id']} ({d['ground_type']}) -> missing "
                  f"{d['missing_region_ids']}  [detached, NOT cited by a percept]")
        if row["surviving_geometry_grounds"]:
            print(f"    surviving geometry-bearing grounds: "
                  f"{[g['ground_type'] for g in row['surviving_geometry_grounds']]}")

    if args.out:
        with open(args.out, "w") as fh:
            json.dump(result, fh, indent=2, sort_keys=True)
        print(f"\nevidence written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
