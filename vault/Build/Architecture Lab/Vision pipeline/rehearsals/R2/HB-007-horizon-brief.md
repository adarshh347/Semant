# Horizon Brief HB-007 — Horizon Weave cycle 7

**Cycle:** 7 · **Date:** 2026-07-22 · **Branch:** `feat/rehearsal-research-r1`
**Primary:** run `008-kinship-pull-ab` **executed** — the first live rehearsal since 007.
**Lanes:** 5, all complete and paused. **Passes:** execution and measurement *Opus-pass*; scoring,
delta re-derivation and judgement *Fable-pass*.

---

## 1. What happened this cycle, in one paragraph

008 ran and closed A6's residual exposure with evidence instead of argument. It landed in the
pre-registered **cell 1**: kinship vocabulary, *in a question*, is sufficient on this pair to
manufacture a shared-motif assertion, while the same pair under a construction frame denied sameness
and under no frame said nothing cross-image at all. On that evidence **A6 moved from NO-GO to
GO-WITH-CONDITIONS** — with a re-derived delta that is the cycle's real design change. The
external-claim convention was amended before 008 so 008 could apply it, and it paid for itself on
its first run. And the cycle-6 claim that `posts.py` promotes auto regions to `creator` was
**rejected by measurement** — it is unreachable dead code with zero corpus instances.

## 2. 008 result — cell 1, THE VOCABULARY DRIVES IT

Same two images, identical bytes and order by sha256 in every arm, co-presence and the symmetric
share/only-one-of-them demand **held constant**. Only the noun varied.

| arm | frame | the model's cross-image verdict | score |
|---|---|---|---|
| **B** | no relational clause | *(no cross-image statement at all)* | `KIN-ABSENT` |
| **C** | "how is it put together" | *"a distinct construction method"… "a different engineering principle"* | `KIN-SPECIFIC-ONLY` |
| **A** | "what motif" | *"Both images share a fundamental motif of creating a sense of the divine or celestial"* | `KIN-HEDGED` |

`(a=kin, c=no-kin, b=no-kin)` — the direct analogue of 007's `a_face_b_none`, in the kinship
register. **The kinship is in the question**, and arm C is the load-bearing proof: it had the pairing
and the symmetric demand and still refused sameness, so the noun is the only surviving explanation.

**3 live calls of a budget of 4; reserve unused. All three `finish_reason: stop`.** Both posts
verified unchanged on four comparisons (key set, lengths, `updated_at` to the millisecond, collection
counts). Replay: 0 calls, key absent.

**HW-L4 §4.5 pre-registered the hedge — *"a shared human urge toward the celestial"* — before any of
this ran. The model produced *"a sense of the divine or celestial."*** The program predicted its own
result almost word for word.

## 3. Kinship/motif pull finding — and its two live implications

**The finding (spark-09):** relational vocabulary is an attractor; the noun is the variable. Sibling
to spark-06 (address). Two relational vocabularies now show the shape.

**Implication 1 — A6's delta is re-derived, and this is a design change, not a note.** A6's baseline
is no longer a fresh stage 1; it is **008's arm A**. Arm A already spends the kinship vocabulary
*without* any third party, so A6's delta becomes **(arm A → stage 2)**, and any movement beyond arm
A's hedge is attributable to the **third-party attribution device** — the only thing A6 was ever
built to measure and the one thing 008 could not test. Full re-derivation and the three
pre-registrable readings are in `HW-C7-a6-reevaluation.md` §2.

**Implication 2 — the declared confound was refuted in the informative direction.** 008 §8.1
predicted arm A's *motif* vocabulary might also inflate attribution. The opposite happened: the
**floor arm** produced the most external claims and the only two monument names (Shah Mosque,
Sainte-Chapelle); arm A named none. So arm A's kinship cannot be explained away as "arm A imported
more outside-frame material." It imported less.

## 4. Actor-carry audit — cycle 6's "real corruption" is REJECTED

`Findings/HW-C7-actor-carry-audit.md` (Opus-pass, read-only, 0 writes).

