import pytest
from fastapi import HTTPException

from backend.config import settings
from backend.security import require_api_key


@pytest.mark.anyio
async def test_no_key_configured_allows_all(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", None)
    await require_api_key(x_api_key=None)  # must not raise


@pytest.mark.anyio
async def test_missing_header_rejected(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "secret123")
    with pytest.raises(HTTPException) as exc:
        await require_api_key(x_api_key=None)
    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_wrong_key_rejected(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "secret123")
    with pytest.raises(HTTPException) as exc:
        await require_api_key(x_api_key="nope")
    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_correct_key_allowed(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "secret123")
    await require_api_key(x_api_key="secret123")  # must not raise


@pytest.fixture
def anyio_backend():
    return "asyncio"
