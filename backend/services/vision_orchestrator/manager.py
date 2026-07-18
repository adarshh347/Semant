"""
VISION-ORCHESTRATOR-001 — ModelManager + DAG scheduler.

One-process, durable-enough orchestration:
  · resource pools with PRIORITY-aware acquisition — GPU capacity 1, heavy CPU 1,
    light CPU 2, remote 1 (all configurable); interactive work overtakes queued
    background work at job boundaries;
  · single-GPU residency with lazy load / explicit unload and load-vs-inference
    telemetry;
  · content-addressed cache lookup + in-flight de-duplication;
  · cancellation (cooperative, at job boundaries — never mid-kernel);
  · failure isolation (an adapter error becomes a FAILED JobResult, siblings survive);
  · a DAG runner that respects dependencies and fans a shared feature out to many
    consumers without recomputing it.

No torch/model import here — the manager drives adapters through the async protocol.
"""
from __future__ import annotations

import asyncio
import heapq
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .cache import ResultCache
from .contracts import (CancelToken, JobResult, JobStatus, Provenance, ResourceKind,
                        VisionArtifact, VisionJob)
from .registry import Adapter, AdapterRegistry


class PriorityResource:
    """An async capacity-limited resource whose waiters are served by priority (lower
    first), then FIFO. This is what lets an INTERACTIVE job overtake a queued BACKGROUND
    job for the single GPU slot."""

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self._in_use = 0
        self._waiters: List = []          # heap of (priority, seq, future)
        self._seq = 0

    async def acquire(self, priority: int) -> None:
        if self._in_use < self.capacity:
            self._in_use += 1
            return
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        heapq.heappush(self._waiters, (priority, self._seq, fut))
        self._seq += 1
        await fut
        self._in_use += 1

    def release(self) -> None:
        self._in_use -= 1
        if self._waiters and self._in_use < self.capacity:
            _, _, fut = heapq.heappop(self._waiters)
            if not fut.done():
                fut.set_result(True)


@dataclass
class Telemetry:
    live: Dict[str, int] = field(default_factory=dict)
    max_concurrency: Dict[str, int] = field(default_factory=dict)
    loads: int = 0
    unloads: int = 0
    infer_calls: int = 0
    load_ms_total: float = 0.0
    order: List[str] = field(default_factory=list)   # completion order (for priority tests)

    def enter(self, res: str) -> None:
        self.live[res] = self.live.get(res, 0) + 1
        self.max_concurrency[res] = max(self.max_concurrency.get(res, 0), self.live[res])

    def exit(self, res: str) -> None:
        self.live[res] = self.live.get(res, 1) - 1


class ModelManager:
    def __init__(self, registry: AdapterRegistry, cache: Optional[ResultCache] = None,
                 *, gpu: Optional[int] = None, cpu: int = 1, cpu_light: int = 2,
                 remote: int = 1) -> None:
        self.registry = registry
        self.cache = cache or ResultCache()
        self.telemetry = Telemetry()
        gpu = gpu if gpu is not None else int(os.environ.get("VISION_GPU_CONCURRENCY", "1"))
        self._pools = {
            ResourceKind.GPU: PriorityResource(gpu),
            ResourceKind.CPU: PriorityResource(cpu),
            ResourceKind.CPU_LIGHT: PriorityResource(cpu_light),
            ResourceKind.REMOTE: PriorityResource(remote),
        }
        self._resident: Dict[str, Adapter] = {}
        self._inflight: Dict[str, asyncio.Future] = {}

    # ── residency ───────────────────────────────────────────────────────────
    async def ensure_loaded(self, adapter: Adapter) -> None:
        if adapter.spec.name in self._resident:
            return
        # single GPU resident: unload any other GPU model before loading this one.
        if adapter.spec.resource is ResourceKind.GPU:
            for name, other in list(self._resident.items()):
                if other.spec.resource is ResourceKind.GPU:
                    await self.unload(name)
        load_ms = await adapter.load()
        self._resident[adapter.spec.name] = adapter
        self.telemetry.loads += 1
        self.telemetry.load_ms_total += (load_ms or 0.0)

    async def unload(self, name: str) -> None:
        adapter = self._resident.pop(name, None)
        if adapter is not None:
            await adapter.unload()
            self.telemetry.unloads += 1

    def resident(self) -> List[str]:
        return list(self._resident)

    # ── single-adapter execution ─────────────────────────────────────────────
    async def run_adapter(self, adapter: Adapter, payload: dict, *, priority: int,
                          cancel: CancelToken, cache_key: Optional[str] = None,
                          timeout_s: Optional[float] = None) -> JobResult:
        if cancel.cancelled:
            return JobResult(JobStatus.CANCELLED)
        # deferred / unavailable adapters never execute.
        if not adapter.is_available():
            return JobResult(JobStatus.UNAVAILABLE,
                             provenance=Provenance(adapter=adapter.spec.name,
                                                   error="adapter unavailable/deferred"))
        # cache hit → no adapter invocation.
        if cache_key is not None:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return JobResult(cached.status, artifact=cached.artifact,
                                 provenance=cached.provenance, from_cache=True)
            # in-flight dedup: identical concurrent work shares one execution.
            if cache_key in self._inflight:
                cached = await self._inflight[cache_key]
                return JobResult(cached.status, artifact=cached.artifact,
                                 provenance=cached.provenance, from_cache=True)

        loop = asyncio.get_event_loop()
        fut: Optional[asyncio.Future] = None
        if cache_key is not None:
            fut = loop.create_future()
            self._inflight[cache_key] = fut

        res = adapter.spec.resource
        pool = self._pools[res]
        await pool.acquire(priority)
        self.telemetry.enter(res.value)
        try:
            if cancel.cancelled:
                result = JobResult(JobStatus.CANCELLED)
            else:
                await self.ensure_loaded(adapter)
                self.telemetry.infer_calls += 1
                try:
                    coro = adapter.infer(payload, cancel)
                    result = await (asyncio.wait_for(coro, timeout_s) if timeout_s else coro)
                except asyncio.TimeoutError:
                    result = JobResult(JobStatus.TIMED_OUT,
                                       provenance=Provenance(adapter=adapter.spec.name,
                                                             error="timeout"))
                except Exception as e:  # failure isolation
                    result = JobResult(JobStatus.FAILED,
                                       provenance=Provenance(adapter=adapter.spec.name,
                                                             error=repr(e)))
        finally:
            self.telemetry.exit(res.value)
            pool.release()

        if cache_key is not None and result.ok:
            self.cache.put(cache_key, result)
        if fut is not None and not fut.done():
            fut.set_result(result)
        if cache_key is not None:
            self._inflight.pop(cache_key, None)
        self.telemetry.order.append(adapter.spec.name)
        return result


