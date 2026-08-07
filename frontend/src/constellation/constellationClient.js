/**
 * WAVE4 — the constellation API, as the page consumes it.
 *
 * Two reads and no write. There is no write path in the router either — this view *shows* the
 * neighbourhood; committing is `/curator`'s and grounding is the kernel's.
 *
 * Every field the backend derives arrives already derived and is passed through untouched:
 * `epistemic`, `ledger_status` and `span` are computed server-side from the mark, the ledger and
 * the endpoints respectively, and a client helper that recomputed any of them would be a second
 * opinion that can disagree.
 */
import { API_URL } from '../config/api';

const BASE = `${API_URL}/api/v1/constellation`;

/** Vocabularies, mirrored so the page can branch without inventing strings. */
export const SPAN_WITHIN = 'within_image';
export const SPAN_BETWEEN = 'between_images';
export const LEDGER_PROPOSED = 'proposed';
export const LEDGER_COMMITTED = 'committed';
export const EPISTEMIC_MEASURED = 'measured';
export const EPISTEMIC_INTERPRETIVE = 'interpretive';

export class ConstellationError extends Error {
    constructor(message, { status, detail } = {}) {
        super(message);
        this.name = 'ConstellationError';
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
        /* a non-JSON error body is still an error */
    }
    throw new ConstellationError(detail, { status: res.status, detail });
}

/** Loci with at least one persisted relation — "where is there anything to see". */
export async function fetchSeeds({ limit = 60 } = {}) {
    const res = await fetch(`${BASE}/seeds?limit=${limit}`);
    return readOr(res, 'The seed loci could not be read.');
}

/** The neighbourhood reachable from one locus, to a bounded depth. */
export async function fetchConstellation(node, { depth = 2 } = {}) {
    const params = new URLSearchParams({ node, depth: String(depth) });
    const res = await fetch(`${BASE}?${params}`);
    return readOr(res, 'That neighbourhood could not be read.');
}
