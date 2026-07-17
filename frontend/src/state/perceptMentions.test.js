import { describe, it, expect } from 'vitest';
import {
  makePercept, upsertPercept, perceptForRegion, perceptId,
  makeExpressionPercept, isExpressionPercept, perceptsForGround,
  makeMention, addMention, removeMentionsForBlock,
  mentionsForBlock, mentionsForRegion, mentionsForPercept,
  blockIdsForRegion, mentionsFromBlocks,
} from './perceptMentions.js';

const region = (id, extra = {}) => ({ id, label: 'shoulder drape', ...extra });

describe('Percept (one creator percept per region per post)', () => {
  it('builds a thin percept from a region', () => {
    const p = makePercept(region('reg_1', { user_note: 'severe' }));
    expect(p).toMatchObject({ id: 'pct_creator_reg_1', regionId: 'reg_1', label: 'shoulder drape', note: 'severe', actor: 'creator' });
  });

  it('upsert is idempotent by (region, actor) — re-attending does not duplicate', () => {
    let ps = [];
    ps = upsertPercept(ps, makePercept(region('reg_1')));
    ps = upsertPercept(ps, makePercept(region('reg_1'), { actor: 'creator' }));
    expect(ps).toHaveLength(1);
    expect(perceptForRegion(ps, 'reg_1')).toBeTruthy();
  });

  it('different actors on the same region are distinct percepts', () => {
    let ps = [];
    ps = upsertPercept(ps, makePercept(region('reg_1'), { actor: 'creator' }));
    ps = upsertPercept(ps, makePercept(region('reg_1'), { actor: 'audience' }));
    expect(ps).toHaveLength(2);
    expect(perceptId('reg_1', 'audience')).toBe('pct_audience_reg_1');
  });
});

describe('Mention (region↔block join, many-to-many)', () => {
  it('addMention is idempotent per edge (same chip re-inserted → one link)', () => {
    let ms = [];
    const men = makeMention({ regionId: 'reg_1', blockId: 'block_a', inlineContentId: 'ic_1', form: 'inline' });
    ms = addMention(ms, men);
    ms = addMention(ms, makeMention({ regionId: 'reg_1', blockId: 'block_a', inlineContentId: 'ic_1', form: 'inline' }));
    expect(ms).toHaveLength(1);
  });

  it('distinguishes two refs in one block via inlineContentId', () => {
    let ms = [];
    ms = addMention(ms, makeMention({ regionId: 'reg_1', blockId: 'block_a', inlineContentId: 'ic_1', form: 'inline' }));
    ms = addMention(ms, makeMention({ regionId: 'reg_2', blockId: 'block_a', inlineContentId: 'ic_2', form: 'inline' }));
    expect(mentionsForBlock(ms, 'block_a')).toHaveLength(2);
  });

  it('a region cited in two blocks resolves both', () => {
    let ms = [];
    ms = addMention(ms, makeMention({ regionId: 'reg_1', blockId: 'block_a', form: 'block' }));
    ms = addMention(ms, makeMention({ regionId: 'reg_1', blockId: 'block_b', form: 'block' }));
    expect(mentionsForRegion(ms, 'reg_1').map((m) => m.blockId).sort()).toEqual(['block_a', 'block_b']);
  });

  it('removeMentionsForBlock drops a block’s edges', () => {
    let ms = [makeMention({ regionId: 'reg_1', blockId: 'block_a' }), makeMention({ regionId: 'reg_2', blockId: 'block_b' })].reduce(addMention, []);
    ms = removeMentionsForBlock(ms, 'block_a');
    expect(ms).toHaveLength(1);
    expect(ms[0].blockId).toBe('block_b');
  });
});

describe('blockIdsForRegion — unions Mentions AND the primary Region.block_id', () => {
  it('degrades gracefully: block_id-only region still lights up', () => {
    const regions = [region('reg_1', { block_id: 'block_primary' })];
    const ids = blockIdsForRegion([], regions, 'reg_1');
    expect([...ids]).toEqual(['block_primary']);
  });

  it('unions both sources without duplication', () => {
    const regions = [region('reg_1', { block_id: 'block_primary' })];
    const ms = [makeMention({ regionId: 'reg_1', blockId: 'block_x' }), makeMention({ regionId: 'reg_1', blockId: 'block_primary' })].reduce(addMention, []);
    expect([...blockIdsForRegion(ms, regions, 'reg_1')].sort()).toEqual(['block_primary', 'block_x']);
  });
});

