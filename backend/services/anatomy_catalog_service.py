"""
Anatomy Catalog Service — scaling per-image region annotations into cross-image
category knowledge. Aggregates region_annotations across all posts, groups by
normalized category + label, computes occurrence/intensity stats, and synthesises
LLM-generated insights about why certain categories consistently affect the curator.

Implements Issue #9: scaling anatomy-based annotation of categories.
"""

import re
from typing import Optional
from backend.database import post_collection, anatomy_catalog_collection
from backend.services.llm_service import llm_service
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Label normalisation — ensures "Neckline", "neckline", "neck line" merge.
# ---------------------------------------------------------------------------
_STRIP_RE = re.compile(r"[_\-]+")
_MULTI_SPACE = re.compile(r"\s{2,}")


def normalize_label(label: str) -> str:
    """Lowercase, collapse whitespace/dashes/underscores, singularise naively."""
    s = (label or "").strip().lower()
    s = _STRIP_RE.sub(" ", s)
    s = _MULTI_SPACE.sub(" ", s)
    # Naïve singular: strip trailing 's' only when word is >4 chars and ends in 's'
    # (avoids "dress" → "dres" but catches "necklines" → "neckline").
    parts = s.split()
    out = []
    for p in parts:
        if len(p) > 4 and p.endswith("s") and not p.endswith("ss"):
            p = p[:-1]
        out.append(p)
    return " ".join(out)


def normalize_category(cat: str) -> str:
    """Normalise the category tag (lowercase, strip whitespace)."""
    return (cat or "other").strip().lower()


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

async def aggregate_categories(
    genre_tag: Optional[str] = None,
    handle: Optional[str] = None,
    min_occurrences: int = 1,
) -> list:
    """
    Walk every post's `region_annotations`, group by normalised (category, label),
    and compute statistics for each group.

    Optional filters:
      - genre_tag: only posts tagged with this general_tag (e.g. "fashion").
      - handle: only posts from this Instagram account.

    Returns a list of dicts sorted by total_intensity descending:
      [{category, label, occurrence_count, prioritised_count, avg_intensity,
        total_intensity, notes[], sample_images[], materials[]}]
    """
    query: dict = {"region_annotations": {"$exists": True, "$ne": None}}
    if genre_tag:
        query["general_tags"] = genre_tag
    if handle:
        h = handle.strip().lower().lstrip("@")
        query["$or"] = [
            {"instagram_handle": h},
            {"source_url": {"$regex": rf"instagram\.com/{re.escape(h)}(?:[/?#]|$)", "$options": "i"}},
        ]

    buckets: dict = {}  # key = (normalised_category, normalised_label)

    cursor = post_collection.find(
        query,
        {"_id": 1, "photo_url": 1, "region_annotations": 1, "general_tags": 1},
    )
    async for post in cursor:
        post_id = str(post["_id"])
        for r in (post.get("region_annotations") or []):
            cat = normalize_category(r.get("category", "other"))
            label = normalize_label(r.get("label", ""))
            if not label:
                continue
            key = (cat, label)
            bucket = buckets.setdefault(key, {
                "category": cat,
                "label": label,
                "occurrence_count": 0,
                "prioritised_count": 0,
                "total_intensity": 0,
                "notes": [],
                "materials": set(),
                "sample_images": [],  # (post_id, photo_url) pairs
            })
            bucket["occurrence_count"] += 1
            if r.get("prioritised"):
                bucket["prioritised_count"] += 1
                bucket["total_intensity"] += (r.get("weight") or 0)
            note = (r.get("user_note") or "").strip()
            if note and note not in bucket["notes"]:
                bucket["notes"].append(note)
            mat = (r.get("material") or "").strip().lower()
            if mat:
                bucket["materials"].add(mat)
            # Keep a handful of sample images.
            if len(bucket["sample_images"]) < 6:
                entry = {"post_id": post_id, "photo_url": post.get("photo_url")}
                if entry not in bucket["sample_images"]:
                    bucket["sample_images"].append(entry)

    # Build output list.
    result = []
    for (cat, label), b in buckets.items():
        if b["occurrence_count"] < min_occurrences:
            continue
        avg = round(b["total_intensity"] / b["prioritised_count"], 1) if b["prioritised_count"] else 0
        result.append({
            "category": cat,
            "label": label,
            "occurrence_count": b["occurrence_count"],
            "prioritised_count": b["prioritised_count"],
            "avg_intensity": avg,
            "total_intensity": b["total_intensity"],
            "notes": b["notes"][:20],   # cap
            "materials": sorted(b["materials"]),
            "sample_images": b["sample_images"],
        })

    # Sort: prioritised_count desc, then total_intensity desc.
    result.sort(key=lambda x: (x["prioritised_count"], x["total_intensity"]), reverse=True)
    return result


