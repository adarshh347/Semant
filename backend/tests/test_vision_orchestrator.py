"""
VISION-ORCHESTRATOR-001 / VISION-BUILD-001 B1 — deterministic fake-adapter tests.

Covers the B1 gate: GPU concurrency=1, cancellation, unload lifecycle, cache
hit/invalidation, deferred/optional adapters, failure isolation, and DINO-like
shared-feature fan-out without duplicate encoding — plus multi-label routing,
region-level selectivity, DAG order, interactive-over-background priority, timeout,
dedup, and cache-key invalidation rules. No models, no torch, no network — async code
is driven via asyncio.run so no pytest-asyncio dependency is added.
"""
import asyncio
from dataclasses import replace

import pytest

from backend.services.vision_orchestrator import (
    AdapterRegistry, CancelToken, FakeAdapter, JobStatus, ModelManager, Priority,
    PriorityResource, ResourceKind, Scheduler, build_plan, default_roster,
    propose_profiles, embedding_key, semantic_key, feature_key, ResultCache)
from backend.services.vision_orchestrator.contracts import AdapterSpec, VisionJob


def reg_with(available=None, fail=(), latency=0.02):
    """A registry with a fake adapter per roster entry; `available` names execute."""
    available = set(default_names() if available is None else available)
    reg = AdapterRegistry()
    for spec in default_roster():
        reg.register(FakeAdapter(replace(spec, available=(spec.name in available)),
                                 latency=latency, fail=(spec.name in fail)))
    return reg


def default_names():
    return [s.name for s in default_roster()]


def run(coro):
    return asyncio.run(coro)


# ── GPU concurrency = 1 ──────────────────────────────────────────────────────
def test_gpu_concurrency_never_exceeds_one():
    reg = reg_with(available=["yolo11n_seg", "sam21_hiera_tiny", "dinov2_vits14"], latency=0.05)
    mgr = ModelManager(reg)

    async def go():
        cancel = CancelToken()
        gpu = [reg.get(n) for n in ("yolo11n_seg", "sam21_hiera_tiny", "dinov2_vits14")]
        await asyncio.gather(*(mgr.run_adapter(a, {}, priority=int(Priority.FOREGROUND),
                                               cancel=cancel) for a in gpu))
        return mgr.telemetry.max_concurrency

    maxc = run(go())
    assert maxc.get("gpu", 0) == 1            # never two heavy GPU jobs at once


def test_cpu_light_pool_allows_two():
    reg = reg_with(available=["cpu_perceptual"], latency=0.05)
    mgr = ModelManager(reg)

    async def go():
        a = reg.get("cpu_perceptual")
        cancel = CancelToken()
        await asyncio.gather(*(mgr.run_adapter(a, {"i": i}, priority=int(Priority.BACKGROUND),
                                               cancel=cancel) for i in range(3)))
        return mgr.telemetry.max_concurrency

    maxc = run(go())
    assert maxc.get("cpu_light", 0) == 2      # bounded pool of two, not three


# ── cancellation ─────────────────────────────────────────────────────────────
def test_cancellation_mid_flight_returns_cancelled():
    reg = reg_with(available=["yolo11n_seg"], latency=0.1)
    mgr = ModelManager(reg)

    async def go():
        cancel = CancelToken()
        a = reg.get("yolo11n_seg")
        task = asyncio.create_task(mgr.run_adapter(a, {}, priority=0, cancel=cancel))
        await asyncio.sleep(0.02)
        cancel.cancel()                       # cancel during the fake's work
        return await task

    res = run(go())
    assert res.status is JobStatus.CANCELLED


def test_cancelled_plan_skips_downstream():
    reg = reg_with()
    mgr = ModelManager(reg)
    sched = Scheduler(mgr)
    prof = propose_profiles({"fashion": 0.9})
    jobs = build_plan(prof, image_hash="h", refine=True)

    async def go():
        cancel = CancelToken(); cancel.cancel()
        return await sched.run_plan(jobs, cancel)

    results = run(go())
    assert all(r.status in (JobStatus.CANCELLED, JobStatus.SKIPPED) for r in results.values())


