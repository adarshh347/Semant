import { describe, it, expect } from 'vitest';
import { buildRecallScript, RECALL_TIMING } from './recall.js';
import { makeGround } from './grounds.js';
import { makeExpressionPercept } from '../state/perceptMentions.js';

const field = () => makeGround('field', { strokes: [{ points: [[0.5, 0.5]], radius: 0.05, strength: 0.8, op: 'add' }] });

describe('buildRecallScript — recede → primary → supporting (stagger) → expression', () => {
  it('stages one ground after the recede, then the expression', () => {
    const g = field();
    const p = makeExpressionPercept({ expression: 'the light pools', ground_ids: [g.id] });
    const { steps, total } = buildRecallScript(p, (id) => (id === g.id ? g : null));
    expect(steps.map((s) => s.kind)).toEqual(['recede', 'ground', 'expression']);
    expect(steps[1]).toMatchObject({ groundId: g.id, role: 'primary', at: RECALL_TIMING.recede });
    expect(steps[2].at).toBeGreaterThan(steps[1].at);
    expect(total).toBeGreaterThan(steps[2].at);
  });

  it('supporting grounds stagger in after the primary', () => {
    const a = field(); const b = field(); const c = field();
    const p = makeExpressionPercept({ expression: 'x', ground_ids: [a.id, b.id, c.id] });
    const byId = Object.fromEntries([a, b, c].map((g) => [g.id, g]));
    const { steps } = buildRecallScript(p, (id) => byId[id] || null);
    const grounds = steps.filter((s) => s.kind === 'ground');
    expect(grounds.map((s) => s.role)).toEqual(['primary', 'supporting', 'supporting']);
    expect(grounds[1].at).toBeGreaterThan(grounds[0].at);
    expect(grounds[2].at - grounds[1].at).toBe(RECALL_TIMING.stagger);
  });

  it('a deleted ground drops out of the performance instead of breaking it', () => {
    const g = field();
    const p = makeExpressionPercept({ expression: 'x', ground_ids: [g.id, 'gnd_gone'] });
    const { steps } = buildRecallScript(p, (id) => (id === g.id ? g : null));
    expect(steps.filter((s) => s.kind === 'ground')).toHaveLength(1);
    expect(steps.at(-1).kind).toBe('expression');
  });

  it('an empty percept still recedes and speaks (nothing to perform)', () => {
    const p = makeExpressionPercept({ expression: 'x', ground_ids: [] });
    const { steps } = buildRecallScript(p, () => null);
    expect(steps.map((s) => s.kind)).toEqual(['recede', 'expression']);
  });

  it('a composition expands into itself, then its members (sequenced)', () => {
    const a = field(); const b = field();
    const c = makeGround('constellation', { member_ids: [a.id, b.id] });
    const byId = Object.fromEntries([a, b, c].map((g) => [g.id, g]));
    const p = makeExpressionPercept({ expression: 'a cluster', ground_ids: [c.id] });
    const { steps } = buildRecallScript(p, (id) => byId[id] || null);
    const gs = steps.filter((s) => s.kind === 'ground');
    expect(gs.map((s) => s.groundId)).toEqual([c.id, a.id, b.id]); // composition first
    expect(gs[0].role).toBe('primary');
  });

  it('does not double-stage a member also named directly in the percept', () => {
    const a = field();
    const c = makeGround('relation', { member_ids: [a.id], relation_label: 'x' });
    const byId = Object.fromEntries([a, c].map((g) => [g.id, g]));
    const p = makeExpressionPercept({ expression: 'x', ground_ids: [c.id, a.id] });
    const { steps } = buildRecallScript(p, (id) => byId[id] || null);
    const ids = steps.filter((s) => s.kind === 'ground').map((s) => s.groundId);
    expect(ids).toEqual([c.id, a.id]); // a appears once
  });
});
