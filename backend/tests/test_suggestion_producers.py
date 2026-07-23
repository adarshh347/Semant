"""
CIRCUIT-001 P4-A — real suggestion producers (SAM refine + semantic read).

Two layers, no model ever called:
  - PURE: suggestion_service maps a fixture region / fixture semantics → suggestion descriptors
    with complete, run-linked provenance (model + run_id present, producer named). Geometry honesty:
    a SAM suggestion references a mask (raster_mask), a label references a region (region_ref, no
    pixels), a relation is `derived`.
  - ROUTE: the refine-suggest route mints a real run and returns quarantined suggestions WITHOUT
    persisting anything; semantic-read gains an additive `suggestions` field. Reuses the fake
    collection harness (no DB, no network) — same idiom as test_circulation_spine_p2_1.
"""
import copy
import pytest
from bson.objectid import ObjectId

from backend.services import suggestion_service as ss
from backend.services import vision_run_service as svc
from backend.services import semantic_pass
from backend.routers import posts as R
from backend.tests.test_circulation_spine_p1 import FakeCollection, run
from backend.tests.test_circulation_spine_p2_1 import _Posts, _img


# ─────────────────────────── PURE: producer 1 (SAM) ──────────────────────────

def test_sam_region_becomes_a_run_linked_region_mask_suggestion():
    region = {"id": "reg_7", "label": "collar", "geometry_rev": 3}
    d = ss.suggestion_from_refine_region(region, run_id="run_abc", latency_ms=42.0, base_id="reg_7")
    assert d["producer"] == "sam_refine" and d["type"] == "region_mask"
    # geometry references the mask SAM produced — never inline pixels
    assert d["geometry"]["kind"] == "raster_mask"
    assert d["geometry"]["mask_ref"] == {"region_id": "reg_7", "geometry_rev": 3}
    # provenance is a complete receipt
    p = d["provenance"]
    assert p["model"] == "sam2.1" and p["run_id"] == "run_abc" and p["producer"] == "sam_refine"
    assert p["adapter"] == "sam2" and p["latency_ms"] == 42.0
    assert d["source_ref"] == "reg_7"       # idempotency key part


def test_sam_suggestion_needs_a_region_id():
    assert ss.suggestion_from_refine_region({"label": "x"}, run_id="r") is None


# ───────────────────────── PURE: producer 2 (semantic) ───────────────────────

def _semantics():
    return {
        "assertions": [
            {"candidate_id": "reg_1", "label": "sleeve", "status": "proposed", "model": "vlm-x"},
            {"candidate_id": "reg_2", "label": "button", "status": "rejected"},       # skipped
            {"candidate_id": "reg_3", "curator_label": "lapel", "label": "collar", "status": "overridden"},
        ],
        "relations": [
            {"from_id": "reg_1", "to_id": "reg_3", "relation": "echoes"},
            {"from_id": "reg_1", "to_id": "reg_3", "relation": "beside"},
            {"from_id": "reg_9", "to_id": None, "relation": "x"},                      # skipped
        ],
        "meta": {"model": "vlm-default"},
    }


def test_semantic_labels_become_region_ref_suggestions_no_geometry_authored():
    ds = ss.suggestions_from_semantics(_semantics(), run_id="run_sem")
    labels = [d for d in ds if d["type"] == "region_mask"]
    assert len(labels) == 2                                 # rejected assertion is not re-suggested
    for d in labels:
        assert d["geometry"]["kind"] == "region_ref"        # the VLM's law: names, never draws
        assert "region_id" in d["geometry"]["region_ref"]
        assert "pixels" not in d["geometry"] and "mask_ref" not in d["geometry"]
        assert d["provenance"]["run_id"] == "run_sem" and d["provenance"]["producer"] == "semantic_read"
    # curator-edited label rides through
    assert any(d["label"] == "lapel" for d in labels)
    # per-assertion model wins over the meta default when present
    assert any(d["provenance"]["model"] == "vlm-x" for d in labels)


def test_semantic_relations_become_derived_relation_marks_with_mapped_roles():
    ds = ss.suggestions_from_semantics(_semantics(), run_id="run_sem")
    rels = [d for d in ds if d["type"] == "relation_mark"]
    assert len(rels) == 2                                   # missing-endpoint relation skipped
    by_label = {d["label"]: d for d in rels}
    assert by_label["echoes"]["role"] == "motif_echo"       # keyword → frozen relation_role
    assert by_label["beside"]["role"] == "address_relation"
    for d in rels:
        assert d["geometry"] == {"kind": "derived"}
        assert d["linked_ground_ids"] == ["reg_1", "reg_3"]


