"""
WAVE3 — occlusion: the relation that answers what WAVE2.5 could only refuse.

The corpus numbers need the depth model and live in `scripts/occlusion_proof.py`. What belongs
here is everything that decides them, on synthetic fields that need no weights — the same split
`depth_organ` made, and the reason its own thirty tests run without a checkpoint.

  1. **the ordering statistic.** `in_front_of` is a claim about ORDER, and the module's first
     version tested a difference of means. That version is why this file pins the distinction:
     inverse depth compresses distance, so two far things differ by little even when one is
     plainly in front of the other. A test builds exactly that case.
  2. **admissibility.** Mask on both sides or it is interpretive, however clean the ordering. The
     WAVE2.5 ruling, applied to the relation that resolves WAVE2.5.
  3. **what it refuses.** No field, a crop field, an anonymous field, too few cells. A depth
     relation that answered anyway would be inventing occlusion.
  4. **`coplanar` is not `inside`.** The null result of this organ is not a containment claim, and
     a test reads that off the API rather than off the prose.
"""
import pytest

from backend.services import depth_organ
from backend.services import nestedness_organ as nestedness
from backend.services import occlusion_organ as occlusion

GRID = 16


def field(depth_values, *, whole_frame=True, model="Depth-Anything-V2-Small-hf",
          revision="abc123", grid=GRID):
    return {"depth": list(depth_values), "grid": grid,
            "adapter": depth_organ.SOURCE_ADAPTER, "model": model, "revision": revision,
            "preprocessing_version": "v1", "whole_frame": whole_frame}


def flat(value, grid=GRID):
    return [float(value)] * (grid * grid)


def rect_mask(x0, y0, x1, y1, grid=GRID):
    """A mask over the cell block [x0,x1) × [y0,y1), as a full-resolution RLE."""
    import numpy as np

    from backend.services import mask_geometry as mg
    side = grid * 4
    bits = np.zeros((side, side), np.uint8)
    bits[y0 * 4:y1 * 4, x0 * 4:x1 * 4] = 1
    return mg.rle_encode_mask(bits)


def masked(rid, x0, y0, x1, y1, grid=GRID):
    return {"id": rid,
            "box": {"x": x0 / grid, "y": y0 / grid,
                    "w": (x1 - x0) / grid, "h": (y1 - y0) / grid},
            "mask_rle": rect_mask(x0, y0, x1, y1, grid)}


def boxed(rid, x0, y0, x1, y1, grid=GRID):
    """A VLM estimate: real data, a legitimate candidate, inadmissible as a grounding."""
    return {"id": rid, "box": {"x": x0 / grid, "y": y0 / grid,
                               "w": (x1 - x0) / grid, "h": (y1 - y0) / grid}}


def depth_with(near_block, near_value, background):
    """A field that is `background` everywhere except one block of cells."""
    values = flat(background)
    x0, y0, x1, y1 = near_block
    for y in range(y0, y1):
        for x in range(x0, x1):
            values[y * GRID + x] = float(near_value)
    return values


# ── 1. the ordering statistic ────────────────────────────────────────────────────────────────

def test_a_small_step_still_orders_when_the_distributions_do_not_overlap():
    """THE TEST THIS MODULE WAS REBUILT AROUND.

    Inverse depth compresses distance: everything far crowds toward zero. On the real finial image
    the frame's depth spans 0.0000–8.6268 while the finial reads 0.3321 against a sky at 0.0008 —
    a step of 3.8% of the range, at the 44th percentile of all region pairs in that picture. A
    magnitude threshold either calls that coplanar or admits most of the picture.

    But the ordering is total: every cell of the finial reads nearer than every cell of the sky.
    That is what `in_front_of` claims, and it is what this measures.
    """
    values = depth_with((6, 2, 9, 5), 0.33, 0.0008)
    values[0] = 8.63                                   # something genuinely near, elsewhere
    finial = masked("finial", 6, 2, 9, 5)
    sky = masked("sky", 0, 8, GRID, GRID)

    verdict = occlusion.measure(finial, sky, field(values))
    assert verdict["relation"] == occlusion.RELATION_IN_FRONT_OF
    assert verdict["front_region_id"] == "finial"
    assert verdict["separation"] == 1.0
    # The magnitude is small against the frame, and that does not weaken the ordering.
    assert abs(verdict["depth_gap"]) / (max(values) - min(values)) < 0.05


