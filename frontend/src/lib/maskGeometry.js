/**
 * Mask geometry helpers (Darshan · VISION-BUILD-001 Increment A).
 *
 * A region's canonical identity is a mask; the backend derives normalized `polygons`
 * — a list of rings (outer + holes, and one ring per disconnected component). The
 * frontend draws them as a SINGLE SVG <path> with `fill-rule="evenodd"`, so holes cut
 * out and multiple components render together. Coordinates are natural-image pixels,
 * consumed inside the shared `viewBox = natural, preserveAspectRatio="xMidYMid meet"`
 * contract — identical to `object-fit: contain`, so masks track the image at any stage
 * size or zoom (see useStageGeometry).
 */

/** True when a region carries derived mask polygons (≥1 real ring). */
export function hasMaskPolygons(region) {
    return Array.isArray(region?.polygons)
        && region.polygons.some((ring) => Array.isArray(ring) && ring.length > 2);
}

/**
 * Rings (normalized [x,y], list of rings) → an SVG path `d` in natural-pixel space.
 * Each ring becomes a closed subpath (`M…L…Z`); with fill-rule="evenodd" the inner
 * rings read as holes. Returns '' when there is nothing to draw.
 */
export function ringsToPath(rings, natW, natH) {
    if (!Array.isArray(rings)) return '';
    return rings
        .filter((ring) => Array.isArray(ring) && ring.length > 2)
        .map((ring) => {
            const [x0, y0] = ring[0];
            const head = `M${x0 * natW},${y0 * natH}`;
            const rest = ring.slice(1).map(([x, y]) => `L${x * natW},${y * natH}`).join('');
            return `${head}${rest}Z`;
        })
        .join('');
}
