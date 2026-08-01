import React, { useMemo } from 'react';
import ArticleView from '../article/ArticleView.jsx';
import PerceptFigure from '../article/PerceptFigure.jsx';
import { isHonestlyEmpty } from './runContract';

/**
 * AGENT-DEMO — what the run produced: the article, or the evidence itself.
 *
 * ON REUSE, and the one seam worth explaining. The brief says render `explore` output "through
 * the same renderers" as the article, and also that nothing in `/differential` may be imported
 * into this surface. Both hold here because `article/PerceptFigure` is the thing that already
 * wraps those renderers — RegionOverlay, FlowFieldLayer, paintFields — for exactly this purpose:
 * one percept, drawn on its image, at whatever size the column is. So this file imports from
 * `article/` only, and the differential renderers arrive transitively through the component
 * whose job is already to host them. A field looks the same here as in the workspace because it
 * is literally the same painter, and no renderer was copied to achieve that.
 *
 * `argue` renders the M4 ArticleView unchanged, defects and all — the relevance flags and the
 * citations that refuse to draw are the interesting part of an article, not blemishes to filter.
 */
export default function RunOutput({ view, onReopen = null }) {
    // A produced descriptor is not a resolved citation, but PerceptFigure only ever reads a
    // handful of fields off one — so `explore` output is adapted rather than re-rendered by a
    // second, near-identical figure component that would then drift from this one.
    const figures = useMemo(() => {
        if (!view || view.article) return [];
        return (view.suggestions || [])
            .filter((s) => s && s.geometry)
            .map((s, i) => ({
                step_id: String(s?.provenance?.step_id || `sug_${i}`),
                actuator: String(s?.provenance?.producer || s?.producer || s?.role || ''),
                label: String(s?.label || s?.role || 'percept'),
                epistemic: String(s?.epistemic_status || ''),
                image: String(s?.post_id || ''),
                image_ref: String(s?.image_ref || ''),
                geometry: s.geometry,
                geometryKind: String(s.geometry?.kind || ''),
                status: 'resolved',
                drawable: true,
                function: '',
                attribution: null,
                detail: '',
                reopen: null,
            }));
    }, [view]);

    if (!view) return null;

    // HONEST EMPTINESS. A finished run that produced nothing says so, with the loop's own
    // reason — never an empty container that reads as success.
    if (isHonestlyEmpty(view)) {
        return (
            <section className="ad-output ad-output--empty" aria-label="What the run produced">
                <h2 className="ad-h2">It produced nothing.</h2>
                <p className="ad-empty-reason">
                    {view.stop_reason || 'The run ended without producing anything, and did not say why.'}
                </p>
                <p className="ad-quiet">
                    That is a result, not a failure to display — nothing was guessed to fill the space.
                </p>
            </section>
        );
    }

    if (view.article) {
        return (
            <section className="ad-output" aria-label="The article">
                <ArticleView article={view.article} onReopen={onReopen} />
            </section>
        );
    }

    return (
        <section className="ad-output" aria-label="What the run produced">
            <h2 className="ad-h2">What it found</h2>
            {figures.length === 0 ? (
                <p className="ad-quiet">
                    Nothing drawable yet — evidence appears here as the run produces it.
                </p>
            ) : (
                <div className="ad-figures">
                    {figures.map((c) => (
                        <figure className="ad-figure" key={c.step_id}>
                            <PerceptFigure citation={c} onReopen={onReopen} />
                            <figcaption className="ad-figure-cap">
                                <span className="ad-figure-label">{c.label}</span>
                                {c.actuator ? <span className="ad-figure-act">{c.actuator}</span> : null}
                            </figcaption>
                        </figure>
                    ))}
                </div>
            )}
        </section>
    );
}
