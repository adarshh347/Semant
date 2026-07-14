# Front door revamp — build spec (phased): Semant identity + decluttered nav  ·  landing = pass 2

**To:** Claude Code (Drishya/UI thread, `feat/frontend`). **Mode:** build.
**Sources:** `frontend-revamp-master-plan.findings.md` (§1 rebrand, §2 IA, §3 landing), `responses/track-E-purpose.findings.md` (the wedge + killer demo the landing dramatises).
**Why this is first:** it's foundational (identity), low-risk (doesn't touch the editor or the Visual pane), and the most visible fix — the nav is what a visitor sees first. It unblocks everything downstream.
**Goal:** the app reads as **Semant**; the primary nav shows only what a user *does*; every internal tool recedes but stays reachable.

> **Scope split (locked).** This build is **Pass 1 = rebrand + nav** only — fast, low-risk, ships on its own. The **landing redesign (Phase 3) is deferred to Pass 2** (its own build/commit) because it carries the motion stack (Motion + GSAP) and is the largest, most craft-heavy piece. Pass 1 must not block on it.

## Locked decisions (all confirmed 2026-07-14 — no ⚠ gates remain)
- **App name → Semant.** **Wordmark = Latin "Semant"** (confirmed). Drop `दृष्टिकोण` entirely — it literally *is* "Drishtikone". Sanskrit terms (Darshan, Aletheia, Anuraṇana) may appear as *section* names, never the app title. No Sanskrit tagline in Pass 1.
- **Room names (confirmed): Atelier + Loom.** The image+read+write workspace (today `PostDetailPage` / "Drishya") → **Atelier**; the standalone editor (Pass-later) → **Loom**. Pass 1 renames the **nav label + logo/UI only** — the route stays `/posts/:postId` for now (full `PostDetailPage`→`/atelier` route rename is a later, serialized pass, per the editor migration).
- **Primary nav (confirmed) → `Gallery · Read · Atelier · You`.** `You` = a taste/profile entry aggregating Highlights / Epics / taste (stub the route if missing). Demote **Research, Unconceal, Anatomy, Motive** into a single **Tools** overflow menu now; the ⌘K palette (cmdk) comes in the Foundation-adopts pass, not here.
- **Delete the stale duplicate `pages/NavBar.jsx`** — it's dead (unimported, malformed JSX, still says the *pre-Drishtikone* name "Framewise").
- **Motion stack (Pass 2):** **Motion** (`motion`, ex-framer-motion) for UI reveals; **GSAP + ScrollTrigger** for the scroll hero. **No Tailwind**, no Aceternity/Magic-UI packages (reference their effects; rebuild on our tokens + Motion).

## Corrected grounding (verified @ `2299ec0` — the master plan's "13 spots" was an overcount)
The brand string is **9 occurrences across 7 files**, only **3 user-visible**:

| File | Line(s) | Kind | Pass-1 action |
|---|---|---|---|
| `src/components/NavBar.jsx` | 45 | **user-visible** logo | → `Semant` |
| `index.html` | 13 | **user-visible** `<title>` | → `Semant — …` |
| `src/pages/LandingPage.jsx` | 15, 21 | **user-visible** hero `दृष्टिकोण` + "Drishtikone weave" copy | swap wordmark + copy (light touch in Pass 1; full redesign Pass 2) |
| `src/index.css` | 2 | comment | → `Semant` |
| `src/pages/AnatomyPage.css` | 3 | comment | → `Semant` |
| `_ds/tokens/theme.css` | 1, 5 | comments | → `Semant` |
| `_ds/tokens/package.json` | 1 | internal pkg name `drishtikone-tokens` | → `semant-tokens` |
| `src/pages/NavBar.jsx` | 11 | dead file, says `Framewise` | **delete the file** |

- **Correction:** `frontend/package.json` name is `"frontend"` — **not** a brand spot (the master plan listed it in error). The only npm name to change is the token sub-package.
- **Three names haunt the tree** (Framewise → Drishtikone → Semant). Sweep so no third ghost lingers.

