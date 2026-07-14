/**
 * blockConvert — Path A `text_blocks` ⇄ one BlockNote document (Editor Path B, Phase 1).
 *
 * The gated risk of the migration: the converter must be LOSSLESS on the things that
 * matter — each block's `id` (so every cross-link that stores a `block_id` still
 * resolves), its order, its `origin` provenance, its colour wash, and its text +
 * inline formatting. Storage stays HTML (Phase 1 decision); we convert on load/save.
 *
 * Pure module: the HTML⇄inline work is delegated to an injected `engine` that exposes
 *   - `tryParseHTMLToBlocks(html) -> Promise<Block[]>`
 *   - `blocksToHTMLLossy(blocks) -> Promise<string>`
 * In the browser that engine is the live BlockNote editor; in tests it's
 * `ServerBlockNoteEditor` from `@blocknote/server-util`. The converter never mounts an
 * editor and never depends on the DOM.
 *
 * A `text_block` is `{ id, type, content(HTML), color, origin }` (see backend
 * `schemas/post.py:TextBlock` — note `origin` is a frontend-carried field, not yet in
 * the persisted schema). Path A uses three types: `paragraph`, `h1`, `quote`.
 *
 * Provenance/colour are carried on the BlockNote block's `props` under `origin`/`color`
 * — metadata this module owns and reads back on export. Phase 3 formalises `origin`
 * (and `actor`) as real props on custom blocks; until then a Phase-2 schema must allow
 * them (or they round-trip only through this converter, which is all Phase 1 needs).
 */

const DEFAULT_ORIGIN = 'human';

// Our block type -> BlockNote {type, props}. Used only as a fallback when a block's
// HTML is empty (freshly-made blocks seed empty content); otherwise the parsed HTML
// is authoritative for the type.
export function toBlockNoteType(tbType) {
  switch (tbType) {
    case 'h1': return { type: 'heading', props: { level: 1 } };
    case 'h2': return { type: 'heading', props: { level: 2 } };
    case 'h3': return { type: 'heading', props: { level: 3 } };
    case 'quote': return { type: 'quote', props: {} };
    case 'paragraph':
    default: return { type: 'paragraph', props: {} };
  }
}

// BlockNote block -> our text_block `type`. Inverse of the mapping above.
export function toTextBlockType(block) {
  if (block?.type === 'heading') return `h${block.props?.level ?? 1}`;
  if (block?.type === 'quote') return 'quote';
  return 'paragraph';
}

/**
 * text_blocks -> BlockNote blocks. Preserves id + order; carries origin + colour as
 * props. One text_block becomes exactly one BlockNote block (so the id stays 1:1).
 */
export async function textBlocksToBlockNote(textBlocks, engine) {
  const blocks = [];
  for (const tb of textBlocks ?? []) {
    const html = (tb?.content ?? '').trim();

    let base = null;
    if (html) {
      const parsed = await engine.tryParseHTMLToBlocks(html);
      // A text_block is a single block; if the HTML somehow parses to several, keep the
      // first so the id mapping stays 1:1 (the tail would be orphaned by design).
      base = parsed?.[0] ?? null;
    }
    if (!base) {
      // Empty content — build an empty block of the block's declared type.
      const { type, props } = toBlockNoteType(tb?.type);
      base = { type, props, content: [] };
    }

    blocks.push({
      ...base,
      id: tb.id,
      props: {
        ...(base.props ?? {}),
        origin: tb?.origin ?? DEFAULT_ORIGIN,
        color: tb?.color ?? null,
      },
    });
  }
  return blocks;
}

/**
 * BlockNote blocks -> text_blocks. Reads id + origin + colour back off each block and
 * re-serialises its content (minus our metadata props) to HTML.
 */
export async function blockNoteToTextBlocks(blocks, engine) {
  const textBlocks = [];
  for (const b of blocks ?? []) {
    const { origin = DEFAULT_ORIGIN, color = null, ...cleanProps } = b?.props ?? {};
    const html = await engine.blocksToHTMLLossy([
      { id: b.id, type: b.type, props: cleanProps, content: b.content ?? [] },
    ]);
    textBlocks.push({
      id: b.id,
      type: toTextBlockType(b),
      content: html,
      color,
      origin,
    });
  }
  return textBlocks;
}
