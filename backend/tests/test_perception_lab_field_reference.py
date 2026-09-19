def test_field_reference_is_lossless_deterministic_and_digest_verifiable():
    import base64
    import gzip
    import hashlib
    import json
    from backend.services.perception_lab.field_reference import field_reference
    values = [0.0, 1/3, 0.5, 1.0]
    ref = field_reference(values, [2, 2])
    assert ref == field_reference(values, [2, 2])
    data = base64.b64decode(ref.uri.split(',', 1)[1])
    assert ref.digest == 'sha256:' + hashlib.sha256(data).hexdigest()
    assert ref.bytes == len(data)
    assert json.loads(gzip.decompress(data)) == {'field_shape': [2, 2], 'values': values}
