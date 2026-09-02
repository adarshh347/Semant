---
title: "The Problem Semant Solves"
slug: "the-problem-semant-solves"
date: "2026-08-27"
blurb: "A poetic reading that never enters the world, or a perception stack that never becomes thought. The hard part is the middle — and the middle is what Semant is for."
series: "Thinking Within Images"
---

# The Problem Semant Solves

Semant does not need the usual “autonomous agent that keeps calling tools until it finishes.” It needs a more unusual kind of agentic life:

> a **perceptual inquiry organism**—a system that can receive a rich, ambiguous human or VLM reading, turn it into bounded questions about a visual world, act through specialised organs, and let what it encounters alter the reading.

The missing property is not intelligence in the abstract. It is **metabolism**: meaning must be transformed into action, action into perceptual material, and perceptual material back into meaning.

Right now, Semant has remarkable organs and a growing vocabulary, but too much of its life is still one-way:

```
prompt → model prose → structured records → more prose
```

or separately:

```
available organ → mask / region / feature / mark
```

The system needs the closed loop:

```
aesthetic reading
  → what precisely is being proposed?
  → which part could be exposed to the world?
  → what must be looked at, and by which organ?
  → organ produces a real artifact
  → artifact becomes a percept/ground
  → the original reading is strengthened, narrowed, complicated, or refused
  → next question changes because of that result
```

That is the kind of “life” the project is demanding.

## The real problem: translating across two incompatible languages

At one end, a VLM is extraordinarily alive and creative. Given your images, it can say:

> The folds no longer merely cover the body; they make stone behave as veil, skin, metal, pressure, or atmosphere.

That sentence is valuable. It notices a relation human cataloguing systems would likely miss. We do not want to flatten it into tags like `fold: yes`, `material: marble`, `transparency: 0.7`.

At the other end are Semant’s reliable operations:

```
segment a phrase
ground an entity
derive a mask
measure overlap
compare contours
inspect depth
inspect shading
retrieve a related region
trace a provenance chain
```

These are narrow, deterministic, and inspectable. But none understands “sensuality,” “tactile philosophy,” or “stone becoming veil.”

The challenge is the middle translation:

```
creative language
      ↓
structured perceptual possibility
      ↓
what visual organization is being claimed?
      ↓
what would count against it?
      ↓
what observable relation bears on it?
      ↓
which registered capability can inspect that relation?
      ↓
real artifact
      ↓
a revised—not mechanically replaced—interpretation
```

If that middle is absent, we get two bad outcomes:

- a poetic VLM answer which sounds intelligent but never enters the world;
- a technically precise perception stack which produces masks and numbers but never becomes thought.

Semant’s purpose is to make those two worlds circulate through one another.

## The agentic mode Semant needs

It should be a **society of constrained minds**, not one grand “agent brain,” and not a swarm for its own sake.

Each mind has a distinct right and limitation.

|Mind|Its job|What it must not do|
|---|---|---|
|Inquiry reader|Read the user’s words into hypotheses, comparisons, ambiguities, and requests|See pixels or invent observations|
|Prompt-blind observer|Describe one image’s visible organization|Know the thesis it is meant to support|
|Alignment mind|Relate frozen observations to the user’s proposition|Invent new observations|
|Operationalizer|Translate a semantic possibility into an observable question and candidate capability classes|Claim a tool result before a tool runs|
|Deterministic resolver|Match a capability class to an actually registered organ|Make aesthetic judgement|
|Perceptual organ|Produce a mask, geometry, depth relation, feature map, or other artifact|Decide what it means philosophically|
|Relation critic|Ask whether a proposed relation is actually warranted, thin, circular, or contradicted|Produce its own supporting evidence|
|Composer|Write a human-readable reading from declared materials|Smuggle unsupported claims into prose|
|Human curator|Decide when the system should continue, reframe, accept a mark, or keep a question open|Be silently replaced by model agreement|

That is not bureaucracy. It is a division of cognitive labour.

A human art historian does something similar without naming it. They see something evocative, isolate a visual condition, inspect it more carefully, compare it to another work, consult material evidence, revise the interpretation, and decide what remains open. Semant needs to enact this process computationally.

## What “dissolution” actually means

Dissolution does **not** mean destroying poetic thought into database fragments.

It means giving every part of a rich thought a different home, so it can remain alive without becoming confused with the others.

Take this:

> The covered face feels transparent because the folds cling to the anatomy, allowing skin and expression to remain present beneath the marble veil.

It should dissolve into a small constellation:

```
Visible observation:
A covering is present over the face.

Visible organization:
Fold ridges follow the nose, cheek, and brow contours.

Appearance effect:
The facial anatomy remains visually legible beneath the covering.

Interpretive possibility:
The stone creates an effect of transparency.

Possible causal hypothesis:
Contour-following drapery contributes to apparent transparency.

Operational question:
Can face and veil regions be grounded separately, and do their boundaries/areas overlap
while facial structure remains detectable?

Potential organs:
phrase grounding → concept segmentation → mask relation / contour analysis.

Interpretive remainder:
Even if those spatial relations are measured, “sensuality” and the artistic force of the veil
remain interpretive rather than measurable facts.
```

