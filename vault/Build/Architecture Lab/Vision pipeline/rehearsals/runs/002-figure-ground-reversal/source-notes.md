# 002 — Source notes

## The subject

Post `695be6c9a9ea58f1b6aef5e0`, read **read-only** from the live `visualDictionaryDB`. Its image
was downloaded once from `photo_url` and frozen as a local fixture so the rehearsal does not depend
on a remote URL staying alive.

- `fixtures/002-figure-ground-reversal/five-sculpture-collage.jpg`
- 680 × 286 JPEG, 35 720 bytes
- `sha256: c6c9fc86673ba3e7e0c25174c4f422843e644642d2037c9b169a45b9ac6e225f`

**What it is:** a labelled comparative plate. Five sculpted heads, photographed separately, cut out
and composited onto flat black, each captioned in white — Solanki, Gupta, Pala, Amaravati,
Gandhara, left to right. This was established by looking at it, and confirmed by the pixel
statistics in `score.md`.

**Metadata status:** the culture/period labels are **the plate's own captions**. No catalogue
number, collection, date, provenance, or material is available for any of the five heads. Nothing
in this rehearsal depends on the labels being correct — the finding concerns the interval and the
plate's construction, not the attribution of any head. No iconographic identification was
attempted.

## Pre-existing annotation layer (context; not the subject)

- **10** `region_annotations` — all objects (`figure` / `body-part`).
- **3** grounds — `gnd_mrpi1jbv_3/4/5`, all `ground_type: "region"`.
- **1** expression percept `pctx_mrpi3rjk_0`, on Gupta↔Pala facial geometry, citing those 3 grounds.

The percept is **context, not subject**. A1's gesture deliberately points away from it. Its
existence matters only as the demonstration that the whole existing layer is object-shaped.

## Why this fixture

Assigned by the R0 breadth portfolio, row **A1**: *"five-sculpture collage `695be6c9` (figurative,
crowded) — promote the interval between heads, not the heads."* The portfolio also predicted the
outcome: *"may stall if no evidence supports the void → a valid refusal."*

## No text source

Unlike `001-eyes-of-stone`, A1 loads **no theoretical text**. This is deliberate: R4 tests a
spatial lens, and the risk on an image this evocative is source ventriloquism — reaching for
Merleau-Ponty or Rasa theory on negative space and then finding what the source predicts. The
rehearsal was run against measurement instead. `source_pressures` is empty by choice, not by
oversight.

## Model

`qwen/qwen3.6-27b` on Groq, `reasoning_effort: "none"` (mandatory — see
`R2-batch-operating-plan.md`). Two calls, 25 s apart, no retries. Both returned
`finish_reason: "stop"` with no `<think>` leakage. Raw text was frozen verbatim; nothing was
parsed, coerced, or cleaned.

## Reproducing the measurements

The pixel statistics in `score.md` are model-free and recomputable from the frozen fixture with
PIL + numpy: interval `x ∈ [0.43, 0.46]`, comparison gaps `x ∈ [0.24, 0.27]` and `[0.62, 0.65]`,
faces `x ∈ [0.27, 0.43]` and `[0.46, 0.52]`, all over `y ∈ [0, 0.6]` to exclude the caption band.

Two derived inspection images (a 4× crop of the interval ±40 px, and a 2× view of the whole plate)
were generated during the rehearsal as viewing aids. They are **not committed**: they are pure
upscales of the frozen fixture, carry no evidentiary weight of their own, and are regenerable from
the fixture with the crop parameters above.

## Honesty notes

- The interval bounds derive from the annotated **face** boxes, not from the composited **cutout**
  edges. See `critique.md` §5 — these are different intervals.
- No production document was written at any point. The post was opened read-only.
