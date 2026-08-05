"""
ATLAS C1 — the Atlas document: arrangement, and nothing else.

The Atlas is a SURFACE over things that already exist — M1's corpus, the ledger, the Differential.
So there is very little logic here to test, and exactly one property that matters enough to pin
from several directions: **the document stores where things sit and never what was seen.**

  the corpus reference resolves, and never invents      → §1
  the arrangement moves nodes and only moves them       → §2
  the document holds no percept data, ever              → §3
  the view is hydrated from the ledger at read time     → §4
  the store round-trips, refusals travel with the save  → §5

Every fixture in this file is SYNTHETIC. No real post, no real caption, no curator's prose.
"""
from __future__ import annotations

import asyncio
import copy

import pytest

from backend.services import atlas_service as A


# ── a fake collection, the shape the other store tests use ───────────────────

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


class FakeCollection:
    def __init__(self):
        self.docs = {}

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
                return _UpdateResult(1, 1)
        return _UpdateResult(0, 0)


def a_post(post_id, *, grounds=(), marks=(), regions=(), photo="https://example.invalid/i.jpg"):
    """A synthetic post document — the four ledger fields the canvas reads, nothing else."""
    return {"_id": post_id, "photo_url": photo, "instagram_handle": f"handle_{post_id}",
            "grounds": list(grounds), "visual_marks": list(marks),
            "region_annotations": list(regions), "percepts": []}


def a_ground(gid, source="user"):
    return {"id": gid, "kind": "soft_mask", "role": "rhythm", "source": source,
            "strokes": [{"points": [[0.5, 0.5]], "radius": 0.05}]}


# ── 1. the corpus reference ──────────────────────────────────────────────────

def test_a_bare_list_of_ids_is_a_corpus():
    ref = A.normalize_corpus_ref(["p1", "p2", "p3"])
    assert ref["kind"] == A.CORPUS_POSTS
    assert ref["post_ids"] == ["p1", "p2", "p3"]
    assert ref["run_id"] is None


def test_duplicate_images_collapse_but_order_survives():
    """Order is evidence (M1). Collapsing a duplicate must not reshuffle the sequence, and the
    same photograph twice is not a corpus this gate models."""
    assert A.normalize_corpus_ref(["c", "a", "c", "b"])["post_ids"] == ["c", "a", "b"]


def test_a_run_reference_keeps_its_run_id():
    ref = A.normalize_corpus_ref({"kind": "run", "run_id": "run_1", "post_ids": ["p1", "p2"]})
    assert ref["kind"] == A.CORPUS_RUN and ref["run_id"] == "run_1"


def test_an_unknown_kind_falls_back_rather_than_inventing_one():
    assert A.normalize_corpus_ref({"kind": "telepathy", "post_ids": ["p1"]})["kind"] == A.CORPUS_POSTS


def test_a_run_corpus_comes_from_what_the_run_resolved_not_what_it_asked_for():
    """The spec is the request; the view is what the run could actually read. A canvas built from
    the request would put a node on it for an image the run never opened."""
    run = {"spec": {"image_ids": ["p1", "p2", "ghost"]},
           "view": {"corpus": [{"post_id": "p1"}, {"post_id": "p2"}]}}
    assert A.post_ids_from_run(run) == ["p1", "p2"]


def test_a_run_that_has_not_resolved_yet_falls_back_to_its_spec():
    assert A.post_ids_from_run({"spec": {"image_ids": ["p1"]}, "view": None}) == ["p1"]
    assert A.post_ids_from_run(None) == []


# ── 2. the arrangement ───────────────────────────────────────────────────────

def test_a_fresh_atlas_opens_in_reading_order():
    """Not clustered by similarity — auto-clustering would assert a relation before anyone drew
    one, which is exactly what spatial position is not allowed to do."""
    nodes = A.default_nodes(["p1", "p2", "p3", "p4"], cols=3)
    assert [n["post_id"] for n in nodes] == ["p1", "p2", "p3", "p4"]
    assert nodes[0]["y"] == 0 and nodes[2]["y"] == 0        # first row
    assert nodes[3]["y"] > 0                                # wrapped
    assert nodes[0]["x"] < nodes[1]["x"] < nodes[2]["x"]


def test_moving_a_node_moves_only_that_node():
    nodes = A.default_nodes(["p1", "p2"])
    moved, refused = A.merge_nodes(nodes, [{"node_id": "n1", "x": 999.0, "y": 5.0}])
    assert not refused
    assert moved[0] == nodes[0]                              # untouched
    assert moved[1]["x"] == 999.0 and moved[1]["y"] == 5.0


def test_a_save_cannot_repoint_a_node_at_a_different_image():
    """The drag gesture this serves has no business relabelling evidence."""
    nodes = A.default_nodes(["p1", "p2"])
    moved, _ = A.merge_nodes(nodes, [{"node_id": "n0", "x": 1.0, "post_id": "SOMETHING_ELSE"}])
    assert moved[0]["post_id"] == "p1"


