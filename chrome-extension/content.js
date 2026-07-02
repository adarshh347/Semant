// Sharirasutra Chrome Extension - Content Script
// Hover any image to get two actions:
//   • Save to Sharirasutra  — stores the image to your gallery
//   • Brainstorm             — "Aletheia" interpretive analysis (lenses + punctum)
// Uses document-level pointer tracking + elementsFromPoint so it works on sites
// (Instagram, Pinterest, ...) that cover images with transparent overlays.

(function () {
    'use strict';

    const SAVE_URL = 'http://localhost:5007/api/v1/posts/upload-from-url';
    const BRAINSTORM_URL = 'http://localhost:5007/api/v1/posts/brainstorm';
    const PERSONA_INGEST_URL = 'http://localhost:5007/api/v1/personas/ingest';
    const DASHBOARD_URL = 'http://localhost:5173/personas';
    const MIN_IMAGE_SIZE = 100;

    // ---- Floating toolbar (Save + Brainstorm) ----------------------------------
    const toolbar = document.createElement('div');
    toolbar.className = 'sharirasutra-toolbar';

    const saveBtn = document.createElement('button');
    saveBtn.className = 'sharirasutra-btn sharirasutra-save-btn';
    saveBtn.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
        <polyline points="17 21 17 13 7 13 7 21"></polyline>
        <polyline points="7 3 7 8 15 8"></polyline>
      </svg><span>Save</span>`;

    const brainstormBtn = document.createElement('button');
    brainstormBtn.className = 'sharirasutra-btn sharirasutra-brainstorm-btn';
    brainstormBtn.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2a7 7 0 0 0-4 12.7V17a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2v-2.3A7 7 0 0 0 12 2z"></path>
        <line x1="9" y1="22" x2="15" y2="22"></line>
      </svg><span>Brainstorm</span>`;

    // Video → frames button (Alexia), shown only when hovering a <video>
    const splitBtn = document.createElement('button');
    splitBtn.className = 'sharirasutra-btn sharirasutra-split-btn';
    splitBtn.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="2" y="2" width="20" height="20" rx="2.5"></rect>
        <line x1="8" y1="2" x2="8" y2="22"></line><line x1="16" y1="2" x2="16" y2="22"></line>
      </svg><span>Split → Save</span>`;

    // Carousel → all photos button (Alexia), shown only when hovering a carousel image
    const sweepBtn = document.createElement('button');
    sweepBtn.className = 'sharirasutra-btn sharirasutra-sweep-btn';
    sweepBtn.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="3" width="13" height="13" rx="2"></rect>
        <path d="M19 8v11a2 2 0 0 1-2 2H8"></path>
      </svg><span>Save all</span>`;

    toolbar.appendChild(brainstormBtn);
    toolbar.appendChild(saveBtn);
    toolbar.appendChild(splitBtn);
    toolbar.appendChild(sweepBtn);
    document.body.appendChild(toolbar);

    // ---- Analysis panel --------------------------------------------------------
    const panel = document.createElement('div');
    panel.className = 'sharirasutra-panel';
    document.body.appendChild(panel);

    // Floating split-queue chip (bottom-right) — visible while the queue is non-empty.
    const queueChip = document.createElement('button');
    queueChip.className = 'ss-queue-chip';
    document.body.appendChild(queueChip);
    queueChip.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); renderQueueView(); });

    let currentImage = null;
    let currentVideo = null;
    let hideTimeout = null;
    let rafScheduled = false;

    // Brainstorm dialogue state
    let bsImageUrl = null;   // image being interpreted
    let bsAnswers = [];      // [{question, choice}] accumulated across rounds
    let bsRound = 0;

    // Carousel sweep state — guards re-entry while the carousel is flipping under
    // the (stationary) cursor, which retriggers showTarget on each new slide.
    let sweeping = false;

    // ---- helpers ---------------------------------------------------------------
    function el(tag, className, text) {
        const n = document.createElement(tag);
        if (className) n.className = className;
        if (text != null) n.textContent = text;
        return n;
    }

    function isValidImage(img) {
        if (!img || img.tagName !== 'IMG') return false;
        const w = img.naturalWidth || img.width;
        const h = img.naturalHeight || img.height;
        if (w < MIN_IMAGE_SIZE || h < MIN_IMAGE_SIZE) return false;
        const src = img.currentSrc || img.src;
        if (!src || src.startsWith('data:image/svg') || src.includes('blank.gif')) return false;
        return true;
    }

    function imageAtPoint(x, y) {
        const stack = document.elementsFromPoint(x, y);
        for (const node of stack) {
            if (node === toolbar || toolbar.contains(node) || node === panel || panel.contains(node)) continue;
            if (node.tagName === 'IMG' && isValidImage(node)) return node;
        }
        for (const node of stack) {
            if (node === toolbar || toolbar.contains(node) || node === panel || panel.contains(node)) continue;
            const img = node.querySelector && node.querySelector('img');
            if (img && isValidImage(img)) return img;
        }
        return null;
    }

    function getImageUrl(img) {
        return img.currentSrc || img.src || img.dataset.src || '';
    }

    function positionToolbar(img) {
        const rect = img.getBoundingClientRect();
        const top = window.pageYOffset || document.documentElement.scrollTop;
        const left = window.pageXOffset || document.documentElement.scrollLeft;
        toolbar.style.top = `${rect.top + top + 10}px`;
        toolbar.style.left = `${rect.right + left - toolbar.offsetWidth - 10}px`;
    }

    function isValidVideo(v) {
        if (!v || v.tagName !== 'VIDEO') return false;
        const w = v.videoWidth || v.offsetWidth;
        const h = v.videoHeight || v.offsetHeight;
        return w >= 120 && h >= 120;
    }

    // A genuine <video> actually under the cursor (hit-testable).
    function videoAtPointStack(x, y) {
        const stack = document.elementsFromPoint(x, y);
        for (const node of stack) {
            if (node === toolbar || toolbar.contains(node) || node === panel || panel.contains(node)) continue;
            if (node.tagName === 'VIDEO' && isValidVideo(node)) return node;
            const v = node.querySelector && node.querySelector('video');
            if (v && isValidVideo(v)) return v;
        }
        return null;
    }

    // Geometric fallback: many sites (Instagram reels) set pointer-events:none on the
    // <video>, so elementsFromPoint EXCLUDES it. Scan real, VISIBLE <video> rects and
    // return the smallest one enclosing the cursor.
    function videoAtPointGeometric(x, y) {
        let best = null, bestArea = Infinity;
        const vids = document.getElementsByTagName('video');
        for (const v of vids) {
            if (!isValidVideo(v)) continue;
            if (v.offsetParent === null) continue;            // skip display:none / detached
            const cs = getComputedStyle(v);
            if (cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) continue;
            const r = v.getBoundingClientRect();
            if (r.width < 120 || r.height < 120) continue;
            if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) {
                const area = r.width * r.height;              // prefer the smallest enclosing video
                if (area < bestArea) { bestArea = area; best = v; }
            }
        }
        return best;
    }

    function rectArea(r) { return Math.max(0, r.width) * Math.max(0, r.height); }

    // Does the (pointer-events:none) video actually COVER the image — i.e. is this a
    // reel whose poster <img> sits under it — rather than an unrelated background video
    // that merely encloses a small photo? Require strong overlap + comparable size.
    function videoCoversImage(video, img) {
        const rv = video.getBoundingClientRect(), ri = img.getBoundingClientRect();
        const ix = Math.max(0, Math.min(rv.right, ri.right) - Math.max(rv.left, ri.left));
        const iy = Math.max(0, Math.min(rv.bottom, ri.bottom) - Math.max(rv.top, ri.top));
        const inter = ix * iy;
        const aImg = rectArea(ri), aVid = rectArea(rv);
        if (aImg === 0) return false;
        const overlap = inter / aImg;                 // how much of the image the video covers
        return overlap > 0.6 && aVid <= aImg * 4;     // reel ≈ same region; reject big backgrounds
    }

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
            if (!b.querySelector('svg') || b.textContent.trim()) continue;  // chevrons are icon-only
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
    // prevButtonIn matters too: on the LAST slide only "Go back" exists.
    function findCarousel(img) {
        const li = img.closest('li');
        const track = li && li.closest('ul');
        if (!track) return null;
        // A slide <li> is essentially all image. This rejects look-alike <ul>/<li>
        // pagers whose items are whole posts (e.g. the modal's prev/next-post track,
        // where the li also holds header/caption/actions).
        if (rectArea(img.getBoundingClientRect()) < rectArea(li.getBoundingClientRect()) * 0.5) return null;
        if (track.querySelectorAll(':scope > li').length < 2) return null;
        let node = track.parentElement;
        for (let depth = 0; node && depth < 5; depth++, node = node.parentElement) {
            if (nextButtonIn(node, track) || prevButtonIn(node, track)) return { track, wrapper: node };
        }
        return null;
    }

    // ---- Carousel slide collection -----------------------------------------------
    // Largest srcset candidate, else currentSrc/src.
    function bestImageUrl(img) {
        let best = null, bestW = 0;
        // Split only on commas that actually separate candidates — a raw comma
        // inside a URL must not break the parse.
        (img.srcset || '').split(/,(?=\s*\S+\s+\d+w)/).forEach(part => {
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

    function setToolbarMode(type) {
        const isVideo = type === 'video';
        brainstormBtn.style.display = isVideo ? 'none' : '';
        saveBtn.style.display = isVideo ? 'none' : '';
        splitBtn.style.display = isVideo ? '' : 'none';
        // Shown per-image by showTarget when a carousel is detected; while a sweep
        // is running, leave it visible so the "Reading N…" progress stays on screen.
        if (!sweeping) sweepBtn.style.display = 'none';
    }

    function showTarget(el, type) {
        if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null; }
        const prev = currentImage || currentVideo;
        if (prev && prev !== el) prev.classList.remove('sharirasutra-hover-highlight');
        currentImage = type === 'image' ? el : null;
        currentVideo = type === 'video' ? el : null;
        el.classList.add('sharirasutra-hover-highlight');
        setToolbarMode(type);
        if (type === 'image') {
            saveBtn.classList.remove('success', 'error', 'saving');
            saveBtn.querySelector('span').textContent = 'Save';
            if (!sweeping) {
                sweepBtn.classList.remove('success', 'error', 'saving');
                sweepBtn.querySelector('span').textContent = 'Save all';
                // Decide sweep visibility BEFORE positioning — it changes toolbar width.
                sweepBtn.style.display = findCarousel(el) ? '' : 'none';
            }
        } else {
            splitBtn.classList.remove('success', 'error', 'saving');
            splitBtn.querySelector('span').textContent = 'Split → Save';
        }
        positionToolbar(el);
        toolbar.classList.add('visible');
    }

    function hideToolbar() {
        if (hideTimeout) clearTimeout(hideTimeout);
        hideTimeout = setTimeout(() => {
            const cur = currentImage || currentVideo;
            if (cur) cur.classList.remove('sharirasutra-hover-highlight');
            toolbar.classList.remove('visible');
            currentImage = null; currentVideo = null;
        }, 300);
    }

    // Show/keep the toolbar for a target without re-rendering if it's unchanged.
    function selectTarget(el, type) {
        const cur = type === 'video' ? currentVideo : currentImage;
        if (el !== cur) showTarget(el, type);
        else if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null; }
    }

    function onPointerMove(e) {
        if (rafScheduled) return;
        rafScheduled = true;
        const x = e.clientX, y = e.clientY;
        requestAnimationFrame(() => {
            rafScheduled = false;
            const top = document.elementFromPoint(x, y);
            if (top && (top === toolbar || toolbar.contains(top) || top === panel || panel.contains(top)
                        || top === personaFab || personaFab.contains(top))) {
                if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null; }
                return;
            }

            // 1) A real <video> directly under the cursor → video mode.
            const stackVideo = videoAtPointStack(x, y);
            if (stackVideo) { selectTarget(stackVideo, 'video'); return; }

            // 2) Resolve photo vs reel. A photo under the cursor wins UNLESS a
            //    pointer-events:none video actually covers it (the reel case).
            const img = imageAtPoint(x, y);
            const geoVideo = videoAtPointGeometric(x, y);
            if (img && geoVideo && videoCoversImage(geoVideo, img)) { selectTarget(geoVideo, 'video'); return; }
            if (img) { selectTarget(img, 'image'); return; }       // <-- static photos work again
            if (geoVideo) { selectTarget(geoVideo, 'video'); return; }  // reel with no poster img

            if (currentImage || currentVideo) hideToolbar();
        });
    }

    document.addEventListener('mousemove', onPointerMove, { passive: true });
    window.addEventListener('scroll', () => { if (currentImage) positionToolbar(currentImage); }, { passive: true });
    toolbar.addEventListener('mouseenter', () => { if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null; } });
    toolbar.addEventListener('mouseleave', hideToolbar);

    // ---- Save ------------------------------------------------------------------
    async function saveImage() {
        if (!currentImage) return;
        const imageUrl = getImageUrl(currentImage);
        if (!imageUrl) return;
        saveBtn.classList.add('saving');
        saveBtn.querySelector('span').textContent = 'Saving…';
        try {
            const r = await fetch(SAVE_URL, {
                method: 'POST', mode: 'cors',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image_url: imageUrl, source_url: location.href, general_tags: [], ...instagramContextForSave(currentImage) })
            });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            await r.json();
            saveBtn.classList.remove('saving'); saveBtn.classList.add('success');
            saveBtn.querySelector('span').textContent = '✓ Saved';
        } catch (err) {
            console.error('Sharirasutra save error:', err);
            saveBtn.classList.remove('saving'); saveBtn.classList.add('error');
            saveBtn.querySelector('span').textContent = '✗ Failed';
        }
    }

    // ---- Brainstorm panel ------------------------------------------------------
    function clearPanel() {
        queueViewOpen = false;   // any other render replaces the queue view
        while (panel.firstChild) panel.removeChild(panel.firstChild);
    }

    function panelHeader() {
        const head = el('div', 'al-head');
        const titleWrap = el('div', 'al-title-wrap');
        titleWrap.appendChild(el('div', 'al-kicker', 'Aletheia'));
        titleWrap.appendChild(el('div', 'al-title', 'Unconcealment'));
        const close = el('button', 'al-close', '×');
        close.addEventListener('click', () => panel.classList.remove('open'));
        head.appendChild(titleWrap);
        head.appendChild(close);
        return head;
    }

    function openPanel() { panel.classList.add('open'); }

    function renderLoading(thumbUrl) {
        clearPanel();
        panel.appendChild(panelHeader());
        const body = el('div', 'al-body');
        if (thumbUrl) {
            const t = el('div', 'al-thumb');
            const im = document.createElement('img'); im.src = thumbUrl; t.appendChild(im);
            body.appendChild(t);
        }
        const loading = el('div', 'al-loading');
        loading.appendChild(el('div', 'al-spinner'));
        loading.appendChild(el('div', 'al-loading-text', 'Letting the image emerge…'));
        body.appendChild(loading);
        panel.appendChild(body);
        openPanel();
    }

    function renderError(msg) {
        clearPanel();
        panel.appendChild(panelHeader());
        const body = el('div', 'al-body');
        body.appendChild(el('div', 'al-error', msg || 'Could not interpret this image.'));
        panel.appendChild(body);
        openPanel();
    }

    function renderResult(data, thumbUrl) {
        clearPanel();
        panel.appendChild(panelHeader());
        const body = el('div', 'al-body');

        if (thumbUrl) {
            const t = el('div', 'al-thumb');
            const im = document.createElement('img'); im.src = thumbUrl; t.appendChild(im);
            body.appendChild(t);
        }

        // Thread of choices made so far (the back-and-forth)
        if (bsAnswers.length) {
            const thread = el('div', 'al-thread');
            thread.appendChild(el('div', 'al-label', `Your reading · round ${bsRound}`));
            const chips = el('div', 'al-thread-chips');
            bsAnswers.forEach(a => chips.appendChild(el('span', 'al-thread-chip', a.choice)));
            thread.appendChild(chips);
            body.appendChild(thread);
        }

        // Lenses with intensity bars
        (data.lenses || []).forEach(lens => {
            const wrap = el('div', 'al-lens');
            const head = el('div', 'al-lens-head');
            head.appendChild(el('span', 'al-lens-name', lens.name || 'Lens'));
            head.appendChild(el('span', 'al-lens-pct', `${lens.intensity ?? 0}`));
            wrap.appendChild(head);
            const bar = el('div', 'al-bar');
            const fill = el('div', 'al-bar-fill');
            fill.style.width = '0%';
            bar.appendChild(fill);
            wrap.appendChild(bar);
            wrap.appendChild(el('p', 'al-lens-reading', lens.reading || ''));
            body.appendChild(wrap);
            requestAnimationFrame(() => requestAnimationFrame(() => {
                fill.style.width = `${Math.max(0, Math.min(100, lens.intensity ?? 0))}%`;
            }));
        });

        // Interactive questions (MCQ) — clicking an option refines the reading
        const questions = data.questions || [];
        if (questions.length) {
            const qWrap = el('div', 'al-questions');
            qWrap.appendChild(el('div', 'al-label', 'Look closer'));
            questions.forEach(q => {
                const block = el('div', 'al-q');
                block.appendChild(el('p', 'al-q-prompt', q.prompt));
                const opts = el('div', 'al-q-opts');
                (q.options || []).forEach(opt => {
                    const b = el('button', 'al-opt', opt);
                    b.addEventListener('click', (e) => {
                        e.preventDefault(); e.stopPropagation();
                        chooseAnswer(q.prompt, opt);
                    });
                    opts.appendChild(b);
                });
                block.appendChild(opts);
                qWrap.appendChild(block);
            });
            body.appendChild(qWrap);
        } else if (bsRound > 0) {
            // model decided the image has settled
            body.appendChild(el('div', 'al-settled', 'The image has settled, for now.'));
        }

        if (data.concealed) {
            const c = el('div', 'al-foot');
            c.appendChild(el('span', 'al-foot-label', 'Concealed'));
            c.appendChild(el('span', 'al-foot-text', data.concealed));
            body.appendChild(c);
        }
        if (data.uncertainty) {
            const u = el('div', 'al-foot');
            u.appendChild(el('span', 'al-foot-label', 'Uncertain'));
            u.appendChild(el('span', 'al-foot-text', data.uncertainty));
            body.appendChild(u);
        }

        panel.appendChild(body);
        openPanel();
    }

    // Fetch a (possibly refined) reading using the accumulated answers
    async function runBrainstorm() {
        renderLoading(bsImageUrl);
        try {
            const r = await fetch(BRAINSTORM_URL, {
                method: 'POST', mode: 'cors',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image_url: bsImageUrl, source_url: location.href, answers: bsAnswers })
            });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const data = await r.json();
            renderResult(data, bsImageUrl);
        } catch (err) {
            console.error('Sharirasutra brainstorm error:', err);
            renderError('Could not interpret this image (is the backend running?).');
        }
    }

    // A clicked MCQ option → record it and ask for a refined reading
    function chooseAnswer(question, choice) {
        bsAnswers.push({ question, choice });
        bsRound += 1;
        runBrainstorm();
    }

    // Entry point: start a fresh dialogue for the hovered image
    function brainstormImage() {
        if (!currentImage) return;
        const imageUrl = getImageUrl(currentImage);
        if (!imageUrl) return;
        bsImageUrl = imageUrl;
        bsAnswers = [];
        bsRound = 0;
        runBrainstorm();
    }

    // ---- Alexia: split a video into frames and save each ------------------------
    // Resolves true on a real seek, false if 'seeked' never fired (streams).
    function seekVideo(video, t) {
        return new Promise((resolve) => {
            let done = false;
            const finish = (ok) => { if (done) return; done = true; video.removeEventListener('seeked', onSeeked); resolve(ok); };
            const onSeeked = () => finish(true);
            video.addEventListener('seeked', onSeeked);
            setTimeout(() => finish(false), 1500);
            try { video.currentTime = t; } catch (e) { finish(false); }
        });
    }

    // ---- Alexia: split queue — background captures + mass save -------------------
    // A queued job captures from its LIVE element immediately (it's on screen at
    // click time); jobs run in parallel; the user scrolls on and queues more. Frames
    // accumulate on the job and are mass-saved from the queue view.
    const splitQueue = new Map();   // jobId -> job
    let nextJobId = 1;
    let queueViewOpen = false;

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
            // Rate: ~3 frames/sec, clamped to 8–60 evenly-spaced frames.
            total: Math.max(8, Math.min(60, Math.round(duration * 3))),
            // Snapshot author context NOW — by save time the user has scrolled
            // to a different post and live page context would be wrong.
            igContext: instagramContextForSave(video),
            sourceUrl: location.href,
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

        job.state = job.frames.length
            ? (job.error || job.frames.length < job.total ? 'partial' : 'captured')
            : 'failed';
        if (job.state === 'failed' && !job.error) job.error = 'no frames';
        if (video.isConnected) {
            try { video.currentTime = prevTime; } catch (e) {}
            video.muted = wasMuted;
            if (!wasPaused) { try { video.play(); } catch (e) {} }
        }
    }

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

    // Append new frames / refresh the status of one job while the view is open —
    // append-only so live capture doesn't flicker the grid or reset panel scroll.
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
    let massSaving = false;    // freezes the bar so live captures can't overwrite save progress
    function updateQueueBar() {
        if (massSaving) return;
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
        clearPanel();
        queueViewOpen = true;
        panel.appendChild(frameHeader('Split queue'));
        const body = el('div', 'al-body al-frames-body');

        if (!splitQueue.size) {
            body.appendChild(el('div', 'al-frames-hint', 'Queue is empty — hover a video and press Split.'));
        }
        for (const job of splitQueue.values()) {
            const sec = el('div', 'al-queue-job');
            const head = el('div', 'al-queue-head');
            const who = job.igContext.instagram_handle ? ` · @${job.igContext.instagram_handle}` : '';
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

    async function massSaveQueue(btn) {
        const settled = [...splitQueue.values()].filter(j => j.state !== 'capturing');
        const work = [];
        settled.forEach(j => j.frames.forEach((url, idx) => {
            if (!j.dropped.has(idx)) work.push({ url, job: j });
        }));
        if (!work.length) return;
        massSaving = true;
        btn.disabled = true;
        let saved = 0;
        for (let i = 0; i < work.length; i++) {
            btn.textContent = `Saving ${i + 1}/${work.length}…`;
            if (await postFrame(work[i].url, ['video-frame'], work[i].job.igContext, work[i].job.sourceUrl)) saved++;
        }
        btn.classList.add(saved ? 'al-done' : 'al-fail');
        btn.textContent = saved ? `✓ Saved ${saved}` : '✗ Failed';
        if (saved) { settled.forEach(j => splitQueue.delete(j.id)); refreshQueueChip(); }
        setTimeout(() => {
            massSaving = false;
            if (queueViewOpen) renderQueueView();   // saved jobs gone; bar rebuilt
        }, 1200);
    }

    // Header for the Alexia frame-review view
    function frameHeader(title) {
        const head = el('div', 'al-head');
        const wrap = el('div', 'al-title-wrap');
        wrap.appendChild(el('div', 'al-kicker', 'Alexia'));
        wrap.appendChild(el('div', 'al-title', title));
        const close = el('button', 'al-close', '×');
        close.addEventListener('click', () => panel.classList.remove('open'));
        head.appendChild(wrap);
        head.appendChild(close);
        return head;
    }

    // Review grid: all items selected by default; tap to deselect; then save kept ones.
    // Used by both the video-frame flow and the carousel sweep. `igContext`/`sourceUrl`
    // are captured by the caller at collection time — the user may scroll to another
    // post before saving, so live page context would attribute the wrong author.
    function renderPickGrid(urls, opts) {
        const { title, hint, tags, noun = 'frame', igContext, sourceUrl } = opts;
        const items = urls.map(url => ({ url, selected: true }));
        clearPanel();
        panel.appendChild(frameHeader(title));

        const body = el('div', 'al-body al-frames-body');
        body.appendChild(el('div', 'al-frames-hint', hint));
        const grid = el('div', 'al-frames-grid');
        items.forEach((it, idx) => {
            const cell = el('div', 'al-frame selected');
            const img = document.createElement('img'); img.src = it.url; cell.appendChild(img);
            cell.appendChild(el('span', 'al-frame-tick', '✓'));
            cell.addEventListener('click', (e) => {
                e.preventDefault(); e.stopPropagation();
                it.selected = !it.selected;
                cell.classList.toggle('selected', it.selected);
                updateBar();
            });
            grid.appendChild(cell);
        });
        body.appendChild(grid);
        panel.appendChild(body);

        const bar = el('div', 'al-frames-bar');
        const toggle = el('button', 'al-frames-toggle', 'Clear all');
        const save = el('button', 'al-frames-save', '');
        bar.appendChild(toggle);
        bar.appendChild(save);
        panel.appendChild(bar);

        const count = () => items.filter(i => i.selected).length;
        function updateBar() {
            const c = count();
            save.textContent = c ? `Save ${c} ${noun}${c > 1 ? 's' : ''}` : 'Save (none)';
            save.disabled = c === 0;
            toggle.textContent = (c === items.length) ? 'Clear all' : 'Select all';
        }
        toggle.addEventListener('click', (e) => {
            e.preventDefault(); e.stopPropagation();
            const selectAll = count() !== items.length;
            items.forEach(it => { it.selected = selectAll; });
            grid.querySelectorAll('.al-frame').forEach((cell, idx) => cell.classList.toggle('selected', items[idx].selected));
            updateBar();
        });
        save.addEventListener('click', (e) => {
            e.preventDefault(); e.stopPropagation();
            saveFrames(items.filter(i => i.selected).map(i => i.url), save, tags, igContext, sourceUrl);
        });

        updateBar();
        openPanel();
    }

    // One frame → backend. igContext/sourceUrl default to the live page when absent.
    async function postFrame(url, tags, igContext, sourceUrl) {
        try {
            const r = await fetch(SAVE_URL, {
                method: 'POST', mode: 'cors',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image_url: url, source_url: sourceUrl || location.href, general_tags: tags || [], ...(igContext || {}) })
            });
            return r.ok;
        } catch (e) { return false; }
    }

    async function saveFrames(urls, btn, tags, igContext, sourceUrl) {
        if (!urls.length) return 0;
        btn.disabled = true;
        let saved = 0;
        for (let i = 0; i < urls.length; i++) {
            btn.textContent = `Saving ${i + 1}/${urls.length}…`;
            if (await postFrame(urls[i], tags, igContext, sourceUrl)) saved++;
        }
        btn.classList.add(saved ? 'al-done' : 'al-fail');
        btn.textContent = saved ? `✓ Saved ${saved}` : '✗ Failed';
        return saved;
    }

    // ---- Alexia: sweep a carousel post — collect every photo slide ---------------
    async function sweepCarousel() {
        if (sweeping) return;
        const img = currentImage;
        if (!img) return;
        // Capture author context NOW — same stale-context hazard as splitVideo:
        // the user may scroll to another post before saving the picked slides.
        const igContext = instagramContextForSave(img);
        const sourceUrl = location.href;
        const car = findCarousel(img);
        if (!car) {
            sweepBtn.classList.add('error');
            sweepBtn.querySelector('span').textContent = '✗ Not a carousel';
            return;
        }
        sweepBtn.classList.remove('success', 'error');
        sweepBtn.classList.add('saving');
        let steps = 0;
        sweeping = true;
        try {
            const found = new Map();
            collectSlides(car.track, found);

            // Page forward, collecting as slides render. IG max is 20 slides; cap at 24.
            // Re-query the chevron each step — React re-renders replace the node, and on
            // the last slide it disappears. Dry steps showing a video slide don't count
            // (video slides add no images by design); 3 truly-dry steps = end (safety).
            const MAX_STEPS = 24;
            let dry = 0;
            while (steps < MAX_STEPS && dry < 3) {
                const next = nextButtonIn(car.wrapper, car.track);
                if (!next) break;
                next.click();
                steps++;
                sweepBtn.querySelector('span').textContent = `Reading ${found.size}…`;
                const added = await waitForNewSlides(car.track, found);
                if (added) dry = 0;
                else if (!car.track.querySelector('li video')) dry++;
            }

            const urls = [...found.values()];
            if (urls.length) {
                sweepBtn.querySelector('span').textContent = 'Save all';
                renderPickGrid(urls, {
                    title: 'Choose photos',
                    hint: `${urls.length} photo${urls.length > 1 ? 's' : ''} · tap to deselect`,
                    tags: ['carousel'],
                    noun: 'photo',
                    igContext, sourceUrl,
                });
            } else {
                sweepBtn.classList.add('error');
                sweepBtn.querySelector('span').textContent = '✗ No images';
            }
        } finally {
            // Page back so the user's position is restored — even on an exception.
            for (let i = 0; i < steps; i++) {
                const prev = prevButtonIn(car.wrapper, car.track);
                if (!prev) break;
                prev.click();
                await new Promise(r => setTimeout(r, 60));
            }
            sweepBtn.classList.remove('saving');
            sweeping = false;
        }
    }

    saveBtn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); saveImage(); });
    brainstormBtn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); brainstormImage(); });
    splitBtn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); queueSplit(currentVideo); });
    sweepBtn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); sweepCarousel(); });

    // ===========================================================================
    // Darpan — Instagram persona capture (profile pages)
    // A floating button that scrapes the account's details + captions and sends
    // them to the backend, which correlates them with images we already have.
    // ===========================================================================
    const RESERVED_IG = new Set(['p', 'reel', 'reels', 'explore', 'accounts', 'direct',
        'stories', 'about', 'tv', 's', 'developer', 'legal', 'privacy', '']);

    function isInstagram() { return /(^|\.)instagram\.com$/i.test(location.hostname); }

    function instagramProfileHandle() {
        // A profile is "/<handle>/" with a single, non-reserved segment.
        const m = location.pathname.match(/^\/([^\/]+)\/?$/);
        if (!m) return null;
        const seg = decodeURIComponent(m[1]).toLowerCase();
        if (RESERVED_IG.has(seg)) return null;
        return seg;
    }

    function instagramStoryHandle() {
        // Stories URL is /stories/<handle>/<story-id>/
        const m = location.pathname.match(/^\/stories\/([^\/]+)/);
        if (!m) return null;
        const seg = decodeURIComponent(m[1]).toLowerCase();
        return RESERVED_IG.has(seg) ? null : seg;
    }

    // On a post/reel page ("/p/…", "/reel/…"), find the author of the post the
    // user is *actually looking at*. This is surprisingly tricky because Instagram
    // shows a post two different ways on desktop:
    //   (a) standalone page  — the post is the centered column; the left
    //       nav-sidebar links to OUR logged-in profile.
    //   (b) modal overlay    — clicking a thumbnail opens <div role="dialog">
    //       over the page behind it. The dialog is a carousel: previous/next
    //       posts are rendered faded on the sides, and the page behind it still
    //       has its own posts + our profile link.
    // A naive "first /username/ link" therefore returns our own handle (nav
    // sidebar / background) or an adjacent faded post. So we select by geometry:
    // among visible "/username/" links inside the horizontally-centered band,
    // pick the one highest on screen — that's the active post's header author.
    function instagramPostAuthorHandle() {
        if (!/^\/(p|reel|reels|tv)\//.test(location.pathname)) return null;

        const scope = document.querySelector('div[role="dialog"]') || document;
        const vw = window.innerWidth;
        const bandMin = vw * 0.18, bandMax = vw * 0.82;  // exclude side/nav columns

        let best = null;
        scope.querySelectorAll('a[href^="/"]').forEach(a => {
            const m = (a.getAttribute('href') || '').match(/^\/([^\/]+)\/$/);
            if (!m) return;
            const seg = m[1].toLowerCase();
            if (RESERVED_IG.has(seg)) return;
            const r = a.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) return;          // hidden
            const cx = r.left + r.width / 2;
            if (cx < bandMin || cx > bandMax) return;             // off-center post / sidebar
            if (!best || r.top < best.top) best = { seg, top: r.top };
        });
        if (best) return best.seg;

        // Fallback: og:title on a post page is "Name (@handle) • Instagram…".
        const og = metaContent('og:title');
        const at = og.match(/\(@([A-Za-z0-9._]+)\)/);
        if (at && !RESERVED_IG.has(at[1].toLowerCase())) return at[1].toLowerCase();
        return null;
    }

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
        // Stories: the URL names the author authoritatively — mention stickers
        // inside the story would otherwise pollute the element-anchored stages.
        const story = instagramStoryHandle();
        if (story) return [story];
        if (el) {
            const fromContainer = handlesFromContainer(el);
            if (fromContainer.length) return fromContainer;
            const near = handlesNearElement(el);
            if (near.length) return near;
        }
        const author = instagramPostAuthorHandle();
        if (author) return [author];
        const profile = instagramProfileHandle();
        return profile ? [profile] : [];
    }

    // The account handle relevant to the current page (profile first, else post author).
    function detectedHandle() {
        return instagramProfileHandle() || instagramPostAuthorHandle();
    }

    // A light account snapshot (only trustworthy on a profile page, where og:image
    // is the avatar and og:title is "Name (@handle)").
    function accountSnapshot() {
        if (!instagramProfileHandle()) return null;
        const ogTitle = metaContent('og:title');
        const ogImage = metaContent('og:image');
        let display_name = '';
        const m = ogTitle.match(/^(.*?)\s*\(@/);
        if (m) display_name = m[1].trim();
        const snap = {};
        if (display_name) snap.display_name = display_name;
        if (ogImage) snap.avatar_url = ogImage;
        return Object.keys(snap).length ? snap : null;
    }

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

    function metaContent(prop) {
        const e = document.querySelector(`meta[property="${prop}"]`) ||
                  document.querySelector(`meta[name="${prop}"]`);
        return e ? (e.getAttribute('content') || '') : '';
    }

    function scrapeInstagramProfile(handle) {
        const ogTitle = metaContent('og:title');         // "Name (@handle) • Instagram…"
        const ogDesc = metaContent('og:description');     // "48K Followers, 6 Following, 30 Posts - …"
        const ogImage = metaContent('og:image');

        let display_name = '';
        const nameMatch = ogTitle.match(/^(.*?)\s*\(@/);
        if (nameMatch) display_name = nameMatch[1].trim();

        const grab = (re) => { const m = ogDesc.match(re); return m ? m[1] : null; };
        const followers = grab(/([\d.,KMB]+)\s+Followers/i);
        const following = grab(/([\d.,KMB]+)\s+Following/i);
        const posts_count = grab(/([\d.,KMB]+)\s+Posts/i);

        // Bio: best-effort from the header, else the snippet after "on Instagram:".
        let bio = '';
        try {
            const headerText = (document.querySelector('header section')?.innerText || '').trim();
            const lines = headerText.split('\n').map(s => s.trim()).filter(Boolean)
                .filter(l => !/followers|following|posts|^@|^\d/i.test(l) && l.toLowerCase() !== display_name.toLowerCase());
            if (lines.length) bio = lines.slice(0, 4).join(' · ');
        } catch (e) { /* ignore */ }
        if (!bio) {
            const m = ogDesc.match(/on Instagram:\s*[“"]?(.+?)[”"]?\s*$/i);
            if (m) bio = m[1].trim();
        }

        const verified = !!document.querySelector('header svg[aria-label="Verified"]');
        const external_link =
            document.querySelector('header a[href*="l.instagram.com"]')?.href ||
            document.querySelector('header a[target="_blank"][rel]')?.href || '';

        // Captions + image urls from visible post thumbnails (alt text carries captions).
        const captions = [], imageUrls = [];
        document.querySelectorAll('main img, article img').forEach(im => {
            const src = im.currentSrc || im.src || '';
            if (src && !src.startsWith('data:')) imageUrls.push(src);
            const alt = (im.getAttribute('alt') || '').trim();
            if (alt && alt.length > 14 && !/profile photo/i.test(alt)) captions.push(alt);
        });
        const uniq = (a, n) => [...new Set(a)].slice(0, n);

        return {
            handle,
            source_url: location.href,
            account: {
                display_name, bio, followers, following, posts_count,
                avatar_url: ogImage || '', external_link, verified,
                raw_og_description: ogDesc || '',
            },
            captured_captions: uniq(captions, 40),
            captured_image_urls: uniq(imageUrls, 40),
        };
    }

    // --- Floating capture button ---
    const personaFab = document.createElement('div');
    personaFab.className = 'ss-persona-fab';
    personaFab.innerHTML = `
      <button class="ss-persona-btn" type="button">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="8" r="4"></circle><path d="M4 21c0-4 4-6 8-6s8 2 8 6"></path>
        </svg><span class="ss-persona-label">Build persona</span>
      </button>
      <a class="ss-persona-open" target="_blank" rel="noopener">Open Darpan ↗</a>`;
    document.body.appendChild(personaFab);
    const personaBtn = personaFab.querySelector('.ss-persona-btn');
    const personaLabel = personaFab.querySelector('.ss-persona-label');
    const personaOpen = personaFab.querySelector('.ss-persona-open');

    async function buildPersona() {
        const handle = detectedHandle();
        if (!handle) return;
        personaBtn.classList.remove('error', 'success');
        personaBtn.classList.add('loading');
        personaLabel.textContent = 'Reading profile…';
        try {
            const payload = scrapeInstagramProfile(handle);
            const r = await fetch(PERSONA_INGEST_URL, {
                method: 'POST', mode: 'cors',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const data = await r.json();
            personaBtn.classList.remove('loading');
            personaBtn.classList.add('success');
            const have = data.matched_image_count || 0;
            personaLabel.textContent = `✓ @${data.handle}${have ? ` · ${have} of ours` : ''}`;
            personaOpen.href = `${DASHBOARD_URL}#${data.handle}`;
            personaOpen.style.display = 'inline';
        } catch (err) {
            console.error('Darpan persona error:', err);
            personaBtn.classList.remove('loading');
            personaBtn.classList.add('error');
            personaLabel.textContent = '✗ Failed (backend?)';
        }
    }
    personaBtn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); buildPersona(); });

    let lastFabHandle = null;
    function refreshPersonaFab() {
        const handle = isInstagram() ? detectedHandle() : null;
        if (handle) {
            if (handle !== lastFabHandle) {
                personaBtn.classList.remove('loading', 'success', 'error');
                personaLabel.textContent = `Build persona · @${handle}`;
                personaOpen.style.display = 'none';
            }
            personaFab.classList.add('visible');
        } else {
            personaFab.classList.remove('visible');
        }
        lastFabHandle = handle;
    }

    // Instagram is a SPA: post-author links load after the route changes, so poll
    // both the path and the detected handle (not just the path).
    let lastPath = location.pathname;
    setInterval(() => {
        if (location.pathname !== lastPath || (isInstagram() && detectedHandle() !== lastFabHandle)) {
            lastPath = location.pathname;
            refreshPersonaFab();
        }
    }, 800);
    window.addEventListener('popstate', refreshPersonaFab);
    refreshPersonaFab();

    console.log('🜂 Alexia + Aletheia + Darpan loaded — unconcealers (Save · Brainstorm · Split · Persona)!');
})();
