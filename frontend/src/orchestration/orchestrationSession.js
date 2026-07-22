/**
 * Orchestration Session — the working context a future model call would consume.
 *
 * CIRCUIT-001 P2C-OS. **Pure assembler. Nothing here calls anything.**
 * No fetch, no model client, no store, no persistence, no `run_id` minted, no
 * clock it is not handed.
 *
 * It is Perceptive Orchestration widened from one percept (P1C's packet) to the
 * whole current circuit: the image, the selection, the writing, the evidence,
 * what was asked before, and what the curator said caught them. It exists BEFORE
 * dispatch for the reason the rehearsal programme paid eleven runs to learn —
 * the value is not in the call but in freezing what was asked, on what evidence,
 * under what constraints, *and being able to refuse an invalid request without
 * spending anything*.
 *
 * What it is NOT:
 *   - not an agent — no loop, no goals, no memory across posts, cannot call out
 *   - not persistent memory — assembled on demand, read once, discarded
 *   - not a mutation path — it holds proposals; applying one goes through
 *     perceptualActions' validators and the curator's hand
 *   - not a prompt — constraints travel as DATA, so the discipline cannot be
 *     quietly edited by whoever writes the next prompt template
 *
 * The governing rule: it may suggest, Semant shapes, the user confirms. Only
 * then does an action enter the circuit.
 *
 * Honesty invariants, in order of how easily a later refactor destroys them:
 *   - `unreadable[]` names everything asked for and not obtained. Silence must
 *     never be readable as absence.
 *   - `external_claims: null` means NOT ASSESSED. `[]` would mean assessed and
 *     found none. There is no assessor, so `null` is the only honest value.
 *   - `resolution_assessed: false` means every `detached` flag carries NO
 *     information — the same refusal `buildPerceptPacket` makes without a resolver.
 *   - `citation_state: 'cites_nothing'` is a RECORD. It is not 'unsupported',
 *     which is a judgement the system cannot make.
 *   - `dispatch_state` is stated inside the object so it cannot be mistaken for
 *     a dispatch record.
 */

import { ACTION_TYPES } from '../differential/perceptualActions';

export const SESSION_VERSION = 1;

/** Which half of the product the curator is standing in. */
export const SURFACES = ['differential', 'manuscript', 'unknown'];

/** Dispatch is stated, never assumed. `sent` requires a run_id the ledger can show. */
export const DISPATCH_STATES = ['none', 'preview_only', 'sent'];

/**
 * The discipline, as data. The first four are P1C's, carried verbatim so a
 * session and a packet cannot drift apart. The last four are this gate's.
 */
export const SESSION_CONSTRAINTS = {
    image_only: true,
    mark_external_claims: true,
    ask_for_contradictions: true,
    no_identity_claims: true,
    // Never assert that one thing produced another. "No longer resolves", not
    // "was replaced by". The circuit has no causal record and must not imply one.
    no_fake_causality: true,
    // What was seen and what was concluded render in different voices (P1D).
    distinguish_observed_from_inferred: true,
    // A proposal is not a finding. Nothing suggested counts as evidence.
    suggestions_are_not_committed_truth: true,
    // The only path into the circuit.
    user_confirmation_required_for_mutation: true,
};

/**
 * What a consumer may return, and what it may not do. `may_mutate: false` is an
 * error to override, not a default to tweak.
 */
export const MODEL_IO_POLICY = {
    output_shape: 'perceptual_action_list',
    must_validate_against: 'perceptualActions.normalizeAction',
    may_mutate: false,
    may_persist: false,
    // P2B's human veto: a model may never author a challenge. Enforced there in
    // the validator, restated here so a session cannot advertise it as allowed.
    may_author_challenge: false,
    unknown_fields_rejected: true,
};

/** Refused to every consumer, with the reason travelling alongside. */
export const FORBIDDEN_ACTIONS = [
    { type: 'challenge_percept', reason: 'a model may not author a challenge' },
    { type: 'ask_model_reading', reason: 'dispatch is not wired in this gate' },
];
const FORBIDDEN_TYPES = FORBIDDEN_ACTIONS.map((f) => f.type);

let _seq = 0;
export function sessionId(prefix = 'os') {
    return `${prefix}_${(_seq++).toString(36)}`;
}
export function _resetSessionIds() { _seq = 0; }  // test aid only

const arr = (v) => (Array.isArray(v) ? [...v] : []);

/**
 * Assemble the session.
 *
 * Everything is supplied; nothing is fetched. An input that is not supplied is
 * not guessed — it is named in `unreadable` so a consumer is told it was not
 * given the thing, rather than inferring from silence that there was none.
 *
 * @returns a plain, JSON-serialisable object. Never null — a session with
 *          nothing in it is still an honest session, and says so.
 */