def test_overlapping_distributions_are_coplanar_however_far_apart_the_means():
    """The converse guard. Two regions whose cells interleave are not ordered, and a mean
    difference between them is not an occlusion — it is a gradient one of them sits across."""
    values = flat(0.0)
    for i in range(GRID * GRID):
        values[i] = float(i % 10)                       # both regions span the same range
    a = masked("a", 0, 0, GRID, 4)
    b = masked("b", 0, 8, GRID, 12)
    verdict = occlusion.measure(a, b, field(values))
    assert verdict["relation"] == occlusion.RELATION_COPLANAR
    assert verdict["separation"] < occlusion.MIN_SEPARATION


def test_the_direction_is_named_rather_than_signed():
    """`front_region_id` and `back_region_id`, not a sign a reader can get backwards. Larger
    inverse depth is NEARER, which is the one convention everything here turns on."""
    values = depth_with((0, 0, 4, 4), 5.0, 0.1)
    near, far = masked("near", 0, 0, 4, 4), masked("far", 8, 8, 12, 12)

    forward = occlusion.measure(near, far, field(values))
    assert (forward["front_region_id"], forward["back_region_id"]) == ("near", "far")

    # Argument order must not change the physics.
    backward = occlusion.measure(far, near, field(values))
    assert (backward["front_region_id"], backward["back_region_id"]) == ("near", "far")
    assert backward["separation"] == pytest.approx(forward["separation"])


def test_dominance_is_reported_so_a_caller_can_disagree_with_the_floor():
    """The floor is free (per the systematicity-floor decision). A reading that carried only the
    verdict would make re-thresholding a re-measurement."""
    values = depth_with((0, 0, 4, 4), 5.0, 0.1)
    verdict = occlusion.measure(masked("a", 0, 0, 4, 4), masked("b", 8, 8, 12, 12), field(values))
    assert 0.0 <= verdict["dominance"] <= 1.0
    assert verdict["separation"] == max(verdict["dominance"], 1 - verdict["dominance"])
    assert verdict["thresholds"]["min_separation"] == occlusion.MIN_SEPARATION


def test_a_region_is_not_in_front_of_itself():
    values = depth_with((0, 0, 4, 4), 5.0, 0.1)
    region = masked("a", 0, 0, 4, 4)
    with pytest.raises(occlusion.OcclusionRefusal):
        occlusion.measure(region, region, field(values))


# ── 2. admissibility — the WAVE2.5 ruling, applied to the relation that resolves it ───────────

def test_a_box_basis_ordering_is_interpretive_however_clean_it_is():
    """THE RULING, HELD. A box's depth is the mean of a thing and the thing behind it, so an
    occlusion read off boxes is the pathology being used as the evidence for itself."""
    values = depth_with((0, 0, 4, 4), 5.0, 0.1)
    verdict = occlusion.measure(boxed("a", 0, 0, 4, 4), boxed("b", 8, 8, 12, 12), field(values))
    assert verdict["separation"] == 1.0
    assert verdict["basis"] == "box"
    assert verdict["epistemic"] == "interpretive"
    assert occlusion.is_admissible(verdict) is False


def test_one_mask_and_one_box_is_a_box_basis_pair():
    """The weaker basis governs — a cross-region claim is a claim about a PAIR, the same rule and
    the same reason as the containment ruling."""
    values = depth_with((0, 0, 4, 4), 5.0, 0.1)
    verdict = occlusion.measure(masked("a", 0, 0, 4, 4), boxed("b", 8, 8, 12, 12), field(values))
    assert verdict["basis"] == "box" and verdict["admissible"] is False


