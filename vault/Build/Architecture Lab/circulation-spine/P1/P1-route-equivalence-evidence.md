# P1 — Route Equivalence Evidence

**Claim:** the instrumented Dissect route is output-equivalent to the pre-P1 route. The
only observable addition is an optional `run_id` field. `logic-tested` (not
`rendered-verified` — P1 is backend-only).

## Method

`test_route_output_equivalent_with_working_and_failing_telemetry` runs the **real**
`detect_regions` coroutine through mocked seams (fake `post_collection`, fake `httpx`
client, fixed YOLO anchors, fixed fine parts, `_resolve_is_fashion → False`) **twice**:

- **Run A** — a working fake `vision_runs` store.
- **Run B** — a store whose `insert_one` raises (telemetry effectively disabled/failing).

Both use identical inputs (a fresh deep-copied post with one creator region).

## Assertions (all pass)

| Property | Result |
|---|---|
| `resp_A` minus `run_id` **==** `resp_B` minus `run_id` | equal |
| `run_id` present (str) in A, `None` in B | ✓ |
| `regions` returned | identical in A and B |
| creator region survives (`actor=="creator"`, id `creator1`) | ✓ both |
| creator `mask_rle` unchanged (`{"size":[10,10],"counts":"creatorRLE"}`) | ✓ both |
| curator fields preserved (`user_note="keep me"`, `weight=5`) | ✓ both |
| `source` string (`"yolo+sukshma"`) | identical |
| `anchor_count` (2) / `fine_count` (1) / `creator_preserved` (1) | identical |
| persisted `region_annotations` **==** returned `regions` | ✓ both |

Because Run B's telemetry store *fails on every call*, this simultaneously proves the
write-behind guarantee: a broken run store changes nothing the caller can see.

## Fallback & partial equivalence

- `test_route_falls_back_and_records_it_when_segmentation_raises`: with segmentation raising
  and `coarse_only=True`, `source` is still `"vision"` (fallback unchanged); the run records
  `dissect.segment.coarse = failed` then `dissect.fallback.detect = succeeded` with
  `fallbacks:["vision"]`. Instrumentation did not change **which** fallback runs.
- `test_route_records_partial_when_fine_decomposition_fails`: fine decomposition raising
  leaves `fine_count == 0`, `anchor_count == 2`, route returns normally; run is `PARTIAL`.
- `test_route_reraises_primary_exception_and_marks_run_failed`: a persistence exception
  after the run is minted re-raises as the **primary** `RuntimeError` (not masked by
  telemetry); the run is finalized `FAILED` / `route_exception`.

## Geometry & curator invariants covered by existing suites (unchanged, still green)

The merge/dedup/canonicalize/creator-preservation logic itself is untouched by P1; its
guarantees remain covered by the pre-existing suites, re-run green on this branch:
`test_mask_geometry.py`, `test_region_geometry.py`, `test_vision_b2_segmenter.py`,
`test_vision_c5_mixed.py`, `test_domain_profiles.py`, `test_vision_orchestrator.py`,
`test_vision_semantic.py`, `test_vision_f1.py`, `test_vision_f4.py` — **122 passed**.

## Honest limits

- These are `logic-tested` with fakes, **not** a live Mongo / live-model / rendered run.
  A real detect-regions call against a running server + DB is deferred to P2's first step
  (the same class of blocker the R1 rendered probe hit; not attempted here to avoid a
  fabricated "verified" claim).
- The equivalence proof covers the code paths the mocks exercise (fashion/arch specialist
  passes are *not* exercised, only asserted absent when not chosen). A live run with a
  fashion image would exercise `dissect.segment.fashion`; its logic is identical shape.
