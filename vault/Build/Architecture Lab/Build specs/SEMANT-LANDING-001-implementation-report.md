# SEMANT-LANDING-001 — implementation report (docs pass)

**Date:** 2026-07-24 · **Branch:** `docs/semant-landing-001` (off `feat/circuit-p5-crossing` @ `6ab3cf6`)
**Scope chosen with Adarsh:** docs + design spec only · all six articles fully written · full cinematic hero *spec* · new branch, commit exact files, **no push**.

## What was built
A complete content + design system for the perception-engineering landing page — no frontend code this round (deliberately, to lock words + direction before touching the app during active CIRCUIT work).

**Files created (all new, exact-staged):**
1. `vault/Build/Architecture Lab/Build specs/SEMANT-LANDING-001-product-article-system.md` — content architecture: purpose, audience, IA (10 sections), article taxonomy (4 families), claims allowed vs. avoid, status-language system, success criteria.
2. `vault/Concepts/Frontend Analysis/SEMANT-LANDING-001-visual-direction-and-hero.md` — the doodle design language, twilight palette tokens, typography, and the full **"Great Arrival" cinematic sequence** (6 movements: arrival → astonishment → connection → fragmentation → memory → afterimage), SVG/CSS build notes, reduced-motion fallback, asset prompt, avoid-list.
3. `vault/Writing/Semant Field Notes/00-landing-page.md` — full landing copy, all 10 sections, with `built / emerging / horizon` status chips throughout.
4. `vault/Writing/Semant Field Notes/01-perceptual-action-grammar.md` — technical · built.
5. `…/02-visual-marks-that-can-be-cited.md` — technical · built.
6. `…/03-orchestration-session.md` — technical/hybrid · emerging.
7. `…/04-manuscript-as-multimodal-field.md` — technical/philosophy · emerging.
8. `…/05-rehearsal-instead-of-benchmarking.md` — research · emerging.
9. `…/06-perception-engineering.md` — hybrid manifesto · horizon.
10. `vault/Build/Architecture Lab/Build specs/SEMANT-LANDING-001-implementation-report.md` — this file.

## Content created
- **Positioning shift** from the current fashion-first "See · Read · Write" landing to **Semant as a perception engineering environment** (Engine + Workbench), with the manifesto line about agentic → perception engineering.
- **Landing copy**: hero + 9 sections (What Semant does · Workbench · Engine · Who it's for · Perception Engineering · Research & philosophy · Feature notes · Product forms · Afterimage).
- **Six full articles**, each with front-matter (title/category/status/source), summary, problem, "what exists now," "why it's built this way," and "where this goes next."

## Visual direction
Sophisticated minimalist doodle; deep twilight palette + one red thread; large negative space; editorial serif headline + humanist sans; the "Great Arrival" hero as a full cinematic doodle sequence with a composed still as the reduced-motion fallback. Complete enough to build from without further art direction.

## Feature article system
Four families (technical / philosophy / research / hybrid); six articles live; the landing's feature grid links to them. Every article is **grounded in real modules** — `perceptualActions.js`, `visualMarks.js`, `suggestionQuarantine.js`, `markStaging.js`, `orchestrationSession.js`, `perceptPacket.js`, `manuscriptField.js`, `attunementPlanner.js`, `recall.js` — and honest about what's `built` vs `emerging` vs `horizon`.

## Frontend files changed
**None.** No files under `frontend/` were touched. The current `LandingPage.jsx` is untouched and still live.

## Tests / build
None run — docs-only pass, no site build touched (per the directive's Gate 7).

## Honesty audit (claims vs. code)
- Stated as **built**: the action grammar + validators, deterministic attunement planner, visual marks + quarantine + derived citability, provenance, recall. ✔ grounded.
- Stated as **emerging**: orchestration session (assembler ships, no dispatch), manuscript field refs (`exists:false` ones), rehearsal harness. ✔ phrased as growing-toward.
- **Avoided**: live model dispatch, agents, persistent memory, detection language, benchmark scores, shipped SAM 3 / fashion-parse / vector-graph. ✔ none claimed as shipped.

## Caveats
- Copy is final-intent draft; a human editorial pass is worth doing before it goes public.
- The earlier "graphic aspect" session was not in context; the visual spec is built from the directive's aesthetic. If that session has saved notes, reconcile them into the Frontend Analysis doc.
- The hero timings are targets, to be tuned against a real build.
- Product-form claims (desktop/CLI/phone/agent) are all marked `horizon`; keep them so until real.

## Next recommended step
**SEMANT-LANDING-002 (frontend pass):** implement the React landing from this copy + spec — components Hero / WhatSemantDoes / WorkbenchEngine / AudienceCards / ResearchPhilosophy / FeatureArticles / ProductForms / FooterAfterimage; build the SVG/CSS doodle hero; wire CTAs to routed article pages (render these six markdown notes); run tests + production build; screenshot-verify. Do it on its own branch, after an editorial pass on the copy.
