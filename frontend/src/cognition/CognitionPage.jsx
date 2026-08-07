import React, { useCallback, useEffect, useState } from 'react';
import WalkStream from './WalkStream.jsx';
import { createCognitionClient } from './cognitionClient.js';
import './cognition.css';

/**
 * COGNITION — watch a being think within an image.
 *
 * Its own route and its own shell, like `/agent`: this is not a run surface with the machine
 * producing something, it is a WALK — one agent, its loci, what it measured, what it refused, and
 * the character that shaped where it went.
 *
 * The comparison view is the point of the page rather than a feature of it. Two characters from
 * one locus produce identical measurements and different routes, and that is a claim best made by
 * putting the two streams side by side and letting a reader check both halves at once.
 */
export default function CognitionPage({ client = null }) {
    const cognition = React.useRef(client || createCognitionClient()).current;

    const [postId, setPostId] = useState('');
    const [regionId, setRegionId] = useState('');
    const [mode, setMode] = useState('compare');
    const [temperament, setTemperament] = useState('depth_seeker');
    const [characters, setCharacters] = useState([]);
    const [result, setResult] = useState(null);
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        cognition.temperaments().then(setCharacters).catch(() => setCharacters([]));
    }, [cognition]);

    const run = useCallback(async () => {
        if (!postId.trim()) { setError('a post id is needed — an agent stands somewhere'); return; }
        setBusy(true); setError(''); setResult(null);
        try {
            const params = { post_id: postId.trim(), region_id: regionId.trim(), steps: 3 };
            const body = mode === 'compare'
                ? await cognition.compare(params)
                : { walks: [await cognition.walk({ ...params, temperament })], comparison: null };
            setResult(body);
        } catch (err) {
            setError(err.message || String(err));
        } finally {
            setBusy(false);
        }
    }, [cognition, postId, regionId, mode, temperament]);

    const comparison = result?.comparison;

    return (
        <div className="cog-shell">
            <header className="cog-head">
                <h1 className="cog-title">Watch an agent walk</h1>
                <p className="cog-lede">
                    A situated agent inhabits a locus, perceives through its organs, and moves along
                    crossings it can actually stand on. What it <em>refused</em> is shown beside what
                    it found — a refusal is evidence, not a blank.
                </p>
            </header>

            <form className="cog-controls" onSubmit={(e) => { e.preventDefault(); run(); }}>
                <label className="cog-field">
                    <span>post id</span>
                    <input value={postId} onChange={(e) => setPostId(e.target.value)}
                           placeholder="a post with regions" />
                </label>
                <label className="cog-field">
                    <span>region (optional)</span>
                    <input value={regionId} onChange={(e) => setRegionId(e.target.value)}
                           placeholder="where it stands" />
                </label>
                <label className="cog-field">
                    <span>view</span>
                    <select value={mode} onChange={(e) => setMode(e.target.value)}>
                        <option value="compare">two characters, one locus</option>
                        <option value="single">one walk</option>
                    </select>
                </label>
                {mode === 'single' && (
                    <label className="cog-field">
                        <span>character</span>
                        <select value={temperament} onChange={(e) => setTemperament(e.target.value)}>
                            <option value="">no declared character</option>
                            {characters.map((c) => (
                                <option key={c.name} value={c.name}>{c.name}</option>
                            ))}
                        </select>
                    </label>
                )}
                <button className="cog-go" type="submit" disabled={busy}>
                    {busy ? 'walking…' : 'walk'}
                </button>
            </form>

            {error && <p className="cog-error" role="alert">{error}</p>}

            {comparison && (
                /* THE BRIGHT LINE, rendered as two claims rather than one. Identical measurements
                   AND different routes — a surface that showed only the divergence would hide the
                   half that is easy to lose. */
                <section className="cog-brightline">
                    <p className={comparison.measurements_identical ? 'cog-ok' : 'cog-warn'}>
                        measurements identical: {String(comparison.measurements_identical)}
                        <span> — temperament biases the route, never the reading</span>
                    </p>
                    <p className={comparison.diverged ? 'cog-ok' : 'cog-neutral'}>
                        routes diverged: {String(comparison.diverged)}
                        <span> — {comparison.detail}</span>
                    </p>
                </section>
            )}

            <div className={`cog-walks ${(result?.walks || []).length > 1 ? 'cog-walks--pair' : ''}`}>
                {(result?.walks || []).map((walk) => (
                    <WalkStream key={walk.agent_id} walk={walk} />
                ))}
            </div>
        </div>
    );
}
