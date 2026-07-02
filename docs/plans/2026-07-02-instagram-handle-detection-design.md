# Element-anchored Instagram handle detection (Alexia → Darpan)

**Date**: 2026-07-02
**Status**: Approved

## Problem

`instagramContextForSave()` in `chrome-extension/content.js` is page-level — it resolves the
account handle from "what page am I on" (profile URL, or geometric post-author detection on
`/p/…` pages). This breaks on:

- **Home feed** (`/`): every scrolled post is a different author, page-level returns nothing —
  feed saves lose their account context entirely.
- **Stories** (`/stories/<handle>/…`): handle is in the URL but never parsed.
- **Reels vertical scroller** (`/reels/`): nothing.
- **Collab posts** (multiple authors): only one handle can attach; all authors should.
- **Stale-context bug**: video frames save *after* a review step; the user may have scrolled to
  a different post by then, so even correct page-level context would be stale.

## Decision

Detection becomes **media-element-anchored**: resolve the author from the hovered `<img>`/`<video>`
element, not from the page. Multiple authors (collabs) all attach and all feed persona synthesis.

## Extension design (`content.js`)

New `handlesForElement(el)` returns an ordered list of handles (first = primary), via a
resolution chain — each stage degrades to the next:

1. **Container walk (structure)**: `el.closest('article')` (feed posts) or
   `el.closest('div[role="dialog"]')` (post modal). Inside the container, collect all distinct
   non-reserved `/handle/` links from its `header`. Collab posts render "userA and userB" as two
   header links, so all authors are captured naturally.
2. **Proximity scan (geometry)** — for reels overlays and header-less containers: walk ancestors
   from the media element; at each level collect *visible* profile-pattern links whose rect
   intersects the media element's rect (slightly expanded); accept the first ancestor yielding
   1–10 candidates. The cap rejects overly-broad ancestors (the feed root would match dozens).
3. **Stories URL**: `location.pathname.match(/^\/stories\/([^\/]+)/)`.
4. **Existing fallbacks**: `instagramPostAuthorHandle()` (geometric band, post pages), then
   `instagramProfileHandle()` (profile page — all media belongs to that account).

`instagramContextForSave(el)` gains the element parameter and returns
`{instagram_handle: <primary>, instagram_handles: [<all>], source_account?}`.

Call-site changes:
- `saveImage()` passes `currentImage`.
- `splitVideo()` captures the context **at split time** (while the video is still the hovered
  element) and threads it through the review grid to `saveFrames()` — fixes the stale-context bug.

A save with zero resolved handles still succeeds (handle-less, as today). No dependence on
Instagram class names — only `article`/`header`/`role="dialog"` semantics plus geometry.

## Backend design

- `Post` + `UrlUploadRequest` (`backend/schemas/post.py`) gain
  `instagram_handles: Optional[List[str]]`. `instagram_handle` (singular) remains and is set to
  the first of the list — full back-compat for Darpan correlation, Unconceal, `/context`.
- `/upload-from-url` (`backend/routers/posts.py`): normalize every handle, store both fields,
  `persona_service.touch()` **every** author (each gets/updates a stub persona);
  `source_account` snapshot attaches to the primary only.
- `persona_service._matched_posts` adds `{"instagram_handles": handle}` to its `$or` — a collab
  image surfaces in *every* author's persona gallery and feeds every author's synthesis.
- Local-context rollup (`add_local_context` / region correspondence): rolls up to **all** handles
  on the post, per the collab decision.

## Alternatives rejected

- **Page-level patches only** (stories URL + keep single handle): cheap but doesn't fix the feed,
  which is the core requirement.
- **Pure geometric proximity** (no DOM structure): resilient to markup churn but noisy —
  tagged-people and comment-author links pollute results. Used as inner fallback only.

## Testing

- Unit-testable pieces: handle regex/reserved filtering, backend normalization + `$or` matching.
- Manual verification matrix (extension): profile page, home feed (two adjacent posts → distinct
  handles), collab post (both handles), story, reel scroller, post modal, non-Instagram site
  (no extras). Video: split on one post, scroll, then save frames → original post's handles.
- Backend verification: upload with `instagram_handles=[a,b]` → both personas touched, image
  appears in both `_matched_posts`.
