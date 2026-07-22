# Lane 5 — Writing studio rework (Drishya edit mode)

GitHub issue: #13

Labels: architecture, lane-5, drishya

## Expected
A calm single-surface block editor: one selection (bubble) toolbar instead of one per block; per-block controls hidden in a gutter; one position-aware insertion flow with Sutradhar compose folded in; word/min/block counts moved to pane chrome; a `human` vs `sutradhar` origin on every block; delete dead `MultiBlockEditor`. Structure only — no colour/spacing polish. Tags deferred to Lane 4.

## Claude Code response & promises
Implement bubble toolbar, left-gutter drag handle + "⋯" overflow (turn-into / colour / move / delete), unified "+ Add block" insert menu (Paragraph/Heading/Quote + Draft-from-image + Write) inserting after the active block, status line in the footer, `origin` on every block, delete dead code, Path A (keep per-block editors + shared toolbar).

## Delivered (verified against the shipped code)
| Promise | Status | Evidence |
|---|---|---|
| Bubble toolbar on selection (B/I/U) | ✅ done | `RichTextBlock.jsx:163` BubbleMenu |
| One shared toolbar (not per block) | ✅ done | per-block MenuBar removed |
| Gutter: drag handle + ⋯ menu | ✅ done | `RichTextBlock.jsx:84–158` |
| ⋯ menu = turn-into / colour / move / delete | ✅ done | `:110–155` |
| Unified insert flow, Sutradhar folded in | ✅ done | `PostDetailPage.jsx:702–766` |
| Position-aware insertion | ✅ done | `insertBlock` inserts after `activeBlockId` `:290–302` |
| Meta counts moved to footer | ✅ done | `.edit-statusline` `:1019–1023` |
| `origin: human \| sutradhar` on every block | ✅ done | `makeBlock` `:280`, set at all 4 creation points |
| Drag-to-reorder | ✅ done (bonus) | drag handlers `RichTextBlock.jsx:80–96` |
| Path A (per-block editors kept) | ✅ done | `useEditor` still per block `:36` |
| Delete `MultiBlockEditor.jsx` | ❌ missed | file still present |

**Verdict: promises largely kept.** The locked architecture is really in the code — this is not hallucinated progress.

## Gaps / deferred / new demands
- **Miss:** `MultiBlockEditor.jsx` still on disk — delete it.
- **New problem (sizing):** `.editor-content-wrapper { min-height: 80px }` (`PostDetailPage.css:1101`) makes a one-line block ~80px tall — blocks look like big empty boxes. Reduce to content-driven height.
- **New problem (legibility):** the two gutter controls (grip + ⋯) render as faint empty squares — they read as "mystery boxes," not controls.
- **Redundancy:** with the composer moved into the insert menu, `.edit-side-column` now holds only the Tags card → the two-column layout no longer earns itself. Fold tags out and drop to one column (coordinate with Lane 4).
- **Leftover chrome:** `.edit-shell-intro` heading "Shape the story quietly…" (`:664–668`) is decorative, never locked — demote/remove.
- **Purpose demand (AI):** Draft-from-image / Write feel like a separate tool; AI generation should blend into *writing*, not sit as a chatbot-style block. (See workflow brainstorm.)
- **Deferred (correct, not a miss):** Tags card-within-card left as-is — owned by Lane 4.

## Decisions
- Delete `MultiBlockEditor.jsx` in next build.
- Block sizing (min-height / padding) is now in scope as a structural fix, not just surface.
- Gutter controls need a clearer resting state (still structure-adjacent).
- Side column collapses to one column once tags move (with Lane 4).
- Decorative intro heading: remove or demote.
- AI subtlety → new Purpose sub-lane (see below).

---

## Second-layer cleanup — Delivered (verified against shipped code)
Build note: `lane-5-second-layer.build.md`. Structure + sizing only; every capability preserved; `npx vite build` passes.

| Item | Status | Evidence |
|---|---|---|
| A.1 One-line block ≠ 80px box | ✅ | `.editor-content-wrapper { min-height: 1.7em }` (`PostDetailPage.css:1065`), height now content-driven |
| A.2 Gutter controls identifiable | ✅ | `.block-drag-handle/.block-menu-btn` resting chip: `--surface-2` bg + visible `--line` border + `--ink-muted` icon (`css:906`) |
| A.3 Remove decorative intro | ✅ | `.edit-shell-intro` "Writing studio / Shape the story quietly…" deleted from JSX + CSS |
| A.4 Delete `MultiBlockEditor.jsx` | ✅ | file absent (removed prior build; re-confirmed) |
| A.5 Collapse to one column | ✅ | `.edit-layout` grid → flex column (`css:548`); `.edit-main-column`/`.edit-side-column` wrappers removed; Tags now a quiet block at the end of the single column |
| B.6 Clear `activeBlockId` on delete | ✅ | `deleteBlock` falls back to prev/next block (`PostDetailPage.jsx:311–321`) |
| B.7 Ready caret on empty edit | ✅ | `startEditing({ seed })` seeds one focused empty paragraph when story empty (`:413`); draft-from-image path passes `seed:false` to avoid a stray block |
| B.8 Surface `origin` as `data-origin` | ✅ | edit: `RichTextBlock.jsx:79`; view: `PostDetailPage.jsx:865`. Hook only — no styling |
| B.9 No duplicate headings | ✅ | intro removed; "Story blocks" kept as the single quiet caption label; "Tags" labels its own section |
| B.11 Block id collision | ✅ | `block_${Date.now()}_${blockSeq.current++}` monotonic counter (`:283`), single source via `makeBlock` |

## Second-layer — Gaps / deferred / flagged
- **B.10 (flagged, not fixed — belongs to Lane 4):** `.story-empty` buttons ("Write the story" / "Draft from image") duplicate the insert flow. Left in place; Lane 4 owns the empty-state / one-tags-home decision.
- **Tags placement still DEFERRED to Lane 4:** tags are parked as a single-column block at the end of the editor (not a second column). Lane 4 decides the final shared home; the tags card-within-card is untouched.
- **AI composer left as-is on purpose (Coordinate caveat):** the insert menu's "Compose with Sutradhar" / "Draft from image" were NOT restyled — the inline slash-command work (`purpose-inline-ai.design.md`) will replace them (`/draft`). Deep AI sidebar untouched.
- **Note:** `data-origin` is exposed but deliberately unstyled — the Surface pass (or range-level origin mark, per inline-AI direction) will visualize human vs AI later.
- **Cosmetic:** tags-card inner JSX is now over-indented (left from unwrapping the side column); renders identically, left for a future formatting sweep.
