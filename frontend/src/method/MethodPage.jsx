import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { SectionEyebrow } from '../components/brand/SectionEyebrow';
import article from './content/semant-is-built-by-rehearsal.md?raw';
import '../writing/writing.css';
import './method.css';

/**
 * /method — how Semant is built.
 *
 * A single static article, inlined at build time by vite's `?raw`. No loader,
 * no fetch, no backend: this is documentation of the project's discipline, and
 * it must read correctly when every service behind it is down.
 *
 * It borrows the /writing reading surface wholesale (`writing.css`) rather than
 * inventing a second article style — same measure, same Fraunces display face,
 * same hairline rules. Deliberately NOT imported from `writing/articles.js`:
 * that module's eager `content/*.md` glob would pull every essay into this
 * chunk to reuse nothing but a class name.
 */

const MD_COMPONENTS = {
    // The article's own `# …` becomes the page's title, wearing the same style
    // the /writing reader gives an article title.
    h1: ({ node, ...props }) => <h1 className="writing-article-title" {...props} />,
    // The rehearsal loop is the one pre-formatted block here. It is tagged so
    // the narrow-screen rules in method.css can reach it without touching the
    // shared writing styles.
    pre: ({ node, ...props }) => <pre className="method-loop" {...props} />,
};

export default function MethodPage() {
    React.useEffect(() => {
        const prev = document.title;
        document.title = 'Method — Semant';
        return () => { document.title = prev; };
    }, []);

    return (
        <main className="writing-page method-page">
            <header className="method-head">
                <SectionEyebrow className="eyebrow">Method</SectionEyebrow>
            </header>

            <article className="writing-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
                    {article}
                </ReactMarkdown>
            </article>
        </main>
    );
}
