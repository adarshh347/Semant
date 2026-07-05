# Frontend Design Audit

## P0 Finish-Up Pass

Source of truth: `frontend/my prompts/visual_component_audit.md`

This pass implemented only the P0 issues called out in the audit.

### Fixed P0 items

- [x] Flatten container stack inside the Content panel.
- [x] Strengthen edit-mode hierarchy so the Content editor is the dominant surface.
- [x] Reduce visual weight of the left Visual panel during editing without hiding it.
- [x] Compact and soften top chrome during editing.
- [x] Slim the source/persona row.
- [x] Make Story Blocks metadata compact and quiet.
- [x] Convert Add Block into a lighter inline toolbar.
- [x] Recast Compose with Sutradhar as a subtle assistant tray.
- [x] Make Tags clearly secondary.
- [x] Integrate Save/Cancel into the editor surface.
- [x] Reduce terracotta overuse on utility actions and secondary UI.

### Files changed

- `frontend/src/components/PostDetailPage.jsx`
- `frontend/src/components/PostDetailPage.css`

### Visual effect of the pass

- The Content side now reads more like one writing surface and less like stacked cards.
- Edit mode is calmer: the page chrome compresses, the writing area widens, and the image pane steps back slightly.
- Utility controls are quieter, with terracotta concentrated on active and primary states instead of scattered across the page.
- Add Block, Compose, and Tags now behave like supporting tools rather than full-weight feature modules.
- Save/Cancel sits closer to the editor language and no longer feels pasted over the bottom edge.

### Explicitly not addressed in this pass

- P1/P2 audit items such as broader empty-state redesigns, richer tab behavior changes, or deeper interaction restructuring.
