import React from 'react';
import { EPISTEMIC_ORDER, EPISTEMIC_LABEL, epistemicCounts, refusedRecords } from './runContract';

/** An unknown is an em dash, never a zero. See runContract.numOrNull for why this matters. */
const val = (v, suffix = '') => (v === null || v === undefined ? '—' : `${v}${suffix}`);

/**
 * AGENT-DEMO — "the actuator tells, in full detail, what it produced."
 *
 * One row per executed step: what it was called with, what it read, what it minted (with M5's
 * epistemic tag and a confidence), which model and adapter actually ran, how long it took, and —
 * when it refused — the reason and the detail.
 *
 * A REFUSAL IS A RESULT, and is rendered as one. It is not an error state, not a gap, and not
 * something to grey out: a producer that declined to trace a projective frame across a flat wall
 * has told you something true about the picture. Hiding it would leave a reader believing the
 * step never ran, which is the opposite of transparency. So refusals get their own visible
 * treatment and a count in the summary.
 *
 * Likewise a step that produced NOTHING but did not refuse is shown, with "produced nothing"
 * stated. The alternative — omitting empty rows — would quietly make the run look tidier than it
 * was.
 */
export default function ProductionPanel({ records = [], open = true }) {
    const counts = epistemicCounts({ production_records: records });
    const refused = refusedRecords({ production_records: records });
    const present = EPISTEMIC_ORDER.filter((k) => counts[k]);

    return (
        <section className="ad-prod" aria-label="What each step produced">
            <header className="ad-prod-head">
                <h2 className="ad-h2">What it did, step by step</h2>
                <div className="ad-prod-summary">
                    <span className="ad-chip">{records.length} steps</span>
                    {present.map((k) => (
                        <span className={`ad-chip ad-chip--${k}`} key={k}>
                            {counts[k]} {EPISTEMIC_LABEL[k].toLowerCase()}
                        </span>
                    ))}
                    {refused.length ? (
                        <span className="ad-chip ad-chip--refused">{refused.length} refused</span>
                    ) : null}
                </div>
            </header>

            {records.length === 0 ? (
                <p className="ad-quiet">No steps have run yet.</p>
            ) : (
                <ul className="ad-prod-list">
                    {records.map((r) => (
                        <li
                            className={`ad-prod-row${r.refusal ? ' is-refused' : ''}`}
                            key={r.step_id || r.actuator}
                            data-step-id={r.step_id}
                        >
                            <div className="ad-prod-top">
                                <span className="ad-actuator">{r.actuator}</span>
                                <span className="ad-step-id" title="The plan step that produced this">
                                    {r.step_id || '—'}
                                </span>
                                <span className="ad-latency">{val(r.latency_ms, ' ms')}</span>
                            </div>

                            <dl className="ad-prod-meta">
                                <div><dt>model</dt><dd>{val(r.model)}</dd></div>
                                <div><dt>adapter</dt><dd>{val(r.adapter)}</dd></div>
                                <div>
                                    <dt>read</dt>
                                    <dd>{r.consumed.length ? r.consumed.join(', ') : '—'}</dd>
                                </div>
                            </dl>

                            {r.refusal ? (
                                <p className="ad-refusal">
                                    <span className="ad-refusal-tag">refused · {r.refusal.reason}</span>
                                    <span className="ad-refusal-detail">{r.refusal.detail}</span>
                                </p>
                            ) : r.produced.length === 0 ? (
                                // Ran, declined nothing, and left nothing behind. Said, not hidden.
                                <p className="ad-quiet ad-produced-none">Produced nothing.</p>
                            ) : (
                                <ul className="ad-produced">
                                    {r.produced.map((p, n) => (
                                        // KEYED ON `ref`, NEVER ON `id`. A quarantined suggestion
                                        // has no id by design (`run_surface._suggestion_ref`), so
                                        // against a live run every row in this list would key on
                                        // the same empty string and React could not tell them
                                        // apart while the panel streams. `ref` (`run:step#n`) is
                                        // the run-local handle that exists for exactly this. The
                                        // index tail is the last resort for a pre-`ref` record,
                                        // not the normal path.
                                        <li className="ad-produced-item" key={p.ref || `${p.id}#${n}`}>
                                            <span className={`ad-epi ad-epi--${p.epistemic_status}`}>
                                                {EPISTEMIC_LABEL[p.epistemic_status] || p.epistemic_status || '—'}
                                            </span>
                                            <span className="ad-produced-kind">{p.kind || '—'}</span>
                                            {/* The id when it HAS one — an accepted, stored
                                                descriptor — and the run-local ref when it does
                                                not. Showing an empty cell for every quarantined
                                                item read as "this produced something nameless";
                                                showing the ref says what it actually is. */}
                                            <span className="ad-produced-id">{p.id || p.ref}</span>
                                            <span className="ad-produced-conf">
                                                {p.confidence === null ? '—' : p.confidence.toFixed(2)}
                                            </span>
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </li>
                    ))}
                </ul>
            )}
        </section>
    );
}
