/**
 * INQUIRY WORKBENCH — the whole mechanism, driven end to end, and the guards that keep it honest.
 *
 * This is HARNESS-003C's counterpart to `simulationHonesty.dom.test.jsx`: that file guards the
 * simulated-capability boundary, this one guards the three things the 002R rehearsal could not
 * see — which stage was running, what the run actually produced, and that a run which stopped
 * short is not a run that finished.
 *
 * Every guard below is named so a mutation can be pointed at it. A guard that cannot be made to
 * fail is not a guard.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import InquiryWorkbenchPage from './InquiryWorkbenchPage.jsx';
import { createMockInquiryClient } from './inquiryClient.js';
import { createMockCorpusClient } from '../inquiryCorpus/corpusClient.js';
import {
    runningStagesFixture, truncatedCompilerFixture, stagedCompleteFixture, barrenFixture,
} from './inquiryFixtures.js';

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

/** Two pages, so "selected across a page boundary" is a real boundary. */
const CORPUS_PAGES = [
    {
        posts: [
            { id: 'post_altes_front', photo_url: 'u1', text_blocks: [{ content: 'Lustgarten front' }] },
            { id: 'post_altes_rotunda', photo_url: 'u2', text_blocks: [{ content: 'Rotunda' }] },
        ],
        total_pages: 2,
    },
    {
        posts: [
            { id: 'post_stair', photo_url: 'u3', text_blocks: [{ content: 'The stair' }] },
        ],
        total_pages: 2,
    },
];

