/**
 * ATLAS C4 — the pure half of plan mode: a proposed argument, laid out and edited.
 *
 * The panel and the canvas do the mounting and the clicking; this module decides what a claim node
 * IS, which connectors may be drawn, what an edit does to the structure, and what the accept
 * request owes the server. Everything here is a function of its arguments.
 *
 * THREE RULES, the same three the backend enforces, stated again on the near side because the
 * surface is where they are visible and therefore where they matter:
 *
 *  1. ONLY A BOUND PERCEPT DRAWS A CONNECTOR. `bindingEdges` filters on `bound`, and it derives
 *     the lines from the claims rather than trusting `plan.connectors` — so deleting a percept
 *     removes its line in the same gesture instead of leaving a wire to evidence the writer just
 *     dropped. `connectorsAgree` pins the derivation against the server's own list.
 *
 *  2. A BINDING IS NOT A RELATION. These edges run claim→image and are marked `binding`. C3's run
 *     image↔image and each is a real `compare_views` percept. Different endpoints, different
 *     class, different word, and nothing here ever writes to `edges`.
 *
 *  3. AN EDIT INVALIDATES THE VERDICT IT WAS MADE AGAINST. Drop a percept from a qualified claim
 *     and `qualified` is no longer a fact about anything — it was computed from a plan that no
 *     longer exists. Every edit marks its claim `dirty`, the surface says so, and accepting sends
 *     the structure back to be re-bound. A client-side status recomputation would be this module
 *     quietly deciding what evidence carries, which is the whole thing the gate exists to do.
 *
 * POSITION STILL ASSERTS NOTHING (C1's rule, and plan mode is where it would break first). A
 * claim's place in the argument is its ORDER, not its coordinates, so claim nodes are laid out
 * FROM that order and are not draggable. Two notions of sequence — one in the list, one on the
 * canvas — would contradict each other the moment anybody moved a card.
 */

import { CLAIM_NODE_PREFIX, isClaimNodeId } from './atlasDocument.js';

export const CLAIM_NODE_TYPE = 'atlasClaim';

/** A claim's node id. Namespaced so the save path can tell a card from a picture. */
export const claimNodeId = (claimId) => `${CLAIM_NODE_PREFIX}${claimId}`;

export { isClaimNodeId };

/** What a claim→image line is. Never the word `relation`, which belongs to C3's percepts. */
export const EDGE_BINDING = 'binding';

// The claim column, in canvas units. Laid to the LEFT of the leftmost image because an argument is
// read before the evidence it points at, and a column that overlapped the corpus would make the
// writer drag pictures to see their own claims.
export const CLAIM_W = 360;
export const CLAIM_H = 190;
export const CLAIM_GAP_Y = 44;
export const CLAIM_COL_GAP = 220;

export const FUNCTION_LABEL = {
    support: 'supports',
    complicate: 'complicates',
    challenge: 'challenges',
};

export const FUNCTION_HINT = {
    support: 'evidence the claim rests on',
    complicate: 'holds, and makes the claim harder to state simply',
    challenge: 'would tell against the claim if it came back strong',
};

export const EPISTEMIC_LABEL = {
    visible: 'visible',
    measured: 'measured',
    sourced: 'sourced',
    interpretive: 'interpretive',
    uncertain: 'uncertain',
};

export const STATUS_LABEL = {
    supported: 'carried',
    qualified: 'carried in part',
    refused: 'nothing can carry this',
};

/** A function outside the vocabulary is shown verbatim, never mapped to `supports`. It is about to
 *  be refused by name, and a tidy label would hide the one thing worth seeing. */
export function functionLabel(fn) {
    return FUNCTION_LABEL[fn] || (fn ? `“${fn}” — not an argumentative function` : 'no function');
}

export function epistemicLabel(kind) {
    return EPISTEMIC_LABEL[kind] || 'uncertain';
}

// ── layout ──────────────────────────────────────────────────────────────────

