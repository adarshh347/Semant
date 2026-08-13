"""
PERCEPTUAL-ORGANS-002 Lane F1 — the vertical, driven through HTTP.

Every test here goes through the same door a browser uses: a post id in, a session out, a plan
proposed in one request and executed in another, and a run record read off the wire. What is faked
is the segmenter and the two collections; the Extent façade, the Topology organs, the resolver, the
conductor, the store and the router are the real ones.

THE FOUR CLAIMS THIS FILE EXISTS FOR, because they cannot be checked anywhere else:

    the post is byte-identical afterwards     — hashed before and after, through the route
    the ledger is untouched                   — no write of any kind to the post collection
    an instance ref survives the wire         — JSON in, and the organ measures that one mask
    a replay has nothing to call              — the handler builds a sealed registry, not a live one

`FakeCollection` counts its writes, so "nothing was written" is a number rather than a promise.
"""
from __future__ import annotations

import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.schemas.perception_lab import (CapabilityState, ExecutionIdentity, LabRun, LabSession,
                                            PerceptualArtifact, RunOutcome)
from backend.routers import perception_lab as R
from backend.services.perception_lab.mongo_store import MongoLabStore
from backend.tests.fixtures import perception_lab_live as F

PREFIX = "/api/v1/perception-lab"


class Wiring:
    """The world one test runs in, and the two knobs a test turns.

    `adapters` is the segmenter table; `posts` is the corpus. Both are read at request time rather
    than at fixture time, so a test can make SAM disappear between two requests of one session —
    which is exactly the situation the capability vocabulary exists for.
    """

    def __init__(self):
        self.posts = F.AsyncFakeCollection([F.post_document()])
        #: The SAME documents, through the synchronous shape the probe uses. Two copies would let
        #: a mutation be visible to the reader and invisible to the probe.
        self.probe_posts = self.posts.sync_view()
        self.collections = F.lab_collections()
        self.adapters = F.extent_adapters()
        self.image = F.png_bytes()

    @property
    def store(self):
        return MongoLabStore(self.collections)

    @property
    def lab_writes(self):
        return sum(c.writes for c in self.collections.values())

    def mutate_post(self, **fields):
        for doc in self.posts.docs.values():
            doc.update(fields)


@pytest.fixture
def wired(monkeypatch):
    """The lab routes on their own app, without the API-key dependency.

    Mounted bare because what is under test is the route; an auth wrapper it does not own would
    only be re-testing `require_api_key`.
    """
    w = Wiring()

    async def _open_source(post_id: str):
        from backend.services.perception_lab import source as src
        post = await src.read_post(post_id, collection=w.posts)
        return src.snapshot_from(post, w.image)

    def _conductor(snapshot, store):
        from backend.services.perception_lab.live import conductor_for
        return conductor_for(snapshot, store=store, extent_adapters=w.adapters,
                             probe_collection=w.probe_posts)

    async def _list_sources(limit: int):
        from backend.services.perception_lab import source as src
        return await src.list_sources(limit=limit, collection=w.posts)

    monkeypatch.setattr(R, "_store", lambda: w.store)
    monkeypatch.setattr(R, "_open_source", _open_source)
    monkeypatch.setattr(R, "_list_sources", _list_sources)
    monkeypatch.setattr(R, "_conductor", _conductor)

    app = FastAPI()
    app.include_router(R.router, prefix=PREFIX)
    with TestClient(app) as client:
        yield client, w


# ── helpers ──────────────────────────────────────────────────────────────────


def _session(client, organ="extent", mode="isolation"):
    res = client.post(f"{PREFIX}/sessions",
                      json={"post_id": F.POST_ID, "selected_organ": organ, "mode": mode})
    assert res.status_code == 201, res.text
    return res.json()


def _plan(client, sid, **body):
    res = client.post(f"{PREFIX}/sessions/{sid}/plans", json=body)
    assert res.status_code == 201, res.text
    return res.json()["plan"]


def _run(client, sid, plan_id, **body):
    res = client.post(f"{PREFIX}/sessions/{sid}/runs",
                      json={"plan_id": plan_id, **body})
    assert res.status_code == 201, res.text
    return res.json()


def _find_all(client, sid, **params):
    plan = _plan(client, sid, planner="direct",
                 commands=[{"operation": "extent.find_all", "parameters": params}])
    return _run(client, sid, plan["plan_id"])


