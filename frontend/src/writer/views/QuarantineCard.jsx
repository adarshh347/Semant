import React, { useState } from 'react';
import { NodeViewWrapper } from '@tiptap/react';
import { useWriterActions } from './WriterActions';

/**
 * An unaccepted render, on screen. This is I1 and I2 made visible.
 *
 * TWO FACES, ONE NODE (see `writerSchema.js` for why a refusal lives here):
 *
 *   quarantined — the proposed prose, its full provenance, and Accept / Dismiss. It is
 *                 marked UNACCEPTED in a way that cannot be mistaken for manuscript: it
 *                 sits in a card, outside the prose measure, wearing the word.
 *
 *   refused     — the reason, in full, and NEVER a prose card. A refusal is an answer, so
 *                 it is not dimmed, not collapsed behind a "details" link, and not styled
 *                 as an error. When it is a style-by-reference refusal it carries the
 *                 `#create` ON-RAMP inline: the author names what the borrowed voice meant
 *                 to them and it becomes an operator they own. Per GROUNDING.md, that
 *                 on-ramp — not the prohibition — is the feature.
 *
 * Neither face can reach the manuscript: the node declares `manuscriptExport: false`, and
 * Accept does not flip a flag here — it calls the W1 gate and only then does the editor
 * replace this node with `paragraph` nodes.
 */

/** The suggested operator name W1's refusal already computed, if this is that refusal. */
function suggestedOperator(refusal) {
  const m = /#create\s+([A-Za-z][\w-]*)/.exec(refusal || '');
  return m ? m[1] : null;
}

export default function QuarantineCard({ node, getPos, editor }) {
  const { passageId, status, text, refusal, provenance, diagnostics = [], directive } = node.attrs;
  const { onAccept, onDismiss, onCreateOperator } = useWriterActions();

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [defining, setDefining] = useState(false);
  const [definition, setDefinition] = useState('');

  const suggested = suggestedOperator(refusal);
  const operators = provenance?.operators ?? [];
  const intents = provenance?.intents ?? [];

  const act = async (fn) => {
    setBusy(true);
    setError('');
    try {
      await fn();
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  };

  // ── the refusal face ──────────────────────────────────────────────────────
  if (status === 'refused' || status === 'unavailable') {
    return (
      <NodeViewWrapper
        className={`writer-card writer-card--${status}`}
        data-testid={status === 'refused' ? 'refusal-card' : 'unavailable-card'}
        contentEditable={false}
      >
        <header className="writer-card__head">
          <span className="writer-card__label">
            {status === 'refused' ? 'refused' : 'unavailable'}
          </span>
          {directive ? <code className="writer-card__directive">{directive}</code> : null}
        </header>

        <p className="writer-card__refusal" data-testid="refusal-reason">
          {refusal}
        </p>

        {suggested && (
          <div className="writer-card__onramp" data-testid="create-onramp">
            {defining ? (
              <>
                <label htmlFor={`define-${suggested}`}>
                  <code>#create {suggested}</code> — the qualities, in your words
                </label>
                <textarea
                  id={`define-${suggested}`}
                  value={definition}
                  onChange={(e) => setDefinition(e.target.value)}
                  placeholder="the remove, the sentence length, what the narrator is allowed to know…"
                  rows={3}
                />
                <div className="writer-card__actions">
                  <button
                    type="button"
                    disabled={busy || !definition.trim()}
                    onClick={() =>
                      act(async () => {
                        await onCreateOperator(suggested, definition.trim());
                        setDefining(false);
                        setBusy(false);
                      })
                    }
                  >
                    Define it
                  </button>
                  <button type="button" onClick={() => setDefining(false)}>Cancel</button>
                </div>
              </>
            ) : (
              <button type="button" onClick={() => setDefining(true)}>
                Define <code>{suggested}</code> in my own words
              </button>
            )}
          </div>
        )}

        <footer className="writer-card__foot">
          <button
            type="button"
            disabled={busy}
            onClick={() => act(async () => editor.commands.deleteRange({ from: getPos(), to: getPos() + node.nodeSize }))}
          >
            Clear
          </button>
        </footer>
        {error && <p className="writer-card__error">{error}</p>}
      </NodeViewWrapper>
    );
  }

  // ── the quarantined-passage face ──────────────────────────────────────────
  return (
    <NodeViewWrapper
      className="writer-card writer-card--quarantined"
      data-testid="quarantine-card"
      contentEditable={false}
    >
      <header className="writer-card__head">
        <span className="writer-card__label" data-testid="quarantine-label">
          quarantined
        </span>
        {directive ? <code className="writer-card__directive">{directive}</code> : null}
      </header>

      <div className="writer-card__prose" data-testid="quarantine-prose">
        {String(text || '').split('\n').map((line, i) => <p key={i}>{line}</p>)}
      </div>

      <div className="writer-card__provenance" data-testid="quarantine-provenance">
        <span className="writer-card__provenance-label">rendered by</span>
        {operators.map((o) => (
          <span key={o.name} className="writer-card__op">
            {o.name} v{o.version}
          </span>
        ))}
        {intents.length > 0 && (
          <span className="writer-card__intents">
            under {intents.map((i) => i.key).join(', ')}
          </span>
        )}
        {provenance?.model && <span className="writer-card__model">{provenance.model}</span>}
      </div>

      {diagnostics.map((d) => (
        <p key={d} className="writer-card__diagnostic">{d}</p>
      ))}

      <footer className="writer-card__foot">
        <span className="writer-card__note">Nothing is in the manuscript until you accept it.</span>
        <button
          type="button"
          data-testid="accept-button"
          disabled={busy}
          onClick={() => act(() => onAccept(passageId, getPos(), node))}
        >
          Accept
        </button>
        <button
          type="button"
          data-testid="dismiss-button"
          disabled={busy}
          onClick={() => act(() => onDismiss(passageId, getPos(), node))}
        >
          Dismiss
        </button>
      </footer>
      {error && <p className="writer-card__error">{error}</p>}
    </NodeViewWrapper>
  );
}
