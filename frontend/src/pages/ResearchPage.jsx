import React, { useState, useEffect, useRef, useCallback } from 'react';
import { researchService } from '../services/researchService';
import EmptyState from '../components/brand/EmptyState';
import './ResearchPage.css';

/* ------------------------------------------------------------------ */
/*  Sankalpa panel — visualises the reader's inferred will            */
/* ------------------------------------------------------------------ */

function WeightedBars({ title, items, max = 5 }) {
    const ranked = [...(items || [])].sort((a, b) => b.weight - a.weight).slice(0, max);
    if (!ranked.length) return (
        <div className="sk-group">
            <h4 className="sk-group-title">{title}</h4>
            <p className="sk-empty">Not yet inferred.</p>
        </div>
    );
    return (
        <div className="sk-group">
            <h4 className="sk-group-title">{title}</h4>
            {ranked.map((it) => (
                <div className="sk-bar-row" key={it.name}>
                    <span className="sk-bar-label">{it.name}</span>
                    <span className="sk-bar-track">
                        <span className="sk-bar-fill" style={{ width: `${Math.round(it.weight)}%` }} />
                    </span>
                </div>
            ))}
        </div>
    );
}

function FormMeter({ label, value, lowText, highText }) {
    return (
        <div className="sk-meter">
            <div className="sk-meter-head">
                <span>{lowText}</span><span>{highText}</span>
            </div>
            <div className="sk-meter-track">
                <span className="sk-meter-dot" style={{ left: `${Math.round(value)}%` }} />
            </div>
            <div className="sk-meter-label">{label}</div>
        </div>
    );
}

function SankalpaPanel({ profile, pulsing }) {
    if (!profile) return null;
    const form = profile.form || {};
    return (
        <aside className={`sankalpa-panel${pulsing ? ' is-pulsing' : ''}`}>
            <div className="sk-header">
                <span className="sk-eyebrow">Sankalpa · संकल्प</span>
                <h3 className="sk-title">The reader's will</h3>
                <p className="sk-reading">{profile.reading}</p>
                <span className="sk-count">{profile.signals_count || 0} signals read</span>
            </div>
            <WeightedBars title="Leaning themes" items={profile.themes} max={5} />
            <WeightedBars title="Tones" items={profile.tones} max={4} />
            <WeightedBars title="Interpretive lenses" items={profile.lenses} max={4} />
            <div className="sk-group">
                <h4 className="sk-group-title">Form</h4>
                <FormMeter label="Length" value={form.length ?? 50} lowText="short" highText="long" />
                <FormMeter label="Image density" value={form.image_density ?? 50} lowText="sparse" highText="image-rich" />
                <FormMeter label="Depth" value={form.depth ?? 50} lowText="skim" highText="deep" />
            </div>
        </aside>
    );
}

/* ------------------------------------------------------------------ */
/*  Run progress                                                       */
/* ------------------------------------------------------------------ */

function RunProgress({ run }) {
    if (!run) return null;
    // Collapse repeated step labels, keeping the latest status of each.
    const byLabel = new Map();
    (run.steps || []).forEach((s) => byLabel.set(s.label, s));
    const steps = [...byLabel.values()];
    return (
        <div className="run-progress">
            <div className="run-progress-head">
                <span className="run-spinner" aria-hidden="true" />
                <span>The agent is working…</span>
            </div>
            <ul className="run-steps">
                {steps.map((s) => (
                    <li key={s.label} className={`run-step run-step--${s.status}`}>
                        <span className="run-step-dot" />
                        <span className="run-step-label">{s.label}</span>
                        {s.detail && <span className="run-step-detail">{s.detail}</span>}
                    </li>
                ))}
            </ul>
        </div>
    );
}

/* ------------------------------------------------------------------ */
/*  Article reader (with feedback affordances)                         */
/* ------------------------------------------------------------------ */

const REACTIONS = [
    { key: 'resonates', label: 'Resonates' },
    { key: 'go_deeper', label: 'Go deeper' },
    { key: 'not_me', label: 'Not me' },
];