/**
 * Where the claim column sits, given where the images are.
 *
 * Derived from the corpus's own bounding box on every render rather than stored: the writer drags
 * pictures around constantly, and a column at a remembered coordinate would end up behind them.
 */
export function claimPositions(count, imageNodes = []) {
    const xs = imageNodes.map((n) => Number(n?.position?.x)).filter(Number.isFinite);
    const ys = imageNodes.map((n) => Number(n?.position?.y)).filter(Number.isFinite);
    const left = (xs.length ? Math.min(...xs) : 0) - CLAIM_W - CLAIM_COL_GAP;
    const top = ys.length ? Math.min(...ys) : 0;
    return Array.from({ length: Math.max(0, count) }, (_, i) => ({
        x: left, y: top + i * (CLAIM_H + CLAIM_GAP_Y),
    }));
}

/** The plan's claims → React Flow nodes, in argument order. */
export function claimFlowNodes(plan, imageNodes = []) {
    const claims = plan?.claims || [];
    const at = claimPositions(claims.length, imageNodes);
    return claims.map((claim, i) => ({
        id: claimNodeId(claim.claim_id),
        type: CLAIM_NODE_TYPE,
        position: at[i],
        // Deliberately no `width`/`height` — see the note in `flowNodesFromView`. A declared box
        // suppresses the measurement pass that records handle positions, and a claim whose handle
        // was never located is a claim whose connectors never draw.
        // The claim's place in the argument is its order. Dragging would invent a second sequence.
        draggable: false,
        connectable: false,
        selectable: true,
        data: { claim, index: i, total: claims.length },
    }));
}

/**
 * The connectors, derived from the claims themselves.
 *
 * A percept draws a line only when all three are true: it BOUND, it names an image this canvas
 * holds, and it is not comparative. The third is not a technicality — a comparative percept is
 * planned across the corpus and pointing it at one photograph would say it was about that picture.
 */
export function bindingEdges(plan) {
    const out = [];
    (plan?.claims || []).forEach((claim) => {
        (claim.percepts || []).forEach((p) => {
            if (!p.bound || p.spans_corpus || !p.node_id) return;
            out.push({
                id: `${claim.claim_id}~${p.step_id}`,
                source: claimNodeId(claim.claim_id),
                target: String(p.node_id),
                // Dashed, labelled with the rhetorical job, and never the same shape a real
                // comparative percept will get in C3.
                type: 'default',
                animated: false,
                className: `atlas-edge is-${p.function || 'unknown'}`,
                label: `${functionLabel(p.function)} · ${epistemicLabel(p.epistemic)}`,
                data: { kind: EDGE_BINDING, claimId: claim.claim_id, stepId: p.step_id,
                    function: p.function, epistemic: p.epistemic, actuator: p.actuator },
            });
        });
    });
    return out;
}

/**
 * Does the client's derivation agree with the server's? Used by the tests, and cheap enough to be
 * worth exporting: the two lists are computed from the same rule in two languages, and a silent
 * divergence would mean the canvas drew a binding the record does not hold.
 */
export function connectorsAgree(plan) {
    const mine = bindingEdges(plan).map((e) => e.id).sort();
    const theirs = (plan?.connectors || []).map((c) => c.edge_id).sort();
    return mine.length === theirs.length && mine.every((id, i) => id === theirs[i]);
}

// ── editing ─────────────────────────────────────────────────────────────────

/** Every edit goes through here, so no path can change a claim without marking it stale. */
function touch(claim, patch) {
    return { ...claim, ...patch, dirty: true };
}

/** Move a claim one place. The argument's order is the writer's, and this is the only thing that
 *  sets it — no sort, no auto-arrange by status, nothing that would rank claims by how well they
 *  did. Reordering does NOT dirty a claim: its evidence is unchanged. */
export function moveClaim(claims, claimId, delta) {
    const list = [...(claims || [])];
    const from = list.findIndex((c) => c.claim_id === claimId);
    const to = from + delta;
    if (from < 0 || to < 0 || to >= list.length) return list;
    const [row] = list.splice(from, 1);
    list.splice(to, 0, row);
    return list.map((c, i) => ({ ...c, order: i }));
}

