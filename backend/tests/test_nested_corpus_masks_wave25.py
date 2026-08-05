"""
WAVE2.5 — masks over boxes: what the mixed corpus actually does, pinned.

The ring-shaped container (`test_movement_kernel_lanem.py`) already pins the principle: a mask
refuses the containment a box grants. What this file pins is the thing that principle runs into on
real data — **a corpus where only some regions carry masks**, which is the state the sweep leaves
it in and the state it will stay in for as long as the VLM's estimated boxes and SAM 3's measured
masks cannot be safely identified with each other.

The measured facts these tests encode, from the two posts the movement kernel seeds and places on:

  · adding masked regions beside unmasked ones does NOT upgrade the unmasked pairs. A mask basis
    needs BOTH regions masked on a shared raster; one of each is still a box measurement.
  · so the box-basis pairs keep dominating the ranking — `fine_0 in cseg_background_0` scored
    0.988 on boxes, which is the finial-in-sky pathology in its new clothes.
  · where both ARE masked, the mask basis refused **114** containments that boxes granted across
    3,618 measurable pairs, and granted 2 that boxes refused.

That last number is the lane's whole point, and the first two are why it is not the end of it.
"""
from __future__ import annotations

import importlib.util
import os

import numpy as np
import pytest

from backend.services import mask_geometry as mg
from backend.services import nestedness_organ as organ

_SPEC = importlib.util.spec_from_file_location(
    "nested_corpus_masks",
    os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "nested_corpus_masks.py"))
sweep = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sweep)


def _box(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h}


def _masked(rid, bits, box):
    return {"id": rid, "mask_rle": mg.rle_encode_mask(bits), "box": box, "label": ""}


def _boxed(rid, box, label=""):
    return {"id": rid, "box": box, "label": label}


def _sky_and_finial():
    """The real failure, as geometry: a sky with a hole where the temple is, and a finial in it.

    This is the corpus case, not the unit case — the sky mask genuinely has a temple-shaped hole,
    and the finial sits in that hole, in front of the sky rather than inside it.
    """
    sky = np.zeros((40, 40), np.uint8)
    sky[0:20, 0:40] = 1
    sky[4:20, 16:24] = 0                       # the temple's silhouette, punched out
    finial = np.zeros((40, 40), np.uint8)
    finial[5:9, 18:22] = 1
    return (_masked("finial", finial, _box(18 / 40, 5 / 40, 4 / 40, 4 / 40)),
            _masked("sky", sky, _box(0.0, 0.0, 1.0, 0.5)))


# ── 1. the headline: masks refuse what boxes granted ─────────────────────────

def test_a_finial_in_front_of_the_sky_is_refused_on_masks_and_granted_on_boxes():
    """0.992 'nested in Sky' was the worst finding of Lane M's run. This is why it happened."""
    inner, outer = _sky_and_finial()
    by_mask = organ.measure(inner, outer)
    assert by_mask["basis"] == "mask"
    assert by_mask["containment"] == 0.0 and by_mask["nested"] is False

    stripped = ({k: v for k, v in inner.items() if k != "mask_rle"},
                {k: v for k, v in outer.items() if k != "mask_rle"})
    by_box = organ.measure(*stripped)
    assert by_box["basis"] == "box"
    assert by_box["containment"] == 1.0 and by_box["nested"] is True


def test_the_box_measurement_says_out_loud_that_it_over_estimates():
    """A box containment is weaker evidence and has to carry that itself — a reader who only has
    the number cannot tell, and `basis` alone does not explain why it matters."""
    inner, outer = _sky_and_finial()
    by_box = organ.measure({k: v for k, v in inner.items() if k != "mask_rle"},
                           {k: v for k, v in outer.items() if k != "mask_rle"})
    assert "over-estimate" in by_box["basis_detail"]


# ── 2. the mixed corpus: one masked region does not upgrade its unmasked partner ──

