/**
 * WAVE4 — the false-positive, pinned.
 *
 * The audit's own bug: five mutations reported BITES against a suite that did not exist, because
 * vitest exited non-zero on the missing file and the runner read a non-zero exit as "the guard
 * fired". These tests exist so that bug cannot come back quietly — every one of them is a way a
 * run can be red for a reason that is not evidence.
 *
 * This runs in the ordinary suite: the harness is wired into CI, so the harness's own judgement
 * has to be guarded by something CI already runs. A guard on the guard, which is not paranoia
 * here — CI trusting a harness that can false-positive is worse than no CI, because the green is
 * believed.
 */
import { describe, it, expect } from 'vitest';
import { classify, BITTEN, HOLE } from './classify.mjs';

const GUARD = 'a relation is drawn as what it is draws a box-basis relation as interpretive';

describe('a mutation counts as bitten only when the named guard ran and failed', () => {
    it('accepts the one case that is real evidence', () => {
        const r = classify({ red: true, failed: [GUARD], expected: GUARD });
        expect(r.verdict).toBe(BITTEN);
    });

    it('still accepts it when the mutation also broke something else', () => {
        // Incidental breakage is worth reporting, not worth rejecting — the named guard did fire.
        const r = classify({ red: true, failed: [GUARD, 'some other test'], expected: GUARD });
        expect(r.verdict).toBe(BITTEN);
        expect(r.incidental).toEqual(['some other test']);
    });
});

describe('every other way a run can be red is a hole', () => {
    it('THE ORIGINAL BUG — a missing suite is never a bite', () => {
        // vitest exits non-zero on a file that is not there, and reports no failed assertion.
        const r = classify({ red: true, failed: [], expected: GUARD });
        expect(r.verdict).toBe(HOLE);
        expect(r.why).toMatch(/crashed rather than a guard firing/);
    });

    it('a suite that was already red before the mutation is not a bite', () => {
        const r = classify({
            setupError: 'suite is already red unmutated', red: true, failed: [GUARD],
            expected: GUARD,
        });
        expect(r.verdict).toBe(HOLE);
    });

    it('an anchor the mutation could not find is not a bite', () => {
        const r = classify({ setupError: 'anchor not found', expected: GUARD });
        expect(r.verdict).toBe(HOLE);
    });

    it('RENAMED, NOT DELETED — red where a DIFFERENT test failed is not a bite', () => {
        // The subtlest one: the suite exists, it went red, and the guarantee is still unguarded
        // because the guard that fired was somebody else's. A renamed test lands here.
        const r = classify({
            red: true, failed: ['an unrelated test that broke too'], expected: GUARD,
        });
        expect(r.verdict).toBe(HOLE);
        expect(r.why).toMatch(/named guard did not fire/);
    });

    it('an unreadable run report is not a bite', () => {
        const r = classify({
            red: true, failed: [GUARD], reportError: 'could not read the run report',
            expected: GUARD,
        });
        expect(r.verdict).toBe(HOLE);
    });

    it('a mutation that names no guard cannot be confirmed by any red', () => {
        const r = classify({ red: true, failed: [GUARD], expected: '' });
        expect(r.verdict).toBe(HOLE);
    });

    it('a green run is a hole — that is the guarantee nothing guards', () => {
        const r = classify({ red: false, failed: [], expected: GUARD });
        expect(r.verdict).toBe(HOLE);
        expect(r.why).toMatch(/stayed green/);
    });
});
