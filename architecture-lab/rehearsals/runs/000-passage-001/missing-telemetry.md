# Passage 001 — missing telemetry (what was NEVER captured)

Passage 001 was an **imaginative-mode** prose rehearsal. Its trace is a
**reconstruction** (`reconstructed: true` on every event). The following was
never captured and is therefore recorded as `null` in `trace.json` — never
guessed, never invented.

## Evidence identity
- **Real image ids / masks.** The six images were *described* in prose, not
  connected as real fixtures. `seed_constellation.images[].real_id` is `null`;
  trace `source_refs`/`target_refs` use `recon-*` placeholder ids only.
- **Real mask_rle / region ids / ground ids.** None exist. No geometry was
  produced or referenced.
- **Real percepts.** No `pct_` (attention) or `pctx_` (expression) percept was
  connected or composed. `seed_constellation.existing_percepts` is empty.

## Organ / model calls
- **`CALL_ORGAN` results.** No SAM / SAM2 / YOLO / SegFormer / DINOv2 /
  FashionCLIP / semantic-provider / VLM call was ever run. Event `e3` marks the
  segmentation the prose *imagines*, with `observation_ref: null`.
- **Model versions, devices, cost, latency, cancellation.** None. Every event's
  `cost` is `null`; no frozen observation exists under `observations/`.

## Cross-image / retrieval
- **`retrieval_service` / `find_similar` calls.** The "Madeleine return" cross
  (event `e9`) was described, not executed; no neighbour set was captured.

## Reversibility / persistence
- **Reversibility and persistence outcomes.** Nothing was written; every event's
  `reversibility` is `null`. No rollback/ledger record exists.

## Human real-time signal
- **Timestamped human reactions.** Only the after-the-fact Passage Score exists.
  Every `timestamp` is `null` with a `timestamp_null_reason`.
- **First-view crops and image order.** The attention path is *claimed* by the
  Score but was never logged. `manifest.yaml:image_order` is a reconstruction,
  not a recording.

## Rendered UI
- **Any rendered UI state.** No Differential / Writer / recall surface was
  driven; no screenshot, no `data-percept-id` chip, no recall script exists.

## Consequence
Because none of the above was captured, Passage 001 can validate the schemas and
anchor the trace grammar, but it can **support no construct beyond SPARK**. See
`sparks.md`.
