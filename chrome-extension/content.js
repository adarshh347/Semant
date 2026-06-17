// Sharirasutra Chrome Extension - Content Script
// Adds a "Save to Sharirasutra" button when hovering over images.
// Uses document-level pointer tracking + elementsFromPoint so it works on sites
// (Instagram, Pinterest, etc.) that cover images with transparent overlays, and
// on infinite-scroll feeds that swap images in/out of the DOM.

(function () {
    'use strict';

    // Configuration
    const API_URL = 'http://localhost:5007/api/v1/posts/upload-from-url';
    const MIN_IMAGE_SIZE = 100; // Minimum image dimension in pixels

    // Create the save button element
    const saveBtn = document.createElement('button');
    saveBtn.className = 'sharirasutra-save-btn';
    saveBtn.innerHTML = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
      <polyline points="17 21 17 13 7 13 7 21"></polyline>
      <polyline points="7 3 7 8 15 8"></polyline>
    </svg>
    <span>Save to Sharirasutra</span>
  `;
    document.body.appendChild(saveBtn);

    let currentImage = null;
    let hideTimeout = null;
    let rafScheduled = false;

    // Check if an element is a valid image worth saving
    function isValidImage(img) {
        if (!img || img.tagName !== 'IMG') return false;

        const width = img.naturalWidth || img.width;
        const height = img.naturalHeight || img.height;
        if (width < MIN_IMAGE_SIZE || height < MIN_IMAGE_SIZE) return false;

        const src = img.currentSrc || img.src;
        if (!src || src.startsWith('data:image/svg') || src.includes('blank.gif')) return false;

        return true;
    }

    // Find the topmost valid <img> at a point, looking THROUGH overlay elements.
    // This is the key to supporting Instagram et al.
    function imageAtPoint(x, y) {
        const stack = document.elementsFromPoint(x, y);
        for (const el of stack) {
            if (el === saveBtn || saveBtn.contains(el)) continue; // ignore our own button
            if (el.tagName === 'IMG' && isValidImage(el)) return el;
        }
        // Fallback: an overlay container that wraps a single image
        for (const el of stack) {
            if (el === saveBtn || saveBtn.contains(el)) continue;
            const img = el.querySelector && el.querySelector('img');
            if (img && isValidImage(img)) return img;
        }
        return null;
    }

    function getImageUrl(img) {
        return img.currentSrc || img.src || img.dataset.src || '';
    }

    // Position the button at the top-right of the image
    function positionButton(img) {
        const rect = img.getBoundingClientRect();
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
        saveBtn.style.top = `${rect.top + scrollTop + 10}px`;
        saveBtn.style.left = `${rect.right + scrollLeft - saveBtn.offsetWidth - 10}px`;
    }

    function showButton(img) {
        if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null; }
        if (currentImage && currentImage !== img) {
            currentImage.classList.remove('sharirasutra-hover-highlight');
        }
        currentImage = img;
        img.classList.add('sharirasutra-hover-highlight');
        positionButton(img);
        saveBtn.classList.add('visible');
        saveBtn.classList.remove('success', 'error', 'saving');
        saveBtn.querySelector('span').textContent = 'Save to Sharirasutra';
    }

    function hideButton() {
        if (hideTimeout) clearTimeout(hideTimeout);
        hideTimeout = setTimeout(() => {
            if (currentImage) currentImage.classList.remove('sharirasutra-hover-highlight');
            saveBtn.classList.remove('visible');
            currentImage = null;
        }, 300);
    }

    // Document-level pointer tracking (throttled to one check per animation frame)
    function onPointerMove(e) {
        if (rafScheduled) return;
        rafScheduled = true;
        const x = e.clientX, y = e.clientY;
        requestAnimationFrame(() => {
            rafScheduled = false;

            // Keep the button alive while the cursor is over it
            const top = document.elementFromPoint(x, y);
            if (top && (top === saveBtn || saveBtn.contains(top))) {
                if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null; }
                return;
            }

            const img = imageAtPoint(x, y);
            if (img) {
                if (img !== currentImage) showButton(img);
                else if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null; }
            } else if (currentImage) {
                hideButton();
            }
        });
    }

    document.addEventListener('mousemove', onPointerMove, { passive: true });
    // Reposition / dismiss on scroll (feeds move under the cursor)
    window.addEventListener('scroll', () => {
        if (currentImage) positionButton(currentImage);
    }, { passive: true });

    // Save image to Sharirasutra
    async function saveImage() {
        if (!currentImage) return;

        const imageUrl = getImageUrl(currentImage);
        if (!imageUrl) { return; }

        saveBtn.classList.add('saving');
        saveBtn.querySelector('span').textContent = 'Saving...';

        try {
            const response = await fetch(API_URL, {
                method: 'POST',
                mode: 'cors',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image_url: imageUrl,
                    source_url: location.href,
                    general_tags: []
                })
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            await response.json();

            saveBtn.classList.remove('saving');
            saveBtn.classList.add('success');
            saveBtn.querySelector('span').textContent = '✓ Saved!';
        } catch (error) {
            console.error('Sharirasutra save error:', error);
            saveBtn.classList.remove('saving');
            saveBtn.classList.add('error');
            saveBtn.querySelector('span').textContent = '✗ Failed';
        }
    }

    saveBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        saveImage();
    });
    saveBtn.addEventListener('mouseenter', () => {
        if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null; }
    });
    saveBtn.addEventListener('mouseleave', hideButton);

    console.log('🎨 Sharirasutra Image Saver loaded (overlay-aware)!');
})();
