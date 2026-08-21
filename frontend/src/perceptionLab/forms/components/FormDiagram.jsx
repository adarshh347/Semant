import React from 'react';
import { isDiagramLayer } from '../layerModel';

/**
 * PERCEPTUAL-FORMS-001E — trees, graphs and matrices, in a space that is not the image.
 *
 * THE WHOLE POINT OF A SEPARATE COMPONENT. `FormStage` refuses a `diagram` layer and this one
 * refuses everything else, so the two spaces cannot be confused by a careless prop. A graph node
 * has no location; the circle it sits on was chosen by this browser because a circle is
 * reproducible, and drawing it over the photograph would give it a place.
 *
 * DIRECTION IS DRAWN AND ALSO WRITTEN. A containment edge gets an arrowhead AND a sentence in the
 * edge list, because "contains" is not symmetric and an arrowhead is small. A person who misses
 * the arrow still reads which one is inside the other.
 *
 * THE MATRIX EXISTS FOR ONE REASON. A node-link drawing renders "examined and unrelated" as empty
 * space, indistinguishable from "never checked". The matrix has a cell for every pair, so the
 * difference between three recorded edges and six examined pairs is visible instead of implied.
 */

const pct = (v) => `${v * 100}%`;

function Nodes({ nodes, focusId, onFocus }) {
    return (
        <>
            {nodes.map((n) => (
                <g key={n.node_id} className="pl-fm-node" data-node={n.node_id}
                    data-degree={n.degree ?? null}
                    data-resolved={n.resolved === false ? 'false' : 'true'}
                    data-focused={focusId === n.node_id ? 'true' : 'false'}
                    onClick={() => onFocus?.(n.node_id)}>
                    <circle cx={pct(n.x)} cy={pct(n.y)} r="14" vectorEffect="non-scaling-stroke"
                        className="pl-fm-nodedot"
                        // A node whose endpoint does not resolve is drawn hollow AND labelled.
                        // Solid-versus-hollow is the second channel; the label is the third.
                        strokeDasharray={n.resolved === false ? '3 3' : undefined} />
                    <text x={pct(n.x)} y={pct(n.y)} className="pl-fm-nodelabel"
                        textAnchor="middle" dominantBaseline="middle">
                        {n.node_id}
                    </text>
                </g>
            ))}
        </>
    );
}

function Edges({ edges, ns }) {
    return (
        <>
            {edges.map((e) => (
                <g key={e.edge_id} className="pl-fm-edge" data-edge={e.edge_id}
                    data-kind={e.kind ?? 'contains'}
                    data-directed={e.directed ? 'true' : 'false'}
                    data-stale={e.stale ? 'true' : 'false'}
                    data-conditioned-on={e.conditioned_on ?? null}>
                    <line
                        x1={pct(e.from.x)} y1={pct(e.from.y)}
                        x2={pct(e.to.x)} y2={pct(e.to.y)}
                        className="pl-fm-edgeline"
                        vectorEffect="non-scaling-stroke"
                        // A disjoint edge is a measured NON-contact. Drawn like a contact it would
                        // say the opposite of what it measured.
                        strokeDasharray={e.kind === 'disjoint' ? '2 6'
                            : e.conditioned_on ? '2 5' : undefined}
                        markerEnd={e.directed ? `url(#${ns}-diagarrow)` : undefined}
                    />
                </g>
            ))}
        </>
    );
}

let seq = 0;

