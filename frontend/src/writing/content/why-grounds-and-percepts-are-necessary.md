---
title: "Why Grounds and Percepts Are Necessary"
slug: "why-grounds-and-percepts-are-necessary"
date: "2026-08-06"
blurb: "An image archive becomes a perceptual world only when what is there and what is noticed are allowed to remain different kinds of thing."
series: "Thinking Within Images"
---

# Why Grounds and Percepts Are Necessary

Looking is never only one act. There is what is available to be looked at, and there is the noticing that takes place upon it. Most image systems collapse the two. A bounding box, an embedding, a caption, and a judgment are collected into one loose record called metadata. It is convenient right up until the system needs to ask a serious question: *what, exactly, does this interpretation rest on?*

Semant separates the terms.

A **ground** is a piece of available evidence in the image: a region, a traced field, a path, a boundary, a whole frame, or a composition of such things. A **percept** is an act of noticing that rests on one or more grounds. The ground may remain while the percept changes. The percept may be revised, contested, or multiplied without rewriting the image itself.

```text
ground:  the nested arches in a particular photograph
percept: "The arches make an inward rhythm."
```

The first is a referent. The second is a reading. They need one another, but they must not be confused.

## Ground before belief

This distinction is an epistemic discipline before it is a data model.

Suppose a model says that a garment is severe, or that a temple façade is recursive. These might be useful readings. But what should a person do with them? If the system cannot name the visual material it is responding to, the reading is only a performance of plausibility. There is no route back to the image, no way to refine the claim, and no way for another reading to begin from the same evidence and arrive elsewhere.

Grounds make a claim answerable. They let us say:

```text
This percept rests on these two regions.
This region came from this detector or this curator action.
This frame was the whole image, not a guessed object.
This path and this field were drawn rather than inferred from a label.
```

The vocabulary matters because images do not offer evidence in only one form. A region is not a frame. A field of brushstrokes is not a path. A relation composed from several grounds is not reducible to one rectangle. Treating all of them as an undifferentiated dictionary makes half the world invisible as soon as the system tries to validate or save it.

This is why a ground model must be typed enough to know what kind of evidence it is, but open enough not to erase forms of evidence that arrive later. The world is allowed to grow. The schema is not allowed to silently discard what it does not yet understand.

## Meaning changes faster than evidence

The separation also protects time.

The same visual material can sustain many percepts. A dark field in a photograph might be named as absence, pressure, shadow, restraint, or simply a dark field. Some of these are measurements; some are readings; some will be abandoned. The material should not be rewritten every time interpretation changes.

Conversely, a percept needs to remain attached to the grounds that made it possible even as its wording sharpens. Otherwise later prose can make a claim appear to have always meant what its newest version means. Keeping grounds and percepts distinct lets a system preserve both historical honesty and interpretive movement.

> Geometry can be stable while meaning changes at human speed. A system that treats them as one object loses both kinds of truth.

The principle holds even when the evidence is produced automatically. A segmentation mask may be measured in pixels while its semantic label is interpretive. The mask and the label do not deserve the same confidence merely because they travelled through the same model. Grounds leave room for that complexity; they do not force a single flattering status onto everything an instrument emitted.

## Why this becomes infrastructure

At first, grounds and percepts may sound like careful annotation. Their larger importance appears when movement begins.

An agent cannot inhabit an abstract caption. It needs a locus: somewhere in an image, supported by durable evidence. A movement engine cannot test whether a relation travels from one picture to another if it has only prose on both sides. It needs to know which grounds are being compared. A graph cannot remember an axis such as nestedness if its edges point to temporary model outputs that vanish at the next request.

With grounds and percepts, a path can be made:

```text
region or field
  → grounded percept
  → relation tested elsewhere
  → movement edge
  → reusable axis
```

The relation is never guaranteed to hold. In fact, the system becomes more valuable when it can refuse a tempting relation and preserve the reason for refusal. But refusal is only meaningful when there was something specific to test.

## A world that can be revised

There is a final, practical reason for the distinction: persistence is dangerous. When an interface saves an entire list of loose objects, one field omitted by a later schema can disappear without anyone noticing. The visual world is then quietly rewritten by the act of editing it.

Typed-but-open grounds and percepts are an answer to that danger. They declare the keys that must survive, preserve unfamiliar keys rather than discard them, and avoid inventing empty defaults on the return journey. A round trip is successful only if it drops nothing and adds nothing that was not there.

This is modest engineering in service of a large idea. A perceptual world cannot become alive if its evidence evaporates when someone clicks save. Before agents move, before axes accumulate, before a machine can remember how it came to see something, there must be a durable difference between the world and a reading of the world.
