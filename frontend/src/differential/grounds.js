/**
 * Ground — how visual evidence occupies the image (Differential v1).
 *
 * Pure helpers; the shared store (`regionStore`) wires them into state and the
 * backend persists them as `post.grounds` (List[dict] — deliberately NOT inside
 * `region_annotations`, which detect-regions wholesale-replaces).
 *
 * Record shape (normalized coords, natural-image space, top-left origin):
 *   { id:'gnd_…', ground_type, actor:'creator'|'auto'|'audience', detector,
 *     label:'', note:'', created_at, …per-type fields }
 *
 * Spatial primitives: region (adapter → region_id), field (strokes), path (points),
 * boundary (points + band_width), frame (whole:true + evidence_ids).
 * Compositions: constellation (member_ids + raw points), relation (member_ids +
 * relation_label). Compositions reference members by id — no flat geometry union.
 *
 * A region-adapter Ground stores ONLY `region_id`. If a re-dissect replaces that
 * Region, the Ground degrades gracefully: `resolveGround` marks it detached, it
 * renders nothing, and inspectors list it as "detached evidence".
 */

export const GROUND_TYPES = [
  'region', 'field', 'path', 'boundary', 'constellation', 'relation', 'frame',
];

export const SPATIAL_TYPES = new Set(['region', 'field', 'path', 'boundary', 'frame']);
export const COMPOSITE_TYPES = new Set(['constellation', 'relation']);

// Monotonic tail so two grounds made in the same millisecond never collide.
let groundSeq = 0;

export function groundId() {
  return `gnd_${Date.now().toString(36)}_${(groundSeq++).toString(36)}`;
}

/** Every creation point flows through here so provenance is always stamped. */
export function makeGround(ground_type, fields = {}) {
  if (!GROUND_TYPES.includes(ground_type)) {
    throw new Error(`Unknown ground_type: ${ground_type}`);
  }
  return {
    id: groundId(),
    ground_type,
    actor: 'creator',
    detector: null,
    label: '',
    note: '',
    created_at: new Date().toISOString(),
    ...fields,
  };
}

/** The Region adapter — reference, not duplication. Geometry stays on the Region. */
export function groundFromRegion(regionId, fields = {}) {
  return makeGround('region', { region_id: regionId, ...fields });
}

export const isSpatialGround = (g) => !!g && SPATIAL_TYPES.has(g.ground_type);
export const isCompositeGround = (g) => !!g && COMPOSITE_TYPES.has(g.ground_type);

/**
 * Resolve a Ground against the live regions + its sibling grounds.
 * Returns { ground, region|null, members: Ground[], detached: boolean }.
 * - region adapter: detached when its region_id no longer resolves (re-dissect).
 * - compositions: members resolve by id; missing members are simply absent, and
 *   the composition is detached only when NO member survives.
 */
export function resolveGround(ground, { regions = [], grounds = [] } = {}) {
  if (!ground) return null;
  if (ground.ground_type === 'region') {
    const region = regions.find((r) => r.id === ground.region_id) || null;
    return { ground, region, members: [], detached: !region };
  }
  if (isCompositeGround(ground)) {
    const members = (ground.member_ids || [])
      .map((id) => grounds.find((g) => g.id === id))
      .filter(Boolean);
    const hasRawPoints = (ground.points || []).length > 0;
    return {
      ground, region: null, members,
      detached: (ground.member_ids || []).length > 0 && members.length === 0 && !hasRawPoints,
    };
  }
  return { ground, region: null, members: [], detached: false };
}

// ── bbox (normalized) — for Mention hover crops and fit-to-ground later ──────

const bboxOfPoints = (pts) => {
  if (!pts?.length) return null;
  let x0 = 1, y0 = 1, x1 = 0, y1 = 0;
  for (const p of pts) {
    const [x, y] = Array.isArray(p) ? p : [p.x, p.y];
    if (x < x0) x0 = x; if (y < y0) y0 = y;
    if (x > x1) x1 = x; if (y > y1) y1 = y;
  }
  return { x: x0, y: y0, w: Math.max(0, x1 - x0), h: Math.max(0, y1 - y0) };
};

const unionBoxes = (boxes) => {
  const bs = boxes.filter(Boolean);
  if (!bs.length) return null;
  const x0 = Math.min(...bs.map((b) => b.x));
  const y0 = Math.min(...bs.map((b) => b.y));
  const x1 = Math.max(...bs.map((b) => b.x + b.w));
  const y1 = Math.max(...bs.map((b) => b.y + b.h));
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
};

const clamp01Box = (b) => {
  if (!b) return null;
  const x = Math.max(0, b.x), y = Math.max(0, b.y);
  return { x, y, w: Math.min(1 - x, b.w), h: Math.min(1 - y, b.h) };
};

/** Normalized bounding box of a Ground's evidence, or null when unresolvable. */
export function groundBBox(ground, ctx = {}) {
  const res = resolveGround(ground, ctx);
  if (!res || res.detached) return null;
  const g = ground;
  switch (g.ground_type) {
    case 'region':
      return res.region?.box || null;
    case 'field': {
      const boxes = (g.strokes || []).map((s) => {
        const b = bboxOfPoints(s.points);
        if (!b) return null;
        const r = s.radius || 0;
        return { x: b.x - r, y: b.y - r, w: b.w + 2 * r, h: b.h + 2 * r };
      });
      return clamp01Box(unionBoxes(boxes));
    }
    case 'path':
    case 'boundary':
      return bboxOfPoints(g.points);
    case 'frame':
      return { x: 0, y: 0, w: 1, h: 1 };
    case 'constellation':
    case 'relation': {
      const memberBoxes = res.members.map((m) => groundBBox(m, ctx));
      const raw = bboxOfPoints(g.points);
      return unionBoxes([...memberBoxes, raw]);
    }
    default:
      return null;
  }
}

/**
 * Hydrate a stored grounds array: keep well-formed records (id + known type),
 * preserve unknown extra fields verbatim. Malformed entries are dropped rather
 * than allowed to break every renderer downstream.
 */
export function hydrateGrounds(raw) {
  if (!Array.isArray(raw)) return [];
  return raw.filter((g) => g && typeof g.id === 'string' && GROUND_TYPES.includes(g.ground_type));
}
