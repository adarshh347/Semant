#!/usr/bin/env python3
"""
WAVE3 — file the sweep's occlusions into the curator's queue. The queue's first real content.

    python scripts/curator_file_occlusions.py                 # dry run: show what would be filed
    python scripts/curator_file_occlusions.py --file          # actually file them
    python scripts/curator_file_occlusions.py --json

The occlusion sweep (#168) measured 13 mask-basis "nestings" that are actually occlusions and
committed none of them — correctly, because committing is a curator's act. But it also *persisted*
none of them, so the 13 lived in a transcript and died with the process. This re-derives them and
files them as proposals, which is what makes them reviewable at all.

## Why this re-measures rather than reading the sweep's output

The sweep is read-only by design and this lane does not change it. So the honest way to get the 13
into the queue is to run the same measurement again through the same organs — `nestedness` for the
containment, `occlusion_organ` for the ordering, `reconcile_containment` for the verdict — and file
what comes back. **This script judges nothing.** If the organs return 12 or 14 today, 12 or 14 are
filed; a script that filed a hard-coded list would be filing #168's transcript rather than a
measurement, and the queue would be full of claims nobody could re-derive.

## What lands in the queue

One proposal per superseded containment, carrying:

    mark        `occlusion_organ.grounding_mark` — the measured `in_front_of`, uncommitted
    evidence    the ordering statistic, the depth grid, the containment it contradicts, the
                arithmetic ceiling that governs the pair — the producer's own numbers, verbatim
    subject     which two regions, in which post

FILING IS NOT COMMITTING. This writes to `curator_proposals` and to no post; `curator.file_proposal`
has no way to reach a post collection. A run with `--file` leaves every post byte-identical, and
the script hashes them before and after to say so.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import curator                                      # noqa: E402
from backend.services import depth_organ                                  # noqa: E402
from backend.services import mask_geometry as mg                          # noqa: E402
from backend.services import movement_kernel as mk                        # noqa: E402
from backend.services import nestedness_organ as nest                     # noqa: E402
from backend.services import occlusion_organ as occlusion                 # noqa: E402

#: #168's grid, and its reasoning inherited whole: the count of occlusions is a function of the
#: depth resolution used to look for them, so a queue filed at another grid is a different queue.
#: It is recorded on every proposal's evidence for that reason.
DEFAULT_GRID = 192

PRODUCER = occlusion.ORGAN
KIND = "occlusion_supersedes_containment"


async def load_posts() -> dict:
    from backend.database import post_collection
    return {str(p["_id"]): p async for p in post_collection.find(
        {"region_annotations.0": {"$exists": True}})}


async def fetch_image(photo_url: str, *, attempts: int = 3):
    import io

    import httpx
    from PIL import Image

    from backend.routers.posts import _image_fetch_headers

    last = None
    for attempt in range(int(attempts)):
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                resp = await client.get(photo_url, headers=_image_fetch_headers(photo_url))
                resp.raise_for_status()
            return Image.open(io.BytesIO(resp.content)).convert("RGB")
        except Exception as exc:                                          # noqa: BLE001
            last = exc
            await asyncio.sleep(2.0 * (attempt + 1))
    raise last


async def depth_field_for(image, *, grid: int):
    from backend.services import depth_service
    from backend.services.vision_orchestrator.adapters import DepthAnythingAdapter
    from backend.services.vision_orchestrator.contracts import CancelToken
    from backend.services.vision_orchestrator.manager import ModelManager
    from backend.services.vision_orchestrator.registry import AdapterRegistry

    adapter = DepthAnythingAdapter()
    if not adapter.is_available():
        raise RuntimeError("depth_anything_v2_small is not available on this box")
    registry = AdapterRegistry()
    registry.register(adapter)
    manager = ModelManager(registry)
    await manager.ensure_loaded(adapter)
    result = await manager.run_adapter(adapter, {"image": image}, priority=0, cancel=CancelToken())
    if not result.ok or result.artifact is None:
        raise RuntimeError(f"the depth adapter returned {result.status}")
    payload = result.artifact.data
    if grid != int(payload.get("grid") or 0):
        payload = await asyncio.to_thread(depth_service.estimate, image, grid=grid)
    return depth_organ.depth_field(
        payload, adapter=adapter.spec.name, model=adapter.spec.model_id,
        revision=getattr(adapter.spec, "revision", "") or depth_service.REVISION,
        preprocessing_version=adapter.spec.preprocessing_version, whole_frame=True)


def masked_regions(post: dict) -> list:
    return [r for r in (post.get("region_annotations") or [])
            if isinstance(r, dict) and mg.rle_is_valid(r.get("mask_rle"))]


def occlusions_in(post: dict, field, *, grid: int) -> list:
    """Every mask-basis nesting the organs say is an occlusion. Judged by them, not by this."""
    regions = {str(r["id"]): r for r in masked_regions(post)}
    pairs = [m for m in nest.find_nested_pairs(list(regions.values()))
             if m["basis"] == nest.ADMISSIBLE_BASIS]

    out = []
    for m in pairs:
        inner_id, outer_id = str(m["inner_region_id"]), str(m["outer_region_id"])
        try:
            reading = occlusion.measure(regions[inner_id], regions[outer_id], field)
        except occlusion.OcclusionRefusal:
            continue
        verdict = occlusion.reconcile_containment(m, reading)
        if verdict["verdict"] != occlusion.CONTAINMENT_SUPERSEDED:
            continue

        mark = occlusion.grounding_mark(reading, post_id=str(post["_id"]),
                                        step_id="wave3_curator:file_occlusions")
        k, n = reading["a_cells"], reading["b_cells"]
        out.append(curator.proposal_entry(
            mark=mark, post_id=str(post["_id"]), producer=PRODUCER, kind=KIND,
            subject={
                "front_region_id": reading["front_region_id"],
                "back_region_id": reading["back_region_id"],
                "front_label": str(regions[inner_id].get("label") or ""),
                "back_label": str(regions[outer_id].get("label") or ""),
                "claim": (f"{reading['front_region_id']} is IN FRONT OF "
                          f"{reading['back_region_id']}, not inside it"),
            },
            evidence={
                # THE PRODUCER'S OWN NUMBERS. A curator judging this needs the ordering statistic
                # and the resolution it was read at; summarising them into a score here would be
                # this script making the judgement it exists to present.
                "ordering_dominance": reading["dominance"],
                "ordering_separation": reading["separation"],
                "separation_floor": occlusion.MIN_SEPARATION,
                "depth_grid": int(grid),
                "basis": reading["basis"],
                "front_cells": k, "back_cells": n,
                # The bound this lane's sweep found: a part's cells are inside its container's, so
                # every part-cell meets itself as a tie and the ordering is capped at 1 − k/(2n).
                # Carried because a curator should be able to see how close to its own ceiling a
                # reading sits.
                "ordering_ceiling": round(1.0 - k / (2.0 * n), 6) if n else None,
                "contradicts": {
                    "relation": nest.RELATION_NESTED_WITHIN,
                    "containment": m["containment"], "nesting_index": m["nesting_index"],
                    "basis": m["basis"],
                },
                "detail": reading["detail"],
                "verdict_detail": verdict["detail"],
            }))
    return out


async def run(args) -> dict:
    posts = await load_posts()
    before = mk.posts_fingerprint(posts)
    record: dict = {
        "grid": int(args.grid), "posts_scanned": len(posts),
        "proposals": [], "failures": [], "filed": [],
    }

    for post_id in sorted(posts):
        post = posts[post_id]
        started = time.perf_counter()
        url = str(post.get("photo_url") or "")
        if not url:
            record["failures"].append({"post_id": post_id, "detail": "no photo_url"})
            continue
        try:
            image = await fetch_image(url)
            field = await depth_field_for(image, grid=int(args.grid))
        except Exception as exc:                                          # noqa: BLE001
            record["failures"].append({"post_id": post_id, "detail": repr(exc)[:120]})
            continue

        found = occlusions_in(post, field, grid=int(args.grid))
        record["proposals"].extend(found)
        print(f"  {post_id}  occlusions={len(found):<3} "
              f"{round(time.perf_counter() - started, 1)}s", file=sys.stderr)

    if args.file:
        for proposal in record["proposals"]:
            stored = await curator.file_proposal(proposal)
            record["filed"].append(stored["proposal_id"])

    # FILING TOUCHES NO POST, and this is the proof rather than the claim. `file_proposal` writes
    # to `curator_proposals` and has no post collection to reach; the hash says so anyway.
    after = await load_posts()
    mk.assert_posts_unchanged(before, mk.posts_fingerprint(after))
    record["posts_unchanged"] = True
    return record


def _print(record: dict) -> None:
    print("\n" + "=" * 78)
    print("  WAVE3 — the occlusions, filed for a curator")
    print("=" * 78)
    print(f"\n  {record['posts_scanned']} posts scanned at depth grid {record['grid']}")
    for failure in record["failures"][:4]:
        print(f"    ! {failure['post_id']}: {failure['detail'][:56]}")

    print(f"\n  {len(record['proposals'])} occlusion(s) found — each one a measured claim that a "
          f"nesting is not a nesting")
    for proposal in record["proposals"]:
        ev, subj = proposal["evidence"], proposal["subject"]
        print(f"\n    {subj['front_region_id']}  IN FRONT OF  {subj['back_region_id']}")
        print(f"      post {proposal['post_id']}  ·  mark {proposal['mark_id']}")
        print(f"      ordering {ev['ordering_separation']:.4f} (floor {ev['separation_floor']}, "
              f"ceiling {ev['ordering_ceiling']}) at grid {ev['depth_grid']}")
        print(f"      contradicts: nested_within, containment "
              f"{ev['contradicts']['containment']:.3f}, index "
              f"{ev['contradicts']['nesting_index']:.3f}")
        print(f"      the mark says {proposal['mark'].get('epistemic_status')!r} — and the ledger "
              f"will say `proposed` until a person accepts it")

    if record["filed"]:
        print(f"\n  FILED {len(record['filed'])} proposal(s) to `curator_proposals`.")
        print("  Review at GET /api/v1/curator/queue; accept one with POST "
              ".../queue/{id}/commit.")
    else:
        print("\n  DRY RUN — nothing filed. Re-run with --file to put these in the queue.")
    print(f"\n  posts unchanged: {record['posts_unchanged']}   (filing writes to no post)")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--grid", type=int, default=DEFAULT_GRID)
    ap.add_argument("--file", action="store_true",
                    help="write the proposals to the queue; without it nothing is stored")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    record = asyncio.run(run(args))
    if args.json:
        print(json.dumps(record, indent=2, default=str))
    else:
        _print(record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
