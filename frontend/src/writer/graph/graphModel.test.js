import { describe, it, expect } from 'vitest';
import {
  RELATION_KINDS,
  RENDERING_KINDS,
  feedsRender,
  planConnection,
  relationsFor,
  targetsFor,
  toFlowEdges,
  toFlowNodes,
  wouldCycle,
} from './graphModel';

/**
 * Semant Writer · W3 — the graph as data.
 *
 * The thing worth pinning here is the ACTS/INERT distinction. `requires` is the only edge
 * that conditions a render; if the graph ever stopped carrying that difference in its data,
 * the author would be looking at five kinds of line that all look equally consequential and
 * would have no way to reason about which ones change their prose.
 */

describe('the edge vocabulary', () => {
  it('matches the backend, and exactly one kind acts', () => {
    expect(RELATION_KINDS).toEqual(['requires', 'precedes', 'evokes', 'amplifies', 'contrasts']);
    expect(RENDERING_KINDS).toEqual(['requires']);
    expect(feedsRender('requires')).toBe(true);
    ['precedes', 'evokes', 'amplifies', 'contrasts'].forEach((k) => {
      expect(feedsRender(k)).toBe(false);
    });
  });
});

describe('toFlowEdges', () => {
  it('carries the acts/inert distinction in the data, not only in CSS', () => {
    const [acts, inert] = toFlowEdges([
      { source: 'interiority', target: 'threshold', kind: 'requires', feeds_render: true },
      { source: 'interiority', target: 'threshold', kind: 'evokes', feeds_render: false },
    ]);

    expect(acts.data.feedsRender).toBe(true);
    expect(acts.className).toContain('writer-edge--acts');
    expect(acts.style?.strokeDasharray).toBeUndefined();

    expect(inert.data.feedsRender).toBe(false);
    expect(inert.className).toContain('writer-edge--inert');
    expect(inert.style.strokeDasharray).toBeTruthy();
  });

  it('derives acts/inert from the kind when the server did not say', () => {
    const [edge] = toFlowEdges([{ source: 'a', target: 'b', kind: 'requires' }]);
    expect(edge.data.feedsRender).toBe(true);
  });

  it('gives an edge an id that distinguishes two kinds between the same pair', () => {
    const [a, b] = toFlowEdges([
      { source: 'x', target: 'y', kind: 'requires' },
      { source: 'x', target: 'y', kind: 'evokes' },
    ]);
    expect(a.id).not.toBe(b.id);
  });
});

describe('toFlowNodes', () => {
  it('keeps a layout the author has already dragged into place', () => {
    const api = [{ id: 'threshold', name: 'threshold', version: 2, definition: 'd' }];
    const [node] = toFlowNodes(api, { threshold: { x: 42, y: 99 } });
    expect(node.position).toEqual({ x: 42, y: 99 });
    expect(node.data.version).toBe(2);
  });

  it('lays out anything new on a grid', () => {
    const api = [{ id: 'a', name: 'a' }, { id: 'b', name: 'b' }];
    const nodes = toFlowNodes(api);
    expect(nodes[0].position).not.toEqual(nodes[1].position);
  });
});

describe('relationsFor', () => {
  it('returns the whole edge set for one operator — the API replaces, not appends', () => {
    const edges = toFlowEdges([
      { source: 'interiority', target: 'threshold', kind: 'requires' },
      { source: 'interiority', target: 'hinge', kind: 'evokes' },
      { source: 'threshold', target: 'hinge', kind: 'requires' },
    ]);
    expect(relationsFor('interiority', edges)).toEqual([
      { target: 'threshold', kind: 'requires' },
      { target: 'hinge', kind: 'evokes' },
    ]);
  });

  it('is empty for an operator with no outgoing edges', () => {
    expect(relationsFor('hinge', toFlowEdges([{ source: 'a', target: 'b', kind: 'requires' }])))
      .toEqual([]);
  });
});

describe('targetsFor', () => {
  it('offers every other operator, never the source itself', () => {
    const nodes = toFlowNodes([{ id: 'a', name: 'a' }, { id: 'b', name: 'b' }]);
    expect(targetsFor('a', nodes)).toEqual(['b']);
  });
});

describe('planConnection — the rules the author meets while drawing', () => {
  const existing = toFlowEdges([{ source: 'interiority', target: 'threshold', kind: 'requires' }]);

  it('adds the edge when it is legal, carrying acts/inert', () => {
    const plan = planConnection({
      source: 'threshold', target: 'hinge', kind: 'requires', edges: existing,
    });
    expect(plan.ok).toBe(true);
    expect(plan.edges).toHaveLength(2);
    expect(plan.edges[1].data).toEqual({ kind: 'requires', feedsRender: true });
  });

  it('refuses a cycle, with the reason', () => {
    const plan = planConnection({
      source: 'threshold', target: 'interiority', kind: 'requires', edges: existing,
    });
    expect(plan.ok).toBe(false);
    expect(plan.error).toContain('would close a cycle');
    expect(plan.edges).toEqual(existing);      // nothing added
  });

  it('refuses self-reference', () => {
    const plan = planConnection({ source: 'a', target: 'a', kind: 'requires', edges: [] });
    expect(plan.ok).toBe(false);
    expect(plan.error).toContain('cannot relate to itself');
  });

  it('refuses a duplicate of the same kind, but allows a second KIND between the same pair', () => {
    expect(planConnection({
      source: 'interiority', target: 'threshold', kind: 'requires', edges: existing,
    }).ok).toBe(false);

    expect(planConnection({
      source: 'interiority', target: 'threshold', kind: 'evokes', edges: existing,
    }).ok).toBe(true);
  });

  it('lets an associative edge close a loop, because it does not feed rendering', () => {
    // `a requires b` plus `b evokes a` is not a rendering cycle — nothing is pulled.
    const plan = planConnection({
      source: 'threshold', target: 'interiority', kind: 'evokes', edges: existing,
    });
    expect(plan.ok).toBe(true);
    expect(plan.edges[1].data.feedsRender).toBe(false);
  });
});

describe('wouldCycle', () => {
  const edges = (pairs) =>
    toFlowEdges(pairs.map(([source, target, kind = 'requires']) => ({ source, target, kind })));

  it('catches a direct cycle', () => {
    expect(wouldCycle('threshold', 'interiority', 'requires',
      edges([['interiority', 'threshold']]))).toBe(true);
  });

  it('catches a transitive cycle', () => {
    expect(wouldCycle('hinge', 'interiority', 'requires',
      edges([['interiority', 'threshold'], ['threshold', 'hinge']]))).toBe(true);
  });

  it('catches self-reference', () => {
    expect(wouldCycle('a', 'a', 'requires', [])).toBe(true);
  });

  it('permits a diamond', () => {
    expect(wouldCycle('b', 'c', 'requires', edges([['a', 'b'], ['a', 'c']]))).toBe(false);
  });

  it('ignores associative edges — only `requires` can close a rendering cycle', () => {
    // `a evokes b` and `b requires a` is not a cycle in the graph that feeds rendering.
    expect(wouldCycle('b', 'a', 'requires', edges([['a', 'b', 'evokes']]))).toBe(false);
    expect(wouldCycle('b', 'a', 'evokes', edges([['a', 'b']]))).toBe(false);
  });
});
