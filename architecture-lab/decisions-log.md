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
