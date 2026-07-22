# Foundry Score — FS-001-creative-circulation

**Sandbox:** FS-001-creative-circulation · **Axis:** creative-circulation · **Mode:** foundry · **RESEARCH-ONLY**

**Research question.** Does Semant support creative recurrence, or only one-shot annotation?

> Registers stay separate: **Evidence** (what is present), **Reading** (composed from evidence),
> **Opening** (speculative). Zero live model calls. Zero production reads — every number below is
> quoted from an artifact already frozen in the repository.

---

## 1. What was actually done

A zero-call pass over the frozen record. Sources, all inside the sandbox's declared `allowed_inputs`:

- `runs/*/pre-state.json` and `runs/*/post-state.json` — frozen production-state snapshots taken
  either side of runs 004–011 (two different snapshot shapes exist; both were handled);
- `R2/A2R-recall-evidence-honesty.md` — the confirmed recall bug and its fix;
- `R1/R1-existing-circulation-probe.md` — the one attempt the program has made to traverse the loop;
- `R2/CANDIDATE-REGISTER.md` — for the HW-S1 scout's findings, cited **through the register**
  because `Findings/` is outside this sandbox's declared inputs. That constraint is honoured rather
  than quietly ignored, and it limits §3 (see §5).

**Bounded task:** score every percept in the frozen runs on the four rubric dimensions. It completed
early, for a reason that is itself the finding.

## 2. Evidence

**E1 — The posts the program has instrumented contain no writing.** Parsing every `pre-state.json` /
`post-state.json` across runs 004–011 yields **9 distinct posts**:

| post | text_blocks | percepts | grounds |
|---|---:|---:|---:|
| `695be6bc…5df` | 0 | 0 | 0 |
| `695be790…5ef` | 0 | 0 | 0 |
| `695be803…5f8` | 0 | 0 | 0 |
| `695be815…5f9` | 0 | 0 | 0 |
| `695be817…5fa` | 0 | 0 | 0 |
| `695be817…5fb` | 0 | 0 | 0 |
| `695be843…5ff` | 0 | 0 | 0 |
| `695be8ba…609` | 0 | 0 | 1 |
| `695be8ec…60b` | 0 | 0 | 0 |

**Posts carrying any writing: 0 of 9.**

**E2 — The two posts that DO carry percepts also carry no writing.** Both recorded in frozen
documents rather than state snapshots:

- `695be6c9` — 1 expression percept `pctx_mrpi3rjk_0`, citing 3 grounds, and **0 text mentions**
  (`R1-existing-circulation-probe.md`, "Production-safety statement").
- `695be786` — 7 regions, 5 grounds, 2 percepts, **0 text_blocks** (`A2R`, "Production unchanged").

Across the **11 distinct posts** for which the program holds frozen state, the number of passages
citing a percept is **zero**.

**E3 — Recall reads; nothing writes back.** `buildRecallScript` emits a staged timeline — recede →
primary ground → supporting → expression (`R1` probe, unit-suite table). A2R's fix added
`isResolved`, `unresolvedGroundIds`, `resolvedCount`/`citedCount` and an `evidenceNote`. Every one of
those is a **read** of stored grounds. Neither document describes any path that writes back to a
percept as a result of a recall.

**E4 — The only recorded "returns" are imaginative.** `runs/001-eyes-of-stone/virtual-score.json`
carries a `returns` array with two entries — `return-veil`, `return-gravity-sentence`. Run 001 is
`mode: imaginative`; per `fixtures/001-eyes-of-stone/README.md` its images have **no post ids,
Region ids, masks, Grounds or Percepts**. The returns are real as prose and attach to nothing.

**E5 — The one attempt to traverse the loop was blocked and honestly stopped.** R1's circulation
probe was declared level A (insert chip → trigger recall → discard). It never ran: every long-lived
server died with exit 144. Recorded as **"logic-verified, rendered-unverified"** — 56 unit tests
green, no rendered proof. R1 recommended R2 carry the rendered probe "as its first obligation".
Runs 002–011 are all single-encounter model probes; **none is that probe.**

## 3. Reading

**R1 — The loop's second leg has never been traversed.** Creative recurrence requires at minimum:
image → percept → *writing that cites it* → return to image → *a changed percept*. E1 and E2 show
the third step has **zero instances** across every post the program has frozen. This is not a claim
that the machinery fails. It is a claim that the machinery is **unexercised**: `blockConvert.test.js`
proves chips survive an import→export round trip losslessly (18 tests), and no chip has ever been in
a saved document.

