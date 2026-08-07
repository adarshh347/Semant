import React from 'react';
import { curve, curveMid, layout } from './layout';
import {
    EPISTEMIC_INTERPRETIVE, EPISTEMIC_MEASURED, LEDGER_COMMITTED, SPAN_WITHIN,
} from './constellationClient';

/**
 * WAVE4 — the neighbourhood, drawn.
 *
 * ## Three facts per edge, on three channels, and none of them alone
 *
 *     span            which COLUMN(s) the line lives in — a within-image edge stays inside one
 *                     picture's column, a crossing spans the gap. Plus a class, plus the label.
 *     epistemic       stroke DASH — solid for measured, dashed for interpretive, dotted for an
 *                     edge whose mark cannot be read at all.
 *     ledger_status   stroke WIDTH — thin while proposed, heavy once a person has committed it.
 *
 * Every one of them is also written on the edge's label. Styling alone would put the whole
 * epistemic story in the hands of a stylesheet, and the failure the curator lane already caught —
 * two honest fields rendered as one settled-looking thing — is a rendering failure, not a data one.
 *
 * ## `epistemic: null` is drawn as unreadable, not as uncertain
 *
 * An Atlas movement edge whose cited mark nobody committed genuinely cannot say what kind of
 * knowing it is: the mark is in no post and there is nothing to read it off. That is a third state
 * and it gets a third treatment (dotted, and the label says "no readable mark") rather than being
 * folded into `interpretive`, which is a producer's claim about its own work and would be putting
 * words in an absence's mouth.
 */

function edgeClass(edge) {
    const parts = ['con-edge', `con-edge--${edge.span}`];
    if (edge.epistemic === EPISTEMIC_MEASURED) parts.push('con-edge--measured');
    else if (edge.epistemic === EPISTEMIC_INTERPRETIVE) parts.push('con-edge--interpretive');
    else parts.push('con-edge--unreadable');
    parts.push(edge.ledger_status === LEDGER_COMMITTED
        ? 'con-edge--committed' : 'con-edge--proposed');
    return parts.join(' ');
}

function edgeLabel(edge) {
    const known = edge.epistemic || 'no readable mark';
    return `${edge.relation} · ${known} · ${edge.ledger_status}`;
}

export default function ConstellationGraph({ nodes, edges, onSelectEdge, selectedEdgeId }) {
    if (!nodes || nodes.length === 0) {
        return <p className="con-muted">Nothing to draw yet.</p>;
    }
    const { columns, positions, width, height } = layout(nodes);
    // THE LEFT GUTTER the within-image arcs and their labels bow into. `layout` sizes the columns;
    // the arc is a rendering decision and its room belongs here, not in the geometry.
    const gutter = 170;

    return (
        <div className="con-graphwrap">
            {/* INTRINSIC SIZE, not `width="100%"`. A one-column neighbourhood has a viewBox
                ~316 wide; stretched to fill an 810px pane it scaled everything by 2.5x and the
                11px labels rendered at 28, overlapping the curves they belonged to. The wrapper
                scrolls instead — which is what `overflow-x: auto` was already there for. */}
            <svg className="con-graph"
                 viewBox={`${-gutter} 0 ${width + gutter} ${height}`}
                 width={width + gutter} height={height}
                 role="img" aria-label="the constellation reachable from this locus">
                <defs>
                    <marker id="con-arrow" viewBox="0 0 10 10" refX="9" refY="5"
                            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                        <path d="M 0 0 L 10 5 L 0 10 z" className="con-arrowhead" />
                    </marker>
                </defs>

                {/* THE IMAGE COLUMNS. A picture is a place, and drawing it as one is what makes
                    "this edge stays inside a picture" visible before any stroke is read. */}
                {columns.map((column) => (
                    <g key={column.post_id} className="con-column">
                        <rect x={column.x - 14} y={26} width={column.width + 28}
                              height={height - 52} rx="12" className="con-columnbox" />
                        <text x={column.x + column.width / 2} y={16} className="con-columnlabel">
                            {column.post_id.slice(-8)}
                        </text>
                    </g>
                ))}

                {edges.map((edge) => {
                    const from = positions[edge.a_node];
                    const to = positions[edge.b_node];
                    if (!from || !to) return null;
                    const mid = curveMid(from, to);
                    const active = edge.edge_id === selectedEdgeId;
                    return (
                        <g key={edge.edge_id}
                           className={`con-edgegroup${active ? ' is-active' : ''}`}
                           onClick={() => onSelectEdge && onSelectEdge(edge.edge_id)}>
                            <path
                                d={curve(from, to)}
                                className={edgeClass(edge)}
                                fill="none"
                                markerEnd={edge.directed ? 'url(#con-arrow)' : undefined}
                            />
                            {/* In the left gutter the arcs bow into, right-aligned so several
                                labels stack cleanly instead of overlapping each other and the
                                region names on the other side of the dots. */}
                            <text x={mid.x - 4} y={mid.y + 3} className="con-edgelabel">
                                {edgeLabel(edge)}
                            </text>
                        </g>
                    );
                })}

                {nodes.map((node) => {
                    const at = positions[node.node_id];
                    if (!at) return null;
                    return (
                        <g key={node.node_id}
                           className={`con-node${node.is_seed ? ' is-seed' : ''}`}
                           transform={`translate(${at.x}, ${at.y})`}>
                            <circle r={node.is_seed ? 8 : 5} className="con-nodedot" />
                            <text x={13} y={4} className="con-nodelabel">
                                {node.region_id}
                            </text>
                            <text x={13} y={17} className="con-nodehop">
                                {node.is_seed ? 'the seed' : `${node.hop} hop${node.hop === 1 ? '' : 's'}`}
                            </text>
                        </g>
                    );
                })}
            </svg>
        </div>
    );
}
