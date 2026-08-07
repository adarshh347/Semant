/**
 * SOCIETY — the surface, mounted. The two lies a meeting view would tell, made runnable.
 *
 *   1. a joint hypothesis shown as measured, or as one voice  → TestHypothesisIsProposed
 *   2. a number on an incommensurable pair                    → TestNoCrossSenseNumber
 *   3. a wholly-received belief shown as held                 → TestRefusalIsRefused
 *
 * No testing-library — plain DOM queries against a real root, the shape the existing
 * `.dom.test.jsx` suites use.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

import SocietyPage from './SocietyPage.jsx';
import meetingFixture from './societyFixture.js';

let container;
let root;

const client = { meeting: async () => meetingFixture };

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});

afterEach(() => {
    act(() => root.unmount());
    container.remove();
});

async function convene() {
    await act(() => root.render(<SocietyPage client={client} />));
    const input = container.querySelector('.cog-field input');
    const setValue = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, 'value').set;
    await act(async () => {
        setValue.call(input, 'pA');
        input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await act(async () => { container.querySelector('.cog-go').click(); });
    await act(async () => { await Promise.resolve(); });
}

describe('TestHypothesisIsProposed', () => {
    it('renders the joint claim as proposed and never as measured', async () => {
        await convene();
        const status = container.querySelector('.soc-hypothesis .cog-status');
        expect(status.textContent).toBe('proposed');
        expect(container.textContent).not.toContain('nested_at_boundary measured');
        expect(container.querySelector('.soc-hypothesis .cog-status--measured')).toBeNull();
    });

    it('shows both contributors and the mark each stood behind', async () => {
        await convene();
        const rests = container.querySelectorAll('.soc-rest');
        expect(rests).toHaveLength(2);
        const text = container.textContent;
        expect(text).toContain('agent_nestedness');
        expect(text).toContain('agent_adjacency');
        expect(text).toContain('vm_nest_1');
        expect(text).toContain('vm_adj_1');
    });

    it('shows contributed and received per holder rather than one voice', async () => {
        await convene();
        expect(container.textContent).toContain('contributed 1');
        expect(container.textContent).toContain('received 1');
    });
});

describe('TestNoCrossSenseNumber', () => {
    it('renders the incommensurable pair with its refusal and no number', async () => {
        await convene();
        const row = container.querySelector('.soc-verdict--incommensurable');
        expect(row).not.toBeNull();
        expect(row.textContent).toContain('no common scale');
        expect(row.textContent).toContain('no shared frame');
        // Nothing quantitative anywhere in that row — a similarity is exactly what must not appear.
        expect(row.textContent).not.toMatch(/0\.\d+/);
    });

    it('renders all three outcomes distinguishably', async () => {
        await convene();
        expect(container.querySelector('.soc-verdict--composed')).not.toBeNull();
        expect(container.querySelector('.soc-verdict--coexistent')).not.toBeNull();
        expect(container.querySelector('.soc-verdict--incommensurable')).not.toBeNull();
    });

    it('shows the comparability partition', async () => {
        await convene();
        expect(container.querySelector('.soc-classes').textContent)
            .toContain('agent_chroma');
    });
});

describe('TestRefusalIsRefused', () => {
    it('shows a wholly-received belief as refused, not as a held one with a caveat', async () => {
        await convene();
        const refusal = container.querySelector('.soc-refusals .cog-refusal');
        expect(refusal).not.toBeNull();
        expect(refusal.textContent).toContain('refused to hold — wholly_received');
        expect(refusal.textContent).toContain('contributed no mark');
    });

    it('does not list the refused claim among what that agent holds', async () => {
        await convene();
        const holds = [...container.querySelectorAll('.soc-hold')]
            .find((el) => el.textContent.includes('agent_chroma'));
        expect(holds.textContent).toContain('holds nothing here');
    });
});

describe('TestJourneysConverge', () => {
    it('renders one journey per member, with its character and where it arrived', async () => {
        await convene();
        const journeys = container.querySelectorAll('.soc-journey');
        expect(journeys).toHaveLength(3);

        const text = container.textContent;
        expect(text).toContain('analogy_seeker');
        expect(text).toContain('contact_seeker');
        expect(text).toContain('depth_seeker');
        // The arrival is accounted for even while the walk is folded — otherwise collapsing would
        // hide the one thing the convergence is claiming.
        expect(container.querySelectorAll('.soc-arrival')).toHaveLength(3);
        expect(container.querySelector('.soc-arrival').textContent).toContain('vm_pMeet:rim');
    });

    it('expands a journey into the cognition view\'s own walk rendering', async () => {
        await convene();
        expect(container.querySelector('.cog-walk')).toBeNull();

        await act(async () => { container.querySelector('.soc-journey-head').click(); });
        // WalkStream's own markup — not a second renderer written here.
        expect(container.querySelector('.cog-walk')).not.toBeNull();
        expect(container.querySelector('.cog-station')).not.toBeNull();
        expect(container.querySelector('.cog-step-arrival').textContent).toContain('empty field');
    });

    it('shows a refusal met on the way, in the shared refusal style', async () => {
        await convene();
        const heads = [...container.querySelectorAll('.soc-journey-head')];
        const adjacency = heads.find((h) => h.textContent.includes('agent_adjacency'));
        await act(async () => { adjacency.click(); });

        const refusal = container.querySelector('.cog-refusal');
        expect(refusal).not.toBeNull();
        expect(refusal.textContent).toContain('could not ground — interpretive_basis');
    });

    it('places the convergence before the partition', async () => {
        await convene();
        const convergence = container.querySelector('.soc-convergence');
        const partition = container.querySelector('.soc-partition');
        expect(convergence.compareDocumentPosition(partition) & Node.DOCUMENT_POSITION_FOLLOWING)
            .toBeTruthy();
    });
});

describe('TestUntravelledIsItsOwnFinding', () => {
    const refusing = {
        meeting: async () => {
            throw new Error('agent alpha has walked 0 measured crossing(s) and this meeting requires 1');
        },
    };

    it('renders "nobody travelled far enough" as a finding, not as an error line', async () => {
        await act(() => root.render(<SocietyPage client={refusing} />));
        const input = container.querySelector('.cog-field input');
        const setValue = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value').set;
        await act(async () => {
            setValue.call(input, 'pA');
            input.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await act(async () => { container.querySelector('.cog-go').click(); });
        await act(async () => { await Promise.resolve(); });

        expect(container.querySelector('.soc-untravelled')).not.toBeNull();
        expect(container.textContent).toContain('nobody travelled far enough');
        expect(container.textContent).toContain('This is not an empty partition');
        // And NOT the generic error line — the two findings must not render alike.
        expect(container.querySelector('p.cog-error')).toBeNull();
    });
});
