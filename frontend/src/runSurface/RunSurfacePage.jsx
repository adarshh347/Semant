import React, { useCallback, useEffect, useRef, useState } from 'react';
import WalkStream from '../cognition/WalkStream.jsx';
import Convergence from '../society/Convergence.jsx';
import { createCognitionClient } from '../cognition/cognitionClient.js';
import { API_URL } from '../config/api';
import '../cognition/cognition.css';
import '../society/society.css';
import './runSurface.css';

/**
 * RUN SURFACE — drive the agents, rather than read what they did.
 *
 * `/cognition` and `/society` are windows: you give them a locus and they show you a walk. This is
 * the same endpoints with the dials exposed — seed, character, organ, steps, and one agent or a
 * society — so the question "what do character-having, goal-less agents actually DO" becomes
 * something you watch instead of something you argue about.
 *
 * NOTHING IS RENDERED HERE. Every result goes into `WalkStream` and `Convergence`, the components
 * `/cognition` and `/society` already use. That is the journeys lane's rule and it is the reason
 * this page is short: refusals as content, no narrated arrival, status by stroke not hue,
 * temperament biasing the path and never the measurement — all inherited, none re-implemented. A
 * third renderer would be a third set of honesty rules and the one that drifted would be the one
 * nobody read.
 *
 * NOTHING IS COMMITTED. These endpoints derive and propose; committing stays the curator's act on
 * the curator surface, and there is no write method on this page's client to misuse.
 */

const MODES = [
    { id: 'walk', label: 'one agent walks' },
    { id: 'compare', label: 'two characters, one seed' },
    { id: 'society', label: 'a society convenes' },
];

const ORGANS = ['nestedness_organ', 'adjacency_organ', 'chroma_organ', 'depth_organ'];

