import React from 'react';
import { Link } from 'react-router-dom';
import { FIELD_NOTES, CATEGORY_LABEL, STATUS_LABEL } from '../content/fieldNotes';
import './FieldNotes.css';

/**
 * Semant Field Notes — index of the six feature articles behind the landing.
 * Grouped view; each card links to /notes/:slug. Twilight surface, matching the
 * perception-engineering landing.
 */
export default function FieldNotesPage() {
  return (
    <div className="fnotes">
      <div className="fnotes-wrap">
        <p className="fnotes-eyebrow">Semant Field Notes</p>
        <h1 className="fnotes-title">Notes from the workbench.</h1>
        <p className="fnotes-lede">
          The landing is the view from altitude. These are the mechanisms beneath it —
          what is built, what is emerging, and where each one goes next. Every note is
          grounded in the engine as it actually stands.
        </p>

        <div className="fnotes-grid">
          {FIELD_NOTES.map((n) => (
            <Link className="fnote-card" to={`/notes/${n.slug}`} key={n.slug}>
              <div className="fnote-card-head">
                <span className="fnote-cat">{CATEGORY_LABEL[n.category]}</span>
                <span className={`perc-chip perc-chip--${n.status}`}>{STATUS_LABEL[n.status]}</span>
              </div>
              <h2>{n.title}</h2>
              <p>{n.summary}</p>
              <span className="fnote-more">Read the note →</span>
            </Link>
          ))}
        </div>

        <p className="fnotes-back"><Link to="/">← Back to the landing</Link></p>
      </div>
    </div>
  );
}
