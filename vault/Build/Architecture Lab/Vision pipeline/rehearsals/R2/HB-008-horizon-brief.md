# Horizon Brief HB-008 — Horizon Weave cycle 8

**Cycle:** 8 · **Date:** 2026-07-22 · **Branch:** `feat/rehearsal-research-r1`
**Primary:** **Option B chosen** — run `009-motif-noun-isolation` executed. **A6 was not run.**
**Lanes:** 5, all complete and paused. **Passes:** execution and measurement *Opus-pass*; scoring,
naming and adjudication *Fable-pass*.

---

## 1. Cycle 7 commit result

**Committed as `1f65327`** — `feat(rehearsal): cycle 7 — kinship pull resolves A6 instrument`.
20 files, **2261 insertions**, 7 deletions. Exactly the seven Cycle 7 paths were staged; **19
user-owned dirty/untracked entries preserved and not staged** (`.obsidian`, the rehearsals README,
writing plans, `AGENTS.md`, `audit-bundles/`, `new-planning/`, `scripts/_run_backend.py`, the 001
imports, `_Inbox/`, and the rest). Branch is `ahead 35`. **Nothing pushed, merged or rebased; the
save branch was not touched.**

## 2. Lane 1 — Option B chosen, and why

**Chosen: the fourth-arm probe, not A6.** The deciding reason: **B informs A, but A forecloses B.**
If the noun alone produced no kinship, then A6's stage-2 wording bundles two live causes and would
need redesign, not execution — and running A6 first would have spent the expensive run to learn
that. It also cost 1 call against A6's multi-call two-stage device, and A6's anchor (008 arm A) was a
single unreplicated sample.

**That is exactly what happened.**

### 009 result — THE PRESUPPOSITION CARRIES IT

Arm A's prompt with its **final sentence deleted and nothing else changed**, on byte-identical 008
fixtures. The model named a motif for image 1, a motif for image 2, and **made no cross-image
statement of any kind**. `KIN-ABSENT`.

**The 2×2 is now complete, with exactly one filled corner:**

| | no relational demand | relational demand |
|---|---|---|
| **without *motif*** | 008 arm B — `KIN-ABSENT` | 008 arm C — `KIN-SPECIFIC-ONLY`, **denies sameness** |
| **with *motif*** | **009 arm D — `KIN-ABSENT`** | 008 arm A — `KIN-HEDGED`, **asserts a shared motif** |

**Neither ingredient is sufficient alone.** 008's headline — *"the vocabulary drives it"* — was
right but too coarse.

**The sharpest single fact in the cycle.** Arm D wrote, of **image 2 alone**, *"intended to evoke a
sense of the divine"*. 008 arm A wrote, of **both together**, *"Both images share a fundamental
motif of creating a sense of the divine or celestial."* **Same phrase, same vocabulary — a property
of one picture in one arm, a bridge between two in the other.** The content was always available;
what the relational demand supplied was **the move of predicating it jointly**.

**1 live call** (budget 2, reserve unused), `finish_reason: stop`, replay 0 calls, both posts
unchanged on four comparisons, pre-state byte-identical to 008's post-state.

## 3. A6 status — GO-WITH-CONDITIONS holds, with one NEW residual

**Cycle 7's re-derived delta (008 arm A → A6 stage 2) SURVIVES** and is better anchored: a fresh
stage 1 without a relational clause would now be *predicted* to return `KIN-ABSENT`, which is a
floor, not a baseline. Arm A remains the right anchor.

