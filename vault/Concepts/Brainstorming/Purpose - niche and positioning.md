# Purpose — niche and positioning

The bet for [[Darshan - vision pipeline]]: **the close-reading tool for images.** Most tools tag *objects*; Darshan annotates *felt meaning and aesthetic parts*, learns the curator's taste, and writes with it.

## Candidate niches (Track E to pick 1–2)
- **Fashion curation** — decompose garments (fold, drape, material, silhouette) + atmosphere; build a taste corpus; generate grounded copy.
- **Architecture / interiors** — elements, materials, light, spatial mood.
- **Photography** — composition, light quality, colour fields, atmosphere.

## Why it could be useful / sellable / resume-worthy
- Articulates *why* an image works, part by part — a hard, valuable, unautomated task.
- Accumulates a personal **vision-language** (taste) that then powers writing.
- Differentiator vs Pinterest / Are.na / Cosmos / CLIP taggers: felt-meaning + taste-learning + writing, not similarity or object tags.

## The killer demo (to define in Track E)
One image in → intelligent parts + a deep context-triggered reading + taste signal → a generated piece of writing grounded in the actual visual detail. That end-to-end is the thing to show.

Open question: lead with one niche (likely fashion — richest part vocabulary already scaffolded in the Sūkṣma garment mode) or stay domain-general.

---

## Fashion market reframe (July 2026 research)
Full research: `architecture-lab/responses/fashion-market-research.md`.

**The market splits into two crowded, reductive camps — avoid both:**
- Catalog attribute tagging (Ximilar, Pixyle, Syte, YesPlz) → image → *labels* for search/SEO. Commoditized (~95%).
- Trend forecasting (Heuritech, Trendalytics) → social/runway → *market predictions*. Enterprise.
Generic AI copy tools exist but produce captions **detached from the actual garment**.

**Our wedge = the unautomated creative layer:** *moodboard drift* + *tacit storytelling*. Fashion education itself treats "the story behind the work, part by part" as what separates original from derivative — and no tool produces it. Incumbents answer *"what is it"* / *"what's trending"*; Darshan answers **"why does this work, and what's my story."** Position as the **taste-and-story layer for fashion creatives**, NOT a tagger/forecaster.

**Narrowed use cases:** (1) moodboard-with-reasoning → a real brief, not a drifting board; (2) editorial/PR copy grounded in the actual garment + your voice; (3) a personal taste corpus / "portrait of your eye."

## Open source to ADOPT (leapfrog the hand-rolled Sūkṣma) — see [[Darshan - vision pipeline]]
- **Fashionpedia** — expert ontology: 27 categories, **19 parts, 294 attributes** + masks + Attribute Mask-RCNN. → adopt as the region taxonomy + segmenter (Track B, Track A schema).
- **DeepFashion / DeepFashion2** — clothing detection/segmentation backbone.
- **FashionCLIP** (HF, Farfetch, 800K) — fashion CLIP embeddings → the **taste-vector** layer + zero-shot attribute labels (Track C).
- **SAM / SAM-CLIP** — class-agnostic masks for textures/drape/atmosphere beyond fixed classes.
- **MMFashion** — OSS fashion-analysis toolbox to crib from.

**Portfolio demo:** image → Fashionpedia-grade parts + felt reading per part + taste signature → grounded editorial piece. Credible (real fashion CV + VLM + embeddings/RAG), not a GPT wrapper.
