"""
ATLAS L1 — the curated corpus: a named, ordered walk that outlives the canvas built over it.

C1 refused to create this collection and gave the condition under which it would be worth having:
not "a fifth place a corpus can be defined, and the one that nothing else reads". So the property
this file pins hardest is that it IS read — an Atlas opens from it — and that everything else about
it stays as disciplined as the Atlas document.

  order is the argument, and only an explicit gesture changes it   → §1
  a corpus references posts and never copies them                  → §2
  the store round-trips; refusals travel with the change           → §3
  the routes, and the ONE that matters: an Atlas opened from a walk → §4

Every fixture is SYNTHETIC. No real post, no curator's text.
"""
from __future__ import annotations

import asyncio
import copy

import pytest

from backend.services import atlas_service as A
from backend.services import corpus_store as C


# ── fakes ────────────────────────────────────────────────────────────────────

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


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = dict(docs or {})

    async def insert_one(self, doc):
        self.docs[doc["_id"]] = copy.deepcopy(doc)
        return type("R", (), {"inserted_id": doc["_id"]})()

    async def find_one(self, query, projection=None):
        for d in self.docs.values():
            if all(d.get(k) == v for k, v in (query or {}).items()):
                return copy.deepcopy(d)
        return None

    def find(self, query=None, projection=None):
        return _Cursor([copy.deepcopy(d) for d in self.docs.values()])

    async def update_one(self, query, update, upsert=False):
        for d in self.docs.values():
            if all(d.get(k) == v for k, v in (query or {}).items()):
                d.update(update.get("$set", {}))
                return type("R", (), {"matched_count": 1, "modified_count": 1})()
        return type("R", (), {"matched_count": 0, "modified_count": 0})()

    async def delete_one(self, query):
        for k, d in list(self.docs.items()):
            if all(d.get(f) == v for f, v in (query or {}).items()):
                del self.docs[k]
                return type("R", (), {"deleted_count": 1})()
        return type("R", (), {"deleted_count": 0})()


def a_post(post_id, regions=0, marks=0):
    return {"_id": post_id, "photo_url": f"https://example.invalid/{post_id}.jpg",
            "instagram_handle": f"handle_{post_id}",
            "region_annotations": [{"id": f"r{i}"} for i in range(regions)],
            "visual_marks": [{"id": f"m{i}"} for i in range(marks)],
            "grounds": [], "percepts": []}


def run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


THE_WALK = [
    {"post_id": "p1", "note": "the Lustgarten — the building at its most public"},
    {"post_id": "p2", "note": "the colonnade, frontal"},
    {"post_id": "p3", "note": "oblique, into the portico"},
    {"post_id": "p4", "note": "the stair"},
    {"post_id": "p5", "note": "the rotunda"},
]


# ── 1. order is the argument ─────────────────────────────────────────────────

def test_the_order_given_is_the_order_kept():
    """M1: "the caller's sequence IS the argument, and renumbering it here would silently rewrite
    the claim." A corpus is the first place that sequence can survive being closed."""
    doc = C.new_corpus_doc(corpus_id="c1", images=THE_WALK)
    assert [i["post_id"] for i in doc["images"]] == ["p1", "p2", "p3", "p4", "p5"]
    assert [i["position"] for i in doc["images"]] == [0, 1, 2, 3, 4]


def test_positions_come_from_the_array_not_from_the_payload():
    """A client that sent `position` fields could disagree with the array it sent them in, and
    there would be no way to tell which it meant."""
    doc = C.new_corpus_doc(corpus_id="c1", images=[
        {"post_id": "p1", "position": 9}, {"post_id": "p2", "position": 0}])
    assert [(i["post_id"], i["position"]) for i in doc["images"]] == [("p1", 0), ("p2", 1)]


def test_the_same_photograph_twice_is_one_image():
    doc = C.new_corpus_doc(corpus_id="c1", images=["p1", "p2", "p1"])
    assert [i["post_id"] for i in doc["images"]] == ["p1", "p2"]


