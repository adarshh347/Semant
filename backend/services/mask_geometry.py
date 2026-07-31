"""
Canonical mask geometry — the ONE owner of the RLE ↔ binary mask ↔ polygon ↔ bbox ↔
crop chain (Darshan · VISION-BUILD-001 Increment A).

The authoritative segment identity is a **mask**, carried as a COCO-style *uncompressed*
RLE: `{"size": [h, w], "counts": [int, ...]}`, column-major (Fortran) order, the run
list starting with a 0-run (COCO convention). Everything else a region needs —
`polygons` (multi-ring: outer + holes), the legacy single `polygon`, and the `box`
(normalized bbox) — is DERIVED from the RLE by this module. Boxes are for hover, crops,
compatibility and model-prompt geometry only; they never carry identity when a mask
exists.

Design constraints (Increment A):
  · The core (encode/decode/area/bbox/rasterize) is **pure Python** — no numpy, no cv2 —
    so it works in the slim deploy exactly like the rest of the backend degrades. The
    RLE round-trip is therefore always exact.
  · `bits_to_polygons` uses cv2 (already an optional dep) for accurate contours WITH
    holes + multiple components when available, and falls back to per-component
    bounding-rect rings when cv2 is absent (coarse, but the RLE — the identity — is
    untouched; the polygon is only a render aid). This degradation is the one known
    information loss and is documented at the call site.
  · No models, no GPU, no network. COCO-compatible RLE so the future roster
    (SAM2/detectron masks) drops in without a format change.

Column-major index math: a flat mask is stored row-major (`bits[r*w + c]`); the RLE
walks it column-major, so sequence index `k` maps to `c = k // h`, `r = k % h`.
"""

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

MIN_SIZE = 1e-4  # a normalized extent below this is treated as degenerate


# ─────────────────────────────────────────────────────────────────────────────
# RLE ↔ binary mask (pure python, exact, always available)
# ─────────────────────────────────────────────────────────────────────────────
def rle_encode(bits: Sequence[int], h: int, w: int) -> dict:
    """Row-major bit buffer (len h*w, 0/1) → COCO uncompressed RLE (column-major)."""
    counts: List[int] = []
    prev = 0
    run = 0
    total = h * w
    for k in range(total):
        c = k // h
        r = k % h
        v = 1 if bits[r * w + c] else 0
        if v == prev:
            run += 1
        else:
            counts.append(run)
            prev = v
            run = 1
    counts.append(run)
    return {"size": [int(h), int(w)], "counts": counts}


def rle_encode_mask(mask2d) -> dict:
    """numpy fast path: a 2-D (h,w) 0/1 array → COCO uncompressed RLE (column-major).
    Produces byte-identical output to `rle_encode` but O(runs) instead of O(h*w) Python
    iterations — the encoder for real image-resolution instance masks (YOLO/SAM). Falls
    back to the pure encoder if numpy is unavailable."""
    try:
        import numpy as np
    except Exception:
        h, w = len(mask2d), len(mask2d[0]) if mask2d else 0
        bits = bytearray(h * w)
        for r in range(h):
            for c in range(w):
                if mask2d[r][c]:
                    bits[r * w + c] = 1
        return rle_encode(bits, h, w)
    arr = np.asarray(mask2d)
    h, w = int(arr.shape[0]), int(arr.shape[1])
    flat = (arr != 0).astype(np.uint8).ravel(order="F")   # column-major (COCO)
    if flat.size == 0:
        return {"size": [h, w], "counts": [0]}
    change = np.flatnonzero(np.diff(flat)) + 1
    bounds = np.concatenate(([0], change, [flat.size]))
    runs = np.diff(bounds)
    first_val = int(flat[0])
    counts = [int(c) for c in runs]
    if first_val == 1:                                     # COCO starts with a 0-run
        counts = [0] + counts
    return {"size": [h, w], "counts": counts}


def rle_decode(rle: dict) -> Tuple[bytearray, int, int]:
    """COCO RLE → (row-major bit buffer, h, w). Exact inverse of `rle_encode`."""
    h, w = int(rle["size"][0]), int(rle["size"][1])
    bits = bytearray(h * w)
    k = 0
    val = 0
    for cnt in rle["counts"]:
        cnt = int(cnt)
        if val:
            for kk in range(k, k + cnt):
                c = kk // h
                r = kk % h
                bits[r * w + c] = 1
        k += cnt
        val ^= 1
    return bits, h, w


def rle_is_valid(rle) -> bool:
    """A structurally sound RLE whose runs sum to h*w."""
    if not isinstance(rle, dict):
        return False
    size = rle.get("size")
    counts = rle.get("counts")
    if not (isinstance(size, (list, tuple)) and len(size) == 2):
        return False
    if not isinstance(counts, (list, tuple)):
        return False
    try:
        h, w = int(size[0]), int(size[1])
        return h > 0 and w > 0 and sum(int(c) for c in counts) == h * w
    except (TypeError, ValueError):
        return False


def rle_area(rle: dict) -> int:
    """Set-pixel count. 1-runs sit at odd indices (counts[0] is the leading 0-run)."""
    return sum(int(c) for i, c in enumerate(rle["counts"]) if i % 2 == 1)


def rle_bbox_norm(rle: dict) -> dict:
    """Tight normalized bbox {x,y,w,h} of the set pixels (empty → all zeros)."""
    bits, h, w = rle_decode(rle)
    minr = minc = 1 << 30
    maxr = maxc = -1
    for r in range(h):
        base = r * w
        for c in range(w):
            if bits[base + c]:
                if r < minr: minr = r
                if r > maxr: maxr = r
                if c < minc: minc = c
                if c > maxc: maxc = c
    if maxr < 0:
        return {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0}
    return {
        "x": round(minc / w, 6), "y": round(minr / h, 6),
        "w": round((maxc - minc + 1) / w, 6), "h": round((maxr - minr + 1) / h, 6),
    }


