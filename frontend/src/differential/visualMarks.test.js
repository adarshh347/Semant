import { describe, it, expect, beforeEach } from 'vitest';
import {
    MARK_TYPES, MARK_SOURCES, MARK_STATUSES, GEOMETRY_KINDS,
    FIELD_ROLE_KEYS, TRACE_ROLE_KEYS, RELATION_ROLE_KEYS, FRAME_ROLE_KEYS, COLLECTION_ROLE_KEYS,
    ROLE_VOCABULARY, makeVisualMark, normalizeMark, validateMark, validateMarkList,
    markId, _resetMarkIds, actionToDraftMark, markRoleFromAction,
    markHasOwnGeometry, markSummary, setMarkStatus,
} from './visualMarks';
import { SOURCES as ACTION_SOURCES } from './perceptualActions';

/**
 * CIRCUIT-001 P2D-A — the mark model. Contract §1–2.
 *
 * The load-bearing property is FAIL CLOSED: an invalid mark comes back null, never a partial
 * object, so a caller cannot render a half-valid mark as evidence.
 */

const good = (type, fields = {}) => normalizeMark({ type, ...fields }, { now: 'T' });

beforeEach(() => { _resetMarkIds(); });

// ── the vocabulary reuses P2B, does not fork it ──────────────────────────────

describe('the mark vocabulary extends the action vocabulary rather than forking it', () => {
    it('every action source is a valid mark source', () => {
        // Contract §2: "do not invent a fourth dialect". The two additions are the only
        // difference, and they exist for reasons a mark has and an action does not.
        for (const s of ACTION_SOURCES) expect(MARK_SOURCES, s).toContain(s);
        expect(MARK_SOURCES).toContain('model_refined');
        expect(MARK_SOURCES).toContain('imported');
    });

    it('every family maps to a role vocabulary', () => {
        for (const t of MARK_TYPES) expect(ROLE_VOCABULARY[t], t).toBeTruthy();
    });

    it('trace roles include the two the contract adds beyond P2B', () => {
        expect(TRACE_ROLE_KEYS).toContain('rhythm');
        expect(TRACE_ROLE_KEYS).toContain('return_path');
        expect(TRACE_ROLE_KEYS).toContain('gaze_address');   // …and keeps P2B's
    });

    it('the five role vocabularies match the contract exactly', () => {
        expect(FIELD_ROLE_KEYS).toContain('external_limit');
        expect(RELATION_ROLE_KEYS).toContain('contradiction');
        expect(FRAME_ROLE_KEYS).toEqual(
            ['aperture', 'boundary', 'crop', 'threshold', 'field_boundary', 'external_limit']);
        expect(COLLECTION_ROLE_KEYS).toContain('percept_constellation');
    });
});

// ── shape ────────────────────────────────────────────────────────────────────

describe('a normalized mark carries the full contract shape', () => {
    it('has every §1 field, with a null run_id slot', () => {
        const m = good('brush_field', { role: 'light_field', geometry: { kind: 'soft_mask' } });
        expect(Object.keys(m).sort()).toEqual([
            'created_at', 'derived_from', 'geometry', 'id', 'label', 'linked_action_ids',
            'linked_ground_ids', 'linked_percept_ids', 'provenance', 'role', 'source',
            'status', 'style', 'type', 'updated_at', 'warnings',
        ]);
        expect(m.provenance.run_id).toBe(null);
        expect(m.derived_from).toBe(null);
    });

    it('mints monotonic vm_ ids', () => {
        const a = markId(); const b = markId();
        expect(a).toMatch(/^vm_[a-z0-9]+_0$/);
        expect(b).toMatch(/^vm_[a-z0-9]+_1$/);
        expect(a).not.toBe(b);
    });

    it('defaults geometry to unresolved and warns', () => {
        const m = good('brush_field', { role: 'fold' });
        expect(m.geometry.kind).toBe('unresolved');
        expect(m.warnings.join(' ').toLowerCase()).toContain('needs a mark from you');
    });
});