async def get_top_categories(n: int = 10, genre_tag: Optional[str] = None) -> list:
    """Return the top-N most-affecting categories (by prioritised_count)."""
    full = await aggregate_categories(genre_tag=genre_tag, min_occurrences=1)
    return full[:n]


# ---------------------------------------------------------------------------
# LLM insight synthesis
# ---------------------------------------------------------------------------

async def synthesize_insights(
    genre_tag: Optional[str] = None,
    handle: Optional[str] = None,
) -> dict:
    """
    Run the LLM over the aggregated category profile to produce a
    natural-language 'anatomy language' — a synthesised paragraph
    describing what the curator consistently notices and responds to.

    Returns: {portrait, per_category: [{label, insight}], updated_at}
    """
    profile = await aggregate_categories(genre_tag=genre_tag, handle=handle)
    if not profile:
        return {"portrait": "Not enough anatomy data yet.", "per_category": [], "updated_at": datetime.now(timezone.utc)}

    # Build a summary string for the LLM.
    lines = []
    for p in profile[:20]:
        line = f"- {p['label']} ({p['category']}): seen {p['occurrence_count']}×, starred {p['prioritised_count']}×, avg intensity {p['avg_intensity']}"
        if p["notes"]:
            line += f' — notes: "{"; ".join(p["notes"][:3])}"'
        if p["materials"]:
            line += f" — materials: {', '.join(p['materials'][:3])}"
        lines.append(line)
    profile_text = "\n".join(lines)

    result = llm_service.synthesize_anatomy_language(profile_text, genre_tag)

    # Save to the catalog collection for caching.
    doc = {
        "genre_tag": genre_tag,
        "handle": handle,
        "portrait": result.get("portrait", ""),
        "per_category": result.get("per_category", []),
        "profile_snapshot": profile[:20],
        "updated_at": datetime.now(timezone.utc),
    }
    await anatomy_catalog_collection.update_one(
        {"genre_tag": genre_tag, "handle": handle},
        {"$set": doc},
        upsert=True,
    )
    return doc


async def get_cached_insights(
    genre_tag: Optional[str] = None,
    handle: Optional[str] = None,
) -> Optional[dict]:
    """Return cached insights if available."""
    doc = await anatomy_catalog_collection.find_one(
        {"genre_tag": genre_tag, "handle": handle},
        {"_id": 0},
    )
    return doc


async def get_images_for_category(category: str, label: str, limit: int = 50) -> list:
    """
    Return all posts that have a region_annotation matching the given
    normalised category + label. Each result includes the post id, photo_url,
    and the specific matching region data.
    """
    norm_cat = normalize_category(category)
    norm_label = normalize_label(label)

    cursor = post_collection.find(
        {"region_annotations": {"$exists": True, "$ne": None}},
        {"_id": 1, "photo_url": 1, "region_annotations": 1, "general_tags": 1, "instagram_handle": 1},
    ).limit(500)  # scan limit

    results = []
    async for post in cursor:
        for r in (post.get("region_annotations") or []):
            rc = normalize_category(r.get("category", "other"))
            rl = normalize_label(r.get("label", ""))
            if rc == norm_cat and rl == norm_label:
                results.append({
                    "post_id": str(post["_id"]),
                    "photo_url": post.get("photo_url"),
                    "general_tags": post.get("general_tags", []),
                    "instagram_handle": post.get("instagram_handle"),
                    "region": {
                        "label": r.get("label"),
                        "category": r.get("category"),
                        "prioritised": r.get("prioritised", False),
                        "weight": r.get("weight", 0),
                        "user_note": r.get("user_note", ""),
                        "material": r.get("material", ""),
                        "box": r.get("box"),
                    },
                })
                break  # one match per post is enough
        if len(results) >= limit:
            break

    return results