def test_an_entry_naming_no_image_is_dropped_not_kept_as_a_hole():
    """A blank entry is a typo, not a slot to fill later — and a hole in the sequence is something
    every downstream consumer would have to remember to skip."""
    doc = C.new_corpus_doc(corpus_id="c1", images=[{"post_id": ""}, "p1", {"note": "orphan"}])
    assert [i["post_id"] for i in doc["images"]] == ["p1"]


def test_a_reorder_moves_one_image_and_renumbers_the_rest():
    images = C.new_corpus_doc(corpus_id="c1", images=THE_WALK)["images"]
    moved, refused = C.reorder(images, "p4", 1)      # the stair, earlier
    assert refused is None
    assert [i["post_id"] for i in moved] == ["p1", "p4", "p2", "p3", "p5"]
    assert [i["position"] for i in moved] == [0, 1, 2, 3, 4]


def test_a_reorder_CANNOT_change_what_the_walk_contains():
    """The whole reason reordering is its own call. "I moved the stair earlier" and "I removed the
    rotunda" must not be able to look the same in the record."""
    images = C.new_corpus_doc(corpus_id="c1", images=THE_WALK)["images"]
    before = {i["post_id"] for i in images}
    moved, _ = C.reorder(images, "p5", 0)
    assert {i["post_id"] for i in moved} == before


def test_reordering_an_image_this_walk_does_not_hold_is_refused_by_name():
    images = C.new_corpus_doc(corpus_id="c1", images=THE_WALK)["images"]
    _, refused = C.reorder(images, "ghost", 0)
    assert refused["reason"] == C.REFUSED_UNKNOWN_IMAGE
    assert "ghost" in refused["detail"]


def test_a_position_outside_the_walk_is_refused():
    images = C.new_corpus_doc(corpus_id="c1", images=THE_WALK)["images"]
    _, refused = C.reorder(images, "p1", 99)
    assert refused["reason"] == C.REFUSED_OUT_OF_RANGE


def test_a_note_says_why_this_image_sits_here():
    """M1 built `CorpusImage.note` for exactly this and had nowhere to get one from: "a corpus that
    cannot say why the stair follows the colonnade is a folder"."""
    images = C.new_corpus_doc(corpus_id="c1", images=THE_WALK)["images"]
    noted, refused = C.with_note(images, "p4", "the turn the whole walk is built around")
    assert refused is None
    assert next(i for i in noted if i["post_id"] == "p4")["note"] \
        == "the turn the whole walk is built around"


def test_dropping_an_image_closes_the_gap():
    images = C.new_corpus_doc(corpus_id="c1", images=THE_WALK)["images"]
    left, refused = C.without_image(images, "p3")
    assert refused is None
    assert [i["position"] for i in left] == [0, 1, 2, 3]


def test_dropping_something_absent_is_refused_rather_than_ignored():
    """A client that thinks it removed something has to be told it did not."""
    images = C.new_corpus_doc(corpus_id="c1", images=THE_WALK)["images"]
    left, refused = C.without_image(images, "ghost")
    assert refused["reason"] == C.REFUSED_UNKNOWN_IMAGE
    assert len(left) == len(images)


# ── 2. references, never copies ──────────────────────────────────────────────

def test_a_corpus_holds_ids_and_order_and_nothing_else():
    doc = C.new_corpus_doc(corpus_id="c1", title="the walk", why="what it is for",
                           images=THE_WALK)
    assert set(doc) == {"_id", "contract_version", "title", "why", "images",
                        "created_at", "updated_at"}
    assert set(doc["images"][0]) == {"post_id", "position", "note"}


def test_an_entry_carrying_percept_data_is_refused():
    """The same discipline as the Atlas document. A cached `photo_url` goes stale the moment a post
    is re-uploaded, in a document that looks authoritative."""
    with pytest.raises(ValueError, match="carries percept data"):
        C.assert_no_percept_data({"images": [{"post_id": "p1", "photo_url": "http://x"}]})
    with pytest.raises(ValueError, match="carries percept data"):
        C.assert_no_percept_data({"images": [{"post_id": "p1", "visual_marks": []}]})


