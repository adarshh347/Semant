import { describe, it, expect, beforeAll } from 'vitest';
import { ServerBlockNoteEditor } from '@blocknote/server-util';
import {
  BlockNoteSchema,
  defaultInlineContentSpecs,
  createInlineContentSpec,
} from '@blocknote/core';
import {
  textBlocksToBlockNote,
  blockNoteToTextBlocks,
  toBlockNoteType,
  toTextBlockType,
} from './blockConvert.js';

// The engine used in tests — a headless BlockNote that does real HTML⇄blocks in Node,
// exactly what the live editor does in the browser (Phase 2).
let engine;
// A schema-aware engine mirroring the Manuscript's regionRef contract (Phase 3):
// same on-disk markup, so the converter preserves the /part · /lens chip. (A core
// inline spec, since server-util is DOM-only; the browser uses the React version.)
let chipEngine;
beforeAll(() => {
  engine = ServerBlockNoteEditor.create();
  // Mirrors regionRefInline's markup contract (core spec — server-util is DOM-only).
  const regionRef = createInlineContentSpec(
    { type: 'regionRef', propSchema: { refKind: { default: 'part' }, regionIds: { default: '' }, perceptId: { default: '' }, mentionId: { default: '' }, markId: { default: '' }, postId: { default: '' }, label: { default: '' } }, content: 'none' },
    {
      render: (ic) => {
        const p = ic.props;
        const regionId = (p.regionIds || '').split(',').filter(Boolean)[0] || '';
        const s = document.createElement('span');
        s.setAttribute('data-region-ref', '');
        s.setAttribute('data-ref-kind', p.refKind);
        s.setAttribute('data-inline-type', p.refKind);
        s.setAttribute('data-region-ids', p.regionIds);
        if (regionId) s.setAttribute('data-region-id', regionId);
        if (p.perceptId) s.setAttribute('data-percept-id', p.perceptId);
        if (p.mentionId) s.setAttribute('data-mention-id', p.mentionId);
        if (p.markId) s.setAttribute('data-mark-id', p.markId);
        if (p.postId) s.setAttribute('data-post-id', p.postId);
        s.setAttribute('data-label', p.label);
        s.className = `ref-chip ref-chip--${p.refKind}`;
        s.textContent = p.label;
        return { dom: s };
      },
      parse: (el) => (el.hasAttribute('data-region-ref')
        ? {
            refKind: el.getAttribute('data-inline-type') || el.getAttribute('data-ref-kind') || 'part',
            regionIds: el.getAttribute('data-region-ids') || el.getAttribute('data-region-id') || '',
            perceptId: el.getAttribute('data-percept-id') || '',
            mentionId: el.getAttribute('data-mention-id') || '',
            markId: el.getAttribute('data-mark-id') || '',
            postId: el.getAttribute('data-post-id') || '',
            label: el.getAttribute('data-label') || el.textContent || '',
          }
        : undefined),
    },
  );
  const schema = BlockNoteSchema.create({ inlineContentSpecs: { ...defaultInlineContentSpecs, regionRef } });
  chipEngine = ServerBlockNoteEditor.create({ schema });
});

const roundTrip = async (textBlocks) =>
  blockNoteToTextBlocks(await textBlocksToBlockNote(textBlocks, engine), engine);

const stripTags = (html) => (html ?? '').replace(/<[^>]+>/g, '').trim();

// A realistic story: heading + prose + a sutradhar-authored paragraph + a colour wash
// + a quote. Ids look like the backend's `block_{uuid}`.
const STORY = [
  { id: 'block_h', type: 'h1', content: '<h1>The turned collar</h1>', origin: 'human', color: null },
  {
    id: 'block_p1',
    type: 'paragraph',
    content: '<p>The drape softens the <strong>severe</strong> shoulder.</p>',
    origin: 'human',
    color: null,
  },
  {
    id: 'block_sut',
    type: 'paragraph',
    content: '<p>An <em>Aletheia</em> reading, drafted for you.</p>',
    origin: 'sutradhar',
    color: null,
  },
  {
    id: 'block_wash',
    type: 'paragraph',
    content: '<p>A remembered line.</p>',
    origin: 'human',
    color: '#fef3c7',
  },
  { id: 'block_q', type: 'quote', content: '<blockquote>The moat stays ours.</blockquote>', origin: 'human', color: null },
];

