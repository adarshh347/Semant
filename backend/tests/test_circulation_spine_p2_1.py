"""
CIRCULATION-SPINE-001 · P2.1 — heterogeneous sibling-route instrumentation.

Proves, per family (geometry / semantic / retrieval), that recording a VisionRun is additive:
run created with the right operation + correlation refs; response gains only run_id; telemetry
failure isolates (run_id None, route unaffected, no run doc); and authoritative geometry /
curator state / semantics are untouched. Route-level tests with mocked services (no models).
"""
import asyncio
import copy
import pytest
from bson.objectid import ObjectId

from backend.services.vision_orchestrator.contracts import JobStatus
from backend.services.vision_orchestrator import vision_run_contracts as vrc
from backend.services import vision_run_service as svc
from backend.routers import posts as R
from backend.services import semantic_pass
from backend.services import find_similar_service, retrieval_service, region_embedding_service
from backend.tests.test_circulation_spine_p1 import FakeCollection, _UpdateResult, run


class _Posts:
    """Fake post_collection: one post; records every $set write."""
    def __init__(self, post):
        self.post = post
        self.writes = []

    async def find_one(self, q, *a, **k):
        return copy.deepcopy(self.post)

    async def update_one(self, q, update):
        s = update.get("$set", {})
        self.writes.append(s)
        self.post.update(s)
        return _UpdateResult(1, 1)


async def _img(*a, **k):
    return b"imgbytes"


# ════════════════════════ refine (geometry family) ═══════════════════════════

def _install_refine(monkeypatch, posts, runs):
    region = {"id": "r1", "mask_rle": {"size": [8, 8], "counts": "NEWMASK"}, "geometry_rev": 3,
              "proposed": True, "actor": "creator"}

    async def _propose(post_id, req):
        return posts.post["_id"], copy.deepcopy(posts.post), copy.deepcopy(region)
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(R, "_propose_refined_region", _propose)
    monkeypatch.setattr(svc, "vision_run_collection", runs)


def _refine_post():
    return {"_id": ObjectId(), "region_annotations": [
        {"id": "r1", "actor": "creator", "prioritised": True, "weight": 4, "user_note": "keep",
         "mask_rle": {"size": [8, 8], "counts": "OLDMASK"}, "geometry_rev": 2, "depth": 1}]}


def test_refine_records_run_and_preserves_geometry_and_curator(monkeypatch):
    posts, runs = _Posts(_refine_post()), FakeCollection()
    _install_refine(monkeypatch, posts, runs)
    resp = run(R.refine_region_confirm(str(posts.post["_id"]), R.RefineRequest(base_id="r1", base_geometry_rev=2)))

    # response is additive: run_id present; region is the authoritative refined mask
    assert isinstance(resp["run_id"], str)
    reg = resp["region"]
    assert reg["mask_rle"] == {"size": [8, 8], "counts": "NEWMASK"} and reg["geometry_rev"] == 3
    assert reg["proposed"] is False
    # curator fields carried from prev region
    assert reg["prioritised"] is True and reg["weight"] == 4 and reg["user_note"] == "keep"
    # persisted region_annotations == the refined region (authoritative geometry round-trips)
    assert posts.post["region_annotations"][0]["mask_rle"] == {"size": [8, 8], "counts": "NEWMASK"}

    # a run was recorded with the refine operation + geometry correlation refs
    proj = run(svc.get_run(resp["run_id"], collection=runs))
    assert proj["operation"] == "refine" and proj["status"] == "succeeded"
    assert proj["requested_profile"]["region_id"] == "r1"
    assert proj["requested_profile"]["geometry_rev"] == 3
    assert proj["result_summary"]["geometry_rev"] == 3
    stages = [e["stage_id"] for e in proj["events"]]
    assert stages == ["refine.receive", "refine.propose", "refine.merge_curator_state",
                      "refine.persist_regions", "refine.complete"]


def test_refine_telemetry_failure_isolated(monkeypatch):
    posts, runs = _Posts(_refine_post()), FakeCollection(); runs.fail_insert = True
    _install_refine(monkeypatch, posts, runs)
    resp = run(R.refine_region_confirm(str(posts.post["_id"]), R.RefineRequest(base_id="r1", base_geometry_rev=2)))
    assert resp["run_id"] is None                                # telemetry degraded silently
    assert resp["region"]["mask_rle"] == {"size": [8, 8], "counts": "NEWMASK"}   # geometry intact
    assert posts.post["region_annotations"][0]["geometry_rev"] == 3             # real persist happened
    assert len(runs.docs) == 0                                   # no run doc created


