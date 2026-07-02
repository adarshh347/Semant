# Element-Anchored Instagram Handle Detection — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Alexia resolves the correct Instagram author(s) for a saved image from the hovered media element itself — working in the home feed, stories, reels, post modals, and collab posts (all authors attach and feed all their personas).

**Architecture:** The extension gains `handlesForElement(el)` — a 4-stage resolution chain (container-header walk → proximity scan → stories URL → existing page-level fallbacks) returning an ordered handle list. The backend gains `instagram_handles: List[str]` alongside the existing singular `instagram_handle` (= first of list, full back-compat); upload touches every author's persona, correlation matches on both fields, and local-context/region rollups feed every author.

**Tech Stack:** Vanilla JS content script (no build step), FastAPI + Motor + Pydantic, pytest for backend unit tests (new dev dep).

**Design doc:** `docs/plans/2026-07-02-instagram-handle-detection-design.md`

**Context notes for a fresh engineer:**
- Backend runs locally: `PYTHONPATH="$PWD" ./venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 5007 --reload` from repo root. Requires a filled `.env`.
- The extension is loaded unpacked at `chrome://extensions`; after editing `content.js`, hit its refresh icon AND hard-refresh the Instagram tab.
- `chrome-extension/content.js` is one big IIFE — there is no JS test harness and we are NOT adding one; extension tasks are verified manually per the matrix in Task 7.
- There are currently no backend tests either; Task 1 bootstraps pytest.

---

### Task 1: Backend `normalize_handles` helper (TDD, bootstraps pytest)

**Files:**
- Modify: `backend/services/persona_service.py` (near `normalize_handle`, line ~31)
- Create: `backend/tests/__init__.py` (empty), `backend/tests/test_persona_handles.py`

**Step 1: Install pytest into the venv**

Run: `./venv/bin/pip install pytest`

**Step 2: Write the failing test**

`backend/tests/test_persona_handles.py`:
```python
from backend.services.persona_service import normalize_handles


def test_normalizes_and_dedupes_preserving_order():
    assert normalize_handles(["@UserB", "usera", "userb ", ""]) == ["userb", "usera"]


def test_empty_and_none_input():
    assert normalize_handles([]) == []
    assert normalize_handles(None) == []


def test_single_handle():
    assert normalize_handles(["@Some.User"]) == ["some.user"]
```

**Step 3: Run test to verify it fails**

Run: `PYTHONPATH="$PWD" ./venv/bin/pytest backend/tests/test_persona_handles.py -v`
Expected: FAIL — `ImportError: cannot import name 'normalize_handles'`

Note: importing `persona_service` imports `config.py`, which reads `.env` — the repo `.env` is filled, so this works locally.

**Step 4: Write minimal implementation**

In `backend/services/persona_service.py`, directly below `normalize_handle`:
```python
def normalize_handles(raw_list) -> list:
    """Normalize a list of handles, dropping empties and duplicates, keeping order.
    First element is the primary author (collab posts carry several)."""
    out = []
    for raw in raw_list or []:
        h = normalize_handle(raw or "")
        if h and h not in out:
            out.append(h)
    return out
```

**Step 5: Run test to verify it passes**

Run: `PYTHONPATH="$PWD" ./venv/bin/pytest backend/tests/test_persona_handles.py -v`
Expected: 3 PASS

**Step 6: Commit**

```bash
git add backend/tests/ backend/services/persona_service.py
git commit -m "feat(backend): normalize_handles helper + pytest bootstrap"
```

---

### Task 2: Backend schema — `instagram_handles` field

**Files:**
- Modify: `backend/schemas/post.py:42-45` (Post) and `:99-104` (UrlUploadRequest)
- Modify: `backend/routers/posts.py:77-78` (post_helper)

**Step 1: Add the field to both models**

In `Post` (after `instagram_handle`, line 42):
```python
    instagram_handles: Optional[List[str]] = None  # ALL authors (collab posts); first = primary
```

In `UrlUploadRequest` (after `instagram_handle`, line 103):
```python
    instagram_handles: Optional[List[str]] = None  # all authors on a collab post
```

**Step 2: Expose it in `post_helper`** (`backend/routers/posts.py`, next to line 77):
```python
        "instagram_handles": post.get("instagram_handles"),
```

**Step 3: Verify the app still boots**

Run: `PYTHONPATH="$PWD" ./venv/bin/python -c "from backend.main import app; print('ok')"`
Expected: `ok`

**Step 4: Commit**

