"""
VISION-F · F1 — backup, migration ledger, per-post rollback.

Proves: a scoped backup captures posts + sidecar rows with an identity hash; restoring on a
disposable copy reproduces the curator identity after a mutation; the ledger is idempotent
(a committed job is skipped, so rerunning duplicates nothing); per-post rollback restores
geometry, assertions and embeddings without touching other posts.
"""
import asyncio
import os
import tempfile

import numpy as np
import pytest

from backend.services import vision_recovery as vr
from backend.services import mask_geometry as mg


# in-memory async collection ---------------------------------------------------
def _match(doc, filt):
    for k, v in filt.items():
        if isinstance(v, dict) and "$in" in v:
            if doc.get(k) not in v["$in"]:
                return False
        elif doc.get(k) != v:
            return False
    return True


class _Cursor:
    def __init__(self, docs): self._docs = docs
    def __aiter__(self): self._it = iter(self._docs); return self
    async def __anext__(self):
        try: return next(self._it)
        except StopIteration: raise StopAsyncIteration


class _Coll:
    def __init__(self): self.docs = []
    async def find_one(self, filt, projection=None):
        for d in self.docs:
            if _match(d, filt): return d
        return None
    def find(self, filt, projection=None):
        return _Cursor([dict(d) for d in self.docs if _match(d, filt)])
    async def update_one(self, filt, update, upsert=False):
        for d in self.docs:
            if _match(d, filt):
                d.update(update.get("$set", {})); return
        if upsert:
            d = dict(filt); d.update(update.get("$setOnInsert", {})); d.update(update.get("$set", {}))
            self.docs.append(d)
    async def delete_many(self, filt):
        self.docs = [d for d in self.docs if not _match(d, filt)]


def _region(rid, y0, y1, x0, x1, note="", rev=1):
    b = np.zeros((60, 80), np.uint8); b[y0:y1, x0:x1] = 1
    r = {"id": rid, "mask_rle": mg.rle_encode_mask(b)}
    mg.canonicalize_geometry(r, provenance={"adapter": "t"})
    r.update({"user_note": note, "prioritised": bool(note), "weight": 3 if note else 0,
              "label": rid, "actor": "creator" if note else "auto"})
    return r


def _post(pid):
    return {"_id": pid, "photo_url": "http://x/y.jpg", "photo_public_id": "pub_" + pid,
            "source_url": "http://insta/" + pid,
            "region_annotations": [_region("r0", 5, 30, 5, 40, note="curator note"),
                                   _region("r1", 32, 55, 45, 75)],
            "semantics": {"assertions": [{"candidate_id": "r0", "status": "accepted",
                                          "curator_label": "my label", "label": "auto"}]},
            "grounds": [{"id": "g0", "ground_type": "region", "region_id": "r0"}],
            "percepts": [{"id": "p0", "ground_ids": ["g0"], "expression": "a noticing"}]}


def _emb_rows(pid):
    return [{"embedding_id": f"emb_dinov2_vits14_identity_{pid}_r0", "post_id": pid,
             "region_id": "r0", "vector": [0.1] * 8, "space": "s", "role": "identity"}]


# tests ------------------------------------------------------------------------
def test_backup_captures_posts_and_embeddings_with_hash():
    posts = _Coll(); embs = _Coll()
    p = _post("pA"); posts.docs.append(p)
    embs.docs.extend(_emb_rows("pA"))
    backup = asyncio.run(vr.backup_scope(["pA"], post_collection=posts, emb_collection=embs))
    assert backup["n_posts"] == 1 and backup["n_embeddings"] == 1
    snap = backup["posts"][0]
    assert snap["identity_hash"] and snap["schema"]["backup"] == vr.BACKUP_SCHEMA
    assert snap["identity_hash"] == vr.curator_identity_hash(p)


