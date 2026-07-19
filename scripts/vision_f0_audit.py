"""
VISION-F · F0 — post-merge smoke test + read-only corpus audit.

STRICTLY READ-ONLY: a write-guard monkeypatches every mutating Mongo call to raise, so this
script physically cannot write. It produces a deterministic machine-readable manifest and a
summary. Run: PYTHONPATH=. venv/bin/python scripts/vision_f0_audit.py
"""
import asyncio
import hashlib
import io
import json
import os

import httpx

from backend.database import post_collection, region_embeddings_collection as REC
from backend.services import mask_geometry as mg
from backend.services import region_embedding_service as res

OUT = "architecture-lab/vision-f-recovery/F0-audit"
OOB_LO, OOB_HI = -0.002, 1.002


# ── write-guard: F0 must not write a single byte ─────────────────────────────
class _Blocked(Exception):
    pass


def _guard(*a, **k):
    raise _Blocked("F0 is read-only — a write was attempted")


for coll in (post_collection, REC):
    for m in ("update_one", "update_many", "insert_one", "insert_many",
              "delete_one", "delete_many", "replace_one", "find_one_and_update",
              "find_one_and_replace", "find_one_and_delete", "bulk_write"):
        try:
            setattr(coll, m, _guard)
        except Exception:
            pass


def _oob(v):
    return v < OOB_LO or v > OOB_HI


def classify_region(r):
    if mg.rle_is_valid(r.get("mask_rle")):
        return "mask"
    polys = r.get("polygons")
    poly = r.get("polygon")
    if (isinstance(polys, list) and any(len(x) >= 3 for x in polys)) or \
       (isinstance(poly, list) and len(poly) >= 3):
        return "polygon"
    if r.get("box"):
        return "box"
    return "none"


def region_corruption(r):
    flags = set()
    box = r.get("box") or {}
    if box:
        x, y, w, h = box.get("x", 0), box.get("y", 0), box.get("w", 0), box.get("h", 0)
        if w <= 0 or h <= 0:
            flags.add("crush")
        elif w < 0.006 or h < 0.006:
            flags.add("sliver")
        if _oob(x) or _oob(y) or _oob(x + w) or _oob(y + h):
            flags.add("coord_oob")
    for ring in (r.get("polygons") or []):
        if any(_oob(p[0]) or _oob(p[1]) for p in ring if len(p) >= 2):
            flags.add("poly_coord_oob"); break
    poly = r.get("polygon") or []
    if any(len(p) >= 2 and (_oob(p[0]) or _oob(p[1])) for p in poly):
        flags.add("poly_coord_oob")
    return sorted(flags)


def curator_signals(post):
    regs = post.get("region_annotations") or []
    notes = sum(1 for r in regs if (r.get("user_note") or "").strip())
    prioritised = sum(1 for r in regs if r.get("prioritised"))
    weighted = sum(1 for r in regs if (r.get("weight") or 0))
    creator_regions = sum(1 for r in regs if r.get("actor") == "creator")
    sem = post.get("semantics") or {}
    curated = sum(1 for a in (sem.get("assertions") or [])
                  if a.get("status") in ("accepted", "rejected", "overridden", "tentative")
                  or a.get("curator_label"))
    return {"region_notes": notes, "prioritised": prioritised, "weighted": weighted,
            "creator_regions": creator_regions, "semantic_curated": curated}


def detached(post):
    regs = post.get("region_annotations") or []
    rids = {str(r.get("id")) for r in regs}
    grounds = post.get("grounds") or []
    gids = {str(g.get("id")) for g in grounds}
    det_grounds = [g.get("id") for g in grounds
                   if g.get("ground_type") == "region" and str(g.get("region_id")) not in rids]
    percepts = post.get("percepts") or []
    det_percepts = [p.get("id") for p in percepts
                    if any(str(gid) not in gids for gid in (p.get("ground_ids") or []))]
    # mentions: references to grounds/percepts inside the writing (text_blocks), detached if gone
    blob = json.dumps(post.get("text_blocks") or [], default=str)
    pids = {str(p.get("id")) for p in percepts}
    mentioned = [x for x in (gids | pids) if x and x in blob]
    return {"detached_grounds": det_grounds, "detached_percepts": det_percepts,
            "n_grounds": len(grounds), "n_percepts": len(percepts), "n_mentions": len(mentioned)}


