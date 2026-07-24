---
title: "Rehearsal Instead of Benchmarking"
category: research
status: emerging
summary: "Situated seeing can't be scored on a leaderboard. Semant evaluates it the way a company rehearses a performance — scored runs over real fixtures, a manifest refused before it's spent, the discipline learned before the generative part is allowed in."
source: the rehearsal programme (vault/Build/Architecture Lab/Vision pipeline/rehearsals) · attunementPlanner.js · perceptPacket.js
---

# Rehearsal Instead of Benchmarking

**Category:** research · **Status:** emerging (the rehearsal method is real and has shaped the engine; the productised harness is maturing)

## Summary
A benchmark asks: on a fixed dataset, what score does the model get? That question barely touches what Semant does, because *situated seeing* has no single right answer — a reading is a claim held against evidence, made by a particular person for a particular purpose. So Semant borrows a different model from the performing arts: **rehearsal.** You run the act over real material, again and again, score the *run* rather than the model, and keep the discipline that survives. Several of the engine's hardest rules were paid for in rehearsal before a line of product code was written.

## The problem it solves
Benchmarks optimise for the measurable, and the most important properties of perception work are not a single number. Did the reading rest on evidence that actually resolves? Did the system refuse a bad request instead of answering it confidently? Did a suggestion stay a suggestion until a human took it? A leaderboard can't see any of that. Worse, chasing a benchmark trains a system to produce *confident answers*, which is precisely the failure Semant is built to avoid — a model that always returns something, whether or not there's anything there.

## What exists now
The rehearsal programme is where Semant's costliest lessons were learned, and its fingerprints are all over the shipped engine:

- **Freeze the ask before you spend.** The rehearsals ran many times over to learn that the value isn't in the model call but in the *manifest* — freezing what was asked, on what evidence, under what constraints, and being able to refuse an invalid request without spending anything. That lesson is now the Percept Packet and the Orchestration Session.
- **Build the guardrail before the generator.** The act grammar and its validators had to exist and be trustworthy *before* anything generative was allowed near them. So the Attunement Planner ships **deterministic** — a lexicon-driven proposer that reads your words and offers matching acts, carrying the exact cues it matched. A planner that hallucinated a field role would be caught and dropped; a planner that produced free prose would have nothing to be caught by. Swapping it for a model later changes only the *source* of the proposals — every one still faces the same validators.
- **Score runs over fixtures, not a leaderboard.** Evaluation is organised as *runs* over concrete fixtures — real images, real asks — with the results recorded as scored performances, so a change is judged by how a rehearsal goes, not by a delta on a benchmark it was never designed for.
- **Honesty is a gradeable property.** Because the engine records what it *couldn't* read (`unreadable[]`), what it *didn't* assess (`external_claims: null`), and what a sentence *cites* versus what it *rests on*, a rehearsal can actually grade whether the system stayed honest — not just whether it was right.

## Why it's built this way
Perception engineering is young enough that its metrics don't exist yet. Reaching for a benchmark now would mean optimising the part that's easy to measure and losing the part that matters — restraint, provenance, refusal. Rehearsal keeps the evaluation close to the real act: run it on real material, watch where it strains, keep the rule that held. It also fits the product's grain — Semant is a workbench for a *practice*, and practices are rehearsed, not benchmarked.

## Where this goes next
- **A productised rehearsal harness** — fixtures, scored runs, and honesty checks a builder can run on a change before shipping it.
- **Benchmarking situated seeing, carefully** — where a measure *is* honest (does cited evidence resolve? is refusal correct?), turn it into a repeatable score, without letting it pull the system toward confident answers.
- **Models on the far end** — once a model authors proposals or readings, rehearsals become the way we tell whether it stayed inside the grammar and the guardrails, run by run.

*Benchmarks ask if the model is right. Rehearsals ask if the system stayed honest while being useful. Semant is built to be graded on the second question.*
