"""
Anuraṇana taste map (Layer-4 data-viz) — Phase 1 backend.

Proves the one new capability (a cached, versioned numpy-PCA 2D projection) and the
map read model honour the invariants:
  · the projection is DETERMINISTIC and order-independent (sorted by embedding_id);
  · ONE SPACE PER MAP — a projection built for the fashion space never ingests a
    vector from another space (E0);
  · coverage is reported honestly as {embedded, total} — never fabricated;
  · the endpoint payload has the agreed shape (points + region metadata + crop
    thumbs + the evidence disclaimer), caps by `limit`, and carries no vectors;
  · the cache rebuilds when coverage grows;
  · the backfill is honest under absence (no encoder → embeds nothing).

Runs entirely on in-memory fake collections (no Mongo, no network, no GPU). Async
service calls are driven with `asyncio.run`, matching this repo's test convention
(no pytest-asyncio).
"""
import asyncio

import numpy as np
import pytest
from bson import ObjectId

from backend.services import region_embedding_service as res
from backend.services import taste_map_service as tm

FASHION_SPACE = res.space_key("fashion-clip", "fashion", "vitb32", 512)
OTHER_SPACE = res.space_key("dinov2_vits14", "identity", "dino-v1", 384)


# ── in-memory async stand-ins ────────────────────────────────────────────────
def _match(doc, filt):
    for k, v in filt.items():
        dv = doc.get(k)
        if isinstance(v, dict) and "$in" in v:
            if dv not in v["$in"]:
                return False
        elif isinstance(v, dict):
            continue  # other operators unused by these paths → treat as match-all
        elif dv != v:
            return False
    return True


class _Cursor:
    def __init__(self, docs):
        self._docs = docs
    def limit(self, n):
        self._docs = self._docs[:n]
        return self
    def __aiter__(self):
        self._it = iter(self._docs)
        return self
    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = [dict(d) for d in (docs or [])]
    async def create_index(self, *a, **k):
        return "ok"
    def find(self, filt=None, projection=None):
        filt = filt or {}
        return _Cursor([dict(d) for d in self.docs if _match(d, filt)])
    async def find_one(self, filt, projection=None):
        for d in self.docs:
            if _match(d, filt):
                return {k: v for k, v in d.items() if k != "_id"}
        return None
    async def count_documents(self, filt):
        return sum(1 for d in self.docs if _match(d, filt))
    async def delete_many(self, filt):
        before = len(self.docs)
        self.docs = [d for d in self.docs if not _match(d, filt)]
        return before - len(self.docs)
    async def insert_many(self, rows):
        self.docs.extend(dict(r) for r in rows)
    async def update_one(self, filt, update, upsert=False):
        for d in self.docs:
            if _match(d, filt):
                d.update(update.get("$set", {}))
                return
        if upsert:
            d = dict(update.get("$setOnInsert", {}))
            d.update(update.get("$set", {}))
            self.docs.append(d)


def _emb(eid, post_id, region_id, vector, space=FASHION_SPACE):
    return {"embedding_id": eid, "post_id": post_id, "region_id": region_id,
            "vector": vector, "space": space, "dim": len(vector)}


def _post(oid, regions):
    return {"_id": oid, "region_annotations": regions}


# ── PCA: determinism, order-independence, degenerate inputs ───────────────────
def test_pca_2d_shape_and_reproducible():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(12, 8)).tolist()
    a = tm.pca_2d(X)
    b = tm.pca_2d(X)
    assert a.shape == (12, 2)
    assert np.array_equal(a, b)                     # deterministic, sign-fixed
    assert float(np.max(np.abs(a))) <= 1.0 + 1e-9   # scaled to ~[-1, 1]


def test_pca_2d_degenerate():
    assert tm.pca_2d([]).shape == (0, 2)
    assert tm.pca_2d([[1.0, 2.0, 3.0]]).shape == (1, 2)
    assert np.array_equal(tm.pca_2d([[1.0, 2.0, 3.0]]), np.zeros((1, 2)))


def test_pca_sign_is_pinned():
    # The flip removes SVD's sign ambiguity → two runs on the same data are equal.
    X = [[2.0, 0.0], [-2.0, 0.0], [0.0, 1.0], [0.0, -1.0]]
    assert np.array_equal(tm.pca_2d(X), tm.pca_2d(X))


