"""
VISION-E · E2 — DINOv2 shared visual representation (orchestration logic).

Proves the model-reuse rule with an injected fake encoder (no GPU): the whole image is encoded
ONCE for a whole post, Region identity vectors come from POOLING that shared grid (not from
re-encoding), context vectors are crop-encoded, box-only Regions fall back to crop encoding, and
every vector is stored spaced + routed. GPU load/unload of the real model is checked separately.
"""
import io
import math

import numpy as np
import pytest
from PIL import Image

from backend.services import mask_geometry as mg
from backend.services import evidence_embedding_service as ees
from backend.services import region_embedding_service as res


# ── fake encoder: counts calls, returns deterministic mask/crop-dependent vectors ──
def _l2(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class FakeEncoder:
    model_tag = "dinov2_vits14"; checkpoint = "fake-ckpt"; preprocessing_version = "dino-v1"; dim = 8

    def __init__(self, available=True):
        self._av = available
        self.n_encode_image = self.n_pool = self.n_crop = 0

    def available(self): return self._av

    def encode_image(self, image):
        self.n_encode_image += 1
        grid = 4
        patches = np.arange(grid * grid * self.dim, dtype=float).reshape(grid, grid, self.dim)
        return {"cls": _l2([1.0] * self.dim), "patches": _FakeT(patches), "grid": grid}

    def pool_region(self, features, mask_rle):
        self.n_pool += 1
        area = mg.rle_area(mask_rle)
        if area < 4:                                   # sub-patch → let the caller crop-encode
            return None
        return _l2([float((area % (i + 3)) + i * 2) for i in range(self.dim)])

    def encode_crop(self, image):
        self.n_crop += 1
        w, h = image.size
        return _l2([float(((w * h) % (i + 2)) + i) for i in range(self.dim)])


class _FakeT:
    """Minimal stand-in for the torch tensor the real encoder returns (only `.numpy()` used)."""
    def __init__(self, arr): self._a = arr
    def numpy(self): return self._a


# ── in-memory async store (persist tests) ────────────────────────────────────
def _match(doc, filt):
    for k, v in filt.items():
        if isinstance(v, dict) and "$in" in v:
            if doc.get(k) not in v["$in"]:
                return False
        elif doc.get(k) != v:
            return False
    return True


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


class _Cursor:
    def __init__(self, docs): self._docs = docs
    def __aiter__(self): self._it = iter(self._docs); return self
    async def __anext__(self):
        try: return next(self._it)
        except StopIteration: raise StopAsyncIteration


@pytest.fixture()
def store(monkeypatch):
    fake = _FakeCollection()
    monkeypatch.setattr(res, "region_embeddings_collection", fake)
    return fake


# ── helpers ──────────────────────────────────────────────────────────────────
def _img_bytes(w=120, h=90):
    buf = io.BytesIO(); Image.new("RGB", (w, h), (60, 90, 140)).save(buf, "PNG"); return buf.getvalue()


def _region(rid, y0, y1, x0, x1, H=90, W=120):
    b = np.zeros((H, W), np.uint8); b[y0:y1, x0:x1] = 1
    r = {"id": rid, "mask_rle": mg.rle_encode_mask(b)}
    mg.canonicalize_geometry(r, provenance={"adapter": "t"})
    return r


def _post(regions):
    return {"_id": "pX", "region_annotations": regions}


def _run(post, enc, **kw):
    import asyncio
    return asyncio.run(ees.embed_post_regions(post, _img_bytes(), encoder=enc, **kw))


# ── the shared-computation rule ──────────────────────────────────────────────
def test_whole_image_encoded_once_for_many_regions():
    enc = FakeEncoder()
    post = _post([_region("a", 10, 40, 10, 50), _region("b", 50, 80, 60, 100),
                  _region("c", 20, 35, 80, 110)])
    out = _run(post, enc, persist=False)
    assert out["status"] == "ready"
    assert out["whole_image_encodes"] == 1 and enc.n_encode_image == 1   # NOT once-per-region
    assert enc.n_pool == 3                                               # identity via pooling
    assert enc.n_crop == 3                                               # context via crop
    roles = [r["role"] for r in out["records"]]
    assert roles.count("whole_image") == 1 and roles.count("identity") == 3 and roles.count("context") == 3
    routes = {r["role"]: r["route"] for r in out["records"] if r["role"] != "whole_image"}
    assert routes["identity"] == "mask_pool" and routes["context"] == "crop_cls"


def test_whole_image_role_uses_cls_route():
    out = _run(_post([_region("a", 10, 40, 10, 50)]), FakeEncoder(), persist=False)
    whole = [r for r in out["records"] if r["role"] == "whole_image"][0]
    assert whole["region_id"] == ees.WHOLE_REGION_ID and whole["route"] == "whole_cls"


# ── deterministic + distinct region vectors ──────────────────────────────────
def test_region_vectors_deterministic_and_distinct(store):
    post = _post([_region("a", 10, 40, 10, 50), _region("b", 50, 85, 55, 115)])  # different areas
    _run(post, FakeEncoder(), persist=True)
    va = (store_get(store, "emb_dinov2_vits14_identity_pX_a"))["vector"]
    vb = (store_get(store, "emb_dinov2_vits14_identity_pX_b"))["vector"]
    assert va != vb                                                     # distinct masks → distinct vectors
    # a second run reproduces the same vectors (deterministic)
    _run(post, FakeEncoder(), persist=True)
    assert store_get(store, "emb_dinov2_vits14_identity_pX_a")["vector"] == va


def store_get(store, eid):
    return next(d for d in store.docs if d["embedding_id"] == eid)


# ── routes: box-legacy and sub-patch fall back to crop encoding ──────────────
def test_box_only_region_falls_back_to_crop():
    post = _post([{"id": "boxy", "box": {"x": 0.2, "y": 0.2, "w": 0.3, "h": 0.3}}])
    out = _run(post, FakeEncoder(), persist=False)
    ident = [r for r in out["records"] if r["role"] == "identity"][0]
    assert ident["route"] == "crop_cls"                                # no mask to pool


def test_subpatch_mask_falls_back_to_crop():
    enc = FakeEncoder()
    post = _post([_region("tiny", 10, 11, 10, 12)])                    # area 2 < 4 → pool None
    out = _run(post, enc, persist=False)
    ident = [r for r in out["records"] if r["role"] == "identity"][0]
    assert ident["route"] == "crop_cls" and enc.n_crop >= 1


# ── spaces + persistence + provenance ────────────────────────────────────────
def test_roles_live_in_separate_spaces_and_carry_provenance(store):
    _run(_post([_region("a", 10, 40, 10, 50)]), FakeEncoder(), persist=True)
    ident = store_get(store, "emb_dinov2_vits14_identity_pX_a")
    ctx = store_get(store, "emb_dinov2_vits14_context_pX_a")
    assert ident["space"] != ctx["space"]                              # identity vs context never mixed
    assert ident["role"] == "identity" and ident["route"] == "mask_pool"
    assert ident["source_content_hash"] and ident["mask_hash"] and ident["dim"] == 8
    assert ident["checkpoint"] == "fake-ckpt" and ident["preprocessing_version"] == "dino-v1"


def test_unavailable_encoder_is_explicit():
    out = _run(_post([_region("a", 10, 40, 10, 50)]), FakeEncoder(available=False), persist=False)
    assert out["status"] == "unavailable" and out["records"] == [] and out["whole_image_encodes"] == 0
