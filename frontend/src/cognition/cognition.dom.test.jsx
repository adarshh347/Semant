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
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

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

const HERE = path.dirname(fileURLToPath(import.meta.url));

/**
 * The fixture carries one epistemic status, which is honest about the walk it describes and no use
 * at all for proving the OTHER branches render distinctly. This puts one perception of each status
 * at a single station, so every branch of `statusClass` has to fire on the same screen.
 */
const walkWithStatuses = (statuses) => ({
    ...walkFixture,
    stations: [{
        ...walkFixture.stations[0],
        perceptions: statuses.map((epistemic, i) => ({
            organ: 'nestedness_organ', relation: 'nested_within', direction: 'within',
            other_region_id: `whole_${i}`, basis: 'mask', admissible: true,
            epistemic, expression: `a ${epistemic} reading`, mark_id: `vm_${i}`,
        })),
        horizon: { reachable: [], refused: [], tally: {} },
    }],
});

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

    it('renders a refusal as something a person can actually see', () => {
        // Counting elements is not enough. A refusal that is present in the DOM and hidden is a
        // blank on screen — the exact failure this describe block is named for — and it satisfies
        // `toHaveLength(2)` perfectly. So: not hidden, not display:none, not zero-height.
        render(<WalkStream walk={walkFixture} />);
        expect(container.querySelectorAll('.cog-refusal').length).toBe(2);
        for (const el of container.querySelectorAll('.cog-refusal')) {
            expect(el.hidden).toBe(false);
            expect(el.getAttribute('aria-hidden')).toBeNull();
            expect(el.style.display).not.toBe('none');
            expect(el.style.visibility).not.toBe('hidden');
            expect(el.textContent.trim().length).toBeGreaterThan(0);
        }
        const css = fs.readFileSync(path.join(HERE, 'cognition.css'), 'utf8');
        const rule = css.match(/\.cog-refusal\s*\{([^}]*)\}/);
        expect(rule && rule[1]).not.toMatch(/display:\s*none|visibility:\s*hidden/);
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
    it('gives every status its own class, not just the one the fixture happens to carry', () => {
        // The fixture is all `measured`, so asserting `.cog-status--measured` exists proved only
        // that ONE branch fires. `proposed` could have returned the measured class and nothing
        // here would have noticed — which is the collapse this suite is named for.
        render(<WalkStream walk={walkWithStatuses(
            ['measured', 'interpretive', 'proposed', 'guessed'])} />);
        const classes = [...container.querySelectorAll('.cog-status')]
            .map((el) => el.getAttribute('class'));
        expect(new Set(classes).size).toBe(4);
        expect(classes).toContain('cog-status cog-status--measured');
        expect(classes).toContain('cog-status cog-status--interpretive');
        expect(classes).toContain('cog-status cog-status--proposed');
        // a status outside the vocabulary is `other` — never quietly folded into a known one
        expect(classes).toContain('cog-status cog-status--other');
    });

    it('gives those classes different treatments in the stylesheet', () => {
        // Off the stylesheet, because no DOM query reaches it: four distinct classes landing on
        // four identical rules is a page where the distinction exists only in the markup.
        const css = fs.readFileSync(path.join(HERE, 'cognition.css'), 'utf8');
        const rule = (name) => {
            const m = css.match(new RegExp(`\\.cog-status--${name}\\s*\\{([^}]*)\\}`));
            return m ? m[1].replace(/\s+/g, ' ').trim() : null;
        };
        const names = ['measured', 'interpretive', 'proposed', 'other'];
        const rules = names.map(rule);
        expect(rules.every(Boolean)).toBe(true);
        expect(new Set(rules).size).toBe(names.length);
        // and they differ in KIND, not in opacity alone — legible without colour vision
        expect(rule('measured')).toMatch(/border:[^;]*solid/);
        expect(rule('interpretive')).toMatch(/border:[^;]*dashed/);
        expect(rule('proposed')).toMatch(/border:[^;]*dotted/);
    });

    it('never renders a status as a bare blank', () => {
        render(<WalkStream walk={walkFixture} />);
        const badges = container.querySelectorAll('.cog-status');
        expect(badges.length).toBeGreaterThan(0);   // else the loop asserts nothing at all
        for (const el of badges) {
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
