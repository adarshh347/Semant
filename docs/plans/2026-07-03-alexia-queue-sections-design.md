# Alexia queue sections + premium polish (design)

**Date:** 2026-07-03 · **Status:** approved (flash-✓-then-clear chosen by Adarsh)

## Problem

Two splits completed and the queue view appeared to swap the old job's frame grid for the
new one ("old was not recovered"). Root cause: jobs queued or finishing **while the panel
is open** are never added to the open view — `syncQueueJob` only touches jobs that had
`_grid`/`_status` refs from the last full render. Structural confusion, plus the user
wants a distinctly *premium, minimal* visual pass on all Alexia surfaces.

## Design

### Sections (each renders only when non-empty; empty queue → hint line)

1. **Splitting** — compact rows, NO grids: 40px first-frame thumb (live-updates), title
   `Video #N · @handle`, thin progress bar + `12/38`, ✕ cancel. Rows are inserted the
   moment a job is queued, update in place, and MOVE to Ready on completion.
2. **Ready to save** — per-job block: header (thumb, title, status dot + text:
   `38 frames` / `partial · 21/38` / failure reason) + tap-to-deselect frame grid.
   Grids exist only here → they can never be replaced mid-choose.
3. **Saving** — during mass save, participating jobs move here as rows with
   `uploading 12/38` progress; on completion each flashes `✓ Saved N` briefly, then
   clears from the panel (no history section — the gallery is the record).

Footer: single `Save all (N frames)` button (N = selected in Ready). Reentrancy
guards (`massSaving`, `capturingVideos`, `job.cancelled`) unchanged.

### Live-update model (replaces per-frame `syncQueueJob` grid appends)

- Job state machine: `capturing → captured | partial | failed → saving → (cleared)`.
- Surgical DOM helpers: `buildSplittingRow(job)`, `buildReadyBlock(job)`,
  `buildSavingRow(job)`; `renderQueueView()` composes sections from `splitQueue`;
  live events insert/move/remove nodes and toggle section visibility:
  - `queueSplit` → append row to Splitting (if view open).
  - capture progress → update that row's bar/count/thumb only (no grid work).
  - capture done → remove row, insert Ready block (ordered by job id).
  - mass save start → move settled blocks to Saving rows; per-upload progress on rows;
    done → flash ✓, remove, update chip/bar.
- Grids are built once per job (on entering Ready) — append-only logic deleted.

### Premium-minimal polish (content.css, Editorial palette only)

Quieter uppercase kickers with hairline rules for section headers; status = small dot
(+ muted text) instead of loud colored words; thin terracotta progress bars (existing
`al-bar` recipe); refined grid cells (consistent radius, subtle hover, smaller tick);
chip → frosted dark pill (backdrop-blur, like `.ss-persona-open`) with a gentle pulse
while splitting; consistent paddings/sizes; small fade-in on inserted rows. Slightly
smaller type where oversized. No new colors, no decorative noise.

### Files

`chrome-extension/content.js` (queue view rewrite, ~self-contained) +
`chrome-extension/content.css` (queue styles rewrite + polish touches). No backend.

### Testing (manual)

Queue #1, open panel, queue #2 while open → #2 row appears instantly; #1 completes →
moves to Ready with grid intact while #2 still splitting; Save all mid-splitting →
settled jobs move to Saving with progress, flash ✓, clear; #2 completes after → lands
in Ready; cancel a splitting row; failed video shows dot + reason; chip pulses while
splitting; visual pass looks calm/premium in the IG dark feed context.
