import { describe, it, expect } from 'vitest';
import {
    perfectFreehandRibbon, freehandOutline, outlineToPath, outlineVertexCount, pfOptions,
} from './freehandStroke';
import { taperedRibbon } from './freehandTaper';

const NAT = { w: 3024, h: 4032 };

// A synthetic stand-in for the corpus's heaviest real stroke (OH §1.10: 1194 pts).
function heavyStroke(n = 1194, seed = 7) {
    let s = seed;
    const rnd = () => { s = (s * 1664525 + 1013904223) % 4294967296; return s / 4294967296; };
    const pts = [];
    for (let i = 0; i < n; i++) {
        const t = i / (n - 1);
        const x = 0.12 + 0.76 * t + 0.05 * Math.sin(t * 11.3) + (rnd() - 0.5) * 0.004;
        const y = 0.5 + 0.3 * Math.sin(t * 6.2) * Math.cos(t * 2.1) + (rnd() - 0.5) * 0.004;
        const p = Math.min(1, Math.max(0.05, Math.sin(t * Math.PI) ** 0.6 + (rnd() - 0.5) * 0.08));
        pts.push([Math.min(1, Math.max(0, x)) * NAT.w, Math.min(1, Math.max(0, y)) * NAT.h, p]);
    }
    return pts;
}

describe('perfect-freehand ribbon is a drop-in for taperedRibbon', () => {
    it('returns a closed SVG path string, empty for <1 point', () => {
        expect(perfectFreehandRibbon([])).toBe('');
        const d = perfectFreehandRibbon([[100, 100, 0.5], [200, 150, 0.9], [300, 120, 0.4]], { maxWidth: 20 });
        expect(typeof d).toBe('string');
        expect(d.endsWith('Z')).toBe(true);
        expect(d.startsWith('M')).toBe(true);
    });

    it('output is plain data — arrays of finite numbers, no renderer object', () => {
        const outline = freehandOutline([[10, 10, 0.5], [50, 50, 0.9]], { maxWidth: 8 });
        expect(Array.isArray(outline)).toBe(true);
        expect(outline.every((p) => Array.isArray(p) && p.every((n) => Number.isFinite(n)))).toBe(true);
    });

    it('honours real pressure (does not fabricate it)', () => {
        expect(pfOptions(10).simulatePressure).toBe(false);
    });

    it('responds to pressure: flattening pressure moves the outline', () => {
        const px = heavyStroke();
        const withP = freehandOutline(px, { maxWidth: 0.02 * NAT.w });
        const flat = freehandOutline(px.map(([x, y]) => [x, y, 0.5]), { maxWidth: 0.02 * NAT.w });
        const n = Math.min(withP.length, flat.length);
        let shift = 0;
        for (let i = 0; i < n; i++) shift += Math.hypot(withP[i][0] - flat[i][0], withP[i][1] - flat[i][1]);
        expect(shift / n).toBeGreaterThan(0);
    });

    it('the render-cost finding holds: PF emits many more vertices than taperedRibbon', () => {
        const px = heavyStroke();
        const maxWidth = 0.02 * NAT.w;
        const pfV = outlineVertexCount(freehandOutline(px, { maxWidth }));
        const ftV = (taperedRibbon(px, { maxWidth }).match(/[ML]/g) || []).length;
        expect(pfV).toBeGreaterThan(ftV);            // the documented rollback reason
        // Both cover roughly the same footprint (same gesture).
        const bbox = (pts) => {
            let x0 = Infinity, x1 = -Infinity;
            for (const p of pts) { if (p[0] < x0) x0 = p[0]; if (p[0] > x1) x1 = p[0]; }
            return x1 - x0;
        };
        const pfW = bbox(freehandOutline(px, { maxWidth }));
        expect(pfW).toBeGreaterThan(0.5 * NAT.w);    // spans the frame like the input
        // eslint-disable-next-line no-console
        console.log(`P2E-B PF-vs-FT heavy(1194): PF ${pfV} vtx / ${perfectFreehandRibbon(px, { maxWidth }).length} chars · FT ${ftV} vtx / ${taperedRibbon(px, { maxWidth }).length} chars`);
    });

    it('outlineToPath round-trips vertex count', () => {
        const outline = [[0, 0], [10, 0], [10, 10], [0, 10]];
        const d = outlineToPath(outline);
        expect((d.match(/[ML]/g) || []).length).toBe(outline.length);
    });
});
