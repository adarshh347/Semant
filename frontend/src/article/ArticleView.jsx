import React from 'react';
import PerceptFigure from './PerceptFigure.jsx';
import {
    EPISTEMIC_LEGEND, FUNCTION_HINT, FUNCTION_LABEL, articleBlocks, articleDefects,
    draftOf, isCommitted, reopenTarget, sectionCitations, sectionDefects,
} from './articleDraft.js';
import './ArticleView.css';

/**
 * CIRCUIT-003 M4 — the perceptual article: prose interleaved with live percepts.
 *
 * M3 composed the argument; the backend resolver joined each citation to the geometry actually
 * produced for it. This renders the result as a document a reader can walk and — crucially — can
 * CHECK: every paragraph is followed by the evidence it rests on, drawn live from that evidence's
 * own geometry on its own source image, and clicking it reopens that image in the Differential.
 *
 * WHAT THIS DOCUMENT DOES THAT AN ARTICLE NORMALLY CANNOT. It shows its own defects. M3 recorded
 * two channels that had never been rendered anywhere — a paragraph naming an image it does not
 * cite, and a percept the composer itself judged not to bear on its claim — and observed that if
 * M4 did not surface them, a reader would never see them though the data sat right there. So the
 * defect channel is rendered inline, beside the prose it qualifies, in the same visual weight as
 * the prose. Putting it in a footnote or an expander would be a way of shipping the honesty
 * without shipping it.
 *
 * READ-ONLY. There is no Accept here, no edit, no commit. The draft carries `committed: false` and
 * this component renders that fact rather than offering to change it.
 */

const Prose = ({ text }) => (
    <>{String(text || '').split(/\n{2,}/).filter(Boolean).map((p, i) => (
        <p className="art-p" key={i}>{p}</p>
    ))}</>
);

function DefectChannel({ defects }) {
    if (!defects.length) return null;
    return (
        <aside className="art-defects" role="note" aria-label="What this section admits">
            <h4 className="art-defects-h">What this section admits</h4>
            <ul className="art-defects-list">
                {defects.map((d, i) => (
                    <li className={`art-defect is-${d.kind}`} key={i} data-defect-kind={d.kind}>
                        <span className="art-defect-kind">{d.kind}</span>
                        <span className="art-defect-title">{d.title}</span>
                        {d.detail ? <span className="art-defect-detail">{d.detail}</span> : null}
                    </li>
                ))}
            </ul>
        </aside>
    );
}

function Legend() {
    return (
        <div className="art-legend" aria-label="How each claim is known">
            <span className="art-legend-h">How each claim is known</span>
            <ul className="art-legend-list">
                {EPISTEMIC_LEGEND.map((e) => (
                    <li key={e.status} className="art-legend-item">
                        <span className={`diff-chip diff-epistemic-chip is-${e.status}`}
                            data-epistemic={e.status}>{e.label}</span>
                        <span className="art-legend-hint">{e.hint}</span>
                    </li>
                ))}
            </ul>
        </div>
    );
}

function SectionBlock({ section, article, index, onReopen }) {
    const citations = sectionCitations(section, article);
    const defects = sectionDefects(section, article);
    return (
        <section className={`art-section${section.qualified ? ' is-qualified' : ''}`}
            data-claim-id={section.claim_id} data-function={section.function}>
            <header className="art-section-head">
                <span className="art-section-n">§{index}</span>
                <span className={`art-fn is-${section.function}`}
                    title={FUNCTION_HINT[section.function] || ''}>
                    {FUNCTION_LABEL[section.function] || section.function}
                </span>
                <span className={`diff-chip diff-epistemic-chip is-${section.epistemic}`}
                    data-epistemic={section.epistemic}>{section.epistemic}</span>
                {section.qualified ? (
                    <span className="art-qualified-tag">qualified</span>
                ) : null}
            </header>

            <p className="art-claim">{section.claim}</p>
            <Prose text={section.prose} />

            <div className="art-figures">
                {citations.map((c) => (
                    <PerceptFigure key={c.step_id} citation={c} onReopen={onReopen} />
                ))}
            </div>

            <DefectChannel defects={defects} />
        </section>
    );
}

