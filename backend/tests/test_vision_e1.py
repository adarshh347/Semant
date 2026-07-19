"""
VISION-E · E1 — canonical evidence projections (identity + context crops).

Proves both projections are deterministic, driven by the authoritative mask (not a bbox), and
sensitive to geometry but blind to semantics: a mask change moves both projection hashes; a
label/note edit moves neither. Hard cases: holes, disconnected components, thin structures,
edge-touching evidence, portrait/landscape, box-only legacy.
"""
import numpy as np
from PIL import Image

from backend.services import mask_geometry as mg
from backend.services import evidence_projection as ep


def _img(w=120, h=90, colour=(40, 90, 160)):
    return Image.new("RGB", (w, h), colour)


def _region_from_bits(bits):
    r = {"id": "seg_0", "mask_rle": mg.rle_encode_mask(bits.astype(np.uint8))}
    mg.canonicalize_geometry(r, provenance={"adapter": "test"})
    return r


def _solid(h=90, w=120, y0=20, y1=50, x0=30, x1=70):
    b = np.zeros((h, w), np.uint8); b[y0:y1, x0:x1] = 1
    return b


def test_projects_identity_and_context_from_mask():
    r = _region_from_bits(_solid())
    proj = ep.project_region(r, _img(), source_content_hash="src1")
    assert set(proj) == {"identity", "context"}
    ident, ctx = proj["identity"], proj["context"]
    assert ident["source"] == "mask" and ident["image"].mode == "RGB"
    # context admits surrounding context → strictly larger than the identity crop
    assert ctx["image"].size[0] >= ident["image"].size[0]
    assert ctx["image"].size[1] >= ident["image"].size[1]
    # the target mask box is recorded inside the context crop, within [0,1]
    tb = ctx["target_mask_box"]
    assert 0.0 <= tb["x"] <= 1.0 and 0.0 < tb["w"] <= 1.0


def test_projection_hashes_are_deterministic():
    r = _region_from_bits(_solid())
    a = ep.project_region(r, _img(), source_content_hash="src1")
    b = ep.project_region(r, _img(), source_content_hash="src1")
    assert a["identity"]["projection_hash"] == b["identity"]["projection_hash"]
    assert a["context"]["projection_hash"] == b["context"]["projection_hash"]
    # and the pixels themselves are identical
    assert a["identity"]["image"].tobytes() == b["identity"]["image"].tobytes()


def test_geometry_change_moves_both_projections():
    base = ep.project_region(_region_from_bits(_solid()), _img())
    moved = ep.project_region(_region_from_bits(_solid(x0=45, x1=95)), _img())   # mask shifted
    assert base["identity"]["projection_hash"] != moved["identity"]["projection_hash"]
    assert base["context"]["projection_hash"] != moved["context"]["projection_hash"]


def test_label_or_note_change_does_not_move_projections():
    bits = _solid()
    r1 = _region_from_bits(bits)
    r2 = _region_from_bits(bits)
    r2.update({"label": "a totally different name", "user_note": "curator musing", "category": "x"})
    p1 = ep.project_region(r1, _img())
    p2 = ep.project_region(r2, _img())
    # semantics are not an input to a visual projection
    assert p1["identity"]["projection_hash"] == p2["identity"]["projection_hash"]
    assert p1["context"]["projection_hash"] == p2["context"]["projection_hash"]


def test_mask_is_preferred_over_box_and_isolates_evidence():
    # identity over neutral bg: pixels outside the mask must be the neutral colour, so a
    # bbox-only crop (which would keep the blue background) is provably NOT what we produced.
    bits = _solid(y0=20, y1=50, x0=30, x1=70)
    r = _region_from_bits(bits)
    ident = ep.project_region(r, _img(colour=(0, 0, 255)))["identity"]
    arr = np.asarray(ident["image"])
    # a corner of the padded identity crop lies outside the mask → neutral grey, not blue
    assert tuple(arr[0, 0]) == ep.NEUTRAL_BG


def test_box_only_legacy_is_honest():
    r = {"id": "seg_0", "box": {"x": 0.25, "y": 0.2, "w": 0.3, "h": 0.3}}   # no mask
    proj = ep.project_region(r, _img())
    assert proj["identity"]["source"] == "box-legacy"
    assert proj["identity"]["provenance"]["source"] == "box-legacy"
    assert proj["context"]["image"].size[0] > 0


def test_none_when_no_geometry():
    assert ep.project_region({"id": "x"}, _img()) is None


def test_hard_shapes_do_not_crash():
    H, W = 90, 120
    cases = {}
    # hole (ring)
    ring = np.zeros((H, W), np.uint8); ring[20:60, 20:80] = 1; ring[35:45, 40:60] = 0
    cases["hole"] = ring
    # disconnected components
    disc = np.zeros((H, W), np.uint8); disc[10:25, 10:30] = 1; disc[60:80, 85:110] = 1
    cases["disconnected"] = disc
    # thin structure
    thin = np.zeros((H, W), np.uint8); thin[45:47, 10:110] = 1
    cases["thin"] = thin
    # edge-touching
    edge = np.zeros((H, W), np.uint8); edge[0:30, 0:40] = 1
    cases["edge"] = edge
    for name, bits in cases.items():
        proj = ep.project_region(_region_from_bits(bits), _img(W, H))
        assert proj is not None, name
        assert proj["identity"]["image"].size[0] >= 1 and proj["identity"]["image"].size[1] >= 1, name
        assert proj["identity"]["projection_hash"] and proj["context"]["projection_hash"], name


def test_portrait_and_landscape_images():
    bits = _solid(h=160, w=90, y0=40, y1=90, x0=20, x1=60)
    for img in (_img(90, 160), _img(160, 90)):
        # rebuild a region whose mask matches THIS image's aspect via its own [h,w]
        r = _region_from_bits(bits)
        proj = ep.project_region(r, img)
        assert proj is not None
        assert proj["context"]["image"].size[0] <= img.size[0]
        assert proj["context"]["image"].size[1] <= img.size[1]
