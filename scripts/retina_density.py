#!/usr/bin/env python3
"""
WAVE3 — embed the masked regions, so the retina can propose the only geometry that may ground.

    python scripts/retina_density.py                  # dry run: report the gap, write nothing
    python scripts/retina_density.py --persist        # embed the missing masked regions
    python scripts/retina_density.py --post <id>      # one post
    python scripts/retina_density.py --json           # the raw record

## Why this is an embedding lane and not a rebuild lane

`scripts/retina_build.py` already rebuilds the LanceDB index from `region_embeddings` in seconds,
and rebuilding it changes nothing here: the index faithfully mirrors a sidecar that has no rows for
the masked regions. The gap is upstream of the index.

The masks sweep appended 361 `cseg_*` regions carrying measured masks. `embed_post_regions` has not
run since, so **not one of them has an embedding**. Meanwhile #143's ruling made mask basis the only
admissible grounding. The two facts together starve the kernel from both ends:

    the retina can propose only VLM boxes           (the only rows in the index)
    the kernel may ground only on masks            (the ruling)
    → every proposal is inadmissible; grounded = 0

Measured before this ran: identity rows **140**, masked regions **420 of 505**, masked regions with
no embedding **365**. A retina query from a masked region's neighbourhood returned **0 of 12**
mask-carrying candidates.

## Additive, never a rewrite

Only regions that HAVE a mask and LACK an identity embedding are embedded. A post is not re-embedded
wholesale: a filtered copy carrying just those regions is handed to `embed_post_regions`, and the
`whole_image` role is requested only where that row is genuinely absent.

That is what makes "additive" true rather than aspirational. `upsert_embedding` is keyed on a
deterministic `embedding_id`, so a wholesale re-run would not DUPLICATE anything — but it would
`$set` every existing row with a fresh `updated_at`, which is a mutation of 140 rows nobody asked
for. Existing rows are hashed before and after and the run fails if one moved.

## Same store, same path

No parallel index and no second embedding route. This drives `evidence_embedding_service`, exactly
as the original 140 rows were produced. Masked regions take the BETTER path of the two it already
has: `pool_region` over the shared feature grid (route `mask_pool`) rather than a bounding-box crop,
because there is now a mask to pool over.

## Honesty

The retina still only PROPOSES. Nothing here grounds anything, and a mask-carrying candidate is not
a relation — it is a candidate the kernel is now *permitted* to ground, if the organ measures one.
Posts are hashed before and after; this writes to `region_embeddings` and to no post.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx                                                              # noqa: E402
from bson import ObjectId                                                 # noqa: E402

from backend.database import post_collection, region_embeddings_collection  # noqa: E402
from backend.services import evidence_embedding_service as ees            # noqa: E402
from backend.services import mask_geometry as mg                          # noqa: E402

#: The role the retina's candidate search reads, and therefore the one whose absence starves it.
IDENTITY = "identity"

#: What is embedded for a newly covered region. `whole_image` is per-POST rather than per-region and
#: is requested separately, only where it is missing.
REGION_ROLES = ("identity", "context")


def _digest(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, default=str).encode()).hexdigest()


async def embedded_keys(role: str = IDENTITY) -> set:
    """(post_id, region_id) for every region that already has an embedding in this role."""
    out = set()
    async for e in region_embeddings_collection.find({"role": role},
                                                     {"_id": 0, "post_id": 1, "region_id": 1}):
        out.add((str(e["post_id"]), str(e["region_id"])))
    return out


async def survey(post_id: str = "") -> dict:
    """The gap, measured. Returns the per-post work list and the corpus totals."""
    have = await embedded_keys()
    query = {"region_annotations.0": {"$exists": True}}
    if post_id:
        query["_id"] = ObjectId(post_id)

    work, totals = {}, {"regions": 0, "masked": 0, "masked_unembedded": 0, "embedded": len(have)}
    async for post in post_collection.find(query, {"region_annotations": 1, "photo_url": 1}):
        pid = str(post["_id"])
        missing = []
        for region in post.get("region_annotations") or []:
            rid = str(region.get("id") or "")
            if not rid:
                continue
            totals["regions"] += 1
            if not mg.rle_is_valid(region.get("mask_rle")):
                continue
            totals["masked"] += 1
            if (pid, rid) in have:
                continue
            totals["masked_unembedded"] += 1
            missing.append(rid)
        if missing:
            work[pid] = {"photo_url": post.get("photo_url"), "region_ids": missing}
    return {"work": work, "totals": totals}


async def has_whole_image(post_id: str) -> bool:
    row = await region_embeddings_collection.find_one(
        {"post_id": post_id, "role": "whole_image"}, {"_id": 1})
    return row is not None


async def embed_post(post_id: str, region_ids, *, http, persist: bool) -> dict:
    """Embed exactly these regions of one post. Everything else is left alone.

    The post handed to `embed_post_regions` is a shallow copy whose `region_annotations` holds only
    the targets — which is what keeps this additive. The service embeds every region it is given.
    """
    post = await post_collection.find_one({"_id": ObjectId(post_id)})
    if post is None:
        return {"post_id": post_id, "status": "missing_post", "records": 0}
    wanted = set(region_ids)
    targets = [r for r in (post.get("region_annotations") or []) if str(r.get("id")) in wanted]
    if not targets:
        return {"post_id": post_id, "status": "nothing_to_do", "records": 0}

    url = post.get("photo_url")
    if not url:
        return {"post_id": post_id, "status": "no_image", "records": 0}
    image = (await http.get(url)).content

    roles = list(REGION_ROLES)
    if not await has_whole_image(post_id):
        # Absent rather than stale — adding it is additive too, and the retina's whole_image space
        # is otherwise short a row for this post.
        roles.append("whole_image")

    filtered = {**post, "region_annotations": targets}
    started = time.perf_counter()
    out = await ees.embed_post_regions(filtered, image, roles=tuple(roles), persist=persist)
    return {
        "post_id": post_id,
        "status": out.get("status"),
        "requested": len(targets),
        "records": len(out.get("records") or []),
        "roles": roles,
        "routes": sorted({r.get("route") for r in (out.get("records") or [])}),
        "seconds": round(time.perf_counter() - started, 2),
        "reason": out.get("unavailable_reason") or "",
    }


async def main_async(args) -> int:
    plan = await survey(args.post)
    totals = plan["totals"]
    print(f"\ncorpus: {totals['regions']} regions, {totals['masked']} masked, "
          f"{totals['embedded']} identity embeddings")
    print(f"gap:    {totals['masked_unembedded']} masked regions with NO embedding, "
          f"across {len(plan['work'])} post(s)")

    if not plan["work"]:
        print("\n✓ nothing to embed — every masked region is already retrievable.")
        return 0
    for pid, w in sorted(plan["work"].items(), key=lambda kv: -len(kv[1]["region_ids"])):
        print(f"   {pid}  {len(w['region_ids']):>4} region(s)")

    if not args.persist:
        print("\n(dry run — nothing written. Re-run with --persist.)")
        return 0

    # The two things this run promises not to move.
    before_rows = {}
    async for e in region_embeddings_collection.find({}, {"_id": 0}):
        before_rows[str(e.get("embedding_id"))] = _digest(e)
    before_posts = {}
    async for p in post_collection.find({"region_annotations.0": {"$exists": True}}):
        before_posts[str(p["_id"])] = _digest(p)

    results = []
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as http:
        for pid, w in plan["work"].items():
            r = await embed_post(pid, w["region_ids"], http=http, persist=True)
            results.append(r)
            print(f"   {pid}: {r['status']} {r['records']} record(s) "
                  f"from {r['requested']} region(s) in {r.get('seconds')}s "
                  f"routes={r.get('routes')}")

    after_rows = {}
    async for e in region_embeddings_collection.find({}, {"_id": 0}):
        after_rows[str(e.get("embedding_id"))] = _digest(e)
    after_posts = {}
    async for p in post_collection.find({"region_annotations.0": {"$exists": True}}):
        after_posts[str(p["_id"])] = _digest(p)

    moved_rows = sorted(k for k in before_rows if before_rows[k] != after_rows.get(k))
    moved_posts = sorted(k for k in before_posts if before_posts[k] != after_posts.get(k))
    added = len(after_rows) - len(before_rows)

    print(f"\nrows: {len(before_rows)} → {len(after_rows)}  (+{added})")
    print(f"pre-existing rows moved: {len(moved_rows)}   posts moved: {len(moved_posts)}")
    if moved_rows or moved_posts:
        print(f"✗ NOT ADDITIVE — rows {moved_rows[:5]} posts {moved_posts[:5]}", file=sys.stderr)
        return 1
    print("✓ additive: every pre-existing row and every post is byte-identical.")
    print("\nNext: python scripts/retina_build.py   (the index mirrors the sidecar)")

    if args.json:
        print(json.dumps({"results": results, "totals": totals}, indent=2, default=str))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--post", default="", help="only this post id")
    ap.add_argument("--persist", action="store_true", help="write the embeddings")
    ap.add_argument("--json", action="store_true")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
