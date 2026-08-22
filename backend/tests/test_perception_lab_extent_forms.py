"""
PERCEPTUAL-FORMS-001B — the three exact Extent forms, and what each of them may not say.

WHAT THIS MODULE HOLDS TO. `test_perception_lab_forms.py` proves the grammar is closed and the
payload shapes cannot express certain lies. This proves the PRODUCER: that what comes out of
`extent_forms` validates as the form it claims, that a hole is never a fragment, that an outer
boundary is never a hole boundary, and that two runs over one mask produce the same bytes on any
machine.

THE EXACTNESS PROOF IS THE ROUND TRIP. A ring is claimed to be the exact border of a pixel set, so
rasterizing every ring of a mask must reproduce that mask byte for byte — not approximately, not
within a tolerance. `mask_geometry.polygons_to_bits` is the rasterizer the rest of the tree
already uses, and it is used here unmodified so the proof is against something this package does
not own.

THE FIXTURES ARE ASCII. A donut written as `#####` / `#...#` is checkable by eye, and the seven
controls the lane was asked for — solid, donut, two islands, touching islands, nested, malformed,
incompatible — are each written out in full rather than generated.

PURE. No database, no network, no model, no image, no cv2.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

import pytest
from pydantic import ValidationError

from backend.schemas import perception_lab as S
from backend.schemas.perception_lab import (ExtentInstance, ExtentSetPayload, PerceptualForm,
                                            RefusalCode, RingWinding)
from backend.services.mask_geometry import polygons_to_bits, rle_encode
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab.extent_forms import boundary as B
from backend.services.perception_lab.extent_forms import fragments as F
from backend.services.perception_lab.extent_forms import holes as H
from backend.services.perception_lab.extent_forms import inputs as I
from backend.services.perception_lab.extent_forms import measure as M
from backend.services.perception_lab.extent_forms import raster as R

DIGEST = "sha256:0f1e2d3c"


def mask(rows: Sequence[str]) -> Dict[str, Any]:
    """ASCII to COCO RLE. `#` is a pixel of the thing; anything else is not."""
    h, w = len(rows), len(rows[0])
    bits = bytearray()
    for row in rows:
        assert len(row) == w, "every row of a synthetic mask is the same width"
        bits.extend(1 if ch == "#" else 0 for ch in row)
    return rle_encode(bits, h, w)


def extent(rows: Sequence[str], *, artifact_id: str = "art_1", instance_id: str = "inst_1",
           geometry_rev: int = 3) -> I.SourceExtent:
    return I.source_extent(artifact_id, {"instance_id": instance_id, "mask_rle": mask(rows),
                                         "geometry_rev": geometry_rev})


#: The seven synthetic controls this lane was asked to prove itself against.
SOLID = ["........", "..####..", "..####..", "..####..", "........"]
DONUT = ["#####", "#...#", "#...#", "#...#", "#####"]
TWO_ISLANDS = ["#..#", "#..#", "...."]
CORNER_TOUCH = ["#...", ".#..", "....", "...."]
EDGE_TOUCH = ["##..", "....", "....", "...."]
NESTED = ["#####", "#...#", "#.#.#", "#...#", "#####"]
PINCHED = ["####", "#.##", "##.#", "####"]
EMPTY = ["....", "....", "....", "...."]
MALFORMED = {"size": [4, 4], "counts": [3, 3]}


def rasterize(payload) -> Dict[int, Dict[str, Any]]:
    """Every boundary in a payload, drawn back onto its own raster by the tree's own rasterizer."""
    out: Dict[int, Dict[str, Any]] = {}
    for i, record in enumerate(payload.boundaries):
        h, w = record.raster_shape
        rings = [[[p[0], p[1]] for p in ring.points] for ring in record.rings]
        out[i] = rle_encode(polygons_to_bits(rings, h, w), h, w)
    return out


# ── extent.boundary_rings ────────────────────────────────────────────────────


def test_a_solid_rectangle_has_one_outer_ring_and_no_holes():
    derived = B.boundary_rings([extent(SOLID)], source_image_digest=DIGEST)
    assert derived.form is PerceptualForm.EXTENT_BOUNDARY_RINGS
    assert derived.payload.rings_traced == 1
    ring, = derived.payload.boundaries[0].rings
    assert ring.winding is RingWinding.OUTER
    assert len(ring.points) == 4, "four corners, because the straight runs between them are not"


def test_a_donut_has_an_outer_ring_and_an_inner_one_and_they_are_not_interchangeable():
    derived = B.boundary_rings([extent(DONUT)], source_image_digest=DIGEST)
    outer, inner = derived.payload.boundaries[0].rings
    assert (outer.winding, inner.winding) == (RingWinding.OUTER, RingWinding.INNER)
    assert derived.measurements["encloses_px"][outer.ring_id] == 25
    assert derived.measurements["encloses_px"][inner.ring_id] == 9


