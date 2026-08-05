/**
 * ATLAS C4 — the pure half of plan mode.
 *
 * What is pinned here is the near side of the three rules the backend also enforces, because the
 * surface is where a violation would actually mislead somebody:
 *
 *   only a BOUND percept draws a connector          → §2
 *   an edit invalidates the verdict it was made against → §3
 *   an accept sends structure, never statuses       → §4
 *
 * Every fixture is synthetic and shaped exactly like `atlas_plan.plan_view`'s output.
 */
import { describe, it, expect } from 'vitest';

import {
    CLAIM_H, CLAIM_NODE_TYPE, CLAIM_W, acceptPayload, bindingEdges, claimFlowNodes,
    claimPositions, connectorsAgree, dropClaim, dropPercept, emptyPlanReason, functionLabel,
    isClaimNodeId, isEdited, moveClaim, planSummary, refusalLines, rewordClaim,
} from './atlasPlan.js';
import { arrangementFrom, positionsOf } from './atlasDocument.js';

const percept = (over = {}) => ({
    step_id: 'c0:0:negative_space', actuator: 'negative_space', params: {},
    function: 'support', known_function: true, target_status: 'interpretive',
    epistemic: 'measured', image: 'p1', node_id: 'n0', spans_corpus: false,
    bound: true, why: '', note: '', ...over,
});

const claim = (over = {}) => ({
    claim_id: 'c0', order: 0, text: 'the field disperses', proposed_text: 'the field disperses',
    note: '', status: 'supported', reason: 'all_percepts_bound', binding: 'planned',
    target_status: 'interpretive', achieved_status: 'measured', downgraded: false,
    struck: false, caveats: [], functions: ['support'], percepts: [percept()], ...over,
});

const aPlan = (over = {}) => ({
    contract_version: 1, thesis: 'the sequence disperses', planner: 'argument_groq',
    accepted: false, planner_available: true, complete: false, has_challenge: true,
    weakest_status: 'measured', claims: [claim()], connectors: [],
    refusals: [], gaps: [], notes: [],
    counts: { claims: 1, supported: 1, qualified: 0, refused: 0, connectors: 1 }, ...over,
});

const imageNodes = [
    { id: 'n0', position: { x: 0, y: 0 } },
    { id: 'n1', position: { x: 540, y: 0 } },
];

// ── 1. layout ───────────────────────────────────────────────────────────────

describe('the claim column', () => {
    it('sits to the left of the corpus, in argument order', () => {
        const at = claimPositions(3, imageNodes);
        expect(at[0].x).toBe(-CLAIM_W - 220);
        expect(at.map((p) => p.y)).toEqual([0, CLAIM_H + 44, 2 * (CLAIM_H + 44)]);
        expect(at.every((p) => p.x < 0)).toBe(true);   // never on top of an image
    });

    it('survives a canvas whose nodes have no usable positions', () => {
        expect(claimPositions(1, [{ id: 'n0', position: { x: NaN, y: undefined } }]))
            .toEqual([{ x: -CLAIM_W - 220, y: 0 }]);
    });

    it('namespaces a claim node so the save path can tell it from a picture', () => {
        // The cards share the node array with the images — that is what gets them MEASURED, and an
        // unmeasured node has no handle bounds and anchors no connector. The namespace is what
        // keeps them out of the arrangement anyway.
        const [n] = claimFlowNodes(aPlan(), imageNodes);
        expect(n.id).toBe('claim:c0');
        expect(isClaimNodeId(n.id)).toBe(true);
        expect(isClaimNodeId('n0')).toBe(false);
    });

    it('keeps claim cards out of the arrangement a save carries', () => {
        const mixed = [
            { id: 'n0', position: { x: 10, y: 20 } },
            { id: 'claim:c0', position: { x: -500, y: 0 } },
        ];
        expect(Object.keys(positionsOf(mixed))).toEqual(['n0']);
        expect(arrangementFrom(mixed, {}).map((p) => p.node_id)).toEqual(['n0']);
    });

    it('lays a claim out FROM its order and refuses to let it be dragged', () => {
        // Two notions of sequence — one in the list, one on the canvas — would contradict each
        // other the moment anybody moved a card. The order is the argument; position is derived.
        const nodes = claimFlowNodes(aPlan({ claims: [claim(), claim({ claim_id: 'c1' })] }),
                                     imageNodes);
        expect(nodes.map((n) => n.id)).toEqual(['claim:c0', 'claim:c1']);
        expect(nodes.every((n) => n.type === CLAIM_NODE_TYPE)).toBe(true);
        expect(nodes.every((n) => n.draggable === false)).toBe(true);
        expect(nodes[1].position.y).toBeGreaterThan(nodes[0].position.y);
    });
});

