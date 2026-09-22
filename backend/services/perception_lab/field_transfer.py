"""Validate and copy a Lab session export into fresh Lab-only identities."""
from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import json
import math
from collections.abc import Mapping
from uuid import uuid4

from backend.schemas.perception_lab import LabPlan, LabReview, LabRun, LabSession, PerceptualArtifact
from backend.services.perception_lab.derivations import LabDerivation
from backend.services.perception_lab.field_data import (
    FieldError, MAX_COMPRESSED, _bounded_gunzip, decode_grid)

MAX_EXPORT_BYTES = 80 * 1024 * 1024


def _field_payload(artifact: PerceptualArtifact):
    if artifact.identity.artifact_kind.value == "sample_grid":
        return artifact.measurement.payload
    return None


def _references(value):
    if isinstance(value, Mapping):
        if {"uri", "digest", "media_type"} <= set(value):
            yield value
        else:
            for child in value.values():
                yield from _references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _references(child)


def _validate_legacy_reference(ref, assets) -> None:
    from backend.schemas.perception_lab import DataRef
    pointer = DataRef.model_validate(ref)
    if pointer.media_type != "application/gzip":
        raise FieldError("unsupported legacy DataRef encoding")
    raw = _bounded_gunzip(_asset_bytes(pointer, assets))
    try:
        field = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise FieldError("invalid legacy field JSON") from exc
    shape = field.get("field_shape") if isinstance(field, Mapping) else None
    values = field.get("values") if isinstance(field, Mapping) else None
    if (not isinstance(shape, list) or len(shape) != 2
            or any(type(n) is not int or n <= 0 for n in shape)
            or math.prod(shape) > 16_777_216 or not isinstance(values, list)
            or len(values) != math.prod(shape)
            or any(not isinstance(v, (int, float)) or not math.isfinite(v)
                   or v < 0 or v > 1 for v in values)):
        raise FieldError("invalid legacy field dimensions or values")


def _asset_bytes(ref, assets) -> bytes:
    if ref.uri.startswith("data:application/gzip;base64,"):
        encoded = ref.uri.split(",", 1)[1]
        if len(encoded) > MAX_COMPRESSED * 4 // 3 + 4:
            raise FieldError("encoded field exceeds limit")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise FieldError("invalid field base64") from exc
    elif ref.uri == "lab-asset:" + ref.digest and ref.uri in assets:
        data = assets[ref.uri]
    else:
        raise FieldError("field asset unavailable or reference unsupported")
    if (len(data) > MAX_COMPRESSED or len(data) != ref.bytes
            or "sha256:" + hashlib.sha256(data).hexdigest() != ref.digest):
        raise FieldError("field asset digest or byte count mismatch")
    return data


def attach_field_assets(bundle: Mapping, asset_store) -> dict:
    """Add verified binary assets to the existing #238 export; legacy keys stay intact."""
    out = copy.deepcopy(dict(bundle))
    out["field_assets"] = []
    unavailable = []
    attached = set()
    for raw in out.get("artifacts", []):
        artifact = PerceptualArtifact.model_validate(raw)
        payload = _field_payload(artifact)
        if payload is None:
            for reference in _references(raw):
                try:
                    _validate_legacy_reference(reference, {})
                except FieldError:
                    unavailable.append(reference.get("uri", "unknown"))
            continue
        ref = payload.field_ref
        try:
            if ref.uri.startswith("lab-asset:"):
                try:
                    supplied = asset_store.get(ref.uri)
                except (KeyError, LookupError, ValueError) as exc:
                    raise FieldError("Lab field asset unavailable") from exc
                data = _asset_bytes(ref, {ref.uri: supplied})
            else:
                data = _asset_bytes(ref, {})
            decode_grid(payload.manifest, ref, get_asset=lambda _: data)
        except FieldError:
            unavailable.append(ref.uri)
            continue
        if ref.uri.startswith("lab-asset:") and ref.uri not in attached:
            out["field_assets"].append({"uri": ref.uri, "digest": ref.digest,
                                        "bytes": len(data), "base64": base64.b64encode(data).decode()})
            attached.add(ref.uri)
    out["field_asset_status"] = "complete" if not unavailable else "incomplete"
    out["unavailable_field_assets"] = unavailable
    return out


def _validated_assets(bundle: Mapping) -> dict[str, bytes]:
    if bundle.get("field_asset_status", "complete") != "complete":
        raise FieldError("export has unavailable field assets")
    assets = {}
    for entry in bundle.get("field_assets", []):
        if not isinstance(entry, Mapping) or set(entry) != {"uri", "digest", "bytes", "base64"}:
            raise FieldError("malformed field asset entry")
        encoded = entry["base64"]
        if not isinstance(encoded, str) or len(encoded) > MAX_COMPRESSED * 4 // 3 + 4:
            raise FieldError("encoded field exceeds limit")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise FieldError("invalid field asset base64") from exc
        uri = entry["uri"]
        if (not isinstance(uri, str) or uri != "lab-asset:" + entry["digest"]
                or entry["bytes"] != len(data) or len(data) > MAX_COMPRESSED
                or "sha256:" + hashlib.sha256(data).hexdigest() != entry["digest"]
                or uri in assets):
            raise FieldError("field asset identity, length or digest invalid")
        assets[uri] = data
    return assets


def _remap(value, ids):
    if isinstance(value, str):
        return ids.get(value, value)
    if isinstance(value, list):
        return [_remap(item, ids) for item in value]
    if isinstance(value, dict):
        return {key: _remap(item, ids) for key, item in value.items()}
    return value


