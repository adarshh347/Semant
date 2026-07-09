"""
Region embedding sidecar (Darshan Track A) — the taste-vector store.

FashionCLIP vectors are kept OUT of the Region document and the posts collection:
each region carries only an `embedding_id` pointer, and the actual vector lives here
in `region_embeddings`, keyed by that id. This keeps every post payload light (the
UI never renders a 512-float vector) and makes the backing store swappable — today a
plain Mongo collection, later an Atlas Vector Search index or an external vector DB —
without touching the Region schema.

STATUS: live. Track B Phase 1 (`fashion_clip_service` + `POST /{id}/enrich-regions`)
writes the vectors; Track C reads them back through `search_similar` to ground the
writer in the curator's accrued taste (Anuraṇana).
"""

import heapq
from typing import Optional, List, Sequence
from datetime import datetime, timezone

from backend.database import region_embeddings_collection


def make_embedding_id(post_id: str, region_id: str, model: str = "fashion-clip") -> str:
    """Deterministic pointer for a (post, region, model) triple. Stable so re-running
    enrichment is idempotent — the same region always maps to the same embedding_id,
    letting callers cache (an embedding is immutable once computed)."""
    return f"emb_{model}_{post_id}_{region_id}"


async def upsert_embedding(
    embedding_id: str,
    vector: List[float],
    *,
    model: str = "fashion-clip",
    post_id: Optional[str] = None,
    region_id: Optional[str] = None,
) -> str:
    """
    Store (or replace) a taste-vector for a region, keyed by `embedding_id`.
    Returns the embedding_id. Vectors are immutable per (region, model) — callers
    reuse the id and skip recompute on post edits.

    STUB: exercised by Track B once FashionCLIP inference lands. Kept minimal and
    idempotent so the contract is stable now.
    """
    doc = {
        "embedding_id": embedding_id,
        "vector": vector,
        "model": model,
        "dim": len(vector) if vector is not None else 0,
        "post_id": post_id,
        "region_id": region_id,
        "updated_at": datetime.now(timezone.utc),
    }
    await region_embeddings_collection.update_one(
        {"embedding_id": embedding_id}, {"$set": doc}, upsert=True
    )
    return embedding_id


async def get_embedding(embedding_id: str) -> Optional[dict]:
    """Fetch a stored embedding doc by id (Track C RAG reads via this)."""
    if not embedding_id:
        return None
    return await region_embeddings_collection.find_one(
        {"embedding_id": embedding_id}, {"_id": 0}
    )


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity, defensive about normalization. FashionCLIP already returns
    L2-normalized vectors (so this is a dot product), but a vector written by another
    model — or an older one — must not silently produce an out-of-range score."""
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


async def search_similar(
    query: List[float],
    *,
    post_ids: Sequence[str],
    exclude_post_id: Optional[str] = None,
    top_k: int = 5,
    model: str = "fashion-clip",
    min_score: float = 0.0,
) -> List[dict]:
    """
    Top-k nearest stored regions by cosine similarity — the taste-graph query that
    grounds the writer (Track C §4).

    `post_ids` is REQUIRED and scopes the search to a set of posts: retrieval is
    own-history-only by Adarsh's lock, and this signature makes it impossible to
    accidentally search the whole collection. An empty `post_ids` returns [] — a
    curator with no history gets no taste history, not everyone else's. The sidecar
    deliberately knows nothing about handles; the caller resolves ownership.

    Returns `[{embedding_id, post_id, region_id, score}]`, best first. Vectors are
    never returned — the caller wants the notes behind them, not 512 floats.
    """
    if not query or not post_ids:
        return []

    scoped = [p for p in post_ids if p]
    if not scoped:
        return []

    heap: List[tuple] = []  # min-heap of (score, embedding_id, doc) capped at top_k
    cursor = region_embeddings_collection.find(
        {"post_id": {"$in": scoped}, "model": model},
        {"_id": 0, "embedding_id": 1, "post_id": 1, "region_id": 1, "vector": 1},
    )
    async for doc in cursor:
        if exclude_post_id and doc.get("post_id") == exclude_post_id:
            continue
        vec = doc.get("vector") or []
        if len(vec) != len(query):  # a different model's space — not comparable
            continue
        score = _cosine(query, vec)
        if score < min_score:
            continue
        hit = {
            "embedding_id": doc.get("embedding_id"),
            "post_id": doc.get("post_id"),
            "region_id": doc.get("region_id"),
            "score": round(score, 4),
        }
        # `embedding_id` breaks score ties so heapq never compares the dicts.
        if len(heap) < top_k:
            heapq.heappush(heap, (score, hit["embedding_id"], hit))
        elif score > heap[0][0]:
            heapq.heapreplace(heap, (score, hit["embedding_id"], hit))

    return [h[2] for h in sorted(heap, key=lambda t: -t[0])]