// ── 2. only a bound percept draws a connector ───────────────────────────────

describe('the connectors', () => {
    it('draws a line from the claim to the image its bound percept names', () => {
        const [edge] = bindingEdges(aPlan());
        expect(edge.source).toBe('claim:c0');
        expect(edge.target).toBe('n0');
        expect(edge.data.kind).toBe('binding');
    });

    it('says on the line what the percept is doing and what it can know', () => {
        const [edge] = bindingEdges(aPlan());
        expect(edge.label).toBe('supports · measured');
        expect(edge.className).toContain('is-support');
    });

    it('draws NOTHING for a percept the gate refused', () => {
        // A greyed line is still a line: the shape of a supported argument, with the refusal
        // demoted to a caption nobody reads.
        const plan = aPlan({ claims: [claim({
            status: 'refused', struck: true,
            percepts: [percept({ bound: false, why: 'missing_input: needs 2× mark' })] })] });
        expect(bindingEdges(plan)).toEqual([]);
    });

    it('draws nothing for a comparative percept, which is about no single image', () => {
        const plan = aPlan({ claims: [claim({ percepts: [percept({
            actuator: 'compare_views', spans_corpus: true, image: null, node_id: null })] })] });
        expect(bindingEdges(plan)).toEqual([]);
    });

    it('draws nothing when the image is not a node on this canvas', () => {
        const plan = aPlan({ claims: [claim({ percepts: [percept({ node_id: null })] })] });
        expect(bindingEdges(plan)).toEqual([]);
    });

    it('agrees with the server about which bindings exist', () => {
        // The same rule in two languages. A silent divergence would mean the canvas drew a
        // binding the record does not hold.
        const plan = aPlan({ connectors: [{ edge_id: 'c0~c0:0:negative_space' }] });
        expect(connectorsAgree(plan)).toBe(true);
        expect(connectorsAgree(aPlan({ connectors: [] }))).toBe(false);
    });
});

// ── 3. an edit invalidates the verdict it was made against ──────────────────

describe('editing the plan', () => {
    const two = [claim(), claim({ claim_id: 'c1', text: 'the rotunda gathers' })];

    it('reorders without touching what the evidence did', () => {
        const moved = moveClaim(two, 'c1', -1);
        expect(moved.map((c) => c.claim_id)).toEqual(['c1', 'c0']);
        expect(moved.map((c) => c.order)).toEqual([0, 1]);
        expect(moved.some((c) => c.dirty)).toBe(false);
    });

    it('does not fall off either end of the argument', () => {
        expect(moveClaim(two, 'c0', -1).map((c) => c.claim_id)).toEqual(['c0', 'c1']);
        expect(moveClaim(two, 'c1', 1).map((c) => c.claim_id)).toEqual(['c0', 'c1']);
    });

    it('drops a claim and renumbers the rest', () => {
        const left = dropClaim(two, 'c0');
        expect(left.map((c) => c.claim_id)).toEqual(['c1']);
        expect(left[0].order).toBe(0);
    });

    it('marks a claim stale when a percept is cut, and takes its line with it', () => {
        const edited = dropPercept([claim()], 'c0', 'c0:0:negative_space');
        expect(edited[0].percepts).toEqual([]);
        expect(edited[0].dirty).toBe(true);
        expect(bindingEdges({ claims: edited })).toEqual([]);
    });

    it('keeps what a reworded claim was proposed as', () => {
        // Binding proves the percepts RESOLVE, not that they bear on the sentence. The original
        // wording is the only record of what the evidence was actually chosen for.
        const [edited] = rewordClaim([claim()], 'c0', 'the rotunda gathers');
        expect(edited.text).toBe('the rotunda gathers');
        expect(edited.proposed_text).toBe('the field disperses');
        expect(edited.dirty).toBe(true);
    });

    it('never recomputes a status on the client', () => {
        // Deciding what evidence carries is the gate's job. A canvas that guessed would be a
        // second, disagreeing planner.
        const [edited] = dropPercept([claim()], 'c0', 'c0:0:negative_space');
        expect(edited.status).toBe('supported');   // stale, and flagged as such
        expect(edited.dirty).toBe(true);
    });

    it('knows when the plan on screen is no longer the one that was planned', () => {
        const plan = aPlan();
        expect(isEdited(plan, plan.claims)).toBe(false);
        expect(isEdited(plan, dropPercept(plan.claims, 'c0', 'c0:0:negative_space'))).toBe(true);
        expect(isEdited(plan, [])).toBe(true);
        expect(isEdited(aPlan({ claims: [claim(), claim({ claim_id: 'c1' })] }),
                        moveClaim([claim(), claim({ claim_id: 'c1' })], 'c1', -1))).toBe(true);
    });
});