# ── opening ──────────────────────────────────────────────────────────────────


def test_the_first_response_carries_the_real_source_and_not_a_placeholder(wired):
    client, w = wired
    body = _session(client)

    assert body["execution_identity"] == "LIVE"
    source = body["source"]
    assert source["post_id"] == F.POST_ID
    assert source["image_digest"].startswith("sha256:")
    assert (source["natural_width"], source["natural_height"]) == (F.WIDTH, F.HEIGHT)
    assert source["region_count"] == 2
    assert body["session"]["source"]["image_digest"] == source["image_digest"]


def test_a_post_that_is_not_there_is_a_404_and_not_an_empty_session(wired):
    client, w = wired
    res = client.post(f"{PREFIX}/sessions",
                      json={"post_id": "64b7f1a2c3d4e5f607182999"})
    assert res.status_code == 404
    assert res.json()["detail"]["error"] == "unknown_post"
    assert w.lab_writes == 0


def test_an_organ_this_lab_does_not_have_is_refused_at_the_door(wired):
    client, w = wired
    res = client.post(f"{PREFIX}/sessions", json={"post_id": F.POST_ID, "selected_organ": "smell"})
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "unknown_organ"


# ── the vertical ─────────────────────────────────────────────────────────────


def test_a_control_press_reaches_the_real_extent_organ_over_http(wired):
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    body = _find_all(client, sid)

    assert body["execution_identity"] == "LIVE"
    assert body["outcome"] == "ready"
    LabRun.model_validate(body["run"])
    artifact = PerceptualArtifact.model_validate(body["artifacts"][0])
    assert artifact.identity.artifact_kind.value == "extent_set"
    assert len(artifact.measurement.payload.instances) == 2
    assert w.adapters["yolo_sam2_auto"].calls


def test_a_sentence_reaches_the_same_organ_as_the_control(wired):
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    plan = _plan(client, sid, planner="rules", prompt="what is in this picture?")
    body = _run(client, sid, plan["plan_id"])

    assert [s["operation"] for s in plan["resolved_steps"]] == ["extent.find_all"]
    assert body["outcome"] == "ready"
    # The prompt turn is recorded on the session — the words, and the plan they became.
    turns = body["session"]["prompt_turns"]
    assert turns[-1]["text"] == "what is in this picture?"
    assert turns[-1]["plan_id"] == plan["plan_id"]


def test_planning_does_not_run_anything(wired):
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    _plan(client, sid, planner="direct", commands=[{"operation": "extent.find_all"}])
    assert w.adapters["yolo_sam2_auto"].calls == []


def test_an_instance_ref_survives_the_wire_the_resolver_and_the_organ(wired):
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    extents = _find_all(client, sid)
    artifact = extents["artifacts"][0]
    aid = artifact["identity"]["artifact_id"]
    ids = [i["instance_id"] for i in artifact["measurement"]["payload"]["instances"]]

    updated = client.patch(f"{PREFIX}/sessions/{sid}", json={
        "selected_organ": "topology",
        "selected_artifact_ids": [aid],
        "selected_instance_refs": [{"artifact_id": aid, "instance_id": i} for i in ids]})
    assert updated.status_code == 200, updated.text
    assert updated.json()["session"]["selected_instance_refs"] == [
        {"artifact_id": aid, "instance_id": i} for i in ids]

    plan = _plan(client, sid, planner="direct", commands=[{
        "operation": "topology.containment",
        "input_refs": [
            {"role": "source", "scope": "session", "artifact_id": aid, "instance_id": ids[1]},
            {"role": "target", "scope": "session", "artifact_id": aid, "instance_id": ids[0]}]}])
    body = _run(client, sid, plan["plan_id"])

    assert body["outcome"] == "ready"
    relation = body["artifacts"][0]["measurement"]["payload"]["relations"][0]
    assert relation["source"]["instance_id"] == ids[1]
    assert relation["target"]["instance_id"] == ids[0]
    assert relation["measurements"]["containment"] == pytest.approx(1.0)


