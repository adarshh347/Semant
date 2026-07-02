# Alexia Split Queue Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split becomes fire-and-forget — click queues a background capture, the user scrolls on and queues more videos, and a queue panel mass-saves all captured frames at the end.

**Architecture:** In-memory job queue in the content script. Each job captures frames from its live `<video>` immediately and asynchronously (parallel jobs, per-job canvas), with a hidden-tab-safe wait (`seeked` + `setTimeout`, no rAF) and per-job Instagram context snapshotted at queue time. A floating chip shows live progress; the existing panel gains a queue view (per-job sections + the familiar pick-grid) with one "Save all" that reuses a generalized `saveFrames`.

**Tech Stack:** Vanilla JS Chrome MV3 content script — `chrome-extension/content.js` + `content.css`. No build, no backend changes.

**Design doc:** `docs/plans/2026-07-03-alexia-split-queue-design.md`
**Base:** branch `feat/alexia-carousel-sweep` at `dd5d8cc` (content.js clean, md5 `7c0d69b8…`).

**Testing note (TDD deviation):** same as the carousel sweep — no JS harness exists and behavior depends on live Instagram DOM + tab visibility; per-task verification is `node --check` + reload-and-poke, with a full manual checklist at the end.

---

### Task 1: Capture core + job queue (replaces blocking splitVideo)

**Files:** Modify `chrome-extension/content.js` (§ "Alexia: split a video into frames", lines ~550–620; splitBtn wiring ~line 782)

**Step 1: `seekVideo` reports timeouts** — replace its body so it resolves `true` on a real seek, `false` on the 1.5s fallback:

```js
    function seekVideo(video, t) {
        return new Promise((resolve) => {
            let done = false;
            const finish = (ok) => { if (done) return; done = true; video.removeEventListener('seeked', onSeeked); resolve(ok); };
            const onSeeked = () => finish(true);
            video.addEventListener('seeked', onSeeked);
            setTimeout(() => finish(false), 1500); // 'seeked' never fired (streams)
            try { video.currentTime = t; } catch (e) { finish(false); }
        });
    }
```

**Step 2: replace `async function splitVideo() {…}` wholesale** with the queue + capture core:

```js
    // ---- Alexia: split queue — background captures + mass save -------------------
    // A queued job captures from its LIVE element immediately (it's on screen at
    // click time); jobs run in parallel; the user scrolls on. Frames accumulate on
    // the job and are mass-saved from the queue view.
    const splitQueue = new Map();   // jobId -> job
    let nextJobId = 1;

    function queueSplit(video) {
        if (!video) return;
        for (const j of splitQueue.values()) {
            if (j.video === video) {
                splitBtn.classList.add('success');
                splitBtn.querySelector('span').textContent = '✓ Already queued';
                return;
            }
        }
        const duration = video.duration;
        if (!duration || !isFinite(duration) || duration <= 0) {
            splitBtn.classList.add('error');
            splitBtn.querySelector('span').textContent = '✗ No duration';
            return;
        }
        const job = {
            id: nextJobId++,
            video,
            state: 'capturing',            // capturing | captured | partial | failed
            frames: [],                    // dataURLs, grows during capture
            dropped: new Set(),            // frame indexes deselected in the queue view
            total: Math.max(8, Math.min(60, Math.round(duration * 3))),
            // Snapshot NOW — by save time the user has scrolled to a different post.
            context: { source_url: location.href, ...instagramContextForSave() },
            error: null,
        };
        splitQueue.set(job.id, job);
        splitBtn.classList.add('success');
        splitBtn.querySelector('span').textContent = `✓ Queued #${job.id}`;
        captureFrames(job).finally(() => {
            refreshQueueChip();
            if (queueViewOpen) syncQueueJob(job);
        });
        refreshQueueChip();
    }

    async function captureFrames(job) {
        const video = job.video;
        const duration = video.duration;
        const wasPaused = video.paused, prevTime = video.currentTime, wasMuted = video.muted;
        video.muted = true;
        try { video.pause(); } catch (e) {}

        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        let missed = 0;                    // consecutive seek timeouts

        for (let i = 0; i < job.total; i++) {
            if (!video.isConnected) { job.error = 'video left the page'; break; }
            if (missed >= 2) { job.error = 'stream stopped seeking'; break; }
            const ok = await seekVideo(video, duration * ((i + 0.5) / job.total));
            missed = ok ? 0 : missed + 1;
            // rAF never fires in hidden tabs — settle with a timer instead (background
            // throttling makes it ~1s there, which only slows the capture down).
            await new Promise(r => setTimeout(r, 60));
            const vw = video.videoWidth, vh = video.videoHeight;
            if (!vw || !vh) continue;
            canvas.width = vw; canvas.height = vh;
            try {
                ctx.drawImage(video, 0, 0, vw, vh);
                job.frames.push(canvas.toDataURL('image/jpeg', 0.85));
            } catch (err) {
                console.error('Alexia: canvas tainted (cross-origin video, no CORS):', err);
                job.error = 'protected video';
                break;
            }
            refreshQueueChip();
            if (queueViewOpen) syncQueueJob(job);
        }

        job.state = job.error
            ? (job.frames.length ? 'partial' : 'failed')
            : (job.frames.length ? 'captured' : 'failed');
        if (job.state === 'failed' && !job.error) job.error = 'no frames';
        if (video.isConnected) {
            try { video.currentTime = prevTime; } catch (e) {}
            video.muted = wasMuted;
            if (!wasPaused) { try { video.play(); } catch (e) {} }
        }
    }
