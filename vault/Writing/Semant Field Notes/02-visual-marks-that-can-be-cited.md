---
title: "Visual Marks That Can Be Cited"
category: technical
status: built
summary: "A renderer-independent truth for everything drawn on an image, and a quarantine that keeps model suggestions from laundering themselves into evidence — so a passage can cite a mark and the citation actually means something."
source: frontend/src/differential/visualMarks.js · suggestionQuarantine.js · markStaging.js
---

# Visual Marks That Can Be Cited

**Category:** technical · **Status:** built

## Summary
A mark on an image is easy to draw and surprisingly hard to *trust*. Semant treats every mark as a small, renderer-independent record of truth — not a shape a drawing library happened to make — and wraps model-proposed marks in a quarantine so that accepting one leaves a visible trail. The payoff: a sentence can **cite** a mark, and that citation is a real claim about real, human-owned evidence, not a decorative link.

## The problem it solves
Two quiet failures haunt annotation tools.

First, **the renderer becomes the ontology.** If a mark is "a Konva line" or "a Fabric path," then the drawing library's schema silently becomes your data model, and the day you change renderers you lose your meaning. A mark should be true independently of whatever draws it.

Second, **suggestions launder into evidence.** A model proposes a region; you click accept; now it looks exactly like something you drew yourself. A week later no one — including you — can tell which marks were yours and which a model talked you into. When those marks then get *cited* by your writing, the citation is quietly resting on the model's authority while wearing your name.

## What exists now
**The `visual_mark` is the truth; the drawing is a view.** A Konva line or a Fabric path is only ever a *rendering* of a mark. Serialising a library's scene graph would make its schema Semant's ontology — so Semant keeps its own small model (fields, traces, relations, frames, collections, and segmented `region_mask`s) and, like the action grammar, **fails closed**: an invalid mark comes back as nothing, never as a partial object.

**Sources are honest and specific.** A mark records not just *that* a model was involved but *how*: `user` (untouched by a model), `user_confirmed` (the model proposed it, you accepted), `model_suggested` (still in quarantine), `model_refined` (you drew it, a model tightened it), `imported` (from outside this session). "I drew this," "I approved this," and "a model tightened mine" are three different provenances, and the system can tell them apart.

**The quarantine makes acceptance leave a trail.** This is the load-bearing idea, borrowed from two lessons in the field. From Label Studio: accepting a suggestion **mints a new mark that points back at the suggestion**, and the suggestion is preserved untouched — so `user_confirmed` is a *derived fact* (a mark whose lineage resolves to a suggestion), not a flag someone had to remember to set. From the opposite lesson of tools where provenance was stored but never shown: every mark can **say what it is, out loud, in the UI.** A provenance nobody can see is no provenance at all.

**Citability is a derived rule, and it lives in exactly one place.** A mark may be cited by a percept *if and only if* it is committed, its source is the curator's own or confirmed by them, and it actually has geometry. Every clause is a real gate:

- not committed → it's still in flight; citing it cites a draft;
- still `model_suggested` → citing it launders a suggestion into evidence;
- geometry still `unresolved` → it's a role with no shape; citing it cites nothing.

Because the rule is *derived, never stored*, it can't drift out of sync with the mark's real state — there is no cached "citable: true" to go stale.

**Arming is not drawing.** When a proposed act becomes a mark, it arrives with `unresolved` geometry — the planner never touches the image, so the mark has a role and no shape until *your hand* supplies the geometry. A model can propose *that* a gaze be traced; only you decide *where* it goes.

## Why it's built this way
The through-line of the whole engine is one sentence: *the model may suggest; Semant shapes; you confirm.* Marks are where that sentence meets the pixels. If acceptance were a silent status flip, the sentence would be a slogan. Because acceptance mints a back-pointing mark and citability is gated on human ownership, the sentence becomes an invariant the code enforces — you cannot construct a suggested mark outside the quarantine, and you cannot cite one until you've made it yours.

## Where this goes next
- **Model-refined geometry** as a first-class, visibly-marked path (you draw, a segmenter tightens — clearly not the same as either drawing alone).
- **Cross-surface citation** — a mark cited from the Manuscript that can *recall* itself back on the image (see the Recall and Manuscript notes).
- **Segment-to-reading discipline** — a `region_mask` is *what was segmented*; the perceptual reading of it stays a separate, explicit act, so a shape is never mistaken for a felt field.

*The test of this system is simple: at any moment, every mark can tell you where it came from, and nothing your writing cites can secretly belong to a model.*
