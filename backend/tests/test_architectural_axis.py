"""
CIRCUIT-001 TRACE-001 — architectural_axis: converter, producer, refusal.

CPU only. The converter tests use SYNTHETIC segment lists and need no image and no OpenCV; the
few that exercise detection build their own bitmaps. Nothing here loads a model or touches a GPU.
"""
from __future__ import annotations

import math

import pytest

from backend.services import suggestion_service as ss
from backend.services.mask_geometry import (axial_coherence, flow_field_coherence,
                                            flow_field_coverage,
                                            line_orientation_flow_field as flow)


def vertical_lines(n=4, size=200):
    step = size / (n + 1)
    return [((i + 1) * step, size * 0.05, (i + 1) * step, size * 0.95) for i in range(n)]


def horizontal_lines(n=4, size=200):
    step = size / (n + 1)
    return [(size * 0.05, (i + 1) * step, size * 0.95, (i + 1) * step) for i in range(n)]


def detection(segments, width=200, height=200, adapter="opencv_lsd"):
    total = sum(math.hypot(s[2] - s[0], s[3] - s[1]) for s in segments)
    return {"segments": list(segments), "width": width, "height": height,
            "count": len(segments), "total_length": total,
            "diagonal": math.hypot(width, height), "adapter": adapter}


# ── the converter ────────────────────────────────────────────────────────────

class TestConverter:

    def test_parallel_vertical_lines_give_an_aligned_vertical_field(self):
        cells, rows, cols = flow(vertical_lines(), 200, 200)
        assert (rows, cols) == (14, 14)
        live = [c for c in cells if c[2] > 0]
        assert live
        for dx, dy, _m in live:
            assert abs(dx) < 0.05 and abs(abs(dy) - 1.0) < 0.05
        assert axial_coherence(cells) > 0.95

    def test_parallel_horizontal_lines_give_an_aligned_horizontal_field(self):
        cells, _, _ = flow(horizontal_lines(), 200, 200)
        for dx, dy, _m in (c for c in cells if c[2] > 0):
            assert abs(abs(dx) - 1.0) < 0.05 and abs(dy) < 0.05

    def test_orientation_is_axial_not_directional(self):
        """The property the whole converter is built around.

        The same wall edge traversed in opposite directions is ONE axis. Averaging raw angles
        would send 1° and 181° to 91° — perpendicular to both, an inversion rather than a
        degradation. Doubled-angle accumulation is what prevents it."""
        forward = [(10, 100, 190, 103)]
        backward = [(190, 103, 10, 100)]
        a, _, _ = flow(forward, 200, 200)
        b, _, _ = flow(backward, 200, 200)
        live_a = [c for c in a if c[2] > 0][0]
        live_b = [c for c in b if c[2] > 0][0]
        assert live_a[:2] == pytest.approx(live_b[:2], abs=1e-3)

    def test_the_direction_is_canonicalised_to_the_dx_positive_half_plane(self):
        """There is no arrowhead to put on an axis; the sign must be canonical, not arbitrary."""
        for segs in (vertical_lines(), horizontal_lines(), [(10, 190, 190, 10)]):
            for dx, _dy, m in (c for c in flow(segs, 200, 200)[0] if c[2] > 0):
                assert dx >= 0

    def test_magnitude_is_peak_normalised_to_the_unit_interval(self):
        cells, _, _ = flow(vertical_lines(6), 200, 200)
        mags = [c[2] for c in cells]
        assert max(mags) == pytest.approx(1.0)
        assert all(0.0 <= m <= 1.0 for m in mags)

    def test_a_long_line_outweighs_a_short_one_in_the_same_place(self):
        """Length weighting is what makes 'dominant' mean structurally dominant."""
        mixed = [(100, 10, 100, 190)] + [(96, 96, 104, 104)]     # long vertical + tiny diagonal
        cells, _, _ = flow(mixed, 200, 200)
        centre = [c for c in cells if c[2] > 0.9][0]
        assert abs(centre[0]) < 0.25                              # still reads as vertical

    def test_a_cell_far_from_any_line_is_null_not_invented(self):
        cells, _, _ = flow([(4, 4, 4, 40)], 200, 200)             # one line in a corner
        assert any(c == [0.0, 0.0, 0.0] for c in cells)
        assert flow_field_coverage(cells) < 0.4

    def test_no_segments_refuses(self):
        assert flow([], 200, 200) == ([], 0, 0)

    def test_degenerate_input_refuses_rather_than_dividing_by_zero(self):
        assert flow(vertical_lines(), 0, 200) == ([], 0, 0)
        assert flow([(5, 5, 5, 5)], 200, 200) == ([], 0, 0)       # zero-length segment
        assert flow([None, (1,)], 200, 200) == ([], 0, 0)         # malformed rows


