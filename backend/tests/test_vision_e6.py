"""
VISION-E · E6 — resumable indexing boundary.

Proves an interrupted small-batch index resumes without duplicating rows or re-doing fresh work,
stale evidence (not label edits) triggers re-index, old vectors stay query-isolated by version,
and a dry-run estimates the Increment-F backfill without touching images or the store.
"""
import asyncio
import io

import numpy as np
import pytest
from PIL import Image

from backend.services import indexing_service as ix
from backend.services import region_embedding_service as res
from backend.services import mask_geometry as mg


# fakes ------------------------------------------------------------------------
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


class _FakeCollection:
    def __init__(self): self.docs = []
    async def create_index(self, *a, **k): return "ok"
    async def update_one(self, filt, update, upsert=False):
        for d in self.docs:
            if _match(d, filt):
                d.update(update.get("$set", {})); return
        if upsert:
            d = dict(update.get("$setOnInsert", {})); d.update(update.get("$set", {})); self.docs.append(d)
    def find(self, filt, projection=None):
        return _Cursor([dict(d) for d in self.docs if _match(d, filt)])
    async def find_one(self, filt, projection=None):
        for d in self.docs:
            if _match(d, filt):
                return {k: v for k, v in d.items() if k != "_id"}
        return None
    async def count_documents(self, filt):
        return sum(1 for d in self.docs if _match(d, filt))


def _norm(v):
    import math
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class FakeEncoder:
    model_tag = "dinov2_vits14"; checkpoint = "fake"; preprocessing_version = "dino-v1"; dim = 384
    def __init__(self): self.n_encode_image = 0
    def available(self): return True
    def encode_image(self, image):
        self.n_encode_image += 1
        return {"cls": _norm([1.0] * 384), "patches": _T(np.ones((4, 4, 384))), "grid": 4}
    def pool_region(self, features, mask_rle):
        a = mg.rle_area(mask_rle); return _norm([float((a % (i + 3)) + i) for i in range(384)])
    def encode_crop(self, image):
        w, h = image.size; return _norm([float((w * h) % (i + 2) + i) for i in range(384)])


class _T:
    def __init__(self, a): self._a = a
    def numpy(self): return self._a


@pytest.fixture()
def store(monkeypatch):
    fake = _FakeCollection()
    monkeypatch.setattr(res, "region_embeddings_collection", fake)
    return fake


def _region(rid, y0, y1, x0, x1):
    b = np.zeros((90, 120), np.uint8); b[y0:y1, x0:x1] = 1
    r = {"id": rid, "mask_rle": mg.rle_encode_mask(b)}
    mg.canonicalize_geometry(r, provenance={"adapter": "t"})
    return r


def _post(pid, n):
    return {"_id": pid, "region_annotations": [_region(f"r{i}", 5 + i * 5, 25 + i * 5, 10, 60) for i in range(n)]}


async def _fetch(post):
    buf = io.BytesIO(); Image.new("RGB", (120, 90), (60, 90, 140)).save(buf, "PNG"); return buf.getvalue()


class _Cancel:
    def __init__(self): self.cancelled = False


# tests ------------------------------------------------------------------------
def test_interrupted_batch_resumes_without_duplication(store):
    posts = [_post("p1", 2), _post("p2", 2), _post("p3", 2)]

    async def go():
        enc = FakeEncoder()
        cancel = _Cancel()
        seen = {"n": 0}
        def prog(ev):
            seen["n"] += 1
            if ev["done"] == 1:      # cancel after the first post finishes
                cancel.cancelled = True
        r1 = await ix.run_batch(posts, fetch_image=_fetch, encoder=enc, cancel=cancel, on_progress=prog)
        count_after_interrupt = len(store.docs)
        # resume: fresh posts are skipped, the rest finish, and NO row is duplicated
        r2 = await ix.run_batch(posts, fetch_image=_fetch, encoder=FakeEncoder())
        return r1, r2, count_after_interrupt
    r1, r2, mid = asyncio.run(go())
    assert r1["cancelled"] is True and r1["indexed"] == 1          # stopped after one post
    assert r2["indexed"] >= 1 and r2["skipped"] >= 1              # resumed: some skipped, rest done
    # every embedding_id is unique — no duplicate rows across the two runs
    ids = [d["embedding_id"] for d in store.docs]
    assert len(ids) == len(set(ids))
    # full corpus now indexed: 3 posts × (1 whole + 2 identity + 2 context) = 15 vectors
    assert len(store.docs) == 15


