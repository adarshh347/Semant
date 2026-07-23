import React, { useMemo } from 'react';
import { RegionStoreContext, useRegionState } from '../state/regionStore';
import DifferentialWorkspace from '../differential/DifferentialWorkspace';

/**
 * DEV-ONLY harness for the Differential workspace — CIRCUIT-001 P2E-B verification.
 *
 * The real workspace mounts inside PostDetailPage over a fetched post. This harness
 * mounts it over an OFFLINE fixture post (a data-URI image + a couple of seeded
 * grounds) with a real `useRegionState` store, so the P2E-B mechanics — semantic
 * brush, editable handles, the perfect-freehand toggle, and the suggestion
 * quarantine (via `window.__diffSeedSuggestion()`) — can be exercised without the
 * backend. Not linked from any nav. Reachable at /lab/differential.
 *
 * Autosaves PATCH to an absent backend and fail quietly; local state is the point.
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
        _id: 'lab_p2e_fixture', id: 'lab_p2e_fixture',
        photo_url: photo,
        instagram_handle: 'p2e_fixture',
        domain_profile: { chosen: ['general'] },
        // Seeded grounds so a path is immediately reshapeable (Adjust points / hit-path)
        // and a field is on the canvas. Plain dicts; the store hydrates them.
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
        percepts: [],
    }), [photo]);

    const store = useRegionState(post, () => {});

    return (
        <RegionStoreContext.Provider value={store}>
            <div style={{ position: 'fixed', inset: 0 }}>
                <DifferentialWorkspace post={post} store={store} onExit={() => {}} />
            </div>
        </RegionStoreContext.Provider>
    );
}
