"""
VISION-E · E5 — Find-similar circulation (service logic).

Proves the query indexes on demand, re-indexes when its geometry changed (not its label),
never returns itself, routes to the right space, and hydrates neighbours with the evidence a
curator needs (geometry for mask recall + provenance) — with a fake encoder/store/catalog.
"""
import asyncio

import numpy as np
import pytest
from PIL import Image
import io

from backend.services import find_similar_service as fss
from backend.services import region_embedding_service as res
from backend.services import retrieval_service as rs
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


def _norm(v):
    import math
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class FakeEncoder:
    # dim MUST match retrieval_service's visual space (384) so the space ids align
    model_tag = "dinov2_vits14"; checkpoint = "fake"; preprocessing_version = "dino-v1"; dim = 384
    def available(self): return True
    def encode_image(self, image):
        g = 4
        return {"cls": _norm([1.0] * 384), "patches": _T(np.ones((g, g, 384))), "grid": g}
    def pool_region(self, features, mask_rle):
        a = mg.rle_area(mask_rle)
        return _norm([float((a % (i + 3)) + i) for i in range(384)])   # mask-dependent, distinct
    def encode_crop(self, image):
        w, h = image.size
        return _norm([float((w * h) % (i + 2) + i) for i in range(384)])


class _T:
    def __init__(self, a): self._a = a
    def numpy(self): return self._a


@pytest.fixture()
def store(monkeypatch):
    fake = _FakeCollection()
    monkeypatch.setattr(res, "region_embeddings_collection", fake)
    monkeypatch.setattr(rs, "_dino_available", lambda: True)
    return fake


def _img_bytes():
    buf = io.BytesIO(); Image.new("RGB", (120, 90), (50, 80, 120)).save(buf, "PNG"); return buf.getvalue()


def _region(rid, y0, y1, x0, x1):
    b = np.zeros((90, 120), np.uint8); b[y0:y1, x0:x1] = 1
    r = {"id": rid, "mask_rle": mg.rle_encode_mask(b)}
    mg.canonicalize_geometry(r, provenance={"adapter": "t"})
    return r


def _post():
    return {"_id": "pQ", "region_annotations": [_region("a", 10, 40, 10, 50),
                                                _region("b", 45, 80, 55, 110)]}


def _catalog_from(posts):
    m = {str(p["_id"]): p for p in posts}
    async def cat(pid): return m.get(pid)
    return cat


def _run(post, region_id, **kw):
    cat = _catalog_from([post])
    return asyncio.run(fss.find_similar_for_region(post, region_id, _img_bytes(),
                       scope_post_ids=["pQ"], catalog=cat, encoder=FakeEncoder(), **kw))


# tests ------------------------------------------------------------------------
def test_indexes_on_demand_and_excludes_self(store):
    post = _post()
    out = _run(post, "a")                                     # nothing stored yet
    assert out["status"] == "ready" and out["indexed"] is True
    assert out["space"] == "visual_identity"
    ids = {r["region_id"] for r in out["results"]}
    assert "a" not in ids and "b" in ids                      # never itself; the sibling is a neighbour


def test_results_carry_geometry_and_provenance(store):
    out = _run(_post(), "a")
    nb = out["results"][0]
    assert nb["geometry"]["polygons"] and nb["provenance"]["model"] == "dinov2_vits14"
    assert nb["space"] and nb["score"] is not None            # distance + space present for the curator


def test_stale_geometry_triggers_reindex_but_label_does_not(store):
    post = _post()
    _run(post, "a")                                           # index once
    # a label edit → NOT stale → no reindex
    post["region_annotations"][0]["label"] = "renamed"
    out2 = _run(post, "a")
    assert out2["indexed"] is False and out2["was_stale"] is False
    # a geometry change (new mask/rev) → stale → reindex
    post["region_annotations"][0] = _region("a", 5, 55, 5, 60)   # different mask → new geometry_rev
    post["region_annotations"][0]["geometry_rev"] = 99
    out3 = _run(post, "a", reindex=False)
    assert out3["was_stale"] is True and out3["indexed"] is True


def test_unavailable_space_is_explicit(store, monkeypatch):
    monkeypatch.setattr(rs, "_dino_available", lambda: False)   # DINOv2 down
    out = _run(_post(), "a")
    assert out["status"] == "unavailable" and out["results"] == [] and out["reason"]


def test_missing_region_errors(store):
    out = _run(_post(), "nope")
    assert out["status"] == "error"
