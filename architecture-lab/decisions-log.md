# Decisions log — Drishya (the page formerly PostDetailPage)

Locked decisions live here so the build phase doesn't re-litigate them or lose them in chat.
Status key: **LOCKED** = build to this · **PENDING** = still Adarsh's call · **DEFERRED** = decided later, in the named lane.

---

## Naming

- **Page:** `Drishya` (display) / `DrishyaPage` (code). **LOCKED.** Rename `PostDetailPage → DrishyaPage` in a later build pass, not during analysis.
- **App:** currently `Drishtikone` — being rebranded (the `-kone` tail sounds dated). Frontrunners: **Drishti** (continuity) or **Nazar** (freshest). **PENDING.** App + page renamed together in the build pass.

---

## Lane 5 — Writing studio: answers to Claude Code's 6 questions

1. **Toolbar shape → bubble on selection. LOCKED.**
   One selection/bubble toolbar for inline formatting (bold/italic/underline), not a fixed per-block bar. Block types (Heading/Quote/Paragraph) come from the "+" / "/" insertion menu, not the toolbar.

2. **Meta counts (words / min / blocks) → lift out of the body. LOCKED.**
   They are status, not content. Move to a thin status line at the pane bottom (or header). Out of the writing surface.

3. **Two AI surfaces → fold composer in, keep sidebar. LOCKED.**
   The quick Sutradhar composer (draft-from-image / short prompt) becomes an option inside the "+" insertion flow. The full AI sidebar stays as the deep conversational assistant. One quick, one deep — distinct roles.

4. **Tags home → one shared home; Lane 4 places it. DEFERRED to Lane 4.**
   Lane 5 assumes a single tags home used in both view and edit (a quiet metadata footer/panel). Lane 4 owns the exact placement. Do not solve tags twice.

5. **Per-block controls → left-gutter drag handle + "⋯" overflow menu. LOCKED.**
   Move / delete / colour move off the always-on row into a gutter affordance revealed on hover/active. The drag handle is also the basis for reorder.

6. **Insertion position → position-aware. LOCKED.**
   New single `insertBlock(block, atIndex)` inserts after the active block / at the caret, not always at the end. All three add-sources call it.

---

## Cross-cutting decisions

- **Editor model → Path A first, plan Path B. LOCKED (sequencing).**
  Path A = keep one TipTap editor per block, add one shared bubble toolbar targeting the active block (uses existing `selectedBlockId`, PostDetailPage.jsx:50). Build this first. Path B = one editor for the whole document with block nodes; the all-lanes synthesis should still lay it out (it makes drag-reorder + inline AI cleanest), but it is a later, bigger pass.

