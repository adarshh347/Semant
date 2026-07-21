# Horizon Brief HB-004 — Horizon Weave cycle 4

**Cycle:** 4 · **Date:** 2026-07-21 · **Branch:** `feat/rehearsal-research-r1`
**Primary:** A5 executed (R9 Narrative Overreach) · **Lanes:** 6, all complete and paused.
**Passes:** execution *Opus-pass*; interpretation, clause partition and synthesis *Fable-pass*.

---

## 2. A5 result — the overreach was accepted, and the *untempted* stage was worse

**Stage 2 (tempted)** endorsed all three clauses of *"the figure's grief radiates through the whole
rotunda"* — *"well-supported by the image"* — against a partition **pre-registered before any call**
as supported / **leap** / **leap** / supported. R9's intended outcome did not occur.

**Stage 1 (untempted) is the real finding.** Asked only what is happening and what the photograph
does *not* permit, the model volunteered a title, a sculptor, a date, an institution — and quoted a
scriptural inscription, writing that it *"confirm[s]"* the location.

**That inscription is not in the photograph.** Verified from the pixels at 6× upscale: the medallion
is a coloured figural mosaic with a fragmentary **non-English** band. The model manufactured a piece
of documentary evidence and cited it.

*(Fable-pass.)* This reframes R9. Narrative overreach is not only a sentence going further than the
picture — it is **the evidence base silently growing to meet the sentence**. The grief reading was
never a bare projection from posture; by stage 1 it was already braced by a fabricated chapel, a
fabricated sculptor and a fabricated scripture.

**The reclassification guard fired, in a worse form than designed for.** The manifest anticipated
"retrieves a title and reasons from it." What occurred looks like **invention treated as
evidence** — though `critique.md` records honestly that distinguishing *confabulated* from
*real-but-misapplied* would need external lookup this rehearsal deliberately did not perform.

**And the model contradicted itself inside one response:** having asserted *"Paul Manship, 1921,"*
its own *what the photograph does not let you say* section states the image cannot determine
sculptor or year. The guard section was answered **correctly and had no authority** over what
preceded it.

## 3. A6 decision status — **GO WITH CONDITIONS**

D1 = generous crops, **plus a new fifth score value `DECLINED-ON-INSCRIPTION`** (a script-only
refusal — "Arabic script ⇒ Islamic ⇒ unrelated" — would satisfy the old criterion while never
looking at the ornament). D2 = two-stage with stage-1 wording frozen in the manifest and
**word-boundary matching**, because A4's guard failed on "sur*face*". D3 = curator facts must be
descriptive and must never contain the verdict. D4 = Pair 2; **the contingency is discharged**
because A4 consumed `695be784`, freeing `695be8ec`. D5 = `max_tokens` raised 800 → 1100, with a
live check.

**"Expected refusal" should be CORRECTED NOW.** A2, A3, A4 and now A5 all record *"refusal — none
occurred"*. A6 was carrying the batch's ≥2-refusals criterion on a prediction the batch's own
evidence contradicts.

**The gate also disputes A4's spark-06 narrowing, correctly.** A4 changed *two* variables: the
prompt frame **and** the aperture configuration. A3's structure had **paired lateral windows**;
A4's wall has **one central opening** — eyeless by construction, so it might have produced no face
under either prompt. **spark-06 should read UNRESOLVED, two competing narrowings.** This matters
because the muqarnas hood is the paired-aperture condition in its most extreme corpus form, so A4
gives A6 no protection. The resolving test is cheap: an A/B on `695be843`, the image that already
produced the face.

## 4. Hydration race — **REJECTED**

Two scouts named it "the single most likely killer"; measured, **it does not exist**. `regions` and
`grounds` have one writer each, written in the same synchronous effect body, batched into one React
19 commit, and every consumer reads both from the same memo. Four probes — mount, post-switch,
recall forced at the earliest microtask, `StrictMode` double-invoke — returned **0 asymmetric
passes, 0 false-detach passes**.

**A2R's "Detached evidence" note cannot show a transient false positive**, for four independent
reasons. What does exist is weaker and worth naming: one commit where the store is *uniformly
empty* — a collapsed frame, not a stale one, and with `grounds === []` there is nothing to resolve.

*(Fable-pass.)* This is the cycle's most valuable negative result. Two independent scouts inferred a
bug from code shape; one measurement dissolved it. **Inference from reading is not evidence.**

**Found incidentally and NOT fixed:** `fetchPost` has no abort/sequence guard, so rapid A→B→A
navigation can land the wrong post. Cannot cause false detachment — only a wrong page.

## 5. Repair fork — **notify, not tombstone** (status: proposed)

