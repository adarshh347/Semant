import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import GroundLayers from './GroundLayers';
import { deriveLayers, markLayerKey } from './layerGrouping';

/**
 * CIRCUIT-001 MOUNT-001 — FlowFieldLayer is finally mounted.
 *
 * GEOM shipped the renderer and never called it, so fall_of_light, architectural_axis and
 * external_limit all minted `flow_field` marks that nothing drew: three producers, zero pixels.
 * These tests pin the mount, the axial/directional routing, and the layer integration.
 */

let container; let root;
async function mount(node) { await act(async () => { root.render(node); }); }
beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(async () => { await act(async () => { root.unmount(); }); container.remove(); });

const NAT = { w: 1000, h: 1000 };
const CONTENT = { x: 0, y: 0, w: 1000, h: 1000 };

const CELLS = [[1, 0, 1], [0, 1, 0.8], [0.7071, 0.7071, 0.6], [0, 0, 0]];  // last is null
const flowMark = (role, over = {}) => ({
    id: `m_${role}`, type: 'trace_mark', role, status: 'committed', source: 'user',
    geometry: { kind: 'flow_field', cols: 2, rows: 2, cells: CELLS },
    ...over,
});
const regionMark = () => ({
    id: 'm_region', type: 'region_mask', role: null, status: 'committed', source: 'user',
    geometry: { kind: 'region_ref', region_id: 'reg_1' },
});

const layerFor = (marks, over = {}) =>
    deriveLayers([], [], marks).map((l) => ({ ...l, ...over }));


describe('MOUNT-001 — the mount itself', () => {
    it('a committed flow_field mark now RENDERS (it did not before this gate)', async () => {
        await mount(<GroundLayers grounds={[]} natural={NAT} content={CONTENT}
                                  marks={[flowMark('fall_of_light')]} />);
        expect(container.querySelectorAll('[data-testid="flow-field-layer"]')).toHaveLength(1);
        // three live cells, one null cell drawing nothing
        expect(container.querySelectorAll('.ff-arrow')).toHaveLength(3);
    });

    it('renders one layer per flow_field mark', async () => {
        await mount(<GroundLayers grounds={[]} natural={NAT} content={CONTENT}
                                  marks={[flowMark('fall_of_light'), flowMark('architectural_axis')]} />);
        expect(container.querySelectorAll('[data-testid="flow-field-layer"]')).toHaveLength(2);
    });

    it('no marks means nothing new is drawn — grounds-only callers are unaffected', async () => {
        await mount(<GroundLayers grounds={[]} natural={NAT} content={CONTENT} />);
        expect(container.querySelectorAll('[data-testid="flow-field-layer"]')).toHaveLength(0);
    });

    it('ignores marks that are not flow_field — this adds a lane, it does not take one over', async () => {
        await mount(<GroundLayers grounds={[]} natural={NAT} content={CONTENT}
                                  marks={[regionMark()]} />);
        expect(container.querySelectorAll('[data-testid="flow-field-layer"]')).toHaveLength(0);
    });

    it('an UNCOMMITTED mark does not render — a suggestion is not evidence', async () => {
        await mount(<GroundLayers grounds={[]} natural={NAT} content={CONTENT}
                                  marks={[flowMark('fall_of_light', { status: 'suggested' })]} />);
        expect(container.querySelectorAll('[data-testid="flow-field-layer"]')).toHaveLength(0);
    });

    it('shares the stage-geometry contract with the ground svg, so it cannot drift', async () => {
        await mount(<GroundLayers grounds={[]} natural={NAT} content={CONTENT}
                                  marks={[flowMark('fall_of_light')]} />);
        const ff = container.querySelector('[data-testid="flow-field-layer"]');
        const gl = container.querySelector('svg.gl-svg');
        expect(ff.getAttribute('viewBox')).toBe(`0 0 ${NAT.w} ${NAT.h}`);
        expect(ff.getAttribute('viewBox')).toBe(gl.getAttribute('viewBox'));
        expect(ff.getAttribute('preserveAspectRatio')).toBe(gl.getAttribute('preserveAspectRatio'));
    });
});


