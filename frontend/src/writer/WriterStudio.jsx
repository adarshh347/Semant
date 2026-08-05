import React, { useCallback, useEffect, useState } from 'react';
import { writerService } from './writerService';
import WriterEditor from './WriterEditor';
import OperatorGraph from './graph/OperatorGraph';
import AssemblageSuggestions from './assemblages/AssemblageSuggestions';
import './WriterStudio.css';

/**
 * Semant Writer · W2 — the studio: the author's ontology beside the page.
 *
 * W1 shipped this as a textarea and a results list, which proved the loop and looked like a
 * form. W2 replaces the writing surface with the TipTap editor (`WriterEditor`) and keeps
 * only what belongs OUTSIDE the page: the operator ontology, and the `#create` gesture that
 * grows it.
 *
 * The split is deliberate. Everything that happens to a passage — render, quarantine,
 * accept, dismiss, refuse — happens INLINE in the document now, where the author is
 * looking. Nothing about a passage lives in a side panel any more, because a decision about
 * prose should be made next to the prose.
 */
export default function WriterStudio({ projectId, manuscriptId = '', sceneId = '', initialContent = null }) {
  const [operators, setOperators] = useState([]);
  const [error, setError] = useState('');
  const [drafting, setDrafting] = useState(false);
  const [draft, setDraft] = useState({ name: '', definition: '' });
  const [showGraph, setShowGraph] = useState(false);
  const [showPatterns, setShowPatterns] = useState(false);

  const loadOperators = useCallback(async () => {
    if (!projectId) return;
    try {
      setOperators(await writerService.listOperators(projectId));
    } catch (e) {
      setError(e.message);
    }
  }, [projectId]);

  useEffect(() => { loadOperators(); }, [loadOperators]);

  // propose → the author confirms → store. The registry's `propose` is a pure draft; this
  // surface never stores an operator the author has not looked at.
  const confirm = async () => {
    try {
      await writerService.createOperator(projectId, {
        name: draft.name.trim(),
        definition: draft.definition.trim(),
      });
      setDraft({ name: '', definition: '' });
      setDrafting(false);
      await loadOperators();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="writer-studio">
      <aside className="writer-ontology" data-testid="ontology-panel">
        <h3>Your operators</h3>

        {operators.length === 0 && (
          <p className="writer-empty">
            None yet. An operator is your word for a thing your prose does — define one and
            invoke it with <code>/name</code>.
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

        <button
          type="button"
          onClick={() => setShowPatterns((p) => !p)}
          aria-pressed={showPatterns}
          data-testid="patterns-toggle"
        >
          {showPatterns ? 'Hide patterns' : 'Patterns in my operators'}
        </button>

        <button
          type="button"
          onClick={() => setShowGraph((g) => !g)}
          aria-pressed={showGraph}
          data-testid="graph-toggle"
        >
          {showGraph ? 'Hide the graph' : 'See the graph'}
        </button>

        {drafting ? (
          <div className="writer-draft">
            <input
              aria-label="operator name"
              placeholder="name"
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
            <textarea
              aria-label="operator definition"
              placeholder="what it does, in your words"
              rows={3}
              value={draft.definition}
              onChange={(e) => setDraft({ ...draft, definition: e.target.value })}
            />
            <div className="writer-draft__actions">
              <button
                type="button"
                onClick={confirm}
                disabled={!draft.name.trim() || !draft.definition.trim()}
              >
                Add to my operators
              </button>
              <button type="button" onClick={() => setDrafting(false)}>Cancel</button>
            </div>
          </div>
        ) : (
          <button type="button" onClick={() => setDrafting(true)} data-testid="create-operator">
            #create an operator
          </button>
        )}

        {error && <p className="writer-error">{error}</p>}
      </aside>

      <main className="writer-page">
        {showGraph && (
          <div className="writer-graph-panel">
            <OperatorGraph projectId={projectId} onClose={() => setShowGraph(false)} />
          </div>
        )}
        {showPatterns && (
          <div className="writer-graph-panel">
            <AssemblageSuggestions
              projectId={projectId}
              onAuthored={loadOperators}
              onClose={() => setShowPatterns(false)}
            />
          </div>
        )}
        <WriterEditor
          projectId={projectId}
          manuscriptId={manuscriptId}
          sceneId={sceneId}
          initialContent={initialContent}
        />
      </main>
    </div>
  );
}
