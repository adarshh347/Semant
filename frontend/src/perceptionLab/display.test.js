// PERCEPTUAL-ORGANS-002 Lane E — the vocabulary covers the contract, and the axes stay apart.
//
// The interesting assertion is the last one. Six axes rendered on one screen collapse the moment
// two of them share a word, and "kept" reading as "correct" is not a styling problem — it is the
// laboratory telling a person that a curation state is a judgement. So the words are checked for
// collisions here, mechanically, rather than watched for in review.

import { describe, it, expect } from 'vitest';
import {
    AXIS_COVERAGE, TABLES_BY_NAME, EPISTEMIC, LIFECYCLE, VERDICT, BASIS, OUTCOME,
    describe as describeValue, duration, num, ceilingNote, artifactSummary, orderedMeasurements,
} from './display';
import { EPISTEMIC_STATUSES } from './contract/perceptionLabContract';

describe('the vocabulary covers the contract', () => {
    for (const [name, values] of Object.entries(AXIS_COVERAGE)) {
        it(`${name} has words for every declared value`, () => {
            const table = TABLES_BY_NAME[name];
            for (const value of values) {
                const entry = describeValue(table, value);
                expect(entry.label, `${name}.${value} label`).toBeTruthy();
                expect(entry.hint, `${name}.${value} hint`).toBeTruthy();
            }
            expect(Object.keys(table.entries).sort()).toEqual([...values].sort());
        });
    }

    it('epistemic statuses include the walled one, so it can be shown if it ever appears', () => {
        for (const s of EPISTEMIC_STATUSES) expect(describeValue(EPISTEMIC, s)).toBeTruthy();
        expect(describeValue(EPISTEMIC, 'sourced').hint).toMatch(/walled out/);
    });

    it('an unknown value throws rather than rendering itself', () => {
        expect(() => describeValue(LIFECYCLE, 'archived')).toThrow(/no lifecycle_status vocabulary/);
    });
});

describe('the axes do not share words', () => {
    const labelsOf = (t) => Object.values(t.entries).map((e) => e.label.toLowerCase());

    it('lifecycle and verdict share no label — `kept` is not `correct`', () => {
        const overlap = labelsOf(LIFECYCLE).filter((l) => labelsOf(VERDICT).includes(l));
        expect(overlap).toEqual([]);
    });

    it('epistemic status and lifecycle share no label', () => {
        const overlap = labelsOf(EPISTEMIC).filter((l) => labelsOf(LIFECYCLE).includes(l));
        expect(overlap).toEqual([]);
    });

    it('run outcome and epistemic status share no label', () => {
        const overlap = labelsOf(OUTCOME).filter((l) => labelsOf(EPISTEMIC).includes(l));
        expect(overlap).toEqual([]);
    });

    it('every hint says which axis it is on rather than describing quality', () => {
        expect(describeValue(LIFECYCLE, 'kept').hint).toMatch(/NOT promoted/);
        expect(describeValue(VERDICT, 'correct').hint).toMatch(/changes no status/);
        expect(describeValue(OUTCOME, 'empty').hint).toMatch(/This is a measurement/);
        expect(describeValue(OUTCOME, 'unavailable').hint).toMatch(/Nothing looked at the image/);
    });
});

describe('the ceiling note', () => {
    it('says what a basis may claim, from the contract', () => {
        expect(ceilingNote('box')).toBe('a box basis may claim at most interpretive');
        expect(ceilingNote('mask')).toBe('a mask basis may claim at most measured');
        expect(ceilingNote('manual')).toBe('a drawn basis may claim at most visible');
        expect(describeValue(BASIS, 'box').hint).toMatch(/over-estimate/);
    });
});

describe('numbers a person reads', () => {
    it('an unmeasured duration is not zero', () => {
        expect(duration(null)).toBe('unmeasured');
        expect(duration(undefined)).toBe('unmeasured');
        expect(duration(0)).toBe('0ms');
        expect(duration(412)).toBe('412ms');
        expect(duration(1902)).toBe('1.90s');
    });

    it('an absent number is an em dash, not a zero', () => {
        expect(num(null)).toBe('—');
        expect(num(undefined)).toBe('—');
        expect(num(0)).toBe('0');
        expect(num(0.58312)).toBe('0.583');
    });

    it('measurements come out in a stable order so two can be compared', () => {
        expect(orderedMeasurements({ iou: 0.4, contact_pixels: 12 }).map((m) => m.key))
            .toEqual(['contact_pixels', 'iou']);
    });
});

describe('artifactSummary', () => {
    const wrap = (payload) => ({ measurement: { payload } });
    it('says what an empty extent set was looking for', () => {
        expect(artifactSummary(wrap({ variant: 'extent_set', searched: 'drapery', instances: [] })))
            .toBe('nothing found for “drapery”');
    });
    it('distinguishes no relations from no pairs', () => {
        expect(artifactSummary(wrap({ variant: 'topology_relation_set', pairs_examined: 4,
            relations: [] }))).toBe('4 pairs examined, no relation of that kind');
    });
    it('names a refusal by its code', () => {
        expect(artifactSummary(wrap({ variant: 'refusal',
            refusal: { code: 'missing_depth_artifact' } }))).toBe('missing_depth_artifact');
    });
});
