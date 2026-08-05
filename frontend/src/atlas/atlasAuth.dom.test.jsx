/**
 * ATLAS — a refused key is not an empty shelf.
 *
 * The Atlas index tolerated every failure on the way in, for a good reason badly applied: a fresh
 * install genuinely has no canvases and no images, so a failed list was treated as an empty one.
 * But a 401 means the canvases EXIST and this browser was not allowed to see them, and rendering
 * that as "No images loaded." tells a curator their work is gone.
 *
 * These pin the distinction, and that what a person is told names the thing to change.
 *
 * Every fixture is synthetic.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import AtlasPage from './AtlasPage.jsx';
import { AtlasRequestError, atlasService, authMessage, isAuthFailure } from './atlasService.js';

if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
}

let container; let root;
const mount = async (node) => { await act(async () => { root.render(node); }); };

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

const res = (status, body = {}) => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
});

// ── the client tells refusal from failure ───────────────────────────────────

describe('the Atlas client', () => {
    it('carries the status, so a caller can tell 401 from 404 from empty', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue(res(401));
        await expect(atlasService.list()).rejects.toMatchObject({
            name: 'AtlasRequestError', status: 401,
        });
    });

    it('names the key and what to change, rather than printing a status code', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue(res(401));
        await expect(atlasService.view('atlas_1')).rejects.toThrow(/VITE_API_KEY/);
        // The old message. True, and it helped nobody.
        await expect(atlasService.view('atlas_1')).rejects.not.toThrow(/Failed to load atlas view/);
    });

    it('still says plainly what failed when the failure was not the door', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue(res(404));
        await expect(atlasService.view('gone')).rejects.toThrow(/Failed to load atlas view \(404\)/);
    });

    it('knows which failures are the door', () => {
        expect(isAuthFailure(new AtlasRequestError('x', 401))).toBe(true);
        expect(isAuthFailure(new AtlasRequestError('x', 403))).toBe(true);
        expect(isAuthFailure(new AtlasRequestError('x', 404))).toBe(false);
        expect(isAuthFailure(new Error('offline'))).toBe(false);
    });

    it('says something different for a key that is refused than for one that is not allowed', () => {
        expect(authMessage(401)).toMatch(/did not accept/);
        expect(authMessage(403)).toMatch(/not allowed/);
    });
});

// ── the index renders the refusal ───────────────────────────────────────────

const index = () => (
    <MemoryRouter initialEntries={['/atlas']}>
        <AtlasPage />
    </MemoryRouter>
);

describe('the Atlas index, when the key is refused', () => {
    it('says the key was refused instead of showing an empty picker', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue(res(401));
        await mount(index());
        const alert = container.querySelector('[role="alert"]');
        expect(alert).toBeTruthy();
        expect(alert.textContent).toMatch(/did not accept this browser’s API key/);
        expect(alert.textContent).toMatch(/VITE_API_KEY/);
    });

    it('does not claim the curator has no images when it was never told', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue(res(401));
        await mount(index());
        expect(container.textContent).not.toMatch(/No images loaded/);
        expect(container.textContent).toMatch(/could not be listed/);
    });

    it('still shows a genuinely empty install as empty, with no alarm', async () => {
        // The reason the failures were tolerated in the first place — it has to keep working.
        vi.spyOn(globalThis, 'fetch').mockResolvedValue(res(200, { posts: [], atlases: [] }));
        await mount(index());
        expect(container.querySelector('[role="alert"]')).toBe(null);
        expect(container.textContent).toMatch(/No images loaded/);
    });

    it('stays quiet when the backend is merely unreachable', async () => {
        // Offline is not a refusal. There is nothing to fix in a key here.
        vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));
        await mount(index());
        expect(container.querySelector('[role="alert"]')).toBe(null);
    });

    it('asks the posts route with its trailing slash, so no redirect carries the key', async () => {
        // FastAPI answers 307 without it, and a redirect is where an intermediary is most likely
        // to drop a custom header.
        const fetchSpy = vi.spyOn(globalThis, 'fetch')
            .mockResolvedValue(res(200, { posts: [], atlases: [] }));
        await mount(index());
        const urls = fetchSpy.mock.calls.map((c) => String(c[0]));
        expect(urls.some((u) => /\/api\/v1\/posts\/\?/.test(u))).toBe(true);
        expect(urls.some((u) => /\/api\/v1\/posts\?/.test(u))).toBe(false);
    });
});
