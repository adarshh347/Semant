"""
Region embedding sidecar (Darshan Track A + VISION-E) — the evidence-vector store.

Vectors are kept OUT of the Region document and the posts collection: each region carries
only an `embedding_id` pointer, and the actual vector lives here in `region_embeddings`,
keyed by that id. This keeps every post payload light (the UI never renders a raw vector)
and makes the backing store swappable — today a plain Mongo collection, later an Atlas
Vector Search index or an external vector DB — without touching the Region schema.

VISION-E extends this ONE store (a LOCKED project decision — no second embedding store) to
hold visual-evidence embeddings alongside the original FashionCLIP taste-vectors:

  · a record is a versioned projection of a *stable evidence identity*, not truth. It carries
    `role` (identity | context | whole_image | patch_features), the exact model + checkpoint +
    dim, the crop/preprocessing/pooling versions, `geometry_rev`, and the source + mask hashes;
  · comparisons are legal ONLY within one `space` — the (model, checkpoint, role, preproc, dim)
    tuple. `cosine_same_space` REFUSES to compare two different spaces, so a DINOv2 identity
    vector can never be cosine-scored against a FashionCLIP one, in code;
  · a *semantic label edit never invalidates a visual embedding* — staleness is a function of
    geometry_rev / source / mask / model / preprocessing only (`is_stale`);
  · the migration is additive: legacy FashionCLIP rows (no `role`/`space`/hash fields) stay
    readable and keep their original `embedding_id` and the original model-scoped search path.

STATUS: live. FashionCLIP (Track B) writes 512-d taste vectors; VISION-E adds DINOv2 (and,
if it earns its place, OpenCLIP) evidence vectors in their own spaces.
"""

import hashlib
import heapq
import json
from typing import Optional, List, Sequence, Tuple
from datetime import datetime, timezone

from backend.database import region_embeddings_collection

# roles a stored vector may play (E0 contract). A region can carry several, in different spaces.
ROLES = ("identity", "context", "whole_image", "patch_features")


async def ensure_indexes() -> None:
    """Index the fields the read paths filter on. `search_similar` scopes retrieval with
    `{post_id: {$in: [...]}}` (+ `space` or `model`); `get_embedding` looks up by
    `embedding_id`; stale-checks and re-index look up by `region_id`.

    Idempotent (Mongo no-ops an existing index) and non-fatal: a failure here costs query
    speed, never correctness, and must not take the API down at boot.
    """
    try:
        await region_embeddings_collection.create_index("post_id", name="post_id_idx")
        await region_embeddings_collection.create_index("embedding_id", name="embedding_id_idx")
        # E0: retrieval is space-scoped; stale-detection / re-index are region-scoped.
        await region_embeddings_collection.create_index("space", name="space_idx")
        await region_embeddings_collection.create_index("region_id", name="region_id_idx")
    except Exception as e:
        print(f"⚠️ region_embeddings index creation skipped (non-fatal): {e}")


def make_embedding_id(post_id: str, region_id: str, model: str = "fashion-clip",
                      role: Optional[str] = None) -> str:
    """Deterministic pointer for one projection of a region's evidence. Stable so re-running
    enrichment is idempotent — the same (post, region, model, role) always maps to the same id.

    Legacy compatibility: with `role=None` this returns the original
    `emb_{model}_{post}_{region}` id byte-for-byte, so existing FashionCLIP rows and callers
    are untouched. A role produces a distinct id (`emb_{model}_{role}_{post}_{region}`) so a
    region's identity and context vectors never collide."""
    if role is None:
        return f"emb_{model}_{post_id}_{region_id}"
    return f"emb_{model}_{role}_{post_id}_{region_id}"


def space_key(model: str, role: Optional[str], version: str, dim: int) -> str:
    """The identifier of an incomparable vector space. Two vectors may be compared ONLY when
    their space_key is identical — different model, checkpoint/preprocessing version, role or
    dimension means a different geometry of meaning, never a shared cosine axis."""
    return f"{model}|{role or 'default'}|{version}|{dim}"


def content_hash(data: bytes) -> str:
    """Stable hash of the source image bytes — a source change invalidates the projection."""
    return hashlib.sha256(data or b"").hexdigest()


