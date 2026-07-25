"""
VISION-BUILD-001 Increment A — the canonical mask-geometry contract.

Synthetic round-trips for the hard cases the gate names: rectangles, concave shapes,
disconnected components, holes (where cv2 is available), edge-touching masks and very
small masks — plus persistence (BSON/JSON-safe) and coordinate registration across
resolutions. The RLE is the authoritative identity, so the exact round-trip is
RLE → mask → RLE; polygons are a derived render aid and are checked by IoU.
"""
import json
import pytest

from backend.services import mask_geometry as mg
from backend.schemas.post import Region


# ── synthetic mask builders (row-major bit buffers) ──────────────────────────
def make_bits(h, w, fn):
    bits = bytearray(h * w)
    for r in range(h):
        for c in range(w):
            if fn(r, c):
                bits[r * w + c] = 1
    return bits


def iou(a: bytearray, b: bytearray) -> float:
    inter = sum(1 for x, y in zip(a, b) if x and y)
    union = sum(1 for x, y in zip(a, b) if x or y)
    return inter / union if union else 1.0


RECT = ("rect", 20, 20, lambda r, c: 5 <= r < 15 and 4 <= c < 16)
CONCAVE = ("concave-L", 24, 24, lambda r, c: (4 <= r < 20 and 4 <= c < 9) or (15 <= r < 20 and 4 <= c < 20))
TWO_COMP = ("two-components", 20, 30, lambda r, c: (4 <= r < 12 and 3 <= c < 10) or (6 <= r < 16 and 18 <= c < 26))
HOLE = ("hole", 24, 24, lambda r, c: (3 <= r < 21 and 3 <= c < 21) and not (9 <= r < 15 and 9 <= c < 15))
EDGE = ("edge-touching", 16, 16, lambda r, c: r < 6 or c == 0)              # touches top + left border
TINY = ("tiny-2x2", 10, 10, lambda r, c: 4 <= r < 6 and 4 <= c < 6)
ONE_PX = ("one-pixel", 8, 8, lambda r, c: r == 3 and c == 5)

ALL = [RECT, CONCAVE, TWO_COMP, HOLE, EDGE, TINY, ONE_PX]


# ── RLE ↔ mask exact round-trip (the identity guarantee) ─────────────────────
@pytest.mark.parametrize("name,h,w,fn", ALL, ids=[c[0] for c in ALL])
def test_rle_roundtrip_is_exact(name, h, w, fn):
    bits = make_bits(h, w, fn)
    rle = mg.rle_encode(bits, h, w)
    assert mg.rle_is_valid(rle)
    back, bh, bw = mg.rle_decode(rle)
    assert (bh, bw) == (h, w)
    assert bytes(back) == bytes(bits)                 # exact, not approximate
    assert sum(rle["counts"]) == h * w                # runs tile the frame
    assert mg.rle_area(rle) == sum(bits)              # area = set-pixel count


@pytest.mark.parametrize("name,h,w,fn", ALL, ids=[c[0] for c in ALL])
def test_rle_bbox_matches_pixels(name, h, w, fn):
    bits = make_bits(h, w, fn)
    rle = mg.rle_encode(bits, h, w)
    b = mg.rle_bbox_norm(rle)
    rows = [r for r in range(h) for c in range(w) if bits[r * w + c]]
    cols = [c for r in range(h) for c in range(w) if bits[r * w + c]]
    assert b["x"] == pytest.approx(min(cols) / w, abs=1e-6)
    assert b["y"] == pytest.approx(min(rows) / h, abs=1e-6)
    assert b["w"] == pytest.approx((max(cols) - min(cols) + 1) / w, abs=1e-6)
    assert b["h"] == pytest.approx((max(rows) - min(rows) + 1) / h, abs=1e-6)


# ── mask → polygon → mask (derived; IoU, and holes/components survive) ────────
@pytest.mark.parametrize("name,h,w,fn", ALL, ids=[c[0] for c in ALL])
def test_polygon_roundtrip_iou(name, h, w, fn):
    bits = make_bits(h, w, fn)
    rings = mg.bits_to_polygons(bits, h, w, simplify_tol=0.0)   # no simplification loss
    assert rings, "a non-empty mask must yield at least one ring"
    raster = mg.polygons_to_bits(rings, h, w)
    # coarse shapes (fallback rects) still exceed this; cv2 contours are near-exact.
    assert iou(bits, raster) >= 0.80


