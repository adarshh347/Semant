import React, { useCallback, useEffect, useState } from 'react';
import { Sparkles, Check, Trash2 } from 'lucide-react';
import { API_URL } from '../config/api';
import { getSubject, forgetSubject, tasteHeaders } from '../lib/tasteSession';
import { SectionEyebrow } from './brand/SectionEyebrow';
import './AletheiaHook.css';

const POSTS = `${API_URL}/api/v1/posts`;
const TASTE = `${API_URL}/api/v1/taste`;

/**
 * The consumer "read deeper" hook (Darshan Track F) — the Écart, the pause Darshan
 * opens in the scroll.
 *
 * This is the LITE variant of Track D's Visual pane, extracted rather than rebuilt: the
 * same normalized SVG, the same one-tap gesture (D's `togglePriority`), the same reading
 * engine. What's stripped is everything that makes the creator's surface deep — no parts
 * panel, no note, no intensity slider, no detection verbs. A consumer never annotates.
 *
 * Two taps are the whole product, and each is a taste signal:
 *   · tap a part the reading points at  → `region_tap`
 *   · tap one option of the perceptual fork → `fork`
 *
 * Nothing is captured until the viewer explicitly opts in (F4). Their taste is shown
 * back to them, and they can delete it — "taste given back, not harvested."
 */
