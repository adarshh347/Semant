"""CPU-only deployment of the existing inquiry workflow.

No post mutation routes, local perception models, or research worker are mounted.
Browser access uses HTTP Basic (username `semant`, password API_KEY); scripts may
use X-API-Key. Secrets are never embedded in the frontend bundle.
"""
import asyncio
import base64
import binascii
import hmac
import math
import os
from contextlib import asynccontextmanager
from pathlib import Path

# The shared Settings schema also serves the full application. This deployment
# does not import its upload/OpenRouter services, so no credentials for them are needed.
for _name in ("CLOUDINARY_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET", "OPENROUTER_API_KEY"):
    os.environ.setdefault(_name, "")

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from backend.config import settings
from backend.routers import inquiries


@asynccontextmanager
async def lifespan(app):
    if not settings.API_KEY or len(settings.API_KEY) < 24:
        raise RuntimeError("Set a private API_KEY of at least 24 characters before deployment")
    provider = os.getenv("SEMANT_TEXT_PROVIDER", "groq").lower()
    if provider not in ("sarvam", "groq"):
        raise RuntimeError("SEMANT_TEXT_PROVIDER must be sarvam or groq")
    key = os.getenv("SARVAM_API_KEY") if provider == "sarvam" else settings.GROQ_API_KEY
    if not key:
        raise RuntimeError("The selected text provider has no API key")
    from backend.database import client
    await asyncio.wait_for(client.admin.command("ping"), timeout=15)
    yield
    client.close()


app = FastAPI(title="Semant — Dissolution", lifespan=lifespan)


def authorized(headers):
    expected = settings.API_KEY
    if not expected:
        return False
    supplied = headers.get("x-api-key", "")
    if supplied and hmac.compare_digest(supplied.encode(), expected.encode()):
        return True
    scheme, _, encoded = headers.get("authorization", "").partition(" ")
    if scheme.lower() != "basic":
        return False
    try:
        user, _, password = base64.b64decode(encoded, validate=True).decode().partition(":")
    except (ValueError, UnicodeError, binascii.Error):
        return False
    return user == "semant" and hmac.compare_digest(password.encode(), expected.encode())


@app.middleware("http")
async def private_service(request: Request, call_next):
    if request.url.path == "/health" and request.method in ("GET", "HEAD"):
        return await call_next(request)
    if not authorized(request.headers):
        return JSONResponse({"detail": "Sign in to Semant"}, status_code=401,
                            headers={"WWW-Authenticate": 'Basic realm="Semant dissolution"'})
    # Browsers attach Basic credentials automatically. Reject cross-origin writes.
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin:
        allowed = os.getenv("RENDER_EXTERNAL_URL", str(request.base_url).rstrip("/"))
        if origin.rstrip("/") != allowed.rstrip("/"):
            return JSONResponse({"detail": "Cross-origin writes are not allowed"}, status_code=403)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        # Bound request bodies without trusting Content-Length (including chunked input).
        chunks = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > 131072:
                return JSONResponse({"detail": "Request exceeds 128 KiB"}, status_code=413)
            chunks.append(chunk)
        request._body = b"".join(chunks)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


app.include_router(inquiries.router, prefix="/api/v1/inquiries", tags=["Inquiry"])


@app.get("/health")
async def health():
    # Liveness only. This endpoint never calls a model or exposes configuration.
    return {"status": "ok", "service": "semant-dissolution"}


@app.get("/api/v1/deployment")
async def deployment():
    from backend.services import role_registry
    from backend.database import client
    try:
        await asyncio.wait_for(client.admin.command("ping"), timeout=5)
    except Exception:
        raise HTTPException(503, "Session database is unavailable") from None
    roles = ("scene_theorist", "semantic_dissector", "relation_architect",
             "epistemic_operationalizer", "synthesis_composer")
    return {"roles": {r: {"provider": role_registry.provider_for(r),
                           "model": role_registry.model_for(r)} for r in roles},
            "persistence": "mongodb", "local_models": False,
            "perceptual_execution": "existing declared fixture; not live segmentation"}


@app.get("/api/v1/posts")
@app.get("/api/v1/posts/")
async def sources(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
                  tag: str | None = None):
    from backend.database import post_collection
    query = {"general_tags": tag} if tag else {}
    fields = {"title": 1, "photo_url": 1, "general_tags": 1, "source_url": 1}
    total = await post_collection.count_documents(query)
    rows = await post_collection.find(query, fields).sort("_id", -1).skip((page - 1) * limit).limit(limit).to_list(length=limit)
    return {"posts": [{**p, "_id": str(p["_id"]), "id": str(p["_id"])} for p in rows],
            "total_pages": math.ceil(total / limit), "current_page": page}


@app.post("/api/v1/posts/{path:path}")
async def no_archive_writes(path: str):
    raise HTTPException(403, "This dissolution deployment reads existing archive images only; uploads and archive edits are disabled")


@app.get("/")
async def index():
    return RedirectResponse("/inquiry")


_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}")
    async def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not part of the dissolution service")
        candidate = (_dist / path).resolve()
        if candidate.is_relative_to(_dist) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html")
