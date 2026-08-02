# Horizon Brief HB-005 — Horizon Weave cycle 5

**Cycle:** 5 · **Date:** 2026-07-21 · **Branch:** `feat/rehearsal-research-r1`
**Primary:** run `007-anthropomorphism-ab` executed · **Lanes:** 6, all complete and paused.
**Passes:** execution *Opus-pass*; design, scoring and synthesis *Fable-pass*.

---

## 2. The A/B — spark-06 RESOLVED, decisively

Same image. Identical 768 px stimulus, verified by sha256, in both arms. Same model,
`reasoning_effort`, `max_tokens`, call shape. Both arms stateless. **Only the question differed.**

| arm | the same lamps flanking the spire were called… |
|---|---|
| **A — address-framed** | *"glowing **eyes**"*, *"**face-like** frontality"*, *"almost **facial** architecture"* |
| **B — structure-framed** | *"**light fixtures**"*, *"mirrored placement"*, *"visual anchors"* |

*(Fable-pass.)* **The face is not in the photograph; it is in the question.** Nothing about the
pixels changed between arms — only what was asked of them.

This is the pre-registered `a_face_b_none` cell, and it **supersedes A4's narrowing by evidence
rather than argument**. A4 reasoned from a *negative* result on a *different* image that may have
lacked the triggering feature; this reasons from a *positive* result in one arm and a *positive
non-face* reading in the other, on **the one image known to produce the behaviour**.

**Scope, stated narrowly on purpose:** address vocabulary is **sufficient** to elicit
anthropomorphism; the image alone is not. **Not** resolved: whether *kinship* or *motif-similarity*
vocabulary pulls the same way — which is precisely what A6 asks. A6 gains a real but limited
protection: avoid address vocabulary; do not read this as clearance for A6's actual question.

**Secondary result worth keeping:** arm A reproduced A3's face at 768 px in a *single-image* call,
where A3's original was 256 px inside a *three-image* comparison. A3's finding was therefore **not**
an artifact of downscale degradation or comparison context. A failed replication here would have
quietly undermined A3 and nobody would have gone back to check.

**Model calls:** 2 of 2. Latency 1681.8 / 1516.0 ms; 2018 + 2004 tokens; both `stop`, no `<think>`
leakage. **Replay: 0 adapter calls, 0 sockets, key absent.** **Post `695be843` unchanged.**

## 3. A6 plan correction — applied

`R2-batch-operating-plan.md` edited in place. A6's row now reads that **no refusal is expected**,
quoting the withdrawn prediction inline so the correction is legible *as* a correction. The
load-bearing clause survives: **A6 does not count toward the batch's ≥2-stalls-or-refusals
criterion**, which now rests on A5 and later runs, and if unmet must be **recorded as unmet rather
than satisfied by reinterpreting a hedge**.

A methodological note was added: **A2, A3, A4 and A5 each predicted or permitted a refusal; all four
`score.md` files record "refusal — none occurred." Four for four.** A refusal written into a plan is
a hypothesis, never a count that can be banked in advance.

Three binding warnings were added for A6 — A3 (address without a body), A4 (unresolved via the
two-variable confound), A5 (evidence can be fabricated). **A6 was not run and is not marked ready.**

## 4. The positional-id hazard — REAL, and it breaks the repair decision

**In code: PARTIALLY POSSIBLE (pass-specific).** Four of five id sites emit per-run ordinals —
`fine_{i}`, `seg_{prefix}_{i}`, `arch_{len}`, `fseg_{len}`. Only `refine_*` escapes, and **not**
because it is content-derived: it is a random uuid4 slice, safe by non-collision rather than by
design.

**In corpus: UNDETERMINABLE.** No history exists — zero `region_history`/`superseded` docs, one
`vision_runs` doc (on an unrelated post), and dissect telemetry records counts, never ids. A check
of `region_embeddings` for same-id/different-hash pairs found four matches, **all four artefacts of
empty `mask_hash`** — no genuine reuse evidence. Two posts hold live `fine_0…fine_8`, so a fine
re-run on `695be786`/`695be794` would very likely regenerate `fine_3`/`fine_0` — flagged as
inference, not observation.

**Can it fool `resolveGround`? Yes** — demonstrated with a synthetic probe against the real,
unmodified `grounds.js`: a ground travels resolved → detached → **resolved to a different shape**
("hair" → "gravel", geometry moved), silently.

**Does notify-only handle it? NO — and this is the cycle's most consequential finding.** Every
notification the repair decision contemplates fires on `detached === true`. **Re-attachment makes
`detached` false, so no notification ever fires.** The notification is not merely absent — it is
*affirmatively wrong while working exactly as designed*.

*(Fable-pass.)* The decision's own strongest anti-tombstone argument was that a tombstone would
re-arm A2R's disarmed behaviour "as data, with no failing test." **Ordinal reuse produces the
identical regression by the identical route — without anyone choosing tombstoning.** The doc names
the mechanism in passing but its chosen option gives it **zero** coverage. Also found:
`geometry_recovery.py:153` already implements the exact same-id/different-mask check and **is wired
to no router**; the dissect route never reads `post.grounds`.

