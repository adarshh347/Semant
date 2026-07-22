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
 * The acts a selection can offer.
 *
 * Every one is PREVIEW ONLY in this gate. `wired: false` is carried on each so a
 * surface renders "Preview only — execution path not wired yet" and NO button:
 * an Apply that quietly does nothing teaches the curator that the whole panel is
 * theatre (P2B).
 *
 * `newType: true` marks the seven types not yet in perceptualActions.ACTION_TYPES.
 * `normalizeAction` returns null for an unknown type — the correct failure — so
 * none of these may render an Apply until its spec exists.
 */
export const MANUSCRIPT_ACTIONS = [
    { type: 'create_percept_from_sentence', label: 'Create percept from this sentence', on: 'text', newType: true },
    { type: 'map_sentence_to_image', label: 'Map this sentence to the image', on: 'text', newType: true },
    { type: 'challenge_sentence', label: 'Challenge this sentence', on: 'text', newType: true },
    { type: 'send_sentence_to_differential', label: 'Send to Differential', on: 'text', newType: true },
    { type: 'draft_description', label: 'Draft from selection', on: 'text', newType: false },
    { type: 'recall_percept', label: 'Recall on the image', on: 'percept_chip', newType: false },
    { type: 'revise_cited_percept', label: 'Revise in Differential', on: 'percept_chip', newType: true },
    { type: 'challenge_percept', label: 'Challenge support', on: 'percept_chip', newType: false },
    { type: 'start_manuscript', label: 'Start a passage', on: 'percept_chip', newType: false },
    { type: 'compare_passage', label: 'Compare', on: 'percept_chip', newType: true },
];

export function actionsForSelection(selection) {
    const kind = selection?.kind || 'none';
    if (kind === 'none') return [];
    return MANUSCRIPT_ACTIONS
        .filter((a) => a.on === kind)
        .map((a) => ({
            ...a,
            // Nothing in this gate has an executor. Stated per-action rather
            // than assumed, so wiring one is a visible change.
            wired: false,
            note: 'Preview only — execution path not wired yet',
        }));
}

/** One quiet line for the resting state. Says what is selected, never how good it is. */
export function inspectorSummary(selection, inspection = null) {
    const s = selection || describeSelection();
    if (s.kind === 'none') return 'Nothing selected';
    if (s.kind === 'percept_chip') {
        if (inspection && !inspection.resolved) return 'A citation that no longer resolves';
        const ev = inspection?.evidence?.state;
        return ev && ev !== 'intact' ? `Percept · evidence ${ev}` : 'Percept';
    }
    return s.citation_state === 'cites_percepts'
        ? `Selection · cites ${s.cited_percept_ids.length} percept${s.cited_percept_ids.length === 1 ? '' : 's'}`
        : s.citation_state === 'cites_nothing' ? 'Selection · cites nothing' : 'Selection';
}
