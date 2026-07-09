"""
Corpus backfill — drive POST /posts/{id}/enrich-regions across every post that has
regions, so `region_embeddings` is populated corpus-wide (Darshan Track D · Phase 0).

    # backend must be running (it holds the FashionCLIP model in memory)
    env PYTHONPATH=$PWD ./venv/bin/python scripts/backfill_region_embeddings.py
    …            --base-url http://localhost:8000   # override
    …            --dry-run                          # list what would be enriched

Why the HTTP endpoint rather than calling the service directly: it's the real path the
app uses, it loads the model once in the server process, and enrichment is idempotent
(regions that already carry an `embedding_id` are skipped), so re-running is cheap and
safe.

Until this runs, Track C's taste history is structurally empty: only one post had
vectors, so `search_similar` had nothing to retrieve across posts. After it, the pack's
[THEIR TASTE HISTORY] section can actually fill. The script proves that by querying a
real region and reporting its cross-post neighbours.
"""

import argparse
import asyncio
import sys

import httpx
from bson import ObjectId

from backend.config import settings
from backend.database import post_collection, region_embeddings_collection
from backend.services import region_embedding_service as res


async def targets() -> list:
    """Posts carrying at least one region. Ordered so progress reads sensibly."""
    out = []
    async for post in post_collection.find(
        {"region_annotations": {"$exists": True, "$ne": None}},
        {"region_annotations": 1, "photo_url": 1},
    ):
        regions = post.get("region_annotations") or []
        if not regions or not post.get("photo_url"):
            continue
        pending = sum(1 for r in regions if not r.get("embedding_id"))
        out.append({"id": str(post["_id"]), "regions": len(regions), "pending": pending})
    return out


async def sidecar_stats() -> tuple:
    total = await region_embeddings_collection.count_documents({})
    posts = len(await region_embeddings_collection.distinct("post_id"))
    return total, posts


async def prove_retrieval() -> None:
    """A vector is only worth storing if it retrieves. Query with a real stored region
    and show its nearest neighbours FROM OTHER POSTS — the thing that returned nothing
    before this backfill."""
    print("\n" + "-" * 70)
    print("Cross-post retrieval check (Anuraṇana)")
    all_post_ids = await region_embeddings_collection.distinct("post_id")
    if len(all_post_ids) < 2:
        print("  ⚠️  fewer than 2 posts have vectors — cross-post retrieval still empty")
        return

    seed = await region_embeddings_collection.find_one({}, {"_id": 0})
    hits = await res.search_similar(
        seed["vector"], post_ids=all_post_ids, exclude_post_id=seed["post_id"], top_k=5,
    )
    print(f"  query : region '{seed['region_id']}' of post {seed['post_id'][:8]}…")
    print(f"  scope : {len(all_post_ids)} posts with vectors")
    if not hits:
        print("  ⚠️  no neighbours returned")
        return
    # Name the neighbours: the vectors say which regions, the posts say what they are.
    for hit in hits:
        doc = await post_collection.find_one(
            {"_id": ObjectId(hit["post_id"])}, {"region_annotations": 1}
        )
        label = "?"
        for region in (doc or {}).get("region_annotations") or []:
            if region.get("id") == hit["region_id"]:
                label = region.get("label") or region.get("category") or "?"
        print(f"    cos={hit['score']:.3f}  {label:<22} (post {hit['post_id'][:8]}…)")
    assert all(h["post_id"] != seed["post_id"] for h in hits)
    print("  ✅ retrieval now returns real neighbours from other posts")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 70)
    print("CORPUS EMBEDDING BACKFILL — enrich-regions across all posts with regions")
    print("=" * 70)

    todo = await targets()
    before_vectors, before_posts = await sidecar_stats()
    total_regions = sum(t["regions"] for t in todo)
    total_pending = sum(t["pending"] for t in todo)
    print(f"posts with regions : {len(todo)}")
    print(f"regions            : {total_regions} ({total_pending} without an embedding)")
    print(f"sidecar before     : {before_vectors} vectors across {before_posts} post(s)")

    if args.dry_run:
        for t in todo:
            print(f"  {t['id']}  regions={t['regions']:<3} pending={t['pending']}")
        return 0

    headers = {"X-API-Key": settings.API_KEY} if settings.API_KEY else {}
    embedded = labeled = skipped = 0
    failures = []

    # Enrichment is CPU-bound in the server; drive it serially so we don't queue a
    # thread-pool pile-up behind a single FashionCLIP model.
    async with httpx.AsyncClient(timeout=180.0, headers=headers) as client:
        for i, t in enumerate(todo, 1):
            url = f"{args.base_url}/api/v1/posts/{t['id']}/enrich-regions"
            try:
                resp = await client.post(url)
                if resp.status_code == 503:
                    print("\n❌ FashionCLIP unavailable on the server "
                          "(pip install -r requirements-ml.txt). Aborting.")
                    return 1
                resp.raise_for_status()
                body = resp.json()
                # NB: the endpoint's key is `skipped_cached`, not `skipped`.
                cached = body.get("skipped_cached", 0)
                embedded += body.get("embedded", 0)
                labeled += body.get("labeled", 0)
                skipped += cached
                domain = (body.get("domain") or {}).get("label", "?")
                print(f"[{i:>2}/{len(todo)}] {t['id'][:8]}…  regions={t['regions']:<3} "
                      f"embedded={body.get('embedded', 0):<3} labeled={body.get('labeled', 0):<3} "
                      f"cached={cached:<3} domain={domain}")
            except Exception as e:
                failures.append((t["id"], str(e)[:80]))
                print(f"[{i:>2}/{len(todo)}] {t['id'][:8]}…  ❌ {str(e)[:70]}")

    after_vectors, after_posts = await sidecar_stats()
    print("\n" + "-" * 70)
    print(f"embedded this run  : {embedded}   (already-cached: {skipped})")
    print(f"first-cut labels   : {labeled}")
    print(f"sidecar after      : {after_vectors} vectors across {after_posts} posts "
          f"(+{after_vectors - before_vectors})")
    if failures:
        print(f"\n⚠️  {len(failures)} post(s) failed — these keep their old state, nothing is corrupted:")
        for pid, err in failures:
            print(f"    {pid}: {err}")

    await prove_retrieval()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
