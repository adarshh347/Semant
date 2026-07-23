import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { useRegionState } from './regionStore';
import { normalizeMark, _resetMarkIds } from '../differential/visualMarks';
import { quarantineSuggestion, canCiteMark } from '../differential/suggestionQuarantine';

/**
 * CIRCUIT-001 P2E — visual_marks durability round-trip (contract v2 §7.3).
 *
 * The whole point of the gate: a beautiful brush must not evaporate on reload, and a
 * suggestion must never reach the database. This mounts the real store hook, drives a
 * PATCH, captures the body, and simulates a reload by hydrating a fresh store from the
 * echoed post.
 */

const committedMark = (rid) => normalizeMark({
    type: 'brush_field', role: 'light_field', source: 'user', status: 'committed',
    geometry: { kind: 'soft_mask' }, linked_ground_ids: [rid],
}, { now: 'T' });

const confirmedMark = () => normalizeMark({
    type: 'region_mask', source: 'user_confirmed', status: 'committed', derived_from: 'vm_s',
    geometry: { kind: 'raster_mask', mask_ref: { region_id: 'reg_1', geometry_rev: 1 } },
    provenance: { model: 'sam2' },
}, { now: 'T' });

const suggestion = () => quarantineSuggestion(normalizeMark({
    type: 'brush_field', role: 'shadow_field', source: 'system', geometry: { kind: 'soft_mask' },
}, { now: 'T' }));

// A harness that mounts the hook and hands the live store out through a ref.
function Harness({ post, onPost, storeRef }) {
    const store = useRegionState(post, onPost);
    storeRef.current = store;
    return null;
}

let container;
let root;
let patchBodies;

function stubFetch() {
    patchBodies = [];
    globalThis.fetch = vi.fn(async (url, opts = {}) => {
        const u = String(url);
        if (opts.method === 'PATCH' && /\/posts\/[^/]+$/.test(u)) {
            const body = JSON.parse(opts.body);
            patchBodies.push(body);
            // Echo: the persisted post is the old post plus what was PATCHed (Mongo $set).
            return { ok: true, json: async () => ({ ...lastPost, ...body }) };
        }
        return { ok: true, json: async () => ({}) };
    });
}

let lastPost;

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

describe('committed marks survive PATCH → reload', () => {
    it('hydrates a stored committed mark on load', async () => {
        const stored = committedMark('gnd_1');
        const store = await mountStore({ id: 'p1', visual_marks: [stored] });
        expect(store.current.visualMarks).toHaveLength(1);
        expect(store.current.visualMarks[0].id).toBe(stored.id);
    });

    it('persists only committed/superseded — a suggestion never reaches the PATCH body', async () => {
        const store = await mountStore({ id: 'p1', visual_marks: [] });
        const keep = committedMark('gnd_1');
        const sug = suggestion();
        await act(async () => {
            store.current.addVisualMark(keep, { save: false });
            store.current.addVisualMark(sug, { save: false });
        });
        await act(async () => { await store.current.persistMeta(); });

        expect(patchBodies).toHaveLength(1);
        const written = patchBodies[0].visual_marks;
        expect(written.map((m) => m.id)).toEqual([keep.id]);   // suggestion excluded
        expect(written.some((m) => m.status === 'suggested')).toBe(false);
    });

    it('reload hydrates the committed mark and NOT the suggestion, with lineage + provenance intact', async () => {
        // Round 1: add a confirmed region_mask + a suggestion, persist.
        const store1 = await mountStore({ id: 'p1', visual_marks: [] });
        const confirmed = confirmedMark();
        await act(async () => {
            store1.current.addVisualMark(confirmed, { save: false });
            store1.current.addVisualMark(suggestion(), { save: false });
            await store1.current.persistMeta();
        });
        const persistedPost = { id: 'p1', visual_marks: patchBodies[0].visual_marks };

        // Round 2: a FRESH store hydrates from the persisted post (the reload).
        await act(async () => { root.unmount(); });
        root = createRoot(container);
        const store2 = await mountStore(persistedPost);

        const marks = store2.current.visualMarks;
        expect(marks).toHaveLength(1);
        const m = marks[0];
        expect(m.source).toBe('user_confirmed');       // provenance survived
        expect(m.derived_from).toBe('vm_s');           // lineage survived
        expect(m.provenance.model).toBe('sam2');       // the model's part survived
        expect(canCiteMark(m)).toBe(true);             // still citable evidence
        expect(marks.some((x) => x.status === 'suggested')).toBe(false);
    });

    it('a stored mark that no longer validates is dropped on hydrate, not trusted', async () => {
        const store = await mountStore({
            id: 'p1',
            visual_marks: [
                committedMark('gnd_1'),
                { type: 'brush_field', role: 'not_a_role', status: 'committed' },   // invalid
                { type: 'brush_field', role: 'fold', status: 'draft', geometry: { kind: 'polygon' } }, // not persistable
            ],
        });
        // Only the one valid committed mark survives.
        expect(store.current.visualMarks).toHaveLength(1);
        expect(store.current.visualMarks[0].role).toBe('light_field');
    });
});

describe('the store API', () => {
    it('visualMarksForGround returns marks linked to that ground', async () => {
        const store = await mountStore({ id: 'p1', visual_marks: [] });
        const a = committedMark('gnd_1');
        const b = committedMark('gnd_2');
        await act(async () => {
            store.current.addVisualMark(a, { save: false });
            store.current.addVisualMark(b, { save: false });
        });
        expect(store.current.visualMarksForGround('gnd_1').map((m) => m.id)).toEqual([a.id]);
    });

    it('updateVisualMark promoting a draft to committed schedules a write', async () => {
        const store = await mountStore({ id: 'p1', visual_marks: [] });
        const draft = normalizeMark({ type: 'brush_field', role: 'fold', status: 'draft', geometry: { kind: 'polygon' } }, { now: 'T' });
        await act(async () => { store.current.addVisualMark(draft, { save: false }); });
        // Promote it — this is the moment it becomes persistable.
        await act(async () => { store.current.updateVisualMark(draft.id, { status: 'committed' }); await store.current.persistMeta(); });
        expect(patchBodies.at(-1).visual_marks.map((m) => m.status)).toEqual(['committed']);
    });
});
