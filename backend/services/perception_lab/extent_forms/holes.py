"""
PERCEPTUAL-FORMS-001B — `extent.hole_set`: the voids inside an extent, and the ones that are not.

A HOLE IS A VOID OF SOMETHING. That is the form's rule and it is also the algorithm: a hole is not
found by looking at the mask, it is found by looking at ONE PIECE of the mask and asking what its
complement encloses. Ask the whole mask instead and a separate shape sitting inside an arch turns
the arch's opening into two voids, or none, depending where it sits — the pixels of that shape are
foreground, so globally they are not void at all. Asked of the arch alone they are, because they
are not the arch. See `raster.complement_components(of=…)`.

ENCLOSED IS DECIDED BY THE FRAME, AND THE FRAME IS WHERE LOOKING STOPPED. A void that reaches the
edge of the image is connected to the outside within this picture, and whether a wider crop would
close it is not knowable from here. So it is not a hole: it is examined, counted in
`candidates_examined`, and left out of `holes`. A bay open at one side is a concavity and a
courtyard is not a window.

THIS PRODUCER THEREFORE NEVER WRITES `enclosed: false`, and that is a fact about it rather than
about the field. `ExtentHole.enclosed` exists because a person marking a hole by hand can mean
"this is a void of that thing, and I cannot see whether it closes behind the pillar" — a claim
this package has no way to make and no business making. A test holds the producer to the narrower
half.

HOLES AND INNER RINGS COME OUT ONE-TO-ONE. Every bounded component of a piece's complement is
bounded by exactly one of that piece's inner rings, and this module hands each hole the ring
`boundary.trace` gave it — the same `ring_id`, not a second tracing of the same curve. Two records
of one curve that could disagree is the failure mode; there is only one curve.

PURE. No database, no network, no model, no clock, no image.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend.schemas.perception_lab import ExtentHole, ExtentHoleSetPayload, PerceptualForm
from backend.services.perception_lab.extent_forms import measure as M
from backend.services.perception_lab.extent_forms.boundary import (TracedRing, ring_model, trace)
from backend.services.perception_lab.extent_forms.inputs import (Derived, SourceExtent,
                                                                 provenance_for)
from backend.services.perception_lab.extent_forms.raster import (PixelSet, complement_of,
                                                                 foreground_components)


@dataclass(frozen=True)
class Void:
    """One component of a piece's complement, and whether this picture closes it."""
    pixels: PixelSet
    enclosed: bool
    ring: Optional[TracedRing] = None

    @property
    def hole_id(self) -> str:
        return "hole_" + self.pixels.digest


def _anchor_of(void: PixelSet) -> Tuple[int, int]:
    """The lattice corner every void's own boundary is guaranteed to turn at.

    `pixels` is sorted row-major, so `pixels[0]` is the void's topmost pixel and, within that row,
    its leftmost. Call it `(r, c)`. The pixel above it must belong to the enclosing piece — it is
    8-adjacent to a void pixel, so if it were void it would be in this same void — and the pixel
    to its left must too, or `(r, c)` was not the leftmost of its row. So the piece has a crack
    arriving at corner `(r, c)` from the right and no crack leaving it to the left: the boundary
    TURNS there, which means the corner survives collinear simplification and appears in exactly
    one inner ring. Two voids of one piece are at least two steps apart under the declared
    pairing, so no other ring can hold the same corner. That is what makes the match exact rather
    than a nearest-ring guess.
    """
    return divmod(void.pixels[0], void.w)


def voids_of(piece: PixelSet, rings: Sequence[TracedRing]) -> Tuple[Void, ...]:
    """Every component of one piece's complement, classified, in row-major order."""
    inner = [r for r in rings if not r.is_outer]
    out: List[Void] = []
    for component in complement_of(piece):
        if component.touches_border:
            out.append(Void(pixels=component, enclosed=False))
            continue
        anchor = _anchor_of(component)
        matched = [r for r in inner if anchor in r.lattice]
        if len(matched) != 1:
            raise AssertionError(
                f"a bounded void anchored at {anchor} matched {len(matched)} inner rings. Every "
                f"bounded void is bounded by exactly one, so a count that is not one means the "
                f"tracer and the complement disagree about what encloses what.")
        out.append(Void(pixels=component, enclosed=True, ring=matched[0]))
    return tuple(out)


def hole_model(void: Void, *, h: int, w: int, outer) -> ExtentHole:
    return ExtentHole(
        hole_id=void.hole_id, outer=outer, enclosed=void.enclosed,
        mask_rle=void.pixels.rle,
        rings=[ring_model(void.ring, h=h, w=w)] if void.ring is not None else [],
        area=M.normalized_area(void.pixels))


def hole_set(extents: Sequence[SourceExtent], *, source_image_digest: str) -> Derived:
    """`extent.hole_set` for a set of masked extents, with its receipt.

    `candidates_examined` COUNTS EVERY VOID THAT WAS LOOKED AT, the open ones included. That is
    what the field is for: `holes: []` from an extent that is solid and `holes: []` from an extent
    nobody examined are the same empty list, and only the first is a measurement. An extent with
    one opening and an outside reports two candidates and one hole, and the difference between
    those two numbers is exactly the voids this frame could not close.

    THE HOLE NAMES THE INSTANCE, NOT THE PIECE. `InstanceRef` reaches artifact and instance and
    stops there, so when one instance's mask has several separate pieces every hole of every piece
    names the same instance. That is the contract's depth, not a shortcut taken here; the piece a
    hole belongs to is recoverable from its ring, which is why the ring travels with it.
    """
    holes: List[ExtentHole] = []
    examined = 0
    area_px: Dict[str, int] = {}
    centroid: Dict[str, Any] = {}
    perimeter: Dict[str, int] = {}
    per_instance: Dict[str, int] = {}
    open_voids: Dict[str, int] = {}
    for source in extents:
        h, w = source.raster.shape
        looked = opened = 0
        for piece in foreground_components(source.raster):
            for void in voids_of(piece, trace(piece)):
                looked += 1
                if not void.enclosed:
                    opened += 1
                    continue
                holes.append(hole_model(void, h=h, w=w, outer=source.ref))
                area_px[void.hole_id] = void.pixels.area_px
                centroid[void.hole_id] = M.centroid(void.pixels)
                perimeter[void.hole_id] = M.perimeter_px(void.pixels)
        examined += looked
        per_instance[source.key] = looked
        open_voids[source.key] = opened
    payload = ExtentHoleSetPayload(variant="extent_hole_set", candidates_examined=examined,
                                   holes=holes)
    return Derived(
        form=PerceptualForm.EXTENT_HOLE_SET, payload=payload,
        provenance=provenance_for(extents, source_image_digest=source_image_digest),
        measurements={"area_px": area_px, "centroid": centroid, "perimeter_px": perimeter,
                      "voids_examined": per_instance, "voids_open_to_the_frame": open_voids})


__all__ = ["Void", "hole_model", "hole_set", "voids_of"]