# ─────────────────────────────────────────────────────────────────────────────
# polygon → mask (pure python scanline, even-odd so holes subtract)
# ─────────────────────────────────────────────────────────────────────────────
def polygons_to_bits(rings_norm: List[List[List[float]]], h: int, w: int) -> bytearray:
    """Rasterize normalized rings (outer + holes) into a row-major bit buffer.

    Even-odd fill across ALL rings, so a hole ring toggles its interior back off —
    the multi-component + hole case renders correctly without a hierarchy.
    """
    bits = bytearray(h * w)
    polys = [[(x * w, y * h) for (x, y) in ring] for ring in (rings_norm or []) if len(ring) >= 3]
    if not polys:
        return bits
    for py in range(h):
        yc = py + 0.5
        xs: List[float] = []
        for ring in polys:
            n = len(ring)
            for i in range(n):
                x1, y1 = ring[i]
                x2, y2 = ring[(i + 1) % n]
                if (y1 <= yc < y2) or (y2 <= yc < y1):
                    t = (yc - y1) / (y2 - y1)
                    xs.append(x1 + t * (x2 - x1))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            px_a = max(0, int(math.ceil(xs[i] - 0.5)))
            px_b = min(w - 1, int(math.floor(xs[i + 1] - 0.5)))
            row = py * w
            for px in range(px_a, px_b + 1):
                bits[row + px] = 1
    return bits


# ─────────────────────────────────────────────────────────────────────────────
# mask → polygon(s)  (cv2 fast path with holes/components; pure fallback = rects)
# ─────────────────────────────────────────────────────────────────────────────
def _rect_ring(b: dict) -> List[List[float]]:
    return [
        [round(b["x"], 6), round(b["y"], 6)],
        [round(b["x"] + b["w"], 6), round(b["y"], 6)],
        [round(b["x"] + b["w"], 6), round(b["y"] + b["h"], 6)],
        [round(b["x"], 6), round(b["y"] + b["h"], 6)],
    ]


def _components_4conn(bits: bytearray, h: int, w: int) -> List[List[int]]:
    """4-connected components as lists of flat indices (pure python fallback)."""
    seen = bytearray(h * w)
    comps: List[List[int]] = []
    for start in range(h * w):
        if bits[start] and not seen[start]:
            stack = [start]
            seen[start] = 1
            comp = []
            while stack:
                p = stack.pop()
                comp.append(p)
                r, c = divmod(p, w)
                for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                    if 0 <= nr < h and 0 <= nc < w:
                        q = nr * w + nc
                        if bits[q] and not seen[q]:
                            seen[q] = 1
                            stack.append(q)
            comps.append(comp)
    return comps


