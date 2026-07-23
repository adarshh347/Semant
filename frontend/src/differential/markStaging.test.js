import { describe, it, expect, beforeEach } from 'vitest';
import {
    draftMarkFromAction, markDisplay, marksForPercept, marksSummary, markLineageNote,
} from './markStaging';
import { normalizeAction, _resetActionIds } from './perceptualActions';
import { makeVisualMark, _resetMarkIds, normalizeMark } from './visualMarks';
import { canCiteMark } from './suggestionQuarantine';

beforeEach(() => { _resetActionIds(); _resetMarkIds(); });

const action = (over = {}) => normalizeAction({
    type: 'brush_field', source: 'user', status: 'previewed',
    payload: { field_role: 'light_field', label: 'the falling light' },
    ...over,
}, { now: 1 });

describe('draftMarkFromAction — the arm-time bridge', () => {
    it('turns a brush_field action into a draft brush_field mark, geometry unresolved', () => {
        const mark = draftMarkFromAction(action(), { now: 't' });
        expect(mark.type).toBe('brush_field');
        expect(mark.role).toBe('light_field');
        expect(mark.status).toBe('draft');
        expect(mark.geometry.kind).toBe('unresolved');
    });

    it('turns a trace_direction action into a trace_mark', () => {
        const a = normalizeAction({
            type: 'trace_direction', source: 'user',
            payload: { trace_role: 'fall_of_light', label: 'the fall' },
        }, { now: 1 });
        expect(draftMarkFromAction(a, { now: 't' }).type).toBe('trace_mark');
    });

    it('turns a connect_marks action into a relation_mark', () => {
        const a = normalizeAction({
            type: 'connect_marks', source: 'user', payload: { relation_role: 'tension' },
        }, { now: 1 });
        expect(draftMarkFromAction(a, { now: 't' }).type).toBe('relation_mark');
    });

    it('preserves the action id on the mark (action_id survives)', () => {
        const a = action();
        const mark = draftMarkFromAction(a, { now: 't' });
        expect(mark.linked_action_ids).toEqual([a.id]);
    });

    it('preserves the role (role survives)', () => {
        expect(draftMarkFromAction(action(), { now: 't' }).role).toBe('light_field');
    });

    it('carries the action provenance onto the mark', () => {
        const a = action({ provenance: { planner: 'attunement/lexicon-v1', promptExcerpt: 'the light', matched: ['light'] } });
        const mark = draftMarkFromAction(a, { now: 't' });
        expect(mark.provenance.planner).toBe('attunement/lexicon-v1');
        expect(mark.provenance.matched).toEqual(['light']);
    });

    it('quarantines a model-suggested action into a non-citable suggestion', () => {
        const a = action({ source: 'model_suggested' });
        const mark = draftMarkFromAction(a, { now: 't' });
        expect(mark.source).toBe('model_suggested');
        expect(mark.status).toBe('suggested');
        expect(canCiteMark(mark)).toBe(false);
    });

    it('fails closed for an action whose family makes no mark', () => {
        const a = normalizeAction({ type: 'compose_percept', payload: { draft_text: 'x' } }, { now: 1 });
        expect(draftMarkFromAction(a, { now: 't' })).toBeNull();
    });

    it('never mints a mark from ask_model_reading', () => {
        const a = normalizeAction({ type: 'ask_model_reading', payload: { requested_reading_type: 'describe' } }, { now: 1 });
        expect(draftMarkFromAction(a, { now: 't' })).toBeNull();
    });

    it('returns null for an invalid action rather than a partial mark', () => {
        expect(draftMarkFromAction(null)).toBeNull();
        expect(draftMarkFromAction({ type: 'nonsense' })).toBeNull();
    });
});

describe('markDisplay — one honest descriptor for both surfaces', () => {
    it('marks a draft as needing geometry and not citable', () => {
        const d = markDisplay(draftMarkFromAction(action(), { now: 't' }));
        expect(d.needs_geometry).toBe(true);
        expect(d.citable).toBe(false);
        expect(d.status_label).toBe('Draft mark');
        expect(d.session).toBe(true);
    });

    it('says a committed user mark is citable, and "Yours"', () => {
        const mark = normalizeMark({
            type: 'brush_field', role: 'light_field', source: 'user', status: 'committed',
            geometry: { kind: 'freehand_path' }, linked_ground_ids: ['gnd_1'],
        }, { now: 't' });
        const d = markDisplay(mark);
        expect(d.citable).toBe(true);
        expect(d.provenance).toBe('Yours');
    });

    it('says a model suggestion is a suggestion and not citable', () => {
        const d = markDisplay(draftMarkFromAction(action({ source: 'model_suggested' }), { now: 't' }));
        expect(d.is_suggestion).toBe(true);
        expect(d.citable).toBe(false);
        expect(d.provenance).toMatch(/Model suggestion/);
    });

    it('surfaces derived_from for an accepted mark', () => {
        const mark = normalizeMark({
            type: 'brush_field', role: 'light_field', source: 'user_confirmed', status: 'committed',
            geometry: { kind: 'freehand_path' }, derived_from: 'vm_parent',
        }, { now: 't' });
        expect(markDisplay(mark).derived_from).toBe('vm_parent');
        expect(markDisplay(mark).provenance).toMatch(/you accepted/);
    });

    it('returns null for no mark', () => {
        expect(markDisplay(null)).toBeNull();
    });
});

