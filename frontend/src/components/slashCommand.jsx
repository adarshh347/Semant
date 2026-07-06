import React from 'react';
import { createRoot } from 'react-dom/client';
import { Extension } from '@tiptap/core';
import Suggestion from '@tiptap/suggestion';
import { computePosition, autoUpdate, offset, flip, shift } from '@floating-ui/dom';
import { Pilcrow, Heading1, Quote } from 'lucide-react';
import SlashMenu from './SlashMenu';

/**
 * Phase 1 "/" menu — block types only, no AI. Each command deletes the typed
 * "/query" (range) and applies a block transform to the current node.
 */
const COMMANDS = [
  {
    title: 'Paragraph',
    description: 'Plain text',
    icon: <Pilcrow size={16} />,
    keywords: ['paragraph', 'text', 'plain', 'body', 'p'],
    run: ({ editor, range }) =>
      editor.chain().focus().deleteRange(range).setParagraph().run(),
  },
  {
    title: 'Heading',
    description: 'Section title',
    icon: <Heading1 size={16} />,
    keywords: ['heading', 'title', 'header', 'h1'],
    run: ({ editor, range }) =>
      editor.chain().focus().deleteRange(range).toggleHeading({ level: 1 }).run(),
  },
  {
    title: 'Quote',
    description: 'Callout or citation',
    icon: <Quote size={16} />,
    keywords: ['quote', 'blockquote', 'citation', 'callout'],
    run: ({ editor, range }) =>
      editor.chain().focus().deleteRange(range).toggleBlockquote().run(),
  },
];

const filterCommands = (query) => {
  const q = (query || '').toLowerCase().trim();
  if (!q) return COMMANDS;
  return COMMANDS.filter(
    (c) =>
      c.title.toLowerCase().startsWith(q) ||
      c.keywords.some((k) => k.startsWith(q)),
  );
};

// Strict trigger: fire only at the start of an empty-ish position or right after
// whitespace — never mid-word (so "TCP/IP" or a URL won't open the menu).
const allowSlash = ({ state, range }) => {
  const $from = state.doc.resolve(range.from);
  // Only inside a textblock that can hold paragraphs/headings.
  if (!$from.parent.isTextblock) return false;
  const textBefore = $from.parent.textBetween(0, $from.parentOffset, undefined, '￼');
  const prevChar = textBefore.slice(-1);
  return prevChar === '' || /\s/.test(prevChar);
};

// One floating <SlashMenu> per active suggestion, positioned with floating-ui.
const renderSlashMenu = () => {
  let el;
  let root;
  let menuRef;
  let stopAutoUpdate;

  const draw = (props) => {
    root.render(
      <SlashMenu
        ref={menuRef}
        items={props.items}
        command={(item) => props.command(item)}
      />,
    );
  };

  return {
    onStart: (props) => {
      el = document.createElement('div');
      el.className = 'slash-menu-floating';
      el.style.position = 'absolute';
      el.style.top = '0';
      el.style.left = '0';
      el.style.zIndex = '80';
      document.body.appendChild(el);

      root = createRoot(el);
      menuRef = React.createRef();
      draw(props);

      if (!props.clientRect) return;
      const virtual = { getBoundingClientRect: () => props.clientRect() };
      stopAutoUpdate = autoUpdate(virtual, el, () => {
        computePosition(virtual, el, {
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
      if (props.event.key === 'Escape') return false; // let suggestion close it
      return menuRef?.current?.onKeyDown(props) ?? false;
    },

    onExit: () => {
      stopAutoUpdate?.();
      // Unmount on a microtask — unmounting synchronously inside React's own
      // event/commit flow logs a warning.
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
      suggestion: {
        char: '/',
        startOfLine: false,
        allow: allowSlash,
        items: ({ query }) => filterCommands(query),
        render: renderSlashMenu,
        command: ({ editor, range, props }) => {
          props.run({ editor, range });
        },
      },
    };
  },

  addProseMirrorPlugins() {
    return [
      Suggestion({
        editor: this.editor,
        ...this.options.suggestion,
      }),
    ];
  },
});

export default SlashCommand;
