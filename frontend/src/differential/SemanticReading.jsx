import React, { useState } from 'react';
import { Sparkles, Check, X, HelpCircle, Pencil, RotateCw, Scan } from 'lucide-react';

/**
 * SemanticReading (VISION-D · D4) — the curator's panel over the VLM reading.
 *
 * Renders the evidence the model returned ABOUT the candidate masks — a named reading with
 * ranked alternatives, confidence and provenance; candidate→candidate relations; and an
 * image-global reading — and lets the curator accept / edit / reject / hold-tentative each
 * assertion. It never edits geometry, and it never overwrites the curator's own text: an
 * edit is stored as an override the model's reruns leave alone. When the model says a mask
 * doesn't serve ("needs better evidence"), the curator can launch Refine on that part.
 */

const INTENTS = [
  { key: 'name', label: 'Name' },
  { key: 'material', label: 'Material' },
  { key: 'relate', label: 'Relate' },
  { key: 'compose', label: 'Compose' },
  { key: 'describe', label: 'Describe' },
];

const STATUS_LABEL = {
  proposed: 'proposed', accepted: 'accepted', rejected: 'rejected',
  tentative: 'tentative', overridden: 'edited',
};

const pct = (c) => (c == null ? null : `${Math.round(c * 100)}%`);

export default function SemanticReading({
  semantics, status, error, busyId, regions = [],
  onRead, onCancel, onCurate, onFocusRegion, onHoverRegion, onRefine,
}) {
  const [intent, setIntent] = useState('name');
  const [editing, setEditing] = useState(null);   // candidate id being edited
  const [draft, setDraft] = useState('');

  const nameOf = (id) => {
    const r = regions.find((x) => x.id === id);
    return r?.label || r?.part || r?.category || id;
  };

  const assertions = semantics?.assertions || [];
  const relations = semantics?.relations || [];
  const global = semantics?.global || null;
  const needs = semantics?.needs_better_evidence || [];
  const meta = semantics?.meta || null;
  const hasReading = assertions.length > 0 || relations.length > 0 || !!global;

  const startEdit = (a) => { setEditing(a.candidate_id); setDraft(a.curator_label || a.label || ''); };
  const saveEdit = (a) => {
    const text = draft.trim();
    setEditing(null);
    if (text && text !== (a.curator_label || a.label || '')) onCurate(a.candidate_id, { curator_label: text });
  };

  return (
    <div className="diff-insp-read">
      <div className="diff-read-head">
        <span className="diff-eyebrow"><Sparkles size={12} /> Reading</span>
        {meta?.model && <span className="diff-read-model" title={`${meta.provider} · ${meta.model}`}>{meta.model}</span>}
      </div>

      {/* intent + request/re-read */}
      <div className="diff-read-intents" role="radiogroup" aria-label="Reading intent">
        {INTENTS.map((it) => (
          <button key={it.key} type="button" role="radio" aria-checked={intent === it.key}
            className={`diff-read-intent${intent === it.key ? ' on' : ''}`}
            onClick={() => setIntent(it.key)} disabled={status === 'loading'}>
            {it.label}
          </button>
        ))}
      </div>

      {/* status line + primary action, aria-live for AT */}
      <div className="diff-read-status" aria-live="polite">
        {status === 'loading' && (
          <div className="diff-read-loading">
            <span className="diff-refine-spin" /> reading the evidence…
            <button type="button" className="diff-mini" onClick={onCancel}>Cancel</button>
          </div>
        )}
        {status === 'unavailable' && (
          <div className="diff-read-note diff-read-note--warn">
            The reader is unavailable{error ? ` — ${error}` : ''}. Set an OpenRouter key to enable it.
            <button type="button" className="diff-mini" onClick={() => onRead(intent, false)}>Retry</button>
          </div>
        )}
        {status === 'timeout' && (
          <div className="diff-read-note diff-read-note--warn">
            The reading timed out. <button type="button" className="diff-mini" onClick={() => onRead(intent, true)}>Try again</button>
          </div>
        )}
        {status === 'error' && (
          <div className="diff-read-note diff-read-note--err">
            Reading failed{error ? ` — ${error}` : ''}. <button type="button" className="diff-mini" onClick={() => onRead(intent, true)}>Retry</button>
          </div>
        )}
        {(status === 'idle' || status === 'ready') && (
          <button type="button" className="diff-primary diff-read-go" onClick={() => onRead(intent, hasReading)}>
            {hasReading ? <><RotateCw size={13} /> Re-read</> : <><Sparkles size={13} /> Request a reading</>}
          </button>
        )}
      </div>

      {status !== 'loading' && !hasReading && status !== 'unavailable' && (
        <p className="diff-insp-hint">
          Ask the model to interpret the parts it was given — it can name, qualify, relate and
          read the whole image, but it can never move a mask. Your decisions stay yours.
        </p>
      )}

      {/* assertions */}
      {assertions.map((a) => {
        const shownLabel = a.curator_label || a.label || '—';
        const busy = busyId === a.candidate_id;
        return (
          <div key={a.candidate_id} className={`diff-read-card is-${a.status}`}
            onMouseEnter={() => onHoverRegion?.(a.candidate_id)}
            onMouseLeave={() => onHoverRegion?.(null)}>
            <div className="diff-read-card-top">
              <button type="button" className="diff-read-target" title="Show this part on the image"
                onClick={() => onFocusRegion?.(a.candidate_id)}>{nameOf(a.candidate_id)}</button>
              <span className={`diff-read-state diff-read-state--${a.status}`}>{STATUS_LABEL[a.status] || a.status}</span>
            </div>

            {editing === a.candidate_id ? (
              <div className="diff-read-edit">
                <input autoFocus className="diff-read-input" value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') { e.preventDefault(); saveEdit(a); }
                    if (e.key === 'Escape') { e.stopPropagation(); setEditing(null); }
                  }} />
                <button type="button" className="diff-mini diff-mini--primary" onClick={() => saveEdit(a)}>Save</button>
                <button type="button" className="diff-mini" onClick={() => setEditing(null)}>Cancel</button>
              </div>
            ) : (
              <div className="diff-read-label-row">
                <span className="diff-read-label">{shownLabel}</span>
                {a.confidence != null && (
                  <span className="diff-read-conf" title={`model confidence ${pct(a.confidence)}`}>
                    <span className="diff-read-conf-bar"><span style={{ width: pct(a.confidence) }} /></span>
                    {pct(a.confidence)}
                  </span>
                )}
              </div>
            )}

            {/* ranked alternatives — click to adopt as the curator label */}
            {(a.ranked_alternatives || []).length > 0 && (
              <div className="diff-read-alts">
                {a.ranked_alternatives.map((alt) => (
                  <button key={alt} type="button" className="diff-read-alt"
                    title="Use this alternative as the label"
                    onClick={() => onCurate(a.candidate_id, { curator_label: alt })}>{alt}</button>
                ))}
              </div>
            )}

            {(a.part || a.material || a.style || (a.attributes || []).length > 0) && (
              <div className="diff-read-facets">
                {a.part && <span className="diff-chip diff-chip--dim">part · {a.part}</span>}
                {a.material && <span className="diff-chip diff-chip--dim">{a.material}</span>}
                {a.style && <span className="diff-chip diff-chip--dim">{a.style}</span>}
                {(a.attributes || []).map((at) => <span key={at} className="diff-chip diff-chip--dim">{at}</span>)}
              </div>
            )}
            {a.uncertainty && <p className="diff-read-uncertain">? {a.uncertainty}</p>}

            {/* curator decisions — accept / tentative / reject / edit */}
            <div className="diff-read-actions">
              <button type="button" className="diff-mini diff-mini--ok" disabled={busy}
                onClick={() => onCurate(a.candidate_id, { status: 'accepted' })} title="Accept this reading">
                <Check size={12} /> Accept
              </button>
              <button type="button" className="diff-mini" disabled={busy}
                onClick={() => onCurate(a.candidate_id, { status: 'tentative' })} title="Hold as tentative">
                <HelpCircle size={12} /> Tentative
              </button>
              <button type="button" className="diff-mini diff-mini--no" disabled={busy}
                onClick={() => onCurate(a.candidate_id, { status: 'rejected' })} title="Reject this reading">
                <X size={12} /> Reject
              </button>
              <button type="button" className="diff-mini" disabled={busy}
                onClick={() => startEdit(a)} title="Write your own label"><Pencil size={12} /> Edit</button>
            </div>
            <p className="diff-read-prov">{a.provider} · {a.model}</p>
          </div>
        );
      })}

      {/* needs better evidence → launch Refine */}
      {needs.length > 0 && (
        <div className="diff-read-needs">
          <span className="diff-eyebrow">Needs better evidence</span>
          <p className="diff-insp-hint">The model says the mask doesn't serve these — tighten it with Refine.</p>
          {needs.map((cid) => (
            <button key={cid} type="button" className="diff-mini diff-read-refine"
              onClick={() => onRefine?.(cid)}><Scan size={12} /> Refine {nameOf(cid)}</button>
          ))}
        </div>
      )}

      {/* relations — proposals only; they never change mask ownership */}
      {relations.length > 0 && (
        <div className="diff-read-relations">
          <span className="diff-eyebrow">Relations</span>
          {relations.map((r, i) => (
            <div key={`${r.from_id}-${r.to_id}-${i}`} className="diff-read-rel">
              <button type="button" className="diff-read-relend" onClick={() => onFocusRegion?.(r.from_id)}>{nameOf(r.from_id)}</button>
              <span className="diff-read-reltype">{r.relation}{r.confidence != null ? ` · ${pct(r.confidence)}` : ''}</span>
              <button type="button" className="diff-read-relend" onClick={() => onFocusRegion?.(r.to_id)}>{nameOf(r.to_id)}</button>
            </div>
          ))}
        </div>
      )}

      {/* image-global reading — not an object mask */}
      {global && (global.composition || global.atmosphere || global.colour || global.scene || (global.notes || []).length > 0) && (
        <div className="diff-read-global">
          <span className="diff-eyebrow">Whole image</span>
          {global.composition && <p className="diff-read-gline"><em>composition</em> {global.composition}</p>}
          {global.atmosphere && <p className="diff-read-gline"><em>atmosphere</em> {global.atmosphere}</p>}
          {global.colour && <p className="diff-read-gline"><em>colour</em> {global.colour}</p>}
          {global.scene && <p className="diff-read-gline"><em>scene</em> {global.scene}</p>}
          {(global.notes || []).map((n, i) => <p key={i} className="diff-read-gline">· {n}</p>)}
        </div>
      )}

      {meta && hasReading && (
        <p className="diff-read-meta">
          {meta.from_cache ? 'cached' : 'fresh'}
          {(meta.dropped_ids || []).length > 0 && ` · ${meta.dropped_ids.length} unknown-id dropped`}
        </p>
      )}
    </div>
  );
}