```

Note: `refreshQueueChip`, `queueViewOpen`, `syncQueueJob` arrive in Tasks 2–3; add temporary no-op stubs in this task so the file stays runnable, and replace them in the later tasks:

```js
    let queueViewOpen = false;
    function refreshQueueChip() {}
    function syncQueueJob(job) {}
```

**Step 3: rewire the button** — `splitVideo()` in the click handler (~line 782) becomes `queueSplit(currentVideo)`.

**Step 4:** `node --check chrome-extension/content.js` → passes. Reload extension, click Split on a reel: button shows `✓ Queued #1`, video visibly scrubs then resumes; `splitQueue` fills (verify via a temporary `console.log` or just proceed — the chip in Task 2 makes it visible).

**Step 5: Commit** — `git add chrome-extension/content.js && git commit -m "feat(extension): split queue core — background captureFrames jobs replace blocking splitVideo"`

---

### Task 2: Queue chip

**Files:** Modify `chrome-extension/content.js` (replace the `refreshQueueChip` stub; chip element next to the panel creation ~line 63) and `chrome-extension/content.css`

**Step 1: chip element** (after `document.body.appendChild(panel);`):

```js
    // Floating split-queue chip (bottom-right) — visible while the queue is non-empty.
    const queueChip = document.createElement('button');
    queueChip.className = 'ss-queue-chip';
    document.body.appendChild(queueChip);
    queueChip.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); renderQueueView(); });
```

(`renderQueueView` is Task 3 — stub it there too if committing Task 2 alone: `function renderQueueView() {}`.)

**Step 2: real `refreshQueueChip`** (replace stub):

```js
    function queueStats() {
        let capturing = 0, frames = 0;
        for (const j of splitQueue.values()) { if (j.state === 'capturing') capturing++; frames += j.frames.length; }
        return { jobs: splitQueue.size, capturing, frames };
    }
    function refreshQueueChip() {
        const s = queueStats();
        if (!s.jobs) { queueChip.classList.remove('visible'); return; }
        queueChip.textContent = s.capturing
            ? `⏳ ${s.capturing} splitting · ${s.frames} frames`
            : `🎞 ${s.jobs} split${s.jobs > 1 ? 's' : ''} · ${s.frames} frames`;
        queueChip.classList.add('visible');
    }
```

**Step 3: CSS** (after the `.ss-persona-*` block, mirroring its conventions):

```css
/* ---- Split-queue chip ---- */
.ss-queue-chip {
    all: unset;
    position: fixed !important;
    right: 20px;
    bottom: 20px;
    z-index: 2147483646;
    display: none;
    box-sizing: border-box !important;
    padding: 11px 16px !important;
    border-radius: 999px !important;
    background: linear-gradient(135deg, #3a3550 0%, #2b2740 100%) !important;
    color: #F3EFE6 !important;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    cursor: pointer !important;
    box-shadow: 0 10px 26px rgba(26, 24, 20, 0.35) !important;
    transition: transform 0.15s ease !important;
}
.ss-queue-chip.visible { display: inline-flex !important; }
.ss-queue-chip:hover { transform: translateY(-2px) !important; }
```

**Step 4:** `node --check`; reload; queue a reel → chip appears bottom-right counting frames up, settles at `🎞 1 split · N frames`.

**Step 5: Commit** — `feat(extension): split-queue chip with live progress`

---

### Task 3: Queue view in the panel (live-updating)

**Files:** Modify `chrome-extension/content.js` (replace `renderQueueView`/`syncQueueJob` stubs; place after `renderPickGrid`) + `content.css`

