"""
CIRCULATION-SPINE-001 · P1 — recorded Dissect.

Covers the P1 stop-gate: a real Dissect run produces a retrievable record; every event
is a truthfully executed/skipped stage; run lifecycle + idempotency; telemetry can never
break or alter Dissect (write-behind); and the instrumented route is output-equivalent
to the un-instrumented one (regions / mask_rle / source / counts / creator + curator
preservation / fallback / primary exceptions).

House style: sync tests driving async code via ``asyncio.run`` with injected fake
collections (cf. test_vision_f1.py). No live Mongo, no network, no models.
"""
import asyncio
import copy
from datetime import datetime, timezone, timedelta

import pytest
from bson.objectid import ObjectId

from backend.services.vision_orchestrator.contracts import JobStatus
from backend.services.vision_orchestrator import vision_run_contracts as vrc
from backend.services import vision_run_service as svc
from backend.routers import posts as R


# ── fake async Mongo collection (supports exactly the ops the service uses) ───
class _UpdateResult:
    def __init__(self, matched, modified):
        self.matched_count = matched
        self.modified_count = modified


class FakeCollection:
    def __init__(self):
        self.docs = {}
        self.fail_insert = False
        self.fail_update = False

    async def insert_one(self, doc):
        if self.fail_insert:
            raise RuntimeError("insert boom")
        self.docs[doc["_id"]] = copy.deepcopy(doc)
        return type("R", (), {"inserted_id": doc["_id"]})()

    def _match(self, doc, query):
        for k, v in query.items():
            if k == "events.event_id" and isinstance(v, dict) and "$ne" in v:
                if any(e.get("event_id") == v["$ne"] for e in doc.get("events", [])):
                    return False
            elif isinstance(v, dict) and "$in" in v:
                if doc.get(k) not in v["$in"]:
                    return False
            elif isinstance(v, dict) and "$ne" in v:
                if doc.get(k) == v["$ne"]:
                    return False
            else:
                if doc.get(k) != v:
                    return False
        return True

    async def find_one(self, query):
        doc = self.docs.get(query.get("_id"))
        if doc is None or not self._match(doc, query):
            return None
        return copy.deepcopy(doc)

    async def update_one(self, query, update):
        if self.fail_update:
            raise RuntimeError("update boom")
        doc = self.docs.get(query.get("_id"))
        if doc is None or not self._match(doc, query):
            return _UpdateResult(0, 0)
        for k, v in update.get("$push", {}).items():
            doc.setdefault(k, []).append(v)
        for k, v in update.get("$set", {}).items():
            doc[k] = v
        return _UpdateResult(1, 1)

    def find(self, query):
        return _FakeCursor([copy.deepcopy(d) for d in self.docs.values()
                            if self._match(d, query)])

    async def create_index(self, *a, **k):
        return "idx"


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, field, direction):
        self._docs.sort(key=lambda d: d.get(field) or 0, reverse=direction < 0)
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __aiter__(self):
        self._it = iter(self._docs)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


def run(coro):
    return asyncio.run(coro)


# ══════════════════════════ contract validation ══════════════════════════════

def test_new_run_doc_is_valid_and_versioned():
    doc = vrc.new_run_doc(post_id="p1")
    assert doc["contract_version"] == vrc.CONTRACT_VERSION
    assert doc["operation"] == vrc.OPERATION_DISSECT
    assert doc["status"] == JobStatus.RUNNING.value
    assert doc["events"] == [] and doc["telemetry_degraded"] is False
    for f in ("post_id", "created_at", "started_at", "updated_at",
              "completed_at", "terminal_reason", "error", "result_summary"):
        assert f in doc


def test_make_event_is_valid_and_versioned():
    ev = vrc.make_event(stage_id=vrc.STAGE_RECEIVE, status=JobStatus.SUCCEEDED,
                        detail={"coarse_only": True})
    assert ev["contract_version"] == vrc.CONTRACT_VERSION
    assert ev["stage_id"] == "dissect.receive"
    assert ev["status"] == "succeeded"
    assert isinstance(ev["event_id"], str) and ev["observed_at"] is not None


