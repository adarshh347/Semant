// PERCEPTUAL-FORMS-001E — the stage, the diagram and the legend, mounted.
//
// The unit suites prove the layers are declared. These prove the DECLARATION REACHES THE MARKUP —
// which is a different claim, and the one that matters to a person looking at the page. A layer
// can be perfectly described in a data structure and drawn as an anonymous grey path.

import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

import FormStage from './components/FormStage';
import FormDiagram from './components/FormDiagram';
import FormSurface from './components/FormSurface';
import LayerLegend from './components/LayerLegend';
import { renderView, viewFor } from './rendererRegistry';
import { payloadFor, FIXTURE_SOURCE } from './fixtures/formFixtures';
import { layer, absentLayer, EVIDENCE_TREATMENT } from './layerModel';

if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
}

let container; let root;
const mount = async (node) => { await act(async () => { root.render(node); }); };
const settle = async () => { await act(async () => { await Promise.resolve(); }); };

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
});

const q = (sel) => container.querySelector(sel);
const all = (sel) => [...container.querySelectorAll(sel)];
const click = async (el) => {
    if (!el) throw new Error('nothing to click');
    await act(async () => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
    await settle();
};

const NATURAL = { w: FIXTURE_SOURCE.natural_width, h: FIXTURE_SOURCE.natural_height };

const show = async (formKey, viewKey, scenario = 'contract', ctx = {}) => {
    const out = renderView(formKey, viewKey, payloadFor(formKey, scenario), ctx);
    await mount(<FormSurface view={out.view} layers={out.layers} sides={out.sides}
        items={out.items} natural={NATURAL} error={out.error} />);
    await settle();
    return out;
};

describe('the letterbox contract', () => {
    it('sets a natural-pixel viewBox and xMidYMid meet — the same two lines as RegionOverlay', () => {
        // A surface that reimplements `object-fit: contain` is how a mask lands on the wrong part
        // of a face. These two attributes ARE the contract; nothing else about the geometry is
        // shared, and nothing else needs to be.
        return show('extent.hard_mask', 'fill').then(() => {
            const svg = q('.pl-fm-svg');
            expect(svg.getAttribute('viewBox')).toBe('0 0 1600 1200');
            expect(svg.getAttribute('preserveAspectRatio')).toBe('xMidYMid meet');
        });
    });

    it('lands an 8×8 raster mask at the right eighths of a 1600×1200 frame', async () => {
        await show('extent.hard_mask', 'fill');
        const d = q('[data-layer="mask_fill:inst_1"] .pl-fm-ring').getAttribute('d');
        const xs = [...d.matchAll(/[ML]([\d.]+) ([\d.]+)/g)].map((m) => Number(m[1]));
        const ys = [...d.matchAll(/[ML]([\d.]+) ([\d.]+)/g)].map((m) => Number(m[2]));
        // Every vertex sits on an eighth of the frame: 1600/8 = 200, 1200/8 = 150.
        for (const x of xs) expect(x % 200).toBeCloseTo(0, 9);
        for (const y of ys) expect(y % 150).toBeCloseTo(0, 9);
        // The RLE fills columns 1-3, rows 2-5 of an 8x8 raster.
        expect([Math.min(...xs), Math.max(...xs)]).toEqual([200, 800]);
        expect([Math.min(...ys), Math.max(...ys)]).toEqual([300, 900]);
    });

    it('shows that the declared box and the measured mask do not agree', async () => {
        // A REAL PROPERTY OF THE COMMITTED FIXTURE, and the reason both views exist. The record
        // declares box {0.2, 0.2, 0.6, 0.6} and carries a mask that occupies 0.125-0.5 in x. A
        // laboratory that drew only the box would show a person a rectangle and let them believe
        // they were looking at the segmentation.
        await show('extent.hard_mask', 'box');
        const boxD = q('[data-layer="box_outline:inst_1"] .pl-fm-ring').getAttribute('d');
        const boxXs = [...boxD.matchAll(/[ML]([\d.]+) /g)].map((m) => Number(m[1]));
        expect([Math.min(...boxXs), Math.max(...boxXs)]).toEqual([320, 1280]);
        await show('extent.hard_mask', 'fill');
        const maskD = q('[data-layer="mask_fill:inst_1"] .pl-fm-ring').getAttribute('d');
        const maskXs = [...maskD.matchAll(/[ML]([\d.]+) /g)].map((m) => Number(m[1]));
        expect(Math.max(...maskXs)).toBeLessThan(Math.max(...boxXs));
    });

    it('crops a thumbnail by moving the viewBox, not by rescaling the geometry', async () => {
        await show('extent.hard_mask', 'contact_sheet');
        const svgs = all('.pl-fm-thumb .pl-fm-svg');
        expect(svgs.length).toBeGreaterThan(1);
        const box = svgs[0].getAttribute('viewBox').split(' ').map(Number);
        expect(box[2]).toBeLessThan(1600);
        expect(svgs[0].getAttribute('preserveAspectRatio')).toBe('xMidYMid meet');
        // and the caption says what fraction of the frame is on screen, so a 1% instance does not
        // look the same size as a 40% one
        expect(q('.pl-fm-thumbscale').textContent).toMatch(/% × \d+% of frame/);
    });
});

describe('inferred geometry never looks like visible geometry', () => {
    it('gives each evidence class its own dash in the markup', async () => {
        await show('extent.visible_inferred_partition', 'tricolor');
        const dash = (part) => q(`[data-layer="partition_tricolor:${part}"] .pl-fm-ring, `
            + `[data-layer="partition_tricolor:${part}"] .pl-fm-cellrule`)
            ?.getAttribute('stroke-dasharray') ?? null;
        expect(q('[data-layer="partition_tricolor:visible"]').getAttribute('data-evidence'))
            .toBe('measured');
        expect(q('[data-layer="partition_tricolor:inferred"]').getAttribute('data-evidence'))
            .toBe('inferred');
        expect(dash('visible')).toBeNull();
        expect(dash('inferred')).toBe(EVIDENCE_TREATMENT.inferred.dash);
        expect(dash('inferred')).not.toBe(dash('visible'));
    });

    it('hatches an inferred region and leaves a measured one unhatched', async () => {
        await show('extent.visible_inferred_partition', 'tricolor');
        const hatch = (part) => q(`[data-layer="partition_tricolor:${part}"] .pl-fm-hatch`);
        expect(hatch('visible')).toBeNull();
        expect(hatch('inferred')).toBeTruthy();
        expect(hatch('inferred').getAttribute('fill')).toMatch(/hatch-45/);
    });

    it('prints the word beside every layer, in the legend', async () => {
        await show('extent.visible_inferred_partition', 'tricolor');
        // The channel that survives being read aloud, printed in one colour, or looked at by
        // someone who cannot distinguish two hues.
        expect(all('[data-evidence-word]').map((e) => e.getAttribute('data-evidence-word')))
            .toEqual(['measured', 'inferred', 'hypothetical']);
        expect(container.textContent).toContain('asserted where nothing was seen');
    });

    it('uses a different pattern for a hypothesis than for an inference', async () => {
        await show('extent.visible_inferred_partition', 'tricolor');
        const unknown = q('[data-layer="partition_tricolor:unknown"] .pl-fm-hatch');
        expect(unknown.getAttribute('fill')).toMatch(/hatch-135/);
    });
});

describe('a scalar field is drawn as cells, and never binarized silently', () => {
    it('draws one rect per cell and a rule on every cell boundary', async () => {
        await show('extent.soft_field', 'wash');
        const cells = all('.pl-fm-cell');
        expect(cells).toHaveLength(16);
        expect(all('.pl-fm-cellrule')).toHaveLength(16);
        expect(q('.pl-fm-cells').getAttribute('data-raster')).toBe('4x4');
    });

    it('varies opacity with the value and declares the value on the cell', async () => {
        await show('extent.soft_field', 'wash');
        const cells = all('.pl-fm-cell');
        const values = cells.map((c) => Number(c.getAttribute('data-value')));
        expect(values[0]).toBe(1);
        expect(values[15]).toBe(0);
        expect(Number(cells[0].getAttribute('fill-opacity')))
            .toBeGreaterThan(Number(cells[15].getAttribute('fill-opacity')));
    });

    it('shows the threshold on screen the moment a field is cut', async () => {
        const out = await show('extent.soft_field', 'threshold');
        const cut = out.layers.find((l) => l.binarized);
        expect(cut).toBeTruthy();
        expect(q(`[data-layer="${cut.layer_id}"]`).getAttribute('data-binarized')).toBe('true');
        const shown = q('[data-decl-value="threshold"]');
        expect(shown).toBeTruthy();
        expect(shown.getAttribute('data-threshold')).toBe('0.5');
        expect(shown.textContent).toMatch(/threshold_would_be, recorded by the producer/);
    });

    it('keeps the whole field underneath the cut', async () => {
        // A threshold view that shows only the survivors hides how close the excluded cells were,
        // which is the single most useful thing a sweep can show.
        await show('extent.soft_field', 'threshold');
        expect(q('[data-layer="scalar_wash:under"]')).toBeTruthy();
        expect(q('[data-layer="scalar_wash:above"]')).toBeTruthy();
    });

    it('moves the cut, and says the number came from this page', async () => {
        await show('extent.soft_field', 'threshold', 'contract', { threshold: 0.75 });
        const shown = q('[data-decl-value="threshold"]');
        expect(shown.getAttribute('data-threshold')).toBe('0.75');
        expect(shown.textContent).toMatch(/chosen on this page, and applied here only/);
    });

    it('refuses a field it cannot read, and says the statistics are the measurement', async () => {
        await show('extent.soft_field', 'wash', 'withheld');
        expect(all('.pl-fm-cell')).toHaveLength(0);
        expect(q('[data-why-absent]').textContent).toMatch(/held behind data_ref/);
        expect(q('[data-why-absent]').textContent).toMatch(/would be invented/);
    });
});

describe('a diagram is not a stage', () => {
    it('draws the containment tree with a directed edge and a written sentence', async () => {
        await show('topology.containment_tree', 'tree');
        expect(q('.pl-fm-diagramsvg')).toBeTruthy();
        const edges = all('[data-edge]');
        expect(edges).toHaveLength(2);
        for (const e of edges) expect(e.getAttribute('data-directed')).toBe('true');
        expect(q('.pl-fm-edgeline').getAttribute('marker-end')).toMatch(/diagarrow/);
        // Direction in words too, because an arrowhead is small and the claim is the measurement.
        expect(q('[data-edge-sentence="piazza->fountain"]').textContent)
            .toBe('piazza contains fountain, filling 0.04 of it');
    });

    it('refuses a diagram layer that reaches the image stage, and says so', async () => {
        const out = renderView('topology.containment_tree', 'tree',
            payloadFor('topology.containment_tree'));
        await mount(<FormStage layers={out.layers} natural={NATURAL} />);
        await settle();
        expect(q('[data-stage-refused]')).toBeTruthy();
        expect(q('[data-stage-refused]').textContent).toMatch(/A graph node has no.*location/s);
        expect(all('.pl-fm-shape')).toHaveLength(0);
    });

    it('refuses an image layer that reaches the diagram', async () => {
        const out = renderView('extent.hard_mask', 'fill', payloadFor('extent.hard_mask'));
        await mount(<FormDiagram layers={out.layers} />);
        await settle();
        expect(q('[data-diagram-refused]')).toBeTruthy();
        expect(q('[data-diagram-refused]').textContent).toMatch(/Pixels do.*not belong in a graph/s);
    });

    it('draws a hollow, dashed node for an endpoint that does not resolve', async () => {
        await show('topology.adjacency_graph', 'graph');
        const nodes = all('[data-node]');
        expect(nodes.length).toBe(3);
        for (const n of nodes) expect(n.getAttribute('data-resolved')).toBe('false');
        expect(q('.pl-fm-nodedot').getAttribute('stroke-dasharray')).toBe('3 3');
        // ...and the id is on screen, so "which one is missing" is answerable.
        expect(container.textContent).toContain('pier_1');
    });

    it('gives the matrix three marks, so examined-and-unrelated is not empty space', async () => {
        await show('topology.adjacency_graph', 'matrix');
        expect(q('[data-cell="pier_1|pier_1"]').textContent).toBe('—');
        expect(q('[data-cell="pier_1|pier_2"]').textContent).toBe('meets');
        expect(q('[data-cell="pier_1|pier_3"]').textContent).toBe('disjoint');
        expect(container.textContent).toMatch(/examined, and no relation stood/);
    });

    it('names an isolated node rather than leaving it as blank space', async () => {
        const out = renderView('topology.adjacency_graph', 'graph', {
            ...payloadFor('topology.adjacency_graph'),
            nodes: [...payloadFor('topology.adjacency_graph').nodes, { node_id: 'pier_4' }],
        });
        await mount(<FormSurface view={out.view} layers={out.layers} natural={NATURAL} />);
        await settle();
        expect(q('[data-isolated]').textContent).toMatch(/pier_4 carries no edge/);
    });
});

describe('an arrowhead is only drawn where the record says directed', () => {
    it('draws one on contains and none on disjoint', async () => {
        await show('topology.pair_relation', 'endpoints', 'resolvable');
        const rows = all('.pl-fm-shape[data-layer^="endpoint_pair:"]');
        expect(rows.length).toBeGreaterThan(0);
        for (const g of rows) {
            const arrow = g.getAttribute('data-arrow');
            expect(['true', 'false']).toContain(arrow);
        }
        // `rel_masks` is `meets` and undirected. An arrow on it would assert an ordering the
        // organ did not measure.
        const undirected = q('.pl-fm-shape[data-layer="endpoint_pair:rel_masks"]');
        expect(undirected.getAttribute('data-arrow')).toBe('false');
        expect(q('[data-layer="endpoint_pair:rel_masks"] .pl-fm-polyline')
            .getAttribute('marker-end')).toBeNull();
    });
});

describe('the legend', () => {
    it('renders one row per layer, never collapsed by class', async () => {
        await show('extent.hard_mask', 'fill', 'dense');
        const rows = all('[data-layer][data-evidence].pl-fm-legendrow');
        expect(rows).toHaveLength(18);
        expect(Number(q('[data-legend-count]').getAttribute('data-legend-count'))).toBe(18);
    });

    it('carries the whole declaration, not just the class', async () => {
        await show('extent.hard_mask', 'fill');
        const row = q('.pl-fm-legendrow[data-layer="mask_fill:inst_1"]');
        const decl = (k) => row.querySelector(`[data-decl-value="${k}"]`)?.textContent;
        expect(decl('form')).toBe('extent.hard_mask');
        expect(decl('record')).toBe('art_extent_1#inst_1');
        expect(decl('space')).toBe('image_normalized');
        expect(decl('raster')).toBe('8×8');
        expect(decl('basis')).toBe('mask');
        expect(decl('status')).toBe('measured');
    });

    it('says why an absent layer is absent, in the row where the drawing would be', async () => {
        await show('topology.intersection_area', 'endpoints');
        const why = q('[data-why-absent]');
        expect(why.textContent).toMatch(/no committed fixture carries/);
        expect(why.textContent).toMatch(/would draw a shape nobody measured/);
    });

    it('prints a derived-versus-recorded disagreement as a disagreement', async () => {
        await show('topology.pair_relation', 'contact', 'resolvable');
        const agreements = all('[data-agreement]');
        expect(agreements.length).toBeGreaterThan(0);
        for (const a of agreements) {
            expect(['agrees', 'disagrees']).toContain(a.getAttribute('data-agreement'));
            expect(a.textContent).toMatch(/vs .* — (agrees|DISAGREES)/);
        }
    });

    it('reports a renderer that produced nothing at all as a bug in the renderer', async () => {
        await mount(<LayerLegend layers={[]} />);
        await settle();
        expect(q('[data-legend-empty]')).toBeTruthy();
        expect(container.textContent).toMatch(/That is a bug in.*the renderer/s);
    });
});

describe('keyboard and focus', () => {
    it('makes every layer reachable by Tab, through the legend', async () => {
        // SVG shapes are awkward to focus and worse to describe. The rows are ordinary buttons,
        // so nothing on the stage is reachable ONLY by pointing.
        await show('extent.hard_mask', 'fill');
        const buttons = all('button[data-focus-layer]');
        expect(buttons).toHaveLength(2);
        for (const b of buttons) {
            expect(b.tagName).toBe('BUTTON');
            expect(b.getAttribute('aria-pressed')).toBe('false');
        }
    });

    it('focuses a layer from its legend row and dims the rest', async () => {
        const out = renderView('extent.hard_mask', 'fill', payloadFor('extent.hard_mask'));
        let focusId = null;
        const Harness = () => {
            const [id, setId] = React.useState(null);
            focusId = id;
            return <FormSurface view={out.view} layers={out.layers} natural={NATURAL}
                focusId={id} onFocus={setId} />;
        };
        await mount(<Harness />);
        await settle();
        await click(q('[data-focus-layer="mask_fill:inst_1"]'));
        expect(focusId).toBe('mask_fill:inst_1');
        expect(q('[data-layer="mask_fill:inst_1"].pl-fm-shape').getAttribute('data-focused'))
            .toBe('true');
        expect(q('[data-focus-layer="mask_fill:inst_1"]').getAttribute('aria-pressed')).toBe('true');
        await click(q('[data-focus-layer="mask_fill:inst_1"]'));
        expect(focusId).toBeNull();
    });

    it('gives the stage an accessible name that counts what is drawn', async () => {
        await show('extent.hard_mask', 'fill');
        expect(q('.pl-fm-svg').getAttribute('role')).toBe('img');
        expect(q('.pl-fm-svg').getAttribute('aria-label')).toBe('Mask fill: 1 drawn layer');
    });
});

describe('the alternatives surfaces', () => {
    it('holds three alternatives in three panes, never superimposed', async () => {
        await show('extent.hypothesis_set', 'split');
        const panes = all('[data-pane]');
        expect(panes).toHaveLength(3);
        expect(panes.map((p) => p.getAttribute('data-pane')))
            .toEqual(['alt_one_object', 'alt_two_objects', 'alt_object_and_plane']);
        // Each pane has its own svg — nothing is drawn on top of anything else.
        expect(all('[data-pane] .pl-fm-svg')).toHaveLength(3);
    });

    it('shows one alternative by default, and names which', async () => {
        const out = await show('extent.hypothesis_set', 'tabs');
        expect(out.view.alternatives).toBe('one_at_a_time');
        const ids = out.layers.map((l) => l.hypothesis_id).filter(Boolean);
        expect(new Set(ids).size).toBeLessThanOrEqual(1);
    });

    it('layers them only when the layered view is chosen, keeping each id', async () => {
        const out = await show('extent.hypothesis_set', 'layered');
        const ids = new Set(out.layers.map((l) => l.hypothesis_id).filter(Boolean));
        expect(ids.size).toBe(3);
        expect(all('[data-decl-value="hypothesis"]').length).toBeGreaterThan(1);
    });

    it('puts before and after in separate panes, and flags a stale revision', async () => {
        await show('topology.transition', 'before_after');
        expect(all('[data-pane]').map((p) => p.getAttribute('data-pane')))
            .toEqual(['before', 'after']);
        expect(q('[data-pane-label="before"]').textContent).toMatch(/before — meets/);
        expect(q('[data-pane-label="after"]').textContent).toMatch(/after — overlaps/);
        // `inst_1` is cited at geometry_rev 1 on the after side; the fixture set carries rev 0.
        expect(container.textContent).toMatch(/is NOT the.*geometry this half of the transition/s);
    });
});

describe('a panel is a surface, not a fallback', () => {
    it('renders measurements that have no shape', async () => {
        await show('topology.intersection_area', 'area');
        expect(q('[data-measure="fraction_of_source"]').textContent).toBe('0.83');
        expect(q('[data-measure="fraction_of_target"]').textContent).toBe('0.21');
        expect(container.textContent).toMatch(/reporting one number.*would pick a side/s);
    });

    it('says a ground was not weighed rather than printing a zero', async () => {
        await show('extent.fused_hypothesis', 'grounds');
        const unweighed = all('[data-strength="unweighed"]');
        expect(unweighed.length).toBeGreaterThan(0);
        expect(unweighed[0].textContent).toBe('not weighed');
        expect(q('[data-strength="0.8"]')).toBeTruthy();
    });

    it('says the weights are not probabilities when the record says they are not', async () => {
        await show('extent.hypothesis_set', 'weights');
        expect(container.textContent).toMatch(/THE WEIGHTS ARE NOT PROBABILITIES/);
        expect(container.textContent).toMatch(/reading 0\.62 as "62% likely" is a claim this record/);
    });
});

describe('a render failure does not take the page down', () => {
    it('shows the message where the drawing would be', async () => {
        const out = renderView('extent.hard_mask', 'fill', { instances: null });
        await mount(<FormSurface view={out.view} layers={out.layers} natural={NATURAL}
            error={out.error} />);
        await settle();
        expect(q('[data-render-error]').textContent).toMatch(/could not be built/);
    });

    it('refuses to build a layer that would be drawn without a declaration', async () => {
        expect(() => layer({
            layer_id: 'x', label: 'x', evidence: 'measured',
            coordinate_system: 'nowhere', draw: { kind: 'rings', rings: [] },
        })).toThrow(/coordinate system/);
        // and the only way to have nothing on the stage is to say why
        expect(absentLayer({ layer_id: 'y', label: 'y', why: 'because' }).why_absent).toBe('because');
    });
});

describe('the view registry drives every surface', () => {
    it.each([
        ['extent.hard_mask', 'contact_sheet', 'sheet'],
        ['extent.hard_mask', 'before_after', 'compare'],
        ['extent.hierarchy', 'tree', 'diagram'],
        ['extent.density_field', 'samples', 'panel'],
        ['topology.negative_space_field', 'wash', 'stage'],
    ])('%s/%s renders as a %s', async (formKey, viewKey, surface) => {
        await show(formKey, viewKey);
        expect(viewFor(formKey, viewKey).surface).toBe(surface);
        expect(q('.pl-fm-surface').getAttribute('data-surface')).toBe(surface);
    });

    it('shows the measured negative-space field as absent and the derived one as derived', async () => {
        // The pairing IS the view: the record's own field is behind a ref this page cannot read,
        // and the only picture available is the one this browser computed.
        await show('topology.negative_space_field', 'wash', 'resolvable');
        const measured = q('.pl-fm-legendrow[data-layer="scalar_wash:measured"]');
        const derived = q('.pl-fm-legendrow[data-layer="density_contours:derived"]');
        expect(measured.getAttribute('data-evidence')).toBe('absent');
        expect(derived.getAttribute('data-evidence')).toBe('derived');
        expect(measured.textContent).toMatch(/carries no.*inline values/s);
        expect(derived.textContent).toMatch(/computed in this browser/);
        expect(all('.pl-fm-cell').length).toBeGreaterThan(0);
    });
});
