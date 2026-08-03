import React, { useRef } from 'react';
import GroundLayers from '../differential/GroundLayers.jsx';
import RegionOverlay from '../components/RegionOverlay.jsx';
import useStageGeometry, { useNaturalSize } from '../differential/useStageGeometry.js';
import { perceptSummary } from './atlasDocument.js';
// The region shapes' own stylesheet. Imported explicitly rather than inherited: `.rs-shape` lives
// with `RegionSurface`, and a canvas whose overlays are only styled when some other route happens
// to have been mounted first is a canvas that renders differently depending on where you came from.
import '../components/RegionSurface.css';

/**
 * ATLAS C1/C2 — one image of the corpus, on the canvas, wearing its committed percepts.
 *
 * THE RENDERER IS INHERITED, NOT REWRITTEN. The overlay is `GroundLayers` — the same component the
 * Differential stage and the Chiasm pane both mount — driven by the same stage-geometry contract
 * (`useNaturalSize` + `useStageGeometry`). Writing a second percept renderer for a small canvas is
 * precisely how the two drift, and a percept drawn 20px off on the Atlas is a claim about a part
 * of the picture nobody measured. If a mask lands wrong here, it lands wrong in the workspace too,
 * and one fix corrects both.
 *
 * THE NODE ITSELF STAYS READ-ONLY. `interactive={false}`, no draft, no pick handler, no Accept.
 * C2 adds exactly ONE control, and what it does is leave: `open →` hands the image to the existing
 * Differential. The alternative — growing a brush, a review chip, an Accept onto a 420px card —
 * would have been a second, worse Differential, and then two places where a percept can be made
 * and only one of them properly guarded. The canvas shows evidence; the instrument makes it.
 *
 * AN UNREADABLE IMAGE STILL GETS A NODE. It renders as a card that says it could not be loaded.
 * Dropping it would quietly shrink the corpus, and "no percepts" and "could not be read" are
 * different facts about a photograph.
 */
export default function AtlasImageNode({ data }) {
    const stageRef = useRef(null);
    const [natural, onImgLoad] = useNaturalSize();
    const { content } = useStageGeometry(stageRef, natural);
    const summary = perceptSummary(data);

    const style = { width: `${data.w}px`, height: `${data.h}px` };

    if (!data.readable) {
        return (
            <div className="atlas-node is-unreadable" style={style}
                data-post-id={data.postId} data-readable="false">
                <div className="atlas-node-missing" role="note">
                    <strong>image unavailable</strong>
                    <span className="atlas-node-why">{data.unreadableReason}</span>
                </div>
                <div className="atlas-node-cap">
                    <span className="atlas-node-title">{data.postId}</span>
                </div>
            </div>
        );
    }

    return (
        <div className="atlas-node" style={style} data-post-id={data.postId} data-readable="true">
            <div className="atlas-node-stage" ref={stageRef}>
                {data.imageRef ? (
                    <img className="atlas-node-img" src={data.imageRef} alt={data.title || ''}
                        onLoad={onImgLoad} draggable={false} />
                ) : (
                    <div className="atlas-node-missing">no image on this post</div>
                )}

                {/* The ledger's committed evidence, through the shared renderers — BOTH of them,
                    composed exactly as `PerceptFigure` composes them, because they draw different
                    things. `GroundLayers` draws grounds and marks (field washes, paths, boundaries,
                    flow fields) and takes `regions` only as lookup context for a ground that
                    references one; region EXTENTS are `RegionOverlay`'s. Mounting only the first is
                    how a node with twenty committed regions renders bare — which is what it did
                    before this comment existed. */}
                {natural && content && (
                    <GroundLayers
                        grounds={data.grounds}
                        regions={data.regions}
                        marks={data.marks}
                        natural={natural}
                        content={content}
                        interactive={false}
                    />
                )}

                {natural && data.regions.length > 0 && (
                    <RegionOverlay
                        natural={natural}
                        regions={data.regions}
                        viewMap="focus"
                        interactive={false}
                        className="atlas-node-svg"
                    />
                )}
            </div>

            <div className="atlas-node-cap">
                <span className="atlas-node-title">{data.title || data.postId}</span>
                <span className="atlas-node-count" data-drawn={summary.drawn}>
                    {summary.drawn === 0 ? 'no committed percepts'
                        : `${summary.drawn} percept${summary.drawn === 1 ? '' : 's'}`}
                </span>
                {/* C2: the way in. `nodrag` is load-bearing — without it React Flow claims the
                    pointer for a drag and the button never fires a click. The only control on the
                    node, and it opens the existing instrument rather than doing anything itself. */}
                {data.onOpen && (
                    <button type="button" className="atlas-node-open nodrag nopan"
                        data-open-post={data.postId}
                        onClick={(e) => { e.stopPropagation(); data.onOpen(data.postId); }}
                        title={`Open ${data.title || data.postId} in the Differential`}>
                        open →
                    </button>
                )}
            </div>

            {/* Never a tooltip. A suggestion the canvas declined to draw is exactly the kind of
                thing a hover hides — and the curator would read the shorter list as complete. */}
            {summary.withheldNote && (
                <div className="atlas-node-withheld" role="note">{summary.withheldNote}</div>
            )}
        </div>
    );
}