```bash
git add backend/schemas/post.py backend/routers/posts.py
git commit -m "feat(backend): instagram_handles (multi-author) on Post + UrlUploadRequest"
```

---

### Task 3: Upload stores all handles and touches every author's persona

**Files:**
- Modify: `backend/routers/posts.py:206-233` (upload-from-url handler)
- Modify: `backend/routers/posts.py:15` (import)

**Step 1: Extend the import** (line 15):
```python
from backend.services.persona_service import persona_service, normalize_handle, normalize_handles, handle_from_source_url
```

**Step 2: Replace the handle block** (lines 206-208) with:
```python
    # Normalize the Instagram handle(s) the extension supplied. Collab posts carry
    # several authors; the first is primary and also fills the legacy singular field.
    handles = normalize_handles(
        (request.instagram_handles or [])
        + ([request.instagram_handle] if request.instagram_handle else [])
    )
    handle = handles[0] if handles else None
```

**Step 3: Store both fields** — in `post_document` (lines 220-221), after `"instagram_handle": handle,` add:
```python
            "instagram_handles": handles or None,
```

**Step 4: Touch every author** — replace the `if handle:` persona-touch block (lines 229-233) with:
```python
        for i, h in enumerate(handles):
            try:
                # Account snapshot only describes the page's main author → primary only.
                await persona_service.touch(h, request.source_account if i == 0 else None)
            except Exception as e:
                print(f"Persona touch failed for @{h} (non-fatal): {e}")
```

**Step 5: Verify against the running backend**

Run (backend must be up):
```bash
curl -s -X POST http://127.0.0.1:5007/api/v1/posts/upload-from-url \
  -H 'Content-Type: application/json' \
  -d '{"image_url":"https://picsum.photos/seed/collab/400","source_url":"https://www.instagram.com/p/TEST/","instagram_handles":["@CollabA","collabb"],"general_tags":["plan-test"]}' \
  | python3 -m json.tool | grep -A4 instagram
```
Expected: `"instagram_handle": "collaba"` and `"instagram_handles": ["collaba", "collabb"]`.

Then: `curl -s http://127.0.0.1:5007/api/v1/personas/ | python3 -m json.tool | grep handle`
Expected: both `collaba` and `collabb` stub personas exist.

**Step 6: Commit**

```bash
git add backend/routers/posts.py
git commit -m "feat(backend): upload-from-url stores instagram_handles, touches every author persona"
```

---

### Task 4: Correlation matches the multi-handle field

**Files:**
- Modify: `backend/services/persona_service.py:73-81` (`_matched_posts`)

**Step 1: Add the array match to the `$or`** (line 78):
```python
            {"$or": [{"instagram_handle": handle},
                     {"instagram_handles": handle},
                     {"source_url": {"$regex": rx}}]},
```
(Mongo array-field equality matches any element — no `$in` needed.)

**Step 2: Verify** — with the Task 3 test post in the DB:
```bash
curl -s http://127.0.0.1:5007/api/v1/personas/collabb/images | python3 -m json.tool | head -20
```
Expected: the picsum test image appears for **collabb** (the secondary author) too.

**Step 3: Commit**

```bash
git add backend/services/persona_service.py
git commit -m "feat(backend): persona correlation matches instagram_handles array"
```

---

### Task 5: Rollups feed every author (local-context + region correspondence)

**Files:**
- Modify: `backend/routers/posts.py` — add helper near `post_helper`; use it at lines ~375 (local-context) and in the region-annotations endpoint (~415)

**Step 1: Add a helper** (below `post_helper` in `backend/routers/posts.py`):
```python
def post_handles(post: dict) -> list:
    """All author handles on a post: multi-author field first, then legacy
    singular, then whatever the source_url encodes. Ordered, deduped."""
    return normalize_handles(
        (post.get("instagram_handles") or [])
        + [post.get("instagram_handle") or "",
           handle_from_source_url(post.get("source_url")) or ""]
    )
```

**Step 2: local-context rollup** — replace lines 375-388:
```python
    handles = post_handles(post)
    fed = False
    if handles and request.feed_to_persona and (local_context["commentary"] or request.aletheia):
        for h in handles:
            try:
                await persona_service.add_local_context(
                    handle=h,
                    post_id=post_id,
                    image_url=post.get("photo_url"),
                    commentary=local_context["commentary"],
                    aletheia=request.aletheia,
                )
                fed = True
            except Exception as e:
                print(f"Persona local-context roll-up failed for @{h} (non-fatal): {e}")
```
And the return (line 391): `"handle": handles[0] if handles else None`.

