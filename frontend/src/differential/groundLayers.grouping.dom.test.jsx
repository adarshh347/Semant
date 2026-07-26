import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import GroundLayers from './GroundLayers';

/**
 * CIRCUIT-001 Q-C — GroundLayers partitions committed grounds into one SVG <g> PER LAYER
 * (by producer/role), so masks stop piling onto one flat surface; a hidden layer collapses only
 * its own group, and per-layer opacity flows onto that group. This is the renderer Lane B never
 * built (its Konva-Group binding was rejected in the P2D-B spike).
 */
let container; let root;
async function mount(node) { await act(async () => { root.render(node); }); }
beforeEach(() => { container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container); });
afterEach(async () => { await act(async () => { root.unmount(); }); container.remove(); });

const NAT = { w: 1000, h: 1000 };
const CONTENT = { x: 0, y: 0, w: 1000, h: 1000 };

// two producers: a find_parts region + a trace path
const region = { id: 'g_reg', ground_type: 'region', region_id: 'r1', box: { x: 0.2, y: 0.2, w: 0.4, h: 0.4 } };
const path = { id: 'g_path', ground_type: 'path', points: [[0.2, 0.5], [0.5, 0.5], [0.8, 0.5]] };
const GROUNDS = [region, path];
const REGIONS = [{ id: 'r1', box: { x: 0.2, y: 0.2, w: 0.4, h: 0.4 } }];

describe('GroundLayers — Q-C per-layer grouping', () => {
    it('renders one <g data-layer-key> per producer/role layer', async () => {
        const layers = [
            { key: 'find_parts', visibility: true, opacity: 1 },
            { key: 'trace', visibility: true, opacity: 1 },
        ];
        await mount(<GroundLayers grounds={GROUNDS} regions={REGIONS} natural={NAT} content={CONTENT} layers={layers} />);
        const groups = container.querySelectorAll('.gl-layer[data-layer-key]');
        const keys = [...groups].map((g) => g.getAttribute('data-layer-key'));
        expect(keys).toContain('find_parts');
        expect(keys).toContain('trace');
        // the trace path lives inside the trace group, not loose
        const traceGroup = container.querySelector('.gl-layer[data-layer-key="trace"]');
        expect(traceGroup.querySelector('.gl-path')).not.toBeNull();
    });

    it('hiding a layer collapses only that group to opacity 0', async () => {
        const layers = [
            { key: 'find_parts', visibility: false, opacity: 1 },
            { key: 'trace', visibility: true, opacity: 1 },
        ];
        await mount(<GroundLayers grounds={GROUNDS} regions={REGIONS} natural={NAT} content={CONTENT} layers={layers} />);
        const parts = container.querySelector('.gl-layer[data-layer-key="find_parts"]');
        const trace = container.querySelector('.gl-layer[data-layer-key="trace"]');
        expect(parts.style.opacity).toBe('0');
        expect(trace.style.opacity).toBe('1');   // its neighbour is untouched
    });

    it('per-layer opacity flows onto the group', async () => {
        const layers = [{ key: 'trace', visibility: true, opacity: 0.35 }, { key: 'find_parts', visibility: true, opacity: 1 }];
        await mount(<GroundLayers grounds={GROUNDS} regions={REGIONS} natural={NAT} content={CONTENT} layers={layers} />);
        expect(container.querySelector('.gl-layer[data-layer-key="trace"]').style.opacity).toBe('0.35');
    });

    it('no layers prop → the original single flat group (back-compat)', async () => {
        await mount(<GroundLayers grounds={GROUNDS} regions={REGIONS} natural={NAT} content={CONTENT} />);
        expect(container.querySelector('.gl-layer')).toBeNull();
        expect(container.querySelector('.gl-evidence')).not.toBeNull();
        expect(container.querySelector('.gl-path')).not.toBeNull();
    });
});