def test_operation_is_not_the_groq_fallback_detector():
    # The run operation must not be conflated with vision_service.detect_regions.
    assert vrc.OPERATION_DISSECT == "dissect"
    assert vrc.STAGE_FALLBACK_DETECT == "dissect.fallback.detect"


def test_every_jobstatus_value_is_supported():
    for s in JobStatus:
        assert vrc.as_status(s.value) is s


def test_unknown_optional_telemetry_stays_null_never_guessed():
    ev = vrc.make_event(stage_id="dissect.segment.general", status="succeeded")
    assert ev["latency_ms"] is None          # not measured → absent
    assert ev["provenance"] is None          # device/dtype/vram never fabricated
    assert ev["adapter"] is None and ev["capability"] is None
    assert ev["error"] is None


def test_geometry_payloads_cannot_enter_events():
    for bad in ({"mask_rle": [1]}, {"box": {"x": 0}}, {"polygon": [[0, 0]]},
                {"nested": {"regions": []}}):
        with pytest.raises(vrc.GeometryInEventError):
            vrc.make_event(stage_id="x", status="succeeded", detail=bad)


def test_geometry_guard_covers_provenance_and_requested_profile():
    # defense-in-depth: geometry may not hide in provenance or the run's requested_profile
    with pytest.raises(vrc.GeometryInEventError):
        vrc.make_event(stage_id="x", status="succeeded", provenance={"box": {"x": 0}})
    with pytest.raises(vrc.GeometryInEventError):
        vrc.new_run_doc(post_id="p", requested_profile={"mask_rle": [1]})


def test_dependencies_are_representable_independently_of_order():
    ev = vrc.make_event(stage_id="dissect.merge_anchors", status="succeeded",
                        dependencies=["dissect.segment.general", "dissect.segment.fashion"])
    assert ev["dependencies"] == ["dissect.segment.general", "dissect.segment.fashion"]


# ══════════════════════════ run lifecycle ════════════════════════════════════

def _mk_run(coll, **kw):
    return run(svc.create_run(post_id=kw.get("post_id", "p1"), collection=coll))


def test_create_then_running_then_succeeded():
    c = FakeCollection()
    rid = _mk_run(c)
    proj = run(svc.get_run(rid, collection=c))
    assert proj["status"] == "running" and proj["completed_at"] is None
    run(svc.finalize(rid, JobStatus.SUCCEEDED, actual_source="yolo+sukshma",
                     result_summary={"region_count": 3}, collection=c))
    proj = run(svc.get_run(rid, collection=c))
    assert proj["status"] == "succeeded"
    assert proj["completed_at"] is not None           # terminal carries completion time
    assert proj["actual_source"] == "yolo+sukshma"


def test_create_then_partial():
    c = FakeCollection()
    rid = _mk_run(c)
    run(svc.finalize(rid, JobStatus.PARTIAL, terminal_reason="fine_decomposition_degraded",
                     collection=c))
    proj = run(svc.get_run(rid, collection=c))
    assert proj["status"] == "partial" and proj["completed_at"] is not None
    assert proj["terminal_reason"] == "fine_decomposition_degraded"


def test_create_then_failed():
    c = FakeCollection()
    rid = _mk_run(c)
    run(svc.finalize(rid, JobStatus.FAILED, terminal_reason="route_exception",
                     error="boom", collection=c))
    proj = run(svc.get_run(rid, collection=c))
    assert proj["status"] == "failed" and proj["error"] == "boom"
    assert proj["completed_at"] is not None


def test_duplicate_finalization_is_idempotent():
    c = FakeCollection()
    rid = _mk_run(c)
    run(svc.finalize(rid, JobStatus.SUCCEEDED, collection=c))
    first = run(svc.get_run(rid, collection=c))["completed_at"]
    # second identical finalize must not raise and must not change the terminal state
    run(svc.finalize(rid, JobStatus.SUCCEEDED, collection=c))
    again = run(svc.get_run(rid, collection=c))
    assert again["status"] == "succeeded" and again["completed_at"] == first


def test_illegal_terminal_to_running_is_rejected():
    c = FakeCollection()
    rid = _mk_run(c)
    run(svc.finalize(rid, JobStatus.SUCCEEDED, collection=c))
    with pytest.raises(vrc.IllegalRunTransition):
        run(svc.transition(rid, JobStatus.RUNNING, collection=c))


