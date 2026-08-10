import React, { useMemo, useState } from 'react';
import { EmptyState } from './Chips';
import { RelationRow } from './TopologyStage';
import { projectRelationSet, relationGraph } from '../topologyView';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — the relations, as a list and as a graph.
 *
 * TYPED STAYS TYPED. The single largest failure available to a topology surface is to render
 * `nested_within` as "these two are related" — at which point the one thing the organ measured,
 * WHICH of the two is inside the other, is gone and no amount of hovering brings it back. So every
 * row carries its kind, its direction and its own sentence, and `relationSentence` throws on a
 * kind it has no words for rather than falling through to something generic.
 *
 * The graph is the same measurement, arranged by endpoint instead of by pair. It exists because a
 * list of twenty pairs does not show that one instance is in eighteen of them, and a node's degree
 * is the fastest way to see an adapter that has produced one enormous mask everything touches.
 *
 * NODES ARE IDENTITIES, NOT NAMES. Two instances both called "drapery" are two nodes. Merging
 * them by label would make the graph assert a relation nobody measured.
 */
export default function RelationReadout({ artifact, byId, focusedRelationId, onFocusRelation }) {
    const [as, setAs] = useState('list');
    const relations = useMemo(
        () => projectRelationSet(artifact, byId), [artifact, byId]);
    const graph = useMemo(() => relationGraph(relations), [relations]);

    const payload = artifact?.measurement?.payload;
    if (payload?.variant !== 'topology_relation_set') return null;

    return (
        <section className="pl-panel" aria-label="Relations" data-relation-readout>
            <div className="pl-panel-head">
                <h2 className="pl-panel-title">Relations</h2>
                <span className="pl-segmented" role="group" aria-label="How to arrange them">
                    <button type="button" className="pl-btn" data-arrange="list"
                        aria-pressed={as === 'list'} onClick={() => setAs('list')}>List</button>
                    <button type="button" className="pl-btn" data-arrange="graph"
                        aria-pressed={as === 'graph'} onClick={() => setAs('graph')}>Graph</button>
                </span>
            </div>

            <p className="pl-panel-sub" data-examined-note>
                {payload.pairs_examined} pair{payload.pairs_examined === 1 ? '' : 's'} examined,
                {' '}{payload.relations.length} held.
                {payload.bounded_to !== null
                    ? ` Bounded to ${payload.bounded_to} members, and the bound is on the record.`
                    : ''}
            </p>

            {relations.length === 0 ? (
                <EmptyState title="No relation of that kind held"
                    hint={`${payload.pairs_examined} pairs were compared and none stood in the
                        asked-for relation. That is a measurement — it is not the same as not
                        having looked.`} />
            ) : as === 'list' ? (
                <ul className="pl-steps" data-relation-list>
                    {relations.map((rel) => (
                        <RelationRow key={rel.relation_id} rel={rel}
                            focused={focusedRelationId === rel.relation_id}
                            onFocus={onFocusRelation} />
                    ))}
                </ul>
            ) : (
                <RelationGraph graph={graph} focusedRelationId={focusedRelationId}
                    onFocusRelation={onFocusRelation} />
            )}
        </section>
    );
}

function RelationGraph({ graph, focusedRelationId, onFocusRelation }) {
    return (
        <div data-relation-graph>
            <div className="pl-field">
                <span className="pl-label">Endpoints</span>
                <ul className="pl-list" data-graph-nodes>
                    {graph.nodes.map((n) => (
                        <li key={n.id} className="pl-turn" data-graph-node={n.id}
                            data-node-state={n.state}>
                            <span className="pl-row-name">{n.name}</span>
                            <span className="pl-row-meta" data-node-degree={n.degree}>
                                in {n.degree} relation{n.degree === 1 ? '' : 's'}
                                {n.state !== 'resolved' ? ` · ${n.state}` : ''}
                            </span>
                        </li>
                    ))}
                </ul>
            </div>
            <div className="pl-field">
                <span className="pl-label">Edges</span>
                <div className="pl-scroll">
                    <table className="pl-table" data-graph-edges>
                        <thead>
                            <tr>
                                <th scope="col">from</th>
                                <th scope="col">kind</th>
                                <th scope="col">to</th>
                                <th scope="col">basis</th>
                                <th scope="col">reads</th>
                            </tr>
                        </thead>
                        <tbody>
                            {graph.edges.map((e) => (
                                <tr key={e.relation_id} data-graph-edge={e.relation_id}
                                    data-edge-directed={String(e.directed)}
                                    aria-selected={focusedRelationId === e.relation_id}
                                    onClick={() => onFocusRelation?.(e.relation_id)}>
                                    <td><code>{e.from}</code></td>
                                    <td>
                                        {e.directed ? '→ ' : '— '}
                                        <code data-edge-kind={e.kind}>{e.kind}</code>
                                    </td>
                                    <td><code>{e.to}</code></td>
                                    <td data-edge-basis={e.basis}>{e.basis}</td>
                                    <td>{e.sentence}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
                <p className="pl-panel-sub">
                    An arrow is drawn only where the relation is directed. A symmetric{' '}
                    <code>meets</code> shown with an arrow would assert an asymmetry the organ did
                    not measure.
                </p>
            </div>
        </div>
    );
}
