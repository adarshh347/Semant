import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import PerceptWorkshop from './PerceptWorkshop';

/**
 * CIRCUIT-001 P2 — the percept workshop, mounted.
 *
 * P2 moved "Write from this" out of a row and into a card. That is exactly the kind of
 * refactor that silently drops a callback, so the handoff affordance is pinned HERE, at the
 * component boundary, rather than trusted to have survived. `manuscriptHandoff.test.js`
 * still owns the queue/flush semantics; this owns "the button is present and fires".
 *
 * The other assertions defend the display discipline the P1 gates established: degradation
 * is stated, never explained; a healthy percept carries no health marks; and nothing here
 * dispatches.
 */

const GROUND = (id, extra = {}) => ({ id, ground_type: 'region', region_id: `reg_${id}`, ...extra });
const REGION = (id) => ({ id, label: id, box: { x: 0, y: 0, w: 0.2, h: 0.2 } });

const PERCEPT = {
    id: 'pctx_1',
    expression: 'the upper head turns away',
    ground_ids: ['g1', 'g2'],
    properties: ['light', 'attention'],
    ground_roles: { g1: 'anchor' },
};

let container;
let root;

async function mount(props = {}) {
    await act(async () => {
        root.render(
            <PerceptWorkshop
                percepts={[PERCEPT]}
                grounds={[GROUND('g1'), GROUND('g2')]}
                regions={[REGION('reg_g1'), REGION('reg_g2')]}
                mentions={[]}
                postId="p1"
                {...props}
            />,
        );
    });
}

const text = () => container.textContent || '';
const byText = (t) => [...container.querySelectorAll('button')]
    .find((b) => (b.textContent || '').trim().includes(t));

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

describe('the handoff survives the P2 restructure', () => {
    it('still offers "Write from this" and calls back with the percept', async () => {
        const onSendToManuscript = vi.fn();
        await mount({ onSendToManuscript });
        const write = byText('Write from this');
        expect(write).toBeTruthy();
        await act(async () => { write.click(); });
        expect(onSendToManuscript).toHaveBeenCalledTimes(1);
        // The whole percept, not an id — PostDetailPage's handoff arms from the object.
        expect(onSendToManuscript.mock.calls[0][0].id).toBe('pctx_1');
    });

    it('still offers recall, and plays by percept id', async () => {
        const onPlay = vi.fn();
        await mount({ onPlay });
        await act(async () => { container.querySelector('.pw-play').click(); });
        expect(onPlay).toHaveBeenCalledWith('pctx_1');
    });

    it('omits the actions it was given no handler for, rather than rendering dead ones', async () => {
        await mount({});
        expect(byText('Write from this')).toBeFalsy();
        expect(container.querySelector('.pw-play')).toBe(null);
    });

    it('renders nothing at all when there are no percepts', async () => {
        await mount({ percepts: [] });
        expect(container.textContent).toBe('');
    });
});

describe('what a percept shows about itself', () => {
    it('leads with the noticing and states what it rests on', async () => {
        await mount({});
        expect(container.querySelector('.pw-expression').textContent)
            .toBe('the upper head turns away');
        expect(text()).toContain('2 grounds');
    });

    it('names a ground role inside the percept, where it belongs', async () => {
        // A role is a property of THIS percept's use of a ground, never of the ground
        // record — the same region is an anchor in one noticing and a counterforce in
        // another. It must therefore never render beside the ground itself.
        await mount({});
        const roles = [...container.querySelectorAll('.pw-role')];
        expect(roles.length).toBe(1);
        expect(roles[0].textContent.toLowerCase()).toContain('anchor');
    });

    it('a healthy percept carries no health marks', async () => {
        // Degradation-only. No ticks, no "verified", no badge announcing a nominal state:
        // a surface that announces everything teaches the reader to skim the one line
        // that matters.
        await mount({});
        expect(container.querySelector('.pw-fact--degraded')).toBe(null);
        expect(container.querySelector('.pw-card.has-degraded')).toBe(null);
        // Scoped to the resting display, not the whole subtree: the packet JSON does
        // carry `evidence.state: "intact"`, and that is correct — it is a field in a
        // document the curator deliberately opens, not a badge worn by the percept.
        const resting = container.querySelector('.pw-facts').textContent.toLowerCase();
        expect(resting).not.toContain('verified');
        expect(resting).not.toContain('intact');
        expect(resting).not.toContain('resolve');
    });

    it('states detachment without explaining it', async () => {
        // `resolveGround` knows only that the region_id does not resolve. A re-dissect is
        // one cause among several (a deleted region, an id that never existed), so naming
        // one would assert a fact the code cannot have.
        await mount({ regions: [REGION('reg_g1')] });   // reg_g2 is gone
        const degraded = container.querySelector('.pw-fact--degraded');
        expect(degraded).toBeTruthy();
        expect(degraded.textContent).toContain('1 no longer resolves');
        expect(container.querySelector('.pw-card.has-degraded')).toBeTruthy();
        const t = text().toLowerCase();
        expect(t).not.toContain('replaced');
        expect(t).not.toContain('because');
        expect(t).not.toContain('re-dissect');
    });

    it('says it is in writing only when a mention actually puts it there', async () => {
        await mount({});
        expect(container.querySelector('.pw-fact--writing')).toBe(null);
        // Derived from the live mention set, not from a "sent" flag — a flag would keep
        // claiming the crossing after the chip was deleted.
        await mount({ mentions: [{ perceptId: 'pctx_1', blockId: 'blk1' }] });
        expect(container.querySelector('.pw-fact--writing').textContent).toContain('1 passage');
    });
});

describe('orchestration is inspectable and unsent', () => {
    it('offers the packet as a question, not an action', async () => {
        await mount({});
        const packet = container.querySelector('.pw-packet');
        expect(packet).toBeTruthy();
        expect(packet.querySelector('summary').textContent.toLowerCase())
            .toContain('would be sent');
        // Closed by default: a curator composing is not auditing.
        expect(packet.hasAttribute('open')).toBe(false);
    });

    it('the packet says of itself that nothing was dispatched', async () => {
        await mount({});
        const body = JSON.parse(container.querySelector('.pw-packet-body').textContent);
        expect(body.dispatch.sent).toBe(false);
        expect(body.dispatch.run_id).toBe(null);
    });

    it('no control in the workshop sends anything', async () => {
        const onSendToManuscript = vi.fn();
        await mount({ onSendToManuscript, onPlay: vi.fn() });
        const labels = [...container.querySelectorAll('button')]
            .map((b) => (b.textContent || '').toLowerCase());
        // "Write from this" carries a percept into the manuscript; it does not ask a model.
        expect(labels.some((l) => l.includes('ask') || l.includes('send') || l.includes('run'))).toBe(false);
    });
});
