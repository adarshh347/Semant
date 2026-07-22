import { describe, it, expect, beforeEach } from 'vitest';
import { normalizeMark, _resetMarkIds } from './visualMarks';
import {
    bridgeFieldsFromMark, reconcileBridgeFields, bridgeFieldsAgree,
} from './suggestionQuarantine';

/**
 * CIRCUIT-001 P2E — provenance bridge (contract v2 §7.2-E).
 *
 * The mark is the ONLY authored provenance. A ground/region's mark_source etc. are derived
 * from the mark. The load-bearing property: a bridge field can NEVER disagree with its mark,
 * because the only sanctioned writer reads from the mark.
 */

const mark = (fields) => normalizeMark({
    type: 'brush_field', role: 'light_field', geometry: { kind: 'soft_mask' },
    linked_ground_ids: ['gnd_1'], ...fields,
}, { now: 'T' });

beforeEach(() => { _resetMarkIds(); });

describe('bridgeFieldsFromMark projects the mark, nothing else', () => {
    it('derives mark_id, mark_source, instrument_role, refined_from from the mark', () => {
        const m = mark({ source: 'user_confirmed', role: 'shadow_field', derived_from: 'vm_prev' });
        expect(bridgeFieldsFromMark(m)).toEqual({
            mark_id: m.id, mark_source: 'user_confirmed', instrument_role: 'shadow_field', refined_from: 'vm_prev',
        });
    });

    it('is all-null for no mark', () => {
        expect(bridgeFieldsFromMark(null)).toEqual({
            mark_id: null, mark_source: null, instrument_role: null, refined_from: null,
        });
    });
});

describe('reconcileBridgeFields rewrites a target FROM its linked mark', () => {
    it('stamps the ground with the mark\'s provenance', () => {
        const m = mark({ source: 'user' });
        const ground = { id: 'gnd_1', ground_type: 'field' };
        const out = reconcileBridgeFields(ground, [m]);
        expect(out.mark_source).toBe('user');
        expect(out.mark_id).toBe(m.id);
    });

    it('leaves a ground with no linked mark untouched', () => {
        const ground = { id: 'gnd_orphan' };
        expect(reconcileBridgeFields(ground, [mark({})])).toBe(ground);
    });

    it('the most recently updated linked mark wins (a supersession is the truth)', () => {
        const older = mark({ source: 'user', updated_at: '2026-01-01' });
        const newer = mark({ source: 'user_confirmed', derived_from: 'x', updated_at: '2026-02-01' });
        const out = reconcileBridgeFields({ id: 'gnd_1' }, [older, newer]);
        expect(out.mark_source).toBe('user_confirmed');
    });
});

describe('bridgeFieldsAgree — the drift check made runnable', () => {
    it('is true when the stored bridge matches the mark', () => {
        const m = mark({ source: 'model_refined', derived_from: 'vm_p' });
        const ground = reconcileBridgeFields({ id: 'gnd_1' }, [m]);
        expect(bridgeFieldsAgree(ground, [m])).toBe(true);
    });

    it('CATCHES a bridge field that was authored independently and now lies', () => {
        // Someone hand-set mark_source on the ground; the mark says otherwise. This is the
        // exact drift §7.2-E forbids, and the check must catch it.
        const m = mark({ source: 'user' });
        const drifted = { id: 'gnd_1', mark_id: m.id, mark_source: 'user_confirmed', instrument_role: 'light_field', refined_from: null };
        expect(bridgeFieldsAgree(drifted, [m])).toBe(false);
    });

    it('is true when there is no mark to disagree with', () => {
        expect(bridgeFieldsAgree({ id: 'gnd_orphan', mark_source: 'anything' }, [])).toBe(true);
    });
});
