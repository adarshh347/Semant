import React, { useState } from 'react';
import { LifecycleChip, VerdictChip } from './Chips';
import { LIFECYCLE_STATES, REVIEW_VERDICTS } from '../contract/perceptionLabContract';
import { describe, LIFECYCLE, VERDICT } from '../display';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — a verdict, and separately, a curation state.
 *
 * THIS COMPONENT IS TWO PANELS ON PURPOSE, and they are two panels because "mark correct and keep"
 * is one button away from being the same button. It is the single easiest collapse to build and
 * the hardest to notice afterwards, because both actions feel like approval:
 *
 *   VERDICT     what a person judged. It changes NOTHING: not the epistemic status, not the
 *               lifecycle, not the measurement. It is a separate record keyed by artifact_id.
 *   LIFECYCLE   what the laboratory is doing with the record. `kept` is a filing decision. It is
 *               not `correct`, and `rejected` is not `wrong` — a correct measurement of the wrong
 *               thing gets rejected, and a wrong one is kept as evidence.
 *
 * `promoted` appears in the lifecycle list and is NOT offered as a control. Hiding it would let a
 * person believe this laboratory can promote; showing it disabled says the state exists, that
 * Semant owns it, and that nothing here reaches it.
 *
 * A CORRECTION IS NOT A MEASUREMENT. The corrections editor records field, was, now and a note —
 * it does not write the new value anywhere, and the artifact is untouched. What a person believes
 * the answer should have been is evidence about the organ, not a repair of the record.
 */
