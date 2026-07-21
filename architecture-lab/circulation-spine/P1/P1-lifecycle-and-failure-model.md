# P1 — Lifecycle & Failure Model

## Run lifecycle

```
create_run → RUNNING ──finalize──▶ SUCCEEDED | PARTIAL | FAILED   (completed_at stamped)
                 │
                 └── a stalled RUNNING (updated_at older than STALE_AFTER_SECONDS=120s)
                     is PROJECTED `stale:true` with a real age — never mutated, never
                     claimed live forever.
```

- **create → running**: `create_run` mints status `RUNNING`, `created_at == started_at`.
  A run executes the moment it is minted inside the route, so there is no idle PENDING hop
  (unlike `agent_runs`, which is a queue). `implemented`
- **running → terminal**: `finalize`/`transition` stamps `completed_at` (Invariant 13:
  every successfully created run reaches a terminal status when the app can persist it).
- **Transition guard** (`transition`): the active→terminal write is *atomic* — a conditional
  `update_one({_id, status ∈ {pending,running}}, …)`. If it matches, done. If not, we
  re-read: terminal→**same** status is an idempotent no-op; terminal→**different**
  (including terminal→running) raises `IllegalRunTransition`. `logic-tested`
  (`test_duplicate_finalization_is_idempotent`,
  `test_illegal_terminal_to_running_is_rejected`,
  `test_conflicting_terminal_finalize_is_rejected`).
- **Event append** (`append_event`): atomic `$push` guarded by
  `{"events.event_id": {"$ne": id}}`; a duplicate event_id is a deterministic no-op
  returning `False` (never a second copy). `logic-tested`
  (`test_event_ids_cannot_be_appended_twice`).

## Route-status mapping (truthful, not decorative)

| Real route outcome | Run status | terminal_reason |
|---|---|---|
| anchors + fine both produced | `SUCCEEDED` | `ok` |
| fine decomposition raised (non-fatal; route still returns anchors) | `PARTIAL` | `fine_decomposition_degraded` |
| an unhandled exception propagates out of the route | `FAILED` | `route_exception` |

`PARTIAL` is reachable exactly because the route's own fine-decomposition `try/except` is
non-fatal — the instrumentation reads that reality, it doesn't invent a new one.
`logic-tested` (`test_route_records_partial_when_fine_decomposition_fails`).

## Write-behind failure model (Invariant 7 — telemetry is never load-bearing)

The route uses `DissectRunRecorder`, which **cannot raise** into the route:

| Failure point | Effect on Dissect | Effect on telemetry |
|---|---|---|
| `create_run` fails (store down) | none — route proceeds; `run_id` stays `None`; response `run_id:null` | `telemetry_degraded` (in-memory) |
| `append_event` fails / returns False | none | `telemetry_degraded=True` |
| `finalize` fails | none — primary result/exception preserved | `telemetry_degraded=True` |
| a primary route exception AFTER the run is minted | **re-raised unchanged** (primary stays primary) | best-effort `finalize(FAILED, terminal_reason="route_exception")` |

`logic-tested`: `test_run_store_creation_failure_does_not_raise`,
`test_event_append_failure_does_not_raise`, `test_finalization_failure_does_not_raise`,
`test_route_reraises_primary_exception_and_marks_run_failed`, and the equivalence test
proving a *failing* run store yields byte-identical route output (minus the additive
`run_id`).

## The unavoidable case: final telemetry write itself fails

If `finalize` cannot persist, the run doc is left in its last-written state (typically
`RUNNING` with events up to the last successful append). We do **not** spin up a background
reaper (no new distributed system in P1). Instead the **read projection** tells the truth:
a `RUNNING`/`PENDING` run whose `updated_at` is older than `STALE_AFTER_SECONDS` is returned
with `stale:true` and `staleness_seconds` computed from real timestamps. A poller thus sees
"this run stalled N seconds ago", never "still running forever". `logic-tested`
(`test_stale_running_run_is_projected_honestly`, `test_fresh_running_run_is_not_stale`).

When the *creation* write is what failed, there is no doc at all; `telemetry_degraded` lives
only in the recorder and surfaces as `run_id:null` in the route response — honestly "no
record", never a fake completion.

## What is NOT modelled (truthful absence)

- **Retry / cancellation / model-timeout** — the route has none (P0 §01); P1 records none.
  `blocked`/`absent` by design, not omission.
- **device / dtype / vram / checkpoint** — the inline service calls don't surface these;
  `provenance` stays absent rather than guessed (Invariant 8).