def import_session_bundle(bundle: Mapping, *, store, derivation_store, asset_store,
                          target_source=None) -> dict:
    """Prevalidate every record and asset, then write only to the existing Lab stores."""
    if not isinstance(bundle, Mapping):
        raise FieldError("export must be a JSON object")
    try:
        serialized_size = len(json.dumps(bundle))
    except (TypeError, ValueError) as exc:
        raise FieldError("export is not valid JSON data") from exc
    if serialized_size > MAX_EXPORT_BYTES:
        raise FieldError("export exceeds bounded import size")
    if bundle.get("export_kind") != "perception-lab.session-export" or bundle.get("export_version") != 1:
        raise FieldError("unsupported Lab export")
    models = {"session": LabSession, "plans": LabPlan, "runs": LabRun,
              "artifacts": PerceptualArtifact, "reviews": LabReview,
              "derivations": LabDerivation}
    records = {}
    for key, model in models.items():
        if key == "session" and "session" not in bundle:
            raise FieldError("export has no session record")
        values = [bundle[key]] if key == "session" else bundle.get(key, [])
        if not isinstance(values, list) or len(values) > 10000:
            raise FieldError(f"invalid {key} record list")
        records[key] = [model.model_validate(value) for value in values]
    if len(records["session"]) != 1:
        raise FieldError("export must contain one Lab session")
    old_session = records["session"][0]
    if target_source is not None and target_source.image_digest != old_session.source.image_digest:
        raise FieldError("target source digest differs from exported source")
    source_digest = old_session.source.image_digest
    ids = {old_session.session_id: "labs_" + uuid4().hex[:16]}
    id_fields = {"plans": ("plan_id", "plan_"), "runs": ("run_id", "run_"),
                 "artifacts": ("artifact_id", "art_"),
                 "reviews": ("review_id", "review_"),
                 "derivations": ("derivation_id", "der_")}
    old_sets = {}
    for kind, (field, prefix) in id_fields.items():
        keys = [getattr(record.identity if kind == "artifacts" else record, field)
                for record in records[kind]]
        if len(keys) != len(set(keys)) or any(key in ids for key in keys):
            raise FieldError(f"duplicate {kind} identity")
        old_sets[kind] = set(keys)
        ids.update({key: prefix + uuid4().hex[:16] for key in keys})
    if (set(old_session.run_ids) - old_sets["runs"]
            or set(old_session.review_ids) - old_sets["reviews"]
            or set(old_session.selected_artifact_ids) - old_sets["artifacts"]
            or (old_session.active_artifact_id and
                old_session.active_artifact_id not in old_sets["artifacts"])):
        raise FieldError("session references missing exported records")
    for key in ("plans", "runs", "artifacts", "reviews", "derivations"):
        if key in bundle.get("counts", {}) and bundle["counts"][key] != len(records[key]):
            raise FieldError(f"{key} count differs from records")
    for plan in records["plans"]:
        if plan.session_id != old_session.session_id:
            raise FieldError("plan session mismatch")
    for run in records["runs"]:
        if (run.session_id != old_session.session_id or run.requested_plan_id not in old_sets["plans"]
                or any(key not in old_sets["artifacts"] for key in run.artifact_ids)):
            raise FieldError("run ancestry mismatch")
    for artifact in records["artifacts"]:
        if (artifact.identity.session_id != old_session.session_id
                or artifact.identity.run_id not in old_sets["runs"]
                or artifact.provenance.source_image_digest != source_digest
                or any(key not in old_sets["artifacts"] for key in artifact.identity.derived_from)):
            raise FieldError("artifact ancestry or source mismatch")
        if any(ref.artifact_id and ref.artifact_id not in old_sets["artifacts"]
               for ref in artifact.identity.input_refs):
            raise FieldError("artifact input reference missing from export")
    for review in records["reviews"]:
        if review.artifact_id not in old_sets["artifacts"]:
            raise FieldError("review artifact mismatch")
    for derivation in records["derivations"]:
        if (derivation.session_id != old_session.session_id
                or derivation.source_image_digest != source_digest
                or any(key not in old_sets["artifacts"] for key in derivation.input_artifact_ids)):
            raise FieldError("derivation ancestry or source mismatch")
    assets = _validated_assets(bundle)
    for artifact in records["artifacts"]:
        raw = artifact.model_dump(mode="json")
        for reference in _references(raw):
            if artifact.identity.artifact_kind.value != "sample_grid":
                _validate_legacy_reference(reference, assets)
        payload = _field_payload(artifact)
        if payload is not None:
            data = _asset_bytes(payload.field_ref, assets)
            decode_grid(payload.manifest, payload.field_ref, get_asset=lambda _: data)
    # Existing #238 exports have no field_assets and still pass when they carry
    # only their original inline scalar references.
    remapped = {}
    for kind, items in records.items():
        model = models[kind]
        remapped[kind] = [model.model_validate(_remap(item.model_dump(mode="json"), ids))
                          for item in items]
    for uri, data in assets.items():
        if asset_store.put(data) != uri:
            raise FieldError("asset store returned a different identity")
    store.put_session(remapped["session"][0])
    for plan in remapped["plans"]:
        store.put_plan(plan)
    for run in remapped["runs"]:
        store.put_run(run)
    for artifact in remapped["artifacts"]:
        store.put_artifact(artifact)
    for review in remapped["reviews"]:
        store.put_review(review)
    for derivation in remapped["derivations"]:
        derivation_store.put(derivation)
    return {"session_id": ids[old_session.session_id], "identity_map": ids,
            "counts": {key: len(items) for key, items in remapped.items()}}
