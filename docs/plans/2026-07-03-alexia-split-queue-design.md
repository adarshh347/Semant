# Alexia split queue — background video splits + mass save (design)

**Date:** 2026-07-03 · **Status:** awaiting approval

## Problem

Split → Save is blocking: while a video is being seeked/captured (often 10–30s) the user
must stay put, and switching tabs/windows stalls the capture entirely (the per-frame wait
uses `requestAnimationFrame`, which does not fire in hidden tabs). The user wants to:
queue a split, keep scrolling, queue more videos, and mass-save everything at the end.
**Scope: videos only** — image/carousel flows unchanged.

## Decisions

- Flow: **accumulate + one mass save** (review grid at the end, consistent with the
  carousel sweep's review-first choice; user was AFK — chosen to match "both mass save").
- Capture starts **immediately** on queue (fire-and-forget), jobs run in parallel.
- Partial results are kept: if Instagram destroys the video element mid-capture
  (scrolled very far), the job finalizes as `partial` with the frames it got.

## Approaches considered

- **A. Immediate background capture per queued video (chosen).** Capture on the live
  element starting at click time (element guaranteed alive), asynchronously. Hidden-tab
  stall fixed by replacing the rAF wait with `seeked` + timeout (background timers are
  ~1s-throttled but run). Context snapshotted at queue time.
- **B. `captureStream` + MediaRecorder → split blob offline.** Element-independent after
  recording, but real-time only (60s reel = 60s). Rejected.
- **C. Scrape internal JSON for MP4 URLs, split detached.** Fragile, account-risk,
  most reels are MSE blobs. Rejected.

## Design

### 1. Job model + queueing

```js
// splitQueue: Map<jobId, job>
job = {
  id, video,                 // live element ref (may die)
  state,                     // 'capturing' | 'captured' | 'partial' | 'failed'
  frames: [],                // dataURLs, grows during capture
  total,                     // planned frame count
  context,                   // {source_url, instagram_handle?, source_account?} snapshotted AT QUEUE TIME
  error,                     // for 'failed'
}
```

- Split button click → `queueSplit(currentVideo)`: dedupe (same element already queued →
  no-op), create job, start `captureFrames(job)` (not awaited), button shows `✓ Queued`.
- The old blocking flow is subsumed: one queued video = queue of one; review happens in
  the queue panel instead of auto-opening.

### 2. Capture core (refactor of splitVideo)

- Extract the seek/draw loop into `async captureFrames(job)`:
  - pause/mute, seek N evenly spaced timestamps (existing N = clamp(round(duration*3), 8..60)),
    draw to a per-job canvas, push dataURL, update job progress.
  - **Hidden-tab-safe wait**: after `video.currentTime = t`, await `seeked` event with a
    timeout fallback (existing `seekVideo` already does this) and replace the extra
    `requestAnimationFrame` tick with a short `setTimeout` — timers run (throttled) in
    hidden tabs; rAF does not.
  - **Element death**: before each seek, check `video.isConnected`; two consecutive seek
    timeouts or a disconnected element → finalize as `partial` with collected frames.
  - Tainted canvas (cross-origin) → `failed` with message; other jobs unaffected.
  - Restore paused/muted/currentTime at the end only if still connected.
- Jobs capture in parallel (each owns its canvas; elements are independent).

### 3. Queue chip + panel view

- Floating chip (new element, above the Darpan FAB): visible whenever the queue is
  non-empty, e.g. `⏳ 2 splitting · 84 frames` → click opens the panel's queue view.
- Queue view in the existing panel: per-job section — first-frame thumbnail, status
  line (`capturing 12/38`, `captured · 38`, `partial · 21`, `failed`), discard (✕);
  below it the familiar pick-grid of that job's frames (all selected, tap to deselect).
  Live-updates while captures run (re-render on job progress if the panel is open).
- Footer: **`Save all (N frames)`** — N = selected across all jobs. Sequential POSTs via
  the existing `saveFrames` core, but per-job context: each frame saves with
  `general_tags: ['video-frame']` + its job's snapshotted `source_url`/handle fields
  (requires threading a context override through `saveFrames` — today it reads
  `location.href` + live DOM at save time, which would be wrong after scrolling).
- Saved jobs are removed from the queue; chip disappears when the queue empties.

### 4. Error handling

- Failed/partial jobs stay visible in the panel with their state; partial frames savable.
- Mass-save failures per frame tolerated (existing keep-going pattern, count reported).
- Queue is in-memory per page — a hard navigation/refresh clears it (acceptable; noted
  in the panel? no — YAGNI).

### 5. Files

- `chrome-extension/content.js` — job model, captureFrames refactor, chip, queue view,
  saveFrames context threading.
- `chrome-extension/content.css` — chip + queue-view styles (reuse panel/grid styles).
- No backend changes.

### 6. Testing (manual)

Queue 1 reel → scroll on → chip counts up → grid → Save all (frames land tagged
`video-frame` with the reel's handle). Queue 3 videos rapidly → parallel capture, three
sections. Switch tab mid-capture → returns captured (slower, not stalled). Scroll far
mid-capture → job partial, frames kept. Tainted/protected video → failed, others fine.
Handle context correctness: queue from reel A, scroll to reel B, save — frames carry A's
handle. Single-image + carousel flows regression-check (untouched).