def test_conflicting_terminal_finalize_is_rejected():
    c = FakeCollection()
    rid = _mk_run(c)
    run(svc.finalize(rid, JobStatus.SUCCEEDED, collection=c))
    with pytest.raises(vrc.IllegalRunTransition):
        run(svc.finalize(rid, JobStatus.FAILED, collection=c))


def test_event_ids_cannot_be_appended_twice():
    c = FakeCollection()
    rid = _mk_run(c)
    ev = vrc.make_event(stage_id="dissect.receive", status="succeeded", event_id="fixed")
    assert run(svc.append_event(rid, ev, collection=c)) is True
    assert run(svc.append_event(rid, ev, collection=c)) is False   # deterministic no-op
    proj = run(svc.get_run(rid, collection=c))
    assert sum(1 for e in proj["events"] if e["event_id"] == "fixed") == 1


def test_observation_order_is_stable_and_dependencies_survive_projection():
    c = FakeCollection()
    rid = _mk_run(c)
    run(svc.append_event(rid, vrc.make_event(stage_id="dissect.segment.general",
                         status="succeeded", event_id="e1"), collection=c))
    run(svc.append_event(rid, vrc.make_event(stage_id="dissect.merge_anchors",
                         status="succeeded", event_id="e2",
                         dependencies=["dissect.segment.general"]), collection=c))
    evs = run(svc.get_run(rid, collection=c))["events"]
    assert [e["event_id"] for e in evs] == ["e1", "e2"]            # insertion order
    assert evs[1]["dependencies"] == ["dissect.segment.general"]  # causal, not positional


def test_get_run_is_post_scoped():
    c = FakeCollection()
    rid = run(svc.create_run(post_id="owner", collection=c))
    assert run(svc.get_run(rid, post_id="owner", collection=c)) is not None
    assert run(svc.get_run(rid, post_id="intruder", collection=c)) is None  # ownership


def test_latest_run_is_most_recent_for_post():
    c = FakeCollection()
    r1 = run(svc.create_run(post_id="p", collection=c))
    # force r2 to sort after r1 by bumping its created_at
    r2 = run(svc.create_run(post_id="p", collection=c))
    c.docs[ObjectId(r2)]["created_at"] = datetime.now(timezone.utc) + timedelta(seconds=5)
    latest = run(svc.get_latest_run("p", collection=c))
    assert latest["run_id"] == r2


# ══════════════════════════ telemetry degradation ════════════════════════════

def test_run_store_creation_failure_does_not_raise():
    c = FakeCollection(); c.fail_insert = True
    rec = svc.DissectRunRecorder(post_id="p", collection=c)
    run(rec.start())
    assert rec.run_id is None and rec.telemetry_degraded is True
    run(rec.event(vrc.STAGE_RECEIVE, JobStatus.SUCCEEDED))     # safe no-op
    run(rec.finish(JobStatus.SUCCEEDED))                        # safe no-op


def test_event_append_failure_does_not_raise():
    c = FakeCollection()
    rec = svc.DissectRunRecorder(post_id="p", collection=c)
    run(rec.start())
    assert rec.run_id is not None
    c.fail_update = True
    run(rec.event(vrc.STAGE_SEGMENT_GENERAL, JobStatus.SUCCEEDED))
    assert rec.telemetry_degraded is True


def test_finalization_failure_does_not_raise():
    c = FakeCollection()
    rec = svc.DissectRunRecorder(post_id="p", collection=c)
    run(rec.start())
    c.fail_update = True
    run(rec.finish(JobStatus.SUCCEEDED))                        # must not raise
    assert rec.telemetry_degraded is True


def test_stale_running_run_is_projected_honestly():
    c = FakeCollection()
    rid = _mk_run(c)
    # backdate updated_at well past the stale threshold
    old = datetime.now(timezone.utc) - timedelta(seconds=vrc.STALE_AFTER_SECONDS + 60)
    c.docs[ObjectId(rid)]["updated_at"] = old
    proj = run(svc.get_run(rid, now=datetime.now(timezone.utc), collection=c))
    assert proj["status"] == "running"           # not lied into 'completed'
    assert proj["stale"] is True and proj["staleness_seconds"] >= vrc.STALE_AFTER_SECONDS