def test_an_instance_the_session_never_selected_is_refused_over_http_by_name(wired):
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    aid = _find_all(client, sid)["artifacts"][0]["identity"]["artifact_id"]
    client.patch(f"{PREFIX}/sessions/{sid}", json={"selected_organ": "topology",
                                                   "selected_artifact_ids": [aid]})

    plan = _plan(client, sid, planner="direct", commands=[{
        "operation": "topology.containment",
        "input_refs": [
            {"role": "source", "scope": "session", "artifact_id": aid, "instance_id": "inst_9"},
            {"role": "target", "scope": "session", "artifact_id": aid, "instance_id": "inst_8"}]}])

    assert plan["resolved_steps"] == []
    refusal = plan["refusals"][0]
    assert refusal["code"] == "unknown_reference"
    assert refusal["missing"] == [f"{aid}#inst_9"]


def test_a_malformed_reference_is_a_422_about_the_request_not_a_lab_refusal(wired):
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    res = client.post(f"{PREFIX}/sessions/{sid}/plans", json={
        "planner": "direct",
        "commands": [{"operation": "topology.containment",
                      "input_refs": [{"role": "source", "scope": "session",
                                      "instance_id": "inst_1"}]}]})
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "invalid_input_ref"


# ── the six outcomes ─────────────────────────────────────────────────────────


def test_all_six_outcomes_survive_the_api(wired):
    client, w = wired

    # ready
    sid = _session(client)["session"]["session_id"]
    assert _find_all(client, sid)["outcome"] == "ready"

    # empty — it looked and found nothing, and says what it looked for
    w.adapters = F.extent_adapters(
        yolo_sam2_auto=F.FakeSegmenter("yolo_sam2_auto", instances=0))
    sid = _session(client)["session"]["session_id"]
    empty = _find_all(client, sid)
    assert empty["outcome"] == "empty"
    assert empty["artifacts"][0]["measurement"]["payload"]["searched"]

    # unavailable — the adapter is in the catalogue and is not running here
    w.adapters = F.extent_adapters(
        yolo_sam2_auto=F.FakeSegmenter("yolo_sam2_auto", state=CapabilityState.UNAVAILABLE))
    sid = _session(client)["session"]["session_id"]
    unavailable = _find_all(client, sid)
    assert unavailable["outcome"] == "unavailable"
    assert unavailable["run"]["refusals"][0]["code"] == "capability_unavailable"

    # failed — it ran and raised. No claim is made about the image.
    w.adapters = F.extent_adapters(
        yolo_sam2_auto=F.FakeSegmenter("yolo_sam2_auto", raises=RuntimeError("cuda is gone")))
    sid = _session(client)["session"]["session_id"]
    failed = _find_all(client, sid)
    assert failed["outcome"] == "failed"
    assert failed["artifacts"] == []

    # refused — a law said no
    w.adapters = F.extent_adapters()
    sid = _session(client, organ="topology")["session"]["session_id"]
    plan = _plan(client, sid, planner="direct",
                 commands=[{"operation": "topology.containment"}])
    refused = _run(client, sid, plan["plan_id"])
    assert refused["outcome"] == "refused"
    assert refused["run"]["refusals"][0]["code"] == "missing_extent_inputs"

    # partial — some of it came back and some of it did not
    sid = _session(client)["session"]["session_id"]
    client.patch(f"{PREFIX}/sessions/{sid}",
                 json={"active_region_ids": ["seg_0", "seg_vanished"]})
    plan = _plan(client, sid, planner="direct", commands=[{
        "operation": "extent.reuse",
        "input_refs": [
            {"role": "regions", "scope": "canonical", "region_id": "seg_0", "geometry_rev": 3},
            {"role": "regions", "scope": "canonical", "region_id": "seg_vanished",
             "geometry_rev": 0}]}])
    partial = _run(client, sid, plan["plan_id"])
    assert partial["outcome"] == "partial"
    assert partial["artifacts"]
    assert partial["run"]["refusals"][0]["code"] == "unknown_reference"


def test_a_refused_run_is_a_201_carrying_the_refusal_rather_than_an_http_error(wired):
    client, w = wired
    sid = _session(client, organ="topology")["session"]["session_id"]
    plan = _plan(client, sid, planner="direct", commands=[{"operation": "topology.containment"}])
    res = client.post(f"{PREFIX}/sessions/{sid}/runs", json={"plan_id": plan["plan_id"]})

    assert res.status_code == 201
    assert res.json()["run"]["refusals"][0]["remedy"]


