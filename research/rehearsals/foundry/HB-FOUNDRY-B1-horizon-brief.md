# Horizon Brief — Foundry Batch 1

**Cycle:** Foundry Batch 1 · **Branch:** `feat/rehearsal-research-r1` · **Lanes:** 3, all complete and
paused · **Live model calls: 0** (0 budgeted, 0 approved) · **Production data: not mutated** ·
**No code changed.**

> Deliberately numbered `HB-FOUNDRY-B1` rather than `HB-011`, so it does not collide with the R2
> Horizon Weave cycle sequence. HB-011 remains available for cycle 11, whose primary is still
> `012-repeat-stability`. **This brief does not reschedule that.**

---

## 1. What changed

**The program now knows why its sparks will not graduate, and it is the same reason three times.**

The Candidate Foundry requires a **circulation test** before graduation. FS-001 established that on
the frozen record there is nothing downstream to test against: across the **11 posts** the program
holds state for, **0 carry writing** — including the 2 that carry percepts. Every R2 spark is stuck at
one gate for a reason none of them names.

The wall generalised. **All three lanes hit an empty positive class**: no circulating percept, no
instrumented run with a source text, no observed reader. Batch 1's most transferable finding is not
about any single axis — **the program is rich in machinery and poor in instances.** `Mention` is
complete, 17-test-covered, and has never held a Mention.

**A control variable is not recording what the program believes it records.** 11 of 13 run manifests
declare `source_condition: "present"` while supplying **zero texts**; `R1-schema-decisions.md` defines
the field as *"whether the source was there"*. `absent`, `replaced`, `misleading` have never been used.

**Semant's communication gap is transmission, not honesty.** `visionActivity.js` discriminates absent
from unreadable and has a **tested** ban on causal wording — then renders `"N recorded"`, folding
`partial`/`timed_out`/`stale` into a count, in a drawer collapsed by default.

## 2. Method corrections

**Mandatory section, and this cycle was not clean.**

- **FS-002's strongest objection was raised, tested, and refuted *within the run*.** The critique
  proposed that `source_condition: present` might mean "no adversarial manipulation applied". The
  definition was searched for, found, and killed the alternative. **The finding survived its own
  attack** — the first time in the program a critique has run its own named killer to completion.
- **The same search produced a better finding than the score had.** A6 was the **only** run ever
  designed with `source_condition: misleading`; its retirement (HB-010 §3) removed the program's only
  source-manipulation arm. HB-010 records the loss of the *suggestibility* test with regret; **the
  loss of the source-condition test is recorded nowhere.** A retirement argued on one axis cost a
  capability on another.
- **FS-001's rubric failed its own `discrimination` test** — every case scored to one class. The
  instrument is not yet validated and must be re-earned against ≥1 positive instance.
- **FS-004 overreached and downgraded itself.** *"The denominator is the mechanism"* is retracted; the
  defensible claim is only that the surface discards a distinction it already computes.
- **FS-002 declared a human-prose control and never scored it** — the control existed to stop the
  measure separating nothing, and was dropped.
- **One analyst wrote all three lanes in one order.** Cross-lane insights **cannot be claimed as
  independent**. The single exception is UQ3 (below), reached separately by two lanes.

**Does any earlier conclusion fall?** **No.** spark-03, spark-06, spark-08, spark-09, spark-10, A2R,
HW-S1 and HB-010 are all restated or cited, **none contradicted**. Batch 1 produced no evidence that
moves any prior result — which is itself worth noticing after three lanes of work.

## 3. Data integrity findings

**One, and it is in research metadata, not production data.** `source_condition` is mis-set on eleven
frozen run manifests (§1). **Recorded only, never repaired** — HW-C6 settled the general form:
*"Do not retro-fill the runs."* Runs are frozen evidence.

**Production:** zero reads, zero writes, zero mutations. No post, region, ground, percept, embedding
or vision_run was touched by any lane.

## 4. Model / runtime constraints

**None encountered — 0 calls made, 0 adapters resolved, no network path entered.** All three
manifests ship with `max_live_calls: 0, approved: false`, and the harness rejects a raise without an
explicit approval diff.

The binding constraint on Batch 1 was **not budget**. It was **evidence supply**: two lanes could not
falsify their own central claims inside their declared `allowed_inputs`, and the boundaries were
honoured rather than quietly widened.

## 5. Candidate sparks

**Ten, all SPARK, none promoted.** Full detail in each run's `sparks.md`; the register is
`foundry/BATCH-1-SYNTHESIS.md` §3. The three worth the orchestrator's attention:

