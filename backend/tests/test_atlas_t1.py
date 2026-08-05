"""
ATLAS T1 — the author-notes slot, and the wall between the two lanes.

T1 adds exactly one new kind of data to the Atlas document: freehand notes the writer types under
an image. The tests that matter are therefore not about storage — they are about what a note is
NOT. A note is not a percept, not evidence, not citable, carries no epistemic status, and can
never become one. `assert_no_percept_data` is the enforcement, and it has to keep passing after a
document has notes in it, including when a client tries to smuggle geometry through the slot.

Every fixture is synthetic.
"""
import asyncio
import re
from pathlib import Path

import pytest

from backend.services import atlas_service as A


def run(coro):
    """House style: sync tests over `asyncio.run`. There is no pytest-asyncio in this project."""
    return asyncio.run(coro)


class FakeCollection:
    """The tiny in-memory stand-in the C1 tests use — `collection` is injectable for this reason."""

    def __init__(self, docs=None):
        self.docs = {d["_id"]: dict(d) for d in (docs or [])}

    async def insert_one(self, doc):
        self.docs[doc["_id"]] = dict(doc)

    async def find_one(self, query):
        doc = self.docs.get(query.get("_id"))
        return dict(doc) if doc else None

    async def update_one(self, query, update):
        doc = self.docs.get(query.get("_id"))
        if doc:
            doc.update(update.get("$set") or {})


def a_doc(**over):
    doc = A.new_atlas_doc(atlas_id="atlas_t1", corpus_ref=["p1", "p2"],
                          post_ids=["p1", "p2"], title="the walk", now="2026-01-01T00:00:00Z")
    doc.update(over)
    return doc


# ── a fresh node has the slot ────────────────────────────────────────────────

def test_a_new_node_starts_with_an_empty_notes_slot():
    # Present from the start, so "no notes yet" and "written before notes existed" read the same.
    assert all(n["notes"] == [] for n in A.default_nodes(["p1", "p2"]))


# ── what a note is allowed to be ─────────────────────────────────────────────

class TestCleanNote:
    def test_keeps_the_text_and_mints_an_id(self):
        note = A.clean_note({"text": "the light does the arguing here"})
        assert note["text"] == "the light does the arguing here"
        assert note["note_id"].startswith("note_")

    def test_keeps_an_id_the_client_already_has(self):
        assert A.clean_note({"note_id": "note_abc", "text": "hm"})["note_id"] == "note_abc"

    def test_a_bare_string_is_a_note(self):
        assert A.clean_note("just a line")["text"] == "just a line"

    def test_blank_text_is_not_a_note(self):
        # An emptied slot is how a curator DELETES a note; storing it would leave an invisible row.
        assert A.clean_note({"text": "   "}) is None
        assert A.clean_note({"text": ""}) is None

    def test_text_that_is_not_text_is_not_a_note(self):
        assert A.clean_note({"text": {"box": [0, 0, 1, 1]}}) is None
        assert A.clean_note({"text": 42}) is None
        assert A.clean_note(None) is None

    def test_a_very_long_note_is_cut_rather_than_refused(self):
        note = A.clean_note({"text": "x" * 5000})
        assert len(note["text"]) == A.MAX_NOTE_CHARS

    def test_everything_except_id_and_text_is_dropped(self):
        # THE test for this slot. A note is BUILT from two known fields, never edited down from
        # what arrived — so percept data has no path in, whatever it is called.
        note = A.clean_note({
            "text": "looks like a mask", "note_id": "note_1",
            "geometry": {"kind": "polygon"}, "box": [0, 0, 1, 1], "mask": "…",
            "epistemic_status": "grounded", "source": "user_confirmed", "provenance": {"run": 1},
        })
        assert set(note.keys()) == {"note_id", "text"}


# ── saving notes ─────────────────────────────────────────────────────────────

