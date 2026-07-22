# Foundry Batch 1 — synthesis

**Lanes:** FS-001 creative-circulation · FS-002 textual-dynamism · FS-004 communication-quality.
**All three complete and paused.** **RESEARCH-ONLY** — no production entity, route, collection,
surface, schema or datum was created or changed. **Live model calls: 0 of 0 budgeted.**

---

## 1. What each sandbox discovered

### FS-001 — creative circulation

**Semant supports one-shot annotation. Creative recurrence is unattested — not refuted, unattested.**

Across the **11 posts** the program holds frozen state for, **0 carry writing**, including the 2 that
carry percepts. The loop's second leg — percept → passage citing it — has **zero instances**. The
`Mention` machinery is complete, 17-test-covered, and **has never held a Mention**, because its only
durable form is markup inside a saved passage and no passage has been saved.

What exists is **playback, not recurrence**: recall re-presents a stored reading on a timeline and
nothing writes back. The percept has no vocabulary for a second turn — spark-07 found it lacks
*scope*; this lane finds it also lacks *time*.

**The lane's rubric failed its own `discrimination` test** (every case scored to one class), so the
instrument is not yet validated. And **its central claim is unfalsifiable inside its own boundary** —
the killing check is a read-only corpus count the manifest forbids.

### FS-002 — textual dynamism

**The demonstrated live force is the question, not the source.**

Two clean results show **one word changes what the model reports seeing** — *address* → a face on a
facade (spark-06), *motif* → shared-purpose talk (spark-09). And **11 of 13 run manifests declare
`source_condition: "present"` while supplying zero texts**; the field is defined in
`R1-schema-decisions.md` as *"whether the source was there"*, so this is a genuine control-variable
failure, not a quibble. `absent`, `replaced` and `misleading` have **never been used**.

Two corrections the critique produced, which the score had wrong:
- the absence is **partly deliberate** — A3's plan reads *"choreography — **not** Merleau-Ponty;
  avoid source ventriloquism"*;
- **A6 was the only run ever designed with `misleading`, and its retirement silently cost the program
  its only source-manipulation arm.** HB-010 §3 records the loss of the *suggestibility* test with
  regret; the loss of the *source-condition* test is recorded nowhere.

### FS-004 — communication quality

**Semant's problem is transmission, not honesty.**

`visionActivity.js` discriminates *absent* from *unreadable* and carries a **tested** prohibition on
causal wording — then the rendered closed summary folds `partial` / `timed_out` / `stale` into
`"N recorded"`, in a drawer that is collapsed by default, below the counts footer. **The honesty is
implemented one level below where it is spoken.**

The program has **one render-verified honest sentence** — A2R's *"Detached evidence — none of the 2
cited grounds still resolves."* — and it exists because a bug was found, not because a practice
exists. Meanwhile the failure the program has actually **measured** (spark-10: force rises as content
thins) has **no counterpart guard anywhere**.

---

## 2. What axis moved

| axis | movement | honest characterisation |
|---|---|---|
| **creative-circulation** | unmeasured → **unmeasurable on present evidence** | The population has no positive class. Real movement, not the kind hoped for. |
| **textual-dynamism** | one axis → **split into two, one attested and one never tested** | The strongest half is **inherited** from runs 007–009, not earned here. |
| **communication-quality** | unexamined → **examined; reframed as a transmission gap** | Modest. n = 4 utterances, 2 user-facing, 0 observed in a browser. |

**All three lanes hit the same structural wall: an empty positive class.** No circulating percept, no
instrumented run with a source, no observed reader. Batch 1's most transferable result is not about
any one axis — it is that **the program is rich in machinery and poor in instances.**

## 3. Candidate sparks

Ten, all SPARK, none promoted. Full entries in each run's `sparks.md`.

| id | one line | strength |
|---|---|---|
| FS001-01 | playback is not recurrence, and Semant has only playback | weak — may be a definition dressed as a discovery |
| FS001-02 | the corpus has percepts and no passages; the second leg is unexercised | **count is solid**; scope contested; unfalsifiable in-sandbox |
| FS001-03 | the qualified replay (A2R) is the only recurrence-shaped behaviour | weak, n = 1, possibly flattering |
| FS002-01 | the demonstrated live force is the question, not the source | positive half **borrowed**; negative half solid (n = 11) |
| FS002-02 | `source_condition` is set to a value the runs do not have | **strongest in batch** — machine-checkable, survived its own strongest objection |
| FS002-03 | A6's retirement silently cost the only source-manipulation run | n = 1, but names a reusable shape: *what else was a retired run carrying?* |
| FS002-04 | the flame-stimulator form exists and has never been stressed | n = 1 imaginative run |
| FS004-01 | the surface discards a distinction the module already computes | second-hand (restates HW-S1 E5 with a reason) |
| FS004-02 | every user-facing utterance closes; none invites a return | most interesting, least observed |
| FS004-03 | the measured failure has no counterpart guard | inherits spark-10, whose deflationary reading is still live |

