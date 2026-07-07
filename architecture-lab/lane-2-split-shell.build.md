# Lane 2 — split shell build (Structure + Behaviour; region model DEFERRED)

**To:** Claude Code. **Mode:** build, structure/behaviour only (no colour/surface polish). Preserve every capability. Verify by **screenshot + keyboard test**. Commit per `workflow-protocol.md`. Source: `responses/lane-2-split-shell.findings.md` + the 5 locked answers in `decisions-log.md`.

## Build (shell only)
1. **Header cleanup** — drop `<h3>Visual</h3>` / `<h3>Content</h3>`. Each `.panel-header` becomes: tabs on the left, a right-aligned actions slot (keep the Content pencil-edit + any pane actions there).
2. **Edit narrows the Visual pane** — on `isEditing`, set `leftPanelWidth` to a smaller preset (~30) via the single source of truth, with a smooth width transition; restore the prior width on exit. Remove the opacity-dim approach. It stays draggable back.
3. **Divider presets** — add a **collapse toggle** (Visual → thin rail) and **double-click-to-reset** to the 45% default, in addition to drag. Keep the 20–80% clamp.
4. **Accessibility (harden the hand-rolled divider to the ARIA APG window-splitter)** — `role="separator"`, `tabindex="0"`, `aria-orientation="vertical"`, `aria-valuenow/valuemin/valuemax` tracking `leftPanelWidth`, and **Arrow-key resize** (Left/Right nudge, Home/End or Enter to collapse/reset). No `allotment` dependency.

## DO NOT (deferred to Darshan Track A)
- Do **not** merge or modify `bounding_box_tags` / `region_annotations`.
- Do **not** build cross-pane selection linking (box-select → content, anatomy-part → image). That waits on the unified region model (Track A). Leave `BoundingBoxEditor.jsx` and `RegionDetectorModal.jsx` untouched.

## Verify
Headers show tabs + actions, no h3; entering edit smoothly narrows Visual and restores on exit; divider drags, collapses, double-click-resets; the separator is keyboard-focusable and Arrow keys resize it. Commit per protocol referencing the Lane 2 issue; update it; push the PR.

## Coordination
Touches `PostDetailPage.jsx` + `.css`. `git pull` first; don't run alongside another session editing `PostDetailPage.jsx` (Darshan/editor threads).
