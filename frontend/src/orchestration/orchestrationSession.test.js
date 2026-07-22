import { describe, it, expect, beforeEach } from 'vitest';
import {
    buildOrchestrationSession, summarizeSession, sessionAllowedActions,
    sessionForModelPreview, validateSession, allowedFrom, _resetSessionIds,
    MANUSCRIPT_ACTION_STATUSES, RETURN_TARGETS,
} from './orchestrationSession';
import { ACTION_TYPES } from '../differential/perceptualActions';
import { describeSelection } from '../manuscript/manuscriptField';

beforeEach(() => _resetSessionIds());

const base = { postId: 'post_1', activeSurface: 'manuscript' };

describe('missing data is represented honestly', () => {
    it('names everything it was not given in unreadable', () => {
        const s = buildOrchestrationSession({});
        expect(s.unreadable).toContain('post_id');
        expect(s.unreadable).toContain('image_context');
        expect(s.unreadable).toContain('manuscript_context');
        expect(s.unreadable).toContain('operation_memory');
    });

    it('reports image dimensions as not obtained rather than guessing', () => {
        const s = buildOrchestrationSession({ ...base, image: { regions: 3, grounds: 2 } });
        expect(s.image_context.dimensions).toBeNull();
        expect(s.unreadable).toContain('image_dimensions');
    });

    it('never assumes evidence is healthy without a packet', () => {
        const s = buildOrchestrationSession({ ...base, percept: { id: 'pctx_1', expression: 'x' } });
        expect(s.percept_context.evidence_state).toBe('unknown');
        expect(s.unreadable).toContain('percept_packet');
    });

    it('keeps external_claims null — not an empty list', () => {
        // [] would mean assessed and found none. There is no assessor.
        const s = buildOrchestrationSession({ ...base, manuscript: { block_count: 2 } });
        expect(s.manuscript_context.external_claims).toBeNull();
        expect(s.manuscript_context.external_claims).not.toEqual([]);
        expect(s.unreadable).toContain('external_claim_assessment');
    });

    it('flags that detached carries no information when resolution was not assessed', () => {
        const s = buildOrchestrationSession({
            ...base, groundEntries: [{ ground_id: 'g1', label: 'a', role: 'anchor' }],
        });
        expect(s.ground_context.resolution_assessed).toBe(false);
        expect(s.unreadable).toContain('ground_resolution');
        expect(validateSession(s).warnings.join(' ')).toMatch(/carry no information/);
    });

    it('is still a valid session when it knows almost nothing', () => {
        expect(validateSession(buildOrchestrationSession({})).valid).toBe(true);
    });
});

