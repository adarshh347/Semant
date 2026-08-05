import React from 'react';
import { NodeViewWrapper } from '@tiptap/react';
import { ORCHESTRATION_KEYS } from '../schema/writerSchema';

/**
 * The `//` layer, on screen — the author's private reasoning.
 *
 * THE VISUAL JOB, and it is a real requirement rather than polish: the author must never
 * confuse "this conditions generation, invisible" with "this renders, visible". So
 * orchestration sits in the margin register — monospaced, muted, marked with its `//`,
 * and never set in the prose face. The schema is what GUARANTEES it stays off the page
 * (`manuscriptExport: false`); this only makes the guarantee legible.
 *
 * An unknown key renders as visibly inert rather than being silently dropped, mirroring
 * `dsl.parse_block`: the author's words are kept, they simply condition nothing.
 */
export default function OrchestrationView({ node }) {
  const { key, value, known } = node.attrs;
  const inert = !known || !key;

  return (
    <NodeViewWrapper
      className={`writer-orchestration${inert ? ' writer-orchestration--inert' : ''}`}
      data-testid="orchestration-node"
      contentEditable={false}
    >
      <span className="writer-orchestration__mark" aria-hidden="true">
        //
      </span>
      {key ? <span className="writer-orchestration__key">{key}</span> : null}
      <span className="writer-orchestration__value">{value}</span>
      {inert && (
        <span className="writer-orchestration__note" title={`orchestration keys: ${ORCHESTRATION_KEYS.join(', ')}`}>
          conditions nothing
        </span>
      )}
      <span className="writer-orchestration__invisible">not part of the manuscript</span>
    </NodeViewWrapper>
  );
}
