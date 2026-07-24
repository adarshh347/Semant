import React, { useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { FIELD_NOTES, noteBySlug, CATEGORY_LABEL, STATUS_LABEL } from '../content/fieldNotes';
import MiniMarkdown from '../components/MiniMarkdown';
import './FieldNotes.css';

/**
 * A single Semant Field Note, by slug. Renders the canonical vault essay via
 * MiniMarkdown, with a header (category + status), and prev/next navigation.
 * An unknown slug falls back to a quiet not-found within the surface.
 */
export default function FieldNotePage() {
  const { slug } = useParams();
  const note = noteBySlug(slug);

  useEffect(() => { window.scrollTo(0, 0); }, [slug]);

  if (!note) {
    return (
      <div className="fnotes">
        <div className="fnote-article">
          <p className="fnotes-eyebrow">Field note</p>
          <h1 className="fnote-h1">That note isn’t here.</h1>
          <p className="fnote-lede">The link may be old. Browse the full set instead.</p>
          <p className="fnotes-back"><Link to="/notes">← All field notes</Link></p>
        </div>
      </div>
    );
  }

  const idx = FIELD_NOTES.findIndex((n) => n.slug === note.slug);
  const prev = idx > 0 ? FIELD_NOTES[idx - 1] : null;
  const next = idx < FIELD_NOTES.length - 1 ? FIELD_NOTES[idx + 1] : null;

  return (
    <div className="fnotes">
      <article className="fnote-article">
        <p className="fnotes-back fnotes-back--top"><Link to="/notes">← Field notes</Link></p>
        <div className="fnote-meta">
          <span className="fnote-cat">{CATEGORY_LABEL[note.category]}</span>
          <span className={`perc-chip perc-chip--${note.status}`}>{STATUS_LABEL[note.status]}</span>
        </div>
        <h1 className="fnote-h1">{note.title}</h1>
        <p className="fnote-lede">{note.summary}</p>
        <hr className="fnote-rule" />

        <MiniMarkdown source={note.body} className="fnote-body" />

        <nav className="fnote-nav">
          {prev
            ? <Link className="fnote-nav-link" to={`/notes/${prev.slug}`}>← {prev.title}</Link>
            : <span />}
          {next
            ? <Link className="fnote-nav-link fnote-nav-link--next" to={`/notes/${next.slug}`}>{next.title} →</Link>
            : <span />}
        </nav>
      </article>
    </div>
  );
}
