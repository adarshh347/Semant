"""
CIRCUIT-002 PROV-001 Seam 4 — a refinement tightens the mask, it does not erase the region.

Pure-dict tests against `_merge_refined_region`: no GPU, no SAM2, no image fetch, no database.
That is deliberate and it is the reason the merge was lifted out of the route body — the defect
was never in the model, it was in one assignment on the persist path, and a test that needed a
GPU to reach it is a test nobody runs.

THE BUG, as found in the corpus: refine kept the region's `id` and replaced everything else, so a
region that had been named, categorised, described and linked to a prose block came back carrying
only geometry and schema defaults. All six creator regions in the corpus read `label: null`. A
Mention pointing at such a region still resolves — and finds nothing left to mean.

  1. meaning survives a refinement                → TestMeaningSurvives
  2. geometry is genuinely replaced, not merged   → TestGeometryIsReplaced
  3. curator fields are not erased by defaults    → TestCuratorFields
"""
from __future__ import annotations

from backend.routers.posts import _merge_refined_region


def prev_region() -> dict:
    """A region as it exists after a curator has worked on it."""
    return {
        "id": "reg_1", "actor": "creator", "detector": "yolo",
        "box": {"x": 0.1, "y": 0.1, "w": 0.5, "h": 0.5},
        "polygon": [[0.1, 0.1], [0.6, 0.1], [0.6, 0.6]],
        "polygons": [[[0.1, 0.1], [0.6, 0.1], [0.6, 0.6]]],
        "mask_rle": {"size": [10, 10], "counts": [0, 100]},
        "geometry_rev": 3,
        "geometry_provenance": {"kind": "mask", "method": "rle"},
        "confidence": 0.4,
        # the meaning the bug destroyed
        "label": "shoulder drape", "category": "garment", "material": "silk",
        "description": "the fall of cloth across the shoulder",
        "part": "shoulder", "attributes": ["draped", "matte"],
        "embedding_id": "emb_42", "block_id": "block_7",
        # hierarchy + curator meaning
        "depth": 1, "parent_id": "reg_0",
        "prioritised": True, "weight": 5, "user_note": "the reason I kept this",
    }


def refined_region() -> dict:
    """What the refiner mints: geometry from this run, plus Region's own defaults."""
    return {
        "id": "reg_1", "actor": "creator", "detector": "sam2",
        "box": {"x": 0.2, "y": 0.2, "w": 0.3, "h": 0.3},
        "polygon": [[0.2, 0.2], [0.5, 0.2], [0.5, 0.5]],
        "polygons": [[[0.2, 0.2], [0.5, 0.2], [0.5, 0.5]]],
        "mask_rle": {"size": [10, 10], "counts": [0, 50, 50]},
        "geometry_rev": 4,
        "geometry_provenance": {"kind": "mask", "method": "rle", "adapter": "sam21_hiera_tiny"},
        "confidence": 0.91,
        "refined_from": "reg_1", "proposed": False, "mark_source": "model_refined",
        # schema defaults — knowledge-free, and the trap the merge has to avoid
        "prioritised": False, "weight": 0, "user_note": "",
    }


# ── 1. meaning survives ──────────────────────────────────────────────────────

class TestMeaningSurvives:

    def test_the_label_is_not_destroyed(self):
        """THE CLAIM, and the one the corpus disproved before this fix."""
        merged = _merge_refined_region(prev_region(), refined_region())
        assert merged["label"] == "shoulder drape"

    def test_every_semantic_field_survives(self):
        merged = _merge_refined_region(prev_region(), refined_region())
        assert merged["category"] == "garment"
        assert merged["material"] == "silk"
        assert merged["description"] == "the fall of cloth across the shoulder"
        assert merged["part"] == "shoulder"
        assert merged["attributes"] == ["draped", "matte"]

    def test_the_cross_surface_links_survive(self):
        """`block_id` is the region's end of a prose chip and `embedding_id` points at the taste
        vector. Dropping either leaves a Mention pointing at something with nothing to say."""
        merged = _merge_refined_region(prev_region(), refined_region())
        assert merged["embedding_id"] == "emb_42"
        assert merged["block_id"] == "block_7"

    def test_hierarchy_survives(self):
        merged = _merge_refined_region(prev_region(), refined_region())
        assert merged["depth"] == 1
        assert merged["parent_id"] == "reg_0"

    def test_the_identity_is_unchanged(self):
        merged = _merge_refined_region(prev_region(), refined_region())
        assert merged["id"] == "reg_1"


