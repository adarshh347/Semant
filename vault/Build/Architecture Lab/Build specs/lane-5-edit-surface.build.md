# Lane 5 — edit-surface polish (found on visual verification)

**To:** Claude Code. **Mode:** build, structure/layout only. Verify every visual fix by **screenshot**, not by reading CSS. Commit per `workflow-protocol.md` (issue #14 for polish, #15 for slash).

The block-height fix worked, but rendering unconcealed new edit-surface issues.

## 1. Gutter reads as useless boxes AND misaligns the text (one root cause) — #14
`.rich-text-block` is a flex row: an **in-flow** `.block-gutter` (~22px, drag handle + "⋯") then `.block-body` with its own `padding-left: var(--space-4)` + 2px border-left. Result: block text starts ~48px right of the section labels ("STORY BLOCKS", "From @handle"), which sit flush at the `.content-area` left padding (`--space-7`). So (a) the labels and block text don't share a left edge, and (b) the two faint gutter controls look like empty stranded boxes.
**Fix (Notion pattern):**
- Move `.block-gutter` **out of flow** into the left margin (absolute-position it in the content-area's left padding / negative offset), so it no longer indents the text.
- Remove/neutralise `.block-body`'s left padding so block text shares ONE left edge with "STORY BLOCKS" and "From @handle". Keep the active left-accent, but as an inset/box-shadow or negative-margin border that does NOT shift the text.
- Reveal the controls on **hover** (and active), with clearly visible icons — not faint empty squares.
- **Screenshot check:** block text, "STORY BLOCKS", and "From @handle" all start at the same x; margin controls don't push the text; a hovered block shows an identifiable grip + menu.

## 2. Multi-line paragraph spacing — #14 (minor, don't over-do)
When 2+ paragraphs are written, extra space stacks (`.ProseMirror p { margin: 0 0 0.5rem 0 }`).
**Opinion locked:** keep gentle spacing for readability. At most trim to ~0.35rem, and ensure no empty trailing `<p>` adds phantom height. **Do not over-contract** — cramped paragraphs read worse, especially under the later design layer.

## 3. Button weight — #14
- **Save:** keep it (never hide the only save), but rest it quiet and brighten only when `isDirty` (state already exists, `PostDetailPage.jsx`). ⌘S/Ctrl+S already works — lean on it.
- **Add block:** to be dissolved by the slash menu (task 4). After slash works, reduce the big "Add block" to a subtle inline "+" (revealed between/after blocks on hover) or remove it.

## 4. Then: Phase 1 slash menu — #15
Proceed with Phase 1 (block types only, no AI): `/paragraph /heading /quote`, deps `@tiptap/suggestion` + `@tiptap/extension-placeholder` + `@floating-ui/dom`, one shared `<SlashMenu>` via floating-ui, strict trigger (empty block / after whitespace). Keep the old Add-block button working until verified, then apply task 3's de-weighting. Screenshot-verify.

## Order & git
0. First clear any queued uncommitted work per `workflow-protocol.md` (handle `android/` — decide gitignore, don't blind-add).
1–3. Edit-surface fixes above (#14), committing each as a small `fix(drishya): … (#14)`.
4. Phase 1 slash (#15) as `feat(drishya): slash menu for block types (#15)`.
Update #14 and #15, push the PR, end with a one-paragraph handoff.