# ════════════════════════ semantic-read (semantic family) ════════════════════

def _install_semantic(monkeypatch, posts, runs):
    async def _run_sem(post, img, *, intent="name", force=False):
        return {"assertions": [{"candidate_id": "c1", "label": "sleeve"}], "meta": {"status": "ready"}}
    monkeypatch.setattr(semantic_pass, "run_semantic", _run_sem)
    monkeypatch.setattr(semantic_pass, "merge_curator_state", lambda new, prior: new)
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(R, "_fetch_post_image_cached", _img)
    monkeypatch.setattr(svc, "vision_run_collection", runs)


def _sem_post():
    return {"_id": ObjectId(),
            "region_annotations": [{"id": "r1", "mask_rle": {"size": [4, 4], "counts": "M"}}],
            "semantics": None}


def test_semantic_read_records_run_and_never_touches_geometry(monkeypatch):
    posts, runs = _Posts(_sem_post()), FakeCollection()
    _install_semantic(monkeypatch, posts, runs)
    resp = run(R.semantic_read(str(posts.post["_id"]), R.SemanticReadRequest(intent="name")))

    assert isinstance(resp["run_id"], str)
    assert resp["semantics"]["assertions"][0]["candidate_id"] == "c1"
    assert resp["status"] == "ready"
    # EVERY write set only 'semantics' — geometry (region_annotations) never written
    assert posts.writes and all(set(w.keys()) == {"semantics"} for w in posts.writes)
    proj = run(svc.get_run(resp["run_id"], collection=runs))
    assert proj["operation"] == "semantic_read" and proj["status"] == "succeeded"
    assert proj["requested_profile"]["region_ids"] == ["r1"]      # correlation ref
    stages = [e["stage_id"] for e in proj["events"]]
    assert stages == ["semantic_read.receive", "semantic_read.fetch_image", "semantic_read.run",
                      "semantic_read.merge_curator_state", "semantic_read.persist_semantics",
                      "semantic_read.complete"]


def test_semantic_read_telemetry_failure_isolated(monkeypatch):
    posts, runs = _Posts(_sem_post()), FakeCollection(); runs.fail_insert = True
    _install_semantic(monkeypatch, posts, runs)
    resp = run(R.semantic_read(str(posts.post["_id"]), R.SemanticReadRequest()))
    assert resp["run_id"] is None
    assert resp["semantics"]["assertions"][0]["candidate_id"] == "c1"   # response unchanged
    assert posts.post.get("semantics", {}).get("meta", {}).get("status") == "ready"  # persist happened
    assert len(runs.docs) == 0


# ════════════════════════ find-similar (retrieval family) ════════════════════

class _Distinctable:
    async def distinct(self, field, query):
        return []


def _install_find_similar(monkeypatch, posts, runs, result):
    monkeypatch.setattr(R, "post_collection", posts)
    monkeypatch.setattr(R, "_fetch_post_image_cached", _img)
    monkeypatch.setattr(find_similar_service, "_domain_of", lambda post: "fashion")
    monkeypatch.setattr(retrieval_service, "route",
                        lambda **k: {"space": "evidence_identity", "reason": "ok"})
    monkeypatch.setattr(retrieval_service, "_SPACES",
                        {"evidence_identity": {"model": "dinov2_vits14"}})
    monkeypatch.setattr(region_embedding_service, "region_embeddings_collection", _Distinctable())

    async def _fs(post, region_id, img, **k):
        return copy.deepcopy(result)
    monkeypatch.setattr(find_similar_service, "find_similar_for_region", _fs)
    monkeypatch.setattr(svc, "vision_run_collection", runs)


def _fs_post():
    return {"_id": ObjectId(), "region_annotations": [{"id": "r1"}], "domain": {"label": "fashion"}}


def test_find_similar_records_run_and_writes_no_post_state(monkeypatch):
    result = {"status": "ready", "space": "evidence_identity", "mode": "identity",
              "results": [{"post_id": "x", "region_id": "y", "score": 0.9}]}
    posts, runs = _Posts(_fs_post()), FakeCollection()
    _install_find_similar(monkeypatch, posts, runs, result)
    resp = run(R.find_similar(str(posts.post["_id"]), "r1", R.FindSimilarRequest(mode="identity", top_k=8)))

    assert isinstance(resp["run_id"], str)                       # additive on the research dict
    assert resp["status"] == "ready" and len(resp["results"]) == 1
    assert posts.writes == []                                    # retrieval writes NO post state
    proj = run(svc.get_run(resp["run_id"], collection=runs))
    assert proj["operation"] == "find_similar" and proj["status"] == "succeeded"
    assert proj["requested_profile"]["region_id"] == "r1"
    assert proj["result_summary"]["neighbours"] == 1
    stages = [e["stage_id"] for e in proj["events"]]
    assert stages == ["find_similar.receive", "find_similar.route_space", "find_similar.scope",
                      "find_similar.fetch_image", "find_similar.retrieve", "find_similar.complete"]