- **Code: unreachable dead code.** The `continue` guard (`posts.py:804`) and the `actor` carry
  (`814-815`) key off the same list under the same equality, so if the carry could fire the
  `continue` already did. Verified by a **6813-case brute force → 0 firings**. It was live and
  unguarded for eleven days (introduced `153d469`, incidentally shadowed by C5's `00b71c5`); it is
  vestigial, not malicious — superseded by whole-region preservation.
- **Corpus: 0 observed.** 127 posts, 10 with regions, 43 regions: 37 `auto`, 6 `creator`, 0 missing.
  All 6 creator regions carry genuine `sam2-refine` provenance. A promotion would keep its auto
  `detector`, giving a clean discriminator; **zero hits**.
- **Minimal fix (not implemented):** delete `posts.py:814-815`. Two lines, no behaviour change.
  **Must not be reported as closing the identity hazard** — that still needs Option D.

**The one thing the audit flags is not the carry.** Two curator regions hold the auto ordinal
`seg_0` (`695be8b0a9ea58f1b6aef606`, `6a5b91ecbf74ef485d00399f`) — genuine refine-in-place upgrades,
**not** promotions. But they are Cycle 5's collision surface loaded: a re-dissect regenerating
`seg_0` would have its new detection silently dropped by the `continue` guard in favour of the older
curator mask, logging `creator_preserved: 1` as success. The carry would have corrupted *authorship*;
the guard that killed it corrupts *reference*. **Same root cause: identity by positional ordinal,
trusted across runs** — spark-03's territory, not A6's.

## 5. A6 status — GO-WITH-CONDITIONS

Upgraded from cycle 6's NO-GO. `HW-C7-a6-reevaluation.md`, superseding `HW-C6-a6-go-nogo.md`.

Three of six conditions **satisfied** (008 ran, 008 is interpretable, convention amended); three
**carried** as obligations A6 discharges in its own manifest (reuse frozen bytes; record the two
fixture corrections; state its bounded exposure). **No condition failed and no further measurement is
required before A6 runs** — every remaining item is doc-level. The nine-point checklist A6 ticks is
in the re-evaluation §4.

**Not conditions:** implementing Option D, deleting the dead carry, cleaning the durable `detached`
flags, retro-filling ledgers 001–006.

## 6. Amended external-claim convention

`Decisions/HW-C5-external-claim-convention.md` §9, doc-only, made **before** 008.

- **The overturn test now keys on the `kind` column** (audit resolution (a)). "Three consecutive
  empty ledgers" was untriggerable because every run carries a low-grade `material`/`period` band; it
  now reads "three consecutive runs with **no identity-reaching row**." A ledger of only
  material/period/other counts as a **negative**, and the run must say so.
- **`stimulus-contradicts` added** as a third frame-status value, for a claim the **frozen request
  record** falsifies (A5's *"multiple cropped views"* when one image was sent) — distinct from
  `frame-contradicts`, which the pixels falsify.
- **`kind` gained `material` and `period`.** Column count unchanged; §4.5's "must not grow" respected.
- **`frame-contradicts` §C3 clarifier left OPEN**, deliberately: the gate authorised two amendments.

008's ledger — 13 rows, **6 identity-reaching / 7 low-grade**, 0 contradictions — is the amendment's
first exercise, and it is exactly the split the old wording could not see.

## 7. Sparks / candidates

- **spark-09 (NEW):** relational vocabulary is an attractor; the noun is the variable. n=1 pair.
  Sibling to spark-06.
- **spark-08:** upgraded from "n=1" to **corroborated**. 008 reproduced the cycle-6 audit's
  question-type clustering *prospectively and on identical bytes* — the "say what it is" arm named
  both monuments; the motif and construction arms named none. Still a spark (one run, side
  observation), but no longer standing on A5 alone.
- **spark-06:** unchanged (resolved, address vocabulary). A **recorded negative** added: a symmetric,
  cell-dense, frontal ornament produced no face under three frames; HW-L4's four face predictions did
  not occur.
- **spark-03:** unchanged by 008 (which wrote nothing), but the actor-carry audit sharpens its
  territory — the live hazard is `seg_0`-style ordinal collision on annotated posts, a **reference**
  failure, and the merge-boundary check (Option D) remains the only proposal that would catch it.
- Register table and spark-09 section updated in `CANDIDATE-REGISTER.md`.

## 8. Model / runtime notes — the 2400-vs-1000 question is SETTLED

Arm B's `prompt_tokens` = **3649** for two images + a ~45-word prompt ≈ **1794 tokens/image**.
**Both prior estimates were wrong:** the stated 2400/image rule was over-cautious (predicted ~4860),
and the ~1000/image figure extrapolated from 007 was an underestimate (predicted ~2060). The three
arms agree to within 19 tokens despite very different prompt lengths, so **image cost dominates and
is stable**: budget two-image runs at **~1800/image (~3650 fixed) + completion**. Worst case here was
4680 total against the 8000 TPM ceiling.

The §6 stop condition was honoured **mechanically**: arm B was captured and its `prompt_tokens`
inspected in a scratch run-root *before* C and A were sent, then adopted via `reuse_frozen` (0
re-calls) — so a reading over 6900 would have halted with two calls unspent. No new provider failure
mode this cycle; no `<think>` leakage; temperature 0.2, single samples, within-arm variance
unmeasured.

## 9. What the orchestrator should study deeply

**(1) The re-derived A6 delta, and whether it is worth running at all.** 008 already spent the
vocabulary. A6 now measures only what the *third-party attribution* adds over arm A's hedge. If the
orchestrator's read is that the attribution device is low-value, the honest move may be to run the
**fourth arm instead** (noun without presupposition, one call) and retire A6's two-stage device —
the gate's own logic ("the remedy for a five-cause observation is not to run it earlier") points that
way. *Read:* `HW-C7-a6-reevaluation.md` §2 and 008 `critique.md` §6.

**(2) The `seg_0` collision surface is now concrete, with named victims.** Two real curator regions
carry an auto ordinal today. The audit shows the carry that cycle 6 feared is dead, but the *guard
that killed it* has the same failure by reference. This is the strongest, most grounded form spark-03
has ever had — an actual post id, not a synthetic probe. *Read:* `HW-C7-actor-carry-audit.md` §5 and
the §3 note in HB-006. **Option D is the only proposal that addresses it; it remains unbuilt and
unauthorized.**

**(3) The convergence on question-conditionality now has three independent lines.** 007 (address),
the cycle-6 audit (identity claims across six runs), and now 008's floor arm (both monuments named
under "what is it", none under "what motif"). If this generalises it reframes spark-08 from "the
model invents citations" toward "the model's importing tracks the question" — which is a claim about
**prompt design**, and it bears directly on every instruction the product would ever put in front of
a VLM. *Read:* 008 `sparks.md` spark-08.

**(4) Two devices are still untested, and A6 does not fix that.** A5's sycophancy control never fired
(the model never dissented); A6's third-party analogy device inherits that gap; and 008 tested
neither. A6's re-derived third reading (stage 2 *falls short* of arm A) would be the **first** chance
in the program to see the sycophancy control fire — worth designing A6 to make that outcome legible
rather than treating it as noise.

## 10. Recommended continuation prompt

> **Continue Horizon Weave cycle 8.** 008 landed in cell 1 and A6 is now GO-WITH-CONDITIONS with a
> re-derived delta (baseline = 008's arm A, not a fresh stage 1). Before committing to A6's two-stage
> device, decide between two primaries and run exactly one: **(A6)** execute A6 per the nine-point
> checklist in `HW-C7-a6-reevaluation.md` §4, reusing 008's frozen bytes, measuring its delta against
> arm A; **or (fourth-arm)** run the single-call fourth arm (*"say what motif each image carries"*,
> no relational clause) that separates the noun from the identity presupposition, and reconsider
> whether A6's attribution device is worth its cost. State which you chose and why. Keep the
> read-only side-lanes: (1) decide the OPEN `frame-contradicts` §C3 clarifier in the amended
> convention; (2) a read-only probe of whether any *other* corpus posts carry auto ordinals on
> curator regions beyond the two `seg_0` cases the actor-carry audit found. Model-role split
> unchanged. All lanes pause after their bounded task. **Do not** implement Option D, delete
> `posts.py:814-815`, clean the durable `detached` flags, retro-fill ledgers 001–006, or push/merge.

**Must not happen next:** A6 before its checklist is ticked and its delta re-derived against arm A;
any merge-boundary detector, dead-code deletion, flag cleanup or backfill implemented in production;
any production entity, route, collection or committed frontend surface; any push or merge.

## 11. Artifacts

`runs/008-kinship-pull-ab/` (manifest, trace, 3 observations, score, critique, sparks, source-notes,
pre/post-state, instrumented-score) · `fixtures/008-kinship-pull-ab/` (2 frozen fixtures + 1 parent
reference) · `Decisions/HW-C5-external-claim-convention.md` (amended §9) ·
`Findings/HW-C7-actor-carry-audit.md` · `R2/HW-C7-a6-reevaluation.md` ·
`R2/CANDIDATE-REGISTER.md` (spark-09 added, spark-08 upgraded) · this brief.
**Production data: not mutated.** Tests: **60 backend, 96 frontend** (unchanged; no code changed).
Live model calls this cycle: **3**.
