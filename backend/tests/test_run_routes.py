"""
CIRCUIT-002 SURFACE-002 — the four run routes, over fakes.

`test_run_surface.py` pins the ENGINE; this pins the SURFACE a person actually touches: start,
poll, stream, answer. The store is a `FakeCollection`, the posts are raw, the producers are fake,
and the planner is offline — so the whole arc runs in a couple of seconds with no GPU, no network
and no database.

The one thing only this file can test: an `awaiting_answer` run answered in a SEPARATE REQUEST is
the same run. A3 made the answer resumable inside one process; the store and these routes are what
carry that across the boundary a curator actually crosses.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time

import pytest
from bson.objectid import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import runs as R
from backend.services import epistemics, run_store
from backend.services.director import run_surface as rs
from backend.tests.test_circulation_spine_p1 import FakeCollection

_A = ObjectId("507f1f77bcf86cd799439031")
_B = ObjectId("507f1f77bcf86cd799439032")

TERMINAL = (rs.STATUS_COMPLETE, rs.STATUS_STOPPED, rs.STATUS_AWAITING_ANSWER)


def _raw_post(oid, title):
    return {"_id": oid, "photo_url": f"scratch://{title}.jpg", "title": title,
            "general_tags": ["facade"], "updated_at": "2026-08-01T00:00:00Z"}


def _hash(doc):
    return hashlib.sha256(json.dumps(doc, sort_keys=True, default=str).encode()).hexdigest()


@pytest.fixture
def wired(monkeypatch):
    """A minimal app holding only the run routes, with every boundary faked.

    The router is mounted WITHOUT the API-key dependency: what is under test is the route, and an
    auth wrapper it does not own would only be re-testing `require_api_key`.
    """
    import backend.routers.posts as P
    import backend.services.director.argument_planner as ap
    import backend.services.director.composition as comp
    import backend.services.director.groq_planner as gp
    import backend.services.segmentation_service as seg
    import backend.services.dinov2_service as dsvc

    # BOTH planners and the composer, or a route test would quietly reach the real API.
    monkeypatch.setattr(gp.GroqPlanner, "_get_client", lambda self: None)
    monkeypatch.setattr(ap.GroqArgumentPlanner, "_get_client", lambda self: None)
    monkeypatch.setattr(comp.LLM, "from_service", classmethod(lambda cls: None))
    monkeypatch.setattr(seg, "is_available", lambda: True)
    monkeypatch.setattr(seg, "segment_image_bytes",
                        lambda data, **k: [{"id": f"seg_{i}", "geometry_rev": 0,
                                            "box": {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.3},
                                            "mask_rle": None} for i in range(2)])
    monkeypatch.setattr(dsvc, "is_available", lambda: True)

    async def _fetch(post_id, post):
        return b"\x89PNG-fake"
    monkeypatch.setattr(P, "_fetch_post_image_cached", _fetch)

    def _mk(role):
        async def _handler(post_id, post, region, req, run_id):
            return [epistemics.stamp({
                "producer": role, "type": "brush_field", "role": role,
                "geometry": {"kind": "soft_mask",
                             "strokes": [{"points": [[0.5, 0.5]], "radius": 0.05}]},
                "provenance": {"model": f"fake::{role}", "adapter": role, "run_id": run_id},
                "confidence": 0.6})], "ready", True
        return _handler
    for name in ("material_field", "rhythm", "pressure_zone", "negative_space",
                 "presence_check", "light_field", "shadow_field"):
        monkeypatch.setitem(P._FIELD_PRODUCERS, name, _mk(name))

    posts = FakeCollection()
    posts.docs[_A] = _raw_post(_A, "A")
    posts.docs[_B] = _raw_post(_B, "B")
    runs_coll = FakeCollection()

    monkeypatch.setattr(R, "post_collection", posts)
    # The store's collection is resolved lazily per call; point every one of them at the fake.
    monkeypatch.setattr(run_store, "_collection", lambda collection=None: runs_coll)

    app = FastAPI()
    app.include_router(R.router, prefix="/api/v1/runs")
    with TestClient(app) as client:
        yield client, posts, runs_coll


def _await_terminal(client, run_id, timeout=30.0):
    """Poll until the run reaches a state a person could act on."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/v1/runs/{run_id}").json()
        if body.get("status") in TERMINAL:
            return body
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} never reached a terminal state")


# ── starting a run ────────────────────────────────────────────────────────────

def test_a_prompt_and_a_set_of_images_is_the_whole_input(wired):
    client, posts, _ = wired
    before = {k: _hash(v) for k, v in posts.docs.items()}

    started = client.post("/api/v1/runs", json={"prompt": "read the material of the surface",
                                                "image_ids": [str(_A), str(_B)]})
    assert started.status_code == 200
    run_id = started.json()["run_id"]

    body = _await_terminal(client, run_id)
    assert body["status"] == rs.STATUS_COMPLETE
    assert body["intention"] == "read the material of the surface"
    assert [c["post_id"] for c in body["corpus"]] == [str(_A), str(_B)]
    assert body["suggestions"] and body["production_records"]
    # SUGGESTIONS-ONLY, at the route: not one post document moved.
    assert {k: _hash(v) for k, v in posts.docs.items()} == before


