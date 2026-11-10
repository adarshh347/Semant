from io import BytesIO

import pytest
from PIL import Image

from backend.services.perception_lab.field_data import decode_grid, encode_grid, path_sample
from backend.services.perception_lab.families import illumination as organ
from backend.services.perception_lab.image_preparation import prepare_image


class Cancel:
    def raise_if_cancelled(self):
        pass


def prepared(mode, size, pixels):
    im = Image.new(mode, size)
    im.putdata(pixels)
    out = BytesIO()
    im.save(out, format='PNG')
    return prepare_image(out.getvalue())


def test_linear_luminance_black_white_midgray_and_alpha_unknown():
    p = prepared('RGBA', (4, 1), [(0, 0, 0, 255), (255, 255, 255, 255),
                                   (128, 128, 128, 255), (255, 0, 0, 0)])
    f = organ.image_luminance(p, {}, (), Cancel())
    assert f.valid == [True, True, True, False]
    assert f.values[0] == 0
    assert f.values[1] == 1
    assert f.values[2] == pytest.approx(.21586, abs=.0001)
    assert f.values[3] == 0
    assert 'no intrinsic decomposition' in f.metadata['value_convention']
    manifest, ref = encode_grid(f.metadata, f.values, f.valid)
    restored = decode_grid(manifest, ref)
    assert restored.valid == tuple(f.valid)
    assert restored.values[2] == pytest.approx(f.values[2], abs=1e-7)
    assert path_sample(restored, [(0, 0), (3, 0)])[1]['valid'] is False


def test_non_square_gradient_alignment_and_alpha_threshold():
    p = prepared('RGBA', (3, 2), [(0, 0, 0, 255), (127, 127, 127, 255),
        (255, 255, 255, 255), (0, 0, 0, 127), (127, 127, 127, 127), (255, 255, 255, 127)])
    f = organ.image_luminance(p, {'alpha_min': 128}, (), Cancel())
    assert f.metadata['shape'] == [2, 3, 1]
    assert f.valid == [True] * 3 + [False] * 3
    assert f.values[0] < f.values[1] < f.values[2]
    assert f.values[3:] == [0] * 3
    with pytest.raises(ValueError):
        organ.image_luminance(p, {'alpha_min': 256}, (), Cancel())


def test_shading_uses_dense_service_and_preserves_model_invalid(monkeypatch):
    import numpy as np
    from backend.services import intrinsic_service
    p = prepared('RGB', (3, 2), [(20, 20, 20)] * 6)
    seen = []
    def fake(image):
        seen.append(image.size)
        return {'shading': np.arange(6, dtype='float32').reshape(2, 3),
                'valid': np.array([[True, False, True], [True, True, True]]),
                'native_shape': [4, 8], 'device': 'cpu'}
    monkeypatch.setattr(intrinsic_service, 'estimate_dense', fake)
    f = organ.estimated_shading(p, {}, (), Cancel())
    assert seen == [(3, 2)]
    assert f.valid == [True, False, True, True, True, True]
    assert f.values[1] == 0
    assert f.values[5] == 5
    assert '8x4' in f.metadata['value_convention']
    manifest, ref = encode_grid(f.metadata, f.values, f.valid)
    assert decode_grid(manifest, ref).values[5] == 5


def test_shading_unavailable_never_falls_back_to_luminance(monkeypatch):
    from backend.services import intrinsic_service
    p = prepared('RGB', (2, 1), [(0, 0, 0), (255, 255, 255)])
    monkeypatch.setattr(intrinsic_service, 'estimate_dense', lambda image: (_ for _ in ()).throw(RuntimeError('missing checkpoint')))
    with pytest.raises(RuntimeError, match='missing checkpoint'):
        organ.estimated_shading(p, {}, (), Cancel())


def test_dense_service_uninverts_pinned_output_and_keeps_legacy_separate(monkeypatch):
    import sys
    import types
    import numpy as np
    from backend.services import intrinsic_service as service

    monkeypatch.setattr(service, 'is_available', lambda: True)
    monkeypatch.setattr(service, '_load', lambda: None)
    monkeypatch.setattr(service, '_model', object())
    monkeypatch.setattr(service, '_device', lambda: 'cpu')
    observed = []
    def gray(model, rgb, **kwargs):
        observed.append(kwargs)
        return {'gry_shd': np.array([[.5, 0, 1.1, np.nan]], dtype='float32'),
                'image': np.zeros((16, 32, 3), dtype='float32')}
    package = types.ModuleType('intrinsic')
    package.__path__ = []
    pipeline = types.ModuleType('intrinsic.pipeline')
    pipeline.run_gray_pipeline = gray
    monkeypatch.setitem(sys.modules, 'intrinsic', package)
    monkeypatch.setitem(sys.modules, 'intrinsic.pipeline', pipeline)
    result = service.estimate_dense(Image.new('RGB', (4, 1)))
    assert observed == [{'device': 'cpu', 'maintain_size': True}]
    assert result['native_shape'] == [16, 32]
    assert result['shading'][0, :3].tolist() == pytest.approx([1, 999, 0])
    assert result['valid'][0].tolist() == [True, True, True, False]
    # The older suggestion route intentionally keeps its raw coarse convention.
    legacy = service.estimate(Image.new('RGB', (4, 1)), grid=2)
    assert legacy['grid'] == 2
