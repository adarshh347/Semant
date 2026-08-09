/**
 * INQUIRY WORKBENCH — the reading, the claims, the observables and the decisions, mounted.
 *
 * Component-level: each panel is a pure function of a normalised session, so its guarantees can
 * be asserted without driving the whole page. The page-through-the-client proofs live in
 * `inquiryWorkbench.dom.test.jsx`.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import ProvisionalReading from './ProvisionalReading.jsx';
import ClaimBlocks from './ClaimBlocks.jsx';
import ObservablePlan from './ObservablePlan.jsx';
import DecisionStream from './DecisionStream.jsx';
import DecisionCard from './DecisionCard.jsx';
import { normalizeSession, openDecision } from './inquiryContract.js';
import {
    consultFixture, respondedFixture, completedFixture, autoFixture,
    measuredEvidenceFixture, unknownFutureFixture, otherDomainFixture,
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
const render = async (el) => { await act(async () => { root.render(el); }); };
const click = async (el) => { await act(async () => { el.click(); }); };

// ── the provisional reading ──────────────────────────────────────────────────

describe('the provisional reading', () => {
    it('is labelled interpretive, and the word measured appears nowhere on it', async () => {
        const s = normalizeSession(consultFixture());
        await render(<ProvisionalReading reading={s.graph.reading} />);
        expect($('.iw-badge--interpretive')).toBeTruthy();
        expect($('.iw-badge--measured')).toBeNull();
        expect(text()).not.toMatch(/\bmeasured\b/);
        expect(text()).toMatch(/not a measurement of them/i);
    });

    it('a reading that arrived claiming measured is capped, and the cap is SHOWN', async () => {
        const raw = consultFixture();
        raw.graph.reading.status = 'measured';
        const s = normalizeSession(raw);
        await render(<ProvisionalReading reading={s.graph.reading} />);
        expect($('.iw-badge--interpretive')).toBeTruthy();
        expect($('.iw-badge--measured')).toBeNull();
        // hiding the mismatch would conceal the upstream defect as effectively as honouring it
        // would conceal the epistemic one
        const capped = $('[data-capped-from="measured"]');
        expect(capped).toBeTruthy();
        expect(capped.textContent).toMatch(/cannot be stronger than interpretive/i);
    });

    it('keeps the model receipt closed until asked', async () => {
        const s = normalizeSession(consultFixture());
        await render(<ProvisionalReading reading={s.graph.reading} />);
        expect($('.iw-receipt-list')).toBeNull();
        expect($('.iw-expand').getAttribute('aria-expanded')).toBe('false');
        await click($('.iw-expand'));
        expect($('.iw-expand').getAttribute('aria-expanded')).toBe('true');
        expect($('.iw-receipt-list').textContent).toContain('scene_theorist');
    });
});

// ── claims ───────────────────────────────────────────────────────────────────

describe('claim blocks', () => {
    it('renders one block per claim with its kind, status and source excerpt', async () => {
        const s = normalizeSession(consultFixture());
        await render(<ClaimBlocks session={s} />);
        expect($$('.iw-claim').length).toBe(4);

        const first = $('[data-claim-id="clm_colonnade"]');
        expect(first.querySelector('[data-kind="entity"]')).toBeTruthy();
        expect(first.querySelector('[data-status="proposed"]')).toBeTruthy();
        expect(first.querySelector('.iw-claim-source-text').textContent)
            .toContain('a screen of columns');
    });

    it('says whose words a claim came from, and does not blur the two', async () => {
        const s = normalizeSession(consultFixture());
        await render(<ClaimBlocks session={s} />);
        const fromPrompt = $('[data-claim-id="clm_threshold_converts"] [data-origin="prompt"]');
        const fromReading = $('[data-claim-id="clm_colonnade"] [data-origin="reading"]');
        expect(fromPrompt.textContent).toBe('from your question');
        expect(fromReading.textContent).toBe('from the reading');
    });

    it('offers no way to edit a model claim in place', async () => {
        const s = normalizeSession(consultFixture());
        await render(<ClaimBlocks session={s} />);
        // An edited model claim is indistinguishable from a model claim, and the provenance is
        // gone the moment it is saved. Disagreement goes through an append-only amendment.
        expect($$('input').length).toBe(0);
        expect($$('textarea').length).toBe(0);
        expect($$('[contenteditable]').length).toBe(0);
        expect(text()).toMatch(/nothing here edits a claim in place/i);
    });

    it('a Phase-1 claim shows NO support, because a simulated receipt is not evidence', async () => {
        const s = normalizeSession(completedFixture());
        await render(<ClaimBlocks session={s} />);
        await click($('[data-claim-id="clm_colonnade"] .iw-expand'));
        const block = $('[data-claim-id="clm_colonnade"]');
        expect(block.querySelector('.iw-claim-support')).toBeNull();
        expect(block.querySelector('.iw-claim-nosupport').textContent)
            .toMatch(/nothing has been measured/i);
        // the session HAS a receipt for this claim's observable — it just is not evidence
        expect(s.capability_receipts[0].request_ref).toBe('obs_extent');
    });

    it('a measured badge appears only when a backend EVIDENCE object supplies it', async () => {
        const s = normalizeSession(measuredEvidenceFixture());
        await render(<ClaimBlocks session={s} />);
        await click($('[data-claim-id="clm_colonnade"] .iw-expand'));
        const support = $('[data-claim-id="clm_colonnade"] .iw-claim-support');
        expect(support).toBeTruthy();
        expect(support.querySelector('[data-status="measured"]')).toBeTruthy();
        expect(support.textContent).toContain('19% of the frame');
    });

    it('labels a model confidence as the model\'s own, and never as evidence', async () => {
        const s = normalizeSession(consultFixture());
        await render(<ClaimBlocks session={s} />);
        const conf = $('[data-claim-id="clm_colonnade"] .iw-confidence');
        // SF-004-R2 §4.3: a confident, well-formed mask of the background. A number is not a
        // status and this label is what stops it reading as one.
        expect(conf.textContent).toMatch(/model confidence 0\.71/);
        expect(conf.getAttribute('title')).toMatch(/not evidence/i);
    });

    it('a missing confidence is absent, never rendered as 0.00', async () => {
        const s = normalizeSession(consultFixture());
        await render(<ClaimBlocks session={s} />);
        const block = $('[data-claim-id="clm_threshold_converts"]');
        expect(block.querySelector('.iw-confidence')).toBeNull();
        expect(block.textContent).not.toContain('0.00');
    });

    it('an unrecognised claim kind and status render as unknown, with the raw value kept', async () => {
        const s = normalizeSession(unknownFutureFixture());
        await render(<ClaimBlocks session={s} />);
        const future = $('[data-claim-id="clm_future"]');
        expect(future.dataset.status).toBe('unknown');
        expect(future.querySelector('.iw-badge--unknown')).toBeTruthy();
        expect(future.querySelector('[data-raw="attuned"]')).toBeTruthy();
        expect(future.querySelector('[data-raw="affective_resonance"]')).toBeTruthy();
        // not rounded into the nearest thing this client understands
        expect(future.querySelector('.iw-badge--interpretive')).toBeNull();
        expect(future.querySelector('.iw-badge--proposed')).toBeNull();
    });
});

// ── observables ──────────────────────────────────────────────────────────────

describe('how Semant could investigate', () => {
    it('renders every observable, including the ones nothing can serve', async () => {
        const s = normalizeSession(consultFixture());
        await render(<ObservablePlan session={s} />);
        expect($$('.iw-obs').length).toBe(3);
        expect($('[data-availability="available"]')).toBeTruthy();
        expect($('[data-availability="unavailable"]')).toBeTruthy();
        expect($('[data-availability="capability_gap"]')).toBeTruthy();
    });

    it('a capability GAP is not the same row as an unavailable one', async () => {
        const s = normalizeSession(consultFixture());
        await render(<ObservablePlan session={s} />);
        const gap = $('[data-observable-id="obs_centre_compare"]');
        const unavailable = $('[data-observable-id="obs_movement"]');
        // one is a capability that does not exist; the other is one held back in this phase
        expect(gap.className).not.toBe(unavailable.className);
        expect(gap.textContent).toMatch(/Nothing in Semant can make this observable/i);
        expect(unavailable.textContent).toMatch(/not being used in this phase/i);
        expect(unavailable.textContent).not.toMatch(/Nothing in Semant can/i);
    });

    it('names capability CLASSES and ground forms, not tool names', async () => {
        const s = normalizeSession(consultFixture());
        await render(<ObservablePlan session={s} />);
        const row = $('[data-observable-id="obs_extent"]');
        expect(row.querySelector('.iw-tag--capability').textContent).toBe('locate_phrase');
        expect([...row.querySelectorAll('.iw-tag--ground')].map((t) => t.textContent))
            .toEqual(['region', 'mask']);
    });

    it('shows what stays interpretive even if every measurement succeeds', async () => {
        const s = normalizeSession(consultFixture());
        await render(<ObservablePlan session={s} />);
        await click($('[data-observable-id="obs_extent"] .iw-expand'));
        const residual = $('[data-observable-id="obs_extent"] .iw-residual');
        expect(residual.textContent).toMatch(/stays interpretive regardless/i);
        expect(residual.textContent).toMatch(/stays interpretive however exact the region is/i);
    });

    it('an alternative with no stated availability is not printed as unavailable', async () => {
        const s = normalizeSession(consultFixture());
        await render(<ObservablePlan session={s} />);
        const stated = $('[data-alternative-id="alt_centrality"]');
        const unstated = $('[data-alternative-id="alt_whole_colonnade"]');
        expect(stated.textContent).toMatch(/not available/i);
        expect(unstated.textContent).not.toMatch(/not available/i);
        expect(unstated.textContent).not.toMatch(/availability not stated/i); // it IS stated: true
    });
});

// ── the decision stream ──────────────────────────────────────────────────────

describe('the decision stream', () => {
    it('shows an automatic choice with the same weight as a human one, and names the decider', async () => {
        const auto = normalizeSession(autoFixture());
        await render(<DecisionStream records={auto.decision_records} />);
        const row = $('[data-decider="system"]');
        expect(row).toBeTruthy();
        expect(row.textContent).toMatch(/Semant chose, without asking/);
        expect(row.textContent).toMatch(/One extent for the whole colonnade/);
        // auto mode means no interruption, not invisible agency: the reason is present too
        expect(row.textContent).toMatch(/Reversible, non-authorial/);
    });

    it('a user choice and a system choice use the same row component', async () => {
        const auto = normalizeSession(autoFixture());
        const user = normalizeSession(respondedFixture());
        await render(<DecisionStream records={auto.decision_records} />);
        const autoRow = $('.iw-decision').className.replace(/--\w+/, '');
        await render(<DecisionStream records={user.decision_records} />);
        const userRow = $('.iw-decision').className.replace(/--\w+/, '');
        expect(autoRow).toBe(userRow);
        expect($('[data-decider="user"]').textContent).toMatch(/You chose/);
    });

    it('free text is attributed as YOUR DIRECTION, never as a finding', async () => {
        const s = normalizeSession(respondedFixture());
        const records = [{ ...s.decision_records[0], free_text: 'narrow it to the west end' }];
        await render(<DecisionStream records={records} />);
        const free = $('.iw-decision-free');
        expect(free.querySelector('.iw-author--user').textContent).toBe('your direction');
        expect(free.textContent).not.toMatch(/finding|observed|measured/i);
    });
});

// ── the open decision card ───────────────────────────────────────────────────

describe('the open decision card', () => {
    const mountCard = async (props = {}) => {
        const s = normalizeSession(consultFixture());
        await render(
            <DecisionCard
                decision={openDecision(s)}
                revision={s.revision}
                onRespond={() => {}}
                {...props}
            />);
        return s;
    };

    it('renders the question, why it matters now, and every option with its consequence', async () => {
        await mountCard();
        expect($('.iw-decision-question').textContent).toMatch(/one extent, or column by column/i);
        expect($('.iw-decision-why-now').textContent).toMatch(/cost differently/i);
        expect($$('.iw-option').length).toBe(2);
        for (const o of $$('.iw-option')) {
            expect(o.querySelector('.iw-option-consequence').textContent.length)
                .toBeGreaterThan(20);
        }
        expect($('.iw-recommended')).toBeTruthy();
    });

    it('previews the consequence before anything is sent', async () => {
        const onRespond = vi.fn();
        await mountCard({ onRespond });
        expect($('.iw-preview')).toBeNull();
        await click($('[data-option-id="opt_per_column"]'));
        const preview = $('[data-preview-for="opt_per_column"]');
        expect(preview.textContent).toMatch(/Rhythm becomes investigable/);
        expect(preview.textContent).toMatch(/Nothing has been sent yet/i);
        expect(onRespond).not.toHaveBeenCalled();
    });

    it('submits the decision id, a response id, the option and the expected revision', async () => {
        const onRespond = vi.fn();
        await mountCard({ onRespond });
        await click($('[data-option-id="opt_whole"]'));
        await act(async () => { $('.iw-submit').click(); });

        expect(onRespond).toHaveBeenCalledTimes(1);
        const sent = onRespond.mock.calls[0][0];
        expect(sent).toMatchObject({
            decisionId: 'dec_extent_grain',
            optionId: 'opt_whole',
            action: 'select',
            expectedRevision: 3,
        });
        expect(sent.responseId).toMatch(/^res_/);
    });

    it('sends free text as an AMENDMENT, not as a selection', async () => {
        const onRespond = vi.fn();
        await mountCard({ onRespond });
        const box = $('#iw-free-text');
        await act(async () => {
            Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')
                .set.call(box, 'narrow it to the west end');
            box.dispatchEvent(new Event('input', { bubbles: true }));
        });
        expect($('.iw-free-note').textContent).toMatch(/your direction/i);
        expect($('.iw-free-note').textContent).toMatch(/not a finding about the images/i);

        await act(async () => { $('.iw-submit').click(); });
        expect(onRespond.mock.calls[0][0]).toMatchObject({
            action: 'amend', freeText: 'narrow it to the west end', optionId: '',
        });
    });

    it('cannot be submitted empty', async () => {
        await mountCard();
        expect($('.iw-submit').disabled).toBe(true);
    });

    it('a conflict keeps the selection and reuses the SAME response id on retry', async () => {
        const onRespond = vi.fn();
        const s = normalizeSession(consultFixture());
        const decision = openDecision(s);
        await render(<DecisionCard decision={decision} revision={3} onRespond={onRespond} />);
        await click($('[data-option-id="opt_whole"]'));
        await act(async () => { $('.iw-submit').click(); });
        const firstId = onRespond.mock.calls[0][0].responseId;

        // the page re-renders the card with the conflict and a refreshed revision
        await render(
            <DecisionCard
                decision={decision}
                revision={6}
                onRespond={onRespond}
                conflict={{ message: 'expected revision 3, session is at 6', refreshed: true }}
            />);

        expect($('[data-conflict="stale"]').textContent).toMatch(/moved on while you were deciding/i);
        // the input was NOT discarded
        expect($('[data-option-id="opt_whole"]').getAttribute('aria-checked')).toBe('true');
        expect($('.iw-preview')).toBeTruthy();

        await act(async () => { $('.iw-submit').click(); });
        const second = onRespond.mock.calls[1][0];
        // a fresh id would let a response that in fact landed be applied twice
        expect(second.responseId).toBe(firstId);
        expect(second.expectedRevision).toBe(6);
    });

    it('moves focus to the open question without hiding what came before', async () => {
        await mountCard();
        expect(document.activeElement).toBe($('.iw-decision-question'));
        // focused in place, not trapped in a dialog: the inquiry is paused, not interrupted
        expect($('[role="dialog"]')).toBeNull();
        expect($('.iw-decision-card').getAttribute('aria-modal')).toBeNull();
    });

    it('exposes the options as a radio group', async () => {
        await mountCard();
        expect($('[role="radiogroup"]').getAttribute('aria-label')).toBe('Options');
        expect($$('[role="radio"]').length).toBe(2);
        await click($('[data-option-id="opt_whole"]'));
        expect($('[data-option-id="opt_whole"]').getAttribute('aria-checked')).toBe('true');
        expect($('[data-option-id="opt_per_column"]').getAttribute('aria-checked')).toBe('false');
    });
});

// ── generality ───────────────────────────────────────────────────────────────

describe('no topic branch reaches the components', () => {
    it('a weld micrograph renders through exactly the same panels', async () => {
        const s = normalizeSession(otherDomainFixture());
        await render(
            <div>
                <ProvisionalReading reading={s.graph.reading} />
                <ClaimBlocks session={s} />
                <ObservablePlan session={s} />
                <DecisionCard decision={openDecision(s)} revision={s.revision} onRespond={() => {}} />
            </div>);
        expect($('.iw-badge--interpretive')).toBeTruthy();
        expect($('[data-claim-id="clm_boundary_follow"] [data-kind="pattern_or_sequence"]'))
            .toBeTruthy();
        expect($('[data-observable-id="obs_weld_network"]')).toBeTruthy();
        expect($$('.iw-option').length).toBe(2);
        expect(text()).toMatch(/heat-affected zone/i);
    });
});
