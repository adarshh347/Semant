"""
ATLAS C3 — relation edges: a drawn line is a comparative percept, or it is nothing.

C3 owns no comparison logic — `compare_views` names the relation and `resolve_corpus` decides
whether it may be attempted — so what is worth pinning is the seam, from both ends:

  committed marks are what `compare_views` gets to see       → §1
  a grounded relation carries BOTH sides                     → §2
  every way this refuses, and that it persists nothing       → §3
  an edge stores references; the ledger is read at view time → §4
  the ledger write appends, and one relation keeps one id    → §5
  the two routes, end to end                                 → §6

Every fixture is SYNTHETIC. No real post, no model call, no database.
"""
from __future__ import annotations

import asyncio
import copy

import pytest

from backend.services import atlas_relation as R
from backend.services import atlas_service as A


# ── fixtures ─────────────────────────────────────────────────────────────────

def a_mark(mark_id: str, label: str, *, source: str = "user", role: str = "axis") -> dict:
    return {"id": mark_id, "type": "trace_mark", "role": role, "label": label,
            "source": source, "status": "committed", "source_ref": mark_id,
            "geometry": {"kind": "path", "points": [[0.1, 0.1], [0.4, 0.4]]}}


def a_post(post_id: str, marks=()) -> dict:
    return {"_id": post_id, "photo_url": f"https://example.invalid/{post_id}.jpg",
            "instagram_handle": f"handle_{post_id}", "visual_marks": list(marks),
            "region_annotations": [], "grounds": [], "percepts": []}


def pairs(*specs):
    """(post_id, marks) … → the `relate` argument."""
    return [(pid, a_post(pid, marks)) for pid, marks in specs]


def an_atlas(*post_ids) -> dict:
    return {"_id": "atlas_1", "title": "the walk", "edges": [],
            "nodes": [{"node_id": f"n{i}", "post_id": p, "x": 0.0, "y": 0.0}
                      for i, p in enumerate(post_ids)]}


class _UpdateResult:
    def __init__(self, matched=1, modified=1):
        self.matched_count = matched
        self.modified_count = modified


class FakeCollection:
    """Supports the operators these routes actually use: `$set` and `$push`."""

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

    async def count_documents(self, query, limit=None):
        return sum(1 for d in self.docs.values()
                   if all(d.get(k) == v for k, v in (query or {}).items()))

    async def update_one(self, query, update, upsert=False):
        for d in self.docs.values():
            if all(d.get(k) == v for k, v in (query or {}).items()):
                d.update(update.get("$set", {}))
                for field, value in (update.get("$push") or {}).items():
                    d.setdefault(field, []).append(copy.deepcopy(value))
                return _UpdateResult()
        return _UpdateResult(0, 0)


def run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


# ── 1. the seam: committed marks are what the comparison sees ────────────────

def test_committed_marks_are_visible_to_the_comparison():
    """The whole reason C3 needs no change inside `compare_views`.

    The default context answers `marks_by_image()` with what THIS RUN produced, which on a canvas
    of already-committed percepts is always empty — every comparison would refuse while the writer
    looks at two marks they drew themselves.
    """
    out = R.relate(pairs(("p1", [a_mark("m1", "the doorway")]),
                         ("p2", [a_mark("m2", "the mirror")])),
                   source_node="n0", target_node="n1", relation_role="kinship")
    assert "relation" in out, out


def test_a_quarantined_mark_is_not_evidence():
    """A `model_suggested` mark is a proposal. A relation resting on one would be a comparison
    between two things nobody has accepted."""
    assert R.committed_marks(a_post("p1", [a_mark("m1", "x", source="model_suggested")])) == []
    assert len(R.committed_marks(a_post("p1", [a_mark("m1", "x")]))) == 1


