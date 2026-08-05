/**
 * AGENT-DEMO — the run contract, asserted.
 *
 * Pure-module tests. The claims here are about the CONTRACT — what a run requires, what an
 * unknown is allowed to become, when a run is honestly empty — and none of them needs a DOM.
 */
import { describe, it, expect } from 'vitest';
import {
    RUN_STATUSES, IS_TERMINAL, IS_LIVE, IS_BLOCKED_ON_HUMAN,
    canStartRun, startRunBody, normalizeRunView, normalizeProductionRecord,
    numOrNull, epistemicCounts, refusedRecords, isHonestlyEmpty, stopSummary,
} from './runContract';
import runViewFixture, { emptyRunFixture, awaitingAnswerFixture } from './runViewFixture';

describe('annotation-independence', () => {
    it('a run needs only a corpus and a prompt', () => {
        expect(canStartRun({ imageIds: ['p1'], prompt: 'why is this centred?' })).toBe(true);
    });

    it('THE CLAIM: a corpus with zero annotations is startable', () => {
        // There is nothing to assert about regions/grounds/marks because the gate never looks at
        // them. That absence IS the feature — this test exists so that a future "must be
        // annotated" check cannot be added without failing here.
        const post = { id: 'p1', photo_url: 'x', region_annotations: [], grounds: [], percepts: [] };
        expect(canStartRun({ imageIds: [post.id], prompt: 'what holds this together?' })).toBe(true);
    });

    it('a tag alone is a corpus', () => {
        expect(canStartRun({ tags: ['altes-museum'], prompt: 'how does it gather?' })).toBe(true);
    });

    it('but images without a question are not a run, and neither is the reverse', () => {
        expect(canStartRun({ imageIds: ['p1'], prompt: '   ' })).toBe(false);
        expect(canStartRun({ prompt: 'a real question' })).toBe(false);
    });

    it('the start body omits empty selectors rather than sending []', () => {
        const body = startRunBody({ imageIds: ['p1'], prompt: ' q ', mode: 'argue' });
        expect(body).toEqual({ prompt: 'q', image_ids: ['p1'], mode: 'argue' });
        expect('tags' in body).toBe(false);
    });

    it('an unknown mode falls back to explore rather than travelling to the server', () => {
        expect(startRunBody({ tags: ['t'], prompt: 'q', mode: 'nonsense' }).mode).toBe('explore');
    });
});

describe('the lifecycle', () => {
    it('knows which states are live, terminal, and blocked on a human', () => {
        expect(RUN_STATUSES).toContain('awaiting_answer');
        expect(IS_LIVE('running')).toBe(true);
        expect(IS_TERMINAL('complete')).toBe(true);
        expect(IS_TERMINAL('stopped')).toBe(true);
        expect(IS_BLOCKED_ON_HUMAN('awaiting_answer')).toBe(true);
        // awaiting_answer is NOT terminal: the run resumes on an answer.
        expect(IS_TERMINAL('awaiting_answer')).toBe(false);
    });
});

describe('unknowns are never fabricated', () => {
    it('a missing number stays null instead of becoming 0', () => {
        // 0 ms is a measurement that was never taken presented as an instant one; 0 confidence
        // reads as certainty about being wrong. Both are worse than an em dash.
        expect(numOrNull(undefined)).toBeNull();
        expect(numOrNull(null)).toBeNull();
        expect(numOrNull('412')).toBeNull();
        expect(numOrNull(NaN)).toBeNull();
        expect(numOrNull(0)).toBe(0);          // a real zero survives
    });

    it('a record with no model, adapter or latency normalises to nulls', () => {
        const r = normalizeProductionRecord({ step_id: 's1', actuator: 'rhythm' });
        expect(r.model).toBeNull();
        expect(r.adapter).toBeNull();
        expect(r.latency_ms).toBeNull();
        expect(r.produced).toEqual([]);
        expect(r.refusal).toBeNull();
    });

    it('a refusal survives as a result, not as an error', () => {
        const r = normalizeProductionRecord({
            step_id: 's4', actuator: 'external_limit',
            refusal: { reason: 'up_vector_spread', detail: 'frontal' },
        });
        expect(r.refusal).toEqual({ reason: 'up_vector_spread', detail: 'frontal' });
    });
});

describe('normalizeRunView survives a payload that is not the contract yet', () => {
    it('an empty object still renders as a run', () => {
        const v = normalizeRunView({});
        expect(v.status).toBe('pending');
        expect(v.mode).toBe('explore');
        expect(v.corpus).toEqual([]);
        expect(v.production_records).toEqual([]);
        expect(v.article).toBeNull();
    });

    it('an unrecognised status becomes pending, so the watch keeps listening', () => {
        // Older client than server. Treating an unknown state as "finished" would abandon a run
        // that is still going; treating it as pending merely polls once more.
        expect(normalizeRunView({ status: 'reticulating' }).status).toBe('pending');
    });

    it('null lists do not throw', () => {
        const v = normalizeRunView({ corpus: null, rounds: null, production_records: null });
        expect(v.corpus).toEqual([]);
        expect(v.rounds).toEqual([]);
        expect(v.production_records).toEqual([]);
    });
});