def test_fresh_running_run_is_not_stale():
    c = FakeCollection()
    rid = _mk_run(c)
    proj = run(svc.get_run(rid, now=datetime.now(timezone.utc), collection=c))
    assert proj["stale"] is False and proj["staleness_seconds"] is None


# ══════════════════════════ route equivalence ════════════════════════════════
#
# Runs the real detect_regions route through mocked seams, once with a WORKING run
# store and once with a FAILING one, and asserts the visible result is identical apart
# from the additive run_id — i.e. instrumentation changes nothing observable.

def _fresh_post():
    return {
        "_id": ObjectId(),
        "photo_url": "http://img.example/x.jpg",
        "region_annotations": [
            {"id": "creator1", "actor": "creator", "detector": "sam2",
             "box": {"x": 0.7, "y": 0.7, "w": 0.2, "h": 0.2},
             "mask_rle": {"size": [10, 10], "counts": "creatorRLE"},
             "user_note": "keep me", "prioritised": True, "weight": 5,
             "geometry_provenance": {"via": "refine"}},
        ],
    }


class _FakePosts:
    def __init__(self, post):
        self.post = post
        self.saved = None

    async def find_one(self, q):
        return copy.deepcopy(self.post)

    async def update_one(self, q, update):
        self.saved = update["$set"]["region_annotations"]
        return _UpdateResult(1, 1)


class _FakeResp:
    content = b"imgbytes"

    def raise_for_status(self):
        return None


class _FakeClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, headers=None):
        return _FakeResp()


class _FakeHttpx:
    def AsyncClient(self, *a, **k):
        return _FakeClient()


def _yolo_anchors(_bytes):
    return [
        {"id": "y1", "box": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
         "mask_rle": {"size": [10, 10], "counts": "y1RLE"}, "category": "figure"},
        {"id": "y2", "box": {"x": 0.4, "y": 0.4, "w": 0.2, "h": 0.2},
         "mask_rle": {"size": [10, 10], "counts": "y2RLE"}, "category": "figure"},
    ]


async def _fine_parts(photo_url, anchors=None, lens="", mode="general"):
    return [{"id": "f1", "box": {"x": 0.11, "y": 0.11, "w": 0.05, "h": 0.05},
             "parent_label": "y1", "category": "detail"}]


def _install_route_mocks(monkeypatch, posts_coll, runs_coll):
    monkeypatch.setattr(R, "post_collection", posts_coll)
    monkeypatch.setattr(R, "httpx", _FakeHttpx())
    monkeypatch.setattr(R, "_image_fetch_headers", lambda url: {})

    async def _not_fashion(post, obj_id, img_bytes):
        return False
    monkeypatch.setattr(R, "_resolve_is_fashion", _not_fashion)
    monkeypatch.setattr(R.segmentation_service, "segment_image_bytes", _yolo_anchors)
    monkeypatch.setattr(R.vision_service, "decompose_regions", _fine_parts)
    monkeypatch.setattr(svc, "vision_run_collection", runs_coll)


def _run_route(monkeypatch, runs_coll):
    posts_coll = _FakePosts(_fresh_post())
    _install_route_mocks(monkeypatch, posts_coll, runs_coll)
    from backend.schemas.post import RegionDetectRequest
    pid = str(posts_coll.post["_id"])
    resp = run(R.detect_regions(pid, RegionDetectRequest(coarse_only=False)))
    return resp, posts_coll