export default function AletheiaHook({ postId }) {
    const [post, setPost] = useState(null);
    const [hook, setHook] = useState(null);
    const [loading, setLoading] = useState(false);
    const [optedIn, setOptedIn] = useState(false);
    const [chosen, setChosen] = useState(null);
    const [tapped, setTapped] = useState(new Set());
    const [portfolio, setPortfolio] = useState(null);
    const [error, setError] = useState('');

    useEffect(() => {
        fetch(`${POSTS}/${postId}`).then(r => r.json()).then(setPost).catch(() => setError('Could not load the image.'));
        fetch(`${TASTE}/consent`, { headers: tasteHeaders() })
            .then(r => r.json()).then(d => setOptedIn(!!d.opted_in)).catch(() => {});
    }, [postId]);

    const refreshPortfolio = useCallback(async () => {
        const res = await fetch(`${TASTE}/portfolio`, { headers: tasteHeaders() });
        if (res.ok) setPortfolio(await res.json());
    }, []);

    useEffect(() => { if (optedIn) refreshPortfolio(); }, [optedIn, refreshPortfolio]);

    const setConsent = async (value) => {
        const res = await fetch(`${TASTE}/consent`, {
            method: 'POST', headers: tasteHeaders(), body: JSON.stringify({ opted_in: value }),
        });
        if (res.ok) { setOptedIn(value); if (!value) setPortfolio(null); }
    };

    const readDeeper = async () => {
        setLoading(true); setError('');
        try {
            const res = await fetch(`${POSTS}/${postId}/aletheia-read`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ depth: 'hook' }),
            });
            if (!res.ok) throw new Error();
            setHook((await res.json()).aletheia);
        } catch { setError('The reading is unavailable right now.'); }
        finally { setLoading(false); }
    };

    // One batched POST per gesture. Signals are events, never Regions — the consumer's
    // tap must not write into the creator's curated array.
    const sendSignal = async (signal) => {
        if (!optedIn) return;   // opt-in is the gate; silence is the default
        try {
            await fetch(`${TASTE}/signals`, {
                method: 'POST', headers: tasteHeaders(),
                body: JSON.stringify({ signals: [{ post_id: postId, ...signal }] }),
            });
            refreshPortfolio();
        } catch { /* a lost signal is not worth interrupting a viewer for */ }
    };

    const tapRegion = (regionId) => {
        setTapped(s => new Set(s).add(regionId));
        sendSignal({ signal_type: 'region_tap', region_id: regionId, lens: lens?.name });
    };

    const tapFork = (choice, index) => {
        setChosen(choice);
        sendSignal({
            signal_type: 'fork', prompt: fork?.prompt, choice, choice_index: index,
            lens: lens?.name, region_id: (lens?.region_ids || [])[0] || null,
        });
    };

    const clearMyTaste = async () => {
        await fetch(`${TASTE}/signals`, { method: 'DELETE', headers: tasteHeaders() });
        forgetSubject();
        setPortfolio(null); setOptedIn(false); setChosen(null); setTapped(new Set());
    };

    if (!post) return <div className="hook-shell"><p className="hook-muted">{error || 'Loading…'}</p></div>;

    const lens = hook?.lenses?.[0];
    const fork = hook?.questions?.[0];
    const cited = new Set(lens?.region_ids || []);
    const regions = (post.region_annotations || []).filter(r => cited.has(r.id));

    return (
        <div className="hook-shell">
            <div className="hook-card">
                <div className="hook-stage">
                    <img src={post.photo_url} alt="" referrerPolicy="no-referrer" />
                    {/* Only the parts the reading actually points at are tappable. The
                        consumer is never shown forty boxes — they're shown what was read. */}
                    {lens && (
                        <svg className="hook-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
                            {regions.map(r => {
                                const poly = Array.isArray(r.polygon) && r.polygon.length > 2;
                                const cls = `hook-shape${tapped.has(r.id) ? ' is-tapped' : ''}`;
                                const common = {
                                    className: cls, vectorEffect: 'non-scaling-stroke',
                                    onClick: () => tapRegion(r.id),
                                };
                                if (poly) return <polygon key={r.id} {...common}
                                    points={r.polygon.map(([x, y]) => `${x * 100},${y * 100}`).join(' ')} />;
                                const b = r.box || {};
                                return <rect key={r.id} {...common}
                                    x={b.x * 100} y={b.y * 100} width={b.w * 100} height={b.h * 100} />;
                            })}
                        </svg>
                    )}
                    {!hook && (
                        <button className="hook-cta" onClick={readDeeper} disabled={loading}>
                            {loading ? <span className="hook-spin" /> : <Sparkles size={15} />}
                            Read this deeper
                        </button>
                    )}
                </div>

                {hook && (
                    <div className="hook-body">
                        <span className="hook-kicker">{lens?.name}</span>
                        <p className="hook-reading">{lens?.reading}</p>

                        {fork && (
                            <div className="hook-fork">
                                <p className="hook-prompt">{fork.prompt}</p>
                                <div className="hook-options">
                                    {fork.options.map((opt, i) => (
                                        <button key={opt}
                                            className={`hook-option${chosen === opt ? ' on' : ''}`}
                                            onClick={() => tapFork(opt, i)}>
                                            {chosen === opt && <Check size={13} />} {opt}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        {regions.length > 0 && (
                            <p className="hook-hint">
                                Tap a part of the image the reading rests on — {tapped.size > 0
                                    ? `${tapped.size} noted` : 'it tells your taste which part moved you'}.
                            </p>
                        )}
                        {/* CIRCUIT-001 P1C — the lens cites parts that are no longer in the
                            image. Previously this produced zero tappable shapes AND no hint,
                            because the hint was guarded by `regions.length > 0`: the reading
                            stood unchanged over an image it could no longer point at, and
                            said nothing. States the absence, never a cause. */}
                        {cited.size > 0 && regions.length === 0 && (
                            <p className="hook-hint hook-hint--absent">
                                The parts this reading points at are no longer in the image.
                            </p>
                        )}
                    </div>
                )}
            </div>

            {/* Consent + the portfolio: the reciprocity that earns the opt-in. */}
            <aside className="hook-taste">
                {!optedIn ? (
                    <div className="hook-consent">
                        <SectionEyebrow className="hook-kicker">Your taste</SectionEyebrow>
                        <p className="hook-muted">
                            Nothing is captured unless you say so. Turn this on and your taps build
                            <strong> your own taste portfolio</strong> — shown back to you, deletable
                            any time, never sold as your identity.
                        </p>
                        <button className="hook-primary" onClick={() => setConsent(true)}>
                            Turn on taste capture
                        </button>
                    </div>
                ) : (
                    <div className="hook-portfolio">
                        <div className="hook-portfolio-head">
                            <SectionEyebrow className="hook-kicker">Your taste</SectionEyebrow>
                            <button className="hook-ghost" onClick={clearMyTaste} title="Delete every signal">
                                <Trash2 size={13} /> Clear
                            </button>
                        </div>
                        {portfolio?.totals?.signals ? (
                            <>
                                <p className="hook-muted">
                                    {portfolio.totals.signals} signals · {portfolio.totals.images} images
                                </p>
                                {['parts', 'lenses', 'attributes'].map(group => (
                                    portfolio.leans[group]?.length > 0 && (
                                        <div key={group} className="hook-lean">
                                            <span className="hook-lean-label">{group}</span>
                                            <div className="hook-lean-chips">
                                                {portfolio.leans[group].slice(0, 5).map(l => (
                                                    <span key={l.name} className="hook-chip">{l.name} ·{l.count}</span>
                                                ))}
                                            </div>
                                        </div>
                                    )
                                ))}
                                {!Object.values(portfolio.leans).some(v => v.length) && (
                                    <p className="hook-muted">Your eye is still forming — a lean needs more than one tap.</p>
                                )}
                            </>
                        ) : (
                            <p className="hook-muted">No signals yet. Tap a part, or answer the fork.</p>
                        )}
                        <button className="hook-ghost" onClick={() => setConsent(false)}>Turn off capture</button>
                    </div>
                )}
                <p className="hook-subject">session <code>{getSubject().slice(0, 12)}…</code> — an opaque id, not you</p>
            </aside>

            {error && <p className="hook-error">{error}</p>}
        </div>
    );
}
