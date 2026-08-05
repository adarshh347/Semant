/**
 * ATLAS L1 — the pure half of curation.
 *
 * One property matters more than the rest and most of this file is about it: **a corpus is a
 * SEQUENCE, not a set.** Nothing here sorts, click order survives every gesture, and the two
 * things that could quietly destroy an order — a re-pick and a reorder — are pinned against doing
 * each other's job.
 */
import { describe, it, expect } from 'vitest';

import {
    MAX_IMAGES, corpusSummary, imagesFrom, move, saveBlocker, toggle, walkRows,
} from './corpusDocument.js';

describe('picking the walk', () => {
    it('keeps click order, which IS the walk', () => {
        let sel = [];
        ['p3', 'p1', 'p2'].forEach((p) => { sel = toggle(sel, p); });
        expect(sel).toEqual(['p3', 'p1', 'p2']);
    });

    it('un-picks in place rather than reshuffling', () => {
        // A curator un-picking the third of five expects four, not a new order.
        const sel = toggle(['p1', 'p2', 'p3'], 'p2');
        expect(sel).toEqual(['p1', 'p3']);
    });

    it('re-picking after un-picking appends, because that is a new decision', () => {
        expect(toggle(toggle(['p1', 'p2'], 'p1'), 'p1')).toEqual(['p2', 'p1']);
    });
});

describe('reordering the walk', () => {
    it('moves one image and leaves membership alone', () => {
        const before = ['p1', 'p2', 'p3', 'p4'];
        const after = move(before, 'p4', -2);
        expect(after).toEqual(['p1', 'p4', 'p2', 'p3']);
        expect([...after].sort()).toEqual([...before].sort());
    });

    it('does not fall off either end', () => {
        expect(move(['p1', 'p2'], 'p1', -1)).toEqual(['p1', 'p2']);
        expect(move(['p1', 'p2'], 'p2', 1)).toEqual(['p1', 'p2']);
    });

    it('ignores an image the walk does not hold', () => {
        expect(move(['p1', 'p2'], 'ghost', 1)).toEqual(['p1', 'p2']);
    });
});

describe('what a save sends', () => {
    it('carries the order and each image\'s reason for its place', () => {
        const body = imagesFrom(['p2', 'p1'], { p2: '  the colonnade  ', p1: '' });
        expect(body).toEqual([
            { post_id: 'p2', note: 'the colonnade' },
            { post_id: 'p1', note: '' },
        ]);
    });

    it('never sends anything about what an image SHOWS', () => {
        // A corpus references posts by id. A cached url or count would go stale the moment a post
        // was re-uploaded, in a document that looks authoritative.
        const [row] = imagesFrom(['p1'], { p1: 'why' });
        expect(Object.keys(row).sort()).toEqual(['note', 'post_id']);
    });
});

describe('why a walk cannot be saved yet', () => {
    it('says the reason rather than presenting a dead button', () => {
        expect(saveBlocker([], 'x')).toMatch(/Pick the images/);
        expect(saveBlocker(['p1'], '  ')).toMatch(/Give the walk a name/);
        expect(saveBlocker(Array.from({ length: MAX_IMAGES + 1 }, (_, i) => `p${i}`), 'x'))
            .toMatch(/at most/);
    });

    it('is empty when the walk is ready', () => {
        expect(saveBlocker(['p1'], 'the approach')).toBe('');
    });
});

describe('reading a saved walk', () => {
    it('counts images and notes separately', () => {
        // An unexplained walk is still a walk; folding the note count into the total would make
        // it read as a defect rather than a prompt.
        const s = corpusSummary({ id: 'c1', title: 'the approach', images: [
            { post_id: 'p1', note: 'first' }, { post_id: 'p2', note: '' }] });
        expect(s).toEqual({ id: 'c1', title: 'the approach', count: 2, noted: 1, why: '' });
    });

    it('falls back to the id when a walk was never named', () => {
        expect(corpusSummary({ id: 'c1', images: [] }).title).toBe('c1');
    });

    it('keeps an unreadable image IN the walk, saying why', () => {
        // "This image has no percepts" and "this image could not be loaded" are different facts
        // about a corpus, and a walk that shortened itself would lie about its own extent.
        const rows = walkRows({ images: [
            { post_id: 'p1', position: 0, readable: true, image_ref: 'u', committed: 3 },
            { post_id: 'ghost', position: 1, readable: false,
                unreadable_reason: 'post:ghost could not be read' }] });
        expect(rows.map((r) => r.postId)).toEqual(['p1', 'ghost']);
        expect(rows[1].readable).toBe(false);
        expect(rows[1].unreadableReason).toContain('could not be read');
        expect(rows[0].committed).toBe(3);
    });

    it('preserves order in the rows it draws', () => {
        const rows = walkRows({ images: [
            { post_id: 'p3', position: 0 }, { post_id: 'p1', position: 1 }] });
        expect(rows.map((r) => r.postId)).toEqual(['p3', 'p1']);
    });
});
