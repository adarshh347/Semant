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
    ATLAS_MODES, ATLAS_NODE_TYPE, MACHINE_READ_INTENTION, MODE_CANVAS, MODE_LIGHT_TABLE,
    arrangementFrom, finite, flowNodesFromView, isMode, notePatchesFrom, notesOf, perceptSummary,
    positionsOf, refusalLines, withNoteAdded, withNoteEdit,
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

    // C2 — the way into the Differential rides on `data`, which is how React Flow reaches a
    // custom node at all.
    it('passes the way in to every readable image', () => {
        const onOpen = () => {};
        expect(flowNodesFromView(view(), { onOpen }).every((n) => n.data.onOpen === onOpen))
            .toBe(true);
    });

    it('withholds it from an image that could not be read', () => {
        const v = view({ nodes: [{ node_id: 'n0', post_id: 'ghost', x: 0, y: 0,
            readable: false, unreadable_reason: 'post:ghost could not be read' }] });
        expect(flowNodesFromView(v, { onOpen: () => {} }).at(0).data.onOpen).toBe(null);
    });

    it('is null when nobody offered one', () => {
        expect(flowNodesFromView(view()).at(0).data.onOpen).toBe(null);
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

// ── T1: the modes ────────────────────────────────────────────────────────────

describe('the modes', () => {
    it('are a closed, tiny list — a mode is a lens, not an app', () => {
        expect(ATLAS_MODES.map((m) => m.key)).toEqual([MODE_CANVAS, MODE_LIGHT_TABLE]);
    });

    it('recognises only the modes that exist', () => {
        expect(isMode(MODE_LIGHT_TABLE)).toBe(true);
        expect(isMode('gallery')).toBe(false);
        expect(isMode(undefined)).toBe(false);
    });

    it('each says what it is for, so the control is not two unexplained words', () => {
        expect(ATLAS_MODES.every((m) => m.label && m.hint)).toBe(true);
    });
});

// ── T1: the author-notes slot ────────────────────────────────────────────────

const withNotes = (notes) => view({ nodes: [
    { node_id: 'n0', post_id: 'p1', x: 0, y: 0, readable: true, notes },
] });

describe('notes on the way in', () => {
    it('carries the writer’s own lines onto the node', () => {
        const node = flowNodesFromView(withNotes([{ note_id: 'a', text: 'the light argues' }]))[0];
        expect(node.data.notes).toEqual([{ note_id: 'a', text: 'the light argues' }]);
    });

    it('is an empty list when nothing has been written', () => {
        expect(flowNodesFromView(view())[0].data.notes).toEqual([]);
    });

    it('keeps the notes of an image that could not be read', () => {
        // A note is about the WRITER's thinking, not the ledger's contents. Losing it because a
        // photograph went missing would delete the one thing the ledger never held.
        const v = view({ nodes: [{ node_id: 'n0', post_id: 'ghost', x: 0, y: 0, readable: false,
            unreadable_reason: 'gone', notes: [{ note_id: 'a', text: 'still mine' }] }] });
        expect(flowNodesFromView(v)[0].data.notes).toHaveLength(1);
    });

    it('never lets a note arrive carrying anything but an id and text', () => {
        const v = withNotes([{ note_id: 'a', text: 'hm', box: [0, 0, 1, 1],
            epistemic_status: 'grounded' }]);
        expect(Object.keys(flowNodesFromView(v)[0].data.notes[0]).sort())
            .toEqual(['note_id', 'text']);
    });

    it('is never counted as a percept', () => {
        const node = flowNodesFromView(withNotes([{ note_id: 'a', text: 'x' }]))[0];
        expect(perceptSummary(node.data).drawn).toBe(0);
    });
});

describe('editing notes', () => {
    const notes = [{ note_id: 'a', text: 'one' }, { note_id: 'b', text: 'two' }];

    it('rewrites the one that was typed in', () => {
        expect(withNoteEdit(notes, 'b', 'two, revised'))
            .toEqual([{ note_id: 'a', text: 'one' }, { note_id: 'b', text: 'two, revised' }]);
    });

    it('deletes a note the writer emptied — taking it back is the same gesture', () => {
        expect(withNoteEdit(notes, 'a', '   ')).toEqual([{ note_id: 'b', text: 'two' }]);
    });

    it('adds an empty slot to write into', () => {
        expect(withNoteAdded(notes, 'c').at(-1)).toEqual({ note_id: 'c', text: '' });
    });

    it('leaves an abandoned empty slot out of the save', () => {
        const nodes = [{ id: 'n0', data: { notes: withNoteAdded([], 'c') } }];
        expect(notePatchesFrom(nodes, { n0: [] })).toEqual([]);
    });
});

describe('notePatchesFrom', () => {
    const node = (id, notes) => ({ id, data: { notes } });

    it('sends only the images whose notes changed', () => {
        const saved = { n0: [{ note_id: 'a', text: 'one' }], n1: [] };
        const patches = notePatchesFrom(
            [node('n0', [{ note_id: 'a', text: 'one' }]), node('n1', [{ note_id: 'b', text: 'new' }])],
            saved);
        expect(patches).toEqual([{ node_id: 'n1', notes: [{ note_id: 'b', text: 'new' }] }]);
    });

    it('sends nothing when a note was retyped to exactly what it said', () => {
        expect(notePatchesFrom([node('n0', [{ note_id: 'a', text: 'same' }])],
            { n0: [{ note_id: 'a', text: 'same' }] })).toEqual([]);
    });

    it('notices a deletion, not only an edit', () => {
        expect(notePatchesFrom([node('n0', [])], { n0: [{ note_id: 'a', text: 'gone' }] }))
            .toEqual([{ node_id: 'n0', notes: [] }]);
    });

    it('carries the notes and nothing else — never the image, never a position', () => {
        const patches = notePatchesFrom(
            [{ id: 'n0', position: { x: 5, y: 6 },
                data: { notes: [{ note_id: 'a', text: 'x' }], postId: 'p1', grounds: [{ id: 'g' }] } }],
            {});
        expect(Object.keys(patches[0]).sort()).toEqual(['node_id', 'notes']);
        expect(Object.keys(patches[0].notes[0]).sort()).toEqual(['note_id', 'text']);
    });

    it('is what an arrangement save is diffed against, separately', () => {
        // The two saves share no state: `notesOf` and `positionsOf` read different halves, so
        // neither gesture can perform the other's.
        const nodes = [{ id: 'n0', position: { x: 1, y: 2 }, data: { notes: [] } }];
        expect(notesOf(nodes)).toEqual({ n0: [] });
        expect(positionsOf(nodes)).toEqual({ n0: { x: 1, y: 2 } });
        expect(arrangementFrom(nodes, { n0: { x: 1, y: 2 } })).toEqual([]);
    });
});

// ── T1: the machine read ─────────────────────────────────────────────────────

describe('the machine read', () => {
    it('is offered on a readable image', () => {
        const onMachineRead = () => {};
        expect(flowNodesFromView(view(), { onMachineRead })[0].data.onMachineRead)
            .toBe(onMachineRead);
    });

    it('is withheld from an image that could not be read', () => {
        // A model asked to look at nothing. The affordance would be a dead end.
        const v = view({ nodes: [{ node_id: 'n0', post_id: 'ghost', x: 0, y: 0, readable: false }] });
        expect(flowNodesFromView(v, { onMachineRead: () => {} })[0].data.onMachineRead).toBe(null);
    });

    it('asks for an act by name, in the curator’s own vocabulary', () => {
        // It is handed to the Director exactly as a typed intention would be — no private API,
        // no new actuator, nothing the Orchestrate bar could not have been told.
        expect(typeof MACHINE_READ_INTENTION).toBe('string');
        expect(MACHINE_READ_INTENTION.trim().length).toBeGreaterThan(0);
    });
});

// ── T1: refusals from the notes save render too ──────────────────────────────

describe('refusalLines, for notes', () => {
    it('says a note was not saved rather than letting it vanish', () => {
        expect(refusalLines([{ node_id: 'n0', reason: 'bad_note', detail: '1 note had no text' }])[0])
            .toMatch(/1 note had no text — not saved/);
    });

    it('says when the slot was full', () => {
        expect(refusalLines([{ node_id: 'n0', reason: 'too_many_notes',
            detail: 'an image holds at most 12 notes; 3 not saved' }])[0])
            .toMatch(/3 not saved/);
    });
});