class Scheduler:
    """Runs a VisionJob DAG. Independent jobs proceed concurrently (bounded by the
    manager's resource pools); a job runs once all its deps have succeeded. A failed or
    unavailable dependency SKIPS its dependents but never its siblings."""

    def __init__(self, manager: ModelManager) -> None:
        self.manager = manager

    async def run_plan(self, jobs: List[VisionJob], cancel: Optional[CancelToken] = None
                       ) -> Dict[str, JobResult]:
        cancel = cancel or CancelToken()
        results: Dict[str, JobResult] = {}
        events: Dict[str, asyncio.Event] = {j.id: asyncio.Event() for j in jobs}
        by_id = {j.id: j for j in jobs}

        async def run_job(job: VisionJob) -> None:
            # wait for dependencies to finish
            for dep in job.deps:
                if dep in events:
                    await events[dep].wait()
            # a failed/unavailable/cancelled dependency skips this job
            dep_results = [results.get(d) for d in job.deps]
            if any(r is None or not r.ok for r in dep_results):
                results[job.id] = JobResult(JobStatus.SKIPPED,
                                            provenance=Provenance(adapter=job.adapter or job.kind,
                                                                  error="dependency not satisfied"))
                events[job.id].set()
                return
            if cancel.cancelled:
                results[job.id] = JobResult(JobStatus.CANCELLED)
                events[job.id].set()
                return
            # adapter-less orchestration steps (CanonicalDecode, CandidateMerge) are
            # inline: no model, they just succeed once their deps are satisfied. Candidate
            # merge is geometry-first (done in mask_geometry / candidate logic), never a
            # label-only parent step — this layer carries no label→geometry rule.
            if not job.adapter:
                art = VisionArtifact(kind=job.kind, data={"inline": True},
                                     provenance=Provenance(adapter=job.kind))
                results[job.id] = JobResult(JobStatus.SUCCEEDED, artifact=art)
                events[job.id].set()
                return
            adapter = self.manager.registry.get(job.adapter)
            if adapter is None:
                results[job.id] = JobResult(JobStatus.UNAVAILABLE,
                                            provenance=Provenance(adapter=job.adapter,
                                                                  error="no adapter registered"))
                events[job.id].set()
                return
            # pass dependency artifacts to the job (shared-feature fan-out)
            payload = dict(job.payload)
            payload["deps"] = {d: results[d].artifact for d in job.deps if results.get(d)}
            results[job.id] = await self.manager.run_adapter(
                adapter, payload, priority=int(job.priority), cancel=cancel,
                cache_key=job.cache_key, timeout_s=job.timeout_s)
            events[job.id].set()

        await asyncio.gather(*(run_job(by_id[j.id]) for j in jobs))
        return results
