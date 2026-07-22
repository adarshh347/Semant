/**
 * Manuscript field — deriving what a selection or a percept chip rests on.
 *
 * CIRCUIT-001 P2C-MS. **Pure. No React, no DOM ownership, no store, no fetch.**
 * It is handed what was selected and answers questions about it.
 *
 * The Manuscript stops being a text box beside the image and becomes a surface
 * of the circuit: a sentence can be asked what it cites, and can answer
 * honestly — including "nothing", and including "not assessed".
 *
 * The distinction this module exists to hold, and the one most easily lost:
 *
 *   RECORD      what the markup shows.  "cites nothing."
 *   JUDGEMENT   what the system concludes and owns. "rests on nothing."
 *
 * The system possesses the first and not the second. A sentence with no chip may
 * be perfectly grounded in a curator's looking and simply uncited. Rendering
 * `unsupported` where we know only `cites_nothing` is the fake causality P1
 * forbids, and it would make citation performative: a curator scored on
 * citations cites to clear the score, and the mention graph stops recording
 * where attention actually went.
 *
 * So: no green ticks. Nothing renders when nothing is wrong. The inspector
 * answers when asked and volunteers only a real degradation.
 */

import { groundRoleList, roleLabel } from '../differential/groundRoles';
import { normalizeAction } from '../differential/perceptualActions';

/** The objects that can live in, or attach to, the writing. `exists` is honest. */
export const MANUSCRIPT_OBJECTS = [
    { key: 'text', label: 'plain text', exists: true },
    { key: 'selection', label: 'sentence / selection', exists: true, derived: true },
    { key: 'passage', label: 'paragraph / passage', exists: true },
    { key: 'percept_chip', label: 'percept chip', exists: true },
    { key: 'ground_ref', label: 'ground reference', exists: false },
    { key: 'field_ref', label: 'field reference', exists: false },
    { key: 'trace_ref', label: 'trace reference', exists: false },
    { key: 'relation_ref', label: 'relation reference', exists: false },
    { key: 'model_draft', label: 'model draft', exists: true, partial: true },
    { key: 'external_claim', label: 'external claim', exists: false },
    { key: 'action_block', label: 'action block', exists: false },
    { key: 'recall_target', label: 'recall target', exists: true, derived: true },
];
export const MANUSCRIPT_OBJECT_KEYS = MANUSCRIPT_OBJECTS.map((o) => o.key);

/** What the markup shows about a selection's citations. All three are RECORDS. */
export const CITATION_STATES = ['cites_nothing', 'cites_percepts', 'not_assessed'];

export const SELECTION_KINDS = ['none', 'text', 'percept_chip'];

/**
 * Describe a selection.
 *
 * @param kind        'none' | 'text' | 'percept_chip'
 * @param text        the selected prose, verbatim — never paraphrased, because
 *                    `compose_percept` is seeded with the curator's own sentence
 * @param blockId     the block the selection sits in, when known
 * @param chips       [{ perceptId, regionIds, label }] found inside the range
 * @param assessed    whether the caller actually looked for chips. false ⇒
 *                    `not_assessed`, never `cites_nothing` — the difference
 *                    between "no citations" and "we did not check"
 */
export function describeSelection({
    kind = 'none', text = '', blockId = null, chips = [], assessed = true,
} = {}) {
    const k = SELECTION_KINDS.includes(kind) ? kind : 'none';
    const list = Array.isArray(chips) ? chips : [];
    const perceptIds = [...new Set(list.map((c) => c?.perceptId).filter(Boolean))];
    // A percept chip's `data-region-ids` are GROUND ids (see perceptMentions'
    // note) — so they are collected as grounds, not regions.
    const groundIds = [...new Set(
        list.flatMap((c) => String(c?.regionIds || '').split(',').filter(Boolean)),
    )];

    let citation_state = 'not_assessed';
    if (k !== 'none' && assessed) {
        citation_state = perceptIds.length ? 'cites_percepts' : 'cites_nothing';
    }

    return {
        kind: k,
        text: k === 'none' ? '' : String(text || ''),
        block_id: blockId || null,
        cited_percept_ids: perceptIds,
        cited_ground_ids: groundIds,
        citation_state,
    };
}

