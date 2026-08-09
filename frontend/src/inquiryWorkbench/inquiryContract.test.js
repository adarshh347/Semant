/**
 * INQUIRY WORKBENCH — the contract, asserted.
 *
 * Pure-module suite (no DOM): every rule the surface rests on is decided in `inquiryContract.js`,
 * so it can be pinned here rather than only observed through a rendered page.
 */
import { describe, it, expect } from 'vitest';
import {
    normalizeSession, normalizeReading, normalizeClaim, normalizeReceipt, normalizeEvidence,
    normalizeObservable, normalizeDecisionRequest, normalizeSynthesis, normalizeTraceEvent,
    isEvidenceGrade, receiptOutcome, openDecision, supportingEvidence, evidenceForClaim,
    hasMeasuredEvidence, outcomeCounts, canStartInquiry, startInquiryBody, decisionResponseBody,
    numOrNull, boolOrNull, enumField, observablesForClaim, claimById,
    SHOULD_KEEP_WATCHING, IS_TERMINAL_STATE, IS_AWAITING_USER,
    SESSION_STATES, INTERACTION_MODES, DEFAULT_MODE, CLAIM_KINDS,
} from './inquiryContract.js';
import {
    consultFixture, respondedFixture, completedFixture, autoFixture, outcomesFixture,
    measuredEvidenceFixture, unknownFutureFixture, otherDomainFixture, FIXTURE_PROMPT,
} from './inquiryFixtures.js';

// ── the lifecycle ────────────────────────────────────────────────────────────

describe('the session lifecycle', () => {
    it('names the twelve states the board pinned', () => {
        expect(SESSION_STATES).toEqual([
            'framing', 'reading', 'compiling', 'awaiting_user', 'ready', 'executing',
            'judging', 'composing', 'complete', 'exhausted', 'refused', 'error',
        ]);
    });

    it('keeps watching an UNRECOGNISED state rather than calling it finished', () => {
        // The conservative direction, and the one that cannot lose a session: a client older than
        // the server must not declare a run complete because it did not recognise the word.
        expect(SHOULD_KEEP_WATCHING('reconciling')).toBe(true);
        expect(IS_TERMINAL_STATE('reconciling')).toBe(false);
        expect(IS_AWAITING_USER('reconciling')).toBe(false);
    });

    it('stops watching a terminal state and a blocked one', () => {
        for (const s of ['complete', 'exhausted', 'refused', 'error', 'awaiting_user']) {
            expect(SHOULD_KEEP_WATCHING(s)).toBe(false);
        }
        expect(SHOULD_KEEP_WATCHING('executing')).toBe(true);
    });
});

// ── unknown values survive as themselves ─────────────────────────────────────

describe('an unrecognised value is kept, not rewritten', () => {
    it('reports the raw string and marks it unknown', () => {
        const f = enumField('attuned', ['measured', 'interpretive']);
        expect(f).toEqual({ value: 'attuned', known: false });
    });

    it('a future session normalises without any field being coerced to a familiar one', () => {
        const s = normalizeSession(unknownFutureFixture());
        expect(s.state).toEqual({ value: 'reconciling', known: false });

        const future = s.graph.claims.find((c) => c.claim_id === 'clm_future');
        expect(future.kind).toEqual({ value: 'affective_resonance', known: false });
        expect(future.status).toEqual({ value: 'attuned', known: false });
        expect(future.author).toEqual({ value: 'oracle', known: false });

        // and none of the recognised claims were disturbed
        expect(CLAIM_KINDS).toContain(s.graph.claims[0].kind.value);
        expect(s.graph.claims[0].kind.known).toBe(true);
    });

    it('an unknown receipt status derives an unknown outcome, never a successful one', () => {
        const s = normalizeSession(unknownFutureFixture());
        const r = s.capability_receipts[0];
        expect(r.execution_mode).toEqual({ value: 'holographic', known: false });
        expect(r.outcome).toBe('unknown');
        // It CLAIMS to be usable, and an execution mode this client cannot place is refused
        // anyway — vouching for a mode we do not understand is the coercion the contract forbids.
        expect(r.usable_as_evidence).toBe(true);
        expect(isEvidenceGrade(r)).toBe(false);
    });
});

