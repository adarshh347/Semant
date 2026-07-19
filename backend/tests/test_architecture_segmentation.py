"""
VISION-C · C2 — architecture surface segmentation contract.

Tests the ADE→category mapping and the semantic-map → separate-mask-candidate conversion
on a SYNTHETIC semantic map (no model load), so it is fast and deterministic. The real
SegFormer-B0 run is exercised at the C2 gate (service + endpoint + browser).
"""
import numpy as np
import pytest

from backend.services import architecture_segmentation_service as arch
from backend.services import mask_geometry as mg
from backend.schemas.post import Region


def test_category_mapping():
    assert arch._category_for("wall") == "surface"
    assert arch._category_for("floor, flooring") == "surface"
    assert arch._category_for("windowpane, window") == "opening"
    assert arch._category_for("door, double door") == "opening"
    assert arch._category_for("building, edifice") == "structure"
    assert arch._category_for("column, pillar") == "structure"
    assert arch._category_for("person, individual") is None      # not architectural
    assert arch._category_for("sculpture") is None


def test_semantic_map_becomes_separate_masks():
    H = W = 60
    pred = np.zeros((H, W), dtype=np.int64)
    pred[:25, :] = 0          # wall  (top band)
    pred[40:, :] = 3          # floor (bottom band)
    pred[28:38, 20:40] = 8    # window (a rectangle in the middle)
    id2label = {0: "wall", 3: "floor", 8: "windowpane, window", 12: "person"}
    probs = np.zeros((13, H, W), dtype=np.float32)
    for c in (0, 3, 8):
        probs[c][pred == c] = 0.9

    regions = arch._regions_from_semantic(pred, probs, id2label, W, H)
    labels = {r["label"] for r in regions}
    assert {"wall", "floor", "window"} <= labels                 # three separate surfaces
    by_label = {r["label"]: r for r in regions}
    # each is an authoritative mask with derived geometry + arch provenance
    for lbl in ("wall", "floor", "window"):
        r = by_label[lbl]
        assert mg.rle_is_valid(r["mask_rle"]) and r["polygons"]
        assert r["box"] == mg.rle_bbox_norm(r["mask_rle"])       # box derived from mask
        assert r["detector"] == "segformer_ade"
        assert r["geometry_provenance"]["adapter"] == "segformer_b0_ade"
        Region(**r)                                              # schema-valid
    assert by_label["window"]["category"] == "opening"
    assert by_label["wall"]["category"] == "surface"


def test_labels_never_touch_geometry():
    # the window mask's bbox is exactly its pixels — not clipped toward wall/floor.
    H = W = 60
    pred = np.full((H, W), 0, dtype=np.int64)   # all wall
    pred[10:20, 10:30] = 8                       # a window inside the wall
    id2label = {0: "wall", 8: "windowpane, window"}
    probs = np.zeros((9, H, W), dtype=np.float32)
    probs[0][pred == 0] = 0.9
    probs[8][pred == 8] = 0.9
    regions = arch._regions_from_semantic(pred, probs, id2label, W, H)
    win = next(r for r in regions if r["label"] == "window")
    b = win["box"]
    assert b["x"] == pytest.approx(10 / W, abs=0.02) and b["w"] == pytest.approx(20 / W, abs=0.02)


def test_below_area_floor_dropped():
    H = W = 100
    pred = np.zeros((H, W), dtype=np.int64)      # all wall
    pred[0, 0] = 8                                 # a 1px window — below the 1% floor
    id2label = {0: "wall", 8: "windowpane, window"}
    probs = np.zeros((9, H, W), dtype=np.float32)
    probs[0][pred == 0] = 0.9; probs[8][pred == 8] = 0.9
    regions = arch._regions_from_semantic(pred, probs, id2label, W, H)
    assert not any(r["label"] == "window" for r in regions)      # tiny blob dropped
