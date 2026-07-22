# 008 — source notes

## Pre-spending A6's Pair 2 — declared, in the design's own words

**This run pre-spends A6's Pair 2.** The pair is A6's own stimulus (HW-L4 D4, confirmed HW-C4 D4),
and using it here spends it before A6 runs. Chosen deliberately: a kinship probe on a *different*
pair would repeat exactly the error HW-C4 §3 convicted A4 of — a null on a stimulus that may lack
the feature at issue bounds nothing.

**Binding consequences.**

1. **A6 must send the byte-identical fixture files**, verified by sha256:
   `img1-muqarnas-parent.jpg` = `7cf371cd4a10a48b6fc759281007b9bb1cd1189cc773af5a4728d4ab46e54f03`;
   `img2-vault-crop.png` = `4e76caff29217bc5d40d9adfdf50133ebe52b4d73572b65143c7701889067b47`.
2. **A6 may adopt this run's arm B as its stage-1 baseline** rather than buying it again. Arm B is a
   strictly weaker prime than A6's planned stage-1 closing clause, which HW-C4 D2.3 already records
   as presupposing a pairing. If A6 prefers its own stage 1, it must record that its stage 1 is a
   second, independent look at an already-seen pair. Both calls are stateless, so there is no
   carry-over mechanism; the cost is corpus-level independence of observation, not contamination.
3. **This run's observations are NOT new independent corpus observations for A6.**
4. **The running order is now forced: 008, then A6, on identical bytes.**

## Fixtures — verified by looking, before call 1

Both files were opened and viewed after cutting and before any model call. **Zero free-standing
figures remain in either fixture.**

- **Image 1** is the parent JPEG **unchanged** — no crop, no resample, no re-encode. 680 × 442.
  Muqarnas half-hood of an iwan portal, two vertical blue-ground thuluth panels, a horizontal band
  above a tiled dado, real cloudy sky through the open top. No figure, no caption, no watermark.
- **Image 2** is the curator crop `(0, 0, 454, 353)` — a lossless cut, no resampling — saved as PNG
  so no second lossy pass is introduced. The suspended gilt corona **with a small figure inside it**,
  the organ pipes, and the burned-in text overlay are all below y = 0.52 and are **gone**.
- **Retained deliberately:** the **figurative stained glass inside the lancets** (small saints in the
  coloured glass), per HW-C4 D1 — *"it is evidence of medium and cult"*. It is a visible,
  curator-unsupplied property the model may legitimately cite, **and it did**: arm A named
  *"Figurative Art … likely depicting biblical stories or saints"* and built its `Unique Features`
  contrast on it. Also retained: a small bright rectangle at top right, a modern fitting or skylight,
  not a figure.

## Atlas correction — `695be8eca9ea58f1b6aef60b` is NOT a mirrored composite

`HW-L2-seed-ecology-image-atlas.md` describes this post twice as a *"mirrored/kaleidoscopic
composite"* and *"a manipulated photograph"*, and `HW-C4` §3 repeats "mirrored". **Both are wrong.**

The design measured a mean absolute luminance difference of **32.2** between the left half and the
horizontally flipped right half (a pixel mirror is ~0). **Confirmed independently at execution time
by looking:** the clouds visible through the open top of the arch are **not** symmetric left to
right — which no pixel mirror could produce. The bilateral symmetry is **architectural and
photographic**, not synthetic. Correct `reproduction_vs_depiction` is therefore **`depiction`**, and
no "the image is itself a manipulation" line appears anywhere in this run.

## New corpus finding — a burned-in text overlay on `695be815a9ea58f1b6aef5f9`

The parent carries a **burned-in dark text overlay / photographer credit** at the right edge
(x ≈ 0.93–1.00, y ≈ 0.63–0.71), angled with the perspective and partly cut off by the frame edge.
**It is recorded in no prior document** — not in HW-L2, HW-L4 or HW-C4. HW-C4 D1's stated failure
mode was *"the context band re-introduces a figure or a legible caption/watermark that dominates the
reading"*, and the mandatory visual check caught it. **The crop excludes it.**

## Format asymmetry — declared, not corrected

Image 1 is JPEG, image 2 is PNG. This is **held constant across all three arms**, so it cannot
explain any between-arm difference. It is declared rather than corrected because re-encoding either
file would break the byte freeze A6 depends on.

## Mechanism — how the §6 stop condition was honoured

The design requires halting **before** arms C and A if arm B's `prompt_tokens` exceeds 6900. The
runner executes all probes of a capture in one pass, so a single three-probe capture could not have
stopped in time. The run was therefore executed in two phases:

1. **Arm B alone**, captured into a scratch runs-root — **1 live call**. Its `prompt_tokens` was read
   (**3649**, under the threshold) before anything else was sent.
2. **The real run**: arm B **adopted** from phase 1 via the runner's `reuse_frozen` path — **0
   calls**, because re-sending an already-answered prompt would be a second asking and would spend
   budget to obtain evidence already held — then arms C and A live, each throttled ≥ 90 s.

**Total live image-bearing calls: 3**, of a budget of 4. The reserve was never touched. Arm B's
observation therefore carries the provenance suffix `:reused_frozen` in `trace.json`, which is the
honest record of how it was obtained. `reuse_frozen` refuses to invent an observation: the file must
exist and must validate against the observation schema, and it did.

## Honesty notes

- **The manifest was refused once before any call was made.** `source_notes` must be an object, not
  a string; the runner's validate-then-capture ordering caught it and **zero model calls** were
  spent on the correction. This is the second time in the program that ordering has paid for itself
  (007 lost a cycle to `seed_constellation` requiring `texts` and `existing_percepts`).
- **No external lookup was performed.** The rehearsal does not know whether image 1 is the Shah
  Mosque or image 2 the Sainte-Chapelle, and does not need to. The ledger records that the frame
  does not settle them; it asserts nothing about whether they are right.
- **Semant asserts nothing** about Islamic architecture, Gothic architecture, or their relationship.
  Arm A's shared-motif claim is recorded as **something the model said under a particular question**,
  never as a finding about the buildings.
- **The two idioms in the anthropomorphism watch were judged, not counted.** *"Draws the eye
  upward"* was read as the viewer's eye and scored as **not** a hit. A different curator could argue
  it; the judgement is recorded here so the argument is available rather than buried.