// ── the reading ceiling ──────────────────────────────────────────────────────

describe('the provisional reading', () => {
    it('is interpretive when the backend says nothing', () => {
        expect(normalizeReading({ text: 'x' }).status).toBe('interpretive');
        expect(normalizeReading({ text: 'x' }).capped_from).toBeNull();
    });

    it('CAPS a reading that arrives claiming to be measured, and says it capped it', () => {
        const r = normalizeReading({ text: 'x', status: 'measured' });
        expect(r.status).toBe('interpretive');
        expect(r.capped_from).toBe('measured');
    });

    it('leaves a weaker-than-interpretive status alone', () => {
        expect(normalizeReading({ text: 'x', status: 'imagined' }).status).toBe('imagined');
        expect(normalizeReading({ text: 'x', status: 'imagined' }).capped_from).toBeNull();
    });
});

// ── evidence grade ───────────────────────────────────────────────────────────

describe('what may be shown as evidence', () => {
    it('a fixture receipt is not evidence, whatever its flag says', () => {
        const r = normalizeReceipt({
            execution_mode: 'fixture', status: 'simulated', usable_as_evidence: true,
        });
        // The upstream defect is not honoured by the surface that exists to catch it.
        expect(isEvidenceGrade(r)).toBe(false);
        expect(r.outcome).toBe('simulated');
        expect(r.simulated).toBe(true);
    });

    it('a missing usable_as_evidence is null and fails closed', () => {
        const r = normalizeReceipt({ execution_mode: 'live', status: 'live' });
        expect(r.usable_as_evidence).toBeNull();
        expect(isEvidenceGrade(r)).toBe(false);
    });

    it('a live evidence object marked usable IS evidence', () => {
        const s = normalizeSession(measuredEvidenceFixture());
        expect(s.evidence).toHaveLength(1);
        expect(isEvidenceGrade(s.evidence[0])).toBe(true);
        expect(hasMeasuredEvidence(s)).toBe(true);
    });

    it('the Phase-1 completed session has NO measured evidence at all', () => {
        const s = normalizeSession(completedFixture());
        expect(s.capability_receipts).toHaveLength(1);
        expect(s.capability_receipts[0].simulated).toBe(true);
        expect(s.evidence).toEqual([]);
        expect(hasMeasuredEvidence(s)).toBe(false);
        // and the claim it was requested for gains no support from the receipt
        expect(supportingEvidence(s, 'clm_colonnade')).toEqual([]);
        expect(evidenceForClaim(s, 'clm_colonnade')).toEqual([]);
    });

    it('derives the outcome from the execution mode, not from the status word', () => {
        const r = normalizeReceipt({
            execution_mode: 'fixture', status: 'live', usable_as_evidence: true,
        });
        expect(receiptOutcome(r)).toBe('simulated');
    });
});

// ── the five nothings ────────────────────────────────────────────────────────

describe('empty, unavailable, refused and gap stay four different things', () => {
    it('counts each outcome separately', () => {
        const s = normalizeSession(outcomesFixture());
        expect(outcomeCounts(s)).toEqual({
            simulated: 1, empty: 1, unavailable: 1, refused: 1, capability_gap: 1,
        });
    });

    it('records whether anything was ATTEMPTED, which is what separates empty from unavailable', () => {
        const s = normalizeSession(outcomesFixture());
        const by = (id) => s.capability_receipts.find((r) => r.receipt_id === id);
        expect(by('capr_empty').attempted).toBe(true);
        expect(by('capr_unavailable').attempted).toBe(false);
        expect(by('capr_refused').attempted).toBe(false);
    });
});

// ── the graph ────────────────────────────────────────────────────────────────

