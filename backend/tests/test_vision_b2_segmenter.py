"""
VISION-BUILD-001 B2 — general segmentation adapter (mask identity).

Tests the pure conversion (native instance masks → regions with authoritative mask_rle)
without loading a model, plus the numpy encoder's equivalence to the pure encoder and the
geometry guard that semantic parenting can never clip a mask region. A real YOLO
end-to-end run is captured as evidence in the B2 report, not in the always-run suite.
"""
import json
import numpy as np
import pytest

from backend.services import mask_geometry as mg
from backend.services.vision_orchestrator.adapters import masks_to_regions, coco_category
from backend.schemas.post import Region


def rect_mask(h, w, r0, r1, c0, c1):
    m = np.zeros((h, w), dtype=np.uint8)
    m[r0:r1, c0:c1] = 1
    return m


NAMES = {0: "person", 24: "handbag", 60: "diningtable"}


# ── numpy encoder == pure encoder (byte-identical RLE) ───────────────────────
@pytest.mark.parametrize("h,w", [(20, 20), (30, 12), (12, 30), (64, 64)])
def test_rle_encode_mask_matches_pure(h, w):
    m = rect_mask(h, w, 3, h - 4, 2, w - 5)
    m[0, 0] = 1                      # edge-touching pixel
    bits = bytearray(m.reshape(-1).tolist())
    assert mg.rle_encode_mask(m) == mg.rle_encode(bits, h, w)


# ── multi-object collage: each instance keeps its own authoritative mask ──────
def test_multi_object_collage_not_collapsed():
    h, w = 40, 90
    masks = [rect_mask(h, w, 8, 30, 5, 25),      # left
             rect_mask(h, w, 6, 32, 35, 55),     # centre
             rect_mask(h, w, 10, 28, 65, 85)]    # right
    regions = masks_to_regions(masks, [0, 0, 0], [0.9, 0.8, 0.7], NAMES)
    assert len(regions) == 3                                   # none merged
    centers = []
    for r in regions:
        assert mg.rle_is_valid(r["mask_rle"])                 # authoritative mask present
        assert r["box"] == mg.rle_bbox_norm(r["mask_rle"])    # box is DERIVED from mask
        assert r["geometry_rev"] >= 1
        assert r["geometry_provenance"]["kind"] == "mask"
        assert r["geometry_provenance"]["adapter"] == "yolo11n_seg"
        assert r["detector"] == "yolo" and r["actor"] == "auto"
        b = r["box"]; centers.append(round(b["x"] + b["w"] / 2, 3))
    assert len(set(centers)) == 3                              # three distinct locations


def test_five_sculpture_style_stays_five_regions():
    # five separate instance masks (like five detected heads) must stay five regions.
    h, w = 30, 150
    masks = [rect_mask(h, w, 6, 26, 5 + i * 28, 25 + i * 28) for i in range(5)]
    regions = masks_to_regions(masks, [0] * 5, [0.9] * 5, NAMES)
    assert len(regions) == 5
    xs = sorted(r["box"]["x"] for r in regions)
    assert len(set(xs)) == 5                                   # each on its own slice


# ── disconnected shape → multi-ring polygons; holes preserved by RLE ─────────
def test_disconnected_instance_yields_multiple_rings():
    h, w = 40, 60
    m = np.zeros((h, w), dtype=np.uint8)
    m[8:24, 6:20] = 1                 # blob A
    m[10:26, 38:52] = 1               # blob B (same instance mask, disjoint)
    regions = masks_to_regions([m], [0], [0.9], NAMES)
    assert len(regions) == 1
    assert len(regions[0]["polygons"]) >= 2                    # both components as rings


# ── edge-touching + portrait/landscape aspect ────────────────────────────────
def test_edge_touching_and_aspect():
    # landscape, mask touching top-left border
    land = rect_mask(30, 80, 0, 15, 0, 20)
    r_land = masks_to_regions([land], [0], [0.9], NAMES)[0]
    assert r_land["box"]["x"] == 0.0 and r_land["box"]["y"] == 0.0
    # portrait
    port = rect_mask(80, 30, 50, 78, 4, 26)
    r_port = masks_to_regions([port], [0], [0.9], NAMES)[0]
    assert r_port["box"] == mg.rle_bbox_norm(r_port["mask_rle"])


# ── empty detection: honest, no fabricated mask ──────────────────────────────
def test_empty_mask_is_dropped_not_fabricated():
    empty = np.zeros((20, 20), dtype=np.uint8)
    solid = rect_mask(20, 20, 4, 16, 4, 16)
    regions = masks_to_regions([empty, solid], [0, 0], [0.9, 0.8], NAMES)
    assert len(regions) == 1                                   # empty instance skipped
    assert mg.rle_area(regions[0]["mask_rle"]) > 0


# ── geometry guard: a mask region's box is the mask's, independent of any parent ─
def test_mask_geometry_independent_of_parent_box():
    m = rect_mask(40, 40, 5, 35, 5, 35)
    region = masks_to_regions([m], [0], [0.9], NAMES)[0]
    box_before = dict(region["box"])
    # re-canonicalising (what the route does) must not move the mask's derived box, and
    # there is no code path that clips a mask region toward a smaller "parent".
    mg.canonicalize_geometry(region, provenance={"via": "detect-regions"})
    assert region["box"] == box_before == mg.rle_bbox_norm(region["mask_rle"])
    assert region["geometry_provenance"]["kind"] == "mask"    # never downgraded to box


# ── persistence: a YOLO-shaped region round-trips through the model + JSON ─────
def test_yolo_region_persists():
    m = rect_mask(48, 48, 6, 40, 6, 40)
    region = masks_to_regions([m], [0], [0.95], NAMES)[0]
    model = Region(**{**region, "box": region["box"]})
    dumped = json.loads(json.dumps(model.model_dump()))
    assert dumped["mask_rle"] == region["mask_rle"]
    assert dumped["polygons"] and dumped["geometry_rev"] >= 1
    back, h, w = mg.rle_decode(dumped["mask_rle"])
    assert bytes(back) == bytes(mg.rle_decode(region["mask_rle"])[0])


def test_coco_category_mapping():
    assert coco_category("person") == "figure"
    assert coco_category("handbag") == "garment"
    assert coco_category("diningtable") == "object"