def test_the_run_output_never_contains_the_committed_marks_it_was_shown():
    """`suggestions` is the plan's OUTPUT and stays that way. Seeding committed marks into it
    would make the ledger's own evidence come back out looking model-produced."""
    corpus = R.build_relation_corpus(pairs(("p1", [a_mark("m1", "a")]),
                                           ("p2", [a_mark("m2", "b")])))
    posts = {"p1": a_post("p1", [a_mark("m1", "a")]), "p2": a_post("p2", [a_mark("m2", "b")])}
    ctx = R.build_relation_context(corpus, posts)
    try:
        assert ctx.all_suggestions() == []
        assert len(ctx.marks_by_image()["p1"]) == 1      # visible to the actuator
    finally:
        ctx.close()


def test_the_corpus_keeps_the_order_the_line_was_drawn_in():
    """`compare_views` records a left and a right. "The façade prepares the rotunda" is not the
    same claim as its reverse, so drawn order is source→target and is preserved."""
    corpus = R.build_relation_corpus(pairs(("p2", []), ("p1", [])))
    assert list(corpus.post_ids) == ["p2", "p1"]


# ── 2. a grounded relation carries both sides ────────────────────────────────

def test_a_grounded_relation_names_both_posts_and_both_marks():
    """A cross-image claim that cannot say which pictures it spans is not checkable, and an
    uncheckable comparison is the article's whole risk."""
    out = R.relate(pairs(("p1", [a_mark("m1", "the doorway")]),
                         ("p2", [a_mark("m2", "the mirror")])),
                   source_node="n0", target_node="n1", relation_role="kinship")
    relation = out["relation"]

    assert (relation.get("corpus") or {}).get("spans") == ["p1", "p2"]
    assert (relation.get("geometry") or {}).get("cross_image") is True
    sources = (relation.get("provenance") or {}).get("sources") or []
    assert [s.get("post_id") for s in sources] == ["p1", "p2"]
    assert [s.get("mark_ref") for s in sources] == ["m1", "m2"]


def test_the_writers_own_word_for_the_relation_is_used():
    out = R.relate(pairs(("p1", [a_mark("m1", "a")]), ("p2", [a_mark("m2", "b")])),
                   source_node="n0", target_node="n1", relation_role="echo")
    assert out["relation"]["label"] == "echo"


def test_explicit_refs_choose_which_marks_are_related():
    out = R.relate(pairs(("p1", [a_mark("m1", "a"), a_mark("m1b", "second")]),
                         ("p2", [a_mark("m2", "b")])),
                   source_node="n0", target_node="n1",
                   relation_role="kinship", left_ref="m1b", right_ref="m2")
    refs = [s["mark_ref"] for s in out["relation"]["provenance"]["sources"]]
    assert refs == ["m1b", "m2"]


def test_the_committed_relation_carries_an_epistemic_kind():
    """`compare_views` is the one relation minter that does not stamp its own output, so C3 calls
    M5's public `stamp` on the way to the ledger. A named relation is a reading of two
    measurements — `interpretive` — and the chip on the edge is that word."""
    out = R.relate(pairs(("p1", [a_mark("m1", "a")]), ("p2", [a_mark("m2", "b")])),
                   source_node="n0", target_node="n1", relation_role="kinship")
    mark = R.committed_relation(out["relation"])
    assert mark["epistemic_status"] == "interpretive"


def test_stamping_never_overwrites_a_status_the_producer_declared():
    """So the day `compare_views` starts stamping its own output, C3's call is a no-op rather
    than a conflict."""
    mark = R.committed_relation({"producer": "semantic_read", "epistemic_status": "uncertain"})
    assert mark["epistemic_status"] == "uncertain"


def test_a_drawn_relation_is_committed_not_quarantined():
    """The gesture IS the decision a review step would otherwise ask for. What the model
    contributed stays visible in provenance, so the record never pretends a person wrote it."""
    out = R.relate(pairs(("p1", [a_mark("m1", "a")]), ("p2", [a_mark("m2", "b")])),
                   source_node="n0", target_node="n1", relation_role="kinship")
    mark = R.committed_relation(out["relation"])
    assert mark["source"] == "user_confirmed"
    assert mark["status"] == "committed"
    assert mark["provenance"]["committed_by"] == "atlas_c3_draw"
    assert mark["provenance"]["producer"] == "compare_views"     # still says who named it


