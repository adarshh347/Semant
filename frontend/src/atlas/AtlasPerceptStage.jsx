import React, { useRef } from 'react';
import GroundLayers from '../differential/GroundLayers.jsx';
import RegionOverlay from '../components/RegionOverlay.jsx';
import useStageGeometry, { useNaturalSize } from '../differential/useStageGeometry.js';
// The region shapes' own stylesheet. Imported explicitly rather than inherited: `.rs-shape` lives
// with `RegionSurface`, and a surface whose overlays are only styled when some other route happens
// to have been mounted first renders differently depending on where you came from.
import '../components/RegionSurface.css';

/**
 * ATLAS T1 — one image wearing its committed percepts, read-only. The renderer BOTH modes mount.
 *
 * WHY THIS FILE EXISTS. C1 put this composition inside the canvas node. T1 adds a second mode that
 * needs the identical thing in a grid cell, and the tempting move — copy the twelve lines — is
 * exactly how two renderers begin to drift. A percept drawn 20px off in the Light Table would be a
 * claim about a part of the picture nobody measured, and it would disagree with the same percept
 * on the Canvas. So the composition moved here and both modes call it. Modes swap the LAYOUT
 * around the evidence; they never swap how the evidence is drawn.
 *
 * BOTH RENDERERS, ALWAYS. `GroundLayers` draws grounds and marks (field washes, paths, boundaries,
 * flow fields) and takes `regions` only as lookup context for a ground that references one; region
 * EXTENTS belong to `RegionOverlay`. Mounting only the first is how an image with twenty committed
 * regions renders bare — which it did, before C2's live proof caught it. `PerceptFigure` composes
 * them the same way, and the stage-geometry contract (`useNaturalSize` + `useStageGeometry`) is the
 * sanctioned path: re-deriving letterbox maths by hand is how the earrings land on a cheekbone.
 *
 * READ-ONLY, HERE AND EVERYWHERE. `interactive={false}`, no draft, no pick handler, no Accept.
 * Percepts are made in the Differential. This surface shows what the ledger holds.
 */
export default function AtlasPerceptStage({ data, className = '' }) {
    const stageRef = useRef(null);
    const [natural, onImgLoad] = useNaturalSize();
    const { content } = useStageGeometry(stageRef, natural);

    const regions = data?.regions || [];

    return (
        <div className={`atlas-stage ${className}`.trim()} ref={stageRef}>
            {data?.imageRef ? (
                <img className="atlas-node-img" src={data.imageRef} alt={data.title || ''}
                    onLoad={onImgLoad} draggable={false} />
            ) : (
                <div className="atlas-node-missing">no image on this post</div>
            )}

            {natural && content && (
                <GroundLayers
                    grounds={data.grounds}
                    regions={regions}
                    marks={data.marks}
                    natural={natural}
                    content={content}
                    interactive={false}
                />
            )}

            {natural && regions.length > 0 && (
                <RegionOverlay
                    natural={natural}
                    regions={regions}
                    viewMap="focus"
                    interactive={false}
                    className="atlas-node-svg"
                />
            )}
        </div>
    );
}
