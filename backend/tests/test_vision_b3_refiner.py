"""
VISION-BUILD-001 B3 — exact-mask refiner integration (SAM 2.1 Hiera Tiny).

The real model is benchmarked in the B3 report (peak ~597 MiB VRAM, warm prompts
11–166 ms, clean unload). Here we test the pure integration seam: a refiner mask →
a PROPOSED region revision that is non-destructive (bumps geometry_rev, never overwrites
the base), plus the adapter's MaskRefiner identity.
"""
import numpy as np
import pytest

from backend.services import mask_geometry as mg
from backend.services.vision_orchestrator.adapters import (
    refined_mask_to_region, Sam2RefinerAdapter)
from backend.services.vision_orchestrator.contracts import Capability, ResourceKind


def disc(h, w, cy, cx, r):
    yy, xx = np.mgrid[0:h, 0:w]
    return ((yy - cy) ** 2 + (xx - cx) ** 2 <= r * r).astype("uint8")


def test_refined_mask_becomes_proposed_region():
    m = disc(60, 60, 30, 30, 18)
    region = refined_mask_to_region(m, score=0.86, prompt="point")
    assert mg.rle_is_valid(region["mask_rle"])
    assert region["box"] == mg.rle_bbox_norm(region["mask_rle"])   # box derived from mask
    assert region["detector"] == "sam2" and region["actor"] == "creator"
    assert region["proposed"] is True                              # not authoritative yet
    assert region["confidence"] == 0.86
    prov = region["geometry_provenance"]
    assert prov["kind"] == "mask" and prov["method"] == "sam2-refine"
    assert prov["adapter"] == "sam21_hiera_tiny" and prov["prompt"] == "point"


def test_refine_proposes_next_revision_without_touching_base():
    base = {"id": "seg_2", "box": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
            "mask_rle": mg.rle_encode_mask(disc(50, 50, 20, 20, 8)), "geometry_rev": 3}
    base_snapshot = dict(base)
    proposal = refined_mask_to_region(disc(50, 50, 25, 25, 14), base_id="seg_2",
                                      base_geometry_rev=base["geometry_rev"], score=0.9)
    # same identity is upgraded, next revision proposed, base object untouched.
    assert proposal["id"] == "seg_2" and proposal["refined_from"] == "seg_2"
    assert proposal["geometry_rev"] == 4                           # base 3 → proposed 4
    assert base == base_snapshot                                   # base not mutated
    assert proposal["mask_rle"] != base["mask_rle"]               # a genuinely new mask


def test_box_and_existing_mask_prompt_kinds_recorded():
    m = disc(40, 40, 20, 20, 10)
    assert refined_mask_to_region(m, prompt="box")["geometry_provenance"]["prompt"] == "box"
    assert refined_mask_to_region(m, prompt="existing-mask")["geometry_provenance"]["prompt"] == "existing-mask"


def test_refined_region_is_schema_valid():
    # VISION-B5 regression: a refined region must validate against the Region model —
    # curator fields carry real defaults, never None (else the Post response_model 500s
    # on a later GET). This was the bug browser-verification of the Differential tool found.
    from backend.schemas.post import Region
    region = refined_mask_to_region(disc(40, 40, 20, 20, 12), score=0.9)
    assert region["prioritised"] is False and region["weight"] == 0 and region["user_note"] == ""
    m = Region(**region)                                    # must not raise
    assert m.prioritised is False and m.weight == 0 and m.user_note == ""


def test_refiner_adapter_identity():
    a = Sam2RefinerAdapter()
    assert a.spec.name == "sam21_hiera_tiny"
    assert a.spec.capability is Capability.MASK_REFINE
    assert a.spec.resource is ResourceKind.GPU
    assert a.spec.model_id == "sam2.1_hiera_tiny"
    # availability reflects deps + checkpoint presence on this box (installed in B3).
    assert isinstance(a.is_available(), bool)
