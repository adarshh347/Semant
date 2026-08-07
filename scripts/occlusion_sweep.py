#!/usr/bin/env python3
"""
WAVE3 — how many of this corpus's "nestings" are actually occlusions? The founding pathology, swept.

    python scripts/occlusion_sweep.py                    # the full sweep
    python scripts/occlusion_sweep.py --posts 3          # a smaller bound
    python scripts/occlusion_sweep.py --grid 192         # the occlusion lane's grid
    python scripts/occlusion_sweep.py --json

#165 resolved ONE case: `in_front_of(cseg_golden_finial_7, cseg_Sky_0)`, ordering 0.9987, against
65 true containments that topped out at 0.9390 — a clean gap in one image. This asks the same
question of every mask-basis nesting in the corpus, using the SAME statistic, and reports the
partition: which nestings are genuinely occlusions, and which are true containments.

## The statistic, and why it is not the one #164 used

Both this and the society-characterization sweep (#164) ask "does depth contradict this nesting".
They use different instruments and only one of them carries information:

    #164   MEAN SEPARATION   (depth(inner) − depth(outer)) / frame spread
           65 of 67 pairs positive, median +0.168 — the SIGN carries no information, because a
           container's depth mean averages its receding parts and a part on its face is nearer
           than that mean while being genuinely inside it.

    here   ORDERING          P(a cell of A reads nearer than a cell of B), ties at half
           the finial 0.9987 against a containment class topping out at 0.9390. Inverse depth
           compresses distance, so the STEP is tiny (3.8% of the frame's range) while the ORDER is
           unambiguous — and the order is what occlusion means.

**This sweep is #164's seed set, re-run with the instrument the occlusion lane had already found
the first one lacked.** Both baselines are reproduced side by side (`--json` carries the mean for
every pair) so the improvement is shown rather than asserted.

## It applies the relation; it does not re-ground one

`occlusion_organ.measure` and `reconcile_containment` do the judging. This script decides nothing:
it enumerates pairs, hands each to the organ, and counts. No relation is minted, no mark committed,
no post touched — and `structure_map`, the agents and the kernel are not imported at all.

## Where no claim is made

- **Mask basis only, both sides.** `reconcile_containment` refuses to supersede a measured
  containment on box geometry — an estimate may propose a correction and may not make one — so a
  box-basis pair is `unjudged` and counted as such rather than as a containment that stood.
- **Too few cells.** `MIN_CELLS_PER_SIDE` refuses an ordering over a handful of grid cells. A
  refusal is a fact about the geometry, and it is counted by reason.
- **No image, no depth.** Counted, by post.

READS POSTS, WRITES NONE — every mutating method on the post collection is replaced with a raiser
before the first query, and the posts are hashed before and after.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import depth_organ                                  # noqa: E402
from backend.services import mask_geometry as mg                          # noqa: E402
from backend.services import movement_kernel as mk                        # noqa: E402
from backend.services import nestedness_organ as nest                     # noqa: E402
from backend.services import occlusion_organ as occlusion                 # noqa: E402

#: The occlusion lane's grid, and its reasoning inherited whole: at 48 the finial covers ZERO cells
#: and the organ refuses rather than measuring the grid. 192 puts ~2.7×4.8 native pixels in a cell
#: for this corpus's images — within the model's own resolution, not invented detail.
DEFAULT_GRID = 192

#: The two candidates #164 named, on the weaker statistic. This lane's first job is to say what the
#: ordering statistic makes of them — the card asks, and a sweep that reported only aggregates
#: would leave the question that motivated it unanswered.
NAMED_CANDIDATES = (
    ("6a5fef58a3ddb6341fd69930", "cseg_tree_silhouette_11", "cseg_Temple_Reflection_1"),
    ("6a5fef58a3ddb6341fd69930", "cseg_tree_silhouette_11", "cseg_tree_silhouette_6"),
    ("6a6041b61ecd6db1c931eb79", "cseg_stone_texture_8", "cseg_wall_surface_0"),
    ("6a6041b61ecd6db1c931eb79", "auto_6", "cseg_wall_surface_0"),
    ("6a6041b61ecd6db1c931eb79", "cseg_stone_texture_13", "cseg_wall_surface_0"),
    ("6a6041b61ecd6db1c931eb79", "cseg_architectural_ledge_0", "cseg_wall_surface_0"),
)


class WriteAttempted(Exception):
    """A write was attempted against a collection this run may only read."""


def freeze(*collections) -> None:
    def _blocked(*_a, **_k):
        raise WriteAttempted("this is a measurement lane — it reads the corpus and writes nothing")

    for coll in collections:
        for method in ("update_one", "update_many", "insert_one", "insert_many",
                       "delete_one", "delete_many", "replace_one", "bulk_write",
                       "find_one_and_update", "find_one_and_replace", "find_one_and_delete"):
            try:
                setattr(coll, method, _blocked)
            except Exception:                                             # noqa: BLE001
                pass


async def load_posts() -> dict:
    from backend.database import post_collection
    freeze(post_collection)
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
    """A whole-frame depth field through the roster adapter. Whole-frame is not optional here:
    monocular depth is a global inference and an ordering read off a crop orders the crop."""
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


# ── the sweep ───────────────────────────────────────────────────────────────

def masked_regions(post: dict) -> list:
    return [r for r in (post.get("region_annotations") or [])
            if isinstance(r, dict) and mg.rle_is_valid(r.get("mask_rle"))]


def judge_post(post: dict, field) -> list:
    """Every mask-basis nesting in this post, judged against depth by the occlusion organ.

    NO CACHING, deliberately. `occlusion.measure` derives each region's cells itself, and reaching
    around that to memoize would mean this script and the organ could come to disagree about what a
    region covers — which is the exact reason `depth_organ.region_cells` was made public rather than
    duplicated. The cost is real (each pair re-derives both sides) and it is the organ's to fix.
    """
    regions = {str(r["id"]): r for r in masked_regions(post)}
    pairs = [m for m in nest.find_nested_pairs(list(regions.values()))
             if m["basis"] == nest.ADMISSIBLE_BASIS]
    if not pairs:
        return []

    depth_values = list(field["depth"])
    spread = (max(depth_values) - min(depth_values)) or 1.0
    out = []
    for m in pairs:
        inner_id, outer_id = str(m["inner_region_id"]), str(m["outer_region_id"])
        try:
            reading = occlusion.measure(regions[inner_id], regions[outer_id], field)
        except occlusion.OcclusionRefusal as exc:
            out.append({
                "post_id": str(post["_id"]), "inner_region_id": inner_id,
                "outer_region_id": outer_id, "nesting_index": m["nesting_index"],
                "verdict": "refused", "reason": _refusal_reason(str(exc)),
                "detail": str(exc)[:160],
            })
            continue

        verdict = occlusion.reconcile_containment(m, reading)
        # THE OTHER INSTRUMENT, on the same pair. #164's statistic is computed alongside so its
        # sign-uninformativeness is reproduced from this run's own data rather than cited.
        mean_separation = (reading["a_depth"] - reading["b_depth"]) / spread
        out.append({
            "post_id": str(post["_id"]),
            "inner_region_id": inner_id, "outer_region_id": outer_id,
            "inner_label": str(regions[inner_id].get("label") or ""),
            "outer_label": str(regions[outer_id].get("label") or ""),
            "nesting_index": m["nesting_index"], "containment": m["containment"],
            "verdict": verdict["verdict"],
            "relation": verdict.get("relation"),
            "dominance": reading["dominance"],
            "separation": reading["separation"],
            "separated": reading["separated"],
            "front_region_id": reading["front_region_id"],
            "basis": reading["basis"],
            "inner_cells": reading["a_cells"], "outer_cells": reading["b_cells"],
            "mean_separation": round(mean_separation, 4),
            "detail": verdict["detail"][:200],
        })
    return out


def _refusal_reason(message: str) -> str:
    """Refusals BY REASON, because they are different facts about the corpus. `too_few_cells` says
    the geometry is finer than the grid; `unreadable` says a region carries nothing to read."""
    if "depth cells, below" in message or "covers" in message:
        return "too_few_cells"
    if "neither a valid mask nor a valid box" in message:
        return "unreadable"
    return "other"


def named_candidates(posts: dict, fields: dict) -> list:
    """The pairs #164 named on the weaker statistic, judged on the ordering one."""
    out = []
    for post_id, inner_id, outer_id in NAMED_CANDIDATES:
        post, field = posts.get(post_id), fields.get(post_id)
        row = {"post_id": post_id, "inner_region_id": inner_id, "outer_region_id": outer_id}
        if post is None or field is None:
            out.append({**row, "verdict": "no_depth_field"})
            continue
        regions = {str(r["id"]): r for r in masked_regions(post)}
        if inner_id not in regions or outer_id not in regions:
            out.append({**row, "verdict": "region_absent"})
            continue
        try:
            containment = nest.measure(regions[inner_id], regions[outer_id])
            reading = occlusion.measure(regions[inner_id], regions[outer_id], field)
        except (nest.NestednessRefusal, occlusion.OcclusionRefusal) as exc:
            out.append({**row, "verdict": "refused", "detail": str(exc)[:160]})
            continue
        verdict = occlusion.reconcile_containment(containment, reading)
        depth_values = list(field["depth"])
        spread = (max(depth_values) - min(depth_values)) or 1.0
        out.append({
            **row,
            "nested": containment["nested"], "nesting_index": containment["nesting_index"],
            "containment": containment["containment"], "containment_basis": containment["basis"],
            "dominance": reading["dominance"], "separation": reading["separation"],
            "separated": reading["separated"], "front_region_id": reading["front_region_id"],
            "mean_separation": round((reading["a_depth"] - reading["b_depth"]) / spread, 4),
            "verdict": verdict["verdict"], "detail": verdict["detail"][:220],
        })
    return out