def test_the_two_rings_of_a_donut_run_in_opposite_directions_and_the_class_is_the_sign():
    """The producer knows which side is inside because it put it there.

    A reader is forbidden from recovering that from point order — but the producer's own
    classification had better BE the orientation, or the declared winding is a guess that happens
    to be right.
    """
    pieces = R.foreground_components(R.raster_of(mask(DONUT), what="donut"))
    outer, inner = B.trace(pieces[0])
    assert M.lattice_area(outer.lattice) > 0 and outer.winding is RingWinding.OUTER
    assert M.lattice_area(inner.lattice) < 0 and inner.winding is RingWinding.INNER


def test_a_reader_cannot_recover_the_winding_from_the_points_which_is_why_it_is_declared():
    """The schema accepts a ring whose points run one way and whose winding says the other.

    That is not a hole in the contract; it is the contract's point. Winding is DECLARED, so a
    consumer must read the field — and this test is what stops someone replacing that field with
    an inference the day two renderers disagree.
    """
    derived = B.boundary_rings([extent(DONUT)], source_image_digest=DIGEST)
    outer = derived.payload.boundaries[0].rings[0]
    reversed_ring = outer.model_copy(update={"points": list(reversed(outer.points))})
    assert reversed_ring.winding is RingWinding.OUTER


def test_two_separated_islands_are_two_outer_rings_of_one_instance():
    derived = B.boundary_rings([extent(TWO_ISLANDS)], source_image_digest=DIGEST)
    record, = derived.payload.boundaries
    assert derived.payload.rings_traced == 2
    assert [r.winding for r in record.rings] == [RingWinding.OUTER, RingWinding.OUTER]


def test_islands_that_touch_at_a_corner_stay_two_rings_and_ones_that_share_an_edge_become_one():
    corner = B.boundary_rings([extent(CORNER_TOUCH)], source_image_digest=DIGEST)
    edge = B.boundary_rings([extent(EDGE_TOUCH)], source_image_digest=DIGEST)
    assert corner.payload.rings_traced == 2
    assert edge.payload.rings_traced == 1


def test_a_shape_inside_a_hole_keeps_its_own_outer_ring_and_does_not_join_the_ring_around_it():
    derived = B.boundary_rings([extent(NESTED)], source_image_digest=DIGEST)
    rings = derived.payload.boundaries[0].rings
    assert [r.winding for r in rings] == [RingWinding.OUTER, RingWinding.INNER, RingWinding.OUTER]
    assert len({r.ring_id for r in rings}) == 3


def test_a_void_that_narrows_to_a_single_corner_stays_one_ring_that_passes_through_it_twice():
    """The pinch. Two void pixels meeting diagonally inside one piece are ONE void under the
    declared pairing, so their boundary is one closed curve — and the corner where it pinches is
    visited twice, by two different turns."""
    derived = B.boundary_rings([extent(PINCHED)], source_image_digest=DIGEST)
    outer, inner = derived.payload.boundaries[0].rings
    assert inner.winding is RingWinding.INNER
    assert derived.measurements["encloses_px"][inner.ring_id] == 2
    corners = [tuple(p) for p in inner.points]
    assert len(corners) != len(set(corners)), "the pinch corner is on the ring twice"


def test_every_ring_rasterizes_back_to_the_mask_it_was_traced_from():
    """The exactness claim, made falsifiable. Not `close to`, not `within a tolerance` — the same
    bytes, through a rasterizer this package does not own."""
    for rows in (SOLID, DONUT, TWO_ISLANDS, CORNER_TOUCH, EDGE_TOUCH, NESTED, PINCHED,
                 ["###", "#.#", "##."], ["#"], ["#####"], ["#", "#", "#"]):
        source = extent(rows)
        derived = B.boundary_rings([source], source_image_digest=DIGEST)
        assert rasterize(derived.payload)[0] == source.raster.rle, rows


def test_the_traced_perimeter_and_the_counted_perimeter_are_the_same_number():
    """Two independent routes to one integer: the tracer follows the cracks into curves, and
    `perimeter_px` counts the outward-facing pixel sides without tracing anything."""
    for rows in (SOLID, DONUT, NESTED, PINCHED, CORNER_TOUCH):
        raster = R.raster_of(mask(rows), what="x")
        counted = sum(M.perimeter_px(p) for p in R.foreground_components(raster))
        traced = sum(r.cracks for p in R.foreground_components(raster) for r in B.trace(p))
        assert counted == traced, rows


def test_an_empty_mask_has_no_boundary_and_that_is_an_answer_rather_than_a_failure():
    derived = B.boundary_rings([extent(EMPTY)], source_image_digest=DIGEST)
    assert derived.payload.rings_traced == 0
    assert derived.payload.boundaries == []


