/**
 * INQUIRY WORKBENCH — the surface, driven through the client boundary.
 *
 * Every test here starts at the entry form and reaches the rest of the page the way a person
 * does: fill the prompt, pick images, press Begin, and let the mocked HTTP boundary answer. No
 * test injects a session into a panel — the point is the round trip, and a surface whose panels
 * are individually correct can still fail to hand a decision back to the same session.
 *
 * The suites this complements:
 *   · inquiryContract.test.js   — what a payload means
 *   · inquiryClient.test.js     — what goes on the wire, and what a 409 is
 *   · inquiryEntry.dom.test.jsx — the form's own gates
 *   · inquiryGraph.dom.test.jsx — the reading/claims/observables/decision panels
 *   · inquiryOutput.dom.test.jsx— capability, evidence, synthesis, remainder, trace
 *
 * and this one: the thread, the honesty guarantees in the assembled DOM, and the guards that read
 * the source and stylesheet directly.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import InquiryWorkbenchPage from './InquiryWorkbenchPage.jsx';
import { createMockInquiryClient, InquiryRequestError } from './inquiryClient.js';
import {
    consultFixture, respondedFixture, completedFixture, autoFixture, outcomesFixture,
    conflictSessionFixture, duplicateSessionFixture, unknownFutureFixture, otherDomainFixture,
    measuredEvidenceFixture, compilingFixture, FIXTURE_CORPUS, FIXTURE_PROMPT,
} from './inquiryFixtures.js';

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
const settle = async () => { await act(async () => { await Promise.resolve(); }); };

/** Source with comments removed — see the import guard for why this matters. */
const stripComments = (src) =>
    src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

const POSTS = FIXTURE_CORPUS.map((c) => ({
    id: c.post_id, photo_url: c.image_url, title: c.title, region_annotations: [],
}));

