"""
Region embedding sidecar (Darshan Track A) — the taste-vector store.

FashionCLIP vectors are kept OUT of the Region document and the posts collection:
each region carries only an `embedding_id` pointer, and the actual vector lives here
in `region_embeddings`, keyed by that id. This keeps every post payload light (the
UI never renders a 512-float vector) and makes the backing store swappable — today a
plain Mongo collection, later an Atlas Vector Search index or an external vector DB —
without touching the Region schema.

STATUS: write path is a STUB. Track B (FashionCLIP integration) computes the vectors
and calls `upsert_embedding`; today nothing produces them, so `embedding_id` stays
None on every region. The collection + contract exist now so Track B has a home.
"""

from typing import Optional, List
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