function ArticleReader({ article, onExplicit, registerSection }) {
    const [rating, setRating] = useState(0);
    const [reactions, setReactions] = useState({});
    const [mcq, setMcq] = useState({});
    const [images, setImages] = useState({}); // section_id/leftover idx -> kept bool

    useEffect(() => {
        // reset local UI state when a new article loads
        setRating(0); setReactions({}); setMcq({}); setImages({});
    }, [article?.id]);

    const react = (sectionId, reaction) => {
        setReactions((r) => ({ ...r, [sectionId]: reaction }));
        onExplicit([{ type: 'section', payload: { section_id: sectionId, reaction } }]);
    };

    const choose = (question, choice) => {
        setMcq((m) => ({ ...m, [question]: choice }));
        onExplicit([{ type: 'mcq', payload: { question, choice } }]);
    };

    const rate = (value) => {
        setRating(value);
        onExplicit([{ type: 'rating', payload: { value } }]);
    };

    const toggleImage = (key, kept) => {
        setImages((im) => ({ ...im, [key]: kept }));
        onExplicit([{ type: 'image', payload: { kept } }]);
    };

    return (
        <article className="article-reader">
            <header className="article-head">
                <div className="article-meta">
                    <span className="article-lens">{article.angle}</span>
                    {article.source_tags?.slice(0, 4).map((t) => (
                        <span className="article-tag" key={t}>{t}</span>
                    ))}
                </div>
                <h1 className="article-title">{article.title}</h1>
                {article.abstract && <p className="article-abstract">{article.abstract}</p>}
                {article.rationale && <p className="article-rationale">Why now — {article.rationale}</p>}
            </header>

            {article.sections.map((s) => (
                <section
                    key={s.section_id}
                    className="article-section"
                    ref={(el) => registerSection(s.section_id, el)}
                    data-section-id={s.section_id}
                >
                    {s.heading && <h2 className="section-heading">{s.heading}</h2>}
                    {s.image && (
                        <figure
                            className="section-figure"
                            onMouseEnter={() => registerSection(`img:${s.section_id}`, null, Date.now())}
                            onMouseLeave={() => {
                                const ms = registerSection(`img:${s.section_id}`, null);
                                if (ms > 1200) onExplicit([{ type: 'linger', payload: { image_id: s.image.post_id, ms } }], true);
                            }}
                        >
                            <img src={s.image.url} alt={s.image.caption} loading="lazy" />
                            <figcaption>{s.image.caption}</figcaption>
                        </figure>
                    )}
                    {s.content.split(/\n{2,}/).map((para, i) => (
                        <p className="section-para" key={i}>{para}</p>
                    ))}

                    <div className="section-reactions">
                        {REACTIONS.map((r) => (
                            <button
                                key={r.key}
                                className={`react-chip${reactions[s.section_id] === r.key ? ' is-active' : ''}`}
                                onClick={() => react(s.section_id, r.key)}
                            >
                                {r.label}
                            </button>
                        ))}
                    </div>
                </section>
            ))}

            {article.leftover_images?.length > 0 && (
                <section className="article-plate">
                    <h2 className="section-heading">Held in reserve</h2>
                    <p className="plate-note">Images the agent gathered but didn't place. Keep the ones that belong.</p>
                    <div className="plate-grid">
                        {article.leftover_images.map((img, i) => {
                            const key = `leftover:${i}`;
                            const kept = images[key];
                            return (
                                <figure key={key} className={`plate-item${kept === false ? ' is-dropped' : ''}`}>
                                    <img src={img.url} alt={img.caption} loading="lazy" />
                                    <figcaption>{img.caption}</figcaption>
                                    <div className="plate-actions">
                                        <button className={`react-chip${kept === true ? ' is-active' : ''}`} onClick={() => toggleImage(key, true)}>Keep</button>
                                        <button className={`react-chip${kept === false ? ' is-active' : ''}`} onClick={() => toggleImage(key, false)}>Drop</button>
                                    </div>
                                </figure>
                            );
                        })}
                    </div>
                </section>
            )}

            {article.steering_questions?.length > 0 && (
                <section className="article-steering">
                    <span className="sk-eyebrow">Steer the next one</span>
                    <h2 className="section-heading">Where should the agent look next?</h2>
                    {article.steering_questions.map((q) => (
                        <div className="steer-q" key={q.prompt}>
                            <p className="steer-prompt">{q.prompt}</p>
                            <div className="steer-options">
                                {q.options.map((opt) => (
                                    <button
                                        key={opt}
                                        className={`mcq-option${mcq[q.prompt] === opt ? ' is-active' : ''}`}
                                        onClick={() => choose(q.prompt, opt)}
                                    >
                                        {opt}
                                    </button>
                                ))}
                            </div>
                        </div>
                    ))}
                </section>
            )}

            <section className="article-rating">
                <span className="sk-eyebrow">How did this land?</span>
                <div className="star-row">
                    {[1, 2, 3, 4, 5].map((n) => (
                        <button
                            key={n}
                            className={`star${n <= rating ? ' is-filled' : ''}`}
                            onClick={() => rate(n)}
                            aria-label={`${n} stars`}
                        >★</button>
                    ))}
                </div>
            </section>
        </article>
    );
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function ResearchPage() {
    const [sankalpa, setSankalpa] = useState(null);
    const [skPulse, setSkPulse] = useState(false);
    const [articles, setArticles] = useState([]);
    const [current, setCurrent] = useState(null);
    const [run, setRun] = useState(null);
    const [running, setRunning] = useState(false);
    const [topic, setTopic] = useState('');
    const [error, setError] = useState('');

    const pollRef = useRef(null);
    // implicit-signal accumulators
    const dwellRef = useRef({});       // sectionId -> { in: ts|null, acc: ms }
    const lingerRef = useRef({});      // key -> ts
    const scrollRef = useRef(0);
    const observerRef = useRef(null);
    const sectionEls = useRef({});

    /* ---- initial load ---- */
    useEffect(() => {
        (async () => {
            try {
                const [sk, list] = await Promise.all([
                    researchService.getSankalpa(),
                    researchService.listArticles(1, 20),
                ]);
                setSankalpa(sk);
                setArticles(list.articles || []);
                if (list.articles?.length) {
                    const full = await researchService.getArticle(list.articles[0].id);
                    setCurrent(full);
                }
            } catch (e) {
                setError(e.message);
            }
        })();
        return () => clearInterval(pollRef.current);
    }, []);

    /* ---- implicit dwell tracking via IntersectionObserver ---- */
    const registerSection = useCallback((id, el, mark) => {
        // dual-purpose: section refs (el provided) + linger timing (mark/return ms)
        if (id.startsWith('img:') || id.startsWith('leftover')) {
            if (mark) { lingerRef.current[id] = mark; return; }
            const start = lingerRef.current[id];
            if (start) { delete lingerRef.current[id]; return Date.now() - start; }
            return 0;
        }
        if (el) sectionEls.current[id] = el;
        else delete sectionEls.current[id];
    }, []);

    useEffect(() => {
        // (re)build observer whenever the current article changes
        if (observerRef.current) observerRef.current.disconnect();
        dwellRef.current = {};
        scrollRef.current = 0;
        if (!current) return;

        const obs = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                const id = entry.target.dataset.sectionId;
                if (!id) return;
                const d = dwellRef.current[id] || { in: null, acc: 0 };
                if (entry.isIntersecting) {
                    d.in = Date.now();
                } else if (d.in) {
                    d.acc += Date.now() - d.in;
                    d.in = null;
                }
                dwellRef.current[id] = d;
            });
        }, { threshold: 0.5 });

        // observe after paint
        const t = setTimeout(() => {
            Object.values(sectionEls.current).forEach((el) => el && obs.observe(el));
        }, 100);
        observerRef.current = obs;

        const onScroll = () => {
            const doc = document.documentElement;
            const max = doc.scrollHeight - doc.clientHeight;
            if (max > 0) scrollRef.current = Math.max(scrollRef.current, Math.round((doc.scrollTop / max) * 100));
        };
        window.addEventListener('scroll', onScroll, { passive: true });

        return () => { clearTimeout(t); obs.disconnect(); window.removeEventListener('scroll', onScroll); };
    }, [current]);

    /* ---- flush implicit signals (beacon) ---- */
    const flushImplicit = useCallback((articleId) => {
        if (!articleId) return;
        const signals = [];
        Object.entries(dwellRef.current).forEach(([id, d]) => {
            let ms = d.acc + (d.in ? Date.now() - d.in : 0);
            if (ms > 800) signals.push({ type: 'dwell', payload: { section_id: id, ms: Math.round(ms) } });
        });
        if (scrollRef.current > 0) signals.push({ type: 'scroll', payload: { depth: scrollRef.current } });
        if (signals.length) researchService.beaconFeedback(articleId, signals);
        dwellRef.current = {};
        scrollRef.current = 0;
    }, []);

    // flush on tab hide / unmount
    useEffect(() => {
        const onHide = () => { if (document.hidden) flushImplicit(current?.id); };
        document.addEventListener('visibilitychange', onHide);
        return () => { document.removeEventListener('visibilitychange', onHide); flushImplicit(current?.id); };
    }, [current, flushImplicit]);

    /* ---- run the agent ---- */
    const runAgent = async () => {
        setError('');
        flushImplicit(current?.id);
        try {
            setRunning(true);
            const started = await researchService.runAgent({ topic: topic.trim() || null });
            setTopic('');
            pollRef.current = setInterval(async () => {
                try {
                    const r = await researchService.getRun(started.id);
                    setRun(r);
                    if (r.status === 'done' || r.status === 'failed') {
                        clearInterval(pollRef.current);
                        setRunning(false);
                        if (r.status === 'done' && r.article_id) {
                            const full = await researchService.getArticle(r.article_id);
                            setCurrent(full);
                            setRun(null);
                            window.scrollTo({ top: 0, behavior: 'smooth' });
                            const list = await researchService.listArticles(1, 20);
                            setArticles(list.articles || []);
                        } else if (r.status === 'failed') {
                            setError(r.error || 'The agent run failed.');
                        }
                    }
                } catch (e) { /* keep polling */ }
            }, 2500);
        } catch (e) {
            setError(e.message);
            setRunning(false);
        }
    };

    /* ---- explicit feedback ---- */
    const sendExplicit = async (signals, silent = false) => {
        if (!current) return;
        try {
            const res = await researchService.sendFeedback(current.id, signals);
            if (res?.sankalpa) {
                setSankalpa(res.sankalpa);
                if (!silent) { setSkPulse(true); setTimeout(() => setSkPulse(false), 900); }
            }
        } catch (e) { /* non-fatal */ }
    };

    const openArticle = async (id) => {
        flushImplicit(current?.id);
        try {
            const full = await researchService.getArticle(id);
            setCurrent(full);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } catch (e) { setError(e.message); }
    };

    return (
        <div className="research-page">
            <div className="research-hero">
                <span className="sk-eyebrow">The studio</span>
                <h1 className="research-h1">Research agent</h1>
                <p className="research-sub">
                    A background agent picks a topic from your gallery, weaves your images into an
                    essay, and learns your will through every reaction. The more you respond, the
                    more <em>Sankalpa</em> knows what you are reaching for.
                </p>
                <div className="research-controls">
                    <input
                        className="research-input"
                        placeholder="Optional: give it a topic, or leave blank to let it choose"
                        value={topic}
                        onChange={(e) => setTopic(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && !running && runAgent()}
                        disabled={running}
                    />
                    <button className="btn btn-primary research-run" onClick={runAgent} disabled={running}>
                        {running ? 'Working…' : 'Run the agent'}
                    </button>
                </div>
                {error && <p className="research-error">{error}</p>}
            </div>

            <div className="research-body">
                <main className="research-main">
                    {running && <RunProgress run={run} />}
                    {current ? (
                        <ArticleReader article={current} onExplicit={sendExplicit} registerSection={registerSection} />
                    ) : (
                        !running && (
                            <EmptyState
                                motif="infer"
                                title="Nothing inferred yet"
                                body="No articles yet. Run the agent to compose the first one from what you've been reading."
                                action={{ onClick: runAgent, label: 'Run the agent' }}
                            />
                        )
                    )}

                    {articles.length > 1 && (
                        <div className="article-archive">
                            <h3 className="archive-title">Earlier articles</h3>
                            <div className="archive-list">
                                {articles.map((a) => (
                                    <button
                                        key={a.id}
                                        className={`archive-item${current?.id === a.id ? ' is-current' : ''}`}
                                        onClick={() => openArticle(a.id)}
                                    >
                                        <span className="archive-item-title">{a.title}</span>
                                        <span className="archive-item-meta">{a.angle}</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}
                </main>

                <SankalpaPanel profile={sankalpa} pulsing={skPulse} />
            </div>
        </div>
    );
}