def test_tags_can_stand_in_for_ids(wired):
    client, _, _ = wired
    started = client.post("/api/v1/runs", json={"prompt": "read the material", "tags": ["facade"]})
    body = _await_terminal(client, started.json()["run_id"])
    assert {c["post_id"] for c in body["corpus"]} == {str(_A), str(_B)}


def test_a_run_needs_a_prompt_and_at_least_one_image(wired):
    client, _, _ = wired
    assert client.post("/api/v1/runs", json={"prompt": "  ", "image_ids": [str(_A)]}).status_code == 422
    assert client.post("/api/v1/runs", json={"prompt": "look"}).status_code == 422
    # named images that do not exist is a 404 — not an empty run, which would read as "I looked
    # and found nothing" about pictures nobody ever had.
    missing = client.post("/api/v1/runs",
                          json={"prompt": "look", "image_ids": [str(ObjectId())]})
    assert missing.status_code == 404


def test_an_unknown_run_is_a_404_everywhere(wired):
    client, _, _ = wired
    assert client.get("/api/v1/runs/run_nope").status_code == 404
    assert client.post("/api/v1/runs/run_nope/answer", json={"answer": "x"}).status_code == 404


# ── polling and streaming agree ───────────────────────────────────────────────

def test_the_stream_and_the_poll_return_the_same_shape(wired):
    client, _, _ = wired
    run_id = client.post("/api/v1/runs", json={"prompt": "read the material",
                                               "image_ids": [str(_A)]}).json()["run_id"]
    polled = _await_terminal(client, run_id)

    with client.stream("GET", f"/api/v1/runs/{run_id}/events") as stream:
        assert stream.headers["content-type"].startswith("text/event-stream")
        frames = []
        for line in stream.iter_lines():
            if line.startswith("data: "):
                frames.append(json.loads(line[len("data: "):]))
                break
    assert frames, "the stream said something"
    assert set(frames[0]) == set(polled), "a client that cannot hold a stream gets the same truth"
    assert frames[0]["run_id"] == polled["run_id"]


def test_the_listing_finds_the_run_just_started(wired):
    client, _, _ = wired
    run_id = client.post("/api/v1/runs", json={"prompt": "read the material",
                                               "image_ids": [str(_A)]}).json()["run_id"]
    _await_terminal(client, run_id)
    listed = client.get("/api/v1/runs").json()["runs"]
    assert any(r["run_id"] == run_id for r in listed)


# ── A3 across the request boundary ────────────────────────────────────────────

def test_a_run_that_needs_a_phrase_asks_and_waits(wired):
    client, _, runs_coll = wired
    run_id = client.post("/api/v1/runs", json={"prompt": "check whether it is present",
                                               "image_ids": [str(_A)]}).json()["run_id"]
    body = _await_terminal(client, run_id)

    assert body["status"] == rs.STATUS_AWAITING_ANSWER
    assert body["question"]["missing_param"] == "phrase"
    assert body["question"]["text"]
    # and the state to continue from was actually written down
    stored = runs_coll.docs[run_id]
    assert run_store.is_answerable(stored)
    assert stored["resume"]["question"]["actuator"] == "presence_check"


@pytest.mark.ml          # drives a real producer; see conftest
def test_the_answer_arrives_in_a_SEPARATE_request_and_continues_the_same_run(wired):
    """The whole point of the store. A3 resumes a loop inside one process; a curator answers
    minutes later over a new request, and it has to be the same run — one receipt, not two."""
    client, posts, _ = wired
    before = {k: _hash(v) for k, v in posts.docs.items()}
    run_id = client.post("/api/v1/runs", json={"prompt": "check whether it is present",
                                               "image_ids": [str(_A)]}).json()["run_id"]
    asked = _await_terminal(client, run_id)
    assert asked["status"] == rs.STATUS_AWAITING_ANSWER

    answered = client.post(f"/api/v1/runs/{run_id}/answer", json={"answer": "a cross"})
    assert answered.status_code == 200
    body = answered.json()

    assert body["run_id"] == run_id                          # the SAME run
    assert body["answer"]["accepted"] is True
    assert body["answer"]["source"] == "curator"
    assert len(body["rounds"]) > len(asked["rounds"])        # the trace EXTENDS
    assert [r["round"] for r in body["rounds"]] == list(range(len(body["rounds"])))
    ran = [p for p in body["production_records"]
           if p["actuator"] == "presence_check" and p["status"] == "ok"]
    assert ran, "the blocked step ran once the curator supplied the phrase"
    # a later GET sees the continued run, not the paused one
    assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == body["status"]
    # and answering still committed nothing
    assert {k: _hash(v) for k, v in posts.docs.items()} == before


