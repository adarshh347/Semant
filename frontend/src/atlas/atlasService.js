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

/**
 * Like `json`, but carries the server's `detail` onto the thrown error.
 *
 * C5's refusals ARE the answer — "every claim in this plan was refused" is what the writer needs
 * to read, and the plain helper above would replace it with "Failed to draft (409)". Used only
 * where the body is worth more than the status.
 */
async function jsonOrDetail(res, action) {
    if (res.ok) return res.json();
    let detail = null;
    try { detail = (await res.json())?.detail ?? null; } catch { /* not every error has a body */ }
    const err = new Error(`Failed to ${action} (${res.status})`);
    err.detail = detail;
    err.status = res.status;
    throw err;
}

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
    /** Take the edge off the canvas. The committed relation stays in the ledger. */
    async removeRelation(id, edgeId) {
        return json(await fetch(`${BASE}/${id}/relations/${edgeId}`, { method: 'DELETE' }),
            'remove the relation');
    },

    // ── C5: the writer ──
    /** The accepted plan → an executed chain → M3's prose → M4's live percepts. The slow one:
     *  this runs the producers. Refusals arrive as a 409 whose detail is the writer's sentence. */
    async draftArticle(id, { why = '' } = {}) {
        return jsonOrDetail(await post(`${BASE}/${id}/draft`, { why }), 'draft the article');
    },
    /** The drafted passages → the manuscript. The one call that takes prose out of quarantine. */
    async acceptDraft(id, payload = {}) {
        return jsonOrDetail(await post(`${BASE}/${id}/draft/accept`, payload),
            'accept the draft');
    },
    /** Drop the draft. The accepted plan and the arrangement survive it. */
    async dismissDraft(id) {
        return json(await fetch(`${BASE}/${id}/draft`, { method: 'DELETE' }),
            'dismiss the draft');
    },
    /** The M4 perceptual-article artifact. A read: exporting accepts nothing. */
    async exportDraft(id) {
        return jsonOrDetail(await fetch(`${BASE}/${id}/draft/export`), 'export the article');
    },
};

export default atlasService;
