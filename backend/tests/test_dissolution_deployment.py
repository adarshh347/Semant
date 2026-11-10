import base64
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.dissolution_main import app, settings
from backend.services.text_provider import SarvamClient
from backend.services import role_registry

KEY = "test-only-deployment-password-123456"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", KEY)
    # No lifespan: these tests must never connect to a real database or provider.
    return TestClient(app)


def test_health_public_but_all_other_routes_private(client):
    assert client.get("/health").status_code == 200
    for path in ("/", "/inquiry", "/docs", "/openapi.json", "/api/v1/inquiries", "/api/v1/posts/"):
        assert client.get(path).status_code == 401


def test_fail_closed_without_key(client, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", None)
    assert client.get("/docs", headers={"X-API-Key": KEY}).status_code == 401


def test_both_auth_methods_and_bad_basic(client):
    assert client.get("/docs", auth=("semant", KEY)).status_code == 200
    assert client.get("/docs", headers={"X-API-Key": KEY}).status_code == 200
    for header in ("Basic invalid!", "Basic " + base64.b64encode(b"other:wrong").decode()):
        assert client.get("/docs", headers={"Authorization": header}).status_code == 401


def test_csrf_and_size_and_archive_writes(client):
    headers = {"X-API-Key": KEY}
    assert client.post("/api/v1/inquiries", headers={**headers, "Origin": "https://evil.invalid"}, json={}).status_code == 403
    assert client.post("/api/v1/inquiries", headers=headers, content=b"x" * 131073).status_code == 413
    assert client.post("/api/v1/posts/upload", headers=headers, json={}).status_code == 403
    # A valid-sized body still reaches the original route parser after middleware reads it.
    assert client.post("/api/v1/inquiries", headers=headers, json={"prompt": "test"}).status_code == 422


def test_sarvam_payload_and_actual_provider(monkeypatch):
    monkeypatch.setenv("SEMANT_TEXT_PROVIDER", "sarvam")
    assert role_registry.model_for("semantic_dissector") == "sarvam-105b"
    assert role_registry.provider_for("semantic_dissector") == "sarvam"
    assert role_registry.provider_for("scene_theorist") == "groq"
    def handle(request):
        body = json.loads(request.content)
        assert request.url.host == "api.sarvam.ai"
        assert request.headers["api-subscription-key"] == "test-only"
        assert body["max_tokens"] == 99
        assert "max_completion_tokens" not in body
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]})
    c = SarvamClient("test-only", httpx.MockTransport(handle))
    assert c.create(model="sarvam-105b", messages=[{"content": "Return JSON"}], max_completion_tokens=99).choices[0].message.content == "{}"
    with pytest.raises(ValueError):
        c.create(model="other", messages=[])
    with pytest.raises(ValueError):
        c.create(model="sarvam-105b", messages=[{"content": []}])
    c._http.close()


def test_provider_failure_not_replaced():
    c = SarvamClient("test-only", httpx.MockTransport(lambda r: httpx.Response(429)))
    with pytest.raises(httpx.HTTPStatusError):
        c.create(model="sarvam-105b", messages=[])
    c._http.close()
