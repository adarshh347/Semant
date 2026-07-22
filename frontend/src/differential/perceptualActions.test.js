import { describe, it, expect, beforeEach } from 'vitest';
import {
    ACTION_TYPES, TARGETS, SOURCES, STATUSES, TARGET_LABEL,
    FIELD_ROLE_KEYS, TRACE_ROLE_KEYS, RELATION_ROLE_KEYS, MANUSCRIPT_MODE_KEYS, CHALLENGE_TYPE_KEYS,
    normalizeAction, validateAction, validateActionList, specFor,
    actionNeedsGeometry, actionCanApplyNow, actionToHumanLabel, actionToShortReason,
    groupActionsByTarget, summarizeActions, setActionStatus, _resetActionIds,
} from './perceptualActions';

/**
 * CIRCUIT-001 P2B — the grammar.
 *
 * The load-bearing property is FAIL CLOSED. A proposal that does not validate must not come
 * back as a half-object, because a caller that gets an object will render it, and a
 * half-valid action rendered as a card is exactly what this grammar exists to prevent.
 */

const ok = (type, payload = {}, extra = {}) =>
    normalizeAction({ type, payload, ...extra }, { now: 1000 });

beforeEach(() => { _resetActionIds(); });

// ── shape ────────────────────────────────────────────────────────────────────

describe('every action family is specified', () => {
    it('has a spec, and the spec names a real target', () => {
        for (const t of ACTION_TYPES) {
            const s = specFor(t);
            expect(s, t).toBeTruthy();
            expect(TARGETS, t).toContain(s.target);
        }
    });

    it('every target that can appear has a display label', () => {
        for (const t of TARGETS) expect(TARGET_LABEL[t]).toBeTruthy();
    });

    it('a normalized action carries the full common shape', () => {
        const a = ok('find_parts', { way_of_looking: 'general' });
        expect(Object.keys(a).sort()).toEqual([
            'createdAt', 'id', 'intent', 'label', 'payload', 'provenance',
            'requiresConfirmation', 'source', 'status', 'target', 'type', 'warnings',
        ]);
        expect(a.status).toBe('proposed');
        expect(a.createdAt).toBe(1000);
        expect(SOURCES).toContain(a.source);
        expect(STATUSES).toContain(a.status);
    });

    it('derives a human label when none is given, and keeps one that is', () => {
        expect(ok('brush_field', { field_role: 'light_field', label: 'x' }).label).toBe('Brush light field');
        expect(ok('trace_direction', { trace_role: 'gaze_address', label: 'x' }).label).toBe('Trace gaze / address');
        expect(ok('find_parts', {}, { label: 'Open the image' }).label).toBe('Open the image');
    });

    it('the spec decides requiresConfirmation, not the caller', () => {
        // A proposal must not be able to declare itself confirmation-free and skip the user.
        const a = normalizeAction(
            { type: 'brush_field', payload: { field_role: 'fold', label: 'f' }, requiresConfirmation: false },
            { now: 0 },
        );
        expect(a.requiresConfirmation).toBe(true);
    });
});

// ── fail closed ──────────────────────────────────────────────────────────────

