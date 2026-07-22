# Source Groups — preserving the relationship between images

## The motive
Images on social platforms are rarely isolated. A **reel** is a *sequence* of frames; a **carousel** is a *set* of slides; a **post** ties images to an account. Today the extension's "Split → Save" turns a reel into orphan Posts — no memory of which frames are siblings, no order. Preserve that relationship (group + sequence) so the app and the taste intelligence can reason about images **in context, not in isolation.**

## Why it matters (serves the bigger purpose)
- **Context = meaning.** A frame read in sequence means something a lone frame can't; a reel is a narrative. The "how the culture feels" layer needs the thread, not orphan stills.
- **Dedup.** Adjacent reel frames are near-identical; ungrouped, they flood the gallery and pollute the taste graph. Grouping lets us cluster/collapse them.
- **Taste proximity.** *Which* frame of a reel someone lingered on is a sharp signal — only meaningful if frames know their neighbours (Track F).
- **Navigation.** Show a reel as an ordered strip; group siblings in the gallery instead of scattering them.

## Data model (Post) — add `source_group`
- `group_id` — shared uuid across all siblings from one reel/carousel/post.
- `group_type` — `reel | carousel | video | post | single`.
- `sequence_index` — position within the group (frame order / slide order); null for single.
- `sequence_total` — optional, total in the group if known.
- `t_ms` — optional, video-frame timestamp (a *richer* proximity axis than index — two frames 200ms apart are near-duplicates).
Reuse existing `source_url` / `instagram_handles` / `source_account` (they already tie to account + post).

## Extension (`chrome-extension/content.js`)
- **At split time:** generate ONE `group_id` for the reel session, set `group_type="reel"`, and assign each captured frame an incrementing `sequence_index` (+ `t_ms` from the video's currentTime) in order. Send all three on every `upload-from-url`.
- **Carousel (Phase 2):** detect the multi-image post → one `group_id`, `group_type="carousel"`, slide index.
- **Single save:** `group_type="single"`, no group.

## Backend (`UrlUploadRequest` + `upload-from-url` + Post schema)
- Accept + persist the `source_group` fields.
- **Siblings endpoint:** `GET /posts/{id}/siblings` (or `/posts/group/{group_id}`) → the ordered group (by `sequence_index` / `t_ms`).

## Proximity (what the relationship unlocks)
Adjacent (`index ±1` or small `t_ms` delta) = most related. Enables near-duplicate collapse, taste proximity signal, "related images" that are actually related, and sequence navigation.

## Phasing
1. **Core (backend + extension):** schema fields + extension stamps `group_id`/`sequence_index`/`t_ms` at split + backend stores them + the siblings endpoint. This is the "memory" Adarsh asked for.
2. **Carousel grouping** (multi-image posts).
3. **UI + intelligence:** sibling strip on a post, gallery grouping, and proximity feeding dedup + the taste graph.

## Coordination
Backend + extension + schema — **does NOT touch `PostDetailPage.jsx`.** Fits `feat/vision-pipeline` (relates to Track A data model + Track B/F video/reels). No frontend-thread collision until the Phase 3 UI, which is small and separately serialized.

## Naming
`source_group` in code (plain). Could be themed later as a "thread" connecting images, consistent with the Sūtra vocabulary.
