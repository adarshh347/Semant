# CIRCULATION-SPINE-001 · P1 — Implementation Report

**Branch:** `feat/circulation-spine-001-p1` (worktree), from `main@99e92b3` (Vision-F merge).
**Scope:** backend only. Nothing rendered — no `rendered-verified` claim appears anywhere in P1.

Evidence tags used below: `implemented` · `logic-tested` · `adopted` · `inferred` · `blocked`.
(`rendered-verified` is deliberately unused; P1 ships no UI.)

## What P1 does

Gives the inline production Dissect route (`POST /posts/{id}/detect-regions`) a truthful,
persistent, **execution-engine-neutral** Run + Stage-Event record — without changing its
visual results, geometry, failure semantics, or curator-preservation behaviour. Strategy 1
("instrument the inline route first"), exactly as the P0.5 executive recommendation and
strategy comparison concluded. `adopted`

## Deliverables

| File | Change | Tag |
|---|---|---|
| `backend/services/vision_orchestrator/vision_run_contracts.py` | **new** — fresh, import-safe VisionRun/VisionStageEvent contract; reuses `JobStatus` (verbatim) from `contracts.py`; stage-id constants; geometry guard; transport models; stale-aware projection | `implemented` |
| `backend/services/vision_run_service.py` | **new** — `vision_runs` persistence (create / append / transition / finalize / read / latest / ensure_indexes) + `DissectRunRecorder` (write-behind, never raises) | `implemented` |
| `backend/database.py` | +9 — one collection handle `vision_run_collection = get_collection("vision_runs")` | `implemented` |
| `backend/main.py` | +3 — wire `ensure_vision_run_indexes()` into startup, next to the taste/embedding index hooks | `implemented` |
| `backend/routers/posts.py` | instrument `detect_regions` at existing `await` seams; add `GET /{id}/vision-runs/latest` and `GET /{id}/vision-runs/{run_id}` | `implemented` |
| `backend/tests/test_circulation_spine_p1.py` | **new** — 27 tests (contract / lifecycle / degradation / route-equivalence) | `logic-tested` |
| `architecture-lab/circulation-spine/P1/*` | these eight reports | — |

## Contract at a glance

- **Operation** `dissect` — deliberately *not* `vision_service.detect_regions` (the Groq
  fallback detector), which appears only as the `dissect.fallback.detect` stage's adapter.
  No conflation. `implemented`
- **Statuses** are `JobStatus` verbatim (pending/running/succeeded/partial/skipped/
  unavailable/timed_out/cancelled/failed). `adopted`
- **Events** are an observation-ordered list; causal order rides `dependencies[]`, never
  array position (Invariants 14/15). `stage_id` is free-form + optional `capability`, so a
  future `Scheduler.run_plan` can emit the same contract unchanged. `implemented`
- **Provenance** payloads follow `Provenance.as_dict()`; populated opportunistically
  (`latency_ms` from real `perf_counter` deltas), never fabricated (Invariant 8). `implemented`
- **Persistence** is one poll-friendly `vision_runs` document with embedded events,
  mirroring the proven `agent_runs` run+step-ledger shape. `adopted`

## Model-role log (per direction §"Model roles")

1. **Fable** — verified the P0/P0.5 audit bundles against the live tree, confirmed the seams
   had not drifted (posts.py still at `24d0a52`), restated the boundary, and resolved two
   repo-state conflicts (missing bundles → user supplied them; `architecture-lab/`
   retirement is an r1-branch-only reorg, absent on main, so the literal report path is
   correct here).
2. **Opus** — implemented the contract, service, route instrumentation, read endpoints, and
   tests; ran the suites.
3. **Fable** — post-test contradiction/scope review (see `P1-surprises-and-corrections.md`).

Switches were announced to the user at each hand-off.

## Stop-gate status

All eight P1 completion conditions met — see `P1-test-evidence.md` for the mapping.
No PR opened, no merge, no P2 begun, no other worktree touched.
