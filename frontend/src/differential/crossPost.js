// CIRCUIT-001 P5-A — the crossing: resolving a reference across the image border.
//
// The rule this module holds: a crossing is a REFERENCE WITH RECEIPTS — never a copy, never an
// assertion, never silent about its own staleness. A foreign chip names `{post_id, region_id,
// geometry_rev}` on ANOTHER post; nothing of that post's geometry is ever carried here. To
// perform it we must FETCH the source (not assume it loaded), confirm the referenced region still
// exists, and detect drift — so the chip degrades exactly as a detached ground does (P1B): never
// a crash, never a silent no-op, always a stated absence.
//
// Pure but for an injected `fetchPost` — no store, no router, no direct fetch. The click seam
// (PostDetailPage) supplies the fetcher and acts on the verdict (navigate, or state the loss).

import { crossPostReference } from './visualMarks';

export { crossPostReference };

// The regions live under `region_annotations` on a persisted post (the backend name); some
// client shapes carry `regions`. Read both so resolution never misses on a shape difference.
const regionsOf = (post) => post?.region_annotations || post?.regions || [];

/**
 * Resolve a border reference against its source post. `fetchPost(postId) -> post | null`
 * (throwing is treated as "gone"). Returns a verdict the click seam acts on:
 *
 *   { status: 'ok',          post, region, currentRev }   navigate + perform recall natively
 *   { status: 'stale',       post, region, currentRev }   still resolves, but the source drifted
 *   { status: 'post_gone',   ref }                        the source post no longer resolves
 *   { status: 'region_gone', post, ref }                  the region the citation named is gone
 *   { status: 'no_ref' }                                  not a cross-post reference at all
 *
 * `stale` is deliberately NOT a failure — the region still exists, so the crossing still performs;
 * the drift is reported (in inspection), never hidden and never a reason to refuse the recall.
 */
export async function resolveCrossPost(ref, { fetchPost } = {}) {
    if (!ref || !ref.post_id || typeof fetchPost !== 'function') return { status: 'no_ref', ref };
    let post = null;
    try { post = await fetchPost(ref.post_id); } catch { post = null; }
    if (!post) return { status: 'post_gone', ref };

    const region = regionsOf(post).find((r) => r.id === ref.region_id) || null;
    if (!region) return { status: 'region_gone', post, ref };

    const currentRev = (typeof region.geometry_rev === 'number') ? region.geometry_rev : null;
    // Drift is a real, quiet danger: a citation that named rev 3 now points at rev 5 may be
    // pointing at different pixels. Detectable → stated. When either rev is unknown we cannot
    // claim drift, so we do not (silence about an unknowable is honest; a false "stale" is not).
    const stale = ref.geometry_rev != null && currentRev != null && ref.geometry_rev !== currentRev;
    return { status: stale ? 'stale' : 'ok', post, region, currentRev };
}

/**
 * The human-facing note for a verdict — the same honesty channel `recall.evidenceNote` speaks in.
 * Empty string when the crossing performs cleanly (nothing to say).
 */
export function crossPostNote(resolution) {
    switch (resolution?.status) {
        case 'post_gone':
            return 'Evidence unavailable — the source post is gone.';
        case 'region_gone':
            return 'Evidence unavailable — the cited region no longer exists on the source.';
        case 'stale':
            return 'Source has changed since cited — the reference may point elsewhere now.';
        default:
            return '';
    }
}

/** Does a verdict still resolve to something a recall can perform? (`ok` or `stale`.) */
export const crossPostResolves = (resolution) =>
    resolution?.status === 'ok' || resolution?.status === 'stale';
