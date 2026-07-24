---
title: "Manuscript as a Multimodal Field"
category: technical / philosophy
status: emerging
summary: "Writing that stops being a text box beside an image and becomes a surface of the circuit — a sentence can be asked what it cites and answer honestly, including 'nothing' and 'not assessed', with no green ticks and no fake scores."
source: frontend/src/manuscript/manuscriptField.js · differential/recall.js
---

# Manuscript as a Multimodal Field

**Category:** technical / philosophy · **Status:** emerging (field derivation and recall ship; some reference types are honestly marked "does not exist yet")

## Summary
In most tools, writing sits *next to* the image and knows nothing about it. In Semant, the Manuscript is a surface of the same circuit as the marks and percepts: a sentence can be **asked what it rests on** and can answer truthfully — including "nothing," and including "not assessed." It shows no green ticks and volunteers nothing when nothing is wrong. Writing becomes something that can point at its own evidence without being turned into a score.

## The problem it solves
The moment you make writing "cite its sources" and reward it for doing so, you corrupt the thing you were trying to measure. A writer graded on citations will cite to clear the grade, and the record of *where attention actually went* stops being honest. Worse, most systems conflate two very different statements: what the markup *shows* ("this sentence cites nothing") and what the system *concludes* ("this sentence is unsupported"). The first is a record. The second is a judgement — and it's usually one the software has no standing to make. A perfectly grounded sentence, resting on a curator's real looking, may simply be uncited.

## What exists now
The Manuscript field module is **pure**: handed a selection or a percept chip, it answers questions about it and owns no DOM, no store, no network. The distinction it exists to protect is the one most easily lost:

- **RECORD** — what the markup shows. *"cites nothing."*
- **JUDGEMENT** — what the system concludes and owns. *"rests on nothing."*

Semant possesses the first and not the second. So it renders `cites_nothing`, never `unsupported`. There are **no green ticks**; nothing appears when nothing is wrong. The inspector answers when asked, and volunteers only a *real* degradation — for instance, a sentence whose cited evidence has actually decayed since it was written.

The module is also honest about **what kinds of reference exist yet.** Plain text, a selected sentence, a passage, and a percept chip are real today. Ground references, field references, and trace references are named in the model but carry an explicit `exists: false` — the vocabulary is laid down before the feature, and it refuses to pretend the feature is here. (This is the same discipline as the Orchestration Session's honesty invariants: an absent capability says so.)

Alongside it, **Recall** turns a citation back into an experience. A percept mentioned in the writing can *re-perform itself* on the image: the image recedes, the primary ground blooms, supporting grounds enter one after another, and the reading's caption breathes — a short, legible sequence, not theatre. And it stays honest under motion: a ground whose region was replaced by a re-dissection still *exists* but has nothing left to draw, so Recall reports the unresolved evidence rather than performing an empty highlight and asserting a reading over nothing. Under reduced-motion, it skips straight to the composed final state.

## Why it's built this way
This is where Semant's phenomenology becomes engineering. A reading is a claim held *across a gap* from its evidence — never identical to it. So the writing is allowed to point at what it rests on, but the system is forbidden from collapsing "points at nothing" into "is worth nothing." The refusal to render fake causality (`unsupported` where only `cites_nothing` is known) is what keeps the mention-graph — the record of where attention travelled — trustworthy. Green ticks would turn writing into a compliance exercise; their absence keeps it a record of real looking.

## Where this goes next
- **Ground / field / trace references becoming real** — flipping those `exists: false` entries on, each with the same citability gate the marks use.
- **Two-way recall** — click a sentence, watch its evidence perform; click a mark, find the sentences that rest on it.
- **Multimodal passages** — writing modes (description, critique, script, caption) that compose text *with* marks and percepts inline, provenance intact, so a finished piece carries its own seeing with it.

*The Manuscript's promise is narrow and hard: let writing say what it rests on, and never let that honesty be turned into a number.*