class TestMergeNotes:
    def test_writes_the_note_onto_the_named_node(self):
        nodes, refused = A.merge_notes(a_doc()["nodes"],
                                       [{"node_id": "n0", "notes": [{"text": "first"}]}])
        assert [n["text"] for n in nodes[0]["notes"]] == ["first"]
        assert refused == []

    def test_leaves_every_other_node_alone(self):
        nodes, _ = A.merge_notes(a_doc()["nodes"], [{"node_id": "n0", "notes": [{"text": "a"}]}])
        assert nodes[1]["notes"] == []

    def test_replaces_the_slot_wholesale_so_editing_and_deleting_are_one_path(self):
        doc = a_doc()
        nodes, _ = A.merge_notes(doc["nodes"], [{"node_id": "n0", "notes": [
            {"note_id": "note_1", "text": "one"}, {"note_id": "note_2", "text": "two"}]}])
        nodes, _ = A.merge_notes(nodes, [{"node_id": "n0", "notes": [
            {"note_id": "note_1", "text": "one, edited"}]}])
        assert [n["text"] for n in nodes[0]["notes"]] == ["one, edited"]

    def test_never_moves_a_node(self):
        # The mirror of `merge_nodes` carrying no note: neither gesture can perform the other.
        doc = a_doc()
        before = {n["node_id"]: (n["x"], n["y"]) for n in doc["nodes"]}
        nodes, _ = A.merge_notes(doc["nodes"], [
            {"node_id": "n0", "notes": [{"text": "a"}], "x": 9999, "y": 9999}])
        assert {n["node_id"]: (n["x"], n["y"]) for n in nodes} == before

    def test_an_arrangement_save_cannot_write_a_note(self):
        nodes, _ = A.merge_nodes(a_doc()["nodes"],
                                 [{"node_id": "n0", "x": 10, "y": 20,
                                   "notes": [{"text": "smuggled"}]}])
        assert nodes[0]["notes"] == []

    def test_refuses_a_node_this_atlas_does_not_hold(self):
        nodes, refused = A.merge_notes(a_doc()["nodes"],
                                       [{"node_id": "n7", "notes": [{"text": "hi"}]}])
        assert refused[0]["reason"] == A.REFUSED_UNKNOWN_NODE
        assert len(nodes) == 2

    def test_says_when_a_note_had_no_text_rather_than_dropping_it_silently(self):
        nodes, refused = A.merge_notes(a_doc()["nodes"], [
            {"node_id": "n0", "notes": [{"text": "kept"}, {"text": "  "}]}])
        assert [n["text"] for n in nodes[0]["notes"]] == ["kept"]
        assert refused[0]["reason"] == A.REFUSED_BAD_NOTE

    def test_caps_the_slot_and_says_what_was_not_saved(self):
        over = A.MAX_NOTES_PER_NODE + 3
        nodes, refused = A.merge_notes(a_doc()["nodes"], [
            {"node_id": "n0", "notes": [{"text": f"note {i}"} for i in range(over)]}])
        assert len(nodes[0]["notes"]) == A.MAX_NOTES_PER_NODE
        assert refused[0]["reason"] == A.REFUSED_TOO_MANY_NOTES
        assert "3 not saved" in refused[0]["detail"]

    def test_refuses_a_notes_field_that_is_not_a_list(self):
        _, refused = A.merge_notes(a_doc()["nodes"], [{"node_id": "n0", "notes": "a string"}])
        assert refused[0]["reason"] == A.REFUSED_BAD_NOTE

    def test_a_refusal_does_not_discard_the_rest_of_the_save(self):
        nodes, refused = A.merge_notes(a_doc()["nodes"], [
            {"node_id": "n9", "notes": [{"text": "stale"}]},
            {"node_id": "n1", "notes": [{"text": "real"}]}])
        assert [n["text"] for n in nodes[1]["notes"]] == ["real"]
        assert len(refused) == 1


# ── the guard still holds, now over notes too ────────────────────────────────

class TestTheGuard:
    def test_a_document_with_notes_still_carries_no_percept_data(self):
        doc = a_doc()
        doc["nodes"], _ = A.merge_notes(doc["nodes"], [
            {"node_id": "n0", "notes": [{"text": "the light does the arguing"}]},
            {"node_id": "n1", "notes": [{"text": "compare with the rotunda"}]}])
        A.assert_no_percept_data(doc)          # must not raise

    def test_a_note_carrying_geometry_is_caught(self):
        # Hand-built past `clean_note`, which is the only way this shape could ever exist.
        doc = a_doc()
        doc["nodes"][0]["notes"] = [{"note_id": "n", "text": "x", "geometry": {"kind": "poly"}}]
        with pytest.raises(ValueError, match="author note"):
            A.assert_no_percept_data(doc)

    def test_a_note_carrying_an_epistemic_status_is_caught(self):
        # A note has no epistemic status by design: the five-way vocabulary says how well a claim
        # is GROUNDED, and a note claims nothing. Wearing one would smuggle it into the system.
        doc = a_doc()
        doc["nodes"][0]["notes"] = [{"note_id": "n", "text": "x", "epistemic_status": "grounded"}]
        with pytest.raises(ValueError, match="author note"):
            A.assert_no_percept_data(doc)

    def test_a_note_that_is_not_a_mapping_is_caught(self):
        doc = a_doc()
        doc["nodes"][0]["notes"] = ["a bare string that got past the door"]
        with pytest.raises(ValueError, match="not a note"):
            A.assert_no_percept_data(doc)


# ── the view carries notes, and only what a note is ──────────────────────────