def test_a_walk_of_plain_references_passes_the_same_check():
    C.assert_no_percept_data(C.new_corpus_doc(corpus_id="c1", images=THE_WALK))


def test_post_ids_are_what_build_corpus_already_consumes():
    """The whole integration surface: M1 takes an ordered tuple of post ids and did before L1."""
    from backend.services.director.corpus import build_corpus
    doc = C.new_corpus_doc(corpus_id="c1", images=THE_WALK)
    corpus = build_corpus(corpus_id="c1", images=C.post_ids_of(doc))
    assert list(corpus.post_ids) == ["p1", "p2", "p3", "p4", "p5"]
    assert [i.position for i in corpus.images] == [0, 1, 2, 3, 4]


# ── 3. the store ─────────────────────────────────────────────────────────────

def test_the_corpus_round_trips():
    async def go():
        coll = FakeCollection()
        made = await C.create_corpus(title="the walk", why="the approach", images=THE_WALK,
                                     corpus_id="c1", collection=coll)
        again = await C.get_corpus("c1", collection=coll)
        assert again["title"] == "the walk"
        assert C.post_ids_of(again) == C.post_ids_of(made)
    run(go())


def test_saving_a_new_order_renumbers_and_keeps_membership():
    async def go():
        coll = FakeCollection()
        await C.create_corpus(images=THE_WALK, corpus_id="c1", collection=coll)
        doc = await C.get_corpus("c1", collection=coll)
        moved, _ = C.reorder(doc["images"], "p5", 0)
        saved = await C.save_images("c1", moved, collection=coll)
        assert C.post_ids_of(saved) == ["p5", "p1", "p2", "p3", "p4"]
        assert [i["position"] for i in saved["images"]] == [0, 1, 2, 3, 4]
    run(go())


def test_deleting_a_corpus_touches_no_post():
    async def go():
        corpora, posts = FakeCollection(), FakeCollection({"p1": a_post("p1")})
        await C.create_corpus(images=["p1"], corpus_id="c1", collection=corpora)
        assert await C.delete_corpus("c1", collection=corpora) is True
        assert await C.get_corpus("c1", collection=corpora) is None
        assert posts.docs["p1"]["_id"] == "p1"        # untouched
    run(go())


# ── 4. the routes, and the Atlas opened from a walk ──────────────────────────

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

    app = FastAPI()
    app.include_router(CorporaRouter.router, prefix="/api/v1/corpora")
    app.include_router(AtlasRouter.router, prefix="/api/v1/atlas")
    return TestClient(app), posts


def _seed(posts, ids):
    for n, pid in enumerate(ids):
        posts.docs[pid] = a_post(pid, regions=n)


def test_route_creates_a_named_ordered_walk(wired):
    client, posts = wired
    _seed(posts, ["p1", "p2", "p3"])
    res = client.post("/api/v1/corpora/", json={
        "title": "the approach", "why": "what the sequence is for",
        "images": [{"post_id": "p1", "note": "first"}, {"post_id": "p2"}, {"post_id": "p3"}]})
    body = res.json()
    assert res.status_code == 201
    assert [i["post_id"] for i in body["images"]] == ["p1", "p2", "p3"]
    assert body["images"][0]["note"] == "first"


def test_route_refuses_a_walk_with_no_images(wired):
    client, _ = wired
    res = client.post("/api/v1/corpora/", json={"title": "empty", "images": []})
    assert res.status_code == 400
    assert "not\na walk" in res.json()["detail"].replace(" ", "\n") or "walk" in res.json()["detail"]


def test_route_reorders_and_reports_a_stale_id_without_losing_the_rest(wired):
    """Refusals travel WITH the change: a curator adjusting four things should not lose three of
    them because the fourth was stale."""
    client, posts = wired
    _seed(posts, ["p1", "p2", "p3"])
    cid = client.post("/api/v1/corpora/", json={"images": [{"post_id": p} for p in
                                                           ("p1", "p2", "p3")]}).json()["id"]
    body = client.patch(f"/api/v1/corpora/{cid}",
                        json={"move": "p3", "to": 0, "note_for": "ghost", "note": "x"}).json()

    assert [i["post_id"] for i in body["corpus"]["images"]] == ["p3", "p1", "p2"]
    assert [r["reason"] for r in body["refused"]] == [C.REFUSED_UNKNOWN_IMAGE]


