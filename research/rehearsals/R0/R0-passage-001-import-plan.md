# R0 — Passage 001 import plan (reconstructed historical run, not doctrine)

Passage 001 (`vault/passage rehearsals/PASSAGE-REHEARSAL-001.md`, "Gesture as the place where a
world is remembered") is the program's first and richest run. It must enter the research substrate
as **run #0** — a *reconstructed historical* trace — without pretending its telemetry was captured
live and without promoting any of its constructs.

## What Passage 001 actually is

An imaginative-mode rehearsal (doctrine §execution modes): real source text (Merleau-Ponty /
Benjamin / Proust distilled) + a described image constellation (two crowded reliefs, a three-view
figure, a dancing pair, two hand close-ups) + a human second-order observation ("the close-up
*taught the eye a gesture*"). It produced a Passage Score and an "architecture harvest," but **no
structured event trace, no real post/region ids, no rendered evidence, no model calls.**

## Import as run #0 (R1 work — planned, not executed here)

Location: `architecture-lab/rehearsals/runs/000-passage-001/`.

```text
runs/000-passage-001/
  manifest.yaml        # rehearsal_id, family (R2 Sensitisation-and-Return), mode: imaginative,
                       # reconstructed: true, conducted_by: human+prose, date_original, date_imported
  source.md            # the unedited seed text fragment + why-selected (discriminator/temporal/spatial lens)
  score.md             # the original Passage Score, verbatim (frozen)
  trace.json           # reconstructed event grammar, EACH event flagged reconstructed:true
  candidates.md        # the harvest as SPARK-level candidate stubs (not cards yet)
  missing-telemetry.md # explicit list of what was never captured
```

### Reconstructed trace — honest flags

Map the Passage Score's "attention path" (hand → wrist → whole-body → addressed space → reliefs →
multi-view → text → return) onto the event grammar (`RECEIVE → ATTEND → ASK → CALL_ORGAN → OBSERVE
→ DISAGREE → REDIRECT → PROPOSE → HUMAN_TURN → CROSS → RETURN → REVISE → SEDIMENT → HARVEST`). Every
event carries `reconstructed: true` and leaves genuinely-uncaptured fields **null**, never guessed.

### `missing-telemetry.md` — what was never captured (must be explicit)

- real image ids / masks (the images were *described*, not connected fixtures);
- `CALL_ORGAN` results (no SAM/DINOv2/VLM was actually run);
- costs, latencies, model versions, cancellation;
- reversibility and persistence outcomes (nothing was written);
- the human's real-time reactions with timestamps (only the after-the-fact Score);
- first-view crops and image order (sequence is claimed but not logged);
- any rendered UI state.

### Candidates as SPARK only (not cards)

The harvest — posture-field, kinetic dependency field, address field, context breathing,
isolate-and-return, compare-by-mode-of-address, gesture-thinking, Madeleine return, sedimented
salience, determinate interval, passage versions — is recorded at **SPARK** level (named once).
None becomes a CANDIDATE card until a *new, instrumented* rehearsal re-derives it (foundry
promotion ladder). Passage 001 cannot promote its own constructs (patience rule: "no candidate
graduates in its originating run").

## Why import it at all

- It anchors the trace/score schemas against a real, rich example (schema stress-test).
- It records **source contribution** so later runs can test whether the philosophy manufactured the
  insight (run without the source; counter-source) — the `05-source…` protocol.
- It is the R2 (Sensitisation-and-Return) family exemplar the breadth portfolio deliberately does
  **not** merely repeat.

## Explicit non-goals

No construct from Passage 001 becomes a schema, entity, UI element, or agent skill in R0/R1. The
import is archival + schema-validating only.
