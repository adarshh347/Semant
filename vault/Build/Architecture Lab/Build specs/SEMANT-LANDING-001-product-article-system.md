# SEMANT-LANDING-001 — Perception Engineering landing & article system (content architecture)

**Status:** build spec (content + IA). Docs-only pass — no frontend code this round.
**Author date:** 2026-07-24 · **Branch:** `docs/semant-landing-001`
**Companion docs (this pass):** the landing copy → `vault/Writing/Semant Field Notes/00-landing-page.md`; the visual direction + cinematic hero → `vault/Concepts/Frontend Analysis/SEMANT-LANDING-001-visual-direction-and-hero.md`; six feature articles → `vault/Writing/Semant Field Notes/01…06`; the implementation report → `Build specs/SEMANT-LANDING-001-implementation-report.md`.

---

## 1. Purpose
Replace the current fashion-first "See · Read · Write" landing (a real page — `frontend/src/pages/LandingPage.jsx`, design-language v1.3 *Paper + Plum*) with a broader, more serious public identity: **Semant as a perception engineering environment.** The landing is the high-level showcase; every mechanism gets a *linked* deeper article, so the landing itself stays readable and visual, never documentation.

Written from the vantage of Semant **~3 months ahead**: coherent, ambitious, product-shaped — and honest. Shipped mechanisms are stated plainly; unshipped ones are marked *emerging / being built / the workbench is growing toward* via status language and subtle status cards (§8).

## 2. Audience
Two rings, one page:
- **Primary (public / creative):** curators, designers, filmmakers, writers, artists, researchers, architects — people who are *captivated by images and must do something structured with that captivation.* They need the poetry and the "what it lets me do," not the internals.
- **Secondary (technical / builder):** AI builders, agent engineers, perception researchers. They need to trust the claims — so the copy is anchored in real modules (`perceptualActions.js`, `suggestionQuarantine.js`, `orchestrationSession.js`, `manuscriptField.js`, `attunementPlanner.js`, `visualMarks.js`, `recall.js`) and every deep article cites what exists now vs. what's next.

## 3. Positioning (the fixed spine)
Semant is **not** a chatbox beside an image. Semant is **not** an annotation tool. Semant is a **perception engineering environment**: it turns visual captivation into *inspectable, editable, refusable acts* — marks, fields, traces, percepts, manuscript passages, recall performances, model suggestions, citations, provenance, orchestration sessions.

The long-term claim (the manifesto line):
> Agentic engineering gave language models access to software work. **Perception engineering** gives models, agents, and humans access to *situated seeing*.

Semant builds both halves:
1. **the Engine** — the action grammar, the orchestration session, visual marks, provenance, model/tool pathways;
2. **the Workbench** — the Differential (image-side perception workshop), the Manuscript (writing-side multimodal field), the visual instruments, recall, marks, percepts, writing.

## 4. Information architecture (landing, top → bottom)
1. **Hero — "The Great Arrival"** — full-viewport twilight doodle; headline + three CTAs.
2. **What Semant does** — seven verb cards: Notice · Mark · Compose · Cite · Recall · Challenge · Orchestrate.
3. **The Workbench** — surface cards: Differential · Manuscript · Atlas/Codex (horizon) · product forms (web/desktop/CLI/phone/agent).
4. **The Engine** — mechanism cards: Perceptual Action Grammar · Attunement Planner · Visual Marks · Suggestion Quarantine · Orchestration Session · Provenance · Mark Recall · Tool pathways/actuators.
5. **Who it is for** — audience cards, each stating a concrete act it unlocks.
6. **Perception Engineering** — the big claim, plainly.
7. **Research & philosophy** — intellectual grounding tied to capability (never name-dropping).
8. **Feature article grid** — the six linked cards (§6).
9. **Product forms** — web workbench · desktop (Cursor-like + Cowork-like studio) · CLI · phone capture · agent-facing engine/API (later).
10. **Footer / afterimage** — quiet poetic close.

CTAs: **Explore the Workbench** (primary) · **Read the Technical Notes** (secondary) · **View Research Horizons** (third). In this docs pass CTAs point to the article set; they wire to routes in the frontend pass.

## 5. Article taxonomy (four families)
- **Technical depth** — mechanisms built or being actively built: Perceptual Action Grammar, First Attention, Visual Marks, Suggestion Quarantine, Manuscript Recall, Orchestration Session, Mark Citation, CLI/workbench pathways.
- **Philosophical vision** — the perspective: embodied cognition, phenomenology (Merleau-Ponty), Deleuze/DeLanda, Gestalt figure-ground, gaze studies, psychoanalysis, colour theory, architecture & perception (Pallasmaa, Casey).
- **Research horizon** — emerging work: VLMs as perceptual collaborators, model/tool-calling through the action grammar, agentic workflows, rehearsal/eval harnesses, diffusion/model grounding, multimodal memory, benchmarking situated seeing.
- **Hybrid manifesto** — product + philosophy + AI research: Perception Engineering, why model suggestions are not evidence, why an action grammar matters, how workbench and engine meet.