/**
 * The eight questions a sentence can be asked (P2C-MS §2). Each answer states
 * its own voice, and `answerable: false` is reported rather than hidden — a
 * question we cannot answer must not look like a question with a clean answer.
 */
export function selectionQuestions(selection) {
    const s = selection || describeSelection();
    const cites = s.cited_percept_ids.length;
    const grounds = s.cited_ground_ids.length;
    const assessed = s.citation_state !== 'not_assessed';

    return [
        {
            key: 'cites', voice: 'record', answerable: assessed,
            question: 'What do I cite?',
            answer: !assessed ? 'not assessed'
                : cites ? `${cites} percept${cites === 1 ? '' : 's'}` : 'nothing',
        },
        {
            key: 'percepts', voice: 'record', answerable: assessed,
            question: 'What percepts support me?',
            answer: !assessed ? 'not assessed'
                : cites ? `${cites} cited` : 'none cited',
        },
        {
            key: 'grounds', voice: 'record', answerable: assessed,
            question: 'What grounds do I rely on?',
            answer: !assessed ? 'not assessed'
                : grounds ? `${grounds} ground${grounds === 1 ? '' : 's'} through its percepts` : 'none cited',
        },
        // Needs `extract_claims`, which does not exist. Answering anything else
        // would convert "we did not look" into "there are none".
        {
            key: 'external', voice: 'judgement', answerable: false,
            question: 'What here is external?',
            answer: 'external claims not assessed',
        },
        // Deliberately NOT "unsupported". See the module header.
        {
            key: 'unsupported', voice: 'judgement', answerable: false,
            question: 'What is unsupported?',
            answer: 'not assessed — cites nothing is not rests on nothing',
        },
        {
            key: 'recall', voice: 'record', answerable: assessed,
            question: 'What should be recalled on the image?',
            answer: !assessed ? 'not assessed'
                : cites ? `${cites} noticing${cites === 1 ? '' : 's'}` : 'nothing to replay',
        },
        {
            key: 'become_percept', voice: 'proposal', answerable: s.kind === 'text' && !!s.text.trim(),
            question: 'Should I become a percept?',
            answer: s.kind === 'text' && s.text.trim() ? 'can be proposed' : 'select some prose first',
        },
        {
            key: 'return', voice: 'proposal', answerable: s.kind !== 'none',
            question: 'Should I return to Differential?',
            answer: s.kind !== 'none' ? 'can be proposed' : 'nothing selected',
        },
    ];
}

/**
 * Open a percept chip into what it rests on (P2C-MS §3).
 *
 * Section order is the argument: what it says, what it rests on, what is wrong
 * ONLY IF something is, where it lives, what can be done.
 *
 * @param percept   the expression percept, or null when the chip's id does not
 *                  resolve in the store — a detached citation still reads, and
 *                  says so
 * @param grounds   the post's grounds
 * @param resolve   `(ground) => ({ detached })`. **Absent ⇒ evidence is UNKNOWN,
 *                  never intact.** Same refusal as buildPerceptPacket.
 * @param mentions  percept → block edges
 * @param recallCount session-local, and the copy must say "this session"
 */