**Step 3: Region-correspondence rollup** — find the `add_region_correspondence` call in the region-annotations endpoint (~line 415); apply the same pattern: compute `handles = post_handles(post)`, loop the persona call over `handles`, keep response shape (`handle` = primary).

**Step 4: `/context` endpoint** (line 342) — use the helper for the primary:
```python
    handles = post_handles(post)
    handle = handles[0] if handles else None
```
And add `"instagram_handles": handles,` to the returned dict.

**Step 5: Verify boot + tests**

Run: `PYTHONPATH="$PWD" ./venv/bin/pytest backend/tests/ -v && PYTHONPATH="$PWD" ./venv/bin/python -c "from backend.main import app; print('ok')"`
Expected: tests PASS, `ok`.

**Step 6: Commit**

```bash
git add backend/routers/posts.py
git commit -m "feat(backend): local-context + region rollups feed every collab author"
```

---

### Task 6: Extension — `handlesForElement` resolution chain

**Files:**
- Modify: `chrome-extension/content.js` — Darpan section (functions around lines 596-683)

**Step 1: Add the stories parser** (next to `instagramProfileHandle`):
```javascript
    function instagramStoryHandle() {
        // Stories URL is /stories/<handle>/<story-id>/
        const m = location.pathname.match(/^\/stories\/([^\/]+)/);
        if (!m) return null;
        const seg = decodeURIComponent(m[1]).toLowerCase();
        return RESERVED_IG.has(seg) ? null : seg;
    }
```

**Step 2: Add link-parsing + the two element-anchored stages** (below `instagramPostAuthorHandle`):
```javascript
    // "/handle/" (single non-reserved segment) → handle, else null.
    function profileHrefHandle(a) {
        const m = (a.getAttribute('href') || '').match(/^\/([^\/?#]+)\/?$/);
        if (!m) return null;
        const seg = decodeURIComponent(m[1]).toLowerCase();
        return RESERVED_IG.has(seg) ? null : seg;
    }

    // Stage 1 — structure: the post container's header names its author(s).
    // Feed posts are <article>s; opened posts render inside role="dialog".
    // Collab posts put every author link in the header ("userA and userB").
    function handlesFromContainer(el) {
        const container = el.closest('article') || el.closest('div[role="dialog"]');
        if (!container) return [];
        const out = [];
        container.querySelectorAll('header a[href^="/"]').forEach(a => {
            const h = profileHrefHandle(a);
            const r = a.getBoundingClientRect();
            if (h && r.width > 0 && r.height > 0 && !out.includes(h)) out.push(h);
        });
        return out;
    }

    // Stage 2 — geometry: reels overlays have no <header>; the author link sits
    // on/near the video. Walk up from the media element; at each ancestor take
    // visible profile links whose rect intersects the (slightly expanded) media
    // rect. Accept the first ancestor yielding 1..10 — more means we've reached
    // a feed-level root and would pick up unrelated posts.
    function handlesNearElement(el) {
        const r = el.getBoundingClientRect();
        const pad = 48;
        const box = { l: r.left - pad, t: r.top - pad, r: r.right + pad, b: r.bottom + pad };
        let node = el.parentElement;
        for (let depth = 0; node && depth < 12; depth++, node = node.parentElement) {
            const out = [];
            node.querySelectorAll('a[href^="/"]').forEach(a => {
                const h = profileHrefHandle(a);
                if (!h || out.includes(h)) return;
                const ar = a.getBoundingClientRect();
                if (ar.width === 0 || ar.height === 0) return;
                if (ar.right < box.l || ar.left > box.r || ar.bottom < box.t || ar.top > box.b) return;
                out.push(h);
            });
            if (out.length >= 1 && out.length <= 10) return out;
            if (out.length > 10) return [];   // too broad — bail to later stages
        }
        return [];
    }

    // The full chain: element-anchored first, then page-level fallbacks.
    // Returns an ordered list; first entry is the primary author.
    function handlesForElement(el) {
        if (!isInstagram()) return [];
        if (el) {
            const fromContainer = handlesFromContainer(el);
            if (fromContainer.length) return fromContainer;
            const near = handlesNearElement(el);
            if (near.length) return near;
        }
        const story = instagramStoryHandle();
        if (story) return [story];
        const author = instagramPostAuthorHandle();
        if (author) return [author];
        const profile = instagramProfileHandle();
        return profile ? [profile] : [];
    }
```