def test_find_similar_degraded_retrieval_is_partial(monkeypatch):
    result = {"status": "unavailable", "space": "evidence_identity", "reason": "no index", "results": []}
    posts, runs = _Posts(_fs_post()), FakeCollection()
    _install_find_similar(monkeypatch, posts, runs, result)
    resp = run(R.find_similar(str(posts.post["_id"]), "r1", R.FindSimilarRequest()))
    proj = run(svc.get_run(resp["run_id"], collection=runs))
    assert proj["status"] == "partial" and proj["terminal_reason"] == "unavailable"


def test_find_similar_telemetry_failure_isolated(monkeypatch):
    result = {"status": "ready", "space": "evidence_identity", "results": [{"score": 0.5}]}
    posts, runs = _Posts(_fs_post()), FakeCollection(); runs.fail_insert = True
    _install_find_similar(monkeypatch, posts, runs, result)
    resp = run(R.find_similar(str(posts.post["_id"]), "r1", R.FindSimilarRequest()))
    assert resp.get("run_id") is None                            # research still returned
    assert resp["status"] == "ready" and len(runs.docs) == 0


# ════════════════════ recorder generalization + latest-by-operation ══════════

def test_dissect_recorder_alias_is_vision_run_recorder():
    assert svc.DissectRunRecorder is svc.VisionRunRecorder


def test_latest_run_is_operation_scoped():
    c = FakeCollection()
    rd = run(svc.create_run(post_id="p", operation="dissect", collection=c))
    rr = run(svc.create_run(post_id="p", operation="refine", collection=c))
    latest_refine = run(svc.get_latest_run("p", operation="refine", collection=c))
    latest_dissect = run(svc.get_latest_run("p", operation="dissect", collection=c))
    assert latest_refine["run_id"] == rr and latest_refine["operation"] == "refine"
    assert latest_dissect["run_id"] == rd and latest_dissect["operation"] == "dissect"


# ══════════════ P2.1R-R1 · cancellation terminalization + R3 FAILED ═══════════
# A cancelled request must terminalize an already-minted run as CANCELLED/request_cancelled
# and re-raise the original CancelledError (never swallow/translate). An ordinary exception
# must terminalize FAILED/route_exception and re-raise the primary error (R3).

def _assert_terminal(runs, status, reason):
    docs = list(runs.docs.values())
    assert len(docs) == 1, f"expected exactly one run, got {len(docs)}"
    assert docs[0]["status"] == status, f"status={docs[0]['status']}"
    assert docs[0]["terminal_reason"] == reason, f"reason={docs[0]['terminal_reason']}"


# ---- cancellation (all four instrumented routes) ----

def test_dissect_cancellation_terminalizes_cancelled(monkeypatch):
    from backend.tests.test_circulation_spine_p1 import _FakePosts, _fresh_post, _install_route_mocks
    from backend.schemas.post import RegionDetectRequest
    runs = FakeCollection(); posts = _FakePosts(_fresh_post())
    _install_route_mocks(monkeypatch, posts, runs)
    async def _cancel(q, u):
        raise asyncio.CancelledError()
    monkeypatch.setattr(posts, "update_one", _cancel)           # cancel at persist (after mint)
    with pytest.raises(asyncio.CancelledError):
        run(R.detect_regions(str(posts.post["_id"]), RegionDetectRequest(coarse_only=True)))
    _assert_terminal(runs, "cancelled", "request_cancelled")


def test_refine_cancellation_terminalizes_cancelled(monkeypatch):
    posts, runs = _Posts(_refine_post()), FakeCollection()
    _install_refine(monkeypatch, posts, runs)
    async def _cancel(q, u):
        raise asyncio.CancelledError()
    monkeypatch.setattr(posts, "update_one", _cancel)
    with pytest.raises(asyncio.CancelledError):
        run(R.refine_region_confirm(str(posts.post["_id"]),
                                    R.RefineRequest(base_id="r1", base_geometry_rev=2)))
    _assert_terminal(runs, "cancelled", "request_cancelled")


