import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { personaService } from '../services/personaService';
import './PersonasPage.css';

const Chips = ({ items }) => (
    <div className="dp-chips">
        {(items || []).map((it, i) => <span className="dp-chip" key={i}>{it}</span>)}
    </div>
);

function Dossier({ dossier }) {
    if (!dossier) return null;
    const voice = dossier.voice || {};
    return (
        <div className="dp-dossier">
            {dossier.summary && <p className="dp-summary">{dossier.summary}</p>}

            {dossier.identity && (
                <div className="dp-block">
                    <h4 className="dp-block-title">Identity</h4>
                    <p>{dossier.identity}</p>
                </div>
            )}

            {dossier.aesthetic?.length > 0 && (
                <div className="dp-block">
                    <h4 className="dp-block-title">Aesthetic</h4>
                    <Chips items={dossier.aesthetic} />
                </div>
            )}

            {dossier.themes?.length > 0 && (
                <div className="dp-block">
                    <h4 className="dp-block-title">Recurring themes</h4>
                    <Chips items={dossier.themes} />
                </div>
            )}

            {(voice.tone || voice.vocabulary || voice.devices) && (
                <div className="dp-block">
                    <h4 className="dp-block-title">Voice</h4>
                    <div className="dp-voice">
                        {voice.tone && <p><strong>Tone</strong> — {voice.tone}</p>}
                        {voice.vocabulary && <p><strong>Vocabulary</strong> — {voice.vocabulary}</p>}
                        {voice.devices && <p><strong>Devices</strong> — {voice.devices}</p>}
                    </div>
                </div>
            )}

            {dossier.values?.length > 0 && (
                <div className="dp-block">
                    <h4 className="dp-block-title">Values</h4>
                    <Chips items={dossier.values} />
                </div>
            )}

            {dossier.audience && (
                <div className="dp-block">
                    <h4 className="dp-block-title">Audience</h4>
                    <p>{dossier.audience}</p>
                </div>
            )}

            {dossier.generative_guide && (
                <div className="dp-block dp-generative">
                    <h4 className="dp-block-title">Create as them</h4>
                    <p>{dossier.generative_guide}</p>
                </div>
            )}

            {dossier.content_ideas?.length > 0 && (
                <div className="dp-block">
                    <h4 className="dp-block-title">Content ideas</h4>
                    <ul className="dp-ideas">
                        {dossier.content_ideas.map((c, i) => <li key={i}>{c}</li>)}
                    </ul>
                </div>
            )}

            {dossier.caption_samples?.length > 0 && (
                <div className="dp-block">
                    <h4 className="dp-block-title">Captions in their voice</h4>
                    {dossier.caption_samples.map((c, i) => (
                        <blockquote className="dp-caption" key={i}>"{c}"</blockquote>
                    ))}
                </div>
            )}
        </div>
    );
}