def test_route_output_equivalent_with_working_and_failing_telemetry(monkeypatch):
    ok_runs = FakeCollection()
    resp_ok, posts_ok = _run_route(monkeypatch, ok_runs)

    bad_runs = FakeCollection(); bad_runs.fail_insert = True
    resp_bad, posts_bad = _run_route(monkeypatch, bad_runs)

    # identical apart from the additive run_id (present when telemetry works, None when not)
    strip = lambda d: {k: v for k, v in d.items() if k != "run_id"}
    assert strip(resp_ok) == strip(resp_bad)
    assert isinstance(resp_ok["run_id"], str)
    assert resp_bad["run_id"] is None

    # geometry + curator + creator preservation, identical in both runs
    for resp, posts in ((resp_ok, posts_ok), (resp_bad, posts_bad)):
        assert resp["creator_preserved"] == 1
        creator = next(r for r in resp["regions"] if r["id"] == "creator1")
        assert creator["actor"] == "creator"
        assert creator["mask_rle"] == {"size": [10, 10], "counts": "creatorRLE"}
        assert creator["user_note"] == "keep me" and creator["weight"] == 5
        assert resp["source"] == "yolo+sukshma"
        assert resp["anchor_count"] == 2 and resp["fine_count"] == 1
        assert posts.saved == resp["regions"]          # persisted == returned


def test_route_creates_retrievable_run_with_truthful_events(monkeypatch):
    runs = FakeCollection()
    resp, _ = _run_route(monkeypatch, runs)

    # a real run record exists and is retrievable, scoped to the post
    proj = run(svc.get_run(resp["run_id"], collection=runs))
    assert proj is not None and proj["status"] == "succeeded"
    assert proj["operation"] == "dissect" and proj["actual_source"] == "yolo+sukshma"

    stages = [e["stage_id"] for e in proj["events"]]
    # every recorded stage actually executed on this path (no fashion/arch — not chosen)
    assert stages == [
        "dissect.receive", "dissect.fetch_image", "dissect.route_domain",
        "dissect.segment.general", "dissect.merge_anchors", "dissect.decompose_fine",
        "dissect.merge_curator_state", "dissect.canonicalize_geometry",
        "dissect.persist_regions", "dissect.complete",
    ]
    assert "dissect.segment.fashion" not in stages     # not chosen → not emitted
    assert "dissect.fallback.detect" not in stages     # segmentation succeeded

    # no event smuggled geometry
    for e in proj["events"]:
        for payload in (e.get("detail"), e.get("input_refs"), e.get("output_refs")):
            if isinstance(payload, dict):
                assert not (set(payload) & vrc._FORBIDDEN_EVENT_KEYS)


def test_route_records_partial_when_fine_decomposition_fails(monkeypatch):
    runs = FakeCollection()
    posts_coll = _FakePosts(_fresh_post())
    _install_route_mocks(monkeypatch, posts_coll, runs)

    async def _boom(*a, **k):
        raise RuntimeError("groq down")
    monkeypatch.setattr(R.vision_service, "decompose_regions", _boom)

    from backend.schemas.post import RegionDetectRequest
    pid = str(posts_coll.post["_id"])
    resp = run(R.detect_regions(pid, RegionDetectRequest(coarse_only=False)))

    # route still succeeds with anchors only; run is PARTIAL (honest degradation)
    assert resp["fine_count"] == 0 and resp["anchor_count"] == 2
    proj = run(svc.get_run(resp["run_id"], collection=runs))
    assert proj["status"] == "partial"
    fine_ev = next(e for e in proj["events"] if e["stage_id"] == "dissect.decompose_fine")
    assert fine_ev["status"] == "failed" and "groq down" in (fine_ev["error"] or "")


def test_route_falls_back_and_records_it_when_segmentation_raises(monkeypatch):
    runs = FakeCollection()
    posts_coll = _FakePosts(_fresh_post())
    _install_route_mocks(monkeypatch, posts_coll, runs)

    def _seg_boom(_bytes):
        raise RuntimeError("no cuda")
    monkeypatch.setattr(R.segmentation_service, "segment_image_bytes", _seg_boom)

    async def _vision_fallback(photo_url):
        return [{"id": "v1", "box": {"x": 0.2, "y": 0.2, "w": 0.3, "h": 0.3},
                 "category": "figure"}]
    monkeypatch.setattr(R.vision_service, "detect_regions", _vision_fallback)

    from backend.schemas.post import RegionDetectRequest
    pid = str(posts_coll.post["_id"])
    resp = run(R.detect_regions(pid, RegionDetectRequest(coarse_only=True)))

    assert resp["source"] == "vision"                  # fallback source unchanged
    proj = run(svc.get_run(resp["run_id"], collection=runs))
    stages = {e["stage_id"]: e for e in proj["events"]}
    assert stages["dissect.segment.coarse"]["status"] == "failed"
    assert stages["dissect.fallback.detect"]["status"] == "succeeded"
    assert stages["dissect.fallback.detect"]["fallbacks"] == ["vision"]


