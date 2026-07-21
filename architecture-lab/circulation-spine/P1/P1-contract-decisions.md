# P1 — Contract Decisions

Fresh production contract in `vision_run_contracts.py` (import-safe: no torch/model/Mongo,
verified — `heavy_imports_pulled_in = []`). Rehearsal JSON schemas were **not** imported
(Invariant 10); the contract is authored from scratch, honouring the P0.5 atlas §06
neutrality rules.

## VisionRun document (mirrors `agent_runs`)

```jsonc
{
  "_id": ObjectId,                 // run_id == str(_id) in projection (agent_runs idiom)
  "contract_version": "vision-run-v1",
  "post_id": "…",
  "operation": "dissect",          // NOT vision_service.detect_regions (the Groq fallback)
  "status": "running",             // JobStatus verbatim
  "initiator": "api",              // honest transport fact — no auth principal (see note)
  "requested_profile": {"mode": "general", "lens": "", "coarse_only": false, "chosen": []},
  "actual_source": "yolo+sukshma", // the route's own `source` string, stamped at finalize
  "created_at": ISODate, "started_at": ISODate, "updated_at": ISODate,
  "completed_at": ISODate|null,
  "terminal_reason": "ok"|"fine_decomposition_degraded"|"route_exception"|null,
  "error": "…"|null,
  "telemetry_degraded": false,
  "events": [ VisionStageEvent, … ],
  "result_summary": {"anchor_count": 5, "fine_count": 12, "creator_preserved": 1, "region_count": 14}
}
```

**Deviations from the direction's conceptual field list** (per the "document every change"
requirement): none dropped; three added for repo-consistency —
- `updated_at` (poll freshness + the `agent_runs`/taste idiom);
- `terminal_reason` given concrete values (`ok` / `fine_decomposition_degraded` /
  `route_exception`);
- `result_summary` carries bounded counts only (never geometry).

`initiator = "api"` records the honest transport fact — this route carries no
authenticated principal, so we do **not** guess a human `"curator"` (a guess that would
mislabel acceptance scripts and tests). A future authenticated or background caller can set
a truer initiator. (Changed from an initial `"curator"` after the Fable review flagged it
as an unmeasured assertion — see `P1-surprises-and-corrections.md`.)

The geometry guard (`_assert_geometry_free`) also covers `provenance` and the run's
`requested_profile`, not just event `detail`/`refs` — defense-in-depth added after the same
review. `logic-tested` (`test_geometry_guard_covers_provenance_and_requested_profile`).

## VisionStageEvent (embedded)

```jsonc
{
  "event_id": "hex",               // uniqueness enforced at service layer (atomic $push guard)
  "run_id": "…",
  "contract_version": "vision-run-v1",
  "stage_id": "dissect.segment.general",   // FREE-FORM string, not an enum
  "capability": "segment"|null,            // optional tag; a future planner may set its own
  "status": "succeeded",                   // JobStatus verbatim
  "observed_at": ISODate,
  "started_at": null, "completed_at": null,
  "latency_ms": 42.3,              // ONLY when measured (real perf_counter delta), else null
  "dependencies": [],              // causal prerequisites — independent of array position
  "adapter": "yolo11_seg"|null,
  "provenance": null,              // Provenance.as_dict() when a path knows it; else absent
  "fallbacks": [],                 // e.g. ["vision"] on dissect.fallback.detect
  "input_refs": [], "output_refs": [],
  "error": null,
  "detail": {"count": 5}           // bounded summary; geometry keys REJECTED at build time
}
```

## Neutrality rules honoured (P0.5 atlas §06)

1. **No implied linearity** — `events` is an observation-ordered list; `project_run` never
   claims causal order; `dependencies[]` carries causality. A concurrent DAG fits unchanged.
2. **Free-form stage identity** — `stage_id: str` + optional `capability`. The current
   inline names (`dissect.segment.general`, …) and a future planner's job kinds
   (`GeneralPropose`, …) both fit with zero migration.
3. **Status = `JobStatus` verbatim** — covers both worlds, including fallback-vs-skip:
   fallback = `succeeded` + `fallbacks:["vision"]`; a skipped dep would be `skipped`.
4. **Provenance = `Provenance.as_dict()`** shape — opportunistic, never guessed.

## Geometry prohibition (Invariant 6)

`make_event` runs `_assert_geometry_free` over `detail`/`input_refs`/`output_refs`,
recursively rejecting `{mask_rle, mask, rle, polygon, polygons, bbox, box,
region_annotations, regions, segmentation, contours, points}` → raises
`GeometryInEventError`. The route passes only bounded counts, ids, and `source` strings.
`logic-tested` (`test_geometry_payloads_cannot_enter_events`,
`test_route_creates_retrievable_run_with_truthful_events`).

## Contract version

`CONTRACT_VERSION = "vision-run-v1"` stamped on every run and event from day one — the
repo's own versioning idiom (cf. `BACKUP_SCHEMA = "vision-f-backup-v1"`). A future
Scheduler migration keeps the same observable contract or bumps this deliberately.