describe('type mapping', () => {
  it('maps our types to BlockNote and back', () => {
    expect(toBlockNoteType('h1')).toEqual({ type: 'heading', props: { level: 1 } });
    expect(toBlockNoteType('quote')).toEqual({ type: 'quote', props: {} });
    expect(toBlockNoteType('paragraph')).toEqual({ type: 'paragraph', props: {} });
    expect(toBlockNoteType('anything-else').type).toBe('paragraph');

    expect(toTextBlockType({ type: 'heading', props: { level: 1 } })).toBe('h1');
    expect(toTextBlockType({ type: 'quote' })).toBe('quote');
    expect(toTextBlockType({ type: 'paragraph' })).toBe('paragraph');
  });
});

describe('round-trip fidelity (the gate)', () => {
  it('preserves ids and their order', async () => {
    const out = await roundTrip(STORY);
    expect(out.map((b) => b.id)).toEqual(STORY.map((b) => b.id));
  });

  it('preserves origin provenance (incl. the sutradhar block)', async () => {
    const out = await roundTrip(STORY);
    expect(out.map((b) => b.origin)).toEqual(['human', 'human', 'sutradhar', 'human', 'human']);
  });

  it('preserves the colour wash', async () => {
    const out = await roundTrip(STORY);
    const wash = out.find((b) => b.id === 'block_wash');
    expect(wash.color).toBe('#fef3c7');
    // blocks without a wash stay null (not undefined / not a stray colour)
    expect(out.find((b) => b.id === 'block_h').color).toBeNull();
  });

  it('preserves block types (heading + quote survive)', async () => {
    const out = await roundTrip(STORY);
    expect(out.map((b) => b.type)).toEqual(['h1', 'paragraph', 'paragraph', 'paragraph', 'quote']);
  });

  it('preserves visible text and inline formatting', async () => {
    const out = await roundTrip(STORY);
    expect(stripTags(out[0].content)).toBe('The turned collar');
    expect(stripTags(out[1].content)).toBe('The drape softens the severe shoulder.');
    // inline marks survive the HTML round-trip
    expect(out[1].content).toContain('<strong>severe</strong>');
    expect(out[2].content).toContain('<em>Aletheia</em>');
  });

  it('is idempotent — a second round-trip changes nothing', async () => {
    const once = await roundTrip(STORY);
    const twice = await roundTrip(once);
    expect(twice).toEqual(once);
  });
});

describe('cross-link integrity', () => {
  it('a Highlight.block_id and a Region.block_id still resolve after round-trip', async () => {
    const highlight = { id: 'hl_1', text: 'severe', block_id: 'block_p1' };
    const region = { id: 'reg_1', label: 'shoulder drape', block_id: 'block_wash' };

    const out = await roundTrip(STORY);
    const ids = new Set(out.map((b) => b.id));

    expect(ids.has(highlight.block_id)).toBe(true);
    expect(ids.has(region.block_id)).toBe(true);
    // and the resolved block is still the right one (order/identity intact)
    expect(out.find((b) => b.id === highlight.block_id).type).toBe('paragraph');
  });

  it('emits data-block-id-resolvable ids for EVERY block (no id dropped/rewritten)', async () => {
    const bn = await textBlocksToBlockNote(STORY, engine);
    expect(bn.map((b) => b.id)).toEqual(STORY.map((b) => b.id));
    const back = await blockNoteToTextBlocks(bn, engine);
    expect(back.map((b) => b.id)).toEqual(STORY.map((b) => b.id));
  });
});

