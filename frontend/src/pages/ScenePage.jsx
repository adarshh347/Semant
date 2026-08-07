import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { API_URL } from '../config/api';
import './ScenePage.css';

/**
 * WAVE4 — the scene view: a picture, its regions, and the relations grounded on them.
 *
 * The engine has been grounding nesting, adjacency, occlusion and chromatic rhyme on regions for
 * three waves, and there has been nowhere to SEE them on the picture they were measured from.
 *
 * THE ONE RULE THIS PAGE EXISTS TO KEEP. A relation must look like what it IS:
 *
 *   measured (mask basis)     a solid stroke      — the geometry supports the claim
 *   interpretive (box basis)  a dashed stroke     — an estimate of an extent, never a measurement
 *   proposed                  hollow marker       — nobody has accepted this
 *   committed                 filled marker       — a curator did
 *
 * A dashed line and a solid line are different at a glance and stay different when the colour is
 * gone (print, greyscale, colour-blindness), which is why the status is carried by STROKE and not
 * by hue. Rendering an interpretive relation like a measured one would be the founding pathology
 * again, in CSS: `cseg_golden_finial_7 in region_2` scores containment 1.000, and it is the first
 * relation this page draws on the temple scene. It must be visibly an estimate.
 *
 * Read-only. There is no commit here — that is the curator surface. This shows; it does not change.
 */

const KINDS = [
    { key: 'nesting', label: 'Nesting', hint: 'A is inside B' },
    { key: 'adjacency', label: 'Adjacency', hint: "A's edge lies against B's" },
    { key: 'occlusion', label: 'Occlusion', hint: 'A is in front of B — corrects a nesting' },
    { key: 'rhyme', label: 'Rhyme', hint: 'warmth fields rhyme — points to another image' },
    { key: 'committed', label: 'Committed', hint: 'accepted by a curator' },
];

const centreOf = (region) => {
    if (region?.polygons?.length) {
        const pts = region.polygons.flat();
        if (pts.length) {
            const sx = pts.reduce((a, p) => a + p[0], 0) / pts.length;
            const sy = pts.reduce((a, p) => a + p[1], 0) / pts.length;
            return [sx, sy];
        }
    }
    const b = region?.box;
    return b ? [b.x + b.w / 2, b.y + b.h / 2] : null;
};

const ringPath = (ring, w, h) =>
    ring.length ? `M ${ring.map(([x, y]) => `${x * w} ${y * h}`).join(' L ')} Z` : '';

