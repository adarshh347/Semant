"""
Canonical Region geometry (REGION-GEOMETRY-001).

ONE coordinate contract at the persistence boundary and everywhere downstream:

    a box is {"x","y","w","h"}, NORMALIZED to [0,1] against the SOURCE image's
    natural pixels, ORIGIN top-left, (x,y) = top-left corner, (w,h) = size.

Model-specific frames (pixel xyxy, pixel xywh, a resized/letterboxed inference
canvas) are converted to this contract EXACTLY ONCE, before persistence. Crops,
overlays, Differential Grounds, and recall all consume boxes already in this
contract — they must never re-derive coordinates from rendered/container sizes.

The bug this module exists to prevent: a fine part being force-clipped into a
coarse anchor it does not actually belong to. On an under-segmented image (one
`person` anchor for five sculptures) that silently relocates parts onto the wrong
figure and crushes off-anchor parts to degenerate slivers. Parenting is therefore
GEOMETRY-first here — a label hint never overrides where a box actually is.
"""

from typing import Optional

MIN_SIZE = 0.01  # a box narrower/shorter than this is treated as degenerate


def clamp01(v) -> float:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


def normalize_box(box: dict) -> dict:
    """Clamp a normalized box into the unit frame (x+w ≤ 1, y+h ≤ 1), rounded."""
    x, y = clamp01(box.get("x")), clamp01(box.get("y"))
    w, h = clamp01(box.get("w")), clamp01(box.get("h"))
    if x + w > 1.0:
        w = 1.0 - x
    if y + h > 1.0:
        h = 1.0 - y
    return {"x": round(x, 4), "y": round(y, 4),
            "w": round(max(w, 0.0), 4), "h": round(max(h, 0.0), 4)}


# ── model-frame → canonical conversions (do these ONCE, before persistence) ──

def xyxy_to_xywh(x0, y0, x1, y1) -> dict:
    return {"x": min(x0, x1), "y": min(y0, y1),
            "w": abs(x1 - x0), "h": abs(y1 - y0)}


def pixels_to_normalized(box_px: dict, width: int, height: int) -> dict:
    """A pixel-space {x,y,w,h} in the SOURCE image → normalized. `width`/`height`
    MUST be the source image's natural size, never a rendered/crop/inference size."""
    if not width or not height:
        return {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0}
    return normalize_box({
        "x": box_px["x"] / width, "y": box_px["y"] / height,
        "w": box_px["w"] / width, "h": box_px["h"] / height,
    })


def unletterbox_normalized(box_letterboxed: dict, orig_w: int, orig_h: int,
                           canvas: int) -> dict:
    """Invert a square letterboxed inference canvas back to the original aspect.

    A prediction normalized against a `canvas`×`canvas` square (the image resized
    to fit with padding) → normalized against the ORIGINAL image. The padding sits
    on the short side; removing it and rescaling is the step whose omission is
    hypothesis #1. If the producer already returns original-frame coords, DON'T
    call this — double-correcting is its own bug.
    """
    if not orig_w or not orig_h or not canvas:
        return normalize_box(box_letterboxed)
    scale = canvas / max(orig_w, orig_h)          # fit-longest-side
    scaled_w, scaled_h = orig_w * scale, orig_h * scale
    pad_x = (canvas - scaled_w) / 2.0
    pad_y = (canvas - scaled_h) / 2.0
    # canvas-normalized → canvas pixels → remove pad → original pixels → normalized
    px = box_letterboxed["x"] * canvas - pad_x
    py = box_letterboxed["y"] * canvas - pad_y
    pw = box_letterboxed["w"] * canvas
    ph = box_letterboxed["h"] * canvas
    return normalize_box({
        "x": px / scaled_w, "y": py / scaled_h,
        "w": pw / scaled_w, "h": ph / scaled_h,
    })


# ── geometry ─────────────────────────────────────────────────────────────────

def box_area(b: dict) -> float:
    return max(0.0, b.get("w", 0.0)) * max(0.0, b.get("h", 0.0))


