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
import dissolution from '../../../contracts/samples/inquiry-session.dissolution.json';
// HARNESS-003F. The four above are full-coverage runs, so every scope field on them is the
// unbounded answer — and a parity suite reading only those would prove the client tolerates an
// UNBOUNDED scope, which is the same shape of assurance that let the backend stop sending source
// units without anybody noticing. This one is a slice that bites.
import scoped from '../../../contracts/samples/inquiry-session.scoped.json';
import {
    normalizeSession, openDecision, isEvidenceGrade, hasMeasuredEvidence, supportingEvidence,
    outcomeCounts, SHOULD_KEEP_WATCHING, IS_TERMINAL_STATE, receiptOutcome,
    STATE_LABEL, STATUS_COPY, OUTCOME_COPY, PASS_LABEL, PASS_OUTCOME_COPY,
    uncoveredSourceUnits, earliestFailingPass,
} from './inquiryContract';

const SAMPLES = [
    ['awaiting-user', awaitingUser],
    ['complete', complete],
    ['auto-complete', autoComplete],
    ['dissolution', dissolution],
    ['scoped', scoped],
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

/**
 * HARNESS-003D — the dissolution sample, and why a fourth one was needed.
 *
 * The three above are v1 graphs. Every dissolution field on them is legitimately empty, so a parity
 * suite reading only those proves that this client TOLERATES the absence of source units, atoms,
 * coverage and pass receipts — which is precisely the assurance Lane C already had, and precisely
 * why nobody noticed the backend was not sending them.
 *
 * These tests fail if a field this surface consumes disappears from the wire. That is the
 * directive's `frontend parity must fail if a field it consumes disappears`, and it is a different
 * claim from "nothing unrecognised arrived": a backend that dropped `coverage` entirely would pass
 * every enum check above while making the phase's central artifact invisible again.
 */
describe('the dissolution a v2 graph carries', () => {
    const session = () => normalizeSession(dissolution);

    it('the whole chain arrived: units, atoms, coverage, claims, observables, remainder', () => {
        const g = session().graph;
        // Not `toBeDefined`. A count is what makes this a parity test rather than a shape test —
        // an empty array is what the wire sent before this lane, and it satisfied every normaliser.
        expect(g.source_units.length).toBeGreaterThan(0);
        expect(g.semantic_atoms.length).toBeGreaterThan(0);
        expect(g.coverage.length).toBeGreaterThan(0);
        expect(g.claims.length).toBeGreaterThan(0);
        expect(g.observables.length).toBeGreaterThan(0);
        expect(g.semantic_remainder.length).toBeGreaterThan(0);
    });

    it('every source unit carries the words it is a pointer at, and who wrote them', () => {
        for (const u of session().graph.source_units) {
            expect(u.source_unit_id).not.toBe('');
            expect(u.source_type.known).toBe(true);
            expect(u.exact_quote).not.toBe('');
        }
    });

    it('the person\'s own clauses stay theirs', () => {
        const g = session().graph;
        const mine = g.semantic_atoms.filter((a) => a.author.value === 'user');
        expect(mine.length).toBeGreaterThan(0);
        // Derived from the anchors by the backend and NOT recomputed here: every atom the wire
        // attributes to the person is anchored only to prompt clauses, and a client that
        // re-derived it would be second-guessing the one attribution nothing downstream can check.
        const clauses = new Set(g.source_units
            .filter((u) => u.source_type.value === 'prompt_clause')
            .map((u) => u.source_unit_id));
        for (const atom of mine) {
            expect(atom.source_unit_ids.every((id) => clauses.has(id))).toBe(true);
        }
    });

    it('every source unit has exactly one disposition, and none is lost', () => {
        const g = session().graph;
        expect(uncoveredSourceUnits(g)).toEqual([]);
        const seen = new Set();
        for (const c of g.coverage) {
            expect(c.disposition.known).toBe(true);
            expect(seen.has(c.source_unit_id)).toBe(false);
            seen.add(c.source_unit_id);
        }
        expect(seen.size).toBe(g.source_units.length);
    });

    it('the backend\'s coverage arithmetic and this client\'s agree', () => {
        // Computed on opposite sides of the wire on purpose. Agreement is the assertion; a
        // divergence is a real disagreement rather than something one side quietly absorbs.
        const g = session().graph;
        expect(g.coverage_summary.source_units).toBe(g.source_units.length);
        expect(g.coverage_summary.lost_count).toBe(uncoveredSourceUnits(g).length);
        expect(g.coverage_summary.complete).toBe(true);
        expect(g.coverage_summary.user_units + g.coverage_summary.reading_units)
            .toBe(g.source_units.length);
    });

    it('every pass says which mind it was and how it ended, in words this client has', () => {
        const passes = session().graph.passes;
        expect(passes.length).toBeGreaterThan(3);
        for (const p of passes) {
            expect(p.pass_name.known).toBe(true);
            expect(p.outcome.known).toBe(true);
            expect(PASS_LABEL[p.pass_name.value]).toBeTruthy();
            expect(PASS_OUTCOME_COPY[p.outcome.value]).toBeTruthy();
        }
        expect(earliestFailingPass(session().graph)).toBeNull();
    });

    it('a pass that never waited reports no waiting rather than zero', () => {
        // `waited_ms: 0` would say a pacer answered and reported no wait. Nothing paced a replay,
        // and those two must not render alike — it is the null-duration law, one field over.
        for (const p of session().graph.passes) {
            expect(p.waited_ms).toBeNull();
            expect(p.capacity_waits).toEqual([]);
            expect(p.capacity_limited).toBe(false);
        }
    });

    it('the compiler stage counts the dissolution, not just the claims', () => {
        const compiler = session().stages.find((s) => s.stage.value === 'compiler');
        expect(compiler).toBeTruthy();
        // The nouns are the backend's. A surface assembling "7 → 13" from the numbers would be
        // inventing the units, and the units are the half that makes the numbers readable.
        for (const noun of ['source units', 'atoms', 'claims', 'observables']) {
            expect([noun, compiler.counts_line.includes(noun)]).toEqual([noun, true]);
        }
        expect(compiler.call_topology).toBe('council_passes');
    });

    it('the compiler stage streams the council\'s own progress', () => {
        const compiler = session().stages.find((s) => s.stage.value === 'compiler');
        // One event per pass entered and left, plus one per dissector batch. Reported once at the
        // end, a stage that sat silent for four minutes is indistinguishable from one that hung.
        expect(compiler.substages.length).toBeGreaterThan(5);
        for (const s of compiler.substages) {
            expect(s.label).not.toBe('');
        }
        expect(compiler.substages.some((s) => s.label.includes('batch'))).toBe(true);
    });
});

describe('the deployment badge', () => {
    it.each(SAMPLES)('%s: says what produced it, and it is not a guess', (_n, raw) => {
        const s = normalizeSession(raw);
        expect(s.deployment.declared).toBe(true);
        expect(s.deployment.kind.known).toBe(true);
        expect(s.deployment.detail).not.toBe('');
    });

    it('the samples are a replay and say so', () => {
        // The 002R rehearsal ran against a replay server and the record said so in a receipt three
        // panels down. A screenshot of a replay is otherwise the same picture as a live one.
        expect(normalizeSession(dissolution).deployment.kind.value).toBe('replay');
    });

    it('a response built without a stage binding says nobody asked, never `live`', () => {
        const s = normalizeSession({ ...dissolution, deployment: undefined });
        expect(s.deployment.declared).toBe(false);
        expect(s.deployment.kind.value).toBe('undeclared');
        expect(s.deployment.kind.value).not.toBe('live');
    });
});


// ── the declared scope, as the backend actually sends it (HARNESS-003F) ──────

describe('the scope record survives the wire', () => {
    it('is present on every sample, including the four that are unbounded', () => {
        for (const [name, body] of SAMPLES) {
            const session = normalizeSession(body);
            expect([name, session.execution_scope.mode.known]).toEqual([name, true]);
            // ABSENT IS NOT `full`. Every response carries the answer, so a reader never has to
            // infer an unbounded run from a missing key.
            expect([name, typeof body.execution_scope]).toEqual([name, 'object']);
        }
    });

    it('reads the slice sample as bounded, with every exclusion carrying its reason', () => {
        const session = normalizeSession(scoped);
        const scope = session.execution_scope;
        expect(scope.mode.value).toBe('vertical_slice');
        expect(scope.bounded).toBe(true);
        expect(scope.full_coverage).toBe(false);
        expect(scope.recorded).toBe(true);
        expect(scope.exclusions.length).toBeGreaterThan(0);
        for (const e of scope.exclusions) {
            expect(e.ref).toBeTruthy();
            expect(e.reason.length).toBeGreaterThan(40);
        }
        // The two kinds this sample can exercise — see the sample script for why a claim exclusion
        // is not reachable at one permitted relation request.
        expect([...new Set(scope.exclusions.map((e) => e.kind))].sort())
            .toEqual(['semantic_atom', 'source_unit']);
    });

    it('reads a bound as spent, apart from the partition it was spent against', () => {
        const session = normalizeSession(scoped);
        const plan = session.graph.passes
            .find((p) => p.pass_name.value === 'relation_architect').batch_plan;
        expect(plan.batches_sent).toBe(session.execution_scope.relation_batches_sent);
        expect(plan.batches).toBeGreaterThanOrEqual(plan.batches_sent);
    });

    it('reads the four unbounded samples as unbounded', () => {
        for (const [name, body] of SAMPLES.filter(([n]) => n !== 'scoped')) {
            const scope = normalizeSession(body).execution_scope;
            expect([name, scope.mode.value]).toEqual([name, 'full']);
            expect([name, scope.bounded]).toEqual([name, false]);
            expect([name, scope.full_coverage]).toEqual([name, true]);
            expect([name, scope.exclusions]).toEqual([name, []]);
            expect([name, scope.relation_batches_allowed]).toEqual([name, null]);
        }
    });
});
