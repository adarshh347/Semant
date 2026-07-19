"""
VISION-E · E3 — retrieval spaces + query routing (DINOv2 / FashionCLIP / OpenCLIP-deferred).

Proves the router picks the correct space per query, absent models produce explicit unavailable
states (never a silent empty), FashionCLIP is activated for fashion evidence in its OWN space,
and no cross-space cosine is possible in code — a fashion query never touches a visual vector.
"""
import asyncio
import io

import numpy as np
import pytest
from PIL import Image

from backend.services import retrieval_service as rs
from backend.services import region_embedding_service as res
from backend.services import evidence_embedding_service as ees
from backend.services import mask_geometry as mg


# ── fake async store (reused shape) ──────────────────────────────────────────
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


@pytest.fixture()
def store(monkeypatch):
    fake = _FakeCollection()
    monkeypatch.setattr(res, "region_embeddings_collection", fake)
    return fake


@pytest.fixture()
def avail(monkeypatch):
    # deterministic availability: DINOv2 + FashionCLIP on, OpenCLIP deferred off
    monkeypatch.setattr(rs, "_dino_available", lambda: True)
    monkeypatch.setattr(rs, "_fashion_available", lambda: True)
    monkeypatch.setattr(rs, "_openclip_available", lambda: False)


# ── routing ──────────────────────────────────────────────────────────────────
def test_route_evidence_defaults_to_visual_identity(avail):
    r = rs.route(query_kind="evidence")
    assert r["space"] == "visual_identity" and r["available"] is True


def test_route_context_sensitive_uses_visual_context(avail):
    assert rs.route(query_kind="evidence", context_sensitive=True)["space"] == "visual_context"


def test_route_fashion_domain_uses_fashion_space(avail):
    assert rs.route(query_kind="evidence", domain="fashion")["space"] == "fashion"
    assert rs.route(query_kind="text", domain="fashion")["space"] == "fashion"


def test_route_general_text_is_openclip_and_deferred(avail):
    r = rs.route(query_kind="text")
    assert r["space"] == "text_image" and r["available"] is False
    assert "OpenCLIP" in r["reason"] and "E4" in r["reason"]      # honest deferral, not silent


# ── availability surfaced ────────────────────────────────────────────────────
def test_list_spaces_reflects_availability(avail):
    spaces = {s["name"]: s for s in rs.list_spaces()}
    assert spaces["visual_identity"]["available"] and spaces["fashion"]["available"]
    assert spaces["text_image"]["available"] is False and spaces["text_image"]["reason"]


def test_find_similar_unavailable_space_is_explicit(avail, store):
    out = asyncio.run(rs.find_similar([0.1] * 4, space="text_image", post_ids=["p1"]))
    assert out["status"] == "unavailable" and out["results"] == [] and out["reason"]


# ── no cross-space comparison possible in code ───────────────────────────────
def test_fashion_query_never_touches_visual_vectors(avail, store):
    async def go():
        # one DINOv2 identity vector (384) and one FashionCLIP vector (512) on the same post
        await res.upsert_embedding(res.make_embedding_id("p1", "r0", "dinov2_vits14", "identity"),
                                   [1.0] + [0.0] * 383, model="dinov2_vits14", post_id="p1",
                                   region_id="r0", role="identity", preprocessing_version="dino-v1")
        await res.upsert_embedding(res.make_embedding_id("p1", "r0", "fashion-clip", "fashion"),
                                   [1.0] + [0.0] * 511, model="fashion-clip", post_id="p1",
                                   region_id="r0", role="fashion", preprocessing_version="vitb32")
        fash = await rs.find_similar([1.0] + [0.0] * 511, space="fashion", post_ids=["p1"])
        vis = await rs.find_similar([1.0] + [0.0] * 383, space="visual_identity", post_ids=["p1"])
        return fash, vis
    fash, vis = asyncio.run(go())
    assert fash["status"] == "ready" and len(fash["results"]) == 1     # only the fashion vector
    assert vis["status"] == "ready" and len(vis["results"]) == 1       # only the dino vector
    # the underlying comparator refuses a cross-space pairing outright
    with pytest.raises(ValueError):
        res.cosine_same_space([1.0], rs.space_id("fashion"), [1.0], rs.space_id("visual_identity"))


# ── FashionCLIP activation writes into the fashion space ─────────────────────
class _FakeFashion:
    def is_available(self): return True
    def embed_image(self, image): return [1.0] + [0.0] * 511      # 512-d, already L2


def test_embed_fashion_region_uses_its_own_space(avail, store):
    buf = io.BytesIO(); Image.new("RGB", (100, 80), (200, 30, 60)).save(buf, "PNG")
    b = np.zeros((80, 100), np.uint8); b[20:60, 30:70] = 1
    region = {"id": "garment_0", "mask_rle": mg.rle_encode_mask(b)}
    mg.canonicalize_geometry(region, provenance={"adapter": "t"})
    out = asyncio.run(ees.embed_fashion_region({"_id": "pF"}, region, buf.getvalue(),
                                               fashion=_FakeFashion(), persist=True))
    assert out["status"] == "ready" and out["dim"] == 512
    assert out["space"] == res.space_key("fashion-clip", "fashion", "vitb32", 512)
    stored = next(d for d in store.docs if d["region_id"] == "garment_0")
    assert stored["role"] == "fashion" and stored["model"] == "fashion-clip"
    # a fashion vector is never in a DINOv2 space
    assert stored["space"] != res.space_key("dinov2_vits14", "identity", "dino-v1", 384)


def test_embed_fashion_region_unavailable_is_explicit():
    class _Off:
        def is_available(self): return False
    out = asyncio.run(ees.embed_fashion_region({"_id": "pF"}, {"id": "r"}, b"x",
                                               fashion=_Off(), persist=False))
    assert out["status"] == "unavailable"
