"""
Writing Studio · WS-0A — the sacred manuscript.

Covers the canon store: manuscript/chapter/scene CRUD, the hierarchy as a single
atomic source of truth, the canonical scene write (word counting), immutable version
snapshots with non-destructive restore, reorder integrity (never creates/drops
content), cascade deletes, and export assembly.

House style: sync tests driving async service code via ``asyncio.run`` with injected
fake async Mongo collections (cf. test_circulation_spine_p1.py). No live Mongo, no
network, no models.
"""
import asyncio
import copy

import pytest

from backend.services import manuscript_service as svc


# ── fake async Mongo collection (supports exactly the ops the service uses) ───
class _UpdateResult:
    def __init__(self, matched, modified):
        self.matched_count = matched
        self.modified_count = modified


class _DeleteResult:
    def __init__(self, deleted):
        self.deleted_count = deleted


class _Cursor:
    """Async-iterable result of find(); supports .sort()."""
    def __init__(self, docs):
        self._docs = docs

    def sort(self, field, direction=1):
        self._docs = sorted(
            self._docs,
            key=lambda d: (d.get(field) is None, d.get(field)),
            reverse=direction < 0,
        )
        return self

    def __aiter__(self):
        async def gen():
            for d in self._docs:
                yield copy.deepcopy(d)
        return gen()


def _match(doc, query):
    for k, v in (query or {}).items():
        if isinstance(v, dict) and "$in" in v:
            if doc.get(k) not in v["$in"]:
                return False
        else:
            if doc.get(k) != v:
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
            if _match(d, query):
                return copy.deepcopy(d)
        return None

    def find(self, query=None, projection=None):
        return _Cursor([copy.deepcopy(d) for d in self.docs.values() if _match(d, query)])

    async def update_one(self, query, update, upsert=False):
        for _id, d in self.docs.items():
            if _match(d, query):
                d.update(update.get("$set", {}))
                return _UpdateResult(1, 1)
        if upsert:
            new = dict(query)
            new.update(update.get("$set", {}))
            self.docs[new["_id"]] = new
            return _UpdateResult(0, 0)
        return _UpdateResult(0, 0)

    async def delete_one(self, query):
        for _id, d in list(self.docs.items()):
            if _match(d, query):
                del self.docs[_id]
                return _DeleteResult(1)
        return _DeleteResult(0)

    async def delete_many(self, query):
        hits = [i for i, d in self.docs.items() if _match(d, query)]
        for i in hits:
            del self.docs[i]
        return _DeleteResult(len(hits))


@pytest.fixture
def store(monkeypatch):
    ms, sc, ver = FakeCollection(), FakeCollection(), FakeCollection()
    monkeypatch.setattr(svc, "manuscript_collection", ms)
    monkeypatch.setattr(svc, "scene_collection", sc)
    monkeypatch.setattr(svc, "scene_version_collection", ver)
    return svc.manuscript_service, ms, sc, ver


def run(coro):
    return asyncio.run(coro)


# helper — a paragraph block
def blk(bid, text, btype="paragraph", origin="human", color=None):
    return {"id": bid, "type": btype, "content": f"<p>{text}</p>", "color": color, "origin": origin}


# ── pure helpers ─────────────────────────────────────────────────────────────

def test_strip_html_and_word_count():
    assert svc._strip_html("<p>hello <strong>brave</strong> world</p>") == "hello brave world"
    assert svc._word_count([blk("b1", "one two three"), blk("b2", "four")]) == 4
    assert svc._word_count([]) == 0
    # empty content contributes nothing
    assert svc._word_count([{"id": "x", "type": "paragraph", "content": "<p></p>"}]) == 0


def test_blocks_to_markdown_prefixes_by_type():
    md = svc._blocks_to_markdown([
        {"id": "h", "type": "h1", "content": "<h1>Title</h1>"},
        {"id": "p", "type": "paragraph", "content": "<p>Body.</p>"},
        {"id": "q", "type": "quote", "content": "<blockquote>Said.</blockquote>"},
        {"id": "empty", "type": "paragraph", "content": ""},
    ])
    assert md == "# Title\n\nBody.\n\n> Said."


# ── manuscripts ──────────────────────────────────────────────────────────────

def test_create_and_get_manuscript(store):
    service, *_ = store
    ms = run(service.create_manuscript("The Turned Collar", "A short synopsis."))
    assert ms["id"].startswith("ms_")
    assert ms["title"] == "The Turned Collar"
    assert ms["chapters"] == []
    got = run(service.get_manuscript(ms["id"]))
    assert got["synopsis"] == "A short synopsis."
    assert got["scenes"] == {}


def test_get_missing_manuscript_is_none(store):
    service, *_ = store
    assert run(service.get_manuscript("ms_nope")) is None