def bits_to_polygons(bits: bytearray, h: int, w: int,
                     simplify_tol: float = 0.004) -> List[List[List[float]]]:
    """Row-major mask → list of normalized rings (outer + holes, all components).

    Rings are returned flat (outer and hole rings together); the even-odd fill rule
    in `polygons_to_bits` and in the frontend `<path fill-rule="evenodd">` reconstructs
    holes without a hierarchy. cv2 gives true contours; without cv2 we emit one
    bounding-rect ring per 4-connected component (coarse — the RLE stays authoritative).
    """
    rings: List[List[List[float]]] = []
    try:
        import numpy as np
        import cv2
        # cv2 traces contours through pixel CENTERS, which shrinks the shape by ~½px on
        # each side — negligible on big blobs, ruinous on thin/tiny ones. Contour on an
        # upsampled copy so that error is ~1/U px, then normalize by the upsampled size:
        # the derived polygon rasterizes back to the mask faithfully.
        U = 4
        base = np.frombuffer(bytes(bits), dtype=np.uint8).reshape(h, w)
        arr = np.repeat(np.repeat(base, U, axis=0), U, axis=1)
        Uh, Uw = h * U, w * U
        contours, _ = cv2.findContours(arr, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, simplify_tol * peri, True) if (simplify_tol > 0 and peri > 0) else cnt
            ring = [[round(float(p[0][0]) / Uw, 6), round(float(p[0][1]) / Uh, 6)] for p in approx]
            if len(ring) >= 3:
                rings.append(ring)
    except Exception:
        for comp in _components_4conn(bits, h, w):
            minr = min(p // w for p in comp)
            maxr = max(p // w for p in comp)
            minc = min(p % w for p in comp)
            maxc = max(p % w for p in comp)
            rings.append(_rect_ring({
                "x": minc / w, "y": minr / h,
                "w": (maxc - minc + 1) / w, "h": (maxr - minr + 1) / h,
            }))
    # A very small / thin mask can defeat contour simplification — never emit nothing
    # for a non-empty mask; fall back to its bounding rect so the region stays drawable.
    if not rings and any(bits):
        rle = rle_encode(bits, h, w)
        rings.append(_rect_ring(rle_bbox_norm(rle)))
    return rings


def bbox_from_polygons(rings_norm: List[List[List[float]]]) -> dict:
    """Normalized bbox spanning all rings."""
    xs = [p[0] for ring in rings_norm for p in ring]
    ys = [p[1] for ring in rings_norm for p in ring]
    if not xs:
        return {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0}
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    return {"x": round(x0, 6), "y": round(y0, 6),
            "w": round(x1 - x0, 6), "h": round(y1 - y0, 6)}


def largest_ring(rings_norm: List[List[List[float]]]) -> Optional[List[List[float]]]:
    """The ring with the widest bbox — the legacy single `polygon` for old consumers."""
    if not rings_norm:
        return None
    def span(ring):
        xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
        return (max(xs) - min(xs)) * (max(ys) - min(ys))
    return max(rings_norm, key=span)


# ─────────────────────────────────────────────────────────────────────────────
# mask → crops (PIL; alpha-masked identity crop + rectangular context crop)
# ─────────────────────────────────────────────────────────────────────────────
def mask_to_crops(rle: dict, image) -> dict:
    """Given an RLE mask and a PIL image, return the alpha-masked identity crop, the
    rectangular context crop, and the normalized box. The mask is nearest-neighbour
    scaled from its own [h,w] to the image, so mask and image need not match resolution.
    Returns {box, context_crop (RGB), alpha_crop (RGBA)}."""
    from PIL import Image
    h, w = int(rle["size"][0]), int(rle["size"][1])
    iw, ih = image.size
    box = rle_bbox_norm(rle)
    l = max(0, min(int(box["x"] * iw), iw - 1))
    t = max(0, min(int(box["y"] * ih), ih - 1))
    rgt = max(l + 1, min(int(round((box["x"] + box["w"]) * iw)), iw))
    bot = max(t + 1, min(int(round((box["y"] + box["h"]) * ih)), ih))
    context_crop = image.crop((l, t, rgt, bot))

    bits, _, _ = rle_decode(rle)
    alpha = Image.new("L", (iw, ih), 0)
    apx = alpha.load()
    for yy in range(ih):
        my = min(h - 1, yy * h // ih)
        for xx in range(iw):
            mx = min(w - 1, xx * w // iw)
            if bits[my * w + mx]:
                apx[xx, yy] = 255
    rgba = image.convert("RGBA")
    rgba.putalpha(alpha)
    alpha_crop = rgba.crop((l, t, rgt, bot))
    return {"box": box, "context_crop": context_crop, "alpha_crop": alpha_crop}


# ─────────────────────────────────────────────────────────────────────────────
# canonicalisation — the single entry the save path calls
# ─────────────────────────────────────────────────────────────────────────────
def canonicalize_geometry(region: dict, *, default_mask_size: Optional[Tuple[int, int]] = None,
                          provenance: Optional[dict] = None) -> dict:
    """Make a region's geometry canonical and stamp lineage, IN PLACE, preserving `id`.

    · If the region carries a valid `mask_rle`, that mask is authoritative: `polygons`,
      the legacy `polygon`, and `box` are re-derived from it.
    · Else if it carries multi-ring `polygons` and a raster size is available, the rings
      are rasterized into an authoritative `mask_rle`, then the rest is derived.
    · Else the region is a legacy box/single-polygon mark: its geometry is left exactly
      as-is (the "retain box-only legacy explicitly" rule) — no mask is fabricated.

    `geometry_rev` bumps whenever a mask identity is (re)derived; `geometry_provenance`
    records kind + method (+ any caller-supplied fields for the observability contract).
    """
    prov_extra = dict(provenance or {})

    rle = region.get("mask_rle")
    rings = region.get("polygons")

    if rle_is_valid(rle):
        bits, h, w = rle_decode(rle)
        derived = bits_to_polygons(bits, h, w)
        region["polygons"] = derived
        lr = largest_ring(derived)
        if lr is not None:
            region["polygon"] = lr
        region["box"] = rle_bbox_norm(rle)
        region["geometry_rev"] = int(region.get("geometry_rev") or 0) + 1
        region["geometry_provenance"] = {"kind": "mask", "method": "rle",
                                         "size": [h, w], **prov_extra}
        return region

    if isinstance(rings, list) and any(len(r) >= 3 for r in rings) and default_mask_size:
        h, w = int(default_mask_size[0]), int(default_mask_size[1])
        bits = polygons_to_bits(rings, h, w)
        new_rle = rle_encode(bits, h, w)
        region["mask_rle"] = new_rle
        region["polygons"] = bits_to_polygons(bits, h, w)
        lr = largest_ring(region["polygons"])
        if lr is not None:
            region["polygon"] = lr
        region["box"] = rle_bbox_norm(new_rle)
        region["geometry_rev"] = int(region.get("geometry_rev") or 0) + 1
        region["geometry_provenance"] = {"kind": "mask", "method": "polygons",
                                         "size": [h, w], **prov_extra}
        return region

    # legacy: box-only or single-ring polygon — retained explicitly, geometry untouched.
    if not region.get("geometry_provenance"):
        kind = "polygon" if (region.get("polygon") and len(region["polygon"]) >= 3) else "box"
        region["geometry_provenance"] = {"kind": f"legacy-{kind}", **prov_extra}
    return region


# ─────────────────────────────────────────────────────────────────────────────
# negative-space converter (CIRCUIT-001 P6-A) — the first brush_field producer's
# geometry helper. A figure mask that ALREADY EXISTS → its complement → a soft field
# → editable strokes[]. Pure, no I/O, no model: the negative space is what is shaped by
# NOT being the figure, so it is derivable from the figure alone. Stays in this module
# because that keeps `mask_geometry` the one owner of the RLE ↔ mask chain.
# ─────────────────────────────────────────────────────────────────────────────

def mask_complement(rle: dict) -> dict:
    """The complement of a mask: every pixel flipped (figure → ground, ground → figure).

    Exact and self-inverse — `mask_complement(mask_complement(m)) == m` on the bit buffer —
    because it rides the exact RLE round-trip. This is the whole geometric content of
    "negative space": the part of the frame the figure is not."""
    bits, h, w = rle_decode(rle)
    comp = bytearray(1 - (1 if b else 0) for b in bits)
    return rle_encode(comp, h, w)


def soft_field_from_mask(rle: dict, *, _diag: float = math.sqrt(2)) -> Tuple[List[float], int, int]:
    """A figure mask → a SOFT field over its negative space (a chamfer distance transform).

    Returns `(field, h, w)` where `field` is a row-major list in [0, 1]: 0.0 on every figure
    pixel, ramping up with distance INTO the negative space, normalized so the deepest point
    is 1.0. "Soft" is literal — the falloff is the distance from the figure's edge, not a hard
    complement. Pure Python (two-pass chamfer), no numpy.

    Degenerate inputs return an all-zero field (nothing to draw): an empty mask has no figure
    to define a negative space against, and a full mask leaves no negative space at all. The
    producer treats "no field" as a refusal rather than fabricating one."""
    bits, h, w = rle_decode(rle)
    n = h * w
    if n == 0:
        return [], h, w
    INF = float(h + w) * 2.0 + 1.0
    dist = [0.0 if bits[i] else INF for i in range(n)]

    # forward pass (raster order): each ground pixel takes the cheapest step from an
    # already-visited neighbour (W, NW, N, NE).
    for r in range(h):
        base = r * w
        for c in range(w):
            i = base + c
            if bits[i]:
                continue
            d = dist[i]
            if c > 0:
                d = min(d, dist[i - 1] + 1.0)
            if r > 0:
                d = min(d, dist[i - w] + 1.0)
                if c > 0:
                    d = min(d, dist[i - w - 1] + _diag)
                if c < w - 1:
                    d = min(d, dist[i - w + 1] + _diag)
            dist[i] = d

    # backward pass (reverse raster): relax against E, SE, S, SW.
    for r in range(h - 1, -1, -1):
        base = r * w
        for c in range(w - 1, -1, -1):
            i = base + c
            if bits[i]:
                continue
            d = dist[i]
            if c < w - 1:
                d = min(d, dist[i + 1] + 1.0)
            if r < h - 1:
                d = min(d, dist[i + w] + 1.0)
                if c < w - 1:
                    d = min(d, dist[i + w + 1] + _diag)
                if c > 0:
                    d = min(d, dist[i + w - 1] + _diag)
            dist[i] = d

    mx = 0.0
    for i in range(n):
        if not bits[i] and dist[i] < INF and dist[i] > mx:
            mx = dist[i]
    if mx <= 0.0:
        return [0.0] * n, h, w
    field = [0.0 if bits[i] else min(1.0, dist[i] / mx) for i in range(n)]
    return field, h, w


def strokes_from_field(field: Sequence[float], h: int, w: int, *, grid: int = 8,
                       threshold: float = 0.12, radius: float = 0.05) -> List[dict]:
    """A soft field → editable `strokes[]` in the freehand-stroke shape the field tools already
    consume: `{points:[[x,y]], radius, strength, op}` with NORMALIZED (0..1) points and
    `strength ∝ value`. Samples a `grid`×`grid` lattice of cell centres and drops a stroke
    wherever the field clears `threshold` — so a suggestion arrives as marks a curator can move,
    reweight or erase, never as a baked-in wash. Deterministic (no randomness)."""
    strokes: List[dict] = []
    if h <= 0 or w <= 0 or not field:
        return strokes
    gy = max(1, min(grid, h))
    gx = max(1, min(grid, w))
    for gyi in range(gy):
        r = min(h - 1, max(0, int((gyi + 0.5) * h / gy)))
        for gxi in range(gx):
            c = min(w - 1, max(0, int((gxi + 0.5) * w / gx)))
            v = float(field[r * w + c])
            if v < threshold:
                continue
            strokes.append({
                "points": [[round((c + 0.5) / w, 4), round((r + 0.5) / h, 4)]],
                "radius": radius,
                "strength": round(v, 4),
                "op": "add",
            })
    return strokes


# ─────────────────────────────────────────────────────────────────────────────
# same-material converter (CIRCUIT-001 P6-B) — a seed patch's DINOv2 feature vs the
# shared patch grid → a cosine "same material" soft field. Pure (no torch, no numpy):
# the caller hands over the already-computed patch tokens as plain vectors (the real
# DINOv2 tensor is `.tolist()`-ed at the boundary), so the field logic is testable with
# a synthetic grid and never needs a GPU. The field then reuses `strokes_from_field`.
# ─────────────────────────────────────────────────────────────────────────────

def cosine_field_from_features(patch_vectors: Sequence[Sequence[float]], grid: int,
                               seed_index: int, *, floor: float = 0.0
                               ) -> Tuple[List[float], int, int]:
    """A seed patch feature vs the whole patch grid → a same-material soft field.

    `patch_vectors` is a flat, row-major sequence of ``grid*grid`` feature vectors (each a list of
    floats — the RAW DINOv2 patch tokens; this fn L2-normalizes internally). `seed_index` is the
    flat index of the tapped patch. Returns ``(field, grid, grid)`` with the field row-major in
    [0, 1]: the cosine similarity of every patch to the seed, floored at 0 (a material field is a
    STRENGTH — a patch of a different material is "not this material", not negatively so). The seed
    against itself is exactly 1.0, so the field is already normalized with its peak at the tap.

    Degenerate input (bad grid, too few vectors, out-of-range seed) → an empty field, which the
    producer reads as a refusal rather than a field to draw."""
    n = grid * grid
    if grid <= 0 or len(patch_vectors) < n or not (0 <= seed_index < n):
        return [], grid, grid

    def _unit(v: Sequence[float]) -> List[float]:
        s = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / s for x in v]

    seed = _unit(patch_vectors[seed_index])
    field: List[float] = []
    for i in range(n):
        p = _unit(patch_vectors[i])
        cos = sum(a * b for a, b in zip(seed, p))
        field.append(cos if cos > floor else floor)
    return field, grid, grid


def field_contrast(field: Sequence[float]) -> float:
    """Dynamic range of a field — max minus min. A crisp material extent has high contrast; a
    near-uniform field (everything reads like the seed, so nothing is distinguished) has almost
    none, and the producer refuses it rather than paint the whole frame."""
    if not field:
        return 0.0
    return float(max(field) - min(field))


# ─────────────────────────────────────────────────────────────────────────────
# response-map converter (CIRCUIT-001 P6-D) — the generic "a measurement over the
# image → a soft field" step. Gabor energy, structure-tensor coherence, and later a
# depth map are all just per-cell magnitudes; normalizing them is one operation, so it
# lives here once rather than once per producer. Pure: plain floats in, floats out — no
# cv2, no numpy, so the field logic is testable without any of the CPU vision stack.
# ─────────────────────────────────────────────────────────────────────────────

def soft_field_from_map(values: Sequence[float], grid: int) -> Tuple[List[float], int, int]:
    """A raw response map (``grid*grid`` magnitudes, row-major) → a normalized [0,1] soft field.

    Min-max scaled, so the strongest cell reads 1.0 and the weakest 0.0 — the field says
    "strong HERE relative to the rest of what was read", which is the only claim a magnitude
    can honestly support. Degenerate input (bad grid, wrong length) → an empty field, which the
    producer reads as a refusal.

    Note a flat map normalizes to all-zeros rather than all-ones: when nothing varies, nothing
    stands out, and the honest field is empty rather than a wash over everything."""
    n = grid * grid
    if grid <= 0 or len(values) < n:
        return [], grid, grid
    vals = [float(v) for v in values[:n]]
    lo, hi = min(vals), max(vals)
    span = hi - lo
    if span <= 1e-12:
        return [0.0] * n, grid, grid           # nothing varies → nothing to draw
    return [(v - lo) / span for v in vals], grid, grid


def depth_band_field(depth: Sequence[float], grid: int, *, band: str = "far"
                     ) -> Tuple[List[float], int, int]:
    """A relative-depth map → the NEAR or FAR band as a normalized [0,1] soft field.

    Depth-Anything emits INVERSE depth (larger = nearer), so after min-max normalization the
    near band is the map itself and the far band is its complement. `background_recession` is
    the far band — what falls away behind — and `atmosphere_field` the near one, the condition
    the foreground sits in.

    A scene with no depth relief (a flat wall, a copy shot) normalizes to all-zeros and yields
    an empty far band, which the producer reads as a refusal rather than inventing distance."""
    field, gh, gw = soft_field_from_map(depth, grid)
    if not field:
        return [], gh, gw
    if band == "near":
        return field, gh, gw
    return [1.0 - v for v in field], gh, gw


# ─────────────────────────────────────────────────────────────────────────────
# shading converters (CIRCUIT-001 P6-G) — light, its withholding, and its direction.
# Intrinsic decomposition hands back a shading map (larger = more lit). Light and
# shadow are then one normalization and one inversion; the FALL of light is the
# map's gradient, which is a direction rather than a field. Pure — plain floats in.
# ─────────────────────────────────────────────────────────────────────────────

def shading_band_field(shading: Sequence[float], grid: int, *, band: str = "light"
                       ) -> Tuple[List[float], int, int]:
    """A shading map → the LIT or the WITHHELD band as a normalized [0,1] soft field.

    `light` is the normalized shading itself — where the light lands. `shadow` is its exact
    complement: shadow is not a separate measurement but the same one read as absence, which is
    the honest way to put it (nothing measures "shadow"; it is where light is not).

    An evenly-lit surface normalizes to all-zeros and yields no band, which the producer reads as
    a refusal — a flat studio wash has no light field worth marking."""
    field, gh, gw = soft_field_from_map(shading, grid)
    if not field:
        return [], gh, gw
    if band == "light":
        return field, gh, gw
    return [1.0 - v for v in field], gh, gw


def shading_gradient(shading: Sequence[float], grid: int) -> Optional[Dict[str, float]]:
    """A shading map → the direction light FALLS across it, as a unit vector + strength.

    Central differences over the coarse grid give a mean gradient; light falls from bright toward
    dark, so the fall direction is the NEGATIVE gradient. Returns
    ``{"dx", "dy", "strength"}`` in normalized image axes (x right, y down), or None when the
    field is too flat for a direction to mean anything.

    This is the geometry a `fall_of_light` TRACE mark would carry. P6-G ships the converter and
    the two field producers; the trace producer is a separate act — a direction is a different
    mark family (`trace_mark`/vector), not a brush_field, and inventing that surface unattended
    would be exactly the overreach this gate's guard is about."""
    n = grid * grid
    if grid < 3 or len(shading) < n:
        return None
    vals = [float(v) for v in shading[:n]]
    lo, hi = min(vals), max(vals)
    if hi - lo <= 1e-12:
        return None                                    # evenly lit — no direction to report
    gx_sum = 0.0
    gy_sum = 0.0
    for r in range(1, grid - 1):
        for c in range(1, grid - 1):
            gx_sum += (vals[r * grid + c + 1] - vals[r * grid + c - 1]) / 2.0
            gy_sum += (vals[(r + 1) * grid + c] - vals[(r - 1) * grid + c]) / 2.0
    inner = max(1, (grid - 2) * (grid - 2))
    gx, gy = gx_sum / inner, gy_sum / inner
    mag = math.sqrt(gx * gx + gy * gy)
    if mag <= 1e-12:
        return None                                    # symmetric lighting — no net fall
    # light falls from lit toward unlit: the negative gradient, unitized.
    return {"dx": round(-gx / mag, 4), "dy": round(-gy / mag, 4),
            "strength": round(mag / (hi - lo), 4)}


# ─────────────────────────────────────────────────────────────────────────────
# flow-field converter (CIRCUIT-001 GEOM-001) — the DENSE sibling of shading_gradient.
# Where shading_gradient reports the ONE mean direction light falls, this reports a
# direction PER CELL: the fall of light is not uniform (light rounds a form, pools in a
# recess, rakes across a wall), and a single arrow flattens exactly the structure a
# curator wants to trace. A scalar soft field cannot hold this — a field is a magnitude
# at each cell, a flow_field is a VECTOR at each cell. That is the whole reason the kind
# exists. Pure: plain floats in, a serialisable grid of unit-vectors + magnitudes out.
# ─────────────────────────────────────────────────────────────────────────────

def shading_flow_field(shading: Sequence[float], grid: int, *, out_grid: int = 14
                       ) -> Tuple[List[List[float]], int, int]:
    """A shading map → a DENSE flow field: the direction light falls, per cell.

    Returns ``(cells, rows, cols)`` where ``cells`` is a row-major list of ``[dx, dy, m]``:
    ``(dx, dy)`` is the UNIT direction light travels at that cell (the negative shading
    gradient, unitized) in normalized image axes (x right, y down), and ``m`` is that cell's
    gradient magnitude normalized to ``[0, 1]`` against the strongest cell in the grid. A cell
    with no local gradient is ``[0.0, 0.0, 0.0]`` — a null cell, not a fabricated direction.

    The lattice is sampled at ``out_grid × out_grid`` (capped by the native grid), so the field
    is a bounded, legible arrow lattice regardless of the shading grid's resolution. Central
    differences are taken in native-grid space at each sample, so the direction is the real local
    fall, not an interpolation artefact.

    Refuses (returns ``([], 0, 0)``) when nothing is directional — a flat or evenly-lit map has no
    fall to trace, and a grid of invented arrows over a blank wall is the same lie ``shading_gradient``
    refuses with ``None``. This is the geometry a ``fall_of_light`` trace mark carries."""
    n = grid * grid
    if grid < 3 or len(shading) < n:
        return [], 0, 0
    vals = [float(v) for v in shading[:n]]
    lo, hi = min(vals), max(vals)
    if hi - lo <= 1e-12:
        return [], 0, 0                                # evenly lit — no fall to trace

    cols = rows = max(2, min(out_grid, grid))
    # Sample the interior so central differences always have both neighbours; map each output
    # cell centre to a native-grid coordinate, then difference one native step either side.
    raw: List[List[float]] = []                        # [dx, dy, mag] with dx,dy the raw gradient
    mags: List[float] = []
    for ri in range(rows):
        for ci in range(cols):
            # cell centre in native-grid coords, clamped so ±1 stays in range
            fc = (ci + 0.5) * grid / cols
            fr = (ri + 0.5) * grid / rows
            c = min(grid - 2, max(1, int(fc)))
            r = min(grid - 2, max(1, int(fr)))
            gx = (vals[r * grid + c + 1] - vals[r * grid + c - 1]) / 2.0
            gy = (vals[(r + 1) * grid + c] - vals[(r - 1) * grid + c]) / 2.0
            mag = math.sqrt(gx * gx + gy * gy)
            # store the FALL direction (negative gradient); unitize later against per-cell mag
            raw.append([-gx, -gy, mag])
            mags.append(mag)

    peak = max(mags) if mags else 0.0
    if peak <= 1e-12:
        return [], 0, 0                                # no cell has a direction → refuse
    cells: List[List[float]] = []
    for dx_neg, dy_neg, mag in raw:
        if mag <= 1e-12:
            cells.append([0.0, 0.0, 0.0])              # null cell — honest absence
        else:
            cells.append([round(dx_neg / mag, 4), round(dy_neg / mag, 4),
                          round(mag / peak, 4)])
    return cells, rows, cols


def flow_field_coherence(cells: Sequence[Sequence[float]]) -> float:
    """How aligned a flow field is: the magnitude-weighted mean resultant length of its unit
    directions, in ``[0, 1]``. 1.0 is a single raking light (every arrow parallel); near 0 is a
    swirling or divergent field (light from many sides). It is the honest ``confidence`` a
    ``fall_of_light`` mark can carry — not "is this right" but "is there one direction here" —
    and it is a reading ABOUT the geometry, never painted into it."""
    sx = sy = sw = 0.0
    for cell in cells:
        if len(cell) < 3:
            continue
        dx, dy, m = float(cell[0]), float(cell[1]), float(cell[2])
        sx += dx * m
        sy += dy * m
        sw += m
    if sw <= 1e-12:
        return 0.0
    return round(math.sqrt(sx * sx + sy * sy) / sw, 4)


# ─────────────────────────────────────────────────────────────────────────────
# grounding converter (CIRCUIT-001 P8-A) — a phrase-grounding result → this repo's
# canonical geometry. Florence-2 emits PIXEL coordinates against the image it saw;
# everything downstream speaks normalized [0,1] against the source image. Converting
# exactly once, here, is the REGION-GEOMETRY-001 rule. Pure: numbers in, numbers out.
# ─────────────────────────────────────────────────────────────────────────────

def normalize_polygon(flat_xy: Sequence[float], width: int, height: int
                      ) -> List[List[float]]:
    """Florence's flat ``[x1,y1,x2,y2,…]`` pixel ring → a normalized ``[[x,y],…]`` ring.

    Values are clamped into the unit frame: a model may place a vertex a pixel outside the
    image, and a ring that escapes [0,1] would break every consumer that assumes the contract."""
    if not flat_xy or width <= 0 or height <= 0:
        return []
    pts: List[List[float]] = []
    for i in range(0, len(flat_xy) - 1, 2):
        x = min(1.0, max(0.0, float(flat_xy[i]) / width))
        y = min(1.0, max(0.0, float(flat_xy[i + 1]) / height))
        pts.append([round(x, 5), round(y, 5)])
    return pts


def normalize_box_xyxy(box: Sequence[float], width: int, height: int) -> Optional[Dict[str, float]]:
    """Florence's pixel ``[x0,y0,x1,y1]`` → the canonical normalized ``{x,y,w,h}``.

    Returns None for a degenerate box — a zero-area detection is not evidence of anything."""
    if not box or len(box) < 4 or width <= 0 or height <= 0:
        return None
    x0, y0, x1, y1 = (float(v) for v in box[:4])
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    nx, ny = max(0.0, x0 / width), max(0.0, y0 / height)
    nw, nh = min(1.0 - nx, (x1 - x0) / width), min(1.0 - ny, (y1 - y0) / height)
    if nw <= MIN_SIZE or nh <= MIN_SIZE:
        return None
    return {"x": round(nx, 5), "y": round(ny, 5), "w": round(nw, 5), "h": round(nh, 5)}


def region_geometry_from_grounding(grounding: Optional[Dict[str, Any]]
                                   ) -> Optional[Dict[str, Any]]:
    """A Florence grounding result → ``{"polygons": [...], "box": {...}}`` in normalized space.

    Prefers polygons (a real extent) and falls back to the grounding box. Returns None when
    nothing survives normalization — a phrase that grounds only a degenerate sliver has, honestly,
    grounded nothing."""
    if not isinstance(grounding, dict):
        return None
    size = grounding.get("image_size") or [0, 0]
    w, h = int(size[0] or 0), int(size[1] or 0)
    if w <= 0 or h <= 0:
        return None

    rings: List[List[List[float]]] = []
    for poly_group in grounding.get("polygons") or []:
        # Florence nests: one instance → a list of rings, each a flat pixel list.
        groups = poly_group if isinstance(poly_group, (list, tuple)) else []
        for ring in groups:
            pts = normalize_polygon(ring, w, h) if isinstance(ring, (list, tuple)) else []
            if len(pts) >= 3:                       # fewer than 3 points is not an extent
                rings.append(pts)
    if rings:
        return {"polygons": rings, "box": bbox_from_polygons(rings)}

    for box in grounding.get("boxes") or []:
        nb = normalize_box_xyxy(box, w, h)
        if nb:
            return {"polygons": [], "box": nb}
    return None

# ─────────────────────────────────────────────────────────────────────────────
# line-orientation flow field (CIRCUIT-001 TRACE-001) — the first TRACE-lane converter.
# Same output contract as `shading_flow_field`, different physics: where that reads a
# continuous scalar map and differentiates it, this reads discrete LINE SEGMENTS and asks
# what orientation dominates near each cell. Detection (OpenCV) lives in
# `line_structure_service`; this stays pure so a synthetic segment list can test it.
#
# THE ONE THING THAT MAKES THIS DIFFERENT FROM EVERY OTHER FLOW FIELD: a line has an
# ORIENTATION, not a direction. A wall edge is the same edge read upward or downward — 179°
# and 1° are nearly the same axis, but their plain mean is 90°, i.e. exactly perpendicular
# to both. Averaging raw angles here does not degrade gracefully, it inverts. So every
# accumulation below is done in DOUBLED-ANGLE space (cos2θ, sin2θ), summed, and halved at
# the end — the standard treatment for axial data, and the reason this file gets its own
# coherence function instead of reusing `flow_field_coherence`.
# ─────────────────────────────────────────────────────────────────────────────

def line_orientation_flow_field(segments: Sequence[Sequence[float]], width: float, height: float,
                                *, out_grid: int = 14, influence: float = 1.6
                                ) -> Tuple[List[List[float]], int, int]:
    """Line segments → a DENSE flow field: the dominant structural orientation, per cell.

    `segments` is ``[(x0, y0, x1, y1), …]`` in PIXEL coordinates; `width`/`height` size the
    image those pixels came from. Returns ``(cells, rows, cols)`` on exactly the contract
    `shading_flow_field` established: row-major ``[dx, dy, m]``, unit orientation in normalized
    image axes (x right, y down), ``m`` the cell's line density normalized to ``[0, 1]`` against
    the densest cell, and ``[0.0, 0.0, 0.0]`` for a cell with no lines near it — a null cell, not
    a fabricated axis.

    `(dx, dy)` is AXIAL and canonicalised to the half-plane ``dx >= 0``. There is no arrowhead to
    put on it: the sign carries no information and a consumer that draws one is asserting a
    direction the picture does not contain.

    Each segment is walked at sub-cell steps and deposits its length into the cells it crosses, so
    a long wall edge counts for more than a short window mullion — weighting by length is what
    makes "dominant" mean structurally dominant rather than merely numerous. Cells then gather
    from neighbours within `influence` cells with a ``1/(1+d²)`` falloff, which is the "nearby line
    density" that keeps a single cell between two parallel edges from reading as empty.

    Refuses (``([], 0, 0)``) only when there is nothing to measure — no segments, or no cell
    accumulating any length. Whether the lines that DO exist amount to architecture is a
    judgement about the scene, and it belongs to the producer, not to the geometry."""
    if width <= 0 or height <= 0:
        return [], 0, 0
    cols = rows = max(2, int(out_grid))
    cell_w = float(width) / cols
    cell_h = float(height) / rows
    step = max(1e-6, min(cell_w, cell_h) / 2.0)          # sub-cell walk: never skip a cell

    acc_c2 = [0.0] * (rows * cols)
    acc_s2 = [0.0] * (rows * cols)
    acc_w = [0.0] * (rows * cols)
    total_length = 0.0

    for seg in segments or ():
        if seg is None or len(seg) < 4:
            continue
        x0, y0, x1, y1 = (float(seg[0]), float(seg[1]), float(seg[2]), float(seg[3]))
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            continue
        total_length += length
        theta = math.atan2(dy, dx)
        c2, s2 = math.cos(2.0 * theta), math.sin(2.0 * theta)
        n = max(1, int(length / step))
        w = length / n                                   # each sample carries its share of length
        for i in range(n + 1):
            t = i / n
            px, py = x0 + dx * t, y0 + dy * t
            ci = int(px / cell_w)
            ri = int(py / cell_h)
            if ci < 0 or ci >= cols or ri < 0 or ri >= rows:
                continue
            k = ri * cols + ci
            acc_c2[k] += w * c2
            acc_s2[k] += w * s2
            acc_w[k] += w

    if total_length <= 1e-9 or max(acc_w) <= 1e-12:
        return [], 0, 0                                  # nothing linear to report

    # Neighbourhood gather — density, not just incidence.
    radius = max(0, int(math.ceil(influence)))
    cells: List[List[float]] = []
    gathered_c2: List[float] = []
    gathered_s2: List[float] = []
    gathered_w: List[float] = []
    for ri in range(rows):
        for ci in range(cols):
            gc2 = gs2 = gw = 0.0
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    rr, cc = ri + dr, ci + dc
                    if rr < 0 or rr >= rows or cc < 0 or cc >= cols:
                        continue
                    d2 = float(dr * dr + dc * dc)
                    if d2 > influence * influence:
                        continue
                    fall = 1.0 / (1.0 + d2)
                    k = rr * cols + cc
                    gc2 += acc_c2[k] * fall
                    gs2 += acc_s2[k] * fall
                    gw += acc_w[k] * fall
            gathered_c2.append(gc2)
            gathered_s2.append(gs2)
            gathered_w.append(gw)

    peak = max(gathered_w) if gathered_w else 0.0
    if peak <= 1e-12:
        return [], 0, 0
    for gc2, gs2, gw in zip(gathered_c2, gathered_s2, gathered_w):
        if gw <= 1e-12:
            cells.append([0.0, 0.0, 0.0])                # null cell — honest absence
            continue
        # Halve the doubled angle to recover the axis, then canonicalise to dx >= 0.
        theta = math.atan2(gs2, gc2) / 2.0
        ux, uy = math.cos(theta), math.sin(theta)
        if ux < 0:
            ux, uy = -ux, -uy
        cells.append([round(ux, 4), round(uy, 4), round(gw / peak, 4)])
    return cells, rows, cols


def axial_coherence(cells: Sequence[Sequence[float]]) -> float:
    """How aligned an AXIAL flow field is, in ``[0, 1]``. 1.0 is one dominant orientation.

    A separate function from `flow_field_coherence` for the reason stated at the top of this
    section, and it is not a stylistic preference: two cells at 89° and −89° are nearly the same
    axis, but as raw unit vectors they very nearly cancel, so `flow_field_coherence` would report
    a strongly-aligned field as incoherent. Doubling the angles before summing makes antiparallel
    directions agree, which for a line is the truth.

    This is the honest ``confidence`` an ``architectural_axis`` mark carries — not "is this the
    right axis" but "is there a dominant axis here at all"."""
    sc = ss = sw = 0.0
    for cell in cells:
        if len(cell) < 3:
            continue
        dx, dy, m = float(cell[0]), float(cell[1]), float(cell[2])
        if m <= 0:
            continue
        theta = math.atan2(dy, dx)
        sc += math.cos(2.0 * theta) * m
        ss += math.sin(2.0 * theta) * m
        sw += m
    if sw <= 1e-12:
        return 0.0
    return round(math.sqrt(sc * sc + ss * ss) / sw, 4)


def flow_field_coverage(cells: Sequence[Sequence[float]]) -> float:
    """Fraction of cells carrying any magnitude, in ``[0, 1]``.

    Distinguishes "lines everywhere" from "one strong line in a corner". A producer deciding
    whether a scene is structurally linear needs both this and the total density: a single lamp
    post against a sky is coherent and dense at one cell, and it is not architecture."""
    if not cells:
        return 0.0
    live = sum(1 for c in cells if len(c) >= 3 and float(c[2]) > 0.0)
    return round(live / len(cells), 4)

# ─────────────────────────────────────────────────────────────────────────────
# horizon / projective converter (CIRCUIT-001 TRACE-002) — the second TRACE-lane converter.
# Input is a per-cell UP-VECTOR field (where gravity points, projected into the image) as a
# monocular calibration model emits it. Output is the same flow_field contract everything
# else on this lane uses.
#
# THE LIMIT IS PERPENDICULAR TO UP. `external_limit` traces the horizon, and the local horizon
# at a point is the line orthogonal to the local vertical. So this rotates the up-vector by 90°
# rather than drawing it: an arrow pointing at the sky is not the limit, it is the thing the
# limit is measured against.
#
# AND THE REFUSAL INVERTS relative to `architectural_axis`. There, high coherence meant "there
# is an axis". Here it does not: a flat frontal wall has a PERFECTLY constant up-vector, so its
# horizon field is perfectly coherent — and it has no projective structure whatsoever. The thing
# that distinguishes a perspective view is that the up-vector VARIES across the frame as the
# scene converges. So coherence scores the mark and SPREAD decides whether there is a mark at
# all, and reusing coherence for both would accept exactly the images it should refuse.
# ─────────────────────────────────────────────────────────────────────────────

def up_vector_spread(up_x: Sequence[float], up_y: Sequence[float], grid: int) -> float:
    """How much the up-vector field VARIES across the frame, in ``[0, 1]``.

    Circular variance of the up-vector angles: ``1 - R``, where R is the mean resultant length.
    A frontal photograph of a wall has one up direction everywhere → R = 1 → spread 0.0. A
    receding street or a nave shot down its length swings the up-vector as the scene converges
    → spread rises.

    This is the measure of "is there a projective frame here at all", and it is deliberately NOT
    coherence — see the section note. Up-vectors are DIRECTIONAL (up and down are different), so
    this uses plain circular statistics, unlike `axial_coherence` next door."""
    n = grid * grid
    if grid < 2 or len(up_x) < n or len(up_y) < n:
        return 0.0
    sx = sy = 0.0
    count = 0
    for i in range(n):
        ux, uy = float(up_x[i]), float(up_y[i])
        mag = math.hypot(ux, uy)
        if mag <= 1e-9:
            continue
        sx += ux / mag
        sy += uy / mag
        count += 1
    if count == 0:
        return 0.0
    r = math.sqrt(sx * sx + sy * sy) / count
    return round(max(0.0, min(1.0, 1.0 - r)), 4)


def horizon_flow_field(up_x: Sequence[float], up_y: Sequence[float], grid: int,
                       *, out_grid: int = 14) -> Tuple[List[List[float]], int, int]:
    """A per-cell up-vector field → the local HORIZON as a dense flow_field.

    Returns ``(cells, rows, cols)`` on the `shading_flow_field` contract: row-major
    ``[dx, dy, m]``, unit direction, magnitude peak-normalized, ``[0.0, 0.0, 0.0]`` for a cell the
    model could not determine. Each direction is the up-vector rotated 90° — the local horizon —
    and is canonicalised into the ``dx >= 0`` half-plane because a horizon is AXIAL: left-to-right
    and right-to-left are the same line, and `axial_coherence` is the measure that matches.

    ``m`` is the up-vector's own magnitude (how strongly the model determined the vertical there),
    peak-normalized. A cell where the model is unsure is faint rather than absent, and a cell where
    it returned nothing is null rather than invented.

    Refuses (``([], 0, 0)``) when the field is empty or degenerate. It does NOT judge whether the
    scene is projective — that needs `up_vector_spread`, and it is the producer's call."""
    n = grid * grid
    if grid < 2 or len(up_x) < n or len(up_y) < n:
        return [], 0, 0
    cols = rows = max(2, min(int(out_grid), grid))

    raw: List[Tuple[float, float, float]] = []
    mags: List[float] = []
    for ri in range(rows):
        for ci in range(cols):
            c = min(grid - 1, max(0, int((ci + 0.5) * grid / cols)))
            r = min(grid - 1, max(0, int((ri + 0.5) * grid / rows)))
            ux, uy = float(up_x[r * grid + c]), float(up_y[r * grid + c])
            mag = math.hypot(ux, uy)
            # rotate 90°: the horizon is orthogonal to the local vertical
            raw.append((-uy, ux, mag))
            mags.append(mag)

    peak = max(mags) if mags else 0.0
    if peak <= 1e-12:
        return [], 0, 0
    cells: List[List[float]] = []
    for hx, hy, mag in raw:
        if mag <= 1e-12:
            cells.append([0.0, 0.0, 0.0])                # the model said nothing here
            continue
        ux, uy = hx / mag, hy / mag
        if ux < 0:                                       # axial: canonicalise the sign away
            ux, uy = -ux, -uy
        cells.append([round(ux, 4), round(uy, 4), round(mag / peak, 4)])
    return cells, rows, cols
