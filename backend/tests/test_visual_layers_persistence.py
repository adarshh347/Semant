"""
CIRCUIT-001 QUALITY-001 (Q-C) — visual_layers persistence.

The render layers' saved visibility/opacity ride the same additive PATCH as visual_marks, so a
layer a curator hides stays hidden across reload. These tests pin the round-trip WITHOUT a DB:
a PATCH carrying visual_layers is written via $set, and the GET serialization (post_helper)
surfaces it back.
"""
from bson.objectid import ObjectId

from backend.routers import posts as R
from backend.schemas.post import PostUpdate
from backend.tests.test_circulation_spine_p1 import FakeCollection, run

_OID = ObjectId("507f1f77bcf86cd799439011")


def _seed():
    posts = FakeCollection()
    posts.docs[_OID] = {"_id": _OID, "photo_url": "http://x/y.jpg"}
    return posts


def test_patch_writes_and_get_surfaces_visual_layers(monkeypatch):
    posts = _seed()
    monkeypatch.setattr(R, "post_collection", posts)

    layers = [
        {"key": "find_parts", "visibility": False, "opacity": 0.4, "order": 10},
        {"key": "field:material_field", "visibility": True, "opacity": 1, "order": 51},
    ]
    result = run(R.update_post(str(_OID), PostUpdate(visual_layers=layers)))

    # $set wrote it onto the stored doc …
    assert posts.docs[_OID]["visual_layers"] == layers
    # … and the GET serialization surfaces it back (round-trip across reload).
    assert result["visual_layers"] == layers


def test_visual_layers_is_optional_and_additive(monkeypatch):
    """A PATCH that does not mention visual_layers must not touch them (exclude_unset), so a
    grounds-only save never wipes a curator's hidden layers."""
    posts = _seed()
    posts.docs[_OID]["visual_layers"] = [{"key": "find_parts", "visibility": False}]
    monkeypatch.setattr(R, "post_collection", posts)

    run(R.update_post(str(_OID), PostUpdate(grounds=[{"id": "g1", "ground_type": "region"}])))

    # untouched by a save that only carried grounds
    assert posts.docs[_OID]["visual_layers"] == [{"key": "find_parts", "visibility": False}]
    assert posts.docs[_OID]["grounds"] == [{"id": "g1", "ground_type": "region"}]
