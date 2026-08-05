import React from 'react';
import { Link, useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { SectionEyebrow } from '../components/brand/SectionEyebrow';
import { articles, getArticle, formatDate } from './articles.js';
import './writing.css';

/**
 * /writing/:slug — the reader.
 *
 * The markdown is already in the bundle, so the article paints on first render.
 * `document.title` is set per article (and restored on unmount) because this
 * section is a showcase — the tab title is part of what gets shared.
 */

// A table that scrolls inside its own box, so a wide table never makes the
// whole page scroll sideways on a phone.
const MD_COMPONENTS = {
    table: ({ node, ...props }) => (
        <div className="writing-table-wrap">
            <table {...props} />
        </div>
    ),
};

export default function WritingArticlePage() {
    const { slug } = useParams();
    const article = getArticle(slug);

    React.useEffect(() => {
        const prev = document.title;
        document.title = article ? `${article.title} — Semant` : 'Writing — Semant';
        return () => { document.title = prev; };
    }, [article]);

    // Scroll to the top when moving between articles — otherwise a click from
    // the foot of a long essay lands you mid-way down the next one.
    React.useEffect(() => { window.scrollTo(0, 0); }, [slug]);

    if (!article) {
        return (
            <main className="writing-page">
                <Link className="writing-back" to="/writing">← Writing</Link>
                <header className="writing-article-head">
                    <h1 className="writing-article-title">Not found</h1>
                    <p className="writing-article-blurb">
                        There is no essay at this address.
                    </p>
                </header>
            </main>
        );
    }

    // "Next" wraps around the list, so the last essay still offers somewhere to go.
    const idx = articles.findIndex((a) => a.slug === article.slug);
    const next = articles.length > 1 ? articles[(idx + 1) % articles.length] : null;

    return (
        <main className="writing-page">
            <Link className="writing-back" to="/writing">← Writing</Link>

            <header className="writing-article-head">
                {article.series && (
                    <SectionEyebrow className="eyebrow">{article.series}</SectionEyebrow>
                )}
                <h1 className="writing-article-title">{article.title}</h1>
                {article.blurb && <p className="writing-article-blurb">{article.blurb}</p>}
                {article.date && (
                    <p className="writing-card-meta" style={{ marginTop: '1.1rem', marginBottom: 0 }}>
                        <time dateTime={article.date}>{formatDate(article.date)}</time>
                    </p>
                )}
            </header>

            <article className="writing-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
                    {article.body}
                </ReactMarkdown>
            </article>

            {next && (
                <footer className="writing-article-foot">
                    <Link className="writing-foot-link" to={`/writing/${next.slug}`}>
                        <span className="writing-foot-label">Next</span>
                        <span className="writing-foot-title">{next.title}</span>
                    </Link>
                </footer>
            )}
        </main>
    );
}
