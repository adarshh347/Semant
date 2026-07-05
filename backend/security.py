from typing import Optional
from fastapi import Header, HTTPException

from backend.config import settings


async def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    """Static API-key gate for the single-curator system.

    When API_KEY is unset (local dev), all requests pass. When set, every
    request must carry a matching X-API-Key header.
    """
    if not settings.API_KEY:
        return
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
