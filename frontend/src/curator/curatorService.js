/**
 * WAVE4 — the curator API, as the UI consumes it.
 *
 * Three calls against the surface #172 built, and no fourth. There is no bulk-commit here because
 * there is no bulk-commit route, and adding one client-side — a loop over `commit` behind one
 * button — would put back exactly what that lane deliberately left out. The absence is the design:
 * one deliberate act per claim.
 *
 * ## The two statuses arrive already separated, and this module does not blend them
 *
 *     epistemic      how the PRODUCER knows it   `measured` | `interpretive` | null
 *     ledger_status  whether a HUMAN agreed      `proposed` | `committed`
 *
 * The backend derives both on every read — `epistemic` off the mark, `ledger_status` off whether
 * that mark is in the post's ledger. This client passes them through untouched and never computes
 * one from the other. A row reading `measured` + `proposed` is not a contradiction to resolve; it
 * is the whole point, and a helper that collapsed them into one "state" would be the first place
 * that story got lost.
 */
import { API_URL } from '../config/api';

const BASE = `${API_URL}/api/v1/curator`;

/** The vocabularies, mirrored from the backend so the UI can branch without inventing strings. */
export const LEDGER_PROPOSED = 'proposed';
export const LEDGER_COMMITTED = 'committed';
export const EPISTEMIC_MEASURED = 'measured';
export const EPISTEMIC_INTERPRETIVE = 'interpretive';

/**
 * A failed call, carrying the backend's own reason.
 *
 * The curator routes answer with a real explanation — "would put the same mark in the ledger
 * twice", "went nowhere" — and a client that replaced those with "Something went wrong" would
 * strip the one thing that tells a curator whether their commit happened. `detail` is kept.
 */
export class CuratorError extends Error {
    constructor(message, { status, detail } = {}) {
        super(message);
        this.name = 'CuratorError';
        this.status = status;
        this.detail = detail || message;
    }
}

async function readOr(res, fallback) {
    if (res.ok) return res.json();
    let detail = fallback;
    try {
        const body = await res.json();
        if (body && body.detail) detail = body.detail;
    } catch {
        /* a non-JSON error body is still an error; the fallback stands */
    }
    throw new CuratorError(detail, { status: res.status, detail });
}

/**
 * The queue, in FILED ORDER — the order the backend returns and this does not re-sort.
 *
 * A queue ranked by the evidence's own strength would be the UI telling the curator what to look
 * at first, which is the judgement it exists to present rather than to make. #172 left the backend
 * unsorted for that reason and the client honours it.
 */
export async function fetchQueue({ kind, committed, limit = 200 } = {}) {
    const params = new URLSearchParams();
    if (kind) params.set('kind', kind);
    if (committed === true || committed === false) params.set('committed', String(committed));
    if (limit) params.set('limit', String(limit));
    const res = await fetch(`${BASE}/queue?${params}`);
    return readOr(res, 'The queue could not be read.');
}

export async function fetchProposal(proposalId) {
    const res = await fetch(`${BASE}/queue/${encodeURIComponent(proposalId)}`);
    return readOr(res, `No proposal ${proposalId}.`);
}

/**
 * Commit one proposal. THE ONLY WRITE THIS MODULE MAKES.
 *
 * `curator` is required by the route and is not defaulted here — an anonymous commit is a claim in
 * the ledger that nobody stands behind, and a client that filled in "curator" or the browser's
 * user would be inventing the accountability the whole seam rests on.
 */
export async function commitProposal(proposalId, { curator, note = '' }) {
    if (!curator || !String(curator).trim()) {
        throw new CuratorError('A commit needs a curator: this goes in the ledger under a name.');
    }
    const res = await fetch(`${BASE}/queue/${encodeURIComponent(proposalId)}/commit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ curator: String(curator).trim(), note }),
    });
    return readOr(res, 'The commit did not happen.');
}
