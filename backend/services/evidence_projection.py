"""
VISION-E · E1 — canonical evidence projections.

Two deterministic visual projections of a Region's *confirmed evidence*, produced through the
one geometry owner (`mask_geometry`, Increment A):

  · **identity crop** — the exact mask, composited over a neutral background, with deterministic
    padding. This is "what the evidence IS", isolated from its surroundings.
  · **context crop** — the same evidence with a controlled amount of surrounding image context,
    recording where the target mask sits inside the crop. This is "what the evidence is AMONG".

Rules honoured:
  · when an authoritative `mask_rle` exists it is used — never a bbox-only crop;
  · a Region that carries only a legacy `box` (no mask) still projects honestly, tagged
    `source="box-legacy"` in provenance, so the loss of the exact mask is explicit, not hidden;
  · the projection is a pure function of the *evidence* (source pixels + mask + crop params),
    so its hash is deterministic and a geometry change moves it — while a semantic label or
    note change touches nothing here.

Projections are disposable, rebuildable artifacts of the evidence; the mask stays the identity.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

from backend.services import mask_geometry as mg
from backend.services.region_embedding_service import mask_hash as _mask_hash

CROP_VERSION = "evidence-crop-v1"
IDENTITY_PAD = 0.12        # deterministic padding, as a fraction of the bbox's longer side
CONTEXT_SCALE = 1.8        # the bbox is grown to this multiple to admit surrounding context
NEUTRAL_BG = (127, 127, 127)


def _px_box(box: dict, iw: int, ih: int):
    l = int(round(box["x"] * iw)); t = int(round(box["y"] * ih))
    r = int(round((box["x"] + box["w"]) * iw)); b = int(round((box["y"] + box["h"]) * ih))
    return l, t, r, b


def _expand(l: int, t: int, r: int, b: int, iw: int, ih: int, *,
            scale: float = 1.0, pad_frac: float = 0.0):
    """Grow a pixel box about its centre by `scale`, then pad by `pad_frac` of its longer side,
    and clamp to the image. Deterministic (integer rounding), edge-safe."""
    cx = (l + r) / 2.0; cy = (t + b) / 2.0
    bw = (r - l) * scale; bh = (b - t) * scale
    pad = pad_frac * max(r - l, b - t)
    nl = int(round(cx - bw / 2 - pad)); nr = int(round(cx + bw / 2 + pad))
    nt = int(round(cy - bh / 2 - pad)); nb = int(round(cy + bh / 2 + pad))
    nl = max(0, min(nl, iw - 1)); nt = max(0, min(nt, ih - 1))
    nr = max(nl + 1, min(nr, iw)); nb = max(nt + 1, min(nb, ih))
    return nl, nt, nr, nb


def _alpha_from_rle(rle: dict, iw: int, ih: int):
    """Full-image L mask (255 inside evidence), nearest-neighbour scaled from the mask's own
    [h,w] to the image — mask and image need not share resolution."""
    from PIL import Image
    bits, h, w = mg.rle_decode(rle)
    try:
        import numpy as np
        arr = np.frombuffer(bytes(bits), dtype=np.uint8).reshape(h, w)
        ys = np.minimum(np.arange(ih) * h // ih, h - 1)
        xs = np.minimum(np.arange(iw) * w // iw, w - 1)
        scaled = (arr[ys][:, xs] * 255).astype("uint8")
        return Image.fromarray(scaled, "L")
    except Exception:
        a = Image.new("L", (iw, ih), 0); px = a.load()
        for yy in range(ih):
            my = min(h - 1, yy * h // ih)
            for xx in range(iw):
                if bits[my * w + min(w - 1, xx * w // iw)]:
                    px[xx, yy] = 255
        return a


def _hash(role: str, source: str, img) -> str:
    """Deterministic content hash of a projection — role + crop version + source pixels. A
    geometry change moves the pixels and thus the hash; a label/note change cannot."""
    h = hashlib.sha256()
    h.update(role.encode()); h.update(CROP_VERSION.encode()); h.update(source.encode())
    h.update(str(img.size).encode())
    h.update(img.convert("RGB").tobytes())
    return h.hexdigest()


def project_region(region: dict, image, *, source_content_hash: Optional[str] = None
                   ) -> Optional[Dict[str, Any]]:
    """Return the identity and context projections of `region`'s evidence over PIL `image`,
    or None if the region carries neither a mask nor a box. Each projection is
    `{role, image (PIL RGB), box, target_mask_box?, source, provenance, projection_hash}`."""
    iw, ih = image.size
    rle = region.get("mask_rle")
    has_mask = mg.rle_is_valid(rle)
    if has_mask:
        box = mg.rle_bbox_norm(rle); source = "mask"; mh = _mask_hash(rle)
    else:
        box = region.get("box"); source = "box-legacy"; mh = ""
        if not box:
            return None
    l, t, r, b = _px_box(box, iw, ih)

    base_prov = {
        "crop_version": CROP_VERSION, "source": source, "identity_pad": IDENTITY_PAD,
        "context_scale": CONTEXT_SCALE, "image_size": [iw, ih], "mask_hash": mh,
        "geometry_rev": region.get("geometry_rev"),
        "source_content_hash": source_content_hash,
    }

    # ── identity: exact mask over neutral bg, deterministically padded ──
    il, it, ir, ib = _expand(l, t, r, b, iw, ih, scale=1.0, pad_frac=IDENTITY_PAD)
    if has_mask:
        alpha = _alpha_from_rle(rle, iw, ih)
        rgba = image.convert("RGBA"); rgba.putalpha(alpha)
        from PIL import Image
        cut = rgba.crop((il, it, ir, ib))
        identity_img = Image.new("RGB", cut.size, NEUTRAL_BG)
        identity_img.paste(cut, mask=cut.split()[-1])
    else:
        # honest box-only fallback: no mask to isolate, so the padded box is the best we have
        identity_img = image.convert("RGB").crop((il, it, ir, ib))

    # ── context: surrounding context, with the target mask's box recorded ──
    cl, ct, cr, cb = _expand(l, t, r, b, iw, ih, scale=CONTEXT_SCALE, pad_frac=0.0)
    context_img = image.convert("RGB").crop((cl, ct, cr, cb))
    cw = cr - cl; ch = cb - ct
    target_mask_box = {"x": (l - cl) / cw, "y": (t - ct) / ch,
                       "w": (r - l) / cw, "h": (b - t) / ch}

    return {
        "identity": {
            "role": "identity", "image": identity_img, "box": box, "source": source,
            "provenance": {**base_prov, "role": "identity", "pad_frac": IDENTITY_PAD},
            "projection_hash": _hash("identity", source, identity_img),
        },
        "context": {
            "role": "context", "image": context_img, "box": box, "source": source,
            "target_mask_box": target_mask_box,
            "provenance": {**base_prov, "role": "context", "target_mask_box": target_mask_box},
            "projection_hash": _hash("context", source, context_img),
        },
    }
