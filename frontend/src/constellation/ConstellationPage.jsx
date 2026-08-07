import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import ConstellationGraph from './ConstellationGraph';
import {
    LEDGER_COMMITTED, SPAN_BETWEEN, SPAN_WITHIN, fetchConstellation, fetchSeeds,
} from './constellationClient';
import './constellation.css';

/**
 * WAVE4 — the constellation: the world an agent inhabits, seen.
 *
 * A scene shows one picture. An agent lives in a neighbourhood — regions across several images,
 * stitched by the relations it grounded — and this draws that neighbourhood out from a seed to a
 * bounded depth.
 *
 * ## The bound is on the page, not only in the URL
 *
 * A neighbourhood of six nodes is a claim about how far this walked, and a viewer that showed six
 * nodes without saying "two hops" would read as a claim about the world. So the depth control and
 * the backend's own `bound_detail` are both on screen, and the sources tally says which of the
 * three durable places each edge came from.
 *
 * ## What it will not draw
 *
 * A candidate the retina proposed and the kernel refused. Not by filtering — by there being
 * nothing to filter: refusals are never persisted, so they cannot reach this page. That is stated
 * on the page rather than assumed, because the day something starts filing candidates this view
 * would draw them and the guard would have to be built then.
 */
export default function ConstellationPage() {
    const [params, setParams] = useSearchParams();
    const seedParam = params.get('node') || '';
    const depthParam = Number(params.get('depth') || 2);

    const [seeds, setSeeds] = useState([]);
    const [seedsDetail, setSeedsDetail] = useState('');
    const [walk, setWalk] = useState(null);
    const [selectedEdgeId, setSelectedEdgeId] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        fetchSeeds()
            .then((data) => {
                if (cancelled) return;
                setSeeds(data.seeds || []);
                setSeedsDetail(data.detail || '');
                // The busiest locus is the default only because it is the best place to SEE a
                // neighbourhood — not because it matters more. Stated in the sidebar.
                if (!seedParam && data.seeds && data.seeds[0]) {
                    setParams({ node: data.seeds[0].node_id, depth: String(depthParam) },
                               { replace: true });
                }
            })
            .catch((e) => { if (!cancelled) setError(e.detail || 'Could not read the seeds.'); });
        return () => { cancelled = true; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        let cancelled = false;
        if (!seedParam) { setLoading(false); return undefined; }
        setLoading(true); setError('');
        fetchConstellation(seedParam, { depth: depthParam })
            .then((data) => { if (!cancelled) { setWalk(data); setSelectedEdgeId(''); } })
            .catch((e) => { if (!cancelled) setError(e.detail || 'Could not walk from there.'); })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, [seedParam, depthParam]);

    const select = useCallback((node, depth) => {
        setParams({ node, depth: String(depth) });
    }, [setParams]);

    const selectedEdge = useMemo(
        () => (walk && walk.edges.find((e) => e.edge_id === selectedEdgeId)) || null,
        [walk, selectedEdgeId]);

    const tally = (walk && walk.tally) || {};
    const bySpan = tally.by_span || {};

    return (
        <div className="con-page">
            <header className="con-header">
                <div>
                    <span className="con-eyebrow">the constellation</span>
                    <h1 className="con-title">The world reachable from one place</h1>
                    <p className="con-sub">
                        Regions as places, grounded relations as the ways between them. An occlusion
                        moves <em>through</em> a picture; a nesting or a rhyme moves <em>between</em>
                        {' '}pictures. Only relations that were actually written down appear here.
                    </p>
                </div>
                <Link className="con-back" to="/">← back</Link>
            </header>

            {error ? <p className="con-error" role="alert">{error}</p> : null}

            <div className="con-body">
                <aside className="con-side">
                    <h2 className="con-h2">where there is something to see</h2>
                    <p className="con-note">{seedsDetail}</p>
                    <ol className="con-seeds">
                        {seeds.map((seed) => (
                            <li key={seed.node_id}>
                                <button
                                    type="button"
                                    className={`con-seed${seed.node_id === seedParam ? ' is-open' : ''}`}
                                    onClick={() => select(seed.node_id, depthParam)}
                                >
                                    <span className="con-seed-region">{seed.region_id}</span>
                                    <span className="con-seed-meta">
                                        <span className="con-seed-post">{seed.post_id.slice(-8)}</span>
                                        <span className="con-seed-degree">{seed.degree}</span>
                                    </span>
                                </button>
                            </li>
                        ))}
                    </ol>
                    <p className="con-note">
                        Ordered by how many relations touch each locus — that is about where a
                        neighbourhood is legible, not about which matters.
                    </p>
                </aside>

                <section className="con-main">
                    <div className="con-controls">
                        <span className="con-controls-label">depth</span>
                        {[0, 1, 2, 3, 4].map((d) => (
                            <button
                                key={d}
                                type="button"
                                className={`con-depth${d === depthParam ? ' is-on' : ''}`}
                                onClick={() => select(seedParam, d)}
                            >
                                {d}
                            </button>
                        ))}
                        {walk ? (
                            <span className="con-counts">
                                <strong>{tally.nodes}</strong> loci ·{' '}
                                <strong>{tally.images}</strong> image{tally.images === 1 ? '' : 's'} ·{' '}
                                <strong>{bySpan[SPAN_WITHIN] || 0}</strong> through ·{' '}
                                <strong>{bySpan[SPAN_BETWEEN] || 0}</strong> between
                            </span>
                        ) : null}
                    </div>

                    {loading ? <p className="con-muted">walking…</p> : null}

                    {walk && walk.nodes.length === 1 && walk.edges.length === 0 ? (
                        <p className="con-muted">
                            Nothing persisted touches this locus. That is a fact about what has been
                            filed, not about what the engine has measured.
                        </p>
                    ) : null}

                    {walk ? (
                        <ConstellationGraph
                            nodes={walk.nodes}
                            edges={walk.edges}
                            selectedEdgeId={selectedEdgeId}
                            onSelectEdge={setSelectedEdgeId}
                        />
                    ) : null}

                    <div className="con-legend">
                        <h3 className="con-h3">how to read a line</h3>
                        <ul>
                            <li>
                                <span className="con-swatch con-edge--within_image con-edge--measured con-edge--proposed" />
                                stays inside one column — depth <strong>through</strong> a picture
                            </li>
                            <li>
                                <span className="con-swatch con-edge--between_images con-edge--measured con-edge--proposed" />
                                crosses the gap — a move <strong>between</strong> pictures
                            </li>
                            <li>
                                <span className="con-swatch con-edge--interpretive con-edge--proposed" />
                                dashed: <strong>interpretive</strong> — an estimate, not a measurement
                            </li>
                            <li>
                                <span className="con-swatch con-edge--unreadable con-edge--proposed" />
                                dotted: the cited mark is <strong>not in any ledger</strong>, so this
                                edge cannot say what kind of knowing it is
                            </li>
                            <li>
                                <span className="con-swatch con-edge--measured con-edge--committed" />
                                heavy: a person <strong>committed</strong> it
                            </li>
                        </ul>
                        <p className="con-note">
                            Every one of those is written on the edge's own label too. Styling alone
                            would put the epistemic story in a stylesheet's hands.
                        </p>
                    </div>

                    {selectedEdge ? (
                        <div className="con-edgedetail">
                            <h3 className="con-h3">{selectedEdge.relation}</h3>
                            <p className="con-edgedetail-claim">{selectedEdge.detail}</p>
                            <dl className="con-dl">
                                <dt>axis</dt><dd>{selectedEdge.axis || '—'}</dd>
                                <dt>span</dt>
                                <dd>{selectedEdge.span === SPAN_WITHIN
                                    ? 'within one image — depth through the picture'
                                    : 'between images — a crossing'}</dd>
                                <dt>the organ says</dt>
                                <dd>{selectedEdge.epistemic || 'nothing readable — its mark is in no ledger'}</dd>
                                <dt>the ledger says</dt>
                                <dd>{selectedEdge.ledger_status}</dd>
                                <dt>basis</dt><dd>{selectedEdge.basis || '—'}</dd>
                                <dt>filed as</dt><dd>{selectedEdge.source}</dd>
                            </dl>
                        </div>
                    ) : null}

                    {walk ? (
                        <div className="con-bound">
                            <h3 className="con-h3">the bound, and where these came from</h3>
                            <p className="con-note">{walk.bound_detail}</p>
                            <p className="con-note">
                                Across the whole corpus:{' '}
                                <strong>{walk.sources.ledger_relation_marks}</strong> committed
                                relation mark(s),{' '}
                                <strong>{walk.sources.curator_proposals}</strong> filed proposal(s),{' '}
                                <strong>{walk.sources.atlas_movement_edges}</strong> atlas movement
                                edge(s). Every Wave 3 lane measured relations and returned them into a
                                transcript; only the occlusion queue writes any of them down, which is
                                why this graph is small.
                            </p>
                        </div>
                    ) : null}
                </section>
            </div>
        </div>
    );
}
