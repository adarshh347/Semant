import React, { useEffect, useState } from 'react';
import './Registers.css';

/**
 * Semant Writer · W10 — the manuscript by the author's layers. DERIVED, NEVER INTERPRETED.
 *
 * WHAT THIS VIEW SHOWS is which committed spans were MADE at which layer, read off the
 * register each operator carried when it fired. What it must never show is what the book
 * MEANS at a layer. "Here is the philosophical reading of your chapter" is the model's
 * account of the author's book presented as the book's own depth — the same fabrication W9
 * refuses for summaries, on the axis where it is hardest to catch, because a confident
 * reading of a theme sounds like insight rather than invention.
 *
 * So there is no analysis panel here, no per-layer commentary, and no score. Filtering by a
 * register shows the author their own paragraphs; the meaning of those paragraphs at that
 * layer is theirs and is not the subject of any sentence this component renders.
 *
 * UNTAGGED SPANS ARE NAMED, NOT HIDDEN. Prose the author typed, or rendered before they had
 * a ladder, carries no register — and is shown as carrying none rather than being quietly
 * left out or guessed at. A classifier here would be the imposed taxonomy arriving through
 * the back door.
 */
export default function DepthView({ onLoad, onClose = null }) {
  const [view, setView] = useState(null);
  const [active, setActive] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const data = await onLoad();
        if (live) setView(data);
      } catch (err) {
        if (live) setError(err.message || 'could not load the depth view');
      }
    })();
    return () => { live = false; };
  }, [onLoad]);

  if (error) {
    return (
      <section className="writer-depth" data-testid="depth-view">
        <p className="writer-registers__error">{error}</p>
      </section>
    );
  }
  if (!view) return null;

  const vocabulary = view.vocabulary || [];
  const spans = view.spans || [];

  if (!vocabulary.length) {
    return (
      <section className="writer-depth" data-testid="depth-view">
        <p className="writer-depth__empty" data-testid="depth-no-ladder">
          You have not named any layers yet, so there is no depth axis to read your
          manuscript along. Declare your registers first — the ladder is yours to write.
        </p>
      </section>
    );
  }

  const shown = active
    ? spans.filter((s) => (s.registers || []).includes(active))
    : spans;

  return (
    <section className="writer-depth" data-testid="depth-view">
      <header className="writer-registers__head">
        <h4>Your manuscript by layer</h4>
        <p className="writer-registers__note">
          Which layers each passage was made at, from the operators that made it. Nothing
          here is a reading.
        </p>
        {onClose && (
          <button type="button" data-testid="depth-close" onClick={onClose}>close</button>
        )}
      </header>

      <div className="writer-depth__filters" data-testid="depth-filters">
        <button
          type="button"
          data-testid="depth-all"
          aria-pressed={!active}
          onClick={() => setActive('')}
        >
          all ({spans.length})
        </button>
        {/* In the AUTHOR'S order — the server returns their ladder as they sorted it. */}
        {vocabulary.map((register) => (
          <button
            key={register.name}
            type="button"
            data-testid="depth-filter"
            aria-pressed={active === register.name}
            onClick={() => setActive(active === register.name ? '' : register.name)}
            title={register.description || ''}
          >
            {register.name} ({(view.by_register?.[register.name] || []).length})
          </button>
        ))}
      </div>

      {shown.length === 0 ? (
        <p className="writer-depth__empty" data-testid="depth-empty">
          Nothing you have committed was made at that layer yet.
        </p>
      ) : (
        <ul className="writer-depth__list">
          {shown.map((span) => (
            <li key={`${span.lineage_id}@${span.version}`} className="writer-depth__span"
              data-testid="depth-span">
              {/* The author's own prose, unaltered — W9's rule holds here too. */}
              <blockquote data-testid="depth-span-text">{span.text}</blockquote>
              <footer>
                {(span.registers || []).length ? (
                  (span.registers || []).map((name) => (
                    <span key={name} className="writer-depth__tag" data-testid="depth-tag">
                      {name}
                    </span>
                  ))
                ) : (
                  // Named honestly. No guess is made about writing with nothing declared
                  // behind it.
                  <span className="writer-depth__untagged" data-testid="depth-untagged">
                    you wrote this yourself — no layer recorded
                  </span>
                )}
                <span className="writer-depth__version">v{span.version}</span>
              </footer>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
