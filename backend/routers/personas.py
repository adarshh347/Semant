"""
Darpan — Instagram persona-context API.

Mounted under /api/v1/personas:
  POST /ingest               -> extension posts scraped account data
  POST /{handle}/synthesize  -> build the dossier (vision + LLM)
  GET  /                     -> list personas
  GET  /{handle}             -> read one persona
  GET  /{handle}/images      -> gallery images we have from this account
"""

from fastapi import APIRouter, HTTPException

from backend.schemas.persona import PersonaIngestRequest
from backend.services.persona_service import persona_service

router = APIRouter()


@router.post("/ingest")
async def ingest_persona(request: PersonaIngestRequest):
    """Create/merge a persona from an extension scrape; correlates our gallery."""
    try:
        persona = await persona_service.ingest(request.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return persona


@router.post("/{handle}/synthesize")
async def synthesize_persona(handle: str):
    persona = await persona_service.synthesize(handle)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona


@router.get("/")
async def list_personas():
    return {"personas": await persona_service.list_personas()}


@router.get("/{handle}")
async def get_persona(handle: str):
    persona = await persona_service.get_persona(handle)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona


@router.get("/{handle}/images")
async def persona_images(handle: str):
    return {"images": await persona_service.images_for_handle(handle)}