async def sweep(args) -> dict:
    posts = await load_posts()
    before = mk.posts_fingerprint(posts)
    chosen = sorted(posts)[:int(args.posts)] if args.posts else sorted(posts)

    record: dict = {
        "bound": {
            "posts_in_corpus": len(posts), "posts_scanned": len(chosen),
            "grid": int(args.grid), "min_separation": occlusion.MIN_SEPARATION,
            "min_cells_per_side": occlusion.MIN_CELLS_PER_SIDE,
            "statistic": "ordering (dominance), per occlusion_organ — NOT mean separation",
        },
        "posts": [], "pairs": [], "failures": [],
    }
    fields: dict = {}

    for post_id in chosen:
        post = posts[post_id]
        started = time.perf_counter()
        url = str(post.get("photo_url") or "")
        field = None
        if url:
            try:
                image = await fetch_image(url)
                field = await depth_field_for(image, grid=int(args.grid))
                fields[post_id] = field
            except Exception as exc:                                      # noqa: BLE001
                record["failures"].append({"post_id": post_id, "detail": repr(exc)[:120]})
        else:
            record["failures"].append({"post_id": post_id, "detail": "no photo_url"})

        judged = judge_post(post, field) if field is not None else []
        record["pairs"].extend(judged)
        record["posts"].append({
            "post_id": post_id, "masked_regions": len(masked_regions(post)),
            "had_depth": field is not None, "pairs": len(judged),
            "seconds": round(time.perf_counter() - started, 1),
        })
        print(f"  {post_id}  regions={len(masked_regions(post)):<4} "
              f"depth={'y' if field is not None else 'n'}  pairs={len(judged):<5} "
              f"{record['posts'][-1]['seconds']}s", file=sys.stderr)
        if args.state:
            with open(args.state, "w") as handle:
                json.dump(record, handle, default=str)

    record["named_candidates"] = named_candidates(posts, fields)
    record["partition"] = partition(record["pairs"])
    mk.assert_posts_unchanged(before, mk.posts_fingerprint(posts))
    record["posts_unchanged"] = True
    return record


