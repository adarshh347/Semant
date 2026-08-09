/**
 * INQUIRY WORKBENCH — capability activity, evidence, synthesis, remainder and trace, mounted.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import CapabilityActivity from './CapabilityActivity.jsx';
import EvidencePanel from './EvidencePanel.jsx';
import SynthesisView from './SynthesisView.jsx';
import TraceView from './TraceView.jsx';
import { NextActions, SessionHeader } from './InquiryWorkbenchPage.jsx';
import { normalizeSession } from './inquiryContract.js';
import {
    completedFixture, outcomesFixture, measuredEvidenceFixture, simulatedEvidenceFixture,
    unknownFutureFixture, respondedFixture, autoFixture, FIXTURE_PROMPT,
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

// ── capability activity ──────────────────────────────────────────────────────

describe('capability activity', () => {
    it('gives each of the six outcomes its own row and its own class', async () => {
        const s = normalizeSession(outcomesFixture());
        await render(<CapabilityActivity receipts={s.capability_receipts} />);
        expect($$('.iw-receipt').length).toBe(5);
        const classes = $$('.iw-receipt').map((r) => r.className);
        // no two receipts share an appearance — an outcome that looked like another outcome
        // would be two different facts about the world wearing one
        expect(new Set(classes).size).toBe(classes.length);
        for (const o of ['simulated', 'empty', 'unavailable', 'refused', 'capability_gap']) {
            expect($(`[data-outcome="${o}"]`)).toBeTruthy();
        }
    });

    it('says the four nothings in four different sentences', async () => {
        const s = normalizeSession(outcomesFixture());
        await render(<CapabilityActivity receipts={s.capability_receipts} />);
        const copy = (id) => $(`[data-receipt-id="${id}"] .iw-receipt-copy`).textContent;
        expect(copy('capr_empty')).toMatch(/ran and returned nothing/i);
        expect(copy('capr_unavailable')).toMatch(/not available, so nothing was attempted/i);
        expect(copy('capr_refused')).toMatch(/refused/i);
        expect(copy('capr_gap')).toMatch(/Nothing in Semant can currently/i);
        expect(new Set([
            copy('capr_empty'), copy('capr_unavailable'),
            copy('capr_refused'), copy('capr_gap'),
        ]).size).toBe(4);
    });

    it('prints whether anything was ATTEMPTED, which is what separates empty from unavailable', async () => {
        const s = normalizeSession(outcomesFixture());
        await render(<CapabilityActivity receipts={s.capability_receipts} />);
        expect($('[data-receipt-id="capr_empty"] [data-attempted="true"]').textContent)
            .toBe('attempted');
        expect($('[data-receipt-id="capr_unavailable"] [data-attempted="false"]').textContent)
            .toBe('not attempted');
    });

    it('never renders an empty result as "nothing exists"', async () => {
        const s = normalizeSession(outcomesFixture());
        await render(<CapabilityActivity receipts={s.capability_receipts} />);
        const row = $('[data-receipt-id="capr_empty"]');
        expect(row.textContent).toMatch(/That is a result, not a failure to display/i);
        expect(row.textContent).toMatch(/unresolved/i);
        expect(row.textContent).not.toMatch(/there is nothing there|does not exist/i);
    });

    it('a missing latency is an em dash, never 0 ms', async () => {
        const s = normalizeSession(outcomesFixture());
        await render(<CapabilityActivity receipts={s.capability_receipts} />);
        const row = $('[data-receipt-id="capr_unavailable"]');
        expect(row.querySelector('.iw-latency').textContent).toBe('—');
        expect(row.textContent).not.toContain('0 ms');
    });
});

describe('the SIMULATED label', () => {
    it('sits beside the payload in TEXT, not in a tooltip', async () => {
        const s = normalizeSession(completedFixture());
        await render(<CapabilityActivity receipts={s.capability_receipts} />);
        const label = $('[data-receipt-id="capr_locate_1"] .iw-simulated');
        expect(label).toBeTruthy();
        expect(label.textContent).toBe('SIMULATED — not evidence');
        // in the payload block itself, so a reader reaching the geometry cannot have passed it
        expect(label.closest('.iw-payload-block')).toBeTruthy();
        // and it is not a title attribute anywhere
        expect($('[title*="SIMULATED"]')).toBeNull();
    });

    it('is repeated beside the geometry once the payload is expanded', async () => {
        const s = normalizeSession(completedFixture());
        await render(<CapabilityActivity receipts={s.capability_receipts} />);
        await click($('[data-receipt-id="capr_locate_1"] .iw-expand'));
        const payload = $('.iw-payload');
        expect(payload.textContent).toContain('regions');
        const beside = $('.iw-simulated--payload');
        expect(beside.textContent).toMatch(/SIMULATED — not evidence/);
        expect(beside.textContent).toMatch(/cannot support any claim/i);
    });

    it('does NOT appear on a live receipt', async () => {
        const s = normalizeSession(measuredEvidenceFixture());
        await render(<CapabilityActivity receipts={s.capability_receipts} />);
        expect($('.iw-simulated')).toBeNull();
        expect($('[data-outcome="live"]')).toBeTruthy();
    });

    it('an unrecognised execution mode is unknown, and gets no successful treatment', async () => {
        const s = normalizeSession(unknownFutureFixture());
        await render(<CapabilityActivity receipts={s.capability_receipts} />);
        expect($('[data-outcome="unknown"]')).toBeTruthy();
        expect($('.iw-badge-raw').textContent).toBe('attuned');
        expect($('[data-outcome="live"]')).toBeNull();
    });
});

// ── evidence ─────────────────────────────────────────────────────────────────

describe('evidence', () => {
    it('a Phase-1 session shows NO evidence and says why, rather than an empty panel', async () => {
        const s = normalizeSession(completedFixture());
        await render(<EvidencePanel session={s} />);
        expect($('[data-evidence-count="0"]').textContent)
            .toMatch(/Nothing here has been measured/i);
        // an empty list because everything was simulated must not look like one where nothing
        // was requested — the disqualified object is kept visible with its reason
        const not = $('[data-not-evidence="true"]');
        expect(not.textContent).toMatch(/Returned, but not evidence/i);
        expect(not.querySelector('.iw-simulated').textContent).toBe('SIMULATED — not evidence');
        expect(not.textContent).toMatch(/supports no claim/i);
    });

    it('a fixture-minted evidence object is listed under "not evidence", not filtered away', async () => {
        const s = normalizeSession(simulatedEvidenceFixture());
        await render(<EvidencePanel session={s} />);
        expect($('.iw-evidence-item')).toBeNull();
        expect($('[data-evidence-count="0"]')).toBeTruthy();
        const disqualified = $('[data-not-evidence="true"] [data-evidence-id="evd_simulated"]');
        expect(disqualified).toBeTruthy();
        expect(disqualified.textContent).toMatch(/produced by a fixture/i);
        // its `measured` status reaches no badge anywhere on the panel
        expect($('.iw-badge--measured')).toBeNull();
        expect($('[data-verdict="supports"]')).toBeNull();
    });

    it('a live usable object IS listed as evidence, with its verdict', async () => {
        const s = normalizeSession(measuredEvidenceFixture());
        await render(<EvidencePanel session={s} />);
        const item = $('[data-evidence-id="evd_extent"]');
        expect(item).toBeTruthy();
        expect(item.querySelector('[data-status="measured"]')).toBeTruthy();
        expect(item.querySelector('[data-verdict="supports"]')).toBeTruthy();
        expect(item.textContent).toMatch(/That it IS a colonnade is not/);
        expect(item.textContent).toMatch(/serves clm_colonnade/);
    });
});

// ── synthesis and remainder ──────────────────────────────────────────────────

describe('the answer', () => {
    it('renders every section with its status, and expands to its references', async () => {
        const s = normalizeSession(completedFixture());
        await render(<SynthesisView session={s} />);
        expect($$('.iw-section').length).toBe(3);
        await click($('[data-section-id="sec_front"] .iw-expand'));
        const refs = $('[data-section-id="sec_front"] .iw-section-refs');
        expect(refs.querySelector('[data-claim-ref="clm_colonnade"]')).toBeTruthy();
        // and it says plainly that nothing measured supports it
        expect(refs.querySelector('.iw-section-noevidence').textContent)
            .toMatch(/No measurement supports this section/i);
    });

    it('a user-authored section says YOUR DIRECTION, never a finding', async () => {
        const s = normalizeSession(completedFixture());
        await render(<SynthesisView session={s} />);
        const section = $('[data-section-id="sec_grain"]');
        expect(section.querySelector('.iw-author--user').textContent).toBe('your direction');
        expect(section.textContent).not.toMatch(/visual finding|we observed|measurement shows/i);
    });

    it('no section claims to be measured in a session with no evidence', async () => {
        const s = normalizeSession(completedFixture());
        await render(<SynthesisView session={s} />);
        expect($('.iw-badge--measured')).toBeNull();
        expect($('.iw-badge--visible')).toBeNull();
    });

    it('says that reading the answer commits nothing to the ledger', async () => {
        const s = normalizeSession(completedFixture());
        await render(<SynthesisView session={s} />);
        const note = $('[data-not-accepted="true"]');
        expect(note.textContent).toMatch(/No mark, percept or Atlas edge has been committed/i);
        expect(note.textContent).toMatch(/different actions/i);
        // and there is no control here that could do it
        expect($$('button').filter((b) => /accept|commit|publish/i.test(b.textContent)))
            .toEqual([]);
    });
});

describe('the semantic remainder', () => {
    it('is its own panel, not a footnote, and is not collapsed behind a toggle', async () => {
        const s = normalizeSession(completedFixture());
        await render(<SynthesisView session={s} />);
        const panel = $('.iw-remainder');
        expect(panel.getAttribute('aria-label')).toBe('Semantic remainder');
        expect($$('.iw-remainder-item').length).toBe(2);
        expect(panel.querySelector('.iw-expand')).toBeNull();
        expect(panel.textContent).toMatch(/No measurement of these pixels can settle it/i);
    });

    it('appears even when there is no answer yet', async () => {
        const s = normalizeSession(respondedFixture());
        await render(<SynthesisView session={s} />);
        expect($('.iw-synthesis')).toBeNull();
        expect($$('.iw-remainder-item').length).toBe(2);
    });
});

// ── trace ────────────────────────────────────────────────────────────────────

describe('the trace', () => {
    it('carries both model/system and user actors, distinguishably', async () => {
        const s = normalizeSession(respondedFixture());
        await render(<TraceView trace={s.trace} defaultOpen />);
        expect($('[data-actor-kind="user"]')).toBeTruthy();
        expect($('[data-actor-kind="model"]')).toBeTruthy();
        expect($('[data-actor-kind="system"]')).toBeTruthy();
        expect($('[data-actor-kind="user"] .iw-actor').textContent).toBe('you');
        expect($$('.iw-trace-event').length).toBe(5);
    });

    it('shows the transition, the reason and the causal refs', async () => {
        const s = normalizeSession(respondedFixture());
        await render(<TraceView trace={s.trace} defaultOpen />);
        const ev = $('[data-event-id="evt_5"]');
        expect(ev.querySelector('.iw-trace-transition').textContent).toBe('ready → executing');
        expect(ev.textContent).toMatch(/through the simulation adapter/i);
        expect(ev.querySelector('.iw-trace-refs').textContent).toContain('capr_locate_1');
    });

    it('is available on a completed session, not only a running one', async () => {
        const s = normalizeSession(completedFixture());
        await render(<TraceView trace={s.trace} />);
        expect($('.iw-trace-list')).toBeNull();
        await click($('.iw-expand'));
        expect($$('.iw-trace-event').length).toBe(7);
    });
});

// ── the session header and next actions ──────────────────────────────────────

describe('the session header', () => {
    it('shows the prompt byte-identically, the mode and the revision', async () => {
        const s = normalizeSession(completedFixture());
        await render(<SessionHeader session={s} />);
        expect($('.iw-session-prompt').textContent).toBe(FIXTURE_PROMPT);
        expect($('[data-mode="consult"]').textContent).toMatch(/Consult mode/);
        expect(text()).toMatch(/revision 7/);
        expect($('[data-state="complete"]')).toBeTruthy();
    });

    it('offers no way to edit the prompt after starting', async () => {
        const s = normalizeSession(completedFixture());
        await render(<SessionHeader session={s} />);
        expect($$('input, textarea, [contenteditable]').length).toBe(0);
    });

    it('shows a live marker while working, and no fabricated progress bar', async () => {
        const s = normalizeSession(autoFixture());
        await render(<SessionHeader session={s} working />);
        expect($('.iw-pulse')).toBeTruthy();
        // the inquiry does not know how many transitions it will take, so a bar would be
        // inventing a denominator
        expect($('progress')).toBeNull();
        expect($('[role="progressbar"]')).toBeNull();
    });

    it('an unrecognised state is named as one, not shown as a familiar neighbour', async () => {
        const s = normalizeSession(unknownFutureFixture());
        await render(<SessionHeader session={s} />);
        expect($('[data-state="unknown"]').textContent).toMatch(/does not recognise/i);
        expect($('.iw-badge-raw').textContent).toBe('reconciling');
    });
});

describe('what you can do about an outcome', () => {
    it('answers each of the four with its own sentence, and none of them is "try again"', async () => {
        const s = normalizeSession(outcomesFixture());
        await render(<NextActions session={s} onRestart={() => {}} />);
        for (const k of ['empty', 'unavailable', 'refused', 'capability_gap']) {
            expect($(`[data-next="${k}"]`)).toBeTruthy();
        }
        // a gap will not resolve on a retry — there is nothing to run
        expect($('[data-next="capability_gap"]').textContent)
            .toMatch(/Retrying will not change that/i);
        // and re-issuing on an empty is how an observation becomes a sampling artifact
        expect($('[data-next="empty"]').textContent).toMatch(/sampling artifact/i);
    });

    it('is absent when nothing came back short', async () => {
        const s = normalizeSession(measuredEvidenceFixture());
        await render(<NextActions session={s} onRestart={() => {}} />);
        expect($('.iw-next')).toBeNull();
    });
});