function NodeLink({ layer, focusId, onFocus }) {
    const ns = React.useMemo(() => { seq += 1; return `pl-fd-${seq}`; }, []);
    const { nodes, edges, dangling = [], isolated = [], unreached = [] } = layer.draw;
    return (
        <div className="pl-fm-diagram" data-diagram={layer.layer_id}
            data-nodes={nodes?.length ?? 0} data-edges={edges?.length ?? 0}>
            <svg className="pl-fm-diagramsvg" viewBox="0 0 100 100" preserveAspectRatio="none"
                role="img" aria-label={layer.label}>
                <defs>
                    <marker id={`${ns}-diagarrow`} className="pl-fm-arrow" viewBox="0 0 10 10"
                        refX="18" refY="5" markerWidth="5" markerHeight="5"
                        orient="auto-start-reverse">
                        <path d="M 0 0 L 10 5 L 0 10 z" />
                    </marker>
                </defs>
                <Edges edges={edges || []} ns={ns} />
                <Nodes nodes={nodes || []} focusId={focusId} onFocus={onFocus} />
            </svg>

            {/* The edge list. Direction in words, because an arrowhead is small and the claim is
                the whole measurement. */}
            {edges?.length ? (
                <table className="pl-fm-edgetable" data-edge-table={layer.layer_id}>
                    <caption>
                        {edges.length} edge{edges.length === 1 ? '' : 's'}, in record order
                    </caption>
                    <thead>
                        <tr>
                            <th scope="col">relation</th>
                            <th scope="col">directed</th>
                            <th scope="col">basis</th>
                            <th scope="col">status</th>
                            <th scope="col">measurements</th>
                        </tr>
                    </thead>
                    <tbody>
                        {edges.map((e) => (
                            <tr key={e.edge_id} data-edge-row={e.edge_id}>
                                <td data-edge-sentence={e.edge_id}>
                                    {e.sentence
                                        ?? `${e.source_node_id} → ${e.target_node_id}`}
                                </td>
                                <td data-edge-directed={e.directed ? 'true' : 'false'}>
                                    {e.directed ? 'yes' : 'no'}
                                </td>
                                <td>{e.basis ?? '—'}</td>
                                <td>{e.epistemic_status ?? '—'}</td>
                                <td data-edge-measurements={e.edge_id}>
                                    {Object.entries(e.measurements || {})
                                        .filter(([, v]) => v !== null && v !== undefined)
                                        .map(([k, v]) => `${k.replace(/_/g, ' ')} ${v}`)
                                        .join(' · ') || 'none recorded'}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            ) : null}

            {/* Named rather than dropped. Each of these is a fact about the RECORD. */}
            {dangling.length ? (
                <p className="pl-fm-why" data-dangling={dangling.length}>
                    {dangling.length} edge{dangling.length === 1 ? '' : 's'} name a node that is
                    {' '}not in this record: {dangling.map((d) => `${d.edge_id} → `
                        + `${(d.missing || [d.missing_parent]).join(', ')}`).join('; ')}.
                </p>
            ) : null}
            {unreached.length ? (
                <p className="pl-fm-why" data-unreached={unreached.length}>
                    {unreached.join(', ')} {unreached.length === 1 ? 'is' : 'are'} in this record
                    {' '}and the declared roots never reach {unreached.length === 1 ? 'it' : 'them'}.
                    {' '}Re-rooting them silently would hide the break.
                </p>
            ) : null}
            {isolated.length ? (
                <p className="pl-fm-why" data-isolated={isolated.length}>
                    {isolated.join(', ')} carr{isolated.length === 1 ? 'ies' : 'y'} no edge. That
                    {' '}is a node the record examined and related to nothing — not a node that
                    {' '}went missing.
                </p>
            ) : null}
        </div>
    );
}

function Matrix({ layer }) {
    const { matrix } = layer.draw;
    return (
        <div className="pl-fm-matrixwrap" data-matrix={layer.layer_id}>
            <table className="pl-fm-matrix">
                <caption>{layer.label}</caption>
                <thead>
                    <tr>
                        <th scope="col"><span className="pl-fm-vh">source ╲ target</span></th>
                        {matrix.ids.map((id) => <th key={id} scope="col">{id}</th>)}
                    </tr>
                </thead>
                <tbody>
                    {matrix.rows.map((row) => (
                        <tr key={row.node_id}>
                            <th scope="row">{row.node_id}</th>
                            {row.cells.map((c) => (
                                <td
                                    key={c.col}
                                    data-cell={`${c.row}|${c.col}`}
                                    data-self={c.self ? 'true' : 'false'}
                                    data-edge-kind={c.edge?.kind ?? 'none'}
                                >
                                    {/* THREE STATES, THREE MARKS. A self-pair was never a pair; a
                                        recorded edge names its kind; a blank cell is a pair that
                                        was examined and found unrelated. */}
                                    {c.self ? '—' : (c.edge ? c.edge.kind : '·')}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
            <p className="pl-fm-note">
                <strong>—</strong> a thing against itself, which was never a pair.
                {' '}<strong>·</strong> examined, and no relation stood.
            </p>
        </div>
    );
}

export default function FormDiagram({ layers = [], focusId = null, onFocus = null }) {
    const drawable = layers.filter(isDiagramLayer);
    const refused = layers.filter(
        (l) => l.coordinate_system === 'image_normalized' || l.coordinate_system === 'raster_cells');
    return (
        <div className="pl-fm-diagrams" data-diagram-layers={drawable.length}>
            {drawable.map((l) => (l.draw.matrix
                ? <Matrix key={l.layer_id} layer={l} />
                : <NodeLink key={l.layer_id} layer={l} focusId={focusId} onFocus={onFocus} />))}
            {refused.length ? (
                <p className="pl-fm-refused" data-diagram-refused={refused.length}>
                    {refused.length} image-space layer{refused.length === 1 ? '' : 's'} reached the
                    {' '}diagram and {refused.length === 1 ? 'was' : 'were'} not drawn. Pixels do
                    {' '}not belong in a graph any more than nodes belong on an image.
                </p>
            ) : null}
        </div>
    );
}