The entire original idea remains. But now Semant knows where it may act, where it may only speculate, and where it must ask a person.

That is much closer to intelligence than generating a more polished paragraph.

## Why an observation inventory is the first living tissue

The inventory is not a final ontology. It is the first material that can travel between minds.

A VLM might say, in prose:

> The Buddha’s folds are sharper and more metallic, while the veiled woman’s folds dissolve into the face.

The inventory lets this become separate, attributable materials:

```
Image: Buddha
- fold ridge
- sharper boundary
- deeper shadow separation
- effect: thickness / rigidity
- possibility: metallic or architectural density

Image: veiled woman
- shallow face-following ridge
- continuous contour with facial plane
- effect: anatomy remains legible
- possibility: apparent transparency
```

Only after this can a contrast planner ask:

```
What is the actual contrast?

A: boundary separation and high ridge contrast
B: contour continuity and low ridge separation

What would undermine it?

If the woman’s veil also has deep, detached ridges,
or the Buddha’s drapery follows anatomy with comparable continuity,
the proposed distinction weakens.
```

Only then can an operationalizer say:

```
Possible test:
Compare ridge/edge concentration, mask adjacency, contour alignment,
or shading discontinuity across selected regions.
```

The observation inventory is therefore not a fancy data format. It is the conversion layer between **perceptual language** and **perceptual work**.

## What the external world says

There are close relatives to this idea, but Semant’s combination is unusually specific.

ReAct established a foundational principle: reasoning and acting should interleave. A model’s verbal reasoning should guide actions, and results from the world should update later reasoning. Semant shares that logic, but its “world” is a visual/perceptual world rather than a web page or database. [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)

Visual ChatGPT showed that a language model can coordinate specialised visual foundation models for multi-step image work. But its primary orientation was image answering/editing; Semant’s more difficult ambition is to preserve the distinction between visual description, interpretation, measurement, and curator commitment. [Visual ChatGPT](https://arxiv.org/abs/2303.04671)

ViperGPT demonstrated that an LLM can compose vision modules into executable programs. That is close to Semant’s “semantic possibility → operation” problem. Its weakness for Semant is that generated programs can be flexible but are not, by themselves, an epistemic record of what a visual result licenses aesthetically. [ViperGPT](https://arxiv.org/abs/2303.08128)

Recent active-perception research reaches the same broad conclusion: VLMs work better when they can decide what further visual information to obtain—cropping, zooming, probing, or using a specialised tool—rather than treating the first view as sufficient. [AP-VLM](https://arxiv.org/abs/2409.17641) and [GUI-Eyes](https://arxiv.org/abs/2601.09770) are useful neighbours.

Industry agent guidance makes a complementary point: the most reliable systems are not unbounded model monoliths. They use explicit workflows where predictability matters, reserve model judgment for ambiguity, use tool outputs as environmental feedback, and evaluate traces rather than only final answers. [Anthropic’s agent architecture guidance](https://www.anthropic.com/engineering/building-effective-agents) and [tool-design guidance](https://www.anthropic.com/engineering/writing-tools-for-agents) support that direction.

Finally, Semant’s provenance instinct has a real intellectual lineage. The W3C PROV standard treats entities, activities, and agents as distinct things whose derivation can be represented and queried. Semant goes further by attaching epistemic distinctions—what was observed, measured, proposed, interpreted, accepted, or refused—to that lineage. [W3C PROV-O](https://www.w3.org/TR/prov-o/)

So Semant is not trying to invent “agents with tools” from nothing. Its distinctive contribution is this:

> build a perceptual, provenance-bearing, human-steerable inquiry loop in which creative visual thought can cause real perceptual action without being falsely reduced to measurement.

## The crucial design rule

The model should retain freedom only where freedom is meaningful:

```
creative noticing
comparison
hypothesis formation
counterexample generation
interpretive composition
asking the human a good question
```

The system should become deterministic wherever a claim touches the world:

```
capability vocabulary
tool resolution
input artifact selection
parameter validation
execution
stored result
provenance
epistemic status
replay
```

This is not a compromise between creativity and rigor. It is how each protects the other.

Without creative language, the machine has no reason to look.

Without deterministic action and provenance, the language never meets resistance from the world.

Without return flow, tools merely decorate the answer.

The next build milestone should therefore be named plainly:

> **The first perceptual circulation:** an observation inventory generates one operational question; Semant calls one real organ; the organ returns a typed artifact; and the inquiry visibly revises one interpretation from that artifact.

Once that exists, the simulation, atlas, editor, agents, and specialist organs will have something alive to participate in.