def test_a_plan_that_requires_confirmation_is_a_409_until_it_is_confirmed(wired):
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    extents = _find_all(client, sid)
    aid = extents["artifacts"][0]["identity"]["artifact_id"]
    ids = [i["instance_id"] for i in
           extents["artifacts"][0]["measurement"]["payload"]["instances"]]
    client.patch(f"{PREFIX}/sessions/{sid}", json={
        "selected_organ": "topology", "selected_artifact_ids": [aid],
        "selected_instance_refs": [{"artifact_id": aid, "instance_id": i} for i in ids]})
    plan = _plan(client, sid, planner="direct", commands=[{
        "operation": "topology.occlusion",
        "input_refs": [
            {"role": "source", "scope": "session", "artifact_id": aid, "instance_id": ids[0]},
            {"role": "target", "scope": "session", "artifact_id": aid, "instance_id": ids[1]}]}])

    unconfirmed = client.post(f"{PREFIX}/sessions/{sid}/runs", json={"plan_id": plan["plan_id"]})
    assert unconfirmed.status_code == 409
    assert unconfirmed.json()["detail"]["error"] == "confirmation_required"

    confirmed = _run(client, sid, plan["plan_id"], confirmed=True)
    # And the refusal that follows is about DEPTH, which is a different no from the confirmation.
    assert confirmed["run"]["refusals"][0]["code"] == "missing_depth_artifact"


# ── the source, and the ledger ───────────────────────────────────────────────


def test_the_post_is_byte_identical_after_a_full_run_and_nothing_was_written_to_it(wired):
    client, w = wired
    before = copy.deepcopy(w.posts.docs)
    writes_before = w.posts.writes

    sid = _session(client)["session"]["session_id"]
    _find_all(client, sid)
    aid = None
    body = _find_all(client, sid)
    aid = body["artifacts"][0]["identity"]["artifact_id"]
    client.patch(f"{PREFIX}/sessions/{sid}", json={"selected_artifact_ids": [aid]})
    client.post(f"{PREFIX}/sessions/{sid}/reviews",
                json={"artifact_id": aid, "verdict": "correct", "reviewer": "person"})
    client.patch(f"{PREFIX}/sessions/{sid}/artifacts/{aid}/lifecycle", json={"status": "kept"})

    assert w.posts.docs == before
    assert w.posts.writes == writes_before == 0
    assert w.probe_posts.writes == 0
    # And the lab DID write — to its own five collections, which is the whole point of the split.
    assert w.lab_writes > 0


def test_a_run_reports_the_source_it_re_read_rather_than_the_one_it_started_with(wired):
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    body = _find_all(client, sid)

    assert body["source_unchanged"] is True
    assert body["run"]["source_digest_after"] == body["run"]["source_digest_before"]


def test_a_post_that_moved_during_a_run_fails_it(wired):
    """The probe RE-READS. A conductor that copied the before-digest forward would report this
    run as clean, and the one thing a laboratory cannot afford to assert on no evidence is that
    the thing it was measuring held still."""
    client, w = wired
    sid = _session(client)["session"]["session_id"]

    class _MutatesWhileMeasuring(F.FakeSegmenter):
        def measure(self, step, ctx, params):
            w.mutate_post(visual_marks=[{"id": "mark_1", "note": "something was accepted"}])
            return super().measure(step, ctx, params)

    w.adapters = F.extent_adapters(yolo_sam2_auto=_MutatesWhileMeasuring("yolo_sam2_auto"))
    body = _find_all(client, sid)

    assert body["outcome"] == "failed"
    assert body["source_unchanged"] is False
    assert body["run"]["refusals"][-1]["code"] == "source_mutated"


def test_an_image_swapped_behind_the_post_refuses_before_anything_is_measured(wired):
    """A `photo_url` can serve different bytes tomorrow. A session that measured the new picture
    under the old digest would produce an artifact that validates and is about another image."""
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    w.image = F.png_bytes(width=F.WIDTH, height=F.HEIGHT + 8)

    body = _find_all(client, sid)

    # `failed`, not `refused`, and the ordering is the deliverable: a measurement of an image that
    # moved is a measurement of neither, so nothing else about the run may be reported as its
    # result. BOTH guards fire — the bridge's, before the segmenter was called, and the
    # conductor's probe afterwards — and the adapter was never reached.
    assert body["outcome"] == "failed"
    assert {r["code"] for r in body["run"]["refusals"]} == {"source_mutated"}
    # No SEGMENTER ran. `invoked` on the stage stays true and correctly so — the conductor did
    # call its adapter, and the adapter is the bridge; what the bridge did was refuse before it
    # reached a model. The two facts are at two levels and neither is the other's evidence.
    assert w.adapters["yolo_sam2_auto"].calls == []
    bridge_refusal = next(r for r in body["run"]["refusals"] if r["detail"].get("in_hand"))
    assert bridge_refusal["detail"]["in_hand"] != bridge_refusal["detail"]["session_digest"]


