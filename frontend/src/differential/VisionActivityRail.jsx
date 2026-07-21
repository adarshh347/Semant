// CIRCULATION-SPINE-001 · P2.2 — Vision Activity Rail.
//
// A quiet margin in the Differential inspector that lets a curator inspect what Semant
// actually executed across the FOUR currently instrumented operations (dissect, refine,
// semantic_read, find_similar). Read-only observation — never orchestration, never a causal
// chain between separate runs. All derivation/copy lives in ./visionActivity (unit-tested);
// this file is thin JSX. Raw stored error text is never shown by default (R2).
import { useMemo, useState } from 'react';
import { useVisionActivity } from './useVisionActivity';
import { OPERATIONS, deriveEntry } from './visionActivity';
import './VisionActivityRail.css';

function StatusMark({ present }) {
  if (present.key === 'running') {
    return <span className="va-mark va-mark--active" aria-hidden="true" />;
  }
  return <span className={`va-mark va-mark--${present.tone}`} aria-hidden="true" />;
}

function Entry({ entry }) {
  const { present } = entry;
  if (entry.isEmpty) {
    return (
      <div className="va-entry va-entry--empty">
        <div className="va-entry-head">
          <StatusMark present={present} />
          <span className="va-op">{entry.label}</span>
          <span className="va-status va-status--muted">No recorded activity</span>
        </div>
      </div>
    );
  }
  const meta = [];
  if (entry.adapter) meta.push(entry.adapter);
  if (typeof entry.latencyMs === 'number') meta.push(`${entry.latencyMs} ms`);
  if (typeof entry.neighbours === 'number') meta.push(`${entry.neighbours} neighbour${entry.neighbours === 1 ? '' : 's'}`);

  return (
    <div className={`va-entry va-entry--${present.tone}`}>
      <div className="va-entry-head">
        <StatusMark present={present} />
        <span className="va-op">{entry.label}</span>
        <span className={`va-status va-status--${present.tone}`}>{present.label}</span>
        {entry.affects && <span className="va-affects">{entry.affects}</span>}
        {entry.ageText && <span className="va-age">{entry.ageText}</span>}
      </div>

      <p className="va-epistemic">{entry.epistemic}</p>

      {(entry.friendly || entry.fallbacks.length > 0 || entry.regionRef || entry.telemetryDegraded) && (
        <div className="va-notes">
          {entry.friendly && <span className="va-note">{entry.friendly}</span>}
          {entry.fallbacks.length > 0 && (
            <span className="va-note va-note--fallback">Fell back to {entry.fallbacks.join(', ')}</span>
          )}
          {entry.regionRef && <span className="va-note va-note--ref">{entry.regionRef}</span>}
          {entry.telemetryDegraded && <span className="va-note">Some telemetry was not recorded.</span>}
        </div>
      )}

      {meta.length > 0 && <div className="va-meta">{meta.join(' · ')}</div>}

      {entry.stages.length > 0 && (
        <details className="va-stages">
          <summary>{entry.stages.length} stages</summary>
          <ol className="va-stage-list">
            {entry.stages.map((s, i) => (
              <li key={`${s.id}-${i}`} className={`va-stage va-stage--${s.status}`}>
                <span className="va-stage-name">{s.human}</span>
                {s.status !== 'succeeded' && <span className="va-stage-status">{s.status}</span>}
                {typeof s.latencyMs === 'number' && <span className="va-stage-lat">{Math.round(s.latencyMs)} ms</span>}
                {s.fallbacks.length > 0 && <span className="va-stage-fb">↳ {s.fallbacks.join(', ')}</span>}
              </li>
            ))}
          </ol>
        </details>
      )}

      {entry.diagnostics && (
        <details className="va-diag">
          <summary>Technical detail (diagnostics)</summary>
          <pre className="va-diag-text">{entry.diagnostics}</pre>
        </details>
      )}
    </div>
  );
}

export default function VisionActivityRail({ postId, regions, actionStatus }) {
  const [open, setOpen] = useState(false);
  const { runs, loading, refresh } = useVisionActivity(postId, { actionStatus });

  const regionsById = useMemo(() => {
    const m = {};
    (regions || []).forEach((r) => {
      if (r && r.id) m[r.id] = r.name || r.label || r.category || r.id;
    });
    return m;
  }, [regions]);

  const now = Date.now();
  const entries = useMemo(
    () => OPERATIONS.map((op) => deriveEntry(op, runs[op] ?? null, { regionsById, now })),
    [runs, regionsById, now],
  );

  const recordedCount = entries.filter((e) => !e.isEmpty).length;
  const anyActive = entries.some((e) => e.isActive);

  return (
    <section className={`va-rail${open ? ' is-open' : ''}`} aria-label="Vision activity">
      <button
        type="button"
        className="va-toggle"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="va-eyebrow">Vision activity</span>
        <span className="va-summary">
          {anyActive ? 'observing…' : recordedCount === 0 ? 'nothing recorded yet' : `${recordedCount} recorded`}
        </span>
        <span className="va-caret" aria-hidden="true">{open ? '▾' : '▸'}</span>
      </button>

      {open && (
        <div className="va-body">
          <div className="va-scope">
            Records dissect, refine, semantic read and find similar — not all vision activity.
          </div>
          {entries.map((e) => (
            <Entry key={e.operation} entry={e} />
          ))}
          <div className="va-foot">
            <button type="button" className="va-refresh" onClick={refresh} disabled={loading}>
              {loading ? 'refreshing…' : 'Refresh'}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
