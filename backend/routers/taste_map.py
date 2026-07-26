"""
Anuraṇana — the taste MAP (creator/studio side, Layer-4 data-viz).

Distinct from `taste.py` (the audience/consent surface): this is the curator's own
corpus laid out by visual similarity, so it is mounted behind the API-key gate in
main.py, not on the public consumer router. One space per map (E0); the projection
is derived, versioned and disposable; similarity is research evidence, not truth
(Invariant 4) — the payload carries that disclaimer.
"""
from fastapi import APIRouter, HTTPException, Query

from backend.database import post_collection
from backend.services import taste_map_service as tm

router = APIRouter()


@router.get("/map")
async def taste_map(
    space: str = Query(tm.DEFAULT_SPACE, description="retrieval-space name; one map, one space (E0)"),
    color_by: str = Query("category", description="category | actor | prioritised"),
    limit: int = Query(tm.DEFAULT_LIMIT, ge=1, le=50000),
):
    """The similarity map for one embedding space: derived 2D points + region
    metadata + crop-thumbnail URLs + honest coverage. Never mixes spaces; carries
    no vectors."""
    if tm.resolve_space_id(space) is None:
        raise HTTPException(status_code=400,
                            detail=f"unknown space {space!r} — one map, one space (E0)")
    return await tm.get_map(space, color_by=color_by, limit=limit)


@router.post("/map/backfill")
async def taste_map_backfill(
    space: str = Query(tm.DEFAULT_SPACE),
    limit_posts: int = Query(200, ge=1, le=5000, description="posts scanned per call (heavy)"),
):
    """Best-effort coverage backfill for the map's space — embeds missing FashionCLIP
    taste vectors where the model is available, otherwise reports coverage without
    fabricating. Heavy; gated to `limit_posts` per call. Rebuild the projection
    afterwards by hitting GET /map (it recomputes when coverage grew)."""
    if tm.resolve_space_id(space) is None:
        raise HTTPException(status_code=400, detail=f"unknown space {space!r}")

    # Lazy import to avoid a router↔router import cycle at module load.
    from backend.routers.posts import _fetch_post_image_cached

    cursor = post_collection.find({}).limit(limit_posts)
    posts = [p async for p in cursor]

    async def _fetch(post):
        return await _fetch_post_image_cached(str(post.get("_id")), post)

    return await tm.ensure_coverage(posts, fetch_image=_fetch, space_name=space)