## 5. External-claim convention — ADOPT NOW, in reduced form

A markdown-only `## External claims` ledger in `score.md`, standing for R2 runs from the next one
onward. **No schema change** — `instrumented-score.schema.json` has `additionalProperties: false`,
so a field would be a real change, and an optional field would make `0` indistinguishable from
absent, destroying the negative-evidence property that justified adopting at all.

The reduced shape improves on the brief in two ways worth noting. The brief's four categories
collapse to **two frame-status values**, because distinguishing *true-and-sourced-externally* from
*invented* requires the external lookup A5 correctly refused. And "speaker-flagged" becomes an
**orthogonal column with a `contradicted` value** — because A5 flagged the limit *and* asserted the
claim in the same response, and an exclusive taxonomy would have made spark-07's central finding
unrecordable. A5's inscription gets a value the brief lacked: **`frame-contradicts`**, the only cell
a rehearsal can settle on its own authority.

Run 007 is the **first voluntary adopter** — its ledger records three `frame-silent` claims and no
contradictions.

## 6. Seed intake — what to gather first

12 image categories with good/bad guidance, counts and priorities; six HIGH. Lead ask unchanged: **a
photograph of ordinary people in ordinary space** (3+, no artistic intent) — the only honest route
to R7 and the missing control for the anthropomorphism defect.

The pack's real contribution is the **intake policy** the earlier request lacked: a
`vault/_Inbox/seed-intake/` layout with numbered category folders, a
`<cat>-<slug>-<YYYYMM>-<nn>.ext` filename convention, a **four-field sidecar** (`where / when / what
/ unknown`), and a three-rule duplicate policy — the corpus already carries a byte-identical pair
and ~79 near-duplicate carousel siblings.

Texts: Casey, Warburg's *Mnemosyne*, Didi-Huberman now; Heidegger and Barthes later. **Lacan
explicitly not wanted yet.** Slices only — a theme plus locator, never the passage.

## 7. Sparks

**spark-06 → RESOLVED** (address vocabulary; kinship vocabulary explicitly out of scope).
**spark-08** unchanged but now has an adopted recording convention — its stated next move is done.
Unchanged: 01, 02, **03 (still strongest, and now complicated by §4)**, 04, 05, 07.

## 8. Model / runtime notes

- Two single-image 768 px calls: 2018 and 2004 tokens at `max_tokens: 1000`. Comfortable.
- **The runner refused an invalid manifest before spending any budget** — `seed_constellation`
  requires `texts` and `existing_percepts`; the first attempt cost one cycle and **zero model
  calls**. Evidence that validate-then-capture is doing real work.
- No new provider failure modes this cycle.

## 9. What the orchestrator should study deeply

**(1) The repair decision is now insufficient, and it is the third cycle open.** Notify-only cannot
see re-attachment, because re-attachment looks like health. The decision needs revisiting *before*
any notification work begins — building it now would ship a guard that is silent exactly when it
matters. *Read:* `Findings/HW-C5-positional-id-reattachment-probe.md` Q4.

**(2) `geometry_recovery.py:153` already contains the needed check and is wired to nothing.** That
is a strange and useful fact: the detection logic exists, unused, in the codebase. *Read:* the probe
report's code section.

**(3) A6's residual exposure is kinship vocabulary, not address.** The A/B closed one door and
explicitly did not close the other. *Read:* `007/score.md` §"What this means for A6".

**(4) The four-for-four refusal record.** The batch has never once produced a predicted refusal.
Either the fixtures are too congenial, the prompts too permissive, or the model does not refuse in
this register at all — and the plan can no longer bank on it. *Read:* the corrected
`R2-batch-operating-plan.md` §Expected stalls.

## 10. Next execution expectation

**Next primary: revisit the repair fork** against the re-attachment gap — a decision, not an
implementation. **Then A6**, under the gate's checklist, with kinship-vocabulary exposure stated as
a known unknown.

**Must not happen next:** A6 before its checklist is ticked; any repair, tombstone, backfill or
re-attachment guard implemented in production; any production entity, route, collection or committed
frontend surface; any push or merge.

## 11. Artifacts

`runs/007-anthropomorphism-ab/` (manifest, trace, 3 observations, score, critique, sparks,
source-notes, pre/post-state, instrumented-score) · `fixtures/007-anthropomorphism-ab/` ·
`R2/R2-batch-operating-plan.md` (corrected) ·
`Findings/HW-C5-positional-id-reattachment-probe.md` ·
`Decisions/HW-C5-external-claim-convention.md` · `Plans/HW-C5-seed-intake-pack.md` ·
`R2/CANDIDATE-REGISTER.md` (spark-06 resolved) · this brief.
Tests: **60 backend, 96 frontend**.
