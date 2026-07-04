import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Sparkles, Eye, Star, ChevronRight, Layers, BarChart3, Search, RefreshCw } from 'lucide-react';
import {
    fetchCategories,
    fetchCategoryImages,
    synthesizeInsights,
    fetchInsights,
} from '../services/anatomyService';
import './AnatomyPage.css';

export default function AnatomyPage() {
    const [categories, setCategories] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [genreFilter, setGenreFilter] = useState('');
    const [activeGenre, setActiveGenre] = useState(null);

    // Detail panel
    const [selectedCat, setSelectedCat] = useState(null);
    const [detailImages, setDetailImages] = useState([]);
    const [detailLoading, setDetailLoading] = useState(false);

    // Insights
    const [insights, setInsights] = useState(null);
    const [insightsLoading, setInsightsLoading] = useState(false);

    // Available genre tags (extracted from categories)
    const [availableGenres, setAvailableGenres] = useState([]);

    const loadCategories = useCallback(async (tag = null) => {
        setLoading(true); setError('');
        try {
            const data = await fetchCategories({ tag, minOccurrences: 1 });
            setCategories(data.categories || []);
            // Extract unique genres from sample images' tags
            const genres = new Set();
            (data.categories || []).forEach(c =>
                (c.sample_images || []).forEach(img =>
                    (img.general_tags || []).forEach(t => genres.add(t))
                )
            );
        } catch (e) { setError('Could not load anatomy categories.'); }
        finally { setLoading(false); }
    }, []);

    const loadAvailableGenres = useCallback(async () => {
        try {
            const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:5008'}/api/v1/posts/tags/popular?limit=15`);
            if (res.ok) {
                const tags = await res.json();
                setAvailableGenres(tags || []);
            }
        } catch { /* non-fatal */ }
    }, []);

    useEffect(() => {
        loadCategories();
        loadAvailableGenres();
        fetchInsights().then(d => { if (d.cached) setInsights(d); }).catch(() => {});
    }, [loadCategories, loadAvailableGenres]);

    const applyGenre = (tag) => {
        const t = tag || null;
        setActiveGenre(t);
        loadCategories(t);
        setSelectedCat(null);
        setDetailImages([]);
    };

    const selectCategory = async (cat) => {
        setSelectedCat(cat);
        setDetailLoading(true);
        try {
            const data = await fetchCategoryImages(cat.category, cat.label, 30);
            setDetailImages(data.images || []);
        } catch { setDetailImages([]); }
        finally { setDetailLoading(false); }
    };

    const runSynthesize = async () => {
        setInsightsLoading(true);
        try {
            const data = await synthesizeInsights(activeGenre);
            setInsights(data);
        } catch { /* toast? */ }
        finally { setInsightsLoading(false); }
    };

    // Stats
    const totalOccurrences = categories.reduce((s, c) => s + c.occurrence_count, 0);
    const totalPrioritised = categories.reduce((s, c) => s + c.prioritised_count, 0);
    const topIntensity = categories.length ? Math.max(...categories.map(c => c.avg_intensity)) : 0;

    // Find the insight for a given label
    const insightFor = (label) => {
        if (!insights?.per_category) return null;
        return insights.per_category.find(
            p => (p.label || '').toLowerCase() === (label || '').toLowerCase()
        );
    };

    return (
        <div className="anatomy-page">
            {/* Hero */}
            <header className="anatomy-hero">
                <span className="eyebrow">Anatomy Catalog</span>
                <h1 className="anatomy-hero-title">
                    Your Anatomy Language
                </h1>
                <p className="anatomy-hero-sub">
                    Which parts of images consistently affect you — scaled across every image you've annotated.
                </p>
            </header>

            {/* Stats bar */}
            <div className="anatomy-stats">
                <div className="anatomy-stat">
                    <Layers size={16} />
                    <strong>{categories.length}</strong>
                    <span>categories</span>
                </div>
                <div className="anatomy-stat">
                    <BarChart3 size={16} />
                    <strong>{totalOccurrences}</strong>
                    <span>total occurrences</span>
                </div>
                <div className="anatomy-stat">
                    <Star size={16} />
                    <strong>{totalPrioritised}</strong>
                    <span>prioritised</span>
                </div>
                <div className="anatomy-stat">
                    <Eye size={16} />
                    <strong>{topIntensity}</strong>
                    <span>peak intensity</span>
                </div>
            </div>

            {/* Genre filter chips */}
            <div className="anatomy-filters">
                <button
                    className={`anatomy-genre-chip${activeGenre === null ? ' active' : ''}`}
                    onClick={() => applyGenre(null)}
                >All</button>
                {availableGenres.map(g => (
                    <button
                        key={g}
                        className={`anatomy-genre-chip${activeGenre === g ? ' active' : ''}`}
                        onClick={() => applyGenre(g)}
                    >{g}</button>
                ))}
                <div className="anatomy-filter-search">
                    <Search size={14} />
                    <input
                        placeholder="Filter by tag…"
                        value={genreFilter}
                        onChange={e => setGenreFilter(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter' && genreFilter.trim()) applyGenre(genreFilter.trim()); }}
                    />
                </div>
            </div>

            {/* Insights portrait */}
            {insights?.portrait && (
                <div className="anatomy-portrait-card">
                    <div className="anatomy-portrait-head">
                        <Sparkles size={16} />
                        <strong>Your anatomy language</strong>
                    </div>
                    <p className="anatomy-portrait-text">{insights.portrait}</p>
                </div>
            )}

            {error && <p className="anatomy-error">{error}</p>}

            {/* Main content: category grid + detail panel */}
            <div className="anatomy-main">
                {/* Category grid / treemap */}
                <div className="anatomy-grid-section">
                    <div className="anatomy-grid-head">
                        <h2>Categories</h2>
                        <button className="btn btn-ghost btn-sm" onClick={runSynthesize} disabled={insightsLoading || !categories.length}>
                            {insightsLoading ? <span className="anatomy-spin" /> : <Sparkles size={14} />}
                            {insights ? 'Re-synthesize' : 'Synthesize insights'}
                        </button>
                    </div>

                    {loading ? (
                        <div className="anatomy-loading">
                            <span className="anatomy-spin" /> Loading anatomy data…
                        </div>
                    ) : categories.length === 0 ? (
                        <div className="anatomy-empty">
                            <Eye size={32} />
                            <p>No anatomy annotations yet.</p>
                            <p className="anatomy-empty-hint">
                                Open an image in Sutradhar → Unconceal tab → <strong>Detect parts</strong> to start
                                building your anatomy catalog.
                            </p>
                        </div>
                    ) : (
                        <div className="anatomy-grid">
                            {categories.map((cat, i) => {
                                const maxOcc = categories[0]?.occurrence_count || 1;
                                const sizeFactor = 0.6 + 0.4 * (cat.occurrence_count / maxOcc);
                                const intensityPct = Math.min(cat.avg_intensity, 100);
                                const isSelected = selectedCat?.label === cat.label && selectedCat?.category === cat.category;
                                const catInsight = insightFor(cat.label);
                                return (
                                    <button
                                        key={`${cat.category}-${cat.label}-${i}`}
                                        className={`anatomy-cell${isSelected ? ' selected' : ''}${cat.prioritised_count > 0 ? ' has-priority' : ''}`}
                                        style={{
                                            '--size-factor': sizeFactor,
                                            '--intensity': `${intensityPct}%`,
                                        }}
                                        onClick={() => selectCategory(cat)}
                                    >
                                        <span className="anatomy-cell-label">{cat.label}</span>
                                        <span className="anatomy-cell-cat">{cat.category}</span>
                                        <span className="anatomy-cell-stats">
                                            {cat.occurrence_count}× · {cat.prioritised_count}★
                                            {cat.avg_intensity > 0 && ` · ${cat.avg_intensity}`}
                                        </span>
                                        {cat.materials.length > 0 && (
                                            <span className="anatomy-cell-materials">
                                                {cat.materials.slice(0, 2).join(', ')}
                                            </span>
                                        )}
                                        <div className="anatomy-cell-bar" />
                                        {catInsight && <span className="anatomy-cell-dot" title="Has insight" />}
                                    </button>
                                );
                            })}
                        </div>
                    )}
                </div>

                {/* Detail panel */}
                <div className={`anatomy-detail${selectedCat ? ' open' : ''}`}>
                    {selectedCat ? (
                        <>
                            <div className="anatomy-detail-head">
                                <div>
                                    <h3>{selectedCat.label}</h3>
                                    <span className="chip">{selectedCat.category}</span>
                                    {selectedCat.materials.map(m => (
                                        <span key={m} className="chip chip-accent">{m}</span>
                                    ))}
                                </div>
                                <button className="btn btn-ghost btn-sm" onClick={() => { setSelectedCat(null); setDetailImages([]); }}>
                                    Close
                                </button>
                            </div>

                            <div className="anatomy-detail-stats">
                                <div><strong>{selectedCat.occurrence_count}</strong> occurrences</div>
                                <div><strong>{selectedCat.prioritised_count}</strong> prioritised</div>
                                <div><strong>{selectedCat.avg_intensity}</strong> avg intensity</div>
                            </div>

                            {/* Intensity bar */}
                            <div className="anatomy-detail-bar-wrap">
                                <div className="anatomy-detail-bar" style={{ width: `${Math.min(selectedCat.avg_intensity, 100)}%` }} />
                                <span>{selectedCat.avg_intensity}</span>
                            </div>

                            {/* Per-category insight */}
                            {insightFor(selectedCat.label) && (
                                <div className="anatomy-detail-insight">
                                    <Sparkles size={14} />
                                    <p>{insightFor(selectedCat.label).insight}</p>
                                </div>
                            )}

                            {/* Curator notes */}
                            {selectedCat.notes.length > 0 && (
                                <div className="anatomy-detail-notes">
                                    <h4>Curator notes</h4>
                                    {selectedCat.notes.map((n, i) => (
                                        <blockquote key={i}>{n}</blockquote>
                                    ))}
                                </div>
                            )}

                            {/* Image grid */}
                            <div className="anatomy-detail-images">
                                <h4>Images with this part ({detailImages.length})</h4>
                                {detailLoading ? (
                                    <div className="anatomy-loading"><span className="anatomy-spin" /> Loading…</div>
                                ) : (
                                    <div className="anatomy-img-grid">
                                        {detailImages.map((img, i) => (
                                            <Link key={i} to={`/posts/${img.post_id}`} className="anatomy-img-card">
                                                <img src={img.photo_url} alt="" referrerPolicy="no-referrer" loading="lazy" />
                                                <div className="anatomy-img-overlay">
                                                    {img.region.prioritised && <Star size={12} fill="currentColor" />}
                                                    {img.region.weight > 0 && <span>{img.region.weight}</span>}
                                                </div>
                                                {img.region.user_note && (
                                                    <p className="anatomy-img-note">{img.region.user_note}</p>
                                                )}
                                            </Link>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </>
                    ) : (
                        <div className="anatomy-detail-empty">
                            <ChevronRight size={20} />
                            <p>Select a category to see details and images</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
