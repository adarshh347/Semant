// PERCEPTUAL-ORGANS-002 Lane E — the shell: source, organ lock, mode, and the upload that fails.
//
// Mounted against the fixture client, which is the client every other suite in this lane uses,
// so what is asserted here is the same surface a person opens.

import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import PerceptionLab from './PerceptionLab';
import { createFixtureClient, defaultCapabilityStates } from './clients/fixtureClient';
import { assertClientShape } from './clients/labClient';

if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
}

let container; let root;
const mount = async (node) => { await act(async () => { root.render(node); }); };
const settle = async () => { await act(async () => { await Promise.resolve(); }); };

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
});

const text = () => container.textContent;
const q = (sel) => container.querySelector(sel);
const all = (sel) => [...container.querySelectorAll(sel)];
const click = async (el) => {
    await act(async () => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
    await settle();
};

describe('the shell says what it is talking to', () => {
    it('names the client, and that is not the badge on a run', async () => {
        await mount(<PerceptionLab client={createFixtureClient()} />);
        await settle();
        expect(q('[data-client-identity]').textContent).toContain('FIXTURE');
        expect(q('[data-client-identity]').getAttribute('title')).toMatch(/different questions/);
    });

    it('reports the adapter table it was given, rather than assuming', async () => {
        await mount(<PerceptionLab client={createFixtureClient()} />);
        await settle();
        // sam3_concept is unavailable in the default fixture deployment
        expect(text()).toMatch(/adapters available here/);
        const chips = all('.pl-cap');
        const sam3 = chips.find((c) => c.textContent.includes('sam3_concept'));
        expect(sam3.getAttribute('data-state')).toBe('unavailable');
        expect(sam3.getAttribute('title')).toMatch(/not loadable in this deployment/);
    });
});

describe('the organ catalogue', () => {
    it('lists all eight families and enables exactly two', async () => {
        await mount(<PerceptionLab client={createFixtureClient()} />);
        await settle();
        const organs = all('.pl-organ');
        expect(organs).toHaveLength(8);
        const enabled = organs.filter((o) => !o.disabled);
        expect(enabled.map((o) => o.getAttribute('data-organ'))).toEqual(['extent', 'topology']);
    });

    it('a closed organ keeps its question and says it is registered, not missing', async () => {
        await mount(<PerceptionLab client={createFixtureClient()} />);
        await settle();
        const depth = all('.pl-organ').find((o) => o.getAttribute('data-organ') === 'depth');
        expect(depth.disabled).toBe(true);
        expect(depth.textContent).toContain('What is nearer, and what is further away?');
        expect(depth.textContent).toContain('registered, and not enabled in this phase');
    });

    it('the organ lock is visible on the root, and follows the selection', async () => {
        await mount(<PerceptionLab client={createFixtureClient()} />);
        await settle();
        expect(q('.pl').getAttribute('data-organ')).toBe('extent');
        const topology = all('.pl-organ').find((o) => o.getAttribute('data-organ') === 'topology');
        await click(topology);
        expect(q('.pl').getAttribute('data-organ')).toBe('topology');
        expect(topology.getAttribute('aria-pressed')).toBe('true');
    });
});

describe('the two switches', () => {
    it('scope and arm move independently, and each states its consequence', async () => {
        await mount(<PerceptionLab client={createFixtureClient()} />);
        await settle();
        expect(q('[data-mode-consequence]').getAttribute('data-mode-consequence')).toBe('isolation');
        expect(q('[data-mode-consequence]').textContent).toMatch(/organ_locked/);

        await click(q('[data-mode="chain"]'));
        expect(q('.pl').getAttribute('data-mode')).toBe('chain');
        expect(q('[data-mode-consequence]').textContent).toMatch(/asks for confirmation/);
        // the arm has not moved
        expect(q('.pl').getAttribute('data-arm')).toBe('direct');

        await click(q('[data-arm="prompt"]'));
        expect(q('.pl').getAttribute('data-arm')).toBe('prompt');
        expect(q('.pl').getAttribute('data-mode')).toBe('chain');
        expect(q('[data-arm-consequence]').textContent).toMatch(/same resolver/);
    });
});

describe('the source rail', () => {
    it('opens a session against the source, carrying its digest', async () => {
        await mount(<PerceptionLab client={createFixtureClient()} />);
        await settle();
        expect(text()).toContain('No session is open');
        await click(q('[data-source-id="scene_controls"]'));
        expect(text()).not.toContain('No session is open');
        expect(text()).toContain('sha256:fixture_controls_v1');
    });

    it('an upload that fails reports the failure and opens nothing', async () => {
        const client = createFixtureClient({ uploadFails: true });
        await mount(<PerceptionLab client={client} />);
        await settle();
        const before = all('.pl-source').length;
        const input = q('#pl-file');
        // A File the jsdom input will accept for the purposes of our own handler.
        await act(async () => {
            Object.defineProperty(input, 'files', {
                value: [new File(['x'], 'broken.jpg', { type: 'image/jpeg' })],
                configurable: true,
            });
            input.dispatchEvent(new Event('change', { bubbles: true }));
        });
        const upload = [...container.querySelectorAll('button')]
            .find((b) => /Upload and open/.test(b.textContent));
        await click(upload);
        expect(q('[role="alert"]').textContent).toMatch(/The upload did not complete/);
        expect(q('[role="alert"]').textContent).toMatch(/not in the list/);
        expect(all('.pl-source')).toHaveLength(before);
        expect(text()).toContain('No session is open');
    });

    it('an upload that succeeds adds the source and opens it', async () => {
        const client = createFixtureClient();
        await mount(<PerceptionLab client={client} />);
        await settle();
        const before = all('.pl-source').length;
        const input = q('#pl-file');
        await act(async () => {
            Object.defineProperty(input, 'files', {
                value: [new File(['x'], 'finial.jpg', { type: 'image/jpeg' })],
                configurable: true,
            });
            input.dispatchEvent(new Event('change', { bubbles: true }));
        });
        await click([...container.querySelectorAll('button')]
            .find((b) => /Upload and open/.test(b.textContent)));
        expect(all('.pl-source')).toHaveLength(before + 1);
        expect(container.querySelector('[role="alert"]')).toBe(null);
        expect(text()).not.toContain('No session is open');
    });
});

describe('every state has a deliberate rendering', () => {
    it('a source list that has not loaded says so, rather than rendering nothing', async () => {
        const never = {
            ...createFixtureClient(),
            listSources: () => new Promise(() => {}),
            capabilities: () => new Promise(() => {}),
        };
        await mount(<PerceptionLab client={never} />);
        await settle();
        expect(text()).toContain('Reading the available images…');
    });

    it('an empty source list is an intentional empty state', async () => {
        const client = createFixtureClient();
        const bare = { ...client, listSources: async () => ({ sources: [] }) };
        await mount(<PerceptionLab client={bare} />);
        await settle();
        expect(text()).toContain('No images are listed');
    });

    it('a client that cannot be reached says so and changes nothing', async () => {
        const client = createFixtureClient();
        const broken = { ...client, listSources: async () => { throw new Error('offline'); } };
        await mount(<PerceptionLab client={broken} />);
        await settle();
        expect(q('[role="alert"]').textContent).toMatch(/offline/);
        expect(q('[role="alert"]').textContent).toMatch(/has been changed by the attempt/);
    });
});

describe('the client contract is enforced at mount', () => {
    it('a client missing a method fails loudly rather than half-rendering', () => {
        // `useLabSession` runs this during render, so a half-wired client from Lane F cannot
        // reach a screen where some panels work and some are quietly blank.
        expect(() => assertClientShape({ identity: () => 'FIXTURE' }))
            .toThrow(/missing capabilities, listSources/);
    });

    it('the default deployment declares at least one adapter unavailable, on purpose', () => {
        expect(defaultCapabilityStates().sam3_concept).toBe('unavailable');
    });
});
