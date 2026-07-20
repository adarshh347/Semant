# Track C — Aletheia deepening → native context intelligence (research + plan only)

**Read first:** `00-brief.md`. **Do not edit code.** Write `responses/track-C-aletheia.findings.md`. Web search allowed for context-engineering/RAG patterns.

## Mission
Aletheia today = 3–5 generic freeform lenses. Adarsh finds the phenomenological/semiotic/atmospheric split too simple. Deepen it into a **context-triggered** reading whose lenses are chosen by the *image itself*, and which becomes the **native intelligence** feeding the inline writing AI.

## Read
- `backend/services/vision_service.py` — `analyze_image` (Aletheia), `_parse_aletheia`, the lens prompt (lines ~600–630), the brainstorm/answers refinement.
- `backend/schemas/post.py` — LocalContextRequest, BrainstormRequest.
- How the reading is stored (`local_context.aletheia`) and where it could feed writing (`epicService` prompt-enhanced calls; the inline slash AI).

## Answer
1. **Context-triggered lenses:** instead of fixed generic lenses, select/generate lenses from the image's context (domain from Track B, detected parts, mood, source). Design the mechanism.
2. **Depth:** what makes a reading *deep* not generic — specificity to this image, tension between lenses, grounding in named parts. Propose a richer schema (lenses tied to regions? evidence per claim?).
3. **Native intelligence / context engineering:** how the per-image reading + region notes + taste catalog become retrievable context (RAG / structured context) that makes the inline writing AI actually image-specific. What's stored, retrieved, and injected.
4. **Feedback loop:** how viewer answers + the curator's own commentary refine future readings and the persona.
5. **Naming:** confirm Aletheia scales up (vs a new name for the native intelligence).

## Output contract → `responses/track-C-aletheia.findings.md`
Current-Aletheia map · context-trigger design · deeper reading schema · context-engineering/RAG plan (what feeds inline AI) · feedback loop · questions for Adarsh.

---

## Addendum (v2 strategy — 2026-07-08)
Read `01-strategy-two-sided.md` + `model-integration-plan.md`. Two additions to the mission:
- **Taste-vector + RAG:** FashionCLIP embeddings are the taste vector; design RAG over the taste graph so the writer is grounded in *this image + this person's history* (upgrades the frequency-count catalog). Re-role the vision-LLM to *felt-reading/story*, not geometry.
- **Two readings, one engine:** produce both the **deep creator reading** and a **short consumer reading** (the Aletheia-in-feed hook, strategy §5) + one-tap perceptual forks that double as audience taste signal. Lenses become fashion-literate (silhouette, drape, era/reference, styling logic, mood/story).
