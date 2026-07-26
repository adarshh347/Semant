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


# ─────────────── ROUTE: the generic producer-invocation surface (P6-C) ───────────────
# One endpoint reaches every field producer. Fake-driven: negative_space is CPU (real mask);
# material is exercised by monkeypatching the DINOv2 manager path so CI needs no GPU.

def _masked_post(region_id="reg_ns", h=8, w=8):
    bits = bytearray(h * w)
    for r in range(h):
        for c in range(w):
            if 2 <= r <= 5 and 2 <= c <= 5:
                bits[r * w + c] = 1
    rle = mg.rle_encode(bits, h, w)
    return {"_id": ObjectId(), "region_annotations": [{"id": region_id, "label": "figure", "mask_rle": rle}]}


def test_produce_field_unknown_producer_is_a_400(monkeypatch):
    posts, runs = _Posts(_masked_post()), FakeCollection()
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(svc, "vision_run_collection", runs)
    import pytest as _pt
    from fastapi import HTTPException
    with _pt.raises(HTTPException) as ei:
        run(R.produce_field(str(posts.post["_id"]),
                            R.ProduceFieldRequest(producer="not_a_producer", region_id="reg_ns")))
    assert ei.value.status_code == 400


def test_produce_field_negative_space_returns_a_run_linked_quarantined_suggestion(monkeypatch):
    posts, runs = _Posts(_masked_post()), FakeCollection()
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(svc, "vision_run_collection", runs)

    resp = run(R.produce_field(str(posts.post["_id"]),
                               R.ProduceFieldRequest(producer="negative_space", region_id="reg_ns")))
    assert resp["available"] is True and resp["status"] == "ready"
    assert len(resp["suggestions"]) == 1
    sug = resp["suggestions"][0]
    assert sug["producer"] == "negative_space" and sug["type"] == "brush_field"
    assert sug["provenance"]["run_id"] == resp["run_id"]
    assert posts.writes == []                                       # a suggestion is never persisted
    proj = run(svc.get_run(resp["run_id"], collection=runs))
    assert proj["operation"] == "produce" and proj["status"] == "succeeded"


def test_produce_field_refusal_is_honest_not_an_error(monkeypatch):
    # a region with NO mask → nothing to invert → status 'empty', available True, no mark, no error
    post = {"_id": ObjectId(), "region_annotations": [{"id": "bare", "label": "no mask"}]}
    posts, runs = _Posts(post), FakeCollection()
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(svc, "vision_run_collection", runs)

    resp = run(R.produce_field(str(posts.post["_id"]),
                               R.ProduceFieldRequest(producer="negative_space", region_id="bare")))
    assert resp["available"] is True and resp["status"] == "empty"
    assert resp["suggestions"] == []
    proj = run(svc.get_run(resp["run_id"], collection=runs))
    assert proj["operation"] == "produce" and proj["status"] == "succeeded"   # honest, not failed