def is_degenerate(b: dict, min_size: float = MIN_SIZE) -> bool:
    return b.get("w", 0.0) < min_size or b.get("h", 0.0) < min_size


def overlap_fraction(inner: dict, outer: dict) -> float:
    """Fraction of `inner`'s area that lies inside `outer` (0..1)."""
    ix0, iy0 = inner.get("x", 0.0), inner.get("y", 0.0)
    ix1, iy1 = ix0 + inner.get("w", 0.0), iy0 + inner.get("h", 0.0)
    ox0, oy0 = outer.get("x", 0.0), outer.get("y", 0.0)
    ox1, oy1 = ox0 + outer.get("w", 0.0), oy0 + outer.get("h", 0.0)
    iw = max(0.0, min(ix1, ox1) - max(ix0, ox0))
    ih = max(0.0, min(iy1, oy1) - max(iy0, oy0))
    inter = iw * ih
    area = box_area(inner)
    return inter / area if area > 0 else 0.0


def center_in(box: dict, outer: dict) -> bool:
    cx = box.get("x", 0.0) + box.get("w", 0.0) / 2
    cy = box.get("y", 0.0) + box.get("h", 0.0) / 2
    ox0, oy0 = outer.get("x", 0.0), outer.get("y", 0.0)
    return ox0 <= cx <= ox0 + outer.get("w", 0.0) and oy0 <= cy <= oy0 + outer.get("h", 0.0)


# ── parenting (geometry-first) ───────────────────────────────────────────────

MIN_PARENT_OVERLAP = 0.5   # a part must be at least half inside an anchor to be its child


def match_parent(fine_box: dict, anchors: list, parent_label: str = "",
                 min_overlap: float = MIN_PARENT_OVERLAP) -> Optional[dict]:
    """The anchor a fine part GEOMETRICALLY belongs to, or None.

    A part is a child only when it is genuinely (≥ min_overlap) inside an anchor.
    A matching label is a tie-breaker AMONG qualifying anchors — never a way to
    adopt a part that lies outside every anchor. This is what stops an
    under-segmented image from sucking every part into the one anchor it has.
    """
    plabel = (parent_label or "").lower().strip()
    best, best_score = None, 0.0
    for a in anchors:
        abox = a.get("box") or {}
        frac = overlap_fraction(fine_box, abox)
        if frac < min_overlap:
            continue
        alabel = (a.get("label") or "").lower()
        label_hit = bool(plabel) and (plabel in alabel or alabel in plabel)
        # prefer the tightest genuine container; nudge ties toward a label match
        score = frac + (0.25 if label_hit else 0.0) - 0.05 * box_area(abox)
        if score > best_score:
            best, best_score = a, score
    return best


def clip_box_to_parent(box: dict, parent: dict, pad: float = 0.04,
                       min_size: float = MIN_SIZE) -> dict:
    """Nudge a fine box inside its parent (padded). Safe ONLY for a genuine child
    (see `match_parent`): a box mostly inside its parent is only trimmed at the
    overflow, never crushed. As a backstop, if clipping would drive the box
    degenerate the ORIGINAL box is kept — geometry is never silently destroyed.
    """
    px, py = parent.get("x", 0.0), parent.get("y", 0.0)
    pw, ph = parent.get("w", 1.0), parent.get("h", 1.0)
    x0, y0 = max(0.0, px - pad), max(0.0, py - pad)
    x1, y1 = min(1.0, px + pw + pad), min(1.0, py + ph + pad)
    bx = min(max(box["x"], x0), x1)
    by = min(max(box["y"], y0), y1)
    bw = min(box["w"], x1 - bx)
    bh = min(box["h"], y1 - by)
    clipped = {"x": round(bx, 4), "y": round(by, 4),
               "w": round(bw, 4), "h": round(bh, 4)}
    if is_degenerate(clipped, min_size):
        return normalize_box(box)  # refuse to crush — keep the honest box
    return clipped
