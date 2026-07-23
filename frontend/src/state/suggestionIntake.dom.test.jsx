import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { useRegionState } from './regionStore';
import { _resetMarkIds, persistableMarks } from '../differential/visualMarks';
import { canCiteMark } from '../differential/suggestionQuarantine';

/**
 * CIRCUIT-001 P4-A — store intake of producer suggestions (contract v3 §8.4).
 *
 * The three guarantees: idempotent (a producer re-run does not duplicate), fail-closed
 * (invalid descriptors dropped), and NEVER persisted (a suggestion cannot reach the PATCH
 * body from either direction). This mounts the real store hook and drives `ingestSuggestions`.
 */

const labelDescriptor = (cid) => ({
    producer: 'semantic_read', type: 'region_mask', role: null, label: `label ${cid}`,
    source_ref: cid, geometry: { kind: 'region_ref', region_ref: { region_id: cid } },
    linked_ground_ids: [],
    provenance: { model: 'vlm', adapter: 'semantic_pass', run_id: 'run_sem', producer: 'semantic_read' },
});
const badDescriptor = () => ({
    producer: 'semantic_read', type: 'relation_mark', role: 'friendship', source_ref: 'x',
    geometry: { kind: 'derived' }, provenance: { producer: 'semantic_read', run_id: 'r' },
});

function Harness({ post, onPost, storeRef }) {
    const store = useRegionState(post, onPost);
    storeRef.current = store;
    return null;
}

let container, root, patchBodies, lastPost;

function stubFetch() {
    patchBodies = [];
    globalThis.fetch = vi.fn(async (url, opts = {}) => {
        const u = String(url);
        if (opts.method === 'PATCH' && /\/posts\/[^/]+$/.test(u)) {
            const body = JSON.parse(opts.body);
            patchBodies.push(body);
            return { ok: true, json: async () => ({ ...lastPost, ...body }) };
        }
        return { ok: true, json: async () => ({}) };
    });
}

async function mountStore(post) {
    lastPost = post;
    const storeRef = { current: null };
    await act(async () => {
        root.render(<Harness post={post} onPost={(p) => { lastPost = p; }} storeRef={storeRef} />);
    });
    return storeRef;
}

beforeEach(() => {
    _resetMarkIds();
    stubFetch();
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
    vi.restoreAllMocks();
});

describe('ingestSuggestions — producer output onto the quarantine layer', () => {
    it('ingests valid descriptors as uncitable suggestions, drops the invalid', async () => {
        const store = await mountStore({ id: 'p1', visual_marks: [] });
        await act(async () => {
            store.current.ingestSuggestions([labelDescriptor('reg_1'), badDescriptor(), labelDescriptor('reg_2')]);
        });
        expect(store.current.visualMarks).toHaveLength(2);              // bad one dropped
        expect(store.current.visualMarks.every((m) => !canCiteMark(m))).toBe(true);
        expect(store.current.visualMarks.every((m) => m.source === 'model_suggested')).toBe(true);
    });

    it('is IDEMPOTENT — re-running a producer replaces, never duplicates', async () => {
        const store = await mountStore({ id: 'p1', visual_marks: [] });
        await act(async () => { store.current.ingestSuggestions([labelDescriptor('reg_1'), labelDescriptor('reg_2')]); });
        await act(async () => { store.current.ingestSuggestions([labelDescriptor('reg_1'), labelDescriptor('reg_2')]); });
        expect(store.current.visualMarks).toHaveLength(2);             // same two, not four
    });

    it('NEVER persists a suggestion — the PATCH body excludes every ingested mark', async () => {
        const store = await mountStore({ id: 'p1', visual_marks: [] });
        await act(async () => {
            store.current.ingestSuggestions(Array.from({ length: 20 }, (_, i) => labelDescriptor(`reg_${i}`)));
        });
        await act(async () => { await store.current.persistMeta(); });
        const written = patchBodies.at(-1)?.visual_marks || [];
        expect(persistableMarks(store.current.visualMarks)).toHaveLength(0);
        expect(written).toHaveLength(0);                               // nothing durable to write
    });

    it('does not survive a reload by STORAGE — a fresh store from the persisted post has no suggestions', async () => {
        const store1 = await mountStore({ id: 'p1', visual_marks: [] });
        await act(async () => {
            store1.current.ingestSuggestions([labelDescriptor('reg_1')]);
            await store1.current.persistMeta();
        });
        const persistedPost = { id: 'p1', visual_marks: patchBodies.at(-1)?.visual_marks || [] };
        // The reload: unmount and hydrate a FRESH store from the persisted post.
        await act(async () => { root.unmount(); });
        root = createRoot(container);
        const store2 = await mountStore(persistedPost);
        expect(store2.current.visualMarks).toHaveLength(0);           // re-derivation, not storage
    });
});
