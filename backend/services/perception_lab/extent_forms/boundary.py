"""
PERCEPTUAL-FORMS-001B — `extent.boundary_rings`, traced exactly, along the cracks between pixels.

WHAT IS TRACED. Not the pixel CENTRES — the cracks: the unit edges of the lattice that separate a
pixel of the piece from a pixel that is not. A ring made of cracks is the exact border of the
pixel set, so rasterizing it back reproduces the mask it came from, byte for byte. A ring made of
centres is inset by half a pixel on every side, which is invisible on a cathedral and swallows a
window-bar whole; `mask_geometry.bits_to_polygons` compensates for that by contouring a 4x
upsampled copy, and it needs cv2 to do it at all. This needs nothing, approximates nothing, and
returns the same rings on a machine with no cv2 installed.

THE INSIDE IS ALWAYS ON THE RIGHT. Every crack is emitted in the direction that keeps the piece
on the right-hand side of travel, which is what makes the rest of the file arithmetic rather than
heuristics:

  · The ring CLASSIFIES ITSELF. A closed walk with the inside on the right has positive lattice
    area when it encloses the piece and negative area when it encloses a void. Signed area of a
    rectilinear lattice polygon is an INTEGER, so `outer` versus `inner` is decided with no
    tolerance and no ring that flips class on a rounding error.
  · THE PINCH RESOLVES ITSELF. Where a void narrows to a single lattice corner — two void pixels
    meeting diagonally inside one piece — that corner has two ways out, and the walk takes the
    sharpest available RIGHT turn. Hugging the inside is what keeps a 4-connected piece's boundary
    one curve instead of two, and it is the same choice `raster.py` makes when it pairs the
    connectivities. The two agree because they are the same rule seen from two sides.

WINDING IS DECLARED, NOT INFERRED — the contract's rule, and this file is the reason it can be
obeyed. The producer knows which side is inside because it put it there; a reader who tried to
recover that from point order would have to guess a handedness convention, and half the renderers
in the world guess the other one.

`length` IS LEFT NULL, DELIBERATELY. `BoundaryRing.length` has no unit beside it. A normalized
length would mix two different scales on any raster that is not square — a step of one pixel is
`1/w` across and `1/h` down — and a pixel length in a field a reader takes for normalized is
worse than an absent one. The exact integer perimeter is returned in `measurements`, where it is
labelled.

PURE. No database, no network, no model, no clock, no image, no cv2.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from backend.schemas.perception_lab import (BoundaryRing, ExtentBoundaryPayload, InstanceBoundary,
                                            PerceptualForm, RingWinding)
from backend.services.perception_lab.extent_forms import measure as M
from backend.services.perception_lab.extent_forms.inputs import (Derived, SourceExtent,
                                                                 provenance_for)
from backend.services.perception_lab.extent_forms.raster import (DIGEST_CHARS, PixelSet,
                                                                 foreground_components)

Corner = Tuple[int, int]      # (row, col) on the lattice of pixel corners, 0..h and 0..w
Crack = Tuple[Corner, Corner]

#: Preference order at a corner with more than one way out, as rotations of the incoming
#: direction: sharpest right, then straight on, then left, then back the way we came. See the
#: module docstring — this is the pinch rule, and it is why it is a tuple rather than an `if`.
_TURNS = (
    lambda d: (d[1], -d[0]),      # right
    lambda d: d,                  # straight
    lambda d: (-d[1], d[0]),      # left
    lambda d: (-d[0], -d[1]),     # reverse
)


@dataclass(frozen=True)
class TracedRing:
    """One closed crack curve, on the integer lattice, before anything is normalized."""
    ring_id: str
    winding: RingWinding
    lattice: Tuple[Corner, ...]
    encloses_px: int
    cracks: int

    @property
    def is_outer(self) -> bool:
        return self.winding is RingWinding.OUTER


def _cracks_of(piece: PixelSet) -> Dict[Corner, List[Corner]]:
    """Every unit edge with the piece on one side, directed so the piece is on the RIGHT.

    A crack exists only where exactly one of the two pixels it separates is in the piece, so the
    directed set has no duplicates: the top edge of a pixel and the bottom edge of the pixel above
    it are the same crack in opposite directions, and both are emitted only when neither pixel is
    in the piece — which cannot happen, because then there is no crack.
    """
    out: Dict[Corner, List[Corner]] = {}
    w, h, members = piece.w, piece.h, piece.members

    def outside(r: int, c: int) -> bool:
        return not (0 <= r < h and 0 <= c < w) or (r * w + c) not in members

    def add(tail: Corner, head: Corner) -> None:
        out.setdefault(tail, []).append(head)

    for p in piece.pixels:
        r, c = divmod(p, w)
        if outside(r - 1, c):
            add((r, c), (r, c + 1))
        if outside(r, c + 1):
            add((r, c + 1), (r + 1, c + 1))
        if outside(r + 1, c):
            add((r + 1, c + 1), (r + 1, c))
        if outside(r, c - 1):
            add((r + 1, c), (r, c))
    return out


def _simplify(path: Sequence[Corner]) -> Tuple[Corner, ...]:
    """Drop the corners that are not corners.

    LOSSLESS AND CYCLIC. Consecutive unit steps in the same direction describe one straight edge,
    and collapsing them changes no pixel — the ring still rasterizes to the same mask. It is done
    cyclically so the seam where the walk started is not left as a false corner, which would make
    two runs that began at different cracks produce two different-looking rings of the same shape.

    A PINCH SURVIVES IT. A corner visited twice appears twice in `path`, and each visit is judged
    on its own incoming and outgoing step, so the two visits are kept apart rather than merged.
    """
    n = len(path)
    if n < 3:
        return tuple(path)
    kept: List[Corner] = []
    for i in range(n):
        prev, cur, nxt = path[i - 1], path[i], path[(i + 1) % n]
        before = (cur[0] - prev[0], cur[1] - prev[1])
        after = (nxt[0] - cur[0], nxt[1] - cur[1])
        if before != after:
            kept.append(cur)
    return tuple(kept)


def _ring_id(lattice: Sequence[Corner], winding: RingWinding, h: int, w: int) -> str:
    body = (f"{h}x{w}|{winding.value}|"
            + ";".join(f"{r},{c}" for r, c in lattice))
    return "ring_" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:DIGEST_CHARS]


def trace(piece: PixelSet) -> Tuple[TracedRing, ...]:
    """Every closed ring of one connected piece: exactly one `outer`, then one `inner` per void.

    DETERMINISTIC IN THREE PLACES, and all three matter. The walk starts at the lexicographically
    smallest unused crack, so the ring ORDER is a fact about the mask rather than about dictionary
    iteration. Each walk follows the right-hug rule, so the POINTS are a fact about the mask. And
    the winding comes from an integer sign, so the CLASS is a fact about the mask. Two runs on two
    machines produce identical tuples.
    """
    graph = _cracks_of(piece)
    remaining: Set[Crack] = {(tail, head) for tail, heads in graph.items() for head in heads}
    rings: List[TracedRing] = []
    while remaining:
        start = min(remaining)
        path: List[Corner] = []
        cur = start
        while True:
            remaining.discard(cur)
            path.append(cur[0])
            head = cur[1]
            direction = (head[0] - cur[0][0], head[1] - cur[0][1])
            nxt: Optional[Crack] = None
            for turn in _TURNS:
                dr, dc = turn(direction)
                candidate = (head, (head[0] + dr, head[1] + dc))
                if candidate in remaining:
                    nxt = candidate
                    break
            if nxt is None:
                # The only way out of a boundary walk is back where it began: every corner has as
                # many cracks leaving it as arriving, so a walk that cannot continue has closed.
                if head != path[0]:
                    raise AssertionError(
                        f"a boundary walk stopped at {head} having started at {path[0]}. Every "
                        f"crack set closes; a walk that does not means the crack set was built "
                        f"wrong, and a half-open ring is not a boundary.")
                break
            cur = nxt
        area = M.lattice_area(path)
        winding = RingWinding.OUTER if area > 0 else RingWinding.INNER
        lattice = _simplify(path)
        rings.append(TracedRing(ring_id=_ring_id(lattice, winding, piece.h, piece.w),
                                winding=winding, lattice=lattice, encloses_px=abs(area),
                                cracks=len(path)))
    return tuple(rings)


def ring_model(ring: TracedRing, *, h: int, w: int) -> BoundaryRing:
    """A traced ring as the contract's record. `length` is null — see the module docstring."""
    return BoundaryRing(
        ring_id=ring.ring_id, winding=ring.winding, closed=True, length=None,
        points=[[M.round6(c / w), M.round6(r / h)] for r, c in ring.lattice])


