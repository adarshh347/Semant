import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import FlowFieldLayer from './FlowFieldLayer';
import { FLOW_FIELD_KIND } from './flowField';
import { makeVisualMark, validateMark } from './visualMarks';

/**
 * CIRCUIT-001 GEOM-001 — the flow_field renderer draws one arrow per LIVE cell and nothing for a
 * null cell, holds its own SVG (additive), and validates as a real trace_mark geometry.
 * A square natural size keeps the maths simple; jsdom needs no layout for an SVG viewBox.
 */

let container; let root;
async function mount(node) { await act(async () => { root.render(node); }); }
beforeEach(() => { container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container); });
afterEach(async () => { await act(async () => { root.unmount(); }); container.remove(); });

const NAT = { w: 1000, h: 1000 };
const RIGHT = [1, 0, 1.0];
const NULL = [0, 0, 0];
const field = (cells, cols = 2, rows = 2) => ({ kind: FLOW_FIELD_KIND, cols, rows, cells });

describe('FlowFieldLayer — render', () => {
    it('draws one arrow group per live cell, skipping null cells', async () => {
        await mount(<FlowFieldLayer geometry={field([RIGHT, RIGHT, RIGHT, NULL])} natural={NAT} />);
        expect(container.querySelectorAll('.ff-arrow')).toHaveLength(3);
        expect(container.querySelectorAll('.ff-shaft')).toHaveLength(3);
        expect(container.querySelectorAll('.ff-head')).toHaveLength(3);
    });

    it('accepts the field on a mark.geometry as well as a bare geometry prop', async () => {
        const mark = makeVisualMark('trace_mark', {
            role: 'fall_of_light',
            geometry: field([RIGHT, RIGHT, RIGHT, RIGHT]),
        });
        await mount(<FlowFieldLayer mark={mark} natural={NAT} />);
        expect(container.querySelectorAll('.ff-arrow')).toHaveLength(4);
    });

    it('a right-pointing cell draws a shaft whose end x exceeds its start x', async () => {
        await mount(<FlowFieldLayer geometry={field([RIGHT, RIGHT, RIGHT, RIGHT])} natural={NAT} />);
        const shaft = container.querySelector('.ff-shaft');
        expect(Number(shaft.getAttribute('x2'))).toBeGreaterThan(Number(shaft.getAttribute('x1')));
        // a horizontal fall keeps y level
        expect(Number(shaft.getAttribute('y2'))).toBeCloseTo(Number(shaft.getAttribute('y1')), 3);
    });

    it('renders nothing for an all-null / missing field or absent natural size', async () => {
        await mount(<FlowFieldLayer geometry={field([NULL, NULL, NULL, NULL])} natural={NAT} />);
        expect(container.querySelector('[data-testid="flow-field-layer"]')).toBeNull();

        await mount(<FlowFieldLayer geometry={field([RIGHT, RIGHT, RIGHT, RIGHT])} natural={null} />);
        expect(container.querySelector('[data-testid="flow-field-layer"]')).toBeNull();
    });

    it('carries a resting state class when not focused', async () => {
        await mount(<FlowFieldLayer geometry={field([RIGHT, RIGHT, RIGHT, RIGHT])} natural={NAT} focused={false} />);
        expect(container.querySelector('.ff-layer.is-resting')).not.toBeNull();
    });
});

describe('FlowFieldLayer — the kind validates as a real trace_mark', () => {
    it('a flow_field trace_mark passes validateMark', () => {
        const mark = makeVisualMark('trace_mark', {
            role: 'fall_of_light',
            status: 'suggested',
            source: 'model_suggested',
            derived_from: null,
            geometry: field([RIGHT, RIGHT, RIGHT, RIGHT]),
            provenance: { run_id: 'run_1', producer: 'fall_of_light', adapter: 'intrinsic_ordinal_shading' },
        });
        const v = validateMark(mark);
        expect(v.errors).toEqual([]);
        expect(v.valid).toBe(true);
    });
});

describe('FlowFieldLayer — TRACE-001: axial rendering', () => {
    // An architectural_axis field: every direction canonicalised to dx >= 0, because the sign
    // of a wall edge carries no information.
    const AXIS = field([[0, 1, 1], [0.7071, 0.7071, 0.6], [1, 0, 0.4], NULL]);

    it('draws NO arrowhead in axial mode — a wall edge has no direction', async () => {
        await mount(<FlowFieldLayer geometry={AXIS} natural={NAT} axial />);
        expect(container.querySelectorAll('.ff-shaft')).toHaveLength(3);   // null cell drew nothing
        expect(container.querySelectorAll('.ff-head')).toHaveLength(0);
    });

    it('still draws arrowheads by default — fall_of_light is unchanged by this prop', async () => {
        await mount(<FlowFieldLayer geometry={AXIS} natural={NAT} />);
        expect(container.querySelectorAll('.ff-head')).toHaveLength(3);
    });

    it('a null cell renders nothing in axial mode too — absence stays absence', async () => {
        await mount(<FlowFieldLayer geometry={AXIS} natural={NAT} axial />);
        expect(container.querySelectorAll('.ff-arrow')).toHaveLength(3);
    });

    it('the shaft stays centred on its cell, so an axis reads both ways', async () => {
        await mount(<FlowFieldLayer geometry={field([[0, 1, 1]], 1, 1)} natural={NAT} axial />);
        const line = container.querySelector('.ff-shaft');
        const y1 = Number(line.getAttribute('y1'));
        const y2 = Number(line.getAttribute('y2'));
        expect((y1 + y2) / 2).toBeCloseTo(NAT.h / 2, 1);   // centred on the single cell
        expect(Math.abs(y2 - y1)).toBeGreaterThan(1);      // and it has extent
    });
});