def test_rerun_is_idempotent_and_skips_fresh(store):
    posts = [_post("p1", 2)]
    async def go():
        await ix.run_batch(posts, fetch_image=_fetch, encoder=FakeEncoder())
        n1 = len(store.docs)
        enc2 = FakeEncoder()
        r = await ix.run_batch(posts, fetch_image=_fetch, encoder=enc2)
        return n1, len(store.docs), r, enc2.n_encode_image
    n1, n2, r, encodes = asyncio.run(go())
    assert n1 == n2 and r["skipped"] == 1 and r["indexed"] == 0    # nothing new, nothing duplicated
    assert encodes == 0                                            # no wasted whole-image encode


def test_geometry_change_reindexes_but_label_does_not(store):
    posts = [_post("p1", 1)]
    async def go():
        await ix.run_batch(posts, fetch_image=_fetch, encoder=FakeEncoder())
        # a label edit → still fresh → skipped
        posts[0]["region_annotations"][0]["label"] = "renamed"
        r_label = await ix.run_batch(posts, fetch_image=_fetch, encoder=FakeEncoder())
        # a geometry change → stale → re-indexed
        posts[0]["region_annotations"][0] = _region("r0", 1, 40, 1, 80)
        posts[0]["region_annotations"][0]["geometry_rev"] = 77
        plan = await ix.plan_batch(posts)
        r_geo = await ix.run_batch(posts, fetch_image=_fetch, encoder=FakeEncoder())
        return r_label, plan, r_geo
    r_label, plan, r_geo = asyncio.run(go())
    assert r_label["skipped"] == 1 and r_label["indexed"] == 0
    assert plan["regions_to_index"] == 1 and plan["posts_to_index"] == 1
    assert r_geo["indexed"] == 1


def test_dry_run_plans_without_touching_images_or_store(store):
    posts = [_post("p1", 3), _post("p2", 2)]
    async def go():
        return await ix.plan_batch(posts)
    plan = asyncio.run(go())
    assert plan["posts_to_index"] == 2 and plan["regions_to_index"] == 5
    assert plan["est_vectors"] == (1 + 3 * 2) + (1 + 2 * 2)        # per post: 1 whole + 2/role/region
    assert plan["est_seconds"] > 0 and plan["est_storage_kb"] > 0
    assert store.docs == []                                        # planning wrote nothing


def test_old_vectors_stay_query_isolated_by_version(store):
    # a v1 vector and a v2 (re-preprocessed) vector of the SAME region live in different spaces
    async def go():
        await res.upsert_embedding(res.make_embedding_id("p", "r", "dinov2_vits14", "identity"),
                                   [1.0] + [0.0] * 383, model="dinov2_vits14", post_id="p",
                                   region_id="r", role="identity", preprocessing_version="dino-v1")
        await res.upsert_embedding("emb_dinov2_vits14_identity_v2_p_r",
                                   [1.0] + [0.0] * 383, model="dinov2_vits14", post_id="p",
                                   region_id="r", role="identity", preprocessing_version="dino-v2")
        v1 = res.space_key("dinov2_vits14", "identity", "dino-v1", 384)
        v2 = res.space_key("dinov2_vits14", "identity", "dino-v2", 384)
        h1 = await res.search_similar([1.0] + [0.0] * 383, post_ids=["p"], space=v1)
        h2 = await res.search_similar([1.0] + [0.0] * 383, post_ids=["p"], space=v2)
        return v1, v2, h1, h2
    v1, v2, h1, h2 = asyncio.run(go())
    assert v1 != v2 and len(h1) == 1 and len(h2) == 1             # each version queried in isolation
