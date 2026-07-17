import { useCallback, useEffect, useState } from 'react';

/**
 * The stage-geometry contract (Differential v1 · extracted from RegionSurface).
 *
 * One coordinate system, three renderers:
 *
 *   - the <img> letterboxes inside the stage via `object-fit: contain`;
 *   - the SVG overlay carries the image's NATURAL pixel viewBox and letterboxes
 *     identically via `preserveAspectRatio="xMidYMid meet"` — so shapes cannot drift;
 *   - HTML (labels, dots) and the canvas layer need the rendered content box in CSS
 *     pixels — that is what this hook measures.
 *
 * All stored geometry is normalized (0..1, top-left origin, natural-image space).
 * The two converters below are the ONLY sanctioned pointer↔normalized paths; a
 * surface that reimplements the letterbox math is how "the earrings land on a
 * cheekbone" happens again.
 *
 * Later deep-zoom swaps the container, not this contract.
 */

/** Where the contain-fitted image actually sits inside a stage of (sw × sh). */
export function contentBox(sw, sh, naturalW, naturalH) {
    if (!sw || !sh || !naturalW || !naturalH) return null;
    const scale = Math.min(sw / naturalW, sh / naturalH);
    const w = naturalW * scale;
    const h = naturalH * scale;
    return { x: (sw - w) / 2, y: (sh - h) / 2, w, h };
}

/**
 * Pointer event → normalized image coords, clamped to [0,1].
 * Returns null when geometry isn't ready. Pass `clamp: false` to detect
 * out-of-image pointers instead (returns unclamped coords).
 */
export function pointerToNormalized(e, stageEl, content, { clamp = true } = {}) {
    if (!stageEl || !content) return null;
    const box = stageEl.getBoundingClientRect();
    const x = (e.clientX - box.left - content.x) / content.w;
    const y = (e.clientY - box.top - content.y) / content.h;
    if (!clamp) return { x, y };
    return { x: Math.min(1, Math.max(0, x)), y: Math.min(1, Math.max(0, y)) };
}

/** Normalized image coords → CSS-pixel position inside the stage. */
export function normalizedToStage(pt, content) {
    if (!pt || !content) return null;
    return { left: content.x + pt.x * content.w, top: content.y + pt.y * content.h };
}

/** Track an <img>'s natural pixel size: `const [natural, onImgLoad] = useNaturalSize()`. */
export function useNaturalSize() {
    const [natural, setNatural] = useState(null);
    const onImgLoad = useCallback((e) => {
        setNatural({ w: e.target.naturalWidth, h: e.target.naturalHeight });
    }, []);
    return [natural, onImgLoad];
}

/**
 * Measure the letterboxed content box of a contain-fitted image inside stageRef,
 * re-measuring on any stage resize (pane drag, container query, window).
 */
export default function useStageGeometry(stageRef, natural) {
    const [content, setContent] = useState(null);

    const measure = useCallback(() => {
        const stage = stageRef.current;
        if (!stage || !natural) return;
        const { width: sw, height: sh } = stage.getBoundingClientRect();
        const box = contentBox(sw, sh, natural.w, natural.h);
        if (box) setContent(box);
    }, [stageRef, natural]);

    useEffect(() => {
        measure();
        const stage = stageRef.current;
        if (!stage) return undefined;
        const ro = new ResizeObserver(measure);
        ro.observe(stage);
        return () => ro.disconnect();
    }, [measure, stageRef]);

    return { content, measure };
}
