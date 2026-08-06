---
title: "Thinking Within Images"
slug: "thinking-within-images"
date: "2026-08-06"
blurb: "An embodied perceptual agent is not a model handed an image. It is a situated process with a locus, a limited body of organs, and a memory of what it encountered from there."
series: "Thinking Within Images"
---

# Thinking Within Images

Most image AI thinks *about* an image from nowhere. The entire frame enters a model; the model returns a description; the description speaks with the authority of a view that was never located. This is efficient, and it has an important cost: no one can distinguish what the system saw from where it stood from what it inferred from the image as a whole.

An embodied perceptual agent begins with the opposite constraint. It does not receive an image in full. It **inhabits a locus** within a perceptual world. It has a current position, a limited set of senses, a history of prior encounters, and a goal. What it knows is knowledge from where it stands.

```text
agent = locus + organs + trajectory + episodic memory + goal
```

This is not an attempt to pretend that a program is an animal. It is a way of making locality operational. If a system claims to have found a relation in an image, we should be able to ask: which part of the image did it inhabit, which instrument perceived it, and what path led it to the claim?

## A world made of perceptual material

The agent's world is not a game-engine replica of the photograph. It is made from the image's available perceptual material: regions, frames, fields, paths, marks, grounds, and the relations that have been measured between them.

At a locus, an agent may invoke only the organs bound to its body. A geometric agent may ask whether its region is nested within another. A chromatic agent may encounter a gradient. A depth-oriented agent may find recession or foreground. These are not personality traits pasted onto a chatbot; they are consequences of which perceptual instruments the agent can actually call.

That produces a useful form of partiality. A geometric agent and a chromatic agent can stand at the same place and have different fields of experience, because their organs disclose different relations. Neither needs to possess the whole image in order for their difference to matter.

> Situatedness is not a limitation imposed on intelligence. It is the condition that gives a claim a point of view.

The first implemented form of this idea is intentionally small: one agent inhabits one region in one image. It perceives through its bound organs, records what those organs found, and reports an observation. It does not yet freely cross images or converse with another agent. That restraint is important. A world should be expanded only after the evidence that supports the next kind of movement is strong enough.

## Private experience and shared memory

Embodiment reveals a distinction that ordinary agent systems often blur.

When an organ measures something from an agent's locus, that result can become part of the agent's private episodic memory. The agent is entitled to live on what its body perceived; it need not wait for a human being to approve the existence of its own sensory event.

But private experience is not automatically public knowledge.

The agent's report to the shared ledger remains a proposal until the relevant mark is committed. The same underlying observation therefore appears differently in two places:

```text
private agent memory:  organ-backed reading, with its actual epistemic basis
shared world ledger:   a proposed observation, pending curator commitment
```

This is not a contradiction. It separates what happened to the agent from what the community of the system is prepared to remember as durable knowledge. Without that separation, either the agent becomes blind until a person approves every sensation, or an automatic run silently rewrites the world's truth.

## Why language is kept outside the body

The agent's first-person form is dangerous because it is persuasive. "I found recursive arches" sounds like experience even when it might be borrowed from a language model's prior. So the perceptual agent is kept deliberately narrow: it cannot call a general thinker to invent claims. It can report only what an organ of its own measured from its own locus. A claim about a place it did not inhabit, or about a relation no bound organ found, is refused as hearsay.

This is the practical difference between an embodied agent and a chat interface that says "I see." The latter has a pronoun. The former has a constraint.

As the world grows, agents will be able to move along grounded horizons, exchange partial reports, and inhabit carefully declared hybrid worlds. But those later capacities must inherit the same rule. Dialogue may form a hypothesis; it cannot upgrade a hypothesis into a measurement. A hybrid world may be imaginatively fertile; its discoveries count only when grounded back in a real image.

To think within images is therefore not to simulate consciousness in miniature. It is to build a system in which perception has a location, memory has a history, and language is answerable to what a body could actually have encountered.