describe('observed vs inferred is explicit', () => {
    it('attributes the captivation prompt to the curator, not to perception', () => {
        const s = buildOrchestrationSession({
            ...base, captivation: { prompt: 'the gaze she points toward', matched: ['gaze'] },
        });
        expect(s.user_captivation.note).toMatch(/curator's words/);
        expect(s.user_captivation.note).toMatch(/Not a perception/);
    });

    it('refuses to imply one operation produced another', () => {
        const s = buildOrchestrationSession({ ...base, operationMemory: [{ operation: 'dissect', state: 'done' }] });
        expect(s.operation_memory.note).toMatch(/no run is claimed to have produced anything/);
    });

    it('carries the no-fake-causality and observed/inferred constraints as data', () => {
        const s = buildOrchestrationSession(base);
        expect(s.constraints.no_fake_causality).toBe(true);
        expect(s.constraints.distinguish_observed_from_inferred).toBe(true);
        expect(s.constraints.suggestions_are_not_committed_truth).toBe(true);
        expect(s.constraints.user_confirmation_required_for_mutation).toBe(true);
    });

    it('keeps cites_nothing a record, never "unsupported"', () => {
        const s = buildOrchestrationSession({
            ...base,
            manuscript: { block_count: 1, selection: describeSelection({ kind: 'text', text: 'x' }) },
        });
        expect(s.manuscript_context.selection.citation_state).toBe('cites_nothing');
        expect(JSON.stringify(s)).not.toMatch(/unsupported/);
    });
});

describe('allowed actions come from perceptualActions', () => {
    it('intersects with the grammar and cannot invent a type', () => {
        const s = buildOrchestrationSession({
            ...base, capabilities: ['find_parts', 'brush_field', 'teleport_percept'],
        });
        expect(s.allowed_actions).toEqual(['find_parts', 'brush_field']);
        for (const t of sessionAllowedActions(s)) expect(ACTION_TYPES).toContain(t);
    });

    it('never allows a model-authored challenge, even if claimed as a capability', () => {
        expect(allowedFrom(['challenge_percept'])).toEqual([]);
        const s = buildOrchestrationSession({ ...base, capabilities: ['challenge_percept'] });
        expect(s.allowed_actions).not.toContain('challenge_percept');
        expect(s.forbidden_actions.map((f) => f.type)).toContain('challenge_percept');
    });

    it('never allows a model reading — dispatch is not wired', () => {
        expect(allowedFrom(['ask_model_reading'])).toEqual([]);
    });

    it('carries the reason alongside each refusal', () => {
        const s = buildOrchestrationSession(base);
        for (const f of s.forbidden_actions) expect(f.reason).toBeTruthy();
    });

    it('offers no tools at all by default', () => {
        expect(buildOrchestrationSession(base).available_tools).toEqual([]);
    });
});

describe('dispatch state defaults to none and cannot be faked', () => {
    it('defaults to none', () => {
        expect(buildOrchestrationSession(base).dispatch_state).toBe('none');
        expect(buildOrchestrationSession(base).provenance.run_id).toBeNull();
    });

    it('accepts preview_only', () => {
        expect(buildOrchestrationSession({ ...base, dispatchState: 'preview_only' }).dispatch_state).toBe('preview_only');
    });

    it('falls back to none for an unknown dispatch state', () => {
        expect(buildOrchestrationSession({ ...base, dispatchState: 'obviously_sent' }).dispatch_state).toBe('none');
    });

    it('REFUSES a sent session with no run_id, rather than correcting it', () => {
        // Silently resetting the flag is how a dispatch happens.
        const s = buildOrchestrationSession({ ...base, dispatchState: 'sent' });
        const v = validateSession(s);
        expect(v.valid).toBe(false);
        expect(v.errors.join(' ')).toMatch(/no run_id/);
    });

    it('accepts a sent session once the ledger can show the run', () => {
        const s = buildOrchestrationSession({ ...base, dispatchState: 'sent', provenance: { run_id: 'run_1' } });
        expect(validateSession(s).valid).toBe(true);
    });

    it('states in the preview that nothing is sent', () => {
        const p = sessionForModelPreview(buildOrchestrationSession(base));
        expect(p.note).toMatch(/nothing is sent/);
        expect(p.dispatch_state).toBe('none');
        expect(p.session_id).toBeUndefined();
    });
});

describe('validateSession refuses rather than corrects', () => {
    it('refuses a mutating or persisting policy', () => {
        const s = buildOrchestrationSession(base);
        expect(validateSession({ ...s, model_io_policy: { ...s.model_io_policy, may_mutate: true } }).valid).toBe(false);
        expect(validateSession({ ...s, model_io_policy: { ...s.model_io_policy, may_persist: true } }).valid).toBe(false);
    });

    it('refuses an allowed action outside the grammar', () => {
        const s = buildOrchestrationSession(base);
        expect(validateSession({ ...s, allowed_actions: ['make_it_nicer'] }).valid).toBe(false);
    });

    it('refuses external claims asserted without an assessor', () => {
        const s = buildOrchestrationSession({ ...base, manuscript: { block_count: 1 } });
        const faked = { ...s, manuscript_context: { ...s.manuscript_context, external_claims: [] } };
        expect(validateSession(faked).valid).toBe(false);
        expect(validateSession(faked).errors.join(' ')).toMatch(/without an assessor/);
    });

    it('warns rather than errors on unknown evidence, so the weakness travels', () => {
        const s = buildOrchestrationSession({ ...base, percept: { id: 'pctx_1' } });
        const v = validateSession(s);
        expect(v.valid).toBe(true);
        expect(v.warnings.join(' ')).toMatch(/evidence state unknown/);
    });

    it('refuses nothing at all', () => {
        expect(validateSession(null).valid).toBe(false);
    });
});

describe('manuscript selection and percept context can be included', () => {
    it('includes a text selection with its citations', () => {
        const selection = describeSelection({
            kind: 'text', text: 'the fold reads as architecture',
            chips: [{ perceptId: 'pctx_1', regionIds: 'gnd_1,gnd_2' }],
        });
        const s = buildOrchestrationSession({
            ...base, manuscript: { block_count: 3, is_editing: true, selection },
        });
        expect(s.manuscript_context.selection.kind).toBe('text');
        expect(s.manuscript_context.selection.text).toBe('the fold reads as architecture');
        expect(s.manuscript_context.selection.cited_percept_ids).toEqual(['pctx_1']);
        expect(s.manuscript_context.selection.cited_ground_ids).toEqual(['gnd_1', 'gnd_2']);
        expect(s.manuscript_context.is_editing).toBe(true);
    });

    it('defaults to an empty selection rather than omitting the field', () => {
        const s = buildOrchestrationSession({ ...base, manuscript: { block_count: 1 } });
        expect(s.manuscript_context.selection.kind).toBe('none');
        expect(s.manuscript_context.selection.citation_state).toBe('not_assessed');
    });

    it('records which blocks are model-origin', () => {
        const s = buildOrchestrationSession({
            ...base, manuscript: { block_count: 2, model_origin_blocks: ['b2'] },
        });
        expect(s.manuscript_context.model_origin_blocks).toEqual(['b2']);
    });

    it('includes the packet and thread summary when supplied', () => {
        const packet = { evidence: { state: 'partial' }, dispatch: { sent: false, run_id: null } };
        const s = buildOrchestrationSession({
            ...base,
            percept: { id: 'pctx_1', expression: 'the upper head' },
            packet, threadSummary: 'cites 2 grounds · not yet in the writing',
        });
        expect(s.percept_context.evidence_state).toBe('partial');
        expect(s.percept_context.packet).toBe(packet);
        expect(s.percept_context.thread_summary).toMatch(/cites 2 grounds/);
        expect(s.unreadable).not.toContain('percept_packet');
    });

    it('counts named ground roles as a record', () => {
        const s = buildOrchestrationSession({
            ...base, resolutionAssessed: true,
            groundEntries: [
                { ground_id: 'g1', role: 'anchor', detached: false },
                { ground_id: 'g2', role: 'counterforce', detached: false },
                { ground_id: 'g3', role: null, detached: false },
            ],
        });
        expect(s.ground_context.roles_named).toBe(2);
        expect(s.ground_context.resolution_assessed).toBe(true);
    });
});

describe('a Manuscript action can be represented, and never implies dispatch', () => {
    it('records the requested action, its status, and its return target', () => {
        const s = buildOrchestrationSession({
            ...base,
            manuscriptAction: { type: 'revise', status: 'applied', return_target: 'differential' },
        });
        expect(s.manuscript_context.requested_action).toEqual({
            type: 'revise', status: 'applied', return_target: 'differential',
        });
        // A local effect ran — but nothing was dispatched.
        expect(s.dispatch_state).toBe('none');
    });

    it('defaults an unknown status to preview_only and an unknown target to null', () => {
        const s = buildOrchestrationSession({
            ...base, manuscriptAction: { type: 'map_sentence', status: 'teleported', return_target: 'the_moon' },
        });
        expect(s.manuscript_context.requested_action.status).toBe('preview_only');
        expect(s.manuscript_context.requested_action.return_target).toBeNull();
    });

    it('is null when no action was reached for', () => {
        expect(buildOrchestrationSession(base).manuscript_context.requested_action).toBeNull();
    });

    it('an applied Manuscript action does not make the session claim a dispatch', () => {
        const s = buildOrchestrationSession({
            ...base, manuscriptAction: { type: 'recall', status: 'applied', return_target: 'image' },
        });
        expect(validateSession(s).valid).toBe(true);
        expect(s.dispatch_state).not.toBe('sent');
    });

    it('exposes the status and target vocabularies', () => {
        expect(MANUSCRIPT_ACTION_STATUSES).toContain('preview_only');
        expect(MANUSCRIPT_ACTION_STATUSES).toContain('staged');
        expect(MANUSCRIPT_ACTION_STATUSES).toContain('applied');
        expect(RETURN_TARGETS).toEqual(['image', 'differential', 'percept', 'ground']);
    });
});

describe('the session is serialisable and inert', () => {
    it('round-trips through JSON unchanged', () => {
        const s = buildOrchestrationSession({ ...base, capabilities: ['find_parts'] });
        expect(JSON.parse(JSON.stringify(s))).toEqual(s);
    });

    it('holds no functions', () => {
        const walk = (v) => {
            expect(typeof v).not.toBe('function');
            if (v && typeof v === 'object') Object.values(v).forEach(walk);
        };
        walk(buildOrchestrationSession({ ...base, capabilities: ['find_parts'] }));
    });

    it('declares a policy that forbids mutation and persistence', () => {
        const s = buildOrchestrationSession(base);
        expect(s.model_io_policy.may_mutate).toBe(false);
        expect(s.model_io_policy.may_persist).toBe(false);
        expect(s.model_io_policy.may_author_challenge).toBe(false);
        expect(s.model_io_policy.must_validate_against).toMatch(/normalizeAction/);
    });

    it('does not mint a run_id', () => {
        expect(buildOrchestrationSession(base).provenance.run_id).toBeNull();
    });
});

describe('summarizeSession says what is so, quietly', () => {
    it('reports the surface, the selection, and that nothing was sent', () => {
        const s = buildOrchestrationSession({
            ...base,
            manuscript: { block_count: 1, selection: describeSelection({ kind: 'text', text: 'x' }) },
        });
        expect(summarizeSession(s)).toBe('manuscript · text selected · cites nothing · nothing sent');
    });

    it('counts suggested acts as suggested, never found', () => {
        const s = buildOrchestrationSession({ ...base, proposedActions: [{ type: 'brush_field' }, { type: 'find_parts' }] });
        expect(summarizeSession(s)).toMatch(/2 suggested acts/);
        expect(summarizeSession(s)).not.toMatch(/found/);
    });

    it('stays silent about healthy evidence', () => {
        const s = buildOrchestrationSession({
            ...base, percept: { id: 'p' }, packet: { evidence: { state: 'intact' } },
        });
        expect(summarizeSession(s)).not.toMatch(/evidence/);
    });

    it('surfaces degraded evidence', () => {
        const s = buildOrchestrationSession({
            ...base, percept: { id: 'p' }, packet: { evidence: { state: 'detached' } },
        });
        expect(summarizeSession(s)).toMatch(/evidence detached/);
    });
});