# ── replay ───────────────────────────────────────────────────────────────────


def test_a_replay_re_shows_the_run_and_calls_nothing(wired):
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    live_run = _find_all(client, sid)
    calls_after_live = len(w.adapters["yolo_sam2_auto"].calls)

    res = client.post(f"{PREFIX}/sessions/{sid}/replays",
                      json={"run_id": live_run["run"]["run_id"]})
    assert res.status_code == 201, res.text
    body = res.json()

    assert body["execution_identity"] == "REPLAY"
    assert body["run"]["execution_identity"] == "REPLAY"
    assert all(a["invoked"] is False for a in body["run"]["stage_attempts"])
    assert body["run"]["artifact_ids"] == live_run["run"]["artifact_ids"]
    assert len(w.adapters["yolo_sam2_auto"].calls) == calls_after_live


def test_the_replay_handler_never_builds_a_live_registry(wired):
    """The structural guard, at the route. Read rather than exercised: a handler that reached for
    `live_registry` would pass every behavioural test until the day something called it."""
    import inspect
    source = inspect.getsource(R.replay_run)
    assert "SealedAdapterRegistry" in source
    assert "live_registry" not in source
    assert "_conductor" not in source


def test_replaying_a_run_that_is_gone_refuses_rather_than_rebuilding_it(wired):
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    res = client.post(f"{PREFIX}/sessions/{sid}/replays", json={"run_id": "run_nobody"})

    assert res.status_code == 201
    body = res.json()
    assert body["run"]["outcome"] == "refused"
    assert body["run"]["refusals"][0]["code"] == "replay_cannot_recompute"


# ── re-opening ───────────────────────────────────────────────────────────────


def test_re_opening_a_session_restores_its_references_and_its_whole_history(wired):
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    extents = _find_all(client, sid)
    aid = extents["artifacts"][0]["identity"]["artifact_id"]
    ids = [i["instance_id"] for i in
           extents["artifacts"][0]["measurement"]["payload"]["instances"]]
    client.patch(f"{PREFIX}/sessions/{sid}", json={
        "selected_artifact_ids": [aid], "active_artifact_id": aid,
        "selected_instance_refs": [{"artifact_id": aid, "instance_id": ids[0]}],
        "active_region_ids": ["seg_0"]})

    reopened = client.get(f"{PREFIX}/sessions/{sid}").json()["session"]
    assert reopened["selected_artifact_ids"] == [aid]
    assert reopened["active_artifact_id"] == aid
    assert reopened["selected_instance_refs"] == [{"artifact_id": aid, "instance_id": ids[0]}]
    assert reopened["active_region_ids"] == ["seg_0"]

    history = client.get(f"{PREFIX}/sessions/{sid}/history").json()
    assert len(history["runs"]) == 1
    assert len(history["plans"]) == 1
    assert [a["identity"]["artifact_id"] for a in history["artifacts"]] == [aid]
    for record, model in ((history["session"], LabSession), (history["runs"][0], LabRun),
                          (history["artifacts"][0], PerceptualArtifact)):
        model.model_validate(record)


def test_deselecting_an_artifact_takes_its_instances_with_it(wired):
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    extents = _find_all(client, sid)
    aid = extents["artifacts"][0]["identity"]["artifact_id"]
    ids = [i["instance_id"] for i in
           extents["artifacts"][0]["measurement"]["payload"]["instances"]]
    client.patch(f"{PREFIX}/sessions/{sid}", json={
        "selected_artifact_ids": [aid], "active_artifact_id": aid,
        "selected_instance_refs": [{"artifact_id": aid, "instance_id": ids[0]}]})

    cleared = client.patch(f"{PREFIX}/sessions/{sid}",
                           json={"selected_artifact_ids": [], "clear_active": True}).json()

    assert cleared["session"]["selected_artifact_ids"] == []
    assert cleared["session"]["selected_instance_refs"] == []
    assert cleared["session"]["active_artifact_id"] is None


