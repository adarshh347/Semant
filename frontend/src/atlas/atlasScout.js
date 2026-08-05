/**
 * ATLAS T2 — the pure half of the Scout: what a ghost edge is, and what it is not.
 *
 * THREE KINDS OF LINE NOW CROSS THIS CANVAS, and a reader has to tell them apart without reading
 * any labels, because a line between two photographs IS a claim in this system:
 *
 *   C3 relation — SOLID, ARROWED, coloured by epistemic kind.
 *                 A comparison was run and committed. The strongest line on the canvas.
 *   C4 binding  — dashed, unarrowed, muted, labelled with an argumentative function.
 *                 A claim would resolve against this image. About the argument, not the pictures.
 *   T2 ghost    — DOTTED, unarrowed, GREYED and translucent, labelled with a hunch and carrying
 *                 the word "unconfirmed". Nothing has been run. It is a question, not an answer.
 *
 * The ghost is the weakest mark that can appear here and it must look it. A candidate rendered in
 * the relation style would be a model's guess wearing the costume of a committed comparison — the
 * exact fabrication the Scout's whole design exists to prevent, arriving through the stylesheet.
 *
 * A GHOST IS SESSION MATERIAL. It has no id in any document, is never sent back to the server, and
 * disappears on reload. `GHOST_EDGE_PREFIX` is what makes that structurally checkable: an id that
 * cannot collide with a stored edge's, so a ghost can never be mistaken for one by any code that
 * handles both.
 *
 * CONFIRMING IS NOT A WRITE. Nothing in this module turns a candidate into an edge. Confirming
 * calls C3's `drawRelation` — the same function the drag gesture calls — and what comes back is
 * either a real relation or the gate's refusal. There is no third outcome and no shortcut.
 */

/** The prefix a candidate line carries, so it can never be mistaken for a stored edge. */
export const GHOST_EDGE_PREFIX = 'ghost:';

export const isGhostEdgeId = (id) => String(id ?? '').startsWith(GHOST_EDGE_PREFIX);

/** A stable id for one candidate pair. Unordered, because a candidate has no direction to assert. */
export function ghostId(candidate) {
    const a = String(candidate?.from ?? '');
    const b = String(candidate?.to ?? '');
    return `${GHOST_EDGE_PREFIX}${[a, b].sort().join('~')}`;
}

/**
 * How the Scout's own failure reads, in the header.
 *
 * "Nothing worth comparing" and "the scout could not be reached" are different facts and must not
 * be shown in the same words — a writer who reads a dead API as an empty corpus learns something
 * false about their own images.
 */
export function scoutRefusalLine(refused) {
    if (!refused) return '';
    const detail = refused.detail || 'refused';
    switch (refused.reason) {
        case 'too_few_images':
            return `Nothing to compare — ${detail}`;
        case 'model_unavailable':
            return `The scout could not be reached — ${detail}`;
        case 'nothing_proposed':
            return `The scout proposed nothing — ${detail}`;
        default:
            return `No candidates — ${detail}`;
    }
}

/**
 * What the Scout declined to pass on, as lines a person can read.
 *
 * Shown, not swallowed. How often a model invents an image or tries to name a relation is the
 * observable that tells a writer how much to trust the next batch of candidates; hiding it would
 * make the Scout look better than it is, which is the one direction this surface must never lean.
 */
export function droppedLines(drops) {
    return (drops || []).map((d) => {
        const pair = d.from && d.to ? `${d.from}→${d.to}` : 'a candidate';
        switch (d.reason) {
            case 'unknown_node':
                return `${pair}: named an image not on this Atlas — dropped.`;
            case 'named_a_relation':
                return `${pair}: tried to name the relation — dropped. Only the comparison may do that.`;
            case 'already_drawn':
                return `${pair}: a relation is already drawn here — dropped.`;
            case 'same_node':
                return `${pair}: an image is not related to itself — dropped.`;
            case 'no_rationale':
                return `${pair}: no reason given — dropped.`;
            case 'duplicate':
                return `${pair}: proposed twice — dropped.`;
            default:
                return `${pair}: ${d.detail || d.reason || 'dropped'}`;
        }
    });
}

/** The one-line state of what has been proposed, for the header. */
export function scoutSummary(candidates, drops) {
    return {
        proposed: (candidates || []).length,
        dropped: (drops || []).length,
    };
}

/**
 * Candidates → React Flow edges, in the ghost style.
 *
 * The label carries the rationale VERBATIM and prefixed with "unconfirmed". Verbatim because the
 * hunch is the only thing that lets a writer decide whether to spend a comparison on this pair,
 * and paraphrasing it here would put the surface's words in the model's mouth. Prefixed because a
 * sentence on a line between two photographs reads as a finding unless something says otherwise.
 */
export function ghostEdges(candidates) {
    return (candidates || [])
        .filter((c) => c?.from && c?.to)
        .map((c) => ({
            id: ghostId(c),
            source: String(c.from),
            target: String(c.to),
            type: 'default',
            className: 'atlas-ghost',
            label: `unconfirmed · ${c.rationale || 'no reason given'}`,
            // NO arrow. An arrow would say a direction was established; the Scout established
            // nothing, and `compare_views` is what records a left and a right.
            data: {
                kind: 'candidate',
                from: String(c.from),
                to: String(c.to),
                rationale: c.rationale || '',
                // Said in the data as well as the label, so any code branching on it reads the
                // same fact the curator does.
                confirmed: false,
            },
        }));
}

/** Drop one candidate — after it grounded, after it refused, or because the writer dismissed it. */
export function withoutCandidate(candidates, from, to) {
    const pair = [String(from), String(to)].sort().join('~');
    return (candidates || []).filter(
        (c) => [String(c.from), String(c.to)].sort().join('~') !== pair);
}

/**
 * The candidate a ghost edge stands for, from the edge's own id.
 *
 * Used when the confirm gesture arrives from React Flow, which knows only edge ids. Reading the
 * pair back off `data` rather than re-parsing the id keeps one source of truth for which two
 * images this line joins.
 */
export function candidateOfEdge(edge) {
    if (!edge || !isGhostEdgeId(edge.id)) return null;
    const from = edge.data?.from || edge.source;
    const to = edge.data?.to || edge.target;
    if (!from || !to) return null;
    return { from: String(from), to: String(to), rationale: edge.data?.rationale || '' };
}
