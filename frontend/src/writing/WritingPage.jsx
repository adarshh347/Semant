import React from 'react';
import { Link } from 'react-router-dom';
import { SectionEyebrow } from '../components/brand/SectionEyebrow';
import { articles, formatDate } from './articles.js';
import './writing.css';

/**
 * /writing — the index.
 *
 * A quiet editorial list, newest first. Everything is compiled in (see
 * articles.js), so there is no loading state and no fetch: the section renders
 * with the backend down.
 */
export default function WritingPage() {
    React.useEffect(() => {
        const prev = document.title;
        document.title = 'Writing — Semant';
        return () => { document.title = prev; };
    }, []);

    return (
        <main className="writing-page">
            <header className="writing-hero">
                <SectionEyebrow className="eyebrow">Writing</SectionEyebrow>
                <h1 className="writing-hero-title">Essays</h1>
                <p className="writing-hero-lede">
                    Notes on looking at images with instruments that can be held to account.
                </p>
            </header>

            {articles.length === 0 ? (
                <p className="writing-empty">Nothing published yet.</p>
            ) : (
                <ul className="writing-list">
                    {articles.map((a) => (
                        <li className="writing-item" key={a.slug}>
                            <Link className="writing-card" to={`/writing/${a.slug}`}>
                                <div className="writing-card-meta">
                                    {a.series && <span className="writing-card-series">{a.series}</span>}
                                    {a.date && <time dateTime={a.date}>{formatDate(a.date)}</time>}
                                </div>
                                <h2 className="writing-card-title">{a.title}</h2>
                                {a.blurb && <p className="writing-card-blurb">{a.blurb}</p>}
                            </Link>
                        </li>
                    ))}
                </ul>
            )}
        </main>
    );
}