// ── fail closed ──────────────────────────────────────────────────────────────

describe('invalid marks fail closed', () => {
    it('returns null for junk and unknown types', () => {
        for (const junk of [null, undefined, 42, 'brush_field', [], {}]) {
            expect(normalizeMark(junk, { now: 'T' })).toBe(null);
        }
        expect(good('summon_mark', { role: 'x' })).toBe(null);
    });

    it('rejects an unknown role rather than coercing it', () => {
        expect(good('brush_field', { role: 'vibes' })).toBe(null);
        expect(good('trace_mark', { role: 'destiny' })).toBe(null);
        expect(good('relation_mark', { role: 'friendship' })).toBe(null);
        expect(good('frame_mark', { role: 'wormhole' })).toBe(null);
        expect(good('collection_mark', { role: 'pile' })).toBe(null);
    });

    it('accepts every key in every published role vocabulary', () => {
        const geomFor = { relation_mark: 'derived', collection_mark: 'derived' };
        for (const [type, vocab] of Object.entries(ROLE_VOCABULARY)) {
            for (const role of vocab) {
                const m = good(type, { role, geometry: { kind: geomFor[type] || 'polygon' } });
                expect(m, `${type}:${role}`).toBeTruthy();
            }
        }
    });

    it('rejects an unknown source, status, or geometry kind', () => {
        expect(good('brush_field', { role: 'fold', source: 'wizard' })).toBe(null);
        expect(good('brush_field', { role: 'fold', status: 'vibing' })).toBe(null);
        expect(good('brush_field', { role: 'fold', geometry: { kind: 'hologram' } })).toBe(null);
    });

    it('every declared geometry kind is accepted', () => {
        for (const kind of GEOMETRY_KINDS) {
            expect(good('brush_field', { role: 'fold', geometry: { kind } }), kind).toBeTruthy();
        }
    });
});

// ── the discipline rules ─────────────────────────────────────────────────────

describe('rules that are product, not schema', () => {
    it('a confidence score on a mark is refused', () => {
        expect(good('brush_field', { role: 'fold', provenance: { confidence: 0.9 } })).toBe(null);
    });

    it('a non-null run_id is refused', () => {
        expect(good('brush_field', { role: 'fold', provenance: { run_id: 'run_1' } })).toBe(null);
    });

    it('a model_suggested mark may not arrive committed', () => {
        expect(good('brush_field', {
            role: 'fold', source: 'model_suggested', status: 'committed', geometry: { kind: 'polygon' },
        })).toBe(null);
    });

    it('user_confirmed and model_refined require lineage', () => {
        // Contract §4.2: anything the model touched must say what it came from.
        expect(good('brush_field', { role: 'fold', source: 'user_confirmed', geometry: { kind: 'polygon' } })).toBe(null);
        expect(good('brush_field', { role: 'fold', source: 'model_refined', geometry: { kind: 'polygon' } })).toBe(null);
        // …and are fine WITH it.
        expect(good('brush_field', {
            role: 'fold', source: 'user_confirmed', derived_from: 'vm_x', geometry: { kind: 'polygon' },
        })).toBeTruthy();
    });

    it('validateMarkList keeps the good and reports the bad by index', () => {
        const g = good('brush_field', { role: 'fold', geometry: { kind: 'polygon' } });
        const { marks, rejected } = validateMarkList([g, { type: 'brush_field', role: 'vibes' }]);
        expect(marks).toEqual([g]);
        expect(rejected[0].index).toBe(1);
    });
});

// ── the action bridge ────────────────────────────────────────────────────────

