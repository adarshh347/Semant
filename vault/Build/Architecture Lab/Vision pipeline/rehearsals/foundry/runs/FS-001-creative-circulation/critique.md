# Foundry Critique — FS-001-creative-circulation

**Sandbox:** FS-001-creative-circulation · **Axis:** creative-circulation · **RESEARCH-ONLY**

> The critique argues against the run's own score. A cycle with no correction is either genuinely
> clean or insufficiently adversarial — and this document must say which.

---

## 1. The strongest case against the result

**The score measured a corpus, not an architecture, and then spoke about the architecture.**

"0 of 9 posts carry writing" is a fact about **which posts the rehearsal program chose to snapshot**.
Runs 004–011 selected fixtures for *model probes* — figure/ground pairs, kinship pairs, monuments.
Nobody picked those posts because someone had written about them. Finding no writing on posts chosen
for not-writing reasons is close to tautological.

The honest version of E1 is narrower than the score states: **the posts the rehearsal program has
instrumented carry no writing.** Whether the wider corpus does is *unknown to this run*, because
checking would require reading the production DB, which the sandbox forbids. §2 of the score says
"the posts the program has instrumented", but §3's Reading R1 slides to "every post the program has
frozen" and the headline slides further. **That slide is the run's main defect.**

## 2. Deflationary reading

**Nobody has used the feature yet, and that is all this shows.**

The Chiasm writer path (BlockNote, chips, RefPicker, `insertRegionChip`) is recent work. The
circulation probe was blocked in R1 and never rescheduled. A feature nobody has exercised produces
no instances — which is what "0 of 11" says, without any architectural claim attached.

Under this reading, "Semant supports only one-shot annotation" is not a finding about Semant. It is
a finding about a corpus assembled by a research program that has, so far, deliberately studied
single-turn model behaviour. **The deflationary reading is strong and is not defeated by anything in
this run.** It is weakened only slightly by R3 (the percept genuinely has no time/scope vocabulary),
which is a structural observation independent of usage.

## 3. Confounds

- **Selection.** As §1. The fixtures were chosen to answer evidence-honesty questions.
- **Snapshot shape drift.** Runs 004–007 store flat counts; 008–011 store `lengths` + `present`. My
  first parse conflated `present: true` (field exists) with a count, and briefly produced "8
  text_blocks". That was wrong and was corrected before it entered the score — **but it nearly
  became evidence**, and a reader should know the parse was non-trivial.
- **Non-blind analyst.** I designed FS-001's rubric knowing the R2 register, then scored against it.
  The `dies-at-image` result was foreseeable from spark-03 before any parsing.
- **Two evidence classes mixed.** E1 comes from machine-readable state; E2 from prose in two
  documents. They are not equally checkable, and the score presents them in one paragraph.

## 4. Method corrections

**Correction 1 — the rubric was mis-designed, and the run proved it.** `discrimination` scored
`names-everything`. A measure with no positive class cannot be validated. The correct move is not to
report the other three dimensions as if they stand: it is to record that **FS-001's rubric is not yet
a working instrument** and must be re-earned against ≥1 circulating percept. The score says this;
this critique upgrades it from a row in a table to a **method finding**.

**Correction 2 — `survival_of_detachment` cannot be scored from A2R without double-counting.**
A2R is where the detachment was found *and* fixed. Scoring `pctx_mrqp950d_0` as `noticed` records the
A2R fix a second time under a different axis. It is not independent evidence of circulation.

**Does an earlier conclusion fall?** No. spark-03 stands — this run neither strengthens nor weakens
it. It does, however, **remove one prop**: spark-03's [SPEC] note imagines surfacing detachment "near
existing percept/ground inspectors". This run shows there is no downstream reader to notify, because
nothing downstream exists yet.

## 5. What would kill this finding

**The cheapest killer: one post with a saved passage citing a percept.** If the wider corpus holds
even one, E1's headline is false and R1 collapses to "the rehearsal fixtures happen not to have any".

That check is **one read-only query** — and this sandbox forbids it. The right response is not to
weaken the guard but to note that **FS-001 cannot falsify its own central claim**, which is a serious
limitation and the reason §6 declines to promote the finding above SPARK.

A second killer: the rendered probe (R1's blocked level-A) succeeding and showing chip→recall works
end-to-end. That would not restore recurrence, but it would move the blocker from "unattested" to
"attested once".

## 6. Declared weaknesses

- **n = 3 percepts**, 11 posts, 0 positive instances. There is no positive class.
- **1 analyst, non-blind, rubric self-designed.**
- **0 live calls, 0 rendered observations** — by design, but it means nothing was tested, only read.
- **The central claim is unfalsifiable within the sandbox's own boundary** (§5).
- **Second-hand frontend evidence** — `recall.js`/`RefPicker`/`homeData.js` cited via the register.

## 7. Recorded discomfort

The playback/recurrence distinction (R2) is the part I find most persuasive and least evidenced. It
is essentially an argument from *absence of a write path* in two documents that were not written to
answer that question. It reads as insight; it may be a definition dressed as a discovery. If a later
run finds any mechanism by which a re-encounter alters stored state, R2 should be retired quickly
and without defending it.

Second discomfort: the score's §4 Reading R4 (A2R as "the closest thing to recurrence") is
flattering to the program. It may simply be a bug fix, and calling it a circulation event may be the
same abstraction-to-altitude move spark-10 describes — pitching a claim where counter-evidence
cannot reach it.
