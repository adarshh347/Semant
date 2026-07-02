# Alexia Carousel Sweep ("Save all") Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** One click on a carousel post collects every photo slide (paging through Instagram's own Next chevron), shows the existing review grid, and saves the kept ones.

**Architecture:** Pure DOM automation inside the existing content script. Instagram virtualizes carousels (only current slide ±1 in DOM), so we click the Next button, poll for newly rendered `<img>`s, dedupe into an ordered Map, page back to restore position, then reuse the video-frames review grid + save loop. No backend changes.

**Tech Stack:** Vanilla JS Chrome extension (MV3 content script) — `chrome-extension/content.js` + `content.css`. No build step, no test harness.

**Design doc:** `docs/plans/2026-07-02-alexia-carousel-sweep-design.md`

**Testing note (TDD deviation):** The extension is a plain content script with no JS test infrastructure in this repo, and its behavior depends on live Instagram DOM. Building a jsdom harness for one feature is YAGNI. Verification is therefore manual per task: reload the unpacked extension at `chrome://extensions` (circular refresh icon on the card), hard-refresh the Instagram tab, and check behavior + DevTools console. The final task is a full manual test checklist.

---

### Task 1: Sweep button + carousel detection

**Files:**
- Modify: `chrome-extension/content.js` (button block ~line 38–50; helpers after `videoCoversImage` ~line 165; `setToolbarMode` ~line 167; `showTarget` ~line 174)

**Step 1: Add the button element**

After the `splitBtn` creation block (ends ~line 45), add:

```js
    // Carousel → all photos button (Alexia), shown only when hovering a carousel image
    const sweepBtn = document.createElement('button');
    sweepBtn.className = 'sharirasutra-btn sharirasutra-sweep-btn';
    sweepBtn.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="3" width="13" height="13" rx="2"></rect>
        <path d="M19 8v11a2 2 0 0 1-2 2H8"></path>
      </svg><span>Save all</span>`;
```

And append it with the others (after `toolbar.appendChild(splitBtn);`):

```js
    toolbar.appendChild(sweepBtn);
```

**Step 2: Add detection helpers**

After `videoCoversImage` (ends ~line 165), add:

```js
    // ---- Carousel detection ------------------------------------------------------
    // Instagram carousels are <ul> tracks of <li> slides with chevron <button>s in an
    // ancestor wrapper. Only the current slide ±1 are in the DOM at any moment.
    function nextButtonIn(wrapper, track) {
        return pagerButtonIn(wrapper, track, 'next');
    }
    function prevButtonIn(wrapper, track) {
        return pagerButtonIn(wrapper, track, 'prev');
    }
    function pagerButtonIn(wrapper, track, dir) {
        // aria-label first (English UI), geometric fallback second (locale-proof).
        const labels = dir === 'next' ? ['Next'] : ['Go back', 'Previous'];
        for (const l of labels) {
            const b = wrapper.querySelector(`button[aria-label="${l}"]`);
            if (b) return b;
        }
        const tr = track.getBoundingClientRect();
        const edge = dir === 'next' ? tr.right : tr.left;
        for (const b of wrapper.querySelectorAll('button')) {
            if (toolbar.contains(b) || panel.contains(b)) continue;
            const r = b.getBoundingClientRect();
            if (r.width === 0 || r.height === 0 || r.width > 80 || r.height > 80) continue;
            const cy = r.top + r.height / 2;
            if (Math.abs(cy - (tr.top + tr.height / 2)) > tr.height * 0.2) continue;  // not vertically centered
            if (Math.abs((r.left + r.width / 2) - edge) > 80) continue;               // not hugging that edge
            return b;
        }
        return null;
    }

    // The hovered <img> → its carousel {track, wrapper}, or null if not a carousel.
    function findCarousel(img) {
        const li = img.closest('li');
        const track = li && li.closest('ul');
        if (!track) return null;
        let node = track.parentElement;
        for (let depth = 0; node && depth < 5; depth++, node = node.parentElement) {
            if (nextButtonIn(node, track) || prevButtonIn(node, track)) return { track, wrapper: node };
        }
        return null;
    }
```

(`prevButtonIn` matters in `findCarousel`: on the *last* slide only "Go back" exists.)

**Step 3: Wire visibility**

In `setToolbarMode` (~line 167) hide the sweep button in video mode by adding one line:

```js
        sweepBtn.style.display = 'none';
```

so the function reads:

```js
    function setToolbarMode(type) {
        const isVideo = type === 'video';
        brainstormBtn.style.display = isVideo ? 'none' : '';
        saveBtn.style.display = isVideo ? 'none' : '';
        splitBtn.style.display = isVideo ? '' : 'none';
        sweepBtn.style.display = 'none';
    }
```

In `showTarget` (~line 174), inside the `if (type === 'image')` branch, after the save-button reset lines, add:

```js
            sweepBtn.classList.remove('success', 'error', 'saving');
            sweepBtn.querySelector('span').textContent = 'Save all';
            sweepBtn.style.display = findCarousel(el) ? '' : 'none';