# ── 3. every way this refuses ────────────────────────────────────────────────

def test_it_refuses_when_only_one_image_carries_marks_AT_PLAN_TIME():
    out = R.relate(pairs(("p1", [a_mark("m1", "a")]), ("p2", [])),
                   source_node="n0", target_node="n1")
    assert "relation" not in out
    assert out["refused"]["reason"] == R.REFUSED_NOT_PLANNED
    assert "2× mark" in out["refused"]["detail"]


def test_it_refuses_at_RUN_time_when_the_marks_are_all_on_one_image():
    """The case `resolve()` cannot catch, and the one that matters most in practice: the merged
    packet counts two marks and two images, so the step is placed — and at dispatch both marks
    turn out to be on the same photograph. Falling back to a same-image pair there would produce
    a well-formed relation answering a question nobody asked."""
    out = R.relate(pairs(("p1", [a_mark("m1", "a"), a_mark("m2", "b")]), ("p2", [])),
                   source_node="n0", target_node="n1")
    assert "relation" not in out
    assert out["refused"]["reason"] == R.REFUSED_NOT_PRODUCED
    assert "2 images" in out["refused"]["detail"]


def test_a_refusal_carries_the_two_nodes_it_was_drawn_between():
    """It has to render ON the attempted edge, so it must know which line that was."""
    out = R.relate(pairs(("p1", [a_mark("m1", "a")]), ("p2", [])),
                   source_node="n0", target_node="n1")
    assert out["refused"]["source_node"] == "n0"
    assert out["refused"]["target_node"] == "n1"


def test_the_gates_own_words_are_passed_through_not_paraphrased():
    """The gate is the authority on why it refused; a friendlier wording would be this module
    inventing a reason."""
    out = R.relate(pairs(("p1", []), ("p2", [])), source_node="n0", target_node="n1")
    assert out["refused"]["detail"].startswith("missing_input")


def test_every_refusal_shape_is_the_same_shape():
    for made in (R.refusal(R.REFUSED_SAME_NODE, "d", source_node="n0", target_node="n0"),
                 R.relate(pairs(("p1", []), ("p2", [])), source_node="n0", target_node="n1")["refused"]):
        assert set(made) == {"reason", "detail", "source_node", "target_node"}


# ── 4. the edge references; the ledger is read at view time ──────────────────

def test_an_edge_stores_ids_and_endpoints_and_nothing_else():
    """C1's rule, applied to edges. An edge that cached the relation's label could disagree with
    the ledger about what was named, silently, in a document that looks authoritative."""
    entry = R.edge_entry(mark_id="vm_rel_1", source_node="n0", target_node="n1",
                         spans=["p1", "p2"])
    assert set(entry) == {"edge_id", "kind", "mark_id", "source_node", "target_node",
                          "spans", "created_at"}
    assert entry["kind"] == R.EDGE_RELATION


def test_an_edge_carrying_percept_data_is_refused_by_the_same_guard_as_a_node():
    with pytest.raises(ValueError, match="carries percept data"):
        A.assert_no_percept_data({"nodes": [], "edges": [
            {"edge_id": "e1", "mark_id": "m", "label": "kinship"}]})
    with pytest.raises(ValueError, match="carries percept data"):
        A.assert_no_percept_data({"nodes": [], "edges": [
            {"edge_id": "e1", "geometry": {"kind": "derived"}}]})