class TestTheView:
    def test_a_node_hands_its_notes_to_the_surface(self):
        doc = a_doc()
        doc["nodes"], _ = A.merge_notes(doc["nodes"], [{"node_id": "n0", "notes": [{"text": "hm"}]}])
        view = A.atlas_view(doc, {"p1": {"photo_url": "https://example.invalid/1.jpg"}})
        assert [n["text"] for n in view["nodes"][0]["notes"]] == ["hm"]

    def test_an_unreadable_image_keeps_the_writer_s_notes(self):
        # A note is about the writer's thinking, not the ledger's contents — losing it because a
        # photograph went missing would delete the one thing the ledger never held.
        doc = a_doc()
        doc["nodes"], _ = A.merge_notes(doc["nodes"], [{"node_id": "n0", "notes": [{"text": "hm"}]}])
        view = A.atlas_view(doc, {})
        assert view["nodes"][0]["readable"] is False
        assert [n["text"] for n in view["nodes"][0]["notes"]] == ["hm"]

    def test_notes_are_never_counted_as_percepts(self):
        doc = a_doc()
        doc["nodes"], _ = A.merge_notes(doc["nodes"], [
            {"node_id": "n0", "notes": [{"text": "a"}, {"text": "b"}]}])
        node = A.atlas_view(doc, {"p1": {"photo_url": "x"}})["nodes"][0]
        assert node["grounds"] == [] and node["marks"] == [] and node["percepts"] == []
        assert node["withheld"] == 0

    def test_a_note_written_by_an_older_build_is_re_cleaned_on_the_way_out(self):
        doc = a_doc()
        doc["nodes"][0]["notes"] = [{"note_id": "n", "text": "ok", "box": [0, 0, 1, 1]}]
        node = A.atlas_view(doc, {"p1": {"photo_url": "x"}})["nodes"][0]
        assert set(node["notes"][0].keys()) == {"note_id", "text"}


# ── the store ────────────────────────────────────────────────────────────────

class TestSaveNotes:
    def test_persists_and_reads_back(self):
        coll = FakeCollection([a_doc()])
        res = run(A.save_notes("atlas_t1", [{"node_id": "n0", "notes": [{"text": "kept"}]}],
                               collection=coll))
        again = run(A.get_atlas("atlas_t1", collection=coll))
        assert [n["text"] for n in again["nodes"][0]["notes"]] == ["kept"]
        assert res["refused"] == []

    def test_refusals_travel_with_the_save(self):
        coll = FakeCollection([a_doc()])
        res = run(A.save_notes("atlas_t1", [{"node_id": "gone", "notes": [{"text": "x"}]}],
                               collection=coll))
        assert res["refused"][0]["reason"] == A.REFUSED_UNKNOWN_NODE

    def test_says_nothing_exists_rather_than_creating_one(self):
        assert run(A.save_notes("nope", [], collection=FakeCollection())) is None

    def test_a_smuggled_percept_never_reaches_the_database(self):
        # The guard runs BEFORE the write. A document that should not exist should not be stored
        # and then reported — `clean_note` already strips this, so reaching the raise means the
        # whitelist regressed.
        coll = FakeCollection([a_doc()])
        run(A.save_notes("atlas_t1",
                         [{"node_id": "n0", "notes": [{"text": "x", "mask": "…"}]}],
                         collection=coll))
        stored = run(A.get_atlas("atlas_t1", collection=coll))
        assert set(stored["nodes"][0]["notes"][0].keys()) == {"note_id", "text"}


# ── the wall, checked in the source ──────────────────────────────────────────

def test_the_atlas_still_never_writes_to_a_post():
    """T1 adds a write route. It writes to the ATLAS document — never to a post.

    The machine read is the other lane, and it goes through the existing Director, which produces
    into a quarantine on the post's own review surface. Nothing in the Atlas's own code may touch
    the ledger, and this is the check that stays true as the surface grows.
    """
    root = Path(__file__).resolve().parent.parent
    writes = re.compile(r"(post_collection|posts)\s*\.\s*"
                        r"(insert_one|insert_many|update_one|update_many|replace_one|"
                        r"delete_one|delete_many|find_one_and_\w+|bulk_write)")
    for name in ("routers/atlas.py", "services/atlas_service.py"):
        assert not writes.findall((root / name).read_text(encoding="utf-8")), \
            f"{name} writes to a post — the Atlas references the ledger, it never edits it"


def test_no_promotion_path_from_a_note_to_a_percept():
    """There is no code that turns an author note into evidence, and there must not be.

    A grep, deliberately. The rule is that the two lanes never merge, and the cheapest way to know
    it still holds is that the words never appear together — a function that read `notes` and
    emitted a ground would be the single change that collapses the distinction T1 is built on.
    """
    root = Path(__file__).resolve().parent.parent
    source = (root / "services/atlas_service.py").read_text(encoding="utf-8")
    promotion = re.compile(r"def\s+\w*(promote|note_to_\w+|notes_as_\w+)\w*\s*\(")
    assert not promotion.findall(source)
    # And notes never acquire the fields that would make them citable evidence.
    assert "note" not in A._FORBIDDEN_NODE_KEYS
    assert A._ALLOWED_NOTE_KEYS == frozenset({"note_id", "text"})
