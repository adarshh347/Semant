# A3 — Execution note (prepared, NOT executed)

**Family:** R7 Gesture and Address · **Status: ready to run, with two corrections to the portfolio.**
Prepared under gate R2-A3P. No A3 model calls have been made.

---

## Correction 1: the subject is not a garment photograph — it is an oil painting

R0's A3 row calls `695be8ba` a **garment**. Looking at the image: it is an **oil painting** —
visible brushwork and palette-knife strokes, a signature at the lower left. It depicts a figure in
a dark jacket, head tilted back, the lower face bound or covered by a large dark bow/scarf.

The "garment" reading comes from the **region labels**, not the artwork: `dress`, `scarf`, `top`,
`jacket`, `tie knot`, `collar`, `black tie` — a fashion segmenter reading a painting as menswear.
**This is the third time a portfolio fixture description has turned out to be inherited detector
output** (A2's "architecture" was a sculpture; A1's plate was a composite). Treat every remaining
row's description as unverified until the image is opened.

This does not disqualify the fixture. A painting whose figure throws its head back and has its face
covered is an *excellent* R7 subject — the gesture is legible and the address is deliberately
withheld. It simply must be run as a painting, not as clothing.

**Second observation, recorded for A3:** this post carries **two coexisting region generations** —
`fseg_*` (7) and `fine_*` (9), 16 total. Unlike `695be786`, where `arch_*` *replaced* `fine_*` and
stranded two grounds, here both survive side by side. So re-dissection does not always replace.
A3 should not disturb either generation.

## Fixture set

| role | post | what it is | why chosen |
|---|---|---|---|
| **subject** | `695be8ba` | oil painting; head thrown back, face bound by dark fabric | gesture legible, **address withheld** |
| **neighbour** | `695be790` | weathered veiled funerary figure, B&W photograph; head tilted back, eyes closed, mouth parted | **same gesture-and-address structure, maximally different medium** |
| **negative** | `695be843` | dark metal structure/spire; no figure, no face, no body | palette-adjacent, **gesture relevance exactly zero** |

`image_order`: `["img-01" (subject), "img-02" (neighbour)]`, recorded explicitly. The negative is
presented **third and separately**, never interleaved, so it cannot contaminate the pairing.

## Why the neighbour is curator-selected, and why that matters

The neighbour was chosen because a stone figure and a painted figure make **the same address
gesture** — head back, eyes shut or covered, the face turned out of the viewer's reach. Nothing
about their surfaces is alike:

| | subject | neighbour |
|---|---|---|
| medium | oil paint | weathered stone, photographed |
| mean luminance | 57.0 | 86.2 |
| **mean saturation** | 0.192 (warm) | **0.0000 (pure greyscale)** |

A zero-saturation greyscale photograph and a warm-toned oil painting are about as far apart as two
images in this corpus get on exactly the axis F6 identified as dominant: *"material / colour
dominance still caps rank-1 on the single-material sculpture set."* If similarity drove selection,
this pair would not be produced.

**That is the whole point of amendment §8:** embedding similarity must not define gesture
relevance. Gesture is a relation between *bodies and their address* — where a figure directs
itself, and where it refuses to. Similarity retrieval answers a different question ("what looks
like this?") and F6 shows it mostly answers it by material and colour. Letting it nominate A3's
comparison would guarantee same-material, same-palette pairs and would systematically miss exactly
the cross-medium gesture rhyme this rehearsal exists to test.

### An honesty constraint A3 must respect

I checked whether the counterfactual could be tested empirically. It cannot:

- subject `695be8ba` — **37** region embeddings
- neighbour `695be790` — **0**
- negative `695be843` — **0**

There is nothing to run a similarity query against, so **A3 may not claim that an embedding would
have ranked the negative above the neighbour.** That claim is unverifiable with current data. A3
must reason from F6's *documented* material/colour dominance and state the counterfactual as
untested. (Also noted: raw chromaticity distance actually places the neighbour *closer* to the
subject than the negative — 0.0494 vs 0.0697 — so the naive version of the argument is wrong, and
the real divergence is medium, saturation, and texture, not hue.)

## Required manifest fields (pre-decided)

| field | value |
|---|---|
| `source_condition` | `present` |
| `image_order` | `["img-01", "img-02"]` — subject first, neighbour second, recorded explicitly |
| `reproduction_vs_depiction` | **`reproduction`** for the subject — a photographed/scanned *painting*, a category distinct from both A1's composite plate and A2/A1F's photograph-of-an-object. The neighbour is a `depiction` (photograph of a sculpture). **Record per image, not per run.** |
| provider / model | groq / `qwen/qwen3.6-27b`, `reasoning_effort: "none"` |
| `model_budget` | **2** live VLM calls (may rise to 3 only if the two-image pairing genuinely needs a third; not expected) |
| `image_call_throttle_s` | 25 (Groq 8K TPM) |
| `retry_policy` | no retries except a provider-level failure of the first call |
| `no_named_refusal_token` | `true` — amendment 1 from 002F |
| `no_production_mutation` | `true` |

**Note the manifest schema change implied:** `reproduction_vs_depiction` was a run-level field in
A2. A3 has two images of different kinds, so it must become **per-image**. Small, additive.

## Seed gesture

> **"where does this gesture's address go?"**

Asked of the subject first, then of the pair. No refusal token named in any prompt.

## Expected outcomes (all valid)

- **Candidate SPARK** — a way to express address/orientation as a relation that is not a region and
  not a similarity score. Plausible: neither `region` nor `field` obviously carries "directed away
  from the viewer".
- **Stall** — if address cannot be evidenced from a single frame without importing iconography.
  Genuinely possible, and the honest outcome if so.
- **Refusal** — if the cross-medium pairing turns out to require a cultural claim the images do not
  support. A natural, unprompted refusal is a result; it must not be re-prompted into compliance.
- **Existing construct sufficient** — `relation` grounds already reference members by id and carry
  a `relation_label`. A3 should check this seriously before proposing anything new; A2's most
  useful finding was of exactly this shape.

## Data safety checks (pre- and post-run)

1. Record pre-state for **all three** posts: counts of `text_blocks`, `grounds`, `percepts`,
   `region_annotations`, plus region id lists.
2. Read-only access only; download images to fixtures and hash them.
3. Re-verify all three post-run and diff against pre-state.
4. **Do not repair** the detached grounds found by A2S, and do not disturb the two coexisting
   region generations on `695be8ba`.
5. Freeze observations; prove replay makes 0 adapter/model/socket calls.
6. Validate manifest, trace, observations, and instrumented-score against the schemas.

## Not in scope for A3

No production entity, route, collection, or frontend surface. No Passage, Atlas, Codex, Scheduler.
No candidate graduation — SPARK only. No embedding backfill to make the counterfactual testable
(that would be a corpus mutation). No repair of detached grounds. A4–A6 not started.
