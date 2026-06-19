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

    toolbar.appendChild(brainstormBtn);
    toolbar.appendChild(saveBtn);
    document.body.appendChild(toolbar);

    // ---- Analysis panel --------------------------------------------------------
    const panel = document.createElement('div');
    panel.className = 'sharirasutra-panel';
    document.body.appendChild(panel);

    let currentImage = null;
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

    function showToolbar(img) {
        if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null; }
        if (currentImage && currentImage !== img) currentImage.classList.remove('sharirasutra-hover-highlight');
        currentImage = img;
        img.classList.add('sharirasutra-hover-highlight');
        positionToolbar(img);
        toolbar.classList.add('visible');
        saveBtn.classList.remove('success', 'error', 'saving');
        saveBtn.querySelector('span').textContent = 'Save';
    }

    function hideToolbar() {
        if (hideTimeout) clearTimeout(hideTimeout);
        hideTimeout = setTimeout(() => {
            if (currentImage) currentImage.classList.remove('sharirasutra-hover-highlight');
            toolbar.classList.remove('visible');
            currentImage = null;
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
            const img = imageAtPoint(x, y);
            if (img) {
                if (img !== currentImage) showToolbar(img);
                else if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null; }
            } else if (currentImage) {
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

    saveBtn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); saveImage(); });
    brainstormBtn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); brainstormImage(); });

    console.log('🎨 Sharirasutra Image Saver loaded (Save + Brainstorm, overlay-aware)!');
})();