The decision agrees with the orchestrator's position but **rejects its stated reason**, and the
correction is worth reading: tombstone-vs-notify is largely a *wording* problem — either can be
worded humbly or arrogantly. The load-bearing difference is that **a notification is speech about
state; a tombstone changes state.** `resolveGround`'s boolean is behaviour, not display: flip it and
`GroundLayers` draws, `groundBBox` returns a box, `recall.js`'s `isResolved` passes — **a tombstone
would silently re-arm exactly what A2R disarmed, with no code change and no failing test.**

**Two new code-read findings changed the analysis:**
1. **Tombstoning cannot repair the motivating case.** `detect-regions` persists via one wholesale
   `$set`; there is no history or archive. `fine_0`/`fine_3`'s masks are gone. Tombstone is
   prospective-only.
2. **Region ids are positional ordinals** (`fine_{i}`, `arch_{len}`). A re-run of the fine pass on
   `695be786` would emit a `fine_3` again and `resolveGround` would **silently re-attach** the
   detached ground to an unrelated shape — fabricated provenance with zero code. **This is arguably
   more urgent than detachment**, because false re-attachment is silent and confident.

## 6. Seed-supply request

One page, actionable: ~20 photographs and 3 books. Lead ask unchanged — **a photograph of ordinary
people in ordinary space**, the only honest route to R7 and the missing control for the
anthropomorphism defect. Books: a real **Casey** monograph, **Warburg's *Mnemosyne*** method,
**Didi-Huberman *Confronting Images***. Stated plainly so the user does not helpfully supply the
wrong thing: **Lacan is not wanted yet.**

## 7. Sparks — added and changed

**New spark-08 — the evidence base grows silently to meet the claim.** Semant's Grounds can only
point *inward*, at this image. There is no way to mark a reading as licensed by something **not in
the frame**. When that licence is false, the percept looks exactly like a grounded one. It is the
inverse of spark-01.

**spark-07 STRENGTHENED.** A4 found the claim/counterexample split across two calls, explicable by
statelessness. A5 found it **inside a single response** — that explanation is now unavailable.

**spark-06 → UNRESOLVED** (§3), reverting A4's confident narrowing.

Unchanged: spark-01, spark-02, **spark-03 (still strongest)**, spark-04, spark-05.

## 8. Model / runtime notes

- Two single-image native-resolution calls: 2515 and 2303 tokens with `max_tokens: 1200`. The third
  budgeted call was reserved for provider failure and **not used**.
- **New failure mode: the model hallucinated its own stimulus** — stage 2 cited *"multiple cropped
  views"* and *"the top crop"* when **one** image was sent. Any multi-image rehearsal must not trust
  the model's account of *which* image it is discussing.
- Decorative scaffolding continues (headers, ✅/⚠️, "Final Assessment"). Harmless only because raw
  text is frozen and never parsed.
- Note for the record: the hydration probe cited `server-exit-144` as blocking a browser check. That
  blocker no longer applies — backend :8000 and vite :5173 have been running all cycle.

## 9. What the orchestrator should study deeply

**(1) spark-08, and what it implies about citation.** A5 is the first run where the model's error
was not over-reading but **importing**. Every Semant construct points inward. *Read:* `006/score.md`,
`006/sparks.md`.

**(2) The positional-ordinal re-attachment hazard.** A silent, confident false re-attachment is
worse than a silent detachment, and it needs no new code to occur — only a re-dissect. *Read:*
`Decisions/HW-C4-detached-evidence-repair-fork.md` §findings.

**(3) That spark-06 is unresolved and A6 has no protection from A4.** The `695be843` A/B is two
cheap native calls. *Read:* `HW-C4-a6-decision-gate.md` §synthesis.

**(4) The rejected hydration race as a methodological lesson.** Two scouts, independently, inferred
a bug from code shape; measurement dissolved it. Weigh future scout inferences accordingly.

## 10. Next execution expectation

**Next primary: the `695be843` A/B** (two cheap native single-image calls, address-framed vs
structure-framed, declared as replication) — it is A6's stated precondition and resolves spark-06.
**Then A6** under the gate's checklist.

**Must not happen next:** A6 before the A/B or an explicit written waiver; any repair, tombstone or
backfill of the four detached grounds; any production entity, route, collection or committed
frontend surface; any push or merge.

## 11. Artifacts

`runs/006-narrative-overreach/` (manifest, trace, 3 observations, score, critique, sparks,
source-notes, pre/post-state for **both** ids, instrumented-score) ·
`fixtures/006-narrative-overreach/` (+ `_medallion-x6.png`, the falsification evidence) ·
`R2/HW-C4-a6-decision-gate.md` · `R2/HW-C4-seed-supply-request.md` ·
`Findings/HW-C4-hydration-race-probe.md` · `Decisions/HW-C4-detached-evidence-repair-fork.md` ·
`R2/CANDIDATE-REGISTER.md` (spark-08 added, 07 strengthened, 06 → unresolved) · this brief.
Tests: **57 backend, 96 frontend**.