def test_route_reraises_primary_exception_and_marks_run_failed(monkeypatch):
    runs = FakeCollection()
    posts_coll = _FakePosts(_fresh_post())
    _install_route_mocks(monkeypatch, posts_coll, runs)

    # a primary failure AFTER the run is minted: persistence blows up
    async def _persist_boom(q, update):
        raise RuntimeError("db exploded")
    monkeypatch.setattr(posts_coll, "update_one", _persist_boom)

    from backend.schemas.post import RegionDetectRequest
    pid = str(posts_coll.post["_id"])
    with pytest.raises(RuntimeError, match="db exploded"):     # primary stays primary
        run(R.detect_regions(pid, RegionDetectRequest(coarse_only=True)))

    # the run was finalized FAILED (best-effort), not left dangling or hidden
    docs = list(runs.docs.values())
    assert len(docs) == 1 and docs[0]["status"] == "failed"
    assert docs[0]["terminal_reason"] == "route_exception"


# ══════════════════ P1.1 — external-review hardening ══════════════════════════

# --- correction 1: response model retains the full event contract ------------

def test_response_model_retains_run_id_and_contract_version():
    c = FakeCollection(); rid = _mk_run(c)
    run(svc.append_event(rid, vrc.make_event(stage_id="dissect.receive",
        status="succeeded", event_id="e1"), collection=c))
    proj = run(svc.get_run(rid, collection=c))
    dumped = vrc.VisionRunOut(**proj).model_dump()      # the actual response_model
    ev = dumped["events"][0]
    assert ev["run_id"] == rid                           # was stripped pre-P1.1
    assert ev["contract_version"] == vrc.CONTRACT_VERSION
    assert dumped["contract_version"] == vrc.CONTRACT_VERSION and dumped["run_id"] == rid


# --- correction 2: cross-run event ownership ---------------------------------

def test_append_event_sets_absent_run_id():
    c = FakeCollection(); rid = _mk_run(c)
    ev = vrc.make_event(stage_id="dissect.receive", status="succeeded", event_id="e1")
    ev["run_id"] = None
    assert run(svc.append_event(rid, ev, collection=c)) is True
    assert run(svc.get_run(rid, collection=c))["events"][0]["run_id"] == rid


def test_append_event_accepts_matching_run_id():
    c = FakeCollection(); rid = _mk_run(c)
    ev = vrc.make_event(stage_id="dissect.receive", status="succeeded", run_id=rid, event_id="e1")
    assert run(svc.append_event(rid, ev, collection=c)) is True


def test_append_event_rejects_conflicting_run_id():
    c = FakeCollection(); rid = _mk_run(c)
    ev = vrc.make_event(stage_id="dissect.receive", status="succeeded",
                        run_id="deadbeef", event_id="e1")
    with pytest.raises(vrc.EventRunMismatch):
        run(svc.append_event(rid, ev, collection=c))
    assert run(svc.get_run(rid, collection=c))["events"] == []      # nothing persisted


# --- correction 3: index matches the real query ------------------------------

def test_ensure_indexes_declares_only_the_supported_compound():
    calls = []
    class IdxColl:
        async def create_index(self, keys, name=None):
            calls.append((keys, name)); return name
    run(svc.ensure_indexes(collection=IdxColl()))
    assert len(calls) == 1                               # only real-query-backed index
    keys, name = calls[0]
    assert keys == [("post_id", 1), ("operation", 1), ("created_at", -1)]
    assert name == "post_operation_created_idx"


# --- correction 4: zero-match persistence is not a false success -------------

