/**
 * Circulation Thread — what happened to a Percept, in the order it happened.
 *
 * CIRCUIT-001 P1A, seed version. Pure derivation over state the client already
 * holds: no fetch, no persistence, no new entity. Mirrors the contract
 * `visionActivity.js` sets for the Rail, including its causal-language rule.
 *
 * THE ONE RULE: this reports SEQUENCE, never CAUSATION. A link says that a
 * relation obtains — formed, cites, mentioned, recalled, recorded — and never
 * why. `DifferentialWorkspace` currently tells a reader a ground's "part was
 * replaced by a re-dissect" when `resolveGround` only knows the region_id no
 * longer resolves; that is the error this module exists not to repeat.
 *
 * The second rule: an absent link says `unavailable` — "not recorded" — never
 * "none". "None" is a claim about the world; "not recorded" is a claim about
 * the record, and only the second is one we can support.
 */

import { resolveGround } from './grounds';
import { blockIdsForPercept } from '../state/perceptMentions';

/** The relation vocabulary. Records describe what happened; judgements are ours. */
export const RELATION = {
    FORMED: 'formed',
    CITES: 'cites',
    MENTIONED: 'mentioned',
    RECALLED: 'recalled',
    RECORDED: 'recorded',
    UNAVAILABLE: 'unavailable',
};

/** A link is `state: 'nominal' | 'degraded' | 'absent'`. Only the first two are facts
 *  about the percept; `absent` is a fact about our record of it. */
const link = (relation, state, text, extra = {}) => ({ relation, state, text, ...extra });

/**
 * @param percept   an expression percept (`pctx_…`)
 * @param ctx.grounds/regions  for resolution, same shape `resolveGround` wants
 * @param ctx.mentions         reconstructed mentions (see perceptMentions)
 * @param ctx.visionRuns       vision_runs for this post, or null when unknown
 * @param ctx.recallCount      recalls observed THIS SESSION (not persisted)
 */
export function buildCirculationThread(percept, {
    grounds = [], regions = [], mentions = [], visionRuns = null, recallCount = 0,
} = {}) {
    if (!percept) return [];
    const out = [];

    // formed — the only link that is true by the percept's existence.
    out.push(link(RELATION.FORMED, 'nominal', 'formed'));

    // cites — how much of the evidence still resolves. Degradation-only: a
    // wholly intact citation says its count and nothing more.
    const cited = percept.ground_ids || [];
    const resolving = cited.filter((id) => {
        const g = grounds.find((x) => x.id === id);
        return g ? !resolveGround(g, { regions, grounds })?.detached : false;
    });
    const lost = cited.length - resolving.length;
    out.push(link(
        RELATION.CITES,
        lost === 0 ? 'nominal' : (resolving.length === 0 ? 'degraded' : 'degraded'),
        lost === 0
            ? `cites ${cited.length} ground${cited.length === 1 ? '' : 's'}`
            // States what no longer resolves. Never why, and never "was deleted".
            : `cites ${cited.length} ground${cited.length === 1 ? '' : 's'} · ${lost} no longer resolve${lost === 1 ? 's' : ''}`,
        { cited: cited.length, resolving: resolving.length },
    ));

    // mentioned — whether the writing carries it. Depends on Part B: before
    // lossless reconstruction a percept chip came back as an anonymous region
    // edge and this link could never be true.
    const blocks = blockIdsForPercept(mentions, percept.id);
    out.push(blocks.size
        ? link(RELATION.MENTIONED, 'nominal', `mentioned in ${blocks.size} passage${blocks.size === 1 ? '' : 's'}`, { blocks: [...blocks] })
        : link(RELATION.MENTIONED, 'absent', 'not yet in the writing'));

    // recalled — session-local by construction. Not persisted, and the text says
    // so rather than implying a history we do not keep.
    out.push(recallCount > 0
        ? link(RELATION.RECALLED, 'nominal', `recalled ${recallCount}× this session`)
        : link(RELATION.RECALLED, 'absent', 'not recalled yet'));

    // recorded — a model reading. NO entity carries a run_id (CIRCUIT-001 P0
    // §5), so a run cannot be tied to THIS percept. Saying "not recorded" is the
    // honest limit of the record; inventing the link would be the exact failure
    // this module exists to avoid. The blank is the argument for run_id.
    out.push(visionRuns && visionRuns.length
        ? link(RELATION.RECORDED, 'nominal', `${visionRuns.length} model run${visionRuns.length === 1 ? '' : 's'} on this image`, { scope: 'post' })
        : link(RELATION.UNAVAILABLE, 'absent', 'no model reading recorded'));

    return out;
}

/** One-line summary for a collapsed row. Degradation-first: mentions what is
 *  wrong if anything is, otherwise stays quiet about health. */
export function threadSummary(thread) {
    if (!thread?.length) return '';
    const degraded = thread.find((l) => l.state === 'degraded');
    if (degraded) return degraded.text;
    const mentioned = thread.find((l) => l.relation === RELATION.MENTIONED);
    return mentioned?.state === 'nominal' ? mentioned.text : (thread[1]?.text || 'formed');
}
