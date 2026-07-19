"""
VISION-F · F3 — geometry recovery planner + executor.

Proves the action per Region is chosen honestly (mask→retain, genuine polygon→derive, box→SAM,
SAM-down→retain_box), a derive/refine preserves the Region's id + label + curator fields and
bumps geometry_rev, masks are never fabricated from a 4-point box, and detached grounds are
marked (never deleted).
"""
import asyncio

import numpy as np
import pytest

from backend.services import geometry_recovery as gr
from backend.services import vision_recovery as vr
from backend.services import mask_geometry as mg


FULL = {"sam": True, "geometry": True}


def _mask_region(rid="m0"):
    b = np.zeros((40, 40), np.uint8); b[5:30, 5:30] = 1
    r = {"id": rid, "mask_rle": mg.rle_encode_mask(b), "label": "kept", "user_note": "note",
         "prioritised": True, "weight": 4, "actor": "creator"}
    mg.canonicalize_geometry(r, provenance={"a": "t"})
    return r


def _polygon_region(rid="p0"):
    # a genuine traced polygon (many points), normalized
    ring = [[0.2 + 0.15 * np.cos(t), 0.3 + 0.2 * np.sin(t)] for t in np.linspace(0, 6.0, 20)]
    return {"id": rid, "polygon": ring, "box": {"x": 0.05, "y": 0.1, "w": 0.3, "h": 0.4},
            "label": "flower", "user_note": "curator", "prioritised": False, "weight": 0, "actor": "auto"}


def _box_region(rid="b0"):
    return {"id": rid, "box": {"x": 0.2, "y": 0.2, "w": 0.3, "h": 0.3}, "label": "crown",
            "user_note": "keep me", "prioritised": True, "weight": 2, "actor": "auto"}


def _box_shaped_polygon(rid="bp0"):
    return {"id": rid, "polygon": [[0.2, 0.2], [0.5, 0.2], [0.5, 0.5], [0.2, 0.5]],  # 4 pts = a box
            "box": {"x": 0.2, "y": 0.2, "w": 0.3, "h": 0.3}, "label": "x"}


# ── classification + planning ────────────────────────────────────────────────
def test_classify_distinguishes_mask_polygon_box():
    assert gr.classify(_mask_region()) == "mask"
    assert gr.classify(_polygon_region()) == "polygon"
    assert gr.classify(_box_region()) == "box"
    assert gr.classify(_box_shaped_polygon()) == "box"      # 4-pt "polygon" is really a box


def test_plan_chooses_honest_action():
    assert gr.plan_region(_mask_region(), FULL)["action"] == "retain_mask"
    assert gr.plan_region(_polygon_region(), FULL)["action"] == "derive_polygon"
    assert gr.plan_region(_box_region(), FULL)["action"] == "sam_refine_box"


def test_sam_down_falls_back_to_retain_box_never_fabricates():
    down = {"sam": False, "geometry": True}
    assert gr.plan_region(_box_region(), down)["action"] == "retain_box"   # honest, not a fake mask


# ── derive preserves identity, bumps rev ─────────────────────────────────────
def test_derive_from_polygon_preserves_identity():
    r = _polygon_region()
    out = gr.derive_mask_from_polygon(r, (100, 100))
    assert out is not None and mg.rle_is_valid(r["mask_rle"])
    assert r["id"] == "p0" and r["label"] == "flower" and r["user_note"] == "curator"  # identity kept
    assert r["geometry_rev"] >= 1 and "_prev_geometry" in r                            # rev bumped, old saved


def test_apply_mask_preserves_non_geometry_fields():
    r = _box_region()
    b = np.zeros((30, 30), np.uint8); b[3:20, 3:20] = 1
    gr.apply_mask_to_region(r, mg.rle_encode_mask(b), method="sam-refine-box", image_hw=(30, 30))
    assert r["label"] == "crown" and r["user_note"] == "keep me" and r["prioritised"] is True
    assert r["weight"] == 2 and mg.rle_is_valid(r["mask_rle"])
    assert r["_prev_geometry"]["box"] == {"x": 0.2, "y": 0.2, "w": 0.3, "h": 0.3}       # old geometry kept


# ── detached grounds marked, not deleted ─────────────────────────────────────
def test_detached_grounds_marked_visibly():
    post = {"region_annotations": [{"id": "r0"}],
            "grounds": [{"id": "g0", "ground_type": "region", "region_id": "gone"},
                        {"id": "g1", "ground_type": "region", "region_id": "r0"}]}
    marked = gr.mark_detached_grounds(post)
    assert marked == ["g0"]
    assert post["grounds"][0]["detached"] is True and post["grounds"][0]["detached_reason"]
    assert "detached" not in post["grounds"][1]                                          # attached one untouched
    assert len(post["grounds"]) == 2                                                     # nothing deleted


# ── executor preserves curator-only hash across a geometry change ────────────
class _FakeRefine:
    async def preview(self, image_bytes, prompt, base_id=None, base_rev=0):
        b = np.zeros((40, 40), np.uint8); b[5:30, 8:32] = 1
        return {"mask_rle": mg.rle_encode_mask(b)}


def test_recover_post_preserves_curator_only_hash():
    post = {"_id": "pX", "region_annotations": [_box_region("b0"), _mask_region("m0")], "grounds": []}
    before = vr.curator_only_hash(post)
    plan = gr.plan_post(post, FULL)
    asyncio.run(gr.recover_post(post, b"img", plan, refine_session=_FakeRefine(), image_hw=(40, 40)))
    assert vr.curator_only_hash(post) == before                     # labels/notes/priority survive
    assert mg.rle_is_valid(post["region_annotations"][0]["mask_rle"])  # the box became a mask