def partition(pairs: list) -> dict:
    """The answer: how many nestings are genuinely occlusions, and how many are containments.

    Both statistics summarised side by side. The ordering one is the claim; the mean one is here so
    #164's result is reproduced from this run's own data — a comparison quoted rather than computed
    is a comparison a reader has to take on trust.
    """
    judged = [p for p in pairs if p["verdict"] != "refused"]
    verdicts = Counter(p["verdict"] for p in judged)
    refusals = Counter(p.get("reason") for p in pairs if p["verdict"] == "refused")

    dominance = sorted(p["separation"] for p in judged)
    means = sorted(p["mean_separation"] for p in judged)
    superseded = [p for p in judged if p["verdict"] == occlusion.CONTAINMENT_SUPERSEDED]
    stands = [p for p in judged if p["verdict"] == occlusion.CONTAINMENT_STANDS]

    def spread(values):
        if not values:
            return {"n": 0}
        return {"n": len(values), "min": round(values[0], 4), "max": round(values[-1], 4),
                "median": round(statistics.median(values), 4)}

    return {
        "pairs_seen": len(pairs), "judged": len(judged),
        "verdicts": dict(verdicts), "refusals": dict(refusals),
        # THE ORDERING STATISTIC — the claim.
        "ordering": {
            **spread(dominance),
            "at_or_above_floor": sum(1 for v in dominance if v >= occlusion.MIN_SEPARATION),
            "superseded_max": (max(p["separation"] for p in superseded) if superseded else None),
            "stands_max": (max(p["separation"] for p in stands) if stands else None),
        },
        # #164's statistic, on the same pairs, so its uninformativeness is shown not cited.
        "mean_separation": {
            **spread(means),
            "positive": sum(1 for v in means if v > 0),
            "positive_share": (round(100.0 * sum(1 for v in means if v > 0) / len(means), 1)
                               if means else None),
        },
        "occlusions": sorted(superseded, key=lambda p: -p["separation"])[:20],
    }


