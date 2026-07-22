import { describe, it, expect, beforeEach } from 'vitest';
import {
    draftMarkFromAction, markDisplay, marksForPercept, marksSummary,
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

    it('counts session marks and flags the uncitable', () => {
        expect(marksSummary([committed])).toBe('1 session mark');
        expect(marksSummary([committed, suggestion])).toBe('2 session marks · 1 not citable');
    });

    it('is empty for no marks', () => {
        expect(marksSummary([])).toBe('');
    });
});
