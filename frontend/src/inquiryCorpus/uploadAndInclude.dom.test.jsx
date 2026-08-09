/**
 * INQUIRY CORPUS — upload an image and read it in the same breath.
 *
 * The round trip between this button and the shell's one uploader, and the correlation id that
 * stops it from stealing somebody else's upload.
 */
import React, { act, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import axios from 'axios';

import UploadAndInclude from './UploadAndInclude.jsx';
import InquiryEntry from '../inquiryWorkbench/InquiryEntry.jsx';
import UploadForm from '../components/UploadForm.jsx';
import { createMockCorpusClient } from './corpusClient.js';

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
const $$ = (sel) => [...container.querySelectorAll(sel)];
const click = async (el) => { await act(async () => { el.click(); }); };

const NEW_POST = {
    id: 'p_uploaded',
    photo_url: 'https://res.cloudinary.com/x/image/upload/v1/p_uploaded.jpg',
    text_blocks: [{ content: 'A new drawing' }],
};

const PAGES = [{
    posts: [
        { id: 'p1', photo_url: 'u1', text_blocks: [{ content: 'Image 1' }] },
        { id: 'p2', photo_url: 'u2', text_blocks: [{ content: 'Image 2' }] },
    ],
    total_pages: 1,
}];

// ── the button on its own ───────────────────────────────────────────────────

describe('the upload-and-include button', () => {
    it('opens the shell\'s one uploader rather than building a second one', async () => {
        const opened = [];
        const listener = (e) => opened.push(e.detail);
        window.addEventListener('semant:open-upload', listener);

        const onUploaded = vi.fn();
        await act(async () => { root.render(<UploadAndInclude onUploaded={onUploaded} />); });
        await click($('[data-upload-and-include="true"]'));
        window.removeEventListener('semant:open-upload', listener);

        // ⌘K and the Archive's Upload button both reach `UploadDialog` through this event.
        expect(opened).toHaveLength(1);
        expect(opened[0].requestId).toMatch(/^iq_upload_/);
    });

    it('ignores an upload it did not ask for', async () => {
        // Without the correlation id, opening the Archive's own Upload button while an inquiry
        // draft is on screen would silently add those images to the inquiry.
        const onUploaded = vi.fn();
        await act(async () => { root.render(<UploadAndInclude onUploaded={onUploaded} />); });
        await click($('[data-upload-and-include="true"]'));

        await act(async () => {
            window.dispatchEvent(new CustomEvent('semant:posts-created', {
                detail: { posts: [NEW_POST], requestId: 'someone_elses_upload' },
            }));
        });
        expect(onUploaded).not.toHaveBeenCalled();
    });

    it('ignores a creation event when it is not waiting for one at all', async () => {
        const onUploaded = vi.fn();
        await act(async () => { root.render(<UploadAndInclude onUploaded={onUploaded} />); });
        await act(async () => {
            window.dispatchEvent(new CustomEvent('semant:posts-created', {
                detail: { posts: [NEW_POST], requestId: '' },
            }));
        });
        expect(onUploaded).not.toHaveBeenCalled();
    });

    it('reports an upload that finished but produced nothing to include', async () => {
        const onUploaded = vi.fn();
        let captured = '';
        await act(async () => {
            root.render(<UploadAndInclude
                onUploaded={onUploaded}
                openUpload={(id) => { captured = id; }}
            />);
        });
        await click($('[data-upload-and-include="true"]'));
        await act(async () => {
            window.dispatchEvent(new CustomEvent('semant:posts-created', {
                detail: { posts: [], requestId: captured },
            }));
        });
        expect(onUploaded).not.toHaveBeenCalled();
        expect($('[data-upload-note="true"]').textContent).toMatch(/returned no post to include/i);
    });

    it('says the draft is safe, because that is the question a person has', async () => {
        await act(async () => { root.render(<UploadAndInclude onUploaded={() => {}} />); });
        expect(container.textContent).toMatch(/question and the images you have already chosen stay/i);
    });
});

// ── the whole round trip, through the real form ─────────────────────────────

describe('uploading from the inquiry, end to end', () => {
    /** The entry and the shell's uploader mounted as siblings, as they are in the app. */
    function Shell({ corpusClient, onStart = () => {} }) {
        const [requestId, setRequestId] = useState('');
        return (
            <>
                <InquiryEntry
                    corpusClient={corpusClient}
                    onStart={onStart}
                    openUpload={setRequestId}
                />
                {requestId ? <UploadForm requestId={requestId} /> : null}
            </>
        );
    }

    async function open() {
        const client = createMockCorpusClient({ pages: PAGES });
        await act(async () => { root.render(<Shell corpusClient={client} />); });
        return client;
    }

    async function uploadOne(result) {
        const spy = vi.spyOn(axios, 'post');
        if (result instanceof Error) spy.mockRejectedValue(result);
        else spy.mockResolvedValue({ data: result });

        await click($('[data-upload-and-include="true"]'));
        const input = $('input[type="file"]');
        Object.defineProperty(input, 'files', {
            value: [new File(['x'], 'new.jpg', { type: 'image/jpeg' })], configurable: true,
        });
        await act(async () => { input.dispatchEvent(new Event('change', { bubbles: true })); });
        await act(async () => {
            $('form[aria-label="Upload images"]')
                .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        });
    }

    it('selects the new post and shows it in the grid, keeping what was already chosen', async () => {
        await open();
        await click($('[data-post-id="p1"]'));
        const prompt = $('.iw-prompt');
        await act(async () => {
            Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')
                .set.call(prompt, 'what changed between these?');
            prompt.dispatchEvent(new Event('input', { bubbles: true }));
        });

        await uploadOne(NEW_POST);

        // selected, and the earlier choice survived
        expect($$('.ic-tray-item').map((n) => n.dataset.trayId)).toEqual(['p1', 'p_uploaded']);
        expect($('[data-selected-count]').textContent).toBe('2 selected');
        // visible in the grid too: a new post lands at the top of page 1, so waiting for a refetch
        // would leave the person's own upload missing from the list they are choosing from
        expect($$('.ic-tile').map((t) => t.dataset.postId))
            .toEqual(['p_uploaded', 'p1', 'p2']);
        // and the draft is untouched
        expect($('.iw-prompt').value).toBe('what changed between these?');
    });

    it('starts the inquiry with the uploaded id among the rest', async () => {
        const onStart = vi.fn();
        const client = createMockCorpusClient({ pages: PAGES });
        await act(async () => { root.render(<Shell corpusClient={client} onStart={onStart} />); });
        await click($('[data-post-id="p2"]'));
        await uploadOne(NEW_POST);
        const prompt = $('.iw-prompt');
        await act(async () => {
            Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')
                .set.call(prompt, 'q');
            prompt.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await click($('.iw-start'));

        expect(onStart.mock.calls[0][0].imageIds).toEqual(['p2', 'p_uploaded']);
    });

    it('a failed upload changes nothing about the selection or the draft', async () => {
        await open();
        await click($('[data-post-id="p1"]'));
        await uploadOne(new Error('Network Error'));

        expect($('[data-upload-error="true"]').textContent).toBe('Network Error');
        expect($$('.ic-tray-item').map((n) => n.dataset.trayId)).toEqual(['p1']);
        expect($('[data-selected-count]').textContent).toBe('1 selected');
        expect($('[data-upload-note="true"]')).toBeNull();
    });

    it('does not duplicate the uploaded post when its page later loads', async () => {
        // Posts sort `_id` descending, so the upload arrives at the top of page 1 on the next
        // fetch — and the injected copy and the fetched one are the same image.
        const client = createMockCorpusClient({
            pages: [
                { posts: PAGES[0].posts, total_pages: 2 },
                { posts: [NEW_POST], total_pages: 2 },
            ],
        });
        await act(async () => { root.render(<Shell corpusClient={client} />); });
        await uploadOne(NEW_POST);
        expect($$('.ic-tile')).toHaveLength(3);

        await click($('.ic-more'));
        expect($$('.ic-tile').map((t) => t.dataset.postId))
            .toEqual(['p_uploaded', 'p1', 'p2']);
    });
});
