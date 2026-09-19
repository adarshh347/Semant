#!/usr/bin/env python3
"""Serve existing Lab routes on loopback, without starting unrelated application workers.

python scripts/perception_lab_serve.py --env-file ../semant/.env --port 5011
Set SAM3_WEIGHTS explicitly before launching. No downloads or fixture substitution.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file')
    parser.add_argument('--port', type=int, default=5011)
    args = parser.parse_args()
    if args.env_file:
        from dotenv import load_dotenv
        load_dotenv(args.env_file)
    from fastapi import Depends, FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from backend.routers.perception_lab import router
    from backend.security import require_api_key
    import uvicorn
    app = FastAPI(title='Perception Lab · existing live adapters and session stores')
    app.add_middleware(CORSMiddleware, allow_origin_regex=r'https?://(localhost|127\.0\.0\.1)(:\d+)?',
                       allow_methods=['*'], allow_headers=['*'])
    app.include_router(router, prefix='/api/v1/perception-lab', dependencies=[Depends(require_api_key)])
    uvicorn.run(app, host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
