# 002 — Figure/Ground Reversal: the space between the Gupta and Pala faces

**Family:** R4 Figure/Ground Reversal · **Mode:** instrumented · **Source condition:** present
**Outcome: STALL — a grounded refusal.** The portfolio predicted this rehearsal "may stall if no
evidence supports the void." It did, and the stall is the result.

RESEARCH-ONLY. No production entity, schema, route, collection, or corpus write.

---

## The gesture

> *what is the space between the Gupta and Pala faces doing?*

The gesture demotes the five heads — the entire existing annotation layer — and promotes the
interval between two of them. Post `695be6c9a9ea58f1b6aef5e0` carries **10 region_annotations,
all objects** (`figure` / `body-part`), and **3 grounds, all `ground_type: "region"`**. Nothing in
the existing layer points at an interval. That is the pressure.

## Where the interval actually is

The two cited faces bound a determinate strip:

| | normalized x | pixels (image 680×286) |
|---|---|---|
| Gupta face (`fine_2`) | 0.27 – **0.43** | 184 – 292 |
| **the interval** | **0.43 – 0.46** | **292 – 312** (20 px wide) |
| Pala face (`fine_4`) | **0.46** – 0.52 | 313 – 354 |

The interval is *determinate*. It is bounded on both sides by evidence. This is what makes A1 a
real test rather than a vague one: the void has coordinates.

## What the interval is made of (measured, no model)

| region (y 0–0.6) | mean | std | % exactly (0,0,0) |
|---|---|---|---|
| **the interval** x .43–.46 | **11.87** | 33.18 | **59.5 %** |
| gap Solanki\|Gupta x .24–.27 | 35.47 | 50.53 | — |
| gap Pala\|Amaravati x .62–.65 | 28.73 | 54.39 | — |

Only **12.9 %** of interval pixels exceed value 16, and those sit at the extreme edges where the
Pala crown bleeds in. There is no gradient, no cast shadow, no floor, no wall, no atmosphere.

And the two heads were never in the same room. Per-channel means over the face areas:

- **Gupta** R 129.7 / G 91.3 / B 64.2 — warm terracotta, R−B spread **65.5**
- **Pala** R 69.1 / G 64.2 / B 58.7 — near-neutral grey, R−B spread **10.4**

Incompatible colour temperature and incompatible lighting direction. Looking at the plate
confirms what the numbers say: this is a **labelled comparative plate** — five heads
photographed separately, cut out, and composited onto flat black, each with a white caption
("Solanki", "Gupta", "Pala", "Amaravati", "Gandhara").

**The interval is not depicted space. It is the keyed-out background of a made plate.**

## What the model said (2 bounded calls, `qwen/qwen3.6-27b`, frozen)

**Probe 1** — the seed gesture, open (712 ms, 902 tokens, `finish_reason: stop`):

> a dark, empty void — a stark black background that isolates each sculpture. It contains no
> objects, textures, or gradients; it is purely negative space. This emptiness serves to visually
> separate the two distinct artistic styles […] draws the viewer's eye directly to the contrasting
> features of the adjacent heads.

The model did **not** hallucinate depicted space. It independently reached the measurement's
conclusion ("no objects, textures, or gradients") and then did something more interesting: it
assigned the interval a **function** — *separate*, *emphasise*, *draw the eye*. Every one of those
verbs is about the plate's rhetoric, not about anything in the world the sculptures came from.

**Probe 2** — the grounding demand (2090 ms, 903 tokens, `finish_reason: stop`):

> **NO_GROUND**
> The narrow vertical strip between the Gupta head and the Pala head contains only the black
> background of the image, with no depicted content.

Asked to point at it, the model refused — correctly, and in the exact form the probe offered.

## Convergence

Three independent routes agree, which is why this stall is trustworthy rather than merely
inconclusive:

1. **Pixel measurement** — 59.5 % literal black, no signal.
2. **The VLM, open** — "purely negative space", but functionally active.
3. **The VLM, forced to ground** — `NO_GROUND`.

## Why it stalls

The stall is *not* a representation gap. I checked, and my first assumption was wrong:
`GROUND_TYPES` includes `field`, `boundary`, and `frame`, and `DifferentialWorkspace.jsx:298–326`
constructs all of them from freehand curator geometry. **A curator can already draw a `field` over
this interval today.** The ontology is not the blocker.

The stall has two other sources, and they are sharper:

**1. Nothing proposes it.** Every automated path produces *regions*, and every region is an
object — the detector proposes figures, `groundFromRegion` requires a `region_id`, and the VLM
returns `NO_GROUND`. Figure/ground reversal is available to the hand but not to the machine. The
interval can only ever enter the system because a human decided to draw on emptiness.

**2. A drawn ground would still be the wrong kind of claim.** A `field` over x .43–.46 asserts
something about the *depicted image plane*. But measurement says there is nothing there to be
about. The true answer to "what is this space doing?" is **separating specimens for typological
comparison** — a property of the plate *as a made artifact*, not of any pictured thing. Every
Ground type is a pointer into the depicted surface. `frame` (`whole: true`) comes closest by
addressing the image as a whole, but it cannot carry "this gap is the comparative apparatus."

So the honest terminal state: **the interval is describable, functionally real, and ungroundable
in the current system** — because what it is doing belongs to the plate, and the plate is not
something Grounds can talk about.

## What this rehearsal refused to do

- It did not invent a percept about "negative space as breath / silence / interval" — the kind of
  sentence this image invites and the evidence cannot carry.
- It did not read the black as depicted darkness, void, or ground in any pictorial sense.
- It did not compare Gupta and Pala facial geometry (the existing percept's territory) — the
  gesture was about the space, and drifting to the faces would have been the figure re-capturing
  attention, i.e. failing the rehearsal.
- It did not graduate anything. See `sparks.md` — SPARK only.

## Provenance

| | |
|---|---|
| model | `qwen/qwen3.6-27b` (Groq), `reasoning_effort: "none"` |
| live calls | **2** (budget 2) · 25 s apart · no retries |
| latency | 712.1 ms, 2090.5 ms |
| tokens | 902 + 903 |
| `<think>` leakage | none in either |
| replay | **0 adapter calls, 0 sockets, key absent** |
| production mutation | **none** — the post was read, never written |
