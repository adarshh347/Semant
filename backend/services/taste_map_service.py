"""
Anuraṇana — the taste map (Layer-4 data-viz backend).

The corpus laid out by visual similarity: FashionCLIP taste vectors that ALREADY
exist (`region_embeddings`, role="fashion" — the 512-d taste space) reduced to a
2D map you can fly over. This module owns the one genuinely new capability — a
cached, versioned 2D projection — plus the read model the `/taste/map` endpoint
returns. It builds NO Motifs/Relations and mutates no Region; it only reads
vectors and writes disposable coordinates.

Grounding & invariants (do not weaken):
  · ONE SPACE PER MAP (E0). We project within a SINGLE vector space — default the
    FashionCLIP taste space (`retrieval_service` "fashion" =
    `fashion-clip|fashion|vitb32|512`) — and never mix spaces on one map. The
    space is resolved through the existing space registry, never invented here.
  · A PROJECTION IS DERIVED, VERSIONED, DISPOSABLE — never canonical geometry
    (Contract-Atlas caveat). Keyed by (space, projection_version); rebuilt when
    coverage changes or the version bumps. The authoritative vector stays in
    `region_embeddings`.
  · SIMILARITY = RESEARCH EVIDENCE, NOT TRUTH (Invariant 4). The payload says so.
  · NO FABRICATION. The map renders only regions that are actually embedded;
    coverage is reported honestly as {embedded, total}. Low coverage shows a
    number, never invented points.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from backend.database import (
    region_embeddings_collection,
    region_projections_collection,
    post_collection,
)
from backend.services import region_embedding_service as res
from backend.services import retrieval_service as rs

# Bump when the reduction algorithm changes so cached coords for the old version
# are ignored and rebuilt — coordinates are disposable, tied to this tag.
PROJECTION_VERSION = "pca-v1"

# Default map space — the FashionCLIP taste space ("what a garment looks like",
# 512-d). This IS the spec's "FashionCLIP · identity · 512-d" taste space; its
# persisted role is "fashion" (see evidence_embedding_service.embed_fashion_region),
# and its concrete key resolves through the retrieval-space registry (E0).
DEFAULT_SPACE = "fashion"

# Rebuild the cached projection when the embedded/projected counts diverge by
# more than this. 0 → rebuild on any change (correct, and cheap for thousands).
REBUILD_DELTA = 0

# A light, honest cap so a huge corpus can't return an unbounded payload.
DEFAULT_LIMIT = 5000

_COLOR_FIELDS = ("category", "actor", "prioritised")

EVIDENCE_NOTE = (
    "similarity map — research evidence, not truth (Invariant 4). "
    "Coordinates are a derived, versioned projection, not canonical geometry."
)


async def ensure_indexes() -> None:
    """Index the fields the projection read/rebuild paths filter on. Idempotent and
    non-fatal — a failure costs query speed, never correctness, and must not take
    the API down at boot (mirrors region_embedding_service.ensure_indexes)."""
    try:
        await region_projections_collection.create_index(
            [("space", 1), ("projection_version", 1)], name="space_version_idx")
        await region_projections_collection.create_index("embedding_id", name="proj_embedding_id_idx")
    except Exception as e:  # pragma: no cover - boot-time best effort
        print(f"⚠️ region_projections index creation skipped (non-fatal): {e}")


def resolve_space_id(space_name: str) -> Optional[str]:
    """Named retrieval space → its concrete `space_key`, or None if unknown. Reuses
    the E0 space registry so the map can never project a space the store doesn't
    actually use, nor invent a third dialect for it."""
    return rs.space_id(space_name)


# ── The projection (the one new capability) ──────────────────────────────────
def _svd_flip_2d(u: np.ndarray, vt: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Deterministic sign convention (sklearn's `svd_flip`, columns-of-U variant):
    for each component, flip its sign so the largest-magnitude entry of that column
    of U is positive. SVD leaves component signs ambiguous; pinning them makes the
    same input yield the same 2D coordinates every time."""
    signs = np.ones(u.shape[1], dtype=np.float64)
    for j in range(u.shape[1]):
        col = u[:, j]
        k = int(np.argmax(np.abs(col)))
        if col[k] < 0:
            signs[j] = -1.0
    return u * signs, vt * signs[:, None]


def pca_2d(vectors: Sequence[Sequence[float]]) -> np.ndarray:
    """Reduce N×D vectors to N×2 by PCA (numpy SVD), DETERMINISTICALLY. Sign-fixed
    so it reproduces exactly; degenerate inputs (0 or 1 rows, <2 real dims) are
    handled without raising. Coordinates are centered and scaled to ~[-1, 1] by a
    single scalar (aspect preserved) for a stable viewer frame."""
    X = np.asarray(vectors, dtype=np.float64)
    if X.ndim != 2 or X.shape[0] == 0:
        return np.zeros((0, 2))
    n = X.shape[0]
    if n == 1:
        return np.zeros((1, 2))
    Xc = X - X.mean(axis=0, keepdims=True)
    u, s, vt = np.linalg.svd(Xc, full_matrices=False)
    u, vt = _svd_flip_2d(u, vt)
    k = min(2, u.shape[1])
    coords = u[:, :k] * s[:k]                     # principal coordinates == Xc @ vt[:k].T
    if coords.shape[1] < 2:                       # <2 real dims → pad the missing axis
        coords = np.hstack([coords, np.zeros((n, 2 - coords.shape[1]))])
    m = float(np.max(np.abs(coords)))
    if m > 0:
        coords = coords / m
    return coords


