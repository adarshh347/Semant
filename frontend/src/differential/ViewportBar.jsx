import React from 'react';
import { ZoomIn, ZoomOut, Maximize2, Hand } from 'lucide-react';

/**
 * The viewport bar — how the curator moves through the image, and nothing else.
 *
 * Deliberately small and deliberately separate from the instrument controls
 * beside it. Zoom changes ACCESS to pixels; brush size changes the extent of
 * authored evidence. Putting them in one cluster would invite the reading that
 * zooming in paints finer, which is precisely the confusion the workbench must
 * not create — the same brush at 4× covers the same anatomical extent, and only
 * looks bigger because the image does.
 *
 * The percentage is a live region so a screen reader hears the destination, but
 * it is `polite` and rendered from settled state rather than from each wheel
 * notch, so a continuous gesture does not flood the queue.
 */
export default function ViewportBar({
    label, atFit, canZoomIn, canZoomOut,
    onZoomIn, onZoomOut, onFit, onNatural, naturalAvailable,
    handTool, onToggleHand,
}) {
    return (
        <div className="diff-viewport-bar" role="group" aria-label="Image view">
            <button type="button" className="diff-vp-btn" onClick={onZoomOut}
                disabled={!canZoomOut} aria-label="Zoom out" title="Zoom out (−)">
                <ZoomOut size={14} />
            </button>

            {/* The current zoom, named the way the curator thinks of it: "Fit" is a
                place, not 100%. */}
            <span className="diff-vp-scale" aria-live="polite" aria-atomic="true">
                <span className="diff-vp-sr">Zoom: </span>{label}
            </span>

            <button type="button" className="diff-vp-btn" onClick={onZoomIn}
                disabled={!canZoomIn} aria-label="Zoom in" title="Zoom in (+)">
                <ZoomIn size={14} />
            </button>

            <button type="button" className={`diff-vp-text${atFit ? ' on' : ''}`}
                onClick={onFit} disabled={atFit}
                aria-label="Fit the whole image" title="Fit the whole image (0)">
                Fit
            </button>

            {/* Offered only when 1:1 is a real destination — an image already past
                natural size at fit has no honest "100%" to go to. */}
            {naturalAvailable && (
                <button type="button" className="diff-vp-text" onClick={onNatural}
                    aria-label="Zoom to natural pixel size" title="Actual pixels (1)">
                    100%
                </button>
            )}

            {/* The pan affordance for anyone without a middle button or a trackpad.
                Space is faster once known; this is how it becomes known. */}
            <button type="button" className={`diff-vp-btn${handTool ? ' on' : ''}`}
                onClick={onToggleHand} aria-pressed={handTool}
                aria-label="Hand tool — drag to pan"
                title="Hand tool (H) — or hold Space to pan without leaving your tool">
                <Hand size={14} />
            </button>

            <span className="diff-vp-hint" aria-hidden="true">
                <Maximize2 size={11} /> ⌘/Ctrl + scroll · Space-drag pans
            </span>
        </div>
    );
}