async def image_reachable(client, url):
    if not url:
        return "no_url"
    try:
        r = await client.head(url, timeout=8.0, follow_redirects=True)
        if r.status_code < 400:
            return "reachable"
        r = await client.get(url, timeout=8.0, follow_redirects=True)   # some CDNs 405 HEAD
        return "reachable" if r.status_code < 400 else f"http_{r.status_code}"
    except Exception as e:
        return f"error:{type(e).__name__}"


async def smoke_test():
    """Service-level smoke of the curator route (read-only): capability availability + a
    retrieval search over an already-stored vector (no model load, no write)."""
    out = {}
    # image fetch/decode
    p = await post_collection.find_one({"photo_url": {"$exists": True}})
    try:
        async with httpx.AsyncClient() as c:
            b = (await c.get(p["photo_url"], timeout=15, follow_redirects=True)).content
        from PIL import Image
        im = Image.open(io.BytesIO(b)); out["image_fetch_decode"] = f"ok {im.size}"
    except Exception as e:
        out["image_fetch_decode"] = f"FAIL {e}"
    # adapters
    from backend.services.vision_orchestrator.adapters import (
        YoloSegmenterAdapter, SegFormerAdeAdapter, Sam2RefinerAdapter,
        FashionpediaAdapter, SemanticAnnotatorAdapter, Dinov2FeatureAdapter)
    for name, A in [("yolo", YoloSegmenterAdapter), ("segformer", SegFormerAdeAdapter),
                    ("sam2", Sam2RefinerAdapter), ("fashionpedia", FashionpediaAdapter),
                    ("semantic_vlm", SemanticAnnotatorAdapter), ("dinov2", Dinov2FeatureAdapter)]:
        try:
            out[f"adapter_{name}"] = "available" if A().is_available() else "deferred"
        except Exception as e:
            out[f"adapter_{name}"] = f"error:{e}"
    # semantic provider + spaces
    from backend.services.semantic_provider import SemanticProvider
    out["semantic_provider"] = SemanticProvider().state()["state"]
    from backend.services import retrieval_service as rs
    out["spaces"] = {s["name"]: s["available"] for s in rs.list_spaces()}
    # retrieval over a stored vector (read-only)
    doc = await REC.find_one({"model": "dinov2_vits14", "role": "identity"})
    if doc:
        r = await rs.find_similar(doc["vector"], space="visual_identity",
                                  post_ids=[doc["post_id"]], top_k=3)
        out["retrieval_search"] = f"{r['status']} ({len(r['results'])} hits)"
    else:
        out["retrieval_search"] = "no stored vector"
    return out


