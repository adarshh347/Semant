"""
ATLAS lifecycle — rename, archive, restore, duplicate. And the one thing there is not: a delete.

An Atlas is an ARRANGEMENT over evidence that lives elsewhere. Every gesture here has to leave
that evidence alone, and every one of them has to leave the Atlas able to say where it came from.

  rename touches the title and nothing else                      → §1
  archive takes a canvas off the shelf and keeps its provenance  → §2
  duplicate references the same evidence; it copies no judgement → §3
  the routes, and what they refuse                               → §4
  nothing on this path writes to a post                          → §5

Every fixture is SYNTHETIC.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json as _json

import pytest

from backend.services import atlas_service as A
from backend.services import corpus_store as C


# ── a fake collection that honours the one query the lifecycle needs ─────────

class _UpdateResult:
    def __init__(self, matched, modified):
        self.matched_count = matched
        self.modified_count = modified


class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *_a, **_k):
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __aiter__(self):
        async def gen():
            for d in self._docs:
                yield d
        return gen()


def _matches(doc, query):
    for k, v in (query or {}).items():
        if isinstance(v, dict) and "$ne" in v:
            if doc.get(k) == v["$ne"]:
                return False
        elif doc.get(k) != v:
            return False
    return True


class FakeCollection:
    def __init__(self):
        self.docs = {}

    async def insert_one(self, doc):
        self.docs[doc["_id"]] = copy.deepcopy(doc)
        return type("R", (), {"inserted_id": doc["_id"]})()

    async def find_one(self, query, projection=None):
        for d in self.docs.values():
            if _matches(d, query):
                return copy.deepcopy(d)
        return None

    def find(self, query=None, projection=None):
        return _Cursor([copy.deepcopy(d) for d in self.docs.values() if _matches(d, query)])

    async def update_one(self, query, update, upsert=False):
        for d in self.docs.values():
            if _matches(d, query):
                d.update(update.get("$set", {}))
                return _UpdateResult(1, 1)
        return _UpdateResult(0, 0)

    async def delete_one(self, query):
        for k, d in list(self.docs.items()):
            if _matches(d, query):
                del self.docs[k]
                return type("R", (), {"deleted_count": 1})()
        return type("R", (), {"deleted_count": 0})()


def a_post(post_id):
    return {"_id": post_id, "photo_url": "https://example.invalid/i.jpg",
            "instagram_handle": f"handle_{post_id}", "grounds": [], "visual_marks": [],
            "region_annotations": [], "percepts": []}


def run(coro):
    return asyncio.run(coro)


def _seeded():
    coll = FakeCollection()
    doc = run(A.create_atlas(
        corpus_ref={"kind": A.CORPUS_CURATED, "corpus_id": "corpus_w", "post_ids": ["p3", "p1"]},
        post_ids=["p3", "p1"], title="the approach", collection=coll))
    return coll, doc


# ── 1. rename ────────────────────────────────────────────────────────────────

def test_rename_changes_the_title_and_nothing_else():
    coll, doc = _seeded()
    run(A.save_arrangement(doc["_id"], [{"node_id": "n1", "x": 99.0}], collection=coll))
    before = run(A.get_atlas(doc["_id"], collection=coll))

    out = run(A.rename_atlas(doc["_id"], "the approach, revisited", collection=coll))
    after = run(A.get_atlas(doc["_id"], collection=coll))

    assert out["title"] == after["title"] == "the approach, revisited"
    assert after["nodes"] == before["nodes"]
    assert after["corpus_ref"] == before["corpus_ref"]
    assert after["updated_at"] >= before["updated_at"]


def test_renaming_an_atlas_that_does_not_exist_is_a_miss_not_a_new_one():
    coll = FakeCollection()
    assert run(A.rename_atlas("atlas_nope", "x", collection=coll)) is None
    assert coll.docs == {}


# ── 2. archive ───────────────────────────────────────────────────────────────

def test_an_archived_atlas_leaves_the_shelf_but_not_the_record():
    coll, doc = _seeded()
    run(A.set_archived(doc["_id"], True, collection=coll))

    assert [d["_id"] for d in run(A.list_atlases(collection=coll))] == []
    listed = run(A.list_atlases(include_archived=True, collection=coll))
    assert [d["_id"] for d in listed] == [doc["_id"]]
    # Still readable, still knows where it came from.
    kept = run(A.get_atlas(doc["_id"], collection=coll))
    assert kept["archived"] is True
    assert kept["corpus_ref"]["kind"] == A.CORPUS_CURATED
    assert kept["corpus_ref"]["corpus_id"] == "corpus_w"
    assert [n["post_id"] for n in kept["nodes"]] == ["p3", "p1"]


def test_restoring_puts_it_back_exactly():
    coll, doc = _seeded()
    run(A.set_archived(doc["_id"], True, collection=coll))
    run(A.set_archived(doc["_id"], False, collection=coll))
    assert [d["_id"] for d in run(A.list_atlases(collection=coll))] == [doc["_id"]]


def test_an_atlas_never_archived_is_listed_as_before():
    """The `$ne` query, not `archived == False`: documents written before this field existed
    carry no `archived` key at all and must not vanish from the shelf."""
    coll, doc = _seeded()
    assert "archived" not in coll.docs[doc["_id"]]
    assert [d["_id"] for d in run(A.list_atlases(collection=coll))] == [doc["_id"]]


# ── 3. duplicate ─────────────────────────────────────────────────────────────

def _judged(coll, doc):
    """An Atlas with every kind of judgement on it: a moved node, a note, an edge, a plan, a draft."""
    run(A.save_arrangement(doc["_id"], [{"node_id": "n1", "x": 321.0, "y": 12.0}], collection=coll))
    run(A.save_notes(doc["_id"], [{"node_id": "n0", "notes": [{"text": "why the stair"}]}],
                     collection=coll))
    run(A.add_edge(doc["_id"], {"edge_id": "e1", "from_node": "n0", "to_node": "n1",
                                "relation_id": "rel_1", "post_id": "p3"}, collection=coll))
    run(A.save_plan(doc["_id"], {"thesis": "t", "claims": []}, collection=coll))
    run(A.save_draft(doc["_id"], {"run_id": "r", "passages": []}, collection=coll))
    return run(A.get_atlas(doc["_id"], collection=coll))


def test_a_duplicate_references_the_same_evidence_and_keeps_the_arrangement():
    coll, doc = _seeded()
    source = _judged(coll, doc)
    copy_ = run(A.duplicate_atlas(doc["_id"], collection=coll))

    assert copy_["_id"] != source["_id"]
    assert copy_["duplicated_from"] == source["_id"]
    assert copy_["corpus_ref"] == source["corpus_ref"]
    assert [n["post_id"] for n in copy_["nodes"]] == [n["post_id"] for n in source["nodes"]]
    assert copy_["nodes"][1]["x"] == 321.0                       # the arrangement travels
    assert copy_["nodes"][0]["notes"][0]["text"] == "why the stair"   # so do the author's notes
    assert copy_["title"] == source["title"]
    A.assert_no_percept_data(copy_)


def test_a_duplicate_copies_no_judgement():
    """The plan was accepted over THAT canvas, the draft is a quarantined suggestion, and an edge
    names a relation somebody committed. None of them is arrangement; none of them travels."""
    coll, doc = _seeded()
    _judged(coll, doc)
    copy_ = run(A.duplicate_atlas(doc["_id"], collection=coll))
    assert copy_["edges"] == []
    assert copy_["plan"] is None
    assert copy_["draft"] is None
    assert not copy_.get("archived")


def test_a_duplicate_can_be_given_its_own_title():
    coll, doc = _seeded()
    copy_ = run(A.duplicate_atlas(doc["_id"], title="another way round", collection=coll))
    assert copy_["title"] == "another way round"


def test_a_duplicate_is_independent_of_its_source():
    coll, doc = _seeded()
    copy_ = run(A.duplicate_atlas(doc["_id"], collection=coll))
    run(A.save_arrangement(copy_["_id"], [{"node_id": "n0", "x": 555.0}], collection=coll))
    run(A.set_archived(doc["_id"], True, collection=coll))

    assert run(A.get_atlas(doc["_id"], collection=coll))["nodes"][0]["x"] == 0.0
    assert not run(A.get_atlas(copy_["_id"], collection=coll)).get("archived")


def test_duplicating_nothing_is_a_miss():
    coll = FakeCollection()
    assert run(A.duplicate_atlas("atlas_nope", collection=coll)) is None
    assert coll.docs == {}


# ── 4. the routes ────────────────────────────────────────────────────────────

@pytest.fixture
def wired(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import backend.database as db
    import backend.routers.atlas as AtlasRouter
    import backend.routers.corpora as CorporaRouter

    corpora, atlases, posts = FakeCollection(), FakeCollection(), FakeCollection()
    monkeypatch.setattr(db, "corpus_collection", corpora, raising=False)
    monkeypatch.setattr(db, "atlas_collection", atlases, raising=False)
    monkeypatch.setattr(CorporaRouter, "post_collection", posts, raising=False)
    monkeypatch.setattr(AtlasRouter, "post_collection", posts, raising=False)
    for pid in ("p1", "p2", "p3"):
        posts.docs[pid] = a_post(pid)

    app = FastAPI()
    app.include_router(CorporaRouter.router, prefix="/api/v1/corpora")
    app.include_router(AtlasRouter.router, prefix="/api/v1/atlas")
    return TestClient(app), posts


def _walk(client, order=("p3", "p1", "p2")):
    return client.post("/api/v1/corpora/", json={
        "title": "the approach", "images": [{"post_id": p} for p in order]}).json()["id"]


def test_route_opens_a_walk_from_its_id_alone(wired):
    """THE PROVEN DEFECT'S OTHER HALF. The browser sends `corpus_id` and NO post ids; the server
    resolves the walk once and stores both the provenance and the resolved order."""
    client, _ = wired
    cid = _walk(client)
    res = client.post("/api/v1/atlas/", json={"corpus_id": cid})
    assert res.status_code == 201
    body = res.json()
    assert body["corpus_ref"]["kind"] == A.CORPUS_CURATED
    assert body["corpus_ref"]["corpus_id"] == cid
    assert body["corpus_ref"]["post_ids"] == ["p3", "p1", "p2"]
    assert [n["post_id"] for n in body["nodes"]] == ["p3", "p1", "p2"]


def test_route_renames_and_archives_and_the_list_follows(wired):
    client, _ = wired
    aid = client.post("/api/v1/atlas/", json={"corpus_id": _walk(client)}).json()["id"]

    res = client.patch(f"/api/v1/atlas/{aid}", json={"title": "renamed"})
    assert res.status_code == 200 and res.json()["title"] == "renamed"

    res = client.patch(f"/api/v1/atlas/{aid}", json={"archived": True})
    assert res.json()["archived"] is True
    assert client.get("/api/v1/atlas/").json()["atlases"] == []
    listed = client.get("/api/v1/atlas/?include_archived=true").json()["atlases"]
    assert [a["id"] for a in listed] == [aid]
    assert listed[0]["title"] == "renamed"
    # Still readable by id — archived is not gone.
    assert client.get(f"/api/v1/atlas/{aid}").status_code == 200

    res = client.patch(f"/api/v1/atlas/{aid}", json={"archived": False})
    assert [a["id"] for a in client.get("/api/v1/atlas/").json()["atlases"]] == [aid]


def test_route_patch_cannot_touch_the_arrangement(wired):
    """The model is closed: a lifecycle patch that names nodes is a patch with its nodes dropped."""
    client, _ = wired
    aid = client.post("/api/v1/atlas/", json={"corpus_id": _walk(client)}).json()["id"]
    res = client.patch(f"/api/v1/atlas/{aid}",
                       json={"title": "t", "nodes": [{"node_id": "n0", "x": 999}],
                             "corpus_ref": {"kind": "posts", "post_ids": ["zz"]}})
    assert res.status_code == 200
    doc = client.get(f"/api/v1/atlas/{aid}").json()
    assert doc["nodes"][0]["x"] == 0.0
    assert doc["corpus_ref"]["kind"] == A.CORPUS_CURATED


def test_route_duplicates(wired):
    client, _ = wired
    cid = _walk(client)
    aid = client.post("/api/v1/atlas/", json={"corpus_id": cid}).json()["id"]
    res = client.post(f"/api/v1/atlas/{aid}/duplicate", json={})
    assert res.status_code == 201
    body = res.json()
    assert body["id"] != aid
    assert body["duplicated_from"] == aid
    assert body["corpus_ref"]["corpus_id"] == cid
    assert [n["post_id"] for n in body["nodes"]] == ["p3", "p1", "p2"]
    assert len(client.get("/api/v1/atlas/").json()["atlases"]) == 2


def test_route_refuses_what_is_not_there(wired):
    client, _ = wired
    assert client.patch("/api/v1/atlas/atlas_nope", json={"title": "x"}).status_code == 404
    assert client.post("/api/v1/atlas/atlas_nope/duplicate", json={}).status_code == 404


def test_there_is_no_delete_route_for_an_atlas(wired):
    """By design, and pinned so that adding one is a decision rather than a drift."""
    client, _ = wired
    aid = client.post("/api/v1/atlas/", json={"corpus_id": _walk(client)}).json()["id"]
    assert client.delete(f"/api/v1/atlas/{aid}").status_code == 405


# ── 5. data safety ───────────────────────────────────────────────────────────

def test_the_lifecycle_writes_to_no_post_and_to_no_corpus(wired):
    client, posts = wired
    cid = _walk(client)
    aid = client.post("/api/v1/atlas/", json={"corpus_id": cid}).json()["id"]
    fingerprint = lambda d: hashlib.sha256(  # noqa: E731
        _json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()
    before_posts = fingerprint(posts.docs)
    before_corpus = client.get(f"/api/v1/corpora/{cid}").json()

    client.patch(f"/api/v1/atlas/{aid}", json={"title": "x"})
    client.patch(f"/api/v1/atlas/{aid}", json={"archived": True})
    client.patch(f"/api/v1/atlas/{aid}", json={"archived": False})
    client.post(f"/api/v1/atlas/{aid}/duplicate", json={"title": "y"})

    assert fingerprint(posts.docs) == before_posts
    assert client.get(f"/api/v1/corpora/{cid}").json() == before_corpus


def test_deleting_the_walk_does_not_reach_an_atlas_or_a_post(wired):
    client, posts = wired
    cid = _walk(client)
    aid = client.post("/api/v1/atlas/", json={"corpus_id": cid}).json()["id"]
    before = copy.deepcopy(posts.docs)
    assert client.delete(f"/api/v1/corpora/{cid}").json()["deleted"] is True
    assert posts.docs == before
    atlas = client.get(f"/api/v1/atlas/{aid}").json()
    assert [n["post_id"] for n in atlas["nodes"]] == ["p3", "p1", "p2"]
    assert atlas["corpus_ref"]["corpus_id"] == cid        # provenance outlives the walk
