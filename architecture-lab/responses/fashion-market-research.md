# Fashion market research — reframing Darshan (July 2026)

Deepens Track E with real market grounding. Bottom line: the fashion-AI money sits in **two crowded, reductive camps**; the **creative/editorial "why + story" layer is unautomated and painful** — that's our wedge. And there is **excellent open source (Fashionpedia, DeepFashion, FashionCLIP)** that lets us leapfrog the hand-rolled pipeline. So we should invest here, not walk away.

## 1. The market is real and large
- McKinsey: generative AI could add up to **$275B** in operating profit to fashion/apparel/luxury over 3–5 years; some brands are replacing up to 70% of production workflows; AI content cuts production cost up to 90% / 10× faster.
- So "AI for fashion" is not speculative — it's a funded, active buyer market. The question is *which slice*.

## 2. What's already SOLVED — do not compete here
Two well-funded, commoditized camps. Both reduce an image to a **label or a number**.

**(a) Catalog attribute tagging / product data** — Ximilar, Pixyle.ai, Syte (3,000+ deep tags), YesPlz, AttributeSmart, Hypotenuse. Turn product images into structured attributes + auto titles/descriptions for search/SEO/merchandising. ~95% accuracy, SKU-scale. *Unit of value: catalog metadata + discoverability.* This is a race to accuracy/price we cannot and should not win.

**(b) Trend forecasting** — Heuritech (analyses millions of social images/day, 2,000+ attributes, forecasts up to 24 months, used by LV/Dior), Trendalytics (TikTok velocity, micro-aesthetic trajectory). *Unit of value: market-scale prediction.* Enterprise/luxury, data-science heavy. Not an individual-creative tool.

**(c) Generative content** — product descriptions, lookbook copy, AI photoshoots (Genera, huhu.ai, LTX). Copywriting is "the most sought-after application," but it's **generic and detached from the actual garment** — the exact gap we exploit.

## 3. The UNAUTOMATED gap — our wedge
The creative-direction / editorial layer is where the pain is, and no one automates it:
- **Moodboard drift.** "Too many references, too many opinions, no clear brief." Research, references, concepts live in separate places; it takes weeks; under time pressure some designers skip moodboarding entirely. Boards are *archives*, not *decision tools*.
- **Storytelling is the differentiator — and it's tacit.** Fashion education treats the *story behind the work* as what separates original from derivative (a London College of Fashion educator reportedly failed a student who couldn't tell their collection's story). A good board must answer: *what does it feel like? which shapes/colours/materials lead? what styling makes the story clear?* — i.e. the **articulated why**, part by part. That is precisely Darshan's core act, and precisely what tagging/forecasting/generic-copy tools do NOT produce.

**So the reframe:** the incumbents answer *"what is it"* (tagging) and *"what's trending"* (forecasting). Darshan answers **"why does this work, and what's my story"** — the taste-and-story layer for fashion creatives.