def test_an_unknown_node_is_refused_not_created():
    """A canvas that silently accreted whatever a client posted would drift from its corpus with
    nothing saying so."""
    nodes = A.default_nodes(["p1"])
    moved, refused = A.merge_nodes(nodes, [{"node_id": "n_ghost", "x": 1.0}])
    assert len(moved) == 1
    assert refused and refused[0]["reason"] == A.REFUSED_UNKNOWN_NODE
    assert refused[0]["node_id"] == "n_ghost"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "over there", None])
def test_a_position_that_is_not_a_number_is_refused(bad):
    """A node at NaN is somewhere React Flow cannot draw and nobody can drag back."""
    nodes = A.default_nodes(["p1"])
    moved, refused = A.merge_nodes(nodes, [{"node_id": "n0", "x": bad}])
    assert moved[0]["x"] == nodes[0]["x"]                    # unmoved
    assert refused and refused[0]["reason"] == A.REFUSED_BAD_POSITION


def test_a_partial_save_moves_what_it_can_and_reports_what_it_cannot():
    nodes = A.default_nodes(["p1", "p2", "p3"])
    moved, refused = A.merge_nodes(nodes, [
        {"node_id": "n0", "x": 10.0}, {"node_id": "n_ghost", "x": 20.0},
        {"node_id": "n2", "x": 30.0}])
    assert moved[0]["x"] == 10.0 and moved[2]["x"] == 30.0
    assert len(refused) == 1


def test_a_save_does_not_reshuffle_the_sequence():
    nodes = A.default_nodes(["p1", "p2", "p3"])
    moved, _ = A.merge_nodes(nodes, [{"node_id": "n2", "x": 1.0}, {"node_id": "n0", "x": 2.0}])
    assert [n["post_id"] for n in moved] == ["p1", "p2", "p3"]


# ── 3. the document holds no percept data ────────────────────────────────────

def test_a_new_document_carries_arrangement_and_references_only():
    doc = A.new_atlas_doc(atlas_id="atlas_1", corpus_ref=["p1", "p2"],
                          post_ids=["p1", "p2"], now="T")
    A.assert_no_percept_data(doc)
    for node in doc["nodes"]:
        # T1 widened this by exactly one key: `notes`, the author's freehand slot. It is listed
        # here rather than the assertion being loosened, so the next addition to a node has to be
        # a deliberate edit to this line and cannot arrive unnoticed.
        assert set(node.keys()) == {"node_id", "post_id", "x", "y", "w", "h", "notes"}
    assert doc["edges"] == [] and doc["draft"] is None


@pytest.mark.parametrize("leak", [
    {"geometry": {"kind": "soft_mask"}},
    {"grounds": [{"id": "g1"}]},
    {"photo_url": "https://example.invalid/cached.jpg"},   # a cached URL goes stale too
    {"epistemic_status": "measured"},
])
def test_a_node_that_starts_copying_the_ledger_is_caught(leak):
    """A canvas that copied percept truth could disagree with the ledger, silently, months later.
    This one cannot disagree because it makes no claim."""
    doc = A.new_atlas_doc(atlas_id="atlas_1", corpus_ref=["p1"], post_ids=["p1"], now="T")
    doc["nodes"][0].update(leak)
    with pytest.raises(ValueError) as exc:
        A.assert_no_percept_data(doc)
    assert "never copies" in str(exc.value)


def test_edges_stay_empty_rather_than_being_seeded_from_proximity():
    """Two nodes side by side are a writer thinking, not a relation claimed. Only a drawn edge
    (a real `compare_views` percept, C3) asserts one."""
    doc = A.new_atlas_doc(atlas_id="atlas_1", corpus_ref=["p1", "p2", "p3"],
                          post_ids=["p1", "p2", "p3"], now="T")
    assert doc["edges"] == []


# ── 4. the view, hydrated at read time ───────────────────────────────────────

def test_the_view_draws_percepts_from_the_ledger_not_from_the_document():
    doc = A.new_atlas_doc(atlas_id="atlas_1", corpus_ref=["p1"], post_ids=["p1"], now="T")
    posts = {"p1": a_post("p1", grounds=[a_ground("g1"), a_ground("g2")])}
    view = A.atlas_view(doc, posts)
    assert len(view["nodes"][0]["grounds"]) == 2
    assert view["nodes"][0]["image_ref"] == "https://example.invalid/i.jpg"
    # and the stored document still says nothing about them
    A.assert_no_percept_data(doc)


def test_accepting_a_percept_later_shows_up_with_nothing_to_migrate():
    """The payoff of reference-not-copy: the same unchanged document, a fuller ledger, a fuller
    canvas."""
    doc = A.new_atlas_doc(atlas_id="atlas_1", corpus_ref=["p1"], post_ids=["p1"], now="T")
    before = A.atlas_view(doc, {"p1": a_post("p1")})
    after = A.atlas_view(doc, {"p1": a_post("p1", grounds=[a_ground("g1")])})
    assert before["nodes"][0]["grounds"] == []
    assert len(after["nodes"][0]["grounds"]) == 1