## Rules (per `workflow-protocol.md`)
- **Verify by SCREENSHOT** (headless Chrome, live app): nav resting + disclosure, dark + light, desktop + mobile widths; the browser tab reading "Semant".
- Conventional commits on `feat/frontend`; open one issue (label `architecture`): *"Front door — Semant rebrand + IA"*. Keep its checklist current.
- `git pull` first; stage only files you change; don't blind-add dist/build output (rebuild dist last).
- End each phase with a handoff line: what changed, commits, issue, next.
- **No editor / Visual-pane / backend work** — front door only.

---

## Phase 1 — Rebrand to Semant (mechanical, do first)
Replace `Drishtikone`/`दृष्टिकोण`/`Framewise` → **Semant** across the 7 files above (delete `pages/NavBar.jsx` rather than editing it). Rename the token package `drishtikone-tokens` → `semant-tokens`. Update favicon/manifest if present.
**Verify:** `grep -rin "drishtikone\|framewise\|दृष्टिकोण"` over `src` + `index.html` + `_ds` → **zero** hits; screenshot the nav logo + browser tab reading "Semant". **Stop for review.**

## Phase 2 — Declutter the nav / IA
- In `components/NavBar.jsx`, cut `NAV_LINKS` (currently the flat 9) to the primary set **Gallery · Read · Atelier · You**:
  - `Read` → the feed route (`/feed`; alias `/read` optional later),
  - `Atelier` → the create/post entry (label only; route unchanged),
  - `You` → a profile route aggregating Highlights / Epics / taste (stub if missing).
- Move **Research, Unconceal, Anatomy, Motive** into a single overflow **"Tools"** menu (reuse the existing disclosure pattern already in `NavBar.jsx`), not the primary bar.
- **Delete `pages/NavBar.jsx`**; confirm nothing imports it (already verified: nothing does).
- Keep every destination reachable (Tools menu now / ⌘K later) — nothing is removed, only demoted.
**Verify:** screenshots — primary nav shows 4 + logo; Tools menu holds the demoted items; every old route still reachable. **Stop for review.**

## Phase 3 — Rebuild dist + handoff (closes Pass 1)
Rebuild `dist`; confirm favicon/title/meta say Semant; re-screenshot the first-visit flow (nav → Gallery). Handoff line. **Pass 1 ends here — landing is Pass 2.**

---

## Pass 2 (deferred) — Landing redesign (the showpiece)
> Its own build/commit after Pass 1 lands. Kept here for continuity; do **not** start until Pass 1 is reviewed.

Rebuild `LandingPage.jsx` (+ css) around **See · Read · Write**, editorial and type-led (`--font-display`, one accent, generous whitespace — not gradient-blob slop).
- **Hero:** the one-line wedge (Track E) + a single confident CTA into Gallery/Atelier; a **live micro-demo** motif — an editorial image whose parts light up → a felt reading line → a paragraph assembling from the picks (scripted/mocked animation, not the live pipeline).
- **Three scroll panels** (GSAP ScrollTrigger): **See** (image → parts), **Read** (felt reading per part), **Write** (grounded paragraph). Each reveal *explains* the flow; `prefers-reduced-motion` respected.
- **Taste/reciprocity strip** (Track F): "your taste, given back — not harvested."
- Deps: `motion`, `gsap`.
- **If too big:** split **2a static editorial landing** (copy, See/Read/Write sections, CTA, responsive — no animation) → ship; then **2b motion layer** (Motion reveals + GSAP scroll timeline + micro-demo).
**Verify:** screenshots (hero, each panel, mobile), a gif of the hero reveal; console clean; reduced-motion disables motion.

---

## Explicitly NOT in this build
- No editor / BlockNote work (separate editor migration build).
- No Visual-pane / Track-D work; no backend changes.
- No page *route* rename yet (label/UI only; `PostDetailPage`→`/atelier` route rename is a later, serialized pass).
- No Tailwind / Aceternity / Magic-UI packages.
- No ⌘K palette yet (Foundation-adopts pass); Pass-1 demotion uses the existing disclosure menu.
