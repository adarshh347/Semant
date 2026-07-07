# Lane 4 — Content view: one framed story column

Labels: architecture, drishya
Full spec: `architecture-lab/lane-4-content-view.build.md` · Research: `architecture-lab/responses/lane-4-content-view.findings.md`

## Goal
Give the Content pane one framed story column — meta-head (identity) → story (empty/editing/reading) → meta-foot (tags) — so metadata stops scattering and moving between containers. Structure only.

## Checklist
- [x] Gate `.source-account-section` + `.epic-badge-section` behind `tab==='content'` (stop rendering on other tabs/modes).
- [x] Persona/@handle lives in the meta-head only (Lane 1 must not duplicate it in the topbar).
- [x] Demote Epic to a chip in the meta-head row (no `<h5>` band).
- [x] One `<TagStrip mode>` at the meta-foot inside `.content-area`; delete the old `.tags-section` (outside) and `.tags-edit-section` (in edit-layout).
- [x] Edit-mode TagStrip sticky/collapsible (reachable while writing).
- [x] Wrap empty/editing/reading in one `.story-column`; empty = zero-block reading (no jump on transition).
- [x] Highlights: `jumpToBlock` (switch to Story + scrollIntoView + flash); graceful degradation on null/missing block_id.
- [x] Remove the persistent `.underline-hint`; keep the selection tooltip.

## Do-no-harm
Tag add/remove/popular, highlight save/remove, StoryFlow, "Open persona", Draft-from-image, all still work.

## Delivered (commit `3978353`, verified by screenshot)
| Item | How | Verified |
|---|---|---|
| Identity gated to Story tab | source + epic moved inside `tab==='content'` gate, wrapped in `.story-column` | `.meta-head` absent on Highlights & Unconceal (asserted false + shots 02/03) |
| @handle here only | topbar carries no handle (unchanged); meta-head renders it | shot 01/05 meta-head; topbar clean |
| Epic → chip | `.epic-chip` inline in meta-head row, no `<h5>` band; `.epic-badge-section` CSS removed | code path + CSS (no post has an epic to render; PATCH rejects the field) |
| One TagStrip, both modes | new `TagStrip.jsx`; both old homes deleted | shots 01/07 (view chip), 05 (edit card) |
| Sticky + collapsible edit tags | `position:sticky; bottom:0` + collapse toggle | shots 05 (open) / 06 (collapsed `TAGS 1 >`) |
| One framed column | empty/editing/reading share meta-head → story → meta-foot | shots 01 (read) / 05 (edit) / 07 (empty) — same frame |
| Highlights jump + flash | `jumpToBlock` → Story tab + `scrollIntoView` + `.block-flash` | shot 04 (jumped, block A flashed); 2/3 cards jumpable |
| Graceful degradation | card clickable only when `block_id` resolves to a live block | orphan card (bad block_id) rendered non-clickable, no error |
| Underline hint removed | `.underline-hint` markup + CSS deleted; selection tooltip retained | shots 01/07 (no strip); `handleTextSelection` untouched |

**Not screenshot-exercised:** the epic chip — no post in the DB has an associated epic and the post PATCH endpoint rejects `associated_epics` (managed via epicService). Verified by code path + CSS only.

## Verify
By screenshot, per each checklist item. Run AFTER Phase 2 slash (#15) — same files.
Note: slash #15 was still uncommitted when this ran, so its state/handlers are fused into `PostDetailPage.jsx/.css`; the pure-slash files were committed separately as `f8d8bf9 (#15)`.