## 6. Initial feature articles (this pass — all fully written)
| # | Title | Family | Status |
|---|---|---|---|
| 01 | The Perceptual Action Grammar | technical | **built** (deterministic planner + validators shipped) |
| 02 | Visual Marks That Can Be Cited | technical | **built** (visual_mark + quarantine + citability shipped) |
| 03 | The Orchestration Session | technical / hybrid | **emerging** (assembler shipped; dispatch not wired) |
| 04 | Manuscript as a Multimodal Field | technical / philosophy | **emerging** (field derivation shipped; some refs `exists:false`) |
| 05 | Rehearsal Instead of Benchmarking | research | **built method / emerging product** (rehearsal programme real; harness maturing) |
| 06 | Perception Engineering | hybrid manifesto | **horizon / identity** |

## 7. Technical claims — allowed vs. avoid
**Allowed (grounded in code):**
- A closed **Perceptual Action Grammar** of 9 action types that validates every proposal and *fails closed* (`perceptualActions.js`).
- A **deterministic attunement planner** that proposes acts from what the curator says caught them, carrying `provenance.matched` — "you said 'gaze'", never "detected" (`attunementPlanner.js`).
- **Renderer-independent `visual_mark`s** and a **suggestion quarantine** where acceptance mints a new mark pointing back at the suggestion; **citability is derived, never stored** (`visualMarks.js`, `suggestionQuarantine.js`, `markStaging.js`).
- An **Orchestration Session** that freezes what was asked, on what evidence, under what constraints — and can *refuse an invalid request without spending anything*; honesty invariants (`unreadable[]`, `external_claims: null` = not assessed) (`orchestrationSession.js`, `perceptPacket.js`).
- A **Manuscript** that distinguishes RECORD ("cites nothing") from JUDGEMENT ("rests on nothing") and shows **no green ticks** (`manuscriptField.js`).
- **Recall** — the visual re-performance of a percept from its mention (`recall.js`).

**Avoid (would be dishonest):**
- Claiming live model dispatch, agents, or persistent cross-session memory as shipped — the engine is a *pure assembler*; nothing calls out yet.
- Claiming detection ("Semant sees the gaze"), leaderboard/benchmark scores, or shipped SAM 3 / fashion-parse / vector-graph features.
- Any "AI understands your image" language. The through-rule: **the model may suggest; Semant shapes; the curator confirms.**

## 8. Status language (the honesty layer)
Three chips used consistently across landing + articles:
- **`built`** — shipped and test-covered; stated in present tense.
- **`emerging`** — partially built / actively under construction; phrased "the workbench is growing toward…", "being built".
- **`horizon`** — researched/planned direction; phrased "we're exploring…", "the direction is…".
Subtle status cards (small corner chip, muted) carry these on feature cards so ambition never reads as a shipped claim.

## 9. Visual direction (summary; full spec in the Frontend Analysis doc)
Sophisticated **minimalist doodle** — delicate ink lines, graphite construction marks, wax-crayon/dry-pastel texture, translucent fluorescent scribbles, restrained luminous grain, human pressure-sensitive strokes. Deep twilight palette (midnight navy · indigo · near-black · electric cyan · ultraviolet · coral-pink · pale gold · brilliant white) with **one small red accent thread**. Large negative space. Editorial serif headline (Fraunces, consistent with current design language), humanist sans body, restrained handwritten micro-labels. Hero = **"The Great Arrival"**, a full cinematic doodle sequence (arrival → astonishment → connection → fragmentation → memory → afterimage). Avoid: anime, realistic portraits, stock space photography, glossy 3D, emoji stars, crowded constellations. Full choreography, SVG/CSS build notes, and asset prompts live in the visual-direction doc.

## 10. Success criteria for this content system
- A general reader grasps *what Semant is and what it lets them do* from the hero + section 2 alone.
- A technical reader can click any Engine card into an article that is **true to the code**.
- Nothing on the page claims a capability the repo doesn't support; every ambitious line carries a status.
- The article set is coherent enough to seed the frontend implementation pass without re-writing copy.

## 11. Next (frontend pass, not this round)
Componentise per the directive (Hero, WhatSemantDoes, WorkbenchEngine, AudienceCards, ResearchPhilosophy, FeatureArticles, ProductForms, FooterAfterimage); wire CTAs to article routes; build the SVG/CSS doodle hero from the spec; run tests + production build; screenshot-verify. Tracked as SEMANT-LANDING-002.
