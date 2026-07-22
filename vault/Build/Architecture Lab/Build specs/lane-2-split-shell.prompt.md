# Lane 2 — The split shell: container, divider, panel headers, pane relationship

**To:** Claude Code (local, in this repo)
**Mode:** deep read + architecture proposal. **Do not edit any app code.** Write findings only.

## Why this lane exists
The Visual and Content panes sit side by side but behave as two unrelated tools. We need to decide the *skeleton*: how the split is structured, how the divider behaves, what belongs in each panel header, and whether the two panes should actually be connected.

## Files to read
- `frontend/src/components/PostDetailPage.jsx` lines ~527–590 — `.post-detail-split`, `.post-detail-left`, `.split-divider`, `.post-detail-right`, and the two `.panel-header` blocks (h3 + `.panel-tabs`).
- Divider logic: lines ~195–232 (drag handlers, `leftPanelWidth`, 20–80% clamp).
- `frontend/src/components/PostDetailPage.css` — `.post-detail-split`, `.post-detail-left/right`, `.split-divider`, `.panel-header`, `.panel-tabs`, `.panel-tab`.

## Questions to answer (architecture only)
1. **Header pattern.** Both panes use `panel-header` = an `<h3>` title ("Visual" / "Content") + a tab group. Is the text title carrying information the tabs don't already imply? Propose the optimal header structure (title? no title? tabs only? where do panel-level actions attach?).
2. **Do the panes complement each other?** Today selecting a bounding box on the left does nothing on the right, and the right's Unconceal→Anatomy names image parts independently. List every place where the two panes reference the same underlying data (image regions, tags, highlights) but are wired separately. Propose whether/how they should link — e.g. selecting a region focuses related content — at a *structural* level (shared state, lifted props), not visuals.
3. **Divider behaviour.** It only drag-resizes. Should there be collapse/expand presets (e.g. collapse Visual while writing)? Is `leftPanelWidth` the right single source of truth? Note the `isEditing` state already nudges widths — reconcile.
4. **Touch vs gap.** How do the two panes meet — shared divider line, or two boxes with a gap? Recommend one, structurally.
5. **Scroll ownership.** Which element scrolls (`.content-area` vs pane vs page)? Confirm each pane scrolls independently and the headers stay put; flag anything that fights this.

## Hard constraints
- Structure only. No colour/font/spacing.
- Keep resize working; keep all three Content tabs and both Visual tabs functional.
- No app code — a plan.

## Output contract → write to `responses/lane-2-split-shell.findings.md`
- **Current shell tree** — the split, panes, headers, divider, with file+line refs.
- **Pane-relationship map** — shared data between panes and how it's currently wired (separately).
- **Proposed shell** — leanest header + divider + linkage structure, as a short tree.
- **Linkage options** — 1–3 concrete structural ways to make the panes complement each other, with effort/ risk notes.
- **Questions for Adarsh.**
