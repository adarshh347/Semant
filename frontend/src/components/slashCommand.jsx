import React from 'react';
import { createRoot } from 'react-dom/client';
import { Extension } from '@tiptap/core';
import Suggestion from '@tiptap/suggestion';
import { computePosition, autoUpdate, offset, flip, shift } from '@floating-ui/dom';
import {
  Pilcrow, Heading1, Quote, GitBranch,
  Sparkles, PenLine, CornerDownRight, RefreshCw, Maximize2, Minimize2,
  Crosshair, Eye,
} from 'lucide-react';
import SlashMenu from './SlashMenu';

/**
 * Context-aware "/" menu (Phase 2).
 *
 * - Empty block / caret at block start → STRUCTURE set: Paragraph, Heading,
 *   Quote, Version (an alternate starting draft from the image). This is the
 *   ONLY place the block-type trio appears.
 * - Caret mid-text (block already has content) → AI set: Draft, Write,
 *   Continue, Rewrite, Expand, Shorten. The trio never shows here.
 * - REF set (/part, /lens) → shown in BOTH contexts. You point at a part while
 *   writing a sentence about it just as often as you open a block with it, so
 *   this is the one set the caret's position must not hide.
 *
 * Block-type commands apply a TipTap transform inline; AI commands are handed
 * up to React (onAiCommand) which calls the existing non-streaming endpoints
 * and inserts a `sutradhar` block; ref commands are handed up (onRefCommand)
 * to open a picker of the image's regions / the reading's lenses.
 */

// Block-type commands — inline TipTap transforms.
const STRUCTURE_COMMANDS = [
  {
    key: 'paragraph', kind: 'block', title: 'Paragraph', description: 'Plain text',
    icon: <Pilcrow size={16} />, keywords: ['paragraph', 'text', 'plain', 'p'],
    run: ({ editor, range }) => editor.chain().focus().deleteRange(range).setParagraph().run(),
  },
  {
    key: 'heading', kind: 'block', title: 'Heading', description: 'Section title',
    icon: <Heading1 size={16} />, keywords: ['heading', 'title', 'header', 'h1'],
    run: ({ editor, range }) => editor.chain().focus().deleteRange(range).toggleHeading({ level: 1 }).run(),
  },
  {
    key: 'quote', kind: 'block', title: 'Quote', description: 'Callout or citation',
    icon: <Quote size={16} />, keywords: ['quote', 'blockquote', 'citation', 'callout'],
    run: ({ editor, range }) => editor.chain().focus().deleteRange(range).toggleBlockquote().run(),
  },
  {
    key: 'version', kind: 'ai', title: 'Version', description: 'Draft an alternate from the image',
    icon: <GitBranch size={16} />, keywords: ['version', 'alternate', 'variant', 'draft'],
  },
];

// AI verbs — dispatched to React (non-streaming endpoints), land as sutradhar blocks.
const AI_COMMANDS = [
  {
    key: 'draft', kind: 'ai', title: 'Draft from image', description: 'Let the image speak',
    icon: <Sparkles size={16} />, keywords: ['draft', 'image', 'auto', 'suggest'],
  },
  {
    key: 'write', kind: 'ai', title: 'Write…', description: 'Write from your instruction',
    icon: <PenLine size={16} />, keywords: ['write', 'prompt', 'instruct'],
  },
  {
    key: 'continue', kind: 'ai', title: 'Continue', description: 'Extend this passage',
    icon: <CornerDownRight size={16} />, keywords: ['continue', 'extend', 'more'],
  },
  {
    key: 'rewrite', kind: 'ai', title: 'Rewrite', description: 'Clarify, keep the meaning',
    icon: <RefreshCw size={16} />, keywords: ['rewrite', 'rephrase', 'reword'],
  },
  {
    key: 'expand', kind: 'ai', title: 'Expand', description: 'Add relevant detail',
    icon: <Maximize2 size={16} />, keywords: ['expand', 'elaborate', 'lengthen'],
  },
  {
    key: 'shorten', kind: 'ai', title: 'Shorten', description: 'Trim to its essence',
    icon: <Minimize2 size={16} />, keywords: ['shorten', 'condense', 'trim', 'tighten'],
  },
];

// References into the image — dispatched to React, which opens a picker at the caret.
// Each is offered only when there is something to point at: `/part` needs marked
// regions, `/lens` needs a reading. An empty picker is a dead end, not a discovery.
const REF_COMMANDS = [
  {
    key: 'part', kind: 'ref', title: 'Part', description: 'Point at a region of the image',
    icon: <Crosshair size={16} />, keywords: ['part', 'region', 'mark', 'anatomy'],
    available: (counts) => counts.parts > 0,
  },
  {
    key: 'lens', kind: 'ref', title: 'Lens', description: "Cite Aletheia's reading",
    icon: <Eye size={16} />, keywords: ['lens', 'reading', 'aletheia', 'cite'],
    available: (counts) => counts.lenses > 0,
  },
];

