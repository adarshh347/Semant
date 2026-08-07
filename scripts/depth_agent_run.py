#!/usr/bin/env python3
"""
WAVE3 — the depth organ, against the real corpus and the real model.

    python scripts/depth_agent_run.py                      # dry run, writes nothing
    python scripts/depth_agent_run.py --post <id>
    python scripts/depth_agent_run.py --locus-region <id>  # stand somewhere exactly
    python scripts/depth_agent_run.py --grid 32            # a finer depth field
    python scripts/depth_agent_run.py --json

Two agents inhabit ONE locus: one carries geometry, the other carries `depth_organ`. The depth
field comes from `depth_anything_v2_small` — a REAL weighted model, loaded through `ModelManager`
on the GPU pool, evicting whatever else was resident. This is the first agent-era organ downstream
of weights, so the residency cost is measured and printed rather than asserted to be small.

WHAT THIS RUN DEMONSTRATES

  · a depth field measured on a MASK, `measured`, and the same region read on its BOUNDING BOX,
    `interpretive` — and here the box argument is not an analogy. A box around a part contains
    what the part is IN FRONT OF, so the box reading is the mean of a thing and its ground. That
    is `cseg_golden_finial_7` itself, in the one modality that could have detected it.
  · a `measured` claim about a box reading, REFUSED by the guard, on a REAL mark (which only works
    because #158 taught `guard` to find a producer named in `provenance`)
  · the model's residency cost: load ms, inference ms, device, and what it evicted
  · `compare_across_senses` raising, because a depth mean and a nesting index are not comparable
    and this lane does not invent a scale

WHAT IT DOES NOT DEMONSTRATE, and the distinction is the point: it does NOT resolve the finial
case. Answering "is the finial inside the sky or in front of it" needs an `in_front_of` RELATION,
which needs the systematicity gate the floor lane is reworking. This run measures what such a
relation would stand on, and mints no relation of any kind.

READS POSTS, WRITES NONE — every mutating method on the post collection is replaced with a raiser
before the first query, and the posts are hashed before and after on top of that. The grounding
marks are PROPOSED and printed; committing one is a curator's act and this script performs none.

THE PIXELS AND THE MODEL BOTH LIVE HERE, never in the organ. `depth_organ` imports no torch and no
image library; it takes the coarse field the model already produces, exactly as `chroma_organ`
takes pixels. That separation is why a population of agents at many loci in one picture shares ONE
inference instead of one per agent.

Needs the usual `.env`, network for the image, Pillow, and torch + transformers with the
Depth-Anything weights available. On this Mac it runs on MPS.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import depth_organ as depth                         # noqa: E402
from backend.services import epistemics                                   # noqa: E402
from backend.services import nestedness_organ as nestedness               # noqa: E402
from backend.services.agents import organs                                # noqa: E402
from backend.services.agents import situated_agent as sa                  # noqa: E402
from backend.services.epistemics import STATUS_KEY                        # noqa: E402

GEO, DEP = "geo", "dep"


class WriteAttempted(Exception):
    """A write was attempted against a collection this run is only allowed to read."""


def freeze(*collections) -> None:
    """Make writing physically impossible, rather than merely unintended.

    The pattern from `vision_f0_audit` and every agent run since. It matters here because this is
    the first agent organ with a MODEL behind it: a wrong depth mark committed to a post would carry
    a checkpoint and a revision, which is exactly the shape a reader trusts most.
    """
    def _blocked(*_a, **_k):
        raise WriteAttempted(
            "this run may not write to posts — an organ proposes, and committing is a curator's act")

    for coll in collections:
        for method in ("update_one", "update_many", "insert_one", "insert_many",
                       "delete_one", "delete_many", "replace_one", "bulk_write",
                       "find_one_and_update", "find_one_and_replace", "find_one_and_delete"):
            try:
                setattr(coll, method, _blocked)
            except Exception:                                   # noqa: BLE001
                pass


def _posts():
    from backend.database import post_collection
    freeze(post_collection)
    return post_collection


async def load_post(post_id: str) -> dict:
    from bson import ObjectId
    query = {"_id": ObjectId(post_id)} if ObjectId.is_valid(post_id) else {"_id": post_id}
    return await _posts().find_one(query) or {}


async def any_post_with_a_photo() -> dict:
    return await _posts().find_one(
        {"photo_url": {"$exists": True, "$ne": ""}, "region_annotations.1": {"$exists": True}}) or {}


async def fetch_image(photo_url: str):
    import io
    import httpx
    from PIL import Image

    from backend.routers.posts import _image_fetch_headers

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(photo_url, headers=_image_fetch_headers(photo_url))
        resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")


async def estimate_depth(image, *, grid: int) -> tuple:
    """Run the roster adapter through `ModelManager`. Returns (field, residency).

    THROUGH THE MANAGER on purpose, rather than calling `depth_service.estimate` directly. The
    manager is what enforces single-GPU residency — loading depth evicts DINOv2/SAM and vice versa
    — and this lane's whole claim about cost is only true if the cost is actually paid here.
    """
    from backend.services.vision_orchestrator.adapters import DepthAnythingAdapter
    from backend.services.vision_orchestrator.contracts import CancelToken
    from backend.services.vision_orchestrator.manager import ModelManager
    from backend.services.vision_orchestrator.registry import AdapterRegistry

    adapter = DepthAnythingAdapter()
    if not adapter.is_available():
        raise RuntimeError(
            "depth_anything_v2_small is not available on this box (torch/transformers or the "
            "pinned weights are missing). The organ is pure and its tests run without them; this "
            "RUN is the part that needs the model, and it refuses rather than inventing a field.")

    registry = AdapterRegistry()
    registry.register(adapter)
    manager = ModelManager(registry)

    resident_before = sorted(manager._resident)
    t0 = time.perf_counter()
    await manager.ensure_loaded(adapter)
    load_ms = (time.perf_counter() - t0) * 1000.0

    from backend.services import depth_service
    t1 = time.perf_counter()
    result = await manager.run_adapter(adapter, {"image": image}, priority=0,
                                       cancel=CancelToken())
    infer_ms = (time.perf_counter() - t1) * 1000.0
    if not result.ok or result.artifact is None:
        raise RuntimeError(f"the depth adapter returned {result.status}")

    # A finer grid than the adapter's default when asked: a region is a fraction of the frame, and
    # the organ refuses below `MIN_CELLS` rather than averaging the grid instead of the region.
    payload = result.artifact.data
    if grid != int(payload.get("grid") or 0):
        payload = await asyncio.to_thread(depth_service.estimate, image, grid=grid)

    prov = result.provenance
    field = depth.depth_field(
        payload, adapter=adapter.spec.name, model=adapter.spec.model_id,
        revision=getattr(adapter.spec, "revision", "") or depth_service.REVISION,
        preprocessing_version=adapter.spec.preprocessing_version, whole_frame=True)

    residency = {
        "adapter": adapter.spec.name,
        "checkpoint": adapter.spec.checkpoint,
        "device": __import__("backend.services.torch_device", fromlist=["resolve"]).resolve(),
        "resource": adapter.spec.resource.value,
        "load_ms": round(load_ms, 1),
        "infer_ms": round(infer_ms, 1),
        "adapter_latency_ms": round(getattr(prov, "latency_ms", 0.0) or 0.0, 1),
        "resident_before": resident_before,
        "resident_after": sorted(manager._resident),
        "grid": int(field["grid"]),
    }
    return field, residency, manager, adapter


def _label(post: dict, region_id: str) -> str:
    for region in post.get("region_annotations") or []:
        if str(region.get("id")) == str(region_id):
            return str(region.get("label") or region.get("category") or region_id)
    return region_id


def pick_locus(post: dict) -> str:
    """The largest masked region — big enough to cover more than `MIN_CELLS` of a coarse grid."""
    from backend.services import mask_geometry as mg

    best, best_area = "", 0
    for region in post.get("region_annotations") or []:
        rle = region.get("mask_rle")
        if not rle:
            continue
        try:
            area = mg.rle_area(rle)
        except Exception:                                       # noqa: BLE001
            continue
        if area > best_area:
            best, best_area = str(region.get("id")), area
    return best


def _print(t: dict, post: dict) -> None:
    print("\n" + "=" * 78)
    print("  WAVE3 — the depth organ: the sense that measures what boxes fake")
    print("=" * 78)

    r = t["residency"]
    print("\n1. THE MODEL — a real load, on the real pool")
    print(f"   adapter    {r['adapter']}  ({r['resource']} pool)")
    print(f"   checkpoint {r['checkpoint']}")
    print(f"   device     {r['device']}")
    print(f"   load       {r['load_ms']:.0f} ms      inference {r['infer_ms']:.0f} ms"
          f"      grid {r['grid']}×{r['grid']}")
    print(f"   resident   before {r['resident_before'] or '[]'} → after {r['resident_after']}")
    print("   ONE inference for the whole frame, shared by every agent standing in it — which is")
    print("   why the sense is a separate, pure module from the model that feeds it.")

    locus = t["locus"]
    print("\n2. ONE LOCUS, TWO KINDS OF BODY")
    print(f"   locus     {locus['region_id']}  ({_label(post, locus['region_id'])!r})")
    for aid, organ_set in t["bodies"].items():
        print(f"   {aid:<5}     {', '.join(organ_set)}")

    print("\n3. TWO FIELDS")
    for aid, rows in t["fields"].items():
        print(f"   {aid} measured {len(rows)}:")
        for row in rows[:4]:
            other = f" {_label(post, row['other_region_id'])!r}" if row["other_region_id"] else ""
            print(f"      {row['relation']:>13}{other:<22} {row['epistemic_status']:<13} "
                  f"{row['detail'][:80]}")
        if len(rows) > 4:
            print(f"      … {len(rows) - 4} more")
    print(f"   relations in common:        {t['shared']['relations'] or '—'}")
    print(f"   measurement keys in common: {t['shared']['measurement_keys']}")

    d = t["depth"]
    print("\n4. THE BOX ARGUMENT — and here it is not an analogy")
    print(f"   on the MASK   depth {d['mask']['depth_mean']:.4f}  relief {d['mask']['relief']:.4f}"
          f"  {d['mask']['frame_rank']:.0%} of the frame behind it  → {d['mask']['status']}")
    print(f"                 {d['mask']['gradient']}")
    print(f"   on the BOX    depth {d['box']['depth_mean']:.4f}  relief {d['box']['relief']:.4f}"
          f"  {d['box']['frame_rank']:.0%} behind                  → {d['box']['status']}")
    print(f"   the two differ by {d['delta']:.4f} in inverse depth. A box around a part contains")
    print("   what the part is IN FRONT OF, so the box reading is the arithmetic mean of a thing")
    print("   and its ground — `cseg_golden_finial_7` exactly, now visible as a number.")
    print(f"   the SAME box reading claiming `measured` → {d['refused']}")

    print("\n5. WHAT THIS DOES NOT SETTLE")
    print("   It does not resolve the finial. Answering 'inside or in front of' needs an")
    print("   `in_front_of` RELATION, which needs the systematicity gate the floor lane is")
    print("   reworking. This organ mints a field_mark and no relation of any kind.")
    print(f"   compare_across_senses(nesting, depth) → {t['incommensurable'][:120]}…")

    print(f"\n   proposed marks (NOT committed): {len(t['proposed_marks'])}")
    for mark in t["proposed_marks"][:6]:
        prov = mark["provenance"]
        print(f"     {mark['id']}  {mark[STATUS_KEY]:<13} producer={prov['producer']}"
              f"{'  model=' + str(prov.get('model')) if prov.get('model') else ''}")
    if len(t["proposed_marks"]) > 6:
        print(f"     … {len(t['proposed_marks']) - 6} more")
    print(f"\n   posts unchanged: {t['posts_unchanged']}")
    print()


async def main_async(args) -> int:
    post = await load_post(args.post) if args.post else await any_post_with_a_photo()
    if not post:
        print(f"✗ no post {args.post or 'with a photo and regions'} found", file=sys.stderr)
        return 2

    post_id = str(post["_id"])
    photo_url = str(post.get("photo_url") or "")
    if not photo_url:
        print(f"✗ post {post_id} has no photo_url — there are no pixels, so there is no depth "
              f"field, and this organ refuses rather than reporting a flat one", file=sys.stderr)
        return 2

    region_id = str(args.locus_region or "") or pick_locus(post)
    if not region_id:
        print("✗ no masked region on this post — a box basis would make BOTH readings estimates",
              file=sys.stderr)
        return 2

    print(f"post {post_id} — {len(post.get('region_annotations') or [])} regions", file=sys.stderr)
    print(f"fetching {photo_url[:88]}…", file=sys.stderr)
    try:
        image = await fetch_image(photo_url)
    except Exception as e:                                      # noqa: BLE001
        print(f"✗ could not fetch the image: {e}", file=sys.stderr)
        return 2
    print(f"image {image.size[0]}×{image.size[1]}; loading the depth model…", file=sys.stderr)

    try:
        field, residency, manager, adapter = await estimate_depth(image, grid=args.grid)
    except Exception as e:                                      # noqa: BLE001
        print(f"✗ {e}", file=sys.stderr)
        return 2

    before = sa.posts_fingerprint({post_id: post})
    geo = sa.inhabit(agent_id=GEO, post_id=post_id, region_id=region_id,
                     organ_set=(nestedness.ORGAN,))
    dep = sa.inhabit(agent_id=DEP, post_id=post_id, region_id=region_id,
                     organ_set=(depth.ORGAN,))
    try:
        sa.perceive(geo, post)
        sa.perceive(dep, post, depth_field=field)
    except organs.OrganRefusal as e:
        print(f"✗ an agent could not perceive: {e}", file=sys.stderr)
        return 1
    except depth.DepthRefusal as e:
        print(f"✗ the depth organ refused: {e}", file=sys.stderr)
        return 1

    transcript: dict = {
        "residency": residency,
        "locus": geo.locus.as_dict(),
        "bodies": {geo.id: list(geo.organ_set), dep.id: list(dep.organ_set)},
        "fields": {a.id: [p.as_dict() for p in a.percept_field] for a in (geo, dep)},
    }
    geo_keys = set(geo.percept_field[0].reading.measurement) if geo.percept_field else set()
    dep_keys = set(dep.percept_field[0].reading.measurement) if dep.percept_field else set()
    transcript["shared"] = {
        "relations": sorted({p.reading.relation for p in geo.percept_field} &
                            {p.reading.relation for p in dep.percept_field}),
        "measurement_keys": sorted(geo_keys & dep_keys),
    }

    region = next(r for r in post["region_annotations"] if str(r.get("id")) == region_id)
    by_mask = depth.measure(region, field)
    by_box = depth.measure({"id": region_id, "box": nestedness._box_of(region)}, field)
    boxed_mark = depth.grounding_mark(by_box, post_id=post_id)
    try:
        epistemics.guard([{**boxed_mark, STATUS_KEY: "measured"}])
        refused = "NOT REFUSED  <-- BUG"
    except epistemics.EpistemicViolation as e:
        refused = f"REFUSED — {str(e)[:96]}…"

    def _row(m):
        return {"depth_mean": m["depth_mean"], "relief": m["relief"],
                "frame_rank": m["frame_rank"], "status": depth.epistemic_for(m["basis"]),
                "gradient": m["gradient"]["detail"]}

    transcript["depth"] = {"mask": _row(by_mask), "box": _row(by_box),
                           "delta": abs(by_mask["depth_mean"] - by_box["depth_mean"]),
                           "refused": refused}

    try:
        depth.compare_across_senses(
            geo.percept_field[0].reading.measurement if geo.percept_field else {}, by_mask)
        transcript["incommensurable"] = "NOT REFUSED  <-- BUG"
    except depth.Incommensurable as e:
        transcript["incommensurable"] = str(e)

    transcript["proposed_marks"] = [*sa.proposed_marks(geo), *sa.proposed_marks(dep)]
    sa.assert_posts_unchanged(before, sa.posts_fingerprint({post_id: post}))
    transcript["posts_unchanged"] = True

    await manager.unload(adapter.spec.name)

    if args.json:
        print(json.dumps(transcript, indent=2, default=str))
    else:
        _print(transcript, post)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--post", default="")
    ap.add_argument("--locus-region", default="")
    ap.add_argument("--grid", type=int, default=32,
                    help="depth grid resolution. The adapter's default is 16 over the whole frame, "
                         "which is coarse for one region — the organ refuses below MIN_CELLS "
                         "rather than reporting the grid's depth as the region's")
    ap.add_argument("--json", action="store_true")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