describe('the semantic inquiry graph', () => {
    it('keeps the prompt byte-identical', () => {
        const s = normalizeSession(consultFixture());
        expect(s.graph.prompt).toBe(FIXTURE_PROMPT);
    });

    it('carries claims, edges, observables and remainder through', () => {
        const s = normalizeSession(consultFixture());
        expect(s.graph.claims).toHaveLength(4);
        expect(s.graph.claim_edges).toHaveLength(3);
        expect(s.graph.observables).toHaveLength(3);
        expect(s.graph.semantic_remainder).toHaveLength(2);
    });

    it('an observable carries a REQUEST and has nowhere to put a result', () => {
        const o = normalizeObservable({
            observable_id: 'obs_x', claim_ref: 'clm_x', capability_classes: ['locate_phrase'],
            payload: { regions: [1, 2, 3] },       // a result, smuggled in
            result: 'found it',
        });
        expect(o.capability_classes).toEqual(['locate_phrase']);
        expect(o.payload).toBeUndefined();
        expect(o.result).toBeUndefined();
    });

    it('a claim keeps its exact source pointer', () => {
        const c = normalizeClaim({
            claim_id: 'c', text: 't', claim_kind: 'entity',
            source_span: { origin: 'reading', text: 'a screen of columns', start: 46, end: 65 },
        });
        expect(c.source_span).toEqual({
            origin: 'reading', text: 'a screen of columns', start: 46, end: 65,
        });
    });

    it('links observables and evidence back to the claim they serve', () => {
        const s = normalizeSession(measuredEvidenceFixture());
        expect(observablesForClaim(s, 'clm_colonnade').map((o) => o.observable_id))
            .toEqual(['obs_extent']);
        expect(claimById(s, 'clm_colonnade').text).toMatch(/colonnade/);
        expect(claimById(s, 'nope')).toBeNull();
    });
});

// ── decisions ────────────────────────────────────────────────────────────────

describe('decisions', () => {
    it('finds the one open decision and stops finding it once answered', () => {
        expect(openDecision(normalizeSession(consultFixture())).decision_id)
            .toBe('dec_extent_grain');
        expect(openDecision(normalizeSession(respondedFixture()))).toBeNull();
        expect(openDecision(null)).toBeNull();
    });

    it('an auto session records the system as the decider, with its rationale', () => {
        const s = normalizeSession(autoFixture());
        expect(s.decision_records).toHaveLength(1);
        expect(s.decision_records[0].decider).toEqual({ value: 'system', known: true });
        expect(s.decision_records[0].rationale).toMatch(/without asking/i);
    });

    it('a decision request carries options with consequences and a recommendation', () => {
        const d = normalizeDecisionRequest(consultFixture().decision_requests[0]);
        expect(d.options).toHaveLength(2);
        expect(d.options[0].consequence).toBeTruthy();
        expect(d.options.filter((o) => o.recommended)).toHaveLength(1);
        expect(d.allow_free_text).toBe(true);
        expect(d.blocking).toBe(true);
    });

    it('the response body sends the expected revision, and omits it when unknown', () => {
        expect(decisionResponseBody({
            decisionId: 'dec_1', responseId: 'res_1', optionId: 'opt_whole', expectedRevision: 3,
        })).toEqual({
            decision_id: 'dec_1', response_id: 'res_1', action: 'select',
            selected_option_id: 'opt_whole', expected_revision: 3,
        });
        expect(decisionResponseBody({ decisionId: 'dec_1', responseId: 'res_1' }))
            .not.toHaveProperty('expected_revision');
    });

    it('free text is sent as an amendment action, trimmed but never as a selection', () => {
        const body = decisionResponseBody({
            decisionId: 'dec_1', responseId: 'res_1', freeText: '  narrow it to the west end  ',
            action: 'amend', expectedRevision: 4,
        });
        expect(body).toEqual({
            decision_id: 'dec_1', response_id: 'res_1', action: 'amend',
            free_text: 'narrow it to the west end', expected_revision: 4,
        });
        expect(body).not.toHaveProperty('selected_option_id');
    });

    it('an unrecognised action falls back to select rather than being sent through', () => {
        expect(decisionResponseBody({ action: 'obliterate' }).action).toBe('select');
    });
});

// ── starting ─────────────────────────────────────────────────────────────────

