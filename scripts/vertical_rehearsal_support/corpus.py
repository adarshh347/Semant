"""
The fixed corpus. Synthetic by construction: every image is rendered from its manifest row at run
time with Pillow, so the repository holds no binaries and two runs see byte-identical pixels. The
marks on each image are KNOWN — they are the lines the renderer drew — which is what lets the audit
say "this relation rests on that mark" rather than trusting a producer.

Never a production post. Every document this module writes carries `photo_public_id` =
`FIXTURE_PUBLIC_ID`, and it is only ever written to the disposable mongod the harness started.

An optional real-photo profile (`--profile real-photo`) reads `SEMANT_VERTICAL_REAL_PHOTOS`, a
directory of the author's own licensed images with a `marks.json` beside them. It is opt-in, never
committed, and the run record says which profile ran.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from bson import ObjectId

FIXTURE_PUBLIC_ID = "vertical-rehearsal-fixture"
HANDLE_PREFIX = "vr_"

_ROLES = ("gesture_line", "contour_edge", "light_edge", "shadow_edge")
_PALETTE = [(214, 196, 168), (168, 184, 214), (190, 214, 168), (214, 168, 184),
            (204, 204, 204), (168, 214, 206), (214, 206, 168), (184, 168, 214)]

SIZE = 512


def core_manifest() -> List[Dict[str, Any]]:
    """Eight readable images with known marks, one marked image with NO marks (so a refusal can be
    shown beside a relation), and one whose image cannot be fetched (the unreadable profile)."""
    rows: List[Dict[str, Any]] = []
    for i in range(8):
        rows.append({"key": f"core-{i}", "title": f"{HANDLE_PREFIX}walk_{i}", "seed": i,
                     "marks": 2, "readable": True})
    rows.append({"key": "core-unmarked", "title": f"{HANDLE_PREFIX}unmarked", "seed": 40,
                 "marks": 0, "readable": True})
    rows.append({"key": "core-unreadable", "title": f"{HANDLE_PREFIX}unreadable", "seed": 41,
                 "marks": 1, "readable": False})
    return rows


def perf_manifest(n: int = 60) -> List[Dict[str, Any]]:
    return [{"key": f"perf-{i}", "title": f"{HANDLE_PREFIX}perf_{i}", "seed": 100 + i,
             "marks": 1, "readable": True} for i in range(n)]


def mark_for(seed: int, index: int) -> Dict[str, Any]:
    """The known mark: the line the renderer draws at the same coordinates."""
    role = _ROLES[(seed + index) % len(_ROLES)]
    y = 0.22 + 0.14 * ((seed + index) % 4)
    return {
        "id": f"vm_vr_{seed}_{index}",
        "type": "trace_mark",
        "role": role,
        "label": f"fixture {role.replace('_', ' ')} {seed}",
        "source": "user_confirmed",
        "status": "committed",
        "source_ref": f"vm_vr_{seed}_{index}",
        "geometry": {"kind": "path",
                     "points": [[0.12, round(y, 3)], [0.88, round(y + 0.08, 3)]]},
        "linked_ground_ids": [],
        "warnings": [],
    }


def region_for(seed: int) -> Dict[str, Any]:
    """One committed region per image, the box the renderer fills. Gives the single-image
    Director a region to seed from without running a segmenter."""
    x = 0.15 + 0.05 * (seed % 5)
    return {"id": f"rg_vr_{seed}_0", "geometry_rev": 0, "source": "user_confirmed",
            "status": "committed", "label": "fixture block",
            "box": {"x": round(x, 3), "y": 0.55, "w": 0.35, "h": 0.3}, "mask_rle": None}


def render_png(row: Dict[str, Any], out: Path) -> Path:
    """Deterministic: same manifest row → same bytes. Pillow only, no fonts, no antialias."""
    from PIL import Image, ImageDraw
    seed = int(row["seed"])
    img = Image.new("RGB", (SIZE, SIZE), _PALETTE[seed % len(_PALETTE)])
    d = ImageDraw.Draw(img)
    box = region_for(seed)["box"]
    d.rectangle([box["x"] * SIZE, box["y"] * SIZE,
                 (box["x"] + box["w"]) * SIZE, (box["y"] + box["h"]) * SIZE],
                fill=(70 + (seed * 13) % 60, 60, 80))
    for m in range(int(row["marks"])):
        pts = mark_for(seed, m)["geometry"]["points"]
        d.line([(p[0] * SIZE, p[1] * SIZE) for p in pts], fill=(20, 20, 20), width=6)
    d.text((12, SIZE - 24), row["key"], fill=(0, 0, 0))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=False)
    return out


def render_all(rows: List[Dict[str, Any]], images_dir: Path) -> Dict[str, str]:
    """Render every row; return key → sha256 of the PNG bytes (the corpus fingerprint)."""
    digests = {}
    for row in rows:
        p = render_png(row, images_dir / f"{row['key']}.png")
        digests[row["key"]] = hashlib.sha256(p.read_bytes()).hexdigest()
    return digests


def post_document(row: Dict[str, Any], image_base_url: str, *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """A post exactly as the app reads one. `readable: False` rows get a URL the image server
    answers 404 for — the backend must then report the node unreadable, not invent pixels."""
    seed = int(row["seed"])
    fname = f"{row['key']}.png" if row.get("readable", True) else f"missing-{row['key']}.png"
    return {
        "_id": ObjectId(),
        "photo_url": f"{image_base_url}/{fname}",
        "photo_public_id": FIXTURE_PUBLIC_ID,
        "updated_at": now or datetime.now(timezone.utc),
        "text_blocks": [],
        "general_tags": ["vertical-rehearsal"],
        "instagram_handle": row["title"],
        "region_annotations": [region_for(seed)],
        "visual_marks": [mark_for(seed, m) for m in range(int(row["marks"]))],
        "grounds": [],
        "percepts": [],
        "fixture": {"harness": "ATLAS-WRITER-MASS-BUILD-001L", "key": row["key"], "seed": seed},
    }


def real_photo_profile() -> Optional[List[Dict[str, Any]]]:
    """The optional marked real-photo profile: `$SEMANT_VERTICAL_REAL_PHOTOS/marks.json` listing
    `{file, title, marks:[...]}`. Returns None (profile unavailable) when unset or unreadable."""
    root = os.environ.get("SEMANT_VERTICAL_REAL_PHOTOS")
    if not root:
        return None
    marks = Path(root) / "marks.json"
    if not marks.is_file():
        return None
    try:
        rows = json.loads(marks.read_text())
    except ValueError:
        return None
    out = []
    for i, r in enumerate(rows):
        src = Path(root) / r["file"]
        if not src.is_file():
            continue
        out.append({"key": f"real-{i}", "title": r.get("title") or f"{HANDLE_PREFIX}real_{i}",
                    "seed": 500 + i, "marks": len(r.get("marks") or []), "readable": True,
                    "source_file": str(src), "explicit_marks": r.get("marks") or []})
    return out or None