# ── Reads over the embedding store (one space only) ──────────────────────────
async def _space_vectors(space_id: str, *, embeddings=None) -> List[dict]:
    """All embedded regions in ONE space, in a deterministic order (by embedding_id)
    so the projection built from them is itself deterministic. Vectors only — never
    crosses into another space."""
    coll = embeddings if embeddings is not None else region_embeddings_collection
    cursor = coll.find(
        {"space": space_id},
        {"_id": 0, "embedding_id": 1, "post_id": 1, "region_id": 1, "vector": 1},
    )
    docs = [d async for d in cursor if d.get("vector")]
    docs.sort(key=lambda d: str(d.get("embedding_id")))
    return docs


async def _embedded_count(space_id: str, *, embeddings=None) -> int:
    coll = embeddings if embeddings is not None else region_embeddings_collection
    return int(await coll.count_documents({"space": space_id}))


async def coverage(space_id: str, *, embeddings=None, posts=None) -> Dict[str, int]:
    """Honest coverage for the space: how many regions are actually embedded vs how
    many dissected regions exist at all. The map renders only the `embedded` set;
    `total` is the denominator so low coverage shows a number, not fabricated points."""
    embedded = await _embedded_count(space_id, embeddings=embeddings)
    pcoll = posts if posts is not None else post_collection
    total = 0
    async for post in pcoll.find({}, {"region_annotations.id": 1}):
        total += sum(1 for r in (post.get("region_annotations") or []) if r.get("id"))
    return {"embedded": int(embedded), "total": int(total)}


# ── Build / cache the projection ─────────────────────────────────────────────
async def build_projection(space_name: str = DEFAULT_SPACE, *,
                           embeddings=None, projections=None) -> Dict[str, Any]:
    """(Re)compute and cache the 2D projection for one space. Clears the prior
    projection for (space, projection_version) first so a removed embedding leaves
    no orphan point — the projection is disposable. Returns a small summary."""
    space_id = resolve_space_id(space_name)
    if not space_id:
        raise ValueError(f"unknown space {space_name!r}")
    pcoll = projections if projections is not None else region_projections_collection

    docs = await _space_vectors(space_id, embeddings=embeddings)
    await pcoll.delete_many({"space": space_id, "projection_version": PROJECTION_VERSION})
    if not docs:
        return {"space": space_name, "space_id": space_id,
                "projection_version": PROJECTION_VERSION, "count": 0}

    coords = pca_2d([d["vector"] for d in docs])
    now = datetime.now(timezone.utc)
    rows = [{
        "embedding_id": d.get("embedding_id"),
        "region_id": d.get("region_id"),
        "post_id": d.get("post_id"),
        "space": space_id,
        "projection_version": PROJECTION_VERSION,
        "x": float(x),
        "y": float(y),
        "source_count": len(docs),
        "built_at": now,
    } for d, (x, y) in zip(docs, coords)]
    await pcoll.insert_many(rows)
    return {"space": space_name, "space_id": space_id,
            "projection_version": PROJECTION_VERSION, "count": len(rows)}


async def _cached_points(space_id: str, *, projections=None) -> List[dict]:
    coll = projections if projections is not None else region_projections_collection
    cursor = coll.find(
        {"space": space_id, "projection_version": PROJECTION_VERSION},
        {"_id": 0},
    )
    return [d async for d in cursor]


async def get_or_build_projection(space_name: str = DEFAULT_SPACE, *,
                                  embeddings=None, projections=None) -> List[dict]:
    """Cached points for the space, rebuilding when coverage has drifted past the
    threshold (or the cache is empty while embeddings exist, or the version bumped —
    old-version rows simply aren't matched, so they're treated as absent)."""
    space_id = resolve_space_id(space_name)
    if not space_id:
        raise ValueError(f"unknown space {space_name!r}")
    cached = await _cached_points(space_id, projections=projections)
    embedded = await _embedded_count(space_id, embeddings=embeddings)
    if (embedded and not cached) or abs(len(cached) - embedded) > REBUILD_DELTA:
        await build_projection(space_name, embeddings=embeddings, projections=projections)
        cached = await _cached_points(space_id, projections=projections)
    return cached