describe('mentionsFromBlocks — reconstruct edges from stored chip markup (no data loss)', () => {
  it('parses data-region-ids out of block HTML into mentions', () => {
    const blocks = [
      { id: 'block_a', content: '<p>The <span data-region-ref data-region-ids="reg_1" data-label="drape">drape</span> holds.</p>' },
      { id: 'block_b', content: '<p><span data-region-ref data-region-ids="reg_2,reg_3" data-label="lens">Phenomenological</span> reads.</p>' },
    ];
    const ms = mentionsFromBlocks(blocks);
    expect(mentionsForBlock(ms, 'block_a')).toHaveLength(1);
    expect(mentionsForBlock(ms, 'block_b').map((m) => m.regionId).sort()).toEqual(['reg_2', 'reg_3']);
    expect(mentionsForRegion(ms, 'reg_1')[0].blockId).toBe('block_a');
  });

  it('handles empty / chip-less stories', () => {
    expect(mentionsFromBlocks([])).toEqual([]);
    expect(mentionsFromBlocks([{ id: 'b', content: '<p>plain</p>' }])).toEqual([]);
  });
});

describe('Expression Percept (Differential v1) — many-to-many-to-many', () => {
  it('builds a pctx percept over ground ids, provenance stamped', () => {
    const p = makeExpressionPercept({ expression: 'the light pools here', ground_ids: ['gnd_1', 'gnd_2'], properties: ['light'] });
    expect(p.id).toMatch(/^pctx_/);
    expect(p).toMatchObject({ kind: 'expression', expression: 'the light pools here', ground_ids: ['gnd_1', 'gnd_2'], properties: ['light'], actor: 'creator' });
    expect(typeof p.created_at).toBe('string');
  });

  it('is a NEW kind: attention percepts are not expression percepts, and vice versa', () => {
    expect(isExpressionPercept(makePercept({ id: 'reg_1', label: 'drape' }))).toBe(false);
    expect(isExpressionPercept(makeExpressionPercept({ expression: 'x' }))).toBe(true);
    // A stored record hydrates by id prefix even if `kind` was stripped.
    expect(isExpressionPercept({ id: 'pctx_abc', expression: 'x' })).toBe(true);
  });

  it('many percepts per ground — NO per-ground uniqueness', () => {
    const a = makeExpressionPercept({ expression: 'first noticing', ground_ids: ['gnd_1'] });
    const b = makeExpressionPercept({ expression: 'second noticing', ground_ids: ['gnd_1'] });
    expect(a.id).not.toBe(b.id);
    expect(perceptsForGround([a, b], 'gnd_1')).toHaveLength(2);
  });

  it('many grounds per percept, and ground queries skip attention percepts', () => {
    const p = makeExpressionPercept({ expression: 'x', ground_ids: ['gnd_1', 'gnd_2', 'gnd_3'] });
    const attention = makePercept({ id: 'gnd_1', label: 'not really a ground' }); // pct_, ignored
    expect(perceptsForGround([p, attention], 'gnd_2')).toEqual([p]);
    expect(perceptsForGround([p], 'gnd_9')).toEqual([]);
  });

  it('many mentions per percept — the existing Mention machinery carries pctx ids as-is', () => {
    const p = makeExpressionPercept({ expression: 'x', ground_ids: ['gnd_1'] });
    let ms = [];
    ms = addMention(ms, makeMention({ perceptId: p.id, blockId: 'block_a', inlineContentId: 'ic_1', form: 'inline' }));
    ms = addMention(ms, makeMention({ perceptId: p.id, blockId: 'block_b', inlineContentId: 'ic_2', form: 'inline' }));
    expect(mentionsForPercept(ms, p.id)).toHaveLength(2);
  });

  it('survives the storage round-trip (plain JSON, nothing lost)', () => {
    const p = makeExpressionPercept({ expression: 'x', ground_ids: ['gnd_1'], properties: ['colour', 'repetition'] });
    expect(JSON.parse(JSON.stringify(p))).toEqual(p);
  });
});