def mask_hash(mask_rle: Optional[dict]) -> str:
    """Stable hash of a region's authoritative mask (its RLE). A mask change (a refine, a
    re-dissect) invalidates the projection; a label/note change does not touch this."""
    if not mask_rle:
        return ""
    payload = json.dumps({"size": mask_rle.get("size"), "counts": mask_rle.get("counts")},
                         sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def spaces_comparable(space_a: Optional[str], space_b: Optional[str]) -> bool:
    """Vectors are comparable iff they inhabit the same space. Two legacy rows (space None)
    are comparable to each other (the original model-scoped behaviour); a spaced vector is
    never comparable to a differently-spaced or unspaced one."""
    return space_a == space_b


def cosine_same_space(a: Sequence[float], space_a: Optional[str],
                      b: Sequence[float], space_b: Optional[str]) -> float:
    """Cosine similarity that STRUCTURALLY refuses a cross-space comparison — the code path
    that makes 'never compare vectors across model/version spaces' unbreakable. Raises
    ValueError rather than return a meaningless score."""
    if not spaces_comparable(space_a, space_b):
        raise ValueError(f"refusing cross-space comparison: {space_a!r} vs {space_b!r}")
    return _cosine(a, b)


def is_stale(record: dict, *, geometry_rev: Optional[int] = None,
             source_content_hash: Optional[str] = None, mask_hash: Optional[str] = None,
             model: Optional[str] = None, preprocessing_version: Optional[str] = None
             ) -> Tuple[bool, str]:
    """Is a stored projection stale against the region's CURRENT evidence? Staleness is a pure
    function of geometry_rev / source / mask / model / preprocessing — NEVER of semantic labels
    or notes. Returns (stale, reason); reason is '' when fresh. A `None` argument is 'unknown,
    do not judge on this axis'."""
    if record is None:
        return True, "missing"
    checks = (
        (geometry_rev, record.get("geometry_rev"), "geometry_rev"),
        (source_content_hash, record.get("source_content_hash"), "source"),
        (mask_hash, record.get("mask_hash"), "mask"),
        (model, record.get("model"), "model"),
        (preprocessing_version, record.get("preprocessing_version"), "preprocessing"),
    )
    for current, stored, reason in checks:
        if current is not None and stored is not None and current != stored:
            return True, reason
    return False, ""


async def upsert_embedding(
    embedding_id: str,
    vector: List[float],
    *,
    model: str = "fashion-clip",
    post_id: Optional[str] = None,
    region_id: Optional[str] = None,
    role: Optional[str] = None,
    geometry_rev: Optional[int] = None,
    checkpoint: Optional[str] = None,
    preprocessing_version: Optional[str] = None,
    crop_version: Optional[str] = None,
    source_content_hash: Optional[str] = None,
    mask_hash: Optional[str] = None,
    route: Optional[str] = None,
    normalized: bool = True,
    status: str = "ready",
    error: str = "",
    stale_reason: str = "",
) -> str:
    """Store (or replace) one evidence projection, keyed by `embedding_id`. Returns the id.

    Back-compatible: the original call `upsert_embedding(id, vec, model=, post_id=, region_id=)`
    still works and writes the same core fields (plus, harmlessly, the new versioned ones as
    None). VISION-E callers pass the full provenance so the record is self-describing and its
    `space` is computed here — the store is the one place that knows how vectors are bucketed."""
    dim = len(vector) if vector is not None else 0
    version = preprocessing_version or checkpoint or model
    space = space_key(model, role, version, dim)
    now = datetime.now(timezone.utc)
    doc = {
        "embedding_id": embedding_id,
        "vector": vector,
        "model": model,
        "checkpoint": checkpoint,
        "dim": dim,
        "role": role,
        "space": space,
        "post_id": post_id,
        "region_id": region_id,
        "geometry_rev": geometry_rev,
        "preprocessing_version": preprocessing_version,
        "crop_version": crop_version,
        "source_content_hash": source_content_hash,
        "mask_hash": mask_hash,
        "route": route,                   # E2: how this vector was made (mask_pool | crop_cls | whole_cls)
        "normalized": normalized,
        "storage": "inline",              # vector lives in this row; location is swappable later
        "status": status,
        "error": error,
        "stale_reason": stale_reason,
        "updated_at": now,
    }
    await region_embeddings_collection.update_one(
        {"embedding_id": embedding_id},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return embedding_id


async def get_embedding(embedding_id: str) -> Optional[dict]:
    """Fetch a stored embedding doc by id (Track C RAG + VISION-E read via this)."""
    if not embedding_id:
        return None
    return await region_embeddings_collection.find_one(
        {"embedding_id": embedding_id}, {"_id": 0}
    )


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity, defensive about normalization. Callers that must not cross spaces
    should use `cosine_same_space`; this raw form is used only after a space match."""
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
    space: Optional[str] = None,
    min_score: float = 0.0,
) -> List[dict]:
    """Top-k nearest stored regions by cosine similarity, best first.

    `post_ids` is REQUIRED and scopes the search — retrieval is own-scope-only and this
    signature makes searching the whole collection impossible; empty `post_ids` returns [].

    Space discipline (VISION-E): pass `space=` to search a single vector space (DINOv2
    identity, FashionCLIP, …); every candidate is filtered to that exact space AND run through
    `cosine_same_space`, so a cross-space score can never be produced. Legacy callers that pass
    only `model=` keep the original model-scoped path (space None on both sides → comparable),
    with the dimension guard as a backstop. Vectors are never returned."""
    if not query or not post_ids:
        return []
    scoped = [p for p in post_ids if p]
    if not scoped:
        return []

    q = {"post_id": {"$in": scoped}}
    if space is not None:
        q["space"] = space
    else:
        q["model"] = model
    query_space = space

    heap: List[tuple] = []  # min-heap of (score, embedding_id, hit) capped at top_k
    cursor = region_embeddings_collection.find(
        q, {"_id": 0, "embedding_id": 1, "post_id": 1, "region_id": 1, "role": 1,
            "vector": 1, "space": 1, "dim": 1},
    )
    async for doc in cursor:
        if exclude_post_id and doc.get("post_id") == exclude_post_id:
            continue
        vec = doc.get("vector") or []
        if len(vec) != len(query):          # a different space — never comparable
            continue
        doc_space = doc.get("space") if space is not None else None
        try:
            score = cosine_same_space(query, query_space, vec, doc_space)
        except ValueError:
            continue                        # spaces disagree — refuse, do not score
        if score < min_score:
            continue
        hit = {
            "embedding_id": doc.get("embedding_id"),
            "post_id": doc.get("post_id"),
            "region_id": doc.get("region_id"),
            "role": doc.get("role"),
            "score": round(score, 4),
        }
        if len(heap) < top_k:
            heapq.heappush(heap, (score, hit["embedding_id"], hit))
        elif score > heap[0][0]:
            heapq.heapreplace(heap, (score, hit["embedding_id"], hit))

    return [h[2] for h in sorted(heap, key=lambda t: -t[0])]