def test_a_run_not_waiting_for_an_answer_refuses_one(wired):
    client, _, _ = wired
    run_id = client.post("/api/v1/runs", json={"prompt": "read the material",
                                               "image_ids": [str(_A)]}).json()["run_id"]
    _await_terminal(client, run_id)
    refused = client.post(f"/api/v1/runs/{run_id}/answer", json={"answer": "a cross"})
    assert refused.status_code == 409
    assert "not waiting for an answer" in refused.json()["detail"]


def test_an_answered_run_cannot_be_answered_twice(wired):
    """Once the run has moved on, the stale resume state is gone — a late answer cannot resume a
    run that has already continued without it."""
    client, _, _ = wired
    run_id = client.post("/api/v1/runs", json={"prompt": "check whether it is present",
                                               "image_ids": [str(_A)]}).json()["run_id"]
    _await_terminal(client, run_id)
    assert client.post(f"/api/v1/runs/{run_id}/answer",
                       json={"answer": "a cross"}).status_code == 200
    again = client.post(f"/api/v1/runs/{run_id}/answer", json={"answer": "a cross"})
    assert again.status_code == 409


# ── honest emptiness, at the route ────────────────────────────────────────────

def test_a_prompt_nothing_serves_comes_back_as_a_run_that_says_so(wired):
    client, _, _ = wired
    run_id = client.post("/api/v1/runs", json={"prompt": "mumble",
                                               "image_ids": [str(_A)]}).json()["run_id"]
    body = _await_terminal(client, run_id)
    assert body["status"] == rs.STATUS_STOPPED
    assert body["stop_reason"] == "nothing_planned"
    assert body["suggestions"] == [] and body["production_records"] == []


# ── the serialization boundary: a cycle costs a marker, never the run ─────────

def test_the_store_projects_a_cyclic_view_instead_of_dying_on_it():
    """The guard that means the NEXT cycle is a visible marker in one field rather than a dead
    run. This is the exact shape argue mode used to build, and the exact way it died.

    Note this is defence, not the fix: the cycle itself is gone at its source in
    `run_surface.compose_for_run`. Something has to hold the line at the boundary anyway, because
    `RecursionError` at BSON-encode time is about as opaque a failure as this system can produce
    — it reached the curator as `run_failed:RecursionError` with no article and no rounds.
    """
    from bson import BSON

    article = {"title": "t", "sections": [{"citations": [{"step_id": "s1"}]}]}
    article["resolved"] = {"version": 1, "draft": article, "resolved": {}}

    breaks = []
    projected = run_store.acyclic({"article": article}, _breaks=breaks)

    assert breaks == ["view.article.resolved.draft"]
    assert projected["article"]["resolved"]["draft"] == {"$cycle": "view.article.resolved.draft"}
    # everything that was not the back-pointer is untouched
    assert projected["article"]["sections"][0]["citations"][0] == {"step_id": "s1"}
    BSON.encode({"view": projected})


def test_a_shared_reference_is_not_a_cycle_and_survives_whole():
    """Identity is tracked over ANCESTORS only. The same citation dict referenced from two
    sections is a DAG — perfectly encodable, and gutting it would be a worse bug than the one
    this guard exists to catch."""
    shared = {"step_id": "c0", "geometry": {"kind": "soft_mask"}}
    view = {"sections": [{"citations": [shared]}, {"citations": [shared]}]}

    breaks = []
    projected = run_store.acyclic(view, _breaks=breaks)

    assert breaks == []
    assert projected["sections"][0]["citations"][0] == shared
    assert projected["sections"][1]["citations"][0] == shared


def test_runaway_nesting_is_bounded_rather_than_recursed():
    """A structure deep enough to exhaust the stack without ever repeating an object. Depth is
    bounded separately from cycle detection because they are different pathologies."""
    from bson import BSON

    deep = {}
    node = deep
    for _ in range(run_store.MAX_ENCODE_DEPTH + 40):
        node["next"] = {}
        node = node["next"]
    node["leaf"] = True

    breaks = []
    projected = run_store.acyclic(deep, _breaks=breaks)
    assert breaks and all(b.startswith("view.next") for b in breaks)
    BSON.encode(projected)


def test_a_healthy_save_records_no_repairs(wired):
    """`encoding_repairs` is empty on every sound run, so a non-empty one is a real signal."""
    client, _, runs_coll = wired
    run_id = client.post("/api/v1/runs", json={"prompt": "check whether it is present",
                                               "image_ids": [str(_A)]}).json()["run_id"]
    _await_terminal(client, run_id)
    stored = runs_coll.docs[run_id]
    assert stored.get("encoding_repairs") == []