def test_two_components_yield_multiple_rings():
    _, h, w, fn = TWO_COMP
    bits = make_bits(h, w, fn)
    rings = mg.bits_to_polygons(bits, h, w, simplify_tol=0.0)
    assert len(rings) >= 2                             # not merged into one


def test_hole_survives_when_cv2_available():
    cv2 = pytest.importorskip("cv2")                   # holes need real contours
    _, h, w, fn = HOLE
    bits = make_bits(h, w, fn)
    rings = mg.bits_to_polygons(bits, h, w, simplify_tol=0.0)
    raster = mg.polygons_to_bits(rings, h, w)
    # a pixel inside the hole must stay OFF after rasterizing the derived rings.
    assert raster[12 * w + 12] == 0
    assert len(rings) >= 2                             # outer + hole contour


def test_very_small_mask_still_drawable():
    for spec in (TINY, ONE_PX):
        _, h, w, fn = spec
        bits = make_bits(h, w, fn)
        rings = mg.bits_to_polygons(bits, h, w)
        assert rings and len(rings[0]) >= 3            # never emits nothing


# ── polygon (normalized) → mask, even-odd holes ──────────────────────────────
def test_polygons_to_bits_even_odd_hole():
    h = w = 40
    outer = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]
    hole = [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]]
    bits = mg.polygons_to_bits([outer, hole], h, w)
    assert bits[2 * w + 2] == 0                        # outside outer (0.1*40=px4)
    assert bits[8 * w + 8] == 1                        # inside outer, outside hole
    assert bits[20 * w + 20] == 0                      # inside the hole → off


# ── coordinate registration: normalized geometry is resolution-independent ────
def test_bbox_registration_across_resolutions():
    # the SAME shape at two resolutions must give the same normalized bbox.
    def centred_square(scale):
        h = w = 20 * scale
        fn = lambda r, c: (5 * scale) <= r < (15 * scale) and (4 * scale) <= c < (16 * scale)
        return mg.rle_bbox_norm(mg.rle_encode(make_bits(h, w, fn), h, w))
    b1, b2 = centred_square(1), centred_square(3)
    for k in "xywh":
        assert b1[k] == pytest.approx(b2[k], abs=1e-6)


# ── persistence: mask_rle survives the Region model + JSON (BSON-safe) ────────
def test_mask_rle_persists_through_model_and_json():
    _, h, w, fn = HOLE
    rle = mg.rle_encode(make_bits(h, w, fn), h, w)
    region = Region(id="reg_test", box={"x": 0, "y": 0, "w": 1, "h": 1}, mask_rle=rle)
    dumped = region.model_dump()
    roundtripped = json.loads(json.dumps(dumped))      # JSON == BSON-safe primitives
    assert roundtripped["mask_rle"] == rle
    back, bh, bw = mg.rle_decode(roundtripped["mask_rle"])
    assert (bh, bw) == (h, w)
    assert bytes(back) == bytes(mg.rle_decode(rle)[0])  # identical after persistence


# ── canonicalisation: mask is identity; legacy box is retained untouched ──────
def test_canonicalize_mask_derives_everything():
    _, h, w, fn = CONCAVE
    rle = mg.rle_encode(make_bits(h, w, fn), h, w)
    region = {"id": "reg_m", "box": {"x": 0, "y": 0, "w": 0.01, "h": 0.01}, "mask_rle": rle}
    out = mg.canonicalize_geometry(region)
    assert out["id"] == "reg_m"                                   # identity preserved
    assert out["polygons"] and len(out["polygons"][0]) >= 3       # derived rings
    assert out["polygon"] and len(out["polygon"]) >= 3            # legacy single ring
    assert out["box"] == mg.rle_bbox_norm(rle)                    # box derived from mask
    assert out["geometry_rev"] == 1
    assert out["geometry_provenance"]["kind"] == "mask"