describe('invalid actions fail closed', () => {
    it('returns null — never a partial object — for an unknown type', () => {
        expect(normalizeAction({ type: 'summon_daemon', payload: {} }, { now: 0 })).toBe(null);
    });

    it('returns null for junk input', () => {
        for (const junk of [null, undefined, 42, 'brush_field', [], {}]) {
            expect(normalizeAction(junk, { now: 0 })).toBe(null);
        }
    });

    it('refuses a family missing its required payload', () => {
        expect(ok('brush_field', { label: 'no role' })).toBe(null);
        expect(ok('brush_field', { field_role: 'light_field' })).toBe(null);   // no label
        expect(ok('trace_direction', { label: 'no role' })).toBe(null);
        expect(ok('connect_marks', {})).toBe(null);
        expect(ok('compose_percept', {})).toBe(null);
        expect(ok('start_manuscript', {})).toBe(null);
        expect(ok('challenge_percept', { percept_ref: 'p' })).toBe(null);
        expect(ok('ask_model_reading', {})).toBe(null);
        expect(ok('assign_ground_role', { ground_id: 'g1' })).toBe(null);
    });

    it('refuses a role outside the vocabulary rather than coercing it', () => {
        // A vocabulary is only worth having if a word outside it is an error. Coercing an
        // unknown role to a known one would make the planner's mistakes invisible.
        expect(ok('brush_field', { field_role: 'vibes', label: 'v' })).toBe(null);
        expect(ok('trace_direction', { trace_role: 'destiny', label: 'd' })).toBe(null);
        expect(ok('connect_marks', { relation_role: 'friendship' })).toBe(null);
        expect(ok('start_manuscript', { mode: 'haiku' })).toBe(null);
        expect(ok('challenge_percept', { percept_ref: 'p', challenge_type: 'vibes' })).toBe(null);
    });

    it('accepts every key in every published vocabulary', () => {
        // The guard against a list and a spec drifting apart.
        for (const k of FIELD_ROLE_KEYS) expect(ok('brush_field', { field_role: k, label: k }), k).toBeTruthy();
        for (const k of TRACE_ROLE_KEYS) expect(ok('trace_direction', { trace_role: k, label: k }), k).toBeTruthy();
        for (const k of RELATION_ROLE_KEYS) expect(ok('connect_marks', { relation_role: k }), k).toBeTruthy();
        for (const k of MANUSCRIPT_MODE_KEYS) expect(ok('start_manuscript', { mode: k }), k).toBeTruthy();
        for (const k of CHALLENGE_TYPE_KEYS) {
            expect(ok('challenge_percept', { percept_ref: 'p', challenge_type: k }), k).toBeTruthy();
        }
    });

    it('refuses a mismatched target', () => {
        const a = ok('brush_field', { field_role: 'fold', label: 'f' });
        expect(validateAction({ ...a, target: 'manuscript' }).valid).toBe(false);
    });

    it('validateActionList keeps the good and reports the bad by index', () => {
        const good = ok('find_parts', {});
        const bad = { type: 'brush_field', payload: {}, id: 'x', label: 'l', source: 'user', status: 'proposed', target: 'image', createdAt: 0 };
        const { actions, rejected } = validateActionList([good, bad]);
        expect(actions).toEqual([good]);
        expect(rejected).toHaveLength(1);
        expect(rejected[0].index).toBe(1);
        expect(rejected[0].errors.join(' ')).toContain('field_role');
    });
});

// ── the discipline rules ─────────────────────────────────────────────────────

describe('rules that are about the product, not the schema', () => {
    it('a model may never author a challenge', () => {
        // P1 addendum §3.1: the human's veto over the circuit. This is the one rule here
        // that is not about shape, and it is the most important one.
        expect(normalizeAction({
            type: 'challenge_percept', source: 'model_suggested',
            payload: { percept_ref: 'p', challenge_type: 'contradiction' },
        }, { now: 0 })).toBe(null);

        // …and the same action from any other source is fine.
        expect(normalizeAction({
            type: 'challenge_percept', source: 'system',
            payload: { percept_ref: 'p', challenge_type: 'contradiction' },
        }, { now: 0 })).toBeTruthy();
    });

    it('an ask that claims it was sent is refused, not quietly corrected', () => {
        // Silently resetting the flag is how a dispatch happens. Refuse it.
        expect(ok('ask_model_reading', {
            requested_reading_type: 'describe', dispatch: { sent: true },
        })).toBe(null);

        const a = ok('ask_model_reading', {
            requested_reading_type: 'describe', dispatch: { sent: false },
        });
        expect(a).toBeTruthy();
        expect(a.warnings.join(' ')).toContain('no model call');
    });

    it('ask_model_reading can never be applied, whatever the UI claims it can do', () => {
        const a = ok('ask_model_reading', { requested_reading_type: 'describe' });
        expect(actionCanApplyNow(a, ACTION_TYPES)).toBe(false);
    });

    it('a manuscript action always warns that nothing is saved', () => {
        const a = ok('start_manuscript', { mode: 'art_critique' });
        expect(a.warnings.join(' ').toLowerCase()).toContain('nothing is saved');
    });

    it('a percept resting on an unsettleable claim says so', () => {
        const a = ok('compose_percept', { draft_text: 'she is Athena', external_claim_warning: true });
        expect(a.warnings.join(' ')).toContain('frame may not settle');
    });
});

// ── geometry and applicability ───────────────────────────────────────────────