# ── unload lifecycle + single-GPU residency ─────────────────────────────────
def test_unload_and_single_gpu_residency():
    reg = reg_with(available=["yolo11n_seg", "sam21_hiera_tiny"])
    mgr = ModelManager(reg)

    async def go():
        a, b = reg.get("yolo11n_seg"), reg.get("sam21_hiera_tiny")
        await mgr.ensure_loaded(a)
        assert mgr.resident() == ["yolo11n_seg"]
        await mgr.ensure_loaded(b)            # loading a 2nd GPU model unloads the first
        assert "yolo11n_seg" not in mgr.resident() and "sam21_hiera_tiny" in mgr.resident()
        assert a.unloaded is True
        await mgr.unload("sam21_hiera_tiny")
        assert mgr.resident() == [] and b.unloaded is True

    run(go())


# ── cache hit / invalidation ─────────────────────────────────────────────────
def test_cache_hit_avoids_adapter_call_and_invalidation_reruns():
    reg = reg_with(available=["yolo11n_seg"])
    mgr = ModelManager(reg)
    a = reg.get("yolo11n_seg")

    async def go():
        cancel = CancelToken()
        r1 = await mgr.run_adapter(a, {}, priority=0, cancel=cancel, cache_key="K1")
        r2 = await mgr.run_adapter(a, {}, priority=0, cancel=cancel, cache_key="K1")
        assert r1.ok and r2.ok and r2.from_cache and not r1.from_cache
        assert a.infer_calls == 1             # second served from cache
        mgr.cache.invalidate(lambda k: k == "K1")
        r3 = await mgr.run_adapter(a, {}, priority=0, cancel=cancel, cache_key="K1")
        assert r3.ok and not r3.from_cache and a.infer_calls == 2

    run(go())


def test_inflight_dedup_shares_one_execution():
    reg = reg_with(available=["yolo11n_seg"], latency=0.05)
    mgr = ModelManager(reg)
    a = reg.get("yolo11n_seg")

    async def go():
        cancel = CancelToken()
        r1, r2 = await asyncio.gather(
            mgr.run_adapter(a, {}, priority=0, cancel=cancel, cache_key="DUP"),
            mgr.run_adapter(a, {}, priority=0, cancel=cancel, cache_key="DUP"))
        assert r1.ok and r2.ok and a.infer_calls == 1   # concurrent identical work deduped

    run(go())


def test_cache_keys_invalidate_on_the_right_change():
    # a LABEL change must NOT change the embedding key; a MASK change MUST.
    base = embedding_key("img", "maskA", "identity", "fashion-clip", "v1")
    same_label = embedding_key("img", "maskA", "identity", "fashion-clip", "v1")
    new_mask = embedding_key("img", "maskB", "identity", "fashion-clip", "v1")
    assert base == same_label and base != new_mask
    # a new candidate set (new geometry revision) changes the semantic/VLM key.
    s1 = semantic_key("img", "candsetA", "p1", "s1", "vlm")
    s2 = semantic_key("img", "candsetB", "p1", "s1", "vlm")
    assert s1 != s2
    # preprocessing/model version changes the feature key.
    f1 = feature_key("img", "dinov2_vits14", "ckA", "v1", 518)
    f2 = feature_key("img", "dinov2_vits14", "ckA", "v2", 518)
    assert f1 != f2


# ── deferred / optional adapters ─────────────────────────────────────────────
def test_deferred_adapter_is_unavailable_and_never_runs():
    reg = reg_with(available=["yolo11n_seg"])   # everything else deferred
    mgr = ModelManager(reg)
    dep = reg.get("fashionpedia_r50fpn")         # deferred (available=False)

    async def go():
        return await mgr.run_adapter(dep, {}, priority=0, cancel=CancelToken())

    res = run(go())
    assert res.status is JobStatus.UNAVAILABLE and dep.infer_calls == 0


# ── failure isolation ────────────────────────────────────────────────────────
def test_one_domain_failure_preserves_other_domain_results():
    reg = reg_with(available=["yolo11n_seg", "fashionpedia_r50fpn", "segformer_b0_ade",
                              "fashion_clip_router", "cpu_perceptual"],
                   fail=["fashionpedia_r50fpn"])
    mgr = ModelManager(reg)
    sched = Scheduler(mgr)
    prof = propose_profiles({"fashion": 0.9, "architecture": 0.8})
    jobs = build_plan(prof, image_hash="h")

    results = run(sched.run_plan(jobs))
    assert results["fashion"].status is JobStatus.FAILED
    assert results["architecture"].status is JobStatus.SUCCEEDED   # sibling survives
    assert results["general"].status is JobStatus.SUCCEEDED
    assert results["merge"].status is JobStatus.SKIPPED            # a dep failed → skip


