---
title: "Beyond the LLM-Centric Picture"
slug: "beyond-the-llm-centric-picture"
date: "2026-08-03"
blurb: "The dominant architecture puts one large model at the centre and treats everything else as plumbing. There is a different shape available, and it is better suited to perception."
series: "Thinking Within Images"
---

Almost every system built in the last three years has the same silhouette. A large model sits at the centre. Around it are tools it may call, memory it may consult, and retrieval it may trigger. The model is the thinker; the periphery is plumbing.

This shape has earned its dominance. It is flexible, it improves for free as the centre improves, and it collapses an enormous amount of engineering into one interface. I am not writing against it in general.

I am writing against it for *perception*, where I think it quietly fails, and where the failure is hard to see because the output looks so good.

## What goes wrong, specifically

Ask a large multimodal model what it sees in a photograph and it will tell you. The answer will be fluent, mostly accurate, and completely undifferentiated. Somewhere inside, in a way neither you nor it can separate, the answer mixes:

- what was actually measured in the pixels,
- what is statistically likely given everything the model has read,
- and what makes for a well-formed sentence.

These are three utterly different epistemic kinds, delivered in one voice, at one confidence. The system cannot tell you which parts of its answer are measurement and which are prior, because internally it does not maintain the distinction. Nothing in its architecture ever required it to.

For most tasks this is tolerable. For looking at images seriously it is disqualifying — because the whole value of looking is finding what is *there*, and a system that cannot separate what is there from what is likely is not looking. It is remembering, eloquently, in the presence of a picture.

> Fluency is not the same as grounding, and only one of them survives contact with a surprising image.

## The other shape

The alternative is not a bigger centre. It is a **decomposed perception layer**: many specialist organs, each measuring one thing and reporting in its own register — objects, properties, chromatic variation, geometric alignment, depth. Each carries an epistemic status with its output. *Measured* is not *interpretive*; *visible* is not *inferred*. The distinction is structural, not a disclaimer appended afterwards.

Above them sits something that composes — call it the conductor — which schedules organs, arbitrates what they report, and assembles a reading. That composing layer may well be a large model. The point is not to banish them; it is to demote them from *the perceiver* to *one role among several*, and to make the perception itself come from instruments that can be held to account.

The gain is that the seams are visible. When a reading says the tilework nests, you can ask which organ said so, what it measured, and how confident it was. When nothing measured it, the reading cannot claim it. The honesty is enforced by the architecture rather than requested in a prompt — which matters, because a prompt asking a model to be careful is a wish, and a wall the model cannot route around is a guarantee.

## A thinker is a role, not a model

One consequence deserves its own name.

If perception is decomposed and the composing layer is one role among several, then no model should be welded into the system anywhere. A thinker is a **role behind a stable interface** — and which model fills that role is a deployment decision, not an architectural one.

This is not future-proofing for its own sake. Different roles genuinely want different models. A chromatic organ and a conductor are not the same job, and the best occupant of each will diverge as the field moves. A system that hardcodes one model everywhere has to be rebuilt each time the frontier shifts. A system with roles just reassigns them.

The corollary is uncomfortable and worth stating: if your architecture would not survive its central model being replaced, the model is not a component of your system. Your system is a wrapper around it.

## What is actually novel

I want to be careful here, because the individual pieces of this are not new and claiming otherwise would be exactly the kind of fluent overreach the whole argument objects to.

Orchestrating specialist vision models under a coordinating agent has been done. Societies of communicating agents with persistent memory have been done — in text worlds, on grids. Retrieval over visual patches has been done. Cross-image relational reasoning is an active benchmark area with real work behind it.

Every *component* has precedent. The *composition* does not: agents embodied in specific image loci, sensing through an epistemically honest decomposed perception layer, moving relationally across images, with horizons as first-class objects, on a substrate where nothing is committed without provenance and nothing is asserted without measurement.

That last clause is the load-bearing one, and it is the part that cannot be retrofitted. Provenance, epistemic status, and propose-never-commit are not features you add to a system that was built without them; they are constraints that shape every seam or they are decoration. A system that learns to be honest late has already built a hundred places where dishonesty was convenient.

## The wager

The bet is that for looking at images, the ceiling on a single-model architecture is not raised by scale. It is set by the fact that the architecture never distinguishes measurement from likelihood, and so cannot show its work — not because it is hiding anything, but because there is no work of that kind to show.

Decomposition costs a great deal. It is slower, more parts, more failure modes, more places to be told there is nothing there. What it buys is a system whose readings you can follow back to the instrument that produced them, and which is capable of the most underrated output in the field:

*Nothing measured that. I cannot say.*