def _print(record: dict) -> None:
    bound, part = record["bound"], record["partition"]
    print("\n" + "=" * 78)
    print("  WAVE3 — the occlusion sweep: which nestings are actually occlusions?")
    print("=" * 78)
    print(f"\n  SCAN BOUND   {bound['posts_scanned']} of {bound['posts_in_corpus']} "
          f"region-carrying posts · depth grid {bound['grid']}")
    print(f"               floor {bound['min_separation']}, "
          f"min {bound['min_cells_per_side']} cells per side")
    print(f"               statistic: {bound['statistic']}")
    for failure in record["failures"][:4]:
        print(f"               ! {failure['post_id']}: {failure['detail'][:56]}")

    print("\n" + "-" * 78)
    print("  THE TWO CANDIDATES #164 NAMED, on the ordering statistic")
    for row in record["named_candidates"]:
        print(f"    {row['inner_region_id']} in {row['outer_region_id']}")
        if "dominance" not in row:
            print(f"      {row['verdict']}  {row.get('detail', '')[:60]}")
            continue
        print(f"      nesting {row['nesting_index']:.3f} on {row['containment_basis']} · "
              f"ordering {row['separation']:.4f} · mean stat {row['mean_separation']:+.3f}")
        print(f"      → {row['verdict'].upper()}   {row['detail'][:100]}")

    print("\n" + "-" * 78)
    print(f"  THE PARTITION — {part['judged']} mask-basis nestings judged "
          f"({part['pairs_seen']} seen)")
    for verdict, count in sorted(part["verdicts"].items(), key=lambda kv: -kv[1]):
        print(f"    {verdict:<26} {count:>6}")
    if part["refusals"]:
        print(f"    refused, by reason:        {part['refusals']}")

    o, m = part["ordering"], part["mean_separation"]
    print("\n  THE ORDERING STATISTIC (the claim)")
    if o["n"]:
        print(f"    {o['n']} pairs · separation {o['min']:.4f} … {o['max']:.4f} · "
              f"median {o['median']:.4f}")
        print(f"    at or above the {bound['min_separation']} floor: {o['at_or_above_floor']}")
        print(f"    strongest that STANDS: {o['stands_max']}   "
              f"strongest SUPERSEDED: {o['superseded_max']}")
    print("\n  THE MEAN STATISTIC (#164's, reproduced on the same pairs)")
    if m["n"]:
        print(f"    {m['n']} pairs · {m['min']:+.3f} … {m['max']:+.3f} · median {m['median']:+.3f}")
        print(f"    positive: {m['positive']} of {m['n']}  ({m['positive_share']}%) "
              f"— the sign carries no information, which is why it is not the claim")

    if part["occlusions"]:
        print("\n  NESTINGS THAT ARE ACTUALLY OCCLUSIONS")
        for row in part["occlusions"]:
            print(f"    {row['separation']:.4f}  {row['post_id'][-8:]}  "
                  f"{row['inner_region_id'][:28]:<28} in front of {row['outer_region_id'][:24]}")
    else:
        print("\n  NESTINGS THAT ARE ACTUALLY OCCLUSIONS:  NONE, within the bound above.")
        print("    Not a failure to look — a measured result about what was scanned. And note the")
        print("    ceiling: a containment's cells are inside its container's, so every part-cell")
        print("    meets itself as a tie and the ordering is capped at 1 - k/(2n). A part covering")
        print("    more than 10% of its container's cells cannot reach the floor at all.")

    print(f"\n  posts unchanged: {record['posts_unchanged']}   nothing written")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--posts", type=int, default=0, help="bound on posts scanned; 0 = all")
    ap.add_argument("--grid", type=int, default=DEFAULT_GRID)
    ap.add_argument("--state", default="", help="checkpoint after every post")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    record = asyncio.run(sweep(args))
    if args.json:
        print(json.dumps(record, indent=2, default=str))
    else:
        _print(record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