def test_the_mark_derives_its_status_from_the_basis():
    """The one place a status is written, and it is derived rather than passed in."""
    values = depth_with((0, 0, 4, 4), 5.0, 0.1)
    measured = occlusion.measure(masked("a", 0, 0, 4, 4), masked("b", 8, 8, 12, 12), field(values))
    estimate = occlusion.measure(boxed("a", 0, 0, 4, 4), boxed("b", 8, 8, 12, 12), field(values))

    assert occlusion.grounding_mark(measured, post_id="p")["epistemic_status"] == "measured"
    assert occlusion.grounding_mark(estimate, post_id="p")["epistemic_status"] == "interpretive"


def test_the_mark_names_both_producers():
    """The organ that read it and the checkpoint that produced the field. A mark naming only one
    leaves the weighted half anonymous — `depth_organ`'s rule, inherited."""
    values = depth_with((0, 0, 4, 4), 5.0, 0.1)
    verdict = occlusion.measure(masked("a", 0, 0, 4, 4), masked("b", 8, 8, 12, 12), field(values))
    mark = occlusion.grounding_mark(verdict, post_id="p", step_id="s")
    assert mark["provenance"]["producer"] == occlusion.ORGAN
    assert mark["provenance"]["model"] and mark["provenance"]["revision"]


# ── 3. what it refuses ───────────────────────────────────────────────────────────────────────

def test_no_field_is_refused_rather_than_read_as_coplanar():
    with pytest.raises(occlusion.OcclusionRefusal):
        occlusion.measure(masked("a", 0, 0, 4, 4), masked("b", 8, 8, 12, 12), None)


def test_a_crop_estimated_field_is_refused():
    """Monocular depth is a GLOBAL inference: on a crop it gives depth relative to the crop, which
    is meaningless for occlusion order and is the same shape and dtype as the real thing."""
    values = depth_with((0, 0, 4, 4), 5.0, 0.1)
    with pytest.raises(occlusion.OcclusionRefusal):
        occlusion.measure(masked("a", 0, 0, 4, 4), masked("b", 8, 8, 12, 12),
                          field(values, whole_frame=False))


def test_a_field_naming_no_model_is_refused():
    """A synthetic grid and a real one are the same list of floats, and this organ mints
    `measured`. The provenance is the whole difference."""
    values = depth_with((0, 0, 4, 4), 5.0, 0.1)
    with pytest.raises(occlusion.OcclusionRefusal):
        occlusion.measure(masked("a", 0, 0, 4, 4), masked("b", 8, 8, 12, 12),
                          field(values, model="", revision=""))


def test_too_few_cells_on_either_side_is_refused():
    """An ordering over a handful of comparisons is an ordering between grid cells, not between
    regions — the guard that made the real finial unreadable until the field was fine enough."""
    values = depth_with((0, 0, 4, 4), 5.0, 0.1)
    speck = masked("speck", 0, 0, 1, 1)
    with pytest.raises(occlusion.OcclusionRefusal) as excinfo:
        occlusion.measure(speck, masked("b", 8, 8, 12, 12), field(values))
    assert "depth cells" in str(excinfo.value)


# ── 4. `coplanar` is not `inside`, and containment is reconciled rather than overruled ────────

def test_the_organ_never_claims_containment():
    """Depth cannot see containment. Two regions at one depth might be nested, adjacent or
    unrelated, and naming this organ's null result `inside` would be the finial overreach in the
    opposite direction."""
    assert occlusion.RELATION_COPLANAR == "coplanar"
    assert not hasattr(occlusion, "RELATION_INSIDE")
    assert nestedness.RELATION_NESTED_WITHIN not in (occlusion.RELATION_IN_FRONT_OF,
                                                     occlusion.RELATION_COPLANAR)


def test_a_containment_at_one_depth_stands():
    """The true-containment case: a thing genuinely enclosed in another is at the same depth as
    it, so nothing contradicts the nesting. Measured on the real picture, all 65 mask-basis
    containments read this way, the strongest ordering among them being 0.5150."""
    values = flat(1.0)
    inner, outer = masked("inner", 6, 6, 10, 10), masked("outer", 2, 2, 14, 14)
    containment = nestedness.measure(inner, outer)
    occluded = occlusion.measure(inner, outer, field(values))
    verdict = occlusion.reconcile_containment(containment, occluded)

    assert containment["nested"] is True
    assert occluded["relation"] == occlusion.RELATION_COPLANAR
    assert verdict["verdict"] == occlusion.CONTAINMENT_STANDS
    assert verdict["relation"] == nestedness.RELATION_NESTED_WITHIN


