"""Synthetic controls and injected producer tests are not evidence of model quality."""
from dataclasses import replace
from io import BytesIO
import copy
import sys
import types

import numpy as np
import pytest
from PIL import Image

from backend.services import depth_service as service
from backend.services.perception_lab.families import depth
from backend.services.perception_lab.families import depth_spec
from backend.services.perception_lab.field_data import (FieldError, compare_fields, decode_grid,
                                                       encode_grid, point_sample)
from backend.services.perception_lab.image_preparation import prepare_image


class Cancel:
    def raise_if_cancelled(self):
        pass


def prepared(size=(3, 2)):
    image = Image.new('RGBA', size, (80, 100, 120, 255))
    image.putpixel((0, 0), (80, 100, 120, 0))
    out = BytesIO(); image.save(out, format='PNG')
    return prepare_image(out.getvalue())


def fake_result():
    return {'depth': np.array([[1, 2, 3], [4, 5, 6]], dtype='float32'),
            'valid': np.array([[True, True, True], [False, True, True]]),
            'native_shape': [2, 3], 'input_shape': [2, 3], 'working_size': [3, 2],
            'working_to_field': [1, 0, 0, 0, 1, 0, 0, 0, 1], 'preprocessing': 'synthetic injected output',
            'device': 'cpu', 'load_ms': 1, 'inference_ms': 2, 'model_cached': False,
            'cache_hit': False, 'invocation_count': 1}


@pytest.fixture
def field(monkeypatch):
    monkeypatch.setattr(service, 'estimate_dense', lambda image, **kw: fake_result())
    monkeypatch.setattr(service, 'unload', lambda: None)
    return depth.produce(prepared(), {}, (), Cancel())


def grid(field):
    return decode_grid(*encode_grid(field.metadata, field.values, field.valid))


def test_native_relative_sign_and_unknown_not_zero(field):
    for name in ('CHECKPOINT', 'REVISION', 'CHECKPOINT_SHA256', 'DENSE_VERSION'):
        assert getattr(depth_spec, name) == getattr(service, name)
    saved = grid(field)
    assert saved.shape == (2, 3, 1)
    assert saved.valid == (False, True, True, False, True, True)
    assert point_sample(saved, 0, 0)['values'] is None
    assert saved.values == (0, 2, 3, 0, 5, 6)
    assert 'larger=nearer' in saved.metadata['value_convention']
    assert field.receipt['checkpoint_digest'] == 'sha256:' + service.CHECKPOINT_SHA256


def test_saved_profile_summary_and_roundtrip_never_infer(field, monkeypatch):
    monkeypatch.setattr(service, 'estimate_dense', lambda *a, **k: pytest.fail('reader invoked model'))
    saved = grid(field)
    samples = depth.profile(saved, [[1, 0], [0, 0], [2, 1]], {})
    assert samples['samples'][1]['valid'] is False
    assert samples['samples'][-1]['values'] == [6]
    assert samples['model_invocations'] == 0
    result = depth.regional_summary(saved, [[1, 0], [1, 0], [2, 1], [0, 0]], {})
    assert result['requested_count'] == 4 and result['sample_count'] == 3
    assert result['valid_count'] == 2 and result['mean'] == [4]
    assert (result['minimum'], result['maximum']) == (2, 6)


def test_empty_invalid_constant_and_bad_readers(field):
    saved = grid(field)
    result = depth.regional_summary(saved, [[0, 0]], {})
    assert result['mean'] is None and result['minimum'] is None
    constant = replace(saved, values=(7,) * 6, valid=(True,) * 6)
    assert depth.regional_summary(constant, [[0, 0], [1, 0]], {})['mean'] == [7]
    for points in ([], [[-1, 0]], [[3, 0]], [[True, 0]], [[0, 0, 0]], [[0, 0]] * 4097):
        with pytest.raises((FieldError, TypeError)):
            depth.profile(saved, points, {})
    with pytest.raises(FieldError):
        depth.profile(saved, [[0, 0]], {'scale': 'metres'})
    bad = copy.deepcopy(saved.metadata); bad['value_convention'] = 'smaller=nearer'
    with pytest.raises(FieldError):
        depth.profile(replace(saved, metadata=bad), [[1, 0]], {})


