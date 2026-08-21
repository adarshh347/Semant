"""
PERCEPTUAL-FORMS-001B — the exact measurements the Extent forms are built out of.

EVERY NUMBER HERE IS A COUNT OR A RATIO OF COUNTS. Areas are pixel counts, perimeters are crack
counts, gaps are integer pixel steps. Nothing is estimated, nothing is sampled, nothing is
smoothed, and the only floats are the last step — a count divided by the raster it was counted on
— rounded at the one precision the rest of the tree rounds normalized geometry to.

WHY THE INTEGERS ARE KEPT. `perimeter_px` could have been reported as a normalized length and
`gap` as a normalized distance, and both would then be uncomparable between a 8x8 fixture and a
1600x1200 photograph in a way nobody could see. The integer is the measurement; a caller that
wants it as a fraction of the frame can divide, and will know it did.

WHAT IS NOT HERE, AND WHY IT IS NOT AN OVERSIGHT. `ExtentFragment` has five fields — id, mask,
box, area, naming — and `extra="forbid"`. So a centroid and a separation have NOWHERE to go in
the payload, and inventing a field for them would be inventing a second artifact model. They are
measurements ABOUT a form rather than parts of it, they are returned beside the payload, and a
later lane that needs them on an artifact puts them in `ArtifactMeasurement` where measurements
live.

PURE. No database, no network, no model, no clock, no image.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from backend.services.perception_lab.extent_forms.raster import PixelSet

#: The precision `mask_geometry` already rounds normalized geometry to. A second precision here
#: would make a box derived by this package differ in its sixth decimal from the same box derived
#: by `rle_bbox_norm`, and a difference nobody meant is a difference somebody debugs.
PRECISION = 6

_ORTHOGONAL = ((-1, 0), (1, 0), (0, -1), (0, 1))
_NEIGHBOURS_8 = _ORTHOGONAL + ((-1, -1), (-1, 1), (1, -1), (1, 1))


def round6(value: float) -> float:
    return round(float(value), PRECISION)


# ── size and place ───────────────────────────────────────────────────────────


def normalized_area(piece: PixelSet) -> float:
    """Pixels, as a fraction of the frame. `0.0` for an empty piece, which is a real answer."""
    frame = piece.h * piece.w
    return round6(piece.area_px / frame) if frame else 0.0


def bbox(piece: PixelSet) -> Optional[Dict[str, float]]:
    """The tight normalized box, or None when there is nothing to bound.

    None RATHER THAN A ZERO BOX. `Box` requires `w > 0` and `h > 0` because a box with no width
    is not a projection of anything, and returning `{"w": 0}` here would only move the refusal to
    whoever tried to build one.
    """
    if not piece.pixels:
        return None
    w = piece.w
    rows = [p // w for p in piece.pixels]
    cols = [p % w for p in piece.pixels]
    r0, r1, c0, c1 = min(rows), max(rows), min(cols), max(cols)
    return {
        "x": round6(c0 / piece.w), "y": round6(r0 / piece.h),
        "w": round6((c1 - c0 + 1) / piece.w), "h": round6((r1 - r0 + 1) / piece.h),
    }


def centroid(piece: PixelSet) -> Optional[Tuple[float, float]]:
    """The mean of the pixel CENTRES, normalized — `(x, y)`, or None when the piece is empty.

    CENTRES, NOT CORNERS. A single pixel at (0, 0) on an 8x8 raster has its centre at
    (0.0625, 0.0625) and its top-left corner at (0.0, 0.0), and only the first of those is
    somewhere the piece actually is. The difference is half a pixel and it is the difference
    between a centroid that lands inside a one-pixel shape and one that lands outside it.
    """
    if not piece.pixels:
        return None
    w = piece.w
    n = len(piece.pixels)
    sum_c = sum(p % w for p in piece.pixels)
    sum_r = sum(p // w for p in piece.pixels)
    return (round6((sum_c + 0.5 * n) / (n * piece.w)),
            round6((sum_r + 0.5 * n) / (n * piece.h)))


def perimeter_px(piece: PixelSet) -> int:
    """How many unit edges separate this piece from everything that is not it.

    COUNTED, NOT TRACED. This walks the pixels and counts the four-sides-that-face-out; the ring
    tracer in `boundary.py` arrives at the same number by following those edges into closed
    curves. They agree by construction, and a test holds them to it — which is how a tracer that
    quietly dropped a ring would be caught by arithmetic rather than by eye.

    THE RASTER EDGE COUNTS. A piece running off the side of the image has a perimeter there: the
    frame is where the measurement stops, not where the shape does.
    """
    total = 0
    w, h = piece.w, piece.h
    members = piece.members
    for p in piece.pixels:
        r, c = divmod(p, w)
        for dr, dc in _ORTHOGONAL:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < h and 0 <= nc < w) or (nr * w + nc) not in members:
                total += 1
    return total


# ── how far apart two pieces are ─────────────────────────────────────────────


def surface(piece: PixelSet) -> Tuple[int, ...]:
    """The pixels of a piece that something else could be next to.

    A pixel whose eight neighbours are all inside the piece cannot be the closest pixel to
    anything outside it — the neighbour in the direction of the other piece is strictly closer and
    is also inside — so the minimum distance between two disjoint pieces is always achieved here.
    Restricting to the surface is exact, not an approximation, and it is what keeps `gap_px` from
    being quadratic in the AREA of two large masks.
    """
    out: List[int] = []
    w, h = piece.w, piece.h
    members = piece.members
    for p in piece.pixels:
        r, c = divmod(p, w)
        if r in (0, h - 1) or c in (0, w - 1):
            out.append(p)
            continue
        for dr, dc in _NEIGHBOURS_8:
            if ((r + dr) * w + (c + dc)) not in members:
                out.append(p)
                break
    return tuple(out)


def gap_px(a: PixelSet, b: PixelSet) -> Optional[int]:
    """The exact Chebyshev distance between two pieces, in pixels. None on a raster mismatch.

    CHEBYSHEV, AND THEREFORE AN INTEGER. `1` means the two pieces touch — edge or corner — and `2`
    means exactly one pixel of clear space lies between them at the closest point. A Euclidean
    distance would answer `1.4142135` for a corner touch and force every caller to decide what
    counted as adjacent; this answers with the number of steps, which is the question "are they
    separate, and by how much" actually asks.

    `0` IS NOT REACHABLE BETWEEN TWO PIECES and is not a special case: two pieces sharing a pixel
    would be one piece. It is returned only when a caller asks for the gap between a piece and
    itself, which is a real answer to a strange question.

    NONE ON A RASTER MISMATCH, NEVER A RESAMPLE — the rule `extent_metrics` already holds every
    comparison to. A distance between two different rasters is a number about neither.
    """
    if a.shape != b.shape:
        return None
    if not a.pixels or not b.pixels:
        return None
    left, right = surface(a), surface(b)
    w = a.w
    best: Optional[int] = None
    for p in left:
        pr, pc = divmod(p, w)
        for q in right:
            qr, qc = divmod(q, w)
            d = max(abs(pr - qr), abs(pc - qc))
            if best is None or d < best:
                if d == 0:
                    return 0
                best = d
    return best


# ── lattice polygons ─────────────────────────────────────────────────────────


def lattice_area(points: Sequence[Tuple[int, int]]) -> int:
    """The signed area of a closed rectilinear lattice polygon, in whole pixels.

    THE SIGN IS THE ANSWER, and it is why this is integer arithmetic rather than float. A ring
    traced with the inside kept on one hand comes out positive when it encloses the piece and
    negative when it encloses a void, so the sign decides `outer` versus `inner` EXACTLY — no
    tolerance, no epsilon, no ring that flips class because a shoelace sum landed at -1e-17.

    `points` are `(row, col)` lattice corners; the shoelace runs in `(x, y) = (col, row)`, and the
    doubled sum of a closed rectilinear lattice path is always even, so the halving is exact.
    """
    doubled = 0
    n = len(points)
    for i in range(n):
        r0, c0 = points[i]
        r1, c1 = points[(i + 1) % n]
        doubled += c0 * r1 - c1 * r0
    return doubled // 2


__all__ = ["PRECISION", "bbox", "centroid", "gap_px", "lattice_area", "normalized_area",
           "perimeter_px", "round6", "surface"]
