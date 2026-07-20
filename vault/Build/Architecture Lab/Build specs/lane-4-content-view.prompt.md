# Lane 4 — Content pane, view mode: source row, empty state, story blocks, tags

**To:** Claude Code (local, in this repo)
**Mode:** deep read + architecture proposal. **Do not edit any app code.** Write findings only.

## Why this lane exists
When you're *reading* a post (not editing), small pieces of metadata are blown up into full sections, and tags live in a different place than they do in edit mode. This lane finds one clean home for each item.

## Files to read
- `frontend/src/components/PostDetailPage.jsx`:
  - `.source-account-section` (~592–606) — avatar + "From @handle" + "Open persona →".
  - `.epic-badge-section` (~608–618).
  - Story view branch: `.underline-hint` (~792–798), `.text-block-item` map (~800–812), `StoryFlow` (~814–823).
  - Empty state `.story-empty` (~770–789) — icon + title + sub + two buttons.
  - `.tags-section` (~952–962) — **view-mode only**, rendered *outside* `.content-area`, at the bottom of the right pane.
- `frontend/src/components/StoryFlow.jsx` — how the flow generator attaches under the story.
- `frontend/src/components/PostDetailPage.css` — `.source-account-section`, `.story-empty`, `.tags-section`, `.text-block-item`, `.underline-hint`.

## Questions to answer (architecture only)
1. **Metadata as sections.** `source-account-section` and `epic-badge-section` are full-width bands for what is essentially a line of identity each. Propose where they belong (panel chrome? a compact meta row? merged?). Note Lane 1 also eyes the persona line — coordinate, don't conflict.
2. **Tags have two homes.** In view mode tags render at the bottom in `.tags-section`; in edit mode they're a card in the side column (Lane 5). This split home is why they feel "out of place." Propose ONE consistent structural home for tags across both modes.
3. **Empty state.** `.story-empty` is a centered hero with two buttons ("Write the story" / "Draft from image") floating in a large empty pane. Ask: should the empty state and the editor be the same surface (so entering is seamless) rather than two separate DOM trees that swap? Propose the structural relationship between empty → editing → reading.
4. **The underline hint.** `.underline-hint` is a persistent instructional strip above the story. Is a permanent strip the right structure, or should the hint be transient/contextual?
5. **View vs edit duplication.** List everything that is rendered twice (once for view, once for edit) with different markup — tags is one; find others. Flag where a single component could serve both modes.

## Hard constraints
- Structure only. No colour/font/spacing.
- Keep highlighting-by-selection, StoryFlow, and tag display all working.
- No app code — a plan.

## Output contract → write to `responses/lane-4-content-view.findings.md`
- **Current view-mode tree** — with file+line refs.
- **One-home-per-item table** — item | current home(s) | proposed single home.
- **View/edit duplication list** — things rendered twice with divergent markup.
- **Empty-state proposal** — how empty, editing, and reading should relate structurally.
- **Questions for Adarsh.**
