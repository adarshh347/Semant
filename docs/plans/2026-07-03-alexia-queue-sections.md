# Alexia Queue Sections + Premium Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild the split-queue view as three live sections (Splitting / Ready to save / Saving) so jobs never vanish or replace each other, and give all Alexia surfaces a premium-minimal polish.

**Architecture:** Replace per-frame grid-append sync (`syncQueueJob`) with a section model: capturing jobs are compact progress ROWS (no grids), settled jobs become BLOCKS with the tap-to-deselect grid (built once), saving jobs move to upload-progress rows that flash ✓ and clear. Live events insert/move/remove nodes surgically via a module `qView` handle; sections auto-hide when empty. CSS gets a restrained Editorial-palette polish (kickers with hairline rules, status dots, thin terracotta bars, frosted pulsing chip, row fade-ins).

**Tech Stack:** Vanilla JS Chrome MV3 content script — `chrome-extension/content.js` + `content.css`. No backend.

**Design doc:** `docs/plans/2026-07-03-alexia-queue-sections-design.md`
**Base:** `feat/alexia-carousel-sweep` at `5932da9`.
**Testing:** `node --check` + manual (no harness; live-IG behavior) — checklist in Task 3.

---

### Task 1: content.js — section model rewrite

**Remove:** `statusLabel`, `queueFrameCell` (renamed), `syncQueueJob`, old `renderQueueView`, old `updateQueueBar` internals, old `massSaveQueue` body, the `syncQueueJob` calls in `captureFrames`/`queueSplit`.

**Job fields added:** `_row {row,fill,count,im}`, `_block`, `uploadDone`, `uploadTotal`, `uploadOk`, `_preSaveState`. State machine gains `'saving'`.

**New pieces (complete code):**

- `jobTitle(job)` → `Video #N · @handle`.
- `qSection(title)` → `{sec,list}` with `.al-qsec-kicker`.
- Module `let qView = null;` — `{splitting, ready, saving, hint}`; all live handlers guard with `.isConnected`.
- `buildJobRow(job, kind)` (kind `'split'`|`'save'`): 40px thumb (first frame, live-filled), title, thin bar+fill, count, ✕ only for split-kind (cancel: `job.cancelled=true`, delete, remove row, refresh chip/sections/bar). Sets `job._row`.
- `updateSplitProgress(job)` / `updateUploadProgress(job)`: update `_row` count text (`12/38` / `uploading 12/38`), fill width, thumb once available.
- `buildReadyBlock(job)`: head (title, status dot+text via `readyStatusText`, ✕ delete) + grid of `frameCell(job, idx)` (the old queueFrameCell, renamed); `dataset.jobId`; sets `job._block`.
- `insertReadyBlock(job)`: ordered insert by job id into `qView.ready.list`.
- `jobSettled(job)` (called from queueSplit's `.finally` instead of `syncQueueJob`): refresh chip; if row connected & job still queued → remove row, `insertReadyBlock`, update sections/bar.
- `updateQueueSections()`: toggle `.al-hidden` per empty list; hint shown only when no jobs at all.
- `renderQueueView()`: header, body = three sections + hint, distribute jobs by state (capturing→row, saving→save-row, else→block), footer bar w/ `queueSaveBtn` (massSaving → disabled 'Saving…'), `updateQueueSections()`, `openPanel()`.
- `updateQueueBar()`: counts settled-only selected frames (skips capturing AND saving), same labels as before.
- `queueSplit`: after `splitQueue.set` — if `qView` live, append `buildJobRow(job,'split')` + update sections/bar.
- `captureFrames`: per-frame hook becomes `refreshQueueChip(); updateSplitProgress(job);`.
- `massSaveQueue(btn)` rewrite: guard `massSaving`; `settled` = not capturing/saving; `participating` = settled with `uploadTotal>0` (failed 0-frame jobs stay in Ready); snapshot `_preSaveState`, set `'saving'`, remove blocks, append save-rows; upload loop updates per-job `uploadDone/uploadOk` + row; finish → button label, rows flash `✓ N` (`.al-q-done`); delete participating from queue when `saved>0`; timeout(1200): clear rows, restore un-deleted jobs to `_preSaveState` + re-insert Ready blocks (failure path), reset `massSaving`/button, update sections/bar.
- `refreshQueueChip()`: text `N splitting · M frames` / `N ready · M frames` (no emoji), `classList.toggle('splitting', capturing>0)`.

### Task 2: content.css — queue styles + premium polish

Replace `.al-queue-*` block with:
- `.al-hidden { display:none !important; }`
- `.al-qsec` (margin), `.al-qsec-kicker` — 10px/700/uppercase/letter-spacing .14em, `#A53F2A`, flex + `::after` hairline (`#EDE8DE`).
- `.al-q-row` — flex, 10px gap, 8px 0 padding, fade-in animation; `.al-q-thumb` 40×40 radius 10 bg `#EDE8DE` (img cover); `.al-q-mid` flex-col; `.al-q-title` 12.5px/600 ink; `.al-q-bar` h4 radius bg `#EDE8DE` + `.al-q-bar-fill` terracotta gradient, width transition .3s; `.al-q-count` 11px tabular muted; `.al-q-x` quiet ✕ (hover red).
- `.al-q-block` (fade-in, margin), `.al-q-head` flex, `.al-q-status` dot+text — `.al-q-dot` 6px circle: captured `#1f8a5b`, partial `#b8860b`, failed `#b8403c`; text 11.5px muted.
- `.al-q-done` row tint (`.al-q-count` → green ✓).
- `@keyframes al-fade-in` (opacity+3px rise, .25s).
- Chip: frosted — `rgba(20,18,14,0.82)` + `backdrop-filter: blur(10px)`, padding 10px 15px, 12.5px; `.ss-queue-chip.splitting::before` — 7px terracotta dot, `al-chip-pulse` 1.4s infinite.
- Grid-cell polish (shared with pick-grid): consistent 10px radius, subtle hover raise, smaller tick badge.

### Task 3: verify + review + handoff

`node --check`; commit; code-review subagent over the diff (spec = design doc; check live-insert paths, saving-state restore on failed save, `_row`/`_block` staleness, massSaving interactions, CSS class consistency JS↔CSS); fix Important+; manual checklist: queue #2 while panel open (row appears), #1 completes while open (moves to Ready, grid intact), Save all mid-splitting (Saving section, ✓ flash, clear; splitting row untouched), failed-save restore, cancel row, failed video dot+reason, chip pulse, overall look.
