/**
 * ATLAS C5 — the writer surface, as data. PURE: no React, no fetch, no DOM.
 *
 * WHAT IS DELIBERATELY NOT HERE. Everything about what an article SAYS — its blocks, its defect
 * channel, its epistemic legend — belongs to M4's `article/articleDraft.js` and is imported from
 * there. A second copy of `sectionDefects` on the Atlas side would be a second answer to "what
 * does this paragraph admit", and the two would drift in exactly the direction that flatters the
 * document. This module holds only what is ATLAS-specific: the seed a plan offers the writer, why
 * a draft cannot be made, and what quarantine means on this surface.
 */

import { articleDefects, draftOf } from '../article/articleDraft.js';

// Mirrors `backend/services/atlas_draft.py`. The surface branches on these.
export const DRAFT_QUARANTINED = 'quarantined';
export const DRAFT_ACCEPTED = 'accepted';

export const BLOCK_NO_PLAN = 'no_accepted_plan';
export const BLOCK_NO_IMAGES = 'atlas_spans_no_images';
export const BLOCK_NO_CLAIMS = 'the_accepted_plan_carries_no_claims';
export const BLOCK_ALL_REFUSED = 'every_claim_in_the_plan_was_refused';

const BLOCKER_TEXT = {
    [BLOCK_NO_PLAN]: 'No plan has been accepted on this Atlas. Plan an argument first — the writer '
        + 'drafts from a plan that was judged, never from a thesis alone.',
    [BLOCK_NO_IMAGES]: 'This Atlas spans no images. There is nothing for a claim to rest on.',
    [BLOCK_NO_CLAIMS]: 'The accepted plan carries no claims. Plan again before drafting.',
    [BLOCK_ALL_REFUSED]: 'Every claim in the accepted plan was refused by the gate. Nothing here '
        + 'can be carried, so nothing is written — read the refusals on the plan.',
};

/** The writer-facing sentence for a blocker. An unknown reason is shown as itself, never hidden. */
export const blockerText = (reason) => BLOCKER_TEXT[reason] || String(reason || '');

/**
 * The seed: what an accepted plan offers the writer BEFORE a word is drafted.
 *
 * Claim stubs bound to their percepts — the structure C4 earned, shown as the shape the prose will
 * take. A struck claim is kept and marked rather than filtered out: the writer accepted a plan
 * that included a refusal, and a seed that quietly dropped it would misrepresent what they
 * accepted.
 */
export function seedStubs(plan) {
    const claims = (plan && plan.claims) || [];
    return claims.map((claim) => ({
        claimId: claim.claim_id,
        text: claim.text || '',
        status: claim.status || '',
        struck: Boolean(claim.struck),
        percepts: (claim.percepts || []).map((p) => ({
            stepId: p.step_id,
            actuator: p.actuator,
            function: p.function,
            epistemic: p.epistemic || '',
            image: p.image || '',
            bound: Boolean(p.bound),
            why: p.why || '',
        })),
    }));
}

/** Can this Atlas be drafted from at all, and if not, why? Mirrors the backend's own order. */
export function seedBlocker(atlas) {
    if (!atlas) return BLOCK_NO_PLAN;
    if (!((atlas.nodes || []).length)) return BLOCK_NO_IMAGES;
    const plan = atlas.plan;
    if (!plan || !Object.keys(plan).length) return BLOCK_NO_PLAN;
    const claims = plan.claims || [];
    if (!claims.length) return BLOCK_NO_CLAIMS;
    if (claims.every((c) => c.struck)) return BLOCK_ALL_REFUSED;
    return null;
}

/** The 409 body the draft route returns → a sentence. Tolerant of a plain-string detail. */
export function blockerFrom(error) {
    const detail = error && (error.detail ?? error.body?.detail ?? error.message);
    if (detail && typeof detail === 'object') {
        return detail.message || blockerText(detail.reason) || 'The draft could not be made.';
    }
    return String(detail || 'The draft could not be made.');
}

export const isQuarantined = (draft) => Boolean(draft) && draft.state === DRAFT_QUARANTINED;
export const isAccepted = (draft) => Boolean(draft) && draft.state === DRAFT_ACCEPTED;

/** The article payload M4's renderer eats, out of the stored draft. */
export const articleOf = (draft) => (draft && draft.article) || null;

/**
 * What the writer is told about a draft at a glance.
 *
 * `live` over `cited` is the number that matters and the one a reader would otherwise have to
 * count: it is how much of this article's evidence can actually be drawn. An article citing six
 * percepts and showing one is a different document from one showing six, and the header says so.
 */
export function draftSummary(draft) {
    const article = articleOf(draft);
    const inner = draftOf(article || {});
    const counts = (article && article.counts) || {};
    return {
        sections: (inner.sections || []).length,
        cited: counts.citations || 0,
        live: counts.drawable || 0,
        unresolved: counts.unresolved || 0,
        defects: articleDefects(article || {}).length,
        limits: limitCount(inner),
        complete: Boolean(inner.complete),
        epistemic: inner.epistemic || '',
        quarantined: isQuarantined(draft),
        accepted: isAccepted(draft),
    };
}

function limitCount(inner) {
    const counter = inner.counter_reading;
    return (inner.qualifications || []).length
        + (inner.uncomposed || []).length
        + (counter && !counter.grounded ? 1 : 0);
}

/**
 * Everything this draft refuses to carry, as sentences the panel must render.
 *
 * NOT COLLAPSIBLE, for C4's reason applied one layer up: a refusal behind a disclosure triangle is
 * the honest thing to compute and the dishonest thing to ship. The writer decides whether to
 * accept an article; they cannot decide it without seeing what it could not say.
 */
export function refusalLines(draft) {
    const inner = draftOf(articleOf(draft) || {});
    const lines = [];
    for (const q of inner.qualifications || []) {
        if (q && q.prose) lines.push(String(q.prose));
    }
    for (const u of inner.uncomposed || []) {
        if (!u) continue;
        const reason = String(u.reason || '').replace(/_/g, ' ');
        if (u.claim) lines.push(`${u.claim} — not written: ${reason}.`);
    }
    const counter = inner.counter_reading;
    if (counter && !counter.grounded) {
        lines.push(counter.absence_detail || 'No counter-reading could be grounded.');
    }
    return lines;
}

/**
 * May this draft be accepted into the manuscript?
 *
 * A draft that composed no prose is refused rather than accepted as an empty passage: "I accepted
 * this article" and "I accepted nothing" must not be the same gesture. An already-accepted draft
 * is refused for the same reason the backend refuses it — twice-accepted prose would appear twice.
 */
export function acceptState(draft) {
    if (!draft) return { can: false, why: 'There is no draft to accept.' };
    if (isAccepted(draft)) {
        return { can: false, why: 'This draft has already been accepted into the manuscript.' };
    }
    const inner = draftOf(articleOf(draft) || {});
    if (!(inner.sections || []).some((s) => s && s.prose)) {
        return { can: false,
            why: 'This draft composed no prose. Read the refusals — there is nothing to accept.' };
    }
    return { can: true, why: '' };
}

/** The passages the export says Accept would write. Read from the export payload, never re-derived. */
export const passagesOf = (exported) => (exported && exported.passages) || [];
