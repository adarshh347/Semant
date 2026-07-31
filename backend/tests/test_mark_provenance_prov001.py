"""
CIRCUIT-002 PROV-001 Seam 2 — mark provenance is declared, and survives the wholesale PATCH.

THE DECISION this pins: provenance is AUTHORED on the produced object (the mark) and DERIVED by
the ground. Grounds are not given a second authored copy — CIRCUIT-001 P3-A keeps provenance in
one place on purpose (`regionStore.js:321`, "visible provenance on a ground, WITHOUT authoring
it"), and two authored copies is the drift `test_producer_parity` exists to catch elsewhere here.

So the defense is the type layer, not a fake accept chokepoint. There is no server-side accept
boundary to hook: grounds/percepts/marks are authored client-side and PATCHed wholesale through
`update_post`. What can be defended is the contract the PATCH validates against.

  1. provenance round-trips through the models that persist it   → TestRoundTrip
  2. typing marks did not start dropping the rest of the mark     → TestNothingElseWasLost
  3. no fabrication: absent stays absent                          → TestNoFabrication

(2) is the non-vacuous half and the real risk of this change. Typing `visual_marks` as a model
could silently delete every undeclared key on the next save — trading the hole this closes for a
strictly bigger one. It is asserted directly, not assumed from `extra="allow"`.
"""
from __future__ import annotations

from backend.schemas.post import Mark, MarkProvenance, PostUpdate


def producer_mark() -> dict:
    """A mark as the client mints it for a real producer — full contract, not just provenance."""
    return {
        "id": "mk_1",
        "type": "brush_field",
        "role": "pressure_zone",
        "label": "the pressure zone",
        "geometry": {"kind": "raster", "strokes": [[0.1, 0.2]]},
        "epistemic_status": "measured",
        "status": "committed",
        "region_id": "reg_1",
        "warnings": [],
        "created_at": "2026-08-01T00:00:00Z",
        "updated_at": "2026-08-01T00:00:00Z",
        "provenance": {
            "planner": None, "prompt_excerpt": None, "model": "dinov2_vits14", "matched": [],
            "run_id": "run_7", "step_id": "s3", "producer": "pressure_zone",
            "adapter": "pressure_zone", "latency_ms": 41.2,
        },
    }


def curator_mark() -> dict:
    """A hand-drawn mark. No producer said anything about it."""
    return {
        "id": "mk_2", "type": "trace_mark", "role": "rhythm",
        "geometry": {"kind": "polyline", "points": [[0.1, 0.1]]},
        "provenance": {"planner": None, "prompt_excerpt": None, "model": None, "matched": []},
    }


# ── 1. the round trip ────────────────────────────────────────────────────────

class TestRoundTrip:

    def test_step_id_survives_the_write_model(self):
        """THE CLAIM. `PostUpdate` is what the wholesale PATCH validates against, so this is the
        path marks are actually persisted by."""
        upd = PostUpdate(visual_marks=[producer_mark()])
        out = upd.model_dump(exclude_unset=True)["visual_marks"][0]
        assert out["provenance"]["step_id"] == "s3"

    def test_run_id_and_producer_survive_too(self):
        upd = PostUpdate(visual_marks=[producer_mark()])
        prov = upd.model_dump(exclude_unset=True)["visual_marks"][0]["provenance"]
        assert prov["run_id"] == "run_7"
        assert prov["producer"] == "pressure_zone"
        assert prov["adapter"] == "pressure_zone"

    def test_step_id_is_a_declared_field_not_an_incidental_extra(self):
        """The whole point of Seam 2. If it were only riding `extra`, it would still round-trip
        here — and still be undefended. This asserts it is part of the contract."""
        assert "step_id" in MarkProvenance.model_fields
        assert "run_id" in MarkProvenance.model_fields
        assert "producer" in MarkProvenance.model_fields
        assert MarkProvenance().step_id is None


# ── 2. typing marks did not cost us the rest of the mark ────────────────────

class TestNothingElseWasLost:
    """The risk this change introduces. A strict model on `visual_marks` would delete every
    undeclared key on the next PATCH, which is a bigger hole than the one being closed."""

    def test_the_whole_mark_contract_survives(self):
        original = producer_mark()
        out = PostUpdate(visual_marks=[original]).model_dump(exclude_unset=True)["visual_marks"][0]
        for key in ("id", "type", "role", "label", "geometry", "epistemic_status",
                    "status", "region_id", "created_at", "updated_at"):
            assert out[key] == original[key], f"typing visual_marks dropped {key!r}"

    def test_undeclared_provenance_keys_survive(self):
        """`planner`, `prompt_excerpt`, `model`, `matched`, `latency_ms` are all real and none is
        declared. `model` is undeclared DELIBERATELY — it collides with Pydantic's protected
        `model_` namespace, and extras carry it without a rename that would break the wire."""
        out = PostUpdate(visual_marks=[producer_mark()]).model_dump(
            exclude_unset=True)["visual_marks"][0]
        prov = out["provenance"]
        assert prov["model"] == "dinov2_vits14"
        assert prov["latency_ms"] == 41.2
        assert prov["matched"] == []
        assert "planner" in prov and "prompt_excerpt" in prov

    def test_a_future_mark_field_is_not_rejected(self):
        """P4/P5/P6 keep adding to the mark. A model that 422s on an unknown key would break the
        PATCH for every client ahead of the server."""
        mark = producer_mark()
        mark["some_field_invented_next_quarter"] = {"nested": True}
        out = PostUpdate(visual_marks=[mark]).model_dump(exclude_unset=True)["visual_marks"][0]
        assert out["some_field_invented_next_quarter"] == {"nested": True}


# ── 3. no fabrication ────────────────────────────────────────────────────────

class TestNoFabrication:

    def test_a_curators_mark_gets_no_invented_run_or_step(self):
        """None means 'no producer said anything'. It must not become a synthesized id, and it
        must not become the string 'None' either."""
        out = PostUpdate(visual_marks=[curator_mark()]).model_dump(
            exclude_unset=True)["visual_marks"][0]
        prov = out["provenance"]
        assert prov.get("run_id") is None
        assert prov.get("step_id") is None
        assert prov.get("producer") is None

    def test_a_mark_with_no_provenance_at_all_is_accepted(self):
        out = PostUpdate(visual_marks=[{"id": "mk_3", "type": "trace_mark"}]).model_dump(
            exclude_unset=True)["visual_marks"][0]
        assert out["id"] == "mk_3"
        assert out.get("provenance") is None

    def test_the_mark_model_declares_only_provenance(self):
        """Deliberately minimal: the mark contract lives in visualMarks.js and is validated by
        validateMark there. Restating it here would create a second copy to drift — the same
        failure this seam closes."""
        assert set(Mark.model_fields) == {"provenance"}
