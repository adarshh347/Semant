import React from 'react';
import { Handle, Position } from '@xyflow/react';

/**
 * One operator, on the graph. Name + version, and the definition it stands for.
 *
 * The version is on the node for the same reason it is on the directive chip: a passage
 * rendered by `threshold v1` and one rendered by `threshold v3` rest on different
 * grounding, and an edge edit is itself a version bump — so the number the author sees
 * here is the number that will appear in provenance.
 */
export default function OperatorNode({ data, selected }) {
  return (
    <div
      className={`writer-op-node${selected ? ' writer-op-node--selected' : ''}`}
      data-testid="operator-node"
      data-operator={data.name}
    >
      <Handle type="target" position={Position.Left} />
      <div className="writer-op-node__head">
        <code>/{data.name}</code>
        <span className="writer-op-node__version">v{data.version}</span>
      </div>
      <p className="writer-op-node__definition">{data.definition}</p>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
