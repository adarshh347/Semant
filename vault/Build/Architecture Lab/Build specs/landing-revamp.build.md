# Landing revamp — build spec (Pass 2): the motive-based front page

**To:** Claude Code (`feat/frontend`). **Mode:** build. **Runs after** front-door Pass 1 (rebrand + nav) is merged.
**Sources (read first):** `landing-articles/01-saving-is-not-seeing.md`, `02-your-taste-is-your-edge.md`, `03-reading-not-tagging.md` (the **voice + copy**), `front-door-revamp.build.md` (Pass 2 outline), `frontend-revamp-master-plan.findings.md` §3, `responses/track-E-purpose.findings.md` (the wedge + the killer demo this landing dramatises).
**Goal:** replace the thin hero with a landing that **shows what Semant is** — editorial, type-led, motion-with-meaning — built around one act: **See · Read · Write.** Not a feature list, not gradient-blob AI-slop.

## Locked (from `decisions-log.md`)
- **Product name in copy = Semant.** The articles are written with the concept word "Darshan" — **use "Semant" as the product/app name in all on-page copy**; keep the articles' *voice*. (Sanskrit terms may name sections only, not the app.)
- **Wordmark:** Latin **Semant** (`--font-display`); no Devanagari.
- **Primary CTA → the creative act:** into **Gallery** (browse) with a secondary into **Atelier** (create). ("Atelier" = the image+read+write workspace; "Loom" = standalone editor — don't surface Loom on the landing yet.)
- **Motion stack:** **Motion** (`motion`, ex-framer-motion) for entrance/hover/layout; **GSAP + ScrollTrigger** for the scroll-driven See→Read→Write timeline. **No Tailwind**; **no Aceternity/Magic-UI packages** — if you want one of their effects, rebuild it on our tokens + Motion.
- Editorial aesthetic: warm paper/ink, one terracotta accent, generous whitespace, Fraunces display + Inter — the existing token system, used with restraint.

## Rules (`workflow-protocol.md`)
- **Verify by SCREENSHOT** (headless Chrome, live): hero, each scroll section, the micro-demo, mobile width, dark + light; a short **gif** of the hero reveal + the See→Read→Write scroll. Console/Lighthouse clean.
- **`prefers-reduced-motion`: all motion degrades to static** — verify it.
- Conventional commits on `feat/frontend`; one issue (label `architecture`): *"Landing revamp (Pass 2)."* Handoff line at the end. Rebuild `dist` last.
- **Scope: landing only.** No editor, no Visual pane, no backend, no route renames.

---

## Phase 2a — the static editorial landing (ship this first, no animation)
Rebuild `pages/LandingPage.jsx` + `LandingPage.css` as a scrollable editorial page. Content, structure, responsiveness — zero motion yet.

1. **Hero.** The wedge in one line (Track E): *every tool tells you what's in an image — Semant tells you **why it moves you, part by part, in your own words.*** Semant wordmark; one confident **CTA → Gallery** (secondary → Atelier). A calm, real editorial image, not a stock gradient.
2. **The problem (from `01-saving-is-not-seeing`).** "Saving is not seeing" — a tight section: moodboards archive attention with the attention removed. Set up the need.
3. **See · Read · Write** — three stacked panels, the spine of the page:
   - **See** — one image decomposed into *meaningful parts* (silhouette, drape, the fall of light) — reading, not tagging (`03-reading-not-tagging`).
   - **Read** — a felt reading per part ("the drape softens the severe shoulder"), lenses the image calls for.
   - **Write** — a paragraph grounded in those exact parts, in your voice (`02-your-taste-is-your-edge`) — "words that sound like the person who saw the thing."
4. **Your taste is your edge** — the portrait-of-your-eye idea; the reciprocity line (Track F): *your taste, given back — not harvested.*
5. **Close** — restate the wedge + the primary CTA again.
- **Responsive + dark/light + real semantics** (headings, landmarks, alt text). Honest copy — nothing the product can't do (mark anything aspirational lightly or cut it).
**Verify:** screenshots (hero, each section, mobile, dark/light); reads as an editorial page with no motion. **Ship 2a, then continue.**

## Phase 2b — the motion layer (the craft)
Add `motion` + `gsap`. Motion must *explain the flow*, never decorate.
- **Hero reveal (Motion):** wordmark + line settle in; the CTA has a purposeful hover.
- **The micro-demo (the centerpiece — GSAP ScrollTrigger):** as the user scrolls the See→Read→Write panels, a single editorial image **progressively reveals**: parts light up (See) → a reading line writes in beside a part (Read) → a short paragraph **assembles from the picked parts** (Write). This is the killer demo (Track E §4) as a scroll-scrubbed sequence. It can be **scripted/mocked** (pre-authored content), not the live pipeline.
- **Section reveals (Motion):** each panel eases in on enter; numerals/labels stagger.
- **Respect `prefers-reduced-motion`:** everything falls back to the 2a static state.
**Verify:** gif of the hero + the scroll micro-demo; reduced-motion screenshot identical to 2a; 60fps-ish scroll, no layout thrash (reserve space); console clean. Handoff.

---

## Explicitly NOT
- No Tailwind, no Aceternity/Magic-UI/shadcn packages (reference effects only).
- No editor / Atelier-pane / backend work.
- No live-pipeline calls in the demo (mock the sequence — keeps the landing fast and offline-safe).
- No route renames (`/atelier`, `/loom` are a later pass).

## If 2b is too big
Ship 2a (the editorial page) as the visible win; land 2b's hero + section reveals first, then the scroll micro-demo as its own commit (it's the hardest, highest-craft piece).

## Copy note
Pull sentences directly from `landing-articles/*` for voice, but swap the product word to **Semant**. Keep it spare — the articles are strong; the page should feel like three of their best lines, not all of them.
