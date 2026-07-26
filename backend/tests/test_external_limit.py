"""
CIRCUIT-001 TRACE-002 — external_limit: converter, producer, refusal, deferral.

Entirely FAKE-DRIVEN. GeoCalib is deferred (see perspective_service for the install verdict), so
every up-vector field here is synthesised. That is a deliberate limitation, not an oversight: it
means these tests prove the WIRING is correct and prove nothing about real projective structure,
which is why `MIN_PROJECTIVE_SPREAD` is labelled uncalibrated in the producer and here.

Nothing in this file loads a model, touches CUDA, or reaches the network.
"""
from __future__ import annotations

import math

import pytest

from backend.services import perspective_service as psvc
from backend.services import suggestion_service as ss
from backend.services.mask_geometry import (axial_coherence, horizon_flow_field,
                                            up_vector_spread)


# ── synthetic up-vector fields ───────────────────────────────────────────────

def frontal(grid=8):
    """A camera square-on to a wall: the vertical is the same everywhere. y is DOWN, so up is -y."""
    n = grid * grid
    return [0.0] * n, [-1.0] * n


def converging(grid=8, swing=0.09):
    """A receding view: the vertical swings across the frame as the scene converges."""
    ux, uy = [], []
    for _r in range(grid):
        for c in range(grid):
            a = -math.pi / 2 + (c - grid / 2) * swing
            ux.append(math.cos(a))
            uy.append(math.sin(a))
    return ux, uy


def reading(ux, uy, grid=8, **kw):
    base = {"up_x": ux, "up_y": uy, "grid": grid, "model": "geocalib_pinhole",
            "adapter": "geocalib", "revision": psvc.REVISION,
            "preprocessing_version": psvc.PREPROCESSING_VERSION}
    base.update(kw)
    return base


# ── the converter ────────────────────────────────────────────────────────────

class TestHorizonConverter:

    def test_a_frontal_field_gives_a_horizontal_horizon(self):
        cells, rows, cols = horizon_flow_field(*frontal(), 8)
        assert (rows, cols) == (8, 8)
        for dx, dy, m in cells:
            assert (abs(dx - 1.0) < 1e-6 and abs(dy) < 1e-6 and m == 1.0)

    def test_the_horizon_is_perpendicular_to_up_not_parallel_to_it(self):
        """An arrow pointing at the sky is not the limit; it is what the limit is measured from."""
        # up tilted 30° from vertical → horizon tilted 30° from horizontal
        a = math.radians(-90 + 30)
        ux, uy = [math.cos(a)] * 4, [math.sin(a)] * 4
        cells, _, _ = horizon_flow_field(ux, uy, 2)
        dx, dy, _m = cells[0]
        up_angle = math.degrees(math.atan2(uy[0], ux[0]))
        h_angle = math.degrees(math.atan2(dy, dx))
        assert abs(abs(h_angle - up_angle) - 90.0) % 180 < 1e-3

    def test_direction_is_canonicalised_axially(self):
        """A horizon has no near end, so the sign is a convention and must be consistent."""
        for ux, uy in (frontal(), converging(), converging(swing=-0.2)):
            for dx, _dy, m in horizon_flow_field(ux, uy, 8)[0]:
                if m > 0:
                    assert dx >= 0

    def test_an_undetermined_cell_is_null_not_invented(self):
        ux, uy = frontal(4)
        ux[5] = uy[5] = 0.0                       # model returned nothing for this cell
        cells, _, _ = horizon_flow_field(ux, uy, 4)
        assert [0.0, 0.0, 0.0] in cells

    def test_magnitude_is_peak_normalised(self):
        ux, uy = frontal(4)
        uy = [v * 0.5 for v in uy]
        uy[0] = -1.0                              # one confident cell
        cells, _, _ = horizon_flow_field(ux, uy, 4)
        assert max(c[2] for c in cells) == pytest.approx(1.0)
        assert all(0.0 <= c[2] <= 1.0 for c in cells)

    def test_degenerate_input_refuses(self):
        assert horizon_flow_field([], [], 8) == ([], 0, 0)
        assert horizon_flow_field([0.0] * 4, [0.0] * 4, 2) == ([], 0, 0)   # all-zero field
        assert horizon_flow_field([0.0], [1.0], 8) == ([], 0, 0)           # short input