**Step 3: Rewire `instagramContextForSave`** — replace the existing function (lines 669-677):
```javascript
    // Extra fields to attach to a save so the image carries its account context.
    // Anchored to the saved media element — the page may show many authors' posts.
    function instagramContextForSave(mediaEl) {
        if (!isInstagram()) return {};
        const handles = handlesForElement(mediaEl || null);
        if (!handles.length) return {};
        const extras = { instagram_handle: handles[0], instagram_handles: handles };
        const snap = accountSnapshot();
        if (snap) extras.source_account = snap;
        return extras;
    }
```
(`accountSnapshot()` already self-guards — returns null off profile pages. `detectedHandle()` stays as-is: the persona FAB is genuinely page-level.)

**Step 4: Syntax check**

Run: `node --check chrome-extension/content.js`
Expected: no output (clean parse).

**Step 5: Commit**

```bash
git add chrome-extension/content.js
git commit -m "feat(extension): element-anchored multi-author handle detection (feed/stories/reels/collab)"
```

---

### Task 7: Extension — call sites + the stale-frame-context fix

**Files:**
- Modify: `chrome-extension/content.js:255` (saveImage), `:441-` (splitVideo), `:512` (renderFrameReview), `:565-575` (saveFrames)

**Step 1: `saveImage` passes the hovered image** (line 255):
```javascript
                body: JSON.stringify({ image_url: imageUrl, source_url: location.href, general_tags: [], ...instagramContextForSave(currentImage) })
```

**Step 2: Capture context at split time.** In `splitVideo()` (line 441), right after `const video = currentVideo;` + its null-guard, add:
```javascript
        // Capture author context NOW — the user reviews frames after scrolling,
        // by which time currentVideo/page context may point at a different post.
        const igContext = instagramContextForSave(video);
        const sourceUrl = location.href;
```
Find where `splitVideo` calls `renderFrameReview(frames)` and change it to `renderFrameReview(frames, igContext, sourceUrl)`.

**Step 3: Thread through the review grid** (line 512):
```javascript
    function renderFrameReview(frames, igContext, sourceUrl) {
```
and its save handler (line 558):
```javascript
            saveFrames(items.filter(i => i.selected).map(i => i.url), save, igContext, sourceUrl);
```

**Step 4: `saveFrames` uses the captured context** (lines 565-575):
```javascript
    async function saveFrames(urls, btn, igContext, sourceUrl) {
```
and in its fetch body:
```javascript
                    body: JSON.stringify({ image_url: urls[i], source_url: sourceUrl || location.href, general_tags: ['video-frame'], ...(igContext || {}) })
```

**Step 5: Syntax check**

Run: `node --check chrome-extension/content.js`
Expected: clean.

**Step 6: Commit**

```bash
git add chrome-extension/content.js
git commit -m "fix(extension): save frames with author context captured at split time"
```

---

### Task 8: End-to-end manual verification matrix

Reload the unpacked extension at `chrome://extensions` (refresh icon) and hard-refresh Instagram. Backend running locally. After each save, check the newest post:

```bash
curl -s "http://127.0.0.1:5007/api/v1/posts/?page=1" | python3 -c "
import sys, json
p = json.load(sys.stdin)['posts'][0]
print(p.get('instagram_handle'), p.get('instagram_handles'), p.get('source_url', '')[:60])"
```

| # | Surface | Action | Expected handles |
|---|---------|--------|------------------|
| 1 | Home feed `/` | Save an image from post A, then from the next post B | A's author, then B's author — different |
| 2 | Collab post | Save its image | BOTH authors, header order |
| 3 | Story `/stories/x/…` | Save the story image | `x` |
| 4 | Reels `/reels/` | Save (split) a reel | reel's author |
| 5 | Post modal (click from profile grid) | Save | that post's author |
| 6 | Profile page | Save a grid image | profile handle |
| 7 | Video stale-context | Split on post A → scroll to post B → save frames | still A's author |
| 8 | Non-Instagram site | Save any image | no handle fields |

Then confirm collab feeding: `curl -s http://127.0.0.1:5007/api/v1/personas/ | python3 -m json.tool | grep -B1 matched` — both collab authors show a nonzero `matched_image_count`.

**Cleanup:** delete the Task 3 test post (`DELETE /api/v1/posts/{id}`) and drop the `collaba`/`collabb` stub personas from Mongo if you don't want them lingering.

**Final commit** (if any doc/plan tweaks accumulated):
```bash
git add -A && git commit -m "docs: verification notes for element-anchored handle detection"
```