# ── shared-feature fan-out (DINO computed once) ──────────────────────────────
def test_dino_feature_fans_out_without_duplicate_encoding():
    reg = reg_with()   # all roster available
    mgr = ModelManager(reg)
    sched = Scheduler(mgr)
    prof = propose_profiles({})
    jobs = build_plan(prof, image_hash="h", deep=True)

    results = run(sched.run_plan(jobs))
    dino = reg.get("dinov2_vits14")
    assert dino.infer_calls == 1                                   # encoded exactly once
    for consumer in ("texture", "pattern", "material"):
        assert results[consumer].status is JobStatus.SUCCEEDED     # all three fanned out


# ── multi-label routing + region-level selectivity ───────────────────────────
def test_multilabel_profile_and_selective_jobs():
    prof = propose_profiles({"fashion": 0.86, "architecture": 0.72, "painting": 0.05})
    assert prof.chosen == ["general", "fashion", "architecture"]   # painting below gate
    ids = {j.id for j in build_plan(prof, image_hash="h")}
    assert "fashion" in ids and "architecture" in ids and "painting" not in ids

    fashion_only = {j.id for j in build_plan(propose_profiles({"fashion": 0.9}), image_hash="h")}
    assert "fashion" in fashion_only and "architecture" not in fashion_only  # not every parser everywhere


def test_user_override_wins():
    prof = propose_profiles({"fashion": 0.1})            # auto would pick general only
    overridden = replace(prof, chosen=["general", "architecture"], user_overridden=True)
    ids = {j.id for j in build_plan(overridden, image_hash="h")}
    assert "architecture" in ids and "fashion" not in ids


# ── DAG dependency order ─────────────────────────────────────────────────────
def test_dag_dependencies_satisfied_before_merge():
    reg = reg_with()
    sched = Scheduler(ModelManager(reg))
    jobs = build_plan(propose_profiles({"fashion": 0.9}), image_hash="h")
    results = run(sched.run_plan(jobs))
    assert results["general"].ok and results["fashion"].ok and results["merge"].ok
    merge_job = next(j for j in jobs if j.id == "merge")
    assert "general" in merge_job.deps and "fashion" in merge_job.deps


# ── interactive priority overtakes queued background ─────────────────────────
def test_priority_resource_serves_interactive_before_background():
    async def go():
        pr = PriorityResource(1)
        await pr.acquire(int(Priority.FOREGROUND))   # occupy the single slot
        order = []

        async def worker(pri, label):
            await pr.acquire(pri)
            order.append(label)
            pr.release()

        bg = asyncio.create_task(worker(int(Priority.BACKGROUND), "bg"))
        inter = asyncio.create_task(worker(int(Priority.INTERACTIVE), "inter"))
        await asyncio.sleep(0.01)                     # let both queue
        pr.release()                                  # free slot → highest priority first
        await asyncio.gather(bg, inter)
        return order

    assert run(go())[0] == "inter"


# ── timeout ──────────────────────────────────────────────────────────────────
def test_timeout_returns_timed_out():
    reg = reg_with(available=["yolo11n_seg"], latency=0.1)
    mgr = ModelManager(reg)
    a = reg.get("yolo11n_seg")
    res = run(mgr.run_adapter(a, {}, priority=0, cancel=CancelToken(), timeout_s=0.02))
    assert res.status is JobStatus.TIMED_OUT


# ── no second geometry contract / no label-only merge ────────────────────────
def test_merge_is_adapterless_and_geometry_first():
    jobs = build_plan(propose_profiles({"fashion": 0.9}), image_hash="h")
    merge = next(j for j in jobs if j.id == "merge")
    assert merge.adapter is None                       # merge runs no model, no label rule
    # it depends only on geometry-producing jobs, never on a semantic/label job.
    assert set(merge.deps) <= {"general", "fashion", "architecture", "painting"}
