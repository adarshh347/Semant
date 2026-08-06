"""
The retina's geometry sidecar — where a region SITS, cached beside where it points in vector space.

The retina ranks by appearance because appearance is all it has: a LanceDB row is a vector plus
provenance, and nothing in it says whether the region it names sits inside anything. WAVE3's density
finding (`FINDING-wave3-retina-density.md`, Surprise 2) is what that costs — on the finial-5 seed the
twelve nearest neighbours by appearance ground *nothing*, because none of them stands in a nesting
relation at all. The proposer cannot see the one property that decides the outcome.

This module gives it that property, under the same terms as the index itself:

  · **derived.** Mongo is the source of truth; this is a rebuildable cache next to `manifest.json`.
    Delete it and you lose a few seconds of build time.
  · **built async, read sync.** The retina's query path touches no database and awaits nothing
    (`store.py`) — an invariant worth more than the convenience of a lazy load. So the Mongo read
    happens once, at rebuild, and the query path reads a file.
  · **boxes, not measurements.** What is cached is extent: a normalized box per region and whether
    that region carries a mask. Nothing here measures a relation, and `relational.py` — the only
    consumer — is bound by the same limit.

## Why the box is the mask's bbox where there is a mask

`canonicalize_geometry` treats `mask_rle` as authoritative and a stored `box` as a derived
convenience, so where the two disagree the mask is right. The organ resolves this the same way.
Taking the mask's tight bbox costs one decode per masked region at build time and makes the cached
extent agree with the extent the kernel will later measure against — which is the whole point of a
prior. It does NOT make the cached box a measurement: a bounding box is an estimate of an extent
however it was derived, which under the WAVE2.5 ruling is exactly what a proposer is allowed to use.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from backend.services import mask_geometry as mg
from backend.services.retina.store import RetinaStore

#: Beside `manifest.json`, for the same reason: the thing that describes a cache belongs with it.
GEOMETRY_FILENAME = "geometry.json"

#: Bumped when the cached SHAPE changes. A sidecar written by an older layout is ignored rather
#: than half-read — a stale prior is worse than none, because it is silently wrong.
GEOMETRY_VERSION = 1

#: What a region's cached geometry is. Deliberately tiny — 505 regions is ~60 KB of JSON, so there
#: is no case for a second Lance table and its versioned-format compaction problem.
_FIELDS = ("box", "has_mask")


def geometry_path(store: Optional[RetinaStore] = None) -> Path:
    return (store or RetinaStore()).path / GEOMETRY_FILENAME


def region_extent(region: Mapping[str, Any]) -> Optional[Dict[str, float]]:
    """The region's normalized box — tightened from its mask where it has one.

    Returns None when the region carries neither usable mask nor usable box. That is a fact about
    the region and it is reported as an absence rather than defaulted to a full-frame box, which
    would make every unlocatable region appear to contain everything.
    """
    rle = region.get("mask_rle")
    if mg.rle_is_valid(rle):
        box = mg.rle_bbox_norm(rle)
        if box.get("w", 0) > 0 and box.get("h", 0) > 0:
            return {k: round(float(box[k]), 6) for k in ("x", "y", "w", "h")}
    raw = region.get("box")
    if not isinstance(raw, Mapping):
        return None
    try:
        box = {k: float(raw.get(k, 0.0)) for k in ("x", "y", "w", "h")}
    except (TypeError, ValueError):
        return None
    if box["w"] <= 0 or box["h"] <= 0:
        return None
    return {k: round(v, 6) for k, v in box.items()}


def post_geometry(post: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """One post → `{region_id: {box, has_mask}}`. Pure; the unit the sidecar is built out of."""
    out: Dict[str, Dict[str, Any]] = {}
    for region in post.get("region_annotations") or []:
        rid = str(region.get("id") or "")
        if not rid:
            continue
        box = region_extent(region)
        if box is None:
            continue
        out[rid] = {"box": box, "has_mask": bool(mg.rle_is_valid(region.get("mask_rle")))}
    return out


async def geometry_rebuild(store: Optional[RetinaStore] = None, *, source=None,
                           write: bool = True) -> Dict[str, Any]:
    """Read the corpus once and cache every region's extent. The only async call in this module.

    Additive and idempotent by construction: it derives a fresh sidecar from posts and replaces the
    file wholesale, so re-running converges rather than accumulating. It writes nothing to Mongo —
    `region_annotations` is read and never touched.
    """
    if source is None:
        from backend.database import post_collection as source
    started = time.perf_counter()
    posts: Dict[str, Dict[str, Any]] = {}
    regions = masked = skipped = 0
    async for post in source.find({"region_annotations.0": {"$exists": True}},
                                  {"region_annotations": 1}):
        pid = str(post["_id"])
        geo = post_geometry(post)
        declared = len(post.get("region_annotations") or [])
        skipped += declared - len(geo)
        regions += len(geo)
        masked += sum(1 for g in geo.values() if g["has_mask"])
        if geo:
            posts[pid] = geo

    payload = {
        "geometry_version": GEOMETRY_VERSION,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "totals": {"posts": len(posts), "regions": regions, "masked": masked,
                   "unlocatable": skipped},
        "posts": posts,
    }
    if write:
        path = geometry_path(store)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, separators=(",", ":")))
        os.replace(tmp, path)          # atomic: a half-written sidecar is never readable
    return {**{k: v for k, v in payload.items() if k != "posts"},
            "seconds": round(time.perf_counter() - started, 3),
            "path": str(geometry_path(store))}


_CACHE: Dict[str, Any] = {"key": None, "payload": None}


def load_geometry(store: Optional[RetinaStore] = None, *, refresh: bool = False) -> Dict[str, Any]:
    """The sidecar, or an empty one. Sync, and cached on (path, mtime, size).

    Returns `{"posts": {}, ...}` rather than raising when the sidecar is missing — a caller that
    asked for a relational ranking and got no geometry should fall back to identity ranking and
    SAY SO, which is what `relational.py` does. A missing cache is a build step not yet run, not a
    broken query.
    """
    path = geometry_path(store)
    try:
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return {"geometry_version": GEOMETRY_VERSION, "built_at": "", "posts": {},
                "totals": {}, "missing": True, "path": str(path)}
    if not refresh and _CACHE["key"] == key:
        return _CACHE["payload"]
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        payload = None
    if not isinstance(payload, dict) or payload.get("geometry_version") != GEOMETRY_VERSION:
        # A sidecar from another layout. Ignored whole rather than partially trusted.
        payload = {"geometry_version": GEOMETRY_VERSION, "built_at": "", "posts": {},
                   "totals": {}, "stale": True, "path": str(path)}
    payload.setdefault("posts", {})
    payload["path"] = str(path)
    _CACHE.update(key=key, payload=payload)
    return payload


def geometry_status(store: Optional[RetinaStore] = None) -> Dict[str, Any]:
    payload = load_geometry(store)
    return {"built_at": payload.get("built_at") or "",
            "totals": payload.get("totals") or {},
            "posts": len(payload.get("posts") or {}),
            "missing": bool(payload.get("missing")),
            "stale": bool(payload.get("stale")),
            "path": payload.get("path")}


def geometry_for(posts: Optional[Mapping[str, Any]] = None,
                 store: Optional[RetinaStore] = None) -> Dict[str, Dict[str, Any]]:
    """The `{post_id: {region_id: …}}` map, from live posts if given, else from the sidecar.

    The override exists so a caller already holding the corpus (the kernel does) need not depend on
    a build step, and so tests can supply geometry without touching disk. Live posts win when
    supplied: they cannot be stale.
    """
    if posts:
        return {str(pid): post_geometry(post) for pid, post in posts.items()}
    return dict(load_geometry(store).get("posts") or {})