@pytest.mark.parametrize('parameters', [{'alpha_min': 0}, {'alpha_min': True}, {'alpha_min': 256},
    {'resolution': 'huge'}, {'crop': [0, 0, 1, 1]}])
def test_bad_measurement_parameters_do_not_infer(monkeypatch, parameters):
    monkeypatch.setattr(service, 'estimate_dense', lambda *a, **k: pytest.fail('invalid input inferred'))
    with pytest.raises(ValueError):
        depth.produce(prepared(), parameters, (), Cancel())


def test_cancel_input_failure_and_release(monkeypatch):
    seen = []
    def fail(*a, **k): raise RuntimeError('inference failed')
    monkeypatch.setattr(service, 'estimate_dense', fail)
    monkeypatch.setattr(service, 'unload', lambda: seen.append('unloaded'))
    with pytest.raises(RuntimeError, match='inference failed'):
        depth.produce(prepared(), {}, (), Cancel())
    assert seen == ['unloaded']
    with pytest.raises(ValueError, match='whole image'):
        depth.produce(prepared(), {}, ['region'], Cancel())
    class Cancelled:
        def raise_if_cancelled(self): raise RuntimeError('cancelled')
    with pytest.raises(RuntimeError, match='cancelled'):
        depth.produce(prepared(), {}, (), Cancelled())
    assert seen == ['unloaded']


def test_source_transform_composes_native_pixel_centres_and_exif(monkeypatch):
    result = fake_result(); result['working_to_field'] = [.5, 0, -.25, 0, .5, -.25, 0, 0, 1]
    monkeypatch.setattr(service, 'estimate_dense', lambda *a, **k: result)
    monkeypatch.setattr(service, 'unload', lambda: None)
    p = replace(prepared((6, 4)), source_to_working=(0, -1, 5, 1, 0, 0, 0, 0, 1))
    produced = depth.produce(p, {}, (), Cancel())
    assert produced.metadata['source_to_field'] == [0, -.5, 2.25, .5, 0, -.25, 0, 0, 1]


def test_compare_only_identical_quantity_source_grid_and_convention(field):
    saved = grid(field)
    assert compare_fields(saved, saved)['max_absolute_difference'] == 0
    for key, value in [('source_digest', 'sha256:' + '1' * 64), ('units', 'metres'),
                       ('value_convention', 'independently normalized'),
                       ('source_to_field', [2, 0, 0, 0, 2, 0, 0, 0, 1])]:
        meta = {**saved.metadata, key: value}
        with pytest.raises(FieldError): compare_fields(saved, replace(saved, metadata=meta))


def test_corrupt_asset_is_not_a_flat_depth(field):
    manifest, ref = encode_grid(field.metadata, field.values, field.valid)
    with pytest.raises(FieldError, match='digest'):
        decode_grid(manifest, ref.model_copy(update={'digest': 'sha256:' + '0' * 64}))


def stub_native(monkeypatch):
    class Tensor:
        shape = (1, 3, 2, 3)
        def __getitem__(self, _): return self
        def float(self): return self
        def cpu(self): return self
        def numpy(self): return np.array([[1, 2, np.nan], [4, 5, 6]], dtype='float32')
    class Inputs(dict):
        def to(self, _): return self
    class Processor:
        do_pad = False
        def __call__(self, **kw): return Inputs(pixel_values=Tensor())
    class Context:
        def __enter__(self): pass
        def __exit__(self, *args): pass
    calls = []
    def model(**kw): calls.append(kw); return types.SimpleNamespace(predicted_depth=Tensor())
    monkeypatch.setattr(service, '_model', model)
    monkeypatch.setattr(service, '_processor', Processor())
    monkeypatch.setattr(service, '_load', lambda **kw: None)
    monkeypatch.setattr(service, '_device', lambda: 'cpu')
    monkeypatch.setattr(service, 'dense_readiness', lambda: (True, 'injected'))
    monkeypatch.setattr(service, 'is_available', lambda: True)
    monkeypatch.setattr(service, '_dense_cache', None)
    monkeypatch.setitem(sys.modules, 'torch', types.SimpleNamespace(no_grad=Context))
    return calls