**One unforced convergence:** FS-001 and FS-004 independently reached the same question — **does
Chiasm render A2R's evidence note in its own pane?** A2R explicitly declines to assume it. Two lanes
arriving there separately is the only cross-lane signal in this batch that is not explained by one
analyst working in one order.

## 4. What should become build specs later

**Nothing in Batch 1 is ready to be a build spec.** One item is *close*, and it is not new:

- **HW-S1 experiment E5** (rail summary tells the truth about non-nominal states) — already scoped,
  reversible, with its own kill condition and home module. FS-004 supplies a reason for it, not a
  design. **This is a decision the orchestrator owns, gated by HB-010's standing rule that no UI
  string changes without an explicit implement instruction.**

Two research-tooling items, neither product-shaped:

- A **cross-field validation rule for future rehearsal manifests** (refuse `source_condition:
  present` when `texts` is empty). The Foundry Harness already performs this class of check for
  sandbox manifests; the rehearsal runner does not.
- **UQ1's read-only corpus count** of `text_blocks` — not a feature, a query, and the thing that
  would kill or confirm the batch's most consequential spark.

## 5. What must not be built yet

Consolidated across the three lanes, in descending danger:

1. **An overclaim / confidence detector** for spark-10. The clearest premature ontology available:
   the phenomenon **may not survive its first repeat**, and `012-repeat-stability` exists to find out.
2. **Percept revision/version fields, `PerceptRevision`, or recall write-back.** Zero positive
   instances is an empty class, not a small sample.
3. **A cross-post relation entity.** Named forbidden in FS-001's manifest precisely because it is the
   attractive move; nothing brings it closer.
4. **A `SourceSlice` / `Pressure` entity.** Zero instrumented instances, and its one designed test was
   retired.
5. **A tone system or voice guide.** Two user-facing samples.
6. **Retro-fixing `source_condition` on eleven frozen runs.** HW-C6 settled the general form:
   *do not retro-fill the runs.*
7. **Opening the Vision Activity Rail by default** — already considered and declined by HW-S1.
8. **Ingesting Warburg / Casey / Didi-Huberman.** Named as gaps only; HW-C5 is explicit that
   **images, not texts, are the bottleneck**.

## 6. Batch 2 recommendation — **UI Emergence + Seed Ecology**

**Recommended, and not close.**

**Why not Model Orchestration + Agent Skill:**
- **FS-003 is blocked by its own manifest**, on a stated precondition: `012-repeat-stability` has not
  run, so the incumbent reader's variance is unknown. Comparing a second model against an unrepeated
  single draw attributes sampling noise to model identity. That precondition is unchanged by Batch 1.
- Model orchestration is the **only Batch-2 candidate requiring live calls**, and a budget rise needs
  explicit approval.
- Agent skill emergence needs **multi-run support** — the rehearsal README places `skills/` at **R6+**.
  Batch 1 shows the program cannot yet demonstrate a repeated pattern on any new axis; skills built
  on that base would encode single draws.

**Why UI Emergence + Seed Ecology:**
- **Batch 1's wall was an empty positive class in every lane.** Seed ecology is the axis that
  *directly attacks that wall* — HW-C5 already establishes the corpus is 39 real unclaimed fixtures,
  not 127, that ~80 posts descend from 10 carousels, and that **there is not one photograph of more
  than two living people**. That is the constraint under everything else.
- **UI emergence is where Batch 1's only shipped-surface pressure landed** (FS-004 / HW-S1 E5), and
  where FS-001's blocked rendered probe lives. Both lanes ended pointing at it.
- Both are **zero-live-call axes**, runnable on frozen artifacts and local files — so Batch 2 can
  proceed without touching the model budget or waiting on 012.
- They are **mutually independent**: seed supply and interface behaviour share no evidence, so one
  analyst running both cannot manufacture convergence between them — the confound that Batch 1 could
  not rule out.

**Sequencing within Batch 2:** UI Emergence first. It inherits two ready questions (E5, the rendered
probe) and can reuse FS-004's utterance rubric. Seed Ecology second, because its most valuable output
is a *supply decision* the orchestrator must make, and it should be informed by whatever the UI lane
learns about which fixtures are actually exercised.

## 7. Batch 1's own method failures

Recorded because a batch with no self-correction is either clean or insufficiently adversarial, and
this one was not clean:

- **One analyst, three lanes, one order.** Cross-lane insights (FS-004 R5 → FS-001; FS-002's Warburg
  observation) **cannot be claimed as independent**. Only the UQ3 convergence survives this.
- **FS-002 declared a human-prose control and never scored it.** The control existed precisely to stop
  the measure separating nothing, and was dropped.
- **FS-004 scored model output and UI copy on one table** after naming that as `analogy_overreach`.
- **Every rubric was self-designed by the analyst who then scored against it**, in all three lanes.
- **Two lanes could not falsify their own central claims** inside their declared inputs (FS-001 UQ1,
  FS-004 UQ1). The boundaries were honoured rather than quietly widened — the correct choice, and a
  real limit on what Batch 1 can assert.
