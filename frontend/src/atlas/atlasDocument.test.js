/**
 * ATLAS C1 — the pure half of the canvas.
 *
 * Two properties are worth pinning here, and they are the same property twice: a save carries
 * POSITION ONLY, and nothing derives meaning from where a node sits.
 *
 * Every fixture is synthetic.
 */
import { describe, it, expect } from 'vitest';

import {
    ATLAS_NODE_TYPE, arrangementFrom, finite, flowNodesFromView, perceptSummary,
    positionsOf, refusalLines,
} from './atlasDocument.js';

const view = (over = {}) => ({
    id: 'atlas_1',
    title: 'a canvas',
    nodes: [
        { node_id: 'n0', post_id: 'p1', x: 0, y: 0, w: 420, h: 320, readable: true,
            image_ref: 'https://example.invalid/1.jpg', title: 'one',
            grounds: [{ id: 'g1' }], regions: [], marks: [], percepts: [], withheld: 0 },
        { node_id: 'n1', post_id: 'p2', x: 540, y: 0, w: 420, h: 320, readable: true,
            image_ref: 'https://example.invalid/2.jpg', title: 'two',
            grounds: [], regions: [], marks: [], percepts: [], withheld: 0 },
    ],
    edges: [],
    unreadable: [],
    ...over,
});

const flowNode = (id, x, y) => ({ id, position: { x, y } });

// ── the view becomes nodes ───────────────────────────────────────────────────

describe('flowNodesFromView', () => {
    it('gives every image a node, in corpus order', () => {
        const nodes = flowNodesFromView(view());
        expect(nodes.map((n) => n.data.postId)).toEqual(['p1', 'p2']);
        expect(nodes.every((n) => n.type === ATLAS_NODE_TYPE)).toBe(true);
    });

    it('carries the ledger’s percepts as render input', () => {
        expect(flowNodesFromView(view()).at(0).data.grounds).toHaveLength(1);
    });

    it('connects nothing — an edge is a percept, and that is C3', () => {
        expect(flowNodesFromView(view()).every((n) => n.connectable === false)).toBe(true);
    });

    it('keeps an unreadable image on the canvas with its reason', () => {
        const v = view({ nodes: [{ node_id: 'n0', post_id: 'ghost', x: 0, y: 0,
            readable: false, unreadable_reason: 'post:ghost could not be read' }] });
        const node = flowNodesFromView(v).at(0);
        expect(node.data.readable).toBe(false);
        expect(node.data.unreadableReason).toMatch(/could not be read/);
    });

    it('survives a position that is not a number rather than rendering nowhere', () => {
        const v = view({ nodes: [{ node_id: 'n0', post_id: 'p1', x: 'over there', y: null }] });
        expect(flowNodesFromView(v).at(0).position).toEqual({ x: 0, y: 0 });
    });
});

describe('finite', () => {
    it.each([[1, 1], ['2.5', 2.5], [NaN, null], [Infinity, null], ['nope', null], [null, null]])(
        '%s → %s', (input, expected) => expect(finite(input)).toBe(expected));
});

// ── what a save carries ──────────────────────────────────────────────────────

describe('arrangementFrom', () => {
    it('sends only the nodes that moved', () => {
        const saved = { n0: { x: 0, y: 0 }, n1: { x: 540, y: 0 } };
        const patches = arrangementFrom([flowNode('n0', 0, 0), flowNode('n1', 900, 40)], saved);
        expect(patches).toEqual([{ node_id: 'n1', x: 900, y: 40 }]);
    });

    it('sends nothing when a drag ends where it started', () => {
        const saved = { n0: { x: 10, y: 10 } };
        expect(arrangementFrom([flowNode('n0', 10.2, 9.9)], saved)).toEqual([]);
    });

    it('sends every node the server has never seen', () => {
        expect(arrangementFrom([flowNode('n0', 1, 2)], {})).toHaveLength(1);
    });

    it('carries position and nothing else — never the image a node points at', () => {
        const patches = arrangementFrom(
            [{ id: 'n0', position: { x: 5, y: 6 }, data: { postId: 'p1', grounds: [{ id: 'g' }] } }],
            {});
        expect(Object.keys(patches[0]).sort()).toEqual(['node_id', 'x', 'y']);
    });

    it('drops a node whose position went non-finite instead of saving it there', () => {
        expect(arrangementFrom([flowNode('n0', NaN, 3)], {})).toEqual([]);
    });
});

describe('positionsOf', () => {
    it('is the shape a save diffs against', () => {
        expect(positionsOf([flowNode('n0', 1, 2)])).toEqual({ n0: { x: 1, y: 2 } });
    });
});

// ── nothing is derived from where a node sits ────────────────────────────────

describe('proximity asserts nothing', () => {
    it('two nodes on top of each other produce no relation, edge or grouping', () => {
        const v = view({ nodes: [
            { node_id: 'n0', post_id: 'p1', x: 100, y: 100, readable: true, grounds: [] },
            { node_id: 'n1', post_id: 'p2', x: 101, y: 100, readable: true, grounds: [] },
        ] });
        const nodes = flowNodesFromView(v);
        expect(v.edges).toEqual([]);
        // No node knows about any other node — there is nowhere for an inferred relation to live.
        nodes.forEach((n) => {
            expect(Object.keys(n.data)).not.toContain('near');
            expect(Object.keys(n.data)).not.toContain('related');
            expect(Object.keys(n.data)).not.toContain('group');
        });
    });
});

// ── counting, and what is withheld ───────────────────────────────────────────

describe('perceptSummary', () => {
    it('counts what is actually drawn', () => {
        expect(perceptSummary({ grounds: [1, 2], marks: [3], regions: [] }).drawn).toBe(3);
    });

    it('never folds a quarantined suggestion into the count', () => {
        const s = perceptSummary({ grounds: [1], marks: [], regions: [], withheld: 2 });
        expect(s.drawn).toBe(1);
        expect(s.withheld).toBe(2);
    });

    it('says what it withheld, in words, and where to go', () => {
        expect(perceptSummary({ withheld: 1 }).withheldNote).toMatch(/1 suggestion not shown/);
        expect(perceptSummary({ withheld: 3 }).withheldNote).toMatch(/Differential/);
    });

    it('says nothing when there is nothing withheld', () => {
        expect(perceptSummary({ grounds: [1] }).withheldNote).toBe('');
    });
});

// ── refusal renders ──────────────────────────────────────────────────────────

describe('refusalLines', () => {
    it('turns a stale node into a sentence a person can act on', () => {
        expect(refusalLines([{ node_id: 'n7', reason: 'unknown_node' }])[0])
            .toMatch(/no longer on this Atlas — not moved/);
    });

    it('says a bad position was not saved', () => {
        expect(refusalLines([{ node_id: 'n0', reason: 'bad_position' }])[0])
            .toMatch(/not moved/);
    });

    it('falls back to the detail rather than swallowing an unknown reason', () => {
        expect(refusalLines([{ node_id: 'n0', reason: 'novel', detail: 'because' }])[0])
            .toContain('because');
    });

    it('is empty when nothing was refused', () => {
        expect(refusalLines([])).toEqual([]);
        expect(refusalLines(null)).toEqual([]);
    });
});
