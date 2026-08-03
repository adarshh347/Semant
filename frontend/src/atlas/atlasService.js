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
};

export default atlasService;
