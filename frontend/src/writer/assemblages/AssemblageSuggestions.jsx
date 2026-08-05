import React, { useCallback, useEffect, useState } from 'react';
import { writerService } from '../writerService';
import './AssemblageSuggestions.css';

/**
 * Semant Writer · W4 — the suggestion feed.
 *
 * THE ONE DIVISION THIS SURFACE HAS TO HOLD: the system earned the right to raise the
 * cluster by pointing at real logged blocks; it has not earned the right to say what the
 * cluster means. So the card shows the EVIDENCE prominently — the block count, and the
 * actual runs and directives it rests on, expandable — and it shows the strawman as an
 * editable draft that says, in its own label, that it is the author's own sentences put
 * next to each other rather than a reading of them.
 *
 * NOTHING HERE COMMITS UNTIL THE AUTHOR DOES. Looking at a suggestion changes nothing.
 * Dismissing changes nothing in the ontology (it records a dismissal so the cluster stops
 * nagging). Only "Name it" writes, and only with an intent the author typed.
 *
 * This component has no route to the manuscript — no accept, no scene, no block. Same
 * discipline as the W3 graph.
 */
export default function AssemblageSuggestions({ projectId, onAuthored = null, onClose = null }) {
  const [suggestions, setSuggestions] = useState([]);
  const [threshold, setThreshold] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [expanded, setExpanded] = useState(null);
  const [naming, setNaming] = useState(null);      // suggestion id being authored
  const [draft, setDraft] = useState({ name: '', rendering_intent: '', definition: '' });

  const load = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const out = await writerService.assemblageSuggestions(projectId);
      setSuggestions(out.suggestions ?? []);
      setThreshold(out.threshold ?? null);
      setError('');
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const beginNaming = (s) => {
    setNaming(s.id);
    // The strawman is a STARTING POINT. It is pre-filled so the author edits rather than
    // starts from nothing, and the label beside it says where it came from.
    // The strawman seeds the INTENT only. The definition is left blank on purpose:
    // it is the one field that must be the author's own, and pre-filling it with the
    // same sentence is exactly what made W4's gate echo its intent back as prose.
    setDraft({ name: s.strawman.name, rendering_intent: s.strawman.rendering_intent, definition: '' });
  };

  const author = async (s) => {
    setError('');
    try {
      await writerService.createAssemblage(projectId, {
        name: draft.name.trim(),
        members: s.members.map((m) => m.name),
        rendering_intent: draft.rendering_intent.trim(),
        definition: draft.definition.trim(),
      });
      setNaming(null);
      setStatus(`\`${draft.name.trim()}\` is yours now — invoke it with / ${draft.name.trim()}`);
      await load();
      if (onAuthored) onAuthored();
    } catch (e) {
      setError(e.message);
    }
  };

  const dismiss = async (s) => {
    setError('');
    try {
      await writerService.dismissAssemblage(projectId, s.members.map((m) => m.name), s.support);
      setStatus('Dismissed — it will not come back unless it recurs a lot more.');
      await load();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <section className="writer-assemblages" data-testid="assemblage-suggestions">
      <header className="writer-assemblages__bar">
        <strong>Patterns in your operators</strong>
        {threshold != null && (
          <span className="writer-assemblages__help">
            raised after a cluster recurs in {threshold} blocks
          </span>
        )}
        {onClose && <button type="button" onClick={onClose}>Close</button>}
      </header>

      {error && <p className="writer-assemblages__error" data-testid="assemblage-error">{error}</p>}
      {status && !error && <p className="writer-assemblages__status">{status}</p>}

      {loading && <p className="writer-assemblages__empty">Reading your usage…</p>}

      {!loading && suggestions.length === 0 && (
        <p className="writer-assemblages__empty" data-testid="assemblage-empty">
          Nothing yet. This reads what you have actually written — when a set of operators
          starts recurring together, it will say so, and show you where.
        </p>
      )}

      {suggestions.map((s) => (
        <article key={s.id} className="writer-assemblage" data-testid="assemblage-card">
          <header>
            {s.members.map((m) => (
              <code key={m.name} className="writer-assemblage__member">
                /{m.name} <span>v{m.version}</span>
              </code>
            ))}
          </header>

          {/* THE EVIDENCE, not a claim about meaning. */}
          <p className="writer-assemblage__evidence" data-testid="assemblage-evidence">
            recurred together in <b>{s.evidence.block_count}</b> blocks
            {s.evidence.blocks_with_pulled_operators > 0 && (
              <span className="writer-assemblage__aside">
                {' '}({s.evidence.blocks_with_pulled_operators} also pulled an operator via
                {' '}<code>requires</code>)
              </span>
            )}
            <button
              type="button"
              className="writer-assemblage__cite"
              data-testid="show-evidence"
              onClick={() => setExpanded(expanded === s.id ? null : s.id)}
            >
              {expanded === s.id ? 'hide the blocks' : 'show the blocks'}
            </button>
          </p>

          {expanded === s.id && (
            <ul className="writer-assemblage__blocks" data-testid="evidence-blocks">
              {s.evidence.blocks.map((b) => (
                <li key={b.run_id}>
                  <code>{b.run_id}</code>
                  {b.at && <span className="writer-assemblage__when">{String(b.at).slice(0, 16)}</span>}
                  <span className="writer-assemblage__directives">{b.directives.join('  ')}</span>
                </li>
              ))}
            </ul>
          )}

          {naming === s.id ? (
            <div className="writer-assemblage__naming" data-testid="assemblage-naming">
              <label htmlFor={`asm-name-${s.id}`}>Call it</label>
              <input
                id={`asm-name-${s.id}`}
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />

              <label htmlFor={`asm-intent-${s.id}`}>
                What it means, in your words
                <span className="writer-assemblage__strawman-note">
                  {s.strawman.source}
                </span>
              </label>
              <textarea
                id={`asm-intent-${s.id}`}
                rows={4}
                value={draft.rendering_intent}
                onChange={(e) => setDraft({ ...draft, rendering_intent: e.target.value })}
              />

              <label htmlFor={`asm-definition-${s.id}`}>
                What it IS in your writing
                <span className="writer-assemblage__strawman-note">
                  not what should happen on the page — that is the field above. An
                  assemblage that says one of them twice renders thinly.
                </span>
              </label>
              <textarea
                id={`asm-definition-${s.id}`}
                rows={3}
                value={draft.definition}
                onChange={(e) => setDraft({ ...draft, definition: e.target.value })}
              />

              <div className="writer-assemblage__actions">
                <button
                  type="button"
                  data-testid="commit-assemblage"
                  disabled={!draft.name.trim() || !draft.rendering_intent.trim()
                    || !draft.definition.trim()
                    || draft.definition.trim() === draft.rendering_intent.trim()}
                  onClick={() => author(s)}
                >
                  Add it to my operators
                </button>
                <button type="button" onClick={() => setNaming(null)}>Cancel</button>
              </div>
            </div>
          ) : (
            <footer className="writer-assemblage__actions">
              <span className="writer-assemblage__note">
                Nothing changes until you name it.
              </span>
              <button type="button" data-testid="name-assemblage" onClick={() => beginNaming(s)}>
                Name it
              </button>
              <button type="button" data-testid="dismiss-assemblage" onClick={() => dismiss(s)}>
                Not a thing
              </button>
            </footer>
          )}
        </article>
      ))}
    </section>
  );
}