def test_a_mask_basis_needs_both_regions_masked():
    """The measured consequence of adding SAM 3 regions beside the VLM's: 25 of 92 nested pairs on
    the real post came back `mask`, and the other 67 stayed `box` because only one side had one."""
    inner, outer = _sky_and_finial()
    half = organ.measure({k: v for k, v in inner.items() if k != "mask_rle"}, outer)
    assert half["basis"] == "box"
    assert half["nested"] is True                  # and so the false grounding survives


def test_masks_on_different_rasters_fall_back_to_boxes_rather_than_resampling():
    """Resampling one mask onto the other's grid would invent detail neither organ measured."""
    small = np.zeros((20, 20), np.uint8)
    small[5:9, 9:11] = 1
    inner = _masked("small_raster", small, _box(18 / 40, 5 / 40, 4 / 40, 4 / 40))
    _, outer = _sky_and_finial()
    assert inner["mask_rle"]["size"] != outer["mask_rle"]["size"]
    assert organ.measure(inner, outer)["basis"] == "box"


def test_find_nested_pairs_reports_both_bases_in_one_mixed_post():
    """The corpus state the sweep leaves behind, in miniature."""
    inner, outer = _sky_and_finial()
    unmasked_whole = _boxed("frame", _box(0.0, 0.0, 1.0, 1.0), label="Frame")
    pairs = organ.find_nested_pairs([inner, outer, unmasked_whole])
    bases = {(p["inner_region_id"], p["outer_region_id"]): p["basis"] for p in pairs}
    assert bases.get(("finial", "frame")) == "box"
    assert ("finial", "sky") not in bases          # refused on masks, so never a pair at all


# ── 3. the sweep's own discipline ────────────────────────────────────────────

def test_the_concept_vocabulary_comes_from_this_image_and_not_a_fixed_list():
    """SF-004-R2: a fixed vocabulary scored 6/18 by asking a neck close-up for `placket`. The
    labels the VLM wrote on THIS image scored 27/35."""
    post = {"region_annotations": [
        _boxed("region_0", _box(0, 0, 1, 1), label="Temple Structure"),
        _boxed("fine_0", _box(0, 0, 0.1, 0.1), label="golden finial"),
        _boxed("fine_1", _box(0, 0, 0.1, 0.1), label="Golden Finial"),   # same concept, cased
        _boxed("fine_2", _box(0, 0, 0.1, 0.1), label="   "),             # nothing to ask for
    ]}
    assert sweep.concepts_of(post) == ["Temple Structure", "golden finial"]


def test_a_concept_this_script_already_produced_is_never_asked_for_again():
    """Idempotence. Re-running must not re-segment, or a second sweep doubles every region."""
    post = {"region_annotations": [
        _boxed("cseg_golden_finial_0", _box(0, 0, 0.1, 0.1), label="golden finial"),
        _boxed("region_0", _box(0, 0, 1, 1), label="Sky"),
    ]}
    assert sweep.concepts_of(post) == ["Sky"]


def test_the_fingerprint_ignores_appended_regions_and_catches_moved_ones():
    """The safety claim the sweep makes: it appends, and nothing that was already there moves."""
    original = [_boxed("region_0", _box(0, 0, 1, 1), label="Sky")]
    before = sweep.regions_fingerprint(original)

    appended = [*original, _boxed("cseg_sky_0", _box(0, 0, 0.5, 0.5))]
    assert sweep.regions_fingerprint(appended) == before, "appending must not trip the guard"

    moved = [{**original[0], "box": _box(0, 0, 0.9, 0.9)}]
    assert sweep.regions_fingerprint(moved) != before, "a moved pre-existing region must trip it"


def test_a_region_carrying_no_label_is_not_a_concept_to_segment():
    """SAM 3 masks SOMETHING for nearly any phrase, so an empty one is an invitation to fabricate
    — the same guard `_run_concept_segment` puts in front of the actuator."""
    assert sweep.concepts_of({"region_annotations": [_boxed("r", _box(0, 0, 1, 1))]}) == []
