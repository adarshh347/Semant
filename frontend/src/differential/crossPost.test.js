import { describe, it, expect } from 'vitest';
import { regionRefMark } from './visualMarks';
import { resolveCrossPost, crossPostNote, crossPostResolves, crossPostReference } from './crossPost';

/**
 * CIRCUIT-001 P5-A — resolving a reference across the border.
 *
 * The discipline: a crossing is a reference with receipts. It must FETCH its source (not assume
 * loaded), confirm the region still exists, and detect drift — degrading exactly as a detached
 * ground does (never a crash, never a silent no-op, always a stated absence).
 */

const sourcePost = (rev) => ({
    id: 'post_B',
    region_annotations: [{ id: 'reg_9', label: 'lapel', geometry_rev: rev }],
});
// A fetcher over a tiny catalog. A missing id resolves to null (post gone); a throwing fetch is
// treated identically (the network could not reach it) — both must degrade, never throw.
const fetcherOver = (catalog) => async (pid) => catalog[pid] ?? null;
const throwingFetcher = async () => { throw new Error('network'); };

const refFor = (mark) => crossPostReference(mark);
const crossingMark = (rev) => regionRefMark({
    regionId: 'reg_9', postId: 'post_B', geometryRev: rev, label: 'lapel',
    producer: 'find_similar', runId: 'run_fs', model: 'dinov2',
});

describe('resolveCrossPost — the border verdict', () => {
    it('OK: the source resolves and the region is unchanged → navigate + perform', async () => {
        const ref = refFor(crossingMark(3));
        const res = await resolveCrossPost(ref, { fetchPost: fetcherOver({ post_B: sourcePost(3) }) });
        expect(res.status).toBe('ok');
        expect(res.region.id).toBe('reg_9');
        expect(crossPostResolves(res)).toBe(true);
        expect(crossPostNote(res)).toBe('');
    });

    it('POST GONE: the source no longer resolves → degrade, do not navigate', async () => {
        const ref = refFor(crossingMark(3));
        const res = await resolveCrossPost(ref, { fetchPost: fetcherOver({}) });
        expect(res.status).toBe('post_gone');
        expect(crossPostResolves(res)).toBe(false);
        expect(crossPostNote(res)).toMatch(/source post is gone/i);
    });

    it('POST GONE: a THROWING fetch degrades identically (never a crash)', async () => {
        const ref = refFor(crossingMark(3));
        const res = await resolveCrossPost(ref, { fetchPost: throwingFetcher });
        expect(res.status).toBe('post_gone');
    });

    it('REGION GONE: the post resolves but the cited region was removed → degrade', async () => {
        const ref = refFor(crossingMark(3));
        const post = { id: 'post_B', region_annotations: [{ id: 'reg_other' }] };
        const res = await resolveCrossPost(ref, { fetchPost: fetcherOver({ post_B: post }) });
        expect(res.status).toBe('region_gone');
        expect(crossPostResolves(res)).toBe(false);
        expect(crossPostNote(res)).toMatch(/region no longer exists/i);
    });

    it('STALE: the region drifted since citation → still resolves, but SAYS so', async () => {
        const ref = refFor(crossingMark(3));                    // cited at rev 3
        const res = await resolveCrossPost(ref, { fetchPost: fetcherOver({ post_B: sourcePost(5) }) });
        expect(res.status).toBe('stale');                       // now rev 5
        expect(res.currentRev).toBe(5);
        expect(crossPostResolves(res)).toBe(true);              // a crossing still performs
        expect(crossPostNote(res)).toMatch(/changed since cited/i);
    });

    it('no false staleness when the rev is unknown on either side', async () => {
        const noRev = regionRefMark({ regionId: 'reg_9', postId: 'post_B',
            producer: 'find_similar', runId: 'run_fs' });        // cited without a rev
        const res = await resolveCrossPost(refFor(noRev), { fetchPost: fetcherOver({ post_B: sourcePost(5) }) });
        expect(res.status).toBe('ok');                           // cannot claim drift → does not
    });

    it('a non-crossing reference (no fetcher / no ref) is a no_ref, not a throw', async () => {
        expect((await resolveCrossPost(null, { fetchPost: fetcherOver({}) })).status).toBe('no_ref');
        expect((await resolveCrossPost({ post_id: 'p' }, {})).status).toBe('no_ref');
    });
});
