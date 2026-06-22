import { API_URL } from '../config/api';

const BASE = `${API_URL}/api/v1/personas`;

async function json(res, msg) {
    if (!res.ok) throw new Error(msg);
    return res.json();
}

export const personaService = {
    async listPersonas() {
        return json(await fetch(`${BASE}/`), 'Failed to fetch personas');
    },
    async getPersona(handle) {
        return json(await fetch(`${BASE}/${encodeURIComponent(handle)}`), 'Failed to fetch persona');
    },
    async synthesize(handle) {
        return json(await fetch(`${BASE}/${encodeURIComponent(handle)}/synthesize`, { method: 'POST' }), 'Failed to synthesize persona');
    },
    async getImages(handle) {
        return json(await fetch(`${BASE}/${encodeURIComponent(handle)}/images`), 'Failed to fetch images');
    },
};
