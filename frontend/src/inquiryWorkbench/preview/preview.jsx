import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import InquiryWorkbenchPage from '../InquiryWorkbenchPage.jsx';
import { createMockInquiryClient } from '../inquiryClient.js';
import {
    compilingFixture, consultFixture, respondedFixture, completedFixture, autoFixture,
    outcomesFixture, measuredEvidenceFixture, simulatedEvidenceFixture, unknownFutureFixture,
    conflictSessionFixture, duplicateSessionFixture, otherDomainFixture, FIXTURE_CORPUS,
} from '../inquiryFixtures.js';
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

const POSTS = FIXTURE_CORPUS.map((c) => ({
    id: c.post_id, photo_url: c.image_url, title: c.title, region_annotations: [],
}));

export function Preview() {
    const initial = new URLSearchParams(window.location.search).get('story') || 'awaiting-user';
    const [storyId, setStoryId] = useState(initial);
    const [, setNonce] = useState(0);

    const story = STORIES.find(([id]) => id === storyId) || STORIES[0];
    // A fresh client per story, and a fresh one on Reset: the mock is stateful (it remembers
    // whether it has been responded to), so reusing one across stories would show a session that
    // had already moved on.
    const client = useMemo(() => createMockInquiryClient(story[2]), [story]);

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

            <InquiryWorkbenchPage key={`${storyId}`} client={client} posts={POSTS} />
        </>
    );
}

createRoot(document.getElementById('root')).render(<Preview />);