def test_zero_match_persistence_records_failed_not_success(monkeypatch):
    runs = FakeCollection()
    posts_coll = _FakePosts(_fresh_post())
    _install_route_mocks(monkeypatch, posts_coll, runs)

    async def _no_match(q, update):
        return _UpdateResult(0, 0)                       # the write touched nothing
    monkeypatch.setattr(posts_coll, "update_one", _no_match)

    from backend.schemas.post import RegionDetectRequest
    pid = str(posts_coll.post["_id"])
    resp = run(R.detect_regions(pid, RegionDetectRequest(coarse_only=True)))

    # response + control flow unchanged: still returns the computed regions
    assert resp["anchor_count"] == 2 and "regions" in resp
    proj = run(svc.get_run(resp["run_id"], collection=runs))
    persist_ev = next(e for e in proj["events"] if e["stage_id"] == "dissect.persist_regions")
    assert persist_ev["status"] == "failed"              # not a false SUCCEEDED
    assert proj["status"] == "partial" and proj["terminal_reason"] == "persist_no_match"


# --- correction 5: bounded telemetry payloads --------------------------------

def test_bounded_payload_rejects_binary_and_unsupported():
    with pytest.raises(vrc.BoundedPayloadError):
        vrc.make_event(stage_id="x", status="succeeded", detail={"blob": b"\x00\x01"})
    with pytest.raises(vrc.BoundedPayloadError):
        vrc.make_event(stage_id="x", status="succeeded", detail={"obj": object()})


def test_bounded_payload_rejects_excess_nesting_cardinality_and_length():
    deep = cur = {}
    for _ in range(vrc.MAX_PAYLOAD_DEPTH + 2):
        cur["n"] = {}; cur = cur["n"]
    with pytest.raises(vrc.BoundedPayloadError):
        vrc.make_event(stage_id="x", status="succeeded", detail={"d": deep})
    with pytest.raises(vrc.BoundedPayloadError):
        vrc.make_event(stage_id="x", status="succeeded",
                       detail={"many": list(range(vrc.MAX_PAYLOAD_ITEMS + 1))})
    with pytest.raises(vrc.BoundedPayloadError):
        vrc.make_event(stage_id="x", status="succeeded",
                       detail={"s": "z" * (vrc.MAX_STRING_LEN + 1)})


def test_bounded_payload_applies_to_run_fields():
    with pytest.raises(vrc.BoundedPayloadError):
        vrc.new_run_doc(post_id="p", requested_profile={"blob": b"x"})
    c = FakeCollection(); rid = _mk_run(c)
    with pytest.raises(vrc.BoundedPayloadError):
        run(svc.transition(rid, JobStatus.SUCCEEDED, result_summary={"blob": b"x"}, collection=c))


def test_normal_route_payloads_stay_valid():
    vrc.make_event(stage_id="dissect.merge_anchors", status="succeeded",
                   detail={"anchor_count": 5, "source": "segformer_clothes+yolo"},
                   provenance={"adapter": "yolo11_seg", "latency_ms": 88.2},
                   fallbacks=["vision"], dependencies=["dissect.segment.general"])
    vrc.new_run_doc(post_id="p", requested_profile={"mode": "general",
                    "lens": "the fabric folds", "coarse_only": False, "chosen": ["fashion"]})


# --- correction 6: error transport bounding ----------------------------------

def test_error_text_is_truncated_not_dropped():
    long = "E" * (vrc.MAX_ERROR_LEN + 500)
    ev = vrc.make_event(stage_id="dissect.decompose_fine", status="failed", error=long)
    assert ev["error"].endswith("…[truncated]")
    assert len(ev["error"]) <= vrc.MAX_ERROR_LEN + len("…[truncated]")
    c = FakeCollection(); rid = _mk_run(c)
    run(svc.finalize(rid, JobStatus.FAILED, error=long, collection=c))
    assert run(svc.get_run(rid, collection=c))["error"].endswith("…[truncated]")


# --- write-behind preserved for the new guards -------------------------------

def test_recorder_swallows_bounded_and_mismatch_errors():
    c = FakeCollection()
    rec = svc.DissectRunRecorder(post_id="p", collection=c)
    run(rec.start())
    run(rec.event("dissect.receive", JobStatus.SUCCEEDED, detail={"blob": b"\x00"}))  # bounded → swallowed
    assert rec.telemetry_degraded is True
    run(rec.finish(JobStatus.SUCCEEDED))                 # still finalizes cleanly
    proj = run(svc.get_run(rec.run_id, collection=c))
    assert all("blob" not in (e.get("detail") or {}) for e in proj["events"])
