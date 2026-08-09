#!/usr/bin/env python3
"""
HARNESS-002D — serve the inquiry API with FROZEN model stages, for the human rehearsal.

    python scripts/inquiry_rehearsal_server.py                 # port 8000, no API key needed
    python scripts/inquiry_rehearsal_server.py --port 8011 --fixture unrelated-domain

WHY THIS EXISTS, AND WHY IT IS A SCRIPT RATHER THAN A DEPLOYMENT FLAG. The HARNESS-002R rehearsal
asks a person to judge whether the moment of interruption is helpful, whether the alternatives are
meaningfully different, and whether their answer visibly changes the work. Those questions need the
pause to happen every time, and the live compiler does not oblige: on a long reading it runs out of
output budget, returns a PREFIX with no observables, and a graph with no observables has no fork in
it. That is reported honestly by the chain and it is a real finding — it is also not something a
person can rehearse against.

So this serves the REAL routes, the real coordinator, the real state machine, the real capability
adapter, the real judge and the real composer, with the two MODEL stages replaced by frozen
payloads. The browser cannot tell the difference and is not meant to: it is exercising the same
HTTP, the same session, the same conflicts.

WHAT MAKES THIS HONEST RATHER THAN A FIXTURE FALLBACK. It is a separate command a person runs on
purpose, never a fallback the product reaches for. The sessions it produces SAY they were replayed —
`call_topology: "replay"`, `call_count: 0` on both receipts — so a screenshot taken here cannot be
mistaken for a live reading by anyone who looks at the provenance. And it is a script, so no
production module imports a test fixture to make it work.

It opens the DATABASE only for posts (the corpus the entry screen lists) and for the runs
collection the sessions are written to. Both are the real ones: this is a rehearsal of the product,
not of the tests.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BANNER = """
┌──────────────────────────────────────────────────────────────────────────┐
│  REPLAY DEPLOYMENT — the scene theorist and the semantic compiler are    │
│  frozen payloads. Everything else is the real thing: routes, session,    │
│  state machine, capability adapter, judge, composer, persistence.        │
│                                                                          │
│  Every session says so: call_topology "replay", call_count 0.            │
│  Phase 1's one capability is SIMULATED here exactly as it is in prod.    │
└──────────────────────────────────────────────────────────────────────────┘
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--fixture", default="")
    args = parser.parse_args()

    import uvicorn
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from backend.routers import inquiries as R
    from backend.services.inquiry_session.capability import LockedFixtureCapability
    from backend.services.inquiry_session.composer import DeterministicComposer
    from backend.services.inquiry_session.judge import judge
    from backend.tests.fixtures import inquiry_session_fixtures as F

    name = args.fixture or F.FIXTURES[0]
    if name not in F.FIXTURES:
        parser.error(f"--fixture must be one of {list(F.FIXTURES)}")

    def stages():
        # A fresh capability adapter per request, exactly as `runtime.build_stages` does it — the
        # one-attempt firewall is the session's existing receipt, not this object's counter.
        return F.stages_for(name, capability=LockedFixtureCapability(), judge=judge,
                            composer=DeterministicComposer())

    R._stages = stages

    app = FastAPI(title="semantic inquiry — replay deployment")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                       allow_headers=["*"])
    # Mounted WITHOUT the API-key dependency: this is a local rehearsal server bound to loopback,
    # and an auth wrapper here would only be re-testing `require_api_key`.
    app.include_router(R.router, prefix="/api/v1/inquiries", tags=["Semantic Inquiry (replay)"])

    # The corpus the entry screen lists comes from the real posts route, so the rehearsal picks
    # from real images even though the reading of them is frozen.
    from backend.routers import posts
    app.include_router(posts.router, prefix="/api/v1/posts", tags=["Posts"])

    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": "inquiry-replay", "fixture": name}

    print(BANNER)
    print(f"  fixture : {name}")
    print(f"  serving : http://{args.host}:{args.port}/api/v1/inquiries")
    print(f"  browser : point VITE_API_URL at http://{args.host}:{args.port} "
          f"and open /inquiry\n")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