def test_the_edge_is_hydrated_from_the_ledger_at_read_time():
    mark = {"id": "vm_rel_1", "role": "kinship", "label": "echoes",
            "epistemic_status": "interpretive", "source_ref": "p1:m1→p2:m2",
            "provenance": {"sources": [{"post_id": "p1"}, {"post_id": "p2"}]}}
    entry = R.edge_entry(mark_id="vm_rel_1", source_node="n0", target_node="n1",
                         spans=["p1", "p2"])
    live = R.hydrate_edge(entry, {"p1": {"visual_marks": [mark]}, "p2": {"visual_marks": [mark]}})

    assert live["live"] is True
    assert live["role"] == "kinship" and live["label"] == "echoes"
    assert live["epistemic"] == "interpretive"
    assert len(live["sources"]) == 2


def test_an_edge_whose_relation_left_the_ledger_says_so_and_stays_on_the_canvas():
    """"Never drawn" and "drawn, then uncommitted" are different facts about the corpus, and a
    canvas that showed the second as the first would be lying by omission."""
    entry = R.edge_entry(mark_id="gone", source_node="n0", target_node="n1", spans=["p1", "p2"])
    stale = R.hydrate_edge(entry, {"p1": {"visual_marks": []}})
    assert stale["live"] is False
    assert "no longer in the ledger" in stale["missing_reason"]
    assert stale["source_node"] == "n0"          # it still renders, between the same two nodes


def test_hydration_finds_the_relation_from_either_end():
    mark = {"id": "vm_rel_1", "role": "kinship", "label": "x", "epistemic_status": "interpretive"}
    entry = R.edge_entry(mark_id="vm_rel_1", source_node="n0", target_node="n1",
                         spans=["p1", "p2"])
    assert R.hydrate_edge(entry, {"p2": {"visual_marks": [mark]}})["live"] is True


# ── 5. the ledger write ──────────────────────────────────────────────────────

def test_the_write_appends_and_never_replaces_the_array():
    """A wholesale `$set` on this field has already destroyed committed evidence in this codebase.
    An append cannot: the existing marks are not read, so there is nothing to go stale."""
    posts = FakeCollection({"p1": a_post("p1", [a_mark("m1", "existing")]),
                            "p2": a_post("p2", [a_mark("m2", "existing")])})
    mark = R.committed_relation({"producer": "semantic_read", "type": "relation_mark"},
                                mark_id="vm_rel_1")
    written = run(R.commit_relation_to_posts(mark, ["p1", "p2"], collection=posts))

    assert written == ["p1", "p2"]
    for pid in ("p1", "p2"):
        marks = posts.docs[pid]["visual_marks"]
        assert len(marks) == 2                                  # the existing one SURVIVED
        assert marks[0]["id"] in ("m1", "m2")
        assert marks[1]["id"] == "vm_rel_1"


def test_one_relation_keeps_one_id_in_both_posts():
    """Two ids for one comparison would leave the Atlas edge referencing one of them and the other
    orphaned, and a later reader counting relations would find two where a writer drew one."""
    posts = FakeCollection({"p1": a_post("p1"), "p2": a_post("p2")})
    mark = R.committed_relation({"producer": "semantic_read"}, mark_id="vm_rel_1")
    run(R.commit_relation_to_posts(mark, ["p1", "p2"], collection=posts))
    assert posts.docs["p1"]["visual_marks"][0]["id"] == posts.docs["p2"]["visual_marks"][0]["id"]


def test_a_post_that_does_not_exist_is_reported_not_created():
    posts = FakeCollection({"p1": a_post("p1")})
    written = run(R.commit_relation_to_posts({"id": "x"}, ["p1", "ghost"], collection=posts))
    assert written == ["p1"]
    assert "ghost" not in posts.docs


def test_the_atlas_edge_list_appends_too():
    async def go():
        coll = FakeCollection()
        await A.create_atlas(corpus_ref=["p1", "p2"], post_ids=["p1", "p2"],
                             atlas_id="a1", collection=coll)
        for i in (1, 2):
            await A.add_edge("a1", R.edge_entry(mark_id=f"vm_{i}", source_node="n0",
                                                target_node="n1", spans=["p1", "p2"]),
                             collection=coll)
        doc = await A.get_atlas("a1", collection=coll)
        assert [e["mark_id"] for e in doc["edges"]] == ["vm_1", "vm_2"]
    run(go())


