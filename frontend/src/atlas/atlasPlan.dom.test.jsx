/**
 * ATLAS C4 — plan mode, mounted.
 *
 * `atlasPlan.test.js` pins what the structure IS; this pins what a writer SEES and can do. Three
 * things have to render or the surface is quietly dishonest: a claim nothing can carry, the reason
 * each refused percept failed, and the fact that an edited plan's verdicts predate the edit.
 *
 * And one thing has to be impossible: accepting a plan must not be able to tell the server what
 * carried. That is asserted against the actual request body.
 *
 * Every fixture is synthetic.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { ReactFlowProvider } from '@xyflow/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import AtlasCanvas from './AtlasCanvas.jsx';
import AtlasClaimNode from './AtlasClaimNode.jsx';
import AtlasPlanPanel from './AtlasPlanPanel.jsx';

// jsdom has no ResizeObserver, and React Flow will not draw an edge whose endpoints it has never
// measured. A stub that fires once on observe is what lets the connectors exist in this
// environment at all — the geometry it reports is zeroes and nothing here asserts on geometry.
if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
        constructor(cb) { this.cb = cb; }
        observe(el) { this.cb([{ target: el, contentRect: { width: 360, height: 190 } }], this); }
        unobserve() {}
        disconnect() {}
    };
}
if (typeof globalThis.DOMMatrixReadOnly === 'undefined') {
    globalThis.DOMMatrixReadOnly = class { constructor() { this.m22 = 1; } };
}

let container; let root;
const mount = async (node) => { await act(async () => { root.render(node); }); };
// A claim node mounted on its own still needs React Flow's store — it carries the source handle
// its connectors leave from.
const mountNode = async (node) => mount(<ReactFlowProvider>{node}</ReactFlowProvider>);
const click = async (el) => { await act(async () => { el.dispatchEvent(
    new MouseEvent('click', { bubbles: true })); }); };

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

// ── fixtures ────────────────────────────────────────────────────────────────

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

const refusedClaim = () => claim({
    claim_id: 'c1', order: 1, text: 'these two marks relate', status: 'refused',
    reason: 'no_percept_could_be_produced', struck: true, achieved_status: 'uncertain',
    percepts: [percept({ step_id: 'c1:0:connect_marks', actuator: 'connect_marks',
        bound: false, why: "missing_input: 'connect_marks' needs 2× mark, has 0" })],
});

const aPlan = (over = {}) => ({
    contract_version: 1, thesis: 'the sequence disperses', planner: 'argument_groq',
    accepted: false, planner_available: true, complete: false, has_challenge: true,
    weakest_status: 'measured', claims: [claim(), refusedClaim()], connectors: [],
    refusals: [], gaps: [], notes: [],
    counts: { claims: 2, supported: 1, qualified: 0, refused: 1, connectors: 1 }, ...over,
});

const aView = (over = {}) => ({
    id: 'atlas_1', title: 'the walk', edges: [], plan: null, unreadable: [],
    nodes: [
        { node_id: 'n0', post_id: 'p1', x: 0, y: 0, w: 420, h: 320, readable: true,
            image_ref: 'https://example.invalid/1.jpg', title: 'one',
            grounds: [], regions: [], marks: [], percepts: [], withheld: 0 },
        { node_id: 'n1', post_id: 'p2', x: 540, y: 0, w: 420, h: 320, readable: true,
            image_ref: 'https://example.invalid/2.jpg', title: 'two',
            grounds: [], regions: [], marks: [], percepts: [], withheld: 0 },
    ],
    ...over,
});

const fakeService = (over = {}) => ({
    view: vi.fn(async () => aView()),
    saveArrangement: vi.fn(async () => ({ atlas: { nodes: [] }, refused: [] })),
    proposePlan: vi.fn(async () => aPlan()),
    acceptPlan: vi.fn(async (id, payload) => ({ plan: { ...aPlan(), accepted: true }, atlas: {} })),
    clearPlan: vi.fn(async () => ({ plan: null })),
    ...over,
});

const panel = (over = {}) => (
    <AtlasPlanPanel thesis="" onThesis={() => {}} onPlan={() => {}} planning={false}
        plan={null} claims={[]} onClaims={() => {}} onAccept={() => {}} onDiscard={() => {}}
        accepting={false} accepted={false} error="" {...over} />
);

// ── 1. a claim, on the canvas ───────────────────────────────────────────────

describe('a claim node', () => {
    it('says what the claim is, what carries it, and how far that reaches', async () => {
        await mountNode(<AtlasClaimNode data={{ claim: claim(), index: 0, total: 2 }} />);
        expect(container.textContent).toContain('the field disperses');
        expect(container.textContent).toContain('supports');
        expect(container.textContent).toContain('negative_space');
        expect(container.textContent).toMatch(/reaches\s*measured/);
    });

    it('renders a refused claim struck through IN THE MARKUP, with the reason', async () => {
        // A stylesheet that failed to load must not silently promote a refused claim back into
        // the argument, and a screen reader has to hear it too.
        await mountNode(<AtlasClaimNode data={{ claim: refusedClaim(), index: 1, total: 2 }} />);
        const node = container.querySelector('.atlas-claim');
        expect(node.getAttribute('data-struck')).toBe('true');
        expect(container.querySelector('s').textContent).toBe('these two marks relate');
        expect(container.textContent).toMatch(/no percept proposed for this claim can be produced/);
    });

    it('names every percept that could not be produced, with the gate\'s own words', async () => {
        await mountNode(<AtlasClaimNode data={{ claim: refusedClaim(), index: 1, total: 2 }} />);
        const line = container.querySelector('[data-bound="false"]');
        expect(line.textContent).toContain('connect_marks');
        expect(line.textContent).toContain('needs 2× mark');
    });

    it('says a comparative percept spans the corpus rather than pointing it at one image', async () => {
        await mountNode(<AtlasClaimNode data={{ index: 0, total: 1, claim: claim({
            percepts: [percept({ actuator: 'compare_views', spans_corpus: true,
                image: null, node_id: null })] }) }} />);
        expect(container.textContent).toContain('across the corpus');
    });

    it('marks an edited claim\'s verdict as predating the edit', async () => {
        await mountNode(<AtlasClaimNode data={{ claim: claim({ dirty: true }), index: 0, total: 1 }} />);
        expect(container.querySelector('.atlas-claim-stale').textContent)
            .toMatch(/verdict is from before the edit/);
    });

    it('shows a caveat rather than folding it into the status', async () => {
        await mountNode(<AtlasClaimNode data={{ index: 0, total: 1, claim: claim({
            caveats: ["planned on 'ghost', whose post could not be read"] }) }} />);
        expect(container.textContent).toContain('could not be read');
    });
});

// ── 2. the panel ────────────────────────────────────────────────────────────

describe('the plan panel', () => {
    it('will not ask for an argument about nothing', async () => {
        await mount(panel({ thesis: '   ' }));
        expect(container.querySelector('.atlas-go').disabled).toBe(true);
    });

    it('counts what the argument holds, without adjectives', async () => {
        await mount(panel({ plan: aPlan(), claims: aPlan().claims }));
        expect(container.textContent).toMatch(/2 claims · 1 carried · 0 in part · 1 refused/);
    });

    it('says out loud that an incomplete argument is incomplete', async () => {
        await mount(panel({ plan: aPlan(), claims: aPlan().claims }));
        expect(container.textContent).toMatch(/not complete — read the refusals/);
    });

    it('renders the argument-level refusal as text, never behind a disclosure', async () => {
        await mount(panel({ claims: [], plan: aPlan({ has_challenge: false, refusals: [
            { reason: 'no_challenge_step',
              detail: 'no percept was given the challenge function' }] }) }));
        expect(container.querySelectorAll('details').length).toBe(0);
        expect(container.querySelector('[role="alert"]').textContent)
            .toMatch(/No counter-reading/);
    });

    it('tells an unreachable planner apart from a corpus with no argument in it', async () => {
        await mount(panel({ claims: [], plan: aPlan({ claims: [], planner_available: false }) }));
        expect(container.textContent).toMatch(/could not be reached/);
        expect(container.textContent).toMatch(/nothing was invented in its place/i);
    });

    it('reorders a claim without pretending its evidence changed', async () => {
        const onClaims = vi.fn();
        const claims = aPlan().claims;
        await mount(panel({ plan: aPlan(), claims, onClaims }));
        await click(container.querySelector('[aria-label="Move c1 earlier"]'));
        const next = onClaims.mock.calls[0][0];
        expect(next.map((c) => c.claim_id)).toEqual(['c1', 'c0']);
        expect(next.some((c) => c.dirty)).toBe(false);
    });

    it('cuts a percept and marks the claim as needing to be judged again', async () => {
        const onClaims = vi.fn();
        const claims = aPlan().claims;
        await mount(panel({ plan: aPlan(), claims, onClaims }));
        await click(container.querySelector(
            '[aria-label="Remove negative_space from claim c0"]'));
        const next = onClaims.mock.calls[0][0];
        expect(next[0].percepts).toEqual([]);
        expect(next[0].dirty).toBe(true);
    });

    it('offers no way to ADD a percept — new evidence goes through the gate, not a form', async () => {
        // Cutting can only weaken a claim and the re-bind reports how far. Hand-attaching an
        // actuator would be asserting a binding nothing judged.
        await mount(panel({ plan: aPlan(), claims: aPlan().claims }));
        const labels = [...container.querySelectorAll('button')]
            .map((b) => (b.getAttribute('aria-label') || b.textContent).toLowerCase());
        expect(labels.some((l) => l.includes('add'))).toBe(false);
        expect(container.querySelector('select')).toBeNull();
    });

    it('warns that an edited plan\'s verdicts are stale', async () => {
        const claims = aPlan().claims.map((c) => ({ ...c, dirty: true }));
        await mount(panel({ plan: aPlan(), claims }));
        expect(container.querySelector('.atlas-banner.is-edited').textContent)
            .toMatch(/accepting sends the structure back to be judged again/);
    });
});

// ── 3. the canvas, end to end ───────────────────────────────────────────────

describe('plan mode on the canvas', () => {
    const typeThesis = async (text) => {
        const box = container.querySelector('#atlas-thesis');
        const setter = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype, 'value').set;
        await act(async () => {
            setter.call(box, text);
            box.dispatchEvent(new Event('input', { bubbles: true }));
        });
        return box;
    };

    const planIt = async (service) => {
        await mount(<AtlasCanvas atlasId="atlas_1" service={service} />);
        await typeThesis('the sequence disperses what the rotunda gathers');
        await click(container.querySelector('.atlas-plan .atlas-go'));
    };

    it('asks the planner over this Atlas and draws what came back', async () => {
        const service = fakeService();
        await planIt(service);

        expect(service.proposePlan).toHaveBeenCalledWith('atlas_1', {
            thesis: 'the sequence disperses what the rotunda gathers' });
        // both claims are on the canvas — including the one nothing can carry
        expect(container.querySelectorAll('.atlas-claim').length).toBe(2);
        expect(container.querySelector('.atlas-claim[data-struck="true"]')).toBeTruthy();
    });

    it('gives a binding both ends to land on', async () => {
        // WHAT THIS DOES NOT TEST, and why. React Flow computes an edge path from measured handle
        // geometry, and jsdom lays nothing out — so no edge element is ever emitted here whatever
        // the plan says. What IS testable is the endpoint contract that was missing before C4: a
        // handle on the claim (source) and one on each image (target). The rule about WHICH
        // percepts get a line is pinned in `atlasPlan.test.js`, and the drawn connector itself is
        // verified in a real browser.
        await planIt(fakeService());
        expect(container.querySelector('.react-flow__edges')).toBeTruthy();
        const claimHandles = container.querySelectorAll('.atlas-claim .react-flow__handle');
        expect(claimHandles.length).toBe(2);          // one source per claim node
        // one TARGET per image node — the end a binding lands on. Since C3 each image also has a
        // source handle for drawing relations, so this counts the landing ends specifically
        // rather than every handle on the node.
        expect(container.querySelectorAll('.atlas-node .react-flow__handle.target').length).toBe(2);

        // A BINDING IS STILL NOT DRAGGED INTO EXISTENCE. C3 made exactly one handle draggable —
        // the image's relation source — and no claim handle is among them: a binding is granted
        // by the gate from a plan, and there is no gesture anywhere that mints one by hand.
        expect(container.querySelectorAll('.atlas-claim .atlas-handle.is-draw').length).toBe(0);
    });

    it('counts the images, not the claim cards sharing the canvas', async () => {
        // Since the claim cards joined the node array (so React Flow would measure them), the
        // header's count had to stop trusting `nodes.length`. It said "5 images" over a corpus of
        // three, which is the one number on this surface a reader would take at face value.
        const service = fakeService();
        await mount(<AtlasCanvas atlasId="atlas_1" service={service} />);
        expect(container.textContent).toContain('2 images');
        await typeThesis('a thesis');
        await click(container.querySelector('.atlas-plan .atlas-go'));
        expect(container.querySelectorAll('.atlas-claim').length).toBe(2);
        expect(container.textContent).toContain('2 images');       // still two, with two claims on it
    });

    it('never sends a claim card to the arrangement', async () => {
        // The cards ride in the same node array as the pictures and must part company at the save
        // boundary: the Atlas document holds where an IMAGE sits and has no node for a claim.
        const service = fakeService();
        await planIt(service);
        const claimNode = container.querySelector('.react-flow__node[data-id^="claim:"]');
        expect(claimNode).toBeTruthy();
        const sent = service.saveArrangement.mock.calls.flatMap(([, patches]) => patches);
        expect(sent.every((p) => !String(p.node_id).startsWith('claim:'))).toBe(true);
    });

    it('says on the surface that a line is a binding, not a relation between images', async () => {
        await planIt(fakeService());
        expect(container.textContent)
            .toMatch(/not a relation between images/);
    });

    it('accepts a plan without telling the server what carried', async () => {
        // The crux. A request that carried `status: supported` would look, to the next person
        // reading it, like something the client was entitled to assert.
        const service = fakeService();
        await planIt(service);
        await click([...container.querySelectorAll('.atlas-plan-actions .atlas-go')][0]);

        const [id, payload] = service.acceptPlan.mock.calls[0];
        expect(id).toBe('atlas_1');
        // `target_status` DOES travel — it is what a claim aims at, which is the writer's
        // intention. What must not travel is any report of what was achieved.
        payload.claims.forEach((c) => {
            ['status', 'achieved_status', 'struck', 'reason', 'binding', 'downgraded']
                .forEach((k) => expect(c).not.toHaveProperty(k));
            c.percepts.forEach((p) => ['bound', 'why', 'epistemic']
                .forEach((k) => expect(p).not.toHaveProperty(k)));
        });
        expect(JSON.stringify(payload)).not.toContain('supported');
        expect(payload.claims.map((c) => c.claim_id)).toEqual(['c0', 'c1']);
    });

    it('adopts the RE-BOUND answer rather than what it sent', async () => {
        // The server judged the edited structure. If a claim lost its evidence, it goes struck on
        // screen — which is only possible because the response replaces the local claims.
        const service = fakeService({
            acceptPlan: vi.fn(async () => ({
                plan: { ...aPlan(), accepted: true,
                    claims: [{ ...claim(), status: 'refused', struck: true,
                        percepts: [percept({ bound: false, why: 'missing_input' })] },
                    refusedClaim()],
                    counts: { claims: 2, supported: 0, qualified: 0, refused: 2, connectors: 0 } },
                atlas: {} })),
        });
        await planIt(service);
        await click([...container.querySelectorAll('.atlas-plan-actions .atlas-go')][0]);

        expect(container.querySelectorAll('.atlas-claim[data-struck="true"]').length).toBe(2);
        expect(container.textContent).toMatch(/Accepted and re-bound/);
        expect(container.textContent).toMatch(/no prose has been written/);
    });

    it('opens an Atlas that already holds an accepted plan wearing it', async () => {
        const service = fakeService({
            view: async () => aView({ plan: { ...aPlan(), accepted: true } }),
        });
        await mount(<AtlasCanvas atlasId="atlas_1" service={service} />);
        expect(container.querySelectorAll('.atlas-claim').length).toBe(2);
        expect(container.querySelector('#atlas-thesis').value).toBe('the sequence disperses');
    });

    it('reports a planner that failed instead of leaving the last answer on screen', async () => {
        const service = fakeService({
            proposePlan: vi.fn(async () => { throw new Error('planner exploded'); }),
        });
        await planIt(service);
        expect(container.querySelector('.atlas-plan [role="alert"]').textContent)
            .toContain('planner exploded');
        expect(container.querySelectorAll('.atlas-claim').length).toBe(0);
    });

    it('writes no prose and offers nothing that would — that is C5', async () => {
        await planIt(fakeService());
        const text = container.textContent.toLowerCase();
        expect(text).not.toMatch(/\bdraft this\b|\bwrite the article\b/);
        expect(container.querySelector('.atlas-plan-note').textContent)
            .toMatch(/proposes claims and where their evidence would come from/);
    });
});
