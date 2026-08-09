/**
 * THE SHARED UPLOADER — the contract HARNESS-003C repaired.
 *
 * The 002R rehearsal's sixth tree cause, in two halves: the success callback ran after a FAILED
 * request, and it ran with NOTHING. The first made a failure look like a success everywhere in the
 * app; the second is why an inquiry could not upload an image and then read it.
 *
 * Every test here is about the boundary between "the request succeeded" and "the callback fired".
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import axios from 'axios';

import UploadForm from './UploadForm.jsx';

let container;
let root;

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});

afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
    vi.restoreAllMocks();
});

const $ = (sel) => container.querySelector(sel);
const text = () => container.textContent || '';

const POST = { id: 'p_new', photo_url: 'https://res.cloudinary.com/x/image/upload/v1/p_new.jpg' };

async function mount(props = {}) {
    await act(async () => { root.render(<UploadForm {...props} />); });
}

/** A file input cannot be typed into; jsdom lets us define `files` directly. */
async function choose(n = 1) {
    const input = $('input[type="file"]');
    const files = Array.from({ length: n }, (_, i) =>
        new File(['x'], `img${i}.jpg`, { type: 'image/jpeg' }));
    Object.defineProperty(input, 'files', { value: files, configurable: true });
    await act(async () => { input.dispatchEvent(new Event('change', { bubbles: true })); });
}

