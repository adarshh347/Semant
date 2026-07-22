/**
 * Manuscript handoff queue — CIRCUIT-001 P1B.
 *
 * P1A's artery fired `insertRef` in the same tick as `setWorkspaceMode('chiasm')`
 * and hit three compounding faults:
 *
 *   1. `<Manuscript>` mounts only while `isEditing`. Arriving from Differential
 *      the curator is usually NOT editing, so the editor ref is null.
 *   2. `insertRef` does `if (!handle) return` — a SILENT no-op. The percept was
 *      dropped with no error and no trace.
 *   3. Even with editing on, a React state update is not synchronous, so the
 *      handle can still be absent in the tick that requested the insertion.
 *
 * The crossing therefore has to be a REQUEST that survives until the editor is
 * ready, not a call. This module owns that request as pure state so the rule can
 * be tested without mounting an editor.
 *
 * The invariant that matters most: a request is fulfilled AT MOST ONCE. Mount,
 * remount, a re-render storm or a second flush must never produce two chips for
 * one click — the curator asked once.
 */

/** Nothing pending. */
export const emptyHandoff = () => ({ percept: null, requestedAt: null, doneIds: [] });

/**
 * Queue a percept for insertion. Re-queuing the SAME percept while it is still
 * pending is a no-op (a double-click is one crossing), but a percept already
 * delivered may be sent again — a noticing can be carried into the writing more
 * than once, deliberately.
 */
export function requestHandoff(state, percept, now = 0) {
    if (!percept?.id) return state;
    if (state.percept?.id === percept.id) return state;
    return { ...state, percept, requestedAt: now };
}

/**
 * May the pending request be delivered now? Every condition must hold: something
 * is pending, the writing surface is mounted and editing, and the editor handle
 * exists. Anything missing means "not yet", never "give up".
 */
export function canFlush(state, { isEditing, hasHandle }) {
    return !!state.percept && !!isEditing && !!hasHandle;
}

/**
 * Mark the request delivered. Returns the cleared state; the id is remembered so
 * a retry in the same session cannot duplicate the chip.
 */
export function completeHandoff(state) {
    if (!state.percept) return state;
    return {
        percept: null,
        requestedAt: null,
        doneIds: [...state.doneIds, state.percept.id],
    };
}

/** Has this exact request already been delivered? Guards a remount replaying it. */
export const wasDelivered = (state, perceptId) => state.doneIds.includes(perceptId);

/**
 * The status line shown beside a percept once it has crossed. Derived from the
 * MENTIONS, never from a flag: a flag would say "sent" even if the chip were
 * later deleted, which is the kind of stored truth that drifts from the circuit.
 * Reports where it is, never why it went.
 */
export function handoffStatus(blockCount, mentionCount = 0) {
    // A chip inserted into an EMPTY document has no block id to be inserted
    // against — `currentBlockId()` is null before the first block exists — so the
    // mention records the crossing without recording where. That is a real limit
    // of what is known, and the status says the true part rather than nothing:
    // the noticing IS in the writing; only the passage count is unavailable.
    if (blockCount) return `in the writing · ${blockCount} passage${blockCount === 1 ? '' : 's'}`;
    if (mentionCount) return 'in the writing';
    return '';
}
