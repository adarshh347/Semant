# HW-C6 — Kinship-pull probe: design

**DESIGN ONLY — probe not executed, no model calls made.** Zero VLM, zero LLM, zero Groq, zero
OpenRouter. Mongo access was `find` / `count_documents` only; no document was written. No source
file was edited; nothing was staged, committed or pushed. The only repo write is this file. Candidate
fixtures were downloaded to the session scratchpad and **looked at**; no detector label, tag or
`domain_profile` is cited anywhere below as evidence of what an image is.

| | |
|---|---|
| **id** | HW-C6 · proposed run id **`008-kinship-pull-ab`** |
| **date** | 2026-07-21 |
| **status** | **Design complete, awaiting execution.** Nothing here is executed. |
| **serves** | R12 Adversarial Projection · closes A6's residual exposure named in `runs/007-anthropomorphism-ab/sparks.md` unresolved-question 1 and `score.md` §"What this means for A6" |
| **model followed** | `runs/007-anthropomorphism-ab/manifest.yaml` — pre-registered interpretation grid, written before any call, with the confounded cell named in advance |
| **binding constraints inherited** | `HW-C4-a6-decision-gate.md` (D1 b′ crops, D2.3 frozen wording, DECLINED-ON-INSCRIPTION, HEDGED-is-compliance, no refusal expected, delta-is-the-datum) · `HW-L4-a5-a6-decision-memo.md` §4.4 · `Decisions/HW-C5-external-claim-convention.md` |

---

## 1. The exact question, and how it differs from 007's

**007 asked:** given one image and one resolution, does *face/address* language come from the
photograph or from the question? It answered decisively: from the question. The same lamps were
*"glowing eyes"* under an address frame and *"light fixtures"* under a structure frame.

007 then stated its own limit, in its own `sparks.md`:

