"""
VISION-F · F1 — scoped backup + live restore drill on a DISPOSABLE copy.

Backs up the mutation scope (the dissected posts + their sidecar rows) to a file, initialises the
migration ledger, and validates restoration on temporary collections (dropped afterwards) — no
live corpus row is mutated. Run: PYTHONPATH=. venv/bin/python scripts/vision_f1_backup.py
"""
import asyncio

from backend.database import post_collection, region_embeddings_collection as REC, database
from backend.services import vision_recovery as vr

OUT = "architecture-lab/vision-f-recovery/F1-backup"


async def main():
    # scope = the dissected posts (the only geometry F3 will touch)
    dissected = [str(p["_id"]) async for p in
                 post_collection.find({"region_annotations.0": {"$exists": True}}, {"_id": 1})]
    backup = await vr.backup_scope(dissected, post_collection=post_collection, emb_collection=REC)
    path = vr.write_backup(backup, f"{OUT}/backup.json")
    print(f"BACKUP: {backup['n_posts']} posts, {backup['n_embeddings']} embeddings -> {path}")

    # migration ledger seeded (planned) — idempotent/resumable
    lg = vr.Ledger(f"{OUT}/ledger.json")
    for pid in dissected:
        lg.plan(pid, "geometry_recovery")
    lg.save()
    print(f"LEDGER: {lg.counts()}")

    # ── restore drill on DISPOSABLE temp collections ──
    drill_pid = dissected[0]
    src = await post_collection.find_one({"_id": __import__("bson").ObjectId(drill_pid)})
    tp = database.get_collection("_f_drill_posts")
    te = database.get_collection("_f_drill_emb")
    await tp.delete_many({}); await te.delete_many({})
    await tp.insert_one(dict(src))
    async for e in REC.find({"post_id": drill_pid}):
        await te.insert_one(dict(e))
    orig_hash = vr.curator_identity_hash(src)
    n_emb_before = await te.count_documents({})

    # destroy the disposable copy: wreck geometry, drop semantics + embeddings
    await tp.update_one({"_id": src["_id"]},
                        {"$set": {"semantics": {"assertions": []},
                                  "region_annotations": [{"id": "wrecked", "box": {"x": 0, "y": 0, "w": 0, "h": 0}}]}})
    await te.delete_many({})
    wrecked = await tp.find_one({"_id": src["_id"]})
    print(f"DRILL wrecked identity_hash == orig? {vr.curator_identity_hash(wrecked) == orig_hash} (expect False)")

    # restore from backup into the disposable copy
    r = await vr.restore_post(drill_pid, backup, post_collection=tp, emb_collection=te)
    restored = await tp.find_one({"_id": src["_id"]})
    n_emb_after = await te.count_documents({})
    ok = vr.curator_identity_hash(restored) == orig_hash
    print(f"DRILL restore: status={r['status']} identity reproduced={ok} "
          f"embeddings {n_emb_before}->wiped->{n_emb_after}")

    # idempotency: a second restore duplicates nothing
    await vr.restore_post(drill_pid, backup, post_collection=tp, emb_collection=te)
    n_emb_2 = await te.count_documents({})
    n_posts = await tp.count_documents({"_id": src["_id"]})
    print(f"DRILL idempotent rerun: posts={n_posts} embeddings={n_emb_2} (expect 1, {n_emb_after})")

    # drop the disposable collections — nothing live was touched
    await tp.drop(); await te.drop()
    print("DRILL temp collections dropped.")
    print(f"\nRESULT: restore drill {'PASS' if ok and n_emb_2 == n_emb_after and n_posts == 1 else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