describe('reading a run', () => {
    it('counts what was produced by way of knowing', () => {
        const counts = epistemicCounts(normalizeRunView(runViewFixture()));
        expect(counts.measured).toBe(2);
        expect(counts.visible).toBe(1);
        expect(counts.interpretive).toBe(1);
    });

    it('finds the refused steps', () => {
        const refused = refusedRecords(normalizeRunView(runViewFixture()));
        expect(refused).toHaveLength(1);
        expect(refused[0].actuator).toBe('external_limit');
    });
});

describe('honest emptiness', () => {
    it('a finished run that produced nothing says so', () => {
        const v = normalizeRunView(emptyRunFixture());
        expect(isHonestlyEmpty(v)).toBe(true);
        expect(stopSummary(v).tone).toBe('stopped');
        expect(stopSummary(v).text).toMatch(/nothing was produced/i);
    });

    it('a RUNNING run that has produced nothing yet is NOT empty', () => {
        // The distinction the whole idea rests on: "nothing yet" and "nothing, finally" are
        // different claims, and only the second is a result.
        const v = normalizeRunView({ status: 'running', production_records: [] });
        expect(isHonestlyEmpty(v)).toBe(false);
        expect(stopSummary(v)).toBeNull();
    });

    it('a stopped run with no reason still admits it stopped', () => {
        const v = normalizeRunView({ status: 'stopped' });
        expect(stopSummary(v).text).toMatch(/did not say why/i);
    });

    it('a completed run WITH output is not empty', () => {
        expect(isHonestlyEmpty(normalizeRunView(runViewFixture()))).toBe(false);
    });
});

describe('the question (A2/A3)', () => {
    it('normalises a grounded question with its real options', () => {
        const v = normalizeRunView(awaitingAnswerFixture());
        expect(v.status).toBe('awaiting_answer');
        expect(v.question.options.map((o) => o.value)).toEqual(['threshold', 'screen']);
        expect(v.question.param).toBe('lens');
        expect(v.question.blocked_step_id).toBe('s7');
    });

    it('a question is null unless the run is asking', () => {
        expect(normalizeRunView(runViewFixture()).question).toBeNull();
    });
});

describe('plan steps — the live shape, not the fixture-only one', () => {
    it('normalizes a server step object into something renderable', () => {
        const v = normalizeRunView({
            rounds: [{
                round: 1,
                plan: {
                    steps: [{
                        step_id: 'groq:1:pressure_zone@post_a',
                        actuator: 'pressure_zone',
                        params: { image: 'post_a' },
                        note: 'detect concentration',
                    }],
                },
            }],
        });
        const [s] = v.rounds[0].plan.steps;
        expect(s.key).toBe('groq:1:pressure_zone@post_a');
        expect(s.label).toBe('pressure_zone');
        expect(s.note).toBe('detect concentration');
        expect(s.image).toBe('post_a');
    });

    it('never leaves a raw object where a React child is rendered', () => {
        // The exact crash: "Objects are not valid as a React child (found: object with keys
        // {step_id, actuator, params, note})". Every step's label must be a primitive.
        const v = normalizeRunView({
            rounds: [{ plan: { steps: [
                { step_id: 'a', actuator: 'rhythm', params: { image: 'p' }, note: 'n' },
                'pressure_zone',
                null,
            ] } }],
        });
        for (const s of v.rounds[0].plan.steps) {
            expect(typeof s.label).toBe('string');
            expect(typeof s.key === 'string' || typeof s.key === 'number').toBe(true);
        }
    });

    it('still accepts a bare string step, so an older server keeps working', () => {
        const v = normalizeRunView({ rounds: [{ plan: { steps: ['rhythm'] } }] });
        expect(v.rounds[0].plan.steps[0].label).toBe('rhythm');
        expect(v.rounds[0].plan.steps[0].actuator).toBe('rhythm');
    });

    it('gives two steps on the same actuator distinct keys', () => {
        const v = normalizeRunView({
            rounds: [{ plan: { steps: ['pressure_zone', 'pressure_zone'] } }],
        });
        const [a, b] = v.rounds[0].plan.steps;
        expect(a.key).not.toBe(b.key);
    });

    it('survives a round with no plan at all', () => {
        const v = normalizeRunView({ rounds: [{ round: 1 }, null] });
        expect(v.rounds[0].plan.steps).toEqual([]);
        expect(v.rounds[1].plan.steps).toEqual([]);
    });
});
