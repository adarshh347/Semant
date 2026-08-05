"""
ATLAS T2 — the Scout: it may propose a pair, and it may do nothing else.

The Scout's whole value is that its output is UNTRUSTED. So the tests worth writing are not about
whether it proposes good pairs — nobody can assert that — but about the fence around it: it cannot
name a relation, cannot invent an image, cannot persist anything, and cannot produce an edge
without `compare_views` having ground one.

Every fixture is synthetic. No model is called: `RelationScout` is a seam and every test hands it
a reply.
"""
import re
from pathlib import Path

import pytest

from backend.services import atlas_scout as S


class FakeScout:
    """The seam, filled by hand. `propose` returns whatever the test wants the model to have said."""

    def __init__(self, payload=None, error=""):
        self.payload = payload
        self.last_error = error
        self.seen = None

    def propose(self, material):
        self.seen = list(material)
        return self.payload


def a_doc(**over):
    doc = {
        "_id": "atlas_t2",
        "nodes": [
            {"node_id": "n0", "post_id": "p1", "x": 0, "y": 0},
            {"node_id": "n1", "post_id": "p2", "x": 1, "y": 0},
            {"node_id": "n2", "post_id": "p3", "x": 2, "y": 0},
        ],
        "edges": [],
    }
    doc.update(over)
    return doc


def a_post(handle="one", marks=(), grounds=()):
    return {
        "photo_url": "https://example.invalid/1.jpg",
        "instagram_handle": handle,
        "visual_marks": [{"label": m, "source": "user_confirmed"} for m in marks],
        "grounds": [{"label": g, "source": "user"} for g in grounds],
    }


POSTS = {"p1": a_post("one", ["a balustrade"]),
         "p2": a_post("two", ["a rotunda"]),
         "p3": a_post("three", ["a crowd"])}


def candidates(*pairs):
    return {"candidates": [{"from": a, "to": b, "rationale": why} for a, b, why in pairs]}


# ── what the model is allowed to see ─────────────────────────────────────────

class TestMaterial:
    def test_gives_the_model_words_and_never_geometry(self):
        # A model handed coordinates starts describing what it "sees" in them, and it sees nothing.
        post = a_post("one", ["a balustrade"])
        post["visual_marks"][0].update({"geometry": {"kind": "polygon", "points": [[0, 0]]},
                                        "box": [0, 0, 1, 1], "mask": "…"})
        material = S.scout_material(a_doc(), {"p1": post, "p2": POSTS["p2"], "p3": POSTS["p3"]})
        blob = repr(material)
        assert "a balustrade" in blob
        for forbidden in ("geometry", "polygon", "box", "mask", "points"):
            assert forbidden not in blob

    def test_never_shows_a_quarantined_mark(self):
        # A suggestion nobody accepted is not something to reason from.
        post = a_post("one", [])
        post["visual_marks"] = [{"label": "a guess", "source": "model_suggested"}]
        material = S.scout_material(a_doc(), {"p1": post})
        assert material[0]["committed"] == []

    def test_keeps_an_unreadable_image_and_says_so(self):
        # Dropping it would let the model propose around a hole it cannot see.
        material = S.scout_material(a_doc(), {"p1": POSTS["p1"], "p2": POSTS["p2"]})
        assert [m["readable"] for m in material] == [True, True, False]

    def test_carries_the_node_ids_the_scout_must_answer_in(self):
        material = S.scout_material(a_doc(), POSTS)
        assert [m["node_id"] for m in material] == ["n0", "n1", "n2"]


# ── the fence ────────────────────────────────────────────────────────────────

