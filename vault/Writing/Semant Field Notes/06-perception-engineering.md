---
title: "Perception Engineering"
category: hybrid manifesto
status: horizon
summary: "Agentic engineering gave language models a grammar of software actions. Perception engineering is the missing layer that gives humans, models, and agents access to situated seeing — with provenance, refusal, and a hard line between a suggestion and evidence."
source: the whole engine (perceptualActions.js · suggestionQuarantine.js · orchestrationSession.js · manuscriptField.js)
---

# Perception Engineering

**Category:** hybrid manifesto · **Status:** horizon (the identity Semant is building toward; grounded in an engine that already exists)

## Summary
Over the last few years software got a new interface. We gave language models a *grammar of actions* — read a file, run a test, open a pull request — and with a human in the loop they became able to *do* software work. We called it agentic engineering. Seeing never got that layer. **Perception engineering** is the name for building it: a grammar of perceptual acts, a provenance for every one, an orchestration session that freezes what was asked, and a hard rule that a model's suggestion is not evidence until a person makes it so.

## The claim, plainly
Agentic engineering made language models *act on software.* Perception engineering lets humans, models, and agents *act on situated seeing.*

That word — *situated* — is doing the work. Not "recognise objects." Not "caption the scene." Situated seeing is looking that belongs to someone, aimed at something, held against evidence, for a purpose: the fall of light *in this frame*, the drape *held against* the shadow, the gaze that addresses *you*. It is the seeing a curator, a director, or a designer actually does. No model can be handed that authority, because the authority isn't in the pixels — it's in the person looking. But a model can *participate*, if the interface is built to let it propose without letting it decide.

## Why the old interface fails
An image today arrives at a model as one flat request and leaves as one flat answer. Three things are missing, and they're the three things engineering is for:

- **No grammar.** There's no vocabulary of perceptual acts — no "mark this field," "trace this axis," "compose this reading" — so a model's contribution can only be prose, which can't be inspected, edited, or refused.
- **No provenance.** Nothing records what a reading rested on, so the moment a suggestion is accepted it's indistinguishable from a human's own looking, and the trail of *where attention went* is lost.
- **No refusal.** Nothing can decline a bad request before paying for it, and nothing can say "I couldn't read that" or "I didn't assess this" — so the system always returns something, whether or not there's anything there.

## Why model suggestions are not evidence
This is the load-bearing conviction, and it's why Semant is built the way it is. A suggestion is a *proposal*: it might be right, it might be a hallucination, it's owed inspection. Evidence is something a person has *taken* — looked at, agreed to, made theirs. Collapse the two and you get the failure mode of every confident AI tool: the model's guess wearing the human's authority. So in Semant, accepting a suggestion mints a new, back-pointing mark rather than flipping a flag; a mark can only be cited once it's committed and curator-owned; a model may never author a challenge; and an orchestration session can refuse an invalid ask without spending a thing. The line between *proposed* and *carried through* is drawn in the code, not left to good intentions.

## Why a grammar matters
Give perception a grammar and everything downstream becomes possible: a suggestion gains a shape you can inspect and refuse; a model can plug into the *same socket* a person uses, proposing acts that face the same validators; an agent can be handed the workbench and act on seeing through the exact guardrails a human does. Without the grammar, "let the model help you see" can only mean "let the model tell you what's there" — which is the thing we're trying to get away from.

## How the workbench and the engine meet
Perception engineering has two halves, and Semant builds both. The **engine** makes the acts real — the action grammar, the visual marks and their quarantine, the orchestration session, provenance, recall. The **workbench** is where people perform them — the Differential (seeing becomes marks) and the Manuscript (writing that can say what it rests on). The engine without the workbench is a library nobody feels; the workbench without the engine is another annotation tool. Together they're a place where a captivation becomes a mark, a mark becomes a reading, a reading becomes writing that remembers its evidence — and a model can help at every step without ever quietly becoming the authority.

## Where this goes next
- **Models as perceptual collaborators** — segmenters, depth, fields, and readings proposing acts in the grammar, each a suggestion, none an author.
- **Agent-facing perception** — the same session and grammar offered to agents, so automated seeing runs inside the same refusal-and-provenance guardrails.
- **A practice, and its tools** — desktop, CLI, and phone forms of one workbench, and a way to rehearse whether the whole thing stays honest as it grows.

*Agentic engineering taught software to act with us. Perception engineering is teaching sight to do the same — carefully, with the human keeping the authority that was always theirs.*