```

Note: `setToolbarMode` runs before this (both called from `showTarget`), so the order-of-operations keeps single images sweep-free.

**Step 4: Verify manually**

Reload the extension, hard-refresh instagram.com. Hover a **carousel** photo (post with the dots indicator): toolbar shows Brainstorm · Save · **Save all**. Hover a **single-image** post: no "Save all". Hover a reel: only "Split → Save". (Button is unstyled until Task 4 — that's fine.)

**Step 5: Commit**

```bash
git add chrome-extension/content.js
git commit -m "feat(extension): carousel detection + Save all button (no-op yet)"
```

---

### Task 2: Slide collection helpers

**Files:**
- Modify: `chrome-extension/content.js` (immediately after the Task 1 helpers)

**Step 1: Add collectors**

```js
    // ---- Carousel slide collection -----------------------------------------------
    // Largest srcset candidate, else currentSrc/src.
    function bestImageUrl(img) {
        let best = null, bestW = 0;
        (img.srcset || '').split(',').forEach(part => {
            const m = part.trim().match(/^(\S+)\s+(\d+)w$/);
            if (m && +m[2] > bestW) { bestW = +m[2]; best = m[1]; }
        });
        return best || img.currentSrc || img.src || '';
    }

    // Dedupe key: same photo renders under different size params across steps,
    // but the CDN filename is stable.
    function slideUrlKey(u) {
        try { return new URL(u, location.href).pathname.split('/').pop() || u; } catch (e) { return u; }
    }

    // Pull every photo currently rendered in the track into `found` (ordered Map).
    // Returns how many NEW photos were added. Skips video slides.
    function collectSlides(track, found) {
        let added = 0;
        track.querySelectorAll('li').forEach(li => {
            if (li.querySelector('video')) return;               // video slide → skip
            li.querySelectorAll('img').forEach(im => {
                if (!isValidImage(im)) return;
                const url = bestImageUrl(im);
                if (!url || url.startsWith('data:')) return;
                const key = slideUrlKey(url);
                if (!found.has(key)) { found.set(key, url); added++; }
            });
        });
        return added;
    }

    // After clicking Next, the new slide's <img> lands asynchronously — poll for it.
    function waitForNewSlides(track, found) {
        return new Promise((resolve) => {
            const t0 = performance.now();
            (function poll() {
                const added = collectSlides(track, found);
                if (added || performance.now() - t0 > 1000) return resolve(added);
                setTimeout(poll, 100);
            })();
        });
    }