def test_repeated_requests_against_one_session_do_not_corrupt_it(wired):
    """The same plan run three times: three runs, three artifacts, one coherent session.

    A store that returned windows rather than values would show this as a session whose `run_ids`
    lost an entry, because two handlers would have been appending to the same list object.
    """
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    plan = _plan(client, sid, planner="direct", commands=[{"operation": "extent.find_all"}])
    runs = [_run(client, sid, plan["plan_id"]) for _ in range(3)]

    session = client.get(f"{PREFIX}/sessions/{sid}").json()["session"]
    assert len(session["run_ids"]) == 3
    assert session["run_ids"] == [r["run"]["run_id"] for r in runs]
    assert len({r["artifacts"][0]["identity"]["artifact_id"] for r in runs}) == 3

    history = client.get(f"{PREFIX}/sessions/{sid}/history").json()
    assert len(history["runs"]) == 3
    assert len(history["artifacts"]) == 3


def test_interleaved_sessions_on_one_post_keep_their_own_ledgers(wired):
    client, w = wired
    a = _session(client)["session"]["session_id"]
    b = _session(client)["session"]["session_id"]
    _find_all(client, a)
    _find_all(client, b)
    _find_all(client, a)

    assert len(client.get(f"{PREFIX}/sessions/{a}/history").json()["runs"]) == 2
    assert len(client.get(f"{PREFIX}/sessions/{b}/history").json()["runs"]) == 1


# ── the catalogue ────────────────────────────────────────────────────────────


def test_the_catalogue_reports_the_two_live_organs_and_the_six_that_are_deferred(wired):
    client, w = wired
    body = client.get(f"{PREFIX}/capabilities").json()

    assert body["execution_identity"] == "LIVE"
    enabled = [o for o in body["organs"] if o["enabled"]]
    deferred = [o for o in body["organs"] if not o["enabled"]]
    assert {o["family"] for o in enabled} == {"extent", "topology"}
    assert len(deferred) == 6
    # A deferred organ offers no operation and therefore no adapter a person could click.
    assert all(o["operations"] == [] for o in deferred)
    assert body["states"]["nestedness_organ"] == "available"


def test_an_adapter_nobody_asked_about_is_absent_rather_than_unavailable(wired):
    client, w = wired
    body = client.get(f"{PREFIX}/capabilities").json()
    assert "depth_anything" not in body["states"]


def test_the_source_listing_admits_it_has_not_hashed_anything(wired):
    client, w = wired
    body = client.get(f"{PREFIX}/sources").json()
    assert body["sources"][0]["post_id"] == F.POST_ID
    assert body["sources"][0]["image_digest"] is None

    detail = client.get(f"{PREFIX}/sources/{F.POST_ID}").json()
    assert detail["source"]["image_digest"].startswith("sha256:")


# ── a person's verdict, the lab's curation, and the promotion that is not here ──


def test_a_review_changes_no_lifecycle_and_no_epistemic_status(wired):
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    artifact = _find_all(client, sid)["artifacts"][0]
    aid = artifact["identity"]["artifact_id"]

    res = client.post(f"{PREFIX}/sessions/{sid}/reviews",
                      json={"artifact_id": aid, "verdict": "correct", "notes": "yes"})
    assert res.status_code == 201, res.text

    after = client.get(f"{PREFIX}/sessions/{sid}/history").json()["artifacts"][0]
    assert after["lifecycle"]["status"] == artifact["lifecycle"]["status"] == "proposed"
    assert after["measurement"]["epistemic_status"] == artifact["measurement"]["epistemic_status"]
    assert len(res.json()["session"]["review_ids"]) == 1


def test_keeping_an_artifact_is_a_lab_state_and_promoting_one_is_not_offered(wired):
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    aid = _find_all(client, sid)["artifacts"][0]["identity"]["artifact_id"]

    kept = client.patch(f"{PREFIX}/sessions/{sid}/artifacts/{aid}/lifecycle",
                        json={"status": "kept"})
    assert kept.status_code == 200
    assert kept.json()["artifact"]["lifecycle"]["status"] == "kept"
    assert kept.json()["artifact"]["identity"]["identity_scope"] == "session"
    assert w.posts.writes == 0

    promoted = client.patch(f"{PREFIX}/sessions/{sid}/artifacts/{aid}/lifecycle",
                            json={"status": "promoted"})
    assert promoted.status_code == 422
    assert promoted.json()["detail"]["error"] == "promotion_is_not_a_lifecycle_edit"