def test_removing_an_edge_leaves_the_ledger_alone():
    """The Atlas never owned the percept and does not get to destroy one."""
    async def go():
        coll = FakeCollection()
        await A.create_atlas(corpus_ref=["p1"], post_ids=["p1"], atlas_id="a1", collection=coll)
        entry = R.edge_entry(mark_id="vm_1", source_node="n0", target_node="n1",
                             spans=["p1", "p2"], edge_id="e1")
        await A.add_edge("a1", entry, collection=coll)
        doc = await A.remove_edge("a1", "e1", collection=coll)
        assert doc["edges"] == []
        assert [n["post_id"] for n in doc["nodes"]] == ["p1"]
    run(go())


# ── 6. the routes ────────────────────────────────────────────────────────────

@pytest.fixture
def wired(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import backend.database as db
    import backend.routers.atlas as Router

    atlases = FakeCollection()
    posts = FakeCollection()
    monkeypatch.setattr(db, "atlas_collection", atlases, raising=False)
    monkeypatch.setattr(Router, "post_collection", posts, raising=False)

    app = FastAPI()
    app.include_router(Router.router, prefix="/api/v1/atlas")
    return TestClient(app), atlases, posts


def _open_atlas(client, posts, spec):
    for pid, marks in spec:
        posts.docs[pid] = a_post(pid, marks)
    res = client.post("/api/v1/atlas/", json={"title": "the walk",
                                              "post_ids": [pid for pid, _ in spec]})
    assert res.status_code == 201
    return res.json()["id"]


def test_route_draws_a_relation_and_stores_it_as_an_edge(wired):
    client, _, posts = wired
    atlas_id = _open_atlas(client, posts, [("p1", [a_mark("m1", "the doorway")]),
                                           ("p2", [a_mark("m2", "the mirror")])])
    res = client.post(f"/api/v1/atlas/{atlas_id}/relations",
                      json={"source_node": "n0", "target_node": "n1",
                            "relation_role": "kinship"})
    body = res.json()

    assert res.status_code == 200 and "edge" in body
    edge = body["edge"]
    assert edge["kind"] == R.EDGE_RELATION
    assert edge["live"] is True
    assert edge["epistemic"] == "interpretive"
    assert edge["spans"] == ["p1", "p2"]
    assert len(edge["sources"]) == 2
    # the relation is in the LEDGER, on both endpoints, under one id
    ids = [m["id"] for p in ("p1", "p2") for m in posts.docs[p]["visual_marks"]
           if m.get("type") == "relation_mark"]
    assert len(ids) == 2 and len(set(ids)) == 1
    # and the stored document holds a reference, not the relation
    stored = client.get(f"/api/v1/atlas/{atlas_id}").json()
    assert set(stored["edges"][0]) == {"edge_id", "kind", "mark_id", "source_node",
                                       "target_node", "spans", "created_at"}


def test_route_refusal_is_200_and_persists_absolutely_nothing(wired):
    """"These two images carry no marks to compare" is an answer about the evidence, not a
    complaint about the request."""
    client, atlases, posts = wired
    atlas_id = _open_atlas(client, posts, [("p1", [a_mark("m1", "a")]), ("p2", [])])
    before = copy.deepcopy(posts.docs)

    res = client.post(f"/api/v1/atlas/{atlas_id}/relations",
                      json={"source_node": "n0", "target_node": "n1"})
    body = res.json()

    assert res.status_code == 200
    assert "edge" not in body and body["refused"]["reason"] == R.REFUSED_NOT_PLANNED
    assert posts.docs == before                                   # the ledger is byte-identical
    assert client.get(f"/api/v1/atlas/{atlas_id}").json()["edges"] == []


def test_route_refuses_a_line_from_an_image_to_itself(wired):
    client, _, posts = wired
    atlas_id = _open_atlas(client, posts, [("p1", [a_mark("m1", "a")]),
                                           ("p2", [a_mark("m2", "b")])])
    body = client.post(f"/api/v1/atlas/{atlas_id}/relations",
                       json={"source_node": "n0", "target_node": "n0"}).json()
    assert body["refused"]["reason"] == R.REFUSED_SAME_NODE


def test_route_refuses_a_node_this_atlas_does_not_hold(wired):
    client, _, posts = wired
    atlas_id = _open_atlas(client, posts, [("p1", [a_mark("m1", "a")]),
                                           ("p2", [a_mark("m2", "b")])])
    body = client.post(f"/api/v1/atlas/{atlas_id}/relations",
                       json={"source_node": "n0", "target_node": "n9"}).json()
    assert body["refused"]["reason"] == R.REFUSED_UNKNOWN_NODE


def test_route_names_an_unreadable_endpoint_rather_than_reporting_no_marks(wired):
    """An unreadable image is not an empty one, and `compare_views` would only be able to say the
    second."""
    client, _, posts = wired
    atlas_id = _open_atlas(client, posts, [("p1", [a_mark("m1", "a")]),
                                           ("p2", [a_mark("m2", "b")])])
    posts.docs.pop("p2")
    body = client.post(f"/api/v1/atlas/{atlas_id}/relations",
                       json={"source_node": "n0", "target_node": "n1"}).json()
    assert body["refused"]["reason"] == R.REFUSED_UNREADABLE
    assert "p2" in body["refused"]["detail"]


def test_the_view_hydrates_every_edge_from_the_ledger(wired):
    client, _, posts = wired
    atlas_id = _open_atlas(client, posts, [("p1", [a_mark("m1", "a")]),
                                           ("p2", [a_mark("m2", "b")])])
    client.post(f"/api/v1/atlas/{atlas_id}/relations",
                json={"source_node": "n0", "target_node": "n1", "relation_role": "kinship"})
    view = client.get(f"/api/v1/atlas/{atlas_id}/view").json()

    assert len(view["edges"]) == 1
    assert view["edges"][0]["role"] == "kinship"
    assert view["edges"][0]["live"] is True


def test_deleting_an_edge_keeps_the_relation_in_the_ledger(wired):
    client, _, posts = wired
    atlas_id = _open_atlas(client, posts, [("p1", [a_mark("m1", "a")]),
                                           ("p2", [a_mark("m2", "b")])])
    edge = client.post(f"/api/v1/atlas/{atlas_id}/relations",
                       json={"source_node": "n0", "target_node": "n1"}).json()["edge"]
    marks_before = len(posts.docs["p1"]["visual_marks"])

    res = client.delete(f"/api/v1/atlas/{atlas_id}/relations/{edge['edge_id']}")
    assert res.status_code == 200
    assert client.get(f"/api/v1/atlas/{atlas_id}").json()["edges"] == []
    assert len(posts.docs["p1"]["visual_marks"]) == marks_before   # the mark is untouched


def test_no_other_atlas_route_writes_to_a_post(wired):
    """C3 is a narrow exception, not an opening. Every other route stays as read-only as it was."""
    import hashlib
    import json as _json

    client, _, posts = wired
    atlas_id = _open_atlas(client, posts, [("p1", [a_mark("m1", "a")]),
                                           ("p2", [a_mark("m2", "b")])])
    before = hashlib.sha256(_json.dumps(posts.docs, sort_keys=True, default=str).encode()).hexdigest()

    client.get(f"/api/v1/atlas/{atlas_id}")
    client.get(f"/api/v1/atlas/{atlas_id}/view")
    client.post(f"/api/v1/atlas/{atlas_id}/arrangement",
                json={"nodes": [{"node_id": "n0", "x": 10, "y": 20}]})
    client.delete(f"/api/v1/atlas/{atlas_id}/plan")

    after = hashlib.sha256(_json.dumps(posts.docs, sort_keys=True, default=str).encode()).hexdigest()
    assert before == after
