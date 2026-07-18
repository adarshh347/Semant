"""
REGION-GEOMETRY-001 — the canonical Region geometry contract.

Covers the coordinate frames the report names (landscape / portrait / square /
letterboxed) plus the exact five-sculpture failure as a regression: a fine part
that lies outside the one detected anchor must NOT be parented into it and must
NOT be crushed to a sliver.
"""
import pytest
from backend.services import region_geometry as rg


# ── round-trip invariant: source px → normalized → px → normalized ──────────
@pytest.mark.parametrize("W,H", [(680, 286), (300, 900), (512, 512), (1920, 1080)])
def test_pixel_normalized_roundtrip(W, H):
    # a box at all four corners + centre
    boxes_px = [
        {"x": 0, "y": 0, "w": W * 0.2, "h": H * 0.2},                 # top-left
        {"x": W * 0.8, "y": 0, "w": W * 0.2, "h": H * 0.2},           # top-right
        {"x": 0, "y": H * 0.8, "w": W * 0.2, "h": H * 0.2},           # bottom-left
        {"x": W * 0.8, "y": H * 0.8, "w": W * 0.2, "h": H * 0.2},     # bottom-right
        {"x": W * 0.4, "y": H * 0.4, "w": W * 0.2, "h": H * 0.2},     # centre
    ]
    for b in boxes_px:
        norm = rg.pixels_to_normalized(b, W, H)
        # normalized stays in frame
        assert 0.0 <= norm["x"] <= 1.0 and 0.0 <= norm["y"] <= 1.0
        assert norm["x"] + norm["w"] <= 1.0001 and norm["y"] + norm["h"] <= 1.0001
        # back to pixels, then normalized again — stable to rounding
        again = rg.pixels_to_normalized(
            {"x": norm["x"] * W, "y": norm["y"] * H, "w": norm["w"] * W, "h": norm["h"] * H}, W, H)
        for k in "xywh":
            assert abs(again[k] - norm[k]) < 1e-3


def test_normalized_frame_is_source_not_container():
    # dividing by a container/crop size instead of natural size (hypothesis #2)
    # would move the box; the helper only accepts natural dims and keeps it in frame.
    b = rg.pixels_to_normalized({"x": 340, "y": 143, "w": 136, "h": 57}, 680, 286)
    assert b == {"x": 0.5, "y": 0.5, "w": 0.2, "h": pytest.approx(57 / 286, abs=1e-4)}


# ── letterbox inversion (hypothesis #1) ─────────────────────────────────────
def test_unletterbox_maps_padded_square_back_to_original():
    # 680×286 fit into a 640 square: scale 640/680, padded top/bottom.
    orig_w, orig_h, canvas = 680, 286, 640
    scale = canvas / orig_w
    pad_y = (canvas - orig_h * scale) / 2.0
    # a box that is the full original frame, expressed in canvas-normalized coords
    lb = {"x": 0.0, "y": pad_y / canvas, "w": 1.0, "h": (orig_h * scale) / canvas}
    out = rg.unletterbox_normalized(lb, orig_w, orig_h, canvas)
    assert out["x"] == pytest.approx(0.0, abs=1e-3)
    assert out["y"] == pytest.approx(0.0, abs=1e-3)
    assert out["w"] == pytest.approx(1.0, abs=1e-3)
    assert out["h"] == pytest.approx(1.0, abs=1e-3)


# ── format conversion ───────────────────────────────────────────────────────
def test_xyxy_to_xywh():
    assert rg.xyxy_to_xywh(0.2, 0.3, 0.6, 0.9) == {"x": 0.2, "y": 0.3, "w": pytest.approx(0.4), "h": pytest.approx(0.6)}
    # reversed corners still yield a positive box
    assert rg.xyxy_to_xywh(0.6, 0.9, 0.2, 0.3) == {"x": 0.2, "y": 0.3, "w": pytest.approx(0.4), "h": pytest.approx(0.6)}


# ── overlap ──────────────────────────────────────────────────────────────────
def test_overlap_fraction():
    outer = {"x": 0.2, "y": 0.2, "w": 0.4, "h": 0.4}
    assert rg.overlap_fraction({"x": 0.3, "y": 0.3, "w": 0.1, "h": 0.1}, outer) == pytest.approx(1.0)
    assert rg.overlap_fraction({"x": 0.7, "y": 0.7, "w": 0.1, "h": 0.1}, outer) == pytest.approx(0.0)
    half = rg.overlap_fraction({"x": 0.5, "y": 0.3, "w": 0.2, "h": 0.1}, outer)  # half sticks out right
    assert half == pytest.approx(0.5, abs=0.01)


