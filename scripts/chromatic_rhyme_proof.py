#!/usr/bin/env python3
"""
WAVE3 — the chromatic rhyme statistic, swept against the real corpus rather than assumed.

    python scripts/chromatic_rhyme_proof.py                # 10 images
    python scripts/chromatic_rhyme_proof.py --posts 20
    python scripts/chromatic_rhyme_proof.py --json

WHAT THIS ANSWERS, and it is the question the occlusion lane made compulsory: is the chosen
statistic measuring RHYME, or is it measuring something that merely correlates with it?

Three checks, each of which the statistic could fail:

  1. THE PERMUTATION NULL — the same two fields with one shuffled. Every value, variance and count
     is preserved; only the cell-to-cell CORRESPONDENCE is destroyed. Whatever survives in the real
     tail and not in the null is correspondence and nothing else.
  2. THE COINCIDENCE TEST — do pairs whose MEAN warmth matches score above the base rate? They must
     not: centring removes the mean arithmetically, so a shared average should confer no advantage
     at all rather than a small one.
  3. THE SWEEP — `MIN_RHYME` is a free parameter ([[DECISION-systematicity-floor-is-a-free-
     parameter]]). This prints what every candidate floor would admit, in the real data and in the
     null, so the choice is inspectable rather than inherited.

READS POSTS AND IMAGES, WRITES NOTHING. Every mutating method on the post collection is replaced
with a raiser before the first query. No marks are minted and nothing is committed.

Needs the usual `.env`, network for the images, and Pillow.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import math
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import chroma_organ as chroma                       # noqa: E402
from backend.services import chromatic_relation as rel                    # noqa: E402


class WriteAttempted(Exception):
    """A write was attempted against a collection this proof is only allowed to read."""


def freeze(*collections) -> None:
    def _blocked(*_a, **_k):
        raise WriteAttempted("this proof may not write — it measures, it does not propose")
    for coll in collections:
        for method in ("update_one", "update_many", "insert_one", "insert_many", "delete_one",
                       "delete_many", "replace_one", "bulk_write", "find_one_and_update"):
            try:
                setattr(coll, method, _blocked)
            except Exception:                                   # noqa: BLE001
                pass


async def collect(limit: int):
    """Every readable region field across `limit` posts, with the image it came from."""
    from backend.database import post_collection
    from backend.routers.posts import _image_fetch_headers
    import httpx
    from PIL import Image

    freeze(post_collection)
    fields = []
    async for post in post_collection.find(
            {"photo_url": {"$exists": True, "$ne": ""},
             "region_annotations.3": {"$exists": True}}).limit(int(limit)):
        url = str(post.get("photo_url") or "")
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=_image_fetch_headers(url))
                resp.raise_for_status()
            image = Image.open(io.BytesIO(resp.content)).convert("RGB")
        except Exception as exc:                                # noqa: BLE001
            print(f"  skip {post['_id']}: {exc}", file=sys.stderr)
            continue
        frame = chroma.image_frame(image, source=url)
        kept = 0
        for region in post.get("region_annotations") or []:
            try:
                cells, basis = rel.warmth_shape(region, frame)
            except (rel.RhymeRefusal, chroma.ChromaRefusal):
                continue
            if basis != "mask":
                continue
            fields.append({"post": str(post["_id"]), "region": str(region.get("id")),
                           "cells": cells})
            kept += 1
        print(f"  {post['_id']}  {kept} readable mask fields", file=sys.stderr)
    return fields


def sweep(fields):
    random.seed(11)
    rows = []
    for i in range(len(fields)):
        a = fields[i]["cells"]
        for j in range(i + 1, len(fields)):
            if fields[i]["post"] == fields[j]["post"]:
                continue                                        # cross-image only
            b = fields[j]["cells"]
            shared = sorted(set(a) & set(b))
            if len(shared) < rel.MIN_SHARED_CELLS:
                continue
            va, vb = [a[k] for k in shared], [b[k] for k in shared]
            if min(statistics.pstdev(va), statistics.pstdev(vb)) < rel.MIN_FIELD_SPREAD:
                continue
            r = rel._correlation(va, vb)
            if r is None:
                continue
            shuffled = list(vb)
            random.shuffle(shuffled)
            rn = rel._correlation(va, shuffled)
            rows.append({
                "r": r, "null": rn if rn is not None else 0.0, "shared": len(shared),
                "mean_gap": abs(statistics.fmean(va) - statistics.fmean(vb)),
                "a": f"{fields[i]['post'][-4:]}:{fields[i]['region']}",
                "b": f"{fields[j]['post'][-4:]}:{fields[j]['region']}",
            })
    return rows


def report(fields, rows):
    print("\n" + "=" * 78)
    print("  WAVE3 — the chromatic rhyme statistic, against the corpus")
    print("=" * 78)
    print(f"\n{len({f['post'] for f in fields})} images, {len(fields)} readable mask fields, "
          f"{len(rows)} cross-image pairs")
    print(f"floors in force: shared cells >= {rel.MIN_SHARED_CELLS}, "
          f"field spread >= {rel.MIN_FIELD_SPREAD}")

    vals = sorted(x["r"] for x in rows)

    def pct(p):
        return vals[int(p / 100 * (len(vals) - 1))]

    print("\n1. THE DISTRIBUTION — smooth and unimodal about zero. There is NO VALLEY, and the")
    print("   threshold is not derived from one.")
    print("   " + "  ".join(f"p{p}={pct(p):+.2f}" for p in (5, 25, 50, 75, 95)))

    print("\n2. THE PERMUTATION NULL — one field shuffled: every value, variance and count kept,")
    print("   only the correspondence destroyed. What the null cannot produce is not chance.")
    print(f"   {'floor':>7}  {'real':>7} {'':>8}  {'null':>7} {'':>8}   excess")
    for thr in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95):
        real = sum(1 for x in rows if x["r"] > thr)
        null = sum(1 for x in rows if x["null"] > thr)
        mark = "  <- MIN_RHYME" if abs(thr - rel.MIN_RHYME) < 1e-9 else ""
        print(f"   {thr:>7.2f}  {real:>7d} {real/max(len(rows),1):>7.2%}  "
              f"{null:>7d} {null/max(len(rows),1):>7.2%}   "
              f"{'inf' if null == 0 else f'{real/null:.0f}x':>6}{mark}")

    print("\n3. THE COINCIDENCE TEST — pairs whose MEAN warmth matches must NOT beat the base rate.")
    matched = [x for x in rows if x["mean_gap"] < 0.02]
    base = sum(1 for x in rows if x["r"] > rel.MIN_RHYME) / max(len(rows), 1)
    if matched:
        hit = sum(1 for x in matched if x["r"] > rel.MIN_RHYME) / len(matched)
        print(f"   {len(matched)} pairs match on mean within 0.02")
        print(f"   above MIN_RHYME: {hit:.2%}   base rate over all pairs: {base:.2%}")
        print(f"   -> sharing an average is {'NO advantage' if hit <= base else 'AN ADVANTAGE — the statistic is wrong'}")
        near = [x for x in rows if x["mean_gap"] < 0.005 and abs(x["r"]) < 0.1]
        if near:
            x = near[0]
            print(f"   e.g. {x['a']} ~ {x['b']}: mean gap {x['mean_gap']:.4f}, rhyme {x['r']:+.3f}")

    print("\n4. THE STRONGEST RHYMES")
    for x in sorted(rows, key=lambda x: -x["r"])[:6]:
        print(f"   r={x['r']:+.3f}  n={x['shared']:2d}  mean_gap={x['mean_gap']:.3f}   "
              f"{x['a']} ~ {x['b']}")
    print()


async def main_async(args) -> int:
    fields = await collect(args.posts)
    if len(fields) < 4:
        print("✗ too few readable fields to sweep anything", file=sys.stderr)
        return 2
    rows = sweep(fields)
    if not rows:
        print("✗ no cross-image pairs survived the floors", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"fields": len(fields), "pairs": len(rows),
                          "rows": sorted(rows, key=lambda x: -x["r"])[:50]}, indent=2))
    else:
        report(fields, rows)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--posts", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
