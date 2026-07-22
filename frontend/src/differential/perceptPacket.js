/**
 * Percept Packet — a percept made into an inspectable operation request.
 *
 * CIRCUIT-001 P1C. **Pure builder. Nothing here sends anything to any model.**
 * No fetch, no route, no persistence, no `run_id`.
 *
 * This is Perceptive Orchestration's first artifact, and it is deliberately the
 * boring half: the PACKING RULE, built and inspectable long before anything is
 * dispatched. The rehearsal programme spent eleven runs learning that the value
 * is not in the call but in freezing what was asked, on what evidence, under
 * what constraints, BEFORE the call — and in being able to refuse an invalid
 * request without spending anything. That discipline was called a *manifest*
 * there. This is the same object, minus the research apparatus.
 *
 * Why it must exist before any sending:
 *   - Today nothing that reaches a VLM knows it is about a percept, and nothing
 *     coming back knows what it was asked about (CIRCUIT-001 P0 §4-5).
 *   - A packet carries its own EVIDENCE STATE, so a question resting on grounds
 *     that no longer resolve is visible as such *before* it is asked, rather
 *     than producing a confident answer about nothing.
 *   - It carries CONSTRAINTS as data, so the discipline travels with the request
 *     instead of living in a prompt someone may later edit.
 *
 * The packet asserts nothing about the world. It records what is being asked and
 * what it rests on.
 */

import { groundRoleList, rolesOf } from './groundRoles';

/**
 * What the curator wants done. Placeholders — nothing dispatches them yet, and
 * naming them here is not scheduling them.
 */
export const INTENTS = [
    { key: 'read', label: 'read', hint: 'interpret what is cited' },
    { key: 'challenge', label: 'challenge', hint: 'argue against the percept from the image' },
    { key: 'compare', label: 'compare', hint: 'hold it against another noticing' },
    { key: 'revise', label: 'revise', hint: 'propose a narrower or truer wording' },
    { key: 'transfer', label: 'transfer', hint: 'ask whether it reaches beyond this image' },
];
export const INTENT_KEYS = INTENTS.map((i) => i.key);

/**
 * Constraints that travel WITH the request. Defaults are conservative on
 * purpose: every one of these is a lesson the rehearsals paid for.
 */
export const DEFAULT_CONSTRAINTS = {
    // The frame is the evidence. R2 runs repeatedly saw outside-frame material
    // presented as read off the image.
    image_only: true,
    // spark-08: the model names what it is asked to name AND what it recognises.
    // Recording is not forbidding — the claim may be made, and must be marked.
    mark_external_claims: true,
    // spark-10, and the sharpest one. A supplied premise came back restated at an
    // altitude its own counter-evidence could not reach. Demanding contradictions
    // is not sufficient to prevent that — arm E supplied three real ones that bore
    // on nothing — but omitting the demand guarantees it.
    ask_for_contradictions: true,
    // A6's territory: identity claims are the ones the frame least often settles.
    no_identity_claims: true,
};

const evidenceLine = (cited, resolving) => {
    if (!cited) return 'cites no grounds';
    const lost = cited - resolving;
    if (!lost) return `cites ${cited} ground${cited === 1 ? '' : 's'}`;
    if (!resolving) return `none of the ${cited} cited ground${cited === 1 ? '' : 's'} still resolves`;
    return `${lost} of ${cited} cited grounds no longer resolve${lost === 1 ? 's' : ''}`;
};

/**
 * Build the packet.
 *
 * @param percept              an expression percept (`pctx_…`)
 * @param ctx.postId           the image this rests on
 * @param ctx.grounds          the post's grounds
 * @param ctx.resolve          `(ground) => ({ detached })` — injected, usually resolveGround bound to regions
 * @param ctx.mentions         reconstructed mentions (percept → block edges)
 * @param ctx.blocks           text blocks, for cheap nearby context. Optional.
 * @param ctx.intent           one of INTENT_KEYS. Optional; defaults to 'read'.
 * @param ctx.constraints      partial override of DEFAULT_CONSTRAINTS.
 * @returns a plain, JSON-serialisable object, or null if there is no percept.
 */
export function buildPerceptPacket(percept, {
    postId = null, grounds = [], resolve = null, mentions = [], blocks = [],
    intent = 'read', constraints = {},
} = {}) {
    if (!percept?.id) return null;

    const groundEntries = groundRoleList(percept, grounds, resolve);
    const cited = groundEntries.length;
    // Without a resolver we cannot claim anything about evidence state, so we
    // say so rather than assuming health. Absent is not nominal.
    const known = resolve ? groundEntries.filter((g) => g.detached !== undefined) : [];
    const resolving = known.filter((g) => !g.detached).length;

    const citingBlocks = (mentions || [])
        .filter((m) => m.perceptId === percept.id && m.blockId)
        .map((m) => m.blockId);
    const uniqueBlocks = [...new Set(citingBlocks)];

    return {
        packet_version: 1,
        // What is being asked, and of what.
        intent: INTENT_KEYS.includes(intent) ? intent : 'read',
        percept: {
            id: percept.id,
            expression: percept.expression || '',
            properties: [...(percept.properties || [])],
            actor: percept.actor || null,
            has_roles: Object.keys(rolesOf(percept)).length > 0,
        },
        source: { post_id: postId },

        // The evidence, WITH what each piece does for this reading. Roles and
        // resolution meet here and nowhere else.
        grounds: groundEntries,

        // Stated so a reader — or a later orchestrator — can see the standing of
        // the evidence before reading the answer.
        evidence: {
            cited,
            resolving: resolve ? resolving : null,
            detached: resolve ? cited - resolving : null,
            // `null` means UNKNOWN, never healthy.
            state: !resolve ? 'unknown' : (cited === 0 ? 'ungrounded' : (resolving === 0 ? 'detached' : (resolving < cited ? 'partial' : 'intact'))),
            note: resolve ? evidenceLine(cited, resolving) : 'evidence state not computed',
        },

        // Where the noticing has been committed to in the writing. A percept
        // carried into prose is a stronger claim than one still in the workspace.
        manuscript: {
            cited_in_blocks: uniqueBlocks,
            mention_count: citingBlocks.length,
            // Cheap context only: the text of the blocks that cite it, nothing
            // fetched and no neighbourhood walked.
            context: (blocks || [])
                .filter((b) => uniqueBlocks.includes(b.id))
                .map((b) => ({ block_id: b.id, origin: b.origin || 'human', content: b.content || '' })),
        },

        constraints: { ...DEFAULT_CONSTRAINTS, ...constraints },

        // Said in the packet itself so it cannot be mistaken for a dispatch record.
        dispatch: { sent: false, run_id: null, note: 'built for inspection; nothing is sent in P1C' },
    };
}

/** A compact human summary for a quiet disclosure. Degradation-aware, not alarmist. */
export function packetSummary(packet) {
    if (!packet) return '';
    const roles = packet.grounds.filter((g) => g.role).length;
    const bits = [
        packet.intent,
        packet.evidence.note,
        roles ? `${roles} role${roles === 1 ? '' : 's'} named` : 'no roles named',
        packet.manuscript.mention_count ? 'in the writing' : 'not yet in the writing',
    ];
    return bits.join(' · ');
}