def test_canonicalize_retains_legacy_box():
    region = {"id": "reg_b", "box": {"x": 0.2, "y": 0.3, "w": 0.4, "h": 0.5}}
    out = mg.canonicalize_geometry(region)
    assert out["box"] == {"x": 0.2, "y": 0.3, "w": 0.4, "h": 0.5}  # untouched
    assert out.get("mask_rle") is None                             # no mask fabricated
    assert out["geometry_provenance"]["kind"] == "legacy-box"
    assert out.get("geometry_rev", 0) == 0


def test_canonicalize_polygons_with_size_makes_rle():
    outer = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]
    region = {"id": "reg_p", "box": {"x": 0, "y": 0, "w": 1, "h": 1}, "polygons": [outer]}
    out = mg.canonicalize_geometry(region, default_mask_size=(50, 50))
    assert mg.rle_is_valid(out["mask_rle"])
    assert out["geometry_provenance"]["method"] == "polygons"
    assert out["box"]["w"] == pytest.approx(0.6, abs=0.03)


# ── crops: alpha identity crop + rectangular context crop ─────────────────────
def test_mask_to_crops_alpha_and_context():
    Image = pytest.importorskip("PIL.Image")
    _, h, w, fn = RECT
    rle = mg.rle_encode(make_bits(h, w, fn), h, w)
    img = Image.new("RGB", (w, h), (120, 120, 120))
    crops = mg.mask_to_crops(rle, img)
    b = mg.rle_bbox_norm(rle)
    assert crops["context_crop"].size == (round(b["w"] * w), round(b["h"] * h))
    assert crops["alpha_crop"].mode == "RGBA"
    # a corner of the (rectangular) alpha crop that lies inside the mask is opaque
    ac = crops["alpha_crop"]
    assert ac.getpixel((0, 0))[3] == 255


# ── negative-space converter (CIRCUIT-001 P6-A) ──────────────────────────────
# The first brush_field producer's geometry: a figure mask → complement → soft field → strokes.

def test_mask_complement_flips_every_pixel_and_is_self_inverse():
    h, w = 6, 8
    fn = lambda r, c: 2 <= r <= 3 and 2 <= c <= 5     # a central rectangle figure
    bits = make_bits(h, w, fn)
    rle = mg.rle_encode(bits, h, w)
    comp = mg.mask_complement(rle)
    cbits, ch, cw = mg.rle_decode(comp)
    assert (ch, cw) == (h, w)
    # every pixel flipped
    assert all((1 - (1 if b else 0)) == cbits[i] for i, b in enumerate(bits))
    # self-inverse: complementing twice returns the original bit buffer exactly
    again, _, _ = mg.rle_decode(mg.mask_complement(comp))
    assert bytes(again) == bytes(bits)


def test_soft_field_is_zero_on_figure_and_peaks_away_from_it():
    h, w = 5, 5
    fn = lambda r, c: r == 2 and c == 2               # a single figure pixel at the centre
    rle = mg.rle_encode(make_bits(h, w, fn), h, w)
    field, fh, fw = mg.soft_field_from_mask(rle)
    assert (fh, fw) == (h, w)
    # figure pixel draws nothing
    assert field[2 * w + 2] == 0.0
    # a corner (farthest from the figure) is the deepest negative space → normalized to 1.0
    assert field[0] == pytest.approx(1.0, abs=1e-9)
    # softness is monotone: an immediate neighbour of the figure is dimmer than a far corner
    assert field[2 * w + 1] < field[0]
    # every value is a valid intensity
    assert all(0.0 <= v <= 1.0 for v in field)


def test_soft_field_degenerate_masks_draw_nothing():
    h, w = 4, 4
    empty = mg.rle_encode(make_bits(h, w, lambda r, c: False), h, w)   # no figure
    full = mg.rle_encode(make_bits(h, w, lambda r, c: True), h, w)     # all figure
    for rle in (empty, full):
        field, _, _ = mg.soft_field_from_mask(rle)
        assert field == [0.0] * (h * w)                                # nothing to draw


