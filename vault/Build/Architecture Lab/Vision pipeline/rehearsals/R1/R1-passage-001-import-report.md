# R1 — Passage 001 import report (reconstructed run #0)

Passage 001 is imported as **`runs/000-passage-001/`** — a *reconstructed historical* run, never a
live capture. This validates the trace/manifest schemas against a rich real example and anchors the
program's memory, without promoting any construct.

## Immutability + provenance (amendment §3)

- **Source not copied.** `source.md` references the original by path
  (`vault/passage rehearsals/PASSAGE-REHEARSAL-001.md`) and records its **sha256
  `43225ff6…3ffcb4282f0965aceaa0e7`** — independently computed by Fable *and* by Opus's
  `local_file_digest` capture; they match. The Passage Score lives in the same vault file and is
  referenced by section + the same hash. The user-owned vault file is untouched.
- **Every trace event is `reconstructed: true`** (verified: 14/14).
- **Uncaptured values are null, not invented** (verified: 14/14 have `observation_ref: null` and
  `timestamp: null` with a `timestamp_null_reason`).
- `missing-telemetry.md` enumerates what was never captured.

## The reconstructed trace

14 events mapping the Passage Score's attention path onto the full event grammar:
`RECEIVE → ATTEND → ASK → CALL_ORGAN → OBSERVE → DISAGREE → REDIRECT → PROPOSE → HUMAN_TURN → CROSS →
RETURN → REVISE → SEDIMENT → HARVEST`. The `CALL_ORGAN` event is honestly hollow — `observation_ref:
null` — because no SAM/VLM was ever run in the original imaginative rehearsal.

## Missing telemetry (recorded, never guessed)

Real image/mask ids · `CALL_ORGAN` results · costs / latencies / model versions · reversibility ·
human real-time reactions with timestamps · first-view crops and image order · any rendered UI state.
The `observations/` dir is intentionally **empty** — run #0 is purely reconstructed; the CAPTURE
demo was routed to a scratch runs-root so nothing synthetic leaks into it.

## Harvest kept at SPARK (amendment §3)

`sparks.md` lists 11 constructs at **SPARK** level only (named once, one-line origin): posture-field,
kinetic dependency field, address field, context breathing, isolate-and-return,
compare-by-mode-of-address, gesture-thinking, Madeleine return, sedimented salience, determinate
interval, passage versions. **No candidate card was created** for any of them — a test asserts the
import emits zero cards and that no spark is above SPARK. None may graduate in its originating run
(patience rule).

## What this import is for

- Schema stress-test against a genuinely rich run (it validates).
- Records **source contribution** and **image order** so later runs can test whether the philosophy
  or the sequence manufactured the insight (run-without-source, sequence-inversion — R2/R3).
- The R2 (Sensitisation-and-Return) family exemplar the breadth portfolio deliberately does **not**
  merely repeat.

It is archival + schema-validating only. Nothing here is presented as a live capture, and nothing
becomes a product entity.