def instance_boundary(extent: SourceExtent) -> Tuple[Optional[InstanceBoundary],
                                                     Tuple[TracedRing, ...]]:
    """One extent's every ring, or `None` when its mask encloses nothing.

    AN EMPTY MASK HAS NO BOUNDARY, and that is the form's declared absence rather than a failure.
    `InstanceBoundary` requires at least one ring and at least one `outer` ring, because a record
    holding only holes describes voids in nothing; so an extent with no pixels produces no record
    at all and contributes `0` to `rings_traced`, which is the honest count of what was found by
    looking.
    """
    traced: List[TracedRing] = []
    for piece in foreground_components(extent.raster):
        traced.extend(trace(piece))
    if not traced:
        return None, ()
    h, w = extent.raster.shape
    return InstanceBoundary(of=extent.ref, raster_shape=[h, w],
                            rings=[ring_model(r, h=h, w=w) for r in traced]), tuple(traced)


def boundary_rings(extents: Sequence[SourceExtent], *, source_image_digest: str) -> Derived:
    """`extent.boundary_rings` for a set of masked extents, with its receipt.

    `rings_traced` IS THE COUNT OF WHAT LOOKING FOUND, not a summary that may drift from the list
    beside it — `ExtentBoundaryPayload` refuses the two disagreeing. It counts rings across every
    extent examined, INCLUDING the extents whose masks turned out to be empty and contributed
    none, which is how "traced and enclosed nothing" stays distinguishable from "never traced".
    """
    boundaries: List[InstanceBoundary] = []
    perimeters: Dict[str, int] = {}
    encloses: Dict[str, int] = {}
    traced_total = 0
    for extent in extents:
        record, traced = instance_boundary(extent)
        traced_total += len(traced)
        for ring in traced:
            perimeters[ring.ring_id] = ring.cracks
            encloses[ring.ring_id] = ring.encloses_px
        if record is not None:
            boundaries.append(record)
    payload = ExtentBoundaryPayload(variant="extent_boundary", rings_traced=traced_total,
                                    boundaries=boundaries)
    return Derived(
        form=PerceptualForm.EXTENT_BOUNDARY_RINGS, payload=payload,
        provenance=provenance_for(extents, source_image_digest=source_image_digest),
        measurements={"perimeter_px": perimeters, "encloses_px": encloses})


__all__ = ["TracedRing", "boundary_rings", "instance_boundary", "ring_model", "trace"]
