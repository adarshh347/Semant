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
from typing import List, Optional, Sequence, Tuple

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
