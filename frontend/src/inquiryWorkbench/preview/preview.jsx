import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import InquiryWorkbenchPage from '../InquiryWorkbenchPage.jsx';
import { createMockInquiryClient } from '../inquiryClient.js';
import {
    compilingFixture, consultFixture, respondedFixture, completedFixture, autoFixture,
    outcomesFixture, measuredEvidenceFixture, simulatedEvidenceFixture, unknownFutureFixture,
    conflictSessionFixture, duplicateSessionFixture, otherDomainFixture,
    runningStagesFixture, truncatedCompilerFixture, barrenFixture, stagedCompleteFixture,
    dissolvedFixture, unknownStageFixture,
} from '../inquiryFixtures.js';
import { createMockCorpusClient } from '../../inquiryCorpus/corpusClient.js';
import '../../index.css';
import './preview.css';

/**
 * INQUIRY WORKBENCH — the development preview.
 *
 * A story picker over the lane's fixtures, mounted through the mock client so the whole surface
 * behaves exactly as it does in the DOM tests — the same `respond` round trip, the same conflict,
 * the same resume.
 *
 * ## Why this exists at all, given the no-fixture-fallback rule
 *
 * Those two things are not in tension, they are the same discipline. The PRODUCTION page must
 * never substitute a fixture for an absent backend, because that turns an outage into a
 * convincing demonstration. A preview whose entire frame says DEVELOPMENT PREVIEW, which lives in
 * a file `vite build` never walks, and which cannot be reached from any route, takes nothing away
 * from that — it is what makes the rule affordable, since otherwise the only way to see the
 * design would be to soften it.
 *
 * The banner is not dismissible and is rendered outside the page component, so no state inside
 * the workbench can remove it.
 */

const STORIES = [
    // HARNESS-003C — the mechanism states, first, because they are what this phase repaired.
    ['running-stages', 'Working — the theorist mid-way through four images',
        { script: [runningStagesFixture()] }],
    ['truncated', 'Truncated — a rich reading, then a compiler that stopped mid-sentence',
        { script: [truncatedCompilerFixture()] }],
    ['barren', 'Barren — the reading compiled into nothing at all',
        { script: [barrenFixture()] }],
    ['dissolved', 'Dissolved — the whole chain, source units through synthesis',
        { script: [dissolvedFixture()] }],
    ['staged-complete', 'Complete — with its whole stage ledger',
        { script: [stagedCompleteFixture()] }],
    ['unknown-stage', 'A future server — an unrecognised stage and outcome',
        { script: [unknownStageFixture()] }],
    ['entry', 'The entry — the whole archive, paged, with upload-and-include',
        { script: [runningStagesFixture()], stayOnEntry: true }],

    ['awaiting-user', 'Awaiting user — a consult session paused at a fork',
        { script: [consultFixture()], afterResponse: respondedFixture() }],
    ['completed', 'Completed — answer, citations and remainder',
        { script: [completedFixture()] }],
    ['compiling', 'Working — compiling, nothing blocked yet',
        { script: [compilingFixture()] }],
    ['auto', 'Auto — the system chose, and says so',
        { script: [autoFixture()] }],
    ['responded', 'Resumed — after a choice, with one simulated receipt',
        { script: [respondedFixture()] }],
    ['outcomes', 'The five nothings — empty, unavailable, refused, gap, simulated',
        { script: [outcomesFixture()] }],
    ['conflict-stale', 'Conflict (stale) — the session moved, the decision is still open',
        {
            script: [consultFixture()], afterResponse: respondedFixture(),
            conflictOnce: true, conflictSession: conflictSessionFixture(),
        }],
    ['conflict-duplicate', 'Conflict (duplicate) — answered in another tab',
        {
            script: [consultFixture()], afterResponse: respondedFixture(),
            conflictOnce: true, conflictSession: duplicateSessionFixture(),
        }],
    ['measured', 'Phase 2 shape — a live, usable evidence object',
        { script: [measuredEvidenceFixture()] }],
    ['simulated-evidence', 'An evidence-shaped object minted from a fixture',
        { script: [simulatedEvidenceFixture()] }],
    ['unknown-future', 'A future server — unrecognised state, kind, status and mode',
        { script: [unknownFutureFixture()] }],
    ['other-domain', 'An unrelated domain, through identical types',
        { script: [otherDomainFixture()] }],
];

/**
 * A three-page archive, so paging, the end state and the scope note are all reachable by hand.
 * Cloudinary URLs so the thumbnail transforms are exercised as they are in the app.
 */
const CORPUS_PAGES = [1, 2, 3].map((page) => ({
    posts: Array.from({ length: page === 3 ? 2 : 6 }, (_, i) => {
        const n = (page - 1) * 6 + i + 1;
        return {
            id: `post_${n}`,
            photo_url: `https://res.cloudinary.com/demo/image/upload/v1/sample.jpg#${n}`,
            text_blocks: n % 3 === 0 ? [] : [{ content: `<p>Archive image ${n}</p>` }],
            general_tags: n % 3 === 0 ? [] : ['schinkel', 'berlin'],
            instagram_handle: n % 2 === 0 ? 'archivist' : '',
            region_annotations: n % 4 === 0 ? [{}, {}] : [],
        };
    }),
    total_pages: 3,
    current_page: page,
}));

/** Never resolves, so the entry story stays on the entry form to be looked at. */
const stalledClient = {
    start: () => new Promise(() => {}),
    get: () => new Promise(() => {}),
    respond: () => new Promise(() => {}),
    watch: () => () => {},
    live: false,
};

export function Preview() {
    const initial = new URLSearchParams(window.location.search).get('story') || 'awaiting-user';
    const [storyId, setStoryId] = useState(initial);
    const [, setNonce] = useState(0);

    const story = STORIES.find(([id]) => id === storyId) || STORIES[0];
    // A fresh client per story, and a fresh one on Reset: the mock is stateful (it remembers
    // whether it has been responded to), so reusing one across stories would show a session that
    // had already moved on.
    const client = useMemo(() => createMockInquiryClient(story[2]), [story]);
    // `story` is the intended reset key: the mock is stateful — it remembers which pages it has
    // served — so switching stories must build a fresh one even though the pages are constant.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    const corpusClient = useMemo(() => createMockCorpusClient({ pages: CORPUS_PAGES }), [story]);

    return (
        <>
            <div className="iwp-banner" role="note">
                <b>DEVELOPMENT PREVIEW</b>
                <span>
                    Fixture data through a mock client. Not the production surface, not routed,
                    and never served by a build — the real page shows an explicit unavailable
                    state when the API is missing.
                </span>
            </div>

            <div className="iwp-bar">
                <label htmlFor="iwp-story">Story</label>
                <select
                    id="iwp-story"
                    value={storyId}
                    onChange={(e) => {
                        setStoryId(e.target.value);
                        const url = new URL(window.location.href);
                        url.searchParams.set('story', e.target.value);
                        window.history.replaceState({}, '', url);
                    }}
                >
                    {STORIES.map(([id, label]) => (
                        <option key={id} value={id}>{label}</option>
                    ))}
                </select>
                <button type="button" onClick={() => setNonce((n) => n + 1)}>Reset</button>
                <span className="iwp-hint">
                    Press Begin to start — the entry form is real, only the network is mocked.
                </span>
            </div>

            <InquiryWorkbenchPage
                key={`${storyId}`}
                client={story[2].stayOnEntry ? stalledClient : client}
                corpusClient={corpusClient}
            />
        </>
    );
}

createRoot(document.getElementById('root')).render(<Preview />);
