"""
VISION-E · E5 — "Find similar" circulation.

Given a confirmed Region, find its visual neighbours — as inspectable RESEARCH, never as
semantic fact. This service resolves the query's space (DINOv2 identity/context, or FashionCLIP
for fashion), ensures the Region has a fresh vector (indexing it on demand, re-indexing when the
mask/source changed), searches ONE space through the sidecar, and hydrates each neighbour with
what the curator needs to judge it: source post, exact-mask geometry (to recall the mask in its
own image), similarity, the model space, and provenance. It creates NO Motifs or Relations —
curator selection, not vector proximity, makes durable links.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from backend.services import retrieval_service as rs
from backend.services import region_embedding_service as res
from backend.services import evidence_embedding_service as ees


def _domain_of(post: dict) -> Optional[str]:
    dp = post.get("domain_profile") or {}
    chosen = dp.get("chosen") or dp.get("auto") or []
    return "fashion" if "fashion" in chosen else (chosen[0] if chosen else None)


def _region(post: dict, region_id: str) -> Optional[dict]:
    for r in post.get("region_annotations", []) or []:
        if str(r.get("id")) == str(region_id):
            return r
    return None


async def _ensure_query_vector(post: dict, region: dict, image_bytes: bytes, *, space_name: str,
                               model: str, role: str, reindex: bool, encoder=None, fashion=None
                               ) -> Dict[str, Any]:
    """Return the region's query vector for `space_name`, (re)indexing on demand. Staleness is
    judged by geometry/source/mask — a label edit never forces a re-embed."""
    post_id = str(post.get("_id") or post.get("id") or "")
    eid = res.make_embedding_id(post_id, str(region.get("id")), model=model, role=role)
    rec = await res.get_embedding(eid)
    rle = region.get("mask_rle")
    from backend.services import mask_geometry as mg
    cur_mask = res.mask_hash(rle) if mg.rle_is_valid(rle) else ""
    src = res.content_hash(image_bytes)
    stale, reason = (True, "missing") if rec is None else res.is_stale(
        rec, geometry_rev=region.get("geometry_rev"), source_content_hash=src,
        mask_hash=cur_mask, model=model)
    indexed = False
    if rec is None or stale or reindex:
        if model == "fashion-clip":
            await ees.embed_fashion_region(post, region, image_bytes, fashion=fashion, persist=True)
        else:
            await ees.embed_post_regions(post, image_bytes, encoder=encoder, persist=True)
        rec = await res.get_embedding(eid)
        indexed = True
    return {"rec": rec, "indexed": indexed, "was_stale": bool(stale), "stale_reason": reason}


async def find_similar_for_region(
    post: dict, region_id: str, image_bytes: bytes, *,
    mode: str = "identity", top_k: int = 8, exclude_self_post: bool = False,
    reindex: bool = False, scope_post_ids: Sequence[str], catalog=None,
    encoder=None, fashion=None,
) -> Dict[str, Any]:
    """The full flow. `mode` ∈ {identity, context}. `catalog` resolves neighbour posts for
    hydration (defaults to the posts collection). Returns a status envelope with results."""
    region = _region(post, region_id)
    if region is None:
        return {"status": "error", "reason": f"no region {region_id}"}
    domain = _domain_of(post)
    routed = rs.route(query_kind="evidence", domain=domain, context_sensitive=(mode == "context"))
    space_name = routed["space"]
    if not routed["available"]:
        return {"status": "unavailable", "space": space_name, "reason": routed["reason"], "results": []}

    sp = rs._SPACES[space_name]
    model, role = sp["model"], sp["role"]
    q = await _ensure_query_vector(post, region, image_bytes, space_name=space_name, model=model,
                                   role=role, reindex=reindex, encoder=encoder, fashion=fashion)
    rec = q["rec"]
    if not rec or not rec.get("vector"):
        return {"status": "error", "space": space_name, "reason": "could not index this region",
                "results": []}

    post_id = str(post.get("_id") or post.get("id") or "")
    # top_k+1 then drop the query's own vector — a region is never its own neighbour.
    found = await rs.find_similar(rec["vector"], space=space_name, post_ids=scope_post_ids,
                                  exclude_post_id=post_id if exclude_self_post else None,
                                  top_k=top_k + 1)
    if found["status"] != "ready":
        return {**found, "mode": mode, "indexed": q["indexed"]}

    neighbours = [h for h in found["results"]
                  if not (h["post_id"] == post_id and str(h["region_id"]) == str(region_id))][:top_k]
    results = await _hydrate(neighbours, catalog=catalog)
    return {"status": "ready" if results else "empty", "space": space_name, "mode": mode,
            "domain": domain, "indexed": q["indexed"], "was_stale": q["was_stale"],
            "query": {"post_id": post_id, "region_id": str(region_id), "role": role},
            "results": results}


async def _hydrate(hits: List[dict], *, catalog=None) -> List[Dict[str, Any]]:
    """Attach to each neighbour what the curator needs to judge it — source, exact-mask geometry
    (for recall), similarity, space, provenance. Neighbours are evidence, not assertions."""
    if catalog is None:
        from backend.database import post_collection
        from bson import ObjectId
        async def catalog(pid):
            try:
                return await post_collection.find_one({"_id": ObjectId(pid)})
            except Exception:
                return None
    out: List[Dict[str, Any]] = []
    for h in hits:
        p = await catalog(h["post_id"])
        if not p:
            continue
        reg = _region(p, h["region_id"]) or {}
        emb = await res.get_embedding(h["embedding_id"]) or {}
        out.append({
            "post_id": h["post_id"], "region_id": h["region_id"], "role": h.get("role"),
            "score": h["score"], "space": emb.get("space"),
            "label": reg.get("label") or reg.get("category") or "",
            "handle": p.get("instagram_handle") or "",
            "photo_url": p.get("photo_url"),
            "geometry": {"polygons": reg.get("polygons"), "box": reg.get("box"),
                         "mask_rle": reg.get("mask_rle")},   # for recalling the exact mask in situ
            "provenance": {"model": emb.get("model"), "checkpoint": emb.get("checkpoint"),
                           "route": emb.get("route"), "dim": emb.get("dim"),
                           "geometry_rev": emb.get("geometry_rev")},
        })
    return out