**Step 1: view + live sync.** Selection lives on `job.dropped` (Set of deselected indexes) so re-renders and live appends keep state. `syncQueueJob` appends only new cells (no flicker, no scroll reset).

```js
    // ---- Split-queue view ---------------------------------------------------------
    function statusLabel(job) {
        switch (job.state) {
            case 'capturing': return `capturing ${job.frames.length}/${job.total}…`;
            case 'captured':  return `${job.frames.length} frames`;
            case 'partial':   return `partial · ${job.frames.length}/${job.total}`;
            default:          return `✗ ${job.error || 'failed'}`;
        }
    }

    function queueFrameCell(job, idx) {
        const cell = el('div', 'al-frame' + (job.dropped.has(idx) ? '' : ' selected'));
        const im = document.createElement('img'); im.src = job.frames[idx]; cell.appendChild(im);
        cell.appendChild(el('span', 'al-frame-tick', '✓'));
        cell.addEventListener('click', (e) => {
            e.preventDefault(); e.stopPropagation();
            if (job.dropped.has(idx)) job.dropped.delete(idx); else job.dropped.add(idx);
            cell.classList.toggle('selected', !job.dropped.has(idx));
            updateQueueBar();
        });
        return cell;
    }

    // Append new frames / refresh status of one job while the view is open.
    function syncQueueJob(job) {
        if (job._status && job._status.isConnected) {
            job._status.textContent = statusLabel(job);
            job._status.className = `al-queue-status st-${job.state}`;
        }
        if (job._grid && job._grid.isConnected) {
            for (let i = job._grid.children.length; i < job.frames.length; i++) {
                job._grid.appendChild(queueFrameCell(job, i));
            }
        }
        updateQueueBar();
    }

    let queueSaveBtn = null;
    function updateQueueBar() {
        if (!queueSaveBtn || !queueSaveBtn.isConnected) return;
        let n = 0, capturing = false;
        for (const j of splitQueue.values()) {
            if (j.state === 'capturing') { capturing = true; continue; }
            n += j.frames.length - j.dropped.size;
        }
        queueSaveBtn.textContent = n
            ? `Save all (${n} frame${n > 1 ? 's' : ''})${capturing ? ' · still splitting…' : ''}`
            : (capturing ? 'Splitting…' : 'Save (none)');
        queueSaveBtn.disabled = n === 0;
    }

    function renderQueueView() {
        queueViewOpen = true;
        clearPanel();
        panel.appendChild(frameHeader('Split queue'));
        const body = el('div', 'al-body al-frames-body');

        if (!splitQueue.size) {
            body.appendChild(el('div', 'al-frames-hint', 'Queue is empty — hover a video and press Split.'));
        }
        for (const job of splitQueue.values()) {
            const sec = el('div', 'al-queue-job');
            const head = el('div', 'al-queue-head');
            const who = job.context.instagram_handle ? ` · @${job.context.instagram_handle}` : '';
            head.appendChild(el('span', 'al-queue-title', `Video #${job.id}${who}`));
            const status = el('span', `al-queue-status st-${job.state}`, statusLabel(job));
            head.appendChild(status);
            const drop = el('button', 'al-queue-drop', '✕');
            drop.addEventListener('click', (e) => {
                e.preventDefault(); e.stopPropagation();
                splitQueue.delete(job.id);
                refreshQueueChip(); renderQueueView();
            });
            head.appendChild(drop);
            sec.appendChild(head);

            const grid = el('div', 'al-frames-grid');
            job.frames.forEach((_, idx) => grid.appendChild(queueFrameCell(job, idx)));
            sec.appendChild(grid);
            job._status = status; job._grid = grid;
            body.appendChild(sec);
        }
        panel.appendChild(body);

        const bar = el('div', 'al-frames-bar');
        queueSaveBtn = el('button', 'al-frames-save', '');
        bar.appendChild(queueSaveBtn);
        panel.appendChild(bar);
        queueSaveBtn.addEventListener('click', (e) => {
            e.preventDefault(); e.stopPropagation();
            massSaveQueue(queueSaveBtn);
        });
        updateQueueBar();
        openPanel();
    }
