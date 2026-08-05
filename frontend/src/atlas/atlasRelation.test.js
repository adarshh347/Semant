/**
 * ATLAS C3 — the pure half of relation edges.
 *
 * What matters here is the pair of distinctions the surface would be dishonest without:
 *
 *   a relation is not a binding, and cannot be styled like one   → §1
 *   a refused line is not an edge, and is never persisted        → §2
 *   an edge whose relation left the ledger still renders, saying so → §3
 *
 * Every fixture is synthetic and shaped exactly like `atlas_relation.hydrate_edge`'s output.
 */
import { describe, it, expect } from 'vitest';

import {
    EDGE_RELATION, REFUSED_EDGE_PREFIX, connectionRefusal, epistemicLabel, isRefusedEdgeId,
    refusalLine, refusedEdge, relationEdges, relationLabel, relationSummary,
} from './atlasRelation.js';
import { bindingEdges } from './atlasPlan.js';

const anEdge = (over = {}) => ({
    edge_id: 'edge_1', kind: 'relation', mark_id: 'vm_rel_1',
    source_node: 'n0', target_node: 'n1', spans: ['p1', 'p2'],
    created_at: '2026-08-05T00:00:00Z',
    live: true, role: 'kinship', label: 'echoes', epistemic: 'interpretive',
    source_ref: 'p1:m1→p2:m2', missing_reason: null,
    sources: [{ post_id: 'p1', mark_ref: 'm1' }, { post_id: 'p2', mark_ref: 'm2' }],
    ...over,
});

const aView = (over = {}) => ({ id: 'atlas_1', nodes: [], edges: [anEdge()], ...over });

// ── 1. a relation is not a binding ──────────────────────────────────────────

describe('a relation edge', () => {
    it('runs between two images and says what the relation IS', () => {
        const [edge] = relationEdges(aView());
        expect(edge.id).toBe('edge_1');
        expect(edge.source).toBe('n0');
        expect(edge.target).toBe('n1');
        expect(edge.data.kind).toBe(EDGE_RELATION);
        expect(edge.label).toBe('kinship · interpretive');
    });

    it('carries the epistemic kind the LEDGER holds, never one decided here', () => {
        expect(relationEdges(aView({ edges: [anEdge({ epistemic: 'measured' })] }))[0].label)
            .toBe('kinship · measured');
        // an unknown kind reads as `uncertain` rather than as nothing at all
        expect(epistemicLabel('nonsense')).toBe('uncertain');
    });

    it('carries both sides, which is what makes a cross-image claim checkable', () => {
        const [edge] = relationEdges(aView());
        expect(edge.data.sources.map((s) => s.post_id)).toEqual(['p1', 'p2']);
        expect(edge.data.spans).toEqual(['p1', 'p2']);
    });

    it('is ARROWED, because a relation is not its own converse', () => {
        // `compare_views` records a left and a right: "the façade prepares the rotunda" and its
        // reverse are different claims, and an unarrowed line would show them as the same one.
        expect(relationEdges(aView())[0].markerEnd).toEqual({ type: 'arrowclosed' });
    });

    it('cannot be confused with a C4 binding — different class, marker and word', () => {
        const [relation] = relationEdges(aView());
        const [binding] = bindingEdges({ claims: [{
            claim_id: 'c0',
            percepts: [{ step_id: 's0', actuator: 'rhythm', function: 'support',
                epistemic: 'measured', node_id: 'n0', bound: true, spans_corpus: false }],
        }] });

        expect(relation.className).toContain('atlas-relation');
        expect(binding.className).toContain('atlas-edge');
        expect(relation.className).not.toContain('atlas-edge ');
        expect(binding.className).not.toContain('atlas-relation');
        expect(binding.markerEnd).toBeUndefined();          // bindings do not point
        expect(relation.data.kind).toBe('relation');
        expect(binding.data.kind).toBe('binding');
    });
});

// ── 2. a refused line is not an edge ────────────────────────────────────────