**R2 — What exists is playback, not recurrence.** From E3, distinguish two things the program has
been calling one thing:

- **Playback** — re-present a stored reading on a timeline. *Implemented, fixed by A2R,
  render-verified.*
- **Recurrence** — a later encounter changes the earlier reading, and the change is recorded.
  *No mechanism, no instance, no schema position.*

**R3 — The percept has no second-turn vocabulary.** spark-07 already found percepts have no notion
of **scope**. The same absence holds for **time**: nothing distinguishes a first statement from a
restatement, and nothing links a percept to an encounter that revised it. A returned-to percept and
a never-revisited one are byte-identical.

**R4 — The A2R fix is a circulation event, and it points the right way.** Before the fix a detached
percept played a confident caption over an empty image. After it the percept still plays —
**qualified, not deleted** — with *"Detached evidence — none of the 2 cited grounds still resolves."*
That is the system letting the *present* state of evidence change how a *past* reading is presented.
It is the closest thing to recurrence the program has built, and it was built as a bug fix.

## 4. Opening

**[SPEC] O1** — If recurrence is ever wanted, R4 suggests the cheapest form is not a new entity but
that same move generalised: let the present state of evidence qualify a past reading at the moment
it is re-presented. A behaviour over data that already exists.

**[SPEC] O2** — E4 hints returns are thinkable in imaginative mode and impossible in instrumented
mode. If so the constraint is infrastructural, not conceptual — which would make the blocked
rendered probe (E5) the true blocker of this entire axis.

**Both speculative. Neither proposed for build.**

## 5. Resistance

- **`insufficient_evidence`** — "does a return *change* the percept?" cannot be answered at all. Not
  one return has occurred on an instrumented post. The `survival_of_detachment` dimension is
  therefore largely **unscoreable**, and is recorded as such rather than scored from A2R's narrative.
- **`curator_refusal` (structural, self-imposed)** — HW-S1's frontend findings sit in `Findings/`,
  outside this sandbox's `allowed_inputs`. They are cited only via `CANDIDATE-REGISTER.md`. Claims
  about `recall.js`, `RefPicker` or `homeData.js` internals are **second-hand here** and must not be
  treated as independently verified by this run.
- **`sensory_unavailable`** — no rendered verification attempted; no browser observation made.

## 6. Scoring rubric

Scored per **percept**, as the recording rule requires. The frozen record yields exactly **3**
percepts (`pctx_mrpi3rjk_0` on `695be6c9`; two on `695be786`, incl. `pctx_mrqp950d_0`).

| dimension | asks | scale | result |
|---|---|---|---|
| circulation_yield | Does the percept change a LATER surface or return, or die at the image? | changes-later / referenced-only / dies-at-image | **3 of 3 `dies-at-image`** — no percept is cited by any passage |
| dependency_visibility | Can the downstream dependency be SHOWN from a frozen artifact? | shown / inferable / asserted | **n/a — there is no downstream dependency to show** |
| survival_of_detachment | If its evidence detached, did anything downstream notice? | noticed / silent-degradation / unaffected | **1 scoreable**: `pctx_mrqp950d_0` = `noticed` **after** the A2R fix, `silent-degradation` before it. 2 unscoreable (no detachment) |
| discrimination | Does the measure separate circulating from non-circulating percepts? | separates / partially / names-everything | **names-everything** — with 0 circulating percepts there is no positive class |

**No composite score.** The `discrimination` row matters most: **the rubric failed its own test.** A
measure that assigns every case to one class has not been validated. Any future circulation scoring
must re-earn it against at least one positive instance.

## 7. Stop condition

Declared stops:

- the declared bounded task is complete
- the budget is exhausted
- a result would require reading the production database
- the finding would require a cross-post relation entity to express

**Fired: the first** — every percept in the frozen runs was scored or marked unscoreable. It fired
**far earlier than designed**, because the population is 3 and the positive class is empty. No stop
was forced by budget (0 of 0 calls spent), by the DB boundary, or by an entity temptation.

## 8. Withheld

- **"Semant cannot do creative recurrence."** Withheld. The evidence supports *unattested*, not
  *unsupported*. E5 shows the probe designed to test it was killed by an environment failure, not by
  the architecture.
- **"Recall should write back to the percept."** Withheld — the new-entity temptation in disguise;
  one run with zero positive instances licenses nothing.
- **"The Home surface is the circulation failure."** Withheld: supporting evidence is second-hand
  here per §5.
- **A cross-post relation entity.** Named forbidden in the manifest precisely because it is the
  attractive move. Nothing in this run brings it closer.
