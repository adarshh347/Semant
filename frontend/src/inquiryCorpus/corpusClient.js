/**
 * INQUIRY CORPUS — the client. The only module here that knows a network exists.
 *
 * Two things it must do that a bare `fetch` would not:
 *
 *   1. go through the SAME TanStack cache the Archive uses, under the same key, so browsing the
 *      Gallery and then opening `/inquiry` does not re-fetch a page the browser already has —
 *      and, more importantly, so the two surfaces cannot hold different ideas of what page 3 is;
 *   2. accept an injected `queryClient`, because `useQueryClient()` is a hook and this file has to
 *      stay callable from a plain test.
 *
 * `createMockCorpusClient` walks a fixed list of pages so the picker's whole paging, selection and
 * search behaviour can be driven with no provider and no network. The real client is exercised
 * separately against a real `QueryClient` — the cache-sharing claim is only worth making if
 * something proves it.
 */
import { API_URL } from '../config/api';
import { PAGE_KEY, PAGE_SIZE, normalizePage, pageUrl } from './corpusSource';

const STALE_MS = 5 * 60 * 1000;     // ArchiveGrid's staleTime, for the same reason: a page of the
                                    // archive does not change while you are looking at it.

export class CorpusRequestError extends Error {
    constructor(message, { status = 0 } = {}) {
        super(message);
        this.name = 'CorpusRequestError';
        this.status = status;
    }
}

/**
 * The live client.
 *
 * `queryClient` is required rather than optional: a client that silently fell back to a private
 * fetch when none was supplied would be the second archive store the board forbids, arriving by
 * accident on whichever screen forgot to pass it.
 */
export function createCorpusClient({ queryClient, fetchImpl = null, apiUrl = API_URL } = {}) {
    if (!queryClient) throw new Error('createCorpusClient needs the app queryClient');
    const f = fetchImpl || ((...a) => globalThis.fetch(...a));

    async function page({ tag = null, page: n = 1, limit = PAGE_SIZE } = {}) {
        const raw = await queryClient.fetchQuery({
            queryKey: PAGE_KEY(tag, n),
            queryFn: async () => {
                const res = await f(pageUrl(apiUrl, { tag, page: n, limit }));
                if (!res.ok) {
                    throw new CorpusRequestError(
                        `${res.status} ${res.statusText}`, { status: res.status });
                }
                return res.json();
            },
            staleTime: STALE_MS,
        });
        return normalizePage(raw);
    }

    /**
     * Put freshly-created posts where both this picker and the Archive will find them.
     *
     * An upload lands at the TOP of page 1 (posts sort by `_id` descending), so the honest thing
     * is to invalidate rather than to splice: `['posts']` is the prefix both surfaces share, and
     * the picker separately keeps the returned posts in its own selection so the person's choice
     * does not depend on a refetch landing.
     */
    function invalidate() {
        queryClient.invalidateQueries({ queryKey: ['posts'] });
    }

    return { page, invalidate, live: true };
}

/**
 * The mock. `pages` is an array of raw page bodies, indexed from 1.
 *
 * `failOnPage` makes exactly one page reject, which is how the error state is reached without
 * making every page fail — the interesting case is a corpus that half-loaded, not one that never
 * started.
 */
export function createMockCorpusClient({ pages = [], failOnPage = null, onPage = null } = {}) {
    const requested = [];

    async function page({ tag = null, page: n = 1 } = {}) {
        requested.push({ tag, page: n });
        onPage?.(n);
        if (failOnPage === n) {
            throw new CorpusRequestError('the archive did not answer', { status: 502 });
        }
        return normalizePage(pages[n - 1] || { posts: [], total_pages: pages.length });
    }

    return { page, invalidate: () => {}, live: false, _requested: requested };
}