def test_list_manuscripts_summaries(store):
    service, *_ = store
    a = run(service.create_manuscript("A"))
    run(service.create_manuscript("B"))
    run(service.add_chapter(a["id"], "Ch1"))
    ms_a = run(service.get_manuscript(a["id"]))
    ch = ms_a["chapters"][0]["id"]
    run(service.add_scene(a["id"], ch, "S1"))
    listing = run(service.list_manuscripts())
    assert len(listing) == 2
    summ = next(x for x in listing if x["id"] == a["id"])
    assert summ["chapter_count"] == 1 and summ["scene_count"] == 1


def test_update_manuscript_metadata(store):
    service, *_ = store
    ms = run(service.create_manuscript("Old"))
    upd = run(service.update_manuscript(ms["id"], {"title": "New", "synopsis": "S"}))
    assert upd["title"] == "New" and upd["synopsis"] == "S"


# ── chapters + scenes hierarchy ──────────────────────────────────────────────

def test_add_chapter_and_scene_updates_hierarchy(store):
    service, ms_c, sc_c, _ = store
    ms = run(service.create_manuscript("Work"))
    run(service.add_chapter(ms["id"], "Chapter One"))
    ms1 = run(service.get_manuscript(ms["id"]))
    ch_id = ms1["chapters"][0]["id"]
    assert ch_id.startswith("ch_")
    scene = run(service.add_scene(ms["id"], ch_id, "Opening", [blk("b1", "hi there")]))
    assert scene["id"].startswith("sc_")
    assert scene["word_count"] == 2
    ms2 = run(service.get_manuscript(ms["id"]))
    assert ms2["chapters"][0]["scene_ids"] == [scene["id"]]
    assert scene["id"] in ms2["scenes"]
    assert ms2["scenes"][scene["id"]]["title"] == "Opening"


def test_add_scene_to_missing_chapter_is_none(store):
    service, *_ = store
    ms = run(service.create_manuscript("Work"))
    assert run(service.add_scene(ms["id"], "ch_missing", "S")) is None


def test_update_scene_is_canonical_write(store):
    service, ms_c, sc_c, _ = store
    ms = run(service.create_manuscript("Work"))
    run(service.add_chapter(ms["id"], "C"))
    ch = run(service.get_manuscript(ms["id"]))["chapters"][0]["id"]
    scene = run(service.add_scene(ms["id"], ch, "S"))
    saved = run(service.update_scene(scene["id"], {"blocks": [blk("b1", "four words go here")]}))
    assert saved["word_count"] == 4
    assert saved["blocks"][0]["content"] == "<p>four words go here</p>"
    # title-only patch preserves blocks
    retitled = run(service.update_scene(scene["id"], {"title": "Renamed"}))
    assert retitled["title"] == "Renamed" and retitled["word_count"] == 4


# ── version snapshots ────────────────────────────────────────────────────────

def test_snapshot_list_and_nondestructive_restore(store):
    service, ms_c, sc_c, ver_c = store
    ms = run(service.create_manuscript("Work"))
    run(service.add_chapter(ms["id"], "C"))
    ch = run(service.get_manuscript(ms["id"]))["chapters"][0]["id"]
    scene = run(service.add_scene(ms["id"], ch, "S", [blk("b1", "first draft")]))

    v1 = run(service.snapshot_scene(scene["id"], "draft one"))
    assert v1["id"].startswith("ver_")
    # author edits the live scene away from the snapshot
    run(service.update_scene(scene["id"], {"blocks": [blk("b1", "totally rewritten now")]}))

    versions = run(service.list_scene_versions(scene["id"]))
    assert len(versions) == 1 and versions[0]["label"] == "draft one"

    # restore copies the snapshot FORWARD and auto-snapshots current first
    restored = run(service.restore_version(scene["id"], v1["id"]))
    assert svc._strip_html(restored["blocks"][0]["content"]) == "first draft"
    after = run(service.list_scene_versions(scene["id"]))
    assert len(after) == 2  # draft one + the "before restore" auto-snapshot
    assert any(v["label"] == "before restore" for v in after)


def test_restore_wrong_scene_is_none(store):
    service, *_ = store
    ms = run(service.create_manuscript("Work"))
    run(service.add_chapter(ms["id"], "C"))
    ch = run(service.get_manuscript(ms["id"]))["chapters"][0]["id"]
    s1 = run(service.add_scene(ms["id"], ch, "S1", [blk("b", "a")]))
    s2 = run(service.add_scene(ms["id"], ch, "S2", [blk("b", "b")]))
    v = run(service.snapshot_scene(s1["id"], "v"))
    # a version of s1 cannot be restored onto s2
    assert run(service.restore_version(s2["id"], v["id"])) is None


# ── deletes cascade ──────────────────────────────────────────────────────────

