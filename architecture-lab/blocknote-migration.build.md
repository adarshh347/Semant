# BlockNote migration — full build spec (phased): the Path-B writing studio

**To:** Claude Code (Drishya thread, `feat/frontend`). **Mode:** build.
**Sources:** `responses/blocknote-adoption-plan.findings.md` (the plan + verdict), `responses/frontend-subsection-and-harvest-map.findings.md` (harvest philosophy), `responses/oss-adoption-dossier.findings.md` (adoption model — extend via API, don't fork). Current editor: `RichTextBlock.jsx`, `slashCommand.jsx`, `SlashMenu.jsx`, `regionRef.js`, and the block state in `PostDetailPage.jsx`.
**Goal:** replace **Path A** (one TipTap editor per block) with **one BlockNote document** (Path B), deleting the hand-built block/slash/gutter/drag plumbing, while keeping the moat (`/part`, `/lens`, `origin`) as **custom blocks we own** and preserving every capability and every cross-link.

## Locked decisions (from the plan; confirm the ⚠ before the phase that needs it)
- **Editor:** BlockNote (`@blocknote/core` + `@blocknote/react`), ProseMirror/TipTap family — a migration, not a rewrite.
- **Styling variant:** **`@blocknote/mantine`, themed to our tokens** via BlockNote CSS variables. **NOT `@blocknote/shadcn`** — we have no Tailwind. (Go headless only if Mantine chrome fights the border-grammar.)
- **Storage format (⚠ Phase 1):** **keep persisting `text_blocks` as HTML** for back-compat; convert HTML⇄BlockNote on load/save. Do **not** migrate backend `TextBlock` storage to BlockNote JSON in this pass. Revisit later if needed.
- **Inline AI (⚠ Phase 4):** build on our existing endpoints (`/chat/vision`, `/rewrite/vision`, `/flow/expand-node`, `epicService`/`promptEnhancedText`). **Do NOT add `@blocknote/xl-ai`** (paid/GPL tier). Harvest Novel's ghost-text *interaction* only.
- **Provenance:** `origin`/`actor` and `block_id` stay **our** block attributes; we own serialization.

## Rules (per `workflow-protocol.md`)
- **Verify UI by SCREENSHOT** (headless Chrome, live app) at read + edit modes; **verify data by test** (the converter is the risk — assert block-id preservation and round-trip, don't eyeball it).
- Conventional commits on `feat/frontend`, referencing the issue: `feat(drishya): … (#NN)`. Open one umbrella issue (label `architecture`): *"Editor Path B — BlockNote migration"*; keep its checklist current in-session.
- **Phase 2 edits the shared `PostDetailPage.jsx` → serialize via the pause-slot** used by the Track-D thread (that thread also edits this file). `git pull` first; confirm no lane is mid-flight on `PostDetailPage.jsx`; land as its own commit(s).
- Every phase ends with a **handoff line**: what changed, commits, issue updated, what's next.
- Keep the tree clean; stage only files you changed; don't blind-add untracked paths.

---

## Phase 0 — Spike in isolation (NO PostDetailPage edit)
Stand BlockNote up in a **dev-harness route** (mirror `RegionSurfaceLab` / `pages/RegionSurfaceLab.jsx`). Prove three things and stop:
1. **Tokens theme it.** Import `@blocknote/mantine` + styles; override BlockNote CSS variables so the editor uses our `--accent`/`--surface`/`--line`/`--radius`/`--font-*`/light-dark. Screenshot light + dark matching our surface.
2. **A custom block renders.** Register one trivial custom block (e.g. a `partRef` stub) via BlockNote's schema API — proves the extension point `/part` and `/lens` will use.
3. **A custom slash item works.** Add one slash item that inserts the custom block.
**Verify:** screenshots (light/dark, custom block, slash insert). **Stop for review.** No real wiring yet.

## Phase 1 — The converter (the real risk; NO PostDetailPage edit yet)
Build and unit-test a pure module `blockConvert.js`:
- **import:** our `text_blocks` (`{id, type, content:HTML, origin, color}`) → BlockNote document. **Preserve each block's `id`** (map onto the BlockNote block id) and carry `origin`/`color` into block props. Use BlockNote's `tryParseHTMLToBlocks` for the HTML body.
- **export:** BlockNote document → our `text_blocks` shape (HTML via `blocksToHTMLLossy`), **same ids**, `origin`/`color` preserved.
- **Tests (must pass, this is the gate):**
  - round-trip: `export(import(blocks))` preserves block **ids**, order, `origin`, and text.
  - **cross-link integrity:** a `Highlight.block_id` and a `Region.block_id` pointing at a block still resolve after round-trip (ids unchanged; `data-block-id` still emitted on the rendered block).
  - edge cases: empty story, a `sutradhar` block, a block with a colour wash, a heading + quote.
**Verify:** test output. **Stop for review.** Nothing user-visible changes.

## Phase 2 — Swap the document body (EDITS PostDetailPage.jsx — SERIALIZED)
Only after 0–1 are green and the ⚠ storage decision is confirmed. **Pause-slot; pull first.**
- Replace the `editedBlocks.map(RichTextBlock)` render (edit mode) with a single `<BlockNoteView editor={…}>`; seed it via `blockConvert.import(post.text_blocks)`; on change/save, `blockConvert.export(...)` back into the existing `text_blocks` save path (`handleSave` → `text_blocks: editedBlocks`).
- **Port the slash menu** (`slashCommand.jsx`): STRUCTURE set (Paragraph/Heading/Quote/Version) and AI set (Draft/Write/Continue/Rewrite/Expand/Shorten) become BlockNote slash items; keep the **context-aware rule** (structure at empty/block-start, AI mid-text) — reimplement against BlockNote's slash `getItems`.
- **Adopt BlockNote's side menu (＋ + drag handle) and formatting toolbar**; **delete** our hand-built gutter, drag-reorder handlers, `insertBlock`/`makeBlock`, per-block move up/down.
- Keep the **status line**, meta-head, tabs, and read-mode rendering intact. Read mode may stay our current renderer or use BlockNote read-only — pick the lower-risk one and note it.
**Verify (screenshots):** edit a story — type, `/` (both contexts), reorder by drag, format via toolbar; save and reload → content, order, `origin` intact; **Highlights still jump to the right block**. **Stop for review.**

## Phase 3 — Custom blocks for the moat (`/part`, `/lens`, `origin`)
- Implement `/part` (insert an annotated region ref) and `/lens` (cite an Aletheia reading) as **BlockNote custom blocks** (or inline content) rendered by our React components, sourced from `Region` / `local_context.aletheia`. Retire the `regionRef.js` TipTap mark.
- Make `origin: 'human'|'sutradhar'` (and `actor` where relevant) a **custom block prop** set at every creation point; render the existing `data-origin` hook from the prop.
- Keep the "empty picker is a dead end" rule: `/part` only when regions exist, `/lens` only when a reading exists.
**Verify:** screenshots of a `/part` and `/lens` block; `origin` prop present on AI-authored blocks; region/reading data renders. **Stop for review.**

## Phase 4 — Inline AI on our endpoints (not xl-ai)
- Wire the AI slash verbs to our endpoints (as `inline-ai-phase2.build.md` did), inserting/replacing via BlockNote's block API with `origin:'sutradhar'`; show the `aiBusy` state.
- Then **harvest Novel's ghost-text interaction** (Tab-to-accept continuation) wired to the streaming endpoint — Phase 3 of the AI roadmap. Confirm no dependency on `@blocknote/xl-ai`.
**Verify:** each verb works and lands a `sutradhar` block/range; ghost-text accepts on Tab. **Stop for review.**

## Phase 5 — Delete Path A
Remove `RichTextBlock.jsx`, `TipTapEditor.jsx`, `slashCommand.jsx`, `SlashMenu.jsx`, `regionRef.js`, and the block/drag/`insertBlock`/`makeBlock` state in `PostDetailPage.jsx`. Grep-confirm no other importer. Net LOC deleted is the payoff.
**Verify:** build passes; full edit→save→reload→highlights walk-through screenshots; handoff.

---

## Explicitly NOT in this build
- **No backend `TextBlock` storage change** (we keep HTML; that's a separate later pass if we ever move to BlockNote JSON).
- **No `@blocknote/xl-ai`, exports, or multi-column** (paid/GPL tier).
- **No Tailwind / shadcn variant.**
- **No Visual-pane / Track-D work** — that's the other thread; this build only touches the writing studio (and `PostDetailPage.jsx`'s Content side, serialized).
- **No collaboration/Yjs** yet (future).

## If a phase is too big
Phase 2 is the largest. Split into **2a body swap + save round-trip** (get one BlockNote doc editing and persisting via the converter, slash/side-menu ported) then **2b delete the old gutter/drag plumbing**. Ship 2a (the visible win) first.

## Open question to surface to Adarsh before Phase 2
Confirm **keep-HTML storage** (default) vs migrate to BlockNote JSON, and **Mantine vs headless** styling. Both are recommended as-defaulted in the plan; a one-line confirm unblocks Phase 2.
