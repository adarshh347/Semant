"""Controlled Lab-only asset bytes. No source or canonical collection is writable here."""
from __future__ import annotations

import hashlib

from backend.services.perception_lab.field_data import FieldError, MAX_COMPRESSED


def asset_uri(data: bytes) -> str:
    if not data or len(data) > MAX_COMPRESSED:
        raise FieldError("field asset exceeds compressed limit")
    return "lab-asset:sha256:" + hashlib.sha256(data).hexdigest()


class InMemoryFieldAssets:
    def __init__(self):
        self._values: dict[str, bytes] = {}

    def put(self, data: bytes) -> str:
        uri = asset_uri(data)
        self._values[uri] = bytes(data)
        return uri

    def get(self, uri: str) -> bytes:
        if uri not in self._values:
            raise FieldError("Lab asset unavailable")
        data = self._values[uri]
        if asset_uri(data) != uri:
            raise FieldError("Lab asset digest mismatch")
        return data


class MongoFieldAssets:
    """A digest-keyed binary collection alongside the existing Lab stores."""

    def __init__(self, collection=None):
        self._collection = collection

    def _c(self):
        if self._collection is None:
            from backend.database import sync_database
            self._collection = sync_database().get_collection("perception_lab_field_assets")
        return self._collection

    def put(self, data: bytes) -> str:
        uri = asset_uri(data)
        self._c().update_one({"_id": uri}, {"$setOnInsert": {
            "kind": "perception_lab_field_asset", "data": bytes(data), "bytes": len(data),
        }}, upsert=True)
        return uri

    def get(self, uri: str) -> bytes:
        if not uri.startswith("lab-asset:sha256:") or len(uri) != 81:
            raise FieldError("invalid Lab asset URI")
        doc = self._c().find_one({"_id": uri, "kind": "perception_lab_field_asset"})
        if not doc or not isinstance(doc.get("data"), bytes):
            raise FieldError("Lab asset unavailable")
        data = doc["data"]
        if asset_uri(data) != uri or len(data) != doc.get("bytes"):
            raise FieldError("Lab asset digest or byte count mismatch")
        return data
