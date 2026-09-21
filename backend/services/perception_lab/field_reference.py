"""Portable, lossless field references carried by ordinary Lab artifact persistence.

Use the existing DataRef contract: a deterministic gzip JSON data URI plus its digest.
No new public asset, database collection, or canonical write is involved.
"""
import base64
import gzip
import hashlib
import json

from backend.schemas.perception_lab import DataRef


def field_reference(values, shape):
    raw = json.dumps({'field_shape': list(shape), 'values': values},
                     separators=(',', ':'), allow_nan=False).encode('utf-8')
    data = gzip.compress(raw, mtime=0)
    return DataRef(uri='data:application/gzip;base64,' + base64.b64encode(data).decode('ascii'),
                   digest='sha256:' + hashlib.sha256(data).hexdigest(),
                   media_type='application/gzip', bytes=len(data))
