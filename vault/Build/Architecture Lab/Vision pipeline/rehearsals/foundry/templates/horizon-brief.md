# Foundry Horizon Brief — {{RUN_ID}}

**Sandbox:** {{SANDBOX_ID}} · **Axis:** {{AXIS}} · **RESEARCH-ONLY**

> Written **for the orchestrator**, not for the file system. Its job is to let someone who has not
> been watching (a) understand what the program now knows, (b) see where it was wrong, and (c) decide
> the next directive without re-reading every run. Report what is **known**, not what was produced —
> file lists belong at the end. **Sparks stay SPARK; a brief never graduates a candidate.**
>
> This supplements the R2 `HORIZON-BRIEF-template.md` with the four foundry-specific questions in
> §2–§5. A cycle running both a rehearsal and a sandbox writes ONE brief, with these sections folded in.

---

## 1. Header

Sandbox · axis · run id · bounded task · live calls spent ({{MAX_LIVE_CALLS}} budgeted) · commits.

## 2. What axis moved

_The single axis this sandbox was scoped to, and how far it actually moved. If it did not move, say
so — a null on a declared axis is a result. If a DIFFERENT axis moved instead, that is the more
important sentence in this brief._

## 3. What product pressure appeared

_Where the finding pushes on the product, stated as pressure rather than proposal. Distinguish
"belongs in an existing surface" from "wants a future surface". Mark every speculative item._

## 4. What repeated pattern emerged

_Only patterns seen more than once. A single occurrence is a spark, not a pattern. Name the prior
run or sandbox it repeats, and whether the repeat held the same variable constant._

## 5. What should be studied

_2–4 items with **why it matters** and **what to read**. Prefer things where the orchestrator's
judgement is genuinely required over things already settled. This is the section that earns the brief._

## 6. What should NOT be built yet

_Explicit. The temptations this run created, and why each is premature. This section is mandatory —
if it is empty, the run either found nothing or is not being honest about what it wants._

## 7. Method corrections

_Where the instrument was wrong. Mandatory: if nothing was corrected, state whether the cycle was
genuinely clean or insufficiently adversarial._

## 8. Model / runtime constraints

_Provider, model, budget spent vs granted, throttles, failure modes actually observed. Things that
will bite the next executor._

## 9. Next execution expectation

_The single next action, its preconditions, and its stop condition. Plus what must NOT happen next._

## 10. Artifacts

_Files written this cycle. Last, and brief. State plainly: production data not mutated, no code
changed, live model calls this cycle: N._