describe('marksForPercept — reaching the instrument behind the evidence', () => {
    const percept = { id: 'pctx_1', ground_ids: ['gnd_1', 'gnd_2'] };
    const markOn = (gid, over = {}) => makeVisualMark('brush_field', {
        role: 'light_field', source: 'user', status: 'committed',
        geometry: { kind: 'freehand_path' }, linked_ground_ids: [gid], ...over,
    }, { now: 't' });

    it('finds a mark linked to a ground the percept cites', () => {
        const marks = [markOn('gnd_1'), markOn('gnd_9')];
        expect(marksForPercept(percept, marks).map((m) => m.id)).toEqual([marks[0].id]);
    });

    it('finds a mark linked directly to the percept', () => {
        const m = makeVisualMark('trace_mark', {
            role: 'fall_of_light', source: 'user', status: 'committed',
            geometry: { kind: 'polyline' }, linked_percept_ids: ['pctx_1'],
        }, { now: 't' });
        expect(marksForPercept(percept, [m])).toHaveLength(1);
    });

    it('returns nothing for a percept with no marks', () => {
        expect(marksForPercept(percept, [markOn('gnd_9')])).toEqual([]);
        expect(marksForPercept(null, [])).toEqual([]);
    });
});

describe('marksSummary', () => {
    const committed = makeVisualMark('brush_field', {
        role: 'light_field', source: 'user', status: 'committed', geometry: { kind: 'freehand_path' },
    }, { now: 't' });
    const suggestion = draftMarkFromAction(action({ source: 'model_suggested' }), { now: 't' });

    it('counts saved marks and flags the uncitable (P3-A: marks are durable now)', () => {
        // A committed mark is saved AND citable — no "not citable" clause.
        expect(marksSummary([committed])).toBe('1 mark · 1 saved');
        // A suggestion is neither saved nor citable; it does not launder into "saved".
        expect(marksSummary([committed, suggestion])).toBe('2 marks · 1 saved · 1 not citable');
    });

    it('is empty for no marks', () => {
        expect(marksSummary([])).toBe('');
    });
});

// ── CIRCUIT-001 P3-A: durability is derived, provenance is visible, lineage shows ──
describe('markDisplay — persistence is derived from status, never asserted', () => {
    const mk = (status, source = 'user') => makeVisualMark('brush_field', {
        role: 'light_field', source, status, geometry: { kind: 'freehand_path' },
        ...(source === 'user_confirmed' || source === 'model_refined' ? { derived_from: 'vm_0' } : {}),
    }, { now: 't' });

    it('a committed mark is persisted (saved), not session', () => {
        const d = markDisplay(mk('committed'));
        expect(d.persisted).toBe(true);
        expect(d.session).toBe(false);
    });

    it('a superseded mark is persisted (recoverable) and flagged superseded', () => {
        const d = markDisplay(mk('superseded'));
        expect(d.persisted).toBe(true);
        expect(d.superseded).toBe(true);
    });

    it('a draft is session-only — the stale blanket "session" is now honest per mark', () => {
        const d = markDisplay(mk('draft'));
        expect(d.persisted).toBe(false);
        expect(d.session).toBe(true);
    });

    it('shows the four provenance sources, never a bare "user" for a model-touched mark', () => {
        expect(markDisplay(mk('committed', 'user')).provenance).toBe('Yours');
        expect(markDisplay(mk('committed', 'user_confirmed')).provenance).toBe('Model proposed · you accepted');
        expect(markDisplay(mk('committed', 'model_refined')).provenance).toBe('You drew · model tightened');
        // a suggestion is quarantined; its provenance is explicit
        const sugg = markDisplay(makeVisualMark('brush_field', {
            role: 'light_field', source: 'model_suggested', status: 'suggested',
            geometry: { kind: 'freehand_path' },
        }, { now: 't' }));
        expect(sugg.provenance).toBe('Model suggestion — not accepted');
        expect(sugg.persisted).toBe(false);
    });
});

describe('markLineageNote — a superseded re-point is visible, never silent (P1F/P1G)', () => {
    it('names what a mark REPLACES and what REPLACED it', () => {
        const old = makeVisualMark('brush_field', {
            id: 'vm_old', role: 'light_field', source: 'user', status: 'superseded',
            geometry: { kind: 'freehand_path' },
        }, { now: 't' });
        const next = makeVisualMark('brush_field', {
            id: 'vm_new', role: 'light_field', source: 'user', status: 'committed',
            geometry: { kind: 'freehand_path' }, derived_from: 'vm_old',
        }, { now: 't' });
        expect(markLineageNote(next, [old, next])).toBe('replaces vm_old');
        expect(markLineageNote(old, [old, next])).toBe('replaced by vm_new');
    });

    it('is empty for a mark with no lineage', () => {
        const m = makeVisualMark('brush_field', {
            role: 'light_field', source: 'user', status: 'committed', geometry: { kind: 'freehand_path' },
        }, { now: 't' });
        expect(markLineageNote(m, [m])).toBe('');
        expect(markLineageNote(null, [])).toBe('');
    });
});
