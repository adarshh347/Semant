/**
 * ATLAS T2 — the pure half of the Scout: a ghost is not an edge.
 *
 * Everything here is one property looked at from several sides: a candidate asserts nothing. It
 * carries no direction, no role, no epistemic kind, no percept; it cannot be confused with a
 * stored edge; and it is not a claim about the pictures but a question about them.
 *
 * Every fixture is synthetic.
 */
import { describe, it, expect } from 'vitest';

import {
    GHOST_EDGE_PREFIX, candidateOfEdge, droppedLines, ghostEdges, ghostId, isGhostEdgeId,
    scoutRefusalLine, scoutSummary, withoutCandidate,
} from './atlasScout.js';
import { relationEdges } from './atlasRelation.js';

const candidate = (from, to, rationale = 'both hold a curved rail') => ({ from, to, rationale });

// ── a ghost cannot be mistaken for an edge ──────────────────────────────────

describe('ghost ids', () => {
    it('are prefixed so no code handling both can confuse them', () => {
        expect(ghostId(candidate('n0', 'n1')).startsWith(GHOST_EDGE_PREFIX)).toBe(true);
        expect(isGhostEdgeId(ghostId(candidate('n0', 'n1')))).toBe(true);
    });

    it('do not collide with a stored edge id', () => {
        const stored = relationEdges({ edges: [{ edge_id: 'edge_1', source_node: 'n0',
            target_node: 'n1', epistemic: 'interpretive' }] })[0];
        expect(isGhostEdgeId(stored.id)).toBe(false);
    });

    it('are the same for a pair proposed either way round', () => {
        // A candidate has no direction to assert — only `compare_views` records a left and a right.
        expect(ghostId(candidate('n0', 'n1'))).toBe(ghostId(candidate('n1', 'n0')));
    });
});

// ── what a ghost draws ──────────────────────────────────────────────────────

describe('ghostEdges', () => {
    it('draws one line per candidate, between the two named images', () => {
        const edges = ghostEdges([candidate('n0', 'n1'), candidate('n1', 'n2')]);
        expect(edges.map((e) => [e.source, e.target])).toEqual([['n0', 'n1'], ['n1', 'n2']]);
    });

    it('carries no arrow — nothing established a direction', () => {
        expect(ghostEdges([candidate('n0', 'n1')])[0].markerEnd).toBeUndefined();
    });

    it('is visually its own kind, not a relation and not a binding', () => {
        const ghost = ghostEdges([candidate('n0', 'n1')])[0];
        expect(ghost.className).toBe('atlas-ghost');
        expect(ghost.className).not.toContain('atlas-relation');
        expect(ghost.className).not.toContain('binding');
    });

    it('says "unconfirmed" on the line itself, before the hunch', () => {
        // A sentence on a line between two photographs reads as a finding unless something says
        // otherwise, and the label is the only thing a reader sees at a glance.
        const ghost = ghostEdges([candidate('n0', 'n1', 'both curve')])[0];
        expect(ghost.label).toMatch(/^unconfirmed · /);
        expect(ghost.label).toContain('both curve');
    });

    it('never carries a role, an epistemic kind or a percept', () => {
        // The three things that would make it look like a comparison had been run.
        const ghost = ghostEdges([candidate('n0', 'n1')])[0];
        expect(sortedKeys(ghost.data)).toEqual(['confirmed', 'from', 'kind', 'rationale', 'to']);
        expect(ghost.data.confirmed).toBe(false);
    });

    it('says so rather than lying when a candidate arrived with no reason', () => {
        expect(ghostEdges([{ from: 'n0', to: 'n1' }])[0].label).toContain('no reason given');
    });

    it('draws nothing for a candidate missing an end', () => {
        expect(ghostEdges([{ from: 'n0', rationale: 'half a pair' }])).toEqual([]);
        expect(ghostEdges(null)).toEqual([]);
    });
});

const sortedKeys = (o) => Object.keys(o).sort();

// ── removing one ────────────────────────────────────────────────────────────

describe('withoutCandidate', () => {
    it('removes the pair regardless of the order it was named in', () => {
        const left = withoutCandidate([candidate('n0', 'n1'), candidate('n1', 'n2')], 'n1', 'n0');
        expect(left.map((c) => c.to)).toEqual(['n2']);
    });

    it('leaves the rest alone', () => {
        expect(withoutCandidate([candidate('n0', 'n1')], 'n7', 'n8')).toHaveLength(1);
    });
});

describe('candidateOfEdge', () => {
    it('reads the pair back off a ghost', () => {
        const ghost = ghostEdges([candidate('n0', 'n1', 'why')])[0];
        expect(candidateOfEdge(ghost)).toEqual({ from: 'n0', to: 'n1', rationale: 'why' });
    });

    it('refuses to read a stored edge as a candidate', () => {
        const stored = relationEdges({ edges: [{ edge_id: 'edge_1', source_node: 'n0',
            target_node: 'n1' }] })[0];
        expect(candidateOfEdge(stored)).toBe(null);
    });
});

// ── refusal and drops render ────────────────────────────────────────────────

describe('scoutRefusalLine', () => {
    it('tells a dead model apart from an empty answer', () => {
        // A writer who reads an unreachable API as "nothing worth comparing" learns something
        // false about their own corpus.
        expect(scoutRefusalLine({ reason: 'model_unavailable', detail: 'GROQ_API_KEY unset' }))
            .toMatch(/could not be reached/);
        expect(scoutRefusalLine({ reason: 'nothing_proposed', detail: 'nothing allowed' }))
            .toMatch(/proposed nothing/);
    });

    it('says when there was nothing to compare in the first place', () => {
        expect(scoutRefusalLine({ reason: 'too_few_images', detail: 'fewer than two readable' }))
            .toMatch(/Nothing to compare/);
    });

    it('is empty when nothing refused', () => {
        expect(scoutRefusalLine(null)).toBe('');
    });
});

describe('droppedLines', () => {
    it('says an invented image was dropped, naming the pair', () => {
        expect(droppedLines([{ reason: 'unknown_node', from: 'n0', to: 'n9' }])[0])
            .toMatch(/n0→n9: named an image not on this Atlas/);
    });

    it('says when the model tried to name the relation, and whose job that is', () => {
        expect(droppedLines([{ reason: 'named_a_relation', from: 'n0', to: 'n1' }])[0])
            .toMatch(/Only the comparison may do that/);
    });

    it('falls back to the detail rather than swallowing an unknown reason', () => {
        expect(droppedLines([{ reason: 'novel', from: 'n0', to: 'n1', detail: 'because' }])[0])
            .toContain('because');
    });

    it('is empty when nothing was dropped', () => {
        expect(droppedLines([])).toEqual([]);
        expect(droppedLines(null)).toEqual([]);
    });
});

describe('scoutSummary', () => {
    it('counts proposals and drops separately — a drop is not a proposal', () => {
        expect(scoutSummary([candidate('n0', 'n1')], [{ reason: 'unknown_node' }]))
            .toEqual({ proposed: 1, dropped: 1 });
    });
});