# ── parenting is geometry-first (the fix) ───────────────────────────────────
def test_match_parent_requires_genuine_containment():
    anchors = [{"id": "a", "label": "person", "box": {"x": 0.2, "y": 0.2, "w": 0.3, "h": 0.75}}]
    inside = {"x": 0.28, "y": 0.28, "w": 0.14, "h": 0.33}
    outside = {"x": 0.62, "y": 0.25, "w": 0.14, "h": 0.35}
    assert rg.match_parent(inside, anchors, parent_label="person")["id"] == "a"
    # a part outside the only anchor is NOT adopted — even though its label matches.
    assert rg.match_parent(outside, anchors, parent_label="person") is None


def test_label_never_overrides_geometry():
    # two anchors; the label points at the far one, but the part sits in the near one.
    anchors = [
        {"id": "near", "label": "figure", "box": {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.8}},
        {"id": "far", "label": "person", "box": {"x": 0.7, "y": 0.1, "w": 0.25, "h": 0.8}},
    ]
    part = {"x": 0.15, "y": 0.2, "w": 0.1, "h": 0.2}  # inside 'near'
    assert rg.match_parent(part, anchors, parent_label="person")["id"] == "near"


def test_tightest_genuine_container_wins():
    anchors = [
        {"id": "big", "label": "scene", "box": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}},
        {"id": "small", "label": "face", "box": {"x": 0.4, "y": 0.4, "w": 0.2, "h": 0.2}},
    ]
    part = {"x": 0.45, "y": 0.45, "w": 0.05, "h": 0.05}
    assert rg.match_parent(part, anchors)["id"] == "small"


# ── clipping never destroys geometry ────────────────────────────────────────
def test_clip_nudges_genuine_child():
    parent = {"x": 0.2, "y": 0.2, "w": 0.4, "h": 0.4}
    part = {"x": 0.5, "y": 0.3, "w": 0.2, "h": 0.1}  # overflows right, but mostly inside
    out = rg.clip_box_to_parent(part, parent)
    assert out["w"] > rg.MIN_SIZE and out["h"] > rg.MIN_SIZE
    assert out["x"] + out["w"] <= parent["x"] + parent["w"] + 0.041


def test_clip_refuses_to_crush():
    # a box wholly to the right of the parent would clip to a sliver — the helper
    # keeps the original instead of emitting a degenerate w=0.01 box.
    parent = {"x": 0.2, "y": 0.2, "w": 0.27, "h": 0.75}
    part = {"x": 0.62, "y": 0.27, "w": 0.13, "h": 0.35}
    out = rg.clip_box_to_parent(part, parent)
    assert out == rg.normalize_box(part)  # untouched, not crushed to 0.01


# ── the five-sculpture regression ───────────────────────────────────────────
def test_five_sculpture_no_crush_and_no_misparent():
    """One `person` anchor over the centre figure; parts spread across the frame.
    The off-anchor parts (Solanki far-left, Amaravati/Gandhara far-right) must
    keep their true boxes — not be parented into the anchor or crushed to slivers,
    which is exactly what the corrupted post shows."""
    anchor = {"id": "seg_0", "label": "person", "box": {"x": 0.2055, "y": 0.2204, "w": 0.2693, "h": 0.7526}}
    parts = {
        "Solanki face": {"x": 0.03, "y": 0.25, "w": 0.12, "h": 0.35},   # far left
        "Gupta face":   {"x": 0.28, "y": 0.28, "w": 0.14, "h": 0.33},   # inside anchor
        "Amaravati face": {"x": 0.60, "y": 0.27, "w": 0.12, "h": 0.36},  # far right
        "Gandhara face":  {"x": 0.80, "y": 0.24, "w": 0.13, "h": 0.35},  # far right
    }
    for label, box in parts.items():
        parent = rg.match_parent(box, [anchor], parent_label="person")
        final = rg.clip_box_to_parent(box, parent["box"]) if parent else rg.normalize_box(box)
        if label == "Gupta face":
            assert parent is not None                     # genuinely inside → parented
        else:
            assert parent is None                         # outside → top-level, own frame
            assert final == rg.normalize_box(box)         # box preserved, not relocated
            assert not rg.is_degenerate(final)            # never a 0.01 sliver
            # and it lands on its OWN half of the frame, not on the anchor
            cx = final["x"] + final["w"] / 2
            assert not rg.center_in(final, anchor["box"])
