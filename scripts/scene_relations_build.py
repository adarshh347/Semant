#!/usr/bin/env python3
"""
WAVE4 — derive the relations a scene carries, once, so a read route can be a read.

    python scripts/scene_relations_build.py                       # every post, every kind
    python scripts/scene_relations_build.py --post <id>
    python scripts/scene_relations_build.py --only nesting,occlusion
    python scripts/scene_relations_build.py --json

## Why this exists at all

The corpus contains **no committed relations**. Every lane through WAVE3 was suggestions-only —
measured, reported, never written — which was the discipline and is why a `visual_marks` scan turns
up three `region_mask` entries and nothing else. So a scene view has nothing to read, and a route
that measured on demand would be worse: `adjacency_organ` walks mask boundaries in Python with no
decode cache (~23 minutes for the structured posts) and occlusion needs a GPU model load.

So the relations are DERIVED ONCE into a cache, on the same terms as the retina index and the
depth-contact sidecar: gitignored, rebuildable, stamped with what produced it. The route reads the
cache and reports when it was built and which kinds are missing, so an unbuilt cache reads as an
absence rather than as an empty scene.

## What it does NOT do

It commits nothing. Every relation in the cache is `proposed` — the ledger status a curator changes,
through the curator surface, and never through here. The cache is a faster way to see what the
organs say, not a second ledger: `hydrate` in the route re-derives `epistemic` from the recorded
basis rather than trusting a field, so a hand-edited cache cannot promote anything.

READS POSTS, WRITES NONE. Every mutating method on the post collection is replaced with a raiser
before the first query, and every post is hashed before and after.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import adjacency_organ as adjacency                # noqa: E402
from backend.services import chroma_organ as chroma                     # noqa: E402
from backend.services import chromatic_relation as chroma_rel           # noqa: E402
from backend.services import depth_organ as depth                       # noqa: E402
from backend.services import mask_geometry as mg                        # noqa: E402
from backend.services import nestedness_organ as nestedness             # noqa: E402
from backend.services import occlusion_organ as occlusion               # noqa: E402
from backend.services import scene_relations as scene                   # noqa: E402

KINDS = ("nesting", "adjacency", "occlusion", "rhyme")
DEFAULT_GRID = 192
STEP_ID = "wave4_scene_relations"


def _payload(scenes: dict, provenance: dict, kinds: list) -> dict:
    """The cache as it stands. Rebuilt on every write so a partial run is still a usable cache —
    thinner than a complete one, and it says which kinds it has."""
    return {
        "cache_version": scene.CACHE_VERSION,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kinds_built": sorted({k for k in kinds}
                              | {k for s in scenes.values()
                                 for k, v in (s.get("relations") or {}).items() if v}),
        "provenance": {
            **provenance,
            "organs": {"nesting": nestedness.ORGAN, "adjacency": adjacency.ORGAN,
                       "occlusion": occlusion.ORGAN, "rhyme": chroma_rel.ORGAN},
        },
        "scenes": scenes,
    }


def freeze(*collections) -> None:
    blocked = ("insert_one", "insert_many", "update_one", "update_many", "replace_one",
               "delete_one", "delete_many", "find_one_and_update", "find_one_and_replace",
               "find_one_and_delete", "bulk_write")

    def _raise(*_a, **_k):
        raise AssertionError("this build is read-only — a write was attempted")

    for collection in collections:
        for name in blocked:
            if hasattr(collection, name):
                setattr(collection, name, _raise)


async def load_posts(post_id: str = "") -> dict:
    from bson import ObjectId

    from backend.database import post_collection
    freeze(post_collection)
    query = {"region_annotations.0": {"$exists": True}}
    if post_id:
        query["_id"] = ObjectId(post_id)
    return {str(p["_id"]): p async for p in post_collection.find(query)}


async def fetch_image(url: str):
    import httpx
    from PIL import Image

    from backend.routers.posts import _image_fetch_headers

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=_image_fetch_headers(url))
        resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")


async def depth_field_for(image, *, grid: int):
    from backend.services import depth_service
    from backend.services.vision_orchestrator.adapters import DepthAnythingAdapter
    from backend.services.vision_orchestrator.contracts import CancelToken
    from backend.services.vision_orchestrator.manager import ModelManager
    from backend.services.vision_orchestrator.registry import AdapterRegistry

    adapter = DepthAnythingAdapter()
    if not adapter.is_available():
        return None
    registry = AdapterRegistry()
    registry.register(adapter)
    manager = ModelManager(registry)
    await manager.ensure_loaded(adapter)
    result = await manager.run_adapter(adapter, {"image": image}, priority=0, cancel=CancelToken())
    payload = result.artifact.data
    if grid != int(payload.get("grid") or 0):
        payload = await asyncio.to_thread(depth_service.estimate, image, grid=grid)
    return depth.depth_field(
        payload, adapter=adapter.spec.name, model=adapter.spec.model_id,
        revision=getattr(adapter.spec, "revision", "") or depth_service.REVISION,
        preprocessing_version=adapter.spec.preprocessing_version, whole_frame=True)


def nesting_rows(post: dict) -> list:
    regions = list(post.get("region_annotations") or [])
    out = []
    for m in nestedness.find_nested_pairs(regions):
        out.append(scene.row(
            kind="nesting", axis=nestedness.AXIS_NESTEDNESS,
            relation=nestedness.RELATION_NESTED_WITHIN,
            source=str(m["inner_region_id"]), target=str(m["outer_region_id"]),
            basis=str(m["basis"]), detail=str(m["detail"]), organ=nestedness.ORGAN,
            numbers={"containment": m["containment"], "scale_ratio": m["scale_ratio"],
                     "nesting_index": m["nesting_index"]}))
    return out


def adjacency_rows(post: dict) -> list:
    regions = list(post.get("region_annotations") or [])
    seen, out = set(), []
    for m in adjacency.find_adjacent_pairs(regions):
        key = tuple(sorted((str(m["inner_region_id"]), str(m["outer_region_id"]))))
        if key in seen:
            continue
        seen.add(key)
        out.append(scene.row(
            kind="adjacency", axis=adjacency.AXIS_ADJACENCY, relation=adjacency.RELATION_MEETS,
            source=str(m["inner_region_id"]), target=str(m["outer_region_id"]),
            basis=str(m["basis"]), detail=str(m["detail"]), organ=adjacency.ORGAN,
            numbers={"contact_fraction": m["contact_fraction"],
                     "boundary_pixels": m.get("boundary_pixels")}))
    return out


def occlusion_rows(post: dict, field) -> list:
    """Only where a nesting SAYS containment — the 13 the sweep found are corrections of nestings.

    Sweeping every pair would bury them: on one post 44 of 57 pairs are ordered, and a scene drawn
    with all of them says only that a picture has depth. What is worth seeing is where the geometry
    claimed one thing and the depth says another.
    """
    regions = list(post.get("region_annotations") or [])
    by_id = {str(r.get("id")): r for r in regions}
    out = []
    for m in nestedness.find_nested_pairs(regions):
        inner, outer = by_id.get(str(m["inner_region_id"])), by_id.get(str(m["outer_region_id"]))
        if inner is None or outer is None:
            continue
        try:
            reading = occlusion.measure(inner, outer, field)
        except occlusion.OcclusionRefusal:
            continue
        verdict = occlusion.reconcile_containment(m, reading)
        if verdict["verdict"] != occlusion.CONTAINMENT_SUPERSEDED:
            continue
        out.append(scene.row(
            kind="occlusion", axis=occlusion.AXIS_OCCLUSION,
            relation=occlusion.RELATION_IN_FRONT_OF,
            source=str(reading["front_region_id"]), target=str(reading["back_region_id"]),
            basis=str(reading["basis"]), detail=str(verdict["detail"]), organ=occlusion.ORGAN,
            numbers={"separation": reading["separation"], "dominance": reading["dominance"],
                     "containment_it_corrects": m["containment"]},
            supersedes={"kind": "nesting", "source": str(m["inner_region_id"]),
                        "target": str(m["outer_region_id"])}))
    return out


def rhyme_rows(post_id: str, post: dict, frame, others: list) -> list:
    """Cross-image chromatic rhymes: the one relation on a scene that points OUT of it."""
    regions = [r for r in (post.get("region_annotations") or []) if mg.rle_is_valid(r.get("mask_rle"))]
    out = []
    for other_id, other_post, other_frame in others:
        other_regions = [r for r in (other_post.get("region_annotations") or [])
                         if mg.rle_is_valid(r.get("mask_rle"))]
        for a in regions[:scene.RHYME_REGION_CAP]:
            for b in other_regions[:scene.RHYME_REGION_CAP]:
                try:
                    m = chroma_rel.measure(a, frame, b, other_frame)
                except chroma_rel.RhymeRefusal:
                    continue
                if str(m.get("relation")) != chroma_rel.RELATION_RHYMES_WITH:
                    continue
                out.append(scene.row(
                    kind="rhyme", axis=chroma_rel.AXIS_CHROMATIC_RHYME,
                    relation=chroma_rel.RELATION_RHYMES_WITH,
                    source=str(a.get("id")), target=str(b.get("id")),
                    basis=str(m.get("basis") or ""), detail=str(m.get("detail") or ""),
                    organ=chroma_rel.ORGAN,
                    numbers={k: m.get(k) for k in ("correlation", "shape_length") if k in m},
                    target_post_id=other_id))
    return out


async def build(args) -> dict:
    posts = await load_posts(args.post)
    kinds = [k.strip() for k in args.only.split(",") if k.strip()] if args.only else list(KINDS)
    unknown = [k for k in kinds if k not in KINDS]
    if unknown:
        raise SystemExit(f"✗ unknown kind(s) {unknown}; this build knows {list(KINDS)}")

    import hashlib
    before = hashlib.sha256(
        json.dumps({k: str(v) for k, v in sorted(posts.items())}, sort_keys=True).encode()
    ).hexdigest()

    existing = scene.load_cache()
    scenes = dict(existing.get("scenes") or {})
    provenance = dict(existing.get("provenance") or {})
    started = time.perf_counter()

    frames: dict = {}
    for post_id, post in posts.items():
        entry = dict(scenes.get(post_id) or {})
        rows = {k: list(v) for k, v in (entry.get("relations") or {}).items()}
        url = str(post.get("photo_url") or "")

        if "nesting" in kinds:
            rows["nesting"] = nesting_rows(post)
            print(f"   {post_id[-6:]} nesting   {len(rows['nesting'])}", flush=True)

        if "adjacency" in kinds:
            rows["adjacency"] = adjacency_rows(post)
            print(f"   {post_id[-6:]} adjacency {len(rows['adjacency'])} "
                  f"({time.perf_counter() - started:.0f}s)", flush=True)

        if "occlusion" in kinds and url:
            image = frames.get(post_id) or await fetch_image(url)
            frames[post_id] = image
            field = await depth_field_for(image, grid=args.grid)
            if field is None:
                print(f"   {post_id[-6:]} occlusion SKIPPED — no depth model on this box",
                      flush=True)
            else:
                rows["occlusion"] = occlusion_rows(post, field)
                provenance["depth"] = {"adapter": field.get("adapter"), "model": field.get("model"),
                                       "revision": field.get("revision"), "grid": field.get("grid")}
                print(f"   {post_id[-6:]} occlusion {len(rows['occlusion'])} "
                      f"({time.perf_counter() - started:.0f}s)", flush=True)

        entry["relations"] = rows
        entry["post_id"] = post_id
        scenes[post_id] = entry
        # WRITTEN PER POST, not at the end. The occlusion pass is minutes of model work over a
        # flaky remote, and the first run lost all of it to one `AutoReconnect` — a build that
        # only persists on success throws away every post it already did.
        scene.write_cache(_payload(scenes, provenance, kinds))

    if "rhyme" in kinds:
        wanted = list(posts)[:scene.RHYME_POST_CAP]
        loaded = []
        for post_id in wanted:
            url = str(posts[post_id].get("photo_url") or "")
            if not url:
                continue
            _ = url
            image = frames.get(post_id) or await fetch_image(url)
            frames[post_id] = image
            # The frame, not a bare image: the mask's coordinates ARE the frame's coordinates,
            # and ORGAN-PROVENANCE-001 measured the same region reading +0.69 on a frame and
            # -0.69 on a crop of it, with an identical mark either way.
            loaded.append((post_id, posts[post_id], chroma.image_frame(image, source=url)))
        for i, (post_id, post, frame) in enumerate(loaded):
            others = loaded[i + 1:]
            found = rhyme_rows(post_id, post, frame, others)
            scenes.setdefault(post_id, {"post_id": post_id, "relations": {}})
            scenes[post_id]["relations"]["rhyme"] = found
            # A rhyme is one relation seen from two scenes; the far end gets it too, reversed.
            for row in found:
                far = row["target_post_id"]
                mirror = dict(row, source=row["target"], target=row["source"],
                              target_post_id=post_id)
                scenes.setdefault(far, {"post_id": far, "relations": {}})
                scenes[far]["relations"].setdefault("rhyme", []).append(mirror)
            print(f"   {post_id[-6:]} rhyme     {len(found)} "
                  f"({time.perf_counter() - started:.0f}s)", flush=True)

    after = hashlib.sha256(
        json.dumps({k: str(v) for k, v in sorted((await load_posts(args.post)).items())},
                   sort_keys=True).encode()
    ).hexdigest()

    scene.write_cache(_payload(scenes, provenance, kinds))

    totals = {kind: sum(len((s.get("relations") or {}).get(kind) or []) for s in scenes.values())
              for kind in KINDS}
    return {"posts": len(posts), "kinds": kinds, "totals": totals,
            "seconds": round(time.perf_counter() - started, 1),
            "posts_unchanged": before == after, "path": str(scene.cache_path())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--post", default="")
    ap.add_argument("--only", default="", help=f"comma-separated subset of {list(KINDS)}")
    ap.add_argument("--grid", type=int, default=DEFAULT_GRID)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    record = asyncio.run(build(args))
    print(f"\n  {record['posts']} post(s), kinds {record['kinds']}")
    for kind, n in record["totals"].items():
        print(f"    {kind:<10} {n}")
    print(f"  {record['seconds']}s → {record['path']}")
    print(f"  posts unchanged: {record['posts_unchanged']}")
    print(f"  every relation is PROPOSED — this build commits nothing.\n")
    if args.json:
        print(json.dumps(record, indent=2, default=str))
    return 0 if record["posts_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
