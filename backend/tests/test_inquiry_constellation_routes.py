"""HTTP persistence and concurrency; the only writable collection is session history."""
import copy
import time

from backend.tests.test_inquiry_session_routes import wired, _start, _settled


def body(session):
    text = session["prompt"]
    return {"expected_checkpoint": session["checkpoint"], "thought": {
        "organising_question": "What relationship should survive?",
        "anchors": [{"origin": "user_prompt", "source_id": "prompt",
                     "span": [0, len(text)], "exact_text": text}],
        "authorship": {"kind": "human", "actor": "synthetic-test-person"},
        "confirmed_by": "synthetic-test-person"}}


def test_prepare_route_persists_before_any_model_and_resumes_same_session(wired):
    client, posts, sessions = wired
    posts_before = copy.deepcopy(posts.docs)
    first = _start(client, prepare_thought=True).json()
    sid = first["session_id"]
    base = f"/api/v1/inquiries/{sid}"
    assert first["state"] == "awaiting_user" and first["stages"] == []
    assert first["semantic_constellations"]["preparation"] == "prompt"
    denied = client.post(base + "/preparation/continue", json={"expected_checkpoint": first["checkpoint"]})
    assert denied.status_code == 422
    saved = client.post(base + "/constellations", json=body(first))
    assert saved.status_code == 200
    saved = saved.json()
    assert len(saved["semantic_constellations"]["history"]) == 1
    again = client.get(base).json()
    assert again["semantic_constellations"] == saved["semantic_constellations"]
    # Old clients cannot overwrite the intervening human write.
    stale = client.post(base + "/constellations", json=body(first))
    assert stale.status_code == 409
    continued = client.post(base + "/preparation/continue", json={"expected_checkpoint": saved["checkpoint"]})
    assert continued.status_code == 200
    for _ in range(100):
        paused = client.get(base).json()
        if paused["semantic_constellations"]["preparation"] == "compiler":
            break
        time.sleep(0.01)
    assert paused["semantic_constellations"]["preparation"] == "compiler"
    assert "compiler" not in [x["stage"] for x in paused["stages"]]
    assert paused["semantic_constellations"]["sources"][1]["origin"] == "model_reading"
    # Lease release can advance the checkpoint after the paused SSE frame.
    for _ in range(100):
        paused = client.get(base).json()
        res = client.post(base + "/preparation/continue", json={"expected_checkpoint": paused["checkpoint"]})
        if res.status_code == 200:
            break
        time.sleep(0.01)
    assert res.status_code == 200
    for _ in range(100):
        done = client.get(base).json()
        if done["graph"]["claims"]:
            break
        time.sleep(0.01)
    assert done["session_id"] == sid
    assert done["semantic_constellations"]["history"][0]["timing"] == "before_compilation"
    assert done["semantic_constellations"]["current"][0]["inspection"] is not None
    assert posts.docs == posts_before
    assert posts.writes == 0
    assert set(sessions.docs) == {sid}


def test_retrospective_route_edit_review_export_and_source_validation(wired):
    client, posts, _ = wired
    original = copy.deepcopy(posts.docs)
    s = _settled(client, _start(client))
    base = f"/api/v1/inquiries/{s['session_id']}"
    invalid = body(s)
    invalid["thought"]["anchors"][0]["exact_text"] = "x" * len(s["prompt"])
    assert client.post(base + "/constellations", json=invalid).status_code == 422
    res = client.post(base + "/constellations", json=body(s))
    assert res.status_code == 200
    s = res.json()
    row = s["semantic_constellations"]["current"][0]
    assert row["timing"] == "retrospective"
    graph = copy.deepcopy(s["graph"])
    review = {"expected_checkpoint": s["checkpoint"], "expected_constellation_revision": row["revision"],
              "graph_hash": row["inspection"]["graph"]["graph_hash"], "actor": "synthetic-test-person",
              "judgment": {"value": "unclear", "note": "Legacy graph lacks source-to-atom lineage."}}
    res = client.post(base + f"/constellations/{row['constellation_id']}/review", json=review)
    assert res.status_code == 200
    s = res.json()
    assert s["graph"] == graph
    assert s["semantic_constellations"]["current"][0]["judgment"]["assessed_by"] == "synthetic-test-person"
    assert client.get(base).json()["semantic_constellations"] == s["semantic_constellations"]
    assert posts.docs == original
    assert posts.writes == 0
