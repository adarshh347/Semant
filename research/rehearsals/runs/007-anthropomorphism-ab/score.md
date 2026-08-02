# 007 — Anthropomorphism A/B: does the face come from the image or the question?

**Type:** instrumented A/B replication · **Resolves:** spark-06
**Outcome: THE QUESTION FRAME DRIVES IT. Decisive, and on positive evidence in both arms.**

RESEARCH-ONLY. No production entity, schema, route, collection, or corpus write.

---

## What was being settled

Run 004 (A3) reported that this exact image — a dark metal structure with **no figure in it** —
was described as having *"windows that function as eyes… a direct, imposing gaze… confrontational
address."* A3 called the behaviour **spontaneous**.

Run 005 (A4) saw no face on an aniconic wall under structure-framed prompts and narrowed the claim
to **question-conditional**. The A6 decision gate then disputed that narrowing, correctly: **A4
moved two variables at once** — prompt frame *and* aperture geometry. A3's structure carries
**paired lateral apertures**; A4's wall has one central opening and is **eyeless by construction**,
so it might have produced no face under either prompt. spark-06 was left **UNRESOLVED**, and A4 was
ruled to give A6 **no protection**.

This run isolates the single variable: **same image, same 768 px probe variant (identical sha256 in
both arms), same model, same `reasoning_effort`, same `max_tokens`, same single-image call shape,
both arms stateless.** Only the question differs. Neither prompt contains *face*, *eye*, *gaze*,
*body*, *head*, or *watching*. The word **address** appears in arm A alone — that is the variable.

## Result: `a_face_b_none`

**Arm A — address-framed** (1681.8 ms, 2018 tokens, `stop`):

> the imposing, vertically oriented structure with its **glowing eyes** and layered, almost
> **facial** architecture […] The glowing **"eyes"** and central spire act as focal points […] the
> structure's symmetrical, **face-like frontality** […]

**Arm B — structure-framed** (1516.0 ms, 2004 tokens, `stop`):

> strong vertical symmetry and hierarchical layering, with the central spire acting as the dominant
> axis […] the mirrored placement of **light fixtures** on either side of the central tower, the
> concentric rings of architectural detail […] the glowing **accents** serve as visual anchors […]

*(Fable-pass.)* **The same physical features are named differently by the two frames.** The lamps
flanking the spire are *"glowing eyes"* under the address frame and *"light fixtures"* — *"mirrored
placement"*, *"visual anchors"* — under the structure frame. Nothing about the pixels changed. The
face is not in the photograph; it is in the question.

This is the pre-registered `a_face_b_none` cell: **prompt frame drives it.**

## spark-06 RESOLVES — and on better evidence than A4 offered

A4's narrowing rested on a **negative** result on a **different** image whose geometry may have
lacked the triggering feature. This run rests on:

- a **positive** result in arm A — the face reproduced, and
- a **positive** non-face reading in arm B — the same lamps described as fixtures,
- on the **one image known to have produced the behaviour**.

**Corrected claim: anthropomorphism here is question-conditional. Address-framing is sufficient to
elicit it; the image alone is not.**

### A secondary result worth recording

Arm A reproduced A3's face reading **at 768 px in a single-image call**. A3's original occurred at
**256 px inside a three-image comparison**. So A3's finding was **not** an artifact of downscale
degradation or of comparison context. The replication succeeded on its own terms.

## What this means for A6

The gate ruled that A4 gave A6 no protection. That ruling was right, and is now **superseded by
evidence rather than by argument**: this run *does* give A6 protection, of a specific and limited
kind.

- **A6 must not use address-framing, or any of its vocabulary,** in either stage. On the corpus's
  most pareidolia-prone stimulus, a structure-framed prompt did not elicit a face.
- **The protection does not extend to kinship language.** This run tested *address*, not *motif
  similarity*. A6 asks whether two ornaments are "the same motif" — a relational question that this
  A/B says nothing about. Do not read this result as clearance for A6's actual question.
- The gate's `DECLINED-ON-INSCRIPTION` guard and the two-stage delta design stand unaffected.

## Honest limits

- **n = 1 image, 1 model, 2 calls.** One A/B on one stimulus.
- **Resolution and call-shape differ from A3 in both arms** (768 px single-image vs 256 px
  three-image). This was recorded in the manifest in advance. It does not weaken the finding —
  because the finding rests on the *contrast between arms*, which holds resolution constant — but
  it does mean the two runs are not strictly identical conditions.
- **Order was not counterbalanced.** Arm A ran first. Both calls are stateless and independent, so
  there is no mechanism for carry-over, but a counterbalanced replication would be stronger.
- **"Address" is not a neutral word.** It arguably *names* a viewer-relation, so arm A may be less
  "a frame" than "a leading question". That is precisely what makes the result useful — it tells
  A6 which words to avoid — but it means the finding is about this vocabulary, not about framing in
  general.

## External claims

*(First voluntary adopter of the convention proposed in `Decisions/HW-C5-external-claim-convention.md`.)*

| verbatim claim | arm | frame status | speaker-flagged |
|---|---|---|---|
| "glowing eyes" / "face-like frontality" | A | **frame-silent** — real illuminated fixtures exist; "eyes" is an interpretation the pixels neither carry nor contradict | no |
| "an unseen sky or cosmos" | A | frame-silent — no sky is visible; the background is dark | no |
| "technological grandeur", "power, precision" | B | frame-silent — attributed intent, not visible content | no |

No claim in either arm was **frame-contradicted** (unlike A5's fabricated inscription), and no
title, artist, date or institution was volunteered.

## Provenance

| | |
|---|---|
| provider / model | groq / `qwen/qwen3.6-27b`, `reasoning_effort: "none"` |
| live VLM calls | **2** (budget 2), 33 s apart, no retries, no provider failures |
| stimulus | identical `probe-768.jpg` in both arms, sha256 `d366b2e1ae779807…` |
| latency | 1681.8 ms, 1516.0 ms |
| tokens | 2018 + 2004 |
| finish_reason | `stop` both · no `<think>` leakage · raw text frozen, no parsing attempted |
| replay | **0 adapter calls, 0 sockets, key absent**; 3 observations, 4 events |
| production mutation | **none** — post `695be843a9ea58f1b6aef5ff` read read-only, never written |