def test_identity_hash_ignores_labels_of_geometry_but_tracks_curator_fields():
    p = _post("pA")
    h0 = vr.curator_identity_hash(p)
    # a transient field (description) doesn't move the identity hash
    p["region_annotations"][0]["description"] = "changed blurb"
    assert vr.curator_identity_hash(p) == h0
    # a curator field (the note) DOES
    p["region_annotations"][0]["user_note"] = "different note"
    assert vr.curator_identity_hash(p) != h0


def test_restore_reproduces_identity_after_mutation():
    posts = _Coll(); embs = _Coll()
    p = _post("pA"); posts.docs.append(p); embs.docs.extend(_emb_rows("pA"))
    orig_hash = vr.curator_identity_hash(p)
    backup = asyncio.run(vr.backup_scope(["pA"], post_collection=posts, emb_collection=embs))
    # mutate the live copy destructively: wreck geometry, drop the curator decision + embeddings
    p["region_annotations"][0]["geometry_rev"] = 99
    p["region_annotations"][0]["mask_rle"] = {"size": [1, 1], "counts": [1]}
    p["semantics"] = {"assertions": []}
    embs.docs.clear()
    assert vr.curator_identity_hash(p) != orig_hash
    # per-post restore from backup
    r = asyncio.run(vr.restore_post("pA", backup, post_collection=posts, emb_collection=embs))
    assert r["status"] == "restored" and r["embeddings"] == 1
    restored = asyncio.run(posts.find_one({"_id": "pA"}))
    assert vr.curator_identity_hash(restored) == orig_hash        # identity reproduced byte-for-byte
    assert len(embs.docs) == 1                                     # embeddings re-materialised


def test_restore_is_idempotent_no_duplicates():
    posts = _Coll(); embs = _Coll()
    posts.docs.append(_post("pA")); embs.docs.extend(_emb_rows("pA"))
    backup = asyncio.run(vr.backup_scope(["pA"], post_collection=posts, emb_collection=embs))
    asyncio.run(vr.restore_post("pA", backup, post_collection=posts, emb_collection=embs))
    asyncio.run(vr.restore_post("pA", backup, post_collection=posts, emb_collection=embs))
    # two restores → still one post row and one embedding row (no duplication)
    assert len(posts.docs) == 1 and len(embs.docs) == 1


def test_restore_touches_only_its_own_post():
    posts = _Coll(); embs = _Coll()
    posts.docs.extend([_post("pA"), _post("pB")]); embs.docs.extend(_emb_rows("pA") + _emb_rows("pB"))
    backup = asyncio.run(vr.backup_scope(["pA", "pB"], post_collection=posts, emb_collection=embs))
    b_hash = vr.curator_identity_hash(asyncio.run(posts.find_one({"_id": "pB"})))
    # corrupt pA only, restore pA only — pB is untouched
    pa = asyncio.run(posts.find_one({"_id": "pA"})); pa["semantics"] = {"assertions": []}
    asyncio.run(vr.restore_post("pA", backup, post_collection=posts, emb_collection=embs))
    assert vr.curator_identity_hash(asyncio.run(posts.find_one({"_id": "pB"}))) == b_hash


def test_ledger_is_idempotent_and_resumable():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "ledger.json")
        lg = vr.Ledger(path)
        lg.plan("pA", "geometry"); lg.plan("pB", "geometry")
        lg.set_state("pA", "committed"); lg.save()
        # a committed job is skipped on resume; pending returns only unfinished work
        lg2 = vr.Ledger(path)
        assert lg2.is_committed("pA") and lg2.pending() == ["pB"]
        assert lg2.counts()["committed"] == 1 and lg2.counts()["planned"] == 1


def test_ledger_records_state_history():
    with tempfile.TemporaryDirectory() as d:
        lg = vr.Ledger(os.path.join(d, "l.json"))
        lg.plan("pA", "geometry"); lg.set_state("pA", "running"); lg.set_state("pA", "committed")
        assert [h[0] for h in lg.rows["pA"]["history"]] == ["planned", "running", "committed"]
