import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { API_URL } from '../config/api';
import './WorldPage.css';

/**
 * WAVE4 — the front door: five surfaces made one app a person can walk into.
 *
 * Five views landed in a week — curator, cognition, scene, society, constellation — each with a
 * route and, mostly, no way to reach it. Four of the five had no nav entry at all. This is the
 * orientation: what the engine is, what each surface shows, and a way in.
 *
 * THE ORIENTATION MUST NOT OVERSELL. That is the whole difficulty of a landing page in this
 * project. Every view below is scrupulous about the difference between what was measured and what
 * is settled; a front door that said "explore the world Semant has built" would undo all of it in
 * one sentence, at the one place a person forms their idea of what they are looking at.
 *
 * So the page states the epistemic reality and it reads that reality LIVE rather than asserting it:
 * the counts come from the curator queue, and at the time of writing the honest number is that
 * **nothing has been committed at all**. If someone commits something tomorrow this page says so
 * without being edited, and if the number is still zero it keeps saying zero.
 *
 * LIVENESS IS PROBED, NOT DECLARED. Each surface is checked against its own cheap read endpoint. A
 * view whose backend is not deployed shows as unreachable rather than as a link that fails when
 * clicked — the same discipline the scene view uses for a kind nobody has derived. A hardcoded
 * `live: true` would be a claim about the deployment, made in the frontend, and wrong the first
 * time a route was renamed.
 *
 * Read-only. This page fetches five status endpoints and nothing else.
 */

//: The curator queue's `total` is the length of the page it returned, not an unfiltered count —
//: so asking for one row reports "1 proposal", which is the wrong number stated confidently. Ask
//: for the route's maximum and say "at least" if we hit it, rather than reporting a ceiling as a
//: fact. (Found by reading the rendered page: it said "1 proposal stand in the queue" when 13 do.)
const QUEUE_LIMIT = 1000;

const SURFACES = [
    {
        key: 'scene',
        name: 'Scene',
        to: '/scene',
        probe: '/api/v1/scene/status',
        what: 'A picture, and the relations grounded on it.',
        honest: 'Nesting, adjacency, occlusion and chromatic rhyme drawn on the image they were '
            + 'measured from — solid where the geometry is a mask, dashed where it rests on a box '
            + 'and is only an estimate.',
    },
    {
        key: 'cognition',
        name: 'Cognition',
        to: '/cognition',
        probe: '/api/v1/cognition/temperaments',
        what: 'One agent, walking.',
        honest: 'Where it stood, what it measured there, what it refused, and why it moved on. '
            + 'Its character shapes the route it takes and never what is true along it.',
    },
    {
        key: 'society',
        name: 'Society',
        to: '/society',
        probe: '/api/v1/society/bodies',
        what: 'Differently-bodied agents meeting.',
        honest: 'Each travels to a shared locus, and there what holds between them is partitioned '
            + '— composed, coexistent, or incommensurable. Most pairs do not compose, and the '
            + 'view says so rather than finding agreement.',
    },
    {
        key: 'constellation',
        name: 'Constellation',
        to: '/constellation',
        probe: '/api/v1/constellation/seeds',
        what: 'The neighbourhood an agent can reach.',
        honest: 'The loci reachable from one, stitched by the crossings an agent could actually '
            + 'walk — including the ones it can see and may not take.',
    },
    {
        key: 'curator',
        name: 'Curator',
        to: '/curator',
        probe: `/api/v1/curator/queue?limit=${QUEUE_LIMIT}`,
        what: 'Where a proposal becomes knowledge.',
        honest: 'The one surface in this system that changes what is durably true, and it does so '
            + 'only because a person pressed something. Nothing here commits on its own.',
    },
];

const UNKNOWN = 'unknown';
const LIVE = 'live';
const UNREACHABLE = 'unreachable';