export function buildOrchestrationSession({
    postId = null,
    activeSurface = 'unknown',
    // image
    image = null,                 // { dimensions, regions, grounds, percepts }
    // selection
    selections = null,            // { region_ids, ground_ids, percept_ids, visual_mark_ids, source }
    // the percept in focus
    percept = null,
    packet = null,                // buildPerceptPacket output, verbatim
    threadSummary = null,         // threadSummary(buildCirculationThread(...))
    groundEntries = null,         // groundRoleList(...) output
    resolutionAssessed = false,
    // the writing
    manuscript = null,            // { block_count, is_editing, selection, model_origin_blocks }
    // memory of asking
    operationMemory = null,       // [{ operation, state, at }]
    // proposals
    proposedActions = [],
    capabilities = [],
    captivation = null,           // { prompt, matched }
    // policy
    constraints = {},
    dispatchState = 'none',
    provenance = {},
    now = null,
} = {}) {
    const unreadable = [];
    const note = (what) => { if (!unreadable.includes(what)) unreadable.push(what); };

    if (!postId) note('post_id');
    if (!image) note('image_context');
    if (!manuscript) note('manuscript_context');
    if (!operationMemory) note('operation_memory');
    if (image && image.dimensions == null) note('image_dimensions');

    const surface = SURFACES.includes(activeSurface) ? activeSurface : 'unknown';

    // ── percept context ──────────────────────────────────────────────────────
    // evidence_state comes from the packet when one is supplied; 'unknown' is the
    // floor, never 'intact'. Absent is not nominal.
    let perceptContext = null;
    if (percept?.id) {
        perceptContext = {
            percept_id: percept.id,
            expression: percept.expression || '',
            evidence_state: packet?.evidence?.state || 'unknown',
            packet: packet || null,
            thread_summary: threadSummary || null,
        };
        if (!packet) note('percept_packet');
        if (!threadSummary) note('circulation_thread');
    }

    // ── ground context ───────────────────────────────────────────────────────
    // `resolution_assessed: false` means `present`/`detached` mean NOTHING. The
    // flag exists so a consumer cannot read a default and believe it.
    const entries = arr(groundEntries);
    const groundContext = {
        cited: entries,
        roles_named: entries.filter((g) => g && g.role).length,
        resolution_assessed: !!resolutionAssessed,
    };
    if (entries.length && !resolutionAssessed) note('ground_resolution');

    // ── manuscript context ───────────────────────────────────────────────────
    const sel = manuscript?.selection || null;
    const manuscriptContext = {
        block_count: manuscript?.block_count ?? 0,
        is_editing: !!manuscript?.is_editing,
        selection: sel
            ? {
                kind: sel.kind || 'none',
                text: sel.text || '',
                block_id: sel.block_id || null,
                cited_percept_ids: arr(sel.cited_percept_ids),
                cited_ground_ids: arr(sel.cited_ground_ids),
                // A RECORD, not a judgement. 'cites_nothing' says what the markup
                // shows; it does not say the sentence rests on nothing.
                citation_state: sel.citation_state || 'not_assessed',
            }
            : { kind: 'none', text: '', block_id: null, cited_percept_ids: [], cited_ground_ids: [], citation_state: 'not_assessed' },
        model_origin_blocks: arr(manuscript?.model_origin_blocks),
        // null = not assessed. `extract_claims` does not exist; anyone who
        // "cleans this up" to [] converts *we did not look* into *there are none*.
        external_claims: null,
    };
    if (manuscript) note('external_claim_assessment');

    // ── operation memory ─────────────────────────────────────────────────────
    const memory = {
        recent: arr(operationMemory),
        assessed: Array.isArray(operationMemory),
        // Being latest says nothing about having produced anything (P1F/visionActivity).
        note: 'a projection of recorded runs; no run is claimed to have produced anything',
    };

    return {
        session_version: SESSION_VERSION,
        session_id: sessionId(),
        post_id: postId,
        built_at: now || null,

        image_context: {
            post_id: postId,
            has_image: !!image,
            dimensions: image?.dimensions ?? null,
            regions_present: image?.regions ?? 0,
            grounds_present: image?.grounds ?? 0,
            percepts_present: image?.percepts ?? 0,
        },

        active_surface: surface,

        selections: {
            region_ids: arr(selections?.region_ids),
            ground_ids: arr(selections?.ground_ids),
            percept_ids: arr(selections?.percept_ids),
            visual_mark_ids: arr(selections?.visual_mark_ids),
            source: selections?.source || 'user',
        },

        percept_context: perceptContext,
        ground_context: groundContext,
        manuscript_context: manuscriptContext,
        operation_memory: memory,

        proposed_actions: arr(proposedActions),
        allowed_actions: allowedFrom(capabilities),
        forbidden_actions: FORBIDDEN_ACTIONS.map((f) => ({ ...f })),
        // Empty means the consumer may call nothing. It is the correct default
        // and this gate does not populate it.
        available_tools: [],

        user_captivation: captivation?.prompt
            ? {
                prompt: captivation.prompt,
                matched: arr(captivation.matched),
                // The planner says what you said, never what it saw.
                note: "the curator's words. Not a perception.",
            }
            : null,

        constraints: { ...SESSION_CONSTRAINTS, ...constraints },
        model_io_policy: { ...MODEL_IO_POLICY },

        dispatch_state: DISPATCH_STATES.includes(dispatchState) ? dispatchState : 'none',
        unreadable,
        provenance: {
            assembler: 'orchestration/session-v1',
            planner: null,
            model: null,
            run_id: null,
            ...provenance,
        },
    };
}

