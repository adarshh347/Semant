/**
 * COGNITION — the read client. The only module here that knows a network exists.
 *
 * Same shape as `agentDemo/runClient.js` and for the same reason: every component below takes a
 * WalkView and renders it, so a fixture and the live routes are interchangeable and the page
 * cannot tell them apart. The dom tests drive the mock; nothing in them stubs a thing the real
 * client does differently.
 *
 * READ-ONLY. There is no write method here to misuse — the surface watches, it does not propose.
 */
import { API_URL } from '../config/api';

const BASE = `${API_URL}/api/v1/cognition`;

async function asJson(res) {
    if (!res.ok) {
        let detail = '';
        try { detail = (await res.json())?.detail || ''; } catch { /* body may not be json */ }
        throw new Error(detail || `${res.status} ${res.statusText}`);
    }
    return res.json();
}

const query = (params) =>
    Object.entries(params)
        .filter(([, v]) => v !== '' && v !== null && v !== undefined)
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
        .join('&');

export function createCognitionClient() {
    // No header plumbing here on purpose: `config/api` patches `window.fetch` once to inject the
    // API key on requests aimed at this backend, so a second place doing it would be a second
    // place to get it wrong. `agentDemo/runClient.js` relies on the same patch.
    return {
        temperaments: () => fetch(`${BASE}/temperaments`).then(asJson),
        walk: (params) => fetch(`${BASE}/walk?${query(params)}`).then(asJson),
        compare: (params) => fetch(`${BASE}/compare?${query(params)}`).then(asJson),
    };
}

export function createMockCognitionClient(fixture) {
    return {
        temperaments: async () => fixture.temperaments,
        walk: async () => fixture.walk,
        compare: async () => fixture.compare,
    };
}
