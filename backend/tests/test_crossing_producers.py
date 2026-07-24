"""
CIRCUIT-001 P5-A — the crossing: find-similar as a producer.

A find-similar neighbour lives on ANOTHER post. It enters the circuit as an evidence-SUGGESTION
(Invariant 4), never an assertion, and never a copy of the neighbour's geometry — only a REFERENCE
across the border ({post_id, region_id, geometry_rev}). Two layers, no model ever called:

  - PURE: suggestion_service maps a fixture research packet → cross-post `region_ref` descriptors
    with complete, run-linked provenance. Border honesty: the geometry references the neighbour by
    id, carrying its rev-at-citation for staleness — never inline pixels, never a mask copy.
  - ROUTE: the recorded find-similar route gains an additive `suggestions` field, computed from the
    same research packet, without writing any post state. Reuses the P2.1 fake-collection harness.
"""
import pytest
from bson.objectid import ObjectId

from backend.services import suggestion_service as ss
from backend.services import vision_run_service as svc
from backend.routers import posts as R
from backend.tests.test_circulation_spine_p1 import FakeCollection, run
from backend.tests.test_circulation_spine_p2_1 import _Posts, _install_find_similar, _fs_post


# ─────────────────────────────── PURE: find-similar ──────────────────────────

def _packet(status="ready"):
    return {
        "status": status, "space": "evidence_identity", "mode": "identity",
        "results": [
            {"post_id": "post_B", "region_id": "reg_9", "label": "lapel", "score": 0.91,
             "geometry": {"mask_rle": {"size": [8, 8], "counts": "MASK"}},   # present, but NEVER copied
             "provenance": {"model": "dinov2_vits14", "geometry_rev": 3}},
            {"post_id": "post_C", "region_id": "reg_2", "label": "", "score": 0.77,
             "provenance": {"model": "dinov2_vits14"}},                      # no rev — omitted, not faked
        ],
    }


def test_neighbours_become_cross_post_region_ref_suggestions():
    ds = ss.suggestions_from_similar(_packet(), run_id="run_fs")
    assert len(ds) == 2
    d = ds[0]
    assert d["producer"] == "find_similar" and d["type"] == "region_mask"
    # the border reference — a reference, never a copy
    assert d["geometry"]["kind"] == "region_ref"
    assert d["geometry"]["region_ref"] == {"region_id": "reg_9", "post_id": "post_B", "geometry_rev": 3}
    # NO geometry crosses the border: no pixels, no mask, despite the neighbour carrying an rle
    assert "mask_rle" not in d["geometry"] and "mask_ref" not in d["geometry"] and "pixels" not in d["geometry"]
    # a complete, run-linked receipt
    p = d["provenance"]
    assert p["run_id"] == "run_fs" and p["producer"] == "find_similar" and p["model"] == "dinov2_vits14"
    # idempotency key is the border target
    assert d["source_ref"] == "post_B:reg_9"


def test_missing_rev_is_omitted_not_invented():
    ds = ss.suggestions_from_similar(_packet(), run_id="run_fs")
    second = ds[1]
    assert "geometry_rev" not in second["geometry"]["region_ref"]     # cannot claim a rev → does not
    assert second["geometry"]["region_ref"] == {"region_id": "reg_2", "post_id": "post_C"}


def test_a_neighbour_without_a_source_is_not_citable():
    packet = {"status": "ready", "results": [{"score": 0.5}, {"post_id": "p"}, {"region_id": "r"}]}
    assert ss.suggestions_from_similar(packet, run_id="run_fs") == []


def test_degraded_or_empty_research_yields_no_suggestions():
    assert ss.suggestions_from_similar(_packet("unavailable"), run_id="r") == []
    assert ss.suggestions_from_similar({"status": "error", "results": []}, run_id="r") == []
    assert ss.suggestions_from_similar(None, run_id="r") == []
    assert ss.suggestions_from_similar({}, run_id="r") == []


# ─────────────────────────────── ROUTE: find-similar ─────────────────────────

def test_find_similar_route_gains_additive_suggestions_without_writing_post_state(monkeypatch):
    result = {"status": "ready", "space": "evidence_identity", "mode": "identity",
              "results": [{"post_id": "post_B", "region_id": "reg_9", "label": "lapel", "score": 0.9,
                           "provenance": {"model": "dinov2_vits14", "geometry_rev": 3}}]}
    posts, runs = _Posts(_fs_post()), FakeCollection()
    _install_find_similar(monkeypatch, posts, runs, result)

    resp = run(R.find_similar(str(posts.post["_id"]), "r1", R.FindSimilarRequest(mode="identity", top_k=8)))

    # research is unchanged; suggestions is the additive cross-post projection
    assert resp["status"] == "ready" and len(resp["results"]) == 1
    sugs = resp["suggestions"]
    assert len(sugs) == 1
    s = sugs[0]
    assert s["producer"] == "find_similar"
    assert s["geometry"]["region_ref"]["post_id"] == "post_B"
    assert s["provenance"]["run_id"] == resp["run_id"]        # the crossing's receipt is the run
    # a suggestion is a proposal, never a write — no post state mutated by the crossing
    assert posts.writes == []


def test_find_similar_route_degraded_carries_no_suggestions(monkeypatch):
    result = {"status": "unavailable", "space": "evidence_identity", "reason": "no index", "results": []}
    posts, runs = _Posts(_fs_post()), FakeCollection()
    _install_find_similar(monkeypatch, posts, runs, result)
    resp = run(R.find_similar(str(posts.post["_id"]), "r1", R.FindSimilarRequest()))
    assert resp["suggestions"] == []                          # nothing to suggest from a degraded search
