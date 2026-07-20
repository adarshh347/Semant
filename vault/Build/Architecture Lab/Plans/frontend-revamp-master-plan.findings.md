# Semant — whole-frontend revamp master plan

**Mode:** research + plan. No app code changed.
**Covers:** (1) the app rebrand **Drishtikone → Semant**, (2) an information-architecture / navigation fix for the redundant "AI-slop" nav, (3) a motive-based landing redesign, (4) the writing studio as a standalone tool + synced to the (renamed) post page, (5) completing the Notion-like BlockNote migration now Phase 1 is done, (6) the open-source picks for the whole revamp, (7) a sequenced roadmap.
**Grounding (@ `2299ec0`):** nav = 9 pipeline links (`NavBar.jsx` `NAV_LINKS`); landing = thin `दृष्टिकोण` hero (`LandingPage.jsx`); `Drishtikone` in 13 spots (`index.css`, `NavBar.jsx`, `index.html`, `LandingPage.jsx`, `AnatomyPage.css`, `_ds/tokens`); BlockNote spike merged (`lab/blocknote`, #30). Design frame: the four-layer lens + Track E's wedge (*"why this moves me, part by part, in my words"*).

---

## 0. The through-line (what the revamp is *for*)
Today the frontend exposes the **pipeline** (Gallery, Highlights, Feed, Epics, Research, Personas, Unconceal, Anatomy, Motive) — internal tool names as top-level nav. That's the "AI-slop" feel: it shows the machine, not the user's act. The revamp reorients every surface around the **one act** (Track E): *see an image → read it part by part → write from what you felt.* Everything else (personas, anatomy catalog, research, unconceal queue) is **infrastructure that should recede**, reachable but not shouting from the primary nav.

Principle carried throughout: **foundation → structure → behaviour → craft**, and *progressive disclosure* — the primary nav shows the few things a user does; power is revealed on demand.

---

## 1. Rebrand — Drishtikone → **Semant**

A small, foundational, do-it-first change (it touches identity everywhere and unblocks the landing).

**Replace in 13 grounded spots:**
- `frontend/index.html` `<title>` (and meta).
- `frontend/src/components/NavBar.jsx` logo text `Drishtikone` → `Semant`.
- `frontend/src/pages/LandingPage.jsx` copy ("let Drishtikone weave…") and the Hindi title `दृष्टिकोण` → decide the wordmark (see below).
- `frontend/src/index.css` header comment; `AnatomyPage.css` comment; `_ds/tokens/theme.css` + `package.json` name.
- Any `document.title`, favicon/manifest, and the dist artefacts (rebuilt).

**Wordmark decision (flag):** the current hero leads with Devanagari `दृष्टिकोण`. For **Semant**, either (a) a clean Latin wordmark "Semant", or (b) keep a Sanskrit anchor but the *right* one — do **not** keep दृष्टिकोण (that's Drishtikone). Recommendation: **Latin "Semant" wordmark**, with an optional small Devanagari/Sanskrit tagline if you want the cultural thread (the vault's Sanskrit system — Darshan, Aletheia, Anuraṇana — can live as *section* names, not the app title). Confirm.

---

## 2. Information architecture — kill the "AI-slop" nav

The 9 flat links mix **user destinations** with **internal tooling**. Regroup so the primary nav carries only what a user *does*, and demote the rest.

**Audit (grounded in routes):**
| Current link | What it really is | New home |
|---|---|---|
| Gallery | the image library (a real destination) | **Primary** |
| Feed | the consumer/reading feed (Track F) | **Primary** (rename → see below) |
| Highlights | saved quotes (a lens on your own content) | **secondary** (inside a "Library"/profile area) |
| Epics | long-form collections | **secondary** (Library) |
| Personas (Darpan) | the taste/voice dossier — *internal intelligence* | **demote** (profile / "your taste") |
| Research | the research agent — *internal tool* | **demote** (tools, or remove from user nav) |
| Unconceal | the Aletheia *queue* — *internal ops* | **demote/remove** (it's a work queue, not a destination) |
| Anatomy | the region/taste *catalog* — *internal* | **demote** (part of "your taste" / admin) |
| Motive (Sankalpa) | the intent/motive tool | **fold** into landing/about or demote |

**Proposed primary nav (user-oriented, ≤4 + identity):**
- **Gallery** (browse images) · **Read** (the feed/consumer reading — Track F) · **Studio** (create: the image+read+write page, §4) · a single **profile/taste** entry (your highlights, epics, taste portfolio, personas behind it).
- Everything else (Research, Unconceal queue, Anatomy catalog) moves under a **command palette (⌘K)** + a small "tools/admin" menu — reachable, not primary. This is the progressive-disclosure fix: the machine recedes; the act leads.

**Structural note:** the `pages/NavBar.jsx` (a stale duplicate of `components/NavBar.jsx`) should be deleted in the same pass — two navbars is itself a slop signal.

---

## 3. Landing page — motive-based, stylised, modern

Today: a thin single hero. Goal: a landing that *shows what Semant is about* — the wedge, felt and demonstrated, not described.

**What it must communicate (in order):**
1. **The one line** (Track E wedge): every tool tells you *what's in an image*; Semant tells you *why it moves you, part by part — in your words.*
2. **Show, don't tell — a live micro-demo:** an editorial image → parts light up → a felt reading → a paragraph assembling from the picks. This is the killer-demo (Track E §4) as the hero interaction. Motion-driven, scroll-revealed.
3. **The three verbs** as scroll sections: **See · Read · Write** (image decomposition → felt reading → grounded writing), each a short animated panel.
4. **The reciprocity/taste angle** (Track F): "your taste, given back — not harvested."
5. **A single, confident CTA** into Gallery/Studio.

**Aesthetic direction (stylised, not slop):** editorial, calm, type-led (your `--font-display`), generous whitespace, one accent, purposeful motion tied to scroll — *not* the AI-startup gradient-blob cliché. Motion is the craft layer here: reveals that *explain* the See→Read→Write flow, not decoration.

**OSS for it (see §6):** **Motion** (component transitions, reveals) + **GSAP ScrollTrigger** (scroll-driven storytelling hero). **Aceternity/Magic-UI effects are Tailwind-locked → reference-only**: harvest the *effect idea*, rebuild on our token CSS with Motion. No Tailwind adoption for a landing.

---

## 4. The writing studio — standalone tool + synced to the post page (+ English name)

You asked for block editing as a **separate writing tool** *and* synced to the post page, and an **English name** for that page.

**Naming (recommendation, confirm):**
- The image + regions + reading + writing page (today `PostDetailPage` / "Drishya") → **"Studio"** (the creator's workspace). Poetic alternate: **"Study"** (an artist's *study* of a subject — close-reading + a room + an artwork); simplest: **"Reading."** I recommend **Studio**.
- The standalone block editor (no image) → **"Writer."**

**One editor, two mounts (this is the sync):** BlockNote (Path B) is a single document component. Mount it:
1. inside **Studio** (right pane), bound to a post's `text_blocks`; and
2. as **Writer**, a standalone `/write` route bound to the same block document model — *the same component, same converter, same save path.* "Synced" = they share one persistence contract (`text_blocks` + `origin`/`block_id`), so a piece written in Writer can attach to an image in Studio, and a Studio story opens in Writer. No second editor, no divergence.

**Sync mechanics:** the block document is the shared unit; a story has an optional `post_id` (attached vs free-standing). Writer = compose free-standing or continue a Studio story; Studio = the same editor + the image/regions/reading context. `/part` and `/lens` blocks are available in both but only *resolve* when a post/reading exists (empty-picker guard already exists).

---

## 5. Completing the Notion-like migration (Phase 1 done → the rest)

Phase 1 (the converter) is done. The remaining phases from `blocknote-migration.build.md` stand, plus the standalone-tool extension:
- **Phase 2** — swap the Studio body to one `<BlockNoteView>`, port slash/side-menu/toolbar, delete Path-A gutter/drag (serialized on `PostDetailPage`).
- **Phase 3** — custom `/part` `/lens` blocks + `origin/actor` props (retire `regionRef` mark).
- **Phase 4** — inline AI on our endpoints (not `xl-ai`), then Novel-style ghost-text.
- **Phase 5** — delete Path A.
- **Phase 6 (NEW) — extract Writer:** lift the BlockNote mount into a standalone `/write` route (the "separate writing tool"), reusing the exact editor + converter; add the optional `post_id` attach/detach. Because it's the same component, this is a thin wrapper, not new editor work.
- **Phase 7 (later)** — collaboration/comments (Yjs) if/when two-sided reading needs it.

---

## 6. Open-source picks for the whole revamp (beyond the editor)

Adopt at Foundation/Behaviour; harvest at Structure; keep the moat bespoke.

| Need | Pick | Licence | Note / catch |
|---|---|---|---|
| **Editor body** | **BlockNote** (in progress) | MPL-2.0 core | Mantine/headless variant (no Tailwind); `/part`,`/lens`,`origin` custom blocks we own |
| **Landing motion (UI)** | **Motion** (ex-Framer-Motion) | MIT | React-native transitions, reveals, gesture; works with our token CSS |
| **Landing scroll storytelling** | **GSAP (+ ScrollTrigger)** | standard (free) | scroll-driven See→Read→Write hero; no Tailwind needed |
| **Landing component effects** | Aceternity / Magic UI | — | **reference-only** (Tailwind-locked) — rebuild the effect with Motion + tokens |
| **Command palette (IA spine)** | **cmdk** | MIT | ⌘K to reach demoted tools + run slash verbs; the progressive-disclosure key |
| **Primitive kit (dialog/menu/toast/tooltip)** | **Radix** (patterns) | MIT | headless, CSS-agnostic → fits our tokens; kills one-off modals |
| **Resizable panes (Studio shell)** | **react-resizable-panels** | MIT | a11y + persistence; retire hand-rolled divider + unused `allotment` |
| **Server-state / optimistic** | **TanStack Query** | MIT | replace manual fetch; "feels instant" |
| **Client-state (decompose god cmpt)** | **Zustand** | MIT | shared selection, UI flags out of the 1.2k-line page |
| **Feed at scale** | masonry + **TanStack Virtual** | MIT | virtualize Gallery/Read + the parts panel |
| **Brand dashboards** | **Recharts / visx** | MIT | over the live `/taste/brand/*` endpoints |
| **Deep-zoom close-reading** | react-zoom-pan-pinch / OpenSeadragon | MIT/BSD | optional; "the fold of the fabric" |

**Guardrails (unchanged):** no Tailwind adoption just for component libs; no second editor engine; annotation/data-model contracts stay ours; don't harvest the moat (Aletheia, taste graph, felt-meaning).

---

## 7. Sequenced roadmap (foundation-first, visible wins early)

1. **Front door (first execution — see `front-door-revamp.build.md`):** rebrand → Semant, declutter nav/IA, delete the duplicate navbar, redesign the landing (motive-based, Motion+GSAP). Low-risk, high-visibility, unblocks identity.
2. **Foundation adopts (parallel, no shared files):** cmdk + Radix + react-resizable-panels + TanStack Query.
3. **Editor Path B (serialized slot):** BlockNote Phases 2–5, then Phase 6 = the standalone **Writer**.
4. **Studio moat build:** reading strip ↔ region link, pick→comment→remember, `/part`/`/lens`, context-pack RAG (backend ready).
5. **Consumer + brand surfaces:** finish **Read** (Aletheia hook/feed), taste portfolio, then the brand dashboard on the live endpoints.
6. **Craft pass (last):** tokens hardened, motion polish, empty/loading/error coverage, a11y.

---

## Decisions (RESOLVED 2026-07-14)
1. **Wordmark → Latin "Semant".** Drop `दृष्टिकोण` (it *is* Drishtikone). Sanskrit terms live as section names, not the app title; no tagline in Pass 1.
2. **Room names → Atelier + Loom** (chosen over Studio/Writer — "more brand vibes"). The image+read+write workspace = **Atelier**; the standalone editor = **Loom**. Warm, craft-forward, English-legible; echoes the "weave" thread. Routes-later: `/atelier/:postId`, `/loom`.
3. **Primary nav → `Gallery · Read · Atelier · You`** — confirmed. Research / Unconceal-queue / Anatomy / Motive demoted to a Tools menu now, ⌘K (cmdk) in the Foundation pass.
4. **Landing motion stack → Motion + GSAP** (scroll storytelling) — confirmed; no Tailwind, Aceternity/Magic-UI reference-only.
5. **First execution → SPLIT.** Pass 1 = rebrand + nav (fast, low-risk); Pass 2 = landing redesign (its own build). See `front-door-revamp.build.md`.

**Grounding correction:** rebrand is **9 occurrences / 7 files, only 3 user-visible** — not "13 spots". `frontend/package.json` name is `"frontend"` (not a brand spot); the token sub-package `drishtikone-tokens` is. Dead `pages/NavBar.jsx` still says the pre-Drishtikone name "Framewise" — delete it. Full table in `front-door-revamp.build.md`.

> Naming note: elsewhere in this doc "Studio" = **Atelier** and "Writer" = **Loom** (written before the naming was locked).

*Research + plan only — no app code touched. The spine: reorient every surface from "the pipeline" to "the act" (See·Read·Write); rebrand to Semant; cut the nav to what users do and push tools behind ⌘K; make the landing demonstrate the wedge with motion; and make the block editor one component mounted as both Atelier (with image) and Loom (standalone), synced by one persistence contract.*
