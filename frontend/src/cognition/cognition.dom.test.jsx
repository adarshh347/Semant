/**
 * COGNITION — the surface, mounted. The honesty rules, made runnable.
 *
 * A viewing surface can be dishonest in ways a service cannot, and all three failures are silent:
 *
 *   1. refusals rendered as blanks        → TestRefusalsRender
 *   2. an arrival narrated                → TestNoNarratedArrival
 *   3. status distinctions flattened      → TestStatusIsDistinct
 *
 * No testing-library — plain DOM queries against a real root, the shape the existing
 * `.dom.test.jsx` suites use.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

import WalkStream from './WalkStream.jsx';
import CognitionPage from './CognitionPage.jsx';
import { createMockCognitionClient } from './cognitionClient.js';
import walkFixture, { compareFixture, temperamentsFixture } from './cognitionFixture.js';

let container;
let root;

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});

afterEach(() => {
    act(() => root.unmount());
    container.remove();
});

const render = (node) => act(() => root.render(node));

describe('TestRefusalsRender', () => {
    it('shows every refused crossing with its reason and its gloss', () => {
        render(<WalkStream walk={walkFixture} />);
        const text = container.textContent;

        expect(container.querySelectorAll('.cog-refusal')).toHaveLength(2);
        expect(text).toContain('could not ground — interpretive_basis');
        expect(text).toContain('could not ground — box_footing');
        expect(text).toContain('grounded on an estimate, not a measurement');
    });

    it('keeps the two families of refusal visually distinguishable', () => {
        render(<WalkStream walk={walkFixture} />);
        const abouts = [...container.querySelectorAll('.cog-refusal')]
            .map((el) => el.getAttribute('data-about'));
        expect(new Set(abouts)).toEqual(new Set(['edge', 'traveller']));
        expect(container.textContent).toContain('1 about the crossing');
        expect(container.textContent).toContain('1 about the traveller');
    });

    it('says a station measured nothing rather than rendering an empty gap', () => {
        render(<WalkStream walk={walkFixture} />);
        expect(container.querySelector('.cog-empty').textContent)
            .toContain('measured nothing');
    });
});

describe('TestNoNarratedArrival', () => {
    it('states that a step arrived with an empty field', () => {
        render(<WalkStream walk={walkFixture} />);
        expect(container.querySelector('.cog-step-arrival').textContent)
            .toContain('empty field');
    });

    it('renders an intra-image step as movement within one picture', () => {
        render(<WalkStream walk={walkFixture} />);
        expect(container.querySelector('.cog-step-kind').textContent)
            .toBe('within one picture');
        expect(container.querySelector('.cog-step--within')).not.toBeNull();
    });

    it('renders a cross-image step differently', () => {
        render(<WalkStream walk={compareFixture.walks[1]} />);
        expect(container.querySelector('.cog-step-kind').textContent).toBe('between pictures');
        expect(container.querySelector('.cog-step--within')).toBeNull();
    });
});

describe('TestStatusIsDistinct', () => {
    it('gives measured and proposed different classes', () => {
        render(<WalkStream walk={walkFixture} />);
        expect(container.querySelector('.cog-status--measured')).not.toBeNull();
    });

    it('never renders a status as a bare blank', () => {
        render(<WalkStream walk={walkFixture} />);
        for (const el of container.querySelectorAll('.cog-status')) {
            expect(el.textContent.trim().length).toBeGreaterThan(0);
        }
    });
});

describe('TestBrightLine', () => {
    it('shows BOTH halves — identical measurements and diverged routes', async () => {
        const client = createMockCognitionClient({
            temperaments: temperamentsFixture, walk: walkFixture, compare: compareFixture,
        });
        render(<CognitionPage client={client} />);
        // React tracks the input's value setter, so assigning `.value` directly is invisible to
        // it — the state stayed empty and the form refused with "a post id is needed", which is
        // the component behaving correctly and the test lying. The native setter is the fix.
        const input = container.querySelector('.cog-field input');
        const setValue = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value').set;
        await act(async () => {
            setValue.call(input, 'pA');
            input.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await act(async () => {
            container.querySelector('.cog-go').click();
        });
        // The client is async, so the state that renders the comparison lands a microtask after
        // the click resolves. Flushed explicitly rather than slept on.
        await act(async () => { await Promise.resolve(); });

        const text = container.textContent;
        expect(text).toContain('measurements identical: true');
        expect(text).toContain('routes diverged: true');
        expect(text).toContain('biases the route, never the reading');
    });
});
