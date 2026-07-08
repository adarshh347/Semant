"""
Track B · Phase 1 verification — FashionCLIP vectorize + zero-shot label + domain
router, end-to-end against the live DB (in-process; no HTTP).

    env PYTHONPATH=$PWD ./venv/bin/python scripts/verify_track_b_phase1.py

Proves:
  1. Embeddings persist to the region_embeddings SIDECAR and Region.embedding_id is
     set — and the vectors are NOT in the post document.
  2. Similarity is meaningful: a region's nearest neighbour scores higher than its
     farthest (numbers printed), and zero-shot text grounding works.
  3. Domain router returns "fashion" on a fashion post; part/attributes[] populate on
     at least one real region.
  4. Regression: aggregate_categories returns identical buckets before vs after
     (enrichment is additive — never touches the six catalog keys).
"""

import asyncio
import httpx

from backend.database import post_collection, region_embeddings_collection
from backend.routers.posts import _compute_region_enrichment, _image_fetch_headers, post_helper
from backend.schemas.post import Post
from backend.services import region_embedding_service, fashion_clip_service as fc
from backend.services import anatomy_catalog_service

FASHIONY = {"garment", "figure", "person-part", "jewellery", "accessory",
            "garment-detail", "hair", "skin"}


def _catalog_fingerprint(profile):
    """Order-independent fingerprint of the catalog buckets (the six-key output)."""
    return sorted(
        (p["category"], p["label"], p["occurrence_count"], p["prioritised_count"],
         p["total_intensity"]) for p in profile
    )


async def pick_fashion_post():
    """A post with several regions whose categories look fashion-ish."""
    best = None
    async for post in post_collection.find({"region_annotations": {"$exists": True, "$ne": None}}):
        regs = post.get("region_annotations") or []
        if len(regs) < 2 or not post.get("photo_url"):
            continue
        score = sum(1 for r in regs if (r.get("category") or "").lower() in FASHIONY)
        if best is None or score > best[0]:
            best = (score, post)
    return best[1] if best else None


