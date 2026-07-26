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
