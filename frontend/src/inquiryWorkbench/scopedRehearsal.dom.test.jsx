/**
 * HARNESS-003F — the declared scope, on screen.
 *
 * The lane's whole risk in one sentence: a vertical slice produces FEWER claims, fewer observables
 * and sometimes none, so an unbadged slice does not read as a bounded run — it reads as a THIN one,
 * and a thin result is evidence about the images. Every test here is a way that could happen.
 *
 * WHAT IS DELIBERATELY NOT TESTED HERE: that the bound works. That is the backend's suite, over the
 * real passes. These are about whether a person can tell.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import ScopePanel, { ScopeBadge } from './ScopePanel.jsx';
import InquiryEntry from './InquiryEntry.jsx';
import { normalizeSession, normalizeFeatures, normalizeExecutionScope, startInquiryBody,
    SCOPE_BANNER } from './inquiryContract.js';
import { scopedFixture, unrecordedScopeFixture, completedFixture, batchedCouncilFixture }
    from './inquiryFixtures.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));

let container;
let root;

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

const text = () => container.textContent || '';
const $ = (sel) => container.querySelector(sel);
const $$ = (sel) => [...container.querySelectorAll(sel)];

async function mount(fixture) {
    const session = normalizeSession(fixture);
    await act(async () => {
        root.render(<><ScopeBadge scope={session.execution_scope} />
            <ScopePanel session={session} /></>);
    });
    return session;
}

describe('the badge says what a screenshot would otherwise hide', () => {
    it('prints SCOPED LIVE REHEARSAL and the banner as WORDS', async () => {
        await mount(scopedFixture());
        const badge = $('[data-scope="vertical_slice"]');
        expect(badge).toBeTruthy();
        expect(badge.textContent).toMatch(/SCOPED LIVE REHEARSAL/);
        // The sentence is IN the badge, not in a title. A tooltip is invisible to a screenshot,
        // to a touchscreen and to the reader who never hovers.
        expect(badge.textContent).toContain(SCOPE_BANNER);
        expect(badge.getAttribute('title')).toBeNull();
    });

    it('renders nothing at all on a full-coverage run', async () => {
        await mount(completedFixture());
        expect($('[data-scope]')).toBeNull();
        expect($('[data-scope-panel]')).toBeNull();
    });

    it('survives onto a session that never reached the compiler', async () => {
        // The state the badge most has to survive, and the one a projection keyed on the graph
        // would lose: asked for as a slice, dead in the theorist, no selection recorded.
        const session = await mount(unrecordedScopeFixture());
        expect(session.execution_scope.recorded).toBe(false);
        expect($('[data-scope="vertical_slice"]')).toBeTruthy();
        expect($('[data-scope-unrecorded]')).toBeTruthy();
        expect(text()).toMatch(/asked/);
        // AND IT STILL REFUSES TO CLAIM COVERAGE. A run nobody recorded is not a run nobody bounded.
        expect($('[data-full-coverage="false"]')).toBeTruthy();
    });

    it('treats a mode this client cannot place as bounded, never as unbounded', () => {
        // An older client meeting a newer scope must not render it as a complete reading. Same
        // conservative direction `SHOULD_KEEP_WATCHING` takes for an unknown state.
        const scope = normalizeExecutionScope({ mode: 'quarter_slice', recorded: true });
        expect(scope.mode.known).toBe(false);
        expect(scope.bounded).toBe(true);
    });
});

describe('the mechanism panel', () => {
    it('shows every count §6 asks for, as a ratio rather than a bare number', async () => {
        await mount(scopedFixture());
        const stat = (name) => $(`[data-scope-stat="${name}"]`).textContent;
        expect(stat('source-units')).toMatch(/9\s*of\s*35/);
        expect(stat('atoms')).toMatch(/18\s*of\s*74/);
        expect(stat('claims')).toMatch(/2\s*of\s*5/);
        expect(stat('relation-batches')).toMatch(/1 sent, 1 permitted/);
        expect(stat('operationalizer-batches')).toMatch(/2 sent, 2 permitted/);
        expect(stat('reconciliation-rounds')).toMatch(/0 sent, 0 permitted/);
    });

    it('prints full_coverage: false as the headline', async () => {
        await mount(scopedFixture());
        expect($('[data-full-coverage="false"]').textContent).toMatch(/full_coverage: false/);
        expect(text()).toContain(SCOPE_BANNER);
    });

    it('names every excluded item with its reason, never as a count alone', async () => {
        await mount(scopedFixture());
        const rows = $$('[data-exclusion]');
        expect(rows.length).toBe(3);
        // All three kinds, and each carries its own sentence. A count tells a reader the size of
        // the gap; this is where it is.
        expect(rows.map((r) => r.getAttribute('data-exclusion')).sort())
            .toEqual(['claim', 'semantic_atom', 'source_unit']);
        for (const row of rows) expect(row.textContent.length).toBeGreaterThan(60);
        expect(text()).toMatch(/not investigated and not evidence of absence/);
        expect(text()).toMatch(/nobody asked/);
    });

    it('says which stage took longest and whether waiting or the model dominated', async () => {
        await mount(scopedFixture());
        expect($('[data-scope-stat="slowest-stage"]')).toBeTruthy();
        const split = $('[data-scope-stat="waiting-split"]');
        expect(split).toBeTruthy();
        // The 003D distinction, kept: a run that is mostly waiting is not a slow run, it is a run
        // inside a smaller allowance than the work needs, and the repairs are opposite.
        expect(split.querySelector('[data-dominant]')).toBeTruthy();
        expect(split.textContent).toMatch(/waiting for provider capacity/);
        expect(split.textContent).toMatch(/in the model/);
    });

    it('says why the run stopped', async () => {
        await mount(unrecordedScopeFixture());
        expect($('[data-scope-stop]').textContent).toMatch(/nothing to compile/);
    });

    it('says nothing at all about a bound nobody recorded', async () => {
        // The unrecorded run reached no pass, so `allowed` and `sent` are both null and the row is
        // ABSENT. Rendering `— sent, no limit` there would describe a pass that never happened.
        await mount(unrecordedScopeFixture());
        expect($('[data-scope-stat="relation-batches"]')).toBeNull();
        expect($('[data-scope-stat="operationalizer-batches"]')).toBeNull();
    });

    it('renders an unlimited bound as the word, never as a number', async () => {
        // `0` permitted is a real configuration in this lane and `null` is unlimited; a large
        // number in that slot would leave a reader guessing whether it was a bound nobody reached.
        //
        // CONSTRUCTED RATHER THAN FIXTURED, and the reason is worth recording: no scope the backend
        // currently writes mixes the two, because `configured_limits` sets all three bounds or
        // none. This asserts the rendering a partially-bounded scope would get, so a later lane
        // that bounds one pass and not another finds the answer already decided rather than
        // deciding it under deadline.
        const session = normalizeSession({
            ...unrecordedScopeFixture(),
            execution_scope: {
                mode: 'vertical_slice', recorded: true, full_coverage: false,
                relation_batches_allowed: null, relation_batches_sent: 3,
                exclusions: [], notes: [],
            },
        });
        await act(async () => { root.render(<ScopePanel session={session} />); });
        const rel = $('[data-scope-stat="relation-batches"]');
        expect(rel.querySelector('[data-unbounded="true"]').textContent).toBe('no limit');
        expect(rel.textContent).not.toMatch(/\d+ permitted/);
    });
});

describe('the entry control', () => {
    async function entry(features) {
        await act(async () => {
            root.render(<InquiryEntry corpusClient={{
                usePosts: () => ({ posts: [], isLoading: false, error: null,
                    hasNextPage: false, fetchNextPage: () => {} }),
            }} features={features} onStart={() => {}} />);
        });
    }

    it('is absent until the backend declares the feature', async () => {
        await entry(null);
        expect($('[data-scope-toggle]')).toBeNull();
        await entry(normalizeFeatures({ scoped_rehearsal: { available: false } }));
        expect($('[data-scope-toggle]')).toBeNull();
    });

    it('appears, unchecked, when the backend declares it', async () => {
        await entry(normalizeFeatures({ scoped_rehearsal: { available: true } }));
        const toggle = $('[data-scope-toggle] input');
        expect(toggle).toBeTruthy();
        expect(toggle.checked).toBe(false);
        // The label is the sentence a person needs BEFORE they start, not an explanation offered
        // afterwards.
        expect($('[data-scope-toggle]').textContent).toMatch(/declared subset/);
    });

    it('warns, in the form, once it is checked', async () => {
        await entry(normalizeFeatures({ scoped_rehearsal: { available: true } }));
        expect($('[data-scope-warning]')).toBeNull();
        await act(async () => { $('[data-scope-toggle] input').click(); });
        expect($('[data-scope-warning]').textContent).toContain(SCOPE_BANNER);
    });

    it('sends `full` on an ordinary start and never omits the field', () => {
        expect(startInquiryBody({ imageIds: ['p1'], prompt: 'q' }).execution_scope).toBe('full');
        expect(startInquiryBody({ imageIds: ['p1'], prompt: 'q', executionScope: 'vertical_slice' })
            .execution_scope).toBe('vertical_slice');
    });

    it('does not coerce an unrecognised scope into a familiar one', () => {
        // The server refuses it visibly. Rewriting it here would put the silent fallback the whole
        // contract forbids inside the client instead.
        expect(startInquiryBody({ imageIds: ['p1'], prompt: 'q', executionScope: 'quarter' })
            .execution_scope).toBe('quarter');
    });
});

describe('the stylesheet carries none of the meaning', () => {
    const css = () => fs.readFileSync(path.join(HERE, 'inquiryWorkbench.css'), 'utf8');
    const rule = (selector) => {
        const m = css().match(new RegExp(`\\${selector}\\s*\\{([^}]*)\\}`));
        return m ? m[1].replace(/\s+/g, ' ').trim() : null;
    };

    it('does not let the scope badge share the deployment badge treatment', () => {
        // Two different questions — "was this read or replayed" and "was all of it looked at" —
        // and neither is a degree of the other. A shared class would let a change to one silently
        // restyle the other.
        expect(rule('.iw-scope--vertical_slice') || rule('.iw-scope'))
            .not.toBe(rule('.iw-deployment--live'));
    });

    it('gives an unrecognised scope its own treatment rather than the softer one', () => {
        expect(rule('.iw-scope--unknown')).not.toBe(rule('.iw-scope'));
    });
});

describe('the batch plan tells the partition from what was sent', () => {
    it('carries batches_sent apart from batches', () => {
        const scoped = normalizeSession(scopedFixture());
        const whole = normalizeSession(batchedCouncilFixture());
        const plan = (s) => s.graph.passes.find((p) => p.pass_name.value === 'relation_architect')
            .batch_plan;
        // THE SAME PARTITION, one request permitted. Four planned in both; one sent here.
        expect(plan(scoped).batches).toBe(4);
        expect(plan(scoped).batches_sent).toBe(1);
        expect(plan(whole).batches).toBe(4);
        expect(plan(whole).batches_sent).toBeNull();
    });
});