class TestProjectiveSpread:

    def test_a_frontal_field_has_no_spread(self):
        assert up_vector_spread(*frontal(), 8) == 0.0

    def test_a_converging_field_has_spread(self):
        assert up_vector_spread(*converging(), 8) > 0.0

    def test_spread_grows_with_convergence(self):
        gentle = up_vector_spread(*converging(swing=0.05), 8)
        strong = up_vector_spread(*converging(swing=0.25), 8)
        assert strong > gentle

    def test_coherence_is_the_WRONG_gate_here_and_this_is_why(self):
        """The inversion that shapes this producer.

        A flat frontal wall is the MOST axially coherent field possible and has no projective
        structure at all. Gating on coherence would accept most confidently the exact images
        with no limit to trace — so spread decides, and coherence only scores."""
        flat_cells, _, _ = horizon_flow_field(*frontal(), 8)
        conv_cells, _, _ = horizon_flow_field(*converging(), 8)
        assert axial_coherence(flat_cells) == 1.0                 # maximal
        assert axial_coherence(conv_cells) < axial_coherence(flat_cells)
        assert up_vector_spread(*frontal(), 8) < up_vector_spread(*converging(), 8)

    def test_empty_is_zero_not_an_error(self):
        assert up_vector_spread([], [], 8) == 0.0


# ── the producer ─────────────────────────────────────────────────────────────

class TestProducer:

    def test_a_projective_scene_yields_a_trace_mark_with_a_flow_field(self):
        sug = ss.suggestion_from_external_limit(reading(*converging()), run_id="r")
        assert sug is not None
        assert sug["producer"] == "external_limit"
        assert sug["type"] == "trace_mark"
        assert sug["role"] == "external_limit"
        assert sug["geometry"]["kind"] == "flow_field"
        assert len(sug["geometry"]["cells"]) == sug["geometry"]["rows"] * sug["geometry"]["cols"]

    def test_a_frontal_image_is_refused(self):
        """No projective frame → no limit. A lattice over a flat wall would assert a recession."""
        assert ss.suggestion_from_external_limit(reading(*frontal()), run_id="r") is None

    def test_the_receipt_is_a_FULL_model_receipt_unlike_architectural_axis(self):
        """This one inferred. architectural_axis measured, and carries no model for that reason."""
        sug = ss.suggestion_from_external_limit(
            reading(*converging()), run_id="run_1", latency_ms=41.0, peak_vram_mib=310.5)
        prov = sug["provenance"]
        assert prov["producer"] == "external_limit"
        assert prov["adapter"] == "geocalib"
        assert prov["model"] == "geocalib_pinhole"
        assert prov["revision"] == psvc.REVISION
        assert prov["preprocessing_version"] == psvc.PREPROCESSING_VERSION
        assert prov["latency_ms"] == 41.0 and prov["peak_vram_mib"] == 310.5

    def test_confidence_rides_the_descriptor_never_the_provenance(self):
        sug = ss.suggestion_from_external_limit(reading(*converging()), run_id="r")
        assert "confidence" not in sug["provenance"]
        assert sug["confidence"] == pytest.approx(
            axial_coherence(sug["geometry"]["cells"]), abs=1e-4)

    def test_the_spread_that_decided_the_refusal_stays_visible(self):
        sug = ss.suggestion_from_external_limit(reading(*converging()), run_id="r")
        assert sug["projective_spread"] == pytest.approx(up_vector_spread(*converging(), 8))
        assert "projective_spread" not in sug["geometry"]      # a reading, never painted in

    def test_could_not_look_is_distinct_from_refused(self):
        assert ss.suggestion_from_external_limit(None, run_id="r") is None
        assert ss.suggestion_from_external_limit({"grid": 0}, run_id="r") is None

    def test_a_malformed_reading_refuses_rather_than_raising(self):
        assert ss.suggestion_from_external_limit(
            {"up_x": [0.0], "up_y": [1.0], "grid": 8}, run_id="r") is None

    def test_the_threshold_is_declared_uncalibrated(self):
        """It was set on synthetic fields. Activation must re-measure it on real photographs,
        and the code must keep saying so until someone does."""
        import inspect
        src = inspect.getsource(ss)
        assert "MIN_PROJECTIVE_SPREAD" in src
        assert "UNCALIBRATED" in src
        assert ss.MIN_PROJECTIVE_SPREAD > 0.0


