/**
 * Shared fixture for the three P2D-B spikes.
 *
 * Deliberately identical across Spike 1 (Konva) and Spike 2 (SVG handles): the
 * comparison is only worth something if both renderers are handed the same
 * marks, the same layers, and the same suggestion to accept.
 *
 * All geometry is normalized 0..1 in natural-image space — the
 * `useStageGeometry` contract, which no spike is permitted to reimplement.
 */

import {
    makeBrushField, makeTraceMark, makeRelationMark, makeVisualLayer, makeAnchor,
    _resetSpikeIds,
} from './visualMarkContract';

/** A stroke shaped like the corpus's heaviest real one (OH §1.10: 1194 points). */
export function synthesizeHeavyStroke(n = 1194, { seed = 7 } = {}) {
    // Deterministic pseudo-random — a spike that renders differently on each
    // reload cannot be compared against itself across a resize.
    let s = seed;
    const rnd = () => {
        s = (s * 1664525 + 1013904223) % 4294967296;
        return s / 4294967296;
    };
    const points = [];
    for (let i = 0; i < n; i++) {
        const t = i / (n - 1);
        // A long looping gesture across the frame, with hand tremor — the shape
        // a real brush drag has, not a smooth analytic curve.
        const x = 0.12 + 0.76 * t + 0.05 * Math.sin(t * 11.3) + (rnd() - 0.5) * 0.004;
        const y = 0.5 + 0.3 * Math.sin(t * 6.2) * Math.cos(t * 2.1) + (rnd() - 0.5) * 0.004;
        // Pressure: rises, holds, releases — what a stylus actually reports.
        const p = Math.min(1, Math.max(0.05, Math.sin(t * Math.PI) ** 0.6 + (rnd() - 0.5) * 0.08));
        points.push([
            Math.min(1, Math.max(0, x)),
            Math.min(1, Math.max(0, y)),
            p,
        ]);
    }
    return { points, radius: 0.05, strength: 0.85, op: 'add' };
}

/** The four layers the brief asks each spike to demonstrate (OH §4.5). */
export function fixtureLayers() {
    return [
        makeVisualLayer({ name: 'Evidence', layer_type: 'evidence', order: 0 }),
        makeVisualLayer({ name: 'Suggestions', layer_type: 'suggestion', order: 1, opacity: 1 }),
        makeVisualLayer({ name: 'Recall', layer_type: 'recall', order: 2, provenance: { created_by: 'system', action_id: null } }),
        makeVisualLayer({ name: 'Scratch', layer_type: 'scratch', order: 3, opacity: 0.8 }),
    ];
}

/** Points for a short hand-drawn brush stroke (light on the left cheek). */
const LIGHT_STROKE = [
    [0.28, 0.30, 0.4], [0.31, 0.33, 0.7], [0.34, 0.37, 0.9], [0.36, 0.42, 1.0],
    [0.37, 0.47, 0.9], [0.36, 0.52, 0.7], [0.34, 0.56, 0.4],
];
const SHADOW_STROKE = [
    [0.62, 0.34, 0.3], [0.66, 0.38, 0.6], [0.69, 0.44, 0.9], [0.70, 0.51, 1.0],
    [0.69, 0.58, 0.8], [0.66, 0.63, 0.5], [0.62, 0.66, 0.3],
];

/**
 * The fixture workspace. Returns `{ layers, marks }` in contract shape.
 *
 * `heavy: true` swaps the light field for the 1194-point stroke — that is the
 * perf case, and it is off by default so the interaction spikes stay readable.
 */
