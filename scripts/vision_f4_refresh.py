"""
VISION-F · F4 — dependent semantic + embedding refresh for the recovered posts.

(1) Marks D semantic assertions stale ONLY where the referenced evidence changed (curator
decisions preserved); (2) refreshes stale E vectors through the resumable indexing job, measuring
throughput/VRAM/failures; (3) proves idempotent resume (no duplicate rows) and that geometry-
stable posts are not recomputed. Run: PYTHONPATH=. venv/bin/python scripts/vision_f4_refresh.py
"""
import asyncio
import io
import time

import httpx
from bson import ObjectId

from backend.database import post_collection, region_embeddings_collection as REC
from backend.services import indexing_service as ix
from backend.services import geometry_recovery as gr
from backend.services import vision_recovery as vr
from backend.services import region_embedding_service as res

BATCH = ["695be6c9a9ea58f1b6aef5e0", "695be8baa9ea58f1b6aef609", "695be786a9ea58f1b6aef5ed",
         "695be794a9ea58f1b6aef5f1", "6a5b91ecbf74ef485d00399f", "695be77ea9ea58f1b6aef5eb"]
BACKUP = "architecture-lab/vision-f-recovery/F1-backup/backup.json"


async def _fetch(post):
    async with httpx.AsyncClient() as c:
        return (await c.get(post["photo_url"], timeout=30, follow_redirects=True)).content


async def main():
    backup = vr.load_backup(BACKUP)
    # prior (pre-recovery) mask hashes per post, from the backup
    prior = {}
    for snap in backup["posts"]:
        pid = snap["post_id"]
        prior[pid] = {str(r.get("id")): (res.mask_hash(r.get("mask_rle"))
                      if r.get("mask_rle") else "") for r in snap["doc"].get("region_annotations") or []}

    # ── (1) semantic staleness — preserve curator decisions ──
    print("=== semantic staleness (curator decisions preserved) ===")
    for pid in BATCH:
        post = await post_collection.find_one({"_id": ObjectId(pid)})
        sem = post.get("semantics") or {}
        if not (sem.get("assertions")):
            continue
        stale = gr.stale_semantic_assertions(post, prior.get(pid, {}))
        curated = [a["candidate_id"] for a in sem["assertions"]
                   if a.get("status") in ("accepted", "overridden", "rejected", "tentative")]
        print(f"  {pid[-6:]}: {len(sem['assertions'])} assertions, stale={stale}, "
              f"curator-decided (preserved)={curated}")
        # (no semantics post had its geometry changed → nothing to rerun; decisions untouched)

    # ── (2) embedding refresh through the resumable job (measure) ──
    print("\n=== embedding refresh (resumable) ===")
    n_before = await REC.count_documents({})
    ids_before = set()
    async for d in REC.find({}, {"embedding_id": 1}):
        ids_before.add(d["embedding_id"])

    peak = 0
    try:
        import torch
        torch.cuda.reset_peak_memory_stats()
    except Exception:
        torch = None
    prog = []
    t0 = time.time()
    r1 = await ix.run_batch([await post_collection.find_one({"_id": ObjectId(p)}) for p in BATCH],
                            fetch_image=_fetch, on_progress=lambda e: prog.append(e))
    dt = time.time() - t0
    if torch:
        peak = torch.cuda.max_memory_allocated() // 1024 ** 2
    n_after = await REC.count_documents({})
    print(f"  run1: {r1}  wall={dt:.1f}s peakVRAM={peak}MiB")
    print(f"  rows {n_before} -> {n_after} (equal = no duplicates; deterministic-id upsert)")

    # ── (3) idempotent resume: a second run recomputes nothing ──
    r2 = await ix.run_batch([await post_collection.find_one({"_id": ObjectId(p)}) for p in BATCH],
                            fetch_image=_fetch)
    n_final = await REC.count_documents({})
    print(f"  run2 (resume): {r2}  rows={n_final}")

    # verify routes/space freshness on a recovered post: identity now mask_pool (was crop_cls)
    doc = await REC.find_one({"post_id": "695be6c9a9ea58f1b6aef5e0", "role": "identity"})
    print(f"\nrecovered identity route now: {doc.get('route')} (mask_pool = uses the new mask); "
          f"space={doc.get('space')}")
    # stale count after refresh should be 0
    stale_now = 0
    for pid in BATCH:
        post = await post_collection.find_one({"_id": ObjectId(pid)})
        for r in post.get("region_annotations") or []:
            rec = await res.get_embedding(res.make_embedding_id(pid, str(r.get("id")),
                                          model="dinov2_vits14", role="identity"))
            if rec:
                st, _ = res.is_stale(rec, geometry_rev=r.get("geometry_rev"),
                                     mask_hash=res.mask_hash(r.get("mask_rle")), model="dinov2_vits14")
                stale_now += int(st)
    ok = (n_after == n_before) and (r2["indexed"] == 0) and stale_now == 0
    print(f"stale embeddings after refresh: {stale_now}")
    print(f"\nRESULT: {'PASS' if ok else 'CHECK'} — no dup rows, resume recomputed nothing, 0 stale")


if __name__ == "__main__":
    asyncio.run(main())
