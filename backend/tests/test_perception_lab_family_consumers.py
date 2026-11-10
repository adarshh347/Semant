from dataclasses import replace

import pytest

from backend.services.perception_lab.families import registry
from backend.services.perception_lab.family_consumers import consume
from backend.services.perception_lab.field_data import FieldError, decode_grid
from backend.services.perception_lab.field_assets import InMemoryFieldAssets
from backend.tests.test_perception_lab_field_transfer import field_record, fixture_slot  # noqa: F401


def install(monkeypatch, handler):
    slot = replace(registry.REGISTRY["colour"], consumers={"colour.read_saved": handler})
    monkeypatch.setitem(registry.REGISTRY, "colour", slot)


def test_only_saved_numbers_and_explicit_parameters_reach_consumer(monkeypatch, fixture_slot):
    record = field_record(InMemoryFieldAssets())
    payload = record.measurement.payload
    grid = decode_grid(payload.manifest, payload.field_ref)
    install(monkeypatch, lambda found, points, params: {
        "sample": found.values[points[0][0]], "setting": params["setting"]})
    result = consume("colour", "colour.read_saved", grid, [[1, 0]], {"setting": 12})
    assert result == {"sample": .25, "setting": 12}
    assert grid.measurement_hash == payload.manifest["measurement_hash"]
    with pytest.raises(FieldError, match="no declared consumer"):
        consume("colour", "depth.read_saved", grid, [], {})


@pytest.mark.parametrize("result", [{"bad": float("nan")}, {"bad": set()}, [1],
                                    {"large": "x" * (4 * 1024 * 1024)}])
def test_invalid_results_cannot_be_saved(monkeypatch, result):
    install(monkeypatch, lambda *_: result)
    with pytest.raises(FieldError):
        consume("colour", "colour.read_saved", None, [], {})


def test_http_consumer_persists_and_reopens_without_a_producer(monkeypatch, fixture_slot):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.routers import perception_lab as route
    from backend.schemas.perception_lab import LabSession, LabSource
    from backend.services.perception_lab.store import InMemoryLabStore
    from backend.services.perception_lab.derivation_store import InMemoryDerivationStore

    assets = InMemoryFieldAssets()
    artifact = field_record(assets)
    store, readings = InMemoryLabStore(), InMemoryDerivationStore()
    store.put_session(LabSession(session_id="labs_fixture", selected_organ="colour",
        mode="isolation", source=LabSource(origin="post", post_id="post_fixture",
        image_digest=artifact.provenance.source_image_digest, natural_width=3, natural_height=2),
        created_at="2026-11-10T00:00:00Z", updated_at="2026-11-10T00:00:00Z"))
    store.put_artifact(artifact)
    install(monkeypatch, lambda grid, points, params: {"sample": grid.values[1], "settings": params})
    monkeypatch.setattr(route, "_store", lambda: store)
    monkeypatch.setattr(route, "_field_assets", lambda: assets)
    monkeypatch.setattr(route, "_derivation_store", lambda: readings)
    app = FastAPI()
    app.include_router(route.router)
    with TestClient(app) as client:
        path = "/sessions/labs_fixture/fields/art_fixture/consume"
        response = client.post(path, json={"operation": "colour.read_saved", "parameters": {"steps": 5}})
        assert response.status_code == 201, response.text
        saved = response.json()["derivation"]
        assert saved["measurements"]["result"] == {"sample": .25, "settings": {"steps": 5}}
        assert saved["input_artifact_ids"] == ["art_fixture"]
        assert readings.get(saved["derivation_id"]).measurements == saved["measurements"]
        refused = client.post(path, json={"operation": "depth.read_saved"})
        assert refused.status_code == 422
        assert len(readings.for_session("labs_fixture")) == 1


def test_unavailable_family_reason_is_kept_in_backend_catalogue():
    from backend.services.perception_lab import definitions
    for family, slot in registry.REGISTRY.items():
        if not slot.available:
            assert definitions.organs()[family].deferred_note == slot.reason