describe('what the surface asks of the user', () => {
    it('needs images and a prompt, and nothing else', () => {
        expect(canStartInquiry({ imageIds: ['p1'], prompt: 'why?' })).toBe(true);
        expect(canStartInquiry({ imageIds: [], prompt: 'why?' })).toBe(false);
        expect(canStartInquiry({ imageIds: ['p1'], prompt: '   ' })).toBe(false);
        expect(canStartInquiry()).toBe(false);
    });

    it('builds the start body with the mode, defaulting an unknown one', () => {
        expect(startInquiryBody({ imageIds: ['p1', 'p2'], prompt: '  q  ', mode: 'step' }))
            .toEqual({ prompt: 'q', image_ids: ['p1', 'p2'], mode: 'step' });
        expect(startInquiryBody({ imageIds: ['p1'], prompt: 'q', mode: 'telepathy' }).mode)
            .toBe(DEFAULT_MODE);
        expect(INTERACTION_MODES).toEqual(['auto', 'consult', 'step']);
    });
});

// ── the small guards ─────────────────────────────────────────────────────────

describe('missing numbers and booleans', () => {
    it('a missing number is null, never 0', () => {
        expect(numOrNull(undefined)).toBeNull();
        expect(numOrNull(null)).toBeNull();
        expect(numOrNull(NaN)).toBeNull();
        expect(numOrNull(0)).toBe(0);
    });

    it('a missing boolean is null, and neither true nor false', () => {
        expect(boolOrNull(undefined)).toBeNull();
        expect(boolOrNull('yes')).toBeNull();
        expect(boolOrNull(false)).toBe(false);
        expect(boolOrNull(true)).toBe(true);
    });

    it('a missing revision is null, so no bogus expected_revision is ever sent', () => {
        expect(normalizeSession({}).revision).toBeNull();
        expect(decisionResponseBody({ expectedRevision: normalizeSession({}).revision }))
            .not.toHaveProperty('expected_revision');
    });
});

describe('normalising rubbish', () => {
    it('survives an empty body', () => {
        const s = normalizeSession(undefined);
        expect(s.session_id).toBe('');
        expect(s.graph.claims).toEqual([]);
        expect(s.synthesis).toBeNull();
        expect(s.trace).toEqual([]);
    });

    it('survives arrays where objects were promised, and objects where arrays were', () => {
        const s = normalizeSession({ graph: { claims: 'nope', observables: {} }, trace: 'nope' });
        expect(s.graph.claims).toEqual([]);
        expect(s.graph.observables).toEqual([]);
        expect(s.trace).toEqual([]);
    });

    it('a null synthesis stays null rather than becoming an empty answer', () => {
        expect(normalizeSynthesis(null)).toBeNull();
        expect(normalizeSynthesis({ sections: [{ section_id: 's', text: 't' }] }).sections)
            .toHaveLength(1);
    });

    it('a trace event without a timestamp reports null rather than an invented one', () => {
        expect(normalizeTraceEvent({ event_id: 'e' }).at).toBeNull();
    });

    it('evidence with no verdict is null, not an inconclusive one invented here', () => {
        expect(normalizeEvidence({ evidence_id: 'e' }).verdict).toBeNull();
    });
});

// ── generality ───────────────────────────────────────────────────────────────

describe('no topic branch', () => {
    it('an entirely different domain normalises through the same types', () => {
        const s = normalizeSession(otherDomainFixture());
        expect(s.graph.claims[0].kind).toEqual({ value: 'pattern_or_sequence', known: true });
        expect(openDecision(s).kind).toEqual({ value: 'choose_scope', known: true });
        expect(s.graph.semantic_remainder).toHaveLength(1);
    });

    it('the contract module names no subject matter', () => {
        // The board's rule, asserted against the vocabulary rather than trusted: the claim kinds
        // are FORMS. Any topic word among them would be a production branch by another name.
        const banned = /ottoman|pantheon|ajanta|sculpture|fold|nestedness|colonnade|weld/i;
        expect(CLAIM_KINDS.some((k) => banned.test(k))).toBe(false);
        expect(SESSION_STATES.some((s) => banned.test(s))).toBe(false);
    });
});
