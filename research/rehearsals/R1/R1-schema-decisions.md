# R1 — Schema decisions

Four **research** JSON schemas (Draft 2020-12). They are *research artifacts*, not Pydantic/Mongo
models — none implies a production entity. Location: `architecture-lab/rehearsals/schemas/`.

## Validator: vendored, not a dependency

`jsonschema` is **not** installed in `venv`. Rather than add a dependency for research scaffolding,
Opus wrote a **minimal self-contained Draft-2020-12 validator** in `rehearsal_run.validate`
supporting type/enum/const/required/properties/additionalProperties/items/`$ref`/`$defs`/
`if-then-else`/anyOf-oneOf-allOf/minLength/minItems/pattern/minimum. A dedicated test
(`test_vendored_validator_rejects_wrong_types`) guards against false-greens. Decision rationale: the
research layer must not pull production dependencies; the validator only needs to cover the
constructs these four schemas use.

## `rehearsal-manifest.schema.json`

Captures the input packet + the amendment-8 experimental controls: `mode`
(imaginative|instrumented|prototype|product), `reconstructed`, `seed_constellation`,
`initiating_act`, **`image_order[]`** (order is an experimental variable), and **`source_condition`**
(present|absent|replaced|misleading) — so a run records whether the source was there, removed, swapped,
or misleading (source-ventriloquism / sequence-confounding guards).

## `rehearsal-trace.schema.json`

Append-only `events[]` with a shared `$defs/event`. Each event **requires**: `event_id`, `actor`,
`kind` (the 14-verb grammar), `parent_event` (id|null), `source_refs[]`, `target_refs[]`, `register`
(evidence|reading|opening — the doctrine's three registers), `uncertainty`, `reconstructed`,
`observation_ref` (id|null), `reversibility`, `cost` (obj|null), `provenance`, `timestamp`
(ISO|null). An `if/then` rule **forces `timestamp_null_reason`** whenever `timestamp` is null — the
schema itself refuses invented telemetry. `register:opening` lets a speculative event be recorded
*as* speculative (weak only when its status is hidden).

## `candidate-card.schema.json`

The CEC shape from `new-planning/02-…`. `epistemic_status` enum `SPARK|CANDIDATE|TRIAL|SUPPORTED|
GRADUATED|DEMOTED|RETIRED`. Two research-safety fields: **`research_only: const true`** (a card can
never claim to be a product entity) and **`percept_kind`** enum `[attention_percept,
expression_percept, n/a]` so a card attached to a `pctx_` vs `pct_` object is never ambiguous. R1
creates **no** real card — only a synthetic one in a test to validate the schema.

## `frozen-observation.schema.json`

`{observation_id, adapter, request_boundary, model, version, device, cost, latency_ms, output,
uncertainty, provenance, captured_at, content_hash}`. `content_hash` makes a capture verifiable
(proven: the digest of the vault passage matched `source.md`). This is the record that lets REPLAY be
deterministic without re-calling a model.

## What the schemas deliberately do NOT encode

No geometry, no mask, no region/percept *production* field, no Atlas/Codex/Passage structure. A trace
`source_ref`/`target_ref` is a string id that *resolves* to real evidence on demand — it never copies
a mask (the same discipline as a Writer Mention). If a future graduated candidate needs a durable
product field, that schema is written under normal `backend/` review, never here.