def test_an_unreadable_image_stays_on_the_canvas_and_says_why():
    """"this image has no percepts" and "this image could not be loaded" are different facts."""
    doc = A.new_atlas_doc(atlas_id="atlas_1", corpus_ref=["p1", "gone"],
                          post_ids=["p1", "gone"], now="T")
    view = A.atlas_view(doc, {"p1": a_post("p1")})
    assert len(view["nodes"]) == 2
    ghost = view["nodes"][1]
    assert ghost["readable"] is False and ghost["unreadable_reason"]
    assert view["unreadable"] == ["gone"]


def test_a_quarantined_suggestion_is_withheld_and_counted():
    """Never drawn as though a curator had accepted it — and never dropped so quietly that the
    shorter list looks complete."""
    posts = {"p1": a_post("p1", grounds=[a_ground("g1"),
                                         a_ground("g2", source="model_suggested")])}
    doc = A.new_atlas_doc(atlas_id="atlas_1", corpus_ref=["p1"], post_ids=["p1"], now="T")
    node = A.atlas_view(doc, posts)["nodes"][0]
    assert [g["id"] for g in node["grounds"]] == ["g1"]
    assert node["withheld"] == 1


# ── 5. the store ─────────────────────────────────────────────────────────────
# House style: sync tests driving the async service via `asyncio.run`, collection injected.

def run(coro):
    return asyncio.run(coro)


def test_create_read_move_reload():
    """The C1 demo criterion, at the service layer: open, arrange, come back to the arrangement."""
    coll = FakeCollection()
    doc = run(A.create_atlas(corpus_ref=["p1", "p2"], post_ids=["p1", "p2"],
                             title="a canvas", collection=coll))
    atlas_id = doc["_id"]

    result = run(A.save_arrangement(atlas_id, [{"node_id": "n1", "x": 777.0, "y": 88.0}],
                                    collection=coll))
    assert result and not result["refused"]

    reloaded = run(A.get_atlas(atlas_id, collection=coll))
    assert reloaded["nodes"][1]["x"] == 777.0 and reloaded["nodes"][1]["y"] == 88.0
    assert reloaded["nodes"][0]["x"] == 0.0                  # the one nobody moved
    A.assert_no_percept_data(reloaded)


def test_a_refusal_travels_with_the_save_rather_than_aborting_it():
    """Dragging four nodes when one has gone stale should move the three that are real."""
    coll = FakeCollection()
    doc = run(A.create_atlas(corpus_ref=["p1", "p2"], post_ids=["p1", "p2"], collection=coll))
    result = run(A.save_arrangement(
        doc["_id"], [{"node_id": "n0", "x": 5.0}, {"node_id": "n_ghost", "x": 6.0}],
        collection=coll))
    assert result["doc"]["nodes"][0]["x"] == 5.0
    assert len(result["refused"]) == 1
    assert result["refused"][0]["reason"] == A.REFUSED_UNKNOWN_NODE


def test_saving_an_atlas_that_does_not_exist_is_a_miss_not_a_new_one():
    coll = FakeCollection()
    assert run(A.save_arrangement("atlas_nope", [{"node_id": "n0", "x": 1.0}],
                                  collection=coll)) is None
    assert coll.docs == {}


def test_the_atlas_never_writes_to_a_post():
    """DATA SAFETY, pinned in source rather than argued in a comment.

    The Atlas reads the ledger and writes arrangement. If a later gate ever reaches for a post
    write from here — to "just mark" something, to cache a thumbnail — this fails, and the reviewer
    gets to decide whether that is really what the canvas should be doing. C2 adds percept
    creation, and it does it through the EXISTING quarantine and Accept path, not through here.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    writes = re.compile(r"(post_collection|posts)\s*\.\s*"
                        r"(insert_one|insert_many|update_one|update_many|replace_one|"
                        r"delete_one|delete_many|find_one_and_\w+|bulk_write)")
    for name in ("routers/atlas.py", "services/atlas_service.py"):
        source = (root / name).read_text(encoding="utf-8")
        found = writes.findall(source)
        assert not found, f"{name} writes to posts: {found}"


def test_the_stored_document_never_grows_percept_data_through_a_save():
    """The invariant, checked after a write rather than only at creation — a store that only
    validated on insert would let the second write be the dishonest one."""
    coll = FakeCollection()
    doc = run(A.create_atlas(corpus_ref=["p1"], post_ids=["p1"], collection=coll))
    run(A.save_arrangement(doc["_id"], [{"node_id": "n0", "x": 1.0, "geometry": {"kind": "x"},
                                         "grounds": [{"id": "g1"}]}], collection=coll))
    stored = run(A.get_atlas(doc["_id"], collection=coll))
    A.assert_no_percept_data(stored)
    assert set(stored["nodes"][0].keys()) == {"node_id", "post_id", "x", "y", "w", "h", "notes"}
