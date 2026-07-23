import React, { useEffect, useMemo, useRef } from 'react';
import { RegionStoreContext, useRegionState } from '../state/regionStore';
import DifferentialWorkspace from '../differential/DifferentialWorkspace';
import { makeVisualMark } from '../differential/visualMarks';
import { quarantineSuggestion } from '../differential/suggestionQuarantine';

/**
 * DEV-ONLY harness for the Differential workspace — CIRCUIT-001 P2E-B / P3-B verification.
 *
 * The real workspace mounts inside PostDetailPage over a fetched post. This harness
 * mounts it over an OFFLINE fixture post (a data-URI image + seeded grounds and a
 * region) with a real `useRegionState` store, so the instrument set — semantic brush
 * + erase, trace (roles / anchors / ambiguity / arrowhead), relation, refine→region_mask,
 * editable handles, the perfect-freehand default, layer controls, and the suggestion
 * quarantine — can be exercised without the backend.
 *
 * The quarantine is seeded here the honest way: this harness is a FIXTURE producer, so
 * it seeds one already-quarantined suggestion straight into the store (the same shape
 * `receiveModelSuggestion` mints from a fixture-source action). There is NO DEV fork
 * inside the production workspace anymore (P3-B Debt 2). Not linked from any nav.
 * Reachable at /lab/differential. Autosaves PATCH to an absent backend and fail quietly.
 */

function fixtureImage(w = 1000, h = 667) {
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    const ctx = c.getContext('2d');
    const g = ctx.createLinearGradient(0, 0, w, h);
    g.addColorStop(0, '#2A2622'); g.addColorStop(0.5, '#6B5A4A'); g.addColorStop(1, '#1A1714');
    ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = 'rgba(255,255,255,0.18)'; ctx.lineWidth = 1;
    for (const t of [0.25, 0.5, 0.75]) {
        ctx.beginPath(); ctx.moveTo(t * w, 0); ctx.lineTo(t * w, h); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(0, t * h); ctx.lineTo(w, t * h); ctx.stroke();
    }
    ctx.fillStyle = 'rgba(232,192,122,0.30)';
    ctx.beginPath(); ctx.ellipse(0.33 * w, 0.45 * h, 0.13 * w, 0.24 * h, -0.3, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = 'rgba(30,24,36,0.45)';
    ctx.beginPath(); ctx.ellipse(0.68 * w, 0.52 * h, 0.11 * w, 0.26 * h, 0.3, 0, Math.PI * 2); ctx.fill();
    return c.toDataURL('image/png');
}

export default function DifferentialLab() {
    const photo = useMemo(() => fixtureImage(), []);
    const post = useMemo(() => ({
        _id: 'lab_p3_fixture', id: 'lab_p3_fixture',
        photo_url: photo,
        instagram_handle: 'p3_fixture',
        domain_profile: { chosen: ['general'] },
        // Seeded grounds so a path is immediately reshapeable (Adjust points / hit-path)
        // and a trace endpoint has something to anchor to. A region so Refine→region_mask
        // is exercisable. Plain dicts; the store hydrates them.
        grounds: [
            {
                id: 'gnd_seed_path', ground_type: 'path', actor: 'creator', detector: null,
                label: 'the gaze, across the frame', instrument_role: 'gaze_address',
                points: [[0.22, 0.62], [0.42, 0.40], [0.62, 0.34], [0.82, 0.22]], arrowhead: true,
            },
            {
                id: 'gnd_seed_boundary', ground_type: 'boundary', actor: 'creator', detector: null,
                label: 'the seam', points: [[0.30, 0.78], [0.50, 0.72], [0.70, 0.80]], band_width: 0.06,
            },
        ],
        regions: [
            { id: 'reg_seed_a', label: 'the lit figure', box: { x: 0.20, y: 0.21, w: 0.26, h: 0.48 } },
            { id: 'reg_seed_b', label: 'the shadowed form', box: { x: 0.57, y: 0.26, w: 0.22, h: 0.52 } },
        ],
        percepts: [],
    }), [photo]);

    const store = useRegionState(post, () => {});

    // Seed a 20-suggestion fixture BATCH so the P4-B review surface (cycle, edit,
    // accept/dismiss, bulk) can be exercised end-to-end — the fixture producer, not a
    // workspace DEV fork. Mix of trace (point-editable) and brush (stroke) families,
    // varied roles, so edit-before-accept and provenance rows are all reachable.
    const seeded = useRef(false);
    useEffect(() => {
        if (seeded.current || !store?.addVisualMark) return;
        seeded.current = true;
        const traceRoles = ['gaze_address', 'gesture', 'fall_of_light', 'movement', 'architectural_axis'];
        const fieldRoles = ['gaze_field', 'light_field', 'shadow_field', 'atmosphere_field', 'pressure_zone'];
        for (let i = 0; i < 20; i++) {
            const isTrace = i % 2 === 0;
            const t = i / 19;
            const y = 0.2 + 0.55 * ((i % 5) / 4);
            const mark = isTrace
                ? makeVisualMark('trace_mark', {
                    role: traceRoles[i % traceRoles.length],
                    label: `proposed line ${i + 1}`, source: 'model_suggested',
                    geometry: { kind: 'polyline', points: [[0.15 + 0.1 * t, y], [0.45 + 0.2 * t, y - 0.05], [0.7, y + 0.05]] },
                    provenance: { planner: 'fixture', model: 'planner-x' },
                })
                : makeVisualMark('brush_field', {
                    role: fieldRoles[i % fieldRoles.length],
                    label: `proposed field ${i + 1}`, source: 'model_suggested',
                    geometry: { kind: 'freehand_path', strokes: [{
                        points: [[0.5 + 0.03 * (i % 4), y, 0.6], [0.58, y + 0.04, 0.9], [0.64, y + 0.1, 0.5]],
                        radius: 0.05, strength: 0.7, op: 'add',
                    }] },
                    provenance: { planner: 'fixture', model: 'planner-x' },
                });
            store.addVisualMark(quarantineSuggestion(mark));
        }
    }, [store]);

    return (
        <RegionStoreContext.Provider value={store}>
            <div style={{ position: 'fixed', inset: 0 }}>
                <DifferentialWorkspace post={post} store={store} onExit={() => {}} />
            </div>
        </RegionStoreContext.Provider>
    );
}
