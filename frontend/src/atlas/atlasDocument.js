/**
 * ATLAS C1 — the pure half of the canvas: view ⇄ React Flow, and what a save owes the server.
 *
 * Everything here is a function of its arguments. The canvas component does the mounting, the
 * dragging and the debouncing; this module decides what a node IS, what changed, and what is
 * worth sending. Keeping that split means the interesting decisions are testable without a DOM,
 * and the component stays small enough to read.
 *
 * THE RULE THIS MODULE ENFORCES: a save carries POSITION ONLY. `arrangementFrom` builds patches of
 * `{node_id, x, y}` and nothing else — never the post id, never the overlays. The backend refuses
 * a repointed node anyway (`merge_nodes`), and this is the same refusal stated on the near side,
 * because a client that tried would mean the drag gesture had started relabelling evidence.
 *
 * PROXIMITY IS NOT A RELATION. Nothing here reads distance between nodes, sorts by position, or
 * derives anything at all from where a node sits. Position is a writer's thinking aid; only a
 * drawn edge (C3, a real `compare_views` percept) asserts a relation.
 */

export const ATLAS_NODE_TYPE = 'atlasImage';

// How far a node must move before the change is worth a round trip. Sub-pixel jitter from a
// pointer that barely moved is not an arrangement anyone chose.
export const MOVE_EPSILON = 0.5;

/**
 * A finite number, or null. Mirrors the backend's `_finite` — a NaN position is not a position.
 *
 * `null`, `undefined` and `''` are rejected before `Number()` sees them, because JavaScript coerces
 * all three to 0 and the backend (where `float(None)` raises) does not. A missing coordinate that
 * silently became the origin would move a node to the top-left corner and call it the curator's
 * arrangement — and the two ends of the same contract would disagree about it.
 */
export function finite(value) {
    if (value === null || value === undefined || value === '') return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
}

/**
 * The hydrated view → React Flow's node array.
 *
 * `data` carries what the custom node draws: the image and the ledger's CURRENT answer for it.
 * That payload is rebuilt from the server on every load and never persisted back — it is a
 * render input, not document state.
 */
export function flowNodesFromView(view) {
    const nodes = view?.nodes || [];
    return nodes.map((n) => ({
        id: String(n.node_id),
        type: ATLAS_NODE_TYPE,
        position: { x: finite(n.x) ?? 0, y: finite(n.y) ?? 0 },
        // The box, told to React Flow rather than left to be measured. The document already knows
        // it, and C4's connectors need an endpoint the moment a plan arrives — an edge whose
        // source has not been measured is simply not drawn, so a binding would appear a frame
        // late, or in a surface that never measures, not at all.
        width: finite(n.w) ?? 420,
        height: finite(n.h) ?? 320,
        // Nobody wires a node by hand: a binding is granted by the gate (C4), a relation is a
        // produced percept (C3). Neither is a line anyone gets to assert with a drag.
        connectable: false,
        data: {
            nodeId: String(n.node_id),
            postId: String(n.post_id || ''),
            title: n.title || '',
            imageRef: n.image_ref || '',
            readable: n.readable !== false,
            unreadableReason: n.unreadable_reason || '',
            grounds: n.grounds || [],
            regions: n.regions || [],
            marks: n.marks || [],
            percepts: n.percepts || [],
            withheld: Number(n.withheld || 0),
            w: finite(n.w) ?? 420,
            h: finite(n.h) ?? 320,
        },
    }));
}

/** node_id → {x, y}, for comparing an arrangement against the one the server last confirmed. */
export function positionsOf(nodes) {
    const out = {};
    (nodes || []).forEach((n) => {
        const x = finite(n?.position?.x);
        const y = finite(n?.position?.y);
        if (n?.id && x !== null && y !== null) out[String(n.id)] = { x, y };
    });
    return out;
}

/**
 * The patches a save should carry: the nodes that actually moved, position only.
 *
 * A node whose position the server already holds is omitted rather than re-sent. Sending the whole
 * canvas on every drag would work and would also mean the request said nothing about what the
 * curator did — and on a sixty-image Atlas it is sixty times the payload for one moved picture.
 */
export function arrangementFrom(nodes, saved = {}) {
    const now = positionsOf(nodes);
    const out = [];
    Object.entries(now).forEach(([nodeId, pos]) => {
        const before = saved[nodeId];
        if (before
            && Math.abs(before.x - pos.x) < MOVE_EPSILON
            && Math.abs(before.y - pos.y) < MOVE_EPSILON) return;
        out.push({ node_id: nodeId, x: pos.x, y: pos.y });
    });
    return out;
}

/**
 * What one node's overlays amount to, for the node's own caption.
 *
 * Counted, not summarised: "4 percepts" is a fact the curator can check against what is drawn.
 * `withheld` is reported separately and never folded into the total — a quarantined suggestion is
 * not a percept this canvas is showing, and a count that included it would say the ledger holds
 * more than it does.
 */
export function perceptSummary(data) {
    const drawn = (data?.grounds?.length || 0) + (data?.marks?.length || 0)
        + (data?.regions?.length || 0);
    return {
        drawn,
        withheld: Number(data?.withheld || 0),
        // A separate line, in the node, when there is one. Never a tooltip: a suggestion the
        // canvas declined to draw is exactly the kind of thing a hover hides.
        withheldNote: data?.withheld
            ? `${data.withheld} suggestion${data.withheld === 1 ? '' : 's'} not shown — review in the Differential`
            : '',
    };
}

/**
 * The refusals a save came back with, as lines a person can read.
 *
 * Refusal is a return value and it must RENDER. A save that silently dropped a stale node would
 * leave the curator believing the canvas holds something it does not.
 */
export function refusalLines(refused) {
    return (refused || []).map((r) => {
        const what = r?.node_id ? `node ${r.node_id}` : 'a node';
        if (r?.reason === 'unknown_node') return `${what} is no longer on this Atlas — not moved.`;
        if (r?.reason === 'bad_position') return `${what} was sent an impossible position — not moved.`;
        return `${what}: ${r?.detail || r?.reason || 'refused'}`;
    });
}