// ── 4. what an accept sends ─────────────────────────────────────────────────

describe('the accept payload', () => {
    it('carries claims and percepts and NOTHING about what carried', () => {
        const body = acceptPayload(' the sequence disperses ', [claim()]);
        expect(body.thesis).toBe('the sequence disperses');
        const [row] = body.claims;
        expect(Object.keys(row).sort())
            .toEqual(['claim_id', 'note', 'percepts', 'proposed_text', 'target_status', 'text']);
        expect(Object.keys(row.percepts[0]).sort())
            .toEqual(['actuator', 'function', 'image', 'note', 'params', 'step_id']);
    });

    it('sends the original wording beside an edited one', () => {
        const body = acceptPayload('t', rewordClaim([claim()], 'c0', 'the rotunda gathers'));
        expect(body.claims[0].text).toBe('the rotunda gathers');
        expect(body.claims[0].proposed_text).toBe('the field disperses');
    });

    it('keeps a refused claim in the plan it sends', () => {
        // Deleting it would leave a shorter argument that looks complete — and the writer chose
        // to keep it, so the record has to.
        const body = acceptPayload('t', [claim({ claim_id: 'c1', status: 'refused', struck: true })]);
        expect(body.claims).toHaveLength(1);
        expect(body.claims[0].claim_id).toBe('c1');
    });
});

// ── 5. reading a plan ───────────────────────────────────────────────────────

describe('reading the plan', () => {
    it('counts, and does not adjectivise', () => {
        expect(planSummary(aPlan())).toEqual({
            claims: 1, supported: 1, qualified: 0, refused: 0, connectors: 1,
            complete: false, hasChallenge: true });
    });

    it('tells an unreachable planner apart from a corpus with no argument in it', () => {
        // The one distinction an empty plan cannot afford to lose.
        expect(emptyPlanReason(aPlan({ claims: [], planner_available: false })))
            .toMatch(/could not be reached/);
        expect(emptyPlanReason(aPlan({ claims: [], planner_available: true })))
            .toMatch(/read this corpus and proposed no claims/);
        expect(emptyPlanReason(aPlan())).toBe('');
    });

    it('renders the argument-level refusal as a sentence', () => {
        const lines = refusalLines(aPlan({ refusals: [
            { reason: 'no_challenge_step', detail: 'nothing could tell against it' }] }));
        expect(lines[0]).toMatch(/No counter-reading/);
        expect(lines[0]).toMatch(/nothing could tell against it/);
    });

    it('shows an unknown argumentative function verbatim rather than tidying it', () => {
        // It is about to be refused by name; a tidy label would hide the one thing worth seeing.
        expect(functionLabel('reinforce')).toContain('reinforce');
        expect(functionLabel('reinforce')).toContain('not an argumentative function');
        expect(functionLabel('challenge')).toBe('challenges');
    });
});