/** Start an inquiry through the real entry form: pick across pages, type, Begin. */
async function startInquiry(script, { afterResponse = null } = {}) {
    const client = createMockInquiryClient({ script, afterResponse });
    const corpusClient = createMockCorpusClient({ pages: CORPUS_PAGES });
    await act(async () => {
        root.render(<InquiryWorkbenchPage client={client} corpusClient={corpusClient} />);
    });

    await click($('[data-post-id="post_altes_front"]'));
    await click($('.ic-more'));
    await click($('[data-post-id="post_stair"]'));

    const prompt = $('.iw-prompt');
    await act(async () => {
        Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')
            .set.call(prompt, 'what does the threshold do?');
        prompt.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await click($('.iw-start'));
    await settle();
    return client;
}

// ── 1. the thread, with the mechanism visible ───────────────────────────────

describe('the whole mechanism, through the client boundary', () => {
    it('carries a selection made across two pages into the started inquiry', async () => {
        const client = await startInquiry([runningStagesFixture()]);
        expect(client._responses).toEqual([]);
        // The 002R entry could only reach page 1's twenty-four newest images.
        expect($('.iw-session-prompt')).toBeTruthy();
        expect($('.iw-entry')).toBeNull();
    });

    it('shows the running stage while the session is still working', async () => {
        await startInquiry([runningStagesFixture()]);
        const stages = $('.iw-stages');
        expect(stages).toBeTruthy();
        expect(stages.querySelector('[data-stage="theorist"]').dataset.outcome).toBe('started');
        expect(stages.querySelector('[data-image-progress="true"]').textContent)
            .toContain('image 2 of 4');
        // and no fabricated completion figure anywhere on the page
        expect($('progress')).toBeNull();
        expect(text()).not.toMatch(/\d+%/);
    });

    it('reaches the truncated diagnosis, the ledger and the export as the session advances', async () => {
        await startInquiry([runningStagesFixture(), truncatedCompilerFixture()]);
        await settle();

        expect($('[data-diagnosis="open"] [data-failed-stage="compiler"]')).toBeTruthy();
        expect($('[data-artifact="reading_blocks"]').dataset.count).toBe('3');
        expect($('[data-absence-ledger="true"]')).toBeTruthy();
        expect($('[data-download-session="true"]')).toBeTruthy();
    });
});

// ── 2. pixel honesty: TestTruncatedIsNotComplete ────────────────────────────

describe('TestTruncatedIsNotComplete', () => {
    it('a truncated run cannot look like a completed one', async () => {
        await startInquiry([truncatedCompilerFixture()]);

        // the diagnosis is present, open, and says which stage
        const card = $('[data-diagnosis="open"]');
        expect(card).toBeTruthy();
        expect(card.dataset.diagnosis).toBe('open');
        expect($('[data-failed-stage="compiler"]')).toBeTruthy();

        // the stage row does not wear `completed`
        expect($('[data-stage="compiler"]').dataset.outcome).toBe('truncated');
        expect($('[data-stage="compiler"][data-outcome="completed"]')).toBeNull();

        // and the finish reason is on the page, not buried
        expect($('[data-finish="length"]')).toBeTruthy();
    });

    it('a completed run shows no diagnosis, so the card means something', async () => {
        await startInquiry([stagedCompleteFixture()]);
        expect($('[data-diagnosis="open"]')).toBeNull();
        // The stage panel collapses for a run that went well — nothing failed, so the machinery
        // is reference material. Opening it shows the compiler completed.
        await click($('.iw-stages .iw-expand'));
        expect($('[data-stage="compiler"]').dataset.outcome).toBe('completed');
    });
});

// ── 3. pixel honesty: TestAbsenceIsPrinted ──────────────────────────────────

describe('TestAbsenceIsPrinted', () => {
    it('grounds, percepts, evidence and Atlas are printed as zeroes', async () => {
        // A blank space where a count should be reads as "pending" to every reader.
        await startInquiry([stagedCompleteFixture()]);
        const absence = $('[data-absence-ledger="true"]');
        expect(absence).toBeTruthy();
        expect(absence.querySelector('[data-absent="grounds"]').textContent)
            .toBe('grounds created: 0');
        expect(absence.querySelector('[data-absent="percepts"]').textContent)
            .toBe('percepts created: 0');
        expect(absence.querySelector('[data-absent="evidence"]').textContent)
            .toBe('evidence created: 0');
        expect(absence.querySelector('[data-absent="atlas"]').textContent)
            .toBe('Atlas changes: 0');
    });

    it('says a finished run did not create them, never that they are pending', async () => {
        await startInquiry([stagedCompleteFixture()]);
        const note = $('.iw-absence-note').textContent;
        expect(note).toMatch(/not stages still to come/);
        expect(note).toMatch(/nothing here is pending/);
        expect(note).not.toMatch(/will be created|coming|in progress/i);
    });
});

// ── 4. pixel honesty: TestSimulationSurvivesTheLedger ───────────────────────

describe('TestSimulationSurvivesTheLedger', () => {
    it('a fixture receipt still says SIMULATED inside the artifact ledger', async () => {
        // The ledger is a new place a receipt is rendered, and a new place is a new opportunity to
        // lose the label.
        await startInquiry([stagedCompleteFixture()]);
        await click($('[data-artifact="receipts"] .iw-expand'));
        const row = $('[data-ledger-receipt="capr_locate_1"]');
        expect(row.querySelector('.iw-simulated').textContent).toBe('SIMULATED — not evidence');
    });

    it('the ledger creates no measured badge anywhere', async () => {
        await startInquiry([stagedCompleteFixture()]);
        expect($('.iw-badge--measured')).toBeNull();
        expect($('[data-verdict="supported_by_evidence"]')).toBeNull();
    });
});

// ── 5. pixel honesty: TestReadingOnlyIsDeclared ─────────────────────────────

describe('TestReadingOnlyIsDeclared', () => {
    it('a barren run says the prose below is only the scene reading', async () => {
        await startInquiry([barrenFixture()]);
        const note = $('[data-reading-only="true"]');
        expect(note).toBeTruthy();
        expect(note.textContent).toMatch(/The prose below is the scene reading, and only that/);
        // and it appears ABOVE the reading in the document
        const reading = $('.iw-reading');
        expect(note.compareDocumentPosition(reading) & Node.DOCUMENT_POSITION_FOLLOWING)
            .toBeTruthy();
    });

    it('is absent when claims were actually compiled', async () => {
        await startInquiry([stagedCompleteFixture()]);
        expect($('[data-reading-only="true"]')).toBeNull();
    });
});

// ── 6. pixel honesty: TestElapsedIsNotDuration ──────────────────────────────

describe('TestElapsedIsNotDuration', () => {
    it('a running stage shows elapsed and a finished one shows its own duration', async () => {
        await startInquiry([runningStagesFixture()]);
        expect($('[data-stage="theorist"] [data-elapsed="true"]').textContent)
            .toMatch(/elapsed$/);
        expect($('[data-stage="framer"] [data-elapsed="true"]')).toBeNull();
    });

    it('an unmeasured duration is an em dash, never zero', async () => {
        await startInquiry([truncatedCompilerFixture()]);
        expect($('[data-stage="steward"] .iw-stage-duration').textContent).toBe('—');
        expect(text()).not.toContain('0 ms');
    });
});

// ── 7. the surface as a whole ───────────────────────────────────────────────

describe('the assembled mechanism page', () => {
    it('labels every new region', async () => {
        await startInquiry([truncatedCompilerFixture()]);
        const labels = $$('[aria-label]').map((n) => n.getAttribute('aria-label'));
        for (const l of ['Stage activity', 'What went wrong', 'Artifacts and provenance',
            'Export and inspect']) {
            expect(labels).toContain(l);
        }
    });

    it('orders the page so the diagnosis precedes the prose and the ledger', async () => {
        await startInquiry([truncatedCompilerFixture()]);
        const order = $$('.iw-panel').map((n) => n.getAttribute('aria-label'));
        expect(order.indexOf('What went wrong'))
            .toBeLessThan(order.indexOf('Provisional reading'));
        expect(order.indexOf('Stage activity')).toBeLessThan(order.indexOf('What went wrong'));
    });

    it('keeps every expander keyboard-reachable and self-describing', async () => {
        await startInquiry([stagedCompleteFixture()]);
        for (const b of $$('.iw-expand')) {
            expect(b.tagName).toBe('BUTTON');
            if (b.hasAttribute('aria-expanded')) {
                expect(['true', 'false']).toContain(b.getAttribute('aria-expanded'));
            }
        }
    });
});