**The new residual, newly visible:** arm A **demands** sameness (*"say which features these two
share"*); A6's stage 2 **asserts** it (*"the same motif rendered in tile and in glass"*, attributed).
A demand invites the model to go find something; an assertion invites agreement. **So the delta still
moves two things at once** — demand→assertion, and no-attribution→attribution.

**The fix is one call: arm E.**

> *"These two images share a motif. Say what in the images supports that, and what contradicts it."*

Arm E sits between arm A and A6's stage 2 and makes the **attribution device the only thing A6
changes**. It is now the highest-value single call available, displacing the fourth arm this cycle
spent.

**A6's status is unchanged and it was not run.** Its checklist should gain arm E, or state
explicitly that it accepts a two-variable delta.

*(Fable-pass, and the question to actually decide next.)* **Each cycle that examines A6 finds one
more variable inside it.** Cycle 6: the kinship vocabulary was untested. Cycle 7: the delta needed
re-deriving. Cycle 8: the sameness *move* is separable from the sameness *word*. That is either
convergence on a well-specified instrument, or evidence that A6's two-stage device bundles too much
to be measured by subtraction. **The honest question is no longer "is A6 ready" but "is A6 the right
instrument."**

## 4. Lane 2 — the OPEN `frame-contradicts` clarifier, DECIDED

`Decisions/HW-C8-frame-contradicts-clarifier.md`. Adopts the cycle-6 audit's proposed rule:

- **`frame-contradicts` requires the falsification be statable using the picture alone, with no
  imported premise.** Test: *could a reader who knows nothing about the subject verify it from the
  crop you supplied?*
- **`stimulus-contradicts` requires the frozen request record and nothing else** — manifest, trace,
  `image_sha256` list, prompt, `usage`. Cite the field.
- **Anything needing an external premise stays `frame-silent`.**

Under this rule the corpus has **2 clean `frame-contradicts` and 0 arguable ones**, so `HW-C5` §6.3
is **not triggered** — the status survives because it was narrowed, not because the corpus got
luckier. The two statuses never overlap: one impugns **the world in the picture**, the other **the
encounter itself**.

**Codification, not invention:** 008 and 009 both hit the boundary at the same place (*"likely verses
from the Quran"* — attributing a source, not quoting content) and **both resolved it this way before
the rule existed**.

**Declared cost:** the ledger will systematically under-count the model's errors. That is the right
trade — an under-counting ledger is recoverable; a ledger that has become a scoreboard of the
curator's art-historical opinions is not. **A low `frame-contradicts` count must never be read as the
model behaving well.**

## 5. Lane 3 — auto-ordinal probe: scope CONFIRMED NARROW

`Findings/HW-C8-auto-ordinal-curator-region-probe.md` (read-only; 0 writes).

**Whole corpus: 421 posts, 57 regions, 51 auto / 6 creator.**

| | count | |
|---|---|---|
| **EXPOSED** (creator region wearing a collision-capable ordinal id) | **2** | `695be8b0a9ea58f1b6aef606`/`seg_0`, `6a5b91ecbf74ef485d00399f`/`seg_0` — both genuine sam2 refine-in-place |
| **SAFE** (creator + uuid id) | 4 | `refine_c6485b9a94`, `refine_3e81b38e50`, `refine_5117cd9d1d`, `refine_747d7bc5cd` |

**Not broader than the two already known — confirmed corpus-wide.** The lane also verified `actor` is
the *only* marker conferring immunity (`posts.py:797`), so the probe is not missing an alternate
ownership signal.

**Corrections to the record, from reading the mint sites:** Cycle 5's `seg_{prefix}_{i}` shorthand is
inaccurate — it is `f"{id_prefix}_{i}"` at `adapters.py:68` with `id_prefix` defaulting to `"seg"`
and **no caller ever passing another value**. The `len()`-based forms (`arch_`, `fseg_`) are **not** a
safer class: they are dense 0..N-1 ordinals. And the mechanism that mints the exposure is
`adapters.py:191`, `base_id or f"refine_..."` — **a refine *with* a base keeps the base's ordinal
id.**

**Crowding is worst-shape, not best:** both exposed posts hold **exactly one region**, the curator
`seg_0`. Any re-dissect finding ≥1 mask collides on its **first, highest-confidence** detection.

**Has a collision already happened? No evidence, and one case affirmatively clean** —
`6a5b91ec…`'s recomputed `mask_hash` matches both embedding rows exactly. For `695be8b0…` there are
no embeddings and **the stored state cannot distinguish "collision happened" from "normal refine"**;
the lane says so rather than inferring.

**Two code facts that sharpen spark-03:** the id guard at `posts.py:804` fires **before** the
geometry dedup at `:826`, so a name-matched candidate is dropped **without its mask ever being
compared**, while a differently-named overlapping one gets a measured IoU check. And the merge
telemetry `{creator_preserved, kept_auto, candidates}` **has no field for an id-suppressed drop** —
it vanishes.

**New this cycle:** `695be8b0…`'s `seg_0` is cited by ground `gnd_mrtof0k1_0` and two curator percepts
(`pctx_mrtof46o_0` "arrow", `pctx_mrtofp6b_1` "fold"). **A collision would leave a ground that still
*resolves* — to different geometry.** That is the quiet inverse of the detached-ground failure
`f4d7b48` fixed: not evidence that vanishes, but evidence that silently changes what it points at.

**Minimal fix (NOT implemented):** at `:804`, compare the candidate's mask against the creator region
about to suppress it and **record the drop** (a `suppressed_by_id` count in the merge-stage detail at
minimum) instead of `continue`-ing silently. Announcement only — no stored geometry touched, no id
migration.

## 6. Lane 4 — UI increment scout

`Findings/HW-C8-ui-increment-scout.md`. **Report only; no source file was touched.**

**A — saver primary action. Feasible, and the crux resolves favourably.** The whole overlay is
`chrome-extension/content.js` (nothing saver-shaped exists in `frontend/`). **Content type is already
in hand at the decision point:** `showTarget(el, type)` receives `type` at `:465` and already calls
`findCarousel(el)` at `:480`, so single/carousel/video → Save / Save all / Split is computable inside
those 24 lines with **zero detection or plumbing**. *"Read with Aletheia"* is a live surface
(`brainstormImage()` `:792` → `POST /api/v1/posts/brainstorm` → the Unconcealment lens panel), not a
stub. Smallest gate: `content.js` + `content.css` only, ~10 lines in `showTarget`/`setToolbarMode`,
**reparenting the four existing button objects rather than merging them**, touching no handler and
none of the eleven `textContent` state writers. Two incidental findings: the comments at `:25`/`:130`
promise a summon shortcut that **does not exist**, and the extension is split between "Alexia" and
"Aletheia" inconsistently.

**B — rename `Dissect` → recommend `Find parts`.** 12 user-visible strings, all in `frontend/src`;
extension, dashboard and showcase have zero. **No URL path contains "dissect"** — the route is
`/detect-regions`, so there is no route risk. `RegionDetectorModal.jsx` is **orphaned** (nothing
mounts it). `Read parts` was **rejected** because `visionActivity.js:19-31` deliberately reserves
*reading* for `semantic_read` ("Interpretation only") against `dissect` ("Visual evidence produced")
— that label would lie. `Map image` was rejected because "map" is already the Quiet/Outline/Focus
view switch. **`Find parts` matches vocabulary the surface already uses in six places** and the
backend rail's "Saved parts". Frozen: `OPERATIONS`, all `EPISTEMIC`/`AFFECTS`/`STAGE_LABEL` keys,
`OPERATION_DISSECT` and `STAGE_*` in `vision_run_contracts.py:44-81`, routes, payload keys, DB fields.

**C — profile controls, with a correction to the brief.** **The YOLO/SAM controls are not
selectors** — `ProfileControl.jsx:84-91` renders `<span>`s with no handlers: a read-only readout of
`scheduled_passes` plus ready/deferred/unavailable state. There is nothing to hide behind
"advanced"; keep the model names verbatim (they are the only unavailable-model signal) inside a
collapsed disclosure. The chips are a **real capability switch** (`PATCH /domain-profile` →
`PROFILE_PASSES` → which detector adapters run). A **third** vocabulary the brief did not name: the
`MODES` select (`RegionSurface.jsx:17-24`) is a *prompt* vocabulary, not a detector — two look-alike
control rows 20 lines apart doing different things. Proposal: `Profile` → *"This image is"*; Fashion
→ **Clothing** (not "Garments", already taken twice), Architecture → *"Built space"*, Painting →
*"Painted surface"*, Auto → *"Sense it"*. **Honest risk:** not choosing a profile means those regions
**don't exist**, not "are hidden" — the `pc-reason` line at `:83` must survive as the honesty carrier.

**Ranking (value / risk): B → A → C.** B is near-zero-risk display strings. A has the highest user
value and stays bounded because the type is already available. C is mechanically safe but is **the
only one that can make the UI say something untrue**, so the honesty decision comes before code.

## 7. Sparks / candidates

- **spark-09 — REVISED and split.** The 008 formulation is retired as too coarse.
  **09a: the noun licenses the register. 09b: the relational demand licenses the joint
  predication.** Evidence is the one-filled-corner 2×2 above. Declared weaknesses: deleting the
  sentence also halved the noun's frequency (2 → 1), and the 009 curator was not blind.
- **spark-08 — CONTROLLED REPLICATION on identical bytes.** Two motif-framed calls named **zero**
  monuments between them; the one *"say what it is"* call named **two**. Because the pictures are
  byte-identical, the variance is attributable to the question alone. Cleaner than the cycle-6 audit,
  which compared across runs differing in fixture, budget and date.
- **spark-06 — a fourth recorded absence**, plus retroactive support for 008's one contestable
  adjudication: the model itself wrote *"the **viewer's** eye"*.
- **spark-03 — sharpened, not by new corpus damage but by mechanism**: the id guard suppresses
  without comparing, the telemetry has no field for the drop, and the exposed `seg_0` is cited by a
  ground and two curator percepts.
- Register updated: spark-09 rewritten, spark-08 upgraded.

## 8. Model / runtime notes

**1 live call this cycle** (budget 2, reserve unused). `finish_reason: stop`, no `<think>` leakage,
temperature 0.2, single sample.

**The ~1800 tokens/image constant holds across four two-image calls:** **3649 / 3668 / 3655 / 3633** —
a spread of **35 tokens** across prompts from ~30 to ~60 words. Image cost dominates and is stable.
**Budget two-image runs at ~3650 fixed + completion.** No new provider failure mode.

Tests **60 backend / 96 frontend**, unchanged — no code changed this cycle.

## 9. What the orchestrator should study deeply

**(1) Is A6 the right instrument, or should it be retired in favour of single-arm calls?** Three
cycles have each found one more variable inside it, and the last three findings all came from
**one-call probes** that cost a fraction of A6 and produced cleaner dissociations. An instrument
whose signal is smaller than the confounds around it is worth redesigning, not gating harder.
*Read:* `009/critique.md` §5.

**(2) The `seg_0` ground that would still resolve — to different geometry.** This is the most
concrete form spark-03 has ever had: a real post, a real ground, two real curator percepts, and a
guard that drops a candidate **without comparing masks** while logging success. It is the inverse of
the failure `f4d7b48` fixed. *Read:* `HW-C8-auto-ordinal-curator-region-probe.md` §spark-03
judgement. **The minimal fix is announcement-only and touches no geometry** — the cheapest honest
move available, and still unauthorized.

**(3) The ledger now under-counts on purpose, and someone must remember that.** Lane 2 narrowed
`frame-contradicts` deliberately. The failure mode is a future reader treating a clean ledger as a
clean model. *Read:* `HW-C8-frame-contradicts-clarifier.md` §§3, 5.

**(4) UI item B is unusually cheap and unusually safe** — 12 display strings, no route contains
"dissect", one of the three files is orphaned. If any UI work happens at all, this is the one with
the best ratio, and the argument against `Read parts` (it would contradict a distinction the code
already draws between *evidence* and *interpretation*) is worth reading in full, because it shows the
codebase already holds a position on what these words mean.

## 10. Recommended continuation prompt

> **Continue Horizon Weave cycle 9.** First commit cycle 8 (run `009-motif-noun-isolation/`,
> `Decisions/HW-C8-frame-contradicts-clarifier.md`, `Findings/HW-C8-auto-ordinal-curator-region-probe.md`,
> `Findings/HW-C8-ui-increment-scout.md`, `R2/HB-008-horizon-brief.md`, `R2/CANDIDATE-REGISTER.md`)
> as `feat(rehearsal): cycle 8 — presupposition isolated, A6 instrument questioned`; preserve all
> unrelated dirty/untracked user files; do not push or merge. Then: **Lane 1 (primary) — decide A6's
> fate, and run at most one call.** Either run **arm E** (*"These two images share a motif. Say what
> in the images supports that, and what contradicts it."*) on the frozen 008 bytes, which isolates
> A6's attribution device and makes A6's delta single-variable; **or** formally retire A6's two-stage
> device and record what replaces it. State the choice and the reasoning before executing.
> **Lane 2** — a frequency-matched control for 009's declared confound: repeat *motif* twice with no
> relational demand, one call, only if Lane 1 does not already spend the budget; otherwise design it
> and stop. **Lane 3 (read-only)** — decide whether the announcement-only merge-boundary fix at
> `posts.py:804` should be authorized for a later build gate; decision doc only, no implementation.
> **Lane 4** — take UI item **B** (`Dissect` → `Find parts`) from scout to a bounded build spec:
> exact file:line list, the frozen-identifier list, and a rollback note. **Spec only unless
> explicitly told to implement.** **Lane 5** — HB-009. Model-role split unchanged. All lanes pause
> after their bounded task.

**Must not happen next:** A6 executed before its delta is single-variable or its retirement recorded;
any merge-boundary detector, id migration, flag cleanup or backfill implemented in production; any
UI change beyond a spec without an explicit instruction; any production entity, route, collection or
schema change; any push or merge.

## 11. Artifacts

`runs/009-motif-noun-isolation/` (manifest, trace, 1 observation, score, critique, sparks,
pre/post-state, instrumented-score) · `Decisions/HW-C8-frame-contradicts-clarifier.md` ·
`Findings/HW-C8-auto-ordinal-curator-region-probe.md` · `Findings/HW-C8-ui-increment-scout.md` ·
`R2/CANDIDATE-REGISTER.md` (spark-09 revised, spark-08 upgraded) · this brief.
**No fixture was cut — 009 reused 008's frozen bytes.** **Production data: not mutated.**
**No code changed.** Live model calls this cycle: **1**.
