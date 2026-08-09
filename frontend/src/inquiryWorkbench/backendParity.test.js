/**
 * HARNESS-002D §7 — the seam, asserted against what the backend actually sends.
 *
 * These fixtures are not written by this lane. `scripts/inquiry_contract_sample.py` generates them
 * from the real coordinator over frozen model payloads, and a backend test regenerates and compares
 * them, so a field the backend renames breaks a test HERE. That is the only arrangement in which
 * the two halves of the contract cannot drift apart quietly: Lane C wrote its client against a
 * shape nobody had produced yet, and this is the shape.
 *
 * WHAT "PARITY" MEANS. Not that every value is recognised — an unknown value is a legitimate
 * outcome and the surface renders it as unknown on purpose. It means that nothing the backend
 * currently sends is unknown, so `known: false` in production means the backend moved rather than
 * that this client was born incomplete.
 */
import { describe, it, expect } from 'vitest';

import awaitingUser from '../../../contracts/samples/inquiry-session.awaiting-user.json';
import complete from '../../../contracts/samples/inquiry-session.complete.json';
import autoComplete from '../../../contracts/samples/inquiry-session.auto-complete.json';
import {
    normalizeSession, openDecision, isEvidenceGrade, hasMeasuredEvidence, supportingEvidence,
    outcomeCounts, SHOULD_KEEP_WATCHING, IS_TERMINAL_STATE, receiptOutcome,
    STATE_LABEL, STATUS_COPY, OUTCOME_COPY,
} from './inquiryContract';

const SAMPLES = [
    ['awaiting-user', awaitingUser],
    ['complete', complete],
    ['auto-complete', autoComplete],
];

/** Every `{value, known}` pair anywhere in a normalised session, with the path that produced it. */
function enumFields(session) {
    const out = [];
    const walk = (node, path) => {
        if (Array.isArray(node)) { node.forEach((v, i) => walk(v, `${path}[${i}]`)); return; }
        if (!node || typeof node !== 'object') return;
        const keys = Object.keys(node);
        if (keys.length === 2 && keys.includes('value') && keys.includes('known')
            && typeof node.known === 'boolean') {
            out.push({ path, ...node });
            return;
        }
        for (const k of keys) walk(node[k], `${path}.${k}`);
    };
    walk(session, '$');
    return out;
}

describe('the backend-generated session is fully readable by this client', () => {
    it.each(SAMPLES)('%s: every enumerated value the backend sent is recognised', (_name, raw) => {
        const unknown = enumFields(normalizeSession(raw))
            .filter((f) => f.value !== '' && !f.known);
        expect(unknown).toEqual([]);
    });

    it.each(SAMPLES)('%s: the parity check can actually fail', (_name, raw) => {
        const tampered = JSON.parse(JSON.stringify(raw));
        tampered.state = 'a_state_nobody_declared';
        const unknown = enumFields(normalizeSession(tampered))
            .filter((f) => f.value !== '' && !f.known);
        expect(unknown.map((f) => f.value)).toContain('a_state_nobody_declared');
    });

    it.each(SAMPLES)('%s: nothing the backend sent is silently rewritten', (_name, raw) => {
        const session = normalizeSession(raw);
        expect(session.session_id).toBe(raw.session_id);
        expect(session.revision).toBe(raw.revision);
        expect(session.state.value).toBe(raw.state);
        expect(session.mode.value).toBe(raw.mode);
        // Byte-identical: the compiler's source spans index into this exact string.
        expect(session.graph.prompt).toBe(raw.graph.prompt);
        expect(session.graph.claims).toHaveLength(raw.graph.claims.length);
        expect(session.graph.observables).toHaveLength(raw.graph.observables.length);
        expect(session.trace).toHaveLength(raw.trace.length);
    });
});

describe('the fields Lane A and Lane C spelled differently arrive under the names this reads', () => {
    it('an observable carries its success, ambiguity and residual conditions', () => {
        const session = normalizeSession(complete);
        const spoken = session.graph.observables.filter((o) => o.success_condition);
        expect(spoken.length).toBeGreaterThan(0);
        for (const o of spoken) {
            expect(o.claim_ref).not.toBe('');
            expect(o.observable_kind).not.toBe('');
            expect(o.capability_classes.length).toBeGreaterThan(0);
        }
        expect(session.graph.observables.some((o) => o.residual_interpretation)).toBe(true);
    });

    it('a claim carries one source span and its whole scope', () => {
        const session = normalizeSession(complete);
        const grounded = session.graph.claims.filter((c) => c.source_span);
        expect(grounded.length).toBeGreaterThan(0);
        for (const c of grounded) {
            expect(c.source_span.origin).not.toBe('');
            expect(c.source_span.text).not.toBe('');
        }
    });

    it('a claim edge carries a relation, not a bare kind', () => {
        const session = normalizeSession(complete);
        expect(session.graph.claim_edges.length).toBeGreaterThan(0);
        for (const e of session.graph.claim_edges) {
            expect(e.relation).not.toBe('');
            expect(e.from_claim).not.toBe('');
            expect(e.to_claim).not.toBe('');
        }
    });

    it('the remainder carries an id, its text and why it is unresolved', () => {
        const session = normalizeSession(complete);
        for (const r of session.graph.semantic_remainder) {
            expect(r.remainder_id).toMatch(/^rem_/);
            expect(r.text).not.toBe('');
            expect(r.why_unresolved).not.toBe('');
        }
    });

    it('an image ref carries a url the thumbnail can render', () => {
        const session = normalizeSession(complete);
        expect(session.graph.image_refs.length).toBeGreaterThan(0);
        for (const img of session.graph.image_refs) {
            expect(img.post_id).not.toBe('');
            expect(img.image_url).toBe(img.image_ref);
        }
    });

    it('an observable this deployment cannot serve says so as a gap', () => {
        const session = normalizeSession(complete);
        const gaps = session.graph.observables.filter((o) => o.availability.value === 'capability_gap');
        expect(gaps.length).toBeGreaterThan(0);
        for (const o of gaps) expect(o.gap_reason).not.toBe('');
    });
});

