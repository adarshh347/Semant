# P1 — Test Evidence

Environment: `venv` (project), no live Mongo / network / models. House style: sync tests
driving async code via `asyncio.run` with injected fake collections (cf. `test_vision_f1`).

## Counts

*Final P1 figures (post the two P1 review fixes). **P1.1 hardening supersedes these — see
`P1.1-test-evidence.md`: 40 suite / 265 full.***

- **New P1 suite** `test_circulation_spine_p1.py`: **28 passed** (P1.1 → **40**).
- **Targeted regression** (geometry / segmenter / merge / domain / orchestrator / semantic /
  recovery): **122 passed**.
- **Full backend suite** `backend/tests/`: **253 passed** — 225 pre-existing on `main` + 28
  new (P1.1 → **265**, +12). Zero failures, zero unrelated pre-existing failures observed.

## New-suite breakdown

**Contract validation (7):** valid VisionRun; valid VisionStageEvent; operation≠Groq
detector; every `JobStatus` value supported; unknown telemetry stays null (never guessed);
geometry payloads rejected in events; dependencies representable independent of order.

**Run lifecycle (10):** create→running→succeeded; →partial; →failed; terminal carries
`completed_at`; duplicate finalize idempotent; illegal terminal→running rejected;
conflicting terminal finalize rejected; event-id double-append is a deterministic no-op;
observation order stable + dependencies survive projection; `get_run` post-scoped
(ownership); latest-run is most recent for a post.

**Telemetry degradation (5):** create failure doesn't raise; append failure doesn't raise;
finalize failure doesn't raise; stale RUNNING projected honestly; fresh RUNNING not stale.

**Route equivalence (5):** working-vs-failing telemetry output-identical (minus `run_id`) +
creator/curator/mask_rle/source/counts preserved; run retrievable with a truthful,
correctly-ordered event list and no geometry leak; PARTIAL on fine-decomposition failure;
fallback recorded with `fallbacks:["vision"]` and unchanged source; primary exception
re-raised + run finalized FAILED.

## Stop-gate → evidence map

| # | Gate | Evidence | Tag |
|---|---|---|---|
| 1 | a real Dissect run produces a retrievable record | `test_route_creates_retrievable_run_with_truthful_events` | logic-tested |
| 2 | every event is an actually-executed / truthfully-skipped stage | same test asserts exact stage list; fashion/arch absent when not chosen; fallback test | logic-tested |
| 3 | geometry + curator-state equivalence | `test_route_output_equivalent_…` + 122-test regression | logic-tested |
| 4 | telemetry failure cannot break Dissect | 3 degradation tests + failing-store equivalence run | logic-tested |
| 5 | contract represents current sequential route AND a future DAG | free-form `stage_id`, unordered events, `dependencies[]`; `test_observation_order…`, `test_dependencies…` | logic-tested |
| 6 | no frontend/Scheduler/Atlas/Codex/Percept/rehearsal in the diff | `git status` scope guard (see file-boundary report) | implemented |
| 7 | relevant + full backend tests green | 253 passed (P1.1 → 265) | logic-tested |
| 8 | branch committed cleanly | see commit (implementation report) | implemented |

## Not claimed

- **No `rendered-verified` anything** — P1 ships no UI.
- **No live-DB / live-model integration run** — deferred to P2.0. Not attempted rather than
  faked (the exit-144 long-lived-server blocker persists this session).
