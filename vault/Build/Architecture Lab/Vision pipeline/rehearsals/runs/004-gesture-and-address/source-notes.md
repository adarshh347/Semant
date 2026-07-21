# 004 — Source notes

## The three subjects

All read **read-only** from the live `visualDictionaryDB`; images downloaded once from `photo_url`
and frozen locally. Full pre-state (counts, region ids, hashes) is in `pre-state.json`.

| role | post | frozen fixture | original size |
|---|---|---|---|
| subject | `695be8baa9ea58f1b6aef609` | `subject-painting-bound-face.jpg` | 643×680, 71 601 B |
| neighbour | `695be790a9ea58f1b6aef5ef` | `neighbour-veiled-funerary.jpg` | 500×666, 52 519 B |
| negative | `695be843a9ea58f1b6aef5ff` | `negative-dark-structure.jpg` | 1366×2048, 489 602 B |

**Subject — a reproduction of an oil painting.** Visible brushwork and palette-knife strokes, a
signature at lower left. A figure in a dark jacket, head thrown back, lower face bound by a large
dark bow/scarf. R0's portfolio called this a **garment**; that reading came from fashion-segmenter
region labels (`dress`, `scarf`, `tie knot`, `collar`, `black tie`), not from the artwork. This is
the **third consecutive** portfolio fixture description found to be inherited detector output.

**Subject carries two coexisting region generations** — `fseg_*` (7) and `fine_*` (9), 16 total.
Unlike post `695be786`, where `arch_*` replaced `fine_*` and stranded two grounds, both survive
here. Re-dissection does not always replace. **Neither generation was disturbed.**

**Neighbour — a depiction.** B&W photograph of a weathered veiled funerary figure, outdoors, head
tilted back, eyes closed, mouth parted. Carries a **visible photographer watermark** at lower
right — a reproduction artifact on an otherwise depictive image, recorded so it is not mistaken for
carved content.

**Negative — a depiction.** Photograph of a dark metal structure/spire. No figure, no face, no body.

**Metadata status:** none of the three has a title, description, or catalogue data. No iconographic
identification was attempted; nothing here depends on attributing, dating, or naming any work.

## Probe variants and why they exist

Groq charges roughly **2400 tokens per image regardless of pixel dimensions**, against an 8000
tokens-per-minute ceiling. A three-image comparison therefore costs ~7200 tokens before any prompt
or completion.

- `probe/` — capped at 768 px long edge, used for the single-image probe 1.
- `probe2/` — capped at **256 px**, used for the three-image probe 2, with `max_tokens: 380`.

All three images were downscaled **identically** at each stage so none is privileged. Originals are
frozen unmodified in the fixture root, and every variant is hashed separately.

**This is a known confound, not a hidden one:** probe 2 judged all three images at 256 px and
mis-described the subject's head as tilted *downward* (it is thrown back) and the fabric as *lace*
(it is a heavy bow). See `critique.md` §1.

## Curator selection, not embedding selection

The neighbour was chosen by looking, on the grounds that both figures throw the head back and
withhold the face. Measured surface difference between subject and neighbour:

| | subject | neighbour |
|---|---|---|
| medium | oil paint (reproduction) | weathered stone (photograph) |
| mean luminance | 57.0 | 86.2 |
| **mean saturation** | 0.192 | **0.0000** |

The negative shares low-key darkness with the subject (87.9 % of pixels below luminance 64, vs
65.7 %) but contains no figure.

**The embedding counterfactual is untestable and was not claimed.** Subject has 37 region
embeddings; neighbour and negative have 0. Raw chromaticity in fact places the neighbour *closer*
to the subject (0.0494) than the negative (0.0697) — the naive argument is wrong, and the real
divergence is medium, saturation, and texture.

## No text source

No theoretical text is loaded. R7's discriminator was recorded in the batch plan as
*choreography, not Merleau-Ponty* — specifically to avoid source ventriloquism on a subject this
evocative. `source_pressures` is empty by choice.

## Model

`qwen/qwen3.6-27b` on Groq, `reasoning_effort: "none"`. **2 live calls**, both `finish_reason:
"stop"`, no `<think>` leakage. Raw text frozen verbatim; **no JSON parsing attempted**, so the
greedy-regex parse risk did not arise.

Probe 1 was captured during an attempt that later aborted when probe 2 was rejected; it was
**adopted from disk** rather than re-called, so the live-call budget reflects evidence actually
obtained. The trace records that event's provenance as `:reused_frozen`.

Three requests were rejected with HTTP 413 before execution, consuming **0 tokens**. Several small
diagnostic calls were made *outside* the rehearsal to isolate that failure; they are not
observations and carry no evidentiary weight.

## Honesty notes

- Probe 2's description of the subject is less accurate than probe 1's; resolution is the likely
  cause and the comparison rests on the degraded view.
- The negative did not function as designed — the model found an address in it. Recorded as a
  finding rather than repaired.
- No production document was written at any point.
