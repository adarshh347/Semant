# R2 — Candidate and spark register

**RESEARCH-ONLY. Every entry is a SPARK.** Nothing here is a candidate, a decision, an approved
design, or a durable object. No entry may be built from without an explicit build gate.

**Graduation bar (R3, not attempted):** ≥3 fixtures, plus a transfer test and a negative case.
Nothing below meets it. Speculative locations are marked **[SPEC]** and are guesses, not proposals.

| id | one line | from | strength |
|---|---|---|---|
| spark-01 | artifact-level claims have nowhere to live | A1 | narrowed by A1F |
| spark-02 | detection proposes things, never intervals | A1, corrected by A1F | moderate |
| spark-03 | **evidence loss should be announced, not merely survived** | A2, A2S | **strongest** |
| spark-04 | out-of-domain collapse ≠ channel disagreement | A2 | moderate |
| spark-05 | address as a viewer-facing stance, maybe without a figure | A3 | new, n=1 |
| spark-06 | spontaneous anthropomorphism is a hazard for A6 | A3 | method warning |

---

## spark-03 — evidence loss should be announced, not merely survived

**Status: SPARK. The strongest entry in the register.**

**Evidence.** `003-sensory-disagreement/score.md`; `R2/A2S-detached-ground-sweep.md`;
`R2/evidence/A2S-detached-ground-sweep.json`; `grounds.js :: resolveGround`.

Percept `pctx_mrqp950d_0` — a curator's own words, *"the upper head"* — is **fully unevidenced**:
both its grounds cite regions `fine_0`/`fine_3` destroyed by a re-dissect. Corpus-wide: **4 of 11**
reference-based grounds detached, **0 of 15** geometry-bearing ones. Confirmed on a second,
independent post (`695be794`, 2 detached, uncited). Nothing announced any of it.

**Why it is not production-ready.**
- The corpus is tiny: 11 annotated posts, 7 percepts, 11 reference grounds. 36.4 % is not a rate.
- **The repair is a real design fork and the program has deliberately not chosen.** Tombstoning old
  regions so grounds resolve to *something*, versus notifying and letting the curator re-point, are
  different theories of what evidence is. Auto-repair by IoU would manufacture provenance.
- Detachment is *already* modelled and rendered. The missing thing is **notification**, which is a
  behaviour, not an entity — and could be built badly as a new schema when it needs none.

**What would strengthen or kill it.** Strengthen: a denser corpus showing detachment rising with
percept density; or evidence that curators do not notice unaided. Kill: showing detachment is rare
once dissection stabilises, or that curators reliably catch it.

**[SPEC] Possible location.** A re-dissect already knows the outgoing region ids and could count
grounds referencing them — no new storage implied. Surfacing **[SPEC]** could sit near existing
percept/ground inspectors. `VisionRun` already has an honest home for a per-operation count.

**Corroborating finding from the frontend scout (HW-S1), which sharpens this considerably:**
`recall.js` builds its playback from a raw ground lookup rather than `resolveGround`, so a detached
ground reportedly becomes a full recall step that draws nothing — the chip plays a confident
caption over empty evidence, and `RefPicker` offers it as "2 grounds". If that holds, the harm is
worse than silence: it is **confident display of absent evidence**. Not yet independently verified
by a rehearsal; flagged as the highest-value thing to confirm.

---

## spark-01 — artifact-level claims have nowhere to live

**Status: SPARK, narrowed.**

**Evidence.** `002-figure-ground-reversal/score.md` + `sparks.md`;
`002F-single-object-followup/score.md`.

The interval between two heads on a comparative plate is determinate (x 0.43–0.46) yet ungroundable:
59.5 % of its pixels are exactly `(0,0,0)` because the plate is a composite with keyed-out black.
What the interval *does* — separating specimens for typological comparison — is a property of the
**plate as a made artifact**, and every Ground type points into the **depicted** surface.

**Why it is not production-ready.** A1F narrowed it hard: on a real photograph the same space is
0.0 % pure black and fully groundable. So this is a claim about **reproductions** (plates, scans,
collages), not about negative space generally. It rests on **one** plate.

**What would strengthen or kill it.** Strengthen: two or three more composite plates showing the
same ungroundable-but-meaningful interval. Kill: showing curators never want to say anything at the
artifact level, or that `frame` already carries such claims adequately.

**[SPEC] Possible location.** Possibly nothing new at all — a `frame` ground plus an honest note may
suffice. Recording *what kind of picture a post holds* (reproduction vs depiction) is the smaller,
better-evidenced move; it has already changed three rehearsal outcomes.

---

## spark-02 — detection proposes things, never intervals

**Status: SPARK, corrected once.**