def test_the_view_hydrates_from_the_ledger_and_keeps_an_unreadable_image(wired):
    client, posts = wired
    _seed(posts, ["p1", "p2"])
    cid = client.post("/api/v1/corpora/", json={"images": [{"post_id": p} for p in
                                                           ("p1", "p2", "ghost")]}).json()["id"]
    view = client.get(f"/api/v1/corpora/{cid}/view").json()

    assert [i["post_id"] for i in view["images"]] == ["p1", "p2", "ghost"]
    assert view["images"][2]["readable"] is False
    assert view["unreadable"] == ["ghost"]
    assert view["images"][1]["committed"] == 1          # p2 seeded with one region


def test_AN_ATLAS_OPENS_FROM_THE_WALK_IN_ORDER(wired):
    """The condition C1 set for this collection existing at all: it is the one that IS read."""
    client, posts = wired
    _seed(posts, ["p1", "p2", "p3"])
    cid = client.post("/api/v1/corpora/", json={
        "title": "the approach",
        "images": [{"post_id": p} for p in ("p3", "p1", "p2")]}).json()["id"]

    atlas = client.post("/api/v1/atlas/", json={"corpus_id": cid}).json()

    assert [n["post_id"] for n in atlas["nodes"]] == ["p3", "p1", "p2"]   # the WALK's order
    assert atlas["corpus_ref"]["kind"] == A.CORPUS_CURATED
    assert atlas["corpus_ref"]["corpus_id"] == cid
    assert atlas["title"] == "the approach"              # the walk names the canvas


def test_an_atlas_keeps_its_images_after_the_walk_is_deleted(wired):
    """The canvas resolved its post ids when it was created. Re-sequencing or deleting the walk
    later cannot reach back and empty a canvas somebody is working on."""
    client, posts = wired
    _seed(posts, ["p1", "p2"])
    cid = client.post("/api/v1/corpora/",
                      json={"images": [{"post_id": p} for p in ("p1", "p2")]}).json()["id"]
    aid = client.post("/api/v1/atlas/", json={"corpus_id": cid}).json()["id"]

    client.delete(f"/api/v1/corpora/{cid}")
    atlas = client.get(f"/api/v1/atlas/{aid}").json()
    assert [n["post_id"] for n in atlas["nodes"]] == ["p1", "p2"]


def test_opening_a_corpus_that_does_not_exist_is_a_404(wired):
    client, _ = wired
    assert client.post("/api/v1/atlas/", json={"corpus_id": "nope"}).status_code == 404


def test_curating_writes_to_no_post(wired):
    """A corpus is an ORDERING of images somebody already has. Curating one cannot change what any
    of them shows."""
    import hashlib
    import json as _json

    client, posts = wired
    _seed(posts, ["p1", "p2", "p3"])
    before = hashlib.sha256(_json.dumps(posts.docs, sort_keys=True, default=str).encode()).hexdigest()

    cid = client.post("/api/v1/corpora/", json={"images": [{"post_id": p} for p in
                                                           ("p1", "p2", "p3")]}).json()["id"]
    client.patch(f"/api/v1/corpora/{cid}", json={"move": "p3", "to": 0})
    client.patch(f"/api/v1/corpora/{cid}", json={"note_for": "p1", "note": "why it is here"})
    client.patch(f"/api/v1/corpora/{cid}", json={"remove": "p2"})
    client.get(f"/api/v1/corpora/{cid}/view")
    client.post("/api/v1/atlas/", json={"corpus_id": cid})

    after = hashlib.sha256(_json.dumps(posts.docs, sort_keys=True, default=str).encode()).hexdigest()
    assert before == after
