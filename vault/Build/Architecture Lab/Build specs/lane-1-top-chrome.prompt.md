# Lane 1 — Top chrome: navbar, Sutradhar strip, trio buttons, persona line

**To:** Claude Code (local, in this repo)
**Mode:** deep read + architecture proposal. **Do not edit any app code.** Write findings only.

## Why this lane exists
Everything above the split workspace is heavier than it needs to be. There are two full-width bars, a duplicated theme toggle, three always-on action buttons, and a persona line that eats a full row. We want the *optimal* chrome: the least structure that still exposes every action.

## Files to read (trace them fully, don't skim)
- `frontend/src/App.jsx` — note that `<Navbar />` and `<main><Outlet/></main>` are **siblings**.
- `frontend/src/components/NavBar.jsx` + `Navbar.css` — the global bar (logo + 9 links + theme + Upload).
- `frontend/src/components/PostDetailPage.jsx` lines ~490–525 — the `.post-detail-topbar` (back link, `.sutradhar-brand`, `.post-detail-actions` with Unsaved pill, ThemeToggle, AI Assistant, Edit, Delete).
- `frontend/src/components/PostDetailPage.css` — rules for `.post-detail-topbar`, `.post-detail-topbar.compact`, `.sutradhar-brand`, `.post-detail-actions`, `.action-btn`.
- `border-layout-plan.md` — the sibling-navbar constraint is already documented; confirm it still holds.

## Questions to answer (architecture only)
1. **Two bars → one?** Map exactly what each bar provides. On a `/posts/*` fullscreen route, which of the nine global links are actually reachable/needed? Propose whether the global navbar should (a) collapse to a slim rail, (b) hide behind a menu, or (c) merge into the post topbar — and what code change each needs, given the sibling constraint (route-aware render in `App.jsx`? a prop? a layout variant?).
2. **Duplicate controls.** ThemeToggle renders in both bars. List every control that appears twice and say which copy should survive.
3. **Trio buttons (AI Assistant / Edit / Delete).** For each: is it a primary, secondary, or rare/destructive action? Propose where each should live so the horizontal strip stops being crowded — candidates: an overflow "…" menu, a per-panel affordance (e.g. Edit as a pencil on the Content header), keeping only one primary. Is a standalone Edit button needed at all, or can the Content pane be made directly editable?
4. **Persona line.** `.source-account-section` ("From @handle · Open persona") currently sits as a full-width band inside the content area. Could this identity live in the Content panel header (chrome) as a compact avatar+handle instead of its own row? What breaks if it moves?
5. **Sutradhar brand.** Is the centered brand name structural or decorative? Can it fold into the topbar without a dedicated center slot?

## Hard constraints
- Architecture and component placement only. **No colour/font/spacing choices.**
- Do not delete any capability — every action must still be reachable after your proposal.
- Do not write app code. Produce a plan.

## Output contract → write to `responses/lane-1-top-chrome.findings.md`
Use these sections:
- **Current chrome inventory** — every bar, every control, with file+line refs, and mark duplicates.
- **Proposed structure** — the leanest arrangement, as a short component tree.
- **Per-control decision table** — control | keep/move/merge/remove | new home | reason.
- **Code-change surface** — which files/functions must change for each move (especially the navbar sibling issue), described, not written.
- **Questions for Adarsh** — anything that needs a human decision before building.
