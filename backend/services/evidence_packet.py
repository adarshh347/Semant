"""
VISION-D · D1 — the evidence packet.

One canonical VLM input built from existing evidence: the whole image, a numbered mask
CONTACT SHEET (each candidate mask outlined + numbered on the image), stable candidate IDs,
profile + model provenance, curator labels/notes marked AUTHORITATIVE, and a compact
request intent. The VLM sees enough to interpret the masks — but the packet gives it no
permission to redefine them (geometry lives only in the Regions; the schema forbids it).

Numbering is deterministic (candidates sorted by id) so it SURVIVES retries + caching:
number N always maps to the same candidate_id for the same region set.
"""
from __future__ import annotations

import base64
import hashlib
import io
from typing import Any, Dict, List, Optional

_MAX_DIM = 768


def _b64_jpeg(img, quality: int = 82) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def _rings_of(region: dict) -> List[list]:
    polys = region.get("polygons")
    if isinstance(polys, list) and polys:
        return [r for r in polys if isinstance(r, list) and len(r) >= 2]
    poly = region.get("polygon")
    if isinstance(poly, list) and len(poly) >= 2:
        return [poly]
    return []


def _centroid_norm(region: dict) -> tuple:
    b = region.get("box") or {}
    return (b.get("x", 0) + b.get("w", 0) / 2, b.get("y", 0) + b.get("h", 0) / 2)


def build_packet(post: dict, image_bytes: bytes, *, intent: str = "name",
                 max_dim: int = _MAX_DIM) -> Dict[str, Any]:
    """Assemble the packet. `intent` is a compact request: name | material | relate |
    compose | describe. Returns image + contact sheet (base64), candidates, allowed_ids,
    stable numbering, profile, and a prompt."""
    from PIL import Image, ImageDraw

    regions = sorted((post.get("region_annotations") or []), key=lambda r: str(r.get("id", "")))
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    W, H = img.size
    scale = min(1.0, max_dim / max(W, H))
    small = img.resize((max(1, int(W * scale)), max(1, int(H * scale))))
    sw, sh = small.size

    sheet = small.copy()
    d = ImageDraw.Draw(sheet, "RGBA")
    candidates: List[Dict[str, Any]] = []
    numbering: Dict[str, int] = {}

    for i, r in enumerate(regions, 1):
        cid = str(r.get("id"))
        numbering[cid] = i
        # outline the mask (or box) so the VLM can see which candidate N refers to
        rings = _rings_of(r)
        if rings:
            for ring in rings:
                pts = [(x * sw, y * sh) for x, y in ring]
                if len(pts) >= 2:
                    d.line(pts + [pts[0]], fill=(255, 90, 90, 255), width=2)
        else:
            b = r.get("box") or {}
            d.rectangle([b.get("x", 0) * sw, b.get("y", 0) * sh,
                         (b.get("x", 0) + b.get("w", 0)) * sw, (b.get("y", 0) + b.get("h", 0)) * sh],
                        outline=(255, 90, 90, 255), width=2)
        # numbered badge at the centroid
        cx, cy = _centroid_norm(r)
        px, py = cx * sw, cy * sh
        rad = 10
        d.ellipse([px - rad, py - rad, px + rad, py + rad], fill=(30, 10, 25, 235))
        d.text((px - (4 if i < 10 else 7), py - 6), str(i), fill=(255, 255, 255, 255))

        is_creator = r.get("actor") == "creator"
        candidates.append({
            "n": i,
            "candidate_id": cid,
            "detector": r.get("detector"),
            "category": r.get("category"),
            "auto_label": r.get("label") or None,
            # curator label/note are AUTHORITATIVE — the VLM must not overwrite them.
            "curator_label": (r.get("label") if is_creator else None),
            "curator_note": (r.get("user_note") or None),
            "authoritative": bool(is_creator or (r.get("user_note") or "").strip()),
            "provenance": (r.get("geometry_provenance") or {}).get("adapter"),
            "confidence": r.get("confidence"),
        })

    packet = {
        "image_b64": _b64_jpeg(small),
        "contact_sheet_b64": _b64_jpeg(sheet),
        "candidates": candidates,
        "allowed_ids": [c["candidate_id"] for c in candidates],
        "numbering": numbering,                       # stable: id → number
        "profile": post.get("domain_profile"),
        "intent": intent,
        "image_hash": hashlib.sha256(image_bytes).hexdigest(),
    }
    packet["prompt"] = build_prompt(packet)
    return packet


def build_prompt(packet: Dict[str, Any]) -> str:
    """A compact prompt: interpret the numbered candidates by id, never invent geometry,
    never overwrite authoritative curator labels."""
    profile = packet.get("profile") or {}
    chosen = ", ".join(profile.get("chosen", ["general"]))
    lines = [
        "You are a careful visual reader. You are given the whole image and a CONTACT SHEET",
        "where each candidate mask is outlined in red and numbered. Interpret ONLY these",
        f"candidates (domain profile: {chosen}). Candidate N maps to candidate_id:",
    ]
    for c in packet["candidates"]:
        auth = ""
        if c.get("curator_label") or c.get("curator_note"):
            auth = f"  [AUTHORITATIVE curator: {c.get('curator_label') or ''} {('· ' + c['curator_note']) if c.get('curator_note') else ''}]".rstrip()
        lines.append(f"  {c['n']}. id={c['candidate_id']} (auto: {c.get('auto_label') or '?'}"
                     f", {c.get('detector') or '?'}){auth}")
    lines += [
        "",
        "RULES: (1) reference candidates ONLY by the ids above — never invent ids or move a",
        "label to a distant candidate. (2) Output NO geometry: no coordinates, boxes,",
        "polygons, masks or sizes. (3) Do NOT overwrite an AUTHORITATIVE curator label —",
        "you may add alternatives/uncertainty, not replace it. (4) If the automatic",
        "candidates are insufficient (e.g. a painting), say so via needs_better_evidence.",
        "",
        f"Request intent: {packet['intent']}. Return the semantic JSON schema: per-candidate",
        "label + ranked_alternatives + part/material/attributes/style + confidence +",
        "uncertainty; relation proposals citing candidate ids; and an image-global reading",
        "(composition/atmosphere/colour/scene) that is NOT an object mask.",
    ]
    return "\n".join(lines)
