# CIRCUIT-001 P1 — Product test scenes

**BUILD-VERIFICATION SCENES — not rehearsals.** Short, human-performed, end-to-end. They verify that
the circuit *circulates*; they are not experiments and they produce no research findings. No scene
requires a model call except where marked optional. **No scene may mutate another scene's post.**

Rests on `CIRCUIT-001-P1-differential-manuscript-circuit-spec.md`. Posts below are **real corpus
documents** identified during the P0 audit, addressed by **full 24-hex id**.

> **A precondition that shapes every scene: the corpus has 0 text blocks.** No post has a manuscript.
> Every scene therefore *creates* the writing it then tests, and that writing is the first real data
> the writing leg has ever held. **Scene 1 is also, incidentally, the first end-to-end use of the
> product's central path.**

**Before each scene:** record `updated_at` to the millisecond for the post. **After:** the only
permitted deltas are `text_blocks`, `grounds` and `percepts`. Any change to `region_annotations`,
`region_embeddings` or `vision_runs` is a **failure**, regardless of how the UI behaved.

---

## Scene 1 — Healthy percept circuit

**The scene that proves the artery exists.**

| | |
|---|---|
| **post** | `695be8b0a9ea58f1b6aef606` — carries a curator region (`seg_0`, sam2-refine, geometry_rev 3), a region ground `gnd_mrtof0k1_0`, and two curator percepts (`pctx_mrtof46o_0` *"arrow"*, `pctx_mrtofp6b_1` *"fold"*) |
| **why this post** | it is the **only** corpus post with a complete, healthy, curator-authored evidence chain already in place |

**Human action.** Open Differential → select the existing ground → **Compose a percept** → write a
short expression → **"Keep and write from it →"** → land in the Manuscript with the chip inserted →
write one sentence around it → click the chip.

**Expected UX.**
1. The composer offers two equal actions; the second exits to the Manuscript.
2. The chip appears **at the caret**, carrying the percept's expression as its label.
3. Clicking it plays recall: the left panel expands, the pane scrolls, the cited region lights, the
   caption shows the expression.
4. **No evidence note appears** — degradation-only display means a healthy circuit is silent.
5. The Circulation Thread's collapsed line reads roughly *formed · 1 cited · in writing · recalled*.

**Expected data state.** A new `pctx_` percept in `post.percepts` citing the existing ground; one new
`text_block` whose `content` carries `data-percept-id` and `data-region-ids`; `region_annotations`
**unchanged**; `updated_at` moves (a legitimate write).

**Failure.**
- The chip's props differ from those produced by the `/percept` slash route — **the two paths have
  drifted and will keep drifting.**
- Recall lights nothing, or lights the wrong region.
- Any evidence badge appears on a healthy chip — **honesty has become noise.**
- After reload, the chip's `data-percept-id` no longer resolves, or the reconstructed Mention has
  `regionId: 'gnd_…'` (Part B regression).

---

## Scene 2 — Detached evidence circuit

**The scene the whole rehearsal program was pointing at.**

| | |
|---|---|
| **post** | `695be786a9ea58f1b6aef5ed` — 5 grounds, 2 percepts; **two grounds (`gnd_mrqp8tls_0` → `fine_3`, `gnd_mrqp8tlt_1` → `fine_0`) are durably flagged detached** and their regions are gone |
| **why this post** | percept `pctx_mrqp950d_0` — a curator's own words, *"the upper head"* — is **fully unevidenced**. This is spark-03's original case |

**Human action.** Insert the **already-existing** unevidenced percept into the Manuscript via
`/percept`. Write a sentence. Click the chip. **Do not** attempt any repair.

**Expected UX.**
1. `RefPicker` shows the percept with a badge reflecting **what resolves**, not what is cited — a
   fully-detached percept must not read *"2 grounds"* beside an empty sub-line.
2. The chip inserts normally. **A percept with dead evidence is still a real noticing** and must
   remain writable-about.
3. On click: the expression is spoken, **no region lights**, the image is **not** dimmed wholesale,
   and the one-line note appears — *"Detached evidence — none of the 2 cited grounds still
   resolves."* — **in the Manuscript**, which today it does not.
4. The note states **absence, never cause.** The string *"replaced by a re-dissect"* must appear
   nowhere.
5. Thread: `cited` carries a judgement; `recalled` still records that recall was played.

**Expected data state.** One new `text_block`. **No ground, percept, region or flag is modified** —
in particular the four durable `detached: true` markers stay exactly as found.

**Failure.**
- No note (the P0 headline bug, unfixed).
- The image dims wholesale (`RegionOverlay.jsx:32-33` path).
- Any cause is asserted.
- The UI offers to "repair", "re-point" or "restore" — **not in this slice, and not without a
  decision.**
- The percept is marked invalid or blocked from writing.

---

## Scene 3 — Long percept text recall circuit

**Tests that the circuit stays legible when the writing is real rather than a stub.**

| | |
|---|---|
| **post** | `695be794a9ea58f1b6aef5f1` — 4 grounds, **2 detached and uncited**; a genuinely mixed state |
| **why this post** | mixed health is the realistic case, and it is the one the arithmetic bug bites: `unresolved` collects expanded members while `citedCount` counts only `ground_ids` |

**Human action.** Compose a percept citing **several** grounds — at least one resolving and one not —
including a composite (constellation or relation) ground. Write **a long paragraph** (150+ words)
around the chip. Reload the page. Click the chip.