class TestAxialCoherence:

    def test_parallel_is_coherent_and_a_perpendicular_grid_is_not(self):
        assert axial_coherence(flow(vertical_lines(), 200, 200)[0]) > 0.95
        grid = vertical_lines(3) + horizontal_lines(3)
        assert axial_coherence(flow(grid, 200, 200)[0]) < 0.6

    def test_it_disagrees_with_flow_field_coherence_where_that_one_is_wrong(self):
        """Near-vertical lines splayed either side of vertical are nearly ONE axis. As raw unit
        vectors they very nearly cancel, so the direction-based measure calls a strongly aligned
        field incoherent. Measured: 0.997 against 0.175 — this is why the second function exists."""
        segs = []
        for i, tilt in enumerate((4, -4, 3, -3, 5, -5)):
            x = 25 + i * 28
            segs.append((x, 15, x + math.tan(math.radians(tilt)) * 170, 185))
        cells, _, _ = flow(segs, 200, 200)
        assert axial_coherence(cells) > 0.95
        assert flow_field_coherence(cells) < 0.5

    def test_empty_is_zero_not_an_error(self):
        assert axial_coherence([]) == 0.0
        assert flow_field_coverage([]) == 0.0


# ── the producer ─────────────────────────────────────────────────────────────

class TestProducer:

    def test_an_aligned_scene_yields_a_trace_mark_carrying_a_flow_field(self):
        sug = ss.suggestion_from_architectural_axis(detection(vertical_lines(8)), run_id="r")
        assert sug is not None
        assert sug["producer"] == "architectural_axis"
        assert sug["type"] == "trace_mark"
        assert sug["role"] == "architectural_axis"
        assert sug["geometry"]["kind"] == "flow_field"
        assert sug["geometry"]["rows"] == 14 and sug["geometry"]["cols"] == 14
        assert len(sug["geometry"]["cells"]) == 196

    def test_the_receipt_is_deterministic_and_names_no_model(self):
        """OpenCV inferred nothing. A model field here would claim a provenance that is false."""
        sug = ss.suggestion_from_architectural_axis(
            detection(vertical_lines(8)), run_id="run_1", adapter="opencv_lsd",
            preprocessing_version="line-structure-v1", latency_ms=31.5)
        prov = sug["provenance"]
        assert prov["producer"] == "architectural_axis"
        assert prov["adapter"] == "opencv_lsd"
        assert prov["run_id"] == "run_1"
        assert "model" not in prov and "checkpoint" not in prov and "revision" not in prov

    def test_confidence_rides_the_descriptor_never_the_provenance(self):
        """Contract §6, unchanged by the new lane."""
        sug = ss.suggestion_from_architectural_axis(detection(vertical_lines(8)), run_id="r")
        assert "confidence" not in sug["provenance"]
        assert sug["confidence"] == pytest.approx(
            axial_coherence(sug["geometry"]["cells"]), abs=1e-4)

    def test_the_confidence_is_axial_coherence(self):
        sug = ss.suggestion_from_architectural_axis(detection(vertical_lines(8)), run_id="r")
        assert sug["confidence"] > 0.95

    def test_an_incoherent_scene_is_refused(self):
        """Organic input: many segments, no dominant axis. Measured 0.119 on a real sketchbook."""
        segs = []
        for i in range(40):
            a = (i * 37 % 180) * math.pi / 180.0        # deterministic angular spread
            cx, cy = 40 + (i * 53 % 120), 40 + (i * 29 % 120)
            segs.append((cx - 22 * math.cos(a), cy - 22 * math.sin(a),
                         cx + 22 * math.cos(a), cy + 22 * math.sin(a)))
        det = detection(segs)
        assert axial_coherence(flow(segs, 200, 200)[0]) < ss.MIN_AXIAL_COHERENCE
        assert ss.suggestion_from_architectural_axis(det, run_id="r") is None

    def test_too_few_segments_is_refused_however_parallel_they_are(self):
        """Two perfectly parallel lines score 1.0. A lamp post is not an architectural axis."""
        assert ss.suggestion_from_architectural_axis(
            detection(vertical_lines(2)), run_id="r") is None

    def test_an_empty_detection_refuses(self):
        assert ss.suggestion_from_architectural_axis(detection([]), run_id="r") is None

    def test_could_not_look_is_distinct_from_found_nothing(self):
        """None-in means detection did not run; it must not be read as 'no lines here'."""
        assert ss.suggestion_from_architectural_axis(None, run_id="r") is None

    def test_the_threshold_is_the_calibrated_one(self):
        assert ss.MIN_AXIAL_COHERENCE == 0.25          # measured gap 0.088 → 0.359

    def test_it_reports_readings_about_the_field_without_painting_them_in(self):
        sug = ss.suggestion_from_architectural_axis(detection(vertical_lines(8)), run_id="r")
        assert 0.0 < sug["coverage"] <= 1.0
        assert sug["segment_count"] == 8
        assert set(sug["geometry"].keys()) == {"kind", "cols", "rows", "cells"}


