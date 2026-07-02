# Alexia carousel sweep — "Save all" design

**Date:** 2026-07-02 · **Status:** awaiting approval

## Problem

Instagram carousel posts (one post, multiple photos) force a manual loop today: horizontally
swipe to each slide, hover it, Save, swipe again. Alexia should extract every photo in the
carousel in one action, with no manual horizontal scrolling.

## Decisions (clarified with Adarsh)

- Scope: **carousel posts** (feed, `/p/` pages, modal overlays) — not DM sweeping.
- Flow: **review grid first** (same as the video Split → Save flow), then save selected.
- Video slides inside a carousel: **skip** (they remain individually splittable via hover).
- Approach: **A — programmatic paging** (recommended; user was AFK at final confirm).

## Approach chosen: programmatic paging

Instagram virtualizes carousels — only the current slide ±1 exist in the DOM. Two ways to
reach the hidden slides:

- **A. Programmatic paging (chosen)** — click IG's own Next chevron, collect rendered
  images at each step. Pure DOM automation, consistent with the rest of the extension,
  zero account risk. Cost: the carousel visibly flips for ~1–2s (position restored after).
- **B. Internal GraphQL/`?__a=1` API** — instant and full-res, but undocumented, rate-
  limited, churns often, and is the classic account-challenge trigger. Rejected.
- **C. Hybrid B→A** — most code, inherits B's fragility. Rejected.

## Design

### 1. Trigger & UI

- New hover-toolbar button **"Save all"** (`sweepBtn`), image mode only, shown only when
  the hovered image is inside a carousel.
- Carousel detection `carouselFor(img)`: hovered `<img>` → closest slide `<li>` → its
  `<ul>` track → carousel root. Confirmed by a Next chevron: `button[aria-label="Next"]`
  first, geometric fallback second (small button vertically centered on the root's right
  edge — aria-labels are locale-dependent).

### 2. Sweep loop (`sweepCarousel`)

1. Collect currently rendered slide images.
2. While a Next button exists and steps < 24 (IG max is 20 slides): click Next, poll
   (~100ms, up to 1s) for a new image URL to render, collect again.
3. Stop early if two consecutive steps yield nothing new.
4. Restore position: click Prev back the number of steps taken.

Collection rules:
- Only `<img>` inside slide `<li>`s, passing the existing `isValidImage` size gate.
- Skip images in any `<li>` that contains a `<video>` (video slides).
- Take the largest `srcset` candidate per image (fall back to `currentSrc`).
- Dedupe into an insertion-ordered Map keyed by URL filename (current ±1 slides
  reappear across steps).

### 3. Review & save

- Generalize `renderFrameReview(frames)` → `renderPickGrid(items, {title, hint, tags})`;
  reuse for both video frames and carousel sweeps (grid `<img>` accepts data URLs and
  CDN URLs alike).
- Save path unchanged: `saveFrames` → `POST /api/v1/posts/upload-from-url` per image,
  `general_tags: ['carousel']`, plus `instagramContextForSave()` extras so saves carry
  `instagram_handle` / `source_account` and feed Darpan.
- **No backend changes** — the endpoint already sends host-aware Referers for IG CDN
  and stores the handle fields.

### 4. Error handling

- No carousel → button simply never shows.
- Zero images collected → `✗ No images` button state.
- Per-image save failures tolerated (existing `saveFrames` keeps going, reports count).

### 5. Files

- `chrome-extension/content.js` — detection, sweep, button wiring, generalized grid.
- `chrome-extension/content.css` — `sweepBtn` style (reuse `.sharirasutra-btn` states).

### 6. Testing (manual)

Feed carousel · `/p/` page carousel · modal-overlay carousel · mixed photo+video
carousel · 10+ slide carousel · single-image post (button must NOT appear) · verify
position restored after sweep · reload unpacked extension + hard-refresh IG tab.
