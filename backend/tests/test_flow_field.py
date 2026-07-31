"""CIRCUIT-001 GEOM-001 — the flow_field kind + the fall_of_light producer.

Covers, with synthetic (no-model) shading maps so it runs in CI:
  · shading_flow_field: a known light source yields the right per-cell orientation, dims, and
    normalized magnitudes; a flat map REFUSES (empty), never a fabricated flow.
  · flow_field_coherence: a raking light reads ~1, a divergent field reads low.
  · suggestion_from_fall_of_light: the descriptor shape + full receipt; the refusal cases.
"""
import math

from backend.services.mask_geometry import shading_flow_field, flow_field_coherence
from backend.services import suggestion_service as ss


# ── synthetic shading maps (row-major, larger value = more lit) ──────────────────

def _bright_left(grid):
    """Bright on the left, dark on the right → light falls left→right (dx > 0)."""
    return [1.0 - c / (grid - 1) for _r in range(grid) for c in range(grid)]


def _bright_top(grid):
    """Bright at the top, dark at the bottom → light falls top→bottom (dy > 0)."""
    return [1.0 - r / (grid - 1) for r in range(grid) for _c in range(grid)]


def _flat(grid, v=0.5):
    return [v] * (grid * grid)


# ── the converter ───────────────────────────────────────────────────────────────

def test_flow_field_left_light_points_right():
    cells, rows, cols = shading_flow_field(_bright_left(8), 8)
    assert rows > 0 and cols > 0
    assert len(cells) == rows * cols
    active = [c for c in cells if c[2] > 0]
    assert active, "a clear gradient must produce directions"
    for dx, dy, m in active:
        assert dx > 0.7, f"light falls toward the dark right → dx>0, got {dx}"
        assert abs(dy) < 0.2, f"a horizontal gradient has ~no vertical fall, got {dy}"
        assert 0.0 < m <= 1.0


def test_flow_field_top_light_points_down():
    cells, _rows, _cols = shading_flow_field(_bright_top(8), 8)
    active = [c for c in cells if c[2] > 0]
    assert active
    for dx, dy, _m in active:
        assert dy > 0.7, f"light falls toward the dark bottom → dy>0, got {dy}"
        assert abs(dx) < 0.2


def test_flow_field_cells_are_unit_and_peak_normalized():
    cells, _rows, _cols = shading_flow_field(_bright_left(10), 10)
    peaks = 0
    for dx, dy, m in cells:
        if m > 0:
            assert abs(math.hypot(dx, dy) - 1.0) < 1e-3, "a live cell carries a UNIT direction"
        assert 0.0 <= m <= 1.0, "magnitude is normalized into [0,1]"
        if abs(m - 1.0) < 1e-6:
            peaks += 1
    assert peaks >= 1, "the strongest cell normalizes to exactly 1.0"


def test_flow_field_dims_bounded_by_out_grid():
    cells, rows, cols = shading_flow_field(_bright_left(40), 40, out_grid=14)
    assert rows == 14 and cols == 14
    assert len(cells) == 14 * 14


def test_flow_field_refuses_flat_map():
    assert shading_flow_field(_flat(8), 8) == ([], 0, 0)


def test_flow_field_refuses_degenerate_input():
    assert shading_flow_field([0.1, 0.2], 8) == ([], 0, 0)   # too short
    assert shading_flow_field(_bright_left(2), 2) == ([], 0, 0)   # grid < 3


def test_coherence_high_for_raking_light_low_for_divergent():
    raking, _r, _c = shading_flow_field(_bright_left(8), 8)
    assert flow_field_coherence(raking) > 0.9, "a single raking light is highly coherent"

    # a radial/divergent field: arrows pointing in all four directions cancel out
    divergent = [[1, 0, 1.0], [-1, 0, 1.0], [0, 1, 1.0], [0, -1, 1.0]]
    assert flow_field_coherence(divergent) < 0.1

    assert flow_field_coherence([]) == 0.0


# ── the producer ────────────────────────────────────────────────────────────────

def _shading(grid, values):
    return {"grid": grid, "shading": values}


def test_producer_shape_and_full_receipt():
    d = ss.suggestion_from_fall_of_light(
        _shading(8, _bright_left(8)), run_id="run_1", region_id="reg_9",
        model="intrinsic_ordinal_shading", checkpoint="compphoto/Intrinsic:paper_weights",
        preprocessing_version="v1", latency_ms=42.0, peak_vram_mib=910.0)
    assert d is not None
    assert d["producer"] == "fall_of_light"
    assert d["type"] == "trace_mark"
    assert d["role"] == "fall_of_light"
    assert d["geometry"]["kind"] == "flow_field"
    assert d["geometry"]["cols"] > 0 and d["geometry"]["rows"] > 0
    assert len(d["geometry"]["cells"]) == d["geometry"]["cols"] * d["geometry"]["rows"]
    # full model receipt, run-linked
    prov = d["provenance"]
    assert prov["run_id"] == "run_1"
    assert prov["producer"] == "fall_of_light"
    assert prov["adapter"] == "intrinsic_ordinal_shading"
    assert prov["model"] == "intrinsic_ordinal_shading"
    assert prov["latency_ms"] == 42.0
    assert prov["peak_vram_mib"] == 910.0
    # confidence lives on the descriptor (contract §6: never inside geometry)
    assert 0.0 <= d["confidence"] <= 1.0
    assert "confidence" not in d["geometry"]
    assert d["source_ref"] == "reg_9:fall_of_light"


def test_producer_refuses_flat_surface():
    assert ss.suggestion_from_fall_of_light(_shading(8, _flat(8)), run_id="r") is None


def test_producer_refuses_non_dict_and_empty():
    assert ss.suggestion_from_fall_of_light(None, run_id="r") is None
    assert ss.suggestion_from_fall_of_light({"grid": 0, "shading": []}, run_id="r") is None


def test_producer_default_label():
    d = ss.suggestion_from_fall_of_light(_shading(8, _bright_top(8)), run_id="r")
    assert d["label"] == "the fall of light"