def test_dense_cache_native_geometry_invalid_and_legacy_shape(monkeypatch):
    calls = stub_native(monkeypatch)
    im = Image.new('RGB', (6, 4))
    result = service.estimate_dense(im)
    assert result['native_shape'] == [2, 3]
    assert result['working_to_field'] == [.5, 0, -.25, 0, .5, -.25, 0, 0, 1]
    assert result['valid'][0, 2] == False
    result['depth'][0, 0] = 999
    restored = service.estimate_dense(im)
    assert restored['depth'][0, 0] == 1
    assert restored['cache_hit'] and restored['invocation_count'] == 0
    assert restored['load_ms'] == restored['inference_ms'] == 0
    assert len(calls) == 1
    legacy = service.estimate(im)
    assert set(legacy) == {'depth', 'grid'} and legacy['grid'] == 16 and len(legacy['depth']) == 256
    assert len(calls) == 2


def test_valid_native_cache_can_feed_legacy_coarse_without_duplicate_inference(monkeypatch):
    calls = stub_native(monkeypatch)
    im = Image.new('RGB', (6, 4))
    service.estimate_dense(im)
    service._dense_cache[1]['valid'][:] = True
    expected = service._to_grid(service._dense_cache[1]['depth'], 16)
    assert service.estimate(im) == {'depth': expected, 'grid': 16}
    assert len(calls) == 1


def test_dense_refuses_untracked_padding_and_unavailable(monkeypatch):
    stub_native(monkeypatch)
    service._processor.do_pad = True
    with pytest.raises(RuntimeError, match='crop/pad'): service.estimate_dense(Image.new('RGB', (3, 2)))
    monkeypatch.setattr(service, 'dense_readiness', lambda: (False, 'missing pinned checkpoint'))
    with pytest.raises(RuntimeError, match='missing pinned'): service.estimate_dense(Image.new('RGB', (3, 2)))


def test_probe_never_imports_ml_stack(monkeypatch):
    # The light CI environment intentionally has no ML extras (including Hub).
    # Test only our cache-probe protocol, not whether a developer installed them.
    huggingface_hub = types.ModuleType('huggingface_hub')
    huggingface_hub.try_to_load_from_cache = lambda *a, **k: '/cached/file'
    monkeypatch.setitem(sys.modules, 'huggingface_hub', huggingface_hub)
    monkeypatch.setattr(service.importlib.util, 'find_spec', lambda name: object())
    monkeypatch.setattr(service, '_load_failed', False)
    assert service.dense_readiness()[0]
    monkeypatch.setattr(service, '_load_failed', True)
    available, reason = service.dense_readiness()
    assert not available and 'Restart after repairing runtime' in reason
    monkeypatch.setattr(service, '_load_failed', False)
    monkeypatch.setattr(huggingface_hub, 'try_to_load_from_cache', lambda *a, **k: None)
    assert not service.dense_readiness()[0]
    monkeypatch.setattr(service.importlib.util, 'find_spec', lambda name: None)
    assert 'installed torch' in service.dense_readiness()[1]


