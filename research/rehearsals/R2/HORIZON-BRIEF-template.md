# Horizon Brief — template

**Purpose.** A Horizon Brief is written *for the orchestrator*, not for the file system. Its job is
to make someone who has not been watching able to (a) understand what the program now knows, (b)
see where it was wrong, and (c) decide the next directive without re-reading every run.

**Cadence.** One brief per Horizon Weave cycle — i.e. after each primary rehearsal plus whatever
read-only scouts ran alongside it.

**Rules.**
- Report what is *known*, not what was *produced*. File lists belong at the end, not the top.
- Method corrections are mandatory, not optional. If nothing was corrected, say so explicitly —
  a cycle with no correction is either genuinely clean or insufficiently adversarial, and the brief
  must say which.
- Every claim gets an evidence pointer. Anything unverifiable is labelled as such.
- Sparks stay SPARK. A brief never graduates a candidate.
- Distinguish three registers everywhere: **what exists**, **what the evidence supports**, and
  **what is speculation**.

---

## 1. Cycle header
Cycle id · date · primary rehearsal executed · scouts run · commits.

## 2. What changed
The 3–6 things now true that were not true before. Each with an evidence pointer. Prose, not lists
of files.

## 3. Method corrections
Where the program's *instrument* was wrong, not just its answer. For each: what was believed, what
proved it wrong, what changed as a result, and whether any earlier conclusion is affected.
State plainly if a prior result stands or falls.

## 4. Data integrity findings
Anything discovered about production data health. Counts, affected ids, and whether harm has
actually landed or is merely possible. **Never repaired inside a rehearsal** — record only.

## 5. Model / runtime constraints
Provider, model, budgets, throttles, failure modes actually observed. Things that will bite the
next executor.

## 6. Candidate sparks
Each spark: one line of claim, evidence source, and what would kill it. Full detail lives in the
candidate register, not here.

## 7. UI / product opportunities
Only what the cycle's evidence actually motivates. Mark speculative. Separate "belongs in an
existing surface" from "wants a future surface".

## 8. What the orchestrator should study deeply
2–4 items, with *why it matters* and *what to read*. This is the section that earns the brief.
Prefer things where the orchestrator's judgement is genuinely required over things already settled.

## 9. Next execution expectation
The single next primary action, its preconditions, and its stop condition. Plus what must NOT
happen next.

## 10. Artifacts
Files written this cycle. Last, and brief.