def test_this_router_offers_no_promotion_surface_at_all(wired):
    """Lane E asserts this of a client; the same assertion belongs on the wire it is a client of."""
    paths = {r.path for r in R.router.routes}
    forbidden = ("promote", "commit", "accept", "publish", "ground", "percept", "mark", "region")
    assert not [p for p in paths if any(word in p for word in forbidden)]


# ── export ───────────────────────────────────────────────────────────────────


def test_the_export_is_the_five_record_types_and_says_it_is_not_a_promotion(wired):
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    aid = _find_all(client, sid)["artifacts"][0]["identity"]["artifact_id"]
    client.post(f"{PREFIX}/sessions/{sid}/reviews",
                json={"artifact_id": aid, "verdict": "correct"})

    body = client.get(f"{PREFIX}/sessions/{sid}/export").json()

    assert body["export_kind"] == "perception-lab.session-export"
    assert body["execution_identity"] == "LIVE"
    assert set(body["counts"]) == {"plans", "runs", "artifacts", "reviews"}
    assert body["counts"] == {"plans": 1, "runs": 1, "artifacts": 1, "reviews": 1}
    assert any("Not a promotion" in line for line in body["not_this"])
    LabSession.model_validate(body["session"])
    PerceptualArtifact.model_validate(body["artifacts"][0])


# ── cancellation ─────────────────────────────────────────────────────────────


def test_cancelling_a_ticket_nobody_is_holding_says_so_rather_than_reporting_success(wired):
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    body = client.post(f"{PREFIX}/sessions/{sid}/runs/cancel",
                       json={"run_ticket": "tkt_nothing"}).json()

    assert body["cancelled"] is False
    assert "cannot be reached from here" in body["note"]


def test_a_ticket_is_open_while_its_run_is_and_closed_afterwards(wired):
    client, w = wired
    from backend.services.perception_lab.live import CANCELS
    sid = _session(client)["session"]["session_id"]
    plan = _plan(client, sid, planner="direct", commands=[{"operation": "extent.find_all"}])

    seen = {}

    class _Watcher(F.FakeSegmenter):
        def measure(self, step, ctx, params):
            seen["open"] = CANCELS.open_tickets
            return super().measure(step, ctx, params)

    w.adapters = F.extent_adapters(yolo_sam2_auto=_Watcher("yolo_sam2_auto"))
    _run(client, sid, plan["plan_id"], run_ticket="tkt_1")

    assert "tkt_1" in seen["open"]
    assert "tkt_1" not in CANCELS.open_tickets


def test_a_cancelled_ticket_stops_the_next_stage_and_the_run_says_which(wired):
    client, w = wired
    from backend.services.perception_lab.live import CANCELS
    sid = _session(client)["session"]["session_id"]
    plan = _plan(client, sid, planner="direct", commands=[
        {"operation": "extent.find_all"}, {"operation": "extent.find_all"}])

    class _CancelsItself(F.FakeSegmenter):
        def measure(self, step, ctx, params):
            CANCELS.cancel("tkt_2", "the person changed their mind")
            return super().measure(step, ctx, params)

    w.adapters = F.extent_adapters(yolo_sam2_auto=_CancelsItself("yolo_sam2_auto"))
    body = _run(client, sid, plan["plan_id"], run_ticket="tkt_2")

    states = [a["state"] for a in body["run"]["stage_attempts"]]
    assert states[0] == "completed" and states[-1] == "skipped"
    assert "changed their mind" in body["run"]["stage_attempts"][-1]["detail"]
    assert body["outcome"] == "partial"


# ── the store's own failure ──────────────────────────────────────────────────


def test_a_lab_store_that_cannot_be_reached_is_a_503_and_not_a_silent_success(wired, monkeypatch):
    client, w = wired

    class _Broken(F.FakeCollection):
        def replace_one(self, query, doc, upsert=False):
            raise RuntimeError("the cluster is not answering")

    broken = dict(w.collections)
    broken["sessions"] = _Broken()
    monkeypatch.setattr(R, "_store", lambda: MongoLabStore(broken))

    res = client.post(f"{PREFIX}/sessions", json={"post_id": F.POST_ID})
    assert res.status_code == 503
    assert res.json()["detail"]["error"] == "lab_store_unavailable"
