"""
VISION-E · E0 — embedding contract + sidecar store.

Proves the ONE store holds versioned evidence projections safely: legacy FashionCLIP rows
stay readable (additive migration); comparisons are impossible across model/version spaces;
a semantic label edit never invalidates a visual embedding while geometry/source/mask/model
changes do. Runs on an in-memory fake collection (no Mongo, no network).
"""
import asyncio

import pytest

from backend.services import region_embedding_service as res


# ── in-memory async stand-in for region_embeddings_collection ────────────────
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
    def __aiter__(self):
        self._it = iter(self._docs)
        return self
    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class _FakeCollection:
    def __init__(self): self.docs = []
    async def create_index(self, *a, **k): return "ok"
    async def update_one(self, filt, update, upsert=False):
        for d in self.docs:
            if _match(d, filt):
                d.update(update.get("$set", {}))
                return
        if upsert:
            d = dict(update.get("$setOnInsert", {})); d.update(update.get("$set", {}))
            self.docs.append(d)
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


# ── ids, spaces, hashing ─────────────────────────────────────────────────────
def test_embedding_id_is_legacy_stable_and_role_distinct():
    # legacy (no role) is byte-identical to the original scheme — existing rows untouched
    assert res.make_embedding_id("p1", "seg_0") == "emb_fashion-clip_p1_seg_0"
    # a role yields a distinct id, so identity & context never collide on one region
    a = res.make_embedding_id("p1", "seg_0", model="dinov2_vits14", role="identity")
    b = res.make_embedding_id("p1", "seg_0", model="dinov2_vits14", role="context")
    assert a != b and a.endswith("identity_p1_seg_0") and b.endswith("context_p1_seg_0")


def test_cosine_refuses_cross_space():
    dino = res.space_key("dinov2_vits14", "identity", "dino-v1", 384)
    fash = res.space_key("fashion-clip", None, "vitb32", 512)
    assert not res.spaces_comparable(dino, fash)
    # same space compares fine…
    assert res.cosine_same_space([1.0, 0.0], dino, [1.0, 0.0], dino) == pytest.approx(1.0)
    # …different spaces RAISE, they never silently return a number
    with pytest.raises(ValueError):
        res.cosine_same_space([1.0, 0.0, 0.0], dino, [1.0, 0.0], fash)


# ── invalidation contract: labels don't, geometry/source/mask/model do ───────
def test_label_edit_does_not_invalidate_but_evidence_change_does():
    rec = {"geometry_rev": 3, "source_content_hash": "src1", "mask_hash": "m1",
           "model": "dinov2_vits14", "preprocessing_version": "dino-v1"}
    # a semantic label/note edit changes none of the evidence axes → NOT stale
    stale, reason = res.is_stale(rec, geometry_rev=3, source_content_hash="src1",
                                 mask_hash="m1", model="dinov2_vits14",
                                 preprocessing_version="dino-v1")
    assert stale is False and reason == ""
    # each evidence axis, changed, invalidates with a named reason
    assert res.is_stale(rec, geometry_rev=4)[0] and res.is_stale(rec, geometry_rev=4)[1] == "geometry_rev"
    assert res.is_stale(rec, mask_hash="m2")[1] == "mask"
    assert res.is_stale(rec, source_content_hash="src2")[1] == "source"
    assert res.is_stale(rec, model="openclip")[1] == "model"
    assert res.is_stale(rec, preprocessing_version="dino-v2")[1] == "preprocessing"


def test_mask_hash_ignores_nothing_but_the_mask():
    m1 = res.mask_hash({"size": [4, 4], "counts": [2, 2, 12]})
    m1b = res.mask_hash({"size": [4, 4], "counts": [2, 2, 12]})
    m2 = res.mask_hash({"size": [4, 4], "counts": [3, 2, 11]})
    assert m1 == m1b and m1 != m2 and res.mask_hash(None) == ""


# ── store round-trip + additive migration + mixed-space rejection ────────────
def test_upsert_writes_full_versioned_record(store):
    async def go():
        eid = res.make_embedding_id("p1", "seg_0", model="dinov2_vits14", role="identity")
        await res.upsert_embedding(eid, [0.1] * 384, model="dinov2_vits14", post_id="p1",
                                   region_id="seg_0", role="identity", geometry_rev=2,
                                   checkpoint="facebook/dinov2-small", preprocessing_version="dino-v1",
                                   crop_version="crop-v1", source_content_hash="src1", mask_hash="m1")
        return await res.get_embedding(eid)
    rec = asyncio.run(go())
    assert rec["role"] == "identity" and rec["dim"] == 384 and rec["geometry_rev"] == 2
    assert rec["space"] == res.space_key("dinov2_vits14", "identity", "dino-v1", 384)
    assert rec["source_content_hash"] == "src1" and rec["mask_hash"] == "m1"
    assert rec["storage"] == "inline" and rec["status"] == "ready" and rec["created_at"]


def test_legacy_row_stays_readable_and_queryable(store):
    async def go():
        # a legacy FashionCLIP row: only the ORIGINAL fields, written the old way
        store.docs.append({"embedding_id": "emb_fashion-clip_p1_seg_0", "vector": [1.0, 0.0] + [0.0] * 510,
                           "model": "fashion-clip", "dim": 512, "post_id": "p1", "region_id": "seg_0"})
        got = await res.get_embedding("emb_fashion-clip_p1_seg_0")
        hits = await res.search_similar([1.0, 0.0] + [0.0] * 510, post_ids=["p1"],
                                        model="fashion-clip")   # legacy model-scoped path
        return got, hits
    got, hits = asyncio.run(go())
    assert got is not None and got["model"] == "fashion-clip"        # still readable
    assert hits and hits[0]["region_id"] == "seg_0"                  # still queryable


def test_mixed_space_search_never_crosses_spaces(store):
    async def go():
        # a 512-d fashion vector (legacy path) and a 384-d dino identity vector (spaced) coexist
        await res.upsert_embedding("emb_fashion-clip_pA_r0", [1.0] + [0.0] * 511, model="fashion-clip",
                                   post_id="pA", region_id="r0")
        await res.upsert_embedding(res.make_embedding_id("pB", "r0", "dinov2_vits14", "identity"),
                                   [1.0] + [0.0] * 383, model="dinov2_vits14", post_id="pB",
                                   region_id="r0", role="identity", preprocessing_version="dino-v1")
        dino_space = res.space_key("dinov2_vits14", "identity", "dino-v1", 384)
        dino_hits = await res.search_similar([1.0] + [0.0] * 383, post_ids=["pA", "pB"], space=dino_space)
        fash_hits = await res.search_similar([1.0] + [0.0] * 511, post_ids=["pA", "pB"], model="fashion-clip")
        return dino_hits, fash_hits
    dino_hits, fash_hits = asyncio.run(go())
    # the dino query sees ONLY the dino vector; the fashion query sees ONLY the fashion vector
    assert [h["post_id"] for h in dino_hits] == ["pB"]
    assert [h["post_id"] for h in fash_hits] == ["pA"]