// Structure context = the block has no real text apart from the "/query" being typed.
const isStructureContext = (editor, query) => {
  const sel = editor?.state?.selection;
  if (!sel) return true;
  if (!sel.empty) return false; // a live selection ⇒ mid-text (AI transforms)
  const parent = sel.$from.parent;
  if (!parent.isTextblock) return true;
  const text = parent.textContent || '';
  const caret = sel.$from.parentOffset;
  const tokenLen = 1 + (query || '').length; // '/' + query
  const before = text.slice(0, Math.max(0, caret - tokenLen));
  const after = text.slice(caret);
  return (before + after).trim().length === 0;
};

const filterCommands = (query, editor, counts) => {
  const contextual = isStructureContext(editor, query) ? STRUCTURE_COMMANDS : AI_COMMANDS;
  const set = [...contextual, ...REF_COMMANDS.filter((c) => c.available(counts))];
  const q = (query || '').toLowerCase().trim();
  if (!q) return set;
  return set.filter(
    (c) => c.title.toLowerCase().startsWith(q) || c.keywords.some((k) => k.startsWith(q)),
  );
};

const allowSlash = ({ state, range }) => {
  const $from = state.doc.resolve(range.from);
  if (!$from.parent.isTextblock) return false;
  const textBefore = $from.parent.textBetween(0, $from.parentOffset, undefined, '￼');
  const prevChar = textBefore.slice(-1);
  return prevChar === '' || /\s/.test(prevChar);
};

const renderSlashMenu = () => {
  let el;
  let root;
  let menuRef;
  let stopAutoUpdate;

  const draw = (props) => {
    root.render(
      <SlashMenu ref={menuRef} items={props.items} command={(item) => props.command(item)} />,
    );
  };

  return {
    onStart: (props) => {
      el = document.createElement('div');
      el.className = 'slash-menu-floating';
      el.style.position = 'fixed';
      el.style.top = '0';
      el.style.left = '0';
      el.style.zIndex = '80';
      document.body.appendChild(el);

      root = createRoot(el);
      menuRef = React.createRef();
      draw(props);

      if (!props.clientRect) return;
      // contextElement anchors the virtual reference to a real DOM node inside
      // .content-area, so autoUpdate can attach scroll listeners to that inner
      // scroll container (a bare virtual ref has no ancestors to track).
      const virtual = {
        getBoundingClientRect: () => props.clientRect(),
        contextElement: props.editor?.view?.dom,
      };
      stopAutoUpdate = autoUpdate(virtual, el, () => {
        computePosition(virtual, el, {
          strategy: 'fixed',
          placement: 'bottom-start',
          middleware: [offset(6), flip({ padding: 8 }), shift({ padding: 8 })],
        }).then(({ x, y }) => {
          el.style.left = `${x}px`;
          el.style.top = `${y}px`;
        });
      });
    },

    onUpdate: (props) => {
      draw(props);
    },

    onKeyDown: (props) => {
      if (props.event.key === 'Escape') return false;
      return menuRef?.current?.onKeyDown(props) ?? false;
    },

    onExit: () => {
      stopAutoUpdate?.();
      const toUnmount = root;
      const toRemove = el;
      Promise.resolve().then(() => {
        toUnmount?.unmount();
        toRemove?.remove();
      });
      el = undefined;
      root = undefined;
      menuRef = undefined;
    },
  };
};

const SlashCommand = Extension.create({
  name: 'slashCommand',

  addOptions() {
    return {
      // Supplied per-editor by RichTextBlock; each receives { key, editor, range }.
      onAiCommand: null,
      onRefCommand: null,
      // Read at menu-open time, not at configure time — the reading can arrive, and a
      // part can be marked, long after this editor was created.
      refCounts: () => ({ parts: 0, lenses: 0 }),
    };
  },

  addProseMirrorPlugins() {
    const { onAiCommand, onRefCommand, refCounts } = this.options;
    return [
      Suggestion({
        editor: this.editor,
        char: '/',
        startOfLine: false,
        allow: allowSlash,
        items: ({ query, editor }) => filterCommands(query, editor, refCounts?.() ?? { parts: 0, lenses: 0 }),
        render: renderSlashMenu,
        command: ({ editor, range, props }) => {
          if (props.kind === 'ai') {
            onAiCommand?.({ key: props.key, editor, range });
          } else if (props.kind === 'ref') {
            onRefCommand?.({ key: props.key, editor, range });
          } else {
            props.run({ editor, range });
          }
        },
      }),
    ];
  },
});

export default SlashCommand;
