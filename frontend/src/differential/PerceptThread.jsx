import React, { useMemo } from 'react';
import { buildCirculationThread, threadSummary, recordsOf, judgementsOf, VOICE } from './circulationThread';
import { buildPerceptPacket } from './perceptPacket';
import { resolveGround } from './grounds';

/**
 * PerceptThread — the Circulation Thread for one percept.
 *
 * CIRCUIT-001 P1D. Render only: every value comes from the pure builder, so the
 * rules that matter (no causation, records vs judgements, degradation-only) are
 * pinned by `circulationThread.test.js` rather than by looking at the screen.
 *
 * RESTING is one quiet line, because most of the time a curator is composing,
 * not auditing. EXPANDED is the relation chain, records above judgements, in two
 * visibly different voices — a record is something observed, a judgement is
 * something concluded, and a surface that renders them identically teaches the
 * reader to trust them equally.
 *
 * Deliberately NOT a timeline: rows are ordered by the question a reader would
 * ask, not by when anything happened, and nothing is joined by an arrow.
 */
export default function PerceptThread({ percept, grounds = [], regions = [], mentions = [], postId = null }) {
    // The packet is built here, unsent, purely so the thread can report that it
    // exists and what it would ask. Nothing dispatches in P1D.
    const packet = useMemo(() => buildPerceptPacket(percept, {
        postId, grounds, mentions,
        resolve: (g) => resolveGround(g, { regions, grounds }),
    }), [percept, postId, grounds, mentions, regions]);

    const thread = useMemo(() => buildCirculationThread(percept, {
        grounds, regions, mentions, packet,
    }), [percept, grounds, regions, mentions, packet]);

    if (!thread.length) return null;

    const records = recordsOf(thread);
    const judgements = judgementsOf(thread);
    // Only a real degradation earns attention on the closed line; "not assessed"
    // is honest but is not news, and must not make a healthy percept look sick.
    const hasDegradation = judgements.some((l) => l.state === 'degraded');

    return (
        <details className={`diff-thread${hasDegradation ? ' has-degraded' : ''}`}>
            <summary className="diff-thread-summary">{threadSummary(thread)}</summary>
            <div className="diff-thread-body">
                {[...records, ...judgements].map((l, i) => (
                    <p key={`${l.relation}-${i}`} className={`diff-thread-row diff-thread-row--${l.voice} is-${l.state}`}>
                        <span className="diff-thread-voice">
                            {l.voice === VOICE.RECORD ? 'Record' : 'Judgement'}
                        </span>
                        <span className="diff-thread-text">{l.text}</span>
                    </p>
                ))}
                {packet && (
                    <details className="diff-packet">
                        <summary>the packet, as it would be asked</summary>
                        <pre className="diff-packet-body">{JSON.stringify(packet, null, 2)}</pre>
                    </details>
                )}
            </div>
        </details>
    );
}
