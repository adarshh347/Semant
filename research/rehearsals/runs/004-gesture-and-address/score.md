# 004 — Gesture and Address: "where does this gesture's address go?"

**Family:** R7 Gesture and Address · **Mode:** instrumented · **A3 of the R2 breadth batch**
**Outcome: COMPLETED — the curator-selected cross-medium neighbour was confirmed on gesture
grounds, and the negative was rejected in an unexpected way that is the run's most interesting
result.**

RESEARCH-ONLY. No production entity, schema, route, collection, or corpus write.

---

## Design

One thing under test: whether **address** — where a figure directs itself, and what it refuses —
is a relation that survives across media, and whether a comparison chosen by *gesture* holds up
when a model is asked to judge it against a *palette-adjacent* control.

| role | post | what it is | `reproduction_vs_depiction` |
|---|---|---|---|
| subject | `695be8ba` | oil painting; head thrown back, lower face bound in dark fabric | **reproduction** |
| neighbour | `695be790` | B&W photograph of a weathered veiled funerary figure | depiction |
| negative | `695be843` | photograph of a dark metal structure; **no figure** | depiction |

The neighbour was chosen by a curator on gesture grounds. On the colour/material axis F6 named as
dominant, it is maximally unlike the subject: **mean saturation 0.0000 (pure greyscale) against
0.192 (warm)**. The negative shares the subject's low-key darkness (87.9 % of pixels below
luminance 64, vs 65.7 %) and contains no figure at all.

## Result 1 — address is legible, and the model reads it as refusal

**Probe 1** — subject alone, seed gesture, no refusal token named (1148.3 ms, 1476 tokens, `stop`):

> The figure's gesture — the turned head, obscured face, and draped black fabric — directs
> attention inward […] It **turns away from the viewer, withholding direct engagement** […] the
> composition's deliberate cropping and the figure's averted posture — we see only what is offered,
> not what is hidden. The painting thus becomes **an act of quiet refusal**, inviting contemplation
> rather than connection.

Address here is not a direction in the picture plane. It is a *stance toward the viewer*, and the
model grounds it in specific evidence: the fabric barrier, the averted posture, the cropping.

## Result 2 — the cross-medium neighbour holds

**Probe 2** — all three images in order, each judged on its own terms, no forced choice
(1322.5 ms, 5118 tokens, `stop`):

> **IMAGE 2 makes the same kind of address as IMAGE 1.** The statue's eyes are closed and its head
> is tilted back in a pose of ecstasy or sorrow that is entirely self-contained. This gesture
> refuses engagement with an external viewer, directing the figure's experience inward.

A warm oil painting and a zero-saturation stone photograph were matched **on address**, across the
exact axis that F6 says dominates similarity retrieval. This is the run's confirmatory result: a
curator-selected comparison, made on gesture, survived independent judgement.

**It does not follow that an embedding would have failed** — see the honesty note below. What is
shown is that the gesture relation is *real and legible*, not that similarity retrieval misses it.

## Result 3 — the negative was rejected, but not for the expected reason

The negative was designed as "no figure ⇒ no address possible." The model disagreed:

> **IMAGE 3 does not make the same kind of address.** The building's facade is structured as a
> **monumental, frontal face with windows that function as eyes**. This architectural design
> creates a **direct, imposing gaze** toward the viewer, establishing a powerful and
> **confrontational address** rather than a refusal.

The right answer — *not the same address* — reached by a route the design did not anticipate. The
model did not say "there is no address here." It **found an address in a building** by reading it
anthropomorphically, and then classified it as the *opposite kind*: frontal and confrontational
versus averted and withholding.

Two consequences:

1. **Address may not require a figure.** If frontality and facing are enough, address is a property
   of *how a thing meets the viewer*, not of having a body. That is a wider and more interesting
   claim than R7 assumed, and it makes address plausibly expressible about architecture, objects,
   and ornament — not only about people.
2. **The model anthropomorphises readily and unprompted.** Nothing in the prompt suggested a face.
   This is a direct warning for **A6 (R12 Adversarial Projection)**, whose expected outcome is a
   *refusal* to accept a seductive false analogy. A model that spontaneously finds eyes in windows
   will find motif kinship in unrelated ornament. A6 must be designed against this tendency.

## Honesty note: the embedding counterfactual was NOT tested

The subject has **37** region embeddings; the neighbour and the negative have **0**. There is
nothing to run a similarity query against, so this run **does not** and **cannot** claim that
embedding retrieval would have preferred the negative. Two further cautions recorded in advance:

- Raw chromaticity distance actually places the **neighbour closer** to the subject (0.0494) than
  the negative (0.0697). The naive form of the argument is simply wrong.
- What separates them is medium, saturation, and texture — not hue.

The claim this run supports is narrow and worth stating exactly: **gesture relevance and surface
similarity are different relations, and the gesture relation is legible to a model that is asked
about it directly.** Whether retrieval would surface it is untested.

## Evaluation against the permitted outcomes

- **(a) SPARK** — yes, one: address as a viewer-facing stance that is neither a region nor a
  similarity score, and that may not require a figure. See `sparks.md`.
- **(b) existing construct sufficient** — **partly, and this must be checked before anything new.**
  A `relation` ground already references members by id and carries a `relation_label`. Within one
  image that may be enough. What it cannot express is a relation **between two posts** — every
  Ground lives on a single post. A3's whole finding is cross-image.
- **(c) stall** — no. Address was evidenced from single frames without importing iconography.
- **(d) refusal** — none occurred, and none was prompted for.

## Provenance

| | |
|---|---|
| provider / model | groq / `qwen/qwen3.6-27b`, `reasoning_effort: "none"` |
| **live VLM calls** | **2** (budget 2) — probe 1 adopted from an aborted attempt, probe 2 fresh |
| rejected requests | **3× HTTP 413**, all pre-execution, **0 tokens consumed** (see `critique.md`) |
| latency | 1148.3 ms, 1322.5 ms |
| tokens | 1476 + 5118 |
| finish_reason | `stop` both · no `<think>` leakage · raw text frozen, no parsing attempted |
| replay | **0 adapter calls, 0 sockets, key absent**; 3 observations, 4 events |
| production mutation | **none** — three posts read read-only, never written |
