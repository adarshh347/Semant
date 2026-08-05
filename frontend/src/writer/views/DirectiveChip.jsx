import React from 'react';
import { NodeViewWrapper } from '@tiptap/react';
import { useWriterActions } from './WriterActions';

/**
 * The `/` layer, on screen — an operator chip.
 *
 * Shows the operator stack with each operator's VERSION, because a passage rendered by
 * `threshold v1` and one rendered by `threshold v3` are not the same claim, and the author
 * should be able to see which one this directive will fire before they run it.
 *
 * An operator the author has not defined is marked undefined right here, so the refusal at
 * render time is never a surprise — the chip already said so.
 *
 * Clicking inspects the definition (read-only in W2). The chip may LINK toward the operator
 * graph later; W2 ships no graph (W3 owns that).
 */
export default function DirectiveChip({ node }) {
  const { operators = [], argument } = node.attrs;
  const { operators: known = [], onInspectOperator } = useWriterActions();

  const resolve = (name) => known.find((o) => o.name === name) || null;
  const anyUndefined = operators.some((n) => !resolve(n));

  return (
    <NodeViewWrapper
      as="span"
      className={`writer-directive${anyUndefined ? ' writer-directive--undefined' : ''}`}
      data-testid="directive-chip"
      contentEditable={false}
    >
      <span className="writer-directive__mark" aria-hidden="true">/</span>
      {operators.map((name, i) => {
        const op = resolve(name);
        return (
          <React.Fragment key={name}>
            {i > 0 && <span className="writer-directive__plus">+</span>}
            <button
              type="button"
              className="writer-directive__op"
              onClick={() => onInspectOperator(name)}
              title={op ? op.definition : 'not defined yet — this will refuse'}
            >
              {name}
              <span className="writer-directive__version">
                {op ? `v${op.version}` : 'undefined'}
              </span>
            </button>
          </React.Fragment>
        );
      })}
      {argument ? <span className="writer-directive__arg">({argument})</span> : null}
    </NodeViewWrapper>
  );
}