export default function RunSurfacePage({ client = null }) {
    const cognition = useRef(client?.cognition || createCognitionClient()).current;
    const society = useRef(client?.society || {
        meeting: async (params) => {
            const q = Object.entries(params)
                .filter(([, v]) => v !== '' && v != null)
                .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&');
            const res = await fetch(`${API_URL}/api/v1/society/meeting?${q}`);
            if (!res.ok) {
                let detail = '';
                try { detail = (await res.json())?.detail || ''; } catch { /* not json */ }
                throw new Error(detail || `${res.status} ${res.statusText}`);
            }
            return res.json();
        },
    }).current;

    const [seed, setSeed] = useState('');
    const [region, setRegion] = useState('');
    const [mode, setMode] = useState('compare');
    const [temperament, setTemperament] = useState('depth_seeker');
    const [organ, setOrgan] = useState('');
    const [steps, setSteps] = useState(3);
    const [characters, setCharacters] = useState([]);
    const [result, setResult] = useState(null);
    const [refusal, setRefusal] = useState(null);
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        cognition.temperaments().then(setCharacters).catch(() => setCharacters([]));
    }, [cognition]);

    const run = useCallback(async () => {
        if (!seed.trim()) {
            setRefusal({ kind: 'input', detail: 'a seed locus is needed — an agent stands somewhere' });
            return;
        }
        setBusy(true); setRefusal(null); setResult(null);
        const params = { post_id: seed.trim(), region_id: region.trim(), steps };
        try {
            if (mode === 'walk') {
                setResult({ mode, walks: [await cognition.walk({ ...params, temperament, organ })] });
            } else if (mode === 'compare') {
                const body = await cognition.compare({ ...params, organ });
                setResult({ mode, walks: body.walks, comparison: body.comparison });
            } else {
                setResult({ mode, meeting: await society.meeting(params) });
            }
        } catch (err) {
            const detail = err.message || String(err);
            // A REFUSAL IS A FINDING, not an error. `409` from `convene`, a `box_footing` horizon,
            // an undeclared character — each is the system saying something true about this seed,
            // and rendering them all as a red line would throw that away.
            setRefusal({
                kind: /travell|walked|society|perceiv/i.test(detail) ? 'untravelled'
                    : /temperament/i.test(detail) ? 'character'
                    : /no post|no region/i.test(detail) ? 'nowhere' : 'error',
                detail,
            });
        } finally {
            setBusy(false);
        }
    }, [cognition, society, seed, region, mode, temperament, organ, steps]);

    const comparison = result?.comparison;

    return (
        <div className="cog-shell">
            <header className="cog-head">
                <h1 className="cog-title">Drive the agents</h1>
                <p className="cog-lede">
                    Spawn a being at a locus, give it a character and a body, and watch what it does.
                    Nothing here is replayed — every run computes on the same endpoints{' '}
                    <code>/cognition</code> and <code>/society</code> use, and nothing it produces is
                    committed: a run proposes, and accepting stays the curator's act.
                </p>
            </header>

            <form className="cog-controls" onSubmit={(e) => { e.preventDefault(); run(); }}>
                <label className="cog-field">
                    <span>seed locus</span>
                    <input value={seed} onChange={(e) => setSeed(e.target.value)}
                           placeholder="post id" />
                </label>
                <label className="cog-field">
                    <span>region</span>
                    <input value={region} onChange={(e) => setRegion(e.target.value)}
                           placeholder="optional" />
                </label>
                <label className="cog-field">
                    <span>run</span>
                    <select value={mode} onChange={(e) => setMode(e.target.value)}>
                        {MODES.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
                    </select>
                </label>
                {mode === 'walk' && (
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
                {mode !== 'society' && (
                    <label className="cog-field">
                        <span>body</span>
                        <select value={organ} onChange={(e) => setOrgan(e.target.value)}>
                            <option value="">default (nestedness)</option>
                            {ORGANS.map((o) => <option key={o} value={o}>{o}</option>)}
                        </select>
                    </label>
                )}
                <label className="cog-field run-steps">
                    <span>steps</span>
                    <input type="number" min="0" max="8" value={steps}
                           onChange={(e) => setSteps(Number(e.target.value))} />
                </label>
                <button className="cog-go" type="submit" disabled={busy}>
                    {busy ? 'running…' : 'run'}
                </button>
            </form>

            {refusal && (
                <section className={`run-refusal run-refusal--${refusal.kind}`} role="alert">
                    <h2 className="soc-h2">
                        {refusal.kind === 'untravelled' ? 'nobody travelled far enough'
                            : refusal.kind === 'character' ? 'no such character'
                            : refusal.kind === 'nowhere' ? 'nowhere to stand'
                            : 'the run did not complete'}
                    </h2>
                    <p className="run-refusal-detail">{refusal.detail}</p>
                    {refusal.kind !== 'error' && (
                        <p className="run-refusal-note">
                            This is a finding, not a failure — the system saying something true about
                            this seed. A different locus, character or step count may afford more.
                        </p>
                    )}
                </section>
            )}

            {comparison && (
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

            {result?.walks && (
                <div className={`cog-walks ${result.walks.length > 1 ? 'cog-walks--pair' : ''}`}>
                    {result.walks.map((walk) => <WalkStream key={walk.agent_id} walk={walk} />)}
                </div>
            )}

            {result?.meeting && (
                <>
                    <Convergence walks={result.meeting.walks} nodeId={result.meeting.node_id} />
                    <section className="soc-partition">
                        <h2 className="soc-h2">the partition</h2>
                        <ul className="soc-verdicts">
                            {result.meeting.verdicts.map((v, i) => (
                                <li key={i} className={`soc-verdict soc-verdict--${v.outcome}`}>
                                    <div className="soc-verdict-head">
                                        <span className="soc-pair">{v.left} ↔ {v.right}</span>
                                        <span className="soc-outcome">{v.outcome}</span>
                                    </div>
                                    <p className="soc-verdict-detail">{v.detail}</p>
                                </li>
                            ))}
                        </ul>
                    </section>
                </>
            )}
        </div>
    );
}
