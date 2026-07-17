import { describe, it, expect } from 'vitest';
import {
  GROUND_TYPES, makeGround, groundFromRegion,
  isSpatialGround, isCompositeGround,
  resolveGround, groundBBox, hydrateGrounds,
} from './grounds.js';

const region = (id, box = { x: 0.2, y: 0.2, w: 0.3, h: 0.4 }) => ({ id, box, label: 'part' });

describe('makeGround — provenance always stamped', () => {
  it('stamps id, actor, detector and created_at on every type', () => {
    for (const t of GROUND_TYPES) {
      const g = makeGround(t);
      expect(g.id).toMatch(/^gnd_/);
      expect(g).toMatchObject({ ground_type: t, actor: 'creator', detector: null });
      expect(typeof g.created_at).toBe('string');
    }
  });

  it('rejects an unknown type instead of storing a lie', () => {
    expect(() => makeGround('blob')).toThrow();
  });

  it('two grounds made back-to-back never share an id', () => {
    expect(makeGround('field').id).not.toBe(makeGround('field').id);
  });

  it('classifies spatial vs compositional honestly', () => {
    expect(isSpatialGround(makeGround('field'))).toBe(true);
    expect(isSpatialGround(makeGround('frame'))).toBe(true);
    expect(isCompositeGround(makeGround('constellation'))).toBe(true);
    expect(isCompositeGround(makeGround('relation'))).toBe(true);
    expect(isCompositeGround(makeGround('path'))).toBe(false);
  });
});

describe('serialize → hydrate round-trip (each type survives storage as plain JSON)', () => {
  const samples = [
    groundFromRegion('reg_1'),
    makeGround('field', { strokes: [{ points: [[0.1, 0.1, 0.5], [0.2, 0.15]], radius: 0.05, strength: 0.8, op: 'add' }] }),
    makeGround('path', { points: [[0.1, 0.9], [0.5, 0.5], [0.9, 0.1]], arrowhead: true }),
    makeGround('boundary', { points: [[0.0, 0.5], [1.0, 0.5]], band_width: 0.08 }),
    makeGround('constellation', { member_ids: ['gnd_a'], points: [{ x: 0.3, y: 0.3 }] }),
    makeGround('relation', { member_ids: ['gnd_a', 'gnd_b'], relation_label: 'answers' }),
    makeGround('frame', { whole: true, evidence_ids: ['gnd_a'] }),
  ];

  it('every type comes back identical through JSON', () => {
    const hydrated = hydrateGrounds(JSON.parse(JSON.stringify(samples)));
    expect(hydrated).toEqual(samples);
  });

  it('hydrate drops malformed records but keeps unknown extra fields', () => {
    const good = { ...makeGround('path', { points: [[0, 0]] }), future_field: 'kept' };
    const hydrated = hydrateGrounds([good, { ground_type: 'path' }, null, { id: 'x', ground_type: 'blob' }]);
    expect(hydrated).toEqual([good]);
    expect(hydrated[0].future_field).toBe('kept');
  });

  it('hydrate tolerates a missing/absent array', () => {
    expect(hydrateGrounds(undefined)).toEqual([]);
    expect(hydrateGrounds(null)).toEqual([]);
  });
});

describe('region adapter — reference, not duplication', () => {
  it('resolves its region when it exists', () => {
    const g = groundFromRegion('reg_1');
    const res = resolveGround(g, { regions: [region('reg_1')] });
    expect(res.region.id).toBe('reg_1');
    expect(res.detached).toBe(false);
  });

  it('degrades gracefully when a re-dissect replaced the region', () => {
    const g = groundFromRegion('reg_gone');
    const res = resolveGround(g, { regions: [region('reg_other')] });
    expect(res.region).toBeNull();
    expect(res.detached).toBe(true);
    expect(groundBBox(g, { regions: [region('reg_other')] })).toBeNull();
  });
});

describe('constellation / relation membership', () => {
  const a = makeGround('path', { points: [[0.1, 0.1], [0.2, 0.2]] });
  const b = groundFromRegion('reg_1');
  const grounds = [a, b];
  const regions = [region('reg_1')];

  it('membership survives the round-trip and resolves member grounds', () => {
    const c = makeGround('constellation', { member_ids: [a.id, b.id] });
    const [hydrated] = hydrateGrounds(JSON.parse(JSON.stringify([c])));
    const res = resolveGround(hydrated, { regions, grounds });
    expect(res.members.map((m) => m.id)).toEqual([a.id, b.id]);
    expect(res.detached).toBe(false);
  });

  it('a deleted member degrades the composition, not the archive', () => {
    const c = makeGround('relation', { member_ids: [a.id, 'gnd_deleted'] });
    const res = resolveGround(c, { regions, grounds });
    expect(res.members.map((m) => m.id)).toEqual([a.id]); // survivor kept
    expect(res.detached).toBe(false);                     // still evidence
    const all = makeGround('relation', { member_ids: ['gnd_x', 'gnd_y'] });
    expect(resolveGround(all, { regions, grounds }).detached).toBe(true);
  });
});

describe('groundBBox — normalized union of the evidence', () => {
  it('region → the region box; frame → the whole image', () => {
    const g = groundFromRegion('reg_1');
    expect(groundBBox(g, { regions: [region('reg_1')] })).toEqual({ x: 0.2, y: 0.2, w: 0.3, h: 0.4 });
    expect(groundBBox(makeGround('frame', { whole: true }), {})).toEqual({ x: 0, y: 0, w: 1, h: 1 });
  });

  it('field pads its stroke points by the brush radius, clamped to the image', () => {
    const g = makeGround('field', { strokes: [{ points: [[0.05, 0.5]], radius: 0.1, strength: 1, op: 'add' }] });
    const b = groundBBox(g, {});
    expect(b.x).toBe(0);                       // 0.05 - 0.1 clamps to the edge
    expect(b.y).toBeCloseTo(0.4);
  });

  it('composition bbox unions members and raw points', () => {
    const p = makeGround('path', { points: [[0.1, 0.1], [0.3, 0.3]] });
    const c = makeGround('constellation', { member_ids: [p.id], points: [{ x: 0.9, y: 0.9 }] });
    const b = groundBBox(c, { grounds: [p], regions: [] });
    expect(b).toEqual({ x: 0.1, y: 0.1, w: 0.8, h: 0.8 });
  });
});
