/**
 * AGENT-DEMO — the surface, mounted. The brief's guards, made runnable.
 *
 *   1. the full fixture renders with NO backend            → TestFixtureRenders
 *   2. the answer box round-trips awaiting_answer → resumed → TestAnswerRoundTrip
 *   3. nothing from /differential is imported here          → TestDecoupled
 *   4. the entry asks for images + a prompt and nothing else → TestEntry
 *
 * No testing-library: the project has none as a dependency, and these are plain DOM queries
 * against a real root — the same shape as the existing `.dom.test.jsx` suites.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

import AgentDemoPage from './AgentDemoPage.jsx';
import RunEntry from './RunEntry.jsx';
import { createMockRunClient } from './runClient.js';
import runViewFixture, {
    runningFixture, awaitingAnswerFixture, emptyRunFixture, exploreFixture, FIXTURE_CORPUS,
} from './runViewFixture.js';

let container;
let root;

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    // ResizeObserver: PerceptFigure measures its stage. jsdom has none.
    if (typeof globalThis.ResizeObserver === 'undefined') {
        globalThis.ResizeObserver = class {
            observe() {} unobserve() {} disconnect() {}
        };
    }
});

afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
    vi.restoreAllMocks();
});

const text = () => container.textContent || '';
const $ = (sel) => container.querySelector(sel);
const $$ = (sel) => [...container.querySelectorAll(sel)];

async function mountRun(script, opts = {}) {
    const client = createMockRunClient({ script, ...opts });
    await act(async () => {
        root.render(<AgentDemoPage client={client} posts={[]} />);
    });
    // drive the entry form → a run
    await act(async () => {
        $('.ad-prompt').value = 'why is this centred?';
        $('.ad-prompt').dispatchEvent(new Event('input', { bubbles: true }));
    });
    return client;
}

// ── 1. the full fixture renders with no backend ─────────────────────────────

describe('the full fixture renders with no backend', () => {
    async function mountView(view) {
        const client = createMockRunClient({ script: [view] });
        await act(async () => {
            root.render(<AgentDemoPage client={client} posts={FIXTURE_CORPUS.map((c) => ({
                id: c.post_id, photo_url: c.image_url, title: c.title, region_annotations: [],
            }))} />);
        });
        // start a run through the real form path, not by injecting state
        const prompt = $('.ad-prompt');
        await act(async () => {
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLTextAreaElement.prototype, 'value').set;
            setter.call(prompt, 'why is this centred?');
            prompt.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await act(async () => { $('.ad-thumb').click(); });
        await act(async () => { $('.ad-start').click(); });
        await act(async () => { await Promise.resolve(); });
        return client;
    }

    it('renders the run column, the production records and the article', async () => {
        await mountView(runViewFixture());
        expect($('.ad-progress')).toBeTruthy();
        expect($('.ad-prod')).toBeTruthy();
        // every step is present, including the ones that produced nothing
        expect($$('.ad-prod-row').length).toBe(6);
        expect($('.ad-output')).toBeTruthy();
    });

    it('a refusal is rendered as a result, with its reason and detail', async () => {
        await mountView(runViewFixture());
        const refused = $$('.ad-prod-row.is-refused');
        expect(refused.length).toBe(1);
        expect(refused[0].textContent).toContain('up_vector_spread');
        expect(refused[0].textContent).toMatch(/no projective frame/i);
    });

    it('unknown model and latency render as em dashes, never as 0 or null', async () => {
        await mountView(runViewFixture());
        const row = $$('.ad-prod-row').find((r) => r.dataset.stepId === 's5');
        expect(row.textContent).toContain('—');
        expect(row.textContent).not.toContain('0 ms');
        expect(row.textContent.toLowerCase()).not.toContain('null');
        expect(row.textContent).toMatch(/produced nothing/i);
    });

    it('the epistemic tags and confidences reach the panel', async () => {
        await mountView(runViewFixture());
        expect($$('.ad-epi--measured').length).toBe(2);
        expect(text()).toContain('0.82');
        // a percept with no confidence shows a dash rather than 0.00. Found by its RUN-LOCAL REF,
        // not by an id: a quarantined suggestion has none (`run_surface._suggestion_ref`), and the
        // fixture now says so the way a live run does.
        const noConf = $$('.ad-produced-item')
            .find((i) => i.textContent.includes('run_demo_1:s2#0'));
        expect(noConf.textContent).toContain('—');
    });

    it('a quarantined item with no id still shows a distinct handle', async () => {
        // The live shape, and the defect this pins. `run_surface._suggestion_ref` sets `id` to
        // null for anything not yet accepted — which in a real run is nearly everything — and
        // offers `ref` (`run:step#n`) as the handle instead. The panel keyed on `id`, so against a
        // live run every row in a step keyed on the same empty string and the id column rendered
        // blank. The fixture used to hand out `sug_N` ids no live run produces, which is exactly
        // the fixture drift the run contract warns about.
        await mountView(runViewFixture());
        const handles = $$('.ad-produced-id').map((n) => n.textContent.trim());
        expect(handles.length).toBeGreaterThan(0);
        expect(handles.every((h) => h.length > 0)).toBe(true);
        expect(new Set(handles).size).toBe(handles.length);
    });

    it('a mid-flight run shows the rounds so far and no fabricated progress bar', async () => {
        await mountView(runningFixture());
        expect($$('.ad-round').length).toBe(1);
        expect($('.ad-pulse')).toBeTruthy();
        // nothing may imply a fraction of an unknown total
        expect($('progress')).toBeNull();
        expect($('[role="progressbar"]')).toBeNull();
    });

    it('explore mode with no article renders the produced evidence instead', async () => {
        await mountView(exploreFixture());
        expect($('.ad-output')).toBeTruthy();
        expect(text()).toContain('What it found');
    });

    it('an empty run states the reason rather than showing an empty success', async () => {
        await mountView(emptyRunFixture());
        expect(text()).toMatch(/produced nothing/i);
        expect(text()).toMatch(/nothing was guessed/i);
        expect($('.ad-output--empty')).toBeTruthy();
    });
});

// ── 2. the answer round-trip (A2/A3) ────────────────────────────────────────

describe('the answer resumes the same run', () => {
    it('renders the grounded question with its real options', async () => {
        const client = createMockRunClient({ script: [awaitingAnswerFixture()] });
        await act(async () => { root.render(<AgentDemoPage client={client} posts={[]} />); });
        const prompt = $('.ad-prompt');
        await act(async () => {
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLTextAreaElement.prototype, 'value').set;
            setter.call(prompt, 'q');
            prompt.dispatchEvent(new Event('input', { bubbles: true }));
        });
        const tags = $('.ad-input');
        await act(async () => {
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            setter.call(tags, 'altes-museum');
            tags.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await act(async () => { $('.ad-start').click(); });
        await act(async () => { await Promise.resolve(); });

        expect($('.ad-question')).toBeTruthy();
        expect($$('.ad-option').length).toBe(2);
        // grounded: it names the param and the step it blocks
        expect($('.ad-question-ground').textContent).toContain('lens');
        expect($('.ad-question-ground').textContent).toContain('s7');
    });

    it('answering POSTs the answer and moves the SAME run on', async () => {
        const resumed = runViewFixture({ run_id: 'run_demo_1', status: 'complete' });
        const client = createMockRunClient({
            script: [awaitingAnswerFixture()], afterAnswer: resumed,
        });
        await act(async () => { root.render(<AgentDemoPage client={client} posts={[]} />); });
        const prompt = $('.ad-prompt');
        await act(async () => {
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLTextAreaElement.prototype, 'value').set;
            setter.call(prompt, 'q');
            prompt.dispatchEvent(new Event('input', { bubbles: true }));
        });
        const tags = $('.ad-input');
        await act(async () => {
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            setter.call(tags, 'altes-museum');
            tags.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await act(async () => { $('.ad-start').click(); });
        await act(async () => { await Promise.resolve(); });

        expect($('.ad-question')).toBeTruthy();
        await act(async () => { $$('.ad-option')[0].click(); });
        await act(async () => { await Promise.resolve(); });

        expect(client._answers).toEqual(['threshold']);
        // the question is gone and the run carried on — same run_id, not a new one
        expect($('.ad-question')).toBeNull();
        expect($('.ad-output')).toBeTruthy();
    });
});

// ── 3. decoupled from the Differential ──────────────────────────────────────

describe('this surface is decoupled from /differential', () => {
    it('no module under agentDemo/ imports from differential/', () => {
        // The brief's guard, asserted structurally rather than trusted. ArticleView and
        // PerceptFigure (in article/) do reach the differential RENDERERS internally, and that is
        // the intended reuse — the rule is that THIS surface adds no new coupling of its own and
        // alters nothing over there.
        const dir = path.resolve(__dirname);
        const offenders = [];
        for (const f of fs.readdirSync(dir)) {
            if (!/\.(js|jsx)$/.test(f) || f.includes('.test.')) continue;
            const src = fs.readFileSync(path.join(dir, f), 'utf8');
            for (const m of src.matchAll(/from\s+['"]([^'"]+)['"]/g)) {
                if (m[1].includes('/differential/') || m[1].includes('differential/')) {
                    offenders.push(`${f} → ${m[1]}`);
                }
            }
        }
        expect(offenders).toEqual([]);
    });
});

// ── 4. the entry asks for images + a prompt, and nothing else ───────────────

describe('the entry', () => {
    it('offers an unannotated image exactly like any other, and says so', async () => {
        await act(async () => {
            root.render(<RunEntry posts={[
                { id: 'p1', photo_url: 'x', title: 'Lustgarten', region_annotations: [] },
                { id: 'p2', photo_url: 'x', title: 'Rotunda', region_annotations: [{}, {}] },
            ]} onStart={() => {}} />);
        });
        expect($$('.ad-thumb').length).toBe(2);
        expect(text()).toContain('no marks yet');
        expect(text()).toContain('2 marks');
        // no filter, no gate, nothing that would exclude the unannotated one
        expect($$('.ad-thumb[disabled]').length).toBe(0);
    });

    it('cannot start without both a corpus and a question', async () => {
        const onStart = vi.fn();
        await act(async () => {
            root.render(<RunEntry posts={[{ id: 'p1', photo_url: 'x' }]} onStart={onStart} />);
        });
        expect($('.ad-start').disabled).toBe(true);
        await act(async () => { $('.ad-thumb').click(); });
        expect($('.ad-start').disabled).toBe(true);   // still no question
    });

    it('passes the mode through', async () => {
        const onStart = vi.fn();
        await act(async () => {
            root.render(<RunEntry posts={[{ id: 'p1', photo_url: 'x' }]} onStart={onStart} />);
        });
        await act(async () => { $('.ad-thumb').click(); });
        const prompt = $('.ad-prompt');
        await act(async () => {
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLTextAreaElement.prototype, 'value').set;
            setter.call(prompt, 'how does it gather?');
            prompt.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await act(async () => { $('[data-mode="argue"]').click(); });
        await act(async () => { $('.ad-start').click(); });
        expect(onStart).toHaveBeenCalledWith(expect.objectContaining({
            imageIds: ['p1'], mode: 'argue', prompt: 'how does it gather?',
        }));
    });
});