class TestParseCandidates:
    ALLOWED = ("n0", "n1", "n2")

    def test_keeps_a_well_formed_pair(self):
        kept, drops = S.parse_candidates(
            candidates(("n0", "n1", "both hold a curved rail")), allowed=self.ALLOWED)
        assert kept == [{"from": "n0", "to": "n1", "rationale": "both hold a curved rail"}]
        assert drops == []

    def test_a_candidate_carries_three_keys_and_no_others(self):
        kept, _ = S.parse_candidates(candidates(("n0", "n1", "why")), allowed=self.ALLOWED)
        assert sorted(kept[0].keys()) == ["from", "rationale", "to"]

    @pytest.mark.parametrize("key,value", [
        ("role", "prepares"), ("relation", "echoes"), ("relation_role", "answers"),
        ("epistemic", "measured"), ("epistemic_status", "grounded"),
        ("confidence", 0.9), ("score", 3), ("geometry", {"kind": "line"}),
        ("mask", "…"), ("box", [0, 0, 1, 1]), ("mark_id", "mark_1"), ("spans", ["p1", "p2"]),
    ])
    def test_refuses_a_candidate_that_tried_to_name_the_relation(self, key, value):
        # THE guard. `compare_views` decides what the relation is, by looking at the marks. A name
        # accepted here would arrive on the canvas as though a comparison had been run.
        kept, drops = S.parse_candidates(
            {"candidates": [{"from": "n0", "to": "n1", "rationale": "why", key: value}]},
            allowed=self.ALLOWED)
        assert kept == []
        assert drops[0]["reason"] == S.DROPPED_NAMED_A_RELATION
        assert key in drops[0]["detail"]

    def test_refuses_an_image_this_atlas_does_not_hold(self):
        kept, drops = S.parse_candidates(
            candidates(("n0", "n9", "a hunch about something off-canvas")), allowed=self.ALLOWED)
        assert kept == []
        assert drops[0]["reason"] == S.DROPPED_UNKNOWN_NODE
        assert "n9" in drops[0]["detail"]

    def test_refuses_an_image_related_to_itself(self):
        kept, drops = S.parse_candidates(candidates(("n0", "n0", "why")), allowed=self.ALLOWED)
        assert kept == [] and drops[0]["reason"] == S.DROPPED_SAME_NODE

    def test_refuses_a_pair_with_no_reason(self):
        # The rationale is the only thing that lets a writer judge a candidate before spending a
        # model run on it, which is what a candidate is for.
        kept, drops = S.parse_candidates(candidates(("n0", "n1", "  ")), allowed=self.ALLOWED)
        assert kept == [] and drops[0]["reason"] == S.DROPPED_NO_RATIONALE

    def test_collapses_the_same_pair_proposed_twice(self):
        kept, drops = S.parse_candidates(
            candidates(("n0", "n1", "first"), ("n1", "n0", "the same thing backwards")),
            allowed=self.ALLOWED)
        assert len(kept) == 1
        assert drops[0]["reason"] == S.DROPPED_DUPLICATE

    def test_does_not_re_propose_a_pair_already_grounded(self):
        kept, drops = S.parse_candidates(
            candidates(("n0", "n1", "why")), allowed=self.ALLOWED,
            already={frozenset(("n0", "n1"))})
        assert kept == [] and drops[0]["reason"] == S.DROPPED_ALREADY_DRAWN

    def test_every_drop_is_reported_never_silent(self):
        # Following `groq_planner`'s guard: a quiet filter would hide how often the model invents
        # nodes, and that count is the observable that says whether to trust the Scout.
        kept, drops = S.parse_candidates(
            {"candidates": [
                {"from": "n0", "to": "n9", "rationale": "invented"},
                {"from": "n0", "to": "n0", "rationale": "itself"},
                {"from": "n0", "to": "n1", "rationale": ""},
                {"from": "n1", "to": "n2", "rationale": "kept"},
            ]}, allowed=self.ALLOWED)
        assert len(kept) == 1
        assert len(drops) == 3

    def test_holds_the_canvas_to_a_readable_number_of_lines(self):
        many = {"candidates": [{"from": "n0", "to": f"n{i}", "rationale": "why"}
                               for i in range(1, 40)]}
        kept, _ = S.parse_candidates(many, allowed=[f"n{i}" for i in range(40)], limit=3)
        assert len(kept) == 3

    def test_a_reply_that_is_not_a_list_is_said_rather_than_crashed(self):
        kept, drops = S.parse_candidates({"candidates": "sure!"}, allowed=self.ALLOWED)
        assert kept == [] and drops[0]["reason"] == "unparseable"

    def test_a_long_rationale_is_cut_rather_than_refused(self):
        kept, _ = S.parse_candidates(candidates(("n0", "n1", "x" * 5000)), allowed=self.ALLOWED)
        assert len(kept[0]["rationale"]) == S.MAX_RATIONALE_CHARS


# ── the gesture ──────────────────────────────────────────────────────────────

