# Front door revamp — build spec (phased): Semant identity + decluttered nav + motive landing

**To:** Claude Code (Drishya/UI thread, `feat/frontend`). **Mode:** build.
**Sources:** `responses/frontend-revamp-master-plan.findings.md` (§1 rebrand, §2 IA, §3 landing), `responses/track-E-purpose.findings.md` (the wedge + killer demo the landing dramatises).
**Why this is first:** it's foundational (identity), low-risk (doesn't touch the editor or the Visual pane), and it's the most visible fix — the landing and nav are what a visitor sees first. It unblocks everything downstream.
**Goal:** the app reads as **Semant**; the primary nav shows only what a user *does*; the landing *demonstrates* the wedge (See · Read · Write) with purposeful motion — no AI-slop.

## Locked decisions (confirm the ⚠ before that phase)
- **App name → Semant** everywhere. **Wordmark ⚠:** Latin "Semant" wordmark (default); do NOT keep `दृष्टिकोण`. If Adarsh wants a Sanskrit tagline, add it small, below.
- **Primary nav ⚠ → `Gallery · Read · Studio · You`** (taste/profile). Demote Research, Unconceal-queue, Anatomy behind a tools menu + (later) ⌘K. `Studio` = the current post page route; keep its path for now, rename label/UI only (full page-rename is a later pass).
- **Motion stack:** **Motion** (`motion` / ex-framer-motion) for UI reveals; **GSAP + ScrollTrigger** for the scroll-driven hero. **No Tailwind**, no Aceternity/Magic-UI packages (reference their effects, rebuild with Motion + our tokens).
- Delete the stale duplicate `pages/NavBar.jsx`.

## Rules (per `workflow-protocol.md`)
- **Verify by SCREENSHOT** (headless Chrome, live app): landing at desktop + mobile widths, nav resting + disclosure, dark + light. Motion: capture key frames / a short gif of the hero reveal.
- Conventional commits on `feat/frontend`; open one issue (label `architecture`): *"Front door — Semant rebrand + IA + landing."* Keep its checklist current.
- Stage only files you change; don't blind-add dist/build output (rebuild dist last).
- End with a handoff line: what changed, commits, issue, next.
- **No editor / Visual-pane / backend work** — front door only.

---

## Phase 1 — Rebrand to Semant (mechanical, do first)
Replace `Drishtikone`/`दृष्टिकोण` → **Semant** in the 13 grounded spots: `frontend/index.html` (`<title>` + meta), `components/NavBar.jsx` (logo), `pages/LandingPage.jsx` (copy + hero wordmark), `src/index.css` header comment, `pages/AnatomyPage.css` comment, `_ds/tokens/theme.css` + `package.json` name, favicon/manifest if present. Grep `Drishtikone`/`दृष्टिकोण` after — **zero** hits in `src` + `index.html`.
**Verify:** grep clean; screenshot the nav logo + browser tab reading "Semant". **Stop for review.**

## Phase 2 — Declutter the nav / IA
- In `components/NavBar.jsx`, cut `NAV_LINKS` to the primary set **Gallery · Read · Studio · You** (map `Read`→`/feed` or `/read`, `Studio`→ the post/create entry, `You`→ a profile route aggregating Highlights/Epics/taste; stub the route if missing).
- Move **Research, Unconceal, Anatomy** (and Motive) into a single overflow **"Tools"** menu (reuse the existing disclosure pattern), not the primary bar.
- **Delete `pages/NavBar.jsx`** (stale duplicate); confirm nothing imports it.
- Keep every destination reachable (Tools menu / footer / ⌘K later) — nothing is removed, only demoted.
**Verify:** screenshots — primary nav shows 4 + logo; Tools menu holds the demoted items; every old route still reachable. **Stop for review.**

## Phase 3 — Landing redesign (the showpiece)
Rebuild `LandingPage.jsx` (+ css) around **See · Read · Write**, editorial and type-led (`--font-display`, one accent, generous whitespace — not gradient-blob slop).
- **Hero:** the one-line wedge (Track E) + a single confident CTA into Gallery/Studio; a **live micro-demo** motif — an editorial image whose parts light up → a felt reading line → a paragraph assembling from the picks (can be a scripted/mocked animation, not live pipeline).
- **Three scroll panels** (GSAP ScrollTrigger): **See** (image → parts), **Read** (felt reading per part), **Write** (grounded paragraph). Each reveal *explains* the flow; motion tied to scroll, reduced-motion respected.
- **Taste/reciprocity strip** (Track F): "your taste, given back — not harvested."
- Use **Motion** for entrance/hover/layout; **GSAP** for the scroll timeline. Add deps: `motion`, `gsap`.
**Verify:** screenshots (hero, each panel, mobile), a gif of the hero reveal; Lighthouse/console clean; `prefers-reduced-motion` disables motion. **Stop for review.**

## Phase 4 — Polish + rebuild
Rebuild `dist`; confirm favicon/title/meta say Semant; re-screenshot the full first-visit flow (landing → CTA → Gallery). Handoff.

---

## Explicitly NOT in this build
- No editor / BlockNote work (separate `blocknote-migration.build.md`).
- No Visual-pane / Track-D work.
- No backend changes.
- No page *route* rename yet (label/UI only; the `PostDetailPage`→Studio route rename is a later, serialized pass).
- No Tailwind / Aceternity / Magic-UI packages.

## If a phase is too big
Phase 3 (landing) is the largest. Split **3a static editorial landing** (rebrand copy, See/Read/Write sections, CTA, responsive — no scroll animation) → ship; then **3b motion layer** (Motion reveals + GSAP scroll timeline + micro-demo). 3a is the real content win; 3b is the craft.

## Confirm before starting
Wordmark (Latin "Semant" vs Sanskrit tagline) and the primary-nav set (`Gallery · Read · Studio · You`). Both defaulted per the master plan — a one-line confirm unblocks Phase 2.
