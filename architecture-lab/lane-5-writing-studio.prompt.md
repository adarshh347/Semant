# Lane 5 — Writing studio (edit mode): the block editor and its sub-tools

**To:** Claude Code (local, in this repo)
**Mode:** deep read + architecture proposal. **Do not edit any app code.** Write findings only.
**This is the heaviest lane. Spend the most time here.**

## Why this lane exists
Edit mode is the worst "cards within cards" offender. Every block carries its own toolbar, its own colour swatches, and its own controls, and there are several overlapping ways to add content. This lane finds the optimal editor structure.

## Files to read
- `frontend/src/components/PostDetailPage.jsx` edit branch (~622–768):
  - `.edit-shell` → `.edit-shell-intro` (kicker + heading + `.editor-meta` words/min/blocks).
  - `.edit-layout` → `.edit-main-column` (`.edit-section` "Story blocks" → `.advanced-editor` → `RichTextBlock` list; then `.editor-tools-section` "Add block" with 3 buttons).
  - `.edit-side-column` → `.sutradhar-composer` (Draft from image; input + Write; hint; error) + `.tags-edit-section` → `.tags-card` (chips + popular tags + input+Add).
- `frontend/src/components/RichTextBlock.jsx` (full) — per block: `.block-toolbar` (H1, P, |, Bold, Italic, Underline, Quote) + `EditorContent` + `.block-controls` (move up/down group, `.color-picker` of **6** swatches, delete).
- `frontend/src/components/MultiBlockEditor.jsx` — check if this is dead/legacy (looks unused); confirm and recommend.
- The three add paths: `addBlock()` (~274), `.sutradhar-composer` (draftFromImage/writeFromPrompt append blocks), and the AI sidebar `onAddBlock` (~987). Map all three.
- `frontend/src/components/PostDetailPage.css` + any block CSS — `.rich-text-block`, `.block-toolbar`, `.block-controls`, `.color-picker`, `.add-block-menu`, `.sutradhar-composer`, `.tags-card`.

## Questions to answer (architecture only)
1. **Per-block toolbar × N.** Every block renders its own always-on formatting toolbar. Propose the optimal alternative — e.g. a single shared toolbar, or a selection/bubble toolbar that appears only on the active block — and describe the component/state change (where the active-block id lives, how the toolbar targets it).
2. **Per-block colour picker (6 swatches).** Same multiplication. Propose a lighter structure (on-demand control, or moved out of the block). Keep colour-setting capability.
3. **Per-block controls.** Move up/down + delete on every block. Optimal home (hover control? drag handle? a single block menu?) — structural only.
4. **Three ways to add content.** `Add block` buttons, the Sutradhar composer, and the AI sidebar all inject blocks. Map each, then propose whether they should converge (one insertion pathway) or stay separate with clear roles. Don't remove capability.
5. **Two-column edit layout in a narrow pane.** `.edit-main-column` + `.edit-side-column` inside the right pane (which can be ~45% width). Does two columns make sense here, or should side tools (composer, tags) become collapsible/inline? Propose the structure.
6. **Intro block.** `.edit-shell-intro` (kicker + sentence + meta). Is the heading sentence structural or decorative? Where should word/min/block counts live (chrome vs its own row)?
7. **Dead code.** Confirm whether `MultiBlockEditor.jsx` is used anywhere; if not, recommend removal.

## Hard constraints
- Structure only. No colour/font/spacing (you may note the 6 hardcoded hex swatches as off-theme for a later lane).
- Preserve every capability: rich-text formatting, colour, reorder, delete, all three add paths, word/read stats, save/cancel.
- No app code — a plan.

## Output contract → write to `responses/lane-5-writing-studio.findings.md`
- **Current editor tree** — `.edit-shell` down to a single `RichTextBlock`, counting how many controls multiply per block, with file+line refs.
- **Multiplication table** — control | rendered per block? | proposed single/shared home.
- **Add-content map** — the three insertion paths and a convergence recommendation.
- **Proposed editor structure** — leanest tree (shared toolbar, block model, side tools), short and concrete.
- **Dead-code note** — MultiBlockEditor status.
- **Questions for Adarsh.**
