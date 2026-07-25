import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import useProduceField from './useProduceField';
import { API_URL } from '../config/api';

/**
 * CIRCUIT-001 P6-C — the generic producer-invocation hook.
 *
 * The three properties: real suggestions enter the SAME quarantine path (store.ingestSuggestions);
 * an available-but-empty run is an honest 'empty' (NOT an error, and nothing ingested); an
 * unavailable model is 'unavailable'. A transport error is 'error'. Mounts the real hook.
 */

let container, root, storeRef, hookRef, fetchCalls;

function Harness({ postId, store }) {
    hookRef.current = useProduceField(postId, store);
    return null;
}

async function mount({ postId = 'p1' } = {}) {
    storeRef = { ingestSuggestions: vi.fn() };
    hookRef = { current: null };
    await act(async () => { root.render(<Harness postId={postId} store={storeRef} />); });
    return hookRef;
}

function stubFetch(responder) {
    fetchCalls = [];
    globalThis.fetch = vi.fn(async (url, opts = {}) => {
        fetchCalls.push({ url: String(url), opts });
        return responder(String(url), opts);
    });
}

const ok = (body) => ({ ok: true, status: 200, json: async () => body });

const descriptor = (over = {}) => ({
    producer: 'negative_space', type: 'brush_field', role: 'negative_space',
    label: 'negative space', source_ref: 'reg_1',
    geometry: { kind: 'soft_mask', strokes: [{ points: [[0.2, 0.2]], radius: 0.05, strength: 0.8, op: 'add' }] },
    linked_ground_ids: [], provenance: { run_id: 'run_x', producer: 'negative_space' }, ...over,
});

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

describe('useProduceField — the field-producer trigger', () => {
    it('ingests real suggestions into the SAME quarantine path and goes ready', async () => {
        stubFetch(() => ok({ producer: 'negative_space', suggestions: [descriptor()], run_id: 'run_x', available: true, status: 'ready' }));
        const h = await mount();
        await act(async () => { await h.current.produce({ producer: 'negative_space', regionId: 'reg_1' }); });
        expect(storeRef.ingestSuggestions).toHaveBeenCalledTimes(1);
        expect(storeRef.ingestSuggestions.mock.calls[0][0]).toHaveLength(1);
        expect(h.current.status).toBe('ready');
        expect(h.current.lastRun).toMatchObject({ producer: 'negative_space', count: 1 });
        // it POSTed the generic endpoint with the producer + region
        const body = JSON.parse(fetchCalls[0].opts.body);
        expect(fetchCalls[0].url).toBe(`${API_URL}/api/v1/posts/p1/produce-field`);
        expect(body).toMatchObject({ producer: 'negative_space', region_id: 'reg_1' });
    });

    it('an available-but-empty run is an honest empty — nothing ingested, no error', async () => {
        stubFetch(() => ok({ producer: 'negative_space', suggestions: [], run_id: 'r', available: true, status: 'empty' }));
        const h = await mount();
        await act(async () => { await h.current.produce({ producer: 'negative_space', regionId: 'bare' }); });
        expect(h.current.status).toBe('empty');
        expect(storeRef.ingestSuggestions).not.toHaveBeenCalled();
        expect(h.current.error).toBe('');
    });

    it('an unavailable model surfaces as unavailable, not an error', async () => {
        stubFetch(() => ok({ producer: 'material_field', suggestions: [], run_id: 'r', available: false, status: 'unavailable' }));
        const h = await mount();
        await act(async () => { await h.current.produce({ producer: 'material_field', regionId: 'reg_1', seedPoint: [0.2, 0.2] }); });
        expect(h.current.status).toBe('unavailable');
        expect(storeRef.ingestSuggestions).not.toHaveBeenCalled();
    });

    it('a transport failure (unknown producer → 400) becomes error', async () => {
        stubFetch(() => ({ ok: false, status: 400, json: async () => ({ detail: 'unknown producer' }) }));
        const h = await mount();
        await act(async () => { await h.current.produce({ producer: 'nope', regionId: 'reg_1' }); });
        expect(h.current.status).toBe('error');
        expect(storeRef.ingestSuggestions).not.toHaveBeenCalled();
    });

    it('unload POSTs the release endpoint (hand the GPU slot back)', async () => {
        stubFetch(() => ok({ unloaded: true }));
        const h = await mount();
        await act(async () => { await h.current.unload(); });
        expect(fetchCalls[0].url).toBe(`${API_URL}/api/v1/posts/produce-field/unload`);
        expect(fetchCalls[0].opts.method).toBe('POST');
    });
});
