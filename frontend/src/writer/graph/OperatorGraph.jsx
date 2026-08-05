import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ReactFlow, Background, Controls, applyNodeChanges } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { writerService } from '../writerService';
import OperatorNode from './OperatorNode';
import {
  KIND_HELP,
  RELATION_KINDS,
  feedsRender,
  planConnection,
  relationsFor,
  toFlowEdges,
  toFlowNodes,
  wouldCycle,
} from './graphModel';
import './OperatorGraph.css';

/**
 * Semant Writer · W3 — the author's ontology, visible and editable.
 *
 * Built on the same React Flow surface the Atlas runs on — the same MIT component, not a
 * second graph library.
 *
 * A VIEW OVER THE LEDGER, AND ONLY THAT. This component reads operators and writes edges.
 * It has no path to the manuscript at all: no accept, no scene, no block. Editing the
 * ontology cannot move a word of committed prose, and the test suite asserts the export is
 * byte-identical across a session of edge editing.
 *
 * EDGES COMMIT DIRECTLY — and that is not a hole in propose-never-commit. That rule governs
 * what the MODEL writes. An edge is the author drawing their own ontology by hand; there is
 * no proposal to accept. What the edit does owe them is a VERSION BUMP (relations are part
 * of what an operator is) and validation, both of which happen server-side.
 *
 * ONE EDGE ACTS. `requires` conditions a render; every other kind is structure the author
 * can see and W4 will read. The picker says which is which, the legend says it again, and
 * the edges look different — because an author who cannot tell which edges change their
 * prose cannot reason about their own ontology.
 */
export default function OperatorGraph({ projectId, onClose = null }) {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [kind, setKind] = useState('requires');
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true);

  const nodeTypes = useMemo(() => ({ operator: OperatorNode }), []);

  const load = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const graph = await writerService.graph(projectId);
      // Keep any layout the author has dragged into place across a reload of the data.
      setNodes((prev) => {
        const positions = Object.fromEntries(prev.map((n) => [n.id, n.position]));
        return toFlowNodes(graph.nodes, positions);
      });
      setEdges(toFlowEdges(graph.edges));
      setError('');
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const onNodesChange = useCallback(
    // Position is a thinking aid and asserts nothing about the ontology — same discipline
    // as the Atlas canvas. It is not persisted.
    (changes) => setNodes((ns) => applyNodeChanges(changes, ns)),
    [],
  );

  /** Persist one operator's whole edge set, then reload so versions are what the server says. */
  const persist = useCallback(async (sourceName, nextEdges) => {
    setError('');
    try {
      const op = await writerService.setRelations(
        projectId, sourceName, relationsFor(sourceName, nextEdges),
      );
      setStatus(`/${sourceName} is now v${op.version}`);
      await load();
      return true;
    } catch (e) {
      setError(e.message);
      await load();          // the server refused; show what it actually holds
      return false;
    }
  }, [projectId, load]);

  // The rules live in `planConnection` (pure, tested); this only reports the outcome.
  // The SERVER validates every one of them again and its refusal is surfaced too — asking
  // locally is a courtesy so the author hears it while drawing, never the guard.
  const onConnect = useCallback(async ({ source, target }) => {
    const plan = planConnection({ source, target, kind, edges });
    if (!plan.ok) {
      setError(plan.error);
      return;
    }
    await persist(source, plan.edges);
  }, [edges, kind, persist]);

  const removeEdge = useCallback(async (edge) => {
    const next = edges.filter((e) => e.id !== edge.id);
    setSelectedEdge(null);
    await persist(edge.source, next);
  }, [edges, persist]);

  const retypeEdge = useCallback(async (edge, nextKind) => {
    if (nextKind === 'requires' && wouldCycle(edge.source, edge.target, 'requires',
      edges.filter((e) => e.id !== edge.id))) {
      setError(`Retyping to \`requires\` would close a cycle.`);
      return;
    }
    const next = edges.map((e) => (
      e.id === edge.id
        ? { ...e, label: nextKind, data: { kind: nextKind, feedsRender: feedsRender(nextKind) } }
        : e
    ));
    setSelectedEdge(null);
    await persist(edge.source, next);
  }, [edges, persist]);

  return (
    <section className="writer-graph" data-testid="operator-graph">
      <header className="writer-graph__bar">
        <strong>Your ontology</strong>

        <label htmlFor="writer-graph-kind">Draw</label>
        <select
          id="writer-graph-kind"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          data-testid="kind-picker"
        >
          {RELATION_KINDS.map((k) => (
            <option key={k} value={k}>
              {k}
              {feedsRender(k) ? ' — shapes the render' : ''}
            </option>
          ))}
        </select>
        <span className="writer-graph__help">{KIND_HELP[kind]}</span>

        {onClose && (
          <button type="button" onClick={onClose} className="writer-graph__close">Close</button>
        )}
      </header>

      <div className="writer-graph__legend">
        <span className="writer-graph__legend-item">
          <i className="writer-graph__swatch writer-graph__swatch--acts" />
          <code>requires</code> — pulled into the render, and recorded in provenance
        </span>
        <span className="writer-graph__legend-item">
          <i className="writer-graph__swatch writer-graph__swatch--inert" />
          everything else — structure you can see; it does not change your prose
        </span>
      </div>

      {error && <p className="writer-graph__error" data-testid="graph-error">{error}</p>}
      {status && !error && <p className="writer-graph__status" data-testid="graph-status">{status}</p>}

      <div className="writer-graph__canvas">
        {loading ? (
          <p className="writer-graph__empty">Loading…</p>
        ) : nodes.length === 0 ? (
          <p className="writer-graph__empty">
            No operators yet. Define one and it appears here.
          </p>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onConnect={onConnect}
            onEdgeClick={(_, edge) => setSelectedEdge(edge)}
            fitView
            proOptions={{ hideAttribution: false }}
          >
            <Background />
            <Controls />
          </ReactFlow>
        )}
      </div>

      {selectedEdge && (
        <aside className="writer-graph__edge-panel" data-testid="edge-panel">
          <code>
            {selectedEdge.source} {selectedEdge.data?.kind ?? selectedEdge.label} {selectedEdge.target}
          </code>
          <span className="writer-graph__help">
            {feedsRender(selectedEdge.data?.kind ?? selectedEdge.label)
              ? 'This edge shapes the render.'
              : 'This edge does not change your prose.'}
          </span>
          <select
            aria-label="edge kind"
            value={selectedEdge.data?.kind ?? selectedEdge.label}
            onChange={(e) => retypeEdge(selectedEdge, e.target.value)}
            data-testid="edge-kind"
          >
            {RELATION_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
          <button type="button" onClick={() => removeEdge(selectedEdge)} data-testid="remove-edge">
            Remove
          </button>
          <button type="button" onClick={() => setSelectedEdge(null)}>Done</button>
        </aside>
      )}
    </section>
  );
}
