# 002F — Single-object followup: does A1's stall generalise?

**Followup control for run `002-figure-ground-reversal`. Not A2.**
**Outcome: A1's stall is largely COMPOSITE-PLATE-SPECIFIC — and one of A1's two probes is now
discredited as an instrument.**

RESEARCH-ONLY. No production entity, schema, route, collection, or corpus write.

---

## Design

One variable changed: the **subject**. Same model (`qwen/qwen3.6-27b`), same
`reasoning_effort: "none"`, same two-probe structure, same wording pattern, and deliberately the
same offered `NO_GROUND` escape token — so any difference is attributable to the image, not the
instrument.

**Subject:** Michelangelo's Pietà photographed **in situ** in its chapel (post
`695be77ea9ea58f1b6aef5eb`) — a single photograph with real architectural depth, as against A1's
composite plate of cut-out heads on keyed black.

## Result 1 — the negative space is full of signal (measured, no model)

| region | mean | std | **% exactly (0,0,0)** |
|---|---|---|---|
| **A1** interval (composite plate) | 11.87 | 33.18 | **59.5 %** |
| 002F above figure / below cross | 99.05 | 55.35 | **0.0 %** |
| 002F beside figure, left | 34.39 | 17.63 | **0.0 %** |
| 002F beside figure, right | 29.95 | 13.41 | **0.0 %** |
| 002F niche wall upper-left | 77.64 | 49.03 | **0.0 %** |

**Zero pure-black pixels anywhere.** The "empty" space in a real photograph carries texture,
gradient, and light throughout. A1's void was an artifact of compositing, not a property of
negative space.

## Result 2 — the model finds groundable content there

**Probe 1** (1052.8 ms, 1947 tokens, `stop`):

> a textured, mottled wall surface composed of layered stone or marble panels in deep browns,
> grays, and muted blues. It appears aged and weathered, with subtle variations in tone that
> suggest depth and historical patina […] a somber, almost cavernous void that frames the
> sculpture without competing for attention.

Compare A1's probe 1: *"no objects, textures, or gradients… purely negative space."* Same
instrument, opposite answer — and this answer matches the measurement. The space beside the figure
is **pointable**: it is wall, panel, patina, shadow.

## Result 3 — the grounding probe contradicted itself, and is now discredited

**Probe 2** (858.4 ms, 1934 tokens, `stop`), verbatim:

> **NO_GROUND**
> The space immediately beside and above the sculpted figure group is occupied by a large cross
> and an ornate marble wall, **which are depicted content.**

The model emitted the refusal token **and then stated the opposite in the same breath.** There is
depicted content — it names it — yet it still reached for `NO_GROUND`.

This confirms, empirically, the weakness flagged in `002/critique.md` §1: **offering `NO_GROUND` as
an explicit reply option makes it an attractor.** The token gets emitted regardless of the model's
own findings, so `NO_GROUND` from this probe design carries almost no evidential weight.

**Does this overturn A1?** No — and this was anticipated rather than rescued after the fact. A1's
critique explicitly recorded that probe 2 "corroborates; it does not establish," and that the
load-bearing evidence was the **pixel measurement** (59.5 % literal black) plus probe 1's
*unprompted* "no objects, textures, or gradients." Both stand untouched. A1's stall holds; A1's
probe-2 *instrument* does not, and must not be reused in A2–A6 in its current form.

## Verdict on the three offered options

**A1's stall is A1-specific — composite-plate-specific — in its main claim.** On a proper
photograph, negative space is depicted, describable, and groundable. There is no stall here.

Component by component:

| A1 claim | verdict under 002F |
|---|---|
| the void carries no evidence | **A1-specific.** 0 % pure black here vs 59.5 % there. |
| **category gap** — the interval's function belongs to the plate-as-artifact, not the depiction | **A1-specific.** It arose *because* the subject was a made comparative plate. No equivalent here: the space beside the Pietà is in the world the photograph depicts. `spark-01` therefore narrows to composite/reproduction sources — which is still a real and common corpus problem, but not the general claim it looked like. |
| **proposal gap** — every automated path is object-shaped, so reversal is never offered by the machine | **PARTIALLY CORRECTED, and this is the substantive finding.** This post's pre-existing regions are `arch_0 "wall"`, `seg_0 "person"`, `arch_1 "floor"`. Detection **did** propose non-figure regions. Proposal machinery is not purely object-shaped: on a real photograph it proposes surfaces and architectural context. |

## The corrected proposal-gap claim

`spark-02` overstated. The accurate, narrower version:

> Detection proposes **things** — figures, and also surfaces like wall and floor. It does not
> propose **intervals**. `arch_0 "wall"` is a non-figure region but it is still an object-like
> extent, not the *relation* or *gap* between two things. No region anywhere in either run points
> at a space-between.

So a curator asking "what is the space beside the figure doing?" on a real photograph **can** be
grounded today — via the existing `wall` region, or a freehand `field`. The reversal is reachable.
What remains unproposed is the interval *as an interval*, and 002F does not settle whether that
matters, because here the space is occupiable by a surface region and nothing was lost.

## Provenance

| | |
|---|---|
| model | `qwen/qwen3.6-27b` (Groq), `reasoning_effort: "none"` |
| live calls | **2** (budget 2), 25 s apart, no retries, no provider failures |
| latency | 1052.8 ms, 858.4 ms |
| tokens | 1947 + 1934 |
| `<think>` leakage | none |
| replay | **0 adapter calls, 0 sockets, key absent** |
| production mutation | **none** — post read read-only, never written |

## Consequence for A2

1. **Retire the probe-2 design.** Never offer `NO_GROUND` (or any refusal token) as a named
   option. Ask for the bounding box and let a refusal be *unprompted*, the way A1's probe 1
   produced its finding.
2. **Record whether a fixture is a reproduction or a depiction** in the manifest. It changed the
   result completely here, and it is currently invisible to the schema.
3. A2 (R5 Sensory Disagreement, architecture `695be786`) can otherwise **proceed unchanged**.