# ── detection (real OpenCV, synthetic bitmaps) ───────────────────────────────

class TestDetection:

    def test_it_finds_lines_in_a_drawn_grid_and_the_producer_accepts(self):
        cv2 = pytest.importorskip("cv2")
        np = pytest.importorskip("numpy")
        from PIL import Image
        from backend.services import line_structure_service as lss

        arr = np.full((400, 400, 3), 240, np.uint8)
        for x in range(40, 400, 45):
            cv2.line(arr, (x, 20), (x, 380), (20, 20, 20), 3)
        det = lss.detect_segments(Image.fromarray(arr))
        assert det is not None and det["count"] >= 8
        assert det["adapter"] in (lss.ADAPTER_LSD, lss.ADAPTER_HOUGH)
        sug = ss.suggestion_from_architectural_axis(det, run_id="r")
        assert sug is not None and sug["confidence"] > 0.8

    def test_a_blank_image_is_looked_at_and_found_empty(self):
        pytest.importorskip("cv2")
        np = pytest.importorskip("numpy")
        from PIL import Image
        from backend.services import line_structure_service as lss

        det = lss.detect_segments(Image.fromarray(np.full((300, 300, 3), 200, np.uint8)))
        assert det is not None                          # looked
        assert det["count"] == 0                        # found nothing
        assert ss.suggestion_from_architectural_axis(det, run_id="r") is None

    def test_detection_never_touches_the_gpu(self):
        """CPU-only is a property of this producer, not a hope. If torch is present, no CUDA
        allocation may occur — the axis producer must never contend for the single-GPU slot."""
        pytest.importorskip("cv2")
        np = pytest.importorskip("numpy")
        from PIL import Image
        from backend.services import line_structure_service as lss
        torch = pytest.importorskip("torch")
        if not torch.cuda.is_available():
            pytest.skip("no CUDA to observe")
        before = torch.cuda.memory_allocated()
        arr = np.full((300, 300, 3), 240, np.uint8)
        for x in range(30, 300, 40):
            arr[20:280, x:x + 2] = 20
        lss.detect_segments(Image.fromarray(arr))
        assert torch.cuda.memory_allocated() == before


class TestRegistration:

    def test_the_producer_is_reachable_on_the_generic_surface(self):
        from backend.routers.posts import _FIELD_PRODUCERS
        assert "architectural_axis" in _FIELD_PRODUCERS

    def test_it_is_absent_from_the_unload_list_because_it_loads_nothing(self):
        """The unload list has leaked three times. A producer with no resident weights cannot
        contribute to a fourth, and adding it would imply state it does not have."""
        import inspect
        from backend.routers import posts
        src = inspect.getsource(posts.produce_field_unload)
        assert "architectural_axis" not in src
        assert "line_structure" not in src
