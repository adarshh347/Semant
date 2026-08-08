"""Overlay and contact sheet — so a reviewer can answer the question the harness cannot.

Every automated number in `score.measured` is compatible with a mask of the wrong thing. The
only instrument that settles concept binding is a person looking at the picture, and a person
cannot look at an RLE. These images are therefore not a nicety attached to the run; they are
the apparatus for the half of the score the machine is forbidden to fill in.

Drawn with PIL alone. No matplotlib, no colormap dependency: a research artifact that needs a
plotting stack installed to be regenerated is one environment change away from unreproducible.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: Distinct hues, in a fixed order. Fixed so instance 0 is the same colour in the overlay and in
#: the contact sheet — a reviewer matching "the second mask" between two images should not have
#: to count.
PALETTE: Tuple[Tuple[int, int, int], ...] = (
    (255, 92, 92), (92, 176, 255), (126, 217, 87), (255, 196, 61),
    (196, 122, 255), (255, 138, 195), (94, 234, 212), (255, 154, 92),
)

FILL_ALPHA = 90
BOUNDARY_ALPHA = 235


def _decode(rle: Dict[str, Any]) -> Optional[Tuple[bytearray, int, int]]:
    from backend.services.mask_geometry import rle_decode, rle_is_valid
    if not rle_is_valid(rle):
        return None
    return rle_decode(rle)


def _boundary(bits: bytearray, h: int, w: int) -> bytearray:
    """4-connected boundary: a set pixel with at least one unset (or off-image) neighbour.

    Drawn as well as the translucent fill because a fill alone hides exactly what a reviewer is
    being asked to judge — where the mask stops. A loose boundary and a clean one look identical
    under 35% alpha.
    """
    edge = bytearray(h * w)
    for r in range(h):
        base = r * w
        for c in range(w):
            if not bits[base + c]:
                continue
            if (r == 0 or c == 0 or r == h - 1 or c == w - 1
                    or not bits[base - w + c] or not bits[base + w + c]
                    or not bits[base + c - 1] or not bits[base + c + 1]):
                edge[base + c] = 1
    return edge


def render_overlay(image_path: str, instances: Sequence[Dict[str, Any]], out_path: str,
                   ) -> Optional[str]:
    """The original image with every mask's fill and boundary. Returns the path, or None when
    there is nothing to draw — an empty result gets no overlay rather than a copy of the
    original masquerading as one."""
    masks = [(i, inst.get("mask_rle")) for i, inst in enumerate(instances)
             if isinstance(inst.get("mask_rle"), dict)]
    if not masks:
        return None
    from PIL import Image

    base = Image.open(image_path).convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    px = layer.load()
    iw, ih = base.size

    for order, (idx, rle) in enumerate(masks):
        decoded = _decode(rle)
        if decoded is None:
            continue
        bits, h, w = decoded
        colour = PALETTE[order % len(PALETTE)]
        edge = _boundary(bits, h, w)
        # The mask is at the model's working resolution, the image at its own. Nearest-neighbour
        # by index rather than resizing the mask: a resampled mask would smooth the very
        # boundary the reviewer is looking at.
        for y in range(ih):
            sr = min(h - 1, y * h // ih)
            row = sr * w
            for x in range(iw):
                sc = min(w - 1, x * w // iw)
                if edge[row + sc]:
                    px[x, y] = (*colour, BOUNDARY_ALPHA)
                elif bits[row + sc]:
                    prev = px[x, y]
                    if prev[3] == 0:
                        px[x, y] = (*colour, FILL_ALPHA)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    Image.alpha_composite(base, layer).convert("RGB").save(out_path)
    return out_path


def render_contact_sheet(image_path: str, instances: Sequence[Dict[str, Any]], out_path: str,
                         *, cell: int = 320) -> Optional[str]:
    """One panel per instance, each showing that mask ALONE over the image.

    Only when there is more than one instance, because with one the overlay already is the
    contact sheet. The per-instance view exists because overlapping masks in a single overlay
    cannot be told apart, and "how many distinct things did it find" is precisely what a reader
    takes `instance_count` to mean.
    """
    masks = [(i, inst) for i, inst in enumerate(instances)
             if isinstance(inst.get("mask_rle"), dict)]
    if len(masks) < 2:
        return None
    from PIL import Image, ImageDraw

    base = Image.open(image_path).convert("RGBA")
    iw, ih = base.size
    scale = min(cell / iw, cell / ih)
    tw, th = max(1, int(iw * scale)), max(1, int(ih * scale))
    cols = min(4, len(masks))
    rows = (len(masks) + cols - 1) // cols
    label_h = 22
    sheet = Image.new("RGB", (cols * tw, rows * (th + label_h)), (18, 18, 20))
    draw = ImageDraw.Draw(sheet)

    for n, (idx, inst) in enumerate(masks):
        panel = base.resize((tw, th))
        layer = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        decoded = _decode(inst["mask_rle"])
        if decoded is not None:
            bits, h, w = decoded
            colour = PALETTE[n % len(PALETTE)]
            edge = _boundary(bits, h, w)
            lp = layer.load()
            for y in range(th):
                sr = min(h - 1, y * h // th)
                row = sr * w
                for x in range(tw):
                    sc = min(w - 1, x * w // tw)
                    if edge[row + sc]:
                        lp[x, y] = (*colour, BOUNDARY_ALPHA)
                    elif bits[row + sc]:
                        lp[x, y] = (*colour, FILL_ALPHA)
        panel = Image.alpha_composite(panel, layer).convert("RGB")
        cx, cy = (n % cols) * tw, (n // cols) * (th + label_h)
        sheet.paste(panel, (cx, cy))
        conf = inst.get("confidence")
        # The confidence is printed and the caption says what it is about. It is the NAMING's
        # confidence, not the mask's, and a reviewer who reads it as a quality score for the
        # geometry is reading it exactly backwards.
        caption = (f"#{idx}  naming conf "
                   f"{'—' if conf is None else f'{float(conf):.2f}'}")
        draw.text((cx + 6, cy + th + 4), caption, fill=(226, 226, 230))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    sheet.save(out_path)
    return out_path