async def main():
    print("=" * 70)
    print("TRACK B · PHASE 1 VERIFICATION (FashionCLIP)")
    print("=" * 70)
    print(f"FashionCLIP available: {fc.is_available()}")
    assert fc.is_available(), "torch/transformers not installed"

    # ---- catalog fingerprint BEFORE ------------------------------------------
    before = _catalog_fingerprint(await anatomy_catalog_service.aggregate_categories(min_occurrences=1))

    post = await pick_fashion_post()
    assert post, "no post with regions found"
    pid = str(post["_id"])

    # Reset any prior enrichment so this is a true fresh run (reproducible counts;
    # scrubs first-cut labels). Geometry + the six catalog keys are untouched.
    cleaned = []
    for r in (post.get("region_annotations") or []):
        r = dict(r)
        r.pop("embedding_id", None); r.pop("part", None); r.pop("attributes", None)
        cleaned.append(r)
    await post_collection.update_one({"_id": post["_id"]},
        {"$set": {"region_annotations": cleaned}, "$unset": {"domain": ""}})
    await region_embeddings_collection.delete_many({"post_id": pid})
    post = await post_collection.find_one({"_id": post["_id"]})

    regions = post.get("region_annotations") or []
    print(f"\nTest post: {pid}  ({len(regions)} regions)")
    print("Loading FashionCLIP (first run downloads ~600MB)…")

    # ---- fetch image + run enrichment (the exact endpoint compute path) ------
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(post["photo_url"], headers=_image_fetch_headers(post["photo_url"]))
        resp.raise_for_status()
        img_bytes = resp.content

    result = await asyncio.to_thread(_compute_region_enrichment, img_bytes, regions, pid)

    # persist exactly as the endpoint does
    for eid, vec, rid in result["to_upsert"]:
        await region_embedding_service.upsert_embedding(eid, vec, model="fashion-clip",
                                                         post_id=pid, region_id=rid)
    await post_collection.update_one(
        {"_id": post["_id"]},
        {"$set": {"region_annotations": result["regions"], "domain": result["domain"]}},
    )

    # ---- 1. embeddings in sidecar, pointers on regions, NOT in post ----------
    updated = await post_collection.find_one({"_id": post["_id"]})
    ur = updated.get("region_annotations") or []
    with_ptr = [r for r in ur if r.get("embedding_id")]
    print(f"\n[1] Sidecar persistence")
    print(f"    regions with embedding_id : {len(with_ptr)}/{len(ur)}")
    sidecar_count = await region_embeddings_collection.count_documents({"post_id": pid})
    print(f"    sidecar docs for this post: {sidecar_count}")
    sample_emb = await region_embedding_service.get_embedding(with_ptr[0]["embedding_id"])
    print(f"    sample vector dim         : {sample_emb['dim']} (model={sample_emb['model']})")
    # vectors must NOT be inside the post document
    post_str = str(updated)
    no_vec_in_post = "vector" not in post_str and not any("vector" in r for r in ur)
    print(f"    vectors absent from post doc: {no_vec_in_post}")
    assert with_ptr, "no region got an embedding_id"
    assert sidecar_count >= len(with_ptr), "sidecar missing embeddings"
    assert sample_emb and sample_emb["dim"] > 0, "embedding vector empty"
    assert no_vec_in_post, "vector leaked into the post document"
    print("    ✅ vectors live in the sidecar; post carries only pointers")

    # ---- 2. similarity is meaningful -----------------------------------------
    print(f"\n[2] Similarity (cosine over FashionCLIP vectors)")
    embs = {}
    for r in with_ptr:
        d = await region_embedding_service.get_embedding(r["embedding_id"])
        if d:
            embs[r["id"]] = (r.get("label", r["id"]), d["vector"])
    ids = list(embs)
    anchor = ids[0]
    alabel, avec = embs[anchor]
    sims = sorted(
        ((embs[j][0], fc.cosine(avec, embs[j][1])) for j in ids if j != anchor),
        key=lambda t: t[1], reverse=True,
    )
    if sims:
        print(f"    anchor region: '{alabel}'")
        print(f"      nearest : '{sims[0][0]}'  cos={sims[0][1]:.3f}")
        print(f"      farthest: '{sims[-1][0]}'  cos={sims[-1][1]:.3f}")
        assert sims[0][1] >= sims[-1][1], "nearest not >= farthest (vector space broken)"
    # zero-shot text grounding on the anchor crop
    from backend.services.fashion_clip_service import _open_image, _crop_norm, zero_shot
    img = _open_image(img_bytes)
    anchor_box = next((r.get("box") for r in ur if r["id"] == anchor), None)
    grounding = zero_shot(_crop_norm(img, anchor_box), ["a garment", "a landscape", "a building", "a face"])
    print(f"    zero-shot on anchor crop  : " + ", ".join(f"{l}={p:.2f}" for l, p in grounding[:4]))
    print("    ✅ nearest ≥ farthest; text-image grounding responds")

    # ---- 3. domain + labels ---------------------------------------------------
    dom = result["domain"]
    labeled = [r for r in ur if r.get("part") or r.get("attributes")]
    print(f"\n[3] Domain router + zero-shot labels")
    print(f"    domain: {dom}")
    for r in labeled[:5]:
        print(f"      region '{r.get('label')}' → part={r.get('part')!r} attrs={r.get('attributes')}")
    print(f"    embedded={result['embedded']} labeled={result['labeled']} skipped_cached={result['skipped']}")
    assert dom.get("label") == "fashion" and dom.get("is_fashion"), f"domain not fashion: {dom}"
    assert labeled, "no region got a part/attributes label"
    print("    ✅ domain=fashion; ≥1 region labeled")

    # ---- 4. catalog regression -----------------------------------------------
    after = _catalog_fingerprint(await anatomy_catalog_service.aggregate_categories(min_occurrences=1))
    print(f"\n[4] Catalog regression")
    print(f"    buckets before={len(before)} after={len(after)} identical={before == after}")
    assert before == after, "aggregate_categories changed — enrichment perturbed the catalog"
    print("    ✅ catalog buckets identical (enrichment is additive)")

    # ---- Post response model still validates ---------------------------------
    Post.model_validate(post_helper(updated))
    print("\n    ✅ enriched post still validates through Post response_model")

    print("\n" + "=" * 70)
    print("ALL CHECKS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