function CounterBlock({ counter, article, onReopen }) {
    const citations = (counter.citations || []).map((c) => {
        const r = (article.resolved || {})[c.step_id];
        return {
            ...c, status: r?.status || 'unproduced', geometry: r?.geometry || null,
            geometryKind: r?.geometry_kind || '', imageRef: r?.image_ref || '',
            imageTitle: r?.image_title || '', label: r?.label || '', detail: r?.detail || '',
            drawable: Boolean(r?.drawable), reopen: r?.reopen || null,
            candidates: r?.candidates || [],
        };
    });
    return (
        <section className="art-section art-counter" data-block="counter">
            <header className="art-section-head">
                <span className="art-section-n">⊘</span>
                <span className="art-fn is-challenge">the counter-reading</span>
            </header>
            {counter.grounded ? (
                <>
                    <Prose text={counter.prose} />
                    <div className="art-figures">
                        {citations.map((c) => (
                            <PerceptFigure key={c.step_id} citation={c} onReopen={onReopen} />
                        ))}
                    </div>
                </>
            ) : (
                // The absence, stated. Never an invented objection — an ungrounded counter-reading
                // is the most convincing possible way to look rigorous while having tested nothing.
                <div className="art-counter-absent" role="note">
                    <strong>No counter-reading could be grounded.</strong>
                    <p className="art-p">{counter.absence_detail}</p>
                    <span className="art-defect-kind">{counter.absence_reason}</span>
                </div>
            )}
        </section>
    );
}

function QualificationsBlock({ items }) {
    return (
        <section className="art-section art-qualifications" data-block="qualifications">
            <header className="art-section-head">
                <span className="art-section-n">†</span>
                <span className="art-fn is-qualification">what this reading could not carry</span>
            </header>
            <ul className="art-qual-list">
                {items.map((q, i) => (
                    <li className="art-qual" key={q.claim_id || i} data-claim-id={q.claim_id}
                        data-status={q.status}>
                        <span className="art-qual-status">{q.status}</span>
                        <p className="art-p">{q.prose}</p>
                    </li>
                ))}
            </ul>
        </section>
    );
}

export default function ArticleView({ article, onReopen = null }) {
    const draft = draftOf(article);
    if (!draft || !Object.keys(draft).length) {
        return <div className="art-empty">No article draft.</div>;
    }
    const blocks = articleBlocks(article);
    const defects = articleDefects(article);
    const counts = (article && article.counts) || {};
    let sectionIndex = 0;

    const handleReopen = (citation) => {
        const target = reopenTarget(citation);
        if (!target) return;
        if (onReopen) onReopen(target, citation);
        else if (typeof window !== 'undefined') window.location.assign(target.href);
    };

    return (
        <article className="art-root" data-committed={String(isCommitted(article))}>
            <header className="art-head">
                <p className="art-eyebrow">A perceptual reading — proposed, not published</p>
                <h1 className="art-thesis">{draft.thesis}</h1>
                <div className="art-status">
                    <span className={`diff-chip diff-epistemic-chip is-${draft.epistemic}`}
                        data-epistemic={draft.epistemic}>{draft.epistemic}</span>
                    <span className="art-status-item">
                        {counts.drawable ?? 0}/{counts.citations ?? 0} percepts shown live
                    </span>
                    {defects.length ? (
                        <span className="art-status-item is-warn">
                            {defects.length} admitted defect{defects.length === 1 ? '' : 's'}
                        </span>
                    ) : null}
                    {!draft.complete ? (
                        <span className="art-status-item is-warn">incomplete</span>
                    ) : null}
                </div>
                <Legend />
            </header>

            {blocks.map((block, i) => {
                if (block.type === 'opening') {
                    return (
                        <section className="art-section art-opening" key={i} data-block="opening">
                            <Prose text={block.prose} />
                        </section>
                    );
                }
                if (block.type === 'section') {
                    sectionIndex += 1;
                    return (
                        <SectionBlock key={block.section.claim_id} section={block.section}
                            article={article} index={sectionIndex} onReopen={handleReopen} />
                    );
                }
                if (block.type === 'counter') {
                    return (
                        <CounterBlock key="counter" counter={block.counter} article={article}
                            onReopen={handleReopen} />
                    );
                }
                if (block.type === 'qualifications') {
                    return <QualificationsBlock key="quals" items={block.items} />;
                }
                if (block.type === 'uncomposed') {
                    return (
                        <section className="art-section art-uncomposed" key="uncomposed"
                            data-block="uncomposed">
                            <header className="art-section-head">
                                <span className="art-section-n">…</span>
                                <span className="art-fn is-qualification">
                                    claims that could not be written
                                </span>
                            </header>
                            <ul className="art-qual-list">
                                {block.items.map((u, j) => (
                                    <li className="art-qual" key={u.claim_id || j}>
                                        <span className="art-qual-status">{u.reason}</span>
                                        <p className="art-p">{u.claim}</p>
                                        {u.detail ? (
                                            <span className="art-defect-detail">{u.detail}</span>
                                        ) : null}
                                    </li>
                                ))}
                            </ul>
                        </section>
                    );
                }
                return null;
            })}

            <footer className="art-foot">
                {/* Read-only, said out loud. The draft is a proposal; there is no Accept here. */}
                This article is a quarantined draft. Nothing in it has been accepted into any post.
            </footer>
        </article>
    );
}
