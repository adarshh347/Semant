# 003 — Sensory Disagreement: "is this one surface or two?"

**Family:** R5 Sensory Disagreement · **Mode:** instrumented · **Source:** depiction (single photograph)
**Outcome: NOT a stall. A2 produced a candidate SPARK and hard evidence that a resensing /
uncertainty surface is needed — because the disagreement has already destroyed curator evidence in
production.**

RESEARCH-ONLY. No production entity, schema, route, collection, or corpus write.

---

## First: the portfolio's description of this fixture is wrong, and the error is the finding

R0's A2 row reads: *"architecture `695be786` (wall/floor, single image) — colour continuity (same
stone) vs. object boundary (wall≠floor)."*

**The image is not architecture.** It is a close-up of a carved stone figure — headdress, face,
shoulder, torso, arm, with relief carving behind. There is no wall in it and no floor in it.

The portfolio inherited the **detector's region labels** as ground truth. All 7 persisted regions
are labelled `wall` (arch_0/1/2/3) or `floor` (arch_4/5). That mislabelling is not an obstacle to
running A2 — **it is the sensory disagreement**, already sitting in production data.

## The answer to the gesture: ONE surface

Three independent routes agree.

**1. Chromaticity (measured, no model).** Brightness-normalised, near-black pixels excluded:

| comparison | chromaticity distance |
|---|---|
| `wall` arch_0 → figure headdress | **0.0061** |
| `floor` arch_4 → figure shoulder | **0.0067** |
| *within-figure* (torso vs headdress) | 0.0102 |
| `wall` arch_0 → `wall` arch_2 (**same label**) | **0.0124** |

The distances **across** the detector's label boundaries are *smaller* than the distance between
two regions it labels the **same**, and smaller than ordinary within-object variation. By material
evidence these label boundaries are not material boundaries. The raw RGB gaps (euclid 43–93) are
almost pure luminance — the channels shift in proportion, i.e. one stone under varying light.

**2. VLM probe 1** (1625.0 ms, 1972 tokens, `stop`) — the seed gesture, open, no refusal token
offered:

> This is **one continuous surface** — the sculpted body of a figure […] the seamless transition
> of texture, lighting, and form […] indicating they are carved from a single block […] not two
> separate objects but one unified sculpture.

**3. VLM probe 2** (3928.3 ms, 2057 tokens, `stop`) — asked what is physically in the upper-left
quadrant, the exact extent the production DB calls `wall`:

> a portion of a **sculpture** […] dark, weathered stone, such as basalt or granite […] a carved
> human figure, specifically showing the **head, shoulder, and upper arm** […] The single most
> prominent thing in this quadrant is the **head** of the sculpted figure: `[0.08, 0.03, 0.54, 0.26]`

**70.1 %** of that head box lies inside the region production labels `wall`.

## The real damage: two curator percepts, one silently unevidenced

Reading the post's own grounds is what turns this from a labelling curiosity into a finding.

| ground | type | points at | state |
|---|---|---|---|
| `gnd_mrqp8tls_0` | `region` | `fine_3` ("hair") | **DETACHED** |
| `gnd_mrqp8tlt_1` | `region` | `fine_0` ("face") | **DETACHED** |
| `gnd_mrqpa3av_2` | `field` | own strokes | survives |
| `gnd_mrq9hljq_0` | `frame` | whole | survives |
| `gnd_mrq9hnef_1` | `frame` | whole + evidence_ids | survives |

The post's current regions are `arch_0…arch_5` + one refine. **`fine_0` and `fine_3` no longer
exist.** A dissect replaced the `fine_*` region set with an architecture-model `arch_*` set.

Consequence:

- Percept **`pctx_mrqp950d_0` — "the upper head" — has 2/2 grounds detached.** A curator noticed
  something, pointed at the face and the hair, and that percept is now floating with no evidence
  it can resolve. What now covers that area asserts `wall`.
- Percept `pctx_mrqpamw0_1` ("braided aspect… indian rock cut architecture") has **0/1** detached —
  it used a **`field`** ground carrying its own strokes, so it survived.

This is a natural experiment already run in production: **reference-based grounds (the region
adapter) were destroyed by re-dissection; geometry-bearing grounds (`field`, `frame`) were not.**
`grounds.js` documents detachment as graceful degradation — and it is graceful, in that nothing
crashes. But nothing *announced* it either.

**The disagreement is not only between two machine channels. It is between the curator's past
attention and the system's current perception — and the system won.**

## Why "disagreement" is the wrong frame here

R5 presumes two competent channels in tension. That is not what this is.

The semantic channel is an architecture/scene segmenter (ADE20K-style: `wall`, `floor`) applied to
a sculpture close-up — a domain for which it has **no correct class**. So it emits its nearest
available labels. All 7 regions collapse into exactly 2 architectural classes on an image
containing neither.

That is **out-of-domain label collapse**, not disagreement. The distinction matters for design: a
UI that asked the curator "wall or figure — which do you trust?" would present a false choice
between a competent reading and a confident non-answer. The evidence needed to tell these apart is
cheap and already present — label diversity collapsing to a handful of classes from the wrong
domain, plus label boundaries that don't coincide with material boundaries.

## Undated and unattributable

There is **1** `vision_runs` document in the entire database, and **0** for this post. The
telemetry built precisely to make an operation like this visible did not exist when this dissect
ran. So *when* the curator's evidence was destroyed, and by which operation, is not recoverable
from the data. Recorded as an observation; no circulation work was done here.

## Evaluation against the four permitted outcomes

- **(a) candidate SPARK** — yes, two. See `sparks.md`. Research-only, not graduated.
- **(b) uncertainty / active-resensing surface needed later** — yes, and now with a concrete
  motivating case rather than a hypothetical: a percept whose evidence silently vanished.
- **(c) existing construct sufficient** — **partly, and this is the most useful design signal.**
  The `field` ground already solves the durability half: it survived the re-dissect that destroyed
  its region-adapter siblings. No new construct is needed to *hold* a noticing across re-dissection.
  What is missing is **notification**, not representation.
- **(d) stall / refusal** — no. The evidence was sufficient and convergent.

## Provenance

| | |
|---|---|
| provider / model | groq / `qwen/qwen3.6-27b`, `reasoning_effort: "none"` |
| live calls | **2** (budget 2), 25 s apart, no retries, no provider failure |
| latency | 1625.0 ms, 3928.3 ms |
| tokens | 1972 + 2057 |
| finish_reason | `stop`, both · no `<think>` leakage · no JSON parsing attempted (raw text frozen verbatim) |
| replay | **0 adapter calls, 0 sockets, key absent** |
| production mutation | **none** — post read read-only, never written |