/**
 * ACTION_TYPES ∩ capabilities, minus the forbidden. Derived — a session can
 * never name an action the grammar does not define, and a surface can never
 * claim a capability the grammar has not sanctioned.
 */
export function allowedFrom(capabilities = []) {
    return ACTION_TYPES.filter(
        (t) => capabilities.includes(t) && !FORBIDDEN_TYPES.includes(t),
    );
}

export const sessionAllowedActions = (session) => arr(session?.allowed_actions);

/** One honest line. Degradation-aware, never alarmist, never reassuring. */
export function summarizeSession(session) {
    if (!session) return '';
    const bits = [session.active_surface];

    const sel = session.manuscript_context?.selection;
    if (sel && sel.kind !== 'none') {
        bits.push(sel.kind === 'percept_chip' ? 'percept chip selected' : 'text selected');
        if (sel.citation_state === 'cites_nothing') bits.push('cites nothing');
        else if (sel.citation_state === 'cites_percepts') {
            const n = sel.cited_percept_ids.length;
            bits.push(`cites ${n} percept${n === 1 ? '' : 's'}`);
        }
    }

    const ev = session.percept_context?.evidence_state;
    if (ev && ev !== 'intact') bits.push(`evidence ${ev}`);

    const n = session.proposed_actions.length;
    if (n) bits.push(`${n} suggested act${n === 1 ? '' : 's'}`);

    bits.push(session.dispatch_state === 'none' ? 'nothing sent' : session.dispatch_state);
    return bits.join(' · ');
}

/**
 * What a model WOULD be given — so a curator can read it before anything is
 * asked. P2C-OH's CVAT lesson: a provenance field nobody can see is, in
 * practice, no provenance at all.
 *
 * Strips the process-local id and the built_at clock (neither is context), and
 * states again, in the returned object, that nothing is sent.
 */
export function sessionForModelPreview(session) {
    if (!session) return null;
    const { session_id, built_at, ...rest } = session;
    return {
        ...rest,
        preview: true,
        note: 'assembled for inspection; nothing is sent',
    };
}

/**
 * Refuse rather than correct. P2B's rule about `dispatch.sent`: silently
 * resetting a flag is *how a dispatch happens*.
 *
 * @returns { valid, errors[], warnings[] } — warnings travel WITH the session
 *          and are shown, which is how an assembly admits its own weakness.
 */
export function validateSession(session) {
    const errors = [];
    const warnings = [];
    if (!session) return { valid: false, errors: ['no session'], warnings };

    if (session.dispatch_state === 'sent' && !session.provenance?.run_id) {
        errors.push('dispatch_state is "sent" but no run_id is recorded');
    }
    for (const t of sessionAllowedActions(session)) {
        if (!ACTION_TYPES.includes(t)) errors.push(`allowed action not in the grammar: ${t}`);
        if (FORBIDDEN_TYPES.includes(t)) errors.push(`forbidden action allowed: ${t}`);
    }
    if (session.model_io_policy?.may_mutate) {
        errors.push('model_io_policy.may_mutate must be false');
    }
    if (session.model_io_policy?.may_persist) {
        errors.push('model_io_policy.may_persist must be false');
    }
    // assessed-and-found-none, asserted without an assessor.
    if (Array.isArray(session.manuscript_context?.external_claims)
        && !(session.available_tools || []).includes('extract_claims')) {
        errors.push('external_claims asserted without an assessor');
    }

    if (session.ground_context && !session.ground_context.resolution_assessed
        && session.ground_context.cited.length) {
        warnings.push('ground resolution not assessed — detached flags carry no information');
    }
    if (session.percept_context?.evidence_state === 'unknown') {
        warnings.push('evidence state unknown — not healthy, not computed');
    }
    if ((session.unreadable || []).length) {
        warnings.push(`not obtained: ${session.unreadable.join(', ')}`);
    }

    return { valid: errors.length === 0, errors, warnings };
}