export function buildChipInspection(percept, {
    grounds = [], resolve = null, mentions = [], recallCount = 0, label = '',
} = {}) {
    if (!percept?.id) {
        return {
            resolved: false,
            label: label || 'percept',
            // A record about our store, not a judgement about the percept.
            note: 'this citation no longer resolves in the workspace',
            sections: [],
            evidence: { state: 'unknown', note: 'evidence state not computed' },
        };
    }

    const entries = groundRoleList(percept, grounds, resolve);
    const cited = entries.length;
    const known = resolve ? entries.filter((g) => g.detached !== undefined) : [];
    const resolving = known.filter((g) => !g.detached).length;
    const state = !resolve ? 'unknown'
        : cited === 0 ? 'ungrounded'
            : resolving === 0 ? 'detached'
                : resolving < cited ? 'partial' : 'intact';

    const roled = entries.filter((g) => g.role);
    const blockIds = [...new Set(
        (mentions || []).filter((m) => m.perceptId === percept.id && m.blockId).map((m) => m.blockId),
    )];

    const sections = [
        { key: 'expression', voice: 'record', label: 'expression', value: percept.expression || '' },
        {
            key: 'grounds', voice: 'record', label: 'cited grounds',
            value: cited ? `${cited} ground${cited === 1 ? '' : 's'}` : 'cites no grounds',
            items: entries.map((g) => ({ id: g.ground_id, label: g.label, type: g.ground_type })),
        },
    ];

    // Roles show only when named. Nothing in the circuit may refuse a percept
    // for lacking them.
    if (roled.length) {
        sections.push({
            key: 'roles', voice: 'record', label: 'ground roles',
            value: roled.map((g) => roleLabel(g.role)).join(' · '),
            items: roled.map((g) => ({ id: g.ground_id, label: g.label, role: g.role })),
            // counterforce is kept, not resolved — it renders distinctly.
            hasCounterforce: roled.some((g) => g.role === 'counterforce'),
        });
    }

    // Degradation-only: nothing renders when the evidence is healthy.
    if (state !== 'intact') {
        sections.push({
            key: 'evidence', voice: 'judgement', label: 'evidence',
            value: evidenceNote(cited, resolving, resolve),
        });
    }

    sections.push({
        key: 'mentions', voice: 'record', label: 'in the writing',
        // Derived from the mentions. Never a "sent" flag — a flag would keep
        // claiming the crossing after the chip was deleted.
        value: blockIds.length
            ? `${blockIds.length} passage${blockIds.length === 1 ? '' : 's'}`
            : 'not yet in the writing',
    });

    if (recallCount > 0) {
        sections.push({
            key: 'recall', voice: 'record', label: 'recall',
            value: `recalled ${recallCount}× this session`,
        });
    }

    return {
        resolved: true,
        percept_id: percept.id,
        label: label || percept.expression || 'percept',
        sections,
        // Carried for the collapsed summary so it need not re-walk the sections.
        ground_count: cited,
        passage_count: blockIds.length,
        role_count: roled.length,
        // A degradation the collapsed line names calmly; `unknown` is not degraded,
        // it is uncomputed, and must not read as trouble.
        degraded: state !== 'intact' && state !== 'unknown',
        evidence: { state, note: evidenceNote(cited, resolving, resolve) },
    };
}

function evidenceNote(cited, resolving, resolve) {
    if (!resolve) return 'evidence state not computed';
    if (!cited) return 'cites no grounds';
    const lost = cited - resolving;
    if (!lost) return `cites ${cited} ground${cited === 1 ? '' : 's'}`;
    if (!resolving) return `none of the ${cited} cited ground${cited === 1 ? '' : 's'} still resolves`;
    return `${lost} of ${cited} cited grounds no longer resolve${lost === 1 ? 's' : ''}`;
}

/**
 * The acts the Manuscript can offer, classified by how far each can actually go
 * in THIS gate. The class is the honesty: a curator learns instantly which acts
 * do something and which are staged, and no act is dressed up beyond what it can
 * carry through.
 *
 *   live      a real, safe UI effect runs now — recall, return to Differential,
 *             begin a passage, carry a sentence back. Nothing mutates the corpus.
 *   disclose  a pure builder reveals something already true (packet, thread).
 *   staged    a valid Perceptual-Action-Grammar proposal is built and shown, and
 *             then STOPS. Nothing is dispatched, nothing is saved. "Ready, not sent."
 *   preview   an act whose grammar type does not exist yet. A structured proposal
 *             is shown — never loose text — and it plainly cannot execute.
 *
 * Copy is deliberately alive rather than administrative (P2C-MS2 §5). The panel
 * should read as a surface that can act, while never claiming to have acted.
 */

