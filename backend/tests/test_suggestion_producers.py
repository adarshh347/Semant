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


# ─────────────── PURE: producer 4 (negative_space — the first brush_field) ───────────────
# Model-free: it inverts a mask ALREADY in the packet. No segmenter, no adapter, no GPU.

from backend.services import mask_geometry as mg


def _rect_region(region_id="reg_ns", label="figure", *, h=8, w=8):
    """A region carrying a real central-rectangle figure mask (mask_rle)."""
    bits = bytearray(h * w)
    for r in range(h):
        for c in range(w):
            if 2 <= r <= 5 and 2 <= c <= 5:
                bits[r * w + c] = 1
    return {"id": region_id, "label": label, "mask_rle": mg.rle_encode(bits, h, w)}


def test_negative_space_region_becomes_a_run_linked_brush_field_suggestion():
    d = ss.suggestion_from_negative_space(_rect_region(), run_id="run_ns")
    assert d is not None
    assert d["producer"] == "negative_space" and d["type"] == "brush_field"
    assert d["role"] == "negative_space"                      # a valid field role
    assert d["source_ref"] == "reg_ns"                        # idempotency key part
    # geometry is a soft field carrying EDITABLE strokes, never inline pixels
    assert d["geometry"]["kind"] == "soft_mask"
    strokes = d["geometry"]["strokes"]
    assert strokes and all(s["op"] == "add" for s in strokes)
    assert all(0.0 <= s["points"][0][0] <= 1.0 and 0.0 <= s["points"][0][1] <= 1.0 for s in strokes)
    # the receipt: a run, a producer — but NO model/adapter/checkpoint (nothing was inferred)
    p = d["provenance"]
    assert p["run_id"] == "run_ns" and p["producer"] == "negative_space"
    assert "model" not in p and "adapter" not in p and "checkpoint" not in p
    # the label speaks about the figure it is the negative of
    assert "negative space" in d["label"]


def test_negative_space_refuses_a_region_with_no_mask():
    # no mask_rle at all → nothing to invert → refuse (fail-closed), never fabricate a field
    assert ss.suggestion_from_negative_space({"id": "reg_x", "label": "bare"}, run_id="run_ns") is None
    # a region with no id cannot be referenced → refuse
    assert ss.suggestion_from_negative_space({"mask_rle": _rect_region()["mask_rle"]}, run_id="run_ns") is None


def test_negative_space_refuses_when_the_field_has_nothing_to_draw():
    # an all-figure mask leaves no negative space; a full-frame figure → empty field → no strokes → refuse
    h = w = 6
    full = {"id": "reg_full", "mask_rle": mg.rle_encode(bytearray([1] * (h * w)), h, w)}
    assert ss.suggestion_from_negative_space(full, run_id="run_ns") is None


def test_negative_space_list_skips_maskless_regions_and_empty_input():
    regions = [_rect_region("reg_a"), {"id": "reg_b"}, _rect_region("reg_c")]
    out = ss.suggestions_from_negative_space(regions, run_id="run_ns")
    assert [d["source_ref"] for d in out] == ["reg_a", "reg_c"]      # maskless reg_b skipped
    assert ss.suggestions_from_negative_space([], run_id="run_ns") == []
    assert ss.suggestions_from_negative_space(None, run_id="run_ns") == []


# ─────────────── PURE: producer 5 (material_field — DINOv2 same-material) ───────────────
# Fake-driven: a synthetic patch grid stands in for DINOv2 output, so no GPU is needed in CI.

def _fake_features(grid=4):
    """A grid×grid patch grid split top/bottom into two 'materials' (A up, B down)."""
    a, b = [1.0, 0.0], [0.0, 1.0]
    patches = []
    for gy in range(grid):
        for gx in range(grid):
            patches.append(a if gy < grid // 2 else b)
    return {"patches": patches, "grid": grid}


def test_material_tap_becomes_a_run_linked_brush_field_with_a_full_receipt():
    feats = _fake_features(4)
    # tap the top-left → material A; A fills the top half of the frame
    d = ss.suggestion_from_material(
        feats, (0.1, 0.1), run_id="run_mat", region_id="reg_9",
        model="facebook/dinov2-small", checkpoint="facebook/dinov2-small",
        preprocessing_version="dino-v1", latency_ms=18.0, peak_vram_mib=104.0)
    assert d is not None
    assert d["producer"] == "material_field" and d["type"] == "brush_field"
    assert d["role"] == "material_field"
    assert d["geometry"]["kind"] == "soft_mask"
    strokes = d["geometry"]["strokes"]
    assert strokes and all(s["op"] == "add" for s in strokes)
    # the receipt is FULL — this one really inferred
    p = d["provenance"]
    assert p["run_id"] == "run_mat" and p["producer"] == "material_field"
    assert p["adapter"] == "dinov2_vits14" and p["model"] == "facebook/dinov2-small"
    assert p["checkpoint"] == "facebook/dinov2-small" and p["preprocessing_version"] == "dino-v1"
    assert p["latency_ms"] == 18.0 and p["peak_vram_mib"] == 104.0
    # confidence NEVER rides on the mark's provenance (contract §6) — it lives on the descriptor
    assert "confidence" not in p
    assert 0.0 <= d["confidence"] <= 1.0
    # idempotency key folds the tapped patch cell → a re-tap on the same cell replaces
    assert d["source_ref"].startswith("reg_9@")


def test_material_confidence_is_the_field_contrast_and_stays_off_the_mark():
    d = ss.suggestion_from_material(_fake_features(4), (0.1, 0.1), run_id="r", region_id="x")
    # a two-material grid has full contrast → confidence ≈ 1
    assert d["confidence"] == pytest.approx(1.0, abs=1e-6)
    assert "confidence" not in d["provenance"]


def test_material_refuses_no_seed_and_out_of_frame_seed():
    feats = _fake_features(4)
    assert ss.suggestion_from_material(feats, None, run_id="r") is None
    assert ss.suggestion_from_material(feats, (0.5,), run_id="r") is None       # malformed
    assert ss.suggestion_from_material(feats, (1.5, 0.2), run_id="r") is None   # outside [0,1]


def test_material_refuses_empty_or_malformed_features():
    assert ss.suggestion_from_material(None, (0.5, 0.5), run_id="r") is None
    assert ss.suggestion_from_material({}, (0.5, 0.5), run_id="r") is None
    assert ss.suggestion_from_material({"grid": 0, "patches": []}, (0.5, 0.5), run_id="r") is None


def test_material_refuses_a_near_uniform_field():
    # every patch is the SAME material → cosine ≈ 1 everywhere → nothing distinguished → refuse
    grid = 4
    uniform = {"patches": [[1.0, 0.0]] * (grid * grid), "grid": grid}
    assert ss.suggestion_from_material(uniform, (0.5, 0.5), run_id="r") is None


def test_material_list_skips_refusing_seeds_and_empty_input():
    feats = _fake_features(4)
    seeds = [(0.1, 0.1), (1.9, 0.1), (0.1, 0.9)]      # middle seed is out-of-frame → skipped
    out = ss.suggestions_from_material(feats, seeds, run_id="r", region_id="reg_9")
    assert len(out) == 2
    assert ss.suggestions_from_material(feats, [], run_id="r") == []
    assert ss.suggestions_from_material(feats, None, run_id="r") == []
