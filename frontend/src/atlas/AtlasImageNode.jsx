import React from 'react';
import AtlasPerceptStage from './AtlasPerceptStage.jsx';
import { perceptSummary } from './atlasDocument.js';

/**
 * ATLAS C1/C2 — one image of the corpus, on the canvas, wearing its committed percepts.
 *
 * THE RENDERER IS INHERITED, NOT REWRITTEN. The overlay composition lives in `AtlasPerceptStage`,
 * which the Light Table mounts too — one renderer, two modes. Underneath it is `GroundLayers`, the
 * same component the Differential stage and the Chiasm pane mount, on the same stage-geometry
 * contract. If a mask lands wrong here it lands wrong in the workspace too, and one fix corrects
 * every surface.
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
            {/* The ledger's committed evidence, through the renderer the Light Table also uses. */}
            <AtlasPerceptStage data={data} className="atlas-node-stage" />

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
