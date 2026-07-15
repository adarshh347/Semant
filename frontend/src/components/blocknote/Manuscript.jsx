import React, { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import {
  BlockNoteSchema,
  defaultBlockSpecs,
  defaultInlineContentSpecs,
  filterSuggestionItems,
  insertOrUpdateBlockForSlashMenu,
} from '@blocknote/core';
import {
  useCreateBlockNote,
  getDefaultReactSlashMenuItems,
  SuggestionMenuController,
} from '@blocknote/react';
import { BlockNoteView } from '@blocknote/mantine';
import '@blocknote/core/fonts/inter.css';
import '@blocknote/mantine/style.css';

import { useTheme } from '../../context/ThemeContext';
import { textBlocksToBlockNote, blockNoteToTextBlocks } from './blockConvert';
import { regionRefInline } from './regionRefInline';
import './Manuscript.css';

/**
 * Manuscript — the writer pane of the Chiasm workspace (Editor Path B).
 *
 * One BlockNote document replaces Path A's N-editors-per-block; storage stays as
 * `text_blocks` (HTML) round-tripped through the converter, so block ids and every
 * reference attr survive. Themed to the plum v1.3 tokens.
 *
 * Props:
 *   - initialBlocks / onChange / editable — seed + serialise (Phase 2).
 *   - store — the shared Chiasm store, read for context (Phase 3+).
 *   - onRefTrigger(kind) — the `/part` · `/lens` slash items call this so the parent
 *     (which owns the RefPicker + regions) can open the picker at the caret; the
 *     parent then calls the imperative `insertRegionChip` (Phase 4).
 * Ref handle: { insertRegionChip(attrs), currentBlockId() }.
 */

const schema = BlockNoteSchema.create({
  blockSpecs: { ...defaultBlockSpecs },
  // The /part · /lens chip — a custom inline content preserving main's
  // <span data-region-ref …> markup (with the Mention identity) through the round-trip.
  inlineContentSpecs: { ...defaultInlineContentSpecs, regionRef: regionRefInline },
});

// Sutradhar (the AI name) is retired per the Chiasm lexicon — provenance lives in
// block `origin`. These seed a sutradhar-origin block; the endpoints wire in Phase 4b.
const AI_STUB = [
  { key: 'draft', title: 'Draft from the image', subtext: 'Write from what the image shows (wires in Phase 4)' },
  { key: 'continue', title: 'Continue writing', subtext: 'Extend this passage (Phase 4)' },
  { key: 'rewrite', title: 'Rewrite', subtext: 'Rephrase the selection (Phase 4)' },
];

function aiSlashItems(editor) {
  return AI_STUB.map((a) => ({
    title: a.title,
    subtext: a.subtext,
    aliases: [a.key, 'ai'],
    group: 'AI',
    icon: <span aria-hidden>✶</span>,
    onItemClick: () => {
      insertOrUpdateBlockForSlashMenu(editor, {
        type: 'paragraph',
        props: { origin: 'sutradhar', color: null },
      });
    },
  }));
}

// /part · /lens — reference the image. They defer to the parent's RefPicker (which
// holds the regions + the store); the pick comes back through insertRegionChip.
function refSlashItems(onRefTrigger) {
  return [
    {
      title: 'Part', subtext: 'Reference a region of the image',
      aliases: ['part', 'region', 'ref', 'chip'], group: 'Chiasm',
      icon: <span aria-hidden>◈</span>,
      onItemClick: () => onRefTrigger?.('part'),
    },
    {
      title: 'Lens', subtext: 'Cite an Aletheia reading',
      aliases: ['lens', 'reading', 'aletheia'], group: 'Chiasm',
      icon: <span aria-hidden>◎</span>,
      onItemClick: () => onRefTrigger?.('lens'),
    },
  ];
}

// True when the caret sits in an empty block — you're picking a block type, not
// transforming prose.
function atBlockStart(editor) {
  try {
    const block = editor.getTextCursorPosition().block;
    const text = (block?.content ?? [])
      .map((n) => (typeof n?.text === 'string' ? n.text : ''))
      .join('');
    return text.trim().length === 0;
  } catch {
    return true;
  }
}

const Manuscript = forwardRef(function Manuscript(
  { initialBlocks = [], onChange, editable = true, store = null, onRefTrigger = null },
  ref,
) {
  void store; // context (RegionStoreContext) carries the store to the chips directly
  const { theme } = useTheme();
  const editor = useCreateBlockNote({ schema });

  const seededRef = useRef(false);
  const debounceRef = useRef(null);
  // The live editor's default schema strips unknown props (origin/color), so we
  // carry provenance + colour in a side-channel keyed by block id and restore it
  // on serialise. (Custom-block origin props are a later refinement.)
  const metaRef = useRef(new Map());

  // Imperative handle — the parent inserts a region chip after the RefPicker resolves.
  useImperativeHandle(ref, () => ({
    currentBlockId: () => {
      try { return editor.getTextCursorPosition()?.block?.id ?? null; } catch { return null; }
    },
    insertRegionChip: ({ refKind = 'part', regionIds = '', label = 'part', perceptId = '', mentionId = '', blockId = null }) => {
      try {
        if (blockId) editor.setTextCursorPosition(blockId, 'end');
        editor.insertInlineContent([
          { type: 'regionRef', props: { refKind, regionIds, perceptId, mentionId, label } },
          ' ', // a trailing space so the caret doesn't stick to the atom
        ]);
        editor.focus();
      } catch { /* editor not ready */ }
    },
  }), [editor]);

  // Seed once from text_blocks (via the converter).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (seededRef.current) return;
      metaRef.current = new Map(
        (initialBlocks ?? []).map((b) => [b.id, { origin: b.origin ?? 'human', color: b.color ?? null }]),
      );
      const blocks = await textBlocksToBlockNote(initialBlocks, editor);
      if (cancelled) return;
      seededRef.current = true;
      if (blocks.length) editor.replaceBlocks(editor.document, blocks);
    })();
    return () => { cancelled = true; };
  }, [editor, initialBlocks]);

  // Serialise back to text_blocks (debounced); restore origin/colour by id.
  const handleChange = () => {
    if (!onChange) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      const textBlocks = await blockNoteToTextBlocks(editor.document, editor);
      const merged = textBlocks.map((tb) => {
        const meta = metaRef.current.get(tb.id);
        return meta ? { ...tb, origin: meta.origin, color: meta.color } : tb;
      });
      onChange(merged);
    }, 400);
  };

  // Field → Manuscript highlight is store-driven at the chip: each RegionRefChip
  // reads the store via RegionStoreContext and lights itself when its region is
  // focused (many-to-many — every chip citing the region lights). No imperative DOM,
  // no doc re-render, no cross-pane coupling.

  return (
    <div className="manuscript">
      <BlockNoteView
        editor={editor}
        editable={editable}
        theme={theme === 'dark' ? 'dark' : 'light'}
        slashMenu={false}
        onChange={handleChange}
      >
        <SuggestionMenuController
          triggerCharacter="/"
          getItems={async (query) => {
            const structure = getDefaultReactSlashMenuItems(editor);
            const refs = refSlashItems(onRefTrigger);
            const ai = aiSlashItems(editor);
            // At a fresh block you're choosing structure; mid-prose you're
            // referencing or transforming — so refs + AI lead there.
            const ordered = atBlockStart(editor)
              ? [...structure, ...refs, ...ai]
              : [...refs, ...ai, ...structure];
            return filterSuggestionItems(ordered, query);
          }}
        />
      </BlockNoteView>
    </div>
  );
});

export default Manuscript;