export default function ScenePage() {
    const { postId } = useParams();
    const navigate = useNavigate();
    const [index, setIndex] = useState([]);
    const [scene, setScene] = useState(null);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [active, setActive] = useState(() => new Set(['occlusion', 'rhyme', 'committed']));
    const [hovered, setHovered] = useState(null);
    // The image's NATURAL pixel size. The overlay carries it as its viewBox and letterboxes with
    // `xMidYMid meet` inside the same box `object-fit: contain` letterboxes the image in — so the
    // two cannot disagree. `preserveAspectRatio="none"` would stretch the viewBox across the
    // stage while the image letterboxed inside it, and a polygon would land somewhere else
    // entirely; `RegionOverlay` documents that failure and this is the same fix.
    const [natural, setNatural] = useState({ w: 1000, h: 1000 });

    useEffect(() => {
        let alive = true;
        fetch(`${API_URL}/api/v1/scene/`)
            .then((r) => (r.ok ? r.json() : []))
            .then((rows) => { if (alive) setIndex(rows || []); })
            .catch(() => { if (alive) setIndex([]); });
        return () => { alive = false; };
    }, []);

    useEffect(() => {
        if (!postId) { setScene(null); return undefined; }
        let alive = true;
        setLoading(true); setError('');
        fetch(`${API_URL}/api/v1/scene/${postId}`)
            .then(async (r) => {
                if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
                return r.json();
            })
            .then((data) => { if (alive) { setScene(data); setLoading(false); } })
            .catch((e) => { if (alive) { setError(String(e.message || e)); setLoading(false); } });
        return () => { alive = false; };
    }, [postId]);

    const regionsById = useMemo(() => {
        const map = new Map();
        (scene?.regions || []).forEach((r) => map.set(r.id, r));
        return map;
    }, [scene]);

    const shown = useMemo(
        () => (scene?.relations || []).filter((rel) => active.has(rel.kind)),
        [scene, active]);

    const toggle = (key) => setActive((prev) => {
        const next = new Set(prev);
        if (next.has(key)) next.delete(key); else next.add(key);
        return next;
    });

    if (!postId) {
        return (
            <div className="scene-page">
                <header className="scene-head">
                    <h1>Scene</h1>
                    <p className="scene-lede">
                        A picture with the relations grounded on it — nesting, adjacency,
                        occlusion, chromatic rhyme — each drawn at its true status. Choose a scene.
                    </p>
                </header>
                <ul className="scene-index">
                    {index.map((row) => (
                        <li key={row.post_id}>
                            <button type="button" onClick={() => navigate(`/scene/${row.post_id}`)}>
                                {row.photo_url
                                    ? <img src={row.photo_url} alt="" loading="lazy" />
                                    : <span className="scene-index-blank">no image</span>}
                                <span className="scene-index-meta">
                                    <strong>{row.regions} regions</strong>
                                    <span>{row.masked} masked</span>
                                    <span className="scene-index-counts">
                                        {KINDS.slice(0, 4).map(({ key, label }) => (
                                            <em key={key} data-zero={!row.relations?.[key]}>
                                                {label} {row.relations?.[key] ?? 0}
                                            </em>
                                        ))}
                                    </span>
                                </span>
                            </button>
                        </li>
                    ))}
                </ul>
                {!index.length && <p className="scene-empty">No scenes yet.</p>}
            </div>
        );
    }

    return (
        <div className="scene-page">
            <header className="scene-head">
                <h1>Scene</h1>
                <p className="scene-lede">
                    Every relation below is drawn as what it is: a <b>solid</b> stroke where the
                    geometry is a mask and the claim is <b>measured</b>, a <b>dashed</b> stroke
                    where it rests on a box and is only <b>interpretive</b>. Hollow markers are
                    <b> proposed</b>; filled ones a curator has <b>committed</b>.
                </p>
            </header>

            {loading && <p className="scene-empty">Reading the scene…</p>}
            {error && <p className="scene-error">{error}</p>}

            {scene && (
                <>
                    <div className="scene-controls">
                        {KINDS.map(({ key, label, hint }) => {
                            const n = scene.tallies?.by_kind?.[key] || 0;
                            const absent = (scene.kinds_absent || []).includes(key);
                            const noneHere = (scene.kinds_none_here || []).includes(key);
                            return (
                                <button
                                    key={key} type="button" title={hint}
                                    className={`scene-chip${active.has(key) ? ' is-on' : ''}`}
                                    aria-pressed={active.has(key)}
                                    onClick={() => toggle(key)}>
                                    <span className={`scene-swatch scene-swatch--${key}`} />
                                    {label} <b>{n}</b>
                                    {absent && <em className="scene-chip-absent">not derived</em>}
                                    {noneHere && <em className="scene-chip-absent">none here</em>}
                                </button>
                            );
                        })}
                    </div>

                    <div className="scene-stage">
                        <div className="scene-frame">
                            {scene.photo_url && (
                                <img
                                    src={scene.photo_url} alt=""
                                    onLoad={(e) => setNatural({
                                        w: e.currentTarget.naturalWidth || 1000,
                                        h: e.currentTarget.naturalHeight || 1000,
                                    })} />
                            )}
                            <svg viewBox={`0 0 ${natural.w} ${natural.h}`}
                                 preserveAspectRatio="xMidYMid meet"
                                 className="scene-overlay" role="presentation">
                                {(scene.regions || []).map((r) => (
                                    (r.polygons || []).map((ring, i) => (
                                        <path
                                            key={`${r.id}-${i}`}
                                            d={ringPath(ring, natural.w, natural.h)}
                                            className={`scene-region${r.has_mask ? '' : ' is-box'}`
                                                + (hovered === r.id ? ' is-hot' : '')} />
                                    ))
                                ))}
                                {shown.map((rel, i) => {
                                    const a = centreOf(regionsById.get(rel.source));
                                    const b = rel.target_post_id
                                        ? null : centreOf(regionsById.get(rel.target));
                                    if (!a) return null;
                                    const cls = `scene-link scene-link--${rel.kind}`
                                        + (rel.admissible ? ' is-measured' : ' is-interpretive')
                                        + (rel.ledger_status === 'committed'
                                            ? ' is-committed' : ' is-proposed');
                                    if (!b) {
                                        // A rhyme points OUT of this picture. It gets a stub to the
                                        // frame edge rather than a line to nowhere — the far end is
                                        // genuinely not on this page and pretending otherwise
                                        // would draw a relation between two things you can see.
                                        return (
                                            <g key={i} className={cls}>
                                                <line x1={a[0] * natural.w} y1={a[1] * natural.h}
                                                      x2={a[0] * natural.w} y2={0} />
                                                <circle cx={a[0] * natural.w} cy={12} r={9} />
                                            </g>
                                        );
                                    }
                                    return (
                                        <g key={i} className={cls}>
                                            <line x1={a[0] * natural.w} y1={a[1] * natural.h}
                                                  x2={b[0] * natural.w} y2={b[1] * natural.h} />
                                            {rel.kind === 'occlusion' && (
                                                <circle cx={a[0] * natural.w}
                                                        cy={a[1] * natural.h} r={10} />
                                            )}
                                        </g>
                                    );
                                })}
                            </svg>
                        </div>

                        <aside className="scene-side">
                            <SceneCache cache={scene.cache} absent={scene.kinds_absent}
                                noneHere={scene.kinds_none_here} />
                            <SceneTallies tallies={scene.tallies} audit={scene.provenance_audit} />
                            <ol className="scene-list">
                                {shown.slice(0, 120).map((rel, i) => (
                                    <li key={i}
                                        className={rel.admissible ? 'is-measured' : 'is-interpretive'}
                                        onMouseEnter={() => setHovered(rel.source)}
                                        onMouseLeave={() => setHovered(null)}>
                                        <span className={`scene-swatch scene-swatch--${rel.kind}`} />
                                        <span className="scene-list-pair">
                                            <code>{rel.source}</code>
                                            <em>{rel.relation.replace(/_/g, ' ')}</em>
                                            <code>{rel.target}</code>
                                            {rel.target_post_id && (
                                                <button type="button" className="scene-jump"
                                                    onClick={() =>
                                                        navigate(`/scene/${rel.target_post_id}`)}>
                                                    in another image →
                                                </button>
                                            )}
                                        </span>
                                        <span className="scene-badges">
                                            <b data-status={rel.epistemic}>{rel.epistemic}</b>
                                            <b data-ledger={rel.ledger_status}>
                                                {rel.ledger_status}
                                            </b>
                                            <span className="scene-basis">{rel.basis}</span>
                                            {rel.misstated && (
                                                <b data-status="misstated">misstated</b>
                                            )}
                                        </span>
                                        <p className="scene-detail">{rel.detail}</p>
                                        {rel.supersedes && (
                                            <p className="scene-supersedes">
                                                corrects a nesting: <code>{rel.supersedes.source}</code>
                                                {' in '}<code>{rel.supersedes.target}</code>
                                            </p>
                                        )}
                                    </li>
                                ))}
                            </ol>
                            {shown.length > 120 && (
                                <p className="scene-empty">
                                    showing 120 of {shown.length} — the rest are in the API
                                </p>
                            )}
                            {!shown.length && (
                                <p className="scene-empty">
                                    Nothing of the selected kinds on this scene.
                                </p>
                            )}
                        </aside>
                    </div>
                </>
            )}
        </div>
    );
}

