# Lane 1 — top chrome build

**To:** Claude Code. **Mode:** build, structure only (no colour/surface polish). Preserve every capability. Verify by **screenshot**. Commit per `workflow-protocol.md`. Source: `responses/lane-1-top-chrome.findings.md` + the 5 locked answers in `decisions-log.md`.

**Run AFTER the Compose-card removal** (both touch `PostDetailPage.jsx`) — see note at bottom.

## Build
1. **Navbar collapse on `/posts/*`.** Collapse the 9 nav links into one disclosure menu (☰▾) using the existing `app-layout--fullscreen` hook (`App.jsx:13`) — CSS-reachable, no new plumbing. Slim rail keeps: logo (compact), ThemeToggle, and the menu; **fold the Upload CTA into that menu**. All 9 links + Upload stay reachable.
2. **Kill the duplicate ThemeToggle.** Keep the navbar copy (`NavBar.jsx:28`); delete the topbar copy (`PostDetailPage.jsx` topbar).
3. **Sutradhar brand** → fold to a small quiet label at the topbar's left (by the back-link). Remove the dedicated center slot.
4. **Trio buttons:**
   - **AI Assistant** → keep, but de-weight from primary to a quiet secondary button.
   - **Edit** → remove the standalone button; add a **pencil affordance on the Content panel header** that enters edit mode.
   - **Delete** → move into a topbar **"⋯" overflow menu** (reuse the overflow pattern from `RichTextBlock.jsx`). Rare + destructive shouldn't be front-of-house.
5. **Back-link** "← Gallery" stays at the topbar left.

## Constraints
- Structure/chrome only. No colour/typography polish (flag surface items for later).
- Every capability reachable after: theme, all 9 links, Upload, leave, AI, edit, delete.
- The navbar change reaches into `NavBar.jsx` + `App.css`; the topbar + pencil + overflow are in `PostDetailPage.jsx/.css`.

## Verify on screen
Navbar is a slim rail with a working links menu on a post page; no duplicate theme toggle; Sutradhar is a small left label; topbar shows back-link + AI (secondary) + "⋯" (with Delete); Edit is gone but a pencil on the Content header enters edit mode. Commit per protocol referencing the Lane 1 issue; update it; push the PR.

## Coordination
Touches `PostDetailPage.jsx` (topbar) — the same file as the Compose-card removal and the editor thread. Do the Compose removal first, then this. `git pull` before starting; don't run alongside another session editing `PostDetailPage.jsx`.
