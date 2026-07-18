# VISION-ORCHESTRATOR-001 — orchestration skeleton report (VISION-BUILD-001 B1)

**Date:** 2026-07-19 · **Branch:** `feat/vision-differential` · **Scope:** B1 — the
current-model orchestration skeleton. No models installed/executed; the registry and
planner nonetheless model the complete `VISION-MODEL-MATRIX-001` roster as deferred
adapters, and every test runs on deterministic fakes. Preconditions: B0 committed
(`ad5a1bd`, CUDA runtime live), Increment A canonical mask service in place.

## Inherited code wrapped vs new orchestration code

- **New (this increment)** — package `backend/services/vision_orchestrator/`:
  `contracts.py`, `registry.py`, `cache.py`, `manager.py`, `planner.py`, `__init__.py`.
  Pure-Python, torch-free on import (verified), so it loads in a slim deploy.
- **Inherited (not yet wrapped — B2+):** `segmentation_service` (YOLO),
  `fashion_segmentation_service` (SegFormer-clothes), `fashion_clip_service`,
  `region_embedding_service`. B1 registers **fake** adapters bearing these models' specs;
  the real wrappers land in B2 (YOLO `Segmenter`) and later. The canonical geometry owner
  `mask_geometry.py` (Increment A) is the single geometry contract — the orchestrator
  defines **no** second one; adapter masks enter as RLE.

## Job graph & state transitions

Planner (`planner.py`) emits a `VisionJob` DAG matching the contract's job graph:

```
decode → cheap_signals, route, general
general → fashion? / architecture? / painting?   (only for chosen profiles)
{general, domain*} → merge
merge → refine? , embed , semantic
decode → dino → texture, pattern, material        (DINO computed once, fanned out)
```

Job states: `PENDING → RUNNING → {SUCCEEDED | PARTIAL | FAILED | TIMED_OUT | CANCELLED
| UNAVAILABLE}`; a job whose dependency is not `ok` becomes `SKIPPED`. Adapter-less steps
(decode, merge) are inline successes — merge is geometry-first, carrying no label→geometry
rule.

## Concurrency / resource policy

`ModelManager` holds one `PriorityResource` per `ResourceKind`:

| resource | capacity | notes |
|---|---|---|
| GPU | **1** (env `VISION_GPU_CONCURRENCY`) | one heavy job; single resident GPU model |
| CPU (heavy) | 1 | begins at 1 |
| CPU_LIGHT | 2 | colour/geometry operators |
| REMOTE (VLM) | 1 | per-image, deduplicated |

`PriorityResource` serves waiters by priority then FIFO, so an **INTERACTIVE** job
overtakes a queued **BACKGROUND** job for the GPU slot (tested). Cancellation is
cooperative at job boundaries (never mid-kernel). Single-GPU residency: loading a second
GPU model unloads the first; load time is recorded separately from inference time.
Telemetry tracks live/max concurrency per resource, loads/unloads, infer calls.

## Cache key & invalidation table (`cache.py`)

| class | key parts | invalidates when |
|---|---|---|
| Canonical image | sha256(EXIF-transposed RGB bytes) | pixels change |
| Model feature | image_hash + model_id + checkpoint + preproc_ver + input_size | model/checkpoint/preproc/size change |
| Analysis result | image_hash + job_kind + profile + operator_ver + params | operator/params/profile change |
| Region embedding | image_hash + mask_hash + crop_mode + embed_model + preproc_ver | **mask** changes (a **label** change does not) |
| Semantic/VLM | image_hash + candidate_set_digest + prompt_ver + schema_ver + vlm_model | new geometry revision (new candidate set) |

`ResultCache` records hits/misses/bypasses/stores/invalidations/avoided_calls; a cache hit
skips the adapter call entirely; in-flight identical work is de-duplicated. Authoritative
Regions/Grounds/Percepts are never stored here.

## Changed files / commits / tests

- New package `backend/services/vision_orchestrator/` (6 files); new
  `backend/tests/test_vision_orchestrator.py` (17 tests).
- Commit: this increment (see git log; B0 was `ad5a1bd`).
- **B1 gate — 17/17 pass**, full backend suite **69 passed**: GPU concurrency never > 1;
  CPU-light pool = 2; mid-flight cancellation; cancelled plan skips downstream; unload +
  single-GPU residency; cache hit avoids the adapter call; invalidation re-runs; in-flight
  dedup; cache keys invalidate on mask/candidate-set/preproc (not label); deferred adapter
  is UNAVAILABLE and never runs; one domain failure preserves the other domain's result;
  DINO feature encoded once and fanned out to 3 consumers; multi-label profile +
  region-level selectivity; user override wins; DAG deps satisfied before merge;
  interactive overtakes background; timeout → TIMED_OUT; merge adapter-less/geometry-first.

## Current limitations & restart behavior

- One-process, in-memory: the `ResultCache` and telemetry do not survive a restart; a
  restart re-plans and re-runs (idempotent by cache key once a disk-backed store lands —
  a later increment; the interface is kept small to swap in).
- No real disk/object artifact store yet; no persistent GPU tensors by design.
- Fakes only — no adapter executes a real model in B1.

## Exact adapter slot for the first MaskRefiner benchmark (B3)

`AdapterSpec(name="sam21_hiera_tiny", capability=Capability.MASK_REFINE,
resource=ResourceKind.GPU, model_id="sam2.1_hiera_tiny")` — registered deferred in
`default_roster()`. B3 replaces its fake with a real wrapper implementing the `Adapter`
protocol (`load`/`unload`/`infer`), driven through `ModelManager.run_adapter` on the GPU
pool with point/box/existing-mask prompts, returning a mask as canonical RLE (a new
geometry revision, non-destructive until curator confirmation).
