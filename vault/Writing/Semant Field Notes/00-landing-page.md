---
title: "Semant — A Workbench for Perception Engineering"
kind: landing-page-copy
status: draft (docs pass — SEMANT-LANDING-001)
audience: public + technical
reduced_motion: the composed hero still is the fallback
---

# Semant — A Workbench for Perception Engineering

> Copy is final-intent draft for the frontend pass. Section numbers match the IA in
> `SEMANT-LANDING-001-product-article-system.md`. Status chips: **built · emerging · horizon**.

---

## 1 · Hero — The Great Arrival

**Headline:**
# Turn visual captivation into structured action.

**Subheadline:**
Semant is a perception engineering workbench — where images become fields, marks become citations, writing recalls what it rests on, and models propose actions without silently becoming authority.

**CTAs:**
`Explore the Workbench` · `Read the Technical Notes` · `View Research Horizons`

*(Behind the words: a small figure at the lower edge watches an enormous hand-drawn meteor arrive across a twilight sky, its tail threading into cyan, violet, coral, and gold — a captivation, marked, remembered. See the visual spec.)*

---

## 2 · What Semant does

Something catches your eye. Today that moment goes one of two places: into a caption a model wrote for you, or into a rectangle you drew and labelled. Semant gives it somewhere better to go — a set of **acts** you can inspect, edit, and take back.

Seven verbs, one surface:

- **Notice** — say, in plain words, what caught you. Semant turns it into *suggested acts*, never claims it saw what you saw.
- **Mark** — put a field, a trace, or a region on the image: the fall of light, an axis, a drape, a gaze.
- **Compose** — gather marks into a **percept**: a reading, not a list. "The arch, *held against* the shadow."
- **Cite** — write a passage that points at the exact marks it rests on. The citation is real, not decorative.
- **Recall** — replay a percept: the image steps back, its evidence performs in turn, the reading breathes.
- **Challenge** — argue with a percept from the image itself. (Only a person may author a challenge — never a model.)
- **Orchestrate** — freeze the whole working context — image, selection, writing, evidence, what was asked — into one inspectable session a model *could* be asked to read.

Every one of these is a structured object with a provenance and a status. Nothing here is loose chat.

---

## 3 · The Workbench

Semant has two working surfaces today, and room for more.

**Differential — the image-side perception workshop.**  `built · growing`
Where seeing becomes marks. You tell it what caught you; it offers acts; your hand places the geometry. Marks become grounds, grounds become percepts, percepts can be recalled. The image is not a backdrop to a chat — it is the instrument.

**Manuscript — the writing-side multimodal field.**  `emerging`
Where writing stops being a text box beside a picture. A sentence can be *asked what it cites* — and answers honestly, including "nothing" and including "not assessed." No green ticks, no fake scores; the page only speaks up when something it rested on has actually decayed.

**Atlas & Codex — comparative and time surfaces.**  `horizon`
Where percepts across many images, and across time, can be held together — motifs, returns, a body of taste. Being explored, not yet built.

Semant is growing toward several **forms** of the same workbench: a web studio today; a desktop application in the spirit of a coding studio crossed with an orchestration cockpit; a CLI for technical users and automation; a phone app for everyday capture; and, later, an agent-facing engine.

---

## 4 · The Engine

Under the workbench is a small, strict engine. Its whole job is to keep one promise: **the model may suggest; Semant shapes; you confirm.**

- **Perceptual Action Grammar** `built` — a closed vocabulary of the things you might do next in an image (mark a field, trace a direction, connect marks, compose a percept, start a manuscript, challenge a reading, ask a model to read). Every proposal is validated; an invalid one is *refused*, not "mostly kept."
- **Attunement Planner** `built` — turns what you said caught you into suggested acts, carrying the exact words it keyed on. It reads "gaze" and offers a way to mark one — it never claims it *saw* a gaze.
- **Visual Marks** `built` — a renderer-independent truth for every instrument. A drawn line is a *view* of a mark, never the other way around.
- **Suggestion Quarantine** `built` — model suggestions are held apart. Accepting one *mints a new mark that points back at the suggestion*, so an approval can never be laundered into looking like your own decision.
- **Orchestration Session** `emerging` — assembles the whole current circuit into one frozen, inspectable request, able to refuse an invalid ask *without spending anything*. Nothing is dispatched yet; that's the point of building the discipline first.
- **Provenance & Citation** `built` — every mark can say, out loud, what it is and where it came from. Only committed, curator-owned marks with real geometry may be cited.
- **Mark Recall** `built` — a percept can re-perform itself from the writing that mentions it.
- **Tool pathways / actuators** `emerging` — the grammar is the socket into which perception models (segmenters, depth, fields, readings) plug — each proposing an act, none authoring the image.

---

## 5 · Who it is for

Anyone whose work begins in being caught by an image.

