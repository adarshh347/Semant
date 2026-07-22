import React, { useMemo } from 'react';
import { Play } from 'lucide-react';
import PerceptThread from './PerceptThread';
import { resolveGround } from './grounds';
import { groundRoleList, roleLabel } from './groundRoles';
import { buildPerceptPacket } from './perceptPacket';
import { blockIdsForPercept } from '../state/perceptMentions';
import './PerceptWorkshop.css';

/**
 * PerceptWorkshop — CIRCUIT-001 P2.
 *
 * A percept as a living unit of attention rather than a line of text with buttons after it.
 * Everything here is derived from state that already exists; nothing new is stored, and the
 * builders (`resolveGround`, `groundRoleList`, `buildPerceptPacket`, `blockIdsForPercept`)
 * are the same ones their own suites already pin.
 *
 * The display rules it inherits, and must not quietly break:
 *
 *  - **Degradation-only.** A healthy percept shows what it cites and nothing about health.
 *    No green ticks, no "verified", no badge that announces a nominal state — because a
 *    surface that announces everything teaches the reader to skim the one line that matters.
 *  - **Absence is stated, never explained.** "no longer resolves", never a cause.
 *  - **In writing is derived from the live mentions**, not from a sent flag: a flag would go
 *    on claiming the crossing after the chip was deleted.
 *  - **Nothing here dispatches.** The packet is inspectable and unsent; the thread reports
 *    that it exists and what it would ask.
 */
export default function PerceptWorkshop({
    percepts = [], grounds = [], regions = [], mentions = [], postId = null,
    onPlay = null, onSendToManuscript = null,
}) {
    if (!percepts.length) return null;
    return (
        <div className="pw">
            <span className="pw-eyebrow">Percepts</span>
            {percepts.map((p) => (
                <PerceptCard
                    key={p.id} percept={p} grounds={grounds} regions={regions}
                    mentions={mentions} postId={postId}
                    onPlay={onPlay} onSendToManuscript={onSendToManuscript}
                />
            ))}
        </div>
    );
}

function PerceptCard({ percept, grounds, regions, mentions, postId, onPlay, onSendToManuscript }) {
    const resolve = useMemo(
        () => (g) => resolveGround(g, { regions, grounds }),
        [regions, grounds],
    );

    // What this noticing rests on, and what each ground DOES for it. `groundRoleList`
    // returns one row per cited ground whether or not a role was named, so an unnamed
    // ground is still visible as evidence rather than silently dropped.
    const cited = useMemo(
        () => groundRoleList(percept, grounds, resolve),
        [percept, grounds, resolve],
    );
    const named = cited.filter((c) => c.role);
    const detached = cited.filter((c) => c.detached);

    // Derived from the live mention set every render — see the header note.
    const blockCount = useMemo(
        () => blockIdsForPercept(mentions, percept.id).size,
        [mentions, percept.id],
    );

    const packet = useMemo(() => buildPerceptPacket(percept, {
        postId, grounds, mentions, resolve,
    }), [percept, postId, grounds, mentions, resolve]);

    return (
        <article className={`pw-card${detached.length ? ' has-degraded' : ''}`}>
            <header className="pw-head">
                {onPlay && (
                    <button
                        type="button" className="pw-play"
                        title="Replay this noticing on the image"
                        aria-label="Replay this noticing on the image"
                        onClick={() => onPlay(percept.id)}
                    >
                        <Play size={11} />
                    </button>
                )}
                <p className="pw-expression">{percept.expression}</p>
            </header>

            <div className="pw-facts">
                <span className="pw-fact">
                    {cited.length} ground{cited.length !== 1 ? 's' : ''}
                </span>
                {/* Degradation-only: this line is absent entirely when nothing is detached. */}
                {detached.length > 0 && (
                    <span className="pw-fact pw-fact--degraded">
                        {detached.length} no longer resolve{detached.length === 1 ? 's' : ''}
                    </span>
                )}
                {blockCount > 0 && (
                    <span className="pw-fact pw-fact--writing">
                        in writing · {blockCount} passage{blockCount !== 1 ? 's' : ''}
                    </span>
                )}
                {(percept.properties || []).length > 0 && (
                    <span className="pw-fact pw-fact--props">{percept.properties.join(' · ')}</span>
                )}
            </div>

            {/* Roles belong to THIS percept's use of a ground — the same region is an anchor
                in one noticing and a counterforce in another — so they are shown inside the
                percept and never beside the ground. */}
            {named.length > 0 && (
                <ul className="pw-roles">
                    {named.map((c) => (
                        <li key={c.ground_id} className={`pw-role${c.detached ? ' is-detached' : ''}`}>
                            <span className="pw-role-name">{roleLabel(c.role)}</span>
                            <span className="pw-role-ground">{c.label || c.ground_type || 'ground'}</span>
                        </li>
                    ))}
                </ul>
            )}

            <div className="pw-actions">
                {onSendToManuscript && (
                    <button
                        type="button" className="pw-write"
                        title="Carry this noticing into the writing"
                        onClick={() => onSendToManuscript(percept)}
                    >
                        Write from this
                    </button>
                )}
            </div>

            {/* The full two-voice thread, and the unsent packet inside it. */}
            <PerceptThread
                percept={percept} grounds={grounds} regions={regions}
                mentions={mentions} postId={postId}
            />

            {/* Named separately from the thread's own disclosure so a curator can ask the
                one question the orchestration layer is for — "what would be sent?" —
                without reading the whole chain. Still unsent: there is no dispatch. */}
            {packet && (
                <details className="pw-packet">
                    <summary>What would be sent, if asking were enabled</summary>
                    <pre className="pw-packet-body">{JSON.stringify(packet, null, 2)}</pre>
                </details>
            )}
        </article>
    );
}