export function dropClaim(claims, claimId) {
    return (claims || []).filter((c) => c.claim_id !== claimId)
        .map((c, i) => ({ ...c, order: i }));
}

/** Remove one percept. Its connector goes with it, because `bindingEdges` reads the claims. */
export function dropPercept(claims, claimId, stepId) {
    return (claims || []).map((c) => (c.claim_id !== claimId ? c
        : touch(c, { percepts: (c.percepts || []).filter((p) => p.step_id !== stepId) })));
}

/**
 * Reword a claim, keeping what it was proposed as.
 *
 * `proposed_text` is never overwritten. M2's binding proves the percepts RESOLVE, not that they
 * bear on the sentence — so the original wording is the only record of what the evidence was
 * actually chosen for, and the server stores both.
 */
export function rewordClaim(claims, claimId, text) {
    return (claims || []).map((c) => (c.claim_id !== claimId ? c : touch(c, { text })));
}

/** Has anything been changed since the planner answered? */
export function isEdited(plan, claims) {
    const original = plan?.claims || [];
    const now = claims || [];
    if (original.length !== now.length) return true;
    if (now.some((c) => c.dirty)) return true;
    return now.some((c, i) => c.claim_id !== original[i].claim_id);
}

// ── what an accept sends ────────────────────────────────────────────────────

/**
 * The accept payload: claims, percepts, and NOTHING about what carried.
 *
 * Statuses are deliberately absent rather than merely ignored server-side. A request that carried
 * `status: supported` would look, to anyone reading it later, like a thing the client was entitled
 * to assert — and the next person to write a route would honour it.
 */
export function acceptPayload(thesis, claims) {
    return {
        thesis: String(thesis || '').trim(),
        claims: (claims || []).map((c) => ({
            claim_id: c.claim_id,
            text: c.text,
            proposed_text: c.proposed_text ?? c.text,
            note: c.note || '',
            target_status: c.target_status,
            percepts: (c.percepts || []).map((p) => ({
                step_id: p.step_id,
                actuator: p.actuator,
                image: p.image,
                function: p.function,
                params: p.params || {},
                note: p.note || '',
            })),
        })),
    };
}

// ── reading a plan ──────────────────────────────────────────────────────────

/** The one-line state of the argument, for the header. Counts, never adjectives. */
export function planSummary(plan) {
    const counts = plan?.counts || {};
    const claims = counts.claims ?? (plan?.claims || []).length;
    return {
        claims,
        supported: counts.supported ?? 0,
        qualified: counts.qualified ?? 0,
        refused: counts.refused ?? 0,
        connectors: counts.connectors ?? bindingEdges(plan).length,
        complete: Boolean(plan?.complete),
        hasChallenge: Boolean(plan?.has_challenge),
    };
}

/**
 * Why an empty plan is empty. The distinction the surface cannot afford to lose: a planner nobody
 * can reach says nothing about the corpus, and a planner that read the corpus and found no
 * argument says everything about it.
 */
export function emptyPlanReason(plan) {
    if (!plan || (plan.claims || []).length > 0) return '';
    if (plan.planner_available === false) {
        return 'The argument planner could not be reached. Nothing was proposed, and nothing was '
            + 'invented in its place — this says nothing about whether the thesis can be argued.';
    }
    return 'The planner read this corpus and proposed no claims: it could not find an argument '
        + 'for this thesis in these images, with these instruments.';
}

/** The argument-level refusals, as lines a person can read. */
export function refusalLines(plan) {
    return (plan?.refusals || []).map((r) => {
        if (r.reason === 'no_challenge_step') {
            return `No counter-reading: ${r.detail}`;
        }
        if (r.reason === 'no_claim_is_carried') {
            return `Nothing is carried: ${r.detail}`;
        }
        if (r.reason === 'no_claims_proposed') {
            return `Nothing was proposed: ${r.detail}`;
        }
        return `${r.reason}: ${r.detail}`;
    });
}