```

**Step 2: Verify manually**

Reload extension + refresh IG. In DevTools console on a carousel post, run a smoke check through the page (content-script functions aren't reachable from the page console, so verify indirectly): confirm no console errors on load and the banner line still prints. Deeper behavior is exercised in Task 4.

**Step 3: Commit**

```bash
git add chrome-extension/content.js
git commit -m "feat(extension): carousel slide collectors (srcset-max, dedupe, poll)"
```

---

### Task 3: Generalize the review grid + tagged saves

**Files:**
- Modify: `chrome-extension/content.js` — `renderFrameReview` (~line 512) and `saveFrames` (~line 565)

**Step 1: Generalize `renderFrameReview` → `renderPickGrid`**

Replace the `renderFrameReview` function signature/head and the hint/save lines. The body stays otherwise identical:

```js
    // Review grid: all items selected by default; tap to deselect; then save kept ones.
    // Used by both the video-frame flow and the carousel sweep.
    function renderPickGrid(urls, opts) {
        const { title, hint, tags } = opts;
        const items = urls.map(url => ({ url, selected: true }));
        clearPanel();
        panel.appendChild(frameHeader(title));

        const body = el('div', 'al-body al-frames-body');
        body.appendChild(el('div', 'al-frames-hint', hint));
```

…(grid construction unchanged)… and the save handler passes tags through:

```js
        save.addEventListener('click', (e) => {
            e.preventDefault(); e.stopPropagation();
            saveFrames(items.filter(i => i.selected).map(i => i.url), save, tags);
        });
```

Then make the old call site in `splitVideo` (~line 491) use it:

```js
        if (frames.length) {
            renderPickGrid(frames, {
                title: 'Choose frames',
                hint: `${frames.length} frames · tap to deselect`,
                tags: ['video-frame'],
            });
        } else {
```

Delete the now-unused `renderFrameReview` name (this IS the rename — no duplicate function left behind).

**Step 2: Thread tags through `saveFrames`**

```js
    async function saveFrames(urls, btn, tags) {
```

and in its POST body replace `general_tags: ['video-frame']` with:

```js
                    body: JSON.stringify({ image_url: urls[i], source_url: location.href, general_tags: tags || [], ...instagramContextForSave() })
```

**Step 3: Verify manually (regression)**

Reload extension + refresh IG. Run **Split → Save** on a reel: grid renders with "N frames · tap to deselect", saving works, saved posts carry the `video-frame` tag (check the gallery at :5173 or Mongo). This proves the refactor didn't break the existing flow.

**Step 4: Commit**

```bash
git add chrome-extension/content.js
git commit -m "refactor(extension): renderFrameReview → renderPickGrid with title/hint/tags"
```

---

### Task 4: The sweep loop + CSS

**Files:**
- Modify: `chrome-extension/content.js` (after `saveFrames`; button wiring ~line 584)
- Modify: `chrome-extension/content.css` (after `.sharirasutra-split-btn`, ~line 47)

**Step 1: Add `sweepCarousel`**

```js
    // ---- Alexia: sweep a carousel post — collect every photo slide ---------------
    async function sweepCarousel() {
        const img = currentImage;
        if (!img) return;
        const car = findCarousel(img);
        if (!car) {
            sweepBtn.classList.add('error');
            sweepBtn.querySelector('span').textContent = '✗ Not a carousel';
            return;
        }
        sweepBtn.classList.remove('success', 'error');
        sweepBtn.classList.add('saving');

        const found = new Map();
        collectSlides(car.track, found);

        // Page forward, collecting as slides render. IG max is 20 slides; cap at 24.
        // Re-query the chevron each step — React re-renders replace the node, and on
        // the last slide it disappears. Two dry steps in a row = end (safety).
        const MAX_STEPS = 24;
        let steps = 0, dry = 0;
        while (steps < MAX_STEPS && dry < 2) {
            const next = nextButtonIn(car.wrapper, car.track);
            if (!next) break;
            next.click();
            steps++;
            sweepBtn.querySelector('span').textContent = `Reading ${found.size}…`;
            const added = await waitForNewSlides(car.track, found);
            dry = added ? 0 : dry + 1;
        }

        // Page back so the user's position is restored.
        for (let i = 0; i < steps; i++) {
            const prev = prevButtonIn(car.wrapper, car.track);
            if (!prev) break;
            prev.click();
            await new Promise(r => setTimeout(r, 60));
        }

        sweepBtn.classList.remove('saving');
        const urls = [...found.values()];
        if (urls.length) {
            sweepBtn.querySelector('span').textContent = 'Save all';
            renderPickGrid(urls, {
                title: 'Choose photos',
                hint: `${urls.length} photo${urls.length > 1 ? 's' : ''} · tap to deselect`,
                tags: ['carousel'],
            });
        } else {
            sweepBtn.classList.add('error');
            sweepBtn.querySelector('span').textContent = '✗ No images';
        }
    }
```

**Step 2: Wire the click** (next to the other three, ~line 584):

```js
    sweepBtn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); sweepCarousel(); });
```

**Step 3: Style the button** — in `content.css` after `.sharirasutra-split-btn` (~line 47):

```css
.sharirasutra-sweep-btn {
    background: linear-gradient(135deg, #2f7d6d 0%, #22665a 100%) !important;
    color: #F3EFE6 !important;
}
```

**Step 4: Verify manually**

Reload extension + refresh IG. On a carousel post: hover → **Save all** (teal) → click. Carousel flips forward then back; panel opens with every photo slide; save 2, confirm they land in the gallery tagged `carousel` with `instagram_handle` set.

**Step 5: Commit**

```bash
git add chrome-extension/content.js chrome-extension/content.css
git commit -m "feat(extension): Alexia carousel sweep — Save all photos in one click"
```

---

### Task 5: Full manual test checklist

Reload the unpacked extension + hard-refresh the IG tab first. Then:

1. **Feed carousel** — hover a photo in a feed carousel: "Save all" appears; sweep collects all slides (count matches the dots), grid order matches slide order, position restored.
2. **`/p/` post page carousel** — same as above on a standalone post page.
3. **Modal-overlay carousel** — open a post from a profile grid (dialog): sweep works, does not leak images from the page behind the dialog (detection is scoped to the track's `<li>`s, but confirm).
4. **Mixed photo+video carousel** — video slides are absent from the grid; photos all present; the video slide can still be Split → Save'd individually.
5. **10+ slide carousel** — all slides collected; no premature stop.
6. **Single-image post** — no "Save all" button.
7. **Reel** — Split → Save regression: grid + save still work, `video-frame` tag intact.
8. **Saves carry context** — a swept save has `general_tags:['carousel']`, `instagram_handle`, `source_url` (check via `GET /api/v1/posts/` or the gallery).
9. **Console** — no errors during any of the above.

Fix anything that fails (use superpowers:systematic-debugging if non-obvious), then update `CONTEXT.md` §12.7 area with a short "Alexia carousel sweep" note and commit:

```bash
git add CONTEXT.md
git commit -m "docs: CONTEXT.md — Alexia carousel sweep note"
```
