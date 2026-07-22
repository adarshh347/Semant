/**
 * Circulation Thread — what happened to a Percept, in two voices.
 *
 * CIRCUIT-001, seeded in P1A, made rich in P1D. Pure derivation over state the
 * client already holds: no fetch, no persistence, no new entity. Mirrors the
 * contract `visionActivity.js` sets for the Rail, including its causal-language
 * rule.
 *
 * ── THE TWO RULES ───────────────────────────────────────────────────────────
 *
 * 1. IT REPORTS RELATIONS, NEVER CAUSATION. A row says that a relation obtains —
 *    formed, cites, mentioned, recalled, prepared — and never why, and never
 *    that one thing produced another. A percept did not *cause* a sentence; a
 *    model run did not *cause* a percept. This is not a timeline.
 *
 * 2. RECORDS AND JUDGEMENTS ARE DIFFERENT VOICES.
 *      A RECORD    is something the system observed and can point at.
 *      A JUDGEMENT is something the system concluded, and owns as its own.
 *    Conflating them is how a surface starts presenting an inference in the same
 *    register as an observation. `DifferentialWorkspace` once told a reader a
 *    ground's "part was replaced by a re-dissect" when `resolveGround` knew only
 *    that an id did not resolve — that is the failure this separation prevents.
 *
 * Corollary held throughout: an absent link says `not recorded` / `not assessed`
 * — a claim about OUR RECORD — never `none`, which would be a claim about the
 * world.
 */

import { resolveGround } from './grounds';
import { blockIdsForPercept } from '../state/perceptMentions';
import { rolesOf, roleLabel } from './groundRoles';

/** Whose voice a row is in. */
export const VOICE = { RECORD: 'record', JUDGEMENT: 'judgement' };

export const RELATION = {
    // Records — observed, pointable.
    FORMED: 'formed',
    CITES: 'cites',
    MENTIONED: 'mentioned',
    RECALLED: 'recalled',
    PACKET: 'packet',
    MODEL_READING: 'model-reading',
    // Judgements — concluded, ours.
    MISSING: 'missing',
    DEGRADED: 'degraded',
    EXTERNAL: 'external',
    SUSPECT: 'suspect',
};

/**
 * `state` is about the ROW, not about the percept's worth:
 *   nominal    — the relation obtains and nothing is wrong
 *   degraded   — the relation obtains, diminished
 *   absent     — it does not obtain, and we can say so
 *   unassessed — we have not looked, and will not pretend otherwise
 */
const row = (voice, relation, state, text, extra = {}) => ({ voice, relation, state, text, ...extra });
const record = (relation, state, text, extra) => row(VOICE.RECORD, relation, state, text, extra);
const judge = (relation, state, text, extra) => row(VOICE.JUDGEMENT, relation, state, text, extra);

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

/**
 * @param percept   an expression percept (`pctx_…`)
 * @param ctx.grounds/regions  for resolution, the shape `resolveGround` wants
 * @param ctx.mentions         reconstructed mentions (see perceptMentions)
 * @param ctx.visionRuns       vision_runs for this post, or null when unknown
 * @param ctx.recallCount      recalls observed THIS SESSION (not persisted)
 * @param ctx.packet           a built Percept Packet, or null
 * @returns rows, records first, in the order a reader would ask them
 */