export function fixtureWorkspace({ heavy = false } = {}) {
    _resetSpikeIds();
    const layers = fixtureLayers();
    const [evidence, suggestion, , scratch] = layers;

    const light = makeBrushField({
        role: 'light_field',
        label: 'light falling across the brow',
        status: 'committed',
        layer_id: evidence.id,
        geometry: {
            kind: 'freehand_path',
            strokes: [heavy
                ? synthesizeHeavyStroke()
                : { points: LIGHT_STROKE, radius: 0.055, strength: 0.85, op: 'add' }],
        },
        style: { color: '#E8C07A', opacity: 0.3, softness: 0.75, width: 0.055 },
    });

    const shadow = makeBrushField({
        role: 'shadow_field',
        label: 'the shadow it is held against',
        status: 'committed',
        layer_id: evidence.id,
        geometry: {
            kind: 'freehand_path',
            strokes: [{ points: SHADOW_STROKE, radius: 0.06, strength: 0.9, op: 'add' }],
        },
        style: { color: '#3B2E4A', opacity: 0.3, softness: 0.8, width: 0.06 },
    });

    const fold = makeBrushField({
        role: 'fold',
        label: 'the fold at the jaw',
        status: 'committed',
        layer_id: scratch.id,
        geometry: {
            kind: 'freehand_path',
            strokes: [{ points: [[0.44, 0.62, 0.5], [0.49, 0.66, 0.9], [0.55, 0.68, 0.5]], radius: 0.03, strength: 0.9, op: 'add' }],
        },
        style: { color: '#8C6A4F', opacity: 0.28, softness: 0.4, width: 0.03 },
    });

    // The trace whose endpoints the spike drags — test #3, the real question.
    const gaze = makeTraceMark({
        role: 'gaze_address',
        label: 'the gaze, leaving the frame',
        status: 'committed',
        layer_id: evidence.id,
        geometry: { kind: 'polyline', points: [[0.40, 0.36], [0.55, 0.32], [0.72, 0.27], [0.88, 0.20]] },
        anchors: { from: makeAnchor('point', null, [0.40, 0.36]), to: makeAnchor('point', null, [0.88, 0.20]) },
        // The gaze leaves the frame — it has no determinate terminus, and the
        // model must be able to say so rather than draw a sharp arrowhead at a
        // target the curator never claimed.
        ambiguous: true,
        arrow: { head: 'open', at: 'end' },
        style: { color: '#D8DCE3', opacity: 1, softness: 0, width: 0.005 },
    });

    const axis = makeTraceMark({
        role: 'architectural_axis',
        label: 'the vertical the head sits on',
        status: 'committed',
        layer_id: evidence.id,
        geometry: { kind: 'polyline', points: [[0.50, 0.12], [0.50, 0.86]] },
        anchors: { from: null, to: null },
        arrow: { head: 'none', at: 'end' },
        style: { color: '#9FB4C7', opacity: 1, softness: 0, width: 0.004 },
    });

    // Derived geometry only — the connector is computed from the two brush
    // fields' centres, never stored (OH §4.4).
    const held = makeRelationMark({
        role: 'contrast',
        label: 'held against',
        reason: 'the light is only legible because the shadow refuses it',
        status: 'committed',
        layer_id: evidence.id,
        source_refs: [{ kind: 'mark', ref: light.id }],
        target_refs: [{ kind: 'mark', ref: shadow.id }],
        style: { color: '#C08457', opacity: 0.7, softness: 0, width: 0.003 },
    });

    // The quarantined proposal. `status: 'staged'` — never `committed`; the
    // contract validator refuses a committed model_suggested mark outright.
    const proposed = makeBrushField({
        role: 'gaze_field',
        label: 'a gaze field the planner proposes',
        source: 'model_suggested',
        status: 'staged',
        layer_id: suggestion.id,
        suggested_by: 'act_spike_0001',
        geometry: {
            kind: 'freehand_path',
            strokes: [{ points: [[0.55, 0.22, 0.6], [0.66, 0.24, 0.9], [0.76, 0.29, 0.6], [0.83, 0.36, 0.3]], radius: 0.07, strength: 0.7, op: 'add' }],
        },
        style: { color: '#7FB3A8', opacity: 0.24, softness: 0.9, width: 0.07 },
        provenance: {
            planner: 'spike-fixture', prompt_excerpt: 'where is the eye asked to go?',
            matched: ['gaze'], model: 'fixture', run_id: null,
        },
    });

    return { layers, marks: [light, shadow, fold, gaze, axis, held, proposed] };
}

/** Centre of a mark in normalized coords — injected into `relationNodes`. */
export function markCenter(marks) {
    return (ref) => {
        const m = marks.find((x) => x.id === ref.ref);
        if (!m) return null;
        const g = m.geometry;
        let pts = [];
        if (g.kind === 'freehand_path') pts = (g.strokes || []).flatMap((s) => s.points || []);
        else if (g.kind === 'polyline' || g.kind === 'curve') pts = g.points || [];
        else if (g.kind === 'vector') pts = [g.from, g.to];
        if (!pts.length) return null;
        let sx = 0, sy = 0;
        for (const p of pts) { sx += p[0]; sy += p[1]; }
        return [sx / pts.length, sy / pts.length];
    };
}

/**
 * A base image for the spikes. Data-URI so the spike needs no backend, no
 * network and no fixture asset — and so `server-exit-144` cannot block it.
 * A 3:2 gradient with a few landmarks, drawn at load into an offscreen canvas.
 */
export function makeSpikeImage(w = 900, h = 600) {
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    const ctx = c.getContext('2d');
    const g = ctx.createLinearGradient(0, 0, w, h);
    g.addColorStop(0, '#2A2622'); g.addColorStop(0.5, '#6B5A4A'); g.addColorStop(1, '#1A1714');
    ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
    // Landmarks at known NORMALIZED positions, so coordinate parity between the
    // two spikes is verifiable by eye and not only by assertion.
    ctx.strokeStyle = 'rgba(255,255,255,0.22)'; ctx.lineWidth = 1;
    for (const t of [0.25, 0.5, 0.75]) {
        ctx.beginPath(); ctx.moveTo(t * w, 0); ctx.lineTo(t * w, h); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(0, t * h); ctx.lineTo(w, t * h); ctx.stroke();
    }
    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    for (const [x, y] of [[0.25, 0.25], [0.5, 0.5], [0.75, 0.75]]) {
        ctx.beginPath(); ctx.arc(x * w, y * h, 5, 0, Math.PI * 2); ctx.fill();
    }
    ctx.fillStyle = 'rgba(232,192,122,0.35)';
    ctx.beginPath(); ctx.ellipse(0.33 * w, 0.42 * h, 0.12 * w, 0.2 * h, -0.3, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = 'rgba(30,24,36,0.5)';
    ctx.beginPath(); ctx.ellipse(0.67 * w, 0.5 * h, 0.1 * w, 0.22 * h, 0.3, 0, Math.PI * 2); ctx.fill();
    return c.toDataURL('image/png');
}
