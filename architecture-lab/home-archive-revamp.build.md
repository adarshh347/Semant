# Home + Archive revamp — build spec (whole revamp + OSS integration)

**To:** Claude Code — the **app-shell / OSS session** (`feat/oss-foundation`; owns Home/Gallery/Feed/App shell). **Mode:** build.
**Sources:** `responses/home-and-archive-revamp.findings.md`, `responses/oss-tools-brainstorm-home-archive-editor.findings.md`, `responses/home-dashboard-design.findings.md`, taste spec **v1.3** (plum), Chiasm lexicon.
**Goal:** replace the tool-page entry with (1) a **curated widget dashboard Home** and (2) a **real image Archive** (Gallery) that browses thousands smoothly and fixes the prev/next race — bringing in the needed OSS. **Zero Chiasm files** (that partition holds). Themed plum v1.3; every tile/photo an on-ramp into the work.

## Locked defaults (per the plans; adjust only if Adarsh says)
- **Home = curated bento** (CSS grid + plum tokens), **not** user-customizable yet (react-grid-layout deferred).
- **Archive = infinite scroll** via TanStack Query `useInfiniteQuery` (fixes the race structurally) + **react-photo-album** justified layout + **TanStack Virtual** (OSS "item 2") + **Cloudinary LQIP** blur-up placeholders (you already use Cloudinary — no new pipeline) + **reuse `RegionLightbox`** for full-view (brand-consistent; else `yet-another-react-lightbox`).
- **Upload + tag-analysis move OFF the archive** (upload → the ⌘K action / a Radix Dialog; tag-analysis → a tool/filter surface).
- **Region-mark motif (◈, plum)** is the home's signature.

## Rules (`workflow-protocol.md`)
- Verify by **screenshot** (Home + Archive, light+dark, mobile; a long-scroll capture; the fixed pager under fast interaction) — the extension must be connected, else note it and use the :5175 eyeball server.
- Conventional commits per piece; keep **#33** updated; open the **separate PR** for `feat/oss-foundation` when the batch is ready (don't touch the Chiasm PR). Handoff each phase. Stop after each.
- No Chiasm files (`PostDetailPage.jsx`, editor, Field). MIT/CSS-agnostic deps only — no Tailwind.

---

## Phase 1 — Fix the Archive data + the race (highest value first)
Rewrite Gallery's data layer: **`useInfiniteQuery`** keyed by page (+ tag/search), an **IntersectionObserver sentinel** fetching the next page on scroll. **Delete the `setCurrentPage(response.current_page)` echo** and the Prev/Next buttons. Ordered + deduped in-flight → the fast-click "hallucination" is structurally gone. Verify: hammer scrolling / rapid loads never show a stale/duplicated page. **Stop.**

## Phase 2 — The Archive layout (browse thousands)
- **react-photo-album** justified grid from image aspect ratios (Google-Photos feel); **TanStack Virtual** so only on-screen rows render (5k+ smooth).
- **Cloudinary LQIP** blur-up (tiny blurred placeholder → cross-fade to full) so nothing pops in grey; native `loading="lazy"`.
- **Click a photo → open Chiasm** on it (`/posts/:id` for now).
- **Declutter:** move the upload form off (→ ⌘K action + a Radix Dialog uploader) and the tag-analysis/story-gen off the archive; keep tag **filter chips** + add a search box. The archive is *just* the archive.
- Full-view: reuse `RegionLightbox` (or YARL). Verify at desktop/mobile, light+dark. **Stop.**

## Phase 3 — The Home widget dashboard (the new entry)
Build a **curated bento** (CSS grid + plum tokens), set it as the **index route**. Tiles (size = importance), each fed by a small `useQuery`:
- **Hero** (full) — wordmark + the wedge line + one ink-pill CTA (Enter Chiasm / Upload).
- **Continue in Chiasm** (2×2) — recent in-progress readings (thumb · title · "N percepts · M words"); horizontal overflow via **Embla**; click → resume.
- **Your taste · Anuraṇana** (2×1) — "your eye leans toward…" + motif chips (from the taste/portfolio endpoint).
- **Read** (1×1) — one Aletheia hook (image + lens + fork).
- **The Archive** (1×1) — a live 3-image mosaic (reuse react-photo-album at tile scale) + "N images →".
- **Parts you recently noticed** (3×1) — recent Percept chips (◈, plum) → jump to percept/region.
- **This week** (1×1, the one dark tile) — readings · words · percepts.
- Responsive 4→2→1 cols; identical gutters; editorial (serif titles, muted body, ≤1 accent/tile). Run the taste-spec slop-checklist. **Stop.**

## Phase 4 — Polish (optional)
- OSS **item 3 — react-hotkeys-hook** (app-wide shortcuts: `g g`→Gallery, `?`→shortcuts; ⌘K already).
- Subtle load motion on tiles (later, Motion lib; reduced-motion safe).

---

## Explicitly NOT in this build
- **No Chiasm files / editor / Field.**
- **No customizable drag-home** (react-grid-layout) yet — curated bento only.
- No Tailwind / shadcn-bento / Aceternity packages (reference only).

## OSS added this build (all MIT, CSS-agnostic → plum tokens)
`@tanstack/react-virtual`, `react-photo-album`, `embla-carousel-react`, (lightbox: reuse RegionLightbox or `yet-another-react-lightbox`), `react-hotkeys-hook` (Phase 4). Cloudinary LQIP = URL transforms, no dep. `@tanstack/react-query` already present.

---

## Separate — for the CHIASM session (not this branch): Manuscript UI fixes
Hand to the Chiasm session (owns `PostDetailPage.jsx`), folds into BlockNote Phase 3, per `home-and-archive-revamp.findings.md` §3:
- **Tags:** move from floating-above to a **thin collapsed strip at the bottom** of Manuscript; expand into a **bounded** panel (max-height, own scroll) that never pushes the writing.
- **Block flow:** keep Enter = new paragraph block but **tighten inter-block spacing so prose flows**; `Shift+Enter` = soft break; structural blocks (heading/quote/list) only via `/`; don't leave stray empty blocks. No new dependency — tune BlockNote.
