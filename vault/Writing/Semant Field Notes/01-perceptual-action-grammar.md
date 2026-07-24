---
title: "The Perceptual Action Grammar"
category: technical
status: built
summary: "A closed vocabulary of the things a curator might do next in an image — so a suggestion arrives as a structured, inspectable, editable, refusable act instead of prose or a silent change."
source: frontend/src/differential/perceptualActions.js
---

# The Perceptual Action Grammar

**Category:** technical · **Status:** built (the grammar and its validators ship; the planner that feeds it is deterministic today, a model tomorrow)

## Summary
When something catches your eye, that impulse has to become *something* before software can help with it. Most tools turn it into prose (a caption) or a mutation (a box drawn on the image). Semant turns it into an **act** — a structured object that names what would be done, where it came from, and whether it's been carried through. The Perceptual Action Grammar is the closed vocabulary of those acts. It is the smallest, strictest part of Semant, and everything else leans on it.

## The problem it solves
A model looking at your image can say almost anything. If what it says arrives as free text, there is nothing to check it against — you either believe it or you don't. If it arrives as a change to the image, it has already happened before you agreed to it. Both failure modes have the same root: **the suggestion had no shape.**

Give the suggestion a shape — a typed action with required fields and a fixed set of legal values — and three things become possible at once. You can *inspect* it (see exactly what it proposes). You can *edit* it (change the wording, the target, the strength). And you can *refuse* it (an action that doesn't validate is dropped, with a reason). A shapeless suggestion offers none of these.

## What exists now
The grammar defines nine kinds of act — the verbs of looking:

- **find_parts** — decompose the image into parts.
- **brush_field** — lay down a felt *field*: light, shadow, atmosphere, material, gaze, negative space, threshold, fold, rhythm, recession, pressure.
- **trace_direction** — draw a *direction*: a gaze, a gesture, an architectural axis, the fall of light, implied movement, a comparison path.
- **connect_marks** — name a *relation* between marks: similarity, contrast, tension, kinship, motif-echo, contradiction.
- **compose_percept** — gather grounds into a **reading**.
- **assign_ground_role** — say what a piece of evidence *does* for a reading (anchor, support, counterforce, threshold, field).
- **start_manuscript** — begin a passage in one of several modes (description, critique, philosophical note, script, caption, question list).
- **challenge_percept** — argue against a reading.
- **ask_model_reading** — request a model's reading (as a proposal; nothing is sent in this gate).

Each act carries a **source** (`user`, `system`, `model_suggested`, `fixture`, or `user_confirmed`), a **status** (`proposed → previewed → applied / dismissed / blocked`), a **target**, and a small typed **payload**. Three design rules make the grammar trustworthy rather than merely tidy:

**1. It fails closed.** An action that doesn't validate is not "mostly fine" — it is refused. The normaliser returns *nothing* rather than a half-filled object, because a caller that receives an object will render it, and a half-valid act rendered as a card is exactly the failure the grammar exists to prevent.

**2. It is a vocabulary, not a taxonomy.** The role lists — the kinds of field, the kinds of trace — are *candidates a curator might reach for*, not a classification of the image. They are never stored on any record. An unknown role is a validation error, not a silent nudge to the nearest known one.

**3. Some rules aren't about shape — they're about power.** A `challenge_percept` may *never* be authored by a model; the human's veto over the circuit is a rule in the code, not a convention. An `ask_model_reading` that claims it already dispatched is refused rather than quietly corrected, because a silently-fixed dispatch flag is how an unwanted dispatch happens.

There is a second honesty layer built in: actions carry **warnings that travel with them** and show on the card. "Needs a mark from you on the image." "Proposed only — no model call is made." "Rests on something the frame may not settle." A proposal admits its own weakness instead of hiding it.

Crucially, the thing that *produces* these acts today is a **deterministic planner** (see the Attunement note): it reads the words you used and offers matching acts, carrying the exact words it keyed on. It doesn't detect a gaze; it notices you said "gaze" and offers a way to mark one. The UI says *"suggested acts"*, never *"detected."*

## Why it's built this way
The ordering is the whole point. The grammar and its validators had to exist and be trustworthy **before** anything generative was allowed near them. A planner that hallucinates a field role is caught and dropped; a planner that produced free prose would have nothing to be caught by. So when the deterministic planner is later swapped for a model, only the *source* of the proposals changes — every proposal still passes the same validators, still arrives marked `model_suggested`, still requires your hand to carry it through. The guardrail is built before the thing it guards.

## Where this goes next
- **Model-authored proposals** flowing through the exact same validators — the socket is already the right shape.
- **Actuators**: perception models (segmenters, depth, field predictors) each proposing acts in this grammar, so "the model brushes" still means "the model *proposes a brush* you carry through."
- **Growth of the vocabulary** — new field and trace roles as real use demands them, added as one-line, refusable candidates, never as silent detections.

*The grammar is the contract the rest of Semant is written against. If a future change makes a suggestion easier to accept than to inspect, it has broken the one thing this module is for.*
