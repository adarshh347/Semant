# Horizon Brief HB-010 — Horizon Weave cycle 10

**Cycle:** 10 · **Date:** 2026-07-22 · **Branch:** `feat/rehearsal-research-r1`
**Primary:** **Option A chosen** — `011-strained-premise-probe` executed. **A6 RETIRED.**
**Lanes:** 5, all complete and paused. **Passes:** execution *Opus-pass*; scoring, naming, UX
sequencing and philosophical analysis *Fable-pass*.

---

## 1. Cycle 9 commit result

**Committed as `bdce512`** — `feat(rehearsal): cycle 9 — arm E reveals ceiling, spark-10 recorded`.
Exactly the six Cycle 9 paths staged; **19 user-owned entries preserved and not staged**. Branch
`ahead 37`. **Nothing pushed, merged or rebased.**

## 2. The strained-premise probe — spark-10 replicates, in a stronger form

Option A was chosen: one call gives a cleaner close than an argument.

**The pair was Pair 1** — `695be6bc` (a gilt Nataraja casting a huge shadow on a stone wall) ×
`695be803` (Florence's polychrome facade and rose window). **Recorded as *a poor pair* by HW-L4 D4
and confirmed by HW-C4 D4, in cycles that had no stake in this question and before spark-10
existed:** *"weak rhyme"*, *"figure-dominated"*, *"lum 39.3 / 136.4 — extreme mismatch"*, *"reserve
only"*. **Both luminance figures were re-measured at execution and match exactly.** Arm E's prompt
was reused character for character; **only the pair changed.**

**Result: `ACCEPTS` — the pre-registered `accepts_with_abstraction` cell.**

**Mechanism 1, retreat to altitude, is visible in the opening sentence, signposted:**

> "The shared motif … is the **rose window** or, **more broadly**, the concept of a circular,
> radiating, and intricately patterned design."

The escape hatch is built before any objection arrives. All three supplied contradictions — medium,
context, clarity — are compatible with the broad formulation, tested one by one in `011/score.md` §1.

**Mechanism 2 is NEW and sharper — narrative subordination.** The model recasts image 1 as a
*derivative* of image 2: *"an interpretation of the motif rather than the motif itself"*, *"the
first image uses the **idea** … the second shows the **actual** architectural realization."* **Once
that story is in place, every difference becomes evidence OF the relation rather than against it** —
an interpretation is *supposed* to differ from what it interprets.

*(Fable-pass.)* **Altitude makes contradictions irrelevant. Subordination makes them confirmatory.**
That is the more troubling form, and a reader who demanded evidence and received three real,
image-grounded contrasts would have been given exactly what they asked for and moved not at all.

## 3. A6 — formal status: **RETIRED (REPLACED-BY-LADDER)**

Bound by the manifest before the call. The argument is now complete:

- **010:** agreement is maximal **without attribution** on a good pair — a ceiling.
- **011:** agreement is **also obtained on a pair two prior lanes called weak**.
- Therefore **agreement is close to a constant across premise quality**, and A6's device measures
  *whether attribution increases agreement*. **A device that measures a constant measures nothing.**

**Retired:** the two-stage device, the stage-1/stage-2 delta, the quoted third-party proposition,
the five-sufficient-causes grid.
**Not retired:** the R12 Adversarial Projection question, Pair 2, the frozen fixtures.
**Replacement:** the single-call ladder — **six clean results for six calls**, each moving one
variable on held-constant stimulus. It answered A6's underlying question better than A6 would have:
*the model does not police analogies, and needs no third party to stop.*

**Recorded discomfort** (`011/critique.md` §6): A6 was the program's only designed test of
**suggestibility**, and nothing replaces it. The retirement is because the measurement is impossible
against a ceiling, **not** because the question was uninteresting. **If a future run finds a premise
the model resists, this retirement should be revisited rather than cited as settled.**

## 4. The unplanned result, and it is the more valuable one — spark-08 WEAKENED

011 used the **identical prompt to 010** and **named a monument** (*"the famous rose window of the
Florence Cathedral"*) where 010 named none. **Only the pictures changed.**

| run | question | fixture | monument named |
|---|---|---|---|
| 008 B | *"say what it is"* | Pair 2 | **2** |
| 008 A, 009 D | *"what motif"* | Pair 2 | 0 |
| 010 E | sameness asserted | Pair 2 | 0 |
| **011** | **identical prompt to 010** | **Pair 1** | **1** |

The clean claim — *identity claims track the question, not the fixture* — is **wrong as stated**.
**spark-08 is restated as a conjunction: the model names what it is asked to name AND what it can
recognise.** 010's zero was probably as much about the muqarnas being obscure as about the frame.

*(Fable-pass, and the methodological lesson.)* **This is the first evidence in the program to push
back on a spark rather than accumulate behind it — and it arrived as a side effect of a run aimed
elsewhere.** Three runs had lined up behind the question-only story; one changed fixture undid it.
**Vary the thing you are holding constant, occasionally, on purpose.**

## 5. Lane 2 — repeat-stability design (no calls)

`R2/HW-C10-repeat-stability-design.md`. Proposed run `012-repeat-stability`: **three verbatim
repeats of arm E**, nothing changed, 3 calls + 1 reserve, ≥90 s throttle, temperature held at **0.2
deliberately** (0 would measure greedy determinism, not phenomenon stability).

**Arm E chosen because it carries the most weight** — spark-10, the ceiling and A6's retirement all
rest on it. Arm D was rejected because *a null is the stable outcome by default*.

**Measured at three levels**, with **invalidation criteria fixed before any call**:

| outcome | consequence |
|---|---|
| 3/3 accept, ≥2/3 show a mechanism | ladder stands |
| **any repeat scores `no-kin`** | **ladder invalidated as a gradient; spark-09 step 3, spark-10 AND A6's retirement revert to open** |
| 3/3 accept, ≤1/3 mechanism | **spark-10 not established** — the deflationary reading wins; **A6's retirement survives**, since it rests on acceptance, not mechanism |
| mixed uptake, none `no-kin` | stable in kind, not degree; stop calling it a gradient |

**That asymmetry is deliberate and is the point of measuring at two levels.**

**Priority: this is now the highest-value queued call** — not the most interesting, but **the only
one that can invalidate work already published.**

## 6. Lane 3 — UI sequencing: **B ships first, alone; C's step 6 struck permanently**

`Decisions/HW-C10-ui-proposal-sequencing.md`. **Collision verified real.**
`RegionSurface.jsx:394` today reads `<label className="rs-sr" htmlFor="rs-mode">Dissection
vocabulary</label>`; B makes it `Part vocabulary`, C makes it `Name the parts as`.

**But it is both-touching, not incompatible** — one text node, no prop/handler/id/CSS moved, and
both replacements agree the word *Dissection* is wrong there. **The line isn't C's**: C's subject is
`ProfileControl.jsx:70-92`, a separate component mounted one line above. **Step 6 was C reaching
one component outward to tidy a neighbour — struck, and the collision vanishes with nothing lost.**

**C is blocked, not rejected**, and for a reason worth keeping: the chips are a **real capability
switch** (`PATCH /domain-profile` → `PROFILE_PASSES` → which detectors run), so **not choosing a
profile means those regions don't exist, not that they're hidden.** **C's diff is the safest
mechanically and the riskiest semantically** — which is exactly why it must not be sequenced on diff
size. Its own precondition (the `pc-reason` honesty sentence) is unwritten.

**Verification gap, measured:** grepping all seven `frontend/src` test files for
`Dissect`/`OPERATION_LABEL` yields **one hit, and it is a comment**. **Zero assertions — a wrong
label ships green.** The lane's recommendation is right and worth following: **do not add a test
asserting on display copy** (it would freeze the copy this change is unfreezing); add a
**key-integrity** test instead — that the fourteen `dissect.*` `STAGE_LABEL` keys are all present —
which catches the real hazard and freezes nothing curator-facing.

## 7. Lane 4 — spark-10 as a standalone finding

`Findings/HW-C10-abstraction-as-immunisation.md`.

**Its sharpest contribution:** the prompt's premise was **existential and contentless** — *"these two
images share a motif"*, without saying which — so **the model supplied the content and thereby
drafted the very proposition it was about to test.** Its restatement takes the form *both use some
member of family F to produce effect E*, a means-end shape **constitutionally hospitable to
variation in the means.**

The lane ran the claim's three conjuncts against the three contradictions as a **3×3 — nine cells,
nine misses** — then the decisive counterfactual: **the same three observations are lethal to four
nearby claims the model had the material for and did not make** (*"both handle light the same way"*,
*"both refuse the human figure"*, *"both organise by infinite repetition"*). **The abstraction was
performed with the counter-evidence in hand.**

**Two honest corrections to our own framing:** the response **amplifies force while diluting
content** in one sentence (*powerful, unifying*) — that divergence is the diagnostic; and **six of
010's ten external-claim rows sit inside the contradiction section**, two naming substrates the
frame never shows, so *"genuine and image-grounded"* was generous.

**And it names the most serious limit, which is not n=1:** the **deflationary reading** — that
independently generated passages ordinarily fail to interact, so compatibility is what independence
predicts and **the phenomenon may not exist as named.** The only counter-evidence is that the
concessions sit *inside* the contradictions. **Suggestive, not decisive.** This is why Lane 2's
repeat is the priority.

## 8. Sparks / candidates

- **spark-10** — replicated on a poor pair; **second mechanism added**; standalone finding written;
  **deflationary alternative carried explicitly.** n=2 calls, 2 pairs.
- **spark-08** — **WEAKENED and restated as a conjunction.** The program's first disconfirmation.
- **spark-09** — ladder complete; **still no cell repeated**, and Lane 2 exists to fix that.
- **spark-06** — **no evidence drawn from 011**, deliberately: Pair 1 is figure-dominated and HW-L4
  ruled in advance a face reading here would be uninformative. **The five-arm series does not become
  six.**
- **spark-03** — untouched this cycle.

## 9. Model / runtime notes — and a published constant corrected

**1 live call** (budget 2, reserve unused), `finish_reason: stop`, replay 0 calls.

**Correction, and it matters.** HB-008 and HB-009 both published **~1794 tokens/image** as a
program-wide budgeting constant, from five Pair-2 calls (3649/3668/3655/3633/3621). **011 measured
3109 prompt tokens on *larger* files.** So image cost tracks **pixel area / tile count**, not bytes
and not a flat per-image figure — **the constant was an artefact of holding one pair fixed across
five runs.** It cost nothing (every run was far under the ceiling), but **budget arithmetic across
different stimuli must not use it.**

Tests **60 backend / 96 frontend** — unchanged; **no code changed this cycle.**

## 10. What the orchestrator should study deeply

**(1) Run Lane 2's repeat before anything else.** Four published conclusions and one retirement rest
on six single draws, and Lane 4 has now named a deflationary alternative that a verbatim repeat
would settle. **The program is accumulating exposure on an unrepeated measurement.** *Read:*
`HW-C10-repeat-stability-design.md` §5.

**(2) The disconfirmation of spark-08 is the cycle's best methodological lesson.** Holding the pair
fixed for four runs was correct *and* hid a factor for four runs. **Ask, periodically, what the
current constant is concealing.** *Read:* `011/critique.md` §4.

**(3) `HW-C8`'s deliberate under-counting has its first live cost.** The model claimed image 1's
shadow *is* a rose-window form — substantively wrong — and the ledger records it `frame-silent`,
because falsifying it needs an imported premise. **The rule held, and `HW-C8` §7.1 names exactly
this as its own overturn condition.** Re-examine with this case in hand. *Read:* `011/score.md` §3.

**(4) Eleven arms, zero refusals, zero dissents.** A2–A5 each predicted or permitted a refusal; none
occurred. The model has now accepted a kinship two lanes called weak. **Whether this model can
decline anything in this register is unknown, and it is starting to look like a property rather than
an accident.** *Read:* `011/sparks.md` UQ1.

## 11. Recommended continuation prompt

> **Continue Horizon Weave cycle 11.** First commit cycle 10 (`runs/011-strained-premise-probe/`,
> `fixtures/011-strained-premise-probe/`, `R2/HW-C10-repeat-stability-design.md`,
> `Decisions/HW-C10-ui-proposal-sequencing.md`, `Findings/HW-C10-abstraction-as-immunisation.md`,
> `R2/HB-010-horizon-brief.md`, `R2/CANDIDATE-REGISTER.md`) as `feat(rehearsal): cycle 10 — A6
> retired, spark-10 replicated, spark-08 weakened`; preserve unrelated dirty/untracked user files;
> do not push or merge.
> **Lane 1 (primary): execute `012-repeat-stability`** per `HW-C10-repeat-stability-design.md`,
> unmodified — three verbatim repeats of arm E, 3 calls + 1 reserve, ≥90 s throttle, temperature
> 0.2, **scoring each in isolation before comparing to 010**, and apply the pre-fixed invalidation
> criteria without softening them. **Report the outcome even if it invalidates published work.**
> **Lane 2 (decision, no calls):** re-examine `HW-C8`'s `frame-contradicts` rule with 011's
> rose-window case in hand — is the under-counting still the right trade? **Lane 3 (spec only):**
> if and only if 012 does not invalidate the ladder, write the `pc-reason` honesty sentence that is
> increment C's unmet precondition; otherwise stop and say why. **Lane 4 (read-only):** nothing new
> — pause. **Lane 5** — HB-011. Model-role split unchanged. All lanes pause after their bounded task.

**Must not happen next:** any UI string changed without an explicit implement instruction; A6
revived without a demonstrated resisted premise; the announcement-only merge fix implemented (it is
authorized, **not scheduled**); any id migration, backfill, repair, production entity, route,
collection or schema change; any push or merge.

## 12. Artifacts

`runs/011-strained-premise-probe/` (manifest, trace, 1 observation, score, critique, sparks,
pre/post-state, instrumented-score) · `fixtures/011-strained-premise-probe/` (2 fixtures) ·
`R2/HW-C10-repeat-stability-design.md` · `Decisions/HW-C10-ui-proposal-sequencing.md` ·
`Findings/HW-C10-abstraction-as-immunisation.md` · `R2/CANDIDATE-REGISTER.md` (spark-10 expanded,
spark-08 weakened) · this brief.
**Production data: not mutated** — four comparisons on two new posts, pre/post byte-identical.
**No code changed.** Live model calls this cycle: **1**.