def test_projection_is_order_independent():
    """Same vectors inserted in different orders → identical coordinates per
    embedding_id (the service sorts by embedding_id before projecting)."""
    vecs = {
        "e1": [1.0, 0.0, 0.0, 0.5],
        "e2": [0.0, 1.0, 0.0, 0.2],
        "e3": [0.0, 0.0, 1.0, 0.9],
        "e4": [0.5, 0.5, 0.5, 0.1],
    }
    forward = FakeCollection([_emb(k, "p", k, v) for k, v in vecs.items()])
    reverse = FakeCollection([_emb(k, "p", k, v) for k, v in reversed(list(vecs.items()))])
    pf, pr = FakeCollection(), FakeCollection()
    asyncio.run(tm.build_projection("fashion", embeddings=forward, projections=pf))
    asyncio.run(tm.build_projection("fashion", embeddings=reverse, projections=pr))
    cf = {d["embedding_id"]: (d["x"], d["y"]) for d in pf.docs}
    cr = {d["embedding_id"]: (d["x"], d["y"]) for d in pr.docs}
    assert cf.keys() == cr.keys() == vecs.keys()
    for k in vecs:
        assert cf[k] == pytest.approx(cr[k], abs=1e-9)


# ── One space per map (E0) ────────────────────────────────────────────────────
def test_projection_never_mixes_spaces():
    emb = FakeCollection([
        _emb("f1", "p1", "r1", [1.0, 0.0, 0.0]),
        _emb("f2", "p1", "r2", [0.0, 1.0, 0.0]),
        _emb("f3", "p2", "r3", [0.0, 0.0, 1.0]),
        # a foreign-space vector that must NEVER enter the fashion projection
        _emb("d1", "p3", "r9", [9.0, 9.0, 9.0], space=OTHER_SPACE),
    ])
    proj = FakeCollection()
    out = asyncio.run(tm.build_projection("fashion", embeddings=emb, projections=proj))
    assert out["count"] == 3
    assert out["space_id"] == FASHION_SPACE
    assert {d["embedding_id"] for d in proj.docs} == {"f1", "f2", "f3"}
    assert all(d["space"] == FASHION_SPACE for d in proj.docs)


# ── Coverage reporting (honest denominator) ──────────────────────────────────
def test_coverage_reports_embedded_and_total():
    emb = FakeCollection([
        _emb("f1", "p1", "r1", [1.0, 0.0]),
        _emb("f2", "p1", "r2", [0.0, 1.0]),
    ])
    posts = FakeCollection([
        _post(ObjectId(), [{"id": "r1"}, {"id": "r2"}, {"id": "r3"}]),  # 3 dissected
        _post(ObjectId(), [{"id": "r4"}, {"id": None}]),                # 1 valid
    ])
    cov = asyncio.run(tm.coverage(FASHION_SPACE, embeddings=emb, posts=posts))
    assert cov == {"embedded": 2, "total": 4}


# ── Endpoint read model (shape, hydration, cap, evidence note) ───────────────
def test_get_map_shape_and_hydration():
    oid1, oid2 = ObjectId(), ObjectId()
    p1, p2 = str(oid1), str(oid2)
    emb = FakeCollection([
        _emb("f1", p1, "r1", [1.0, 0.0, 0.0]),
        _emb("f2", p1, "r2", [0.0, 1.0, 0.0]),
        _emb("f3", p2, "r3", [0.0, 0.0, 1.0]),
    ])
    posts = FakeCollection([
        _post(oid1, [
            {"id": "r1", "label": "silk collar", "category": "garment", "actor": "designer", "prioritised": True},
            {"id": "r2", "label": "hem", "category": "garment", "actor": "model"},
        ]),
        _post(oid2, [{"id": "r3", "category": "texture"}]),  # no label → falls back
    ])
    proj = FakeCollection()
    out = asyncio.run(tm.get_map("fashion", color_by="category", limit=100,
                                 embeddings=emb, projections=proj, posts=posts))

    assert set(out) >= {"space", "space_id", "projection_version", "count",
                        "coverage", "color_by", "evidence_note", "points"}
    assert out["space_id"] == FASHION_SPACE
    assert out["projection_version"] == tm.PROJECTION_VERSION
    assert out["count"] == 3
    assert out["coverage"] == {"embedded": 3, "total": 3}
    assert "research evidence" in out["evidence_note"].lower()

    by_region = {p["region_id"]: p for p in out["points"]}
    assert by_region["r1"]["label"] == "silk collar"
    assert by_region["r1"]["prioritised"] is True
    assert by_region["r1"]["thumb"] == f"/api/v1/posts/{p1}/regions/r1/crop?role=identity"
    assert by_region["r3"]["label"] == "texture"          # label←category fallback
    assert by_region["r2"]["prioritised"] is False
    for pt in out["points"]:                              # payload is light — no vectors
        assert "vector" not in pt
        assert -1.0 - 1e-9 <= pt["x"] <= 1.0 + 1e-9


