import React, { useEffect, useRef, useState } from 'react';
import RegionOverlay from '../components/RegionOverlay.jsx';
import FlowFieldLayer from '../differential/FlowFieldLayer.jsx';
import { paintFields } from '../differential/fieldCanvas.js';

/**
 * CIRCUIT-003 M4 — one LIVE percept, embedded in the article by reference.
 *
 * The whole point of the artifact: the figure beside a sentence is the ACTUAL geometry that was
 * produced, drawn on the actual source image, through the SAME renderers the Differential uses.
 * Not a screenshot. A screenshot would be a picture of evidence rather than the evidence, it
 * would go stale the moment anything was re-run, and nothing in the document would say so.
 *
 * ALIGNMENT IS INHERITED, NOT REIMPLEMENTED. `RegionOverlay` and `FlowFieldLayer` both declare
 * `viewBox="0 0 natural.w natural.h"` with `preserveAspectRatio="xMidYMid meet"`, which letterboxes
 * exactly as `object-fit: contain` letterboxes the image beneath. Both sit in the same box here,
 * so the overlay tracks the image at this figure's size for the same reason it tracks it at full
 * stage size. Writing a second alignment path for a small canvas is how the two drift apart — and
 * a percept drawn 20px off in an article is a claim about a part of the picture nobody measured.
 *
 * A percept that did NOT resolve renders as an honest placeholder, never as an empty frame: an
 * article whose figures silently vanish reads as an article with fewer claims.
 */
/**
 * The letterboxed CONTENT box of a `contain`-fitted image inside its stage.
 *
 * The field painter works in normalized (0..1) IMAGE coordinates, so it has to be given the rect
 * the image actually occupies — not the stage. Painting across the stage instead stretches the
 * wash by the difference between the two aspects, which is the same drift that put FindSimilar's
 * overlay ~129px off its image. The SVG renderers get this for free from
 * `preserveAspectRatio="xMidYMid meet"`; a canvas has no such declaration and must be told.
 */
export function containBox(stage, natural) {
    if (!stage || !natural || !stage.w || !stage.h || !natural.w || !natural.h) return null;
    const stageAspect = stage.w / stage.h;
    const imageAspect = natural.w / natural.h;
    if (stageAspect > imageAspect) {           // pillarboxed — bars left and right
        const h = stage.h;
        const w = h * imageAspect;
        return { x: (stage.w - w) / 2, y: 0, w, h };
    }
    const w = stage.w;                          // letterboxed — bars top and bottom
    const h = w / imageAspect;
    return { x: 0, y: (stage.h - h) / 2, w, h };
}

export default function PerceptFigure({ citation, onReopen = null }) {
    const canvasRef = useRef(null);
    const stageRef = useRef(null);
    const [natural, setNatural] = useState(null);
    const [stage, setStage] = useState(null);
    const geometry = citation?.geometry || null;
    const kind = citation?.geometryKind || geometry?.kind || '';

    // The stage's own size, remeasured on resize — the article is a fluid column, so the figure
    // is not one fixed size and a box measured once would drift the moment the window changed.
    useEffect(() => {
        const el = stageRef.current;
        if (!el || typeof ResizeObserver === 'undefined') return undefined;
        const measure = () => {
            const r = el.getBoundingClientRect();
            if (r.width && r.height) setStage({ w: r.width, h: r.height });
        };
        measure();
        const ro = new ResizeObserver(measure);
        ro.observe(el);
        return () => ro.disconnect();
    }, []);

    // Soft-field washes are a canvas layer, exactly as in GroundLayers — same painter, same
    // stroke shape (`{points, radius, strength, op}` in normalized image space), so a field looks
    // the same in the article as it does in the workspace.
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const box = containBox(stage, natural);
        const strokes = geometry?.strokes;
        if (!box || !Array.isArray(strokes) || !strokes.length) {
            const ctx = canvas.getContext && canvas.getContext('2d');
            if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
            return;
        }
        // Position the canvas ON the image, not on the stage.
        canvas.style.left = `${box.x}px`;
        canvas.style.top = `${box.y}px`;
        canvas.style.width = `${box.w}px`;
        canvas.style.height = `${box.h}px`;
        paintFields(canvas, [{ ground: { strokes }, alpha: 1, progress: 1 }], box);
    }, [geometry, natural, stage]);

    if (!citation) return null;

    const drawable = citation.drawable && geometry;
    const target = citation.reopen;

    const onImageLoad = (e) => {
        const img = e.currentTarget;
        if (img.naturalWidth && img.naturalHeight) {
            setNatural({ w: img.naturalWidth, h: img.naturalHeight });
        }
    };

    const body = (
        <div className="art-figure-stage" ref={stageRef} data-geometry-kind={kind || 'none'}>
            {citation.imageRef ? (
                <img className="art-figure-img" src={citation.imageRef}
                    alt={citation.imageTitle || citation.image || ''} onLoad={onImageLoad} />
            ) : (
                <div className="art-figure-noimg">source image unavailable</div>
            )}

            {/* the soft-field wash — brush_field percepts (rhythm, pressure_zone, …).
                Sized and positioned onto the letterboxed image box by the effect above. */}
            <canvas ref={canvasRef} className="art-figure-canvas" aria-hidden="true" />

            {/* a dense direction field has its own renderer */}
            {drawable && kind === 'flow_field' && natural && (
                <FlowFieldLayer mark={{ geometry }} natural={natural} />
            )}

            {/* an extent — a region or a mask — through the one overlay that draws shapes */}
            {drawable && natural && (kind === 'region_ref' || kind === 'mask' || geometry.box) && (
                <RegionOverlay
                    natural={natural}
                    regions={[{ id: citation.step_id, box: geometry.box, mask: geometry.mask }]}
                    viewMap="focus" interactive={false} className="art-figure-svg" />
            )}
        </div>
    );

    return (
        <figure className={`art-figure${drawable ? '' : ' is-unresolved'}`}
            data-step-id={citation.step_id} data-status={citation.status}>
            {drawable && target ? (
                <button type="button" className="art-figure-open"
                    onClick={() => onReopen && onReopen(citation)}
                    title={`Open ${citation.imageTitle || citation.image} with this percept`}>
                    {body}
                    <span className="art-figure-openhint">open on source →</span>
                </button>
            ) : body}

            {!drawable && (
                // Never an empty frame. An article whose figures silently vanish reads as an
                // article with fewer claims than it actually made.
                <div className="art-figure-missing" role="note">
                    <strong>{citation.actuator}</strong>{' '}
                    {citation.status === 'ambiguous'
                        ? 'could not be shown: which percept this cites cannot be settled.'
                        : 'produced no percept to show.'}
                    {citation.detail ? <span className="art-figure-why"> {citation.detail}</span> : null}
                </div>
            )}

            <figcaption className="art-figure-cap">
                <span className={`art-fn is-${citation.function}`}>{citation.function}</span>
                <span className="art-figure-what">
                    {citation.label || citation.actuator}
                    {citation.imageTitle ? <em> · {citation.imageTitle}</em> : null}
                </span>
                {/* M5's chip contract exactly: same classes, same data attribute, so its
                    stylesheet takes over verbatim when the two branches meet. */}
                <span className={`diff-chip diff-epistemic-chip is-${citation.epistemic}`}
                    data-epistemic={citation.epistemic}>
                    {citation.epistemic}
                </span>
                {citation.attribution ? (
                    <span className="art-figure-attrib">— {citation.attribution}</span>
                ) : null}
            </figcaption>
        </figure>
    );
}
