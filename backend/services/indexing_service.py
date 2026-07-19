"""
VISION-E · E6 — resumable indexing boundary.

The safe job mechanics interactive use and a small explicit batch need — and nothing more. NO
automatic corpus-wide backfill happens here (that is Increment F); this module only provides:

  · **idempotent** work — a Region is skipped when its stored vector is already fresh (identity
    role, judged by geometry_rev / mask / model — a label edit never forces re-work), and writes
    go through the deterministic-id upsert, so re-running never duplicates a row;
  · **resumable** batches — an interrupted run, re-run, re-processes only what it didn't finish;
  · **stale detection** by geometry/source/mask/model/preprocessing (via `region_embedding_service`);
  · **version isolation** — vectors live in per-(model, role, version) spaces, so old embeddings
    stay query-isolated when the model or preprocessing changes;
  · progress / cancellation, resource-aware GPU work through `embed_post_regions` (ModelManager);
  · a **dry-run** inventory + runtime/storage estimate to size the Increment-F backfill.

Dependencies (image fetch, encoder) are injectable so the mechanics are testable without a GPU.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from backend.services import region_embedding_service as res
from backend.services import evidence_embedding_service as ees
from backend.services import mask_geometry as mg

# rough per-item costs measured in E2 (GTX 1650, FP32) — for dry-run estimation only.
_SEC_PER_POST = 0.10          # whole-image encode (warm) + overhead
_SEC_PER_REGION = 0.08        # identity pool + context crop-encode
_BYTES_PER_VECTOR = 3072      # a 384-float vector as JSON in Mongo (~8 chars/float) + keys, rounded


async def _region_stale(post_id: str, region: dict, model: str) -> Dict[str, Any]:
    """Return {needs, reason} for one Region in the query's model space. Freshness is judged
    WITHOUT the image (geometry_rev + mask + model), so planning never fetches pixels; a label
    edit is not one of these axes, so it never marks a Region stale."""
    eid = res.make_embedding_id(post_id, str(region.get("id")), model=model, role="identity")
    rec = await res.get_embedding(eid)
    rle = region.get("mask_rle")
    mh = res.mask_hash(rle) if mg.rle_is_valid(rle) else ""
    if rec is None:
        return {"needs": True, "reason": "missing"}
    stale, reason = res.is_stale(rec, geometry_rev=region.get("geometry_rev"),
                                 mask_hash=mh, model=model)
    return {"needs": stale, "reason": reason or "fresh"}


def _dissected(post: dict) -> List[dict]:
    return [r for r in (post.get("region_annotations") or []) if r.get("id")]


async def plan_batch(posts: Sequence[dict], *, model: str = "dinov2_vits14",
                     force: bool = False) -> Dict[str, Any]:
    """Dry-run a batch: which posts/Regions need (re)indexing, and the estimated cost — without
    fetching a single image or writing anything."""
    per_post = []
    n_regions = n_needs = 0
    for post in posts:
        pid = str(post.get("_id") or post.get("id") or "")
        regs = _dissected(post)
        needs = []
        for r in regs:
            n_regions += 1
            st = {"needs": True, "reason": "forced"} if force else await _region_stale(pid, r, model)
            if st["needs"]:
                needs.append({"region_id": str(r.get("id")), "reason": st["reason"]})
        n_needs += len(needs)
        if needs:
            per_post.append({"post_id": pid, "regions": len(regs), "needs": len(needs),
                             "detail": needs})
    # a post that needs any Region re-encodes all its roles once (shared whole-image compute)
    posts_to_run = len(per_post)
    est_vectors = sum(1 + p["regions"] * 2 for p in per_post)      # 1 whole + 2 roles/region
    est_seconds = round(posts_to_run * _SEC_PER_POST + n_needs * _SEC_PER_REGION, 1)
    est_bytes = est_vectors * _BYTES_PER_VECTOR
    return {"model": model, "posts_total": len(posts), "posts_to_index": posts_to_run,
            "regions_total": n_regions, "regions_to_index": n_needs, "est_vectors": est_vectors,
            "est_seconds": est_seconds, "est_storage_kb": round(est_bytes / 1024, 1),
            "per_post": per_post}


async def run_batch(posts: Sequence[dict], *, fetch_image: Callable, model: str = "dinov2_vits14",
                    roles=("whole_image", "identity", "context"), encoder=None,
                    cancel=None, on_progress: Optional[Callable] = None, force: bool = False
                    ) -> Dict[str, Any]:
    """Index a small explicit batch. Idempotent + resumable: a post with no stale/missing Region
    is skipped (unless `force`); everything else is (re)embedded through `embed_post_regions`
    (deterministic-id upsert → no duplicate rows). Honours a cancel token between posts."""
    indexed = skipped = failed = 0
    done = 0
    total = len(posts)
    for post in posts:
        if cancel is not None and getattr(cancel, "cancelled", False):
            break
        pid = str(post.get("_id") or post.get("id") or "")
        regs = _dissected(post)
        # skip the whole post when nothing is stale (idempotent — no duplicate feature work)
        if not force:
            stale_any = False
            for r in regs:
                if (await _region_stale(pid, r, model))["needs"]:
                    stale_any = True
                    break
            if not stale_any:
                skipped += 1; done += 1
                if on_progress:
                    on_progress({"post_id": pid, "state": "skipped", "done": done, "total": total})
                continue
        try:
            image_bytes = await fetch_image(post)
            await ees.embed_post_regions(post, image_bytes, encoder=encoder, roles=roles, persist=True)
            indexed += 1
        except Exception as e:                          # one bad post never corrupts the batch
            failed += 1
            if on_progress:
                on_progress({"post_id": pid, "state": "failed", "error": str(e),
                             "done": done + 1, "total": total})
            done += 1
            continue
        done += 1
        if on_progress:
            on_progress({"post_id": pid, "state": "indexed", "done": done, "total": total})
    return {"indexed": indexed, "skipped": skipped, "failed": failed,
            "processed": done, "total": total,
            "cancelled": bool(cancel is not None and getattr(cancel, "cancelled", False))}
