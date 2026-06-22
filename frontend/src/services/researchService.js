import { API_URL } from '../config/api';

const BASE = `${API_URL}/api/v1/research`;

async function json(res, errMsg) {
    if (!res.ok) throw new Error(errMsg);
    return res.json();
}

export const researchService = {
    // --- Agent runs ---
    async runAgent({ topic = null, source_tags = null, angle = null } = {}) {
        const res = await fetch(`${BASE}/agent/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic, source_tags, angle }),
        });
        return json(res, 'Failed to start agent run');
    },

    async getRun(runId) {
        return json(await fetch(`${BASE}/agent/runs/${runId}`), 'Failed to fetch run');
    },

    async listRuns(limit = 20) {
        return json(await fetch(`${BASE}/agent/runs?limit=${limit}`), 'Failed to fetch runs');
    },

    // --- Articles ---
    async listArticles(page = 1, limit = 20) {
        return json(await fetch(`${BASE}/articles?page=${page}&limit=${limit}`), 'Failed to fetch articles');
    },

    async getArticle(id) {
        return json(await fetch(`${BASE}/articles/${id}`), 'Failed to fetch article');
    },

    async sendFeedback(articleId, signals) {
        const res = await fetch(`${BASE}/articles/${articleId}/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ signals }),
        });
        return json(res, 'Failed to send feedback');
    },

    // Fire-and-forget for implicit signals (dwell, scroll); never throws.
    beaconFeedback(articleId, signals) {
        try {
            fetch(`${BASE}/articles/${articleId}/feedback`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ signals }),
                keepalive: true,
            }).catch(() => {});
        } catch (_) { /* ignore */ }
    },

    // --- Sankalpa (will profile) ---
    async getSankalpa() {
        return json(await fetch(`${BASE}/sankalpa`), 'Failed to fetch Sankalpa');
    },
};
