"""
ATLAS C3 — the cross-image guard: a relation that spans two photographs is a finding in neither.

C3 commits a `compare_views` relation into BOTH endpoint posts, so either image's record can say
the comparison exists. This file is the payment of that debt, and it is deliberately paranoid: it
walks every surface that answers "what does THIS picture show" and pins that the answer excludes
the relation.

  the predicate reads what the producer already wrote     → §1
  no single-image COUNT includes a cross-image mark       → §2
  the relation is still THERE — withheld, never destroyed → §3
  a same-image relation is NOT cross-image                → §4

Every fixture is SYNTHETIC.
"""
from __future__ import annotations

import asyncio

import pytest

from backend.services import atlas_service as A
from backend.services import cross_image
from backend.services.director.corpus import build_corpus, hydrate_corpus, memory_from_post
from backend.services.director.capabilities import Resource


def a_native_mark(mark_id="m1", role="axis"):
    """A mark this photograph actually shows."""
    return {"id": mark_id, "type": "trace_mark", "role": role, "label": "the doorway",
            "source": "user", "status": "committed", "source_ref": mark_id,
            "geometry": {"kind": "path", "points": [[0.1, 0.1], [0.4, 0.4]]}}


def a_cross_image_relation(mark_id="vm_rel_1", spans=("p1", "p2")):
    """Exactly what `_run_compare_views` mints and C3 commits — both signals present."""
    return {"id": mark_id, "type": "relation_mark", "role": "kinship",
            "label": "echoes", "source": "user_confirmed", "status": "committed",
            "source_ref": f"{spans[0]}:m1→{spans[1]}:m2",
            "geometry": {"kind": "derived", "endpoints": [f"{spans[0]}:m1", f"{spans[1]}:m2"],
                         "cross_image": True},
            "corpus": {"corpus_id": "c1", "spans": list(spans)},
            "epistemic_status": "interpretive"}


def a_same_image_relation(mark_id="vm_rel_same"):
    """`connect_marks`' relation: two marks inside ONE frame. A claim about that frame."""
    return {"id": mark_id, "type": "relation_mark", "role": "kinship", "label": "leads to",
            "source": "user_confirmed", "status": "committed",
            "geometry": {"kind": "derived", "endpoints": ["m1", "m2"]}}


def a_post(post_id="p1", marks=()):
    return {"_id": post_id, "photo_url": f"https://example.invalid/{post_id}.jpg",
            "visual_marks": list(marks), "region_annotations": [], "grounds": [], "percepts": []}


# ── 1. the predicate ─────────────────────────────────────────────────────────

def test_either_signal_alone_is_enough():
    """The mark records the fact twice, and the check is generous on purpose: a native mark
    wrongly withheld is a visible absence somebody notices; a relation wrongly counted credits a
    photograph with evidence it does not hold, silently."""
    assert cross_image.is_cross_image(a_cross_image_relation()) is True
    assert cross_image.is_cross_image(
        {"geometry": {"cross_image": True}}) is True
    assert cross_image.is_cross_image(
        {"corpus": {"spans": ["p1", "p2"]}}) is True


def test_a_native_mark_is_not_cross_image():
    assert cross_image.is_cross_image(a_native_mark()) is False
    assert cross_image.is_cross_image(None) is False
    assert cross_image.is_cross_image("not a mark") is False


def test_one_span_is_not_a_span():
    """A `spans` list naming the same post twice relates nothing across anything."""
    assert cross_image.is_cross_image({"corpus": {"spans": ["p1"]}}) is False
    assert cross_image.is_cross_image({"corpus": {"spans": ["p1", "p1"]}}) is False


def test_splitting_keeps_both_halves():
    """Returned as a pair, never filtered in place — the relations are not noise, they are just
    not findings ABOUT this picture."""
    native, spanning = cross_image.split_marks(
        [a_native_mark("m1"), a_cross_image_relation(), a_native_mark("m2")])
    assert [m["id"] for m in native] == ["m1", "m2"]
    assert [m["id"] for m in spanning] == ["vm_rel_1"]


# ── 2. no single-image count includes it ─────────────────────────────────────

def test_the_atlas_node_does_not_count_a_relation_as_a_percept_of_its_image():
    """The node caption answers "what does THIS picture show". A relation to another picture is
    not part of that answer, however real it is."""
    node = {"node_id": "n0", "post_id": "p1", "x": 0, "y": 0}
    hydrated = A.hydrate_node(node, a_post("p1", [a_native_mark(), a_cross_image_relation()]))

    assert [m["id"] for m in hydrated["marks"]] == ["m1"]
    # and it is not silently gone: named, separately, as what it is
    assert [m["id"] for m in hydrated["relations"]] == ["vm_rel_1"]