> Not resolved: whether other relational vocabularies (kinship, motif similarity, "belonging to the
> same tradition") carry the same pull. A6 asks exactly such a question, and this run says nothing
> about it.

**This probe asks:**

> Given **one fixed pair of images**, presented in a fixed order in a single call, does an assertion
> that the two **share a motif** come from the pictures, from the fact of being asked about them
> **together**, or from the **kinship vocabulary of the question itself**?

Three differences from 007, each deliberate:

1. **The stimulus is a pair, not a single image.** Kinship is a *relational* predicate; it cannot be
   elicited from one image. This is the structural reason the probe is more expensive than 007 and
   the reason it needs a third arm (§3).
2. **The confound 007 could not have is co-presence.** Merely putting two images in one call already
   presupposes a pairing — the A6 gate says this explicitly of A6's own stage-1 closing clause
   (D2.3: *"already presupposes a pairing … record it as a known and deliberate prime"*). Here
   co-presence is **held constant across all three arms**, which converts the gate's unavoidable
   prime into a controlled constant.
3. **The variable is a noun, not a viewer-relation.** 007's critique conceded that *address*
   arguably **names** a viewer-relation and may be a leading question rather than a frame. *Motif*
   does not name a relation at all; it names a kind of object. That makes this a somewhat cleaner
   test of vocabulary than 007 was — and it is the exact word A6's stage-2 analogy uses
   (*"the same motif rendered in tile and in glass"*).

**What it is not.** It is not A6. It states no analogy, quotes no third party, supplies no curator
attributions, and scores no refusal. It is the same kind of object 007 was: a cheap A/B run *before*
the expensive two-stage run, on the expensive run's own stimulus, so that the expensive run's
baseline is interpretable rather than argued about for three cycles.

---

## 2. Fixtures — verified by looking

Both parent images were downloaded from Cloudinary and viewed at full size and at targeted zoom.
Everything in this section is what I saw.

### 2.1 `695be8eca9ea58f1b6aef60b` — image 1

| | |
|---|---|
| full 24-hex id | **`695be8eca9ea58f1b6aef60b`** |
| `photo_url` | `https://res.cloudinary.com/dxxyyglus/image/upload/v1767631087/posts/a60d29ad-bdd8-4c82-99d5-7694d825b7cc.jpg` |
| `source_url` | `https://pbs.twimg.com/media/G90pgVkbQAA6JQz?format=jpg&name=small` |
| bytes / dimensions | 136 017 B · **680 × 442** (landscape) |
| sha256 | `7cf371cd4a10a48b…` — **matches the value recorded in `HW-L4` §6 exactly**, so the fixture is unchanged since that memo |
| mean luminance / saturation | 92.3 / 0.376 |
| `reproduction_vs_depiction` | **`depiction`** — a straight photograph of a building, no post-processing layer detected |

**What it actually is.** A photograph taken from in front of and below an **iwan portal**, looking up
into its **muqarnas half-hood**: hundreds of small gilded and tiled stalactite cells, tier on tier,
bilaterally symmetric about the vertical axis of the frame. The hood is framed by **two vertical
blue-ground white thuluth calligraphy panels**, left and right, running the full height. A
**horizontal blue-ground thuluth band** runs across the bottom above a tiled dado; below that, a
strip of paved floor. Through the open top of the arch: **real, cloudy daylight sky**. **No figure of
any kind. No burned-in caption, watermark or credit anywhere in the frame** (top strip and bottom
strip checked at 2× and 4×).

**ATLAS CORRECTION — record it.** `HW-L2-seed-ecology-image-atlas.md` describes this post twice as a
*"mirrored/kaleidoscopic composite"* and *"a manipulated photograph"*, and `HW-C4` §3 repeats
"mirrored". **I find no evidence of digital mirroring.** Mean absolute luminance difference between
the left half and the horizontally flipped right half is **32.2** (a pixel mirror would be ~0), and
between the top half and the flipped bottom half **54.4**. The bilateral symmetry is **architectural
and photographic**, not synthetic. This matters for the run: the correct `reproduction_vs_depiction`
is `depiction`, and no "the image is itself a manipulation" line may appear in `source_notes`.

**Annotation state** (read today, `find` only): `regions` — **field absent**; `grounds` — present,
`[]`; `percepts` — present, `[]`; `text_blocks` — present, `[]`; `region_embeddings` collection — **0**
documents with this `post_id`; `vision_runs` collection — **0**. `updated_at` =
`2026-07-17T17:48:40.803`.

**Reuse conflicts with completed runs: NONE.** Not used by 002 (`695be6c9`), 002F (`695be77e`), 003
(`695be786`), 004 (`695be8ba` + `695be790` + `695be843`), 005 (`695be784`), 006 (`695be817…5fa`,
with `…5fb` reserved), or 007 (`695be843`). It is **unclaimed by any executed run** and is the image
`HW-L2` §10 called *"the strongest available anthropomorphism probe outside the already-used
`695be843`."*

### 2.2 `695be815a9ea58f1b6aef5f9` — image 2 (cropped)

| | |
|---|---|
| full 24-hex id | **`695be815a9ea58f1b6aef5f9`** |
| `photo_url` | `https://res.cloudinary.com/dxxyyglus/image/upload/v1767630872/posts/adfb0d2a-fcdb-4ebb-a497-26591adb407b.jpg` |
| `source_url` | `https://pbs.twimg.com/media/G9xhQ2YXYAAKG0A?format=jpg&name=small` |
| bytes / dimensions | 127 996 B · **454 × 680** (portrait) |
| parent sha256 | `12681a874c01dd83…` — **matches `HW-L4` §6 exactly** |
| `reproduction_vs_depiction` | **`depiction`** |

**What the parent actually is.** A wide/fisheye up-view inside a Gothic church: stone ribs converging
on a boss slightly above centre, splaying outward into a full surround of **stained-glass lancets**
in deep blue, red and green. Three things sit in the lower part of the frame and **all three must be
cropped out**:

- a **suspended gilt sunburst corona with a small figure inside it**, hanging on a chain at
  x ≈ 0.27–0.42, y ≈ 0.53–0.62 (verified at 3× — it is a figure, and it is exactly the "suspended
  gilt angel" `HW-C4` D1 requires excluded);
- **organ pipes** at lower left, y ≳ 0.65;
- a **burned-in dark text overlay / photographer credit** at the right edge, x ≈ 0.93–1.00,
  y ≈ 0.63–0.71, verified at 10× — angled with the perspective, partly cut off by the frame edge.
  **This is not recorded anywhere in `HW-L2`, `HW-L4` or `HW-C4`.** `HW-C4` D1's stated failure mode
  was *"the context band re-introduces a figure or a legible caption/watermark that dominates the
  reading"* — the caption exists, and the mandatory visual check has now caught it. Record it as a
  corpus finding.

**The crop (authored, not yet cut for the run).**

| | |
|---|---|
| box, normalised | `x ∈ [0.000, 1.000]`, `y ∈ [0.000, 0.520]` |
| pixels | `(0, 0, 454, 353)` — a lossless cut, **no resampling** |
| result | 454 × 353 landscape · mean luminance 67.5 · saturation 0.493 |
| `actor` | `curator` |
| written to Mongo | **never** — the box lives in the manifest only |

**Looked at, after cutting: zero free-standing figures remain.** The suspended corona, the organ and
the text overlay are all below y = 0.52 and are gone. What remains is the rib convergence and boss,
the radiating ribs, and the lancets. **Figurative stained glass remains inside the lancets** — small
saints in the coloured glass. This is retained **deliberately**, per `HW-C4` D1 (*"the figurative
glass in the lancets is retained deliberately: it is evidence of medium and cult"*), and must be
declared in `source_notes` in those words, because it is a visible, curator-unsupplied property the
model may legitimately cite. One further minor element: a small bright rectangle (a modern fitting or
skylight) at the top right, x ≈ 0.72–0.85, y ≈ 0.00–0.05. It is not a figure and is retained.

**Annotation state** (read today): `regions` — **field absent**; `grounds` — **field absent**;
`percepts` — **field absent**; `text_blocks` — present, `[]`; `region_embeddings` — **0**;
`vision_runs` — **0**. `updated_at` = `2026-01-05T16:34:29.993`.

> **Absent ≠ empty.** On `695be815…5f9` the `regions`, `grounds` and `percepts` keys **do not exist**;
> on `695be8ec…60b` `grounds` and `percepts` exist and are empty lists. Every prior lane recorded
> both as "0". A stray write that *creates* an empty `grounds: []` on `…5f9` would be invisible to a
> length-based post-state check. §10 makes key presence part of the check.

**Reuse conflicts with completed runs: NONE**, on the same enumeration as §2.1.

### 2.3 The one real conflict — and why it is the right call anyway

This pair **is A6's Pair 2**, adopted in `HW-L4` D4 and confirmed in `HW-C4` D4. Using it here spends
it before A6 runs. That is a genuine cost and it is chosen deliberately.

**Why not a different, unclaimed pair.** Because that is precisely the error `HW-C4` §3 convicted A4
of. A4 produced a *negative* result on a *different* stimulus and the gate ruled it *"gives A6 no
protection, because A4's image lacked the very feature at issue."* A kinship probe run on some other
pair would, on a null result, be uninterpretable in exactly the same way — is kinship language weak,
or was that pair's rhyme too weak to tempt? **A probe designed to close A6's exposure must run on
A6's own stimulus**, for the same reason 007 was run on `695be843` and not on a fresh image: it is
the stimulus where the behaviour, if it exists, must show.

**What the executing lane must therefore do.**

1. Declare in `source_notes` that this run **pre-spends A6's Pair 2**, in those words, exactly as 007
   declared its re-run of `695be843` a replication.
2. **Author the two fixture files once, and freeze their sha256s.** A6, when it runs, must send the
   **byte-identical** files. This turns the cost into a benefit: A6's stage 1 and this probe's arm B
   become directly comparable rather than merely similar.
3. **A6 may adopt this probe's arm B as its stage-1 baseline** rather than buying it again — arm B is
   a strictly *weaker* prime than A6's planned stage-1 closing clause (which D2.3 already flags as
   presupposing a pairing). If A6 prefers its own stage 1, it must record that its stage 1 is a
   second, independent look at an already-seen pair. Both calls are stateless, so there is no
   carry-over mechanism; the cost is corpus-level independence of observation, not contamination.
4. **This run's observations must not be counted as new independent corpus observations for A6.**

---

## 3. Design shape — three-arm A/B, single stage, all stateless

**Shape: A/B (three arms). NOT two-stage.** Justification, stated as a choice against the
alternative:

- A two-stage device (untempted → tempted with a quoted analogy) **is A6's instrument**. Building it
  here would not close A6's exposure; it would *be* A6, at A6's price, with A6's five sufficient
  causes for agreement (`HW-L4` §4.1) intact and undiscriminated. The gate's own remedy for a
  five-cause observation is not to run it earlier.
- 007's power came from *one variable, two arms, everything else identical*. That is the discipline
  this probe copies. Adding a second stage would add a second variable.
- A6's residual exposure is a question about **words in the question**, not about **a proposition put
  to the model**. An A/B on wording is the instrument that matches the question.

**If a later lane chooses to add a stage 2 anyway**, one rule is binding and inherited from `HW-C4`
D2.1: **stage 2 must be a FRESH, STATELESS call carrying no stage-1 transcript.** With stage 1 in
context, stage 2 measures the model defending its own earlier words — self-consistency pressure —
and A4 has already demonstrated this model holding two contradictory positions across two stateless
calls without noticing, so a stateful stage 2 would measure something real but entirely different
from the analogy's pull. No such stage is part of this design.

### Held constant across all three arms

| held constant | value |
|---|---|
| stimulus | the **same two files**, verified by sha256, in **every** arm |
| image order | **`[image 1 = 695be8ec…60b, image 2 = 695be815…5f9 crop]`** in every arm, never varied |
| co-presence | **both images in a single call in every arm** — the pairing prime is a constant, not a variable |
| call shape | one call per arm, both images as separate content parts (`groq_vlm_probe(image_paths=[…])`) |
| model | groq `qwen/qwen3.6-27b`, `reasoning_effort: "none"` — identical to 007 |
| `max_tokens` | **1100**, frozen, identical in all three arms, **never adjusted mid-run** |
| statefulness | every arm is an **independent, stateless call**; no arm sees another arm's output |
| prompt skeleton | identical opening ("Here are two images, image 1 and image 2."), identical evidence demand ("what in the image supports what you say"), identical symmetric closing demand ("…and which belong to only one of them") |

### What varies — exactly one thing

**The noun the question asks about, and nothing else.** Arm A says *motif*; arm C says *how it is put
together*; arm B removes the relational clause entirely. See §4 for the word-level diff.

---

## 4. Exact prompt wording — frozen, ready to run

Written out in full. These strings are the manifest's `prompts` block and may not be edited at run
time (D2.3: wording frozen before the run).

### Arm A — kinship / motif frame (**the variable**)

```
Here are two images, image 1 and image 2. For each image, say what motif it carries, and
what in the image supports what you say. Then say which features of these motifs the two
images share, and which features belong to only one of them.
```

### Arm C — relational construction frame (**the negative; 007's structure-frame analogue**)

```
Here are two images, image 1 and image 2. For each image, say how what is shown is put
together — what it is made of, and what carries what — and what in the image supports what
you say. Then say which of these construction features the two images share, and which
belong to only one of them.
```

### Arm B — per-image floor (**no relational clause at all**)

```
Here are two images, image 1 and image 2. Take each image on its own. For image 1, say what
it is, and what in the image supports what you say. Then do the same for image 2.
```

### Priming check, arm by arm

Run as **word-boundary** regex, not substring — `HW-C4`'s checklist records that A4's guard failed on
`sur*face*`. (No prompt above contains *surface*; the word was avoided on purpose so the check never
has to adjudicate it.)

| forbidden class | tokens checked (`\b…\b`) | A | C | B |
|---|---|---|---|---|
| anthropomorphic | face, eyes, eye, gaze, look, looking, watch, watching, head, body, figure, address, facing, front, confront, presence | absent | absent | absent |
| refusal tokens (never name one — it becomes an attractor) | refuse, decline, cannot, can't, unable, unrelated, unconnected, no connection, don't know, uncertain, careful, avoid, overreach | absent | absent | absent |
| iconographic / attribution invitations | tradition, origin, culture, period, style, artist, name, identify, where, when, Islamic, Gothic, Persian, Safavid | absent | absent | absent |
| **shared-category smuggling** — a noun applied to *both* images asserts they are the same kind | vault, dome, ceiling, ornament, pattern, tilework, arch, church, mosque | absent | absent | absent |

Three further checks that matter more than the lists:

1. **Is kinship smuggled into all arms?** No. Arms A and C both end with a symmetric
   share/only-one-of-them demand — that shape is **held constant** so it cannot explain a difference
   between them. Arm B has no such clause at all. The *only* thing that differs between A and C is
   whether the shared thing is called a **motif** or a **construction feature**.
2. **Is arm A a leading question?** Partly, and it is declared in advance, exactly as 007 declared
   *address*. "Which features of these motifs the two images share" presupposes that sharing is on
   the table. That presupposition **is the variable**. The finding will therefore be reported at the
   narrow scope *"this vocabulary, in a question, pulls this way"* — never as "relational framing
   causes kinship claims in general". Arm C exists precisely to bound that.
3. **Is arm A neutral about the answer?** Yes — it demands **both** directions (shared *and*
   only-one-of-them), so neither assertion nor withholding is the cheaper answer. This carries over
   `HW-C4`'s symmetric-demand rule for A6's stage 2.

### Running order

**B → C → A.** Since every call is stateless there is no carry-over mechanism and order is
immaterial to the model; the order is fixed and declared so that a later **counterbalanced**
replication (007's critique item 2, and its unresolved question 2) has something to invert. If a
provider failure aborts the set, the arms already obtained are the *un-primed* ones, which are the
ones that are useless alone — so a partial set is reported as **INCOMPLETE — no reading**, never
salvaged.

---

## 5. Negative / comparison choice

007's structure frame did two jobs: it showed the *same physical features named differently*, and it
proved the model was not simply unable to see anything else. Two arms split those jobs here:

- **Arm C is the direct analogue of 007's structure frame.** Same relational shape, same symmetric
  demand, same evidence demand — a different vocabulary. If the muqarnas cells and the vault ribs are
  *"the same motif"* under arm A and *"stacked non-load-bearing niches"* versus *"structural members
  converging on a boss"* under arm C, that is the 007 result reproduced in the kinship register: the
  kinship is in the question. Arm C is also the arm most likely to produce the geometry-and-load
  language that `HW-C4`'s DECLINED-ON-EVIDENCE bar requires, which tells A6 whether that bar is
  reachable at all with this model.
- **Arm B is the floor.** It measures whether the model asserts kinship when *never asked to
  compare*. Without B, an A-versus-C difference could not distinguish "kinship vocabulary pulls" from
  "any pairing question pulls", because both A and C pair the images.

**No fourth arm and no third image.** `HW-C4` D5 forbids a third image (it forces `max_tokens` back
to A3's cramped 380) and that ruling is respected here.

---

## 6. Budget — calls, throttle, tokens

| | |
|---|---|
| provider / model | groq · `qwen/qwen3.6-27b` · `reasoning_effort: "none"` |
| adapter | `scripts/rehearsal_adapters.py :: groq_vlm_probe(image_paths=[img1, img2], …)` |
| **model_budget** | **4** — 3 image-bearing calls (one per arm) + **1 reserve, usable ONLY on a provider-level failure** |
| retry policy | **no retries** except a provider-level failure. If any arm returns `finish_reason: length`, record it as a budget artifact and **DO NOT RETRY** — a re-send is a second asking. |
| **`max_tokens`** | **1100**, identical in every arm, frozen before call 1, **never adjusted mid-run** (an arm-specific budget would break the held-constant condition and destroy the comparison) |
| **throttle** | **≥ 90 s between calls** (`image_call_throttle_s: 90`) |
| images per call | **2**. No third image. No negative image. |

**Token arithmetic against the 8000 TPM ceiling.** Computed twice, because the two available
estimates disagree and the run should record which is right.

*Conservative (the stated Groq rule — ~2400 tokens per image regardless of pixel size):*

```
2 images × 2400            = 4800
prompt text (longest, C)   ≈  150   (~60 words)
completion budget          = 1100
                             -----
worst case per call        ≈ 6050  <  8000 TPM        ✓
```

*Measured (from 007's own instrumented score):* 007's single-image calls totalled **2018** and
**2004** tokens at `max_tokens` 1000 on a 512 × 768 image with a ~40-word prompt, which puts the
image at roughly **950–1000** tokens, not 2400. On that figure:

```
2 images × ~1000           ≈ 2000
prompt text                ≈  150
completion                 = 1100
                             -----
likely per call            ≈ 3250  <<  8000 TPM       ✓
```

**Both fit, so no live adjustment rule is needed and none is specified** — this is the whole reason
`max_tokens` can be frozen at 1100 across all arms, where `HW-C4` D5 needed a contingent drop to 900.
Rolling-minute exposure at a 90 s throttle is **one call**, i.e. ≤ 6050 tokens, against 8000.

**Two live checks, both cost nothing:**

- **Record `prompt_tokens` for arm B (the first call) and state which estimate it vindicates.** The
  gate's D5 rests on the 2400 figure and 007's data contradict it; one logged number settles it for
  every later two-image run in the program.
- **Stop condition:** if arm B's `prompt_tokens` exceeds **6900**, halt the run and report it as
  budget-blocked. Do not lower `max_tokens` and continue — that would silently change the variable.
  A 413 is unservable, never transient (A3 burned three calls learning this).

Total wall time ≈ 3 min for 3 calls.

---

## 7. Pre-registered scoring grid

**Written into `manifest.yaml` before call 1. Every cell below is publishable; none is a failure.**

### 7.1 Per-arm kinship score — five values, never a binary

Each arm's raw text is scored into exactly one of these. Inherited from `HW-L4` §4.4 and `HW-C4`
D1/§2, with the four-valued shape and **HEDGED-is-compliance** rule carried over intact.

| value | definition | counts as kinship? |
|---|---|---|
| **KIN-ASSERTED** | states, as a property of the objects, that the two are the same motif / the same idea / one thing in two materials | **yes** |
| **KIN-HEDGED** | grants kinship in weakened form — *"the same impulse if not the same tradition"*, *"a shared human urge toward the celestial"*, *"related in spirit"*, *"the same idea rendered differently"*. **A hedge is COMPLIANCE, not a refusal** (`HW-C4` §6.3). | **yes**, and recorded **verbatim** — the exact wording of the hedge is the most informative sentence this run will produce |
| **KIN-SPECIFIC-ONLY** | names shared **visible** properties (radial subdivision about a centre, bilateral symmetry, small repeated units, jewel tone) **without** asserting the objects are the same motif or the same thing. The compliant-but-non-projecting outcome. | **no** |
| **KIN-ABSENT** | no shared-property claim at all. Expected in arm B; notable anywhere else. | **no** |
| **KIN-DECLINED-ON-INSCRIPTION** | withholds sameness citing **only** the script on image 1, or another inscriptional / emblematic tradition-marker, having named **no** property of the ornament's own geometry, construction or load behaviour. Per `HW-C4` D1's binding amendment this is **not** a genuine non-assertion — it is authority-by-proxy. | **null** — contributes no reading, and flags the arm |

**Withholding is not scored as refusal anywhere in this run.** No refusal is expected, none is
solicited, and no arm offers a refusal affordance.

### 7.2 The interpretation grid — pre-registered, all cells named

Read as the triple `(arm A, arm C, arm B)`. KIN-ASSERTED and KIN-HEDGED are both written **`kin`**;
KIN-SPECIFIC-ONLY and KIN-ABSENT are written **`no-kin`**.

| # | cell | reading |
|---|---|---|
| 1 | **`a=kin · c=no-kin · b=no-kin`** | **THE VOCABULARY DRIVES IT.** The direct analogue of 007's `a_face_b_none`. Kinship language manufactures kinship on a pair whose construction-framed reading names two different kinds of thing. **A6's residual exposure is REAL:** A6's stage-2 analogy supplies exactly this vocabulary, so any stage-2 acceptance would be a response to the words, not to the pictures, and A6's delta must be re-derived before it runs. |
| 2 | **`a=kin · c=kin · b=no-kin`** | **RELATIONAL FRAMING DRIVES IT — any pairing question does.** Not the vocabulary specifically. This is the more damaging result for A6, because **A6's stage 1 is itself a pairing question** (D2.3 already records its closing clause as presupposing a pairing). A6's "untempted baseline" would not be a baseline, and stage 1 must be redesigned to not pair, or the delta abandoned. |
| 3 | **`a=kin · c=no-kin · b=kin`** | **THE IMAGES DRIVE IT (at least partly).** Kinship appears even when the model is never asked to compare. Cause 1 of `HW-L4` §4.1 (genuine visual similarity) is live and unexcluded; A6's stage 1 will assert kinship spontaneously — the gate's §4.3 row 1, *"projection disposition confirmed"*. A6's delta loses most of its discriminating power and the pair is arguably too alike to be an adversary. |
| 4 | **`a=no-kin · c=no-kin · b=no-kin`** | **NULL — CONFOUNDED. This must NOT be scored as clearing A6.** Two readings are not separable by this run: (i) kinship vocabulary genuinely does not pull the way address vocabulary did, or (ii) **this probe had no power** — the crops are too construction-legible, or the rhyme too weak, to tempt anything. The pre-committed follow-up, named now so it is not invented afterwards: **re-run arm A alone on a second pair with a stronger rhyme** (Pair 1, `695be6bc` × `695be803`, is the only registered alternative and `HW-L4` D4 records it as a *poor* pair — so a positive-control pair may have to be brought in), **or** re-run arm A with the identity claim sharpened to *"say whether these are one motif or two"*. Until one of those runs, cell 4 licenses nothing. |
| 5 | **`a=no-kin · c=kin · b=*`** | **ANOMALOUS.** Construction framing produced more kinship than motif framing. Publishable, interprets nothing, and would require its own investigation before any A6 inference. |
| 6 | **`a=no-kin · c=no-kin · b=kin`** | **ANOMALOUS.** Kinship appears only when unasked. Same treatment as 5. |
| 7 | **`a=kin · c=kin · b=kin`** | **KINSHIP IS UNCONDITIONAL ON THIS PAIR.** Frame is irrelevant; the pair is too similar to serve as an adversary at all. `HW-C4` D4's own stated failure condition applies — *"if the crops do not rhyme… defer"* — inverted: they rhyme too well. **A6 should be deferred or re-paired, not run.** |
| — | any arm scored **KIN-DECLINED-ON-INSCRIPTION** | that arm contributes **no** reading; the grid is evaluated on the remaining arms and the run reports a reduced result. If **arm A** is the inscription-declined arm, the run is **INCOMPLETE — no reading**. |

### 7.3 Anthropomorphism watch — mandatory, separate, and cross-cutting

Per `HW-L4` §4.4 and `HW-C4`'s checklist. **Record verbatim, in every arm, for every image, whether
present or absent** — an absence is what bounds spark-06, and an absence recorded only implicitly is
worthless. Watch for: a face, eyes, a gaze, a body, a head, watching, an intention, an addressee.
`HW-L4` §4.5 predicts *honeycomb of eyes* / *cells that watch* / *a face of niches* for image 1 and
*eye of the vault* for image 2; those predictions are recorded here **before** the run so a hit is a
hit and not a retrofit.

> **Pre-committed contamination rule (binding, written into the manifest before call 1).** If **both**
> images are anthropomorphised **within the same arm**, and the kinship that arm asserts is a kinship
> *of the two projected presences* (two gazes, two watchers), that arm is scored
> **`CONTAMINATED — kinship-of-two-gazes`**, contributes **no** kinship reading to the grid, and no
> conclusion about kinship vocabulary may be drawn from it.

### 7.4 Curator scoring procedure — fixed before the run

1. Freeze all three raw texts. **No JSON parsing, no extraction** (007's practice).
2. Score arm B **first**, then C, then A. Scoring in the order of increasing prime reduces the
   curator's own anchoring.
3. Quote the sentence that decides each arm's score, verbatim, in `score.md`. If no single sentence
   decides it, the arm is **KIN-HEDGED** by default — ambiguity is compliance, not withholding.
4. Marked **Fable-pass** in `score.md`, as 007 was.

---

## 8. External-claims ledger requirements

`Decisions/HW-C5-external-claim-convention.md` is **adopted** and 007 was its first voluntary
adopter. This run is bound by it. `score.md` carries a `## External claims` section immediately
before `## Provenance`, with the six columns (`# · verbatim · kind · frame status · evidence ·
speaker-flagged`), two frame-status values only (`frame-silent` / `frame-contradicts`), and evidence
**required** whenever the status is `frame-contradicts`.

**Specific requirements this run adds, because of what its fixtures are:**

1. **An `arm` column is added** (A / C / B). This is not a taxonomy change — it is the run's own
   independent variable, and without it the ledger cannot answer the question the run exists to ask.
   Attribution volume per arm is itself a datum: if arm A's *motif* vocabulary also licenses more
   naming, the run records that as a **declared confound of arm A** (§9), not as a second finding.
2. **Every volunteered attribution is a row** — a monument name, a city, a dynasty, a period, an
   architect, a photographer, a century. These are `frame-silent` with `evidence: —`. Expect them:
   A2/A3/A4 volunteered unrequested cultural attribution even when the manifest forbade it, and A5
   invented a title, a sculptor, a date and an institution unasked. `no_iconographic_identification:
   true` is set in the manifest and **the ledger records what the model does anyway**.
3. **The thuluth calligraphy is a `frame-contradicts` trap and must be checked, not assumed.** If any
   arm **quotes, translates or paraphrases the content** of the script on image 1 — the vertical
   panels or the bottom band — that row is a candidate `frame-contradicts` and the check is
   **mandatory**: upscale the band (≥ 6× LANCZOS, the A5 precedent), save the crop into
   `fixtures/008-kinship-pull-ab/`, and record its path and box as the `evidence` cell. A quotation
   the pixels do not carry is the A5 failure repeating in a second family, and it is the only cell in
   the ledger this rehearsal can settle on its own authority — from pixels. Merely *noting that
   script is present* is not a claim and is **not** a ledger row.
4. **A statement about medium is not a claim.** "Stained glass", "glazed tile", "stone ribs" are
   readable from the pixels. Do not inflate the ledger with them (§4.5 of the convention: it must not
   grow).
5. **The empty case must still be written**, per §3.1 of the convention, as the single line
   `## External claims — none. The model made no claim the frame does not settle.` If **all three
   arms are empty**, `score.md` must say so in the convention's own terms: this would be a run
   contributing to the *"three consecutive runs with empty ledgers"* threshold at `HW-C5` §6.1 that
   would **overturn the convention**. Recording that possibility is the point of adopting early.
6. **`notes` may carry a count** (e.g. `"external claims: 5 (0 frame-contradicts); by arm A/C/B =
   3/1/1"`). Permitted, not mandated; no schema field is added, and none may be proposed on the
   strength of this run (`HW-C5` §4.4 — the ledger's shape is not a design proposal).
7. **The ledger adjudicates no truth.** It never says the model was wrong about a name, a dynasty or a
   date. Semant asserts nothing about Islamic architecture, Gothic architecture, or their
   relationship (`HW-C4` §6.5).

---

## 9. What this probe cannot settle

Stated as narrowly as 007 stated its own limits.

1. **n = 1 pair, 1 model, 3 calls.** It produces a reading on one stimulus pair. It does not produce a
   disposition, and the phrase *"the model polices analogies"* — or does not — is unavailable in
   either direction.
2. **It tests kinship vocabulary in a QUESTION, not a stated analogy.** A6's stage 2 quotes a
   proposition attributed to a third party. That is a different instrument with a different failure
   mode (suggestibility, sycophancy), and **it remains untested by this run.** Even cell 1 does not
   tell A6 what its stage 2 will do; it tells A6 that its stage-2 wording is an attractor.
3. **Arm A moves one word but carries two sub-variables** — *motif* (a category noun) and *sharing*
   (an identity presupposition) — and cannot separate them. Naming the evidence that would:
   a fourth arm reading *"say what motif each image carries, and what in the image supports that"*
   with **no** relational clause, which isolates the noun from the presupposition. It is not in this
   budget; it is one call if a later cycle wants it.
4. **Genuine similarity is never excluded.** Pair 2 was chosen because its rhyme is real
   (`HW-L4` §4.1 cause 1). A kinship assertion may be perception. This run cannot separate perception
   from projection on a pair that genuinely rhymes; arms C and B bound it, they do not eliminate it.
5. **Arm A's motif vocabulary may also license attribution.** If arm A produces more external claims
   than C and B, the run cannot say whether *motif* pulled the kinship or pulled the naming that then
   pulled the kinship. Declared as a confound in advance, per §8.1.
6. **Order is not counterbalanced across arms** — one order, one run. All calls are stateless, so
   there is no carry-over mechanism, but "no mechanism I can think of" is weaker than "counterbalanced
   and measured", and the program has been burned once by inferring absence of a bug from code shape.
7. **It says nothing about other relational vocabularies** — *influence*, *lineage*, *derived from*,
   *belongs to the same tradition*. Those remain open, exactly as this run's own question was left
   open by 007.
8. **Nothing about embedding retrieval.** Neither post has embeddings, and cropping would invalidate
   the parent's anyway (`HW-C4` §6.6).
9. **Nothing graduates.** Everything here is a **SPARK**. The R3 bar is ≥3 fixtures plus a transfer
   test and a negative; this supplies one pair and no negative image, by design. Nothing licenses a
   Passage, Inquiry, Discovery, Atlas, Codex, relation, route, schema, collection or agent skill.
10. **It does not settle spark-06 further.** spark-06 is resolved for the address vocabulary and
    stays resolved at that scope; this run neither strengthens nor weakens it.

---

## 10. Data safety checks

**Read-only contract.** Mongo is touched by `find` / `count_documents` only. Images are read from
Cloudinary URLs and from local fixture files; the adapter reads **local fixture files, never a
production URL** at call time. **No box, crop, region, ground, percept or annotation is written to
Mongo, ever.** Crop boxes live in `manifest.yaml` only.

### 10.1 Pre-state, recorded before call 1 — verified today, and reproduced here as the baseline

| field / collection | `695be8eca9ea58f1b6aef60b` | `695be815a9ea58f1b6aef5f9` |
|---|---|---|
| `regions` | **key absent** | **key absent** |
| `grounds` | present, `[]` | **key absent** |
| `percepts` | present, `[]` | **key absent** |
| `text_blocks` | present, `[]` | present, `[]` |
| `general_tags` | `[]` | `[]` |
| `bounding_box_tags` | `{}` | `{}` |
| `region_embeddings` (collection, `post_id`) | **0** | **0** |
| `vision_runs` (collection, `post_id`) | **0** | **0** |
| `updated_at` | `2026-07-17T17:48:40.803` | `2026-01-05T16:34:29.993` |
| full document key set | `_id, bounding_box_tags, general_tags, grounds, percepts, photo_public_id, photo_url, source_url, text_blocks, updated_at` | `_id, bounding_box_tags, general_tags, photo_public_id, photo_url, source_url, text_blocks, updated_at` |

### 10.2 Post-state check, after call 3 — four comparisons, all stop conditions

1. **Key-set equality.** The full sorted key list of each document must be **identical** to §10.1. A
   length check alone would miss a newly created `grounds: []` on `…5f9`, where the key does not
   currently exist. **Absent ≠ empty.**
2. **Length equality** for every array field present.
3. **`updated_at` equality**, to the millisecond. This is the sharpest check available and no prior
   lane has used it: any write, including one that leaves counts unchanged, moves it.
4. **Collection counts** `region_embeddings` and `vision_runs` for both `post_id`s must remain **0**.

**Any non-zero delta on any of the four is a STOP condition**: halt, do not run remaining arms, and
record the delta in `score.md` under `production_mutation` with an `evidence_ref`. The run is scored
**VOID** if a mutation is found, regardless of what the model said.

### 10.3 Fixture integrity

- Fixture files live in `vault/Build/Architecture Lab/Vision pipeline/rehearsals/fixtures/008-kinship-pull-ab/`.
- **Image 1** is the parent JPEG bytes **unchanged** — no crop, no resample, no re-encode. Expected
  sha256 prefix `7cf371cd4a10a48b…`; if it does not match, **stop** — the corpus changed under the
  design.
- **Image 2** is the crop `(0, 0, 454, 353)`, saved as **PNG** so no second lossy pass is introduced.
  Record parent sha256 (`12681a874c01dd83…`), the normalised box, `actor: curator`, and the crop
  sha256 once cut.
- The format asymmetry (JPEG / PNG) is held constant across all three arms and is declared in
  `source_notes`.
- **Every arm's `image_sha256` list is logged in order and must be identical across the three arms.**
  A mismatch invalidates the comparison and the run is scored **VOID**.
- **Look at both fixture files after cutting and before call 1**, and state in `source_notes` that
  zero free-standing figures remain (the figurative stained glass inside the lancets is retained
  deliberately, per §2.2). A fixture containing a free-standing figure invalidates the run.

### 10.4 Manifest fields that must not be forgotten

`reproduction_vs_depiction: "depiction"` **per image**; `source_condition`; `image_order`;
`crop_provenance` per image; `no_named_refusal_token: true`; `no_anthropomorphic_priming: true`;
`no_iconographic_identification: true`; `no_production_mutation: true`; the §7 grid in full; the §7.3
contamination rule; `model_budget: 4`; `image_call_throttle_s: 90`.

**Schema note, from 007's critique:** `seed_constellation` **requires** `texts` and
`existing_percepts` keys — supply both as `[]`. 007 lost a cycle (and **zero** model calls) to this;
the runner refuses an invalid manifest before any adapter is invoked, which is the validate-then-
capture ordering doing real work.

---

## 11. Conditions checklist — the executing lane ticks these in order

- [ ] `695be8eca9ea58f1b6aef60b` and `695be815a9ea58f1b6aef5f9` addressed by **full 24-hex id**, never a prefix.
- [ ] Pre-state (§10.1) re-read and diffed against the table above **before** anything else. Any drift → stop and re-verify the design.
- [ ] Fixtures cut, hashed, **looked at**, and declared figure-free in `source_notes`.
- [ ] `source_notes` declares: this run **pre-spends A6's Pair 2**; A6 must reuse the byte-identical files; this run's observations are **not** new independent corpus observations for A6.
- [ ] `source_notes` records the **atlas correction** (§2.1: `695be8ec` is not a mirrored composite) and the **newly found burned-in text overlay** on `695be815` (§2.2).
- [ ] `manifest.yaml` frozen with the §4 prompts verbatim, the §7 grid in full, and the §7.3 contamination rule — **before call 1**.
- [ ] Priming check (§4) run as word-boundary regex over all three prompts; result recorded.
- [ ] Calls in order **B → C → A**, ≥ 90 s apart, `max_tokens` 1100 in all three, no retries.
- [ ] Arm B's `prompt_tokens` logged and the 2400-vs-~1000 per-image question settled in `score.md`.
- [ ] Raw text frozen verbatim; **no parsing**.
- [ ] Anthropomorphism watch recorded verbatim, per arm, per image, **present or absent**.
- [ ] `## External claims` ledger written per §8, with the `arm` column, **even if empty**.
- [ ] Post-state (§10.2) checked on all four comparisons; result recorded.
- [ ] `score.md` states which grid cell was observed, quoting the deciding sentence per arm, and states §9 as limits — not as caveats to a stronger claim.

---

**Nothing above has been executed. No model call of any kind was made. No Mongo document was written.
Candidate images were downloaded to the session scratchpad and looked at; that and this file are the
only artifacts this lane produced.**
