# Vision Initiative — "Darshan": one place to see an image deeply

Working name **Darshan** (देखना — beholding): the unified see → mark → understand → write pipeline. Rename freely. This is bigger than a UI lane — it spans purpose, frontend, backend, and AI. Everything here is **research + planning first**; no code until tracks are read and decisions locked.

## 1. The bigger purpose (the thesis to pressure-test)
Most image tools tag *objects* (generic computer vision). Drishya's bet is different: **structured aesthetic close-reading of images.** A curator takes one image and decomposes it into *meaningful* parts — not "person, handbag" but "the fold of the fabric, the fall of light, the atmospheric melancholy" — says **how each part affects them** (phenomenological, first-person), lets an AI (Aletheia) read it through evolving lenses, and accumulates all of this into a personal **vision-language** that then powers writing (Sutradhar) and curation.

In one line: **the close-reading tool for images** — the visual equivalent of literary annotation, that also *learns your taste* and writes with it.

**Niche fit (why it's useful / sellable / resume-worthy):** visually-driven creators who must articulate *why* an image works, part by part, and build a body of taste over time — fashion curators, architects/interior, photographers, brand/moodboard people. The differentiator is felt-meaning + taste-learning, not object tags. Track E sharpens this.

## 2. What exists today (grounded; file refs)
- **Two annotation systems (the core duplication):**
  - `bounding_box_tags` — manual pixel rectangles, drawn in `BoundingBoxEditor.jsx` (Visual pane). No polygons, no semantics.
  - `region_annotations` — auto-detected, polygon shapes + semantics + user notes. Pipeline below.
- **Segmentation pipeline (Sūkṣma / fine-anatomy):**
  - `services/segmentation_service.py` — YOLO11n-seg on-device: geometric anchors + normalized polygons, but **COCO classes only** (`_category`: person→figure, tie/handbag→garment, else object). Capped 12 regions.
  - `services/vision_service.py` — `detect_regions` / `decompose_regions`: a vision-LLM (Groq llama-4-scout) names parts, steered by `mode` (general|garment|body|texture|material|composition) + free-text `lens`, each mode with its own decomposition vocabulary (e.g. garment → garment/garment-detail/body-part/hair/skin/accessory + `material`). Boxes are model-estimated when no YOLO anchor.
  - `RegionDetectRequest` (schema) already exposes mode/lens/coarse_only — the ambition for texture/material/composition is scaffolded but leans on the LLM, not YOLO.
- **Aletheia** — `vision_service.analyze_image`: 3–5 freeform lenses `{name, reading, intensity 0-100}` + `concealed` + `uncertainty`; refinable by viewer MCQ (`BrainstormRequest.answers`). Generic today.
- **Taste accrual** — `anatomy_catalog_service` aggregates `region_annotations` across posts → category profile + LLM-synthesised "portrait" of the curator's anatomy language (`routers/anatomy.py`).
- **UI split** — manual annotation in the Visual pane; auto anatomy + Aletheia + commentary in the **Unconceal** tab (`RegionDetectorModal.jsx`, Unconceal branch of `PostDetailPage.jsx`).

## 3. The core moves (what this initiative decides)
1. **Unify annotation** — one region data model + one live surface in the **Visual pane**. Retire the separate Unconceal split (fold reading + anatomy into the visual experience). Manual marks and auto segments become the same object type.
2. **Make segmentation intelligent & domain-aware** — beyond COCO objects: garments, architectural elements, textures, materials, light, atmosphere. Diverse domains (fashion / architecture / photography). Optimise the YOLO-anchor + LLM-semantic pipeline; decide where each does what.
3. **Deepen Aletheia into a context-triggered native intelligence** — from generic 3-lens to a reading whose lenses are *selected by the image's own context* (domain, detected parts, mood), and which **feeds the inline writing AI** with real per-image context. (This is the "bigger Aletheia / native intelligence" you named.)
4. **Premium, dynamic Visual pane** — reveal many segments **without mess**: progressive/coarse→fine reveal, focus-one-dims-others, a parts panel; each part **pickable → commentable → remembered** in the DB. True polygon shapes (segmentation already returns them).
5. **Everything accrues** into the curator's vision-language (catalog/persona) and powers Sutradhar's writing — closing the see → mark → understand → write loop.

## 4. Tracks (all research-only → safe to run in PARALLEL sessions)
- `track-A-datamodel.prompt.md` — current-state deep audit + **unify** `bounding_box_tags` + `region_annotations` into one region model (backend schema + storage + frontend consumers + migration).
- `track-B-segmentation.prompt.md` — segmentation **intelligence & optimality**: domain-aware parts/textures/materials/atmosphere; YOLO vs LLM division of labour; new model options.
- `track-C-aletheia.prompt.md` — Aletheia **deepening**: context-triggered lenses; becoming the native intelligence that feeds inline AI (RAG/context-engineering options).
- `track-D-frontend.prompt.md` — unified **annotation UX**: merge the two UI homes into a premium Visual pane; non-messy dynamic reveal; pick → comment → remember.
- `track-E-purpose.prompt.md` — **purpose, niche & positioning**: sharpen the thesis, competitive landscape, which niche(s) and in what way; what makes it demonstrably useful.

## 5. How the parts serve the purpose
E defines *who + why*. A gives a single truthful data spine so B/C/D don't diverge. B supplies the *parts* worth feeling. C supplies the *reading* + context for writing. D makes it feel premium and usable. All feed the taste catalog + Sutradhar. Sequence for building later: E→A anchor, then B/C/D in parallel, then integration.

## 6. Naming
- Initiative: **Darshan** (proposal).
- The "native intelligence": keep **Aletheia** as the name but scaled — it graduates from a 3-lens reader to the context brain. Confirm.
