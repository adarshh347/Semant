import React, { useEffect, useRef } from 'react';
import { paintFields } from './fieldCanvas';

/**
 * GroundLayers — the shared Ground renderer (Differential v1 · increment B).
 *
 * Slaved to the stage-geometry contract: `content` is the letterboxed content
 * box, all stored geometry is normalized. Consumed by BOTH surfaces:
 *   - the Differential stage renders every Ground plus the in-progress draft;
 *   - the Chiasm pane mounts it in recall mode, where only the Grounds a
 *     playing Percept cites appear — Chiasm's resting state stays quiet.
 *
 * Increment B carries the canvas layer (Soft Field). The SVG layer (Path,
 * Boundary, Constellation, Relation, Frame) joins in C/D on the same contract.
 */
export default function GroundLayers({
    grounds = [],
    content = null,
    focusGroundIds = null,
    recall = null,          // useRecallPlayer result, or null
    recallOnly = false,     // Chiasm: render nothing unless a recall is playing
    draftStrokes = null,    // Differential: the uncommitted brush strokes
}) {
    const canvasRef = useRef(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const fields = [];
        for (const g of grounds) {
            if (g.ground_type !== 'field') continue;
            if (recall?.active) {
                const p = recall.progressFor(g.id);
                if (p > 0) fields.push({ ground: g, alpha: 1, progress: p });
                else if (!recallOnly) fields.push({ ground: g, alpha: 0.25, progress: 1 });
            } else if (!recallOnly) {
                const dimmed = focusGroundIds && !focusGroundIds.has(g.id);
                fields.push({ ground: g, alpha: dimmed ? 0.3 : 1, progress: 1 });
            }
        }
        if (draftStrokes?.length) {
            fields.push({ ground: { strokes: draftStrokes }, alpha: 1, progress: 1 });
        }
        paintFields(canvas, fields, content);
    }, [grounds, content, focusGroundIds, recall, recallOnly, draftStrokes]);

    if (!content) return null;
    return (
        <canvas
            ref={canvasRef}
            className="gl-canvas"
            style={{
                position: 'absolute',
                left: content.x, top: content.y,
                width: content.w, height: content.h,
                pointerEvents: 'none',
            }}
            aria-hidden="true"
        />
    );
}
