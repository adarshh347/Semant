# Lane 5 — second-layer cleanup (build note)

**To:** Claude Code. **Mode:** build (small, surgical). Structure + sizing only — no colour palette / typography polish. Preserve every capability. Update `issues/lane-5.md` and `workflow-log.md` when done.

The first Lane 5 pass landed correctly (bubble toolbar, gutter, unified insert, position-aware `insertBlock`, status line, `origin` field, drag-reorder). This pass fixes what that change exposed, plus bugs found on review.

## A. Issues Adarsh pointed out
1. **Blocks too tall for one line.** `.editor-content-wrapper { min-height: 80px }` (`PostDetailPage.css:1101`) forces ~80px per block. Make height content-driven (a single line should look like a single line). Keep a small min so an empty block is still clickable (~1 line). This is now a **structural** fix, not "later surface."
2. **Gutter controls read as mystery boxes.** The grip + "⋯" (`RichTextBlock.jsx:84–158`) render as faint empty squares (`--ink-subtle`, faint border). Give them a clearer resting state or reveal them only adjacent to the caret/active block. A user must be able to tell what they are.
3. **Decorative heading.** Remove/demote `.edit-shell-intro` "Writing studio / Shape the story quietly…" (`PostDetailPage.jsx:664–668`). It is chrome pretending to be content.
4. **Delete dead code.** Remove `MultiBlockEditor.jsx` (zero imports). Do NOT touch the `.text-block-item[data-block-id]` view-mode selector the highlight code uses.
5. **Collapse the side column.** With the composer moved into the insert menu, `.edit-side-column` now holds only the Tags card, so the two-column `.edit-layout` no longer earns itself. Move tags to a single-column position (coordinate with Lane 4's "one tags home") and drop to one column. If Lane 4 isn't decided yet, park tags in a quiet single-column block at the end of the editor — not a second column.

## B. Additional issues found on review (fix these too)
6. **`activeBlockId` is not cleared when its block is deleted.** `deleteBlock` (`:307`) filters the block but leaves `activeBlockId` pointing at the deleted id; `insertBlock` then can't find it and silently falls back to append. On delete, if the deleted id is active, set `activeBlockId` to the previous/next block (or null).
7. **Entering edit with zero blocks is a dead end.** The block list renders nothing and the user must hunt for "+ Add block". On entering edit (or on an empty story), seed one focused empty paragraph so the caret is ready to type. (This also sets up the inline-AI direction.)
8. **`origin` is stored but never surfaced.** `makeBlock` sets `origin` (`:280`) but it is never passed to `RichTextBlock` or the view-mode `.text-block-item`, so it dead-ends. Pass `origin` through and render it as a `data-origin="human|sutradhar"` attribute on the block DOM in both edit and view. **Do not style it** — just expose the hook so the Surface pass can mark human vs AI later.
9. **Two stacked headings before the blocks.** After removing the intro (item 3), also demote `.edit-section-head` "Story blocks" (`:674–676`) — one quiet label at most, not two headings.
10. **Empty-state duplicates the insert menu.** `.story-empty` buttons ("Write the story" / "Draft from image", `:830–838`) duplicate the insert flow. Note for Lane 4; don't fix here, just flag in the issue.
11. **Block id collision risk.** `block_${Date.now()}` (`:281`) can collide if two blocks are made in the same millisecond. Use a monotonic counter or a uuid.

## C. Coordinate with the AI direction
The insert menu's "Compose with Sutradhar" (input + Write, `:730–763`) is a chatbot-in-a-menu that the **inline slash-command work will replace** (see `purpose-inline-ai.design.md`). So in this pass, do **not** invest in restyling that composer — keep it working, but expect it to be superseded. Leave the deep AI sidebar alone.

## Exit check
- One-line block looks like one line. Empty edit gives a ready caret. Gutter controls are identifiable. No `MultiBlockEditor.jsx`. One column. `data-origin` present on blocks. Deleting the active block doesn't break insertion. No duplicate headings. All capabilities intact.
- Update `issues/lane-5.md` (Delivered/ Gaps) and append a line to `workflow-log.md`.
