# Darshan — the vision pipeline

**Darshan** (working name) is the unified **see → mark → understand → write** pipeline of [[Drishya and Semant]]. It's an initiative, not a UI lane — it spans purpose, frontend, backend, and AI. Full brief + research tracks live in `architecture-lab/vision-initiative/`.

## The purpose thesis
**Structured aesthetic close-reading of images** — the visual equivalent of literary annotation, that also *learns your taste and writes with it.* Not object tagging (generic CV); felt-meaning + taste-learning. See [[Purpose - niche and positioning]].

## Current state (as of this study)
- **Two annotation systems (the core duplication):** `bounding_box_tags` (manual pixel rects, `BoundingBoxEditor`) vs `region_annotations` (auto polygons + notes). Must unify into one region model.
- **Segmentation:** `segmentation_service.py` = YOLO11n-seg, geometric anchors + polygons but **COCO classes only** (person/handbag). `vision_service.decompose_regions` = vision-LLM semantic naming, steered by Sūkṣma `mode` (garment/body/texture/material/composition) + free-text `lens`. Capped 12 regions.
- **Aletheia:** `analyze_image` → 3–5 freeform lenses `{name, reading, intensity}` + concealed + uncertainty; refinable by viewer answers. Generic today.
- **Taste accrual:** `anatomy_catalog_service` aggregates `region_annotations` across posts → a "portrait" of the curator's anatomy language.
- **UI split:** manual annotation in the Visual pane; auto anatomy + Aletheia + commentary in the separate **Unconceal** tab. To be merged.

## The five moves
1. **Unify annotation** — one region model + one live Visual-pane surface; retire the Unconceal split.
2. **Domain-aware segmentation** — fashion / architecture / photography; parts + textures + materials + light + atmosphere; optimise YOLO-anchor vs LLM-semantic labour.
3. **Deepen Aletheia** into a context-triggered **native intelligence** that feeds the inline writing AI (context engineering / RAG).
4. **Premium, dynamic Visual pane** — reveal many parts non-messily; each part pick → comment → remember.
5. **Taste accrual** into persona/catalog → powers Sutradhar. Closes the loop.

## Research tracks (parallel, research-only)
A data-model unification · B segmentation intelligence · C Aletheia deepening · D unified annotation UX · E purpose/niche. See the brief.

Bounded by [[Constraints we must not break]]; writes into [[Slash command potentialities]] (region-aware `/part` `/lens`).
