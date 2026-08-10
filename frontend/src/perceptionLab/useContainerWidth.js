// PERCEPTUAL-ORGANS-002 Lane E — the lab responds to its container, not to the window.
//
// Lane F mounts this at a route, and a route may itself sit inside a pane. A layout keyed to the
// viewport would be correct exactly once, on a full-width page, and wrong the first time anybody
// put it beside anything — which is the failure `RegionSurfaceLab` was built to catch for the
// region surface, so this lane inherits the technique rather than rediscovering it.
//
// The bands are the widths the build asks to be tested at, and they are a PURE FUNCTION so the
// responsive suite can assert the boundaries without a browser:
//
//     ≥ 1000   wide     rail · stage · inspector, three columns
//     ≥  680   mid      rail · stage, inspector below
//     ≥  400   narrow   one column, stacked in reading order
//     <  400   tight    one column, tighter gaps
//
// Measured from the element itself on every resize AND on window resize, because a container
// query cannot set an attribute and the layout needs one to reorder without duplicating markup.

import { useCallback, useEffect, useState } from 'react';

export const WIDTH_BANDS = Object.freeze([
    { band: 'wide', min: 1000 },
    { band: 'mid', min: 680 },
    { band: 'narrow', min: 400 },
    { band: 'tight', min: 0 },
]);

/** The band for a width in CSS pixels. `null` and 0 are `tight`: unknown is not wide. */
export function widthBand(px) {
    const w = Number.isFinite(px) ? px : 0;
    return (WIDTH_BANDS.find((b) => w >= b.min) || WIDTH_BANDS[WIDTH_BANDS.length - 1]).band;
}

/** The four widths the build names, for the harness and for the tests. */
export const TARGET_WIDTHS = Object.freeze([1100, 720, 430, 320]);

export default function useContainerWidth(ref) {
    const [width, setWidth] = useState(null);

    const measure = useCallback(() => {
        const el = ref.current;
        if (!el) return;
        const w = el.getBoundingClientRect().width;
        setWidth((prev) => (prev === w ? prev : w));
    }, [ref]);

    useEffect(() => {
        measure();
        const el = ref.current;
        let ro = null;
        if (el && typeof ResizeObserver !== 'undefined') {
            ro = new ResizeObserver(measure);
            ro.observe(el);
        }
        window.addEventListener('resize', measure);
        return () => {
            if (ro) ro.disconnect();
            window.removeEventListener('resize', measure);
        };
    }, [measure, ref]);

    return { width, band: widthBand(width), measure };
}