const submit = async () => {
    await act(async () => {
        $('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    });
};

// ── success ─────────────────────────────────────────────────────────────────

describe('a successful upload', () => {
    it('calls back with the created post, as an array', async () => {
        vi.spyOn(axios, 'post').mockResolvedValue({ data: POST });
        const onUploadSuccess = vi.fn();
        await mount({ onUploadSuccess });
        await choose(1);
        await submit();

        // `response_model=Post` on the single route, `List[Post]` on bulk. Normalised to an array
        // so no caller has to branch.
        expect(onUploadSuccess).toHaveBeenCalledTimes(1);
        expect(onUploadSuccess).toHaveBeenCalledWith([POST]);
        expect(axios.post.mock.calls[0][0]).toMatch(/\/api\/v1\/posts\/$/);
    });

    it('calls back with every post from a bulk upload', async () => {
        const posts = [POST, { id: 'p_two', photo_url: 'u2' }];
        vi.spyOn(axios, 'post').mockResolvedValue({ data: posts });
        const onUploadSuccess = vi.fn();
        await mount({ onUploadSuccess });
        await choose(2);
        await submit();

        expect(onUploadSuccess).toHaveBeenCalledWith(posts);
        expect(axios.post.mock.calls[0][0]).toMatch(/\/bulk-upload$/);
    });

    it('broadcasts the created posts with the requestId it was given', async () => {
        // The inquiry workbench does not mount this form — it lives elsewhere in the shell — and
        // the id is what lets it tell an upload IT asked for from one the person started in the
        // Archive.
        vi.spyOn(axios, 'post').mockResolvedValue({ data: POST });
        const heard = [];
        const listener = (e) => heard.push(e.detail);
        window.addEventListener('semant:posts-created', listener);

        await mount({ requestId: 'iq_upload_7' });
        await choose(1);
        await submit();
        window.removeEventListener('semant:posts-created', listener);

        expect(heard).toEqual([{ posts: [POST], requestId: 'iq_upload_7' }]);
    });

    it('clears the form so the next upload starts clean', async () => {
        vi.spyOn(axios, 'post').mockResolvedValue({ data: POST });
        await mount({ onUploadSuccess: () => {} });
        await choose(1);
        await submit();
        expect($('input[type="text"]').value).toBe('');
        expect($('[data-upload-error="true"]')).toBeNull();
    });
});

// ── failure ─────────────────────────────────────────────────────────────────

describe('a failed upload', () => {
    it('does NOT call the success callback', async () => {
        // The defect: the callback lived after the try/catch, so a failed request closed the
        // dialog, invalidated the cache and raised a green "Image added" toast.
        vi.spyOn(axios, 'post').mockRejectedValue(new Error('Network Error'));
        const onUploadSuccess = vi.fn();
        await mount({ onUploadSuccess });
        await choose(1);
        await submit();

        expect(onUploadSuccess).not.toHaveBeenCalled();
    });

    it('does not broadcast a creation that did not happen', async () => {
        vi.spyOn(axios, 'post').mockRejectedValue(new Error('Network Error'));
        const heard = [];
        const listener = (e) => heard.push(e.detail);
        window.addEventListener('semant:posts-created', listener);
        await mount({ requestId: 'iq_upload_9' });
        await choose(1);
        await submit();
        window.removeEventListener('semant:posts-created', listener);
        expect(heard).toEqual([]);
    });

    it('shows the reason in the form and keeps the files for a retry', async () => {
        vi.spyOn(axios, 'post').mockRejectedValue({
            response: { data: { detail: 'that file is not an image' } },
        });
        await mount({ onUploadSuccess: () => {} });
        await choose(1);
        await submit();

        const err = $('[data-upload-error="true"]');
        expect(err.textContent).toBe('that file is not an image');
        expect(err.getAttribute('role')).toBe('alert');
        // the files are still chosen, so the retry costs nothing
        expect($('input[type="file"]').files).toHaveLength(1);
        expect($('button[type="submit"]').disabled).toBe(false);
    });

    it('uses no alert() anywhere', async () => {
        // A modal alert blocks the page, cannot be inspected, and vanishes on acknowledgement
        // leaving the form looking exactly as it did before.
        const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
        vi.spyOn(axios, 'post').mockRejectedValue(new Error('boom'));
        await mount({ onUploadSuccess: () => {} });
        await choose(1);
        await submit();
        expect(alertSpy).not.toHaveBeenCalled();
    });

    it('refuses an empty submission in the form rather than in a dialog', async () => {
        const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
        const post = vi.spyOn(axios, 'post');
        const onUploadSuccess = vi.fn();
        await mount({ onUploadSuccess });
        await submit();

        expect(text()).toContain('Choose at least one image first.');
        expect(post).not.toHaveBeenCalled();
        expect(onUploadSuccess).not.toHaveBeenCalled();
        expect(alertSpy).not.toHaveBeenCalled();
    });

    it('treats a 2xx that carried no post as a failure to report, not a silent success', async () => {
        vi.spyOn(axios, 'post').mockResolvedValue({ data: {} });
        const onUploadSuccess = vi.fn();
        await mount({ onUploadSuccess });
        await choose(1);
        await submit();

        // Calling back with `[]` would read to a selector as "nothing chosen" rather than as
        // "something went wrong".
        expect(onUploadSuccess).not.toHaveBeenCalled();
        expect($('[data-upload-error="true"]').textContent).toMatch(/returned no post/i);
    });
});

// ── the callers that ignore the payload ─────────────────────────────────────

describe('existing callers are unaffected', () => {
    it('a zero-argument callback still works', async () => {
        // `UploadDialog` — and therefore the whole Gallery path — passes `() => {...}` and reads
        // nothing. Widening the contract must not require it to change.
        vi.spyOn(axios, 'post').mockResolvedValue({ data: POST });
        let ran = 0;
        await mount({ onUploadSuccess: () => { ran += 1; } });
        await choose(1);
        await submit();
        expect(ran).toBe(1);
    });

    it('no callback at all is not an error', async () => {
        vi.spyOn(axios, 'post').mockResolvedValue({ data: POST });
        await mount({});
        await choose(1);
        await submit();
        expect($('[data-upload-error="true"]')).toBeNull();
    });
});

// ── accessibility of the repaired form ──────────────────────────────────────

describe('the form itself', () => {
    it('labels every input and names the form', async () => {
        await mount({});
        expect($('form').getAttribute('aria-label')).toBe('Upload images');
        for (const input of container.querySelectorAll('input')) {
            expect(container.querySelector(`label[for="${input.id}"]`)).toBeTruthy();
        }
    });

    it('disables itself while the request is in flight', async () => {
        let release;
        vi.spyOn(axios, 'post').mockImplementation(
            () => new Promise((r) => { release = () => r({ data: POST }); }));
        await mount({ onUploadSuccess: () => {} });
        await choose(1);
        await submit();

        expect($('button[type="submit"]').textContent).toBe('Uploading…');
        expect($('button[type="submit"]').disabled).toBe(true);
        expect($('input[type="file"]').disabled).toBe(true);

        await act(async () => { release(); });
        expect($('button[type="submit"]').disabled).toBe(false);
    });
});
