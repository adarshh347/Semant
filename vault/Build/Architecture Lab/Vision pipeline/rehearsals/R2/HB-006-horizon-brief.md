# Horizon Brief HB-006 — Horizon Weave cycle 6

**Cycle:** 6 · **Date:** 2026-07-21 · **Branch:** `feat/rehearsal-research-r1`
**A decision cycle: no rehearsal executed, no model calls, no production writes.**
**Lanes:** 5, all complete and paused. Passes: verification *Opus-pass*; decisions *Fable-pass*.

---

## 2. Revised repair fork — **Option D: detect at the merge boundary, keep notify**

Cycle 5 showed notify-only is blind to false reattachment: a notification fires on
`detached === true`, but reattachment makes it `false`, so the guard is **affirmatively wrong while
working as designed**.

The revision's load-bearing argument is one no prior doc stated, verified at source: at
`posts.py:790-847`, `existing` (old regions, keyed by id) and `candidates` (new regions, each
already carrying its authoritative `mask_rle`) are **both in memory in the same function**, before
the wholesale `$set`. Same-id/different-mask is computable there for free. *(Fable-pass:)* every
other option pays to **reconstruct knowledge the merge site already holds and then discards** — the
Ground holds only a string, the client sees one generation, the DB keeps no history.

On `geometry_recovery.py`: **reuse the predicate, refuse the marker.** Wiring the module wholesale
would import HW-C4 §4b's rejected shape through the back door.

Implementation order for later, nothing authorized: observe at merge → stop the silent carry at
`posts.py:808-813` (the `actor == "creator"` promotion grants permanent re-dissect immunity on a
string match, and is the real corruption) → extend notify only if step 1 measures nonzero → revisit
id identity as its own decision.

**A cycle-6 correction to that decision.** The durable `detached: true` marker HW-C4 §4b rejected
**already exists in production** — on all four detached grounds, written by the F-series recovery
(`detached_reason: "region evidence absent after recovery"`), and **read by nothing**
(`resolveGround` recomputes from region presence). Today it is accurate. On an ordinal collision it
would go **stale and wrong**, giving the hazard a second silent victim. Nothing was cleaned up. The
decision's reasoning stands; it should just not be read as having kept the data clean.

## 3. Kinship/motif probe — designed as run `008-kinship-pull-ab`

Three arms, single stage, all stateless, one fixed image pair in fixed order in **every** arm — so
the pairing prime becomes a **held constant rather than a variable**. Arm A asks what **motif** each
carries; arm C is word-for-word parallel but asks how each is **put together**; arm B drops the
relational clause. **Only the noun varies.** Two-stage was rejected explicitly: a quoted analogy *is*
A6's instrument and would reproduce A6's five-sufficient-causes problem rather than close it.

Two fixture corrections, both from looking rather than labels:
- **`695be8ec` is not mirrored.** Left-vs-flipped-right mean abs luminance difference is **32.2**
  (a pixel mirror is ~0). `HW-L2` and `HW-C4` §3 both say "mirrored" and are wrong.
- **`695be815` carries a burned-in text overlay**, recorded nowhere previously — exactly what D1's
  visual check existed to catch. The crop excludes it.

The design **deliberately pre-spends A6's Pair 2** and freezes the fixture bytes, because using a
different pair would repeat A4's error a third time. **The running order is now forced: 008, then
A6, on identical bytes.**

## 4. External-claim audit of runs 001–006 — **do not retro-fill**

Per-run ledgers were reconstructed and the recommendation is to leave the old runs alone: hindsight
contamination is **asymmetric** — it inflates positives (the audit found 3 rows the run authors
missed) and does nothing for the negatives, which were the whole point — and editing six `score.md`
files would destroy 007's legibility as the convention's first voluntary adopter.

Notable rows: A4's **"the central mihrab niche"**, an attribution buried in a referring expression
that `score.md` never recorded; A3's **"the obscuring lace veil"**, a `frame-contradicts` already
falsified by that run's own critique; A5's seven rows including the hallucinated *"multiple cropped
views"* when one image was sent.

