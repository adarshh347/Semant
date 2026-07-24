import { describe, it, expect } from 'vitest';
import {
  makePercept, upsertPercept, perceptForRegion, perceptId,
  makeExpressionPercept, isExpressionPercept, perceptsForGround,
  makeMention, addMention, removeMentionsForBlock,
  mentionsForBlock, mentionsForRegion, mentionsForPercept, mentionsForMark, mentionsForPost,
  blockIdsForRegion, mentionsFromBlocks, blockIdsForPercept,
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

// ── CIRCUIT-001 P1A · Part B — lossless reconstruction ───────────────────────
// The chip has always round-tripped percept id, mention id, ref kind and label
// (blockConvert.test.js proves the markup survives). What did not survive was
// the READ: mentionsFromBlocks parsed one attribute and defaulted the rest, so
// a percept citation came back as an anonymous region edge. These tests pin the
// read, and each of them failed before this change.
describe('mentionsFromBlocks — percept identity survives the markup round-trip', () => {
  const chip = (attrs) =>
    `<p>text <span data-region-ref="" ${attrs}>label</span> more</p>`;

  it('recovers the percept id, so a manuscript chip can find its percept', () => {
    const blocks = [{ id: 'blk1', content: chip('data-inline-type="percept" data-region-ids="gnd_1,gnd_2" data-percept-id="pctx_abc" data-label="the upper head"') }];
    const [men] = mentionsFromBlocks(blocks);
    expect(men.perceptId).toBe('pctx_abc');
    expect(men.refKind).toBe('percept');
    expect(men.label).toBe('the upper head');
    expect(men.blockId).toBe('blk1');
  });

  it('mints ONE edge for a percept chip, not one per ground id', () => {
    // The ids on a /percept chip are GROUND ids. Splitting per id would create
    // region edges pointing at gnd_… — links to something that is not a region.
    const blocks = [{ id: 'blk1', content: chip('data-region-ids="gnd_1,gnd_2,gnd_3" data-percept-id="pctx_abc"') }];
    const out = mentionsFromBlocks(blocks);
    expect(out).toHaveLength(1);
    expect(out[0].perceptId).toBe('pctx_abc');
  });

  it('keeps the id the markup carries, so it is stable across a reload', () => {
    const stored = 'men_pctx_abc_blk1_ic_lx8f_0';
    const blocks = [{ id: 'blk1', content: chip(`data-region-ids="gnd_1" data-percept-id="pctx_abc" data-mention-id="${stored}"`) }];
    expect(mentionsFromBlocks(blocks)[0].id).toBe(stored);
    // Reconstructing twice is the same edge, not two.
    expect(mentionsFromBlocks([...blocks, ...blocks])).toHaveLength(1);
  });

  it('BACK-COMPAT: a chip with no percept id still yields one region edge per id', () => {
    const blocks = [{ id: 'blk1', content: chip('data-region-ids="region_1,region_2" data-inline-type="part"') }];
    const out = mentionsFromBlocks(blocks);
    expect(out.map((m) => m.regionId)).toEqual(['region_1', 'region_2']);
    expect(out.every((m) => m.perceptId === null)).toBe(true);
  });

  it('reads several chips in one block, and several blocks', () => {
    const blocks = [
      { id: 'blk1', content: `${chip('data-region-ids="gnd_1" data-percept-id="pctx_a"')}${chip('data-region-ids="gnd_2" data-percept-id="pctx_b"')}` },
      { id: 'blk2', content: chip('data-region-ids="gnd_3" data-percept-id="pctx_c"') },
    ];
    expect(mentionsFromBlocks(blocks).map((m) => m.perceptId)).toEqual(['pctx_a', 'pctx_b', 'pctx_c']);
  });

  it('ignores markup that is not a chip, and empty blocks', () => {
    expect(mentionsFromBlocks([{ id: 'b', content: '<p>just prose</p>' }, { id: 'c' }])).toEqual([]);
    expect(mentionsFromBlocks()).toEqual([]);
  });

  it('blockIdsForPercept answers "is this carried by the writing?"', () => {
    const blocks = [
      { id: 'blk1', content: chip('data-region-ids="gnd_1" data-percept-id="pctx_a"') },
      { id: 'blk2', content: chip('data-region-ids="gnd_1" data-percept-id="pctx_a"') },
      { id: 'blk3', content: chip('data-region-ids="gnd_9" data-percept-id="pctx_z"') },
    ];
    const ms = mentionsFromBlocks(blocks);
    expect([...blockIdsForPercept(ms, 'pctx_a')].sort()).toEqual(['blk1', 'blk2']);
    expect(blockIdsForPercept(ms, 'pctx_none').size).toBe(0);
  });
});

// ── CIRCUIT-001 P3-A: a mark chip cites a visual_mark directly ───────────────
describe('Mention — the mark edge (P3-A)', () => {
  it('makeMention carries a markId and derives an id without changing the grammar', () => {
    const men = makeMention({ markId: 'vm_1', blockId: 'block_a', inlineContentId: 'ic_1', form: 'inline' });
    expect(men.markId).toBe('vm_1');
    expect(men.perceptId).toBeNull();
    expect(men.regionId).toBeNull();
    // grammar unchanged: men_<subject>_<block>_<slot>, subject = the mark
    expect(men.id).toBe('men_vm_1_block_a_ic_1');
  });

  it('mentionsForMark finds only the edges citing that mark', () => {
    const ms = [
      makeMention({ markId: 'vm_1', blockId: 'b1' }),
      makeMention({ markId: 'vm_2', blockId: 'b2' }),
      makeMention({ perceptId: 'pctx_a', blockId: 'b3' }),
    ].reduce(addMention, []);
    expect(mentionsForMark(ms, 'vm_1').map((m) => m.blockId)).toEqual(['b1']);
    expect(mentionsForMark(ms, 'vm_none')).toEqual([]);
  });

  it('mentionsFromBlocks reconstructs a mark edge from stored chip markup', () => {
    const blocks = [{
      id: 'block_m',
      content: '<p><span data-region-ref data-inline-type="mark" data-mark-id="vm_abc_0" '
        + 'data-region-ids="gnd_a,gnd_b" data-mention-id="men_vm_abc_0_block_m_ic1" '
        + 'data-label="the light gathers" class="ref-chip ref-chip--mark">the light gathers</span></p>',
    }];
    const out = mentionsFromBlocks(blocks);
    expect(out).toHaveLength(1);
    const [men] = out;
    expect(men.markId).toBe('vm_abc_0');
    expect(men.id).toBe('men_vm_abc_0_block_m_ic1'); // the stored id wins, not a re-derived one
    expect(men.regionId).toBeNull(); // a mark chip is NOT split into region edges
    expect(men.refKind).toBe('mark');
    expect(men.label).toBe('the light gathers');
  });
});

// ── CIRCUIT-001 P5-A: the crossing — a mention carries the source-post edge ───
describe('Mention — the crossing edge (P5-A)', () => {
  it('makeMention carries a postId WITHOUT changing the id grammar (the slot keeps it unique)', () => {
    const men = makeMention({ markId: 'vm_1', postId: 'post_B', blockId: 'block_a', inlineContentId: 'ic_1', form: 'inline' });
    expect(men.postId).toBe('post_B');
    // id grammar is untouched — postId does not enter it, so no existing edge is invalidated
    expect(men.id).toBe('men_vm_1_block_a_ic_1');
    // a same-post mark mention leaves postId null (byte-identical to before)
    expect(makeMention({ markId: 'vm_2', blockId: 'b', inlineContentId: 's' }).postId).toBeNull();
  });

  it('mentionsFromBlocks reconstructs the source-post edge from data-post-id', () => {
    const blocks = [{
      id: 'block_x',
      content: '<p><span data-region-ref data-inline-type="mark" data-mark-id="vm_cross_0" '
        + 'data-post-id="post_B" data-mention-id="men_vm_cross_0_block_x_ic1" '
        + 'data-label="lapel" class="ref-chip ref-chip--mark">lapel</span></p>',
    }];
    const [men] = mentionsFromBlocks(blocks);
    expect(men.markId).toBe('vm_cross_0');
    expect(men.postId).toBe('post_B');   // the crossing survived the markup round-trip
  });

  it('mentionsForPost finds only the crossings reaching that source', () => {
    const ms = [
      makeMention({ markId: 'vm_1', postId: 'post_B', blockId: 'b1' }),
      makeMention({ markId: 'vm_2', postId: 'post_C', blockId: 'b2' }),
      makeMention({ markId: 'vm_3', blockId: 'b3' }),          // same-post, no crossing
    ].reduce(addMention, []);
    expect(mentionsForPost(ms, 'post_B').map((m) => m.markId)).toEqual(['vm_1']);
    expect(mentionsForPost(ms, 'post_none')).toEqual([]);
  });
});
