import { describe, it, expect, beforeAll } from 'vitest';
import { ServerBlockNoteEditor } from '@blocknote/server-util';
import {
  textBlocksToBlockNote,
  blockNoteToTextBlocks,
  toBlockNoteType,
  toTextBlockType,
} from './blockConvert.js';

// The engine used in tests — a headless BlockNote that does real HTML⇄blocks in Node,
// exactly what the live editor does in the browser (Phase 2).
let engine;
beforeAll(() => {
  engine = ServerBlockNoteEditor.create();
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