export default function WorldPage() {
    const [status, setStatus] = useState(() =>
        Object.fromEntries(SURFACES.map((s) => [s.key, UNKNOWN])));
    const [ledger, setLedger] = useState(null);

    useEffect(() => {
        let alive = true;
        SURFACES.forEach((surface) => {
            fetch(`${API_URL}${surface.probe}`)
                .then((r) => {
                    if (!alive) return;
                    setStatus((prev) => ({ ...prev, [surface.key]: r.ok ? LIVE : UNREACHABLE }));
                    return surface.key === 'curator' && r.ok ? r.json() : null;
                })
                .then((body) => {
                    // The live epistemic reality, read rather than asserted. `total` is every
                    // proposal the queue holds; the committed count is what a person has accepted.
                    if (alive && body) {
                        setLedger((prev) => ({ ...(prev || {}), proposed: body.total ?? 0,
                                               capped: (body.total ?? 0) >= QUEUE_LIMIT }));
                    }
                })
                .catch(() => {
                    if (alive) setStatus((prev) => ({ ...prev, [surface.key]: UNREACHABLE }));
                });
        });
        return () => { alive = false; };
    }, []);

    useEffect(() => {
        let alive = true;
        fetch(`${API_URL}/api/v1/curator/queue?committed=true&limit=${QUEUE_LIMIT}`)
            .then((r) => (r.ok ? r.json() : null))
            .then((body) => {
                if (alive && body) {
                    setLedger((prev) => ({ ...(prev || {}), committed: body.total ?? 0 }));
                }
            })
            .catch(() => {});
        return () => { alive = false; };
    }, []);

    return (
        <div className="world-page">
            <header className="world-head">
                <p className="world-eyebrow">The simulation engine</p>
                <h1>A world measured from inside its own pictures.</h1>
                <p className="world-lede">
                    Semant puts agents <em>inside</em> photographs. Each one stands at a region,
                    perceives through organs that measure real geometry and real pixels, moves along
                    relations it can prove, and sometimes meets another agent that arrived by a
                    different route and sees differently.
                </p>
            </header>

            <section className="world-truth" aria-labelledby="world-truth-h">
                <h2 id="world-truth-h">What is true here, and what is only proposed</h2>
                <div className="world-truth-body">
                    <p>
                        Every claim in this system carries two statuses, and they are not the same
                        thing. An organ's reading is <b>measured</b> when the geometry supports it —
                        a mask, not a bounding box — and <b>interpretive</b> when it does not. That
                        is what the machine can say for itself.
                    </p>
                    <p>
                        Separately, every claim is <b>proposed</b> until a person accepts it, at
                        which point it is <b>committed</b> and becomes part of the shared record.
                        Nothing commits on its own. There is exactly one route in the system that
                        can change a durable status, and it runs through the curator.
                    </p>
                    <LedgerReality ledger={ledger} />
                </div>
            </section>

            <section className="world-surfaces" aria-labelledby="world-surfaces-h">
                <h2 id="world-surfaces-h">Five ways in</h2>
                <ul className="world-grid">
                    {SURFACES.map((surface) => (
                        <SurfaceCard key={surface.key} surface={surface}
                                     state={status[surface.key]} />
                    ))}
                </ul>
            </section>

            <footer className="world-foot">
                <p>
                    Each surface reads; only the curator writes. None of them measures anything —
                    the organs did that, and every view shows their work at the status the work
                    actually supports.
                </p>
            </footer>
        </div>
    );
}

function LedgerReality({ ledger }) {
    if (!ledger) {
        return (
            <p className="world-count world-count--pending">
                Reading the ledger…
            </p>
        );
    }
    const { proposed = 0, committed = 0, capped = false } = ledger;
    return (
        <p className={`world-count${committed === 0 ? ' world-count--none' : ''}`}>
            {capped ? 'At least ' : ''}<b>{proposed}</b>{' '}
            proposal{proposed === 1 ? '' : 's'} {proposed === 1 ? 'stands' : 'stand'} in the
            queue. <b>{committed}</b> {committed === 1 ? 'has' : 'have'} been committed.
            {committed === 0 && (
                <>
                    {' '}
                    <span>
                        Nothing has been accepted yet — so nearly everything you are about to see
                        is a proposal about a photograph, not a fact about the world. That is the
                        honest state of it, and this line is read from the queue rather than
                        written here.
                    </span>
                </>
            )}
        </p>
    );
}

function SurfaceCard({ surface, state }) {
    const reachable = state === LIVE;
    const body = (
        <>
            <span className="world-card-head">
                <span className="world-card-name">{surface.name}</span>
                <SurfaceState state={state} />
            </span>
            <span className="world-card-what">{surface.what}</span>
            <span className="world-card-honest">{surface.honest}</span>
        </>
    );

    return (
        <li className={`world-card${reachable ? '' : ' is-unreachable'}`}>
            {reachable ? (
                <Link to={surface.to}>{body}</Link>
            ) : (
                // NOT a link. A surface whose backend does not answer is shown as what it is
                // rather than as a door that fails when opened.
                <div aria-disabled="true">{body}</div>
            )}
        </li>
    );
}

function SurfaceState({ state }) {
    if (state === LIVE) return <span className="world-state" data-state="live">live</span>;
    if (state === UNREACHABLE) {
        return (
            <span className="world-state" data-state="unreachable"
                  title="this surface's backend did not answer">
                not answering
            </span>
        );
    }
    return <span className="world-state" data-state="unknown">checking…</span>;
}