def test_strokes_from_field_synthesises_editable_normalized_strokes():
    h, w = 8, 8
    fn = lambda r, c: r == 0 and c == 0               # figure in the corner
    rle = mg.rle_encode(make_bits(h, w, fn), h, w)
    field, fh, fw = mg.soft_field_from_mask(rle)
    strokes = mg.strokes_from_field(field, fh, fw, grid=4, threshold=0.1)
    assert strokes, "a non-trivial negative space yields strokes"
    for s in strokes:
        assert s["op"] == "add"
        assert len(s["points"]) == 1
        x, y = s["points"][0]
        assert 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0                     # normalized coords
        assert 0.0 <= s["strength"] <= 1.0                             # strength ∝ intensity
    # strength really does track the field value at the sampled pixel
    deep = max(strokes, key=lambda s: s["strength"])
    shallow = min(strokes, key=lambda s: s["strength"])
    assert deep["strength"] >= shallow["strength"]


def test_strokes_below_threshold_are_omitted():
    h, w = 8, 8
    rle = mg.rle_encode(make_bits(h, w, lambda r, c: r == 0 and c == 0), h, w)
    field, fh, fw = mg.soft_field_from_mask(rle)
    # a threshold above the field's max leaves nothing to draw
    assert mg.strokes_from_field(field, fh, fw, grid=4, threshold=1.01) == []


# ── same-material cosine converter (CIRCUIT-001 P6-B) ────────────────────────
# A seed patch feature vs a grid of patch features → a cosine "same material" field.

def _grid_of(vectors):
    """A flat row-major list of patch vectors; grid = sqrt(len)."""
    import math as _m
    g = int(round(_m.sqrt(len(vectors))))
    return vectors, g


def test_cosine_field_is_one_at_the_seed_and_normalized():
    # 2×2 grid: two vectors point one way ("material A"), two another ("material B").
    a, b = [1.0, 0.0], [0.0, 1.0]
    vecs, g = _grid_of([a, a, b, b])
    field, gh, gw = mg.cosine_field_from_features(vecs, g, seed_index=0)
    assert (gh, gw) == (2, 2)
    assert field[0] == pytest.approx(1.0, abs=1e-9)          # self-similarity is exactly 1
    assert field[1] == pytest.approx(1.0, abs=1e-9)          # same material → 1
    assert field[2] == pytest.approx(0.0, abs=1e-9)          # orthogonal material → floored to 0
    assert all(0.0 <= v <= 1.0 for v in field)               # normalized


def test_cosine_field_is_monotone_in_similarity():
    seed = [1.0, 0.0]
    near = [0.9, 0.1]        # close to the seed direction
    far = [0.2, 1.0]         # far from it
    vecs, g = _grid_of([seed, near, far, [0.0, 1.0]])
    field, _, _ = mg.cosine_field_from_features(vecs, g, seed_index=0)
    assert field[0] > field[1] > field[2]                    # closer material scores higher


def test_cosine_field_l2_normalizes_so_magnitude_does_not_matter():
    # a scaled copy of the seed is the SAME material (cosine ignores magnitude)
    seed = [3.0, 4.0]                 # |v| = 5
    scaled = [30.0, 40.0]            # same direction, 10× magnitude
    vecs, g = _grid_of([seed, scaled, [4.0, -3.0], [0.0, 0.0]])
    field, _, _ = mg.cosine_field_from_features(vecs, g, seed_index=0)
    assert field[1] == pytest.approx(1.0, abs=1e-9)          # scale-invariant → still 1
    assert field[2] == pytest.approx(0.0, abs=1e-9)          # perpendicular → 0
    assert field[3] == pytest.approx(0.0, abs=1e-9)          # a zero vector never matches


def test_cosine_field_degenerate_inputs_return_empty():
    assert mg.cosine_field_from_features([], 0, 0)[0] == []
    assert mg.cosine_field_from_features([[1.0]], 2, 0)[0] == []      # too few vectors for grid=2
    assert mg.cosine_field_from_features([[1.0], [1.0], [1.0], [1.0]], 2, 9)[0] == []  # seed OOB


def test_field_contrast_distinguishes_crisp_from_uniform():
    assert mg.field_contrast([1.0, 1.0, 0.0, 0.0]) == pytest.approx(1.0)
    assert mg.field_contrast([0.7, 0.71, 0.69, 0.7]) < 0.05             # near-uniform
    assert mg.field_contrast([]) == 0.0
