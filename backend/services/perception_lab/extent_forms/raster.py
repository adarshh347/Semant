"""
PERCEPTUAL-FORMS-001B — the raster substrate every exact Extent form stands on.

THE MASK IS THE INPUT AND THE MASK IS THE AUTHORITY. Nothing in this package looks at an image,
loads a model, or asks an adapter anything. It takes a COCO RLE that some earlier lane already
measured and derives, per pixel, the things that follow from it with no judgement left over:
which pixels are connected to which, which voids are enclosed, where the edge runs.

THE ONE DECISION THAT IS NOT FORCED, MADE ONCE, HERE. Digital topology has no free lunch: if
foreground and background are both 4-connected, a diagonal checkerboard has two objects AND a
background that separates them into two, and Jordan's theorem fails in both directions. The
standard repair is to pair the connectivities, and this package pairs them ONE way and says so:

    FOREGROUND_CONNECTIVITY = 4     two pixels are one piece when they share an EDGE
    BACKGROUND_CONNECTIVITY = 8     two voids are one void when they share an edge OR A CORNER

That pairing is what makes every later statement exact rather than conventional. Two islands
touching only at a corner are TWO fragments — and the single void that runs between them is ONE
void, so nothing is enclosed and no hole is invented at the pinch. Reverse the pairing and both
answers flip. The choice is declared rather than defaulted because a reader who assumed the other
one would read every fragment count in this package wrong.

WHAT A REFUSAL IS HERE. `ExtentFormRefusal` carries a contract `RefusalRecord` — the exception is
only the transport. A caller reports `err.refusal`, never `str(err)`, for the reason the contract
gives: a typed no says what would satisfy it, and an exception message says only that something
went wrong. These functions RAISE rather than returning a half-built raster, on the same grounds
`definitions.operation()` raises: an object handed back is an object somebody hands onward, and a
malformed mask treated as real is precisely the failure this module exists to catch.

PURE. No database, no network, no model, no clock, no image.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.perception_lab import OrganFamily, RefusalCode, RefusalRecord
from backend.services.mask_geometry import rle_decode, rle_encode

ORGAN = OrganFamily.EXTENT

#: The pairing, and the reason it is a pair. See the module docstring.
FOREGROUND_CONNECTIVITY = 4
BACKGROUND_CONNECTIVITY = 8

#: How long a content-addressed id's digest half is. Twelve hex is 48 bits over a pixel set that
#: is already unique within its raster, so the id is decorative collision-wise and load-bearing
#: stability-wise: the SAME pixel set on the SAME raster always gets the SAME id, whatever else
#: in the image changed and whatever order it was found in.
DIGEST_CHARS = 12

_ORTHOGONAL = ((-1, 0), (1, 0), (0, -1), (0, 1))
_DIAGONAL = ((-1, -1), (-1, 1), (1, -1), (1, 1))


class ExtentFormRefusal(Exception):
    """A typed no, in flight. `.refusal` is the record; the message is only for a traceback."""

    def __init__(self, refusal: RefusalRecord) -> None:
        super().__init__(refusal.message)
        self.refusal = refusal


def refuse(code: RefusalCode, message: str, *, missing: Sequence[str] = (),
           remedy: Optional[str] = None, detail: Optional[Mapping[str, Any]] = None) -> None:
    """Raise the one exception this package throws. Never returns."""
    raise ExtentFormRefusal(RefusalRecord(
        code=code, organ=ORGAN, message=message, missing=list(missing), remedy=remedy,
        detail=dict(detail or {})))


# ── the canonical RLE ────────────────────────────────────────────────────────


def canonical_rle(raw: Any, *, what: str) -> Dict[str, Any]:
    """Validate a COCO RLE and return the ONE spelling of the mask it describes.

    STRICTER THAN `mask_geometry.rle_is_valid`, deliberately. That predicate sums the runs and is
    satisfied by a negative count cancelling a positive one — a mask that decodes to garbage and
    passes a validity check is worse than one that fails it, so every count is checked to be a
    non-negative integer here before the sum is trusted.

    RE-ENCODED, NOT COPIED. `{"counts": [0, 4, 0, 0, 12]}` and `{"counts": [0, 4, 12]}` are the
    same four pixels written two ways, and a content-addressed id computed over the first would
    differ from one computed over the second. Round-tripping through decode/encode collapses both
    to the spelling `rle_encode` produces, which is what makes an id stable across producers.
    """
    if not isinstance(raw, Mapping):
        refuse(RefusalCode.MISSING_EXTENT_INPUTS,
               f"{what} is {type(raw).__name__}, not an RLE mask. A derivation with no mask has "
               f"nothing to derive from.",
               missing=["mask_rle"],
               remedy="supply the extent's mask_rle, or route the instance to a form that reads "
                      "boxes")
    size = raw.get("size")
    counts = raw.get("counts")
    if not (isinstance(size, (list, tuple)) and len(size) == 2):
        refuse(RefusalCode.MISSING_EXTENT_INPUTS,
               f"{what} carries size {size!r}; an RLE names its raster as exactly [h, w]",
               missing=["mask_rle.size"])
    if not isinstance(counts, (list, tuple)):
        refuse(RefusalCode.MISSING_EXTENT_INPUTS,
               f"{what} carries counts {type(counts).__name__}, which is not a run list",
               missing=["mask_rle.counts"])
    try:
        h, w = int(size[0]), int(size[1])
    except (TypeError, ValueError):
        refuse(RefusalCode.MISSING_EXTENT_INPUTS,
               f"{what} carries a non-integer raster size {list(size)!r}",
               missing=["mask_rle.size"])
    if h <= 0 or w <= 0:
        refuse(RefusalCode.MISSING_EXTENT_INPUTS,
               f"{what} declares a {h}x{w} raster. A raster with no pixels holds no measurement.",
               missing=["mask_rle.size"])
    runs: List[int] = []
    for i, count in enumerate(counts):
        if isinstance(count, bool) or not isinstance(count, int):
            refuse(RefusalCode.MISSING_EXTENT_INPUTS,
                   f"{what} carries run {i} as {count!r}. A run length is a whole number of "
                   f"pixels.",
                   missing=["mask_rle.counts"])
        if count < 0:
            refuse(RefusalCode.MISSING_EXTENT_INPUTS,
                   f"{what} carries run {i} as {count}. A negative run cancels a real one, so a "
                   f"mask holding it can sum to the right total and still decode to nothing "
                   f"like itself.",
                   missing=["mask_rle.counts"])
        runs.append(count)
    total = sum(runs)
    if total != h * w:
        refuse(RefusalCode.MISSING_EXTENT_INPUTS,
               f"{what} runs sum to {total} on a {h}x{w} raster, which holds {h * w}. A mask that "
               f"does not cover its own raster is not a mask of it.",
               missing=["mask_rle.counts"],
               detail={"declared_pixels": h * w, "encoded_pixels": total})
    bits, _, _ = rle_decode({"size": [h, w], "counts": runs})
    return rle_encode(bits, h, w)


def digest_of(rle: Mapping[str, Any]) -> str:
    """The stable half of a content-addressed id: `sha256` over the canonical spelling."""
    size = rle["size"]
    body = f"{int(size[0])}x{int(size[1])}|" + ",".join(str(int(c)) for c in rle["counts"])
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:DIGEST_CHARS]


# ── the raster, decoded once ─────────────────────────────────────────────────


@dataclass(frozen=True)
class Raster:
    """One mask, decoded. Immutable, so the same object can be handed to four derivations."""
    h: int
    w: int
    bits: bytes                     # row-major, one byte per pixel, 0 or 1
    rle: Dict[str, Any]

    @property
    def pixels(self) -> int:
        return self.h * self.w

    @property
    def shape(self) -> Tuple[int, int]:
        return self.h, self.w

    def at(self, r: int, c: int) -> int:
        if 0 <= r < self.h and 0 <= c < self.w:
            return self.bits[r * self.w + c]
        return 0

    @cached_property
    def area_px(self) -> int:
        return sum(self.bits)

    @property
    def is_empty(self) -> bool:
        return self.area_px == 0


def raster_of(raw: Any, *, what: str) -> Raster:
    """A validated, canonical, decoded mask."""
    rle = canonical_rle(raw, what=what)
    bits, h, w = rle_decode(rle)
    return Raster(h=h, w=w, bits=bytes(bits), rle=rle)


# ── connected pixel sets ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class PixelSet:
    """A connected set of pixels on a named raster, and every exact fact that follows from it.

    `pixels` is a SORTED tuple of row-major flat indices, so two runs over the same mask produce
    the same tuple and therefore the same digest and the same id. A set would not: iteration order
    over a Python set of ints is stable within a process and is not a promise.
    """
    h: int
    w: int
    pixels: Tuple[int, ...]
    connectivity: int

    @property
    def shape(self) -> Tuple[int, int]:
        return self.h, self.w

    @property
    def area_px(self) -> int:
        return len(self.pixels)

    @cached_property
    def members(self) -> frozenset:
        return frozenset(self.pixels)

    @cached_property
    def rle(self) -> Dict[str, Any]:
        bits = bytearray(self.h * self.w)
        for p in self.pixels:
            bits[p] = 1
        return rle_encode(bits, self.h, self.w)

    @cached_property
    def digest(self) -> str:
        return digest_of(self.rle)

    @cached_property
    def touches_border(self) -> bool:
        w, h = self.w, self.h
        for p in self.pixels:
            r, c = divmod(p, w)
            if r == 0 or c == 0 or r == h - 1 or c == w - 1:
                return True
        return False

    def contains(self, r: int, c: int) -> bool:
        return 0 <= r < self.h and 0 <= c < self.w and (r * self.w + c) in self.members


def _components(inside: Sequence[int], h: int, w: int, connectivity: int) -> Tuple[PixelSet, ...]:
    """Flood fill in row-major scan order, so component ORDER is a fact about the mask.

    The first component is the one holding the smallest flat index, the second the next, and so
    on. That ordering is not cosmetic: it is what makes `regions_examined` and any positional
    reading of the output reproducible between two runs on two machines.
    """
    steps = _ORTHOGONAL if connectivity == 4 else _ORTHOGONAL + _DIAGONAL
    seen = bytearray(h * w)
    out: List[PixelSet] = []
    for start in range(h * w):
        if not inside[start] or seen[start]:
            continue
        seen[start] = 1
        stack = [start]
        found: List[int] = []
        while stack:
            p = stack.pop()
            found.append(p)
            r, c = divmod(p, w)
            for dr, dc in steps:
                nr, nc = r + dr, c + dc
                if 0 <= nr < h and 0 <= nc < w:
                    q = nr * w + nc
                    if inside[q] and not seen[q]:
                        seen[q] = 1
                        stack.append(q)
        found.sort()
        out.append(PixelSet(h=h, w=w, pixels=tuple(found), connectivity=connectivity))
    return tuple(out)


def foreground_components(raster: Raster) -> Tuple[PixelSet, ...]:
    """The separable pieces of a mask, 4-connected. Corner-touching pieces stay two."""
    return _components(raster.bits, raster.h, raster.w, FOREGROUND_CONNECTIVITY)


def complement_of(piece: PixelSet) -> Tuple[PixelSet, ...]:
    """The voids of ONE piece, 8-connected: every pixel of its raster that is not it.

    THE PIECE, NOT THE MASK, AND THAT IS NOT AN OPTIMISATION. The void inside a ring is a void OF
    the ring, and asking the question of the whole mask gets a different answer the moment a
    second, separate shape is sitting inside that void: globally those pixels are foreground, so
    the ring's opening comes back split, or missing, depending on where the second shape sat.
    Asked of the ring alone every pixel outside the ring is void — which is exactly what the
    ring's own inner boundary encloses, and it is why a hole and an inner ring come out of this
    package one-to-one.

    EXACT AND WHOLE-RASTER. `bounded_voids` answers the same question in a window and is what the
    hole producer uses; this stays because it is the definition the window is checked against.
    """
    members = piece.members
    inside = bytes(0 if p in members else 1 for p in range(piece.h * piece.w))
    return _components(inside, piece.h, piece.w, BACKGROUND_CONNECTIVITY)


def bounded_voids(piece: PixelSet) -> Tuple[Tuple[PixelSet, bool], ...]:
    """Every void of one piece, with whether it ESCAPES this picture — computed in a window.

    `(pixels, escapes)` RATHER THAN A PIXEL SET, because the two facts come apart here. A void's
    pixels are exactly its pixels; whether it escapes is a fact about what lies beyond the window,
    and squeezing that into `PixelSet.touches_border` would mean adding pixels the void does not
    have in order to make a predicate come out right.

    THE WINDOW IS EXACT RATHER THAN A HEURISTIC. Every bounded void of a piece lies strictly
    inside the piece's own bounding box, so a whole-raster flood fill spends its time on the
    exterior — which is one component however large the picture is. The window is the tight
    bounding box padded by one cell IN A VIRTUAL GRID: cells outside the raster are void like any
    other, so the pad is a complete ring of void around the piece whether or not the piece touches
    the frame. A component reaching that ring escapes; one that does not is enclosed.

    Identical to `complement_of` on every control — `test_the_windowed_voids_agree_with_the_whole
    _raster_fill` checks it on all twelve plus the exhaustive small cases — and the cost stops
    being a function of how big the photograph is. Measured on the rehearsal corpus:
    `extent.hole_set` over twelve masks on a 960x1274 raster took 32.1 s before this and 1.4 after.
    """
    w, h = piece.w, piece.h
    if not piece.pixels:
        return ((PixelSet(h=h, w=w, pixels=tuple(range(h * w)),
                          connectivity=BACKGROUND_CONNECTIVITY), True),)
    rows = [p // w for p in piece.pixels]
    cols = [p % w for p in piece.pixels]
    r0, r1 = min(rows) - 1, max(rows) + 1          # may fall outside the raster; that is the point
    c0, c1 = min(cols) - 1, max(cols) + 1
    wh, ww = r1 - r0 + 1, c1 - c0 + 1
    members = piece.members
    inside = bytearray(wh * ww)
    for wr in range(wh):
        r = wr + r0
        row = wr * ww
        for wc in range(ww):
            c = wc + c0
            outside_raster = not (0 <= r < h and 0 <= c < w)
            inside[row + wc] = 1 if outside_raster or (r * w + c) not in members else 0
    out: List[Tuple[PixelSet, bool]] = []
    for found in _components(inside, wh, ww, BACKGROUND_CONNECTIVITY):
        escapes = any((p // ww) in (0, wh - 1) or (p % ww) in (0, ww - 1) for p in found.pixels)
        real = tuple(sorted(
            ((p // ww) + r0) * w + ((p % ww) + c0) for p in found.pixels
            if 0 <= (p // ww) + r0 < h and 0 <= (p % ww) + c0 < w))
        out.append((PixelSet(h=h, w=w, pixels=real,
                             connectivity=BACKGROUND_CONNECTIVITY), escapes))
    return tuple(out)


def complement_components(raster: Raster, *, of: Optional[PixelSet] = None
                          ) -> Tuple[PixelSet, ...]:
    """The voids of a whole mask, 8-connected — or, with `of`, of one piece measured on it."""
    if of is not None:
        if of.shape != raster.shape:
            refuse(RefusalCode.INVALID_PARAMETERS,
                   f"a piece measured on a {of.h}x{of.w} raster cannot be complemented against a "
                   f"{raster.h}x{raster.w} one",
                   detail={"piece_raster": [of.h, of.w], "mask_raster": [raster.h, raster.w]})
        return complement_of(of)
    inside = bytes(1 - b for b in raster.bits)
    return _components(inside, raster.h, raster.w, BACKGROUND_CONNECTIVITY)


__all__ = [
    "BACKGROUND_CONNECTIVITY", "DIGEST_CHARS", "ExtentFormRefusal", "FOREGROUND_CONNECTIVITY",
    "ORGAN", "PixelSet", "Raster", "bounded_voids", "canonical_rle",
    "complement_components", "complement_of", "digest_of",
    "foreground_components", "raster_of", "refuse",
]
