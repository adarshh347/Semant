// PERCEPTUAL-ORGANS-002 Lane E — the synthetic scenes the laboratory can be opened against.
//
// The master plan's rehearsal asks for "simple synthetic containment/contact/overlap/disjoint
// controls" before any live adapter is trusted, and the frontend needs them for a reason of its
// own: a person cannot tell whether a mask is ALIGNED unless they already know where the shape
// is. On a photograph, a mask drifted by two per cent looks like a mask. On a scene where the
// square's edge is at exactly x=0.15, it looks like a bug.
//
// ONE SOURCE, TWO RENDERINGS. Each scene is a list of normalized shapes. The image is an SVG data
// URI drawn from that list; the mask rasters are rasterized from the SAME list. So if the overlay
// and the picture disagree, the disagreement is in the stage geometry — which is the only thing
// these scenes are trying to test. Nothing here is traced by hand.
//
// The image is a data URI so the harness needs no network, no fixture binaries in the repo, and
// no `photo_url` that only resolves against a running backend.
//
// Lane F replaces these with real posts. The shapes of the records do not change.
//
// PURE MODULE.

import { emptyRaster } from '../geometry/maskRaster';

/** Rasterize one normalized shape at (h × w). Pixel centres, so edges land where they read. */
export function rasterizeShape(shape, h, w) {
    const m = emptyRaster(h, w);
    for (let r = 0; r < h; r++) {
        for (let c = 0; c < w; c++) {
            const x = (c + 0.5) / w;
            const y = (r + 0.5) / h;
            let inside = false;
            if (shape.kind === 'rect') {
                inside = x >= shape.x && x < shape.x + shape.w
                    && y >= shape.y && y < shape.y + shape.h;
            } else if (shape.kind === 'disc') {
                const cx = shape.x + shape.w / 2;
                const cy = shape.y + shape.h / 2;
                const dx = (x - cx) / (shape.w / 2);
                const dy = (y - cy) / (shape.h / 2);
                inside = dx * dx + dy * dy <= 1;
            } else if (shape.kind === 'frame') {
                const outer = x >= shape.x && x < shape.x + shape.w
                    && y >= shape.y && y < shape.y + shape.h;
                const t = shape.thickness ?? 0.05;
                const inner = x >= shape.x + t && x < shape.x + shape.w - t
                    && y >= shape.y + t && y < shape.y + shape.h - t;
                inside = outer && !inner;
            }
            if (inside) m.data[r * w + c] = 1;
        }
    }
    return m;
}

const svgShape = (s) => {
    const pct = (v) => `${(v * 100).toFixed(4)}%`;
    if (s.kind === 'disc') {
        return `<ellipse cx="${pct(s.x + s.w / 2)}" cy="${pct(s.y + s.h / 2)}" `
            + `rx="${pct(s.w / 2)}" ry="${pct(s.h / 2)}" fill="${s.fill}" />`;
    }
    if (s.kind === 'frame') {
        const t = s.thickness ?? 0.05;
        return `<path fill="${s.fill}" fill-rule="evenodd" d="`
            + `M${pct(s.x)} ${pct(s.y)} H${pct(s.x + s.w)} V${pct(s.y + s.h)} H${pct(s.x)} Z `
            + `M${pct(s.x + t)} ${pct(s.y + t)} H${pct(s.x + s.w - t)} `
            + `V${pct(s.y + s.h - t)} H${pct(s.x + t)} Z" />`;
    }
    return `<rect x="${pct(s.x)}" y="${pct(s.y)}" width="${pct(s.w)}" height="${pct(s.h)}" `
        + `fill="${s.fill}" />`;
};

