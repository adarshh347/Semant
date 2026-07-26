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