describe('a refusal', () => {
    const refused = {
        reason: 'gate_refused', source_node: 'n0', target_node: 'n1',
        detail: "missing_input: 'compare_views' needs 2× mark and nothing in this plan provides it",
    };

    it('is drawn on the line that was attempted, carrying the gate\'s own sentence', () => {
        // A refusal about THIS pair belongs on the line between THIS pair, where the writer is
        // already looking — a message in a corner reads as being about the canvas.
        const edge = refusedEdge(refused);
        expect(edge.source).toBe('n0');
        expect(edge.target).toBe('n1');
        expect(edge.label).toContain('needs 2× mark');
    });

    it('carries an id that cannot collide with a stored edge', () => {
        expect(refusedEdge(refused).id.startsWith(REFUSED_EDGE_PREFIX)).toBe(true);
        expect(isRefusedEdgeId(refusedEdge(refused).id)).toBe(true);
        expect(isRefusedEdgeId('edge_1')).toBe(false);
    });

    it('is not styled as a relation and does not point anywhere', () => {
        const edge = refusedEdge(refused);
        expect(edge.className).toContain('is-refused');
        expect(edge.markerEnd).toBeUndefined();     // nothing was established
        expect(edge.data.kind).toBe('refusal');
    });

    it('names which KIND of refusal it was, because the next move differs', () => {
        expect(refusalLine({ reason: 'same_node', detail: 'x' })).toMatch(/Not a relation/);
        expect(refusalLine({ reason: 'unknown_node', detail: 'x' })).toMatch(/Stale canvas/);
        expect(refusalLine({ reason: 'unreadable_image', detail: 'x' })).toMatch(/Could not read/);
        expect(refusalLine({ reason: 'gate_refused', detail: 'x' })).toMatch(/No relation drawn/);
    });

    it('always shows the gate\'s detail verbatim', () => {
        expect(refusalLine(refused)).toContain(refused.detail);
    });

    it('is nothing at all when there is no pair to draw it between', () => {
        expect(refusedEdge(null)).toBeNull();
        expect(refusedEdge({ reason: 'x', source_node: 'n0' })).toBeNull();
    });
});

// ── the two checks the client may honestly make ─────────────────────────────

describe('what the client refuses before asking', () => {
    it('refuses a line from an image to itself', () => {
        const out = connectionRefusal({ source: 'n0', target: 'n0' });
        expect(out.reason).toBe('same_node');
    });

    it('refuses a line touching a C4 claim card — a claim is not evidence', () => {
        // A line from a claim to an image is a BINDING, and bindings are minted by the planner,
        // never dragged into existence.
        const isClaimNode = (id) => String(id).startsWith('claim:');
        expect(connectionRefusal({ source: 'claim:c0', target: 'n1' }, { isClaimNode }).reason)
            .toBe('not_an_image');
        expect(connectionRefusal({ source: 'n0', target: 'claim:c0' }, { isClaimNode }).reason)
            .toBe('not_an_image');
    });

    it('refuses NOTHING else — whether a relation can be named is the gate\'s to answer', () => {
        // Guessing here would refuse comparisons the system would actually have allowed.
        expect(connectionRefusal({ source: 'n0', target: 'n1' })).toBeNull();
    });
});

// ── 3. an edge whose relation left the ledger ───────────────────────────────

describe('a stale edge', () => {
    const stale = anEdge({ live: false, role: '', label: '', epistemic: '',
        missing_reason: 'the relation this edge names is no longer in the ledger' });

    it('stays on the canvas and says the relation is gone', () => {
        // "Never drawn" and "drawn, then uncommitted" are different facts about the corpus.
        const [edge] = relationEdges({ edges: [stale] });
        expect(edge.label).toBe('relation no longer in the ledger');
        expect(edge.className).toContain('is-stale');
        expect(edge.data.live).toBe(false);
    });

    it('still runs between the same two nodes', () => {
        const [edge] = relationEdges({ edges: [stale] });
        expect([edge.source, edge.target]).toEqual(['n0', 'n1']);
    });

    it('is counted separately and never folded into the total', () => {
        const summary = relationSummary({ edges: [anEdge(), stale] });
        expect(summary).toEqual({ drawn: 2, stale: 1 });
    });
});

describe('a relation with no role yet', () => {
    it('still reads as a relation rather than as an empty label', () => {
        expect(relationLabel(anEdge({ role: '', epistemic: 'interpretive' })))
            .toBe('relation · interpretive');
    });

    it('reads an underscored role as words', () => {
        expect(relationLabel(anEdge({ role: 'formal_echo' }))).toBe('formal echo · interpretive');
    });
});
