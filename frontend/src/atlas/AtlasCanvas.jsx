import React, { useCallback } from 'react';
import {
    ReactFlow, Background, Controls, MiniMap, applyNodeChanges,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import AtlasImageNode from './AtlasImageNode.jsx';
import AtlasClaimNode from './AtlasClaimNode.jsx';
import { ATLAS_NODE_TYPE } from './atlasDocument.js';
import { CLAIM_NODE_TYPE } from './atlasPlan.js';

/**
 * ATLAS C1/C2/T1/C3/C4 — the Canvas: a corpus, coexisting, with what has been claimed about it.
 *
 * WHAT THE SURFACE IS FOR. Everything above Layer 3 has looked at one picture at a time. The
 * reading that matters across a corpus — a dispersed civic ground against a centralized rotunda —
 * is not IN any one photograph, and you cannot see it in a surface that shows one. This is the
 * place where the images sit together and a writer can move them around while thinking.
 *
 * SPATIAL POSITION ASSERTS NOTHING. Dragging two nodes together is a writer's thinking aid, not a
 * relation claimed, and nothing in this component reads the distance between nodes. The moment
 * proximity meant something, every accidental arrangement would become an assertion nobody made.
 * Only a DRAWN edge asserts anything, and a drawn edge is a real percept.
 *
 * T1 MADE THIS A RENDERER, AND C3/C4 KEPT IT ONE. It used to own the fetch, the saves and the
 * Differential path; those live in `AtlasWorkspace`, which every mode shares. The plan and the
 * relations live there too — this component receives nodes and edges and reports gestures, and
 * knows nothing about theses, claims, or `compare_views`. That is what lets plan mode be a third
 * MODE rather than a second canvas.
 *
 * TWO KINDS OF LINE, AND THEY MUST NEVER READ AS ONE KIND.
 *   · C4 bindings  — claim→image, dashed, unarrowed, labelled with an argumentative function.
 *                    They assert a percept WOULD resolve, and live in the document's `plan`.
 *   · C3 relations — image↔image, solid, arrowed, labelled with the relation's own role and
 *                    epistemic kind. They assert a comparison WAS produced and committed, and
 *                    live in `edges`.
 * The workspace builds both, already distinguished; the styling that keeps them apart lives in
 * `atlas.css` on `.atlas-edge` and `.atlas-relation`.
 *
 * `applyNodeChanges` stays here because it is React Flow's own reducer and means nothing to the
 * Light Table; the workspace receives the resulting array and decides what is worth saving.
 */

const nodeTypes = {
    [ATLAS_NODE_TYPE]: AtlasImageNode,
    [CLAIM_NODE_TYPE]: AtlasClaimNode,
};

export default function AtlasCanvas({
    nodes = [], edges = [], onNodesChange, onConnect, connectable = false,
}) {
    const handleChanges = useCallback((changes) => {
        onNodesChange?.(applyNodeChanges(changes, nodes));
    }, [nodes, onNodesChange]);

    return (
        <div className="atlas-canvas">
            <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                onNodesChange={handleChanges}
                onConnect={onConnect}
                // Connection is C3's gesture, and it means invoking `compare_views` — not drawing
                // a line. `onConnect` never adds an edge itself: an ungroundable pair leaves the
                // canvas exactly as it was, wearing the refusal.
                nodesConnectable={connectable}
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
    );
}
