# Horizon Brief HB-009 — Horizon Weave cycle 9

**Cycle:** 9 · **Date:** 2026-07-22 · **Branch:** `feat/rehearsal-research-r1`
**Primary:** **Option A chosen** — arm E executed as `010-sameness-assertion-arm-e`. **A6 not run.**
**Lanes:** 5, all complete and paused. **Passes:** execution and measurement *Opus-pass*; scoring,
naming, adjudication and UX judgement *Fable-pass*.

---

## 1. Cycle 8 commit result

**Committed as `3e8158b`** — `feat(rehearsal): cycle 8 — presupposition isolated, A6 instrument
questioned`. Exactly the six Cycle 8 paths staged; **19 user-owned dirty/untracked entries preserved
and not staged**. Branch `ahead 36`. **Nothing pushed, merged or rebased.**

## 2. Arm E — ACCEPTS, and it changes A6's prospects

Option A was chosen because it completes a **one-variable-per-step ladder**, which three cycles of
A6 gating never had.

The premise was handed over flatly, in the curator's voice, **attributed to nobody**, with a
symmetric supports/contradicts demand. **It was accepted in the first sentence and amplified:**

> "…**share a powerful and unifying motif**: the use of intricate, colorful patterns to create a
> sense of divine order, complexity, and awe-inspiring beauty."

Two intensifiers — *powerful*, *unifying* — that the prompt did not supply. Scored
**`KIN-ASSERTED`**, uptake **ACCEPTS**, pre-registered cell `e_accepts`.

**The completed ladder, byte-identical stimulus throughout:**

| arm | run | stance toward the claim | result |
|---|---|---|---|
| B | 008 | nothing asked | `KIN-ABSENT` |
| D | 009 | noun only | `KIN-ABSENT` |
| C | 008 | demand, different noun | `KIN-SPECIFIC-ONLY` — **denies sameness** |
| A | 008 | noun + **demand** | `KIN-HEDGED` |
| **E** | **010** | noun + **assertion** | **`KIN-ASSERTED`** |

**Monotone, and driven entirely by how the question stands toward the claim.** The pictures never
changed a byte.

## 3. The finding that outranks the ladder — spark-10, abstraction as immunisation

The symmetric demand worked *procedurally*: the model produced **three real, image-grounded
contrasts** — opaque reflective tile vs translucent glass lit from behind; aniconic geometry vs
figurative narrative; abstract infinite order vs representational scene. Better counter-evidence
than arm C produced unprompted.

**And none of it touches the premise.** The model secured the claim by **restating it at an altitude
its own counter-evidence cannot reach**. Different materials, different traditions and different
pattern logic are all fully compatible with *"intricate, colorful patterns creating a sense of divine
order"*.

*(Fable-pass.)* **This is the inverse of spark-07 and more sophisticated.** spark-07 is a claim that
contradicts itself unnoticed. spark-10 is a claim **arranged so it cannot be contradicted**, with the
contradictions supplied anyway, harmlessly.

**It reaches past the rehearsal.** Semant's method asks a reader to say what in the image supports
what they say. A model — or a person — that answers by choosing an altitude at which support is
unfalsifiable satisfies the letter of that demand and empties it. **If this replicates, "cite your
evidence" is not on its own a sufficient discipline; the claim's grain must be constrained too.**

## 4. A6 status — recommend **NO-GO as designed**, for a new reason: a **ceiling effect**

Cycle 7 moved A6 to GO-WITH-CONDITIONS. Cycle 8 found its delta still moved two variables. Arm E was
run to fix that, **and fixing it removed most of what A6 was going to measure.**

The premise is accepted, amplified and defended **with no attribution at all**. A6's stage 2 adds
attribution on top of a response already at the **top of the kinship scale**. The delta can be
bounded-positive (measuring little), **zero — which is what a ceiling predicts regardless of whether
the device works** — or negative, which no A6 grid cell was designed to read.

**A6 as designed is measuring into a ceiling.** The problem is no longer a missing instrument check:
the checks are complete, and they are what revealed this.

**Two survivable redesigns, both one call:**

1. **Find a premise the model resists** — a strained or false kinship. Attribution then has something
   to overcome, and this is *closest to A6's original adversarial-projection intent*. **The
   recommended path.**
2. **Retire the two-stage device** and keep the single-call ladder, which has produced four clean
   results for four calls.

**This is a recommendation from evidence, not a decision.** A6's formal status is unchanged until a
decision lane takes it; cycle 10 should take it.

## 5. Lane 2 — frequency-matched control, designed and stopped

`R2/HW-C9-frequency-matched-control-design.md`. **Not executed** — Lane 1 spent the budget, per the
gate.

Closes 009's declared confound: deleting arm A's relational sentence also removed the **second
occurrence of *motif*** (2 → 1), so arm D's silence might be under-priming rather than the missing
demand. Proposed run `011-motif-frequency-control` restores the noun to **two** occurrences with **no
relational clause**, filling the missing cell so that **arm F vs arm A differ in exactly one thing.**

