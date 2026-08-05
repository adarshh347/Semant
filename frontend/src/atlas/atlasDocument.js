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

/**
 * The namespace for nodes that are NOT images of the corpus.
 *
 * C4 puts claim cards on the same canvas, and they go through the same React Flow node array as
 * the pictures — because that array is what React Flow measures, and an unmeasured node cannot
 * anchor a connector. What they must never do is reach the ARRANGEMENT: the Atlas document holds
 * where each image sits, and a claim has no place in it. So the two live together on the canvas
 * and part company at the save boundary, by id.
 */
export const CLAIM_NODE_PREFIX = 'claim:';

export const isClaimNodeId = (id) => String(id ?? '').startsWith(CLAIM_NODE_PREFIX);

/**
 * T1 — the modes.
 *
 * A mode is a LENS over one Atlas document, not an application. Both modes read the same `/view`,
 * write through the same two save routes, and share the same way into the Differential; switching
 * swaps a renderer and nothing else. That is why this is a list of two strings and not a registry
 * with capabilities — the moment a mode could own state the others cannot see, "the same document,
 * looked at differently" would stop being true and the curator would start losing work by
 * navigating.
 */
export const MODE_CANVAS = 'canvas';
export const MODE_LIGHT_TABLE = 'light-table';
// C4. Plan mode is the Canvas plus an argument drawn over it — the SAME renderer, given claim
// cards and binding connectors as well as images. A third lens, not a third surface, which is
// exactly the claim T1's framework makes and the first real test of it.
export const MODE_PLAN = 'plan';

export const ATLAS_MODES = [
    { key: MODE_CANVAS, label: 'Canvas',
        hint: 'arrange the corpus in space — position is a thinking aid' },
    { key: MODE_LIGHT_TABLE, label: 'Light Table',
        hint: 'scan the corpus in a grid — read, note, and ask for a machine read' },
    { key: MODE_PLAN, label: 'Plan',
        hint: 'ask what argument this corpus could carry — and see what it refuses' },
];

export function isMode(value) {
    return ATLAS_MODES.some((m) => m.key === value);
}

/**
 * T1 — what a one-click "machine read" asks for.
 *
 * It is an INTENTION, in the curator's vocabulary, handed to the Director exactly as if it had
 * been typed into the Orchestrate bar — because that is precisely what happens. The Director plans
 * it (`trace_light` → the `light_field` producer), executes real actuators that write nothing to
 * the post, and the result lands in the existing quarantine for review. No new actuator, no second
 * trigger path, nothing bypassed.
 *
 * WHY THIS INTENTION. It has to resolve on ANY image with nothing gathered yet, which rules most
 * chains out: `semantic_read` requires REGION and is only reachable through `read_material`, whose
 * chain re-runs segmentation first. The light field needs the image alone, is quick, and produces
 * real evidence-bound geometry rather than a sentence. When the planner learns a cheaper reading
 * act, this constant is the one place to change.
 *
 * WHY AUTO-RUNNING IS ALLOWED HERE, when the Manuscript's `firstAttentionPrefill` deliberately is
 * not: that prefill carries text the curator wrote for another purpose, so running it would put
 * words in the image's mouth. This runs a fixed, named act the curator invoked by pressing a
 * button that says what it does. The click IS the approval — and the output is still quarantined.
 */
export const MACHINE_READ_INTENTION = 'trace the light';

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
 *
 * C2 passes `onOpen` through `data` because that is how React Flow gets anything to a custom node.
 * It is a callback, not state: an unreadable node never receives it, so the one control on the
 * canvas cannot appear on an image there is nothing to open.
 */
export function flowNodesFromView(view, { onOpen = null, onMachineRead = null } = {}) {
    const nodes = view?.nodes || [];
    return nodes.map((n) => ({
        id: String(n.node_id),
        type: ATLAS_NODE_TYPE,
        position: { x: finite(n.x) ?? 0, y: finite(n.y) ?? 0 },
        // C1 draws no edges and connects nothing; a node is dragged, not wired.
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
            // T1: the author's own lines about this image. From the Atlas document, not the
            // ledger — which is why an unreadable node still has them.
            notes: (n.notes || []).map((note) => ({
                note_id: String(note?.note_id || ''),
                text: String(note?.text || ''),
            })),
            w: finite(n.w) ?? 420,
            h: finite(n.h) ?? 320,
            // Only where there is an image to open. There is nothing to make a percept on in a
            // post that could not be read, and offering the way in would be a dead end dressed
            // as an affordance.
            onOpen: n.readable === false ? null : onOpen,
            // T1: same rule, same reason. A machine read on an image that could not be loaded
            // would be a model asked to look at nothing.
            onMachineRead: n.readable === false ? null : onMachineRead,
        },
    }));
}