describe('which acts need a mark from the curator', () => {
    it('image marks and connections do; the rest do not', () => {
        expect(actionNeedsGeometry(ok('brush_field', { field_role: 'fold', label: 'f' }))).toBe(true);
        expect(actionNeedsGeometry(ok('trace_direction', { trace_role: 'gesture', label: 'g' }))).toBe(true);
        expect(actionNeedsGeometry(ok('connect_marks', { relation_role: 'contrast' }))).toBe(true);
        expect(actionNeedsGeometry(ok('find_parts', {}))).toBe(false);
        expect(actionNeedsGeometry(ok('compose_percept', { draft_text: 'x' }))).toBe(false);
    });

    it('says so in a warning, so the card can never imply it draws for you', () => {
        const a = ok('brush_field', { field_role: 'light_field', label: 'l' });
        expect(a.warnings.join(' ')).toContain('Needs a mark from you');
    });

    it('applicability is decided by the mounted surface, not by the action', () => {
        const a = ok('brush_field', { field_role: 'fold', label: 'f' });
        expect(actionCanApplyNow(a, [])).toBe(false);
        expect(actionCanApplyNow(a, ['brush_field'])).toBe(true);
    });

    it('a dismissed or already-applied action cannot be applied again', () => {
        const a = ok('find_parts', {});
        expect(actionCanApplyNow({ ...a, status: 'dismissed' }, ['find_parts'])).toBe(false);
        expect(actionCanApplyNow({ ...a, status: 'applied' }, ['find_parts'])).toBe(false);
    });
});

// ── reading a set ────────────────────────────────────────────────────────────

describe('presenting a set of proposals', () => {
    const set = () => [
        ok('find_parts', {}),
        ok('brush_field', { field_role: 'light_field', label: 'light' }),
        ok('compose_percept', { draft_text: 'the light holds the left side' }),
        ok('start_manuscript', { mode: 'description' }),
    ];

    it('groups by target in a fixed order, skipping empty groups', () => {
        const groups = groupActionsByTarget(set());
        expect(groups.map((g) => g.target)).toEqual(['image', 'percept', 'manuscript', 'operation']);
        expect(groups.find((g) => g.target === 'ground')).toBeUndefined();
    });

    it('summarises as SUGGESTED acts, never as findings', () => {
        // The planner proposes; it does not detect. Copy that says "found" would make a
        // lexicon match look like an observation about the image.
        const s = summarizeActions(set());
        expect(s).toContain('4 suggested acts');
        expect(s).toContain('1 needs a mark from you');
        expect(s.toLowerCase()).not.toContain('found');
        expect(s.toLowerCase()).not.toContain('detected');
    });

    it('dismissed acts leave the summary', () => {
        const acts = setActionStatus(set(), set()[0].id, 'dismissed');
        expect(summarizeActions(acts.map((a, i) => (i === 0 ? { ...a, status: 'dismissed' } : a))))
            .toContain('3 suggested acts');
        expect(summarizeActions([])).toBe('no suggested acts');
    });

    it('status changes never mutate the input list', () => {
        const before = set();
        const snapshot = JSON.parse(JSON.stringify(before));
        const after = setActionStatus(before, before[1].id, 'dismissed');
        expect(before).toEqual(snapshot);              // untouched
        expect(after[1].status).toBe('dismissed');
        expect(after[0]).toBe(before[0]);              // unchanged items keep identity
    });

    it('refuses an unknown status rather than writing it', () => {
        const before = set();
        expect(setActionStatus(before, before[0].id, 'vibing')).toBe(before);
    });

    it('a short reason prefers the payload, then the intent, then the words matched', () => {
        expect(actionToShortReason(ok('find_parts', { reason: 'because' }))).toBe('because');
        expect(actionToShortReason(ok('find_parts', {}, { intent: 'open it up' }))).toBe('open it up');
        expect(actionToShortReason(ok('find_parts', {}, { provenance: { matched: ['gaze'] } })))
            .toBe('you said “gaze”');
        expect(actionToShortReason(ok('find_parts', {}))).toBe('');
        expect(actionToShortReason(null)).toBe('');
    });

    it('a human label always exists', () => {
        for (const t of ACTION_TYPES) {
            const a = ok(t, minimalPayload(t));
            expect(actionToHumanLabel(a), t).toBeTruthy();
        }
    });
});

function minimalPayload(type) {
    switch (type) {
        case 'brush_field': return { field_role: 'fold', label: 'f' };
        case 'trace_direction': return { trace_role: 'gesture', label: 'g' };
        case 'connect_marks': return { relation_role: 'contrast' };
        case 'compose_percept': return { draft_text: 'x' };
        case 'assign_ground_role': return { ground_id: 'g1', role: 'anchor' };
        case 'start_manuscript': return { mode: 'description' };
        case 'challenge_percept': return { percept_ref: 'p', challenge_type: 'overreach' };
        case 'ask_model_reading': return { requested_reading_type: 'describe' };
        default: return {};
    }
}