def test_the_count_of_rings_traced_never_drifts_from_the_rings_recorded():
    """`rings_traced` is what proves something looked, so it is checked against the list rather
    than trusted beside it — and a producer that reported one number and recorded another would
    not validate."""
    derived = B.boundary_rings([extent(NESTED), extent(DONUT, instance_id="inst_2")],
                               source_image_digest=DIGEST)
    assert derived.payload.rings_traced == 5
    drifted = derived.payload.model_dump()
    drifted["rings_traced"] = 4
    with pytest.raises(ValidationError):
        type(derived.payload).model_validate(drifted)


def test_a_ring_carries_no_length_because_the_field_carries_no_unit():
    """A step of one pixel is `1/w` across and `1/h` down. On any raster that is not square a
    single normalized length mixes two scales, and a pixel count in a field a reader takes for
    normalized is worse than an absent number. The exact integer is in `measurements`."""
    derived = B.boundary_rings([extent(SOLID)], source_image_digest=DIGEST)
    ring, = derived.payload.boundaries[0].rings
    assert ring.length is None
    assert derived.measurements["perimeter_px"][ring.ring_id] == 14


def test_a_ring_id_survives_a_change_somewhere_else_in_the_image():
    """Content-addressed identity, and the reason for it. Adding an island in the corner must not
    renumber the ring around the arch on the other side of the picture."""
    alone = B.boundary_rings([extent(["....", ".##.", ".##.", "...."])],
                             source_image_digest=DIGEST)
    with_island = B.boundary_rings([extent(["#...", ".##.", ".##.", "...."])],
                                   source_image_digest=DIGEST)
    first = alone.payload.boundaries[0].rings[0].ring_id
    assert first in {r.ring_id for r in with_island.payload.boundaries[0].rings}


def test_the_same_mask_traced_twice_produces_the_same_bytes():
    one = B.boundary_rings([extent(NESTED)], source_image_digest=DIGEST)
    two = B.boundary_rings([extent(NESTED)], source_image_digest=DIGEST)
    assert one.payload.model_dump() == two.payload.model_dump()


