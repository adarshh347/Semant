"""
Anatomy Catalog router — exposes the scaled category profile from Issue #9.
Aggregates region_annotations across posts to surface which anatomical
categories consistently affect the curator, with LLM-synthesised insights.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from backend.services import anatomy_catalog_service

router = APIRouter()


@router.get("/categories")
async def get_categories(
    tag: Optional[str] = Query(None, description="Filter by genre tag (e.g. 'fashion')"),
    handle: Optional[str] = Query(None, description="Filter by Instagram handle"),
    min_occurrences: int = Query(1, ge=1, description="Minimum occurrence count to include"),
):
    """
    Aggregated anatomy category profile across all (or filtered) posts.
    Groups region_annotations by normalised category + label, computes
    occurrence counts, prioritisation counts, and average intensity.
    """
    profile = await anatomy_catalog_service.aggregate_categories(
        genre_tag=tag, handle=handle, min_occurrences=min_occurrences,
    )
    return {"categories": profile, "count": len(profile)}


@router.get("/categories/top")
async def get_top_categories(
    n: int = Query(10, ge=1, le=50, description="Number of top categories to return"),
    tag: Optional[str] = Query(None, description="Filter by genre tag"),
):
    """Top N most-affecting anatomy categories."""
    top = await anatomy_catalog_service.get_top_categories(n=n, genre_tag=tag)
    return {"categories": top, "count": len(top)}


@router.get("/categories/{category}/{label}/images")
async def get_category_images(
    category: str,
    label: str,
    limit: int = Query(50, ge=1, le=200),
):
    """All images containing a specific anatomical category + label."""
    images = await anatomy_catalog_service.get_images_for_category(
        category=category, label=label, limit=limit,
    )
    if not images:
        return {"images": [], "count": 0}
    return {"images": images, "count": len(images)}


@router.post("/synthesize")
async def synthesize_insights(
    tag: Optional[str] = Query(None, description="Genre tag to scope insights"),
    handle: Optional[str] = Query(None, description="Instagram handle to scope"),
):
    """
    Trigger LLM insight synthesis over the anatomy category profile.
    Produces a 'portrait' of the curator's anatomy language and
    per-category insights. Results are cached.
    """
    result = await anatomy_catalog_service.synthesize_insights(
        genre_tag=tag, handle=handle,
    )
    return result


@router.get("/insights")
async def get_insights(
    tag: Optional[str] = Query(None),
    handle: Optional[str] = Query(None),
):
    """Return cached anatomy insights (if available). Use POST /synthesize to generate."""
    cached = await anatomy_catalog_service.get_cached_insights(
        genre_tag=tag, handle=handle,
    )
    if not cached:
        return {"portrait": None, "per_category": [], "cached": False}
    return {**cached, "cached": True}