describe('the honesty gates, against the real payload', () => {
    it.each([['complete', complete], ['auto-complete', autoComplete]])(
        '%s: the one receipt reads as simulated and never as evidence', (_n, raw) => {
            const session = normalizeSession(raw);
            expect(session.capability_receipts).toHaveLength(1);
            const receipt = session.capability_receipts[0];
            expect(receipt.simulated).toBe(true);
            expect(receiptOutcome(receipt)).toBe('simulated');
            expect(isEvidenceGrade(receipt)).toBe(false);
            expect(outcomeCounts(session)).toEqual({ simulated: 1 });
            expect(OUTCOME_COPY.simulated).toMatch(/Nothing was measured/);
        });

    it.each(SAMPLES)('%s: nothing on this session is measured evidence', (_n, raw) => {
        const session = normalizeSession(raw);
        expect(session.evidence).toEqual([]);
        expect(hasMeasuredEvidence(session)).toBe(false);
        for (const claim of session.graph.claims) {
            expect(supportingEvidence(session, claim.claim_id)).toEqual([]);
        }
    });

    it.each([['complete', complete], ['auto-complete', autoComplete]])(
        '%s: no answer section claims a finding', (_n, raw) => {
            const session = normalizeSession(raw);
            expect(session.synthesis.sections.length).toBeGreaterThan(0);
            for (const section of session.synthesis.sections) {
                expect(section.status.known).toBe(true);
                expect(['measured', 'visible']).not.toContain(section.status.value);
                expect(section.evidence_refs).toEqual([]);
            }
            expect(session.synthesis.note).toMatch(/SIMULATION/);
        });

    it('the payload the workbench renders is a plausible-looking region, and it is labelled', () => {
        // The guard exists because the payload is plausible. A test against an empty payload would
        // prove the guard is present and never that it is needed.
        const receipt = normalizeSession(complete).capability_receipts[0];
        const region = receipt.payload.proposals[0].region;
        expect(typeof region.x).toBe('number');
        expect(region.measured).toBe(false);
        expect(region.derived_from).toMatch(/not from any image/);
        expect(receipt.payload.notice).toMatch(/SIMULATED/);
    });
});

describe('the session lifecycle the client drives', () => {
    it('the paused sample is answerable and names one open decision', () => {
        const session = normalizeSession(awaitingUser);
        expect(session.state.value).toBe('awaiting_user');
        expect(SHOULD_KEEP_WATCHING(session.state.value)).toBe(false);
        const decision = openDecision(session);
        expect(decision).not.toBeNull();
        expect(decision.kind.known).toBe(true);
        expect(decision.options.length).toBeGreaterThan(1);
        expect(decision.why_now).not.toBe('');
        expect(decision.options.some((o) => o.recommended)).toBe(true);
        expect(STATE_LABEL[session.state.value]).toBe('Waiting on you');
    });

    it.each([['complete', complete], ['auto-complete', autoComplete]])(
        '%s: the finished sample has no open decision and one settled record', (_n, raw) => {
            const session = normalizeSession(raw);
            expect(IS_TERMINAL_STATE(session.state.value)).toBe(true);
            expect(openDecision(session)).toBeNull();
            expect(session.decision_records).toHaveLength(1);
            const record = session.decision_records[0];
            expect(record.decider.known).toBe(true);
            expect(record.action.known).toBe(true);
            expect(record.selected_label).not.toBe('');
            expect(record.rationale).not.toBe('');
        });

    it('auto mode is visible agency: the record says the policy chose', () => {
        const record = normalizeSession(autoComplete).decision_records[0];
        expect(record.decider.value).toBe('policy');
        expect(record.action.value).toBe('select_option');
    });

    it('a consult answer is attributed to the person', () => {
        expect(normalizeSession(complete).decision_records[0].decider.value).toBe('user');
    });

    it('every claim status the backend uses has a sentence explaining it', () => {
        for (const claim of normalizeSession(complete).graph.claims) {
            expect(STATUS_COPY[claim.status.value]).toBeTruthy();
        }
    });
});
