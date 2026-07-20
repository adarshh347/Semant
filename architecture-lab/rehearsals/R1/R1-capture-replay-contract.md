# R1 — Capture / Replay determinism contract

The single most important correction the R1 amendment made: **do not call live model output
deterministic.** Determinism belongs to the *event grammar and replay*; a live sensory observation
is not deterministic. The runner therefore splits cleanly into two modes.

## CAPTURE mode

- May call an adapter **from an explicit allowlist** (`scripts/rehearsal_adapters.py`). A
  non-allowlisted adapter name raises.
- Records a **frozen observation** (`frozen-observation.schema.json`): adapter, request boundary,
  model, version, device, cost, latency_ms, output, uncertainty, provenance, `captured_at`,
  `content_hash`.
- Freezes the observation to `runs/<id>/observations/<observation_id>.json` and references it from
  the trace event's `observation_ref`.
- Is **not** reproducible bit-for-bit if the adapter is a live model — that is expected and honest.
  The trace records *that* a call was made, its boundary and provenance, and the returned value at
  capture time.
- **R1 scope:** the only allowlisted adapter is `local_file_digest` — a pure, local, deterministic
  function (sha256 + size of a fixture file). No SAM / YOLO / SegFormer / DINOv2 / FashionCLIP /
  semantic / LLM call happens in R1. Live sensory adapters are added in R2 under explicit approval.

## REPLAY mode

- Uses **only frozen observations** already on disk; makes **no** network / model / GPU call.
- Reproduces the event trace **deterministically** from the manifest + frozen observations. Same
  inputs → identical trace, every time.
- Is what tests, comparison, and later evaluation run against. A run is "replayable" iff every
  `CALL_ORGAN` event resolves to a frozen `observation_ref`.

## Why the split matters

- It prevents "meta-awareness theatre": a trace that looks reproducible but silently re-queries a
  model. Replay proves the *reasoning path* is stable independent of model nondeterminism.
- It lets a rich live rehearsal (R2+) be **captured once** and then **studied, critiqued, and
  transferred** deterministically — the foundry's origin-replay test runs against frozen truth.
- It keeps the honesty register the doctrine demands: an Opening (speculative) and a live
  Observation are both allowed, but neither is dressed as deterministic fact.

## Invariants the contract enforces

- The runner **never** writes Mongo / posts / region_embeddings / any production schema; research
  output goes only to `runs/<id>/` on disk.
- The runner **never invents missing telemetry** — an uncaptured field is `null` (with a reason),
  never guessed.
- The runner **refuses to overwrite a frozen run** — re-capturing into an existing run id raises
  unless an explicit new id is given.
- A run may terminate as `refused` or `stalled`; that is a **valid terminal outcome**, recorded,
  not raised as an error and not smoothed into success.
- `pct_` (attention_percept) vs `pctx_` (expression_percept) is disambiguated at the boundary; a
  bare/ambiguous percept id is rejected, never silently coerced.

(Implementation details, exact file paths, and the test evidence proving these hold are in
`R1-implementation-report.md`, `R1-schema-decisions.md`, and `R1-test-and-safety-evidence.md`.)