describe('region-ref chips (Phase 3 — no data loss on edit)', () => {
  const chipRoundTrip = async (textBlocks) =>
    blockNoteToTextBlocks(await textBlocksToBlockNote(textBlocks, chipEngine), chipEngine);

  it('preserves a /part chip (data-region-ids survives edit+save)', async () => {
    const story = [
      { id: 'block_c', type: 'paragraph', origin: 'human', color: null,
        content: '<p>The <span data-region-ref data-ref-kind="part" data-region-ids="reg_1" data-label="drape" class="ref-chip ref-chip--part">drape</span> holds the light.</p>' },
    ];
    const out = await chipRoundTrip(story);
    expect(out[0].content).toContain('data-region-ids="reg_1"');
    expect(out[0].content).toContain('data-region-ref');
    expect(out[0].content).toContain('drape');
    expect(out[0].id).toBe('block_c'); // id still preserved
  });

  it('preserves EVERY reference attr through import→export (the Phase-3 gate)', async () => {
    const story = [
      {
        id: 'block_ref', type: 'paragraph', origin: 'sutradhar', color: null,
        content:
          '<p>The <span data-region-ref data-inline-type="part" data-ref-kind="part" ' +
          'data-region-ids="reg_1" data-region-id="reg_1" ' +
          'data-percept-id="pct_creator_reg_1" data-mention-id="men_pct_block_ref_ic1" ' +
          'data-label="shoulder drape" class="ref-chip ref-chip--part">shoulder drape</span> holds it.</p>',
      },
    ];
    const out = await chipRoundTrip(story);
    const html = out[0].content;
    // data-block-id is block-level — the block id itself must survive (the read view emits it).
    expect(out[0].id).toBe('block_ref');
    // Every inline reference attr survives — semantic, not incidental.
    for (const attr of ['data-region-ref', 'data-inline-type', 'data-region-ids', 'data-region-id', 'data-percept-id', 'data-mention-id']) {
      expect(html).toContain(attr);
    }
    expect(html).toContain('data-percept-id="pct_creator_reg_1"');
    expect(html).toContain('data-mention-id="men_pct_block_ref_ic1"');
    expect(html).toContain('data-region-id="reg_1"');
  });

  it('preserves a /lens chip spanning multiple regions', async () => {
    const story = [
      { id: 'block_l', type: 'paragraph', origin: 'sutradhar', color: null,
        content: '<p><span data-region-ref data-ref-kind="lens" data-region-ids="reg_1,reg_2,reg_3" data-label="Phenomenological" class="ref-chip ref-chip--lens">Phenomenological</span> reads the tension.</p>' },
    ];
    const out = await chipRoundTrip(story);
    expect(out[0].content).toContain('data-region-ids="reg_1,reg_2,reg_3"');
    expect(out[0].content).toContain('data-ref-kind="lens"');
    expect(out[0].origin).toBe('sutradhar');
  });

  it('preserves a /percept chip (Differential v1 — pctx id survives for recall)', async () => {
    // A percept-Mention chip: refKind 'percept', data-percept-id carries the
    // pctx_ id (the recall trigger), regionIds carry the GROUND ids.
    const story = [
      { id: 'block_p', type: 'paragraph', origin: 'human', color: null,
        content: '<p>Notice how <span data-region-ref data-inline-type="percept" data-ref-kind="percept" '
          + 'data-region-ids="gnd_a,gnd_b" data-percept-id="pctx_abc_0" data-mention-id="men_pctx_block_p_ic1" '
          + 'data-label="the light gathers" class="ref-chip ref-chip--percept">the light gathers</span> here.</p>' },
    ];
    const out = await chipRoundTrip(story);
    const html = out[0].content;
    expect(html).toContain('data-percept-id="pctx_abc_0"'); // the recall trigger survives
    expect(html).toContain('data-region-ids="gnd_a,gnd_b"'); // the ground ids survive
    expect(html).toContain('percept'); // refKind class/attr present
  });

  it('preserves a /mark chip (CIRCUIT-001 P3-A — vm_ id survives for mark recall)', async () => {
    // A mark-Mention chip: refKind 'mark', data-mark-id carries the vm_ id (the mark
    // recall trigger), regionIds carry the mark's linked GROUND ids (hover context).
    const story = [
      { id: 'block_m', type: 'paragraph', origin: 'human', color: null,
        content: '<p>The <span data-region-ref data-inline-type="mark" data-ref-kind="mark" '
          + 'data-region-ids="gnd_a,gnd_b" data-mark-id="vm_abc_0" data-mention-id="men_vm_block_m_ic1" '
          + 'data-label="the light gathers" class="ref-chip ref-chip--mark">the light gathers</span> holds.</p>' },
    ];
    const out = await chipRoundTrip(story);
    const html = out[0].content;
    expect(html).toContain('data-mark-id="vm_abc_0"');     // the mark recall trigger survives
    expect(html).toContain('data-region-ids="gnd_a,gnd_b"'); // the linked ground ids survive
    expect(html).toContain('data-mention-id="men_vm_block_m_ic1"');
    expect(html).toContain('mark');                          // refKind class/attr present
    expect(out[0].id).toBe('block_m');
  });

  it('preserves a CROSS-POST chip (CIRCUIT-001 P5-A — data-post-id survives edit+save)', async () => {
    // A crossing: the chip cites a mark whose reference reaches another post. data-post-id is
    // the border marker — it MUST round-trip, or the crossing is silently flattened to a
    // same-post citation on the next edit.
    const story = [
      { id: 'block_cross', type: 'paragraph', origin: 'human', color: null,
        content: '<p>Echoes the <span data-region-ref data-inline-type="mark" data-ref-kind="mark" '
          + 'data-mark-id="vm_cross_0" data-post-id="post_B" '
          + 'data-mention-id="men_vm_cross_0_block_cross_ic1" '
          + 'data-label="lapel elsewhere" class="ref-chip ref-chip--mark">lapel elsewhere</span> on another figure.</p>' },
    ];
    const out = await chipRoundTrip(story);
    const html = out[0].content;
    expect(html).toContain('data-post-id="post_B"');    // the border survived serialization
    expect(html).toContain('data-mark-id="vm_cross_0"');
    expect(out[0].id).toBe('block_cross');
  });

  it('under the DEFAULT (chip-less) schema the span would flatten — proves the spec is load-bearing', async () => {
    const story = [
      { id: 'block_x', type: 'paragraph', origin: 'human', color: null,
        content: '<p>The <span data-region-ref data-region-ids="reg_1" data-label="hem">hem</span> falls.</p>' },
    ];
    const out = await blockNoteToTextBlocks(await textBlocksToBlockNote(story, engine), engine);
    expect(out[0].content).not.toContain('data-region-ids'); // flattens without the spec
  });
});