describe('MOUNT-001 — axial vs directional routing', () => {
    it('architectural_axis renders arrowhead-OFF', async () => {
        await mount(<GroundLayers grounds={[]} natural={NAT} content={CONTENT}
                                  marks={[flowMark('architectural_axis')]} />);
        expect(container.querySelectorAll('.ff-shaft')).toHaveLength(3);
        expect(container.querySelectorAll('.ff-head')).toHaveLength(0);
    });

    it('external_limit renders arrowhead-OFF — a horizon has no near end', async () => {
        await mount(<GroundLayers grounds={[]} natural={NAT} content={CONTENT}
                                  marks={[flowMark('external_limit')]} />);
        expect(container.querySelectorAll('.ff-head')).toHaveLength(0);
    });

    it('fall_of_light KEEPS its arrowheads — light travels one way', async () => {
        await mount(<GroundLayers grounds={[]} natural={NAT} content={CONTENT}
                                  marks={[flowMark('fall_of_light')]} />);
        expect(container.querySelectorAll('.ff-head')).toHaveLength(3);
    });

    it('an unknown role is NOT assumed axial, so a future trace keeps its arrowheads', async () => {
        await mount(<GroundLayers grounds={[]} natural={NAT} content={CONTENT}
                                  marks={[flowMark('gaze_address')]} />);
        expect(container.querySelectorAll('.ff-head')).toHaveLength(3);
    });

    it('mixed roles route independently in one render', async () => {
        await mount(<GroundLayers grounds={[]} natural={NAT} content={CONTENT}
                                  marks={[flowMark('fall_of_light'), flowMark('architectural_axis')]} />);
        // one layer keeps heads, the other does not: 3 heads total across 6 shafts
        expect(container.querySelectorAll('.ff-shaft')).toHaveLength(6);
        expect(container.querySelectorAll('.ff-head')).toHaveLength(3);
    });
});


describe('MOUNT-001 — layer integration', () => {
    it('a flow_field mark gets its own per-role trace layer', () => {
        expect(markLayerKey(flowMark('fall_of_light'))).toBe('trace:fall_of_light');
        expect(markLayerKey(flowMark('architectural_axis'))).toBe('trace:architectural_axis');
    });

    it('a non-flow_field mark routes nowhere rather than into "other"', () => {
        // A duplicate layer row would offer a switch that controls nothing.
        expect(markLayerKey(regionMark())).toBe(null);
        expect(markLayerKey(null)).toBe(null);
    });

    it('deriveLayers surfaces one row per trace role, named', () => {
        const layers = deriveLayers([], [], [flowMark('fall_of_light'), flowMark('external_limit')]);
        const byKey = Object.fromEntries(layers.map((l) => [l.key, l]));
        expect(byKey['trace:fall_of_light'].name).toBe('Fall of light');
        expect(byKey['trace:external_limit'].name).toBe('Limit');
        expect(byKey['trace:fall_of_light'].count).toBe(1);
    });

    it('hiding the mark\'s layer hides the mark', async () => {
        const marks = [flowMark('fall_of_light')];
        await mount(<GroundLayers grounds={[]} natural={NAT} content={CONTENT} marks={marks}
                                  layers={layerFor(marks, { visibility: false })} />);
        expect(container.querySelectorAll('[data-testid="flow-field-layer"]')).toHaveLength(0);
    });

    it('showing it again brings it back', async () => {
        const marks = [flowMark('fall_of_light')];
        await mount(<GroundLayers grounds={[]} natural={NAT} content={CONTENT} marks={marks}
                                  layers={layerFor(marks, { visibility: true })} />);
        expect(container.querySelectorAll('[data-testid="flow-field-layer"]')).toHaveLength(1);
    });

    it('the layer\'s opacity reaches the rendered field', async () => {
        const marks = [flowMark('fall_of_light')];
        await mount(<GroundLayers grounds={[]} natural={NAT} content={CONTENT} marks={marks}
                                  layers={layerFor(marks, { opacity: 0.4 })} />);
        const ff = container.querySelector('[data-testid="flow-field-layer"]');
        expect(Number(ff.style.opacity)).toBeCloseTo(0.4, 3);
    });

    it('hiding EVIDENCE hides flow fields too — they are evidence, in their own svg', async () => {
        await mount(<GroundLayers grounds={[]} natural={NAT} content={CONTENT}
                                  marks={[flowMark('fall_of_light')]} evidenceVisible={false} />);
        expect(container.querySelectorAll('[data-testid="flow-field-layer"]')).toHaveLength(0);
    });

    it('evidence opacity multiplies with the layer\'s, it does not replace it', async () => {
        const marks = [flowMark('fall_of_light')];
        await mount(<GroundLayers grounds={[]} natural={NAT} content={CONTENT} marks={marks}
                                  layers={layerFor(marks, { opacity: 0.5 })} evidenceOpacity={0.5} />);
        const ff = container.querySelector('[data-testid="flow-field-layer"]');
        expect(Number(ff.style.opacity)).toBeCloseTo(0.25, 3);
    });

    it('one trace layer can hide while another stays visible', async () => {
        const marks = [flowMark('fall_of_light'), flowMark('architectural_axis')];
        const layers = deriveLayers([], [], marks).map((l) =>
            (l.key === 'trace:fall_of_light' ? { ...l, visibility: false } : l));
        await mount(<GroundLayers grounds={[]} natural={NAT} content={CONTENT}
                                  marks={marks} layers={layers} />);
        const rendered = container.querySelectorAll('[data-testid="flow-field-layer"]');
        expect(rendered).toHaveLength(1);
        expect(rendered[0].getAttribute('class')).toContain('gl-flow--architectural_axis');
    });
});
