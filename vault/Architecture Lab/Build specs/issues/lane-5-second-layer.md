# Lane 5 — second-layer cleanup

Relates to #13. Labels: architecture, lane-5, drishya
Full spec: `architecture-lab/lane-5-second-layer.build.md`

## Goal
Fix what the first Lane 5 pass exposed, plus bugs found on review. Structure + sizing only — no colour/typography polish. Preserve every capability.

## Checklist
### From Adarsh's review
- [ ] Block height content-driven (drop `min-height: 80px`, `PostDetailPage.css:1101`) — one line looks like one line.
- [ ] Gutter grip + "⋯" made identifiable (not faint mystery boxes).
- [ ] Remove decorative intro "Writing studio / Shape the story quietly…".
- [ ] Delete dead `MultiBlockEditor.jsx` (keep the `.text-block-item[data-block-id]` selector).
- [ ] Collapse `.edit-side-column` → one column (tags placement coordinates with Lane 4).

### Found on deeper review
- [ ] Clear `activeBlockId` when its block is deleted (else insertion silently appends).
- [ ] Seed a focused empty block on entering edit / empty story (no dead end).
- [ ] Pass `origin` through to a `data-origin="human|sutradhar"` DOM hook (no styling).
- [ ] Demote the second "Story blocks" heading (avoid two stacked headings).
- [ ] Replace `block_${Date.now()}` id with a collision-safe id.
- [ ] Flag (don't fix) empty-state buttons duplicating the insert flow → Lane 4.

## Coordinate
Do NOT restyle the insert-menu "Compose with Sutradhar" — it is superseded by the slash-command work (see the inline-AI issue).

## Exit check
One-line block looks like one line · empty edit gives a ready caret · gutter controls identifiable · no `MultiBlockEditor.jsx` · one column · `data-origin` present · deleting the active block doesn't break insertion · no duplicate headings · all capabilities intact. Update `issues/lane-5.md` + `workflow-log.md`.
