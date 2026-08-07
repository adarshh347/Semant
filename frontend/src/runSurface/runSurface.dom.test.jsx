/**
 * RUN SURFACE — the control page, mounted.
 *
 * Two things a driving surface could get wrong that the read-only views could not:
 *
 *   1. it renders the run ITSELF instead of handing it to the existing components → TestNoThirdRenderer
 *   2. it renders a refusal as a failure instead of as a finding            → TestRefusalIsAFinding
 *
 * Everything else — refusals as content, arrival, status marks, the bright line — is inherited by
 * construction, and the first test is what makes "inherited" true rather than claimed.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

import RunSurfacePage from './RunSurfacePage.jsx';
import walkFixture from '../cognition/cognitionFixture.js';
import { compareFixture, temperamentsFixture } from '../cognition/cognitionFixture.js';
import meetingFixture from '../society/societyFixture.js';

let container;
let root;

const client = {
    cognition: {
        temperaments: async () => temperamentsFixture,
        walk: async () => walkFixture,
        compare: async () => compareFixture,
    },
    society: { meeting: async () => meetingFixture },
};

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});

afterEach(() => {
    act(() => root.unmount());
    container.remove();
});

async function drive(overrides = {}, mode = 'compare') {
    const merged = { ...client, ...overrides };
    await act(() => root.render(<RunSurfacePage client={merged} />));
    const setValue = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, 'value').set;
    const seed = container.querySelector('.cog-field input');
    await act(async () => {
        setValue.call(seed, 'pA');
        seed.dispatchEvent(new Event('input', { bubbles: true }));
    });
    if (mode !== 'compare') {
        const select = container.querySelector('.cog-field select');
        const setSel = Object.getOwnPropertyDescriptor(
            window.HTMLSelectElement.prototype, 'value').set;
        await act(async () => {
            setSel.call(select, mode);
            select.dispatchEvent(new Event('change', { bubbles: true }));
        });
    }
    await act(async () => { container.querySelector('.cog-go').click(); });
    await act(async () => { await Promise.resolve(); });
}

describe('TestNoThirdRenderer', () => {
    it('hands a walk to the cognition view\'s own component', async () => {
        await drive();
        // WalkStream's markup — not a renderer written on this page.
        expect(container.querySelector('.cog-walk')).not.toBeNull();
        expect(container.querySelector('.cog-station')).not.toBeNull();
        expect(container.querySelector('.cog-step-arrival').textContent).toContain('empty field');
    });

    it('shows both halves of the bright line when two characters are run', async () => {
        await drive();
        expect(container.textContent).toContain('measurements identical: true');
        expect(container.textContent).toContain('routes diverged: true');
        expect(container.querySelectorAll('.cog-walk')).toHaveLength(2);
    });

    it('hands a society run to the society view\'s own components', async () => {
        await drive({}, 'society');
        expect(container.querySelector('.soc-convergence')).not.toBeNull();
        expect(container.querySelector('.soc-verdict--incommensurable')).not.toBeNull();
        // and the incommensurable pair still shows no number, inherited not re-decided
        expect(container.querySelector('.soc-verdict--incommensurable').textContent)
            .not.toMatch(/0\.\d+/);
    });
});

describe('TestRefusalIsAFinding', () => {
    const refusing = (detail) => ({
        cognition: { ...client.cognition, compare: async () => { throw new Error(detail); } },
    });

    it('renders an untravelled group as its finding, not as an error', async () => {
        await drive(refusing('agent alpha has walked 0 measured crossing(s) and this meeting requires 1'));
        expect(container.querySelector('.run-refusal--untravelled')).not.toBeNull();
        expect(container.textContent).toContain('nobody travelled far enough');
        expect(container.textContent).toContain('This is a finding, not a failure');
    });

    it('renders a missing locus as its own finding', async () => {
        await drive(refusing('no post pZ'));
        expect(container.querySelector('.run-refusal--nowhere')).not.toBeNull();
        expect(container.textContent).toContain('nowhere to stand');
    });

    it('still renders a genuine failure as one', async () => {
        await drive(refusing('500 Internal Server Error'));
        expect(container.querySelector('.run-refusal--error')).not.toBeNull();
        expect(container.textContent).toContain('the run did not complete');
        expect(container.textContent).not.toContain('This is a finding, not a failure');
    });

    it('refuses an empty seed before calling anything', async () => {
        await act(() => root.render(<RunSurfacePage client={client} />));
        await act(async () => { container.querySelector('.cog-go').click(); });
        expect(container.textContent).toContain('a seed locus is needed');
        expect(container.querySelector('.cog-walk')).toBeNull();
    });
});
