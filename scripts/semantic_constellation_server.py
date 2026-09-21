#!/usr/bin/env python3
"""Local lane A surface: real inquiry routes/store, isolated durable rehearsal sessions.

python scripts/semantic_constellation_server.py --env-file /path/to/.env --live --port 5012
VITE_API_URL=http://127.0.0.1:5012 npm --prefix frontend run dev -- --host 127.0.0.1 --port 5182

Only the isolated database's runs collection is writable here. The archive supplies read-only
post references. Synthetic stored-output comparisons are explicitly badged fixture, even when
new inquiries use live adapters. Restarting does not replace existing sessions or human judgments.
"""
import argparse
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file")
    parser.add_argument("--port", type=int, default=5012)
    parser.add_argument("--session-uri", default="mongodb://127.0.0.1:27017")
    parser.add_argument("--session-db", default="semant_perceptual_life_001a")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if args.env_file:
        from dotenv import load_dotenv
        load_dotenv(args.env_file)
    import uvicorn
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from motor.motor_asyncio import AsyncIOMotorClient
    from backend.routers import inquiries
    from backend.services.inquiry_session import store, view, runtime, constellations, coordinator
    from backend.schemas.semantic_constellation import SemanticConstellations
    from backend.tests.fixtures import semantic_constellation_fixtures as fixtures
    client = AsyncIOMotorClient(args.session_uri, serverSelectionTimeoutMS=5000)
    sessions = client[args.session_db].runs
    store._collection = lambda collection=None: collection if collection is not None else sessions
    inquiries._stages = lambda: runtime.build_stages() if args.live else coordinator.Stages()
    ordinary_view = inquiries._view

    def projected(session):
        if session.session_id in {"inqs_synthetic_" + name for name in fixtures.CASES}:
            return view.session_view(session, deployment={"kind": "fixture", "declared": True,
                "detail": "Synthetic stored dissolution output. No live model or measurement ran."})
        return ordinary_view(session)
    inquiries._view = projected

    @asynccontextmanager
    async def lifespan(_app):
        for name in fixtures.CASES:
            s = fixtures.session_for(name, compiled=False)
            s = constellations.capture(s, fixtures.thought_for(s), at=fixtures.STAMP)
            s = s.model_copy(update={"graph": fixtures.session_for(name).graph,
                                    "interaction": {"state": "exhausted"},
                                    "stop_reason": "Synthetic stored-output comparison; human assessment pending."})
            s = constellations.reconcile(s, at=fixtures.STAMP)
            if not await sessions.find_one({"_id": s.session_id}):
                await store.create(s)
        # A separate preparation specimen exercises saving and reopening before any execution.
        s = coordinator.new_session(prompt=fixtures.CASES["flower"][0], refs=[], mode="consult",
                                    session_id="inqs_synthetic_preparation", now=fixtures.STAMP)
        s = s.model_copy(update={"semantic_constellations": SemanticConstellations(preparation="prompt")})
        if not await sessions.find_one({"_id": s.session_id}):
            await store.create(s)
        yield
        client.close()

    app = FastAPI(title="Semantic constellation rehearsal", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5182", "http://localhost:5182"],
                       allow_methods=["GET", "POST", "PUT"], allow_headers=["*"])
    app.include_router(inquiries.router, prefix="/api/v1/inquiries")

    @app.get("/health")
    async def health():
        return {"service": "semantic-constellation-rehearsal", "live_enabled": args.live,
                "session_database": args.session_db, "canonical_writes": False}

    # Deliberately read-only: this local surface has no post upload or canonical mutation route.
    @app.get("/api/v1/posts")
    async def posts(page: int = 1, limit: int = 24):
        from backend.database import post_collection
        limit = max(1, min(limit, 100))
        rows = await post_collection.find({}, {"photo_url": 1, "title": 1, "instagram_handle": 1}) \
            .sort("_id", -1).skip(max(0, page - 1) * limit).limit(limit).to_list(length=limit)
        total = await post_collection.count_documents({})
        return {"posts": [{**{k: v for k, v in d.items() if k != "_id"}, "id": str(d["_id"])} for d in rows],
                "current_page": page, "total_pages": (total + limit - 1) // limit}

    print(f"Session storage: {args.session_db}.runs; canonical archive routes are read-only.", flush=True)
    print(f"http://127.0.0.1:5182/inquiry?session=inqs_synthetic_flower", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
