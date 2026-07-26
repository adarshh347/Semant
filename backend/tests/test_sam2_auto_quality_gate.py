"""
CIRCUIT-001 QUALITY-001 (Q-A) — the pure quality gate.

`sam2_auto_service.decomposition_adequate` is the torch-free replacement for the old zero gate
(`if not anchors`). These tests pin its behaviour without a GPU: nothing and any LONE anchor are
FAILURES (→ SAM2-auto/VLM get a turn — the case the old gate missed); a genuine multi-part
decomposition is adequate, unless one part dominates the whole frame.
"""
import numpy as np

from backend.services import sam2_auto_service as sa
from backend.services import mask_geometry


def _box_region(w, h):
    """A box-only region of normalized size w×h (area = w*h)."""
    return {"box": {"x": 0.0, "y": 0.0, "w": w, "h": h}}


def _mask_region(frac):
    """A region whose authoritative RLE covers `frac` of a 100×100 frame."""
    m = np.zeros((100, 100), dtype="uint8")
    side = int(round((frac ** 0.5) * 100))
    m[:side, :side] = 1
    return {"mask_rle": mask_geometry.rle_encode_mask(m)}


def test_empty_or_none_is_inadequate():
    assert sa.decomposition_adequate(None) is False
    assert sa.decomposition_adequate([]) is False


def test_lone_anchor_is_inadequate():
    # a single anchor is never a decomposition — the case the old zero gate let through
    assert sa.decomposition_adequate([_box_region(0.9, 0.78)]) is False   # whole-figure blob
    assert sa.decomposition_adequate([_box_region(0.2, 0.2)]) is False    # lone small anchor too


def test_two_or_more_parts_is_adequate():
    assert sa.decomposition_adequate([_box_region(0.4, 0.4), _box_region(0.2, 0.2)]) is True
    assert sa.decomposition_adequate([_mask_region(0.3), _mask_region(0.1), _mask_region(0.05)]) is True


def test_dominant_part_fails_size_distribution():
    # two parts, but one covers ~95% of the frame — not a sane distribution
    assert sa.decomposition_adequate([_mask_region(0.95), _mask_region(0.02)]) is False


def test_thresholds_are_configurable():
    parts = [_box_region(0.4, 0.4), _box_region(0.2, 0.2)]
    assert sa.decomposition_adequate(parts, min_parts=3) is False   # only 2 parts, need 3
    dominant = [_mask_region(0.8), _mask_region(0.05)]
    assert sa.decomposition_adequate(dominant, max_dominant_frac=0.7) is False  # 0.8 dominates
    assert sa.decomposition_adequate(dominant, max_dominant_frac=0.95) is True
