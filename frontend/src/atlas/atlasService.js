import { API_URL } from '../config/api';

// ATLAS C1 — the Atlas client. Mirrors the repo's per-domain service pattern (raw fetch, throw on
// !ok). The X-API-Key header, when the backend requires one, is installed globally by config/api.js.
const BASE = `${API_URL}/api/v1/atlas`;

async function json(res, action) {
    if (!res.ok) throw new Error(`Failed to ${action} (${res.status})`);
    return res.json();
}

const post = (url, body) =>
    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body ?? {}),
    });

export const atlasService = {
    async list() {
        return json(await fetch(`${BASE}/`), 'list atlases');
    },
    async create({ title = '', post_ids = [], run_id = null } = {}) {
        return json(await post(`${BASE}/`, { title, post_ids, run_id }), 'create atlas');
    },
    /** The STORED document — arrangement only. */
    async get(id) {
        return json(await fetch(`${BASE}/${id}`), 'load atlas');
    },
    /** The document hydrated from the ledger — what the canvas draws. */
    async view(id) {
        return json(await fetch(`${BASE}/${id}/view`), 'load atlas view');
    },
    /** Move nodes. Returns `{atlas, refused}` — the refusals travel with the save. */
    async saveArrangement(id, nodes) {
        return json(await post(`${BASE}/${id}/arrangement`, { nodes }), 'save arrangement');
    },

    // ── C4: plan mode ──
    /** A thesis → the argument this corpus could carry. Proposing does NOT persist. */
    async proposePlan(id, { thesis, why = '' }) {
        return json(await post(`${BASE}/${id}/plan`, { thesis, why }), 'plan an argument');
    },
    /** The writer's edited plan. The server RE-BINDS it — no status this sends is believed. */
    async acceptPlan(id, payload) {
        return json(await post(`${BASE}/${id}/plan/accept`, payload), 'accept the plan');
    },
    async clearPlan(id) {
        return json(await fetch(`${BASE}/${id}/plan`, { method: 'DELETE' }), 'clear the plan');
    },

    // ── C3: relation edges ──
    /** A drawn line → M1's `compare_views`. Resolves to `{atlas, edge}` or `{refused}` — a
     *  refusal arrives as a 200, because "these two images share no evidence to compare" is an
     *  answer about the corpus, not a malfunction to be thrown. */
    async drawRelation(id, body) {
        return json(await post(`${BASE}/${id}/relations`, body), 'draw the relation');
    },
    // ── T2: the Scout ──
    /**
     * Ask which pairs might repay comparison. Resolves to `{candidates, dropped}` or `{refused}`.
     *
     * PROPOSES ONLY. Nothing this returns is stored on either side of the wire. A candidate becomes
     * a relation solely by going through `drawRelation` above — which runs `compare_views` and can
     * refuse — and there is deliberately no endpoint that would shortcut that.
     */
    async scout(id, { limit = 0 } = {}) {
        return json(await post(`${BASE}/${id}/scout`, { limit }), 'ask the scout');
    },

    /** Take the edge off the canvas. The committed relation stays in the ledger. */
    async removeRelation(id, edgeId) {
        return json(await fetch(`${BASE}/${id}/relations/${edgeId}`, { method: 'DELETE' }),
            'remove the relation');
    },
};

export default atlasService;