async def main():
    os.makedirs(OUT, exist_ok=True)
    smoke = await smoke_test()

    posts = [p async for p in post_collection.find({})]
    manifest = []
    agg = {"posts": len(posts), "with_image": 0, "dissected": 0, "regions": 0,
           "region_class": {"mask": 0, "polygon": 0, "box": 0, "none": 0},
           "corruption": {}, "detached_grounds": 0, "detached_percepts": 0,
           "grounds": 0, "percepts": 0, "mentions": 0, "semantic_posts": 0,
           "curator": {"region_notes": 0, "prioritised": 0, "weighted": 0,
                       "creator_regions": 0, "semantic_curated": 0}}

    async with httpx.AsyncClient() as client:
        sem = asyncio.Semaphore(8)
        async def reach(url):
            async with sem:
                return await image_reachable(client, url)
        reach_results = await asyncio.gather(*[reach(p.get("photo_url")) for p in posts])

    for p, reachable in zip(posts, reach_results):
        pid = str(p["_id"])
        regs = p.get("region_annotations") or []
        classes = {"mask": 0, "polygon": 0, "box": 0, "none": 0}
        corr = {}
        for r in regs:
            classes[classify_region(r)] += 1
            for f in region_corruption(r):
                corr[f] = corr.get(f, 0) + 1
        det = detached(p)
        cur = curator_signals(p)
        sem_meta = p.get("semantics") or {}
        assertions = sem_meta.get("assertions") or []
        entry = {
            "post_id": pid, "photo_public_id": p.get("photo_public_id"),
            "source_url": p.get("source_url"),
            "has_image": bool(p.get("photo_url")), "image": reachable,
            "domains": (p.get("domain_profile") or {}).get("chosen") or [],
            "n_regions": len(regs), "region_class": classes, "corruption": corr,
            "detached_grounds": det["detached_grounds"], "detached_percepts": det["detached_percepts"],
            "n_grounds": det["n_grounds"], "n_percepts": det["n_percepts"], "n_mentions": det["n_mentions"],
            "n_assertions": len(assertions),
            "assertions_by_status": _count_by(assertions, "status"),
            "assertions_by_model": _count_by(assertions, "model"),
            "curator": cur,
        }
        manifest.append(entry)
        # aggregate
        if entry["has_image"]:
            agg["with_image"] += 1
        if regs:
            agg["dissected"] += 1
        agg["regions"] += len(regs)
        for k in classes:
            agg["region_class"][k] += classes[k]
        for k, v in corr.items():
            agg["corruption"][k] = agg["corruption"].get(k, 0) + v
        agg["detached_grounds"] += len(det["detached_grounds"])
        agg["detached_percepts"] += len(det["detached_percepts"])
        agg["grounds"] += det["n_grounds"]; agg["percepts"] += det["n_percepts"]; agg["mentions"] += det["n_mentions"]
        if assertions:
            agg["semantic_posts"] += 1
        for k in agg["curator"]:
            agg["curator"][k] += cur[k]

    # embeddings inventory + staleness
    region_geo = {}
    for p in posts:
        for r in (p.get("region_annotations") or []):
            region_geo[(str(p["_id"]), str(r.get("id")))] = {
                "geometry_rev": r.get("geometry_rev"),
                "mask_hash": res.mask_hash(r.get("mask_rle")) if mg.rle_is_valid(r.get("mask_rle")) else "",
            }
    emb = {"total": 0, "by_space": {}, "by_model": {}, "stale": 0, "orphaned": 0, "stale_reasons": {}}
    async for d in REC.find({}):
        emb["total"] += 1
        emb["by_space"][d.get("space") or "legacy-none"] = emb["by_space"].get(d.get("space") or "legacy-none", 0) + 1
        emb["by_model"][d.get("model")] = emb["by_model"].get(d.get("model"), 0) + 1
        key = (str(d.get("post_id")), str(d.get("region_id")))
        if d.get("region_id") == ees_whole():
            continue
        cur = region_geo.get(key)
        if cur is None:
            emb["orphaned"] += 1
            continue
        stale, reason = res.is_stale(d, geometry_rev=cur["geometry_rev"], mask_hash=cur["mask_hash"],
                                     model=d.get("model"))
        if stale:
            emb["stale"] += 1
            emb["stale_reasons"][reason] = emb["stale_reasons"].get(reason, 0) + 1

    report = {"smoke": smoke, "aggregate": agg, "embeddings": emb}
    with open(f"{OUT}/manifest.json", "w") as f:
        json.dump({"report": report, "posts": manifest}, f, indent=1, sort_keys=True, default=str)

    # deterministic manifest hash (audit immutability)
    h = hashlib.sha256(json.dumps(manifest, sort_keys=True, default=str).encode()).hexdigest()
    print("=== F0 SMOKE (service-level, read-only) ===")
    for k, v in smoke.items():
        print(f"  {k}: {v}")
    print("\n=== CORPUS AUDIT ===")
    print(json.dumps(agg, indent=1))
    print("\n=== EMBEDDINGS ===")
    print(json.dumps(emb, indent=1))
    print(f"\nmanifest posts={len(manifest)}  sha256={h[:16]}  -> {OUT}/manifest.json")


def _count_by(items, key):
    out = {}
    for it in items:
        out[str(it.get(key))] = out.get(str(it.get(key)), 0) + 1
    return out


def ees_whole():
    from backend.services.evidence_embedding_service import WHOLE_REGION_ID
    return WHOLE_REGION_ID


if __name__ == "__main__":
    asyncio.run(main())
