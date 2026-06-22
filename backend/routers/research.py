"""
Research Article Agent + Sankalpa API.

Endpoints (mounted under /api/v1/research):
  POST /agent/run          -> enqueue a background article run
  GET  /agent/runs         -> list recent runs
  GET  /agent/runs/{id}    -> poll one run's progress
  GET  /articles           -> list composed articles
  GET  /articles/{id}      -> read one article
  POST /articles/{id}/feedback -> submit feedback signals (updates Sankalpa)
  GET  /sankalpa           -> current will profile
"""

from fastapi import APIRouter, HTTPException

from backend.schemas.research import RunAgentRequest, FeedbackRequest
from backend.services.research_agent_service import research_agent_service
from backend.services.sankalpa_service import sankalpa_service

router = APIRouter()


# --- Agent runs ---

@router.post("/agent/run")
async def run_agent(request: RunAgentRequest):
    """Enqueue a background research-article run. Returns the run to poll."""
    run = await research_agent_service.enqueue_run(
        topic=request.topic,
        source_tags=request.source_tags,
        angle=request.angle,
    )
    return run


@router.get("/agent/runs")
async def list_runs(limit: int = 20):
    return {"runs": await research_agent_service.list_runs(limit)}


@router.get("/agent/runs/{run_id}")
async def get_run(run_id: str):
    run = await research_agent_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


# --- Articles ---

@router.get("/articles")
async def list_articles(page: int = 1, limit: int = 20):
    return await research_agent_service.list_articles(page, limit)


@router.get("/articles/{article_id}")
async def get_article(article_id: str):
    article = await research_agent_service.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.post("/articles/{article_id}/feedback")
async def submit_feedback(article_id: str, request: FeedbackRequest):
    """Record feedback signals and fold them into the reader's will profile."""
    signals = [s.model_dump() for s in request.signals]
    profile = await research_agent_service.record_feedback(article_id, signals)
    if profile is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"ok": True, "sankalpa": profile}


# --- Sankalpa (will profile) ---

@router.get("/sankalpa")
async def get_sankalpa():
    return await sankalpa_service.get_profile()