**Expected UX.**
1. Recall plays only the steps that draw something; a **composite ground whose members are all
   detached produces no timed step** (today it does — `grounds.js:81` reports `detached: false`).
2. The note's arithmetic is coherent. **"2 of 1 cited grounds" is an automatic failure.**
3. The caption remains readable against a long block — the caption box is bounded and scrolls
   (`max-height: 45%`, `overflow-y: auto` already exist in Differential; the Manuscript side must not
   regress).
4. **After reload**, the chip still resolves and the Thread reads the same as before reload.

**Expected data state.** One long `text_block`; percept cites a mix of resolving and detached grounds.

**Failure.**
- Any count that disagrees with what was drawn.
- A timed step that highlights nothing.
- The caption overflowing, truncating the expression, or covering the image.
- **Reload changes the Thread** — that is the Mention-reconstruction loss (Part B) surfacing as
  product behaviour.

---

## Scene 4 — External claim in manuscript circuit

**Tests that authorship survives the round trip — the leg where model prose currently becomes the
curator's.**

| | |
|---|---|
| **post** | `695be843a9ea58f1b6aef5ff` — the run-007 stimulus, an image with **no figure** that the model has twice described in face/address language |
| **why this post** | it is the corpus's known generator of confident outside-frame prose, so a model-authored block here is realistic rather than contrived |

**Human action.** Insert an AI-authored block (the existing `origin: 'sutradhar'` path,
`PostDetailPage.jsx:593`). Write a curator paragraph beside it. Reload. View in the **read** view
(`PostDetailPage.jsx:1194-1206`).

**Expected UX.**
1. The model-authored block is **visibly distinguishable** from the curator's, quietly — a mark of
   authorship, **not a warning badge**, and **never** a claim that its content is false.
2. The distinction **survives reload** — today `relationType:'interprets'` / `actor:'sutradhar'`
   become `'cites'`/`'human'` on every load.
3. Nothing labels the model's sentence true or false. **The ledger is not adopted here.**

**Expected data state.** `text_blocks` contains a block with `origin: 'sutradhar'` **persisted**, not
defaulted to `"human"` by one of the four write paths that omit it.

**Failure.**
- The two blocks are typographically identical in the read view (**today's behaviour**: `data-origin`
  is stamped and has zero CSS rules).
- `origin` is absent after reload.
- Any truth verdict, confidence score, or "unverified" chrome appears — **out of scope and contrary to
  `HW-C5` §4.1.**

---

## Scene 5 — Cross-image / Atlas-prep circuit *(optional; read-only)*

**Not an Atlas. A measurement of whether an Atlas could ever be honest.**

| | |
|---|---|
| **posts** | `695be8eca9ea58f1b6aef60b` and `695be815a9ea58f1b6aef5f9` — the frozen 008/009/010 fixture pair, byte-stable and carrying **zero** regions, grounds and percepts |
| **why this pair** | its bytes and pre/post state are the most verified in the corpus; **and its emptiness is the point** |

**Human action.** Form one percept on **each** post. Write one sentence about each. Then ask a
question the product **cannot answer today**: *"where else have I noticed something like this?"*

**Expected UX.** **There is no answer, and the honest outcome of this scene is that the product says
so** — or, more likely, offers nowhere to ask. **That absence is the result to record.**

The purpose is to measure what a cross-image surface would need: the audit found that nothing can
answer *"where else is this percept cited?"* without parsing every block of every post in the browser
(`regionStore.js:112` parses one post at a time).

**Optional model leg.** A semantic read on one post, **only if** it costs nothing new — to observe
whether the reading is attributable to anything. Expected: it is not; the global reading **has no
id** (`semantic_pass.py:104`).

**Expected data state.** Two percepts, two blocks, **two posts still carrying 0 regions** — the pair's
byte-stability is the corpus's most-verified fact and this scene must not be what breaks it.

**Failure.**
- **Any region, embedding or `vision_run` appears on either post.** These are the frozen rehearsal
  fixtures; mutating them corrupts the ability to replay runs 008–011.
- The product invents a cross-image answer it cannot evidence.
- The scene is recorded as "Atlas works".

---

## Cross-scene invariants

| # | invariant | why |
|---|---|---|
| I1 | **No `region_annotations`, `region_embeddings` or `vision_runs` delta in any scene.** | P1 is frontend-only; a delta means something wrote through an unexpected path |
| I2 | **A healthy circuit is silent.** No badge, tick or "verified" chrome anywhere. | degradation-only is the established discipline; noise is how honesty stops being read |
| I3 | **No cause is ever stated.** Absence, never explanation. | `resolveGround` knows only that an id is missing |
| I4 | **Reload changes nothing a curator can perceive.** | the Mention-reconstruction loss is invisible until it is not; this is the cheapest way to catch it |
| I5 | **No scene offers repair.** | repair is an open decision (§1), not a P1 feature |
| I6 | **Scene 5's two posts end byte-identical in `region_annotations`.** | they are the frozen fixtures for four completed runs |

## What these scenes deliberately do NOT test

Perceptive Orchestration (no operation path exists) · `suspect` (not built in P1) · durable Mentions ·
Atlas · Codex · `run_id` provenance · the announcement-only merge fix · anything requiring production
repair. **A scene that starts testing one of these has escaped its gate.**