function PersonaDetail({ handle }) {
    const [persona, setPersona] = useState(null);
    const [images, setImages] = useState([]);
    const [synthBusy, setSynthBusy] = useState(false);
    const [error, setError] = useState('');
    const [showCaptions, setShowCaptions] = useState(false);

    useEffect(() => {
        setPersona(null); setImages([]); setError('');
        if (!handle) return;
        (async () => {
            try {
                const [p, imgs] = await Promise.all([
                    personaService.getPersona(handle),
                    personaService.getImages(handle),
                ]);
                setPersona(p);
                setImages(imgs.images || []);
            } catch (e) { setError(e.message); }
        })();
    }, [handle]);

    const synthesize = async () => {
        setError(''); setSynthBusy(true);
        try {
            const p = await personaService.synthesize(handle);
            setPersona(p);
        } catch (e) { setError('Synthesis failed — is the backend + Groq key set?'); }
        finally { setSynthBusy(false); }
    };

    if (!handle) return (
        <div className="dp-empty">
            <h3>Pick an account</h3>
            <p>Select a captured account on the left, or capture a new one with the Alexia extension.</p>
        </div>
    );
    if (error) return <div className="dp-empty"><p className="dp-error">{error}</p></div>;
    if (!persona) return <div className="dp-empty"><p>Loading @{handle}…</p></div>;

    const a = persona.account || {};
    return (
        <div className="dp-detail">
            <header className="dp-account">
                {a.avatar_url
                    ? <img className="dp-avatar" src={a.avatar_url} alt={persona.handle} referrerPolicy="no-referrer" />
                    : <div className="dp-avatar dp-avatar--blank">{persona.handle?.[0]?.toUpperCase()}</div>}
                <div className="dp-account-meta">
                    <div className="dp-account-name">
                        {a.display_name || persona.handle}
                        {a.verified && <span className="dp-verified" title="Verified">✓</span>}
                    </div>
                    <a className="dp-handle" href={`https://instagram.com/${persona.handle}`} target="_blank" rel="noopener noreferrer">@{persona.handle}</a>
                    {a.bio && <p className="dp-bio">{a.bio}</p>}
                    <div className="dp-stats">
                        {a.posts_count && <span><strong>{a.posts_count}</strong> posts</span>}
                        {a.followers && <span><strong>{a.followers}</strong> followers</span>}
                        {a.following && <span><strong>{a.following}</strong> following</span>}
                        <span><strong>{persona.matched_image_count}</strong> in our gallery</span>
                    </div>
                    {a.external_link && (
                        <a className="dp-extlink" href={a.external_link} target="_blank" rel="noopener noreferrer">{a.external_link.replace(/^https?:\/\//, '')}</a>
                    )}
                </div>
            </header>

            <div className="dp-actions">
                <button className="btn btn-primary" onClick={synthesize} disabled={synthBusy}>
                    {synthBusy ? 'Mirroring…' : persona.dossier ? 'Re-synthesize persona' : 'Synthesize persona'}
                </button>
                <Link className="dp-review-link" to={`/unconceal?handle=${encodeURIComponent(persona.handle)}`}>
                    Unconceal their images →
                </Link>
                {persona.dossier_generated_at && !synthBusy && (
                    <span className="dp-stamp">last mirrored {new Date(persona.dossier_generated_at).toLocaleString()}</span>
                )}
            </div>

            {synthBusy && !persona.dossier && (
                <div className="dp-synth-loading"><span className="dp-spin" /> Reading the account in the mirror…</div>
            )}

            <Dossier dossier={persona.dossier} />

            {images.length > 0 && (
                <div className="dp-block">
                    <h4 className="dp-block-title">Images we have from them ({images.length})</h4>
                    <div className="dp-img-grid">
                        {images.map(img => (
                            <Link to={`/posts/${img.id}`} key={img.id} className="dp-img">
                                <img src={img.photo_url} alt="" loading="lazy" referrerPolicy="no-referrer" />
                            </Link>
                        ))}
                    </div>
                </div>
            )}

            {persona.captured_captions?.length > 0 && (
                <div className="dp-block">
                    <button className="dp-collapse" onClick={() => setShowCaptions(s => !s)}>
                        {showCaptions ? '▾' : '▸'} Captured captions ({persona.captured_captions.length})
                    </button>
                    {showCaptions && (
                        <ul className="dp-captions">
                            {persona.captured_captions.map((c, i) => <li key={i}>{c}</li>)}
                        </ul>
                    )}
                </div>
            )}
        </div>
    );
}

export default function PersonasPage() {
    const [personas, setPersonas] = useState([]);
    const [selected, setSelected] = useState(null);
    const [error, setError] = useState('');

    const load = useCallback(async () => {
        try {
            const data = await personaService.listPersonas();
            const list = data.personas || [];
            setPersonas(list);
            // deep-link via #handle (the extension links here), else first persona
            const hash = decodeURIComponent((window.location.hash || '').replace('#', '')).toLowerCase();
            setSelected(prev => prev || (hash && list.find(p => p.handle === hash)?.handle) || list[0]?.handle || null);
        } catch (e) { setError(e.message); }
    }, []);

    useEffect(() => { load(); }, [load]);

    return (
        <div className="personas-page">
            <div className="dp-hero">
                <span className="dp-eyebrow">Darpan · दर्पण</span>
                <h1 className="dp-h1">Persona mirror</h1>
                <p className="dp-sub">
                    A context dossier for any Instagram account — who they are and how to create
                    as them — built from what <em>Alexia</em> reads off their profile and the images
                    we already hold of theirs.
                </p>
            </div>

            {error && <p className="dp-error">{error}</p>}

            {personas.length === 0 ? (
                <div className="dp-empty dp-empty--full">
                    <h3>No personas yet</h3>
                    <p>Open an Instagram profile in your browser, then click the <strong>“Build persona”</strong> button
                        the Alexia extension shows at the bottom-left. It captures the account and appears here.</p>
                </div>
            ) : (
                <div className="personas-body">
                    <aside className="persona-list">
                        {personas.map(p => (
                            <button
                                key={p.handle}
                                className={`persona-list-item${selected === p.handle ? ' is-active' : ''}`}
                                onClick={() => setSelected(p.handle)}
                            >
                                {p.account?.avatar_url
                                    ? <img src={p.account.avatar_url} alt="" referrerPolicy="no-referrer" />
                                    : <span className="persona-list-blank">{p.handle?.[0]?.toUpperCase()}</span>}
                                <span className="persona-list-meta">
                                    <span className="persona-list-handle">@{p.handle}</span>
                                    <span className="persona-list-sub">
                                        {p.matched_image_count} imgs{p.dossier ? ' · mirrored' : ''}
                                    </span>
                                </span>
                            </button>
                        ))}
                    </aside>
                    <main className="persona-main">
                        <PersonaDetail handle={selected} />
                    </main>
                </div>
            )}
        </div>
    );
}
