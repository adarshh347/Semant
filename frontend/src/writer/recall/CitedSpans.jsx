import React from 'react';
import './Recall.css';

/**
 * Semant Writer · W9 — what the next render has been asked to stay consistent with.
 *
 * Standing beside the Render button rather than buried in a panel, because a citation
 * changes what the model is given and the author should never be surprised by one. Each
 * entry is removable, and the whole list is empty by default: there is no auto-citation,
 * so nothing is here unless the author put it here.
 *
 * It shows the LOCATION and version, not the prose. The full text is in the recall panel
 * where they chose it; repeating it here would turn the composition surface into a place
 * where earlier prose sits inline, one drag away from being pasted into the book — which
 * is the auto-insertion W9 forbids, arriving as a convenience.
 */
export default function CitedSpans({ cited = [], onUncite = null }) {
  if (!cited.length) return null;

  return (
    <div className="writer-cited" data-testid="cited-spans">
      <span className="writer-cited__label">
        Staying consistent with {cited.length}{' '}
        {cited.length === 1 ? 'passage' : 'passages'}:
      </span>
      <ul>
        {cited.map((span) => (
          <li key={`${span.lineage_id}@${span.version}`} data-testid="cited-span">
            <span className="writer-cited__where">
              {[span.location?.chapter_title, span.location?.scene_title]
                .filter(Boolean)
                .join(' · ') || span.lineage_id}
              <span className="writer-cited__version"> v{span.version}</span>
            </span>
            {onUncite && (
              <button
                type="button"
                data-testid="cited-remove"
                aria-label="stop citing this passage"
                onClick={() => onUncite(span)}
              >
                ×
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
