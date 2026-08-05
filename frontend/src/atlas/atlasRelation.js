/**
 * ATLAS C3 — the pure half of relation edges: what a drawn line is, and what it is not.
 *
 * A RELATION IS NOT A BINDING, and this module exists partly to keep that true on screen. C4 draws
 * claim→image connectors that assert a percept WOULD resolve; they are dashed, muted, labelled
 * with an argumentative function, and they live in `plan`. C3 draws image↔image edges that assert
 * a comparison WAS produced and committed; they are solid, arrowed, labelled with the relation's
 * own role and epistemic kind, and they live in `edges`. Two vocabularies, and nothing here ever
 * uses the other one's word.
 *
 * THE REFUSED EDGE IS NOT AN EDGE. When `compare_views` cannot ground a comparison, the surface
 * draws the line the writer attempted — in the refusal's own colour, carrying the gate's sentence
 * as its label — and persists nothing. It is deliberately given an id that cannot collide with a
 * real edge's, is never sent anywhere, and disappears on the next gesture. Rendering nothing at
 * all would leave a writer believing the drag missed; rendering it as an ordinary edge would be
 * far worse, because a line between two images IS a claim in this system.
 *
 * A STALE EDGE STILL RENDERS. If the relation it names has left the ledger, the edge stays on the
 * canvas and says so. "Never drawn" and "drawn, then uncommitted" are different facts about the
 * corpus, and the second is the one a writer needs to know about.
 */

/** What a C3 edge IS. Never the word `binding`, which is C4's. */
export const EDGE_RELATION = 'relation';

/** The prefix a refused, unpersisted line carries, so it can never be mistaken for a stored edge. */
export const REFUSED_EDGE_PREFIX = 'refused:';

export const isRefusedEdgeId = (id) => String(id ?? '').startsWith(REFUSED_EDGE_PREFIX);

/** A relation's epistemic kinds, in M5's vocabulary. Read from the mark, never decided here. */
export const EPISTEMIC_LABEL = {
    visible: 'visible',
    measured: 'measured',
    sourced: 'sourced',
    interpretive: 'interpretive',
    uncertain: 'uncertain',
};

export const epistemicLabel = (kind) => EPISTEMIC_LABEL[kind] || 'uncertain';

/**
 * How a refusal reads on the line that was attempted.
 *
 * The gate's own `detail` is always shown — it is the authority on why it refused, and it already
 * reads as a sentence. The prefix names which KIND of refusal it was, because "these images share
 * no evidence" and "this Atlas has no such node" call for different next moves from the writer.
 */
export function refusalLine(refused) {
    if (!refused) return '';
    const detail = refused.detail || 'refused';
    switch (refused.reason) {
        case 'same_node':
            return `Not a relation — ${detail}`;
        case 'unknown_node':
            return `Stale canvas — ${detail}`;
        case 'unreadable_image':
            return `Could not read an image — ${detail}`;
        case 'gate_refused':
            return `No relation drawn — ${detail}`;
        case 'produced_nothing':
            return `No relation drawn — ${detail}`;
        default:
            return `No relation drawn — ${detail}`;
    }
}

/** What one stored, hydrated edge says on the canvas. Counts and words, never an adjective. */
export function relationLabel(edge) {
    if (!edge) return '';
    if (edge.live === false) return 'relation no longer in the ledger';
    const role = (edge.role || '').replace(/_/g, ' ');
    const bits = [role || 'relation'];
    if (edge.epistemic) bits.push(epistemicLabel(edge.epistemic));
    return bits.join(' · ');
}

/**
 * The hydrated view's edges → React Flow edges.
 *
 * SOLID, ARROWED, AND CARRYING THEIR EPISTEMIC KIND — the three things that separate them at a
 * glance from C4's dashed, unarrowed, function-labelled bindings. The arrow matters beyond
 * decoration: `compare_views` records a left and a right, and "the façade prepares the rotunda"
 * is not its own converse.
 */
export function relationEdges(view) {
    return (view?.edges || []).map((e) => ({
        id: String(e.edge_id),
        source: String(e.source_node),
        target: String(e.target_node),
        type: 'default',
        className: `atlas-relation is-${e.epistemic || 'uncertain'}`
            + (e.live === false ? ' is-stale' : ''),
        label: relationLabel(e),
        markerEnd: { type: 'arrowclosed' },
        data: {
            kind: EDGE_RELATION,
            markId: e.mark_id,
            spans: e.spans || [],
            role: e.role || '',
            epistemic: e.epistemic || '',
            live: e.live !== false,
            missingReason: e.missing_reason || '',
            // Both sides, which is what makes a cross-image claim checkable at all.
            sources: e.sources || [],
        },
    }));
}

/**
 * The line a writer attempted, when the comparison refused. Never persisted, never sent.
 *
 * Kept as a first-class render input rather than a toast: a refusal about THIS pair belongs on the
 * line between THIS pair, where the writer is already looking, and a message in a corner would be
 * read as being about the canvas rather than about two particular photographs.
 */
export function refusedEdge(refused) {
    if (!refused?.source_node || !refused?.target_node) return null;
    return {
        id: `${REFUSED_EDGE_PREFIX}${refused.source_node}~${refused.target_node}`,
        source: String(refused.source_node),
        target: String(refused.target_node),
        type: 'default',
        className: 'atlas-relation is-refused',
        label: refusalLine(refused),
        // No arrow. An arrow would say a direction was established, and nothing was.
        data: { kind: 'refusal', reason: refused.reason, detail: refused.detail },
    };
}

/**
 * Is this drag worth sending at all?
 *
 * The two checks the client can make honestly on its own: a line needs two ends, and an image
 * cannot relate to itself. Everything else — whether the marks exist, whether a relation can be
 * named — is the gate's to answer, and guessing at it here would mean a canvas that refuses
 * comparisons the system would actually have allowed.
 */
export function connectionRefusal(connection, { isClaimNode = () => false } = {}) {
    const source = connection?.source;
    const target = connection?.target;
    if (!source || !target) return null;
    if (source === target) {
        return {
            reason: 'same_node', source_node: source, target_node: target,
            detail: 'a relation needs two different images; this line starts and ends on one',
        };
    }
    if (isClaimNode(source) || isClaimNode(target)) {
        // C4's cards are not evidence. A line from a claim to an image is a BINDING, and bindings
        // are minted by the planner, never dragged into existence.
        return {
            reason: 'not_an_image', source_node: source, target_node: target,
            detail: 'a relation runs between two images; a claim card is not evidence to compare',
        };
    }
    return null;
}

/** The one-line state of what has been drawn, for the header. */
export function relationSummary(view) {
    const edges = view?.edges || [];
    const stale = edges.filter((e) => e.live === false).length;
    return { drawn: edges.length, stale };
}
