# P1 — Surprises & Corrections

## Surprises during implementation

1. **The run pattern already exists in-repo.** `agent_runs` (research agent) is a persisted
   run-with-appended-step-ledger, poll-friendly, projected via `run_helper`. P1's
   `vision_runs` is a faithful sibling, so the shape is *adopted*, not invented — lower risk
   than the direction implied.
2. **`JobStatus` is richer than the inline route needs.** It already carries
   `skipped / unavailable / timed_out / cancelled`, so the contract can describe a future
   Scheduler's dep-skip and cancellation without any new vocabulary — the neutrality goal
   was cheaper than expected.
3. **The coarse pipeline is one big `try`, not per-stage.** Fetch + domain-route + all three
   segmenters + merge share a single `try/except`→vision-fallback. Splitting it to attribute
   a failure to an exact sub-stage would change exception scope (and could change which
   fallback runs), so P1 records the successful sub-stages individually and marks the
   *block* failure as `dissect.segment.coarse = FAILED` (cause preserved in `error`). This
   is a deliberate honesty/￿safety trade — recording reality over a prettier attribution.
4. **Report path flipped back.** The r1-branch CLAUDE.md says `architecture-lab/` is retired,
   but that reorg is not on `main`; a `main`-based branch legitimately writes to
   `architecture-lab/circulation-spine/P1/`.

## Fable contradiction/scope review — outcome: GO-WITH-FIXES

The post-implementation Fable review confirmed the load-bearing properties:

- **Failure behavior OK** — try/except boundaries match the pre-P1 `-` lines exactly;
  fallback selection unchanged; fine-decomposition still non-fatal; the primary exception is
  re-raised bare (never swallowed/replaced by telemetry); `rec.event`/`rec.finish` catch
  `Exception` internally and cannot raise into the route.
- **Engine-neutral OK** — free-form `stage_id`, unordered events, explicit `dependencies[]`;
  a Scheduler could emit the same contract unchanged.
- **No fabricated latency** — all `latency_ms` are real `perf_counter` deltas;
  device/dtype/vram never populated.
- **No phantom runs** — 400/404 precede the recorder mint, so invalid requests create no run.
- **No P2 scope creep** — Scheduler/rehearsal appear only in docstrings.

### Fixes applied (Fable → Opus, factual corrections)

| Fable finding | Severity | Action |
|---|---|---|
| Geometry guard validated `detail`/`refs` but **not** `provenance` (make_event) or `requested_profile` (new_run_doc) | CONCERN | **Fixed** — `_assert_geometry_free` now covers both; new test `test_geometry_guard_covers_provenance_and_requested_profile` |
| `initiator="curator"` was an unmeasured assertion (mislabels scripts/tests) | CONCERN | **Fixed** — changed to `"api"` (honest transport fact); reports updated |

### Findings acknowledged, deliberately **not** changed

| Finding | Severity | Why left as-is |
|---|---|---|
| Coarse-block failure attributed to `dissect.segment.coarse`, not the exact failing sub-stage (a fetch failure emits no `FETCH_IMAGE` FAILED) | minor | Splitting the shared `try` would alter exception scope / fallback selection — the very thing P1 must not touch. Cause is preserved in `error`. Documented. |
| `dissect.canonicalize_geometry = SUCCEEDED` even when 0 regions needed canonicalization | minor | The stage (the per-region loop) *did* run; `detail.region_count` is truthful. No dishonesty. |
| `_finished` guard: an exception *after* a successful `finish()` would leave the run SUCCEEDED while the route 500s | nit | Practically unreachable — only `len()`/dict-build remain after `finish()`. |
| `/vision-runs/latest` returns `{run:null}` for an unknown post rather than 404 | nit | Intentional: "latest" is a may-be-empty query used for refresh recovery; null is the honest empty answer. |

## Contradiction-honesty note

Nothing here was rewritten to look like a cleaner success than it is. The rendered/live-DB
verification is reported as **not done** (deferred to P2.0), the coarse-attribution limit is
kept visible, and the two review fixes are recorded rather than silently folded in.
