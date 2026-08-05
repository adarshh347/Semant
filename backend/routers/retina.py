"""
Simulation Engine · Lane 3 — the retina routes: what is near this, and what is indexed.

    GET  /api/v1/retina/status       what the index holds, and what the build skipped
    POST /api/v1/retina/candidates   a region or a vector → its nearest neighbours
    POST /api/v1/retina/rebuild      re-derive the index from `region_embeddings`

PROPOSAL ONLY, and structurally so — there is no write path here to misuse. `/candidates`
reads a memory-mapped index and returns neighbours with similarity scores; it creates no
relation, no motif, no mark, and touches no post. The envelope says as much in `grounded:
false` and `note`, so the caveat survives being passed through a client that never read this
docstring.

REFUSALS GET THEIR OWN STATUS CODES. 503 could-not-look, 404 never-indexed, 409 the-query-
names-more-than-one-thing, 400 malformed — because a caller that cannot tell "the index is
stale" from "this region has no neighbours" will draw the wrong conclusion from an empty list.
200 means it looked; the body then says `ready` or `empty`.

The read handlers are plain `def`: LanceDB is embedded and blocking, so FastAPI running them
in its threadpool is exactly right, and the event loop is never held by a page fault.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services import retina

router = APIRouter()

#: Envelope status → HTTP status. `empty` is deliberately a 200: it looked and found nothing,
#: which is an answer, not a failure.
_HTTP_FOR = {
    "ready": 200,
    "empty": 200,
    "unavailable": 503,     # lancedb missing — could not look at all
    "unknown": 404,         # never indexed; NOT the same as "no neighbours"
    "ambiguous": 409,       # the query names more than one space or region
    "error": 400,           # malformed query
}


class CandidatesRequest(BaseModel):
    """One of `embedding_id` / `region_id` / `embedding` — the three ways to say 'near what?'.

    `embedding_id` is the precise form. `region_id` needs `post_id` alongside it on any real
    corpus, because region ids ('seg_0') are unique only within a post. A raw `embedding` needs
    `space` unless exactly one indexed space has its width.
    """
    embedding_id: Optional[str] = None
    region_id: Optional[str] = None
    post_id: Optional[str] = None
    embedding: Optional[List[float]] = None
    space: Optional[str] = None
    role: Optional[str] = retina.DEFAULT_ROLE
    k: int = Field(default=retina.DEFAULT_K, ge=1, le=200)
    exclude_post_id: Optional[str] = None
    exclude_self: bool = True
    min_score: Optional[float] = Field(default=None, ge=-1.0, le=1.0)


class RebuildRequest(BaseModel):
    """`limit` and `spaces` both produce a PARTIAL index — recorded as such in the manifest and
    reported back, because a query answered from a fraction of the corpus is a different
    answer."""
    limit: Optional[int] = Field(default=None, ge=1)
    spaces: Optional[List[str]] = None


@router.get("/status")
def retina_status() -> Dict[str, Any]:
    """What the retina currently holds: spaces, row counts, build time, and the skip ledger.

    Never 503s on an unbuilt or unavailable index — this is the call you make precisely to find
    out which state you are in, so the state belongs in the body.
    """
    return retina.index_status()


@router.post("/candidates")
def retina_candidates(req: CandidatesRequest) -> Dict[str, Any]:
    """Nearest neighbours in ONE vector space. Candidates, never relations."""
    envelope = retina.propose_candidates(
        embedding_id=req.embedding_id, region_id=req.region_id, post_id=req.post_id,
        embedding=req.embedding, space=req.space, role=req.role, k=req.k,
        exclude_post_id=req.exclude_post_id, exclude_self=req.exclude_self,
        min_score=req.min_score)
    code = _HTTP_FOR.get(envelope.get("status"), 500)
    if code != 200:
        raise HTTPException(status_code=code, detail=envelope)
    return envelope


@router.post("/rebuild")
async def retina_rebuild(req: RebuildRequest) -> Dict[str, Any]:
    """Re-derive the index from `region_embeddings`. Idempotent: same source, same index.

    Safe to call at any time — Mongo is the source of truth and this only ever replaces the
    derived copy. The cost is a full scan of the sidecar, so it is a deliberate operation
    rather than something a read path triggers on a miss.
    """
    try:
        return await retina.index_rebuild(limit=req.limit, spaces=req.spaces)
    except retina.RetinaUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    except retina.RetinaError as e:
        raise HTTPException(status_code=400, detail=str(e))