def test_an_unreadable_node_still_answers_the_relations_question():
    hydrated = A.hydrate_node({"node_id": "n0", "post_id": "ghost"}, None)
    assert hydrated["relations"] == []


def test_a_single_image_packet_does_not_count_a_relation_as_a_mark():
    """This is the count `compare_views`' own two-mark requirement is checked against. A relation
    counted as native evidence would help satisfy the requirement for producing another relation —
    the gate grading its own output."""
    packet = memory_from_post(a_post("p1", [a_native_mark(), a_cross_image_relation()]),
                              post_id="p1")
    assert list(packet.mark_ids) == ["m1"]
    assert packet.available()[Resource.MARK] == 1


def test_a_corpus_packet_does_not_count_relations_either():
    corpus = build_corpus(corpus_id="c1", images=[{"post_id": "p1"}, {"post_id": "p2"}])
    memory = hydrate_corpus(corpus, {
        "p1": a_post("p1", [a_native_mark("m1"), a_cross_image_relation()]),
        "p2": a_post("p2", [a_native_mark("m2"), a_cross_image_relation()]),
    })
    # two native marks across the corpus, not four
    assert memory.available()[Resource.MARK] == 2


def test_a_relation_cannot_become_evidence_for_the_next_relation():
    """C3's guard applied to C3's own input: `committed_marks` is what `compare_views` is shown,
    and a relation it already produced must not come back as a mark to relate."""
    from backend.services import atlas_relation as R
    marks = R.committed_marks(a_post("p1", [a_native_mark(), a_cross_image_relation()]))
    assert [m["id"] for m in marks] == ["m1"]


def test_two_related_images_cannot_ground_a_second_relation_on_the_first():
    """End to end: relate p1 and p2, then try again on a corpus where the relation is all that is
    left. It must refuse rather than relate the relation to itself."""
    from backend.services import atlas_relation as R
    posts = [("p1", a_post("p1", [a_cross_image_relation()])),
             ("p2", a_post("p2", [a_cross_image_relation()]))]
    out = R.relate(posts, source_node="n0", target_node="n1")
    assert "relation" not in out
    assert out["refused"]["reason"] in (R.REFUSED_NOT_PLANNED, R.REFUSED_NOT_PRODUCED)


# ── 3. withheld, never destroyed ─────────────────────────────────────────────

def test_the_relation_is_still_in_the_ledger_after_the_guard_hides_it():
    """The guard is a DISPLAY and COUNT rule. The mark stays exactly where C3 put it, discoverable
    from either end — hiding it from a caption must never become deleting it."""
    post = a_post("p1", [a_native_mark(), a_cross_image_relation()])
    A.hydrate_node({"node_id": "n0", "post_id": "p1"}, post)
    memory_from_post(post, post_id="p1")
    assert [m["id"] for m in post["visual_marks"]] == ["m1", "vm_rel_1"]


def test_an_atlas_edge_can_still_find_the_relation_it_names():
    """Because the ledger still holds it — which is what makes the edge's words hydratable."""
    from backend.services import atlas_relation as R
    entry = R.edge_entry(mark_id="vm_rel_1", source_node="n0", target_node="n1",
                         spans=["p1", "p2"])
    hydrated = R.hydrate_edge(entry, {"p1": a_post("p1", [a_cross_image_relation()])})
    assert hydrated["live"] is True
    assert hydrated["role"] == "kinship"


# ── 4. a same-image relation is a finding about that image ───────────────────

def test_connect_marks_relation_stays_native():
    """Relating two marks inside one frame is a claim about that frame's internal structure, and
    it must keep counting as one. The guard is about SPAN, not about the word "relation"."""
    assert cross_image.is_cross_image(a_same_image_relation()) is False
    node = A.hydrate_node({"node_id": "n0", "post_id": "p1"},
                          a_post("p1", [a_same_image_relation()]))
    assert [m["id"] for m in node["marks"]] == ["vm_rel_same"]
    assert node["relations"] == []


def test_the_guard_is_about_span_not_about_type():
    packet = memory_from_post(a_post("p1", [a_same_image_relation()]), post_id="p1")
    assert packet.available()[Resource.MARK] == 1
