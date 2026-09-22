"""Bounded portable numeric grids for Perception Lab measurements.

The envelope may live in an artifact payload or a derivation measurement. DataRef's
SHA-256 is over *compressed bytes* (the #238 rule); measurement_hash is over
canonical metadata and uncompressed numeric/validity bytes.
"""
from __future__ import annotations

import base64
import binascii
import gzip
import hashlib
import json
import math
import struct
import zlib
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from backend.schemas.perception_lab import DataRef

MAX_CELLS = 16_777_216
MAX_CHANNELS = 16
MAX_RAW = 64 * 1024 * 1024
MAX_COMPRESSED = 16 * 1024 * 1024
INLINE_LIMIT = 64 * 1024
CODEC = "gzip-field-v1"
DTYPES = {"float32-le": ("<f", 4), "float64-le": ("<d", 8)}
KINDS = {"scalar": 1, "directed_vector_2d": 2, "axial_orientation_2d": 2,
         "normal_camera_3d": 3, "multichannel": None}
FRAMES = {"image_pixel_xy_topleft", "image_normalized_xy_topleft", "camera_xyz"}


class FieldError(ValueError):
    pass


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical(meta: Mapping) -> bytes:
    return json.dumps(meta, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _checked_meta(meta: Mapping) -> dict:
    if not isinstance(meta, Mapping) or set(meta) != {
        "version", "shape", "dtype", "kind", "channels", "frame", "units",
        "source_digest", "source_to_field", "value_convention"}:
        raise FieldError("field metadata keys are missing or unsupported")
    if meta["version"] != 1 or meta["dtype"] not in DTYPES or meta["kind"] not in KINDS:
        raise FieldError("unsupported field version, dtype or kind")
    shape = meta["shape"]
    if (not isinstance(shape, list) or len(shape) != 3
            or any(type(n) is not int or n <= 0 for n in shape)
            or shape[2] > MAX_CHANNELS or math.prod(shape) > MAX_CELLS):
        raise FieldError("invalid or excessive [height,width,channels]")
    expected = KINDS[meta["kind"]]
    if expected is not None and shape[2] != expected:
        raise FieldError("channel count conflicts with field kind")
    channels = meta["channels"]
    if (not isinstance(channels, list) or len(channels) != shape[2]
            or not all(isinstance(c, Mapping) and set(c) == {"name", "quantity", "unit"}
                       and all(isinstance(c[k], str) and c[k] for k in c) for c in channels)
            or len({c["name"] for c in channels}) != len(channels)):
        raise FieldError("each channel needs a unique name, quantity and unit")
    if meta["frame"] not in FRAMES:
        raise FieldError("unsupported coordinate frame")
    if meta["kind"] == "normal_camera_3d" and meta["frame"] != "camera_xyz":
        raise FieldError("camera normals require camera_xyz")
    if meta["kind"] in {"directed_vector_2d", "axial_orientation_2d"} and meta["frame"] == "camera_xyz":
        raise FieldError("image directions require image axes")
    transform = meta["source_to_field"]
    if (not isinstance(transform, list) or len(transform) != 9
            or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in transform)
            or abs(transform[0] * transform[4] - transform[1] * transform[3]) < 1e-12
            or transform[6:] != [0, 0, 1]):
        raise FieldError("source_to_field must be an invertible 2D affine transform")
    for key in ("units", "source_digest", "value_convention"):
        if not isinstance(meta[key], str) or not meta[key]:
            raise FieldError(f"{key} is required")
    if not meta["source_digest"].startswith("sha256:") or len(meta["source_digest"]) != 71:
        raise FieldError("source digest must be SHA-256 of original source bytes")
    if math.prod(shape) * DTYPES[meta["dtype"]][1] + ((shape[0]*shape[1]+7)//8) > MAX_RAW:
        raise FieldError("field exceeds decoded byte limit")
    return dict(meta)


def _mask_bytes(valid: Sequence[bool]) -> bytes:
    out = bytearray((len(valid) + 7) // 8)
    for i, bit in enumerate(valid):
        if type(bit) is not bool:
            raise FieldError("validity values must be booleans")
        if bit:
            out[i // 8] |= 1 << (i % 8)
    return bytes(out)


def _unmask(data: bytes, cells: int) -> tuple[bool, ...]:
    if len(data) != (cells + 7) // 8:
        raise FieldError("wrong validity length")
    if cells % 8 and data[-1] & ~((1 << (cells % 8)) - 1):
        raise FieldError("nonzero validity padding")
    return tuple(bool(data[i // 8] & (1 << (i % 8))) for i in range(cells))


@dataclass(frozen=True)
class SampleGrid:
    metadata: dict
    values: tuple[float, ...]
    valid: tuple[bool, ...]
    measurement_hash: str

    @property
    def shape(self) -> tuple[int, int, int]:
        return tuple(self.metadata["shape"])


def _validate_values(meta: Mapping, values: Sequence[float], valid: Sequence[bool]) -> None:
    h, w, c = meta["shape"]
    if len(values) != h*w*c or len(valid) != h*w:
        raise FieldError("values or validity do not match declared shape")
    for i, value in enumerate(values):
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise FieldError("nonfinite field sample")
        if not valid[i//c] and value != 0:
            raise FieldError("invalid cells must have zero storage values; validity carries absence")
    if meta["kind"] == "normal_camera_3d":
        for i, is_valid in enumerate(valid):
            if is_valid and abs(math.sqrt(sum(float(v)**2 for v in values[3*i:3*i+3])) - 1) > .02:
                raise FieldError("valid camera normals must be unit length")


def _measurement_hash(meta: Mapping, numbers: bytes, mask: bytes) -> str:
    header = _canonical(meta)
    return _sha(struct.pack("<I", len(header)) + header + numbers + mask)


def encode_grid(metadata: Mapping, values: Sequence[float], valid: Sequence[bool],
                *, put_asset: Callable[[bytes], str] | None = None) -> tuple[dict, DataRef]:
    """Return (manifest, DataRef). Larger fields require an injected Lab asset writer."""
    meta = _checked_meta(metadata)
    _validate_values(meta, values, valid)
    fmt, size = DTYPES[meta["dtype"]]
    try:
        numbers = b"".join(struct.pack(fmt, float(v)) for v in values)
    except (OverflowError, struct.error) as exc:
        raise FieldError("field value cannot be represented in declared dtype") from exc
    mask = _mask_bytes(valid)
    raw = struct.pack("<I", len(_canonical(meta))) + _canonical(meta) + numbers + mask
    if len(raw) > MAX_RAW:
        raise FieldError("field exceeds decoded byte limit")
    compressed = gzip.compress(raw, mtime=0)
    if len(compressed) > MAX_COMPRESSED:
        raise FieldError("field exceeds compressed byte limit")
    if len(compressed) <= INLINE_LIMIT:
        uri = "data:application/gzip;base64," + base64.b64encode(compressed).decode("ascii")
    elif put_asset is not None:
        uri = put_asset(compressed)
        if uri != "lab-asset:" + _sha(compressed):
            raise FieldError("Lab asset writer returned an unexpected ID")
    else:
        raise FieldError("large field requires a Lab-owned asset store")
    ref = DataRef(uri=uri, digest=_sha(compressed), media_type="application/gzip", bytes=len(compressed))
    return {"codec": CODEC, "metadata": meta,
            "measurement_hash": _measurement_hash(meta, numbers, mask)}, ref


def _bounded_gunzip(data: bytes) -> bytes:
    if len(data) > MAX_COMPRESSED:
        raise FieldError("compressed field exceeds limit")
    dec = zlib.decompressobj(wbits=31)
    try:
        raw = dec.decompress(data, MAX_RAW + 1)
        if len(raw) > MAX_RAW or dec.unconsumed_tail:
            raise FieldError("decompressed field exceeds limit")
        raw += dec.flush(MAX_RAW + 1 - len(raw))
    except zlib.error as exc:
        raise FieldError("invalid gzip field") from exc
    if len(raw) > MAX_RAW or not dec.eof or dec.unused_data:
        raise FieldError("truncated, oversized or concatenated gzip field")
    return raw


def decode_grid(manifest: Mapping, ref: DataRef | Mapping,
                *, get_asset: Callable[[str], bytes] | None = None) -> SampleGrid:
    if not isinstance(ref, DataRef):
        ref = DataRef.model_validate(ref)
    if ref.media_type != "application/gzip" or ref.bytes is None or ref.bytes > MAX_COMPRESSED:
        raise FieldError("unsupported field asset")
    if ref.uri.startswith("data:application/gzip;base64,"):
        encoded = ref.uri.split(",", 1)[1]
        if len(encoded) > (MAX_COMPRESSED * 4 // 3 + 4):
            raise FieldError("encoded field exceeds limit")
        try:
            compressed = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise FieldError("invalid base64 field") from exc
    elif ref.uri.startswith("lab-asset:sha256:") and ref.uri == "lab-asset:" + ref.digest:
        if get_asset is None:
            raise FieldError("Lab asset unavailable")
        compressed = get_asset(ref.uri)
    else:
        raise FieldError("remote or arbitrary field URI refused")
    if len(compressed) != ref.bytes or _sha(compressed) != ref.digest:
        raise FieldError("field asset digest or byte count mismatch")
    raw = _bounded_gunzip(compressed)
    if len(raw) < 4:
        raise FieldError("short field")
    length = struct.unpack_from("<I", raw)[0]
    if length > 16384 or 4 + length > len(raw):
        raise FieldError("invalid field metadata length")
    try:
        meta = _checked_meta(json.loads(raw[4:4+length]))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise FieldError("invalid field metadata") from exc
    if manifest.get("codec") != CODEC or manifest.get("metadata") != meta:
        raise FieldError("field manifest does not match decoded metadata")
    h, w, c = meta["shape"]
    fmt, size = DTYPES[meta["dtype"]]
    nbytes = h*w*c*size
    if len(raw) != 4 + length + nbytes + (h*w+7)//8:
        raise FieldError("field dimensions do not match decoded bytes")
    numbers = raw[4+length:4+length+nbytes]
    mask = raw[4+length+nbytes:]
    valid = _unmask(mask, h*w)
    values = tuple(v[0] for v in struct.iter_unpack(fmt, numbers))
    _validate_values(meta, values, valid)
    expected = _measurement_hash(meta, numbers, mask)
    if manifest.get("measurement_hash") != expected:
        raise FieldError("measurement hash mismatch")
    return SampleGrid(meta, values, valid, expected)


def point_sample(grid: SampleGrid, x: int, y: int) -> dict:
    h, w, c = grid.shape
    if type(x) is not int or type(y) is not int or not (0 <= x < w and 0 <= y < h):
        raise FieldError("point is outside field pixel coordinates")
    i = y*w+x
    return {"x": x, "y": y, "valid": grid.valid[i],
            "values": list(grid.values[i*c:(i+1)*c]) if grid.valid[i] else None,
            "channels": grid.metadata["channels"]}


def path_sample(grid: SampleGrid, points: Sequence[Sequence[int]]) -> list[dict]:
    if not points or len(points) > 4096:
        raise FieldError("path needs 1–4096 explicit points")
    return [point_sample(grid, *point) for point in points]


def roi_sample(grid: SampleGrid, points: Sequence[Sequence[int]]) -> dict:
    samples = path_sample(grid, points)
    valid = [s["values"] for s in samples if s["valid"]]
    c = grid.shape[2]
    return {"sample_count": len(samples), "valid_count": len(valid),
            "mean": [sum(v[j] for v in valid)/len(valid) for j in range(c)] if valid else None,
            "channels": grid.metadata["channels"]}


@dataclass(frozen=True)
class ValidatedSourceTransform:
    left_source_digest: str
    right_source_digest: str
    decoded_rgb_digest: str
    matrix: tuple[int, ...]


def validate_source_transform(left_bytes: bytes, right_bytes: bytes) -> ValidatedSourceTransform:
    """Admit identity only after independently decoding both original sources."""
    from backend.services.perception_lab.image_preparation import prepare_image
    left = prepare_image(left_bytes)
    right = prepare_image(right_bytes)
    if (left.working_rgb_digest != right.working_rgb_digest
            or left.source_to_working != right.source_to_working):
        raise FieldError("decoded working images or source transforms differ")
    return ValidatedSourceTransform(left.source_digest, right.source_digest,
                                    left.working_rgb_digest, (1, 0, 0, 0, 1, 0, 0, 0, 1))


def compare_fields(left: SampleGrid, right: SampleGrid, *,
                   source_transform: ValidatedSourceTransform | None = None) -> dict:
    a, b = left.metadata, right.metadata
    for key in ("shape", "kind", "channels", "frame", "units", "value_convention"):
        if a[key] != b[key]:
            raise FieldError(f"incompatible {key}")
    if a["source_digest"] != b["source_digest"]:
        # Identity mapping is meaningful only with an explicitly checked statement
        # that both decoded rasters correspond. A random affine must never make two
        # unrelated images comparable by itself.
        if (not isinstance(source_transform, ValidatedSourceTransform)
                or source_transform.left_source_digest != a["source_digest"]
                or source_transform.right_source_digest != b["source_digest"]
                or source_transform.matrix != (1, 0, 0, 0, 1, 0, 0, 0, 1)
                or not source_transform.decoded_rgb_digest.startswith("sha256:")):
            raise FieldError("source mismatch requires an explicit validated transform")
    if a["source_to_field"] != b["source_to_field"]:
        raise FieldError("field transforms differ")
    diffs = [abs(x-y) for i, (x,y) in enumerate(zip(left.values, right.values))
             if left.valid[i//left.shape[2]] and right.valid[i//right.shape[2]]]
    return {"valid_values": len(diffs), "max_absolute_difference": max(diffs) if diffs else None,
            "mean_absolute_difference": sum(diffs)/len(diffs) if diffs else None,
            "left_hash": left.measurement_hash, "right_hash": right.measurement_hash}
