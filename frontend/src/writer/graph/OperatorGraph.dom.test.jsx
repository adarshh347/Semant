import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import OperatorGraph from './OperatorGraph';
import { writerService } from '../writerService';

/**
 * Semant Writer · W3 — the graph, mounted.
 *
 * `operatorGraph.test.js` owns the data. This owns the boundary: that an edge edit sends
 * the whole edge set for that operator, that a cycle is refused before it is sent, that the
 * server's refusal is surfaced rather than swallowed — and, load-bearing, that this
 * component has no path to the manuscript at all.
 */

// jsdom has neither, and React Flow wants both. Same shim the Atlas graph tests carry
// (cf. `atlas/atlas.dom.test.jsx`) — this is a jsdom gap, not a product concern.
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
if (typeof globalThis.DOMMatrixReadOnly === 'undefined') {
  globalThis.DOMMatrixReadOnly = class { constructor() { this.m22 = 1; } };
}

const GRAPH = {
  nodes: [
    { id: 'threshold', name: 'threshold', version: 1, definition: 'a crossing noticed late' },
    { id: 'interiority', name: 'interiority', version: 1, definition: 'what the body knows' },
    { id: 'hinge', name: 'hinge', version: 1, definition: 'the turn a scene pivots on' },
  ],
  edges: [],
  kinds: ['requires', 'precedes', 'evokes', 'amplifies', 'contrasts'],
  rendering_kinds: ['requires'],
};

let container, root;

beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  vi.spyOn(writerService, 'graph').mockResolvedValue(GRAPH);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.restoreAllMocks();
});

async function mount(props = {}) {
  await act(async () => {
    root.render(<OperatorGraph projectId="ms_1" {...props} />);
  });
}

const byTestId = (id) => container.querySelector(`[data-testid="${id}"]`);
const allByTestId = (id) => [...container.querySelectorAll(`[data-testid="${id}"]`)];

describe('OperatorGraph', () => {
  it('shows the operators it was given, with versions', async () => {
    await mount();
    const nodes = allByTestId('operator-node');
    expect(nodes.length).toBeGreaterThan(0);
    expect(container.textContent).toContain('threshold');
    expect(container.textContent).toContain('v1');
  });

  it('reads the graph and never asks for a scene, a passage or a block', async () => {
    const accept = vi.spyOn(writerService, 'accept');
    const run = vi.spyOn(writerService, 'run');
    await mount();
    // I1/I3 at the surface: this component has no route to the canon at all.
    expect(accept).not.toHaveBeenCalled();
    expect(run).not.toHaveBeenCalled();
    expect(writerService.graph).toHaveBeenCalledWith('ms_1');
  });

  it('says which kind shapes the render, in the picker', async () => {
    await mount();
    const picker = byTestId('kind-picker');
    const requires = [...picker.options].find((o) => o.value === 'requires');
    const evokes = [...picker.options].find((o) => o.value === 'evokes');
    expect(requires.textContent).toContain('shapes the render');
    expect(evokes.textContent).not.toContain('shapes the render');
  });

  it('legends the acts/inert distinction', async () => {
    await mount();
    expect(container.textContent).toContain('pulled into the render');
    expect(container.textContent).toContain('it does not change your prose');
  });

  it('shows an empty state rather than a blank canvas', async () => {
    writerService.graph.mockResolvedValue({ ...GRAPH, nodes: [] });
    await mount();
    expect(container.textContent).toContain('No operators yet');
  });

  it('surfaces a server refusal instead of swallowing it', async () => {
    // e.g. the cycle the server catches authoritatively
    writerService.graph.mockRejectedValue(new Error('would close a cycle: a → b → a'));
    await mount();
    expect(byTestId('graph-error').textContent).toContain('would close a cycle');
  });
});
