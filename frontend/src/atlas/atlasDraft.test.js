/**
 * ATLAS C5 — the writer surface as data.
 *
 * What is pinned here is the ATLAS-specific half: the seed a plan offers, why a draft cannot be
 * made, what quarantine means, and what a writer is told before they accept. The article's own
 * structure belongs to M4's `articleDraft.test.js` and is not restated.
 */
import { describe, it, expect } from 'vitest';

import {
    BLOCK_ALL_REFUSED, BLOCK_NO_CLAIMS, BLOCK_NO_IMAGES, BLOCK_NO_PLAN, DRAFT_ACCEPTED,
    DRAFT_QUARANTINED, acceptState, blockerFrom, blockerText, draftSummary, isAccepted,
    isQuarantined, refusalLines, seedBlocker, seedStubs,
} from './atlasDraft.js';

const aPlan = (claims) => ({ thesis: 'the sequence disperses', claims });

const aClaim = (over = {}) => ({
    claim_id: 'c0', text: 'the field disperses', status: 'supported', struck: false,
    percepts: [{ step_id: 'c0:0:negative_space', actuator: 'negative_space', function: 'support',
        epistemic: 'measured', image: 'p1', bound: true }],
    ...over,
});

const aDraft = (inner = {}, over = {}) => ({
    state: DRAFT_QUARANTINED,
    article: {
        draft: {
            thesis: 'the sequence disperses', thesis_prose: 'An opening.', sections: [],
            uncomposed: [], qualifications: [], counter_reading: null, committed: false, ...inner,
        },
        resolved: {},
        counts: { citations: 0, drawable: 0, unresolved: 0 },
    },
    ...over,
});

const aSection = (over = {}) => ({
    claim_id: 'c0', claim: 'the field disperses', prose: 'One paragraph.', epistemic: 'measured',
    function: 'support', citations: [], caveats: [], relevance_flags: [], uncited_mentions: [],
    qualified: false, ...over,
});

// ── the seed ────────────────────────────────────────────────────────────────

describe('the seed an accepted plan offers the writer', () => {
    it('carries each claim with the percepts it will rest on', () => {
        const [stub] = seedStubs(aPlan([aClaim()]));
        expect(stub.claimId).toBe('c0');
        expect(stub.percepts).toHaveLength(1);
        expect(stub.percepts[0].actuator).toBe('negative_space');
        expect(stub.percepts[0].bound).toBe(true);
    });

    it('keeps a struck claim and marks it rather than filtering it away', () => {
        // The writer accepted a plan that included this refusal. A seed that dropped it would
        // misrepresent what they accepted.
        const [stub] = seedStubs(aPlan([aClaim({ struck: true, status: 'refused' })]));
        expect(stub.struck).toBe(true);
        expect(stub.text).toBe('the field disperses');
    });

    it('carries an unbound percept with the gate\'s reason', () => {
        const [stub] = seedStubs(aPlan([aClaim({
            percepts: [{ step_id: 's', actuator: 'rhythm', function: 'support', bound: false,
                why: 'no committed region to measure' }] })]));
        expect(stub.percepts[0].bound).toBe(false);
        expect(stub.percepts[0].why).toBe('no committed region to measure');
    });

    it('is empty rather than throwing for a plan that is not there', () => {
        expect(seedStubs(null)).toEqual([]);
        expect(seedStubs({})).toEqual([]);
    });
});

// ── why a draft cannot be made ──────────────────────────────────────────────

describe('the blocker, computed the same way the backend computes it', () => {
    const withNodes = (plan) => ({ nodes: [{ node_id: 'n0', post_id: 'p1' }], plan });

    it('reports no images ahead of the plan, because editing the plan cannot fix it', () => {
        expect(seedBlocker({ nodes: [], plan: aPlan([aClaim()]) })).toBe(BLOCK_NO_IMAGES);
    });

    it('reports a missing plan', () => {
        expect(seedBlocker(withNodes(null))).toBe(BLOCK_NO_PLAN);
        expect(seedBlocker(withNodes({}))).toBe(BLOCK_NO_PLAN);
    });

    it('reports a plan with no claims', () => {
        expect(seedBlocker(withNodes(aPlan([])))).toBe(BLOCK_NO_CLAIMS);
    });

    it('reports a plan of nothing but struck claims as a refusal already delivered', () => {
        expect(seedBlocker(withNodes(aPlan([aClaim({ struck: true })])))).toBe(BLOCK_ALL_REFUSED);
    });

    it('reports nothing when one claim survives', () => {
        expect(seedBlocker(withNodes(aPlan([aClaim({ struck: true }), aClaim()])))).toBeNull();
    });

    it('gives every blocker a sentence a writer can read', () => {
        for (const r of [BLOCK_NO_PLAN, BLOCK_NO_IMAGES, BLOCK_NO_CLAIMS, BLOCK_ALL_REFUSED]) {
            expect(blockerText(r)).not.toBe(r);
            expect(blockerText(r).length).toBeGreaterThan(20);
        }
    });

    it('reads the server\'s own sentence out of a 409 rather than the status code', () => {
        const err = new Error('Failed to draft the article (409)');
        err.detail = { reason: BLOCK_ALL_REFUSED, message: 'Every claim was refused.' };
        expect(blockerFrom(err)).toBe('Every claim was refused.');
    });

    it('falls back to the blocker text when the server sent only a reason', () => {
        const err = new Error('x');
        err.detail = { reason: BLOCK_NO_PLAN };
        expect(blockerFrom(err)).toBe(blockerText(BLOCK_NO_PLAN));
    });

    it('survives a plain-string detail', () => {
        const err = new Error('x');
        err.detail = 'this Atlas holds no draft';
        expect(blockerFrom(err)).toBe('this Atlas holds no draft');
    });
});