def test_nothing_in_this_package_imports_a_model_a_database_or_cv2():
    """The independence claim, checked in the source rather than asserted in a docstring.

    `mask_geometry.bits_to_polygons` traces with cv2 when it is there and falls back to bounding
    rectangles when it is not, so the same mask gives two different answers on two machines. This
    package has to give one, which means it cannot reach for either.
    """
    import pathlib
    package = pathlib.Path(R.__file__).parent
    banned = ("cv2", "numpy", "torch", "motor", "pymongo", "PIL", "requests", "httpx")
    for path in sorted(package.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for name in banned:
            assert f"import {name}" not in source, f"{path.name} imports {name}"


# ── what a derivation is handed ──────────────────────────────────────────────


def test_a_derivation_with_no_source_digest_is_refused_rather_than_left_untraceable():
    with pytest.raises(R.ExtentFormRefusal) as caught:
        B.boundary_rings([extent(SOLID)], source_image_digest="short")
    assert caught.value.refusal.code is RefusalCode.INVALID_PARAMETERS
    assert caught.value.refusal.missing == ["source_image_digest"]


def test_the_receipt_points_at_the_instance_and_not_merely_at_the_artifact():
    derived = B.boundary_rings([extent(DONUT, instance_id="inst_7")], source_image_digest=DIGEST)
    ref, = derived.provenance.input_refs
    assert ref.reference == "art_1#inst_7"
    assert ref.geometry_rev == 3
    assert derived.provenance.derived_from == ("art_1",)
    assert derived.provenance.revision == I.DERIVATION_REVISION


def test_a_mask_that_disagrees_with_the_raster_it_was_declared_on_is_refused_not_resampled():
    with pytest.raises(R.ExtentFormRefusal) as caught:
        I.source_extent("art_1", {"instance_id": "inst_1", "mask_rle": mask(SOLID)},
                        raster_shape=[10, 10])
    assert caught.value.refusal.code is RefusalCode.INVALID_PARAMETERS
    assert caught.value.refusal.detail["mask_raster"] == [5, 8]


def test_a_malformed_mask_reaches_no_form_at_all():
    with pytest.raises(R.ExtentFormRefusal) as caught:
        I.source_extent("art_1", {"instance_id": "inst_1", "mask_rle": MALFORMED})
    assert caught.value.refusal.code is RefusalCode.MISSING_EXTENT_INPUTS


def test_a_box_only_instance_is_not_traced_and_is_not_silently_absent_either():
    """GroundingDINO returns boxes. There is no boundary of a box worth tracing, and dropping the
    instance without saying so would make a partial answer look like a complete one."""
    payload = ExtentSetPayload(
        variant="extent_set", searched="every separable instance", instances=[
            ExtentInstance(instance_id="inst_1", mask_rle=mask(DONUT), geometry_rev=1),
            ExtentInstance(instance_id="inst_2", box={"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}),
        ])
    usable, skipped = I.source_extents("art_1", payload)
    assert [e.instance_id for e in usable] == ["inst_1"]
    assert [s.instance_id for s in skipped] == ["inst_2"]


def test_the_producible_form_this_lane_writes_is_the_one_the_registry_declares():
    definition = D.form(PerceptualForm.EXTENT_BOUNDARY_RINGS.value)
    derived = B.boundary_rings([extent(DONUT)], source_image_digest=DIGEST)
    assert derived.payload.variant == definition.payload_variant
    assert definition.producible and not definition.has_producer, (
        "the form is writable and no operation declares it yet — which is why this lane returns "
        "a payload and a receipt rather than an artifact naming an operation that never ran")
    assert derived.provenance.partition.value in definition.admissible_partitions
    assert derived.provenance.epistemic_basis.value in definition.admissible_bases


# ── extent.hole_set ──────────────────────────────────────────────────────────


def test_a_solid_shape_is_examined_for_voids_and_reports_none():
    """`holes: []` from a solid shape and `holes: []` from an extent nobody examined are the same
    empty list. `candidates_examined` is the whole difference."""
    derived = H.hole_set([extent(SOLID)], source_image_digest=DIGEST)
    assert derived.payload.holes == []
    assert derived.payload.candidates_examined == 1, "the outside was looked at and rejected"


def test_a_donut_has_one_enclosed_hole_and_it_names_the_extent_it_is_a_hole_of():
    derived = H.hole_set([extent(DONUT, instance_id="inst_4")], source_image_digest=DIGEST)
    hole, = derived.payload.holes
    assert hole.enclosed is True
    assert str(hole.outer) == "art_1#inst_4"
    assert derived.measurements["area_px"][hole.hole_id] == 9
    assert hole.area == round(9 / 25, 6)


def test_a_void_that_reaches_the_edge_of_the_picture_is_examined_and_is_not_a_hole():
    """A bay open at one side is a concavity. Whether a wider crop would close it is not knowable
    from this frame, so it is counted as examined and left out of `holes`."""
    bay = ["####", "#..#", "#..#", "#..#"]
    derived = H.hole_set([extent(bay)], source_image_digest=DIGEST)
    assert derived.payload.holes == []
    assert derived.payload.candidates_examined == 1
    assert derived.measurements["voids_open_to_the_frame"]["art_1#inst_1"] == 1


def test_this_producer_never_writes_enclosed_false_and_that_is_a_fact_about_the_producer():
    """The field is real and a person marking a hole by hand may need it. Nothing computed from
    one frame can honestly say "this is a void of that thing and I cannot see whether it closes",
    so this package does not."""
    for rows in (SOLID, DONUT, TWO_ISLANDS, NESTED, PINCHED, ["####", "#..#", "#..#", "#..#"]):
        derived = H.hole_set([extent(rows)], source_image_digest=DIGEST)
        assert all(hole.enclosed for hole in derived.payload.holes), rows


def test_a_hole_carries_the_very_ring_the_tracer_gave_it_and_not_a_second_tracing():
    """One curve, one record. Two tracings of one boundary is two things that could disagree."""
    holes = H.hole_set([extent(NESTED)], source_image_digest=DIGEST)
    rings = B.boundary_rings([extent(NESTED)], source_image_digest=DIGEST)
    hole, = holes.payload.holes
    hole_ring, = hole.rings
    inner = [r for r in rings.payload.boundaries[0].rings if r.winding is RingWinding.INNER]
    assert [hole_ring.ring_id] == [r.ring_id for r in inner]
    assert hole_ring.winding is RingWinding.INNER


def test_every_bounded_void_matches_exactly_one_inner_ring_across_every_control():
    """The one-to-one claim, checked on all seven controls rather than asserted once."""
    for rows in (SOLID, DONUT, TWO_ISLANDS, CORNER_TOUCH, EDGE_TOUCH, NESTED, PINCHED,
                 ["#####", "#.#.#", "#####"], ["######", "#.##.#", "#.##.#", "######"]):
        raster = R.raster_of(mask(rows), what="control")
        for piece in R.foreground_components(raster):
            traced = B.trace(piece)
            voids = H.voids_of(piece, traced)
            bounded = [v for v in voids if v.enclosed]
            inner = [r for r in traced if not r.is_outer]
            assert len(bounded) == len(inner), rows
            assert len({v.ring.ring_id for v in bounded}) == len(inner), rows


def test_a_hole_of_a_ring_is_the_whole_void_including_a_separate_shape_sitting_in_it():
    """Asked of the whole mask the island is foreground and the arch's opening comes back split.
    Asked of the arch, the opening is the opening — and it is what the arch's inner ring bounds."""
    derived = H.hole_set([extent(NESTED)], source_image_digest=DIGEST)
    hole, = derived.payload.holes
    assert derived.measurements["area_px"][hole.hole_id] == 9
    whole_mask_voids = R.complement_components(R.raster_of(mask(NESTED), what="n"))
    assert sum(v.area_px for v in whole_mask_voids if not v.touches_border) == 8


def test_two_voids_of_one_extent_get_two_ids_and_neither_is_the_other():
    two = ["######", "#.##.#", "#.##.#", "######"]
    derived = H.hole_set([extent(two)], source_image_digest=DIGEST)
    assert len(derived.payload.holes) == 2
    assert len({h.hole_id for h in derived.payload.holes}) == 2
    assert derived.payload.candidates_examined == 3, (
        "two holes, plus the outside. This shape fills the frame and the outside is therefore "
        "beyond it — examined and rejected like any other void, because `enclosed` already means "
        "'does not reach the frame' and a picture is a crop. Changed in PERCEPTUAL-FORMS-001H, "
        "which is when the count became consistent: every piece has exactly one exterior "
        "candidate plus its holes, whatever it touches")
    assert derived.measurements["voids_open_to_the_frame"]["art_1#inst_1"] == 1


def test_a_void_pinched_to_a_single_corner_is_one_hole_and_not_two():
    """The declared pairing, in the form. An 8-connected void is one void; under a 4-connected
    one this would be two holes of one pixel each, and the pinch would look like a wall."""
    derived = H.hole_set([extent(PINCHED)], source_image_digest=DIGEST)
    hole, = derived.payload.holes
    assert derived.measurements["area_px"][hole.hole_id] == 2


def test_the_same_mask_examined_twice_produces_the_same_holes():
    one = H.hole_set([extent(NESTED)], source_image_digest=DIGEST)
    two = H.hole_set([extent(NESTED)], source_image_digest=DIGEST)
    assert one.payload.model_dump() == two.payload.model_dump()


def test_two_holes_of_one_payload_never_share_an_id():
    """`ExtentHoleSetPayload` refuses a repeated `hole_id`, and content-addressing makes that
    structural: two holes with the same id would have to be the same pixels of the same raster,
    which would make them one hole."""
    two = ["######", "#.##.#", "#.##.#", "######"]
    derived = H.hole_set([extent(two)], source_image_digest=DIGEST)
    clashed = derived.payload.model_dump()
    clashed["holes"][1]["hole_id"] = clashed["holes"][0]["hole_id"]
    with pytest.raises(ValidationError):
        type(derived.payload).model_validate(clashed)


def test_the_hole_form_this_lane_writes_is_the_one_the_registry_declares():
    definition = D.form(PerceptualForm.EXTENT_HOLE_SET.value)
    derived = H.hole_set([extent(DONUT)], source_image_digest=DIGEST)
    assert derived.payload.variant == definition.payload_variant
    assert definition.absence.examined_field == "candidates_examined"
    assert derived.provenance.partition.value in definition.admissible_partitions


# ── extent.fragment_set ──────────────────────────────────────────────────────


def test_two_separated_islands_are_two_fragments_with_their_own_areas_and_centroids():
    derived = F.fragment_set([extent(TWO_ISLANDS)], source_image_digest=DIGEST)
    assert derived.payload.regions_examined == 2
    left, right = derived.payload.fragments
    assert [f.area for f in (left, right)] == [round(2 / 12, 6)] * 2
    assert derived.measurements["centroid"][left.fragment_id] == (0.125, round(1 / 3, 6))
    assert derived.measurements["area_px"][right.fragment_id] == 2


def test_pieces_that_touch_at_a_corner_stay_two_and_pieces_that_share_an_edge_are_one():
    corner = F.fragment_set([extent(CORNER_TOUCH)], source_image_digest=DIGEST)
    edge = F.fragment_set([extent(EDGE_TOUCH)], source_image_digest=DIGEST)
    assert len(corner.payload.fragments) == 2
    assert len(edge.payload.fragments) == 1


def test_a_fragment_set_asserts_no_unity_and_has_nowhere_to_put_one():
    derived = F.fragment_set([extent(TWO_ISLANDS)], source_image_digest=DIGEST)
    assert derived.payload.unity_asserted is False
    lying = derived.payload.model_dump()
    lying["unity_asserted"] = True
    with pytest.raises(ValidationError):
        type(derived.payload).model_validate(lying)
    grouped = derived.payload.model_dump()
    grouped["members"] = ["frag_1", "frag_2"]
    with pytest.raises(ValidationError):
        type(derived.payload).model_validate(grouped)


def test_the_name_of_an_extent_is_not_copied_onto_its_pieces():
    """Three separated patches of a tree, each labelled "the tree", is the unity claim wearing a
    different field. It belongs in `extent.fused_hypothesis` with grounds and a capped status."""
    named = I.source_extent("art_1", {
        "instance_id": "inst_1", "mask_rle": mask(TWO_ISLANDS), "geometry_rev": 1,
        "naming": {"text": "the tree", "source": "prompt", "epistemic_status": "interpretive",
                   "confidence": 0.8}})
    derived = F.fragment_set([named], source_image_digest=DIGEST)
    assert all(f.naming is None for f in derived.payload.fragments)


def test_a_hole_is_not_a_fragment():
    """The two forms are computed from different pixel sets by different functions: fragments come
    from the components of the mask, holes from the bounded components of a PIECE's complement.
    A donut has one fragment and one hole, and neither list holds the other's pixels."""
    frags = F.fragment_set([extent(DONUT)], source_image_digest=DIGEST)
    holes = H.hole_set([extent(DONUT)], source_image_digest=DIGEST)
    fragment, = frags.payload.fragments
    hole, = holes.payload.holes
    assert fragment.mask_rle != hole.mask_rle
    assert frags.measurements["area_px"][fragment.fragment_id] == 16
    assert holes.measurements["area_px"][hole.hole_id] == 9


def test_a_shape_inside_a_hole_is_its_own_fragment_and_the_hole_is_still_a_hole():
    frags = F.fragment_set([extent(NESTED)], source_image_digest=DIGEST)
    holes = H.hole_set([extent(NESTED)], source_image_digest=DIGEST)
    assert len(frags.payload.fragments) == 2
    assert len(holes.payload.holes) == 1
    island = frags.payload.fragments[1]
    assert frags.measurements["area_px"][island.fragment_id] == 1


def test_the_gap_between_two_pieces_is_integer_steps_and_a_corner_touch_is_one():
    pieces = R.foreground_components(R.raster_of(mask(CORNER_TOUCH), what="c"))
    touch, = F.separations(pieces)
    assert touch["gap_px"] == 1 and touch["touching"] is True
    apart = F.separations(R.foreground_components(R.raster_of(mask(TWO_ISLANDS), what="t")))
    assert apart[0]["gap_px"] == 3 and apart[0]["touching"] is False


def test_separations_come_back_closest_first_and_can_be_declined():
    rows = ["#.#....#", "........", "........", "........"]
    derived = F.fragment_set([extent(rows)], source_image_digest=DIGEST)
    gaps = [row["gap_px"] for row in derived.measurements["separations"]]
    assert gaps == sorted(gaps) and gaps == [2, 5, 7]
    declined = F.fragment_set([extent(rows)], source_image_digest=DIGEST,
                              measure_separation=False)
    assert declined.measurements["separations"] is None


def test_a_fragment_id_is_the_piece_and_not_its_position():
    """Adding an island in the corner must not renumber the pieces on the other side."""
    before = F.fragment_set([extent(["...#", "....", "....", "...#"])],
                            source_image_digest=DIGEST)
    after = F.fragment_set([extent(["#..#", "....", "....", "...#"])],
                           source_image_digest=DIGEST)
    assert {f.fragment_id for f in before.payload.fragments} < \
           {f.fragment_id for f in after.payload.fragments}


def test_one_island_in_two_overlapping_instances_is_one_fragment_and_two_examinations():
    twin = [extent(TWO_ISLANDS), extent(TWO_ISLANDS, instance_id="inst_2")]
    derived = F.fragment_set(twin, source_image_digest=DIGEST)
    assert derived.payload.regions_examined == 4
    assert len(derived.payload.fragments) == 2
    found = derived.measurements["found_in"][derived.payload.fragments[0].fragment_id]
    assert found == ["art_1#inst_1", "art_1#inst_2"], "the collapse is visible, not silent"


def test_a_fragment_set_over_two_rasters_is_refused_rather_than_reported_as_one_image():
    small = extent(["#.", ".."])
    large = extent(["#...", "....", "....", "...."], instance_id="inst_2")
    with pytest.raises(R.ExtentFormRefusal) as caught:
        F.fragment_set([small, large], source_image_digest=DIGEST)
    assert caught.value.refusal.code is RefusalCode.INVALID_PARAMETERS
    assert caught.value.refusal.remedy == "derive one fragment set per raster"


def test_boundaries_and_holes_do_not_need_one_raster_because_they_carry_their_own():
    """The refusal above is about the ONE form with nowhere to name a second raster. Making the
    other two refuse as well would be a rule applied where it buys nothing."""
    small = extent(["##", "##"])
    large = extent(["####", "#..#", "#..#", "####"], instance_id="inst_2")
    rings = B.boundary_rings([small, large], source_image_digest=DIGEST)
    holes = H.hole_set([small, large], source_image_digest=DIGEST)
    assert [b.raster_shape for b in rings.payload.boundaries] == [[2, 2], [4, 4]]
    assert holes.payload.holes[0].mask_rle["size"] == [4, 4]


def test_the_same_mask_split_twice_produces_the_same_fragments():
    one = F.fragment_set([extent(NESTED)], source_image_digest=DIGEST)
    two = F.fragment_set([extent(NESTED)], source_image_digest=DIGEST)
    assert one.payload.model_dump() == two.payload.model_dump()
    assert one.measurements == two.measurements


def test_the_fragment_form_this_lane_writes_is_the_one_the_registry_declares():
    definition = D.form(PerceptualForm.EXTENT_FRAGMENT_SET.value)
    derived = F.fragment_set([extent(TWO_ISLANDS)], source_image_digest=DIGEST)
    assert derived.payload.variant == definition.payload_variant
    assert definition.absence.examined_field == "regions_examined"
    assert "fragment_set_asserts_no_unity" in definition.test_obligations


# ── the three forms together ─────────────────────────────────────────────────


ALL_CONTROLS = {
    "solid rectangle": SOLID,
    "donut": DONUT,
    "two separated islands": TWO_ISLANDS,
    "islands touching at a corner": CORNER_TOUCH,
    "islands sharing an edge": EDGE_TOUCH,
    "a shape nested in a hole": NESTED,
    "a void pinched to one corner": PINCHED,
    "a boundary pinched to one corner": ["###", "#.#", "##."],
    "an empty mask": EMPTY,
    "a mask filling the frame": ["####", "####", "####", "####"],
    "a one-pixel mask": ["....", "..#.", "....", "...."],
    "a comb": ["#.#.#.#.", "#.#.#.#.", "########", "........"],
}


def derive_all(rows):
    """All three forms of one mask, keyed by the payload variant the registry names them by."""
    source = extent(rows)
    return {
        "extent_boundary": B.boundary_rings([source], source_image_digest=DIGEST),
        "extent_hole_set": H.hole_set([source], source_image_digest=DIGEST),
        "extent_fragment_set": F.fragment_set([source], source_image_digest=DIGEST),
    }


@pytest.mark.parametrize("name", sorted(ALL_CONTROLS))
def test_every_control_produces_a_payload_the_form_registry_recognises(name):
    """Validated through the registry's own table rather than through the class the producer
    happened to build. A payload that only validates against the model it was constructed from
    proves nothing about the contract."""
    for variant, derived in derive_all(ALL_CONTROLS[name]).items():
        model = S.FORM_PAYLOAD_MODELS[variant]
        assert isinstance(derived.payload, model)
        reloaded = model.model_validate(derived.payload.model_dump(mode="json"))
        assert reloaded.model_dump() == derived.payload.model_dump()
        assert D.form(derived.form.value).payload_variant == variant


@pytest.mark.parametrize("name", sorted(ALL_CONTROLS))
def test_every_control_derives_to_the_same_bytes_twice(name):
    first = derive_all(ALL_CONTROLS[name])
    second = derive_all(ALL_CONTROLS[name])
    for variant in first:
        assert first[variant].payload.model_dump() == second[variant].payload.model_dump(), variant
        assert first[variant].measurements == second[variant].measurements, variant


@pytest.mark.parametrize("name", sorted(ALL_CONTROLS))
def test_an_outer_ring_encloses_its_piece_plus_every_hole_in_it(name):
    """The identity that ties the three forms together, in whole pixels.

    A ring around a piece bounds the piece AND the voids inside it, so the ring's lattice area is
    the piece's pixel count plus its holes'. If the tracer dropped a ring, or the complement
    invented a hole, or a hole belonged to the wrong piece, this arithmetic breaks — which is why
    it is asserted rather than the three forms being checked separately and hoped to agree.
    """
    raster = R.raster_of(mask(ALL_CONTROLS[name]), what=name)
    for piece in R.foreground_components(raster):
        rings = B.trace(piece)
        outer = [r for r in rings if r.is_outer]
        assert len(outer) == 1, "one connected piece has exactly one outer ring"
        holes = [v for v in H.voids_of(piece, rings) if v.enclosed]
        assert outer[0].encloses_px == piece.area_px + sum(v.pixels.area_px for v in holes)


@pytest.mark.parametrize("name", sorted(ALL_CONTROLS))
def test_no_pixel_is_both_a_piece_and_a_void_of_that_piece(name):
    raster = R.raster_of(mask(ALL_CONTROLS[name]), what=name)
    for piece in R.foreground_components(raster):
        for void in H.voids_of(piece, B.trace(piece)):
            assert not (piece.members & void.pixels.members)


def test_the_committed_payload_for_each_form_and_this_producer_agree_on_the_shape():
    """Lane A froze one hand-authored payload per form. This producer's output has to validate
    through the same model, and that model has to accept the frozen one — two directions, because
    a producer agreeing with itself is not agreement."""
    import json
    from backend.services.perception_lab.contracts import CONTRACTS_DIR
    manifest = json.loads((CONTRACTS_DIR / "fixtures" / "perception-lab" / "manifest.json")
                          .read_text(encoding="utf-8"))
    by_form = manifest["form_payloads"]["by_form"]
    for key in ("extent.boundary_rings", "extent.hole_set", "extent.fragment_set"):
        entry = by_form[key]
        committed = json.loads((CONTRACTS_DIR / "fixtures" / "perception-lab" / entry["file"])
                               .read_text(encoding="utf-8"))
        model = S.FORM_PAYLOAD_MODELS[entry["variant"]]
        assert model.model_validate(committed).variant == entry["variant"]
        derived = derive_all(NESTED)[entry["variant"]]
        assert set(derived.payload.model_dump()) == set(committed)


def test_a_larger_mask_derives_deterministically_and_its_rings_still_rasterize_back():
    """Twelve controls are twelve shapes somebody chose. This is a 24x32 mask nobody chose —
    generated from a fixed arithmetic rule, so it is the same mask every run, with pieces and
    voids and pinches nobody arranged."""
    rows = ["".join("#" if (r * r + c * c * 3 + r * c) % 7 < 3 else "." for c in range(32))
            for r in range(24)]
    source = extent(rows)
    first = B.boundary_rings([source], source_image_digest=DIGEST)
    second = B.boundary_rings([source], source_image_digest=DIGEST)
    assert first.payload.model_dump() == second.payload.model_dump()
    assert rasterize(first.payload)[0] == source.raster.rle

    pieces = R.foreground_components(source.raster)
    assert len(pieces) > 5, "the precondition: this mask is genuinely fragmented"
    counted = sum(M.perimeter_px(p) for p in pieces)
    assert counted == sum(r.cracks for p in pieces for r in B.trace(p))
    frags = F.fragment_set([source], source_image_digest=DIGEST, measure_separation=False)
    assert len(frags.payload.fragments) == len(pieces)
    assert sum(frags.measurements["area_px"].values()) == source.raster.area_px


def test_this_package_reaches_no_facade_no_store_and_no_route():
    """The lane's boundary, checked in the source. `extent.py` is not imported, so it cannot be
    changed by being depended on; nothing here can write, and nothing here can be routed to."""
    import pathlib
    package = pathlib.Path(R.__file__).parent
    banned = ("perception_lab.extent", "perception_lab.orchestrator", "perception_lab.session",
              "perception_lab.store", "perception_lab.mongo_store", "perception_lab.live",
              "perception_lab.adapters", "backend.routers", "backend.database", "fastapi")
    for path in sorted(package.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for name in banned:
            assert f"import {name}" not in source and f"from {name}" not in source, \
                f"{path.name} reaches {name}"


# ── the window agrees with the whole raster ──────────────────────────────────


@pytest.mark.parametrize("name", sorted(ALL_CONTROLS))
def test_the_windowed_voids_agree_with_the_whole_raster_fill(name):
    """PERCEPTUAL-FORMS-001H. `bounded_voids` computes in a window and `complement_of` computes
    over the whole raster, and they must find the same holes.

    THE COMPARISON IS ON THE ENCLOSED ONES. The exterior differs by construction and deliberately:
    the window's ring lies partly outside the picture, so a shape that fills the frame has an
    outside there and had none before. What must not differ is which voids are enclosed, and how
    many pixels each one holds.
    """
    raster = R.raster_of(mask(ALL_CONTROLS[name]), what=name)
    for piece in R.foreground_components(raster):
        windowed = sorted(v.pixels for v, escapes in R.bounded_voids(piece) if not escapes)
        whole = sorted(v.pixels for v in R.complement_of(piece) if not v.touches_border)
        assert windowed == whole, name


def test_the_window_finds_an_outside_for_a_shape_that_fills_the_frame():
    """A picture is a crop. The space beyond the frame is a void that was examined and rejected,
    which is what makes `candidates_examined` mean the same thing wherever the shape sits."""
    piece = R.foreground_components(R.raster_of(mask(["##", "##"]), what="full"))[0]
    voids = R.bounded_voids(piece)
    assert [escapes for _, escapes in voids] == [True]
    assert voids[0][0].pixels == (), "the outside of a full frame holds no pixel of this picture"
    assert R.complement_of(piece) == (), "the whole-raster fill sees no outside at all"