def test_relation_role_mapping_defaults_safely():
    assert ss.relation_role_for("same-material-as") == "similarity"
    assert ss.relation_role_for("totally unknown gibberish") == "address_relation"  # valid default
    assert ss.relation_role_for(None) == "address_relation"


def test_empty_semantics_yields_no_suggestions():
    assert ss.suggestions_from_semantics(None, run_id="r") == []
    assert ss.suggestions_from_semantics({}, run_id="r") == []


# ─────────────────────────── ROUTE: refine-suggest ───────────────────────────

def _install_refine_suggest(monkeypatch, posts, runs):
    region = {"id": "r1", "label": "collar", "mask_rle": {"size": [8, 8], "counts": "MASK"},
              "geometry_rev": 3, "proposed": True}

    async def _propose(post_id, req):
        return posts.post["_id"], copy.deepcopy(posts.post), copy.deepcopy(region)
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(R, "_propose_refined_region", _propose)
    monkeypatch.setattr(svc, "vision_run_collection", runs)


def test_refine_suggest_mints_run_and_returns_quarantined_suggestion_without_persisting(monkeypatch):
    posts = _Posts({"_id": ObjectId(), "region_annotations": []})
    runs = FakeCollection()
    _install_refine_suggest(monkeypatch, posts, runs)

    resp = run(R.refine_region_suggest(str(posts.post["_id"]), R.RefineRequest(base_id="r1")))

    # a real run backs the suggestion's run_id
    assert isinstance(resp["run_id"], str)
    assert len(resp["suggestions"]) == 1
    sug = resp["suggestions"][0]
    assert sug["producer"] == "sam_refine" and sug["provenance"]["run_id"] == resp["run_id"]
    assert sug["provenance"]["model"] == "sam2.1"
    # NOTHING was persisted — a suggestion is a proposal, not a write
    assert posts.writes == []
    # the run terminalized as a suggestion (no persist stage)
    proj = run(svc.get_run(resp["run_id"], collection=runs))
    assert proj["operation"] == "refine" and proj["status"] == "succeeded"
    assert proj["terminal_reason"] == "suggested"


# ─────────────────────── ROUTE: semantic-read + suggestions ───────────────────

def _install_semantic(monkeypatch, posts, runs):
    async def _run_sem(post, img, *, intent="name", force=False):
        return {"assertions": [{"candidate_id": "r1", "label": "sleeve"}],
                "relations": [{"from_id": "r1", "to_id": "r1", "relation": "echoes"}],
                "meta": {"status": "ready", "model": "vlm-test"}}
    monkeypatch.setattr(semantic_pass, "run_semantic", _run_sem)
    monkeypatch.setattr(semantic_pass, "merge_curator_state", lambda new, prior: new)
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(R, "_fetch_post_image_cached", _img)
    monkeypatch.setattr(svc, "vision_run_collection", runs)


def test_semantic_read_returns_run_linked_suggestions_additively(monkeypatch):
    posts = _Posts({"_id": ObjectId(),
                    "region_annotations": [{"id": "r1", "mask_rle": {"size": [4, 4], "counts": "M"}}],
                    "semantics": None})
    runs = FakeCollection()
    _install_semantic(monkeypatch, posts, runs)

    resp = run(R.semantic_read(str(posts.post["_id"]), R.SemanticReadRequest(intent="name")))

    # the persisted semantics is unchanged; suggestions is the additive projection
    assert resp["semantics"]["assertions"][0]["candidate_id"] == "r1"
    assert isinstance(resp["run_id"], str)
    sugs = resp["suggestions"]
    assert any(s["type"] == "region_mask" and s["geometry"]["kind"] == "region_ref" for s in sugs)
    assert any(s["type"] == "relation_mark" for s in sugs)
    for s in sugs:
        assert s["provenance"]["run_id"] == resp["run_id"]
        assert s["provenance"]["producer"] == "semantic_read"
    # geometry was never written (only semantics) — the producer authored no pixels
    assert posts.writes and all(set(w.keys()) == {"semantics"} for w in posts.writes)