/** The scene as an `<img src>` — deterministic, offline, and the same geometry as the rasters. */
export function sceneImageUri(scene) {
    const body = scene.shapes.map(svgShape).join('');
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${scene.natural_width}" `
        + `height="${scene.natural_height}" viewBox="0 0 ${scene.natural_width} `
        + `${scene.natural_height}"><rect width="100%" height="100%" fill="${scene.ground}"/>`
        + `${body}</svg>`;
    return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

// ── the scenes ──────────────────────────────────────────────────────────────
//
// `mask_h`/`mask_w` are deliberately COARSER than the image on the controls scene. A mask raster
// that is not the image raster is the ordinary case for a real segmenter, and the inspector says
// so; building every fixture at image resolution would hide a whole class of alignment error.

export const SCENES = [
    {
        id: 'scene_controls',
        title: 'Synthetic controls',
        note: 'Containment, contact, overlap and clearance, at coordinates you can check by eye.',
        origin: 'fixture',
        image_digest: 'sha256:fixture_controls_v1',
        natural_width: 800,
        natural_height: 600,
        mask_h: 120,
        mask_w: 160,
        ground: '#F3EEF1',
        shapes: [
            { id: 'outer', label: 'outer field', kind: 'rect', x: 0.05, y: 0.10, w: 0.34, h: 0.52, fill: '#CCD3DE' },
            { id: 'inner', label: 'inner square', kind: 'rect', x: 0.14, y: 0.24, w: 0.14, h: 0.22, fill: '#4E5586' },
            { id: 'bar_left', label: 'left bar', kind: 'rect', x: 0.46, y: 0.14, w: 0.14, h: 0.30, fill: '#8E3F6A' },
            { id: 'bar_right', label: 'right bar', kind: 'rect', x: 0.60, y: 0.14, w: 0.14, h: 0.30, fill: '#A66273' },
            { id: 'disc_a', label: 'left disc', kind: 'disc', x: 0.44, y: 0.54, w: 0.22, h: 0.30, fill: '#6B5391' },
            { id: 'disc_b', label: 'right disc', kind: 'disc', x: 0.56, y: 0.54, w: 0.22, h: 0.30, fill: '#8E82A0' },
            { id: 'far_dot', label: 'far dot', kind: 'disc', x: 0.86, y: 0.76, w: 0.08, h: 0.11, fill: '#7B2D6B' },
        ],
    },
    {
        id: 'scene_instances',
        title: 'Multi-instance',
        note: 'Five separable instances, two of them near-duplicates — the repeat/duplicate case.',
        origin: 'fixture',
        image_digest: 'sha256:fixture_instances_v1',
        natural_width: 900,
        natural_height: 600,
        mask_h: 100,
        mask_w: 150,
        ground: '#FAF7F5',
        shapes: [
            { id: 'figure_1', label: 'head', kind: 'disc', x: 0.06, y: 0.18, w: 0.16, h: 0.24, fill: '#5E2B50' },
            { id: 'figure_2', label: 'head', kind: 'disc', x: 0.26, y: 0.20, w: 0.16, h: 0.24, fill: '#7B2D6B' },
            { id: 'figure_3', label: 'drapery', kind: 'rect', x: 0.48, y: 0.16, w: 0.12, h: 0.34, fill: '#4E5586' },
            { id: 'figure_4', label: 'drapery', kind: 'rect', x: 0.50, y: 0.18, w: 0.12, h: 0.34, fill: '#6B5391' },
            { id: 'figure_5', label: 'window frame', kind: 'frame', x: 0.72, y: 0.30, w: 0.22, h: 0.42, thickness: 0.04, fill: '#8E3F6A' },
        ],
    },
    {
        id: 'scene_absent',
        title: 'Absent-concept control',
        note: 'A plain ground. Asking for a face here must come back empty, never unavailable.',
        origin: 'fixture',
        image_digest: 'sha256:fixture_absent_v1',
        natural_width: 640,
        natural_height: 480,
        mask_h: 96,
        mask_w: 128,
        ground: '#ECE4EA',
        shapes: [],
    },
];

export const sceneById = (id) => SCENES.find((s) => s.id === id) || null;

/** Every shape of a scene, rasterized once, keyed by shape id. */
export function sceneRasters(scene) {
    const out = {};
    for (const s of scene.shapes) out[s.id] = rasterizeShape(s, scene.mask_h, scene.mask_w);
    return out;
}

/** The `source` block of a `LabSession`, as the contract declares it. */
export function sceneSource(scene) {
    return {
        origin: scene.origin,
        post_id: null,
        image_digest: scene.image_digest,
        natural_width: scene.natural_width,
        natural_height: scene.natural_height,
    };
}

/** What the source picker lists. `photo_url` is the data URI, so it needs no server. */
export function sceneAsSource(scene) {
    return {
        id: scene.id,
        title: scene.title,
        note: scene.note,
        photo_url: sceneImageUri(scene),
        image_digest: scene.image_digest,
        natural_width: scene.natural_width,
        natural_height: scene.natural_height,
        origin: scene.origin,
        instance_count: scene.shapes.length,
    };
}