export const ACTION_KINDS = ['live', 'disclose', 'staged', 'preview'];

export const CHIP_ACTIONS = [
    { key: 'recall', label: 'Recall on the image', kind: 'live', tone: 'Play it back where its grounds live' },
    { key: 'revise', label: 'Revise in Differential', kind: 'live', tone: 'Return to where it was formed' },
    { key: 'start_passage', label: 'Start a passage', kind: 'live', tone: 'Write from here · nothing is saved until you save' },
    { key: 'packet', label: 'Show packet', kind: 'disclose', tone: 'The request as it would be asked — nothing sent' },
    { key: 'thread', label: 'Show circulation', kind: 'disclose', tone: 'Its record in the circuit' },
    { key: 'challenge_support', label: 'Challenge support', kind: 'staged', tone: 'Challenge is staged — no model has read it' },
    { key: 'compare', label: 'Compare', kind: 'preview', tone: 'Ready when a second noticing is chosen' },
];

export const SELECTION_ACTIONS = [
    { key: 'create_percept', label: 'Create percept from selection', kind: 'staged', tone: 'Ready, not sent' },
    { key: 'draft_description', label: 'Draft a description', kind: 'staged', tone: 'Staged draft · nothing is saved until you save' },
    { key: 'draft_critique', label: 'Draft a critique', kind: 'staged', tone: 'Staged draft · nothing is saved until you save' },
    { key: 'draft_script', label: 'Draft a script', kind: 'staged', tone: 'Staged draft · nothing is saved until you save' },
    { key: 'map_sentence', label: 'Map sentence to image', kind: 'preview', tone: 'Needs your mark on the image' },
    { key: 'challenge_sentence', label: 'Challenge sentence', kind: 'preview', tone: 'This sentence has not cited an image yet' },
    { key: 'mark_external', label: 'Mark external claim', kind: 'preview', tone: 'Staged — the frame may not settle this' },
    { key: 'send_first_attention', label: 'Send to Differential', kind: 'live', tone: 'Carry it into Differential' },
];

/** The acts on offer for the current selection. Descriptors only — the inspector
 *  binds `live`/`disclose` keys to callbacks and `staged`/`preview` to builders. */
export function actionsForSelection(selection) {
    const kind = selection?.kind || 'none';
    if (kind === 'percept_chip') return CHIP_ACTIONS.map((a) => ({ ...a }));
    if (kind === 'text') return SELECTION_ACTIONS.map((a) => ({ ...a }));
    return [];
}

// ── grammar-action builders ────────────────────────────────────────────────
// Each returns a fully-validated Perceptual-Action-Grammar action, or null if the
// selection cannot support it. `status: 'previewed'` — surfaced to the curator,
// never 'applied'. `source: 'user'` — the curator staged it, so a challenge is
// theirs to author (P2B refuses a model-authored challenge). Nothing is dispatched.

const DRAFT_MODES = { draft_description: 'description', draft_critique: 'art_critique', draft_script: 'youtube_script' };

/** Create-percept-from-selection → a real `compose_percept`, seeded with the
 *  curator's own sentence VERBATIM (P2B: never a paraphrase). */
export function composePerceptFromSelection(selection, { now = 0, idFn } = {}) {
    if (!selection?.text?.trim()) return null;
    return normalizeAction({
        type: 'compose_percept', source: 'user', status: 'previewed',
        payload: {
            draft_text: selection.text,
            ground_refs: selection.cited_ground_ids || [],
            intent: 'read',
        },
        provenance: { planner: 'manuscript/selection-v1', promptExcerpt: selection.text.slice(0, 80) },
    }, { now, idFn });
}

/** Draft-a-{description,critique,script} → a real `start_manuscript`, unsaved. */
export function draftFromSelection(actionKey, selection, { now = 0, idFn } = {}) {
    const mode = DRAFT_MODES[actionKey];
    if (!mode || !selection?.text?.trim()) return null;
    return normalizeAction({
        type: 'start_manuscript', source: 'user', status: 'previewed',
        payload: { mode, draft: selection.text, insertion_mode: 'unsaved' },
        provenance: { planner: 'manuscript/selection-v1' },
    }, { now, idFn });
}