// ── quarantine ──────────────────────────────────────────────────────────────

describe('what quarantine means on this surface', () => {
    it('a stored draft is quarantined until it is accepted', () => {
        expect(isQuarantined(aDraft())).toBe(true);
        expect(isAccepted(aDraft())).toBe(false);

        const accepted = aDraft({}, { state: DRAFT_ACCEPTED });
        expect(isAccepted(accepted)).toBe(true);
        expect(isQuarantined(accepted)).toBe(false);
    });

    it('counts live percepts against cited ones, because the difference is the document', () => {
        const draft = aDraft({ sections: [aSection()] });
        draft.article.counts = { citations: 6, drawable: 1, unresolved: 5 };
        const summary = draftSummary(draft);
        expect(summary.cited).toBe(6);
        expect(summary.live).toBe(1);
        expect(summary.unresolved).toBe(5);
    });

    it('counts every limit the article admits', () => {
        const draft = aDraft({
            qualifications: [{ claim_id: 'c1', prose: 'could not carry' }],
            uncomposed: [{ claim_id: 'c2', claim: 'x', reason: 'prose_cited_no_bound_percept' }],
            counter_reading: { grounded: false, absence_detail: 'none produced' },
        });
        expect(draftSummary(draft).limits).toBe(3);
    });
});

// ── refusals render ─────────────────────────────────────────────────────────

describe('what the draft could not carry', () => {
    it('lists a qualification', () => {
        const draft = aDraft({ qualifications: [{ claim_id: 'c1', prose: 'The corpus could not carry it.' }] });
        expect(refusalLines(draft)).toContain('The corpus could not carry it.');
    });

    it('lists an uncomposed claim, saying why it was not written', () => {
        const draft = aDraft({ uncomposed: [{ claim_id: 'c1', claim: 'the rotunda gathers',
            reason: 'prose_cited_no_bound_percept' }] });
        const [line] = refusalLines(draft);
        expect(line).toContain('the rotunda gathers');
        expect(line).toContain('not written');
        expect(line).not.toContain('_');       // the reason is read as words, not as a constant
    });

    it('states an ungrounded counter-reading as an absence', () => {
        const draft = aDraft({ counter_reading: { grounded: false,
            absence_detail: 'the challenge percept never arrived' } });
        expect(refusalLines(draft)).toContain('the challenge percept never arrived');
    });

    it('says nothing when the article carried everything', () => {
        expect(refusalLines(aDraft({ sections: [aSection()] }))).toEqual([]);
    });
});

// ── what may be accepted ────────────────────────────────────────────────────

describe('whether a draft may be accepted', () => {
    it('allows a draft that composed prose', () => {
        expect(acceptState(aDraft({ sections: [aSection()] })).can).toBe(true);
    });

    it('refuses a draft that composed nothing, so accepting is never accepting nothing', () => {
        const state = acceptState(aDraft({ sections: [] }));
        expect(state.can).toBe(false);
        expect(state.why).toContain('composed no prose');
    });

    it('refuses a section that exists but carries no prose', () => {
        expect(acceptState(aDraft({ sections: [aSection({ prose: '' })] })).can).toBe(false);
    });

    it('refuses a draft that has already been accepted, so prose cannot land twice', () => {
        const state = acceptState(aDraft({ sections: [aSection()] }, { state: DRAFT_ACCEPTED }));
        expect(state.can).toBe(false);
        expect(state.why).toContain('already been accepted');
    });

    it('refuses when there is no draft at all', () => {
        expect(acceptState(null).can).toBe(false);
    });
});