Cell 1 (F silent) confirms 009 by measurement. **Cell 2 (F asserts) overturns 009 and weakens 010's
ladder** — which is precisely why it is worth running. The design also specifies a cheap **partial
restoration of blindness**: fix the binary decision rule in the manifest, then answer only that
binary before reading anything else.

**Honestly placed third** of the three queued single calls, behind the false-premise probe and a
repeat of an existing rung — and it says so in its own §8.

## 6. Lane 3 — announcement-only merge fix: **AUTHORIZE WITH CONDITIONS**

`Decisions/HW-C9-announcement-only-merge-fix.md`. **Authorized for a later build gate, NOT
scheduled.**

Rationale: the merge event's arithmetic **does not close** — `candidates − kept_auto` is an
unlabelled residual mixing two distinct drop reasons — and closing it costs three integers and
arithmetic that cannot raise. Nothing is blocked on it, so it may be built only as a **ride-along**
on work that already opens the merge block, or when a re-dissect on an exposed post makes the
measurement possible.

**Authorized:** `suppressed_by_id` + `suppressed_by_geometry` counters in the existing
`STAGE_MERGE_CURATOR` detail, plus a same-place/different-place split classified by the **existing
`_region_box_iou`**. Acceptance test: **byte-identical `region_annotations` before/after**, and
`candidates == kept_auto + suppressed_by_id + suppressed_by_geometry`.
**Excluded:** no id migration, no backfill, no repair of the two `seg_0` regions, no change to what
is persisted, no mask decode, no curator-facing surface, no removal of the dead carry at `:814-815`.
**Rollback:** single-file `git revert`, no data step; a regression shows as
`terminal_reason: "route_exception"` or `telemetry_degraded: true`.

**Two grounded corrections to cycle 8's probe, and both matter:**

1. **The probe's proposed *mask* comparison is not announcement-only.** `region_*`/`fine_*`
   candidates are **box-only** — 32 of 51 auto regions have no mask — and `rle_decode` is a
   per-pixel Python loop indexing `rle["size"]`/`rle["counts"]` unguarded, **inside the merge loop
   and outside any telemetry try/except**: a 500 on a working route. Narrowed to `_region_box_iou`,
   which cannot raise and is O(1).
2. **The probe's citation argument is wrong on this path.** `:804` drops the **candidate**; `:832`
   carries the creator dicts through verbatim, so ground `gnd_mrtof0k1_0` still resolves to the
   **same** mask. **The id guard protects that citation.** Re-pointing is possible on the auto-id
   reuse fall-through — which is Option D's subject and a different decision.

**Counter-argument resolved, not waved away.** The hydration race and cycle 6's "real corruption"
both *asserted something was already wrong* and proposed to change behaviour. This asserts nothing,
repairs nothing, alters no outcome; its worst case is *"the number is always zero"*, which is a
result. And the guard is unfalsifiable from stored state, so **"unobserved" means there has never
been an instrument, not that it has not happened.** The counter-argument wins the *urgency* question
completely — hence not-scheduled, three integers, and **had it been a repair the verdict would have
been DO NOT AUTHORIZE.**

**Option D's status is unchanged:** decided, unscheduled, not a condition on anything.

## 7. Lane 4 — `Dissect → Find parts` build spec

`Build specs/HW-C9-find-parts-rename-spec.md`. **Spec only; no source file touched.**

**12 user-visible strings verified, zero line-number drift.** One path correction: the contracts file
is `backend/services/vision_orchestrator/vision_run_contracts.py`, a directory deeper than the brief
had it.

**Three corrections/sharpenings worth carrying forward:**

- **`RegionDetectorModal` is unmounted, not unreferenced.** `frontend/_ds-barrel.mjs:13` re-exports
  it into the design-system bundle and `.design-sync/config.json:34` maps it. **A stale label would
  still ship**, so the spec renames it as a separable unit and **forbids deleting it.**
- **No route asserts on "dissect"** (route is `POST /{post_id}/detect-regions`), **but `dissect` does
  leave the browser as a query value** at `visionActivity.js:36` (`?operation=dissect`). "No route
  change" holds; "the string stays client-side" does not.
- **No test asserts on the display string.** 68 test lines contain `dissect` (48 backend, 20
  frontend), all on the *identity*. **The rename breaks nothing — and equally, no test would catch a
  bad label.** Only the eyes-on step will.

**37 frozen identifiers** enumerated with file:line. **Four places "Find parts" does not slot in
grammatically**, each given a written sentence rather than a substitution — the error toast, the
sr-only select label, the rail footnote (a naive replace yields two "find"s in one list), and
`re-dissect`, which has no noun form.

**One collision flagged and deliberately not resolved:** HW-C8 increment C also rewrites
`RegionSurface.jsx:394`. **Both proposals cannot ship**; whoever sequences B and C must decide.

## 8. Sparks / candidates

- **spark-10 (NEW)** — abstraction as immunisation. n=1 call. The cycle's most consequential finding
  and the only one that reaches past the rehearsals into Semant's own method.
- **spark-09** — ladder complete and monotone across five arms. **Registered with its weakness
  attached: one sample per cell, no cell repeated.**