export function buildCirculationThread(percept, {
    grounds = [], regions = [], mentions = [], visionRuns = null, recallCount = 0, packet = null,
} = {}) {
    if (!percept) return [];
    const records = [];
    const judgements = [];

    // ── Records ─────────────────────────────────────────────────────────────

    records.push(record(RELATION.FORMED, 'nominal', 'formed in Differential'));

    const cited = percept.ground_ids || [];
    const roles = rolesOf(percept);
    const namedRoles = [];
    for (const gid of cited) {
        const r = roles[gid];
        if (r && !namedRoles.includes(r)) namedRoles.push(r);
    }
    // The count is the record. What is WRONG with the evidence is a judgement and
    // lives below — so a healthy citation reads as a plain fact, with no warning
    // attached to it.
    records.push(record(
        RELATION.CITES,
        cited.length ? 'nominal' : 'absent',
        cited.length
            ? `cites ${plural(cited.length, 'ground', 'grounds')}${namedRoles.length ? `: ${namedRoles.map(roleLabel).join(', ')}` : ''}`
            : 'cites no grounds',
        { cited: cited.length, roles: namedRoles },
    ));

    const blocks = blockIdsForPercept(mentions, percept.id);
    const mentionCount = (mentions || []).filter((m) => m.perceptId === percept.id).length;
    records.push(blocks.size
        ? record(RELATION.MENTIONED, 'nominal', `mentioned in ${plural(blocks.size, 'passage', 'passages')}`, { blocks: [...blocks] })
        : mentionCount
            // In the writing, but the passage is not knowable — a chip inserted
            // into an empty document has no block id to be inserted against.
            ? record(RELATION.MENTIONED, 'nominal', 'mentioned in the writing', { blocks: [] })
            : record(RELATION.MENTIONED, 'absent', 'not yet in the writing', { blocks: [] }));

    records.push(recallCount > 0
        // Session-local by construction, and the text says so rather than
        // implying a history we do not keep.
        ? record(RELATION.RECALLED, 'nominal', `recalled ${recallCount}× this session`)
        : record(RELATION.RECALLED, 'absent', 'not recalled yet'));

    if (packet) {
        records.push(record(
            RELATION.PACKET, 'nominal',
            `packet prepared, not sent · intent ${packet.intent}`,
            { intent: packet.intent, sent: !!packet.dispatch?.sent, constraints: packet.constraints },
        ));
    }

    // A fact about OUR LEDGER, not about the percept — which is why it is a
    // record rather than a judgement. No entity carries a run_id (CIRCUIT-001 P0
    // §5), so a run cannot be tied to THIS percept even when runs exist; the
    // scope is declared rather than implied. This blank is the argument for
    // run_id, and it makes it better than a document can.
    records.push(visionRuns && visionRuns.length
        ? record(RELATION.MODEL_READING, 'nominal', `${plural(visionRuns.length, 'model run', 'model runs')} on this image`, { scope: 'post' })
        : record(RELATION.MODEL_READING, 'absent', 'no model reading recorded'));

    // ── Judgements ──────────────────────────────────────────────────────────
    // Degradation-only: a percept whose evidence is intact gets NO judgement
    // about its evidence. Silence is the healthy state.

    const resolveOne = (gid) => {
        const g = (grounds || []).find((x) => x.id === gid);
        if (!g) return { present: false, detached: true };
        return { present: true, detached: !!resolveGround(g, { regions, grounds })?.detached };
    };
    const states = cited.map(resolveOne);
    const lost = states.filter((s) => s.detached).length;

    if (lost) {
        judgements.push(lost === cited.length
            ? judge(RELATION.MISSING, 'degraded',
                `none of the ${plural(cited.length, 'cited ground', 'cited grounds')} still resolves`,
                { lost, cited: cited.length })
            : judge(RELATION.DEGRADED, 'degraded',
                `${lost} of ${cited.length} cited grounds no longer resolve${lost === 1 ? 's' : ''}`,
                { lost, cited: cited.length }));
    }

    // Two things we have NOT looked at. Stated so a reader does not mistake
    // silence for a clean bill: "not assessed" is a fact about our effort.
    judgements.push(judge(RELATION.EXTERNAL, 'unassessed', 'external claims not assessed'));
    judgements.push(judge(RELATION.SUSPECT, 'unassessed', 'substitution not assessed'));

    return [...records, ...judgements];
}

/**
 * The resting line. Degradation-first, and quiet when all is well: it names what
 * is wrong if anything is, and otherwise reports only the plain relations.
 */
export function threadSummary(thread) {
    if (!thread?.length) return '';
    const get = (r) => thread.find((l) => l.relation === r);
    const degraded = thread.find((l) => l.voice === VOICE.JUDGEMENT && l.state === 'degraded');

    const bits = ['formed'];
    const cites = get(RELATION.CITES);
    if (cites) bits.push(cites.text);
    if (degraded) {
        bits.push(degraded.text);
    } else {
        const mentioned = get(RELATION.MENTIONED);
        if (mentioned?.state === 'nominal') bits.push(mentioned.text);
    }
    return bits.join(' · ');
}

/** Rows in one voice — the UI groups by this rather than re-deriving. */
export const recordsOf = (thread) => (thread || []).filter((l) => l.voice === VOICE.RECORD);
export const judgementsOf = (thread) => (thread || []).filter((l) => l.voice === VOICE.JUDGEMENT);
