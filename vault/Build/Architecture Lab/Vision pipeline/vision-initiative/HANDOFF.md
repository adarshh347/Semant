# Darshan initiative — session handoff / context brief

You are taking over the **Darshan** initiative in the Semant repo (`/home/adarsh-yadav/Documents/projects/semant`, GitHub `adarshh347/Semant`). A separate thread continues the Drishya post-editor UI lanes; **you own the vision / annotation / AI pipeline.** Work independently but don't step on shared files (§5).

## 0. Branch guardrail — do this FIRST
- The repo must be on `feat/frontend`. If `git branch --show-current` says `android`, a mix-up happened: ensure no uncommitted *tracked* changes, then `git checkout feat/frontend`.
- The initiative files are backed up at `/tmp/semant-darshan-backup/`. If `architecture-lab/vision-initiative/` is missing after the switch: `cp -r /tmp/semant-darshan-backup/vision-initiative architecture-lab/`.
- Commit `architecture-lab/` and `vault/` as `docs(...)` if untracked — they were left untracked, which is how they got stranded.

## 1. Orient — read these, in order
1. `architecture-lab/vision-initiative/00-brief.md` — the brief (purpose, current-state with file refs, 5 moves, 5 tracks).
2. `vault/Project Context/Darshan - vision pipeline.md` + `vault/Brainstorming/Purpose - niche and positioning.md` — durable summary.
3. `architecture-lab/07-purpose-lens.md` — Purpose → Structure → Surface (judge everything in this order).
4. `architecture-lab/decisions-log.md` — every locked decision so far.
5. `architecture-lab/workflow-protocol.md` — how commits/issues/PRs are handled (you own git hygiene).
6. `vault/Architecture/Constraints we must not break.md` — hard rules.

## 2. What Darshan is
Purpose: **structured aesthetic close-reading of images** — the visual equivalent of literary annotation, that learns the curator's taste and writes with it. Not object tagging; felt-meaning + taste-learning. Lead niche likely fashion (richest part-vocabulary already in code), then architecture, photography.

Current state (grounded): two annotation systems (`bounding_box_tags` manual vs `region_annotations` auto); segmentation = YOLO11n-seg (COCO objects only) + a vision-LLM Sūkṣma decomposition (modes garment/body/texture/material/composition); Aletheia = generic 3–5 lenses; an anatomy catalog aggregates regions into a taste profile; annotation UI is split between the Visual pane and the Unconceal tab.

Five moves: (1) unify the two annotation systems into one region model; (2) domain-aware segmentation (parts + textures/materials/light/atmosphere); (3) deepen Aletheia into a context-triggered native intelligence that feeds the inline writer; (4) premium dynamic Visual pane — many parts reveal without mess, each pick → comment → remember; (5) accrue into the taste catalog that powers Sutradhar.

## 3. The tracks (your work) — in `architecture-lab/vision-initiative/`
- `track-E-purpose.prompt.md` — purpose/niche/positioning. **DO THIS FIRST** (shapes the rest).
- `track-A-datamodel.prompt.md` — unify `bounding_box_tags` + `region_annotations`.
- `track-B-segmentation.prompt.md` — segmentation intelligence & optimality.
- `track-C-aletheia.prompt.md` — Aletheia deepening → native context intelligence.
- `track-D-frontend.prompt.md` — unified annotation UX (premium Visual pane).
All are **research-only and parallel-safe** — each writes its own `architecture-lab/responses/track-*.findings.md`. After E, A/B/C/D can run in several sessions at once.

## 4. Rules
- Research + plan ONLY right now. No app code until Adarsh reviews findings and locks decisions.
- Follow each track's Output contract; ground claims in real file+line refs (backend: `services/vision_service.py`, `segmentation_service.py`, `anatomy_catalog_service.py`, `schemas/post.py`; frontend: `BoundingBoxEditor.jsx`, `RegionDetectorModal.jsx`, Unconceal branch of `PostDetailPage.jsx`). End every findings file with questions for Adarsh.
- Umbrella issue: "Darshan — vision pipeline initiative (umbrella)". Tick its track boxes as findings land. Conventional commits, per `workflow-protocol.md`.
- Any future UI change is verified by screenshot, never by reading CSS.

## 5. Coordination — avoid conflicts with the Drishya-lanes thread
- The other thread edits the post-editor: `PostDetailPage.jsx/.css` (topbar, content pane, slash/editor), `NavBar.jsx`, `App.jsx`.
- Your builds will eventually touch: the backend vision/segmentation/aletheia/schema, and on the frontend the **Visual pane** (`BoundingBoxEditor.jsx`) + the **Unconceal branch of `PostDetailPage.jsx`**.
- **Shared file = `PostDetailPage.jsx`.** Research phase: zero conflict (no edits). Build phase: never edit `PostDetailPage.jsx` at the same time as the other thread — `git pull` first, keep changes scoped, and tell Adarsh before a build that touches a shared file so he can serialize.
- At each session start: `git pull` / check the log so you're on the latest, and re-read `decisions-log.md` + the umbrella issue (this area evolves).

## 6. Your immediate task
Do §0–§1, then run **Track E** (`track-E-purpose.prompt.md`): sharpen the purpose/niche, write `responses/track-E-purpose.findings.md` per its contract, end with questions for Adarsh, and stop. A/B/C/D follow once E is reviewed.

## 7. Stay in sync
Ask Adarsh when a decision is genuinely his; report status crisply (what you read, what you concluded, what you need). Don't drift into building.

---

## Update 2026-07-08 — Track E done + v2 two-sided strategy
- Track E findings landed (`responses/track-E-purpose.findings.md`): fashion-creative wedge.
- Market research landed (`responses/fashion-market-research.md`): adopt Fashionpedia/FashionCLIP/SAM.
- **v2 strategy** now in `vision-initiative/`: `01-strategy-two-sided.md`, `model-integration-plan.md`, `motive-narratives.md`, and new **`track-F-consumer.prompt.md`** (B2C). Project is now B2B+B2C — a taste-and-story layer with a creator→brand chain.
- Awaiting Adarsh on strategy §8 forks (creator-first vs audience-first; make Track F official; video timing; model depth; pitch framing; name the taste graph) + Track A's 7 questions before any build.
- Umbrella GitHub issue still **not created** (open: #8,#9,#10,#13,#15,#19,#21).