def test_semantic_cancellation_terminalizes_cancelled(monkeypatch):
    posts, runs = _Posts(_sem_post()), FakeCollection()
    _install_semantic(monkeypatch, posts, runs)
    async def _cancel(post, img, *, intent="name", force=False):
        raise asyncio.CancelledError()
    monkeypatch.setattr(semantic_pass, "run_semantic", _cancel)
    with pytest.raises(asyncio.CancelledError):
        run(R.semantic_read(str(posts.post["_id"]), R.SemanticReadRequest()))
    _assert_terminal(runs, "cancelled", "request_cancelled")


def test_find_similar_cancellation_terminalizes_cancelled(monkeypatch):
    result = {"status": "ready", "space": "evidence_identity", "results": []}
    posts, runs = _Posts(_fs_post()), FakeCollection()
    _install_find_similar(monkeypatch, posts, runs, result)
    async def _cancel(post, region_id, img, **k):
        raise asyncio.CancelledError()
    monkeypatch.setattr(find_similar_service, "find_similar_for_region", _cancel)
    with pytest.raises(asyncio.CancelledError):
        run(R.find_similar(str(posts.post["_id"]), "r1", R.FindSimilarRequest()))
    _assert_terminal(runs, "cancelled", "request_cancelled")


# ---- recorder finish() shields the finalize write under real task cancellation ----

def test_finish_shields_finalize_write_under_task_cancellation():
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()

        class Gated(FakeCollection):
            async def update_one(self, q, u):
                if isinstance(q.get("status"), dict):           # gate ONLY the finalize transition
                    started.set()
                    await release.wait()
                return await FakeCollection.update_one(self, q, u)

        coll = Gated()
        rid = await svc.create_run(post_id="p", operation="dissect", collection=coll)
        rec = svc.VisionRunRecorder(post_id="p", collection=coll)
        rec.run_id = rid
        task = asyncio.ensure_future(
            rec.finish(JobStatus.CANCELLED, terminal_reason="request_cancelled"))
        await started.wait()                                    # finish is mid shielded-write
        task.cancel()                                           # cancel the outer request
        release.set()                                           # let the shielded write proceed
        with pytest.raises(asyncio.CancelledError):
            await task                                          # cancellation is re-raised
        proj = None
        for _ in range(50):                                     # let the shielded task commit
            await asyncio.sleep(0)
            proj = await svc.get_run(rid, collection=coll)
            if proj["status"] == "cancelled":
                break
        assert proj["status"] == "cancelled"                   # write survived the cancellation
        assert rec._finished is True                           # no double-finalize afterwards
    asyncio.run(scenario())


# ---- R3 · ordinary-exception FAILED finalization (siblings) ----

def test_refine_ordinary_exception_finalizes_failed(monkeypatch):
    posts, runs = _Posts(_refine_post()), FakeCollection()
    _install_refine(monkeypatch, posts, runs)
    async def _boom(q, u):
        raise RuntimeError("db exploded")
    monkeypatch.setattr(posts, "update_one", _boom)
    with pytest.raises(RuntimeError, match="db exploded"):
        run(R.refine_region_confirm(str(posts.post["_id"]),
                                    R.RefineRequest(base_id="r1", base_geometry_rev=2)))
    _assert_terminal(runs, "failed", "route_exception")


def test_semantic_ordinary_exception_finalizes_failed(monkeypatch):
    posts, runs = _Posts(_sem_post()), FakeCollection()
    _install_semantic(monkeypatch, posts, runs)
    async def _boom(post, img, *, intent="name", force=False):
        raise RuntimeError("vlm exploded")
    monkeypatch.setattr(semantic_pass, "run_semantic", _boom)
    with pytest.raises(RuntimeError, match="vlm exploded"):
        run(R.semantic_read(str(posts.post["_id"]), R.SemanticReadRequest()))
    _assert_terminal(runs, "failed", "route_exception")


def test_find_similar_ordinary_exception_finalizes_failed(monkeypatch):
    result = {"status": "ready", "results": []}
    posts, runs = _Posts(_fs_post()), FakeCollection()
    _install_find_similar(monkeypatch, posts, runs, result)
    async def _boom(post, region_id, img, **k):
        raise RuntimeError("retriever exploded")
    monkeypatch.setattr(find_similar_service, "find_similar_for_region", _boom)
    with pytest.raises(RuntimeError, match="retriever exploded"):
        run(R.find_similar(str(posts.post["_id"]), "r1", R.FindSimilarRequest()))
    _assert_terminal(runs, "failed", "route_exception")