```

Also: other panel renders must mark the queue view closed — add `queueViewOpen = false;` as the first line of `clearPanel()`, and `renderQueueView` sets it back to `true` right after calling `clearPanel()` (adjust the code above accordingly: set it after `clearPanel()`).

(`massSaveQueue` is Task 4 — stub `function massSaveQueue(btn) {}` if committing separately.)

**Step 2: CSS** for the job sections:

```css
/* Split-queue view */
.sharirasutra-panel .al-queue-job { margin-bottom: 18px !important; padding-bottom: 14px !important; border-bottom: 1px dashed #E0DACE !important; }
.sharirasutra-panel .al-queue-job:last-child { border-bottom: none !important; }
.sharirasutra-panel .al-queue-head { display: flex !important; align-items: center !important; gap: 8px !important; margin-bottom: 10px !important; }
.sharirasutra-panel .al-queue-title { font-size: 13px !important; font-weight: 700 !important; color: #1A1814 !important; flex: 1 !important; }
.sharirasutra-panel .al-queue-status { font-size: 11.5px !important; font-weight: 600 !important; color: #6F6A61 !important; }
.sharirasutra-panel .al-queue-status.st-captured { color: #1f8a5b !important; }
.sharirasutra-panel .al-queue-status.st-partial { color: #b8860b !important; }
.sharirasutra-panel .al-queue-status.st-failed { color: #b8403c !important; }
.sharirasutra-panel .al-queue-drop { all: unset; cursor: pointer !important; color: #9C968B !important; font-size: 15px !important; padding: 2px 6px !important; border-radius: 6px !important; }
.sharirasutra-panel .al-queue-drop:hover { color: #b8403c !important; background: #F4F1EA !important; }
```

**Step 3:** `node --check`; reload; queue two reels quickly, click the chip mid-capture → two sections, frames appearing live, statuses settle; deselect a few frames; ✕ discards a job.

**Step 4: Commit** — `feat(extension): split-queue panel view — per-job sections, live frame append, discard`

---

### Task 4: Mass save (generalized saveFrames with per-entry context)

**Files:** Modify `chrome-extension/content.js` — `saveFrames` (~line 691), its `renderPickGrid` call site (~line 684), new `massSaveQueue`

**Step 1: generalize `saveFrames`** to entries with optional per-entry context and a return count:

```js
    // entries: [{url, context?}] — context overrides the live-page fields (queue jobs
    // save after the user has scrolled somewhere else). Returns the saved count.
    async function saveFrames(entries, btn, tags) {
        if (!entries.length) return 0;
        btn.disabled = true;
        let saved = 0;
        for (let i = 0; i < entries.length; i++) {
            btn.textContent = `Saving ${i + 1}/${entries.length}…`;
            try {
                const r = await fetch(SAVE_URL, {
                    method: 'POST', mode: 'cors',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        image_url: entries[i].url, general_tags: tags || [],
                        ...(entries[i].context || { source_url: location.href, ...instagramContextForSave() }),
                    })
                });
                if (r.ok) saved++;
            } catch (e) { /* keep going */ }
        }
        btn.classList.add(saved ? 'al-done' : 'al-fail');
        btn.textContent = saved ? `✓ Saved ${saved}` : '✗ Failed';
        return saved;
    }
```

**Step 2: adapt the `renderPickGrid` call site** (carousel + any future direct grids keep live context):

```js
            saveFrames(items.filter(i => i.selected).map(i => ({ url: i.url })), save, tags);
```

**Step 3: `massSaveQueue`** (replace stub):

```js
    async function massSaveQueue(btn) {
        const settled = [...splitQueue.values()].filter(j => j.state !== 'capturing');
        const entries = [];
        settled.forEach(j => j.frames.forEach((url, idx) => {
            if (!j.dropped.has(idx)) entries.push({ url, context: j.context });
        }));
        const saved = await saveFrames(entries, btn, ['video-frame']);
        if (saved) {
            settled.forEach(j => splitQueue.delete(j.id));
            refreshQueueChip();
            setTimeout(() => { if (queueViewOpen) renderQueueView(); }, 1200);
        }
    }
```

**Step 4:** `node --check`; reload; full flow: queue reel A (note its handle), scroll to reel B, queue it, open chip, Save all → posts land tagged `video-frame`, each with **its own** reel's `source_url`/handle (check two saved posts in the gallery/API). Queue empties; chip hides.

**Step 5: Commit** — `feat(extension): mass save — saveFrames entries with per-job snapshotted context`

---

### Task 5: Final review + manual checklist

1. Dispatch a code-review subagent over the full diff (spec = both docs); fix Important+ findings, re-review.
2. Manual checklist (user, logged-in Chrome): single reel queue → chip → Save all; 3 rapid queues (parallel capture, three sections); tab switch mid-capture (continues, slower); scroll far mid-capture (partial, frames kept); protected video (failed, others fine); handle correctness (A's frames carry A's handle after scrolling to B); carousel Save all + image Save + Brainstorm regressions (renderPickGrid/saveFrames untouched paths); console clean.
3. Update `CONTEXT.md` §12.7 with a split-queue note; commit.
