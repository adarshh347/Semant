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
| spark-06 | anthropomorphism is **question-conditional** (address vocabulary) | A3, A4, **resolved by 007 A/B** | **RESOLVED** |
| spark-07 | a claim can be its own counterexample — **within one response** | A4, **strengthened by A5** | moderate |
| spark-08 | **the evidence base grows silently to meet the claim** | A5, **corroborated by 008** | n=1, high value |
| spark-09 | **relational vocabulary is an attractor — the noun is the variable** | 008 (sibling to spark-06) | new, n=1 pair |

---

## spark-09 — relational vocabulary is an attractor; the noun is the variable

**From:** `runs/008-kinship-pull-ab/` (cell 1). **Strength:** SPARK at n=1 pair, 1 model, 3 calls.

On one image pair, held constant in bytes, order and co-presence, asking what **motif** each carries
elicited a shared-motif assertion (`KIN-HEDGED`); asking how each is **put together** elicited shared
properties **plus an explicit denial of sameness** (`KIN-SPECIFIC-ONLY`); asking to compare nothing
elicited no cross-image claim at all (`KIN-ABSENT`). Since arms A and C differ in exactly one respect
— the noun — the noun is the only surviving explanation. **The kinship is in the question.**

Sibling to spark-06, which resolved the same shape for *address* vocabulary. **Two relational
vocabularies now show the effect**; that is a pattern to name, not a disposition to assert.

**What would strengthen it:** the fourth arm (*"say what motif each image carries"*, no relational
clause) separates the **noun** from the **identity presupposition** — one call, now the highest-value
single call the program has. Then a second pair; then other vocabularies (*influence*, *lineage*,
*belongs to the same tradition*).

**What would kill it:** arm A's hedge reproducing under arm C's wording on a different pair — that
would make it a register effect (abstraction, not kinship). **Nearest existing construct: none, and
[SPEC] none is proposed** — this is a fact about prompting a VLM, not about Semant's ontology.

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

## spark-07 — a claim can be general and its own counterexample at once

**Status: SPARK, new, n=1.**

**Evidence.** `005-surface-becoming-structure/score.md` + `sparks.md`.

Asked in the abstract, the model answered *"structure organises, pattern merely fills — the
hierarchy is clear."* Asked minutes later to point at one line, it named a division made by pattern
alone and said the two *"disagree"* there. Measurement confirms the location it chose is the single
largest pattern-fineness change in the image (a **149 % edge-density jump at y ≈ 0.765**).

**Enablement claim.** A percept stated generally and a percept stated locally can contradict each
other while both are sincerely held and separately defensible. Semant records percepts as
independent statements with **no notion of scope**: nothing distinguishes a claim about the whole
composition from a claim about one line in it, and nothing would ever bring two such claims into
contact. Note which is better evidenced — the *local* one — and which is more confident — the
*general* one.

**Why it is not production-ready.** One image, one model, two calls. And the "contradiction" may
be partly an artifact of asking two differently-shaped questions of a model with no memory between
calls; `critique.md` argues this against itself.

**Nearest existing construct:** `Percept` + `Ground`. A general claim tends to cite a `frame`
ground; a local one cites a region or field. **Scope may already be encoded in the ground type** —
which would make this cheap to explore and require no new entity.

**Deliberately NOT concluded:** that Semant should detect contradictions between percepts. Large,
error-prone, and not licensed by one run.

**Next test.** Ask the same question at two scopes deliberately and check whether ground types
differ as predicted. If they do, scope is already encoded and merely unused.

---

## spark-08 — the evidence base grows silently to meet the claim

**Status: SPARK, new, n=1. The most consequential thing A5 found.**

**Evidence.** `006-narrative-overreach/score.md` + `sparks.md`;
`fixtures/006-narrative-overreach/_medallion-x6.png`.

Asked only what is happening in a photograph, the model supplied a title, sculptor, date and
institution, and quoted a scriptural inscription that **is not in the frame** — writing that it
*"confirm[s]"* the location. Verified false from the pixels: the medallion is a coloured figural
mosaic with a fragmentary non-English band.

**Enablement claim.** Percepts cite Grounds, and a Ground points at a region of *this* image. There
is no way to record that a reading was licensed by something **outside the frame** — a remembered
attribution, a catalogue fact, a half-recalled monument type. When that licence is false, the
percept looks exactly like one grounded in the picture.

**Why it outranks ordinary over-reading.** Every earlier run tested whether the model would say too
much *about what is visible*. A5 shows it will **import** evidence and present it as read off the
image. A citation system that can only point inward cannot distinguish "I see this" from "I know
this from elsewhere" — and the second is where the error entered.

**Nearest existing construct:** `Ground` — the exact inverse of spark-01. spark-01 wanted to speak
about the artifact rather than the depiction; spark-08 wants to mark a claim as resting on
something outside the image entirely.

**Deliberately NOT concluded:** that Semant should add an external-citation entity. One run. The
honest first move is far smaller — a rehearsal convention recording, verbatim, whenever a model
supplies a name, date, place or quotation the frame does not contain.

**Next test.** Stage 1 on two further monuments of recognisable *type* but no legible text. If
attribution appears each time, this is standing behaviour, not an accident of one famous pose.

---

## spark-06 — RESOLVED: question-conditional (address vocabulary)

**Status: RESOLVED by run `007-anthropomorphism-ab`. No longer contested.**

**Evidence.** Same image, identical 768 px stimulus by sha256 in both arms, same model,
`reasoning_effort`, `max_tokens` and call shape, both arms stateless. Only the question differed.

- **Address-framed:** *"glowing eyes"*, *"face-like frontality"*, *"almost facial architecture"*.
- **Structure-framed:** *"light fixtures"*, *"mirrored placement"*, *"visual anchors"*.

**The same lamps.** The face is not in the photograph; it is in the question.

**Why this supersedes A4's narrowing.** A4 argued from a *negative* result on a *different* image
whose aperture geometry may have lacked the triggering feature. This argues from a *positive*
result in one arm and a *positive non-face* reading in the other, on **the one image known to have
produced the behaviour**. Pre-registered cell `a_face_b_none`.

**Secondary result:** arm A reproduced A3's face at 768 px single-image, where A3's original was
256 px inside a three-image comparison — so A3's finding was **not** an artifact of downscale
degradation or comparison context.

**Scope — deliberately narrow.** Resolved: **address-framing is sufficient**; the image alone is
not. **Not resolved:** whether kinship or motif-similarity vocabulary pulls the same way. **A6 asks
exactly such a question**, so it gains a real but limited protection — avoid address vocabulary, and
do not read this as clearance for A6's actual question.

**What would overturn it.** A counterbalanced replication where arm B produces the face, or the same
A/B on a second stimulus showing the opposite pattern.

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