/** Challenge-support on a percept chip → a real `challenge_percept`, authored by
 *  the curator. Staged only: no model reads it in this gate. */
export function challengeSupportAction(perceptId, { challengeType = 'alternative_reading', now = 0, idFn } = {}) {
    if (!perceptId) return null;
    return normalizeAction({
        type: 'challenge_percept', source: 'user', status: 'previewed',
        payload: { percept_ref: perceptId, challenge_type: challengeType },
        provenance: { planner: 'manuscript/chip-v1' },
    }, { now, idFn });
}

/** A structured proposal for an act whose grammar type does not exist yet. Not a
 *  validated grammar action, and it says so; but it is structure, not loose text,
 *  so a later gate can lift it into the grammar without reinterpreting prose. */
export function previewProposal(descriptor, selection) {
    const text = selection?.text || '';
    const bodies = {
        map_sentence: { target: 'image', sentence: text, needs_geometry: true },
        challenge_sentence: { target: 'percept', sentence: text, note: 'no percept cited on this sentence' },
        mark_external: { target: 'manuscript', sentence: text, claim_kind: 'external' },
        compare: { target: 'percept', note: 'choose a second noticing to compare against' },
    };
    return {
        proposal_kind: 'structured_preview',
        type: descriptor.key,
        label: descriptor.label,
        grammar: false,                 // not yet a Perceptual-Action-Grammar type
        payload: bodies[descriptor.key] || { sentence: text },
        note: descriptor.tone,
        // Stated on the proposal itself so it cannot be mistaken for a dispatch.
        dispatch: { sent: false },
        status: 'preview_only',
    };
}

/**
 * The compact line shown when the inspector is collapsed. Context-dependent, and
 * it never disappears — a collapsed inspector still says what is in hand.
 *
 *   percept chip   `Percept · 1 ground · 1 passage`  (+ calm degraded note)
 *   plain prose    `Selection · cites nothing`
 *   nothing        a quiet idle line
 */
export function collapsedSummary(selection, inspection = null) {
    const s = selection || describeSelection();
    if (s.kind === 'none') return 'Nothing selected · pick a sentence or a chip';
    if (s.kind === 'percept_chip') {
        if (inspection && !inspection.resolved) return 'Percept · citation no longer resolves';
        const g = inspection?.ground_count ?? 0;
        const p = inspection?.passage_count ?? 0;
        const bits = ['Percept', `${g} ground${g === 1 ? '' : 's'}`, `${p} passage${p === 1 ? '' : 's'}`];
        // Calm, not alarmist: the degraded note only, and only when truly degraded.
        if (inspection?.degraded) bits.push(inspection.evidence.note);
        return bits.join(' · ');
    }
    return s.citation_state === 'cites_percepts'
        ? `Selection · cites ${s.cited_percept_ids.length} percept${s.cited_percept_ids.length === 1 ? '' : 's'}`
        : s.citation_state === 'cites_nothing' ? 'Selection · cites nothing' : 'Selection';
}

/** The expanded header's one-line summary. Says what is selected, never how good. */
export function inspectorSummary(selection, inspection = null) {
    const s = selection || describeSelection();
    if (s.kind === 'none') return 'Nothing selected';
    if (s.kind === 'percept_chip') {
        if (inspection && !inspection.resolved) return 'A citation that no longer resolves';
        const ev = inspection?.evidence?.state;
        return ev && ev !== 'intact' && ev !== 'unknown' ? `Percept · evidence ${ev}` : 'Percept';
    }
    return s.citation_state === 'cites_percepts'
        ? `Selection · cites ${s.cited_percept_ids.length} percept${s.cited_percept_ids.length === 1 ? '' : 's'}`
        : s.citation_state === 'cites_nothing' ? 'Selection · cites nothing' : 'Selection';
}