**Two structural catches that need acting on:** the convention's overturn test (three consecutive
empty ledgers) is **untriggerable as written**, because under a strict reading no ledger is ever
empty — it must key on a `kind` column. And a **`stimulus-contradicts`** value is needed for claims
settled by the frozen request record rather than by pixels.

*(Fable-pass, and the most interesting line in the audit:)* **claims cluster by question type, not
fixture fame.** Identity claims appear in exactly 1 of 6 runs — the only one asked an open *"what is
happening in this photograph?"*. That is the same shape as 007's question-conditional result. Two
independent findings now point the same way: **what the model imports depends on what it is asked,
not on what it is shown.**

## 5. A6 — **NO-GO now; GO-WITH-CONDITIONS once 008 reports**

The reattachment hazard is **discharged as a blocker**: A6 creates no Grounds and no Percepts, its
regions are curator-authored crops never persisted, so nothing it produces can be re-attached. The
brief's concern was the program's honesty posture, and that is satisfied by the hazard being
decided and scheduled rather than unknown.

**The blocker is kinship vocabulary, and it is decisive.** Running A6 now would reproduce **A4's
exact error at higher cost**: every cell of A6's grid — agrees, hedges, declines — is confounded by
an untested instrument, so none of them would carry information about which cause produced it.

Six conditions listed in `HW-C6-a6-go-nogo.md`. **Not** conditions: implementing Option D, cleaning
the durable flags, retro-filling old ledgers.

## 6. Sparks

No new sparks. spark-06 remains **RESOLVED** (address vocabulary only). **spark-08 gains
corroboration** from the audit's question-type clustering. spark-03 is unchanged but increasingly
entangled with evidence identity — §2's finding means the corpus now carries a marker that is true
today and could quietly become false.

## 7. Model / runtime notes

**No model calls this cycle.** One measurement worth keeping from 008's design: worst case 6050
tokens/call at the assumed 2400/image rule, ~3250 at 007's *measured* ~1000/image. **The
2400-vs-1000 discrepancy has never been settled**, and 008 logs arm B's `prompt_tokens` specifically
to settle it for the whole program. Until then, budget arithmetic across the batch rests on an
unverified constant.

## 8. What the orchestrator should study deeply

**(1) The forced order, and what it costs.** 008 pre-spends A6's only good pair. That is the right
call, but it means one stimulus now carries two runs, and if 008 lands in `NULL — CONFOUNDED` the
program has spent its best R12 fixture on an inconclusive instrument check. *Read:*
`HW-C6-kinship-pull-probe-design.md` §fixture conflict.

**(2) The convergence on question-conditionality.** 007 (address) and the audit (identity claims)
independently found that the model's importing behaviour tracks the *question*. If that generalises,
it reframes several sparks at once — including whether spark-08 is about citation at all, or about
prompt design. *Read:* `HW-C6-external-claim-audit-001-006.md` §pattern.

**(3) `posts.py:808-813`.** The revision names the `actor == "creator"` carry — not detachment — as
"the real corruption": a fresh auto region inherits permanent re-dissect immunity on a string match.
That is a live production behaviour nobody has audited. *Read:* `HW-C6-evidence-identity-decision.md`
§ordering, step 2.

**(4) That two devices remain untested.** A5's sycophancy control was never exercised (the model
never dissented), and A6's third-party analogy device inherits that. 008 does not test it either.

## 9. Next execution expectation

**Next primary: execute `008-kinship-pull-ab`** per its design, unmodified — after amending the
external-claim convention (`kind` column, `stimulus-contradicts`) so 008 and A6 share a ledger
shape. **Then** re-evaluate A6 against the six conditions.

**Must not happen next:** A6 before 008; implementing Option D or any merge-boundary detector;
cleaning the durable `detached` flags; retro-filling runs 001–006; any push or merge.

## 10. Artifacts

`Decisions/HW-C6-evidence-identity-decision.md` · `Findings/HW-C6-durable-detached-flag-already-in-production.md` ·
`R2/HW-C6-kinship-pull-probe-design.md` · `R2/HW-C6-external-claim-audit-001-006.md` ·
`R2/HW-C6-a6-go-nogo.md` · this brief. **No code changed; tests unchanged at 60 backend / 96
frontend.**
