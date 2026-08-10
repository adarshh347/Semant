/**
 * INQUIRY WORKBENCH — the council, and where the time went. HARNESS-003D.
 *
 * 003C made the STAGE mechanism visible: which stage failed, what entered it, what came out. That
 * is the right shape for a compiler that is one call. The dissolution council is five passes and
 * two of them can come back differently disappointing, so a surface that showed only a compiler
 * stage would report "the compilation was thin" for a run whose dissector was rate-limited out —
 * two facts with opposite repairs, printed as one.
 *
 * These are the pixel guarantees this lane adds, asserted in the DOM rather than promised in a
 * comment:
 *
 *   · a pass row per pass, with the mind that ran it and the outcome in the council's own words;
 *   · SENDS separated from CALLS, so the account's allowance is never read as extra questions;
 *   · a wait that was TAKEN and a wait the budget REFUSED do not render alike;
 *   · the backend's own coverage arithmetic printed, `lost` as its own number;
 *   · LIVE, REPLAY and FIXTURE said out loud beside the state, with `undeclared` its own answer.
 *
 * The sibling suites keep their own halves: `backendParity.test.js` checks these objects against
 * the checked-in backend sample, and `artifactLedger.dom.test.jsx` owns the dissolution ledger's
 * source units, atoms and dispositions.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import ArtifactLedger from './ArtifactLedger.jsx';
import { DeploymentBadge } from './InquiryWorkbenchPage.jsx';
import { normalizeSession, totalWaitedMs, earliestFailingPass } from './inquiryContract.js';
import { councilFixture, pacedOutFixture, dissolvedFixture } from './inquiryFixtures.js';

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
const click = async (el) => { await act(async () => { el.click(); }); };

async function mount(fixture) {
    const session = normalizeSession(fixture);
    await act(async () => { root.render(<ArtifactLedger session={session} />); });
    return session;
}

const row = (id) => $(`[data-artifact="${id}"]`);
const openRow = async (id) => { await click(row(id).querySelector('.iw-expand')); };
const pass = (name) => $(`[data-pass="${name}"]`);

// ── the council, pass by pass ───────────────────────────────────────────────

describe('TestCouncilPassesAreVisible', () => {
    it('renders one row per pass, in the order the council ran them', async () => {
        await mount(councilFixture());
        expect(row('passes').dataset.count).toBe('5');
        await openRow('passes');
        expect($$('.iw-pass').map((n) => n.dataset.pass)).toEqual([
            'source_ledger', 'semantic_dissector', 'targeted_repair',
            'relation_architect', 'epistemic_operationalizer',
        ]);
    });

    it('names the mind that came up short, not the compilation', async () => {
        // `provenance.compiler` is null in v2 on purpose — naming one of three minds as the author
        // of the whole graph would be a lie — so this row IS the receipt, and it has to be able to
        // say WHICH pass disappointed.
        const session = await mount(councilFixture());
        expect(earliestFailingPass(session.graph).pass_name.value).toBe('targeted_repair');
        await openRow('passes');
        expect(pass('targeted_repair').className).toContain('is-underperforming');
        expect(pass('targeted_repair').dataset.passOutcome).toBe('thin');
        expect(pass('semantic_dissector').className).not.toContain('is-underperforming');
        expect(pass('targeted_repair').textContent)
            .toMatch(/produced less than its inputs implied/);
    });

    it('the row warns when any pass underperformed, and is quiet when none did', async () => {
        await mount(councilFixture());
        expect(row('passes').className).toContain('iw-led-row--warn');

        await act(async () => { root.unmount(); });
        root = createRoot(container);
        const clean = councilFixture();
        clean.graph.passes = clean.graph.passes.filter((p) => p.outcome === 'completed');
        await mount(clean);
        expect(row('passes').className).not.toContain('iw-led-row--warn');
    });

    it('is silent about the council on a graph that carries no pass receipts', async () => {
        // Lane A's v1 graph has none. A surface that showed "0 passes" as a defect would report a
        // session compiled by a single call as a council that never ran.
        await mount(dissolvedFixture());
        expect(row('passes').dataset.count).toBe('0');
        expect(row('passes').className).not.toContain('iw-led-row--warn');
    });
});

// ── the account's allowance is not the inquiry's questions ──────────────────

describe('TestSendsAreNotCalls', () => {
    it('prints sends separately where the same bytes went twice', async () => {
        // Four sends for two calls is a rate limit, not two extra questions. A surface that showed
        // only one number would report an account's allowance as the compiler asking more.
        await mount(councilFixture());
        await openRow('passes');
        const facts = pass('semantic_dissector');
        expect(facts.querySelector('[data-fact="calls"]').textContent).toBe('2 calls');
        expect(facts.querySelector('[data-fact="sends"]').textContent)
            .toMatch(/4 sends — identical bytes, re-sent after a capacity refusal/);
    });

    it('says nothing about sends on the ordinary pass where they equal the calls', async () => {
        await mount(councilFixture());
        await openRow('passes');
        expect(pass('source_ledger').querySelector('[data-fact="sends"]')).toBeNull();
        expect(pass('source_ledger').querySelector('[data-fact="calls"]').textContent)
            .toBe('1 call');
    });
});

// ── waiting, and being refused the wait ─────────────────────────────────────

describe('TestWaitingIsVisible', () => {
    it('prints how long a pass spent waiting, and where the number came from', async () => {
        const session = await mount(councilFixture());
        expect(totalWaitedMs(session.graph)).toBe(41000);
        await openRow('passes');
        expect(pass('semantic_dissector').querySelector('[data-fact="waited"]').textContent)
            .toMatch(/41.0s waiting for provider capacity/);
        const waits = $$('[data-waits-for="pss_2"] li');
        expect(waits.map((n) => n.dataset.waitSource))
            .toEqual(['provider_message', 'provider_retry_after']);
        expect(waits[1].textContent).toMatch(/the provider said how long to wait/);
    });

    it('a pass that never waited has no waiting row, rather than a zero', async () => {
        // `waited_ms: 0` would say a pacer answered and reported no wait. Nothing paced this pass.
        await mount(councilFixture());
        await openRow('passes');
        expect(pass('relation_architect').querySelector('[data-fact="waited"]')).toBeNull();
        expect(text()).not.toContain('0 ms waiting');
    });

    it('a wait the budget REFUSED says the run stopped, not that it waited', async () => {
        // The whole pacing design exists so a run ends honestly short instead of quietly shrinking
        // its reading to fit an allowance. Rendering the gate as one more wait would hide that.
        await mount(pacedOutFixture());
        await openRow('passes');
        const stopped = $('[data-waits-for="pss_4"] [data-wait-taken="false"]');
        expect(stopped).toBeTruthy();
        expect(stopped.className).toContain('iw-wait--stopped');
        expect(stopped.textContent).toMatch(/the run stopped waiting/);
        expect(stopped.textContent).toMatch(/declared time budget ran out, so nothing waited/);
        expect(stopped.textContent).not.toMatch(/^waited/);
    });

    it('says at the row that what is below is what it got to, not what there was', async () => {
        await mount(pacedOutFixture());
        expect(row('passes').textContent)
            .toMatch(/stopped waiting for provider capacity before every pass had finished/);
        expect(row('passes').textContent).toMatch(/what it got to, not what there was/);
    });

    it('a run that was never rate limited says nothing about capacity at all', async () => {
        const clean = councilFixture();
        clean.graph.passes = clean.graph.passes.map((p) => ({
            ...p, capacity_waits: [], waited_ms: null, transport_attempts: p.call_count,
        }));
        await mount(clean);
        expect(row('passes').textContent).not.toMatch(/capacity/i);
        await openRow('passes');
        expect($('[data-fact="sends"]')).toBeNull();
        expect($('.iw-pass-waits')).toBeNull();
    });
});

// ── the backend's arithmetic, printed rather than recomputed ────────────────

describe('TestCoverageSummaryIsTheBackends', () => {
    it('prints the backend\'s own numbers, with lost as its own', async () => {
        await mount(councilFixture());
        await openRow('coverage');
        const summary = $('[data-coverage-summary="true"]');
        expect(summary.textContent).toMatch(/4 of 5 source unit\(s\) disposed of/);
        expect(summary.textContent).toMatch(/3 represented/);
        expect(summary.querySelector('[data-lost-count]').textContent).toBe('1 lost');
        expect(summary.textContent).toMatch(/2 from you, 3 from the reading/);
        expect(summary.textContent).toMatch(/the ledger does NOT balance/);
    });

    it('shows the backend\'s number even when the rows below disagree with it', async () => {
        // The summary and the rows are computed on opposite sides of the wire. A client that
        // recomputed the summary from the rows it happens to hold would make every divergence
        // invisible — and a coverage ledger's whole job is to be checkable.
        const diverging = councilFixture();
        diverging.graph.coverage_summary = {
            ...diverging.graph.coverage_summary, disposed: 5, represented: 4, lost_count: 0,
            lost: [], complete: true,
        };
        await mount(diverging);
        await openRow('coverage');
        expect($('[data-coverage-summary="true"]').textContent)
            .toMatch(/5 of 5 source unit\(s\) disposed of/);
        expect($$('[data-coverage-for]')).toHaveLength(4);   // the rows still say four
    });

    it('makes no coverage claim for a graph that declared none', async () => {
        // Tri-state, and the null is the point: rendering an absent summary as `false` would
        // accuse a v1 compilation of failing a check it never declared.
        const session = await mount(dissolvedFixture());
        expect(session.graph.coverage_summary.complete).toBeNull();
        expect(session.graph.coverage_summary.source_units).toBeNull();
        await openRow('coverage');
        expect($('[data-coverage-summary="true"]')).toBeNull();
        expect(text()).not.toMatch(/does NOT balance|the ledger balances/);
    });
});

// ── live, replay, fixture — said out loud ───────────────────────────────────

describe('TestDeploymentIsDeclared', () => {
    const badge = async (deployment) => {
        const session = normalizeSession({ ...councilFixture(), deployment });
        await act(async () => {
            root.render(<DeploymentBadge deployment={session.deployment} />);
        });
        return session;
    };

    it('says LIVE beside a session whose minds are actually bound', async () => {
        await badge({ kind: 'live', declared: true, reachable: true, detail: 'bound to groq' });
        expect($('[data-deployment="live"]')).toBeTruthy();
        expect($('.iw-deployment-kind').textContent).toBe('LIVE');
        expect($('[data-declared="true"]')).toBeTruthy();
        expect($('[data-deployment="live"]').getAttribute('title')).toBe('bound to groq');
    });

    it('says REPLAY for a frozen council, so a dull run cannot read as a dull model', async () => {
        await badge({ kind: 'replay', declared: true, reachable: null, detail: '' });
        expect($('[data-deployment="replay"]')).toBeTruthy();
        expect($('.iw-deployment-kind').textContent).toBe('REPLAY');
        expect($('[data-deployment="live"]')).toBeNull();
    });

    it('an UNDECLARED deployment is its own answer, never a quiet live', async () => {
        await badge(undefined);
        expect($('[data-deployment="undeclared"]')).toBeTruthy();
        expect($('[data-declared="false"]')).toBeTruthy();
        expect($('.iw-deployment-kind').textContent).not.toBe('LIVE');
        expect($('[data-deployment="undeclared"]').getAttribute('title'))
            .toMatch(/did not say/i);
    });

    it('names an unreachable provider, which only a live binding can be', async () => {
        await badge({ kind: 'live', declared: true, reachable: false, detail: '' });
        expect($('[data-unreachable="true"]').textContent).toBe('provider unreachable');

        await act(async () => { root.unmount(); });
        root = createRoot(container);
        await badge({ kind: 'fixture', declared: true, reachable: null, detail: '' });
        expect($('[data-unreachable="true"]')).toBeNull();
    });
});

// ── the stylesheet has to keep these apart too ──────────────────────────────

describe('the stylesheet keeps the council\'s distinctions', () => {
    const css = () => fs.readFileSync(path.join(HERE, 'inquiryWorkbench.css'), 'utf8');
    const rule = (selector) => {
        const m = css().match(new RegExp(`\\${selector}\\s*\\{([^}]*)\\}`));
        return m ? m[1].replace(/\s+/g, ' ').trim() : null;
    };

    it('gives each deployment its own treatment, undeclared included', () => {
        const kinds = ['live', 'replay', 'fixture', 'undeclared'];
        const seen = new Map();
        for (const k of kinds) {
            const r = rule(`.iw-deployment--${k}`);
            expect([k, r]).not.toEqual([k, null]);
            expect([k, seen.get(r)]).toEqual([k, undefined]);   // no two share one
            seen.set(r, k);
        }
        // and the one that matters without colour: an undeclared deployment is struck through,
        // because a reader who cannot tell red from grey must still not read it as a claim.
        expect(rule('.iw-deployment--undeclared')).toMatch(/line-through/);
    });

    it('never lets a replay wear the live treatment', () => {
        expect(rule('.iw-deployment--replay')).not.toBe(rule('.iw-deployment--live'));
        expect(rule('.iw-deployment--fixture')).not.toBe(rule('.iw-deployment--live'));
    });

    it('gives every pass outcome its own treatment', () => {
        const outcomes = ['completed', 'thin', 'truncated', 'coverage_failed', 'empty',
            'refused', 'unavailable', 'error', 'unknown'];
        const seen = new Map();
        for (const o of outcomes) {
            const r = rule(`.iw-pass-outcome--${o}`);
            expect([o, r]).not.toEqual([o, null]);
            expect([o, seen.get(r)]).toEqual([o, undefined]);
            seen.set(r, o);
        }
    });

    it('separates a refused wait from a taken one', () => {
        expect(rule('.iw-wait--stopped')).not.toBe(rule('.iw-pass-waited'));
        expect(rule('.iw-wait--stopped')).not.toBeNull();
    });
});