def test_get_map_caps_by_limit():
    emb = FakeCollection([_emb(f"f{i}", "p", f"r{i}", [float(i), 1.0, 0.0]) for i in range(10)])
    out = asyncio.run(tm.get_map("fashion", limit=4, embeddings=emb,
                                 projections=FakeCollection(), posts=FakeCollection()))
    assert out["count"] == 4
    assert len(out["points"]) == 4


def test_unknown_space_rejected():
    assert tm.resolve_space_id("no-such-space") is None
    with pytest.raises(ValueError):
        asyncio.run(tm.get_map("no-such-space", embeddings=FakeCollection(),
                               projections=FakeCollection(), posts=FakeCollection()))


# ── Cache rebuilds when coverage grows ───────────────────────────────────────
def test_projection_rebuilds_on_growth():
    emb = FakeCollection([
        _emb("f1", "p1", "r1", [1.0, 0.0, 0.0]),
        _emb("f2", "p1", "r2", [0.0, 1.0, 0.0]),
    ])
    proj = FakeCollection()
    first = asyncio.run(tm.get_or_build_projection("fashion", embeddings=emb, projections=proj))
    assert len(first) == 2
    # a new region gets embedded → the cached projection is now stale
    emb.docs.append(_emb("f3", "p2", "r3", [0.0, 0.0, 1.0]))
    second = asyncio.run(tm.get_or_build_projection("fashion", embeddings=emb, projections=proj))
    assert len(second) == 3
    assert {d["embedding_id"] for d in proj.docs} == {"f1", "f2", "f3"}


# ── Backfill is honest under absence / present with an encoder ────────────────
def test_ensure_coverage_honest_without_encoder(monkeypatch):
    emb = FakeCollection()
    posts = [_post(ObjectId(), [{"id": "r1"}, {"id": "r2"}])]

    async def _never_fetch(post):  # must not even be reached when unavailable
        raise AssertionError("fetch_image called though encoder unavailable")

    monkeypatch.setattr("backend.services.fashion_clip_service.is_available", lambda: False)
    out = asyncio.run(tm.ensure_coverage(posts, fetch_image=_never_fetch, fashion=None,
                                         space_name="fashion", embeddings=emb))
    assert out["available"] is False
    assert out["total"] == 2
    assert out["newly_embedded"] == 0
    assert out["embedded"] == 0


def test_ensure_coverage_embeds_missing_with_encoder(monkeypatch):
    emb = FakeCollection()
    monkeypatch.setattr(res, "region_embeddings_collection", emb, raising=False)

    oid = ObjectId()
    posts = [_post(oid, [{"id": "r1"}, {"id": "r2"}])]

    async def _fetch(post):
        return b"imgbytes"

    from backend.services import evidence_embedding_service as ees

    async def _fake_embed(post, region, image_bytes, *, fashion=None, persist=True):
        eid = res.make_embedding_id(str(post["_id"]), str(region["id"]),
                                    model=ees.FASHION_MODEL, role="fashion")
        await emb.update_one({"embedding_id": eid},
                             {"$set": _emb(eid, str(post["_id"]), str(region["id"]), [1.0, 0.0])},
                             upsert=True)
        return {"status": "ready", "embedding_id": eid, "dim": 2}

    monkeypatch.setattr(ees, "embed_fashion_region", _fake_embed)

    sentinel_encoder = object()  # non-None → treated as available
    out = asyncio.run(tm.ensure_coverage(posts, fetch_image=_fetch, fashion=sentinel_encoder,
                                         space_name="fashion", embeddings=emb))
    assert out["available"] is True
    assert out["total"] == 2
    assert out["newly_embedded"] == 2
    assert out["embedded"] == 2