def test_delete_scene_removes_from_chapter_and_versions(store):
    service, ms_c, sc_c, ver_c = store
    ms = run(service.create_manuscript("Work"))
    run(service.add_chapter(ms["id"], "C"))
    ch = run(service.get_manuscript(ms["id"]))["chapters"][0]["id"]
    scene = run(service.add_scene(ms["id"], ch, "S", [blk("b", "x")]))
    run(service.snapshot_scene(scene["id"], "v"))
    run(service.delete_scene(scene["id"]))
    ms2 = run(service.get_manuscript(ms["id"]))
    assert ms2["chapters"][0]["scene_ids"] == []
    assert run(service.get_scene(scene["id"])) is None
    assert run(service.list_scene_versions(scene["id"])) == []


def test_delete_chapter_cascades_scenes(store):
    service, ms_c, sc_c, ver_c = store
    ms = run(service.create_manuscript("Work"))
    run(service.add_chapter(ms["id"], "C"))
    ch = run(service.get_manuscript(ms["id"]))["chapters"][0]["id"]
    scene = run(service.add_scene(ms["id"], ch, "S"))
    run(service.delete_chapter(ms["id"], ch))
    ms2 = run(service.get_manuscript(ms["id"]))
    assert ms2["chapters"] == []
    assert run(service.get_scene(scene["id"])) is None


def test_delete_manuscript_cascades_everything(store):
    service, ms_c, sc_c, ver_c = store
    ms = run(service.create_manuscript("Work"))
    run(service.add_chapter(ms["id"], "C"))
    ch = run(service.get_manuscript(ms["id"]))["chapters"][0]["id"]
    scene = run(service.add_scene(ms["id"], ch, "S"))
    run(service.snapshot_scene(scene["id"], "v"))
    assert run(service.delete_manuscript(ms["id"])) is True
    assert run(service.get_manuscript(ms["id"])) is None
    assert len(sc_c.docs) == 0 and len(ver_c.docs) == 0
    assert run(service.delete_manuscript(ms["id"])) is False


# ── reorder integrity ────────────────────────────────────────────────────────

def test_reorder_moves_scene_across_chapters(store):
    service, *_ = store
    ms = run(service.create_manuscript("Work"))
    run(service.add_chapter(ms["id"], "A"))
    run(service.add_chapter(ms["id"], "B"))
    full = run(service.get_manuscript(ms["id"]))
    ca, cb = full["chapters"][0]["id"], full["chapters"][1]["id"]
    scene = run(service.add_scene(ms["id"], ca, "S"))
    # move the scene from A to B
    outline = [
        {"id": ca, "title": "A", "scene_ids": []},
        {"id": cb, "title": "B", "scene_ids": [scene["id"]]},
    ]
    res = run(service.reorder(ms["id"], outline))
    assert res["chapters"][1]["scene_ids"] == [scene["id"]]
    assert res["scenes"][scene["id"]]["chapter_id"] == cb  # back-pointer follows


def test_reorder_rejects_unknown_or_missing_ids(store):
    service, *_ = store
    ms = run(service.create_manuscript("Work"))
    run(service.add_chapter(ms["id"], "A"))
    ca = run(service.get_manuscript(ms["id"]))["chapters"][0]["id"]
    scene = run(service.add_scene(ms["id"], ca, "S"))
    # dropping the scene from the outline is not allowed (would silently orphan it)
    with pytest.raises(ValueError):
        run(service.reorder(ms["id"], [{"id": ca, "title": "A", "scene_ids": []}]))
    # inventing a scene id is not allowed
    with pytest.raises(ValueError):
        run(service.reorder(ms["id"], [{"id": ca, "title": "A", "scene_ids": [scene["id"], "sc_ghost"]}]))
    # inventing a chapter id is not allowed
    with pytest.raises(ValueError):
        run(service.reorder(ms["id"], [{"id": "ch_ghost", "title": "X", "scene_ids": [scene["id"]]}]))


# ── export ───────────────────────────────────────────────────────────────────

def test_export_assembles_in_reading_order(store):
    service, *_ = store
    ms = run(service.create_manuscript("The Work", "A tale."))
    run(service.add_chapter(ms["id"], "Chapter One"))
    ch = run(service.get_manuscript(ms["id"]))["chapters"][0]["id"]
    run(service.add_scene(ms["id"], ch, "Opening", [
        blk("b1", "The drape softens the shoulder."),
        blk("b2", "It was evening."),
    ]))
    out = run(service.export_manuscript(ms["id"]))
    assert out["format"] == "markdown"
    assert "# The Work" in out["content"]
    assert "_A tale._" in out["content"]
    assert "## Chapter One" in out["content"]
    assert "### Opening" in out["content"]
    assert "The drape softens the shoulder." in out["content"]
    # chapter heading precedes the scene body
    assert out["content"].index("## Chapter One") < out["content"].index("The drape")
