# P1 → P2 Recommendation

**Status: for review. No P2 work has begun. No PR opened, no merge.**

## What P1 leaves standing

A truthful, persistent, engine-neutral `vision_runs` record for the inline Dissect route,
plus two read endpoints. Write-behind, geometry-free, `JobStatus`-verbatim, DAG-ready. The
one honest gap is that nothing has been exercised against a **live server + Mongo + real
models / browser** — every P1 claim is `logic-tested`, none `rendered-verified`.

## Recommended P2.0 — the deferred live verification (do this FIRST)

Before any new surface, close P1's verification gap exactly as R1's rendered probe was
deferred:

1. Run a **real** `POST /detect-regions` against a running backend + `visualDictionaryDB` on
   a real post; confirm a `vision_runs` document appears, `GET /{id}/vision-runs/{run_id}`
   returns it, event stages match the actual passes, and `region_annotations` /
   `mask_rle` / `geometry_rev` are byte-identical to a pre-P1 run.
2. Verify the write-behind guarantee live (point the collection at a failing target; confirm
   Dissect still succeeds and returns `run_id:null`).

This is currently **blocked** in-session by the exit-144 long-lived-server issue; it needs a
user-run local instance or a resolved server harness. Do not claim P1 "rendered-verified"
until this passes.

## Then, candidate P2 directions (pick one; each still additive)

- **A. Passage Rail (read-only).** A single new frontend component that polls
  `GET /{id}/vision-runs/latest` + `/{run_id}` and renders the run's stages. **Prerequisite
  the P0.5 atlas flagged:** decide the canonical Field surface first — the rail's host is
  ambiguous between `RegionSurface.jsx` and `DifferentialWorkspace.jsx`. Honesty constraint
  (Invariant 12): the rail must scope its claim to Dissect + the already-real recall
  circulation — it must **not** imply the other ~12 vision endpoints are observable.
- **B. Instrument sibling vision routes** (`enrich-regions`, `semantic-read`, refine,
  find-similar) in the *same* additive pattern, so "the passage" is genuinely observable
  before a rail claims it is.
- **C. Server-side `pct_` percept guard** — the cheapest backend fix the atlas exposed
  (reject durable `pct_` ids in `percepts`/chips). Rides any branch; its own reviewed
  semantic-contract increment, explicitly *after* P1.

## Explicitly NOT recommended yet

Scheduler/DAG migration (needs real adapters + a parity harness + GPU-residency rework — P1's
telemetry is the prerequisite baseline, not a detour); Atlas; Codex; corpus expansion; any
model-provider or CUDA change.

## One-line ask

Approve P2.0 (live verification) as the next step, and choose among A/B/C — or hold both
branches (this P1 branch + the untouched work) pending review.
