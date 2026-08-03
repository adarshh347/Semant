import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    ReactFlow, Background, Controls, MiniMap, applyNodeChanges,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import AtlasImageNode from './AtlasImageNode.jsx';
import { atlasService } from './atlasService.js';
import {
    ATLAS_NODE_TYPE, arrangementFrom, flowNodesFromView, positionsOf, refusalLines,
} from './atlasDocument.js';

/**
 * ATLAS C1 — the canvas: a corpus, coexisting, with its committed percepts on it.
 *
 * WHAT THE SURFACE IS FOR. Everything above Layer 3 has looked at one picture at a time. The
 * reading that matters across a corpus — a dispersed civic ground against a centralized rotunda —
 * is not IN any one photograph, and you cannot see it in a surface that shows one. This is the
 * place where the images sit together and a writer can move them around while thinking.
 *
 * SPATIAL POSITION ASSERTS NOTHING. Dragging two nodes together is a writer's thinking aid, not a
 * relation claimed, and nothing in this component reads the distance between nodes. The moment
 * proximity meant something, every accidental arrangement would become an assertion nobody made.
 * A relation is a drawn edge, an edge is a real `compare_views` percept, and that is C3.
 *
 * THE DOCUMENT STORES ARRANGEMENT ONLY. `data` on each node — the image, the overlays — comes from
 * `/view`, hydrated from the ledger on every load, and is never sent back. What this component
 * saves is `{node_id, x, y}`, debounced, for the nodes that actually moved.
 *
 * SAVING IS VISIBLE, INCLUDING WHEN IT REFUSES. A save that dropped a stale node quietly would
 * leave a curator believing the canvas holds something it does not, so refusals render as text on
 * the surface rather than as a console warning.
 */

const SAVE_DEBOUNCE_MS = 600;

const nodeTypes = { [ATLAS_NODE_TYPE]: AtlasImageNode };

export default function AtlasCanvas({ atlasId, service = atlasService }) {
    const [view, setView] = useState(null);
    const [nodes, setNodes] = useState([]);
    const [error, setError] = useState('');
    const [status, setStatus] = useState('');
    const [refusals, setRefusals] = useState([]);

    // The arrangement the SERVER is known to hold. A save diffs against this, not against the last
    // render, so a drag that ends where it started sends nothing.
    const saved = useRef({});
    const timer = useRef(null);

    useEffect(() => {
        let live = true;
        setError('');
        (async () => {
            try {
                const data = await service.view(atlasId);
                if (!live) return;
                setView(data);
                const flow = flowNodesFromView(data);
                setNodes(flow);
                saved.current = positionsOf(flow);
            } catch (e) {
                if (live) setError(e?.message || 'Could not open this Atlas.');
            }
        })();
        return () => { live = false; if (timer.current) clearTimeout(timer.current); };
    }, [atlasId, service]);

    const flush = useCallback(async (current) => {
        const patches = arrangementFrom(current, saved.current);
        if (!patches.length) return;
        setStatus('saving…');
        try {
            const res = await service.saveArrangement(atlasId, patches);
            // Trust what came BACK, not what was sent — the server is what a reload will read,
            // and a refused node must not be recorded here as though it had moved.
            const confirmed = {};
            (res?.atlas?.nodes || []).forEach((n) => {
                confirmed[String(n.node_id)] = { x: Number(n.x), y: Number(n.y) };
            });
            saved.current = confirmed;
            setRefusals(refusalLines(res?.refused));
            setStatus('arrangement saved');
        } catch (e) {
            // Never a silent failure: an arrangement the curator believes is saved and is not
            // is the one outcome worse than an error message.
            setStatus('');
            setError(e?.message || 'The arrangement did not save.');
        }
    }, [atlasId, service]);

    const onNodesChange = useCallback((changes) => {
        setNodes((prev) => {
            const next = applyNodeChanges(changes, prev);
            if (timer.current) clearTimeout(timer.current);
            timer.current = setTimeout(() => flush(next), SAVE_DEBOUNCE_MS);
            return next;
        });
    }, [flush]);

    const unreadable = view?.unreadable || [];
    const counts = useMemo(() => ({
        images: nodes.length,
        percepts: nodes.reduce((n, node) => n
            + (node.data?.grounds?.length || 0)
            + (node.data?.marks?.length || 0)
            + (node.data?.regions?.length || 0), 0),
    }), [nodes]);

    if (error && !view) {
        return <div className="atlas-error" role="alert">{error}</div>;
    }

    return (
        <div className="atlas-shell">
            <header className="atlas-head">
                <div className="atlas-head-what">
                    <h1 className="atlas-title">{view?.title || 'Atlas'}</h1>
                    <p className="atlas-sub">
                        {counts.images} image{counts.images === 1 ? '' : 's'} ·{' '}
                        {counts.percepts} committed percept{counts.percepts === 1 ? '' : 's'}
                        {' · '}
                        {/* Said out loud, on the surface, because it is the rule a canvas most
                            tempts a reader to forget. */}
                        <em className="atlas-note">position is a thinking aid — it asserts nothing</em>
                    </p>
                </div>
                <div className="atlas-head-status" aria-live="polite">
                    {status && <span className="atlas-status">{status}</span>}
                </div>
            </header>

            {unreadable.length > 0 && (
                <div className="atlas-banner is-unreadable" role="note">
                    {unreadable.length} image{unreadable.length === 1 ? '' : 's'} in this corpus
                    could not be read. {unreadable.length === 1 ? 'It stays' : 'They stay'} on the
                    canvas rather than disappearing from it.
                </div>
            )}

            {refusals.length > 0 && (
                <ul className="atlas-banner is-refused" role="alert">
                    {refusals.map((line, i) => <li key={i}>{line}</li>)}
                </ul>
            )}

            {error && view && <div className="atlas-banner is-error" role="alert">{error}</div>}

            <div className="atlas-canvas">
                <ReactFlow
                    nodes={nodes}
                    edges={[]}
                    nodeTypes={nodeTypes}
                    onNodesChange={onNodesChange}
                    // C1 draws no edges. Connection is C3's gesture, and it will mean invoking
                    // `compare_views` — not drawing a line.
                    nodesConnectable={false}
                    elementsSelectable
                    fitView
                    minZoom={0.1}
                    maxZoom={2}
                    proOptions={{ hideAttribution: false }}
                >
                    <Background gap={48} size={1} />
                    <Controls showInteractive={false} />
                    <MiniMap pannable zoomable ariaLabel="Atlas overview" />
                </ReactFlow>
            </div>
        </div>
    );
}