# ── Region metadata join (label / category / actor / prioritised / thumb) ────
def _oid(post_id: str):
    """Best-effort ObjectId for a post-id string (embeddings store `str(_id)`).
    Returns the ObjectId, or the raw string when it isn't a valid ObjectId (so
    string-keyed test fixtures still match)."""
    try:
        from bson import ObjectId
        from bson.errors import InvalidId
        try:
            return ObjectId(post_id)
        except (InvalidId, TypeError):
            return post_id
    except Exception:  # pragma: no cover - bson always present with motor
        return post_id


async def _region_index(post_ids: Sequence[str], *, posts=None) -> Dict[str, Dict[str, dict]]:
    """{post_id_str: {region_id_str: region}} for the given posts, one bulk query."""
    ids = [p for p in post_ids if p]
    if not ids:
        return {}
    pcoll = posts if posts is not None else post_collection
    oids = [_oid(p) for p in ids]
    index: Dict[str, Dict[str, dict]] = {}
    cursor = pcoll.find({"_id": {"$in": oids}}, {"region_annotations": 1})
    async for post in cursor:
        pid = str(post.get("_id"))
        index[pid] = {
            str(r.get("id")): r
            for r in (post.get("region_annotations") or []) if r.get("id")
        }
    return index


# ── The read model the endpoint returns ──────────────────────────────────────
async def get_map(space_name: str = DEFAULT_SPACE, *, color_by: str = "category",
                  limit: int = DEFAULT_LIMIT, embeddings=None, projections=None,
                  posts=None) -> Dict[str, Any]:
    """The taste-map payload: projected points (cap `limit`) hydrated with each
    region's label/category/actor/prioritised + crop thumbnail URL, plus honest
    coverage and the evidence disclaimer. Light — carries no vectors. Raises
    ValueError for an unknown space (the router turns that into a 400)."""
    space_id = resolve_space_id(space_name)
    if not space_id:
        raise ValueError(f"unknown space {space_name!r}")

    raw = await get_or_build_projection(space_name, embeddings=embeddings, projections=projections)
    cov = await coverage(space_id, embeddings=embeddings, posts=posts)

    capped = raw[: max(0, int(limit))]
    region_ix = await _region_index({p.get("post_id") for p in capped}, posts=posts)

    color_by = color_by if color_by in _COLOR_FIELDS else "category"
    points: List[dict] = []
    for p in capped:
        pid = p.get("post_id")
        rid = str(p.get("region_id"))
        reg = region_ix.get(pid, {}).get(rid, {})
        points.append({
            "post_id": pid,
            "region_id": p.get("region_id"),
            "x": round(float(p.get("x", 0.0)), 5),
            "y": round(float(p.get("y", 0.0)), 5),
            "label": reg.get("label") or reg.get("category") or "region",
            "category": reg.get("category"),
            "actor": reg.get("actor"),
            "prioritised": bool(reg.get("prioritised")),
            "thumb": f"/api/v1/posts/{pid}/regions/{rid}/crop?role=identity",
        })

    return {
        "space": space_name,
        "space_id": space_id,
        "projection_version": PROJECTION_VERSION,
        "count": len(points),
        "coverage": cov,
        "color_by": color_by,
        "evidence_note": EVIDENCE_NOTE,
        "points": points,
    }


# ── Coverage backfill (Phase-1 item 1) — best effort, never fabricates ───────
async def ensure_coverage(posts_scope: Sequence[dict], *, fetch_image: Callable,
                          fashion=None, persist: bool = True,
                          space_name: str = DEFAULT_SPACE, embeddings=None) -> Dict[str, Any]:
    """Embed FashionCLIP taste vectors for dissected regions that lack one, reusing
    the on-demand embedder. HONEST UNDER ABSENCE: if the encoder isn't available it
    embeds nothing and just reports coverage — it never fabricates a point.
    `fetch_image(post) -> bytes` and `fashion` are injected so this is testable
    without a GPU."""
    from backend.services import fashion_clip_service
    from backend.services import evidence_embedding_service as ees

    space_id = resolve_space_id(space_name)
    available = True if fashion is not None else fashion_clip_service.is_available()
    newly = 0
    total = 0
    for post in posts_scope:
        pid = str(post.get("_id") or post.get("id") or "")
        regions = [r for r in (post.get("region_annotations") or []) if r.get("id")]
        total += len(regions)
        if not available or not regions:
            continue
        missing = []
        for r in regions:
            eid = res.make_embedding_id(pid, str(r["id"]), model=ees.FASHION_MODEL, role="fashion")
            rec = await res.get_embedding(eid)
            if not rec or not rec.get("vector"):
                missing.append(r)
        if not missing:
            continue
        try:
            image_bytes = await fetch_image(post)
        except Exception:
            continue  # one unfetchable post never fails the batch
        for r in missing:
            try:
                out = await ees.embed_fashion_region(post, r, image_bytes, fashion=fashion, persist=persist)
                if out.get("status") == "ready":
                    newly += 1
            except Exception:
                continue

    embedded = await _embedded_count(space_id, embeddings=embeddings) if space_id else 0
    return {"space": space_name, "space_id": space_id, "available": bool(available),
            "embedded": int(embedded), "total": int(total), "newly_embedded": newly}