describe('edge cases', () => {
  it('empty story round-trips to empty (both directions)', async () => {
    expect(await textBlocksToBlockNote([], engine)).toEqual([]);
    expect(await blockNoteToTextBlocks([], engine)).toEqual([]);
    expect(await roundTrip([])).toEqual([]);
  });

  it('handles null/undefined inputs without throwing', async () => {
    expect(await textBlocksToBlockNote(null, engine)).toEqual([]);
    expect(await blockNoteToTextBlocks(undefined, engine)).toEqual([]);
  });

  it('an empty-content block becomes an empty block of the declared type', async () => {
    const bn = await textBlocksToBlockNote(
      [{ id: 'block_empty', type: 'h1', content: '', origin: 'human', color: null }],
      engine,
    );
    expect(bn[0].id).toBe('block_empty');
    expect(bn[0].type).toBe('heading');
    expect(bn[0].props.level).toBe(1);
    // and it round-trips back to an h1
    const back = await blockNoteToTextBlocks(bn, engine);
    expect(back[0].type).toBe('h1');
    expect(back[0].id).toBe('block_empty');
  });

  it('defaults a missing origin to human', async () => {
    const bn = await textBlocksToBlockNote(
      [{ id: 'block_x', type: 'paragraph', content: '<p>hi</p>' }],
      engine,
    );
    expect(bn[0].props.origin).toBe('human');
    const back = await blockNoteToTextBlocks(bn, engine);
    expect(back[0].origin).toBe('human');
  });
});
