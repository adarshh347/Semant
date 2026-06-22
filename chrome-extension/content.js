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

    toolbar.appendChild(brainstormBtn);
    toolbar.appendChild(saveBtn);
    toolbar.appendChild(splitBtn);
    document.body.appendChild(toolbar);

    // ---- Analysis panel --------------------------------------------------------
    const panel = document.createElement('div');
    panel.className = 'sharirasutra-panel';
    document.body.appendChild(panel);

    let currentImage = null;
    let currentVideo = null;
    let hideTimeout = null;
    let rafScheduled = false;

    // Brainstorm dialogue state
    let bsImageUrl = null;   // image being interpreted
    let bsAnswers = [];      // [{question, choice}] accumulated across rounds
    let bsRound = 0;

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

    function videoAtPoint(x, y) {
        // First try the hit-test stack (cheap).
        const stack = document.elementsFromPoint(x, y);
        for (const node of stack) {
            if (node === toolbar || toolbar.contains(node) || node === panel || panel.contains(node)) continue;
            if (node.tagName === 'VIDEO' && isValidVideo(node)) return node;
            const v = node.querySelector && node.querySelector('video');
            if (v && isValidVideo(v)) return v;
        }
        // Geometric fallback: many sites (Instagram reels) set pointer-events:none on
        // the <video>, so elementsFromPoint EXCLUDES it. Scan real <video> rects instead.
        let best = null, bestArea = Infinity;
        const vids = document.getElementsByTagName('video');
        for (const v of vids) {
            if (!isValidVideo(v)) continue;
            const r = v.getBoundingClientRect();
            if (r.width < 1 || r.height < 1) continue;
            if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) {
                const area = r.width * r.height;     // prefer the smallest enclosing video
                if (area < bestArea) { bestArea = area; best = v; }
            }
        }
        return best;
    }

    function setToolbarMode(type) {
        const isVideo = type === 'video';
        brainstormBtn.style.display = isVideo ? 'none' : '';
        saveBtn.style.display = isVideo ? 'none' : '';
        splitBtn.style.display = isVideo ? '' : 'none';
    }

    function showTarget(el, type) {
        if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null; }
        const prev = currentImage || currentVideo;
        if (prev && prev !== el) prev.classList.remove('sharirasutra-hover-highlight');
        currentImage = type === 'image' ? el : null;
        currentVideo = type === 'video' ? el : null;
        el.classList.add('sharirasutra-hover-highlight');
        setToolbarMode(type);
        positionToolbar(el);
        toolbar.classList.add('visible');
        if (type === 'image') {
            saveBtn.classList.remove('success', 'error', 'saving');
            saveBtn.querySelector('span').textContent = 'Save';
        } else {
            splitBtn.classList.remove('success', 'error', 'saving');
            splitBtn.querySelector('span').textContent = 'Split → Save';
        }
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

    function onPointerMove(e) {
        if (rafScheduled) return;
        rafScheduled = true;
        const x = e.clientX, y = e.clientY;
        requestAnimationFrame(() => {
            rafScheduled = false;
            const top = document.elementFromPoint(x, y);
            if (top && (top === toolbar || toolbar.contains(top) || top === panel || panel.contains(top))) {
                if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null; }
                return;
            }
            const video = videoAtPoint(x, y);
            if (video) {
                if (video !== currentVideo) showTarget(video, 'video');
                else if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null; }
                return;
            }
            const img = imageAtPoint(x, y);
            if (img) {
                if (img !== currentImage) showTarget(img, 'image');
                else if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null; }
            } else if (currentImage || currentVideo) {
                hideToolbar();
            }
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
                body: JSON.stringify({ image_url: imageUrl, source_url: location.href, general_tags: [] })
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
    function clearPanel() { while (panel.firstChild) panel.removeChild(panel.firstChild); }

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
    function seekVideo(video, t) {
        return new Promise((resolve) => {
            let done = false;
            const finish = () => { if (done) return; done = true; video.removeEventListener('seeked', finish); resolve(); };
            video.addEventListener('seeked', finish);
            setTimeout(finish, 1500); // fallback if 'seeked' never fires (streams)
            try { video.currentTime = t; } catch (e) { finish(); }
        });
    }

    async function splitVideo() {
        const video = currentVideo;
        if (!video) return;
        const duration = video.duration;
        if (!duration || !isFinite(duration) || duration <= 0) {
            splitBtn.classList.add('error');
            splitBtn.querySelector('span').textContent = '✗ No duration';
            return;
        }
        // Rate: ~3 frames/sec, clamped to 8–60 evenly-spaced frames.
        const n = Math.max(8, Math.min(60, Math.round(duration * 3)));
        const wasPaused = video.paused, prevTime = video.currentTime, wasMuted = video.muted;
        video.muted = true;
        try { video.pause(); } catch (e) {}

        const restore = () => {
            try { video.currentTime = prevTime; } catch (e) {}
            video.muted = wasMuted;
            if (!wasPaused) { try { video.play(); } catch (e) {} }
        };

        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        splitBtn.classList.remove('success', 'error');
        splitBtn.classList.add('saving');
        const frames = [];

        for (let i = 0; i < n; i++) {
            splitBtn.querySelector('span').textContent = `Reading ${i + 1}/${n}…`;
            await seekVideo(video, duration * ((i + 0.5) / n));
            await new Promise(r => requestAnimationFrame(r));
            const vw = video.videoWidth, vh = video.videoHeight;
            if (!vw || !vh) continue;
            canvas.width = vw; canvas.height = vh;
            try {
                ctx.drawImage(video, 0, 0, vw, vh);
                frames.push(canvas.toDataURL('image/jpeg', 0.85));
            } catch (err) {
                console.error('Alexia: canvas tainted (cross-origin video, no CORS):', err);
                restore();
                splitBtn.classList.remove('saving'); splitBtn.classList.add('error');
                splitBtn.querySelector('span').textContent = '✗ Protected video';
                return;
            }
        }

        restore();
        splitBtn.classList.remove('saving');
        splitBtn.querySelector('span').textContent = 'Split → Save';
        if (frames.length) {
            renderFrameReview(frames);
        } else {
            splitBtn.classList.add('error');
            splitBtn.querySelector('span').textContent = '✗ No frames';
        }
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

    // Review grid: all frames selected by default; tap to deselect; then save kept ones.
    function renderFrameReview(frames) {
        const items = frames.map(url => ({ url, selected: true }));
        clearPanel();
        panel.appendChild(frameHeader('Choose frames'));

        const body = el('div', 'al-body al-frames-body');
        body.appendChild(el('div', 'al-frames-hint', `${frames.length} frames · tap to deselect`));
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
            save.textContent = c ? `Save ${c} frame${c > 1 ? 's' : ''}` : 'Save (none)';
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
            saveFrames(items.filter(i => i.selected).map(i => i.url), save);
        });

        updateBar();
        openPanel();
    }

    async function saveFrames(urls, btn) {
        if (!urls.length) return;
        btn.disabled = true;
        let saved = 0;
        for (let i = 0; i < urls.length; i++) {
            btn.textContent = `Saving ${i + 1}/${urls.length}…`;
            try {
                const r = await fetch(SAVE_URL, {
                    method: 'POST', mode: 'cors',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image_url: urls[i], source_url: location.href, general_tags: ['video-frame'] })
                });
                if (r.ok) saved++;
            } catch (e) { /* keep going */ }
        }
        btn.classList.add(saved ? 'al-done' : 'al-fail');
        btn.textContent = saved ? `✓ Saved ${saved}` : '✗ Failed';
    }

    saveBtn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); saveImage(); });
    brainstormBtn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); brainstormImage(); });
    splitBtn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); splitVideo(); });

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
        const handle = instagramProfileHandle();
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

    function refreshPersonaFab() {
        const handle = isInstagram() ? instagramProfileHandle() : null;
        if (handle) {
            if (!personaFab.classList.contains('visible')) {
                personaBtn.classList.remove('loading', 'success', 'error');
                personaLabel.textContent = `Build persona · @${handle}`;
                personaOpen.style.display = 'none';
            }
            personaFab.classList.add('visible');
        } else {
            personaFab.classList.remove('visible');
        }
    }

    // Instagram is a SPA — watch for client-side route changes.
    let lastPath = location.pathname;
    setInterval(() => {
        if (location.pathname !== lastPath) { lastPath = location.pathname; refreshPersonaFab(); }
    }, 1000);
    window.addEventListener('popstate', refreshPersonaFab);
    refreshPersonaFab();

    console.log('🜂 Alexia + Aletheia + Darpan loaded — unconcealers (Save · Brainstorm · Split · Persona)!');
})();
