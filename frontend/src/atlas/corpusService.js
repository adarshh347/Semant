import { API_URL } from '../config/api';

// ATLAS L1 — the corpus client. Same per-domain service pattern as `atlasService` (raw fetch,
// throw on !ok); the X-API-Key header, where the backend requires one, is installed globally by
// config/api.js.
const BASE = `${API_URL}/api/v1/corpora`;

async function json(res, action) {
    if (!res.ok) throw new Error(`Failed to ${action} (${res.status})`);
    return res.json();
}

const send = (url, method, body) =>
    fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body ?? {}),
    });

export const corpusService = {
    /** The walks a curator has saved, most recently touched first. */
    async list() {
        return json(await fetch(`${BASE}/`), 'list corpora');
    },
    /** Name a walk. The ORDER of `images` is the walk's order and is kept exactly. */
    async create({ title = '', why = '', images = [] } = {}) {
        return json(await send(`${BASE}/`, 'POST', { title, why, images }), 'save the corpus');
    },
    /** The STORED document — ids and order, no percept data. */
    async get(id) {
        return json(await fetch(`${BASE}/${id}`), 'load the corpus');
    },
    /** The walk hydrated from the ledger — what a curation surface draws. */
    async view(id) {
        return json(await fetch(`${BASE}/${id}/view`), 'load the corpus view');
    },
    /**
     * Retitle, restate, reorder, re-note, add or drop. Returns `{corpus, refused}` — the refusals
     * travel with the change rather than aborting it, so adjusting four things cannot lose three
     * because the fourth was stale.
     */
    async patch(id, body) {
        return json(await send(`${BASE}/${id}`, 'PATCH', body), 'update the corpus');
    },
    async remove(id) {
        return json(await fetch(`${BASE}/${id}`, { method: 'DELETE' }), 'delete the corpus');
    },
};

export default corpusService;
