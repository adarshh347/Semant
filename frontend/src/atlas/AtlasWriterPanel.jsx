import React from 'react';

import ArticleView from '../article/ArticleView.jsx';
import {
    acceptState, blockerText, draftSummary, isAccepted, isQuarantined, refusalLines, seedStubs,
} from './atlasDraft.js';

/**
 * ATLAS C5 — the writer: the accepted plan, drafted into prose, on the canvas.
 *
 * A SURFACE OVER M3 AND M4, AND NOTHING ELSE. It does not compose, does not decide what a sentence
 * may rest on, and does not draw an article: `ArticleView` is M4's renderer and is mounted here
 * unchanged, so the document the writer reviews on the canvas is byte-for-byte the document the
 * export produces. A second renderer "tuned for the panel" would be a place for the two to differ,
 * and the one they would differ about is how much evidence is actually live.
 *
 * THE QUARANTINE IS THE LAYOUT. Before Accept the prose is a proposal and is rendered read-only —
 * there is no editor on the drafted article, deliberately. An editable quarantined suggestion
 * would erase the only distinction this circuit keeps: what the model proposed versus what the
 * writer committed. After Accept the prose is the writer's, and it opens in the EXISTING
 * manuscript editor (injected as `editor`, never forked into a second stack here).
 *
 * REFUSALS RENDER, ALWAYS. What the article could not carry is shown beside the Accept button, at
 * the same weight as the prose. A writer who cannot see what the argument failed to say cannot
 * meaningfully accept it.
 */

function SeedStub({ stub }) {
    return (
        <li className={`atlas-w-stub${stub.struck ? ' is-struck' : ''}`}
            data-claim-id={stub.claimId} data-status={stub.status}>
            <p className="atlas-w-stub-text">{stub.text}</p>
            <ul className="atlas-w-stub-percepts">
                {stub.percepts.map((p) => (
                    <li key={p.stepId} data-step-id={p.stepId}
                        className={`atlas-w-p${p.bound ? '' : ' is-unbound'}`}>
                        <span className="atlas-p-fn">{p.function}</span>
                        <span className="atlas-p-act">{p.actuator}</span>
                        {p.bound
                            ? <span className="atlas-p-ep">{p.epistemic}</span>
                            : <span className="atlas-p-why">{p.why || 'refused'}</span>}
                        {p.image && <span className="atlas-p-img">on {p.image}</span>}
                    </li>
                ))}
            </ul>
        </li>
    );
}

export default function AtlasWriterPanel({
    plan, draft, blocker, onDraft, drafting, onAccept, accepting, onDismiss, onExport,
    onReopen = null, error = '', editor = null,
}) {
    const stubs = seedStubs(plan);
    const summary = draft ? draftSummary(draft) : null;
    const refusals = draft ? refusalLines(draft) : [];
    const accept = acceptState(draft);

    return (
        <aside className="atlas-writer" aria-label="Writer">
            <header className="atlas-w-head">
                <h2 className="atlas-h2">The writing</h2>
                <p className="atlas-w-note">
                    The draft is composed from the plan you accepted — and only after its percepts
                    have actually been produced. Every sentence rests on evidence you can open on
                    its own image.
                </p>
            </header>

            {blocker && (
                <p className="atlas-banner is-empty" role="note">{blockerText(blocker)}</p>
            )}
            {error && <p className="atlas-error" role="alert">{error}</p>}

            {!draft && !blocker && (
                <section className="atlas-w-seed" aria-label="What the draft will be written from">
                    <h3 className="atlas-h3">The seed</h3>
                    <p className="atlas-w-note">
                        {stubs.length} claim{stubs.length === 1 ? '' : 's'} from the accepted plan,
                        with the percepts each rests on. Drafting runs those producers for real.
                    </p>
                    <ol className="atlas-w-stubs">
                        {stubs.map((s) => <SeedStub key={s.claimId} stub={s} />)}
                    </ol>
                    <button type="button" className="atlas-go" onClick={onDraft} disabled={drafting}>
                        {drafting ? 'Running the percepts, then writing…' : 'Draft the article'}
                    </button>
                </section>
            )}

            {draft && summary && (
                <section className="atlas-w-draft" aria-label="The drafted article"
                    data-state={draft.state}>
                    <div className="atlas-w-status">
                        {/* Said before anything else, because it is what the document IS. */}
                        <span className={`atlas-w-quarantine is-${draft.state}`}>
                            {isQuarantined(draft)
                                ? 'Quarantined — proposed, not yet yours'
                                : 'Accepted into the manuscript'}
                        </span>
                        <span className="atlas-w-counts">
                            {summary.sections} section{summary.sections === 1 ? '' : 's'} ·{' '}
                            {summary.live}/{summary.cited} percepts live
                            {summary.unresolved > 0 && (
                                // Never folded into the total: a citation that could not be drawn
                                // is the article's own admission, not a rendering detail.
                                <span className="atlas-w-warn">
                                    {' '}· {summary.unresolved} could not be shown
                                </span>
                            )}
                            {summary.defects > 0 && (
                                <span className="atlas-w-warn">
                                    {' '}· {summary.defects} admitted defect
                                    {summary.defects === 1 ? '' : 's'}
                                </span>
                            )}
                        </span>
                    </div>

                    {refusals.length > 0 && (
                        <ul className="atlas-banner is-refused" role="alert"
                            aria-label="What this reading could not carry">
                            {refusals.map((line) => <li key={line}>{line}</li>)}
                        </ul>
                    )}

                    {/* M4's renderer, unchanged. The canvas preview and the export are one thing. */}
                    <div className="atlas-w-article">
                        <ArticleView article={draft.article} onReopen={onReopen} />
                    </div>

                    <div className="atlas-w-actions">
                        {!isAccepted(draft) && (
                            <>
                                <button type="button" className="atlas-go" onClick={onAccept}
                                    disabled={accepting || !accept.can}>
                                    {accepting ? 'Accepting…' : 'Accept into the manuscript'}
                                </button>
                                <button type="button" className="atlas-plain" onClick={onDismiss}
                                    disabled={accepting}>Dismiss</button>
                            </>
                        )}
                        <button type="button" className="atlas-plain" onClick={onExport}>
                            Export the article
                        </button>
                    </div>

                    {!accept.can && !isAccepted(draft) && (
                        <p className="atlas-w-cannot" role="note">{accept.why}</p>
                    )}

                    {isAccepted(draft) && (
                        <p className="atlas-plan-accepted" role="status">
                            Accepted. The prose is in the manuscript now, carrying the step ids it
                            rests on — the draft stays here so you can still see what it rested on.
                        </p>
                    )}

                    {/* The existing manuscript editor, and only once the prose is the writer's. */}
                    {isAccepted(draft) && editor}
                </section>
            )}
        </aside>
    );
}