def test_produce_field_material_goes_through_the_manager_and_carries_a_full_receipt(monkeypatch):
    posts, runs = _Posts(_masked_post("reg_m")), FakeCollection()
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(svc, "vision_run_collection", runs)

    # stub the DINOv2 manager path — a fake two-material patch grid; CI needs no GPU
    from backend.services import dinov2_service as dsvc
    from backend.services import evidence_embedding_service as ees
    monkeypatch.setattr(dsvc, "is_available", lambda: True)

    class _FakePatches:
        def __init__(self, grid):
            a, b = [1.0, 0.0], [0.0, 1.0]
            self._rows = [(a if (i // grid) < grid // 2 else b) for i in range(grid * grid)]
            self.grid = grid
        def reshape(self, n, m):                                    # mimic tensor.reshape(...).tolist()
            return self
        def tolist(self):
            return self._rows

    async def _fake_features(image, image_hash):
        return {"grid": 4, "patches": _FakePatches(4)}
    monkeypatch.setattr(ees, "_features_via_manager", _fake_features)
    monkeypatch.setattr(ees, "_pil", lambda b: object())            # the fake features ignore the image
    monkeypatch.setattr(R, "_fetch_post_image_cached", _img)

    resp = run(R.produce_field(str(posts.post["_id"]),
                               R.ProduceFieldRequest(producer="material_field", region_id="reg_m",
                                                     seed_point=[0.1, 0.1])))
    assert resp["available"] is True and resp["status"] == "ready"
    sug = resp["suggestions"][0]
    assert sug["producer"] == "material_field" and sug["role"] == "material_field"
    p = sug["provenance"]
    assert p["run_id"] == resp["run_id"] and p["adapter"] == "dinov2_vits14"
    assert p["model"] == dsvc.CHECKPOINT and "latency_ms" in p
    assert "confidence" not in p                                    # never on the mark (contract §6)
    assert posts.writes == []


def test_produce_field_material_without_a_seed_refuses_honestly(monkeypatch):
    posts, runs = _Posts(_masked_post("reg_m")), FakeCollection()
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(svc, "vision_run_collection", runs)
    from backend.services import dinov2_service as dsvc
    monkeypatch.setattr(dsvc, "is_available", lambda: True)

    resp = run(R.produce_field(str(posts.post["_id"]),
                               R.ProduceFieldRequest(producer="material_field", region_id="reg_m")))
    assert resp["status"] == "empty" and resp["suggestions"] == []   # no tap → honest nothing


# ─────────── PURE: producer 6 (rhythm — cpu_perceptual, no model at all) ───────────
# Synthetic maps stand in for the Gabor bank: the field logic needs no cv2 in CI.

def _rhythm_analysis(grid=4, textured=True):
    """A patterned energy map (alternating strong/weak) or a flat one."""
    if not textured:
        return {"energy": [0.5] * (grid * grid), "coherence": [0.5] * (grid * grid), "grid": grid}
    energy = [(0.9 if (i % 2 == 0) else 0.05) for i in range(grid * grid)]
    return {"energy": energy, "coherence": list(energy), "grid": grid}


def test_rhythm_becomes_a_run_linked_brush_field_with_a_no_model_receipt():
    d = ss.suggestion_from_rhythm(_rhythm_analysis(), run_id="run_r", region_id="reg_t",
                                  latency_ms=12.5)
    assert d is not None
    assert d["producer"] == "rhythm" and d["type"] == "brush_field" and d["role"] == "rhythm"
    assert d["geometry"]["kind"] == "soft_mask"
    assert d["geometry"]["strokes"] and all(s["op"] == "add" for s in d["geometry"]["strokes"])
    p = d["provenance"]
    # deterministic receipt: an adapter + a run + latency, but NOTHING was inferred
    assert p["run_id"] == "run_r" and p["producer"] == "rhythm"
    assert p["adapter"] == "cpu_perceptual" and p["latency_ms"] == 12.5
    assert "model" not in p and "checkpoint" not in p
    assert "confidence" not in p                      # never on the mark (contract §6)
    assert d["source_ref"] == "reg_t:rhythm"


def test_rhythm_refuses_a_flat_surface():
    # nothing repeats on a flat wall — no rhythm may be claimed
    assert ss.suggestion_from_rhythm(_rhythm_analysis(textured=False), run_id="r") is None


def test_rhythm_refuses_empty_or_malformed_analysis():
    assert ss.suggestion_from_rhythm(None, run_id="r") is None
    assert ss.suggestion_from_rhythm({}, run_id="r") is None
    assert ss.suggestion_from_rhythm({"grid": 0, "energy": []}, run_id="r") is None
    assert ss.suggestion_from_rhythm({"grid": 4, "energy": [1.0, 2.0]}, run_id="r") is None


def test_rhythm_strokes_are_remapped_into_the_regions_box():
    box = {"x": 0.5, "y": 0.5, "w": 0.25, "h": 0.25}
    d = ss.suggestion_from_rhythm(_rhythm_analysis(), run_id="r", region_id="reg_t", box=box)
    for s in d["geometry"]["strokes"]:
        x, y = s["points"][0]
        # a field measured inside the crop lands INSIDE that crop, not over the whole frame
        assert 0.5 <= x <= 0.75 and 0.5 <= y <= 0.75
        assert s["radius"] <= 0.05 * 0.25 + 1e-9      # radius scales with the crop


def test_rhythm_list_form_is_empty_on_refusal():
    assert ss.suggestions_from_rhythm(_rhythm_analysis(textured=False), run_id="r") == []
    assert len(ss.suggestions_from_rhythm(_rhythm_analysis(), run_id="r", region_id="x")) == 1


# ─────────── the cpu_perceptual ADAPTER: available, and never on the GPU pool ───────────

def test_cpu_perceptual_adapter_is_available_and_never_takes_the_gpu_slot():
    from backend.services.vision_orchestrator.adapters import CpuPerceptualAdapter
    from backend.services.vision_orchestrator.contracts import Capability, ResourceKind
    a = CpuPerceptualAdapter()
    assert a.spec.name == "cpu_perceptual"            # the name planner.py already references
    assert a.spec.capability is Capability.PERCEPTUAL
    # THE load-bearing assertion: CPU_LIGHT, so ModelManager never acquires the GPU semaphore
    assert a.spec.resource is ResourceKind.CPU_LIGHT
    assert a.spec.resource is not ResourceKind.GPU
    # no weights → available wherever cv2+numpy are, and nothing to download
    assert a.is_available() is True and a.spec.deferred is False
    assert "opencv" in a.spec.model_id


def test_cpu_perceptual_load_and_unload_are_free_noops():
    from backend.services.vision_orchestrator.adapters import CpuPerceptualAdapter
    a = CpuPerceptualAdapter()
    assert run(a.load()) == 0.0                        # nothing to load
    assert run(a.unload()) is None                     # nothing resident to free


def test_planner_cheap_signals_reference_now_resolves_to_a_real_adapter():
    """planner.py has always named `cpu_perceptual`; P6-D makes that reference real."""
    from backend.services.vision_orchestrator import AdapterRegistry
    from backend.services.vision_orchestrator.adapters import CpuPerceptualAdapter
    from backend.services.vision_orchestrator.contracts import Capability
    reg = AdapterRegistry()
    reg.register(CpuPerceptualAdapter())
    assert reg.get("cpu_perceptual") is not None
    assert "cpu_perceptual" in reg.by_capability(Capability.PERCEPTUAL)


def test_produce_field_rhythm_dispatches_through_the_generic_surface(monkeypatch):
    """rhythm reaches the frontend through the SAME P6-C endpoint — no new route."""
    post = {"_id": ObjectId(),
            "region_annotations": [{"id": "reg_t", "label": "drapery",
                                    "box": {"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5}}]}
    posts, runs = _Posts(post), FakeCollection()
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(svc, "vision_run_collection", runs)
    monkeypatch.setattr(R, "_fetch_post_image_cached", _img)

    from backend.services import evidence_embedding_service as ees
    from backend.services import cpu_perceptual_service as cps

    class _Img:
        size = (100, 100)
        def crop(self, b): return self
        def convert(self, m): return self
    monkeypatch.setattr(ees, "_pil", lambda b: _Img())
    monkeypatch.setattr(cps, "is_available", lambda: True)
    monkeypatch.setattr(cps, "analyze", lambda image, **kw: _rhythm_analysis())

    resp = run(R.produce_field(str(posts.post["_id"]),
                               R.ProduceFieldRequest(producer="rhythm", region_id="reg_t")))
    assert resp["available"] is True and resp["status"] == "ready"
    sug = resp["suggestions"][0]
    assert sug["producer"] == "rhythm" and sug["role"] == "rhythm"
    assert sug["provenance"]["adapter"] == "cpu_perceptual"
    assert "model" not in sug["provenance"]           # no model was involved, and it says so
    assert posts.writes == []                          # nothing persisted
    proj = run(svc.get_run(resp["run_id"], collection=runs))
    assert proj["operation"] == "produce" and proj["status"] == "succeeded"


def test_produce_field_rhythm_flat_surface_refuses_honestly(monkeypatch):
    post = {"_id": ObjectId(), "region_annotations": [{"id": "flat", "box": {"x": 0, "y": 0, "w": 1, "h": 1}}]}
    posts, runs = _Posts(post), FakeCollection()
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(svc, "vision_run_collection", runs)
    monkeypatch.setattr(R, "_fetch_post_image_cached", _img)
    from backend.services import evidence_embedding_service as ees
    from backend.services import cpu_perceptual_service as cps

    class _Img:
        size = (100, 100)
        def crop(self, b): return self
        def convert(self, m): return self
    monkeypatch.setattr(ees, "_pil", lambda b: _Img())
    monkeypatch.setattr(cps, "is_available", lambda: True)
    monkeypatch.setattr(cps, "analyze", lambda image, **kw: _rhythm_analysis(textured=False))

    resp = run(R.produce_field(str(posts.post["_id"]),
                               R.ProduceFieldRequest(producer="rhythm", region_id="flat")))
    assert resp["status"] == "empty" and resp["suggestions"] == []   # honest, not an error
    assert resp["available"] is True


def test_rhythm_refuses_a_near_flat_surface_with_only_noise():
    """The regression the live cv2 run exposed: min-max normalization rescales ANY non-constant
    input to span [0,1], so a blank wall with a whisper of noise would normalize to a full-range
    field and be painted as confident rhythm. The refusal is judged on RELATIVE RELIEF instead."""
    grid = 4
    # a blank surface at magnitude ~20 with ±0.02 of noise → ~0.2% relief: nothing repeats
    noisy_flat = [20.0 + (0.02 if i % 3 == 0 else -0.01) for i in range(grid * grid)]
    analysis = {"energy": noisy_flat, "coherence": noisy_flat, "grid": grid}
    assert ss.suggestion_from_rhythm(analysis, run_id="r") is None
    # and the confidence reported for a real texture is that same relative relief
    d = ss.suggestion_from_rhythm(_rhythm_analysis(), run_id="r", region_id="x")
    assert d["confidence"] == pytest.approx((0.9 - 0.05) / 0.9, abs=1e-3)


# ─────────── PURE: producer 7 (pressure_zone — rhythm's sibling, same reading) ───────────

def test_pressure_zone_reads_coherence_from_the_same_analysis():
    a = _rhythm_analysis()                       # one adapter reading carries BOTH maps
    d = ss.suggestion_from_pressure_zone(a, run_id="run_p", region_id="reg_d", latency_ms=8.0)
    assert d is not None
    assert d["producer"] == "pressure_zone" and d["role"] == "pressure_zone"
    assert d["type"] == "brush_field" and d["geometry"]["kind"] == "soft_mask"
    p = d["provenance"]
    assert p["adapter"] == "cpu_perceptual" and p["run_id"] == "run_p" and p["latency_ms"] == 8.0
    assert "model" not in p and "checkpoint" not in p     # deterministic: nothing inferred
    assert "confidence" not in p
    assert d["source_ref"] == "reg_d:pressure_zone"       # distinct key from rhythm's


def test_rhythm_and_pressure_zone_are_distinct_marks_from_one_reading():
    a = _rhythm_analysis()
    r = ss.suggestion_from_rhythm(a, run_id="r", region_id="reg_d")
    p = ss.suggestion_from_pressure_zone(a, run_id="r", region_id="reg_d")
    assert r["source_ref"] != p["source_ref"]             # they never collide in the quarantine
    assert r["role"] == "rhythm" and p["role"] == "pressure_zone"


def test_pressure_zone_refuses_an_isotropic_surface():
    # no directional organisation → nothing pulls → refuse
    grid = 4
    flat = {"energy": [0.5] * (grid * grid), "coherence": [0.0] * (grid * grid), "grid": grid}
    assert ss.suggestion_from_pressure_zone(flat, run_id="r") is None


def test_pressure_zone_refuses_empty_or_malformed_analysis():
    assert ss.suggestion_from_pressure_zone(None, run_id="r") is None
    assert ss.suggestion_from_pressure_zone({}, run_id="r") is None
    assert ss.suggestion_from_pressure_zone({"grid": 4, "coherence": [0.1]}, run_id="r") is None


def test_pressure_zone_list_form_is_empty_on_refusal():
    grid = 4
    flat = {"coherence": [0.0] * (grid * grid), "grid": grid}
    assert ss.suggestions_from_pressure_zone(flat, run_id="r") == []
    assert len(ss.suggestions_from_pressure_zone(_rhythm_analysis(), run_id="r")) == 1


def test_produce_field_pressure_zone_dispatches_through_the_same_surface(monkeypatch):
    post = {"_id": ObjectId(),
            "region_annotations": [{"id": "reg_d", "label": "drapery",
                                    "box": {"x": 0.1, "y": 0.1, "w": 0.5, "h": 0.5}}]}
    posts, runs = _Posts(post), FakeCollection()
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(svc, "vision_run_collection", runs)
    monkeypatch.setattr(R, "_fetch_post_image_cached", _img)
    from backend.services import evidence_embedding_service as ees
    from backend.services import cpu_perceptual_service as cps

    class _Img:
        size = (100, 100)
        def crop(self, b): return self
        def convert(self, m): return self
    monkeypatch.setattr(ees, "_pil", lambda b: _Img())
    monkeypatch.setattr(cps, "is_available", lambda: True)
    monkeypatch.setattr(cps, "analyze", lambda image, **kw: _rhythm_analysis())

    resp = run(R.produce_field(str(posts.post["_id"]),
                               R.ProduceFieldRequest(producer="pressure_zone", region_id="reg_d")))
    assert resp["status"] == "ready"
    assert resp["suggestions"][0]["role"] == "pressure_zone"
    assert posts.writes == []


# ─────────── PURE: producer 8 (recession — Depth-Anything, a real model) ───────────
# Fake depth grids: CI needs no GPU and no weights.

def _depth(grid=4, flat=False):
    if flat:
        return {"depth": [5.0] * (grid * grid), "grid": grid}
    # inverse depth: top rows far (small), bottom rows near (large)
    return {"depth": [float(1 + (i // grid) * 4) for i in range(grid * grid)], "grid": grid}


def test_recession_becomes_a_brush_field_with_a_FULL_model_receipt():
    d = ss.suggestion_from_recession(
        _depth(), run_id="run_d", region_id="reg_s",
        model="depth_anything_v2_small", checkpoint="depth-anything/Depth-Anything-V2-Small-hf",
        preprocessing_version="depth-anything-v2-s-v1", latency_ms=120.0, peak_vram_mib=210.0)
    assert d is not None
    assert d["producer"] == "recession" and d["type"] == "brush_field"
    assert d["role"] == "background_recession"
    assert d["geometry"]["kind"] == "soft_mask" and d["geometry"]["strokes"]
    p = d["provenance"]
    assert p["adapter"] == "depth_anything_v2_small" and p["model"] == "depth_anything_v2_small"
    assert p["checkpoint"].startswith("depth-anything/") and p["latency_ms"] == 120.0
    assert p["peak_vram_mib"] == 210.0 and p["run_id"] == "run_d"
    assert "confidence" not in p                       # never on the mark (contract §6)
    assert 0.0 <= d["confidence"] <= 1.0


def test_atmosphere_is_the_near_band_of_the_same_reading():
    depth = _depth()
    far = ss.suggestion_from_recession(depth, run_id="r", role="background_recession", region_id="x")
    near = ss.suggestion_from_recession(depth, run_id="r", role="atmosphere_field", region_id="x")
    assert far["role"] == "background_recession" and near["role"] == "atmosphere_field"
    assert far["source_ref"] != near["source_ref"]     # two distinct marks from one reading
    # the bands paint opposite parts of the frame
    far_pts = {tuple(s["points"][0]) for s in far["geometry"]["strokes"]}
    near_pts = {tuple(s["points"][0]) for s in near["geometry"]["strokes"]}
    assert far_pts and near_pts and far_pts != near_pts


def test_recession_refuses_a_scene_with_no_depth_relief():
    assert ss.suggestion_from_recession(_depth(flat=True), run_id="r") is None


def test_recession_refuses_unknown_role_and_malformed_input():
    assert ss.suggestion_from_recession(_depth(), run_id="r", role="not_a_role") is None
    assert ss.suggestion_from_recession(None, run_id="r") is None
    assert ss.suggestion_from_recession({}, run_id="r") is None
    assert ss.suggestion_from_recession({"grid": 4, "depth": [1.0, 2.0]}, run_id="r") is None


def test_recession_list_form_can_emit_both_bands_and_refuses_flat():
    out = ss.suggestions_from_recession(_depth(), run_id="r", region_id="x",
                                        roles=["background_recession", "atmosphere_field"])
    assert [d["role"] for d in out] == ["background_recession", "atmosphere_field"]
    assert ss.suggestions_from_recession(_depth(flat=True), run_id="r") == []


def test_depth_adapter_is_on_the_GPU_pool_and_implements_the_roster_spec():
    from backend.services.vision_orchestrator.adapters import DepthAnythingAdapter
    from backend.services.vision_orchestrator.contracts import Capability, ResourceKind
    a = DepthAnythingAdapter()
    assert a.spec.name == "depth_anything_v2_small"       # the roster's long-standing spec name
    assert a.spec.capability is Capability.DEPTH
    assert a.spec.resource is ResourceKind.GPU            # single-GPU residency applies
    assert a.spec.checkpoint == "depth-anything/Depth-Anything-V2-Small-hf"
    assert a.spec.license == "Apache-2.0"


def test_produce_field_recession_dispatches_through_the_same_surface(monkeypatch):
    post = {"_id": ObjectId(), "region_annotations": [{"id": "reg_s", "box": {"x": 0, "y": 0, "w": 1, "h": 1}}]}
    posts, runs = _Posts(post), FakeCollection()
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(svc, "vision_run_collection", runs)
    monkeypatch.setattr(R, "_fetch_post_image_cached", _img)
    from backend.services import evidence_embedding_service as ees
    from backend.services import depth_service as ds

    class _Img:
        size = (100, 100)
        def convert(self, m): return self
    monkeypatch.setattr(ees, "_pil", lambda b: _Img())
    monkeypatch.setattr(ds, "is_available", lambda: True)

    # stub the manager path so CI runs no model
    class _Art:
        data = _depth()
    class _Job:
        artifact = _Art()
    async def _fake_run(adapter, payload, **kw):
        return _Job()
    import backend.routers.posts as RR
    RR._depth_mgr = type("M", (), {"run_adapter": staticmethod(_fake_run)})()
    RR._depth_adapter = object()

    resp = run(R.produce_field(str(posts.post["_id"]),
                               R.ProduceFieldRequest(producer="background_recession", region_id="reg_s")))
    RR._depth_mgr = None; RR._depth_adapter = None
    assert resp["status"] == "ready"
    sug = resp["suggestions"][0]
    assert sug["role"] == "background_recession" and sug["producer"] == "recession"
    assert sug["provenance"]["model"] == ds.MODEL_TAG      # full receipt from a real model
    assert posts.writes == []


# ─────────── PURE: producer 9 (light / shadow — Intrinsic, deferred weights) ───────────
# Fake shading grids: the producers are fully testable while the model stays deferred.

def _shading(grid=4, flat=False):
    if flat:
        return {"shading": [5.0] * (grid * grid), "grid": grid}
    # lit on the left, falling away to the right
    return {"shading": [float(grid - c) for r in range(grid) for c in range(grid)], "grid": grid}


def test_light_becomes_a_brush_field_with_a_full_model_receipt():
    d = ss.suggestion_from_light(
        _shading(), run_id="run_l", region_id="reg_w",
        model="intrinsic_ordinal_shading", checkpoint="compphoto/Intrinsic:paper_weights",
        preprocessing_version="intrinsic-ordinal-v1", latency_ms=310.0, peak_vram_mib=480.0)
    assert d is not None
    assert d["producer"] == "shading" and d["type"] == "brush_field"
    assert d["role"] == "light_field"
    assert d["geometry"]["kind"] == "soft_mask" and d["geometry"]["strokes"]
    p = d["provenance"]
    assert p["adapter"] == "intrinsic_ordinal_shading" and p["model"] == "intrinsic_ordinal_shading"
    assert p["checkpoint"].startswith("compphoto/") and p["latency_ms"] == 310.0
    assert p["peak_vram_mib"] == 480.0 and p["run_id"] == "run_l"
    assert "confidence" not in p                        # never on the mark (contract §6)
    assert 0.0 <= d["confidence"] <= 1.0


def test_shadow_is_the_same_reading_read_as_absence():
    sh = _shading()
    light = ss.suggestion_from_light(sh, run_id="r", region_id="x")
    shadow = ss.suggestion_from_shadow(sh, run_id="r", region_id="x")
    assert light["role"] == "light_field" and shadow["role"] == "shadow_field"
    assert light["source_ref"] != shadow["source_ref"]   # two distinct marks from one reading
    lit_pts = {tuple(s["points"][0]) for s in light["geometry"]["strokes"]}
    dark_pts = {tuple(s["points"][0]) for s in shadow["geometry"]["strokes"]}
    assert lit_pts and dark_pts and lit_pts != dark_pts  # they paint opposite parts of the frame


def test_shading_producers_carry_the_fall_of_light_as_context_not_geometry():
    d = ss.suggestion_from_light(_shading(), run_id="r", region_id="x")
    fall = d["fall_of_light"]
    assert fall["dx"] == pytest.approx(1.0, abs=1e-6)    # lit left → falls right
    # it is CONTEXT: the mark's geometry stays a soft field, carrying no direction
    assert "fall_of_light" not in d["geometry"]
    assert d["geometry"]["kind"] == "soft_mask"


def test_shading_producers_refuse_an_evenly_lit_surface():
    assert ss.suggestion_from_light(_shading(flat=True), run_id="r") is None
    assert ss.suggestion_from_shadow(_shading(flat=True), run_id="r") is None


def test_shading_producers_refuse_malformed_input_and_unknown_roles():
    assert ss.suggestion_from_light(None, run_id="r") is None
    assert ss.suggestion_from_light({}, run_id="r") is None
    assert ss.suggestion_from_light({"grid": 4, "shading": [1.0, 2.0]}, run_id="r") is None
    assert ss._suggestion_from_shading(_shading(), role="not_a_role", run_id="r") is None


def test_shading_list_form_emits_both_bands_and_refuses_flat():
    out = ss.suggestions_from_shading(_shading(), run_id="r", region_id="x",
                                      roles=["light_field", "shadow_field"])
    assert [d["role"] for d in out] == ["light_field", "shadow_field"]
    assert ss.suggestions_from_shading(_shading(flat=True), run_id="r") == []


def test_intrinsic_adapter_spec_is_correct_and_tracks_installation_state():
    """The adapter's identity is fixed; its AVAILABILITY tracks whether the GitHub-only package
    is installed. P6-G shipped it deferred; P6-I installs it. Both are valid states, so the test
    asserts the invariant (spec) always and the state (available/deferred) consistently."""
    from backend.services.vision_orchestrator.adapters import IntrinsicShadingAdapter
    from backend.services.vision_orchestrator.contracts import Capability, ResourceKind
    from backend.services import intrinsic_service as isvc
    a = IntrinsicShadingAdapter()
    assert a.spec.name == "intrinsic_ordinal_shading"
    assert a.spec.capability is Capability.SHADING
    assert a.spec.resource is ResourceKind.GPU        # heaviest producer — residency matters
    # available and deferred are always each other's inverse, and follow the real install
    assert a.is_available() is isvc.is_available()
    assert a.spec.deferred is (not a.is_available())


def test_an_unavailable_intrinsic_adapter_can_never_produce_a_field():
    """The load-bearing guarantee, asserted regardless of what is installed on this box:
    ModelManager refuses to execute an unavailable adapter — UNAVAILABLE, never a blank field."""
    from backend.services.vision_orchestrator.adapters import IntrinsicShadingAdapter
    from backend.services.vision_orchestrator import (AdapterRegistry, CancelToken, ModelManager,
                                                      Priority, JobStatus)
    a = IntrinsicShadingAdapter()
    a.spec.available = False                          # force the deferred state deterministically
    reg = AdapterRegistry(); reg.register(a)
    job = run(ModelManager(reg).run_adapter(a, {"image": None},
                                            priority=int(Priority.BACKGROUND),
                                            cancel=CancelToken()))
    assert job.status is JobStatus.UNAVAILABLE
    assert job.artifact is None


def test_intrinsic_service_refuses_cleanly_when_the_package_is_absent(monkeypatch):
    """With the package absent, `estimate` refuses WITHOUT touching the image — asserted by
    forcing the absent state, so this holds whether or not the box has Intrinsic installed."""
    from backend.services import intrinsic_service as isvc
    monkeypatch.setattr(isvc, "is_available", lambda: False)
    assert isvc.estimate(object()) is None


def test_intrinsic_availability_probes_the_real_module_not_the_name():
    """A version check could not tell the real package from the PyPI stub — both are 0.0.1 — so
    availability must be decided by importing `intrinsic.pipeline` + `chrislib`."""
    from backend.services import intrinsic_service as isvc
    doc = isvc.is_available.__doc__ or ""
    assert "intrinsic.pipeline" in doc and "chrislib" in doc
    assert isvc.SHADING_KEY == "gry_shd"        # P6-I: confirmed against a real run, pinned


def test_produce_field_light_reports_unavailable_when_the_package_is_absent(monkeypatch):
    """An absent model must surface HONESTLY through the generic endpoint: `unavailable`,
    available=False, no suggestion — never an error and never a fabricated light field.

    The absent state is FORCED rather than assumed, so this keeps testing the refusal path on a
    box where Intrinsic is installed (P6-I) as well as one where it is not (P6-G)."""
    from backend.services import intrinsic_service as isvc
    monkeypatch.setattr(isvc, "is_available", lambda: False)
    post = {"_id": ObjectId(), "region_annotations": [{"id": "reg_w", "box": {"x": 0, "y": 0, "w": 1, "h": 1}}]}
    posts, runs = _Posts(post), FakeCollection()
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(svc, "vision_run_collection", runs)

    resp = run(R.produce_field(str(posts.post["_id"]),
                               R.ProduceFieldRequest(producer="light_field", region_id="reg_w")))
    assert resp["status"] == "unavailable" and resp["available"] is False
    assert resp["suggestions"] == []
    assert posts.writes == []
    proj = run(svc.get_run(resp["run_id"], collection=runs))
    assert proj["operation"] == "produce" and proj["status"] == "unavailable"


def test_produce_field_shading_runs_end_to_end_once_the_package_is_present(monkeypatch):
    """The activation path: flip is_available() + stub the manager, and light/shadow flow through
    the SAME surface with a full receipt — proving only the install is missing, not the wiring."""
    post = {"_id": ObjectId(), "region_annotations": [{"id": "reg_w", "box": {"x": 0, "y": 0, "w": 1, "h": 1}}]}
    posts, runs = _Posts(post), FakeCollection()
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(svc, "vision_run_collection", runs)
    monkeypatch.setattr(R, "_fetch_post_image_cached", _img)
    from backend.services import evidence_embedding_service as ees
    from backend.services import intrinsic_service as isvc

    class _Img:
        size = (100, 100)
        def convert(self, m): return self
    monkeypatch.setattr(ees, "_pil", lambda b: _Img())
    monkeypatch.setattr(isvc, "is_available", lambda: True)

    class _Art:
        data = _shading()
    class _Job:
        artifact = _Art()
    async def _fake_run(adapter, payload, **kw):
        return _Job()
    import backend.routers.posts as RR
    RR._shading_mgr = type("M", (), {"run_adapter": staticmethod(_fake_run)})()
    RR._shading_adapter = object()
    try:
        for producer, role in (("light_field", "light_field"), ("shadow_field", "shadow_field")):
            resp = run(R.produce_field(str(posts.post["_id"]),
                                       R.ProduceFieldRequest(producer=producer, region_id="reg_w")))
            assert resp["status"] == "ready", producer
            sug = resp["suggestions"][0]
            assert sug["role"] == role and sug["producer"] == "shading"
            assert sug["provenance"]["model"] == isvc.MODEL_TAG      # full receipt
    finally:
        RR._shading_mgr = None; RR._shading_adapter = None
    assert posts.writes == []


# ── P6-I: the REAL Intrinsic path, when the GitHub-only package is installed ──────────────────
# Skipped on a box without it (CI stays fake-driven); asserted for real where it exists. This is
# the test that would have caught P6-G's two wrong guesses: the `intrinsic.model_util` import and
# `run_pipeline` (which raises KeyError 'col_model' on the grayscale-only paper_weights).

def _intrinsic_absent():
    from backend.services import intrinsic_service as isvc
    return not isvc.is_available()


@pytest.mark.skipif(_intrinsic_absent(), reason="Intrinsic (GitHub-only) not installed")
def test_real_intrinsic_returns_the_pinned_gry_shd_key_and_feeds_light_and_shadow():
    from PIL import Image
    from backend.services import intrinsic_service as isvc

    # a synthetic left-lit gradient: cheap, deterministic, and genuinely non-uniform
    w = h = 256
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            v = int(235 - (x / w) * 200)
            px[x, y] = (v, v, v)

    sh = isvc.estimate(img)
    assert sh is not None, "the real pipeline returned nothing"
    assert sh["grid"] == isvc.GRID
    vals = sh["shading"]
    assert len(vals) == isvc.GRID * isvc.GRID
    assert max(vals) > min(vals), "a gradient must not read as uniform shading"

    # both bands come off ONE reading, with a full model receipt
    light = ss.suggestion_from_light(sh, run_id="run_real", region_id="reg_r",
                                     model=isvc.MODEL_TAG, checkpoint=isvc.CHECKPOINT,
                                     preprocessing_version=isvc.PREPROCESSING_VERSION,
                                     latency_ms=1.0, peak_vram_mib=1.0)
    shadow = ss.suggestion_from_shadow(sh, run_id="run_real", region_id="reg_r",
                                       model=isvc.MODEL_TAG, checkpoint=isvc.CHECKPOINT)
    assert light is not None and shadow is not None
    assert light["role"] == "light_field" and shadow["role"] == "shadow_field"
    assert light["geometry"]["strokes"] and shadow["geometry"]["strokes"]
    assert light["provenance"]["model"] == isvc.MODEL_TAG
    assert light["provenance"]["checkpoint"] == isvc.CHECKPOINT
    assert "confidence" not in light["provenance"]        # contract §6, even on a real run
    isvc.unload()


@pytest.mark.skipif(_intrinsic_absent(), reason="Intrinsic (GitHub-only) not installed")
def test_real_intrinsic_evenly_lit_surface_still_refuses():
    """The refusal must survive contact with the REAL model, which is harder than it sounds: a
    neural decomposition does not return a constant map for a constant image. Measured, a flat
    gray reads relief 0.062 and a flat white 0.135 — invented structure, well above the 0.05 the
    P6-G scaffold shipped. The threshold is calibrated to 0.25 against those numbers and a real
    photograph's 0.824, so this test pins the calibration, not just the code path."""
    from PIL import Image
    from backend.services import intrinsic_service as isvc
    for shade in ((128, 128, 128), (240, 240, 240)):
        sh = isvc.estimate(Image.new("RGB", (256, 256), shade))
        assert sh is not None                              # the model ran and returned a map
        vals = sh["shading"]
        relief = (max(vals) - min(vals)) / abs(max(vals))
        assert relief < 0.25, f"flat {shade} read relief {relief:.3f} — recalibrate"
        assert ss.suggestion_from_light(sh, run_id="r", region_id="x") is None
        assert ss.suggestion_from_shadow(sh, run_id="r", region_id="x") is None
    isvc.unload()


@pytest.mark.skipif(_intrinsic_absent(), reason="Intrinsic (GitHub-only) not installed")
def test_real_intrinsic_holds_single_gpu_residency_and_unloads_clean():
    """The heaviest producer in the roster (~984 MiB peak). Loading it must evict any other
    resident GPU model, and unloading must release — otherwise it eats the 4 GB card."""
    import torch
    from backend.services.vision_orchestrator import AdapterRegistry, ModelManager
    from backend.services.vision_orchestrator.adapters import (Dinov2FeatureAdapter,
                                                               IntrinsicShadingAdapter)
    if not torch.cuda.is_available():
        pytest.skip("no CUDA on this box")

    reg = AdapterRegistry()
    dino, shade = Dinov2FeatureAdapter(), IntrinsicShadingAdapter()
    reg.register(dino); reg.register(shade)
    mgr = ModelManager(reg)

    run(mgr.ensure_loaded(dino))
    assert mgr.resident() == ["dinov2_vits14"]
    run(mgr.ensure_loaded(shade))
    # single-GPU residency: the heavy one evicted the light one rather than stacking
    assert "dinov2_vits14" not in mgr.resident()
    assert "intrinsic_ordinal_shading" in mgr.resident()
    peak = torch.cuda.max_memory_allocated() / 1048576
    assert peak < 1400, f"peak VRAM {peak:.0f}MiB — too heavy for the 4GB card"

    run(mgr.unload("intrinsic_ordinal_shading"))
    assert mgr.resident() == []
    torch.cuda.empty_cache()


# ─────────── P8-A: open-vocab find_parts (Florence-2 phrase → region) ───────────
# Fake grounding results: CI needs neither GPU nor the 0.5 GB checkpoint.

def _grounding(poly=True, size=(200, 200)):
    if poly:
        return {"polygons": [[[20, 20, 180, 20, 180, 180, 20, 180]]], "boxes": [],
                "labels": [], "phrase": "the folded cloth", "image_size": list(size)}
    return {"polygons": [], "boxes": [[20, 20, 180, 180]], "labels": ["cloth"],
            "phrase": "the folded cloth", "image_size": list(size)}


def test_phrase_becomes_a_region_suggestion_with_a_full_pinned_receipt():
    d = ss.suggestion_from_phrase(
        _grounding(), phrase="the folded cloth", run_id="run_f",
        model="florence2_base", checkpoint="microsoft/Florence-2-base",
        revision="5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac",
        preprocessing_version="florence2-base-v1", latency_ms=880.0, peak_vram_mib=730.0)
    assert d is not None
    assert d["producer"] == "florence_find_parts" and d["type"] == "region_mask"
    assert d["label"] == "the folded cloth"          # the curator's own words name it
    assert d["role"] is None                          # a found extent has no reading yet
    # no Region exists yet, so the mark references nothing and authors no pixels
    assert d["geometry"] == {"kind": "unresolved"}
    # the geometry rides alongside as a PROPOSAL for the acceptance path
    pg = d["proposed_geometry"]
    assert pg["polygons"] and len(pg["polygons"][0]) == 4
    assert 0.0 <= pg["box"]["x"] <= 1.0 and 0.0 < pg["box"]["w"] <= 1.0
    p = d["provenance"]
    assert p["adapter"] == "florence2_base" and p["model"] == "florence2_base"
    assert p["revision"].startswith("5ca5edf5")       # WHICH weights said this
    assert p["peak_vram_mib"] == 730.0 and p["run_id"] == "run_f"
    assert "confidence" not in p                       # contract §6 holds here too


def test_phrase_idempotency_key_is_the_phrase():
    a = ss.suggestion_from_phrase(_grounding(), phrase="The Folded Cloth", run_id="r")
    b = ss.suggestion_from_phrase(_grounding(), phrase="the folded cloth  ", run_id="r")
    assert a["source_ref"] == b["source_ref"]         # same question → same suggestion


def test_phrase_falls_back_to_the_grounding_box_when_no_polygon():
    d = ss.suggestion_from_phrase(_grounding(poly=False), phrase="cloth", run_id="r")
    assert d is not None
    assert d["proposed_geometry"]["polygons"] == []
    assert d["proposed_geometry"]["box"]["w"] == pytest.approx(0.8)


def test_phrase_refuses_when_nothing_is_grounded():
    """The honest counterpart to a presence head: a phrase that finds nothing returns nothing,
    never the nearest thing the model can produce."""
    assert ss.suggestion_from_phrase(None, phrase="a unicorn", run_id="r") is None
    assert ss.suggestion_from_phrase({}, phrase="a unicorn", run_id="r") is None
    assert ss.suggestion_from_phrase(
        {"polygons": [], "boxes": [], "image_size": [200, 200]}, phrase="a unicorn", run_id="r") is None
    # a grounded sliver is not a part
    assert ss.suggestion_from_phrase(
        {"polygons": [], "boxes": [[5, 5, 5, 5]], "image_size": [200, 200]}, phrase="x", run_id="r") is None


def test_phrase_refuses_an_empty_question():
    assert ss.suggestion_from_phrase(_grounding(), phrase="", run_id="r") is None
    assert ss.suggestion_from_phrase(_grounding(), phrase="   ", run_id="r") is None
    assert ss.suggestions_from_phrase(_grounding(), phrase="  ", run_id="r") == []
    assert len(ss.suggestions_from_phrase(_grounding(), phrase="cloth", run_id="r")) == 1


def test_florence_adapter_spec_and_task_surface():
    from backend.services.vision_orchestrator.adapters import Florence2Adapter
    from backend.services.vision_orchestrator.contracts import Capability, ResourceKind
    from backend.services import florence2_service as f
    a = Florence2Adapter()
    assert a.spec.name == "florence2_base"
    assert a.spec.capability is Capability.GROUNDING
    assert a.spec.resource is ResourceKind.GPU          # single-GPU residency applies
    assert a.spec.revision == f.REVISION                 # the pin reaches the receipt
    assert a.is_available() is f.is_available()
    # the reusable "eyes": the whole task surface, not just the one verb P8-A ships
    assert set(f.TASKS) == {f.TASK_CAPTION, f.TASK_DETECT, f.TASK_GROUNDING, f.TASK_REFERRING_SEG}
    assert f.PHRASE_TASKS == {f.TASK_GROUNDING, f.TASK_REFERRING_SEG}


def test_florence_service_refuses_a_phrase_task_without_a_phrase(monkeypatch):
    """"Find the thing I didn't name" has no honest answer — it must not silently become a
    whole-image query."""
    from backend.services import florence2_service as f
    monkeypatch.setattr(f, "is_available", lambda: True)
    assert f.run_task(object(), f.TASK_REFERRING_SEG, phrase="") is None
    assert f.run_task(object(), f.TASK_GROUNDING, phrase=None) is None
    assert f.run_task(object(), "<NOT_A_TASK>", phrase="x") is None


def test_produce_field_phrase_dispatches_through_the_same_surface(monkeypatch):
    post = {"_id": ObjectId(), "region_annotations": [{"id": "r1", "box": {"x": 0, "y": 0, "w": 1, "h": 1}}]}
    posts, runs = _Posts(post), FakeCollection()
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(svc, "vision_run_collection", runs)
    monkeypatch.setattr(R, "_fetch_post_image_cached", _img)
    from backend.services import evidence_embedding_service as ees
    from backend.services import florence2_service as f

    class _Img:
        size = (200, 200)
        def convert(self, m): return self
    monkeypatch.setattr(ees, "_pil", lambda b: _Img())
    monkeypatch.setattr(f, "is_available", lambda: True)

    class _Art: data = _grounding()
    class _Job: artifact = _Art()
    async def _fake_run(adapter, payload, **kw):
        assert payload.get("phrase") == "the folded cloth"   # the words reach the model
        return _Job()
    import backend.routers.posts as RR
    RR._florence_mgr = type("M", (), {"run_adapter": staticmethod(_fake_run)})()
    RR._florence_adapter = object()
    try:
        resp = run(R.produce_field(str(posts.post["_id"]),
                                   R.ProduceFieldRequest(producer="florence_find_parts",
                                                         phrase="the folded cloth")))
        assert resp["status"] == "ready"
        sug = resp["suggestions"][0]
        assert sug["producer"] == "florence_find_parts" and sug["label"] == "the folded cloth"
        assert sug["provenance"]["revision"] == f.REVISION
        assert posts.writes == []                            # a proposal is never a write
    finally:
        RR._florence_mgr = None; RR._florence_adapter = None


def test_produce_field_phrase_with_no_words_refuses_honestly(monkeypatch):
    post = {"_id": ObjectId(), "region_annotations": []}
    posts, runs = _Posts(post), FakeCollection()
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(svc, "vision_run_collection", runs)
    from backend.services import florence2_service as f
    monkeypatch.setattr(f, "is_available", lambda: True)
    resp = run(R.produce_field(str(posts.post["_id"]),
                               R.ProduceFieldRequest(producer="florence_find_parts")))
    assert resp["status"] == "empty" and resp["suggestions"] == []
    assert resp["available"] is True


# ─────────── P8-B: Grounded-SAM open-vocab find_parts (detector → SAM2) ───────────

def _detection(score=0.82, box=(20, 20, 180, 180), size=(200, 200), label="the drapery"):
    return {"boxes": [list(box)], "scores": [score], "labels": [label],
            "image_size": list(size), "phrase": label}


def test_best_grounded_box_normalizes_and_picks_the_highest_score():
    det = {"boxes": [[10, 10, 100, 100], [0, 0, 200, 200]], "scores": [0.6, 0.9],
           "labels": ["a", "b"], "image_size": [200, 200]}
    b = ss.best_grounded_box(det)
    assert b["score"] == 0.9 and b["label"] == "b"
    assert b["box_xyxy"] == [0.0, 0.0, 1.0, 1.0]      # pixel → normalized, exactly once


def test_best_grounded_box_enforces_the_calibrated_threshold():
    """The threshold is the honest presence-check. Measured on a real photograph, absent phrases
    score up to 0.471 ("a traffic light") while "a purple bicycle" (0.444) OUTSCORED a real
    "the drapery" (0.397) — GroundingDINO has no presence head, it always returns its best guess.
    0.5 rejects every absent phrase in that sample; below it, the detector is guessing and SAM2
    would cut a confident mask around nothing."""
    for absent_score in (0.471, 0.444, 0.440, 0.339, 0.286):
        assert ss.best_grounded_box(_detection(score=absent_score)) is None, absent_score
    for present_score in (0.792, 0.582, 0.575, 0.555):
        assert ss.best_grounded_box(_detection(score=present_score)) is not None, present_score


def test_best_grounded_box_refuses_slivers_and_malformed_input():
    assert ss.best_grounded_box(None) is None
    assert ss.best_grounded_box({}) is None
    assert ss.best_grounded_box({"boxes": [], "scores": [], "image_size": [200, 200]}) is None
    # a high-scoring degenerate box is still not a part
    assert ss.best_grounded_box(_detection(score=0.99, box=(5, 5, 5, 5))) is None
    # no image size → nothing can be normalized honestly
    assert ss.best_grounded_box(_detection(size=(0, 0))) is None


def test_grounded_suggestion_references_the_sam_region_and_credits_BOTH_models():
    region = {"id": "refine_abc", "geometry_rev": 2, "mask_rle": {"size": [8, 8], "counts": "M"}}
    d = ss.suggestion_from_grounded_phrase(
        region, phrase="the drapery", run_id="run_g", score=0.79,
        detector_model="grounding_dino_tiny", detector_revision="a2bb814dd30d",
        detector_latency_ms=6000.0, segmenter_latency_ms=1100.0, peak_vram_mib=1691.0)
    assert d["producer"] == "grounded_sam_find_parts" and d["type"] == "region_mask"
    assert d["label"] == "the drapery"
    # SAM2 made a real mask on a real region, so the mark REFERENCES it — no inline pixels,
    # exactly like the click-refine producer it reuses.
    assert d["geometry"]["kind"] == "raster_mask"
    assert d["geometry"]["mask_ref"] == {"region_id": "refine_abc", "geometry_rev": 2}
    p = d["provenance"]
    # a two-model chain crediting one model is a false receipt
    assert p["adapter"] == "grounding_dino_tiny+sam2"
    assert p["model"] == "grounding_dino_tiny" and p["segmenter_model"] == "sam2.1"
    assert p["revision"] == "a2bb814dd30d"
    assert p["detector_latency_ms"] == 6000.0 and p["latency_ms"] == 1100.0
    assert "confidence" not in p                       # contract §6
    assert d["confidence"] == 0.79                      # descriptor only
    assert d["source_ref"] == "phrase:the drapery"      # idempotent on the question


def test_grounded_suggestion_refuses_without_a_region_or_a_phrase():
    region = {"id": "refine_abc"}
    assert ss.suggestion_from_grounded_phrase(None, phrase="x", run_id="r") is None
    assert ss.suggestion_from_grounded_phrase({}, phrase="x", run_id="r") is None
    assert ss.suggestion_from_grounded_phrase(region, phrase="  ", run_id="r") is None
    assert ss.suggestions_from_grounded_phrase(None, phrase="x", run_id="r") == []
    assert len(ss.suggestions_from_grounded_phrase(region, phrase="x", run_id="r")) == 1


def test_grounding_detector_adapter_spec_and_prompt_convention():
    from backend.services.vision_orchestrator.adapters import GroundingDinoAdapter
    from backend.services.vision_orchestrator.contracts import Capability, ResourceKind
    from backend.services import grounding_detector_service as g
    a = GroundingDinoAdapter()
    assert a.spec.name == "grounding_dino_tiny"
    assert a.spec.capability is Capability.GROUNDING
    assert a.spec.resource is ResourceKind.GPU
    assert a.spec.license == "Apache-2.0"               # unlike YOLO's AGPL
    assert a.spec.revision == g.REVISION
    # GroundingDINO's text convention, normalized in one place so it cannot silently degrade
    assert g.normalize_prompt("The Drapery") == "the drapery."
    assert g.normalize_prompt("already done.") == "already done."
    assert g.normalize_prompt("   ") == ""
    assert g.detect(object(), "") is None               # empty phrase asks nothing


def test_produce_field_refuses_when_the_presence_gate_is_unavailable(monkeypatch):
    """FAIL CLOSED when the guard is missing.

    P8-C made CLIP the thing that stops fabrication, and the detector threshold was lowered to
    0.30 on that basis. So if CLIP cannot run, the pipeline must NOT quietly fall back to the
    detector alone — that combination (permissive detector, no verifier) is exactly the state
    that cut a mask around a bicycle. It reports unavailable instead."""
    post = {"_id": ObjectId(), "region_annotations": [{"id": "r1", "box": {"x": 0, "y": 0, "w": 1, "h": 1}}]}
    posts, runs = _Posts(post), FakeCollection()
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(svc, "vision_run_collection", runs)
    monkeypatch.setattr(R, "_fetch_post_image_cached", _img)
    from backend.services import evidence_embedding_service as ees
    from backend.services import grounding_detector_service as gd
    from backend.services.vision_orchestrator import refine_session as rs_mod

    class _Img:
        size = (200, 200)
        def convert(self, m): return self
    from backend.services import clip_presence_service as cps
    monkeypatch.setattr(ees, "_pil", lambda b: _Img())
    monkeypatch.setattr(gd, "is_available", lambda: True)
    monkeypatch.setattr(cps, "is_available", lambda: False)     # the guard is gone

    order = []
    class _Art: data = _detection(score=0.8)
    class _Job: artifact = _Art()
    async def _fake_detect(adapter, payload, **kw):
        order.append("detect"); return _Job()
    async def _fake_unload(name):
        order.append(f"unload:{name}")
    import backend.routers.posts as RR
    RR._grounding_mgr = type("M", (), {"run_adapter": staticmethod(_fake_detect),
                                       "unload": staticmethod(_fake_unload)})()
    RR._grounding_adapter = object()

    async def _fake_preview(image_bytes, prompt, base_id, base_rev):
        order.append("sam2")
        assert "box" in prompt                          # SAM2 got a BOX prompt, not points
        return {"id": "refine_xyz", "geometry_rev": 1, "mask_rle": {"size": [4, 4], "counts": "M"}}
    monkeypatch.setattr(rs_mod.refine_session, "available", lambda: True)
    monkeypatch.setattr(rs_mod.refine_session, "preview", _fake_preview)
    try:
        resp = run(R.produce_field(str(posts.post["_id"]),
                                   R.ProduceFieldRequest(producer="grounded_sam_find_parts",
                                                         phrase="the drapery")))
        assert resp["status"] == "unavailable" and resp["available"] is False
        assert resp["suggestions"] == []
        assert "sam2" not in order, "SAM2 must not run unguarded"
        assert posts.writes == []
    finally:
        RR._grounding_mgr = None; RR._grounding_adapter = None


def test_produce_field_grounded_sam_refuses_a_phrase_that_grounds_nothing(monkeypatch):
    """Below threshold, SAM2 is never even called — a guessed box must not become a mask."""
    post = {"_id": ObjectId(), "region_annotations": []}
    posts, runs = _Posts(post), FakeCollection()
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(svc, "vision_run_collection", runs)
    monkeypatch.setattr(R, "_fetch_post_image_cached", _img)
    from backend.services import evidence_embedding_service as ees
    from backend.services import grounding_detector_service as gd
    from backend.services.vision_orchestrator import refine_session as rs_mod

    class _Img:
        size = (200, 200)
        def convert(self, m): return self
    monkeypatch.setattr(ees, "_pil", lambda b: _Img())
    monkeypatch.setattr(gd, "is_available", lambda: True)

    sam_called = []
    class _Art: data = _detection(score=0.44)          # a real absent-phrase score
    class _Job: artifact = _Art()
    async def _fake_detect(adapter, payload, **kw): return _Job()
    async def _fake_unload(name): pass
    import backend.routers.posts as RR
    RR._grounding_mgr = type("M", (), {"run_adapter": staticmethod(_fake_detect),
                                       "unload": staticmethod(_fake_unload)})()
    RR._grounding_adapter = object()
    async def _never(*a, **k):
        sam_called.append(1); return {}
    monkeypatch.setattr(rs_mod.refine_session, "preview", _never)
    try:
        resp = run(R.produce_field(str(posts.post["_id"]),
                                   R.ProduceFieldRequest(producer="grounded_sam_find_parts",
                                                         phrase="a purple bicycle")))
        assert resp["status"] == "empty" and resp["suggestions"] == []
        assert sam_called == [], "SAM2 must not run on a below-threshold box"
    finally:
        RR._grounding_mgr = None; RR._grounding_adapter = None


# ─────────── P8-C: the CLIP presence gate ───────────

def test_clip_crop_box_pads_and_clamps():
    from backend.services import clip_presence_service as cp
    class _Img:
        size = (200, 100)
        def __init__(self): self.crops = []
        def crop(self, b): self.crops.append(b); return b
    im = _Img()
    out = cp.crop_box(im, [0.25, 0.25, 0.75, 0.75])
    x0, y0, x1, y1 = out
    assert x0 < 50 and x1 > 150                       # padded outward for context
    assert 0 <= x0 and x1 <= 200 and 0 <= y0 and y1 <= 100   # clamped to the frame
    assert cp.crop_box(im, [0.5, 0.5, 0.5, 0.5]) is None     # degenerate → nothing to judge


def test_clip_verify_keeps_only_boxes_that_match_the_phrase(monkeypatch):
    """The gate's whole job: the detector fired, but does the crop actually show it?"""
    from backend.services import clip_presence_service as cp
    det = {"boxes": [[10, 10, 100, 100], [110, 10, 190, 90]], "scores": [0.4, 0.9],
           "labels": ["x", "y"], "image_size": [200, 200]}
    # first box matches the phrase, second does not
    monkeypatch.setattr(cp, "presence_score",
                        lambda img, box, phrase, **kw: 0.91 if box[0] < 0.3 else 0.004)
    out = cp.verify_boxes(object(), det, "the drapery")
    assert len(out) == 1
    assert out[0]["presence"] == 0.91
    assert out[0]["detector_score"] == 0.4            # the LOWER-scoring box survived — the point


def test_clip_verify_rejects_everything_when_nothing_matches(monkeypatch):
    """The detector guessed and it is not really there — measured absent scores are ~0.005."""
    from backend.services import clip_presence_service as cp
    det = {"boxes": [[10, 10, 100, 100]], "scores": [0.471], "image_size": [200, 200]}
    for absent in (0.0048, 0.0040, 0.0005, 0.0003, 0.0001):
        monkeypatch.setattr(cp, "presence_score", lambda *a, **k: absent)
        assert cp.verify_boxes(object(), det, "a purple bicycle") == [], absent


def test_clip_verify_admits_the_present_phrases_the_detector_threshold_dropped(monkeypatch):
    """P8-B's 0.5 detector cutoff refused "the drapery" (det 0.397). CLIP scores it 0.892, so the
    gate recovers it — that recall is the entire point of this stage."""
    from backend.services import clip_presence_service as cp
    det = {"boxes": [[10, 10, 100, 100]], "scores": [0.397], "image_size": [200, 200]}
    for present in (0.979, 0.961, 0.913, 0.892, 0.875, 0.613, 0.356):
        monkeypatch.setattr(cp, "presence_score", lambda *a, **k: present)
        assert cp.verify_boxes(object(), det, "the drapery"), present


def test_clip_verify_treats_unjudgeable_as_refusal(monkeypatch):
    """None means "could not judge" — it must never be read as a pass."""
    from backend.services import clip_presence_service as cp
    det = {"boxes": [[10, 10, 100, 100]], "scores": [0.9], "image_size": [200, 200]}
    monkeypatch.setattr(cp, "presence_score", lambda *a, **k: None)
    assert cp.verify_boxes(object(), det, "x") == []
    assert cp.verify_boxes(object(), None, "x") == []
    assert cp.verify_boxes(object(), {"boxes": [], "image_size": [200, 200]}, "x") == []


def test_clip_presence_adapter_spec():
    from backend.services.vision_orchestrator.adapters import ClipPresenceAdapter
    from backend.services.vision_orchestrator.contracts import Capability, ResourceKind
    from backend.services import clip_presence_service as cp
    a = ClipPresenceAdapter()
    assert a.spec.name == "clip_vit_b32" and a.spec.license == "MIT"
    assert a.spec.capability is Capability.EMBED
    assert a.spec.resource is ResourceKind.GPU
    assert a.spec.revision == cp.REVISION
    assert cp.DEFAULT_PRESENCE_THRESHOLD == 0.25      # calibrated, see the measured table


def test_grounded_receipt_credits_all_three_models_when_verified():
    d = ss.suggestion_from_grounded_phrase(
        {"id": "r1", "geometry_rev": 1}, phrase="the drapery", run_id="r", score=0.397,
        detector_model="grounding_dino_tiny", detector_revision="a2bb",
        presence=0.8916, verifier_model="clip_vit_b32", verifier_revision="3d74")
    p = d["provenance"]
    assert p["adapter"] == "grounding_dino_tiny+clip_vit_b32+sam2"
    assert p["verifier_model"] == "clip_vit_b32" and p["verifier_revision"] == "3d74"
    # both scores stay OFF the mark (contract §6) and ride the descriptor
    assert "presence" not in p and "confidence" not in p
    assert d["presence"] == 0.8916 and d["confidence"] == 0.397


def test_produce_field_grounded_sam_sequences_detector_clip_then_sam2(monkeypatch):
    """Three models, one card: detector → CLIP → SAM2, each leaving before the next arrives."""
    post = {"_id": ObjectId(), "region_annotations": [{"id": "r1", "box": {"x": 0, "y": 0, "w": 1, "h": 1}}]}
    posts, runs = _Posts(post), FakeCollection()
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(svc, "vision_run_collection", runs)
    monkeypatch.setattr(R, "_fetch_post_image_cached", _img)
    from backend.services import evidence_embedding_service as ees
    from backend.services import grounding_detector_service as gd
    from backend.services import clip_presence_service as cps
    from backend.services.vision_orchestrator import refine_session as rs_mod

    class _Img:
        size = (200, 200)
        def convert(self, m): return self
    monkeypatch.setattr(ees, "_pil", lambda b: _Img())
    monkeypatch.setattr(gd, "is_available", lambda: True)
    monkeypatch.setattr(cps, "is_available", lambda: True)

    order = []
    class _DArt: data = _detection(score=0.397)       # a score P8-B would have REFUSED
    class _DJob: artifact = _DArt()
    class _CArt: data = [{"box_xyxy": [0.1, 0.1, 0.9, 0.9], "detector_score": 0.397, "presence": 0.892}]
    class _CJob: artifact = _CArt()

    async def _det(adapter, payload, **kw): order.append("detect"); return _DJob()
    async def _det_unload(name): order.append(f"unload:{name}")
    async def _clip(adapter, payload, **kw): order.append("clip"); return _CJob()
    async def _clip_unload(name): order.append(f"unload:{name}")
    import backend.routers.posts as RR
    RR._grounding_mgr = type("M", (), {"run_adapter": staticmethod(_det),
                                       "unload": staticmethod(_det_unload)})()
    RR._grounding_adapter = object()
    RR._clip_mgr = type("M", (), {"run_adapter": staticmethod(_clip),
                                  "unload": staticmethod(_clip_unload)})()
    RR._clip_adapter = object()

    async def _preview(image_bytes, prompt, base_id, base_rev):
        order.append("sam2")
        return {"id": "refine_z", "geometry_rev": 1, "mask_rle": {"size": [4, 4], "counts": "M"}}
    monkeypatch.setattr(rs_mod.refine_session, "available", lambda: True)
    monkeypatch.setattr(rs_mod.refine_session, "preview", _preview)
    try:
        resp = run(R.produce_field(str(posts.post["_id"]),
                                   R.ProduceFieldRequest(producer="grounded_sam_find_parts",
                                                         phrase="the drapery")))
        assert resp["status"] == "ready"
        sug = resp["suggestions"][0]
        assert sug["provenance"]["adapter"] == "grounding_dino_tiny+clip_vit_b32+sam2"
        assert sug["presence"] == 0.892
        assert order == ["detect", "unload:grounding_dino_tiny",
                         "clip", "unload:clip_vit_b32", "sam2"], order
        assert posts.writes == []
    finally:
        RR._grounding_mgr = RR._clip_mgr = None
        RR._grounding_adapter = RR._clip_adapter = None


def test_produce_field_refuses_when_detector_fires_but_clip_rejects(monkeypatch):
    """THE new refusal: the detector proposed a box, CLIP says the crop is not that thing, so
    SAM2 is never called and no region is minted."""
    post = {"_id": ObjectId(), "region_annotations": []}
    posts, runs = _Posts(post), FakeCollection()
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(svc, "vision_run_collection", runs)
    monkeypatch.setattr(R, "_fetch_post_image_cached", _img)
    from backend.services import evidence_embedding_service as ees
    from backend.services import grounding_detector_service as gd
    from backend.services import clip_presence_service as cps
    from backend.services.vision_orchestrator import refine_session as rs_mod

    class _Img:
        size = (200, 200)
        def convert(self, m): return self
    monkeypatch.setattr(ees, "_pil", lambda b: _Img())
    monkeypatch.setattr(gd, "is_available", lambda: True)
    monkeypatch.setattr(cps, "is_available", lambda: True)

    sam_called = []
    class _DArt: data = _detection(score=0.444)       # the purple-bicycle score, which the
    class _DJob: artifact = _DArt()                    # detector alone could not reject
    class _CJob: artifact = None                       # CLIP verified nothing
    async def _det(adapter, payload, **kw): return _DJob()
    async def _noop(name): pass
    async def _clip(adapter, payload, **kw): return _CJob()
    import backend.routers.posts as RR
    RR._grounding_mgr = type("M", (), {"run_adapter": staticmethod(_det), "unload": staticmethod(_noop)})()
    RR._grounding_adapter = object()
    RR._clip_mgr = type("M", (), {"run_adapter": staticmethod(_clip), "unload": staticmethod(_noop)})()
    RR._clip_adapter = object()
    async def _never(*a, **k): sam_called.append(1); return {}
    monkeypatch.setattr(rs_mod.refine_session, "preview", _never)
    try:
        resp = run(R.produce_field(str(posts.post["_id"]),
                                   R.ProduceFieldRequest(producer="grounded_sam_find_parts",
                                                         phrase="a purple bicycle")))
        assert resp["status"] == "empty" and resp["suggestions"] == []
        assert sam_called == [], "a CLIP-rejected box must never reach SAM2"
    finally:
        RR._grounding_mgr = RR._clip_mgr = None
        RR._grounding_adapter = RR._clip_adapter = None


# ─────────── P8-D: presence_check + enumerate — READINGS, not marks ───────────

def _verified(n=1, presence=0.93):
    return [{"box_xyxy": [0.1, 0.1, 0.5, 0.5], "presence": presence, "detector_score": 0.5}
            for _ in range(n)]


def test_presence_verdict_says_yes_with_the_verifier_confidence():
    v = ss.presence_verdict(_verified(2), phrase="a cross", run_id="r", detector_fired=True,
                            detector_model="grounding_dino_tiny", verifier_model="clip_vit_b32")
    assert v["type"] == "presence_reading"            # a reading, not a mark
    assert v["present"] is True and v["basis"] == "verified"
    assert v["instances"] == 2 and v["confidence"] == 0.93
    assert "geometry" not in v                         # nothing to put on the image
    assert v["provenance"]["adapter"] == "grounding_dino_tiny+clip_vit_b32"


def test_presence_verdict_can_say_NO_which_no_detector_alone_can():
    """The circuit gains the ability to answer 'not here' — and distinguishes plain absence from
    a near miss, because they mean different things to a curator."""
    near = ss.presence_verdict([], phrase="a laptop", run_id="r", detector_fired=True)
    assert near["present"] is False
    assert near["basis"] == "detector_proposed_but_unverified"
    assert near["confidence"] is None

    plain = ss.presence_verdict([], phrase="a laptop", run_id="r", detector_fired=False)
    assert plain["present"] is False and plain["basis"] == "not_detected"


def test_presence_verdict_needs_a_question():
    assert ss.presence_verdict(_verified(), phrase="", run_id="r") is None
    assert ss.presence_verdict(_verified(), phrase="   ", run_id="r") is None


def test_enumerate_counts_the_VERIFIED_not_the_guessed():
    r = ss.enumerate_reading(_verified(3), phrase="the figures", run_id="r",
                             detector_candidates=9, detector_model="grounding_dino_tiny")
    assert r["type"] == "count_reading"
    assert r["count"] == 3 and r["considered"] == 9    # the gap IS the point
    assert len(r["instances"]) == 3
    assert all("box_xyxy" in i and "presence" in i for i in r["instances"])
    assert "geometry" not in r                          # counting mints nothing


def test_enumerate_zero_is_a_real_answer_and_records_what_was_considered():
    """Ask for something absent and the count is 0 — not 'however many boxes fired'. "0 of 14"
    and "0 of 0" are different statements about the image, so both are kept."""
    z = ss.enumerate_reading([], phrase="bicycles", run_id="r", detector_candidates=14)
    assert z["count"] == 0 and z["considered"] == 14 and z["instances"] == []
    none = ss.enumerate_reading([], phrase="bicycles", run_id="r", detector_candidates=0)
    assert none["count"] == 0 and none["considered"] == 0
    assert ss.enumerate_reading(_verified(), phrase="  ", run_id="r") is None


def _install_verify(monkeypatch, *, survivors, boxes=1, gd_ok=True, clip_ok=True):
    """Stub the shared detector→CLIP half so the reading verbs are testable without a GPU."""
    from backend.services import evidence_embedding_service as ees
    from backend.services import grounding_detector_service as gd
    from backend.services import clip_presence_service as cps

    class _Img:
        size = (200, 200)
        def convert(self, m): return self
    monkeypatch.setattr(ees, "_pil", lambda b: _Img())
    monkeypatch.setattr(gd, "is_available", lambda: gd_ok)
    monkeypatch.setattr(cps, "is_available", lambda: clip_ok)

    det = {"boxes": [[10, 10, 100, 100]] * boxes, "scores": [0.5] * boxes,
           "image_size": [200, 200]} if boxes else None
    class _DArt: data = det
    class _DJob: artifact = _DArt() if det else None
    class _CArt: data = survivors
    class _CJob: artifact = _CArt() if survivors else None
    async def _run_det(adapter, payload, **kw): return _DJob()
    async def _run_clip(adapter, payload, **kw): return _CJob()
    async def _noop(name): pass
    import backend.routers.posts as RR
    RR._grounding_mgr = type("M", (), {"run_adapter": staticmethod(_run_det),
                                       "unload": staticmethod(_noop)})()
    RR._grounding_adapter = object()
    RR._clip_mgr = type("M", (), {"run_adapter": staticmethod(_run_clip),
                                  "unload": staticmethod(_noop)})()
    RR._clip_adapter = object()
    return RR


def _reading_post(monkeypatch):
    post = {"_id": ObjectId(), "region_annotations": []}
    posts, runs = _Posts(post), FakeCollection()
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(svc, "vision_run_collection", runs)
    monkeypatch.setattr(R, "_fetch_post_image_cached", _img)
    return posts, runs


def test_produce_field_presence_check_present_and_absent(monkeypatch):
    posts, runs = _reading_post(monkeypatch)
    RR = _install_verify(monkeypatch, survivors=_verified(1))
    try:
        resp = run(R.produce_field(str(posts.post["_id"]),
                                   R.ProduceFieldRequest(producer="presence_check", phrase="a cross")))
        assert resp["status"] == "ready"
        v = resp["suggestions"][0]
        assert v["type"] == "presence_reading" and v["present"] is True
    finally:
        RR._grounding_mgr = RR._clip_mgr = None

    RR = _install_verify(monkeypatch, survivors=[])
    try:
        resp = run(R.produce_field(str(posts.post["_id"]),
                                   R.ProduceFieldRequest(producer="presence_check", phrase="a laptop")))
        # "absent" is a RESULT — status ready, a verdict returned, present False
        assert resp["status"] == "ready"
        v = resp["suggestions"][0]
        assert v["present"] is False and v["basis"] == "detector_proposed_but_unverified"
        assert posts.writes == []
    finally:
        RR._grounding_mgr = RR._clip_mgr = None


def test_produce_field_enumerate_counts_survivors(monkeypatch):
    posts, runs = _reading_post(monkeypatch)
    RR = _install_verify(monkeypatch, survivors=_verified(3), boxes=7)
    try:
        resp = run(R.produce_field(str(posts.post["_id"]),
                                   R.ProduceFieldRequest(producer="enumerate", phrase="the figures")))
        assert resp["status"] == "ready"
        r = resp["suggestions"][0]
        assert r["type"] == "count_reading" and r["count"] == 3 and r["considered"] == 7
        assert posts.writes == []
    finally:
        RR._grounding_mgr = RR._clip_mgr = None


def test_reading_verbs_fail_closed_without_the_presence_gate(monkeypatch):
    """Same rule as P8-C: with the verifier gone, a permissive detector must not answer alone."""
    posts, runs = _reading_post(monkeypatch)
    for producer in ("presence_check", "enumerate"):
        RR = _install_verify(monkeypatch, survivors=_verified(1), clip_ok=False)
        try:
            resp = run(R.produce_field(str(posts.post["_id"]),
                                       R.ProduceFieldRequest(producer=producer, phrase="a cross")))
            assert resp["status"] == "unavailable", producer
            assert resp["available"] is False and resp["suggestions"] == []
        finally:
            RR._grounding_mgr = RR._clip_mgr = None


def test_reading_verbs_need_a_phrase(monkeypatch):
    posts, runs = _reading_post(monkeypatch)
    for producer in ("presence_check", "enumerate"):
        resp = run(R.produce_field(str(posts.post["_id"]),
                                   R.ProduceFieldRequest(producer=producer)))
        assert resp["status"] == "empty" and resp["suggestions"] == []
