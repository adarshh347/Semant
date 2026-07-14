# Showcase analysis — what we built that's worth showing off (for a dedicated session)

**To:** a research session (not a builder). **Mode:** deep read + synthesis. **No app code, no edits.**
**Goal:** surface, from the *actual* work in this repo, what is genuinely impressive — and translate it into material Adarsh can use to show off **subtly and credibly**: a portfolio, the Semant landing page, case-study notes, conference/'build-in-public' posts. **Not** a résumé bullet dump — the aim is *substance shown, not claimed.*

## Audience & tone the output must serve
- **A hiring manager / senior engineer** skimming a portfolio who distrusts buzzwords — wants to see real architectural decisions and trade-offs.
- **A potential user / peer** on the landing page — wants to *feel* what the product does, not read a feature list.
- Voice: understated, specific, evidence-led. Every claim points at a real file, decision, or metric. No "revolutionary AI-powered" slop.

## Read first (the evidence is already written down)
- `architecture-lab/responses/` — the track findings (A datamodel, B segmentation, C aletheia, D frontend, E purpose, F consumer), the lane findings, `frontend-research/` rubric, the harvest/adoption/feature-map/BlockNote/revamp docs.
- `architecture-lab/decisions-log.md`, `workflow-log.md`, `workflow-protocol.md` — the *process* (locked decisions, verify-by-screenshot discipline) is itself showcase-worthy.
- The real code: `backend/services/` (the model stack — YOLO/FashionCLIP/Fashionpedia/SAM2, `anuranana_service`, `lens_registry`, `region_embedding_service`, `taste_signal_service`), `backend/schemas/post.py` (the unified `Region` contract), `frontend/src/components/` (RegionSurface/RegionOverlay/RegionLightbox, the TipTap→BlockNote editor, AletheiaHook).
- `git log` — the commit trail is evidence of disciplined, incremental delivery.

## What to produce → write to `responses/showcase/` (create it)

### 1. `01-highlight-reel.md` — the 5–8 things actually worth showing
For each: **what it is (plain) · why it's hard/non-obvious · the architectural decision behind it · the evidence (file/commit/decision) · the one-line "so what."** Prioritise depth over count. Candidate seams (verify before claiming):
- The **unified `Region` data-model** decision (two parallel models → one `actor`-tagged, normalized, graph-ready contract) — a textbook Foundation call, with a *0-row migration* insight.
- The **two-sided taste graph** (Anuraṇana): creator annotations + audience taps in **one FashionCLIP vector space**, distinguished only by `actor`.
- The **model orchestration**: geometry from CV (YOLO/Fashionpedia/SAM2), vectors from FashionCLIP, meaning from the LLM — "the LLM stops guessing boxes."
- The **close-reading UX**: normalized-SVG region surface, polygon maps, focus-dims-others, deep-zoom, pick→comment→remember.
- The **editor architecture**: Path A → Path B (BlockNote), `/part`/`/lens` custom blocks, `origin` provenance.
- The **orchestration method itself**: the four-layer lens rubric, research-before-build, verify-by-screenshot, the architecture-lab paper-trail.

### 2. `02-portfolio-angles.md` — how to frame it, per audience
- **The systems-thinker cut** (for eng roles): the data-contract + insulation-pointer + phased-migration story.
- **The product cut** (for PM/founder framing): the wedge (felt-meaning per part → taste you can write from) + the two-sided model.
- **The craft cut** (for design/frontend): the lens, the border-grammar, motion-with-meaning, the annotation surface.
Each: a 2–3 sentence positioning + the 3 strongest proof points, in Adarsh's voice (subtle, concrete).

### 3. `03-landing-proof.md` — what the landing page can *show*
Map the highlight reel to landing sections (See·Read·Write): which real capability dramatises each, what a 5–10s micro-demo would show, and the honest one-liner beside it. Flag what's real-today vs roadmap so the landing never overclaims.

### 4. `04-talk-track.md` (optional) — a 60-second and a 5-minute verbal walk-through of the build, for a call/demo.

## Rules
- **Evidence-led:** every showcase claim cites a file, commit, or decision doc. If you can't ground it, cut it or mark it "aspirational (roadmap)."
- **Honest boundaries:** distinguish shipped from planned (e.g. the taste graph's depth is a v1 frequency+vector aggregation, not a trained model — say so).
- **Subtle > loud:** prefer "here's the decision and why" over adjectives. The impressive part is the *reasoning*, let it speak.
- **No new features invented** — you're a curator of what exists, not a marketer.
- Keep Adarsh (a non-coder orchestrator who directed this) as the credible author throughout — the showcase is of *orchestration and architectural judgement*, which is the real story.

*Deliverable: `responses/showcase/{01-highlight-reel,02-portfolio-angles,03-landing-proof,04-talk-track}.md`, committed `docs(arch-lab): showcase analysis`. Research + synthesis only.*
