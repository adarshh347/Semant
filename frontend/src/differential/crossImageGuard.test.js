/**
 * ATLAS C3 — the cross-image guard, on the near side.
 *
 * A `compare_views` relation is committed into BOTH posts it spans, so it arrives in a single
 * image's `visual_marks` while being a claim about the SEQUENCE. The Differential is the
 * single-image instrument; drawing the relation there would put a claim about two photographs on
 * one of them, and counting it would credit this picture with evidence it does not hold.
 *
 * The predicate here must agree EXACTLY with `backend/services/cross_image.py`. Two copies of one
 * rule is a thing that drifts, so the cases below are the same cases that file pins — if one side
 * changes, the other's tests should be the reason somebody notices.
 */
import { describe, it, expect } from 'vitest';

import { isCrossImageMark, nativeMarks, persistableMarks } from './visualMarks.js';

const nativeMark = (id = 'm1') => ({
    id, type: 'trace_mark', role: 'architectural_axis', label: 'the doorway',
    source: 'user', status: 'committed', source_ref: id,
    geometry: { kind: 'path', points: [[0.1, 0.1], [0.4, 0.4]] },
});

const crossImageRelation = (id = 'vm_rel_1', spans = ['p1', 'p2']) => ({
    id, type: 'relation_mark', role: 'kinship', label: 'echoes',
    source: 'user_confirmed', status: 'committed',
    geometry: { kind: 'derived', endpoints: ['p1:m1', 'p2:m2'], cross_image: true },
    corpus: { corpus_id: 'c1', spans },
    epistemic_status: 'interpretive',
});

/** `connect_marks`' relation: two marks inside ONE frame — a claim about that frame. */
const sameImageRelation = () => ({
    id: 'vm_rel_same', type: 'relation_mark', role: 'kinship', label: 'leads to',
    source: 'user_confirmed', status: 'committed',
    geometry: { kind: 'derived', endpoints: ['m1', 'm2'] },
});

describe('the cross-image predicate', () => {
    it('reads either signal the producer wrote', () => {
        expect(isCrossImageMark(crossImageRelation())).toBe(true);
        expect(isCrossImageMark({ geometry: { cross_image: true } })).toBe(true);
        expect(isCrossImageMark({ corpus: { spans: ['p1', 'p2'] } })).toBe(true);
    });

    it('leaves a native mark alone', () => {
        expect(isCrossImageMark(nativeMark())).toBe(false);
        expect(isCrossImageMark(null)).toBe(false);
        expect(isCrossImageMark('not a mark')).toBe(false);
    });

    it('does not treat one post named twice as a span', () => {
        expect(isCrossImageMark({ corpus: { spans: ['p1'] } })).toBe(false);
        expect(isCrossImageMark({ corpus: { spans: ['p1', 'p1'] } })).toBe(false);
    });

    it('is about SPAN, not about the word "relation"', () => {
        // Relating two marks inside one frame is a claim about that frame, and must keep
        // counting as one.
        expect(isCrossImageMark(sameImageRelation())).toBe(false);
        expect(nativeMarks([sameImageRelation()])).toHaveLength(1);
    });
});

describe('what the single-image instrument is given', () => {
    it('never includes a relation that spans two photographs', () => {
        const marks = [nativeMark('m1'), crossImageRelation(), nativeMark('m2')];
        expect(nativeMarks(marks).map((m) => m.id)).toEqual(['m1', 'm2']);
    });

    it('withholds from the RENDER without withholding from the WRITE', () => {
        // The store re-saves `visual_marks` as a whole array. Filtering on load and then saving
        // what was left would silently delete every relation on the post — the wholesale-replace
        // loss that has already destroyed committed evidence in this codebase once. The store
        // holds the withheld relations and puts them back; this pins the shape that relies on.
        const stored = [nativeMark('m1'), crossImageRelation()];
        const shown = nativeMarks(stored);
        const withheld = stored.filter(isCrossImageMark);
        const written = [...persistableMarks(shown), ...withheld];

        expect(shown.map((m) => m.id)).toEqual(['m1']);
        expect(written.map((m) => m.id).sort()).toEqual(['m1', 'vm_rel_1']);
    });
});