## 4. Open source we should ADOPT (leapfrog the hand-rolled Sūkṣma)
This is the "copy as feature" question — and here the answer is a strong YES; these are on-target and credible, not far-off:
- **Fashionpedia** (Google/ECCV'20) — an **expert-built ontology**: 27 apparel categories, **19 apparel parts, 294 fine-grained attributes** + relationships; 48,825 images with **segmentation masks + per-mask attributes**; a baseline **Attribute Mask-RCNN**. This is exactly the domain part+attribute vocabulary our `garment` Sūkṣma mode is hand-writing — but built by fashion experts and localizable. **Adopt the ontology as our region taxonomy; use its model class for real garment-part segmentation.**
- **DeepFashion / DeepFashion2** — 800K / 491K images, categories, attributes, landmarks, per-pixel masks, pose. Clothing detection/segmentation backbone.
- **FashionCLIP** (patrickjohncyh, built with Farfetch, 800K pairs, on Hugging Face) — fashion-tuned CLIP; image+text in one vector space, zero-shot attribute classification + retrieval **with no training**. This can be our **taste-embedding layer** (taste as vectors, not just label counts) and our semantic labeler.
- **SAM / SAM-CLIP** — class-agnostic masks for arbitrary regions (textures, drape, atmosphere zones) beyond any fixed class list. Fills the "not just objects" need.
- **MMFashion** — open-source visual-fashion-analysis toolbox (attribute prediction, parsing, retrieval) to crib architecture from.

## 5. Narrowed use cases (what to actually build for)
1. **Moodboard-with-reasoning** (the wedge) — annotate references part-by-part with felt reasons → a coherent *brief/story*, not a drifting board. Hits the drift + storytelling pain head-on.
2. **Grounded editorial/PR copy** — `/draft` `/part` produce lookbook/trend/PR copy that cites *this* garment's real parts in *your* voice — beating generic detached AI captions.
3. **A personal taste corpus / signature** — the anatomy catalog becomes a "portrait of your eye" (FashionCLIP-backed): a designer's identity, a student's story engine, a portfolio/resume artifact.

## 6. What this demands of each track (the refurnishing)
- **Track B (segmentation):** replace COCO-YOLO-only with **Fashionpedia ontology + a fashion segmenter (Attribute Mask-RCNN / DeepFashion2) + SAM (arbitrary regions) + FashionCLIP (attribute/semantic labels)**. This is the single biggest upgrade — it's what makes the "felt reading per part" actually domain-deep.
- **Track A (data model):** the unified region schema must carry Fashionpedia-shaped fields: `category`, `part`, `attributes[]`, `material` (the catalog already tracks a materials set — extend it).
- **Track C (Aletheia):** fashion-literate lenses (silhouette, drape, era/reference, styling logic, mood/story); **FashionCLIP embeddings as the taste vector**; RAG over the taste corpus so the writer is grounded in *this image + your history*.
- **Track D (frontend):** Fashionpedia yields MANY parts/attributes → the "non-messy dynamic reveal" (progressive, category-filtered, focus-dims-others) becomes even more load-bearing.
- **Track E (positioning):** narrow the pitch to the **taste-and-story layer for fashion creatives** (stylists, creative directors, fashion students/editorial), explicitly NOT a catalog tagger or forecaster.

## 7. Job-hunting / portfolio angle
The demo that sells: *image in → Fashionpedia-grade part decomposition + a felt reading per part + a taste signature → a grounded editorial piece out.* It's portfolio-worthy AND technically credible (real fashion CV models + a VLM + embeddings/RAG), which reads far stronger than "another GPT wrapper."

## Sources
- [BoF — Fashion marketers' AI playbook](https://www.businessoffashion.com/articles/marketing-pr/fashion-marketers-ai-playbook/) · [SG Analytics — AI in fashion 2025](https://www.sganalytics.com/blog/the-future-of-ai-in-fashion-trends-for-2025/) · [SmartDev — AI use cases in fashion](https://smartdev.com/ai-use-cases-in-fashion/)
- [Heuritech](https://heuritech.com/) · [Trendalytics](https://trendalytics.co/insights/ai-fashion-trends-transforming-the-industry-in-2025)
- [Ximilar fashion tagging](https://www.ximilar.com/services/fashion-tagging/) · [Pixyle.ai](https://www.pixyle.ai/) · [Syte deep tagging](https://www.syte.ai/blog/online-merchandising/deep-tagging-fashion-ecommerce-ai-product-discovery/)
- [Fashionpedia](https://fashionpedia.github.io/home/) · [Fashionpedia paper (arXiv 2004.12276)](https://arxiv.org/abs/2004.12276) · [DeepFashion2 (GitHub)](https://github.com/switchablenorms/DeepFashion2) · [DeepFashion](https://mmlab.ie.cuhk.edu.hk/projects/DeepFashion.html)
- [FashionCLIP (GitHub)](https://github.com/patrickjohncyh/fashion-clip) · [FashionCLIP (Hugging Face)](https://huggingface.co/patrickjohncyh/fashion-clip) · [MMFashion (arXiv)](https://arxiv.org/pdf/2005.08847)
- [The F* Word — creative direction workflow](https://thefword.ai/creative-direction-workflow-fashion-brands) · [Make the Dot — moodboard challenges](https://www.makethedot.com/blog/3-major-steps-and-challenges-when-creating-a-fashion-moodboard-advice-from-fashion-designers)
