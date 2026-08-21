"""
PERCEPTUAL-FORMS-001B — the raster substrate, and the eleven things it must not let through.

WHY A SEPARATE MODULE FROM THE FORMS. `test_perception_lab_extent_forms.py` proves the three
payloads are what the contract says they are. This proves the arithmetic underneath them: that a
malformed mask is refused rather than decoded into something plausible, that the connectivity
pairing is the declared one and not whichever `_components_4conn` happened to use, and that every
number is a count rather than an estimate.

THE MASKS ARE ASCII ON PURPOSE. A 5x5 donut written as `#####` / `#...#` is a fixture a person can
check by eye, and a test whose expected value nobody can verify by looking is a test that will be
updated to match whatever the code does.

PURE. No database, no network, no model, no image, no cv2.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

import pytest

from backend.schemas.perception_lab import RefusalCode
from backend.services.mask_geometry import rle_encode
from backend.services.perception_lab.extent_forms import measure as M
from backend.services.perception_lab.extent_forms import raster as R


def mask(rows: Sequence[str]) -> Dict[str, Any]:
    """ASCII to COCO RLE. `#` is a pixel of the thing; anything else is not."""
    h, w = len(rows), len(rows[0])
    bits = bytearray()
    for row in rows:
        assert len(row) == w, "every row of a synthetic mask is the same width"
        bits.extend(1 if ch == "#" else 0 for ch in row)
    return rle_encode(bits, h, w)


def piece_of(rows: Sequence[str]) -> R.PixelSet:
    return R.foreground_components(R.raster_of(mask(rows), what="fixture"))[0]


SOLID = ["........", "..####..", "..####..", "..####..", "........"]
DONUT = ["#####", "#...#", "#...#", "#...#", "#####"]
TWO_ISLANDS = ["#..#", "#..#", "...."]
CORNER_TOUCH = ["#.", ".#"]
EDGE_TOUCH = ["##", ".."]


# ── the malformed masks ──────────────────────────────────────────────────────


@pytest.mark.parametrize("raw, why", [
    (None, "no mask at all"),
    ("{}", "a string"),
    ({"counts": [4]}, "no size"),
    ({"size": [2], "counts": [4]}, "a one-number raster"),
    ({"size": [2, 2], "counts": "0044"}, "counts that are not a run list"),
    ({"size": [2, 2], "counts": [1, 1]}, "runs that do not cover the raster"),
    ({"size": [0, 4], "counts": []}, "a raster with no pixels"),
    ({"size": [2, 2], "counts": [1.5, 2.5]}, "fractional runs"),
])
def test_a_mask_that_is_not_a_mask_is_refused_rather_than_decoded(raw, why):
    with pytest.raises(R.ExtentFormRefusal) as caught:
        R.canonical_rle(raw, what="fixture")
    assert caught.value.refusal.code is RefusalCode.MISSING_EXTENT_INPUTS, why
    assert caught.value.refusal.missing, "a typed no says what would satisfy it"


def test_a_negative_run_is_refused_even_though_the_runs_still_sum_to_the_raster():
    """The one malformation `mask_geometry.rle_is_valid` accepts.

    `[6, -2, 2, 2, 4]` sums to 12 on a 3x4 raster and passes that predicate, and decodes to a mask
    that has nothing to do with what was written. A validity check a lie can satisfy is the reason
    this package does not reuse it.
    """
    from backend.services.mask_geometry import rle_is_valid
    lying = {"size": [3, 4], "counts": [6, -2, 2, 2, 4]}
    assert rle_is_valid(lying), "the precondition for this test: the older predicate accepts it"
    with pytest.raises(R.ExtentFormRefusal) as caught:
        R.canonical_rle(lying, what="fixture")
    assert "negative run" in caught.value.refusal.message


def test_a_refusal_is_a_record_and_not_an_exception_message():
    with pytest.raises(R.ExtentFormRefusal) as caught:
        R.canonical_rle(None, what="fixture")
    refusal = caught.value.refusal
    assert refusal.organ is R.ORGAN
    assert refusal.remedy, "a refusal that cannot be acted on is a failure with better prose"
    assert refusal.model_dump()["code"] == RefusalCode.MISSING_EXTENT_INPUTS


# ── the canonical spelling ───────────────────────────────────────────────────


def test_two_spellings_of_one_mask_collapse_to_one_id():
    """A zero-length run is legal COCO and changes no pixel. It must change no id either."""
    tight = {"size": [2, 2], "counts": [1, 2, 1]}
    padded = {"size": [2, 2], "counts": [1, 2, 0, 0, 1]}
    assert R.canonical_rle(tight, what="a") == R.canonical_rle(padded, what="b")
    assert R.digest_of(R.canonical_rle(tight, what="a")) == \
           R.digest_of(R.canonical_rle(padded, what="b"))


def test_the_same_pixels_on_a_different_raster_are_not_the_same_thing():
    small = R.raster_of(mask(["#.", ".."]), what="small")
    large = R.raster_of(mask(["#...", "....", "....", "...."]), what="large")
    assert R.foreground_components(small)[0].digest != R.foreground_components(large)[0].digest


# ── the connectivity pairing ─────────────────────────────────────────────────


def test_the_pairing_is_four_for_the_thing_and_eight_for_the_void():
    assert (R.FOREGROUND_CONNECTIVITY, R.BACKGROUND_CONNECTIVITY) == (4, 8)


def test_two_islands_touching_only_at_a_corner_stay_two():
    pieces = R.foreground_components(R.raster_of(mask(CORNER_TOUCH), what="corner"))
    assert len(pieces) == 2
    assert [p.area_px for p in pieces] == [1, 1]


def test_two_islands_sharing_an_edge_are_one():
    pieces = R.foreground_components(R.raster_of(mask(EDGE_TOUCH), what="edge"))
    assert len(pieces) == 1 and pieces[0].area_px == 2


def test_the_void_between_two_corner_touching_islands_is_one_void_and_nothing_is_enclosed():
    """The pairing, seen from the other side. Under an 8-connected foreground those two islands
    would be one thing; under a 4-connected background the void between them would be two, and one
    of the two would look enclosed. Neither happens here."""
    raster = R.raster_of(mask(["#..", ".#.", "..#"]), what="diagonal")
    voids = R.complement_components(raster)
    assert len(voids) == 1
    assert voids[0].touches_border


def test_components_come_back_in_row_major_order_of_their_first_pixel():
    pieces = R.foreground_components(R.raster_of(mask(["..#", "...", "#.."]), what="order"))
    assert [p.pixels for p in pieces] == [(2,), (6,)]


def test_a_void_of_one_piece_is_not_a_void_of_the_whole_mask():
    """A ring with a separate island sitting inside it.

    Asked of the whole mask, the ring's opening comes back as the four cells around the island —
    or not at all. Asked of the ring alone, it is the one void the ring encloses, island included,
    which is what the ring's own inner boundary actually bounds.
    """
    raster = R.raster_of(mask(["#####", "#...#", "#.#.#", "#...#", "#####"]), what="nested")
    ring, island = R.foreground_components(raster)
    assert island.area_px == 1
    whole = [v for v in R.complement_components(raster) if not v.touches_border]
    assert sum(v.area_px for v in whole) == 8, "the island is foreground, so it splits the void"
    of_ring = [v for v in R.complement_components(raster, of=ring) if not v.touches_border]
    assert len(of_ring) == 1 and of_ring[0].area_px == 9, "island included: it is not the ring"


def test_a_piece_measured_on_another_raster_cannot_be_complemented_against_this_one():
    small = R.foreground_components(R.raster_of(mask(["#.", ".."]), what="small"))[0]
    large = R.raster_of(mask(["#...", "....", "....", "...."]), what="large")
    with pytest.raises(R.ExtentFormRefusal) as caught:
        R.complement_components(large, of=small)
    assert caught.value.refusal.code is RefusalCode.INVALID_PARAMETERS


# ── the measurements ─────────────────────────────────────────────────────────


def test_area_is_a_count_and_the_ratio_is_the_count_over_the_frame():
    piece = piece_of(SOLID)
    assert piece.area_px == 12
    assert M.normalized_area(piece) == round(12 / 40, 6)


def test_the_box_is_tight_and_an_empty_piece_has_none():
    piece = piece_of(SOLID)
    assert M.bbox(piece) == {"x": 0.25, "y": 0.2, "w": 0.5, "h": 0.6}
    assert M.bbox(R.PixelSet(h=4, w=4, pixels=(), connectivity=4)) is None


def test_the_centroid_of_a_single_pixel_lands_inside_it():
    piece = piece_of(["....", ".#..", "....", "...."])
    assert M.centroid(piece) == (round(1.5 / 4, 6), round(1.5 / 4, 6))


def test_the_centroid_of_a_symmetric_ring_sits_at_its_middle():
    assert M.centroid(piece_of(DONUT)) == (0.5, 0.5)


def test_the_perimeter_counts_the_frame_edge_because_that_is_where_looking_stopped():
    """A shape running off the side of the image has a perimeter there. The measurement ends at
    the frame; pretending the edge is not an edge would make a cropped square look like a strip."""
    assert M.perimeter_px(piece_of(["##", "##"])) == 8
    assert M.perimeter_px(piece_of(["....", ".##.", ".##.", "...."])) == 8


def test_the_gap_between_two_pieces_is_an_integer_number_of_steps():
    a, b = R.foreground_components(R.raster_of(mask(["#..#", "....", "....", "...."]), what="g"))
    assert M.gap_px(a, b) == 3
    touching = R.foreground_components(R.raster_of(mask(CORNER_TOUCH), what="c"))
    assert M.gap_px(*touching) == 1, "a corner touch is one step, not 1.4142135"


def test_a_gap_across_two_rasters_is_none_rather_than_a_resampled_number():
    a = R.foreground_components(R.raster_of(mask(["#.", ".."]), what="a"))[0]
    b = R.foreground_components(R.raster_of(mask(["#...", "....", "....", "...."]), what="b"))[0]
    assert M.gap_px(a, b) is None


def test_the_surface_of_a_piece_is_exactly_the_pixels_a_gap_could_be_measured_from():
    """The restriction is a fact, not an optimisation, so brute force must agree with it.

    A 6x6 frame holding a 4x4 block has twelve surface pixels and four interior ones. If the
    minimum distance to another piece were ever achieved at one of those four, `gap_px` would be
    quietly reporting a larger number than the truth on every large mask.
    """
    inner = piece_of(["......", ".####.", ".####.", ".####.", ".####.", "......"])
    assert len(M.surface(inner)) == 12 and inner.area_px == 16

    other = R.foreground_components(
        R.raster_of(mask(["......", "......", "......", "......", "......", "#....."]),
                    what="far"))[0]
    w = inner.w
    brute = min(max(abs(p // w - q // w), abs(p % w - q % w))
                for p in inner.pixels for q in other.pixels)
    assert M.gap_px(inner, other) == brute


def test_a_signed_lattice_area_is_an_integer_and_its_sign_is_the_answer():
    square = [(0, 0), (0, 2), (2, 2), (2, 0)]
    assert M.lattice_area(square) == 4
    assert M.lattice_area(list(reversed(square))) == -4