def test_a_containment_whose_inner_is_in_front_is_superseded():
    """THE FINIAL, AS A UNIT. The extents overlap in the image plane and the regions are at
    different depths, so the containment is a projection artefact rather than a nesting.

    The container has to be much the larger for this to register, and that is not a rigged
    fixture — it is the effect itself. A container's mask covers the thing in front of it, so its
    own depth reading is pulled toward that thing, exactly as a box's is. The difference is one of
    degree: a mask covers the intruder and its own surface, a box covers the intruder and whatever
    else the rectangle caught.
    """
    values = depth_with((6, 6, 10, 10), 5.0, 0.1)
    inner, outer = masked("inner", 6, 6, 10, 10), masked("outer", 0, 0, GRID, GRID)
    containment = nestedness.measure(inner, outer)
    occluded = occlusion.measure(inner, outer, field(values))
    verdict = occlusion.reconcile_containment(containment, occluded)

    assert containment["nested"] is True and containment["basis"] == "mask"
    assert occluded["front_region_id"] == "inner"
    assert verdict["verdict"] == occlusion.CONTAINMENT_SUPERSEDED
    assert verdict["relation"] == occlusion.RELATION_IN_FRONT_OF


def test_an_estimate_may_propose_the_correction_and_may_not_make_it():
    """The ruling in the other direction, and the case the real finial actually lands in: the
    original 0.999 was box-basis, so a box-basis occlusion reading cannot overturn it either. An
    estimate does not get to correct an estimate into a measurement."""
    values = depth_with((6, 6, 10, 10), 5.0, 0.1)
    inner, outer = boxed("inner", 6, 6, 10, 10), boxed("outer", 2, 2, 14, 14)
    verdict = occlusion.reconcile_containment(nestedness.measure(inner, outer),
                                              occlusion.measure(inner, outer, field(values)))
    assert verdict["verdict"] == occlusion.CONTAINMENT_UNJUDGED


def test_a_containment_whose_OUTER_is_nearer_still_stands():
    """Direction matters: the correction is 'the inner is in front of its container', not 'they
    are at different depths'. A recessed part is still a part."""
    values = depth_with((2, 2, 14, 14), 5.0, 0.1)      # the CONTAINER is the near one
    for y in range(6, 10):                              # the inner sits deeper, a recess
        for x in range(6, 10):
            values[y * GRID + x] = 0.1
    inner, outer = masked("inner", 6, 6, 10, 10), masked("outer", 2, 2, 14, 14)
    verdict = occlusion.reconcile_containment(nestedness.measure(inner, outer),
                                              occlusion.measure(inner, outer, field(values)))
    assert verdict["verdict"] == occlusion.CONTAINMENT_STANDS


def test_no_containment_reading_is_nothing_to_reconcile():
    assert occlusion.reconcile_containment(None, None)["verdict"] == occlusion.CONTAINMENT_UNJUDGED


# ── the organ's own vocabulary ───────────────────────────────────────────────────────────────

def test_the_organ_imports_no_model_and_no_image_library():
    """Pure, like `depth_organ`: two region dicts and a field in, a relation out. This is what
    lets a population of agents share one inference rather than each paying for one."""
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path(occlusion.__file__).read_text())
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    for forbidden in ("torch", "PIL", "transformers", "numpy", "depth_service"):
        assert not any(forbidden in name for name in imported), forbidden


def test_depth_is_never_converted_to_a_distance():
    """`depth_organ`'s rule, inherited: Depth-Anything gives relative inverse depth, and a field
    called `distance_m` would be units arriving from nowhere — and believed."""
    values = depth_with((0, 0, 4, 4), 5.0, 0.1)
    verdict = occlusion.measure(masked("a", 0, 0, 4, 4), masked("b", 8, 8, 12, 12), field(values))
    for banned in ("distance_m", "metres", "meters", "distance"):
        assert banned not in verdict