- **FS002-02** — `source_condition` is set to a value the runs do not have. **Strongest in batch:**
  machine-checkable, n = 11, survived its own strongest objection.
- **FS001-02** — the corpus has percepts and no passages. **The count is solid; its scope is
  contested**, and the killing check lies outside the sandbox.
- **FS002-03** — A6's retirement silently cost the only source-manipulation run. n = 1, but it names a
  reusable shape: *when a run is retired, what else was it carrying?*

## 6. UI / product opportunities

**Only one lane reached a shipped surface**, and it did not invent anything.

`differential/VisionActivityRail.jsx`'s closed line renders a count where `visionActivity.js` holds a
distinction. **This is already scoped as HW-S1 experiment E5** — location, home module, test file and
kill condition all written. FS-004 supplies a *reason* for E5, not a design. *Belongs in an existing
surface; wants no new one.*

Everything else is **[SPEC]** or research tooling: a cross-field validation rule for future rehearsal
manifests, and UQ1's read-only corpus count (a query, not a feature).

## 7. What the orchestrator should study deeply

**(1) UQ1 — does any post in the corpus carry a passage citing a percept?** One read-only count kills
or confirms FS001-02 and, with it, the batch's central claim about circulation. **No sandbox in Batch
1 was permitted to ask it.** *Read:* FS-001 `score.md` §2, `critique.md` §1.

**(2) UQ2 — does the program still want an `absent`/`misleading` source arm now that A6 is gone?**
Without one, source pressure is permanently untested and the doctrine's ventriloquism remedy stays
theoretical. **If the answer is no, textual dynamism should be closed as an axis rather than left
implicitly open.** *Read:* FS-002 `score.md` §3 R4b.

**(3) The R1 rendered probe has been waiting since R1 and servers are alive again.** It died on
exit-144; R2 then ran eleven model probes instead of the one thing R1 called its "first obligation".
It is the cheapest unblocking action on the circulation axis. *Read:*
`R1/R1-existing-circulation-probe.md`.

**(4) UQ3 — does Chiasm render A2R's evidence note in its own pane?** A2R explicitly declines to
assume it. **FS-001 and FS-004 reached this independently** — the only unforced convergence in the
batch. If Chiasm shows the caption without the note, the program's one honest surface is honest in
one place only. *Read:* `A2R-recall-evidence-honesty.md`, "What this does NOT fix".

## 8. Next execution expectation

**The single next primary action is unchanged and is NOT a foundry sandbox: execute
`012-repeat-stability`.** Batch 1 touched nothing that alters HB-010 §10's priority, and three of the
batch's sparks (FS004-03 especially) inherit spark-10, which 012 can invalidate outright.

**In parallel, three zero-cost decisions the orchestrator owns:** UQ1's count, UQ2's keep-or-close,
and whether to run E5.

**Batch 2, when it comes: UI Emergence + Seed Ecology** — not Model Orchestration + Agent Skill.
FS-003 is blocked by its own manifest on the 012 precondition; agent skills need multi-run support
(README places `skills/` at R6+) and Batch 1 demonstrated no repeated pattern on any new axis. UI
Emergence inherits two ready questions (E5, the rendered probe); Seed Ecology attacks the empty
positive class directly (HW-C5: 39 real unclaimed fixtures, not 127; no photograph of more than two
living people). Both are zero-live-call and mutually independent. Full argument:
`BATCH-1-SYNTHESIS.md` §6.

**Must NOT happen next:** any overclaim/confidence detector before 012 runs · any percept
revision/version field or recall write-back · any cross-post relation or `SourceSlice` entity · any
tone system · any retro-fix of frozen run manifests · any UI string changed without an explicit
implement instruction · any push or merge.

## 9. Artifacts

`foundry/sandboxes/FS-004-communication-quality.yaml` (new) ·
`foundry/runs/FS-001-creative-circulation/` · `foundry/runs/FS-002-textual-dynamism/` ·
`foundry/runs/FS-004-communication-quality/` (each: `score.md`, `critique.md`, `sparks.md`,
`product-implications.md`, `horizon-brief.md`, `seeds.json`, `foundry-run.json`) ·
`foundry/BATCH-1-SYNTHESIS.md` · this brief.

**13 seeds frozen, 13 present, 0 missing. Live model calls: 0. Production data: not mutated. No
product code changed. No run manifest edited. Nothing pushed or merged.**
