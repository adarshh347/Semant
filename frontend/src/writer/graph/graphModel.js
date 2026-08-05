/**
 * Semant Writer · W3 — the operator graph, as data.
 *
 * NAMED `graphModel`, NOT `operatorGraph`. A module called `operatorGraph.js` sitting
 * beside the component `OperatorGraph.jsx` is the same path on a case-insensitive
 * filesystem (macOS by default), so the two imports resolved to whichever the bundler
 * reached first — the component came back `undefined` and React failed at mount with an
 * error that pointed nowhere near the cause. Keep the names distinct.
 *
 * Pure builders: the API's `{nodes, edges}` becomes React Flow's shape, and back again.
 * Kept apart from the component so the thing that actually matters here — that `requires`
 * reads as categorically different from the associative edges — is testable without
 * mounting a canvas.
 *
 * WHY THE VISUAL DIFFERENCE IS NOT DECORATION. `requires` is the only edge that feeds a
 * render. Every other kind is ontology structure the author can see and W4 will read, and
 * acting on one would be the blended-field composition Tier 3 reserves. An author who
 * cannot tell at a glance which edges change their prose cannot reason about their own
 * ontology, so the distinction is load-bearing and belongs in the data, not in a CSS file
 * someone might restyle.
 */

/** The edge vocabulary, mirroring `relations.RELATION_KINDS`. */
export const RELATION_KINDS = ['requires', 'precedes', 'evokes', 'amplifies', 'contrasts'];

/** The only kind that conditions a render (v1). Mirrors `relations.RENDERING_KINDS`. */
export const RENDERING_KINDS = ['requires'];

export function feedsRender(kind) {
  return RENDERING_KINDS.includes(kind);
}

/** One-line description per kind, for the legend and the picker. */
export const KIND_HELP = {
  requires: 'needs the other operator’s meaning present — this one shapes the render',
  precedes: 'tends to come before it (a note to yourself; it does not reorder anything)',
  evokes: 'calls it to mind',
  amplifies: 'intensifies it',
  contrasts: 'sets against it',
};

// Wide enough that adjacent nodes never touch — a clipped edge label is the one thing
// that makes the acts/inert distinction unreadable, which is the whole point of the view.
const GRID_X = 360;
const GRID_Y = 190;
const PER_ROW = 3;

/**
 * API nodes → React Flow nodes.
 *
 * `positions` carries any layout the author has already dragged into place; anything new
 * is laid out on a simple grid. Position asserts NOTHING about the ontology — exactly as
 * on the Atlas canvas, only a drawn edge is a claim — so it is not persisted with the
 * operator and losing it costs the author nothing but a rearrange.
 */
export function toFlowNodes(apiNodes = [], positions = {}) {
  return apiNodes.map((n, i) => ({
    id: n.id ?? n.name,
    type: 'operator',
    position: positions[n.id ?? n.name] ?? {
      x: (i % PER_ROW) * GRID_X,
      y: Math.floor(i / PER_ROW) * GRID_Y,
    },
    data: {
      name: n.name,
      version: n.version,
      definition: n.definition ?? '',
      renderingIntent: n.rendering_intent ?? '',
      examples: n.examples ?? [],
      negativeExamples: n.negative_examples ?? [],
    },
  }));
}

/** API edges → React Flow edges, with the rendering/inert distinction carried in the data. */
export function toFlowEdges(apiEdges = []) {
  return apiEdges.map((e) => {
    const acts = e.feeds_render ?? feedsRender(e.kind);
    return {
      id: `${e.source}::${e.kind}::${e.target}`,
      source: e.source,
      target: e.target,
      label: e.kind,
      // A `requires` edge is solid and arrowed because it acts; the associative kinds are
      // dashed because they describe without doing.
      animated: false,
      className: acts ? 'writer-edge writer-edge--acts' : 'writer-edge writer-edge--inert',
      style: acts ? undefined : { strokeDasharray: '5 4' },
      markerEnd: { type: 'arrowclosed' },
      data: { kind: e.kind, feedsRender: acts },
    };
  });
}

/**
 * The edge set for ONE operator, as the relations endpoint wants it.
 *
 * The API replaces an operator's whole edge set at once, so an edit has to send every
 * edge that operator still owns — not just the changed one.
 */
export function relationsFor(sourceName, flowEdges = []) {
  return flowEdges
    .filter((e) => e.source === sourceName)
    .map((e) => ({ target: e.target, kind: e.data?.kind ?? e.label }));
}

/** Every operator name an edge could point at, minus the source itself. */
export function targetsFor(sourceName, flowNodes = []) {
  return flowNodes.map((n) => n.id).filter((id) => id !== sourceName);
}

/**
 * Would adding `source --kind--> target` close a `requires` cycle?
 *
 * The server rejects it authoritatively (`relations.validate_relation`); this is the same
 * question asked locally so the author gets told while they are drawing rather than after
 * a round trip. It is a courtesy, never the guard — the server's answer is the one that
 * counts, and the component surfaces that too.
 */
/**
 * Decide what a drawn connection should do. `{ ok, error, edges }`.
 *
 * Pure, so the rules an author runs into while drawing are testable without a canvas — and
 * so the component stays a renderer. The SERVER still validates every one of these; this
 * exists to answer immediately rather than to be the guard.
 */
export function planConnection({ source, target, kind, edges = [] }) {
  if (!source || !target) {
    return { ok: false, error: 'An edge needs both ends.', edges };
  }
  if (source === target) {
    return { ok: false, error: `\`${source}\` cannot relate to itself.`, edges };
  }
  if (edges.some((e) => e.source === source && e.target === target
    && (e.data?.kind ?? e.label) === kind)) {
    return { ok: false, error: `\`${source} ${kind} ${target}\` already exists.`, edges };
  }
  if (wouldCycle(source, target, kind, edges)) {
    return {
      ok: false,
      error: `\`${source} requires ${target}\` would close a cycle. A required operator has `
        + 'to be renderable without waiting on the one requiring it.',
      edges,
    };
  }
  return {
    ok: true,
    error: '',
    edges: [...edges, {
      id: `${source}::${kind}::${target}`,
      source,
      target,
      label: kind,
      className: feedsRender(kind) ? 'writer-edge writer-edge--acts' : 'writer-edge writer-edge--inert',
      style: feedsRender(kind) ? undefined : { strokeDasharray: '5 4' },
      markerEnd: { type: 'arrowclosed' },
      data: { kind, feedsRender: feedsRender(kind) },
    }],
  };
}

export function wouldCycle(source, target, kind, flowEdges = []) {
  if (kind !== 'requires') return false;
  if (source === target) return true;

  const out = new Map();
  flowEdges
    .filter((e) => (e.data?.kind ?? e.label) === 'requires')
    .forEach((e) => {
      if (!out.has(e.source)) out.set(e.source, []);
      out.get(e.source).push(e.target);
    });
  if (!out.has(source)) out.set(source, []);
  out.get(source).push(target);

  const seen = new Set();
  const stack = [source];
  while (stack.length) {
    const name = stack.pop();
    for (const next of out.get(name) ?? []) {
      if (next === source) return true;
      if (seen.has(next)) continue;
      seen.add(next);
      stack.push(next);
    }
  }
  return false;
}
