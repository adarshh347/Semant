import { describe, it, expect, beforeEach } from 'vitest';
import {
    isSuggestion, canCiteMark, quarantineSuggestion,
    acceptSuggestion, dismissSuggestion, supersedeSuggestion, deriveUserConfirmedMark,
    getSuggestionLineage, summarizeProvenance, hasModelInvolvement, countEvidence,
} from './suggestionQuarantine';
import { makeVisualMark, normalizeMark, _resetMarkIds } from './visualMarks';

/**
 * CIRCUIT-001 P2D-A — quarantine + lineage. Contract §4.
 *
 * The load-bearing property: a model suggestion is never citable, never counted, and never
 * mutated in place. Acceptance MINTS a new mark pointing back; the suggestion survives.
 */

const mk = (fields) => normalizeMark({ type: 'brush_field', role: 'light_field', ...fields }, { now: 'T' });
const committedUser = () => mk({ source: 'user', status: 'committed', geometry: { kind: 'soft_mask' } });
const suggestion = () => quarantineSuggestion(
    mk({ source: 'system', geometry: { kind: 'soft_mask' }, provenance: { model: 'sam2' } }), { now: 'T' });

beforeEach(() => { _resetMarkIds(); });

// ── citability is derived, and strict ────────────────────────────────────────

describe('canCiteMark — the one place citability lives', () => {
    it('a committed, user-owned, geometry-bearing mark is citable', () => {
        expect(canCiteMark(committedUser())).toBe(true);
    });

    it('a suggestion is NEVER citable, whatever else is true of it', () => {
        expect(canCiteMark(suggestion())).toBe(false);
        // even if something forced its status to committed (it can't via normalize, but guard anyway)
        expect(canCiteMark({ ...suggestion(), status: 'committed' })).toBe(false);
    });

    it('a previewed or suggested status is never citable', () => {
        expect(canCiteMark(mk({ source: 'user', status: 'previewed', geometry: { kind: 'polygon' } }))).toBe(false);
        expect(canCiteMark(mk({ source: 'user', status: 'suggested', geometry: { kind: 'polygon' } }))).toBe(false);
    });

    it('unresolved geometry is never citable — a role with no shape cites nothing', () => {
        expect(canCiteMark(mk({ source: 'user', status: 'committed' }))).toBe(false);   // unresolved
    });

    it('model_refined is not citable on its own — tightened is not confirmed', () => {
        const refined = mk({ source: 'model_refined', status: 'committed', derived_from: 'vm_x', geometry: { kind: 'polygon' } });
        expect(canCiteMark(refined)).toBe(false);
    });

    it('user_confirmed IS citable once committed with geometry', () => {
        const conf = mk({ source: 'user_confirmed', status: 'committed', derived_from: 'vm_x', geometry: { kind: 'polygon' } });
        expect(canCiteMark(conf)).toBe(true);
    });
});

// ── quarantine ───────────────────────────────────────────────────────────────

describe('quarantineSuggestion', () => {
    it('forces model_suggested + suggested and warns, idempotently', () => {
        const q = suggestion();
        expect(q.source).toBe('model_suggested');
        expect(q.status).toBe('suggested');
        expect(isSuggestion(q)).toBe(true);
        expect(quarantineSuggestion(q, { now: 'T' }).status).toBe('suggested');
    });
});

// ── acceptance MINTS, never overwrites ───────────────────────────────────────