**Evidence.** A1 `sparks.md` (original, overstated); `002F-single-object-followup/score.md` (the
correction); A2 region labels.

A1 claimed detection is object-shaped end to end. **False** — the Pietà post carries `arch_0
"wall"` and `arch_1 "floor"`, which are non-figure regions. The surviving, narrower claim:
detection proposes **things** (figures *and* surfaces) but never **intervals**. No region in any run
so far points at a space-between.

**Why it is not production-ready.** It is an observation about available detectors, not about
Semant. Nothing follows about what Semant should build. A curator can already draw a `field` over
any interval.

**What would strengthen or kill it.** Kill: any detector returning a genuine interval or
between-ness proposal. Strengthen: showing curators repeatedly hand-draw intervals that no
proposal ever offers.

---

## spark-04 — out-of-domain collapse is not channel disagreement

**Status: SPARK.**

**Evidence.** A2 `score.md`; the post's 7 regions all labelled `wall`/`floor` on a sculpture;
chromaticity across label boundaries (0.0061–0.0067) *lower* than within one label (0.0124).

An ADE20K-style scene segmenter has no sculpture class, so it emits its nearest architectural
labels with no signal that it is out of domain. That is not two competent channels in tension.

**Why it is not production-ready.** One fixture. And the design consequence is a *caution*, not a
feature: an uncertainty UI offering "wall or figure — which do you trust?" would present a false
choice between a competent reading and a confident non-answer.

**What would strengthen or kill it.** Strengthen: the same collapse signature (label diversity
collapsing to a handful of wrong-domain classes) across several out-of-domain posts. Kill: an
in-domain fixture showing the same signature, which would make it useless as a discriminator.

**[SPEC] Possible location.** `VisionRun` already records `capability` and `actual_source`; an
out-of-domain flag would have an honest home there. **No threshold or auto-suppression is
proposed** — suppressing labels on a bad signal is worse than showing them.

---

## spark-05 — address as a viewer-facing stance, possibly without a figure

**Status: SPARK, new, n=1.**

**Evidence.** `004-gesture-and-address/score.md` + `sparks.md`.

Asked where a gesture's address goes, the model answered with a stance toward the viewer, not a
direction in the plane: *"turns away from the viewer, withholding direct engagement… an act of
quiet refusal."* A curator-selected cross-medium neighbour (saturation 0.0000 vs 0.192) was
independently confirmed to make *the same kind of address*. Given a building with no figure, the
model found *"windows that function as eyes… a direct, imposing gaze… confrontational address."*

**Why it is not production-ready.** One subject, one neighbour, one negative, one model. The
comparison was judged at 256 px, where the model **mis-described the subject** (head "downward"
when it is thrown back; "lace" when it is a heavy bow). And the seed gesture presupposes an address
exists.

**What would strengthen or kill it.** **First test whether `relation` already suffices** — it
references members by id and carries a `relation_label`. The one thing it demonstrably cannot do is
reach **across posts**, since every Ground lives on one post, and A3's finding is cross-image. Kill:
showing address is only ever within-image, or that it collapses into existing labels.

**[SPEC] Possible location.** Deliberately not proposed. The obvious thought — a cross-post relation
entity — is exactly what one pair of images does not justify.

---

## spark-06 — spontaneous anthropomorphism is a hazard for A6

**Status: SPARK / method warning. Not a product claim.**

**Evidence.** `004-gesture-and-address/score.md` — the model supplied a face, eyes, and a gaze for a
photograph of a metal structure, entirely unprompted.

**Why it matters now.** A6 (R12 Adversarial Projection) *expects a refusal* when offered a seductive
false analogy between culturally unrelated motifs. A model that anthropomorphises architecture
unprompted will very likely accept an offered analogy.

**Consequence for A6's design:** the false analogy **must not be stated in the prompt**, or the
refusal being measured is a refusal of a suggestion rather than a judgement about the images. This
compounds the existing amendment against naming refusal tokens.

**What would strengthen or kill it.** A6 itself, designed as above.

---

## Withheld across the program

Recorded so the temptations are visible rather than quietly resisted:

- "Negative space as breath / silence / caesura" (A1) — the image invites it; 59.5 % pure black on a
  composited background does not support it.
- "The stone remembers being one block; the labels cut it up" (A2) — a claim about carving practice
  with no evidence about carving.
- "The painting and the statue are both about grief" (A3) — both probes gesture at mourning; neither
  image carries evidence of what it mourns, and the subject has no catalogue data at all.
- Any claim that embedding retrieval would have missed A3's pair — **untestable**, the neighbour and
  negative have zero embeddings.
- Any claim about which detector produced `arch_*`, or when — 1 `vision_runs` doc exists corpus-wide.
