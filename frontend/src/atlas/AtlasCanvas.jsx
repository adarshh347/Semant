import React, { useCallback } from 'react';
import {
    ReactFlow, Background, Controls, MiniMap, applyNodeChanges,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import AtlasImageNode from './AtlasImageNode.jsx';
import { ATLAS_NODE_TYPE } from './atlasDocument.js';

/**
 * ATLAS C1/C2/T1 — the Canvas mode: a corpus, coexisting, with its committed percepts on it.
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
 * T1 MADE THIS A RENDERER. It used to own the fetch, the saves and the Differential path; those
 * moved up to `AtlasWorkspace`, which every mode shares. What is left is exactly the Canvas's own
 * job — laying nodes out in space and reporting drags — and that is the shape a mode should have.
 * `applyNodeChanges` stays here because it is React Flow's own reducer and means nothing to the
 * Light Table; the workspace receives the resulting array and decides what is worth saving.
 */

const nodeTypes = { [ATLAS_NODE_TYPE]: AtlasImageNode };

export default function AtlasCanvas({ nodes = [], onNodesChange }) {
    const handleChanges = useCallback((changes) => {
        onNodesChange?.(applyNodeChanges(changes, nodes));
    }, [nodes, onNodesChange]);

    return (
        <div className="atlas-canvas">
            <ReactFlow
                nodes={nodes}
                edges={[]}
                nodeTypes={nodeTypes}
                onNodesChange={handleChanges}
                // No edges yet. Connection is C3's gesture, and it will mean invoking
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
    );
}
