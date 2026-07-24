import React from 'react';
import { Link } from 'react-router-dom';
import { SemantMark } from './brand/SemantMark';
import { SectionEyebrow } from './brand/SectionEyebrow';
import './PlaceholderPage.css';

/**
 * Branded 404 — the same calm Fraunces language as PlaceholderPage, led by the
 * Ground mark. "A region you were looking for isn't on this ground" plays the
 * brand metaphor straight rather than shrugging with a generic error.
 */
export default function NotFoundPage() {
  return (
    <div className="placeholder">
      <div className="placeholder-inner">
        <SemantMark size={52} color="var(--accent)" title="" aria-hidden="true" style={{ marginBottom: '1.25rem' }} />
        <SectionEyebrow className="placeholder-eyebrow">404 — off the ground</SectionEyebrow>
        <h1 className="placeholder-title">Nothing to read here</h1>
        <p className="placeholder-lede">
          This region isn't on the ground — the page may have moved, or the link
          mis-remembered. Head back to the front door and pick up the thread.
        </p>
        <Link to="/" className="placeholder-pill">
          Return home <span aria-hidden>→</span>
        </Link>
      </div>
    </div>
  );
}