export default function ReviewTray({ artifact, reviews = [], onReview, onLifecycle, busy }) {
    const [verdict, setVerdict] = useState(null);
    const [notes, setNotes] = useState('');
    const [corrections, setCorrections] = useState([]);
    const [draft, setDraft] = useState({ field: '', was: '', now: '', note: '' });

    if (!artifact) return null;
    const id = artifact.identity.artifact_id;
    const last = reviews[reviews.length - 1] || null;

    const submit = () => {
        if (!verdict || busy) return;
        onReview(id, verdict, notes, corrections);
        setVerdict(null); setNotes(''); setCorrections([]);
    };

    return (
        <section className="pl-panel" aria-label="Review and lifecycle" data-review-tray
            data-artifact={id}>
            <div className="pl-panel-head">
                <h2 className="pl-panel-title">Review</h2>
                <span className="pl-chiprow">
                    {last ? <VerdictChip verdict={last.verdict} /> : (
                        <span className="pl-chip" data-unjudged>unjudged</span>
                    )}
                </span>
            </div>

            <fieldset className="pl-field" data-verdict-picker>
                <legend className="pl-label">What do you make of it?</legend>
                <div className="pl-verdicts" role="group" aria-label="Verdict">
                    {REVIEW_VERDICTS.map((v) => (
                        <button key={v} type="button" className="pl-btn"
                            data-verdict-option={v} aria-pressed={verdict === v}
                            title={describe(VERDICT, v).hint}
                            onClick={() => setVerdict(v)}>
                            {describe(VERDICT, v).label}
                        </button>
                    ))}
                </div>
                <div className="pl-field">
                    <label className="pl-label" htmlFor="pl-review-notes">Why</label>
                    <textarea id="pl-review-notes" className="pl-textarea" rows={2} value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        placeholder="what you saw, in your words" />
                </div>

                <div className="pl-field" data-corrections>
                    <span className="pl-label">Corrections</span>
                    {corrections.length ? (
                        <ul className="pl-list">
                            {corrections.map((c, i) => (
                                <li key={i} className="pl-step-why" data-correction={c.field}>
                                    <code>{c.field}</code>: was <code>{c.was}</code>, should be{' '}
                                    <code>{c.now}</code>
                                    {c.note ? ` — ${c.note}` : ''}
                                </li>
                            ))}
                        </ul>
                    ) : null}
                    <div className="pl-btnrow">
                        <input className="pl-input" data-correction-field placeholder="field"
                            aria-label="field" value={draft.field}
                            onChange={(e) => setDraft({ ...draft, field: e.target.value })} />
                        <input className="pl-input" data-correction-was placeholder="was"
                            aria-label="was" value={draft.was}
                            onChange={(e) => setDraft({ ...draft, was: e.target.value })} />
                        <input className="pl-input" data-correction-now placeholder="should be"
                            aria-label="should be" value={draft.now}
                            onChange={(e) => setDraft({ ...draft, now: e.target.value })} />
                        <button type="button" className="pl-btn" data-action="add-correction"
                            disabled={!draft.field || !draft.now}
                            onClick={() => {
                                setCorrections((prev) => [...prev, draft]);
                                setDraft({ field: '', was: '', now: '', note: '' });
                            }}>
                            Note it
                        </button>
                    </div>
                    <p className="pl-panel-sub">
                        A correction is <strong>evidence about the organ</strong>, not a repair of
                        the record. Nothing here writes the new value anywhere, and the
                        measurement above is untouched by it.
                    </p>
                </div>

                <div className="pl-btnrow">
                    <button type="button" className="pl-btn pl-btn--primary"
                        data-action="record-verdict" disabled={!verdict || !!busy}
                        onClick={submit}>
                        Record this verdict
                    </button>
                </div>
                <p className="pl-axisnote" data-verdict-consequence>
                    A verdict changes nothing. Not the epistemic status, not the lifecycle, not the
                    measurement. It is a separate record with your name and the time on it.
                </p>
            </fieldset>

            <fieldset className="pl-field" data-lifecycle-picker>
                <legend className="pl-label">
                    What should the laboratory do with the record?
                </legend>
                <span className="pl-chiprow">
                    <LifecycleChip status={artifact.lifecycle.status} />
                </span>
                <div className="pl-verdicts" role="group" aria-label="Lifecycle">
                    {LIFECYCLE_STATES.map((s) => {
                        // `promoted` is shown and never offered. Removing it would let a person
                        // believe this laboratory has no such state; disabling it says the state
                        // exists, Semant owns it, and nothing on this page reaches it.
                        const reachable = s !== 'promoted';
                        return (
                            <button key={s} type="button" className="pl-btn"
                                data-lifecycle-option={s}
                                aria-pressed={artifact.lifecycle.status === s}
                                disabled={!reachable || !!busy}
                                title={reachable
                                    ? describe(LIFECYCLE, s).hint
                                    : 'Semant owns this state. Nothing in this laboratory can '
                                        + 'reach it, and there is no control here that could.'}
                                onClick={() => reachable && onLifecycle(id, s)}>
                                {describe(LIFECYCLE, s).label}
                            </button>
                        );
                    })}
                </div>
                <p className="pl-axisnote" data-lifecycle-consequence>
                    A filing decision in this session’s ledger. <code>kept</code> is not{' '}
                    <code>correct</code> and <code>rejected</code> is not <code>wrong</code>: a
                    correct measurement of the wrong thing gets rejected, and a wrong one is kept
                    as evidence.
                </p>
            </fieldset>

            {reviews.length ? (
                <div className="pl-field" data-review-history>
                    <span className="pl-label">Every verdict recorded on this artifact</span>
                    <ul className="pl-list">
                        {reviews.map((r) => (
                            <li key={r.review_id} className="pl-turn" data-past-review={r.review_id}>
                                <span className="pl-chiprow">
                                    <VerdictChip verdict={r.verdict} />
                                    <span className="pl-chip">{r.reviewer}</span>
                                    <span className="pl-chip">{r.reviewed_at}</span>
                                </span>
                                {r.notes ? <span className="pl-turn-text">{r.notes}</span> : null}
                                {r.corrections.map((c, i) => (
                                    <span key={i} className="pl-step-why"
                                        data-past-correction={c.field}>
                                        <code>{c.field}</code>: {c.was} → {c.now}
                                    </span>
                                ))}
                            </li>
                        ))}
                    </ul>
                    <p className="pl-panel-sub">
                        Verdicts accumulate; they do not overwrite. Two people disagreeing is a
                        finding, and a surface that kept only the latest would have deleted it.
                    </p>
                </div>
            ) : null}
        </section>
    );
}