function SceneCache({ cache, absent, noneHere }) {
    if (!cache) return null;
    return (
        <section className="scene-card">
            <h2>What has been derived</h2>
            {cache.missing ? (
                <p className="scene-warn">
                    No relations have been derived yet. This scene is not empty — nobody has run
                    the build. <code>scripts/scene_relations_build.py</code>
                </p>
            ) : (
                <>
                    <p>
                        built <time>{cache.built_at || 'unknown'}</time> over {cache.scenes} scene(s)
                    </p>
                    <p className="scene-kinds">
                        derived: {(cache.kinds_built || []).join(', ') || 'nothing'}
                    </p>
                    {!!(absent || []).length && (
                        <p className="scene-warn">
                            never derived: {absent.join(', ')} — missing evidence, which is not
                            the same as evidence of absence
                        </p>
                    )}
                    {!!(noneHere || []).length && (
                        <p>
                            derived and none found here: {noneHere.join(', ')} — this picture
                            genuinely has none
                        </p>
                    )}
                    {cache.provenance?.depth && (
                        <p className="scene-prov">
                            depth: {cache.provenance.depth.model} @ grid{' '}
                            {cache.provenance.depth.grid}
                        </p>
                    )}
                </>
            )}
        </section>
    );
}

function SceneTallies({ tallies, audit }) {
    const ep = tallies?.by_epistemic || {};
    const led = tallies?.by_ledger || {};
    return (
        <section className="scene-card">
            <h2>How much is measured</h2>
            <ul className="scene-tally">
                <li><b data-status="measured">measured</b> {ep.measured || 0}</li>
                <li><b data-status="interpretive">interpretive</b> {ep.interpretive || 0}</li>
                <li><b data-ledger="proposed">proposed</b> {led.proposed || 0}</li>
                <li><b data-ledger="committed">committed</b> {led.committed || 0}</li>
            </ul>
            {audit && (
                <p className="scene-prov">
                    regions: {audit.attributed ?? 0} of {audit.regions ?? 0} name who drew them
                </p>
            )}
        </section>
    );
}