/**
 * node_id → the notes it holds, for diffing a save against what the server confirmed.
 *
 * BLANK NOTES ARE NOT NOTES, which is the same rule the backend keeps (`clean_note` drops them).
 * The two ends have to agree or the diff never settles: an empty slot the writer has opened but
 * not filled would be a difference from the server on every keystroke, so the save would fire, the
 * server would echo back a list without it, and the difference would still be there. Dropping it
 * here means an opened-and-abandoned slot costs nothing and leaves nothing behind.
 */
export function notesOf(nodes) {
    const out = {};
    (nodes || []).forEach((n) => {
        if (isClaimNodeId(n?.id)) return;      // a claim card is not an image and holds no notes
        if (!n?.id) return;
        out[String(n.id)] = (n.data?.notes || [])
            .map((note) => ({
                note_id: String(note?.note_id || ''), text: String(note?.text || ''),
            }))
            .filter((note) => note.text.trim() !== '');
    });
    return out;
}

/** Two note lists, compared by what they SAY — id and text, in order. */
function sameNotes(a, b) {
    if ((a?.length || 0) !== (b?.length || 0)) return false;
    return (a || []).every((note, i) => note.note_id === b[i].note_id && note.text === b[i].text);
}

/**
 * The patches a notes save should carry: the nodes whose notes actually changed.
 *
 * The same shape as `arrangementFrom` and for the same reason — a save that re-sent every node's
 * notes on every keystroke would say nothing about what the writer did, and would race with
 * itself across a sixty-image corpus. The slot travels whole because replacing it is what makes
 * add, edit and delete one code path rather than three.
 */
export function notePatchesFrom(nodes, saved = {}) {
    const now = notesOf(nodes);
    const out = [];
    Object.entries(now).forEach(([nodeId, notes]) => {
        if (sameNotes(saved[nodeId], notes)) return;
        out.push({ node_id: nodeId, notes });
    });
    return out;
}

/**
 * Apply an edit to one node's notes, purely. Blank text deletes.
 *
 * Deleting by emptying is the gesture a text field already has, and it means there is no second
 * "remove" affordance to reason about — a note the writer cleared is a note they took back.
 */
export function withNoteEdit(notes, noteId, text) {
    const next = (notes || []).map((n) => (n.note_id === noteId ? { ...n, text } : n));
    return next.filter((n) => String(n.text || '').trim() !== '');
}

/** Add an empty note to write into. It is not saved until it has text — `notePatchesFrom` and the
 *  backend both drop blank ones, so an abandoned slot leaves nothing behind. */
export function withNoteAdded(notes, noteId) {
    return [...(notes || []), { note_id: noteId, text: '' }];
}

/** node_id → {x, y}, for comparing an arrangement against the one the server last confirmed. */
export function positionsOf(nodes) {
    const out = {};
    (nodes || []).forEach((n) => {
        // A claim card shares the canvas but is not part of the arrangement — it is laid out from
        // the argument's ORDER, and the document has no node to move for it.
        if (!n?.id || isClaimNodeId(n.id)) return;
        const x = finite(n?.position?.x);
        const y = finite(n?.position?.y);
        if (x !== null && y !== null) out[String(n.id)] = { x, y };
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
        // T1's two. A note that vanished without a word would read as an unreliable slot, and a
        // writer who cannot trust the slot stops using it.
        if (r?.reason === 'bad_note') return `${what}: ${r?.detail || 'a note had no text'} — not saved.`;
        if (r?.reason === 'too_many_notes') return `${what}: ${r?.detail || 'too many notes'}.`;
        return `${what}: ${r?.detail || r?.reason || 'refused'}`;
    });
}
