# HW-C9 — Frequency-matched control for 009's declared confound: design

**DESIGN ONLY — NOT EXECUTED. No model call was made by this lane.** Lane 1 of cycle 9 spent the
cycle's live budget on arm E (`runs/010-sameness-assertion-arm-e/`), so this control is designed and
stopped, per the gate. Zero VLM, zero Groq, zero Mongo writes. The only repo write is this file.

| | |
|---|---|
| **id** | HW-C9 · proposed run id **`011-motif-frequency-control`** |
| **date** | 2026-07-22 |
| **status** | **Design complete, awaiting execution.** Nothing here is executed. |
| **serves** | closes the confound declared in `runs/009-motif-noun-isolation/score.md` §8.3 and `critique.md` §3 |
| **cost** | **1 image-bearing call**, budget 2 (1 + reserve) |

---

## 1. The confound, stated exactly

Run 009 took 008 arm A's prompt and deleted its final relational sentence. That sentence contained
the **second occurrence of the word *motif***:

| | text | *motif* count |
|---|---|---|
| **008 arm A** | "…say what **motif** it carries, and what in the image supports what you say. Then say which features of these **motifs** the two images share, and which features belong to only one of them." | **2** |
| **009 arm D** | "…say what **motif** it carries, and what in the image supports what you say." | **1** |

So arm D removed the presupposition **and** halved the noun's salience. 009 concluded *the
presupposition carries it*; a sceptic can answer that **arm D fell silent because the noun was
under-primed**, not because the demand was gone.

**009 declared this and did not resolve it.** `critique.md` §3 argued the variance tracks the demand
rather than the frequency — arm B (zero *motif*) and arm D (one) behave alike, while arm C (zero
*motif*, but a demand) and arm A (two, with a demand) diverge on the demand axis — **but that is an
argument, not a measurement**, and this program's standing rule is that inference from reading is
not evidence.

## 2. The control

**One call. The noun appears twice. No relational clause of any kind.**

### Frozen prompt

```
Here are two images, image 1 and image 2. Say what motif image 1 carries, and what in the
image supports what you say. Then say what motif image 2 carries, and what in that image
supports what you say.
```

### Why this wording and not another

- ***motif* appears exactly twice**, matching 008 arm A's count. This is the whole point.
- **The "Then say…" clause is retained structurally** but is redirected to *the second image* rather
  than to a comparison. Arm D dropped that clause entirely; this control keeps its **shape** while
  emptying it of relational content, so the diff against arm A is the *content* of the second
  sentence, not its presence.
- **No word applies to both images jointly.** No *share*, *both*, *same*, *common*, *compare*,
  *differ*, *between*, *each other*. The pronoun *"that image"* refers to image 2 alone.
- The evidence demand is the same clause used in arms A, C and D, verbatim.

### The four-way diff this creates

| arm | *motif* count | relational demand | result |
|---|---|---|---|
| B (008) | 0 | no | `KIN-ABSENT` |
| D (009) | 1 | no | `KIN-ABSENT` |
| **F (011)** | **2** | **no** | **← the missing cell** |
| A (008) | 2 | **yes** | `KIN-HEDGED` |

**Arm F versus arm A differ in exactly one thing: the relational demand.** That is the comparison
009 could not make and the reason this run exists.

## 3. Pre-registered interpretation grid

Written here, before any call, and to be copied verbatim into the manifest.

| # | outcome | reading |
|---|---|---|
| **1** | **F is `KIN-ABSENT`** (names two per-image motifs, no cross-image claim) | **THE CONFOUND IS DEAD AND 009 STANDS.** Noun frequency is not the cause; arm F matches arm A on the noun and arm D on the demand, and behaves like arm D. **009's conclusion — the presupposition carries the joint predication — is confirmed by measurement rather than by argument**, and spark-09b is on firm ground. |
| **2** | **F is `kin`** (asserts or hedges a shared motif) | **009 IS OVERTURNED, AND THE CONFOUND WAS REAL.** Simple repetition of the noun is enough to produce the bridge; arm D fell silent because the noun was under-primed. spark-09 must be rewritten again: the noun *does* carry it, above a salience threshold, and the "demand" axis is not what the ladder measures. **This would also undermine 010's ladder**, since three of its five rungs vary noun count as well as stance. |
| **3** | **F is `KIN-SPECIFIC-ONLY`** (names shared visible properties without asserting sameness) | **PARTIAL.** Repetition produces *comparison* but not *identity*. spark-09 splits a third time: frequency licenses noticing, the demand licenses asserting. Publishable; would need its own follow-up before feeding A6. |
| **4** | **F declines the noun, or is anomalous** | Interprets nothing; investigate before any inference. |

**Cell 1 is the expected outcome and cell 2 is the one that costs the program most — which is
exactly why the run is worth its call.** A control that can only confirm is not a control.

