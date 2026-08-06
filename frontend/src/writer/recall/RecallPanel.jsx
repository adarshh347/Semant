import React, { useState } from 'react';
import './Recall.css';

/**
 * Semant Writer · W9 — the manuscript's memory of itself, on screen.
 *
 * WHAT THIS PANEL SHOWS IS THE AUTHOR'S OWN SENTENCES, AND NOTHING ELSE. No summary line
 * above the results, no "you established…", no highlighted keywords inserted into the
 * prose, no truncation with an ellipsis this component chose. Every one of those is a
 * small edit to the author's book performed by the tool, and the last is the sneakiest:
 * a "…" is a sentence boundary the author did not write, and once it is on screen the
 * author cannot tell it from one they did.
 *
 * Spans render in a `<blockquote>` with `white-space: pre-wrap` so the two-tier cadence
 * survives — in this editor the line turns are meaning, not formatting.
 *
 * EMPTY IS A RESULT, NOT A FAILED SEARCH. When nothing matches, the panel says so plainly
 * and offers nothing in its place. The temptation here is to fill the space with something
 * helpful ("you might be thinking of…"), which is exactly the fabrication the verbatim rule
 * exists to prevent, arriving through the UI instead of through the model.
 *
 * CITING IS THE AUTHOR'S ACT. Marking a span as grounding for the next render is a click
 * they make. There is no auto-cite, and there is NO "insert into manuscript" — copying
 * prior prose into the book would be the model deciding to repeat the author.
 */
export default function RecallPanel({
  onRecall,
  cited = [],
  onCite = null,
  onUncite = null,
  onJumpTo = null,
  onClose = null,
}) {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [includeHistorical, setIncludeHistorical] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const search = async (event) => {
    event?.preventDefault?.();
    if (!query.trim()) return;
    setError('');
    setBusy(true);
    try {
      setResult(await onRecall({ query: query.trim(), includeHistorical }));
    } catch (err) {
      setError(err.message || 'the search did not go through');
      setResult(null);
    } finally {
      setBusy(false);
    }
  };

  const isCited = (span) =>
    cited.some((c) => c.lineage_id === span.lineage_id && c.version === span.version);

  return (
    <section className="writer-recall" data-testid="recall-panel">
      <header className="writer-recall__head">
        <h4>What have I already written?</h4>
        <p className="writer-recall__note">
          Your own committed passages, exactly as you wrote them. Nothing here is a summary.
        </p>
        {onClose && (
          <button type="button" data-testid="recall-close" onClick={onClose}>close</button>
        )}
      </header>

      <form className="writer-recall__form" onSubmit={search}>
        <input
          data-testid="recall-query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="the cold room, her sister, the latch…"
          aria-label="Search your committed prose"
        />
        <button type="submit" data-testid="recall-search" disabled={busy || !query.trim()}>
          {busy ? 'Searching…' : 'Recall'}
        </button>
        <label className="writer-recall__historical">
          <input
            type="checkbox"
            data-testid="recall-historical"
            checked={includeHistorical}
            onChange={(e) => setIncludeHistorical(e.target.checked)}
          />
          <span>include versions you have replaced</span>
        </label>
      </form>

      {error && <p className="writer-recall__error" data-testid="recall-error">{error}</p>}

      {result && result.spans.length === 0 && (
        // An honest empty. Deliberately nothing offered in its place.
        <p className="writer-recall__empty" data-testid="recall-empty">
          {result.empty_reason}
        </p>
      )}

      {result && result.spans.length > 0 && (
        <>
          <p className="writer-recall__count" data-testid="recall-count">
            {result.spans.length} of your {result.searched} committed{' '}
            {result.searched === 1 ? 'passage' : 'passages'}
          </p>
          <ul className="writer-recall__list">
            {result.spans.map((span) => (
              <li
                key={`${span.lineage_id}@${span.version}`}
                className="writer-span"
                data-testid="recall-span"
              >
                {/* The author's words. Unhighlighted, unclipped, uncommented. */}
                <blockquote className="writer-span__text" data-testid="span-text">
                  {span.text}
                </blockquote>

                <footer className="writer-span__foot">
                  <span className="writer-span__where" data-testid="span-location">
                    {[span.location?.chapter_title, span.location?.scene_title]
                      .filter(Boolean)
                      .join(' · ') || 'somewhere in this manuscript'}
                    <span className="writer-span__version"> v{span.version}</span>
                  </span>

                  {onJumpTo && (
                    <button
                      type="button"
                      data-testid="span-jump"
                      onClick={() => onJumpTo(span)}
                    >
                      go to it
                    </button>
                  )}
                  {onCite && (
                    isCited(span) ? (
                      <button
                        type="button"
                        data-testid="span-uncite"
                        onClick={() => onUncite?.(span)}
                      >
                        stop citing
                      </button>
                    ) : (
                      <button
                        type="button"
                        data-testid="span-cite"
                        onClick={() => onCite(span)}
                        title="The next render will be asked to stay consistent with this"
                      >
                        cite this
                      </button>
                    )
                  )}
                </footer>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
