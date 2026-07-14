import React from 'react';
import { Link } from 'react-router-dom';
import './PlaceholderPage.css';

/**
 * A calm, on-taste placeholder for primary-nav destinations that don't have a
 * full page yet (Atelier, You). Follows the Semant design language: one big
 * Fraunces title, muted body at a short measure, a single ink-pill CTA, oceans
 * of whitespace. Honest by design — it says what the room is for and points to
 * the real on-ramp, rather than faking a finished feature.
 */
export default function PlaceholderPage({ eyebrow, title, lede, cta, links }) {
  return (
    <div className="placeholder">
      <div className="placeholder-inner">
        {eyebrow && <span className="placeholder-eyebrow">{eyebrow}</span>}
        <h1 className="placeholder-title">{title}</h1>
        {lede && <p className="placeholder-lede">{lede}</p>}

        {cta && (
          <Link to={cta.to} className="placeholder-pill">
            {cta.label} <span aria-hidden>→</span>
          </Link>
        )}

        {links && links.length > 0 && (
          <nav className="placeholder-links" aria-label={`${title} sections`}>
            {links.map((l) => (
              <Link key={l.to} to={l.to} className="placeholder-link">
                {l.label}
              </Link>
            ))}
          </nav>
        )}
      </div>
    </div>
  );
}