class TestProposeRelations:
    def test_returns_candidates_over_a_readable_corpus(self):
        out = S.propose_relations(a_doc(), POSTS,
                                  scout=FakeScout(candidates(("n0", "n1", "both curve"))))
        assert out["candidates"][0]["from"] == "n0"
        assert "refused" not in out

    def test_refuses_when_there_is_nothing_to_compare(self):
        out = S.propose_relations(a_doc(), {"p1": POSTS["p1"]}, scout=FakeScout(candidates()))
        assert out["refused"]["reason"] == S.REFUSED_TOO_FEW_IMAGES

    def test_says_unavailable_rather_than_proposing_nothing(self):
        # These are different claims in the same words. "Nothing worth comparing" is a real answer
        # about the corpus; a dead API returning it silently would be a lie told identically.
        out = S.propose_relations(a_doc(), POSTS,
                                  scout=FakeScout(None, error="GROQ_API_KEY unset"))
        assert out["refused"]["reason"] == S.REFUSED_MODEL_UNAVAILABLE
        assert "GROQ_API_KEY" in out["refused"]["detail"]

    def test_an_honest_empty_reply_is_its_own_refusal(self):
        out = S.propose_relations(a_doc(), POSTS, scout=FakeScout(candidates()))
        assert out["refused"]["reason"] == S.REFUSED_NOTHING_PROPOSED

    def test_reports_what_it_dropped_alongside_what_it_kept(self):
        out = S.propose_relations(a_doc(), POSTS, scout=FakeScout(
            candidates(("n0", "n1", "kept"), ("n0", "n7", "invented"))))
        assert len(out["candidates"]) == 1
        assert out["dropped"][0]["reason"] == S.DROPPED_UNKNOWN_NODE

    def test_does_not_re_propose_what_is_already_drawn(self):
        doc = a_doc(edges=[{"edge_id": "e1", "source_node": "n0", "target_node": "n1"}])
        out = S.propose_relations(doc, POSTS, scout=FakeScout(
            candidates(("n0", "n1", "already there"), ("n1", "n2", "new"))))
        assert [c["to"] for c in out["candidates"]] == ["n2"]

    def test_the_scout_only_ever_sees_nodes_on_this_atlas(self):
        scout = FakeScout(candidates(("n0", "n1", "why")))
        S.propose_relations(a_doc(), POSTS, scout=scout)
        assert [m["node_id"] for m in scout.seen] == ["n0", "n1", "n2"]


# ── the wall: a candidate cannot become an edge except through the gate ──────

def test_the_scout_writes_nothing_anywhere():
    """No database call of any kind in the Scout, and it may not call C3's committing helpers.

    A candidate is session material. If this module could write, a ghost would have a path into the
    document that never passed `compare_views` — the one thing T2 must make impossible.
    """
    root = Path(__file__).resolve().parent.parent
    source = (root / "services/atlas_scout.py").read_text(encoding="utf-8")
    writes = re.compile(r"\.\s*(insert_one|insert_many|update_one|update_many|replace_one|"
                        r"delete_one|delete_many|find_one_and_\w+|bulk_write)\s*\(")
    assert not writes.findall(source)
    for forbidden in ("add_edge", "commit_relation_to_posts", "committed_relation", "edge_entry"):
        assert forbidden not in source, f"the Scout must not call {forbidden}"


def test_there_is_no_route_that_turns_a_candidate_into_an_edge():
    """The scout route reads and returns. Only C3's `/relations` may mint an edge.

    Checked in the source because it is a claim about the SHAPE of the API: a second route that
    accepted a candidate and wrote an edge would be a way to draw a line between two photographs
    without ever looking at them, and no single function would announce it.
    """
    root = Path(__file__).resolve().parent.parent
    router = (root / "routers/atlas.py").read_text(encoding="utf-8")
    scout_route = router.split('@router.post("/{atlas_id}/scout")')[1].split("@router")[0]
    for forbidden in ("add_edge", "commit_relation_to_posts", "committed_relation",
                      "edge_entry", "relate("):
        assert forbidden not in scout_route, \
            f"the scout route must not call {forbidden} — grounding is C3's gate"


def test_a_relation_is_committed_in_exactly_one_place():
    """T2 adds no second grounding path: confirming reuses C3's `POST /{atlas_id}/relations`.

    The frontend half (confirming a ghost calls `drawRelation`) is pinned in
    `atlasScout.dom.test.jsx`; this is the server half.
    """
    root = Path(__file__).resolve().parent.parent
    router = (root / "routers/atlas.py").read_text(encoding="utf-8")
    minting = [line for line in router.splitlines() if "R.commit_relation_to_posts" in line]
    assert len(minting) == 1, "a relation must be committed in exactly one place"