- **Fashion designers** — build a moodboard-with-reasoning: mark *why* a garment works, part by part, and let it become a taste you can write in.  `built · growing`
- **Filmmakers & directors** — read a frame's gaze, axis, and light as marks; keep a shot's reasoning, not just a screenshot.  `emerging`
- **Writers** — compose passages that genuinely rest on what you saw, and can prove it.  `built`
- **Artists** — treat an image as an instrument: fields, traces, negative space, rhythm — the felt parts, named.  `built`
- **Researchers** — accumulate percepts and their evidence into something inspectable and comparable.  `emerging`
- **Curators** — turn a stream of captivation into a structured, citable body of looking.  `built`
- **Architects & designers** — mark axes, thresholds, and recession; read how an image builds its space.  `emerging`
- **AI builders & agent engineers** — a grammar and an orchestration session that let models *act on seeing* without becoming its authority.  `horizon`

---

## 6 · Perception Engineering

There's a phrase for what happened to software in the last few years: **agentic engineering.** We gave language models a grammar of actions — read a file, run a test, open a pull request — and suddenly they could *do* software work, inside guardrails, with a human in the loop.

Seeing never got that. Images still arrive at models as one flat request and leave as one flat caption. There is no grammar of *perceptual* acts, no record of what a reading rested on, no way for a model to propose a way of looking without quietly becoming the authority on what's there.

**Perception engineering** is that missing layer. It gives humans, models, and agents access to *situated seeing*: a vocabulary of marks and percepts, a provenance for every one, an orchestration session that freezes what was asked on what evidence, and a hard rule that a suggestion is not evidence until a person makes it so.

Semant is building both halves — the **engine** that makes the acts real and the **workbench** where people perform them.

---

## 7 · Research & philosophy

Semant's design isn't decoration borrowed from theory; each idea earns its place by becoming a capability.

- **Embodied & enactive cognition** — perception is something you *do*, not something done to you. So Semant's core unit is an *act*, not a label.
- **Phenomenology (Merleau-Ponty)** — seeing happens across a gap between the seer and the seen. So a percept holds a reading *against* its evidence rather than collapsing into it, and even the hero's meteor never quite touches the figure.
- **Gestalt figure-ground** — meaning lives in what is shaped by not being there. So *negative space* is a first-class field you can mark.
- **Gaze studies** — where a look goes is data. So gaze and address are traces you can draw and cite.
- **Colour, material, and the architecture of perception (Pallasmaa, Casey)** — light, surface, threshold, and recession are how an image builds a felt space. So they are field roles, not afterthoughts.
- **Assemblage thinking (Deleuze / DeLanda)** — a reading is parts held in relation. So percepts are compositions of grounds with roles, and relations (contrast, tension, kinship) are their own marks.
- **Psychoanalysis of the image** — what an image withholds matters as much as what it shows. So a reading may name its own uncertainty and what stays concealed.

We write about each of these in the field notes — tied, every time, to something the workbench actually does.

---

## 8 · Feature notes (deeper reading)

The landing is the view from altitude. Each mechanism has its own note:

- **The Perceptual Action Grammar** — how a captivation becomes a structured, refusable act.  `technical · built`
- **Visual Marks That Can Be Cited** — why a mark, not a rectangle, and why citability is derived, never stored.  `technical · built`
- **The Orchestration Session** — freezing what was asked, on what evidence, before anything is spent.  `technical · emerging`
- **Manuscript as a Multimodal Field** — writing that can say what it rests on, honestly.  `technical · emerging`
- **Rehearsal Instead of Benchmarking** — why we score runs of situated seeing, not leaderboards.  `research · emerging`
- **Perception Engineering** — the whole claim, in one place.  `hybrid · horizon`

---

## 9 · Product forms

One workbench, several doors:

- **Web workbench** — the Differential and the Manuscript in the browser. `built · growing`
- **Desktop studio** — a perception cockpit in the spirit of a modern coding studio crossed with an orchestration workspace: multiple surfaces, sessions, model pathways. `horizon`
- **CLI** — the grammar and the session for technical users and automation, scriptable and inspectable. `horizon`
- **Phone** — everyday capture: catch an image, mark what caught you, let the reading grow later. `horizon`
- **Agent-facing engine / API** — the same grammar and session offered to agents, so a model acts on seeing through the same guardrails a person does. `horizon`

---

## 10 · Footer — Afterimage

Most tools want to tell you what an image *is*. Semant is building something quieter: an interface where perception can be **marked, questioned, remembered, and returned** — where the thing that caught you doesn't disappear into a caption, but becomes an instrument you can think with.

The sky settles. The thread that reached toward the figure has become a small kept mark beside them.

**Semant — where images become instruments for thought.**

`Explore the Workbench` · `Read the Technical Notes` · `View Research Horizons`