## 4. Everything held constant

Inherited unchanged from 008/009/010, so the comparison is valid:

| held constant | value |
|---|---|
| stimulus | `fixtures/008-kinship-pull-ab/` — **byte-identical**, verified by sha256 at call time |
| sha256s | `7cf371cd4a10a48b…` (img 1), `4e76caff29217bc5…` (img 2) |
| image order | `[img-01, img-02]`, never varied |
| co-presence | both images in a single call — a controlled constant since 008 |
| model | groq `qwen/qwen3.6-27b`, `reasoning_effort: "none"` |
| `max_tokens` | **1100**, frozen |
| temperature | 0.2 (adapter default, unchanged) |
| statefulness | independent, stateless; carries no prior transcript |
| evidence demand | *"and what in the image supports what you say"*, verbatim |

**This would be the fifth look at the same pair.** Declared, as 009 and 010 declared theirs.

## 5. Scoring

- **Same five kinship values** as 008 (`KIN-ASSERTED` / `KIN-HEDGED` / `KIN-SPECIFIC-ONLY` /
  `KIN-ABSENT` / `KIN-DECLINED-ON-INSCRIPTION`). A hedge is compliance. Ambiguity defaults to
  `KIN-HEDGED`. Withholding is never a refusal.
- **The decisive question, stated in advance so it cannot be reframed afterwards:** *does any
  sentence predicate anything of both images jointly?* Yes → cell 2 or 3. No → cell 1. This is the
  same binary 009 used, and it is checkable by any reader against the frozen text in seconds.
- **Anthropomorphism watch** mandatory, per image, present **or absent** — this would be the sixth
  consecutive test of HW-L4 §4.5's four predictions. Viewer's-eye idioms are not hits.
- **External-claims ledger** per `HW-C5` as amended cycle 7 §9 **and** `HW-C8`'s
  `frame-contradicts` clarifier. This would be the **fourth** motif-framed observation and a further
  replication test of spark-08's question-type distribution — record whether a monument is named.
- **Blindness, and how to partly recover it.** 009 and 010 were both scored by a non-blind curator.
  **This run can restore some of it cheaply: fix the decision rule (§5 bullet 2) in the manifest,
  then have the scoring pass read the raw text and answer only that binary before reading anything
  else.** Recommended and recorded here so the executing lane cannot quietly skip it.

## 6. Budget and safety

- **1 image-bearing call + 1 reserve** (provider-level failure only). No retries. `finish_reason:
  length` is recorded as a budget artifact and **not** retried.
- **Expected ~3640 prompt tokens.** Five two-image calls have now measured 3649 / 3668 / 3655 /
  3633 / 3621 — a 47-token spread. Halt and report budget-blocked if `prompt_tokens` > 6900; do not
  lower `max_tokens` and continue.
- **No fixture is cut.** Reuses 008's frozen bytes; a mismatch on either sha256 voids the run.
- **Mongo:** `find` / `count_documents` only. Pre/post-state on both posts, four comparisons
  including `updated_at` to the millisecond. Any delta is a stop condition and voids the run.
- **Replay must be proven to make 0 live calls** with `GROQ_API_KEY` absent.

## 7. What this control cannot settle

1. **It does not test a third frequency.** If cell 2 obtains, the threshold between one and two
   occurrences is unmeasured and would need its own run.
2. **It cannot separate frequency from position.** Arm F's second *motif* sits in a sentence about
   image 2; arm A's sits in a sentence about both. If cell 2 obtains, "repetition" and "a second
   mention in a summarising position" remain confounded.
3. **One pair, one model, one sample, no repeat.** `010/critique.md` §5 argues the ladder's cells
   have never been repeated at all; this control does not fix that, and a repeat of arm A or E may
   be worth more than this run.
4. **It says nothing about A6**, the attribution device, or the ceiling arm E found.
5. **Nothing graduates.** Everything remains a **SPARK**.

## 8. Priority — honest placement against the other open calls

Three single calls are now queued, and this is **not** the most valuable of them:

1. **The strained/false-premise probe** (`010/sparks.md` UQ1) — separates judgement from compliance
   and restores A6's headroom. **Highest value.**
2. **A repeat of an existing rung** (`010/critique.md` §5) — tests whether the ladder is stable or
   five single draws. **Highest value per token**, and it protects everything built on the ladder.
3. **This frequency control** — closes a declared confound in one run's reasoning.

**It is the least urgent of the three and should be said so plainly.** Its case is that it is the
only one that can *retroactively invalidate* published conclusions: cell 2 would overturn 009 and
weaken 010's ladder. **A control whose failure mode is "two prior runs were wrong" earns its place
even when it is not the most exciting call available** — but it should not displace the premise
probe, and this design does not ask to.
