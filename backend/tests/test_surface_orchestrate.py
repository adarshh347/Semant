"""
CIRCUIT-001 SURFACE-001 — the orchestrate endpoint.

Intention → the Director plans + executes (WIRE) → quarantined suggestions for supervised review.
These run WITHOUT a GPU and WITHOUT the network: the Groq client is forced offline (deterministic
rule-based planning) and the produce-field handlers are faked. What's under test is the ENDPOINT —
hydrating memory from the real post, returning the resolved plan (steps + refused, each with its
distinct reason), the suggestions, and the chain provenance — and the hard rule: a plan run leaves
the post byte-identical.
"""
from __future__ import annotations

import copy

import pytest
from bson.objectid import ObjectId

from backend.routers import posts as R
from backend.tests.test_circulation_spine_p1 import FakeCollection, run

_OID = ObjectId("507f1f77bcf86cd799439012")


def _seed_post(regions=None):
    posts = FakeCollection()
    posts.docs[_OID] = {"_id": _OID, "photo_url": "scratch://x.jpg",
                        "region_annotations": regions or [], "updated_at": "2026-07-26T00:00:00Z"}
    return posts


@pytest.fixture(autouse=True)
def _offline_planner(monkeypatch):
    """Force the deterministic rule-based planner — CI must not depend on the Groq API."""
    import backend.services.director.groq_planner as gp
    monkeypatch.setattr(gp.GroqPlanner, "_get_client", lambda self: None)


def _fake_shading(monkeypatch):
    """light_field + shadow_field report available and return a canned suggestion each — no GPU."""
    import backend.services.intrinsic_service as isvc
    monkeypatch.setattr(isvc, "is_available", lambda: True)

    async def _fetch(post_id, post):
        return b"\x89PNG-fake"
    monkeypatch.setattr(R, "_fetch_post_image_cached", _fetch)

    def _mk(role):
        async def _handler(post_id, post, region, req, run_id):
            return [{"producer": role, "type": "brush_field", "role": role,
                     "geometry": {"kind": "soft_mask", "strokes": [{"points": [[0.5, 0.5]], "radius": 0.05}]},
                     "provenance": {"model": "intrinsic_ordinal_shading", "adapter": "intrinsic", "run_id": run_id},
                     "confidence": 0.65}], "ready", True
        return _handler
    monkeypatch.setitem(R._FIELD_PRODUCERS, "light_field", _mk("light_field"))
    monkeypatch.setitem(R._FIELD_PRODUCERS, "shadow_field", _mk("shadow_field"))


def test_orchestrate_plan_suggestions_and_a_refused_step(monkeypatch):
    """'trace the light' on a bare post → light_field + shadow_field RUN (suggestions), and
    semantic_read is REFUSED (it needs a region none exists) — the partial plan is reported, not
    hidden."""
    monkeypatch.setattr(R, "post_collection", _seed_post())
    _fake_shading(monkeypatch)

    out = run(R.orchestrate(str(_OID), R.OrchestrateRequest(intention="trace the light")))

    ran = [s["actuator"] for s in out["plan"]["steps"]]
    assert "light_field" in ran and "shadow_field" in ran
    # the refused step is present WITH its reason — never dropped silently
    refused = {r["actuator"]: r["reason"] for r in out["plan"]["refused"]}
    assert refused.get("semantic_read") == "missing_input"
    # both shading steps produced a quarantined suggestion (never a mark)
    assert len(out["suggestions"]) == 2
    assert {s["role"] for s in out["suggestions"]} == {"light_field", "shadow_field"}
    # provenance names each step's status; the refusal shows up as a gap
    statuses = {r["actuator"]: r["status"] for r in out["provenance"]["lineage"]}
    assert statuses["light_field"] == "ok" and statuses["shadow_field"] == "ok"
    assert any(g["actuator"] == "semantic_read" for g in out["provenance"]["gaps"])


def test_orchestrate_missing_param_is_refused(monkeypatch):
    """'how many …' plans `enumerate`, which needs a phrase; rule-based gives none, so the plan
    REFUSES it with `missing_param` — and says so."""
    monkeypatch.setattr(R, "post_collection", _seed_post())

    out = run(R.orchestrate(str(_OID), R.OrchestrateRequest(intention="how many arches")))

    assert out["plan"]["steps"] == []
    assert any(r["actuator"] == "enumerate" and r["reason"] == "missing_param"
               for r in out["plan"]["refused"])
    assert out["suggestions"] == []


def test_orchestrate_unresolvable_intention_is_honest(monkeypatch):
    monkeypatch.setattr(R, "post_collection", _seed_post())

    out = run(R.orchestrate(str(_OID), R.OrchestrateRequest(intention="zxqw nonsense")))

    assert out["plan"]["steps"] == []
    assert out["suggestions"] == []
    assert any("nothing was planned" in n or "matches" in n for n in out["plan"]["notes"])


def test_orchestrate_never_mutates_the_post(monkeypatch):
    posts = _seed_post()
    monkeypatch.setattr(R, "post_collection", posts)
    _fake_shading(monkeypatch)
    before = copy.deepcopy(posts.docs[_OID])

    run(R.orchestrate(str(_OID), R.OrchestrateRequest(intention="trace the light")))

    assert posts.docs[_OID] == before                     # byte-identical: suggestions only
    assert posts.docs[_OID]["updated_at"] == before["updated_at"]


def test_orchestrate_requires_an_intention(monkeypatch):
    monkeypatch.setattr(R, "post_collection", _seed_post())
    with pytest.raises(Exception):
        run(R.orchestrate(str(_OID), R.OrchestrateRequest(intention="   ")))
