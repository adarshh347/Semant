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