# ── the deferral ─────────────────────────────────────────────────────────────

class TestDeferral:

    def test_the_adapter_is_unavailable_without_the_opt_in(self):
        assert psvc.is_available() is False

    def test_it_reports_could_not_look_rather_than_pretending(self):
        assert psvc.up_vector_field(object()) is None

    def test_activation_cost_states_exactly_what_is_needed(self):
        cost = psvc.activation_cost()
        assert cost["package"]["on_pypi"] is False
        assert psvc.REVISION in cost["package"]["install"]
        assert cost["package"]["new_dependencies"] == []      # deps already satisfied here
        assert cost["weights"]["size_mib"] == pytest.approx(116.1)
        assert cost["weights"]["hf_hosted"] is False
        assert cost["weights"]["manifest_pinnable_by_revision"] is False
        assert cost["env"] == {"SEMANT_ENABLE_GEOCALIB": "1"}
        assert "UNCALIBRATED" in cost["calibration_required"].upper()

    def test_the_rejected_alternative_is_recorded_with_its_reasons(self):
        """PerspectiveFields was rejected on licence and torch pin. Recording WHY stops the next
        gate from re-probing it and reaching a different conclusion on a bad day."""
        rej = psvc.activation_cost()["rejected_alternative"]
        assert rej["name"] == "PerspectiveFields"
        joined = " ".join(rej["reasons"]).lower()
        assert "license" in joined or "licence" in joined
        assert "1.10" in joined

    def test_the_repo_commit_is_pinned_not_a_branch_tip(self):
        """torch.hub defaults to the branch tip — whatever was pushed this morning."""
        assert len(psvc.REVISION) == 40 and psvc.REVISION.isalnum()


class TestRegistrationAndResidency:

    def test_the_producer_is_reachable_on_the_generic_surface(self):
        from backend.routers.posts import _FIELD_PRODUCERS
        assert "external_limit" in _FIELD_PRODUCERS

    def test_it_IS_in_the_unload_list_because_it_is_a_gpu_model(self):
        """The list has leaked three times, always a GPU model registered as a producer and not
        released. Deferred is exactly when it is easiest to forget, so it is wired now."""
        import inspect
        from backend.routers import posts
        src = inspect.getsource(posts.produce_field_unload)
        assert "perspective_service" in src
        assert "geocalib_pinhole" in src

    def test_unload_is_idempotent_and_safe_while_deferred(self):
        psvc.unload()
        psvc.unload()

    def test_the_manifest_records_it_as_deferred_and_unpinnable(self):
        import json
        m = json.load(open("weights.manifest.json"))
        models = m["models"]
        rows = models if isinstance(models, list) else list(models.values())
        entry = next(r for r in rows if r["name"] == "geocalib_pinhole")
        assert entry["kind"] == "torch_hub"          # NOT 'hf' — fetch_weights cannot provision it
        assert entry["deferred"] is True
        assert entry["license"] == "Apache-2.0"
        assert entry["revision"] == psvc.REVISION