describe('acceptSuggestion', () => {
    it('mints a NEW mark and leaves the suggestion untouched', () => {
        const s = suggestion();
        const { accepted, suggestion: kept } = acceptSuggestion(s, {}, { now: 'T2' });
        // the new mark
        expect(accepted.id).not.toBe(s.id);
        expect(accepted.source).toBe('user_confirmed');
        expect(accepted.status).toBe('committed');
        expect(accepted.derived_from).toBe(s.id);
        expect(canCiteMark(accepted)).toBe(true);
        // the suggestion — byte-identical to what went in (Label Studio parent_prediction)
        expect(kept).toEqual(s);
    });

    it('carries the model forward in provenance even though the source is now the human\'s', () => {
        const { accepted } = acceptSuggestion(suggestion(), {}, { now: 'T2' });
        expect(accepted.provenance.model).toBe('sam2');
    });

    it('a geometry edit at acceptance means model_refined, not user_confirmed', () => {
        const { accepted } = acceptSuggestion(suggestion(), { geometry: { kind: 'polygon' } }, { now: 'T2' });
        expect(accepted.source).toBe('model_refined');
        expect(accepted.derived_from).toBeTruthy();
    });

    it('refuses to accept something that is not a suggestion', () => {
        expect(acceptSuggestion(committedUser(), {}, { now: 'T2' })).toBe(null);
    });

    it('deriveUserConfirmedMark returns just the new mark', () => {
        const m = deriveUserConfirmedMark(suggestion(), {}, { now: 'T2' });
        expect(m.source).toBe('user_confirmed');
    });
});

describe('dismissSuggestion keeps the record', () => {
    it('marks dismissed without destroying it', () => {
        const d = dismissSuggestion(suggestion(), { now: 'T2' });
        expect(d.status).toBe('dismissed');
        expect(canCiteMark(d)).toBe(false);
    });
});

// ── supersession stays recoverable ───────────────────────────────────────────

describe('supersedeSuggestion', () => {
    it('keeps the old mark as superseded and links the replacement back', () => {
        const oldMark = committedUser();
        const repl = mk({ source: 'user', status: 'committed', geometry: { kind: 'polygon' } });
        const { replacement, superseded } = supersedeSuggestion(oldMark, repl, { now: 'T2' });
        expect(superseded.status).toBe('superseded');       // recoverable, not deleted
        expect(superseded.id).toBe(oldMark.id);
        expect(replacement.derived_from).toBe(oldMark.id);
        // A superseded mark is no longer citable — the citation must follow the replacement.
        expect(canCiteMark(superseded)).toBe(false);
        expect(canCiteMark(replacement)).toBe(true);
    });
});

// ── lineage + surfacing ──────────────────────────────────────────────────────

describe('getSuggestionLineage', () => {
    it('walks derived_from back to the origin, oldest first', () => {
        const s = suggestion();
        const { accepted } = acceptSuggestion(s, {}, { now: 'T2' });
        const chain = getSuggestionLineage(accepted, [s, accepted]);
        expect(chain.map((m) => m.id)).toEqual([s.id, accepted.id]);
    });

    it('is cycle-guarded', () => {
        const a = { id: 'a', derived_from: 'b' };
        const b = { id: 'b', derived_from: 'a' };
        expect(getSuggestionLineage(a, [a, b]).length).toBeLessThanOrEqual(2);
    });
});

describe('summarizeProvenance — the anti-CVAT requirement', () => {
    it('gives every source a short, honest, visible label', () => {
        expect(summarizeProvenance({ source: 'model_suggested' })).toContain('Model suggestion');
        expect(summarizeProvenance({ source: 'user_confirmed' })).toBe('Model proposed · you accepted');
        expect(summarizeProvenance({ source: 'model_refined' })).toBe('You drew · model tightened');
        expect(summarizeProvenance({ source: 'user' })).toBe('Yours');
        expect(summarizeProvenance(null)).toBe('');
    });

    it('never leaks a confidence number', () => {
        for (const source of ['model_suggested', 'user_confirmed', 'model_refined', 'user']) {
            expect(summarizeProvenance({ source })).not.toMatch(/[0-9]/);
        }
    });

    it('hasModelInvolvement flags anything the model touched', () => {
        expect(hasModelInvolvement({ source: 'user_confirmed' })).toBe(true);
        expect(hasModelInvolvement({ source: 'model_refined' })).toBe(true);
        expect(hasModelInvolvement({ source: 'user' })).toBe(false);
    });
});

describe('countEvidence never counts a suggestion', () => {
    it('counts only committed, non-suggestion marks', () => {
        const marks = [
            committedUser(),
            suggestion(),
            mk({ source: 'user', status: 'draft', geometry: { kind: 'polygon' } }),
        ];
        expect(countEvidence(marks)).toBe(1);
    });
});
