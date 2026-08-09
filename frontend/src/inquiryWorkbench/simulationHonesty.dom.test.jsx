/**
 * HARNESS-002D — the adversarial half of the simulation firewall.
 *
 * Lane C's suites prove the surface reads an HONEST payload honestly. These prove it survives a
 * DISHONEST one, and they exist because the pixel-honesty mutation audit said so: four lies about
 * simulated capability output could be applied to the workbench and every suite stayed green. A
 * guard that cannot be made to fail is not a guard, and the four it named were missing rather than
 * merely misdescribed.
 *
 * The payloads here are upstream DEFECTS on purpose — a fixture receipt claiming to be usable as
 * evidence, a fixture receipt whose status contradicts its mode, an evidence object that simply
 * does not say. None of them should be constructible by the backend (the schema refuses two of the
 * three outright), and that is exactly why the surface must not honour them: the client is the last
 * reader, and a defect that reaches it is one every earlier check missed.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

import CapabilityActivity from './CapabilityActivity.jsx';
import EvidencePanel from './EvidencePanel.jsx';
import {
    normalizeSession, normalizeReceipt, normalizeEvidence, isEvidenceGrade, receiptOutcome,
    hasMeasuredEvidence, supportingEvidence,
} from './inquiryContract.js';
import complete from '../../../contracts/samples/inquiry-session.complete.json';

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
});

const text = () => container.textContent || '';
const $$ = (sel) => [...container.querySelectorAll(sel)];
const render = async (el) => { await act(async () => { root.render(el); }); };
const click = async (el) => { await act(async () => { el.click(); }); };

/** The real backend receipt, with one field bent. */
const bent = (over) => normalizeReceipt({ ...complete.capability_receipts[0], ...over });

describe('a simulated receipt cannot be talked into being evidence', () => {
    it('a fixture receipt that arrived claiming to be usable is still not evidence', () => {
        const receipt = bent({ usable_as_evidence: true });
        expect(receipt.simulated).toBe(true);
        expect(isEvidenceGrade(receipt)).toBe(false);
    });

    it('a fixture receipt whose status contradicts its mode still reads as simulated', () => {
        // The schema refuses `fixture` + `live` outright. If one ever reaches the client, the MODE
        // is what happened and the status is the field that is lying.
        expect(receiptOutcome(bent({ status: 'live' }))).toBe('simulated');
        expect(bent({ status: 'live' }).simulated).toBe(true);
        expect(receiptOutcome(bent({ status: 'empty' }))).toBe('simulated');
    });

    it('an evidence object that does not say whether it is usable is not usable', () => {
        // Absent is not permission. It is also not the same as `false`, and both fail closed.
        const silent = normalizeEvidence({ evidence_id: 'evd_1', claim_refs: ['clm_1'],
                                           execution_mode: 'live', epistemic_status: 'measured' });
        expect(silent.usable_as_evidence).toBeNull();
        expect(isEvidenceGrade(silent)).toBe(false);
    });

    it('an execution mode this client cannot place is not vouched for', () => {
        const alien = normalizeEvidence({ evidence_id: 'evd_1', claim_refs: ['clm_1'],
                                          execution_mode: 'partially_simulated',
                                          usable_as_evidence: true });
        expect(alien.execution_mode.known).toBe(false);
        expect(isEvidenceGrade(alien)).toBe(false);
    });

    it('a session whose fixture receipt claims usability still measured nothing', async () => {
        const session = normalizeSession({
            ...complete,
            capability_receipts: [{ ...complete.capability_receipts[0],
                                    usable_as_evidence: true }],
            evidence: [{ evidence_id: 'evd_1', claim_refs: [complete.graph.claims[0].claim_id],
                         receipt_ref: complete.capability_receipts[0].receipt_id,
                         execution_mode: 'fixture', epistemic_status: 'measured',
                         usable_as_evidence: true, summary: 'The extent was located.' }],
        });
        expect(hasMeasuredEvidence(session)).toBe(false);
        expect(supportingEvidence(session, complete.graph.claims[0].claim_id)).toEqual([]);

        await render(<EvidencePanel session={session} />);
        // Listed rather than filtered away — a defect hidden is a defect nobody fixes — but listed
        // under "not evidence", and the panel still says nothing here was measured.
        expect(text()).toMatch(/Nothing here has been measured/);
        expect(text()).toMatch(/not evidence/);
        expect(text()).toMatch(/evd_1/);
    });
});

describe('the SIMULATED label is where a reader cannot miss it', () => {
    const receipts = () => [normalizeReceipt(complete.capability_receipts[0])];

    it('says SIMULATED — not evidence beside the payload before it is expanded', async () => {
        await render(<CapabilityActivity receipts={receipts()} />);
        const labels = $$('[data-simulated="true"]');
        expect(labels.length).toBeGreaterThan(0);
        expect(labels[0].textContent).toMatch(/SIMULATED — not evidence/);
    });

    it('says it AGAIN beside the geometry once the payload is open', async () => {
        await render(<CapabilityActivity receipts={receipts()} />);
        const before = $$('[data-simulated="true"]').length;
        await click($$('.iw-expand')[0]);
        const after = $$('[data-simulated="true"]');

        expect(after.length).toBeGreaterThan(before);
        const beside = after[after.length - 1];
        expect(beside.className).toMatch(/iw-simulated--payload/);
        // The words themselves, not only the class: a reader who expanded one row out of a long
        // list should not have to remember which one they opened.
        expect(beside.textContent).toMatch(/SIMULATED — not evidence/);
        expect(beside.textContent).toMatch(/cannot support any claim/);
    });

    it('the geometry the label sits beside is a plausible-looking box, and says it is not one',
        async () => {
            await render(<CapabilityActivity receipts={receipts()} />);
            await click($$('.iw-expand')[0]);
            // The guard matters BECAUSE the payload is plausible. A test against an empty payload
            // would prove the label is present and never that it is needed.
            expect(text()).toMatch(/"x":/);
            expect(text()).toMatch(/not from any image/);
            expect(text()).toMatch(/"measured": false/);
        });

    it('no live receipt is given the label', async () => {
        await render(<CapabilityActivity receipts={[bent({ execution_mode: 'live',
                                                           status: 'live' })]} />);
        expect($$('[data-simulated="true"]')).toHaveLength(0);
    });
});