/** Mount the page and drive the real entry form to a started session. */
async function startInquiry(clientOpts, { prompt = 'why is this centred?' } = {}) {
    const client = createMockInquiryClient(clientOpts);
    await act(async () => {
        root.render(<InquiryWorkbenchPage client={client} posts={POSTS} />);
    });

    const box = $('.iw-prompt');
    await act(async () => {
        Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')
            .set.call(box, prompt);
        box.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await click($('.iw-thumb'));
    await click($('.iw-start'));
    await settle();
    return client;
}

// ── 1. the thread: prompt → graph → decision → resumed → answer ─────────────

describe('the whole thread, through a mocked network boundary', () => {
    it('starts from the form and renders the reading, claims and observables it got back', async () => {
        await startInquiry({ script: [consultFixture()] });

        expect($('.iw-entry')).toBeNull();                 // the form gave way to the session
        expect($('.iw-session-prompt').textContent).toBe(FIXTURE_PROMPT);
        expect($('.iw-reading-text')).toBeTruthy();
        expect($$('.iw-claim').length).toBe(4);
        expect($$('.iw-obs').length).toBe(3);
        expect($$('.iw-session-images li').length).toBe(2);
    });

    it('focuses the open decision without hiding what led to it', async () => {
        await startInquiry({ script: [consultFixture()] });

        expect($('.iw-decision-card')).toBeTruthy();
        expect(document.activeElement).toBe($('.iw-decision-question'));
        // the reasoning is still on the page, above and below
        expect($('.iw-reading-text')).toBeTruthy();
        expect($$('.iw-claim').length).toBe(4);
        // and the affected claim and observable are marked rather than isolated
        expect($('[data-claim-id="clm_colonnade"]').className).toMatch(/is-highlighted/);
        expect($('[data-observable-id="obs_extent"]').className).toMatch(/is-highlighted/);
    });

    it('sends the choice with the expected revision and resumes the SAME session', async () => {
        const client = await startInquiry({
            script: [consultFixture()], afterResponse: respondedFixture(),
        });

        await click($('[data-option-id="opt_whole"]'));
        await click($('.iw-submit'));
        await settle();

        expect(client._responses).toHaveLength(1);
        expect(client._responses[0]).toMatchObject({
            decision_id: 'dec_extent_grain',
            selected_option_id: 'opt_whole',
            action: 'select',
            expected_revision: 3,
        });
        expect(client._responses[0].response_id).toMatch(/^res_/);

        // the same session id, moved on — the decision card is gone and the record is in the stream
        expect($('.iw-decision-card')).toBeNull();
        expect($('[data-decider="user"]').textContent).toMatch(/You chose/);
        expect(text()).toMatch(/revision 5/);
    });

    it('renders the SIMULATED receipt and gives it no evidence badge', async () => {
        await startInquiry({
            script: [consultFixture()], afterResponse: respondedFixture(),
        });
        await click($('[data-option-id="opt_whole"]'));
        await click($('.iw-submit'));
        await settle();

        const receipt = $('[data-receipt-id="capr_locate_1"]');
        expect(receipt.dataset.outcome).toBe('simulated');
        expect(receipt.querySelector('.iw-simulated').textContent).toBe('SIMULATED — not evidence');
        // nothing anywhere on the page claims a measurement
        expect($('.iw-badge--measured')).toBeNull();
        expect($('.iw-badge--visible')).toBeNull();
        expect($('.iw-evidence-item')).toBeNull();
    });

    it('renders the cited answer, the remainder and a trace with both actors', async () => {
        await startInquiry({
            script: [consultFixture()], afterResponse: completedFixture(),
        });
        await click($('[data-option-id="opt_whole"]'));
        await click($('.iw-submit'));
        await settle();

        expect($$('.iw-section').length).toBe(3);
        await click($('[data-section-id="sec_front"] .iw-expand'));
        expect($('[data-claim-ref="clm_colonnade"]')).toBeTruthy();

        expect($$('.iw-remainder-item').length).toBe(2);
        expect($('.iw-remainder').textContent).toMatch(/temple portico/);

        await click($('.iw-trace .iw-expand'));
        expect($('[data-actor-kind="user"]')).toBeTruthy();
        expect($('[data-actor-kind="model"]')).toBeTruthy();
        expect($('[data-actor-kind="system"]')).toBeTruthy();
    });

    it('free text goes out as an amendment and comes back attributed to the person', async () => {
        const client = await startInquiry({
            script: [consultFixture()],
            afterResponse: {
                ...respondedFixture(),
                decision_records: [{
                    ...respondedFixture().decision_records[0],
                    action: 'amend',
                    selected_option_id: '',
                    selected_label: '',
                    free_text: 'narrow it to the west end',
                }],
            },
        });

        const box = $('#iw-free-text');
        await act(async () => {
            Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')
                .set.call(box, 'narrow it to the west end');
            box.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await click($('.iw-submit'));
        await settle();

        expect(client._responses[0]).toMatchObject({
            action: 'amend', free_text: 'narrow it to the west end',
        });
        expect(client._responses[0]).not.toHaveProperty('selected_option_id');
        expect($('.iw-decision-free .iw-author--user').textContent).toBe('your direction');
    });

    it('an auto session shows what was chosen for you, without ever pausing', async () => {
        await startInquiry({ script: [autoFixture()] });
        expect($('.iw-decision-card')).toBeNull();
        const row = $('[data-decider="system"]');
        expect(row.textContent).toMatch(/Semant chose, without asking/);
        expect(row.textContent).toMatch(/Reversible, non-authorial/);
    });

    it('shows a working state rather than an instant answer', async () => {
        await startInquiry({ script: [compilingFixture()] });
        expect($('[data-state="compiling"]')).toBeTruthy();
        expect($('.iw-pulse')).toBeTruthy();
        expect($('.iw-synthesis')).toBeNull();
    });
});

// ── 2. the conflict ─────────────────────────────────────────────────────────

describe('a 409 conflict', () => {
    it('refreshes the session, explains itself, and does NOT discard the input', async () => {
        await startInquiry({
            script: [consultFixture()],
            afterResponse: respondedFixture(),
            conflictOnce: true,
            conflictSession: conflictSessionFixture(),
        });

        await click($('[data-option-id="opt_whole"]'));
        await click($('.iw-submit'));
        await settle();

        const conflict = $('[data-conflict="stale"]');
        expect(conflict).toBeTruthy();
        expect(conflict.textContent).toMatch(/moved on while you were deciding/i);
        expect(conflict.textContent).toMatch(/refreshed/i);
        // the selection survived, and so did its preview
        expect($('[data-option-id="opt_whole"]').getAttribute('aria-checked')).toBe('true');
        expect($('.iw-preview')).toBeTruthy();
    });

    it('resubmits the same response id against the refreshed revision, and lands', async () => {
        const client = await startInquiry({
            script: [consultFixture()],
            afterResponse: respondedFixture(),
            conflictOnce: true,
            conflictSession: conflictSessionFixture(),
        });

        await click($('[data-option-id="opt_whole"]'));
        await click($('.iw-submit'));
        await settle();
        await click($('.iw-submit'));
        await settle();

        expect(client._responses).toHaveLength(1);        // the first attempt never landed
        expect(client._responses[0].expected_revision).toBe(6);
        expect($('.iw-decision-card')).toBeNull();
        expect($('[data-conflict="stale"]')).toBeNull();
    });

    it('a DUPLICATE — answered elsewhere — is explained even with no card left to attach it to', async () => {
        // The other conflict, with the opposite right answer. The refreshed session has closed
        // the decision, so nothing here may invite a resubmit; and dropping the message because
        // its card had gone would leave the person's submit looking like it silently did nothing.
        await startInquiry({
            script: [consultFixture()],
            afterResponse: respondedFixture(),
            conflictOnce: true,
            conflictSession: duplicateSessionFixture(),
        });

        await click($('[data-option-id="opt_whole"]'));
        await click($('.iw-submit'));
        await settle();

        expect($('.iw-decision-card')).toBeNull();
        const notice = $('[data-conflict="answered"]');
        expect(notice.textContent).toMatch(/answered somewhere else/i);
        expect(notice.textContent).toMatch(/not applied a second time/i);
        // the session under it is the current one, carrying the answer that did land
        expect($('[data-decider="user"]').textContent).toMatch(/Answered in another tab/);
    });

    it('a plain failure is NOT dressed as a conflict', async () => {
        const client = createMockInquiryClient({ script: [consultFixture()] });
        client.respond = async () => {
            throw new InquiryRequestError('the server fell over', { status: 500 });
        };
        await act(async () => {
            root.render(<InquiryWorkbenchPage client={client} posts={POSTS} />);
        });
        const box = $('.iw-prompt');
        await act(async () => {
            Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')
                .set.call(box, 'q');
            box.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await click($('.iw-thumb'));
        await click($('.iw-start'));
        await settle();

        await click($('[data-option-id="opt_whole"]'));
        await click($('.iw-submit'));
        await settle();

        expect($('[data-conflict="stale"]')).toBeNull();
        expect($('.iw-error').textContent).toMatch(/the server fell over/);
        // and the decision is still open, so the person can try again
        expect($('.iw-decision-card')).toBeTruthy();
    });
});

// ── 3. the production surface never substitutes a fixture ───────────────────

describe('an absent API', () => {
    it('says the API is unavailable and shows no session at all', async () => {
        const client = createMockInquiryClient({ script: [consultFixture()] });
        client.start = async () => {
            throw new InquiryRequestError('Not Found', { status: 404 });
        };
        await act(async () => {
            root.render(<InquiryWorkbenchPage client={client} posts={POSTS} />);
        });
        const box = $('.iw-prompt');
        await act(async () => {
            Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')
                .set.call(box, 'q');
            box.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await click($('.iw-thumb'));
        await click($('.iw-start'));
        await settle();

        const box2 = $('[data-unavailable="api"]');
        expect(box2).toBeTruthy();
        expect(box2.textContent).toContain('404');
        // NOT ONE PANEL of fixture content stands in for the missing backend
        expect($('.iw-reading-text')).toBeNull();
        expect($('.iw-claim')).toBeNull();
        expect($('.iw-decision-card')).toBeNull();
        expect($('.iw-session-prompt')).toBeNull();
        expect(text()).not.toContain(FIXTURE_PROMPT);
    });

    it('a network failure with no status also reports unavailable', async () => {
        const client = createMockInquiryClient({ script: [consultFixture()] });
        client.start = async () => { throw new Error('Failed to fetch'); };
        await act(async () => {
            root.render(<InquiryWorkbenchPage client={client} posts={POSTS} />);
        });
        const box = $('.iw-prompt');
        await act(async () => {
            Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')
                .set.call(box, 'q');
            box.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await click($('.iw-thumb'));
        await click($('.iw-start'));
        await settle();
        expect($('[data-unavailable="api"]').textContent).toMatch(/Failed to fetch/);
    });

    it('the page module never imports a fixture', () => {
        // The structural half of the same guarantee: a page that cannot reach the fixtures cannot
        // fall back to them, however a future refactor is written.
        const src = fs.readFileSync(path.join(HERE, 'InquiryWorkbenchPage.jsx'), 'utf8');
        expect(src).not.toMatch(/from\s+['"]\.\/inquiryFixtures/);
        for (const f of fs.readdirSync(HERE)) {
            if (!/\.jsx?$/.test(f) || f.includes('.test.') || f === 'inquiryFixtures.js') continue;
            const s = fs.readFileSync(path.join(HERE, f), 'utf8');
            expect([f, /inquiryFixtures/.test(s)]).toEqual([f, false]);
        }
    });
});

// ── 4. honesty in pixels, on the assembled page ─────────────────────────────

describe('honesty in pixels', () => {
    it('the word "measured" appears nowhere in a session that measured nothing', async () => {
        await startInquiry({
            script: [consultFixture()], afterResponse: completedFixture(),
        });
        await click($('[data-option-id="opt_whole"]'));
        await click($('.iw-submit'));
        await settle();
        await click($('[data-receipt-id="capr_locate_1"] .iw-expand'));

        expect($('.iw-badge--measured')).toBeNull();
        expect($('[data-status="measured"]')).toBeNull();
        // the only occurrences are the sentences DENYING a measurement
        const claims = text().match(/measure\w*/gi) || [];
        expect(claims.length).toBeGreaterThan(0);
        expect(text()).toMatch(/Nothing here has been measured/i);
        expect(text()).toMatch(/nothing was measured/i);
    });

    it('a measured badge appears once a backend evidence object supplies one', async () => {
        await startInquiry({ script: [measuredEvidenceFixture()] });
        expect($('.iw-evidence-item [data-status="measured"]')).toBeTruthy();
        expect($('[data-verdict="supports"]')).toBeTruthy();
        // and it came from the evidence panel, not from the receipt
        expect($('.iw-receipt [data-status="measured"]')).toBeNull();
    });

    it('the reading is interpretive and never sits under a stronger label', async () => {
        await startInquiry({ script: [consultFixture()] });
        const reading = $('.iw-reading');
        expect(reading.querySelector('.iw-badge--interpretive')).toBeTruthy();
        expect(reading.querySelector('.iw-badge--measured')).toBeNull();
        expect(reading.querySelector('.iw-badge--visible')).toBeNull();
    });

    it('an unavailable outcome is never rendered as an empty one', async () => {
        await startInquiry({ script: [outcomesFixture()] });
        const unavailable = $('[data-receipt-id="capr_unavailable"]');
        const empty = $('[data-receipt-id="capr_empty"]');
        expect(unavailable.dataset.outcome).toBe('unavailable');
        expect(empty.dataset.outcome).toBe('empty');
        expect(unavailable.textContent).toMatch(/nothing was attempted/i);
        expect(empty.textContent).toMatch(/ran and returned nothing/i);
        expect(unavailable.textContent).not.toMatch(/returned nothing/i);
    });

    it('an unknown future session coerces nothing into a familiar success', async () => {
        await startInquiry({ script: [unknownFutureFixture()] });
        expect($('[data-state="unknown"]')).toBeTruthy();
        expect($('[data-claim-id="clm_future"]').dataset.status).toBe('unknown');
        expect($('[data-outcome="unknown"]')).toBeTruthy();
        // nothing was promoted: no measured badge, no live receipt, no evidence item
        expect($('.iw-badge--measured')).toBeNull();
        expect($('[data-outcome="live"]')).toBeNull();
        expect($('.iw-evidence-item')).toBeNull();
    });
});

// ── 5. the stylesheet's own distinctions ────────────────────────────────────

describe('the stylesheet keeps the distinctions it claims', () => {
    const css = () => fs.readFileSync(path.join(HERE, 'inquiryWorkbench.css'), 'utf8');
    const rule = (selector) => {
        const m = css().match(new RegExp(`\\${selector}\\s*\\{([^}]*)\\}`));
        return m ? m[1].replace(/\s+/g, ' ').trim() : null;
    };

    it('gives every capability outcome its own treatment', async () => {
        const outcomes = ['live', 'simulated', 'empty', 'unavailable', 'refused', 'capability_gap'];
        const seen = new Map();
        for (const o of outcomes) {
            const r = rule(`.iw-outcome--${o}`);
            expect([o, r]).not.toEqual([o, null]);
            expect([o, seen.get(r)]).toEqual([o, undefined]);   // no two share one
            seen.set(r, o);
        }
    });

    it('never lets simulated wear the live treatment', () => {
        expect(rule('.iw-outcome--simulated')).not.toBe(rule('.iw-outcome--live'));
        expect(rule('.iw-receipt--simulated')).not.toBe(rule('.iw-receipt--live'));
        // the simulated row is dashed: a distinction that survives without colour
        expect(rule('.iw-receipt--simulated')).toMatch(/dashed/);
    });

    it('gives every claim status its own treatment', () => {
        const statuses = ['measured', 'visible', 'sourced', 'interpretive', 'imagined',
            'proposed', 'unresolved', 'unknown'];
        const seen = new Map();
        for (const s of statuses) {
            const r = rule(`.iw-badge--${s}`);
            expect([s, r]).not.toEqual([s, null]);
            expect([s, seen.get(r)]).toEqual([s, undefined]);
            seen.set(r, s);
        }
    });

    it('keeps unavailable and capability_gap visually apart', () => {
        expect(rule('.iw-availability--unavailable'))
            .not.toBe(rule('.iw-availability--capability_gap'));
        expect(rule('.iw-obs--unavailable')).not.toBe(rule('.iw-obs--capability_gap'));
    });

    it('honours reduced motion without removing the fact that something is working', () => {
        const block = css().match(/@media \(prefers-reduced-motion: reduce\) \{([\s\S]*?)\n\}/g);
        expect(block).toBeTruthy();
        const joined = block.join('\n');
        expect(joined).toMatch(/\.iw-pulse\s*\{[^}]*animation:\s*none/);
        // still visible: whether the inquiry is still moving is information, not decoration
        expect(joined).toMatch(/\.iw-pulse\s*\{[^}]*opacity:\s*1/);
    });

    it('uses editorial tokens rather than hard-coded colour', () => {
        const hexes = css().match(/#[0-9a-f]{3,8}\b/gi) || [];
        expect(hexes).toEqual([]);
    });
});

// ── 6. lane boundaries ──────────────────────────────────────────────────────

describe('this lane stays in its lane', () => {
    it('imports nothing from another surface except the shared api config', () => {
        const allowed = /^(react|react-dom|node:|\.\/|\.\.\/config\/api)/;
        const offenders = [];
        for (const f of fs.readdirSync(HERE)) {
            if (!/\.(js|jsx)$/.test(f) || f.includes('.test.')) continue;
            // Comments are stripped first. Prose in this codebase says "from" a lot, and the
            // first draft of this guard reported two module docstrings as illegal imports —
            // a check that can be tripped by a sentence is a check nobody will trust.
            const src = stripComments(fs.readFileSync(path.join(HERE, f), 'utf8'));
            for (const m of src.matchAll(/from\s+['"]([^'"]+)['"]/g)) {
                if (!allowed.test(m[1])) offenders.push(`${f} → ${m[1]}`);
            }
        }
        // `config/api` is imported rather than reimplemented: it patches `window.fetch` once to
        // inject the API key, and a second place doing that would be a second place to get it
        // wrong. Everything else this surface needs, it owns.
        expect(offenders).toEqual([]);
    });

    it('registers no route and touches no backend path', () => {
        for (const f of fs.readdirSync(HERE)) {
            if (!/\.(js|jsx)$/.test(f) || f.includes('.test.')) continue;
            const src = fs.readFileSync(path.join(HERE, f), 'utf8');
            expect([f, /createBrowserRouter|<Route|useRoutes/.test(src)]).toEqual([f, false]);
        }
    });

    it('branches on no subject matter anywhere in the components', () => {
        // The board's rule is about production BRANCHES, so the check is against code with the
        // comments stripped. A prose paragraph explaining why HARNESS-001C2's fold phrases
        // mattered is not a topic branch, and a guard that could not tell those apart would have
        // to be either weakened or worked around — both of which end with it guarding nothing.
        const banned = /ottoman|pantheon|ajanta|sculpture|\bfold\b|nestedness/i;
        for (const f of fs.readdirSync(HERE)) {
            if (!/\.(js|jsx)$/.test(f) || f.includes('.test.') || f === 'inquiryFixtures.js') {
                continue;
            }
            const src = stripComments(fs.readFileSync(path.join(HERE, f), 'utf8'));
            expect([f, banned.test(src)]).toEqual([f, false]);
        }
    });

    it('renders an unrelated domain through exactly the same page', async () => {
        await startInquiry({ script: [otherDomainFixture()] });
        expect($('.iw-decision-card')).toBeTruthy();
        expect($('[data-claim-id="clm_boundary_follow"]')).toBeTruthy();
        expect($('[data-observable-id="obs_weld_network"]')).toBeTruthy();
        expect($$('.iw-remainder-item').length).toBe(1);
        expect(text()).toMatch(/grain boundaries/i);
    });
});

// ── 7. keyboard and labels on the assembled page ────────────────────────────

describe('the assembled page is reachable from a keyboard', () => {
    it('labels every region', async () => {
        await startInquiry({ script: [consultFixture()] });
        const labels = $$('[aria-label]').map((n) => n.getAttribute('aria-label'));
        for (const l of ['Question and images', 'Provisional reading', 'Claims',
            'How Semant could investigate', 'A decision is open']) {
            expect(labels).toContain(l);
        }
    });

    it('every expander says whether it is open', async () => {
        await startInquiry({ script: [completedFixture()] });
        const expanders = $$('.iw-expand').filter((b) => b.hasAttribute('aria-expanded'));
        expect(expanders.length).toBeGreaterThan(3);
        for (const b of expanders) expect(b.getAttribute('aria-expanded')).toBe('false');
        await click(expanders[0]);
        expect($$('.iw-expand')[0].getAttribute('aria-expanded')).toBe('true');
    });

    it('uses real buttons throughout, with no invented tab order', async () => {
        await startInquiry({ script: [consultFixture()] });
        for (const b of $$('.iw-option, .iw-expand, .iw-submit')) {
            expect(b.tagName).toBe('BUTTON');
            expect(b.getAttribute('tabindex')).toBeNull();
        }
        // the one deliberate tabindex is the decision heading, so focus can move to it
        expect($$('[tabindex]').map((n) => n.className)).toEqual(['iw-decision-question']);
    });
});