# ── 2. geometry is genuinely replaced ────────────────────────────────────────

class TestGeometryIsReplaced:
    """The risk a naive merge introduces is worse than the bug it fixes: a region whose mask is
    new but whose derived polygon/box still describe the old shape would be internally
    inconsistent, and every consumer would trust it."""

    def test_the_mask_is_the_new_one(self):
        merged = _merge_refined_region(prev_region(), refined_region())
        assert merged["mask_rle"] == {"size": [10, 10], "counts": [0, 50, 50]}

    def test_every_derived_geometry_field_is_the_new_one(self):
        merged = _merge_refined_region(prev_region(), refined_region())
        assert merged["box"] == {"x": 0.2, "y": 0.2, "w": 0.3, "h": 0.3}
        assert merged["polygon"] == [[0.2, 0.2], [0.5, 0.2], [0.5, 0.5]]
        assert merged["polygons"] == [[[0.2, 0.2], [0.5, 0.2], [0.5, 0.5]]]
        assert merged["geometry_rev"] == 4
        assert merged["geometry_provenance"]["adapter"] == "sam21_hiera_tiny"

    def test_no_stale_geometry_key_survives_from_the_previous_region(self):
        """Stated as a set difference so a geometry field added later cannot quietly start
        surviving the merge without this failing."""
        prev, refined = prev_region(), refined_region()
        merged = _merge_refined_region(prev, refined)
        for key in ("box", "polygon", "polygons", "mask_rle", "geometry_rev",
                    "geometry_provenance", "confidence"):
            assert merged[key] == refined[key], f"{key} came from the stale region"

    def test_the_run_that_produced_the_geometry_is_the_one_recorded(self):
        merged = _merge_refined_region(prev_region(), refined_region())
        assert merged["detector"] == "sam2"
        assert merged["confidence"] == 0.91
        assert merged["mark_source"] == "model_refined"
        assert merged["refined_from"] == "reg_1"


# ── 3. curator fields are not erased by schema defaults ─────────────────────

class TestCuratorFields:

    def test_a_curators_weighting_is_not_reset_by_the_refiners_defaults(self):
        """The refiner carries `prioritised: False, weight: 0, user_note: ""` — defaults, not
        knowledge. A plain dict merge would let them win and silently un-prioritise the region."""
        merged = _merge_refined_region(prev_region(), refined_region())
        assert merged["prioritised"] is True
        assert merged["weight"] == 5
        assert merged["user_note"] == "the reason I kept this"

    def test_a_region_with_no_prior_curator_meaning_keeps_the_valid_defaults(self):
        prev = prev_region()
        for k in ("prioritised", "weight", "user_note"):
            prev.pop(k)
        merged = _merge_refined_region(prev, refined_region())
        assert merged["prioritised"] is False
        assert merged["weight"] == 0
        assert merged["user_note"] == ""

    def test_a_refinement_of_a_region_that_never_had_meaning_adds_none(self):
        """No fabrication: the merge fills gaps from prev, it does not invent."""
        merged = _merge_refined_region({"id": "reg_1"}, refined_region())
        assert "label" not in merged or merged.get("label") == ""
        assert merged["id"] == "reg_1"
        assert merged["detector"] == "sam2"

    def test_the_inputs_are_not_mutated(self):
        """The route persists the return value; a function that also edited its arguments would
        make the pre-merge region unavailable for the telemetry written after it."""
        prev, refined = prev_region(), refined_region()
        before_prev, before_refined = dict(prev), dict(refined)
        _merge_refined_region(prev, refined)
        assert prev == before_prev
        assert refined == before_refined
