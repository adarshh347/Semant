import React, { useEffect, useRef } from 'react';
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
 * Manuscript — the writer pane of the Chiasm workspace (Editor Path B, Phase 2).
 *
 * One BlockNote document replaces Path A's N-editors-per-block. Storage stays as
 * `text_blocks` (HTML) — we seed from and serialise to it through the Phase-1
 * converter (`blockConvert`), so every block id (and thus every Highlight/Region
 * `block_id` cross-link) survives. Themed to the plum v1.3 tokens via BlockNote's
 * CSS variables (see Manuscript.css).
 *
 * Props:
 *   - initialBlocks: text_blocks to seed the document with (seeded once per key).
 *   - onChange(textBlocks): debounced; hands serialised text_blocks back to the
 *     parent so the existing save/dirty flow keeps working unchanged.
 *   - editable: false renders a read-only document.
 *
 * Custom /part and /lens blocks + inline AI are Phases 3–4; this phase stands the
 * single editor up, ports the context-aware slash menu, and adopts BlockNote's own
 * side-menu / drag / formatting toolbar.
 */

const schema = BlockNoteSchema.create({
  blockSpecs: { ...defaultBlockSpecs },
  // The /part · /lens chip — a custom inline content that preserves main's
  // <span data-region-ref …> markup through the round-trip (Phase 3).
  inlineContentSpecs: { ...defaultInlineContentSpecs, regionRef: regionRefInline },
});

// Context-aware slash menu: STRUCTURE first when the block is empty / at its start
// (you're choosing a block type), Sutradhar AI first mid-text (you're transforming
// what you've written). AI items are stubs here — Phase 4 wires them to our
// endpoints (/chat/vision, /rewrite/vision, /flow/expand-node).
const AI_STUB = [
  { key: 'draft', title: 'Draft with Sutradhar', subtext: 'Write from what the image shows (wires in Phase 4)' },
  { key: 'continue', title: 'Continue writing', subtext: 'Extend this passage (Phase 4)' },
  { key: 'rewrite', title: 'Rewrite', subtext: 'Rephrase the selection (Phase 4)' },
];

function aiSlashItems(editor) {
  return AI_STUB.map((a) => ({
    title: a.title,
    subtext: a.subtext,
    aliases: [a.key, 'ai', 'sutradhar'],
    group: 'Sutradhar',
    icon: <span aria-hidden>✶</span>,
    onItemClick: () => {
      // Phase-4 seam: insert a placeholder paragraph marked as sutradhar-authored.
      insertOrUpdateBlockForSlashMenu(editor, {
        type: 'paragraph',
        props: { origin: 'sutradhar', color: null },
      });
    },
  }));
}

// True when the caret sits in an empty block (or at its very start) — the moment
// you're picking a block type rather than transforming prose.
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

export default function Manuscript({ initialBlocks = [], onChange, editable = true, store = null }) {
  // The shared Chiasm store (regions/percepts/mentions) — read for context; the
  // Mention-backed /part, inline mentions and bidirectional highlight wire in Phase 4.
  void store;
  const { theme } = useTheme();
  const editor = useCreateBlockNote({ schema });

  const seededRef = useRef(false);
  const debounceRef = useRef(null);
  // The live editor's default schema strips unknown props (origin/color), so we
  // carry provenance + colour in a side-channel keyed by block id and restore it
  // on serialise. Phase 3 promotes origin/actor to real custom-block props.
  const metaRef = useRef(new Map());

  // Seed once from text_blocks (via the converter). Guarded so re-renders don't
  // clobber in-progress edits.
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

  // Serialise back to text_blocks on change (debounced) so the parent's save/dirty
  // flow sees ordinary text_blocks. Whole-doc conversion is cheap at this cadence.
  // Restore origin/colour by id (a newly-typed block defaults to human/no-wash).
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
            const ai = aiSlashItems(editor);
            const ordered = atBlockStart(editor) ? [...structure, ...ai] : [...ai, ...structure];
            return filterSuggestionItems(ordered, query);
          }}
        />
      </BlockNoteView>
    </div>
  );
}
