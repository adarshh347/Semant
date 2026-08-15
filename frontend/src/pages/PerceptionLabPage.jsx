import React, { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import PerceptionLab, { createFixtureClient } from '../perceptionLab';
import { createHttpLabClient } from '../perceptionLab/clients/httpClient';
import './PerceptionLabPage.css';

/**
 * PERCEPTUAL-ORGANS-002 Lane F2 — the Perception Lab, mounted.
 *
 * The whole integration is what Lane E said it would be: one import and one element. This file
 * exists for the three things a ROUTE owns and the instrument does not.
 *
 * ── 1. WHICH WIRE, CHOSEN ONCE AND STATED LOUDLY ────────────────────────────
 *
 * The default is LIVE. `?client=fixture` gives the deterministic wire, which is not a debug flag
 * to be embarrassed about: it is how the responsive proof, the human rehearsal and anyone without
 * a backend read this surface, and it is the only way to demonstrate a `failed` stage without
 * breaking a model.
 *
 * WHAT CANNOT HAPPEN IS A SWITCH NOBODY ASKED FOR. There is no fallback here. A backend that is
 * down produces an error inside the laboratory, with nothing on the page pretending to be a
 * measurement; it does not quietly become the fixture wire while the badge still says LIVE. That
 * would be the single most damaging thing this route could do, and it would look like everything
 * working.
 *
 * ── 2. THE BADGE, AT THE TOP, IN WORDS ──────────────────────────────────────
 *
 * The shell puts `client: LIVE` in its own header and the run's own identity beside the run, and
 * those two are right where they are. This banner is the third thing neither of them says: what
 * being on this wire MEANS — that pressing run reaches a model, or that it does not.
 *
 * ── 3. THE ARCHIVE IS ONE ARCHIVE ───────────────────────────────────────────
 *
 * An image uploaded through ⌘K while this page is open is a real post, and the laboratory's source
 * list was read when it mounted. Rather than silently going stale, the page hears
 * `semant:posts-created` — the shell's own upload event — and says so. It does not reach into the
 * laboratory's state to inject a row: the lab's list is what the backend answered, and a row this
 * page pushed in would be a source identity invented in the browser.
 */
export default function PerceptionLabPage() {
    const [params] = useSearchParams();
    const wire = params.get('client') === 'fixture' ? 'FIXTURE' : 'LIVE';
    const [arrived, setArrived] = useState(0);

    // One client per wire, for the life of the mount. `useLabSession` re-reads sources and
    // capabilities whenever the client object changes, so a fresh one on every render would put
    // the laboratory into a permanent loading state.
    const client = useMemo(
        () => (wire === 'FIXTURE' ? createFixtureClient() : createHttpLabClient()),
        [wire]);

    useEffect(() => {
        const onCreated = (event) => {
            const posts = Array.isArray(event?.detail?.posts) ? event.detail.posts : [];
            // The lab's own upload already put its source in the list — it went through this
            // page's client and came back with a digest. This counter is for the OTHER uploads:
            // the ones a person started from ⌘K or the Archive while this page was open.
            if (posts.length) setArrived((n) => n + posts.length);
        };
        window.addEventListener('semant:posts-created', onCreated);
        return () => window.removeEventListener('semant:posts-created', onCreated);
    }, []);

    return (
        <div className="plab-page" data-wire={wire}>
            <div className="plab-wire" role="status" data-lab-wire={wire}>
                <span className="plab-wire-badge" data-identity={wire}>{wire}</span>
                {wire === 'LIVE' ? (
                    <span className="plab-wire-text">
                        This laboratory is wired to the real organs. <strong>Run LIVE</strong> calls
                        a segmenter and measures this image; every artifact it makes is
                        session-local and nothing here can write to a post. A run re-shown from the
                        ledger carries its own <strong>REPLAY</strong> badge, because that is a
                        different question from this one.
                    </span>
                ) : (
                    <span className="plab-wire-text">
                        This laboratory is reading committed scenes. <strong>Nothing here calls a
                        model</strong> and nothing reaches the archive — it is the deterministic
                        wire, for reading the surface without a backend.{' '}
                        <a className="plab-wire-link" href="/lab/perception">Switch to LIVE</a>
                    </span>
                )}
            </div>

            {arrived ? (
                <p className="plab-arrived" role="status" data-sources-arrived={arrived}>
                    {arrived} image{arrived === 1 ? '' : 's'} {arrived === 1 ? 'was' : 'were'} added
                    to the archive while this page was open. Reload to list{' '}
                    {arrived === 1 ? 'it' : 'them'} here — this page will not invent a row for an
                    image it has not read the digest of.
                </p>
            ) : null}

            <PerceptionLab client={client} />
        </div>
    );
}
