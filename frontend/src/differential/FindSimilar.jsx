import React, { useEffect, useState } from 'react';
import { Search, RotateCw, ExternalLink, Loader2 } from 'lucide-react';
import { ringsToPath } from '../lib/maskGeometry';

/**
 * FindSimilar (VISION-E · E5) — the curator's visual-neighbour panel.
 *
 * Presents a selected Region's visual neighbours as INSPECTABLE RESEARCH, never as fact: each
 * result shows the exact-mask evidence crop, its similarity, its model space and provenance, and
 * — on hover — recalls the neighbour's exact mask in its own source image. Opening a source post
 * happens in a new tab, so the current workspace is never lost. Nothing here creates a Motif or
 * Relation; only the curator's own act does that.
 */
const MODES = [
  { key: 'identity', label: 'Identity', hint: 'the evidence itself, isolated' },
  { key: 'context', label: 'Context', hint: 'the evidence in its surroundings' },
];

const pct = (s) => (s == null ? '' : `${Math.round(s * 100)}%`);

function ResultCard({ r, cropUrl }) {
  const [inSitu, setInSitu] = useState(false);
  const rings = r.geometry?.polygons;
  return (
    <div className="es-card" onMouseEnter={() => setInSitu(true)} onMouseLeave={() => setInSitu(false)}>
      <div className="es-thumb">
        {inSitu && r.photo_url ? (
          <div className="es-insitu" title="the neighbour's exact mask in its source image">
            <img src={r.photo_url} alt="" referrerPolicy="no-referrer" />
            {rings && rings.length > 0 && (
              <svg className="es-mask" viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden>
                <path d={ringsToPath(rings, 1, 1)} />
              </svg>
            )}
          </div>
        ) : (
          <img src={cropUrl(r.post_id, r.region_id, r.role)} alt={r.label || 'evidence'}
               referrerPolicy="no-referrer" loading="lazy" />
        )}
        <span className="es-score" title="cosine similarity (within one space)">{pct(r.score)}</span>
      </div>
      <div className="es-meta">
        <span className="es-label">{r.label || <em>unnamed</em>}</span>
        <a className="es-open" href={`/posts/${r.post_id}`} target="_blank" rel="noopener noreferrer"
           title="Open the source post in a new tab (your workspace stays)">
          <ExternalLink size={11} /> source
        </a>
      </div>
      <div className="es-prov">
        <span className="es-space">{r.space?.split('|').slice(0, 2).join(' · ')}</span>
        {r.provenance?.model && <span className="es-model">{r.provenance.model}</span>}
      </div>
    </div>
  );
}

export default function FindSimilar({ regionName, status, error, results, meta, cropUrl,
                                      onFind, onReindex, onCancel }) {
  const [mode, setMode] = useState('identity');

  // run a search whenever the region or mode changes (and one is selected)
  useEffect(() => { if (regionName) onFind(mode); /* eslint-disable-next-line */ }, [regionName, mode]);

  if (!regionName) {
    return (
      <div className="es-panel">
        <span className="diff-eyebrow"><Search size={12} /> Find similar</span>
        <p className="diff-insp-hint">Select a confirmed part, then find its visual neighbours —
          research to inspect, never facts. Nothing here creates a Motif or Relation.</p>
      </div>
    );
  }

  return (
    <div className="es-panel">
      <div className="es-head">
        <span className="diff-eyebrow"><Search size={12} /> Find similar</span>
        {meta?.space && <span className="es-space-badge">{meta.space}</span>}
      </div>
      <p className="es-for">neighbours of <strong>{regionName}</strong></p>

      <div className="es-modes" role="radiogroup" aria-label="Search kind">
        {MODES.map((m) => (
          <button key={m.key} type="button" role="radio" aria-checked={mode === m.key}
            className={`es-mode${mode === m.key ? ' on' : ''}`} title={m.hint}
            onClick={() => setMode(m.key)} disabled={status === 'loading'}>{m.label}</button>
        ))}
      </div>

      <div className="es-status" aria-live="polite">
        {status === 'loading' && (
          <div className="es-loading"><Loader2 size={13} className="es-spin" /> searching…
            <button type="button" className="diff-mini" onClick={onCancel}>Cancel</button></div>
        )}
        {status === 'unavailable' && (
          <div className="es-note es-note--warn">Search unavailable{error ? ` — ${error}` : ''}.
            <button type="button" className="diff-mini" onClick={() => onFind(mode)}>Retry</button></div>
        )}
        {status === 'empty' && (
          <div className="es-note">No neighbours yet in this space.
            <button type="button" className="diff-mini" onClick={() => onReindex(mode)}>Re-index</button></div>
        )}
        {status === 'error' && (
          <div className="es-note es-note--err">Search failed{error ? ` — ${error}` : ''}.
            <button type="button" className="diff-mini" onClick={() => onFind(mode)}>Retry</button></div>
        )}
        {status === 'ready' && meta && (
          <div className="es-metaline">
            {meta.indexed ? (meta.was_stale ? 'evidence changed — re-indexed' : 'indexed') : 'from index'}
            {' · '}<button type="button" className="es-relink" onClick={() => onReindex(mode)}
              title="Re-embed this part's current evidence">
              <RotateCw size={10} /> re-index</button>
          </div>
        )}
      </div>

      {status === 'ready' && (
        <div className="es-grid">
          {results.map((r) => <ResultCard key={`${r.post_id}-${r.region_id}`} r={r} cropUrl={cropUrl} />)}
        </div>
      )}

      <p className="es-disclaimer">Visual matches, not meanings — a neighbour is evidence to weigh,
        not a claim about what this is.</p>
    </div>
  );
}