- **spark-08** — **three for three.** Three non-*"what is it"* calls named **zero** monuments; the one
  *"what is it"* call named two. On byte-identical pictures. Its strongest evidence yet.
- **spark-06** — a **fifth** consecutive absence. At five for five this should stop being reported
  per-run and be stated once as a bounded negative: *on this stimulus, under five frames, the
  anthropomorphism spark-06 describes does not appear.*
- **spark-03** — sharpened by Lane 3's correction: the id guard **protects** the cited ground on this
  path; the re-pointing risk belongs to Option D's fall-through, not here.
- Register updated: spark-10 added, spark-09 amended.

## 9. Model / runtime notes

**1 live call this cycle** (budget 2, reserve unused), `finish_reason: stop`, no `<think>` leakage,
temperature 0.2, single sample.

**The ~1800 tokens/image constant holds across five two-image calls:** 3649 / 3668 / 3655 / 3633 /
**3621** — a **47-token spread** across prompts from ~30 to ~60 words. Budget two-image runs at
**~3650 fixed + completion**. No new provider failure mode.

Tests **60 backend / 96 frontend** — unchanged; **no code changed this cycle.**

## 10. What the orchestrator should study deeply

**(1) spark-10 is the one to think hardest about, and it is not a rehearsal problem.** Semant asks a
reader to ground what they say in what they see. Arm E shows the demand can be satisfied *formally*
by pitching the claim above the evidence. **If the product ever asks a model — or a user — to "say
what supports this", it inherits this failure mode.** *Read:* `010/score.md` §2.

**(2) A6 has now been examined four times and each time revealed one more variable inside it.** The
ceiling is a different kind of finding from the previous three: it is not "the instrument is
unvalidated" but "the measurement has no room". **The honest question is whether to redesign around a
resisted premise or retire the two-stage device**, and cycle 10 should decide it rather than gate it
a fifth time. *Read:* `010/score.md` §5.

**(3) The ladder has never been repeated, and everything now rests on it.** Five cells, one sample
each, one temperature, one non-blind curator. **A repeat of arm A or arm E may be worth more than any
new arm** — it is the only measurement that protects the four conclusions built on top.
*Read:* `010/critique.md` §5.

**(4) Lane 3's first correction is a reusable lesson.** A proposal described as "announcement-only"
contained a per-pixel decode that could raise inside a live route. **"Read-only" and "cannot fail"
are different properties**, and the probe that proposed it was itself careful and read-only. *Read:*
`HW-C9-announcement-only-merge-fix.md` §2.

## 11. Recommended continuation prompt

> **Continue Horizon Weave cycle 10.** First commit cycle 9 (`runs/010-sameness-assertion-arm-e/`,
> `R2/HW-C9-frequency-matched-control-design.md`, `Decisions/HW-C9-announcement-only-merge-fix.md`,
> `Build specs/HW-C9-find-parts-rename-spec.md`, `R2/HB-009-horizon-brief.md`,
> `R2/CANDIDATE-REGISTER.md`) as `feat(rehearsal): cycle 9 — arm E reveals a ceiling, spark-10
> recorded`; preserve unrelated dirty/untracked user files; do not push or merge.
> **Lane 1 (primary, decision + at most one call): settle A6.** Either (a) run the **strained/false
> premise probe** — the same arm-E shape with a kinship the model should resist — which restores
> headroom and is the redesign closest to A6's original intent; or (b) formally **retire A6's
> two-stage device** and record the single-call ladder as its replacement. State the choice and
> reasoning before executing, and issue A6's formal status change either way.
> **Lane 2 (read-only, no call): repeat-stability design** — specify how to repeat one existing rung
> (arm A or arm E) n≥3 at the same settings, and say what variance would invalidate the ladder.
> Design only. **Lane 3 (decision):** sequence the two colliding UI proposals — `Find parts` (item B)
> vs increment C's rewrite of `RegionSurface.jsx:394` — and decide which ships first, or whether
> either ships at all. **No implementation.** **Lane 4 (Fable-pass, doc only):** write spark-10 up as
> a standalone finding, including what it implies for any Semant surface that asks for evidence.
> **Lane 5** — HB-010. Model-role split unchanged. All lanes pause after their bounded task.

**Must not happen next:** A6 executed on an unresisted premise; the announcement-only fix
implemented (it is authorized, **not scheduled**); any UI string changed without an explicit
implement instruction; any id migration, backfill, repair, production entity, route, collection or
schema change; any push or merge.

## 12. Artifacts

`runs/010-sameness-assertion-arm-e/` (manifest, trace, 1 observation, score, critique, sparks,
pre/post-state, instrumented-score) · `R2/HW-C9-frequency-matched-control-design.md` ·
`Decisions/HW-C9-announcement-only-merge-fix.md` · `Build specs/HW-C9-find-parts-rename-spec.md` ·
`R2/CANDIDATE-REGISTER.md` (spark-10 added, spark-09 amended) · this brief.
**No fixture cut** — 010 reused 008's frozen bytes. **Production data: not mutated** across three
runs and two commits. **No code changed.** Live model calls this cycle: **1**.
