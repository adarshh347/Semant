import React, { useCallback, useEffect, useState } from 'react';
import { writerService } from './writerService';
import './WriterStudio.css';

/**
 * Semant Writer · W1 — the executable document, minimally surfaced.
 *
 * W1's point is the LOOP, not the surface: script a block, render it, read what came
 * back, accept or dismiss. The literary-cadence editor is W2 and deliberately absent —
 * this is a plain textarea with operator annotations, and nothing here should grow into
 * a manuscript editor before W2 designs one.
 *
 * The three things this surface must get right, because they are the product:
 *
 *   A REFUSAL IS NOT AN ERROR. A refused directive renders as a first-class result with
 *   its reason in full, in the same list as the passages — not as a toast, not greyed
 *   out, not collapsed. When the model says "you have not defined `ekstasis`", that
 *   sentence is the most useful thing on screen.
 *
 *   NOTHING COMMITS ITSELF. Every rendered passage sits in quarantine wearing that word
 *   until the author presses Accept. There is no auto-accept, no "accept all", and the
 *   accept button never appears on anything that has already been decided.
 *
 *   ORCHESTRATION IS NOT PROSE. `//` notes show as staging, in the margin, visually
 *   apart from the passages they conditioned. The backend strips them at two boundaries;
 *   the UI's job is to never redraw the line it enforces.
 */
export default function WriterStudio({ projectId, manuscriptId = '', sceneId = '' }) {
  const [block, setBlock] = useState('');
  const [operators, setOperators] = useState([]);
  const [results, setResults] = useState([]);
  const [proposals, setProposals] = useState([]);
  const [diagnostics, setDiagnostics] = useState([]);
  const [decided, setDecided] = useState({});   // passage_id → 'accepted' | 'dismissed'
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const loadOperators = useCallback(async () => {
    if (!projectId) return;
    try {
      setOperators(await writerService.listOperators(projectId));
    } catch (e) {
      setError(e.message);
    }
  }, [projectId]);

  useEffect(() => { loadOperators(); }, [loadOperators]);

  const run = async () => {
    if (!block.trim() || busy) return;
    setBusy(true);
    setError('');
    try {
      const out = await writerService.run(projectId, { text: block, manuscriptId, sceneId });
      setResults(out.results ?? []);
      setProposals(out.proposals ?? []);
      setDiagnostics(out.diagnostics ?? []);
      setDecided({});
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const accept = async (passageId) => {
    try {
      await writerService.accept(passageId, sceneId);
      setDecided((d) => ({ ...d, [passageId]: 'accepted' }));
    } catch (e) {
      setError(e.message);
    }
  };

  const dismiss = async (passageId) => {
    try {
      await writerService.dismiss(passageId);
      setDecided((d) => ({ ...d, [passageId]: 'dismissed' }));
    } catch (e) {
      setError(e.message);
    }
  };

  // The author confirms a `#create` the block proposed. `propose` already ran server-side;
  // this is the second, explicit half of the gesture.
  const confirmOperator = async (proposal) => {
    try {
      await writerService.createOperator(projectId, {
        name: proposal.name,
        definition: proposal.definition,
      });
      setProposals((p) => p.filter((x) => x.proposal?.name !== proposal.name));
      await loadOperators();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="writer-studio">
      <section className="writer-ontology">
        <h3>Your operators</h3>
        {operators.length === 0 && (
          <p className="writer-empty">
            None yet. Write <code>#create name: what it does</code> in a block —
            nothing renders until you have defined what it should render with.
          </p>
        )}
        <ul>
          {operators.map((op) => (
            <li key={op.id}>
              <code>/{op.name}</code> <span className="writer-version">v{op.version}</span>
              <p>{op.definition}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="writer-block">
        <label htmlFor="writer-block-input">The block</label>
        <textarea
          id="writer-block-input"
          value={block}
          onChange={(e) => setBlock(e.target.value)}
          spellCheck={false}
          placeholder={
            '// goal: she arrives at the door she has been avoiding\n'
            + '// voice: close third, past tense\n'
            + '/ threshold(the door at the end of the hall)\n'
          }
        />
        <div className="writer-actions">
          <button type="button" onClick={run} disabled={busy || !block.trim()}>
            {busy ? 'Rendering…' : 'Render'}
          </button>
          <span className="writer-note">
            Renders are quarantined. Nothing reaches the manuscript until you accept it.
          </span>
        </div>
        {error && <p className="writer-error">{error}</p>}
        {diagnostics.map((d) => <p key={d} className="writer-diagnostic">{d}</p>)}
      </section>

      {proposals.length > 0 && (
        <section className="writer-proposals">
          <h3>Proposed operators</h3>
          {proposals.map((p) => (
            <div key={p.line} className="writer-proposal">
              {p.error ? (
                <p className="writer-error">line {p.line}: {p.error}</p>
              ) : (
                <>
                  <code>/{p.proposal.name}</code>
                  <p>{p.proposal.definition}</p>
                  <button type="button" onClick={() => confirmOperator(p.proposal)}>
                    Confirm — add to my operators
                  </button>
                </>
              )}
            </div>
          ))}
        </section>
      )}

      <section className="writer-results">
        {results.map((r) => {
          const decision = decided[r.passage_id];
          const intents = Object.entries(r.orchestration ?? {});
          return (
            <article
              key={`${r.line}-${r.directive}`}
              className={`writer-result writer-result--${r.status}`}
            >
              <header>
                <code>{r.directive}</code>
                <span className="writer-status">{r.status}</span>
              </header>

              {intents.length > 0 && (
                <ul className="writer-staging" aria-label="orchestration (never part of the prose)">
                  {intents.map(([k, v]) => <li key={k}><b>{k}</b> {v}</li>)}
                </ul>
              )}

              {r.status === 'refused' ? (
                // The reason, in full. This is a result, not a failure.
                <p className="writer-refusal">{r.refusal}</p>
              ) : r.status === 'ok' ? (
                <>
                  <div className="writer-passage">
                    {r.text.split('\n').map((line, i) => <p key={i}>{line}</p>)}
                  </div>
                  <footer>
                    <span className="writer-provenance">
                      {(r.provenance?.operators ?? [])
                        .map((o) => `${o.name} v${o.version}`).join(' + ')}
                      {intents.length > 0 && ` · under ${intents.map(([k]) => k).join(', ')}`}
                    </span>
                    {decision ? (
                      <span className="writer-decided">{decision}</span>
                    ) : (
                      <>
                        <span className="writer-quarantined">quarantined</span>
                        <button type="button" onClick={() => accept(r.passage_id)}>Accept</button>
                        <button type="button" onClick={() => dismiss(r.passage_id)}>Dismiss</button>
                      </>
                    )}
                  </footer>
                </>
              ) : (
                <p className="writer-unavailable">{r.refusal}</p>
              )}

              {(r.diagnostics ?? []).map((d) => (
                <p key={d} className="writer-diagnostic">{d}</p>
              ))}
            </article>
          );
        })}
      </section>
    </div>
  );
}