- **Block `origin` field → add now. LOCKED.**
  Every block gains `origin: 'human' | 'sutradhar'`, set at each creation point (`addBlock`, `draftFromImage`, `writeFromPrompt`, `handleSuggestionSelect`). Works under Path A. Lets the reader tell human from AI. Surface treatment (how it's shown) is deferred to the design phase — plan the field now.

- **`MultiBlockEditor.jsx` → delete. LOCKED (build pass).**
  Confirmed dead (zero imports). Remove in the build pass, not during analysis. Do not touch the separate `.text-block-item[data-block-id]` view-mode selector the highlight code uses.

- **Highlights in context → use existing `block_id`. LOCKED (Lane 4 owns detail).**
  Highlights already store `block_id`; link each saved quote back to its place in the story instead of showing orphan quotes.

---

## Still open (do not build yet)
- App name (Drishti vs Nazar).
- Region duplication: `bounding_box_tags` vs `region_annotations` merge-or-keep (Lane 3 / Lane 6 to inform).
- Everything Surface (colour / spacing / the 6 hardcoded hex swatches / emoji icons / glassmorphism) — after structure.

---

## Inline AI direction (new Purpose sub-lane) — LOCKED
- AI generation lives **inside writing**, not as a chatbot. Two mechanisms: **inline generation** (streams into the current block) and **slash commands** (`/` menu). **Slash is the primary surface — develop deeply.**
- Replaces the insert-menu "Compose with Sutradhar" and "Draft from image" (→ `/draft`). The deep AI **sidebar stays** for real conversation only.
- `origin` marking is the trace of who wrote what; investigate range-level origin (a TipTap mark) for mixed-authorship blocks.
- Explore further: ghost-text continuations (Tab to accept), selection→AI verbs in the bubble toolbar.
- Slash `/` menu may be the first real reason to consider **Path B** (single-document editor) — Claude Code to advise. Spec + feasibility in `purpose-inline-ai.design.md` → `responses/purpose-inline-ai.findings.md`.

## Lane 5 second-layer cleanup — LOCKED (build)
Block height content-driven; gutter controls identifiable; remove decorative intro + demote "Story blocks" heading; delete `MultiBlockEditor.jsx`; collapse to one column; clear `activeBlockId` on delete; seed a focused empty block on entering edit; surface `origin` as `data-origin` (hook only, no styling); fix `Date.now()` id collision. See `lane-5-second-layer.build.md`.

---

## Inline AI — answers to the 8 findings questions
Phase 1 (slash menu for block types, no AI) only needs Q1–Q3, which are LOCKED. Q4–Q8 are proposed; confirm before Phase 2.
- **Q1 Path A for slash — LOCKED yes.** Path B stays a later, separate pass.
- **Q2 Deps — LOCKED yes** (`@tiptap/suggestion` + `@tiptap/extension-placeholder`). **Override Claude Code:** also add `@floating-ui/dom` for popup positioning — the editor lives in a scrolling, resizable split pane where a hand-rolled popup will drift.
- **Q3 Trigger — LOCKED strict.** `/` opens only on an empty block or after whitespace.
- **Q4 v2 scope — PROPOSED narrow.** Ship `/draft` + `/continue` first, then grow.
- **Q5 expand/shorten/rewrite — PROPOSED bubble-toolbar** (act on selection), not slash. Rule: slash creates at caret, bubble transforms selection.
- **Q6 mixed authorship — PROPOSED later (Phase 3).** Block-level origin for now.
- **Q7 streaming — PROPOSED not v1.** Ship Phase 2 non-streaming; streaming is Phase 3.
- **Q8 Groq async fix — PROPOSED yes, bundled with Phase 3 streaming.**

## Reopened on #14
- **Block rhythm still reads tall on screen** despite `min-height: 1.7em`. Root cause: `--space-5` is undefined in `index.css` (scale skips 4→6) yet used in 4 places incl. `.advanced-editor` gap; plus a residual paragraph margin. Fix the token + tighten one-line rhythm; verify by screenshot.

---

## Slash direction — expanded (from verification session)
- **AI writing becomes slash commands too** (locked direction). Generation verbs at the caret: `/draft` (from image), `/write <prompt>` (write from instruction), `/continue`, `/describe`; transforms: `/rewrite`, `/expand`, `/shorten`, `/version` (offer an alternate, non-destructive). Reference inserts (later): `/part` (an annotated image region), `/lens` (an Aletheia reading) — these also wire the Visual↔Content complementarity from Lane 2. See vault → [[Slash command potentialities]].
- **Retire the big Add-block card** now that slash covers block types; keep AI compose reachable+compact until Phase 2 slash-AI replaces it; keep a **recognisable** "+ Add block" button (it was flattened to near-white).
- **Slash positioning bug:** switch floating-ui to `strategy: 'fixed'` so the menu stays pinned to the caret during inner-container scroll.

---

## Slash Phase 2 — context-aware + replace Compose (LOCKED)
- **Context-aware menu:** empty/at-start block → structure trio + `/version`; mid-text caret → AI verbs (`/draft /write /continue /rewrite /expand /shorten`). The trio must NOT appear mid-text.
- **Compose with Sutradhar button is removed entirely** — replaced by `/draft` + `/write` (min), reusing existing non-streaming endpoints. Keep a recognisable "+ Add block".
- `/version` (empty context) = generate an alternate starting draft from the image (confirm if a different meaning was intended).
- See `inline-ai-phase2.build.md`, vault → [[Slash command potentialities]].

## Lane 4 — answers to the 5 questions (LOCKED unless noted)
1. Persona line → **content meta-head only** (provenance). Lane 1 does NOT also render it. One home.
2. Epic → **keep as a small chip** in the meta-head; not a full section.
3. Highlight jump → **cross-tab (Story + scrollIntoView) now**; inline margin rail is a later enhancement.
4. Edit-mode tags → **sticky/collapsible so reachable while writing** (not buried at the bottom of a long column).
5. Underline hint → **remove the permanent strip**; rely on the selection tooltip.

---

## Lane 1 — top chrome: answers to the 5 questions (LOCKED)
1. **Sutradhar brand** → fold to a small quiet label at the topbar's left (next to the back-link). No dedicated center slot. (Dropping is also acceptable; the trace is carried by block `origin`.)
2. **Navbar collapse** → on `/posts/*`, collapse the 9 links into a single disclosure menu (☰▾), using the existing `app-layout--fullscreen` CSS hook (reachable now — no new plumbing). Not a shrunk-but-visible rail.
3. **Edit button** → remove the standalone top Edit button; entry to editing is a **pencil affordance on the Content panel header** (not pure edit-on-focus — reading page, avoid accidental edits).
4. **AI Assistant** → keep in the topbar but **de-weight from primary to a quiet secondary** button (slash now carries everyday AI; the sidebar is for occasional deep conversation).
5. **Upload vs back-link** → keep the back-link (page's own exit) and logo (home); **fold the Upload CTA into the collapsed navbar menu** rather than a standing button on post pages.

Every capability stays reachable: theme (navbar, dup removed), 9 links + Upload (menu), leave (back-link), AI (secondary button), edit (pencil), delete (topbar "⋯" overflow).

---

## Lane 2 — split shell: answers to the 5 questions (LOCKED)
1. **Region model (Q1)** → **DEFERRED to Darshan Track A.** Lean is Option A (merge into one region model) but this is a Foundation data decision that also gates Lanes 3 & 6 — do NOT build it in the Lane 2 shell pass. Lane 2 touches no region data.
2. **Edit mode** → the Visual pane **narrows** via a width preset on the SSOT (`leftPanelWidth`), smooth transition, restore on exit. Replaces the opacity-dim.
3. **Divider presets** → **yes**: a collapse-to-rail toggle ("focus the writing") + double-click-to-reset to 45%, alongside drag.
4. **Panel titles** → **drop** the "Visual"/"Content" `<h3>`s; header = tabs (left) + a right-aligned actions slot.
5. **Split primitive** → **keep the hand-rolled divider** (no `allotment` dep); harden it to the WAI-ARIA APG window-splitter pattern (focusable separator, role/aria-value*, Arrow-key resize).

---

## Front-door revamp — answers to the 5 decisions (LOCKED 2026-07-14)
1. **Wordmark** → **Latin "Semant"**. Drop `दृष्टिकोण` (it *is* Drishtikone). Sanskrit terms → section names only; no tagline in Pass 1.
2. **Room names** → **Atelier + Loom** (over Studio/Writer — wanted brand vibes). Workspace (image+read+write, today `PostDetailPage`/"Drishya") = **Atelier**; standalone editor = **Loom**. Routes-later: `/atelier/:postId`, `/loom`.
3. **Primary nav** → **`Gallery · Read · Atelier · You`**. Demote Research / Unconceal / Anatomy / Motive to a **Tools** overflow now; ⌘K (cmdk) in the Foundation pass. Delete dead `pages/NavBar.jsx` (unimported, malformed, still says "Framewise").
4. **Landing motion stack** → **Motion + GSAP** (scroll storytelling). No Tailwind; Aceternity/Magic-UI reference-only.
5. **First execution** → **SPLIT**: Pass 1 = rebrand + nav (fast/low-risk); Pass 2 = landing redesign (own build). Spec: `front-door-revamp.build.md`.

Grounding fix: rebrand is **9 occurrences / 7 files, 3 user-visible** — not "13 spots". `frontend/package.json` name = `"frontend"` (not a brand spot); token pkg `drishtikone-tokens` → `semant-tokens`.