describe('actionToDraftMark', () => {
    const action = (type, payload = {}, extra = {}) => ({
        id: 'act_1', type, source: 'system', payload, provenance: { matched: ['gaze'] }, ...extra,
    });

    it('maps the three image families and drops the rest', () => {
        expect(actionToDraftMark(action('brush_field', { field_role: 'light_field' }), { now: 'T' }).type).toBe('brush_field');
        expect(actionToDraftMark(action('trace_direction', { trace_role: 'gaze_address' }), { now: 'T' }).type).toBe('trace_mark');
        expect(actionToDraftMark(action('connect_marks', { relation_role: 'contrast' }), { now: 'T' }).type).toBe('relation_mark');
        expect(actionToDraftMark(action('compose_percept', { draft_text: 'x' }), { now: 'T' })).toBe(null);
        expect(actionToDraftMark(action('find_parts', {}), { now: 'T' })).toBe(null);
    });

    it('NEVER mints a mark from ask_model_reading', () => {
        // The third refusal, at the bridge: an ask is not a mark. Nothing was sent, nothing
        // came back; a mark from one would be evidence for an unanswered question.
        expect(actionToDraftMark(action('ask_model_reading', { requested_reading_type: 'describe' }), { now: 'T' })).toBe(null);
    });

    it('carries the originating action id into linked_action_ids', () => {
        // The P2B gap this closes: commitDraft dropped everything but label.
        const m = actionToDraftMark(action('brush_field', { field_role: 'fold', label: 'the fold' }), { now: 'T' });
        expect(m.linked_action_ids).toEqual(['act_1']);
        expect(m.label).toBe('the fold');
        expect(m.role).toBe('fold');
    });

    it('arrives unresolved, because the planner cannot see the image', () => {
        const m = actionToDraftMark(action('brush_field', { field_role: 'fold' }), { now: 'T' });
        expect(m.geometry.kind).toBe('unresolved');
        expect(m.status).toBe('draft');
    });

    it('carries style suggestions and planner provenance', () => {
        const m = actionToDraftMark(action('brush_field', { field_role: 'light_field', color: '#E8C46A', softness: 0.8 }, {
            provenance: { planner: 'attunement/lexicon-v1', promptExcerpt: 'the light', matched: ['light'] },
        }), { now: 'T' });
        expect(m.style.color).toBe('#E8C46A');
        expect(m.provenance.planner).toBe('attunement/lexicon-v1');
    });

    it('markRoleFromAction reads the family payload key', () => {
        expect(markRoleFromAction(action('brush_field', { field_role: 'shadow_field' }))).toBe('shadow_field');
        expect(markRoleFromAction(action('trace_direction', { trace_role: 'gesture' }))).toBe('gesture');
        expect(markRoleFromAction(action('find_parts', {}))).toBe(null);
    });
});

// ── reading ──────────────────────────────────────────────────────────────────

describe('reading a mark', () => {
    it('markHasOwnGeometry is false for derived and unresolved', () => {
        expect(markHasOwnGeometry(good('brush_field', { role: 'fold', geometry: { kind: 'freehand_path' } }))).toBe(true);
        expect(markHasOwnGeometry(good('relation_mark', { role: 'contrast', geometry: { kind: 'derived' } }))).toBe(false);
        expect(markHasOwnGeometry(good('brush_field', { role: 'fold' }))).toBe(false);   // unresolved
    });

    it('setMarkStatus is immutable and refuses unknown statuses', () => {
        const before = [good('brush_field', { role: 'fold', geometry: { kind: 'polygon' } })];
        const after = setMarkStatus(before, before[0].id, 'committed', { now: 'T2' });
        expect(before[0].status).toBe('draft');       // untouched
        expect(after[0].status).toBe('committed');
        expect(setMarkStatus(before, before[0].id, 'vibing')).toBe(before);
    });

    it('markSummary names the role and never crashes on a bare mark', () => {
        expect(markSummary(good('brush_field', { role: 'light_field', label: 'lit', geometry: { kind: 'soft_mask' } })))
            .toContain('Light field');
        expect(markSummary(null)).toBe('');
    });
});
