"""
VISION-F · F3 — geometry recovery of ONE post (narrowed scope: the five-sculpture collage).

Runs through the F1 ledger + backup: snapshots curator-only hash before, recovers geometry
(polygon-derive + SAM box-refine, preserving ids/labels/curator fields), validates registration
(no slivers, masks in-frame, curator invariant unchanged), and only THEN persists + commits.
Run: PYTHONPATH=. venv/bin/python scripts/vision_f3_recover_one.py <post_id>
"""
import asyncio
import io
import sys

import httpx
from bson import ObjectId
from PIL import Image

from backend.database import post_collection, region_embeddings_collection as REC
from backend.services import geometry_recovery as gr
from backend.services import vision_recovery as vr
from backend.services import mask_geometry as mg
from backend.services.vision_orchestrator.refine_session import refine_session

PID = sys.argv[1] if len(sys.argv) > 1 else "695be6c9a9ea58f1b6aef5e0"
MATRIX = {"sam": True, "geometry": True}
LEDGER = "architecture-lab/vision-f-recovery/F1-backup/ledger.json"
BACKUP = "architecture-lab/vision-f-recovery/F1-backup/backup.json"


def _sliver(region):
    if not mg.rle_is_valid(region.get("mask_rle")):
        return False
    box = region.get("box") or {}
    a = mg.rle_area(region["mask_rle"])
    return a < 16 or (box.get("w", 1) < 0.006 or box.get("h", 1) < 0.006)


def _in_frame(region):
    b = region.get("box") or {}
    return -0.01 <= b.get("x", 0) and -0.01 <= b.get("y", 0) and \
        b.get("x", 0) + b.get("w", 0) <= 1.01 and b.get("y", 0) + b.get("h", 0) <= 1.01


async def main():
    ledger = vr.Ledger(LEDGER)
    backup = vr.load_backup(BACKUP)
    ledger.set_state(PID, "running"); ledger.save()

    post = await post_collection.find_one({"_id": ObjectId(PID)})
    before_curator = vr.curator_only_hash(post)
    before_ids = [str(r.get("id")) for r in post["region_annotations"]]
    before_labels = {str(r.get("id")): r.get("label") for r in post["region_annotations"]}

    async with httpx.AsyncClient() as c:
        img_bytes = (await c.get(post["photo_url"], timeout=30, follow_redirects=True)).content
    W, H = Image.open(io.BytesIO(img_bytes)).size

    plan = gr.plan_post(post, MATRIX)
    print(f"post {PID}: {plan['actions']}")
    result = await gr.recover_post(post, img_bytes, plan, refine_session=refine_session, image_hw=(H, W))
    await refine_session.unload()

    # ── validate BEFORE persisting ──
    after_curator = vr.curator_only_hash(post)
    after_ids = [str(r.get("id")) for r in post["region_annotations"]]
    after_labels = {str(r.get("id")): r.get("label") for r in post["region_annotations"]}
    slivers = [str(r.get("id")) for r in post["region_annotations"] if _sliver(r)]
    oof = [str(r.get("id")) for r in post["region_annotations"] if not _in_frame(r)]
    now_mask = sum(1 for r in post["region_annotations"] if mg.rle_is_valid(r.get("mask_rle")))

    curator_ok = after_curator == before_curator
    ids_ok = before_ids == after_ids
    labels_ok = before_labels == after_labels
    ok = curator_ok and ids_ok and labels_ok and not slivers and not oof

    print(f"  curator_only_hash preserved: {curator_ok} ({before_curator[:10]} -> {after_curator[:10]})")
    print(f"  region ids preserved: {ids_ok} | labels preserved: {labels_ok}")
    print(f"  masks now: {now_mask}/{len(post['region_annotations'])} | slivers: {slivers} | out-of-frame: {oof}")
    for t in result["trace"]:
        if t["action"] in ("derive_polygon", "sam_refine_box"):
            print(f"    {t['region_id']:8} {t['label']:22} {t['action']:16} ok={t['ok']} rev={t.get('geometry_rev')}")

    if not ok:
        ledger.set_state(PID, "failed", reason="validation failed"); ledger.save()
        print("\nVALIDATION FAILED — NOT persisting. Ledger=failed.")
        return

    # ── persist the mutation (geometry + grounds only) + commit ──
    await post_collection.update_one({"_id": ObjectId(PID)},
                                     {"$set": {"region_annotations": post["region_annotations"],
                                               "grounds": post.get("grounds") or []}})
    ledger.set_state(PID, "committed", curator_hash=after_curator,
                     before_curator=before_curator, masks=now_mask,
                     detached_marked=result["detached_marked"]); ledger.save()
    print(f"\nCOMMITTED post {PID}. Ledger={ledger.state(PID)}. Detached marked: {result['detached_marked']}")

    # stale embeddings? (geometry changed → E vectors now stale; F4 will refresh)
    stale = 0
    from backend.services import region_embedding_service as res
    for r in post["region_annotations"]:
        eid = res.make_embedding_id(PID, str(r.get("id")), model="dinov2_vits14", role="identity")
        rec = await res.get_embedding(eid)
        if rec:
            st, _ = res.is_stale(rec, geometry_rev=r.get("geometry_rev"),
                                 mask_hash=res.mask_hash(r.get("mask_rle")), model="dinov2_vits14")
            stale += int(st)
    print(f"embeddings now stale (for F4 refresh): {stale}")


if __name__ == "__main__":
    asyncio.run(main())
