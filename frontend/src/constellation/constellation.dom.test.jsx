/**
 * WAVE4 — the constellation view: the ways a node-link diagram lies.
 *
 * A line between two dots reads as a fact and nobody checks a line. The backend derives `span`,
 * `epistemic` and `ledger_status` honestly; **none of that reaches the screen**, and a renderer
 * that put all three on one stroke — or on none — would draw a convincing world nobody measured.
 *
 *   1. THREE FACTS, THREE CHANNELS, plus the label. No two statuses share a treatment, and nothing
 *      depends on styling alone. §1.
 *   2. WITHIN-IMAGE IS VISIBLY NOT BETWEEN-IMAGE — images are columns, so the distinction is in the
 *      layout before it is in a stroke. §2.
 *   3. `epistemic: null` IS A THIRD STATE, not a shade of interpretive. §1.
 *   4. THE BOUND IS ON THE PAGE. A six-node picture is a claim about how far it walked. §3.
 *
 * No testing-library — plain DOM against a real root, the shape the other `.dom.test.jsx` use.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import ConstellationGraph from './ConstellationGraph.jsx';
import ConstellationPage from './ConstellationPage.jsx';
import { curve, layout } from './layout.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));

let container;
let root;

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});

afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
    vi.restoreAllMocks();
});

// ── fixtures: the shape the real route returns ──────────────────────────────

const NODES = [
    { node_id: 'vm_pA:r0', post_id: 'pA', region_id: 'r0', label: '', hop: 0, is_seed: true },
    { node_id: 'vm_pA:r1', post_id: 'pA', region_id: 'r1', label: '', hop: 1, is_seed: false },
    { node_id: 'vm_pB:rB', post_id: 'pB', region_id: 'rB', label: '', hop: 1, is_seed: false },
];

const WITHIN = {
    edge_id: 'e_within', source: 'proposal', axis: 'axis_occlusion', relation: 'in_front_of',
    a_node: 'vm_pA:r1', b_node: 'vm_pA:r0', span: 'within_image', directed: true,
    front_node: 'vm_pA:r1', epistemic: 'measured', ledger_status: 'proposed', basis: 'mask',
    evidence: { ordering_separation: 0.98 }, detail: 'r1 is IN FRONT OF r0',
};

const BETWEEN = {
    edge_id: 'e_between', source: 'atlas', axis: 'axis_nestedness', relation: 'nested_within',
    a_node: 'vm_pA:r0', b_node: 'vm_pB:rB', span: 'between_images', directed: false,
    front_node: '', epistemic: null, ledger_status: 'proposed', basis: '',
    evidence: {}, detail: 'the mark it cites is not in any ledger',
};

const COMMITTED = { ...WITHIN, edge_id: 'e_committed', ledger_status: 'committed' };
const INTERPRETIVE = { ...WITHIN, edge_id: 'e_interp', epistemic: 'interpretive' };

const WALK = {
    seed: 'vm_pA:r0', depth: 2, nodes: NODES, edges: [WITHIN, BETWEEN],
    images: ['pA', 'pB'],
    tally: { nodes: 3, images: 2, edges: 2,
             by_span: { within_image: 1, between_images: 1 },
             by_ledger_status: { proposed: 2 } },
    bound_detail: 'walked 2 hop(s) from vm_pA:r0. …a candidate the kernel refused was never written down',
    sources: { ledger_relation_marks: 0, curator_proposals: 13, atlas_movement_edges: 1 },
};

const SEEDS = {
    seeds: [{ node_id: 'vm_pA:r0', post_id: 'pA', region_id: 'r0', label: '', degree: 2 }],
    total: 4, detail: 'a fact about what producers have FILED',
};

function backend({ walk = WALK } = {}) {
    const calls = [];
    vi.stubGlobal('fetch', vi.fn(async (url, init) => {
        const target = String(url);
        calls.push(`${(init && init.method) || 'GET'} ${target}`);
        const body = target.includes('/seeds') ? SEEDS : walk;
        return { ok: true, status: 200, json: async () => body };
    }));
    return calls;
}

async function mount(element, { route = '/constellation?node=vm_pA:r0&depth=2' } = {}) {
    await act(async () => {
        root.render(<MemoryRouter initialEntries={[route]}>{element}</MemoryRouter>);
    });
    await act(async () => { await Promise.resolve(); });
    await act(async () => { await Promise.resolve(); });
}

const $ = (sel) => container.querySelector(sel);
const $$ = (sel) => Array.from(container.querySelectorAll(sel));

// ── 1. three facts, three channels ─────────────────────────────────────────

describe('an edge carries its three facts on three channels', () => {
    it('classes each edge by span, epistemic and ledger status', async () => {
        await mount(<ConstellationGraph nodes={NODES} edges={[WITHIN, BETWEEN]} />);
        const within = $('.con-edge--within_image');
        const between = $('.con-edge--between_images');
        expect(within.getAttribute('class')).toContain('con-edge--measured');
        expect(within.getAttribute('class')).toContain('con-edge--proposed');
        expect(between.getAttribute('class')).toContain('con-edge--unreadable');
    });

    it('writes all three on the edge label too, so no fact lives only in a stylesheet', async () => {
        await mount(<ConstellationGraph nodes={NODES} edges={[WITHIN]} />);
        const label = $('.con-edgelabel').textContent;
        expect(label).toContain('in_front_of');
        expect(label).toContain('measured');
        expect(label).toContain('proposed');
    });

    it('renders an unreadable mark as its own state, never as interpretive', async () => {
        await mount(<ConstellationGraph nodes={NODES} edges={[BETWEEN]} />);
        const label = $('.con-edgelabel').textContent;
        expect(label).toContain('no readable mark');
        expect(label).not.toContain('interpretive');
        expect(label).not.toContain('uncertain');
    });

    it('gives measured, interpretive, unreadable, proposed and committed distinct treatments', () => {
        // Off the stylesheet: a claim about pixels no DOM query reaches, and the failure it guards
        // — two statuses that look alike — is exactly what the curator lane already caught once.
        const css = fs.readFileSync(path.join(HERE, 'constellation.css'), 'utf8');
        const rule = (name) => {
            const m = css.match(new RegExp(`\\.con-edge--${name}\\s*\\{([^}]*)\\}`));
            return m ? m[1].replace(/\s+/g, ' ').trim() : null;
        };
        const names = ['measured', 'interpretive', 'unreadable', 'proposed', 'committed'];
        const rules = names.map(rule);
        expect(rules.every(Boolean)).toBe(true);
        expect(new Set(rules).size).toBe(names.length);
        // epistemic rides the DASH, ledger rides the WIDTH — two channels, never one
        expect(rule('interpretive')).toContain('stroke-dasharray');
        expect(rule('unreadable')).toContain('stroke-dasharray');
        expect(rule('proposed')).toContain('stroke-width');
        expect(rule('committed')).toContain('stroke-width');
        expect(rule('proposed')).not.toContain('stroke-dasharray');
    });

    it('draws an arrowhead only where the relation is directed', async () => {
        await mount(<ConstellationGraph nodes={NODES} edges={[WITHIN, BETWEEN]} />);
        const paths = $$('path.con-edge');
        const withArrow = paths.filter((p) => p.getAttribute('marker-end'));
        expect(withArrow).toHaveLength(1);
        expect(withArrow[0].getAttribute('class')).toContain('within_image');
    });
});

// ── 2. within-image is visibly not between-image ───────────────────────────

describe('images are places, and the layout says so', () => {
    it('gives each image its own column, seed first', () => {
        const { columns, positions } = layout(NODES);
        expect(columns.map((c) => c.post_id)).toEqual(['pA', 'pB']);
        expect(positions['vm_pA:r0'].column).toBe(0);
        expect(positions['vm_pB:rB'].column).toBe(1);
    });

    it('keeps a within-image edge inside one column and makes a crossing span two', () => {
        const { positions } = layout(NODES);
        const sameColumn = positions[WITHIN.a_node].column === positions[WITHIN.b_node].column;
        const acrossColumns = positions[BETWEEN.a_node].column !== positions[BETWEEN.b_node].column;
        expect(sameColumn).toBe(true);
        expect(acrossColumns).toBe(true);
    });

    it('draws a column box and a label per image', async () => {
        await mount(<ConstellationGraph nodes={NODES} edges={[WITHIN, BETWEEN]} />);
        expect($$('.con-columnbox')).toHaveLength(2);
        expect($$('.con-columnlabel').map((t) => t.textContent)).toEqual(['pA', 'pB']);
    });

    it('lays out deterministically — the same input twice gives the same coordinates', () => {
        // A force layout would place these fine and place them differently every run, which would
        // render "which image a node lives in" as an accident of the simulation.
        expect(layout(NODES).positions).toEqual(layout(NODES).positions);
        expect(curve({ x: 0, y: 0, column: 0 }, { x: 0, y: 60, column: 0 }))
            .toBe(curve({ x: 0, y: 0, column: 0 }, { x: 0, y: 60, column: 0 }));
    });

    it('bows edges inside a column LEFT, away from the labels, and by the span', () => {
        // Five parts in front of one wall is the commonest shape in this corpus. Straight lines
        // rendered them as one thick stroke hiding five claims; bowing RIGHT — the first fix —
        // ran all five through the region names, which are drawn to the right of their dots.
        const near = curve({ x: 130, y: 0, column: 0 }, { x: 130, y: 62, column: 0 });
        const far = curve({ x: 130, y: 0, column: 0 }, { x: 130, y: 248, column: 0 });
        const cx = (d) => Number(d.split('Q ')[1].split(' ')[0]);
        expect(cx(near)).toBeLessThan(130);
        expect(cx(far)).toBeLessThan(cx(near));   // longer span, wider arc: they separate
    });
});

// ── 3. the bound is on the page ────────────────────────────────────────────

describe('the page states its bound and its sources', () => {
    it('shows the depth, the counts and the backend’s own bound sentence', async () => {
        backend();
        await mount(<ConstellationPage />);
        expect($('.con-bound').textContent).toContain('never written down');
        expect($('.con-counts').textContent).toContain('1 through');
        expect($('.con-counts').textContent).toContain('1 between');
        expect($('.con-depth.is-on').textContent).toBe('2');
    });

    it('reports how many relations exist in each durable place', async () => {
        backend();
        await mount(<ConstellationPage />);
        const text = $('.con-bound').textContent;
        expect(text).toContain('13');   // filed proposals
        expect(text).toContain('only the occlusion queue writes any of them down');
    });

    it('says a lone locus is a fact about filing, not about the world', async () => {
        backend({ walk: { ...WALK, nodes: [NODES[0]], edges: [],
                          tally: { nodes: 1, images: 1, edges: 0, by_span: {} } } });
        await mount(<ConstellationPage />);
        expect(container.textContent).toContain('what has been filed');
    });

    it('offers a legend in which every treatment is named in words', async () => {
        backend();
        await mount(<ConstellationPage />);
        const legend = $('.con-legend').textContent;
        for (const word of ['through', 'between', 'interpretive', 'not in any ledger', 'committed']) {
            expect(legend).toContain(word);
        }
    });
});

// ── 4. read-only ───────────────────────────────────────────────────────────

describe('the view only reads', () => {
    it('makes no request that is not a GET', async () => {
        const calls = backend();
        await mount(<ConstellationPage />);
        expect(calls.length).toBeGreaterThan(0);
        expect(calls.every((c) => c.startsWith('GET'))).toBe(true);
    });

    it('has no write path in its source', () => {
        // PRECISELY, not by keyword. The page RENDERS the words "committed" and "proposed" — they
        // are the ledger's vocabulary and it must be able to say them. A scan that could not tell
        // a rendered word from a request would force the view to stop explaining itself, which is
        // the same blunt-instrument mistake as grepping a docstring for what it refuses.
        const strip = (src) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
        for (const file of ['ConstellationPage.jsx', 'ConstellationGraph.jsx',
                            'constellationClient.js']) {
            const body = strip(fs.readFileSync(path.join(HERE, file), 'utf8'));
            // no request carries a method, so every fetch here is a GET
            expect(body).not.toMatch(/method\s*:/);
            expect(body).not.toMatch(/\bbody\s*:\s*JSON\.stringify/);
            // and nothing reaches the one surface that does write
            expect(body).not.toContain('curatorService');
            expect(body).not.toMatch(/commitProposal|\/commit/);
        }
    });
});
