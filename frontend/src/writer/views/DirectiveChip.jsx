import React from 'react';
import { NodeViewWrapper } from '@tiptap/react';
import { useWriterActions } from './WriterActions';
import { directivesInDoc } from '../schema/writerDoc';

/** This chip's index among all directives — what `run_block` counts (W3 §1). */
function directiveIndexOf(editor, pos) {
  const found = directivesInDoc(editor.state.doc).find((d) => d.pos === pos);
  return found ? found.index : 0;
}

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
export default function DirectiveChip({ node, getPos, editor }) {
  const { operators = [], argument, satisfiedBy } = node.attrs;
  const { operators: known = [], onInspectOperator, onRerenderDirective } = useWriterActions();

  const resolve = (name) => known.find((o) => o.name === name) || null;
  const anyUndefined = operators.some((n) => !resolve(n));

  return (
    <NodeViewWrapper
      as="span"
      className={`writer-directive${anyUndefined ? ' writer-directive--undefined' : ''}`
        + `${satisfiedBy ? ' writer-directive--satisfied' : ''}`}
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
      {satisfiedBy && (
        // Satisfied: its render is canon, so the default Render leaves it alone. Asking
        // for another proposal is the author's explicit choice, offered right here.
        <button
          type="button"
          className="writer-directive__rerender"
          data-testid="rerender-button"
          title="This directive's render is already accepted — render it again?"
          onClick={() => onRerenderDirective(directiveIndexOf(editor, getPos()))}
        >
          accepted · re-render
        </button>
      )}
    </NodeViewWrapper>
  );
}