def test_direct_prompt_persistence_import_and_http_consumer_without_model(field, monkeypatch):
    from contextlib import nullcontext
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.routers import perception_lab as route
    from backend.schemas.perception_lab import LabSource, OrganFamily, ExecutionIdentity
    from backend.services.perception_lab import live
    from backend.services.perception_lab.bridges import LabRuntime, live_registry
    from backend.services.perception_lab.families import bridge
    from backend.services.perception_lab.orchestrator import PerceptionConductor
    from backend.services.perception_lab.planners.base import DirectCommand
    from backend.services.perception_lab.field_assets import InMemoryFieldAssets
    from backend.services.perception_lab.field_transfer import attach_field_assets, import_session_bundle
    from backend.services.perception_lab.store import InMemoryLabStore
    from backend.services.perception_lab.derivation_store import InMemoryDerivationStore

    monkeypatch.setattr(service, 'dense_readiness', lambda: (True, 'test injected producer'))
    monkeypatch.setattr(bridge, 'learned_model_lease', lambda **kw: nullcontext())
    p = prepared()
    source = LabSource(origin='post', post_id='post_synthetic_depth', image_digest=p.source_digest,
                       natural_width=3, natural_height=2)
    store, assets = InMemoryLabStore(), InMemoryFieldAssets()
    conductor = PerceptionConductor(store=store, registry=live_registry(LabRuntime(source=source,
        image_bytes=p.source_bytes, field_assets=assets)), source_probe=lambda: p.source_digest)
    machine = conductor.open_session(source=source, organ=OrganFamily.DEPTH)
    direct = conductor.plan_direct(machine, DirectCommand('depth.estimate'))
    prompt = conductor.plan_prompt(machine, 'estimate relative depth', planner='rules')
    assert not direct.plan.refusals and not prompt.plan.refusals
    assert direct.plan.resolved_steps[0].operation == prompt.plan.resolved_steps[0].operation
    first = conductor.execute(machine, direct.plan, confirmed=True)
    second = conductor.execute(machine, prompt.plan, confirmed=True)
    assert first.run.outcome.value == second.run.outcome.value == 'ready'
    artifact = first.artifacts[0]
    assert artifact.measurement.epistemic_basis.value == 'model_estimate'
    assert artifact.measurement.epistemic_status.value == 'uncertain'
    assert artifact.measurement.payload.manifest == second.artifacts[0].measurement.payload.manifest
    bundle = attach_field_assets(live.export_json(store, machine.session, identity=ExecutionIdentity.LIVE), assets)
    fresh, fresh_assets, readings = InMemoryLabStore(), InMemoryFieldAssets(), InMemoryDerivationStore()
    monkeypatch.setattr(service, 'estimate_dense', lambda *a, **k: pytest.fail('reopen/import/consumer inferred'))
    imported = import_session_bundle(bundle, store=fresh, asset_store=fresh_assets,
                                    derivation_store=readings, target_source=source)
    artifact_id = imported['identity_map'][artifact.identity.artifact_id]
    sid = imported['session_id']
    monkeypatch.setattr(route, '_store', lambda: fresh)
    monkeypatch.setattr(route, '_field_assets', lambda: fresh_assets)
    monkeypatch.setattr(route, '_derivation_store', lambda: readings)
    app = FastAPI(); app.include_router(route.router)
    with TestClient(app) as client:
        response = client.get(f'/sessions/{sid}/fields/{artifact_id}/preview')
        assert response.status_code == 200, response.text
        assert response.json()['measurement_hash'] == artifact.measurement.payload.manifest['measurement_hash']
        response = client.post(f'/sessions/{sid}/fields/{artifact_id}/consume', json={
            'operation': 'depth.profile', 'points': [[1, 0], [0, 0], [2, 1]]})
        assert response.status_code == 201, response.text
        saved = response.json()['derivation']
        assert saved['measurements']['result']['samples'][2]['values'] == [6]
        assert saved['basis'] == 'model_estimate' and saved['ceiling'] == 'uncertain'
        assert saved['input_artifact_ids'] == [artifact_id]
        assert readings.get(saved['derivation_id']).measurements == saved['measurements']
