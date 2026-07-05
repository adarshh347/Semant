import { useEditor, EditorContent } from '@tiptap/react';
import { BubbleMenu } from '@tiptap/react/menus';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import React, { useEffect, useRef, useState } from 'react';
import {
  Bold, Italic, Underline as UnderlineIcon, Quote, Heading1, Pilcrow,
  Trash2, ChevronUp, ChevronDown, GripVertical, MoreHorizontal, Check,
} from 'lucide-react';

// NOTE: the 6 hex swatches are off-theme; flagged for the Surface pass, not this
// (structure) lane. Kept as-is to preserve the colour capability.
const COLOR_OPTIONS = ['transparent', '#fef3c7', '#dcfce7', '#dbeafe', '#f3e8ff', '#fee2e2'];

function RichTextBlock({
  block,
  onContentChange,
  onColorChange,
  onDelete,
  onMoveUp,
  onMoveDown,
  onFocusBlock,
  isFirst,
  isLast,
  isActive,
  // drag-to-reorder
  onDragStartBlock,
  onDragEnterBlock,
  onDropBlock,
  onDragEndBlock,
  isDropTarget,
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  const editor = useEditor({
    extensions: [StarterKit, Underline],
    content: block.content,
    onUpdate: ({ editor }) => onContentChange(block.id, editor.getHTML()),
    onFocus: () => onFocusBlock?.(block.id),
    editorProps: {
      attributes: { class: 'prose prose-sm focus:outline-none' },
    },
  });

  // Close the overflow menu on outside-click / Escape.
  useEffect(() => {
    if (!menuOpen) return undefined;
    const onDocPointer = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false);
    };
    const onKey = (e) => { if (e.key === 'Escape') setMenuOpen(false); };
    document.addEventListener('mousedown', onDocPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);

  // Block-type conversion lives here (moved off the old per-block toolbar).
  const setType = (type) => {
    if (editor) {
      const chain = editor.chain().focus();
      if (type === 'h1') chain.toggleHeading({ level: 1 }).run();
      else if (type === 'quote') chain.toggleBlockquote().run();
      else chain.setParagraph().run();
    }
    setMenuOpen(false);
  };

  const wash = block.color && block.color !== 'transparent' && block.color !== '#2a2a2a'
    ? block.color
    : 'transparent';

  return (
    <div
      className={`rich-text-block${isActive ? ' is-active' : ''}${isDropTarget ? ' is-drop-target' : ''}`}
      data-origin={block.origin || 'human'}
      style={{ backgroundColor: wash }}
      onDragEnter={() => onDragEnterBlock?.(block.id)}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => { e.preventDefault(); onDropBlock?.(block.id); }}
    >
      {/* Left gutter: drag handle + overflow menu (revealed on hover/active) */}
      <div className="block-gutter">
        <button
          type="button"
          className="block-drag-handle"
          title="Drag to reorder"
          aria-label="Drag to reorder block"
          draggable
          onDragStart={(e) => { e.dataTransfer.effectAllowed = 'move'; onDragStartBlock?.(block.id); }}
          onDragEnd={() => onDragEndBlock?.()}
        >
          <GripVertical size={15} />
        </button>

        <div className="block-menu" ref={menuRef}>
          <button
            type="button"
            className="block-menu-btn"
            title="Block options"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((o) => !o)}
          >
            <MoreHorizontal size={15} />
          </button>

          {menuOpen && (
            <div className="block-overflow" role="menu">
              <div className="block-overflow-group">
                <span className="block-overflow-label">Turn into</span>
                <button type="button" className="block-overflow-item" role="menuitem" onClick={() => setType('paragraph')}>
                  <Pilcrow size={14} /> Paragraph
                </button>
                <button type="button" className="block-overflow-item" role="menuitem" onClick={() => setType('h1')}>
                  <Heading1 size={14} /> Heading
                </button>
                <button type="button" className="block-overflow-item" role="menuitem" onClick={() => setType('quote')}>
                  <Quote size={14} /> Quote
                </button>
              </div>

              <div className="block-overflow-group">
                <span className="block-overflow-label">Colour</span>
                <div className="block-overflow-colors">
                  {COLOR_OPTIONS.map((color) => (
                    <button
                      key={color}
                      type="button"
                      className={`color-swatch${block.color === color ? ' active' : ''}`}
                      style={{ backgroundColor: color === 'transparent' ? 'var(--surface-2)' : color }}
                      title={color === 'transparent' ? 'Default' : 'Colour'}
                      aria-label={color === 'transparent' ? 'Default colour' : `Colour ${color}`}
                      onClick={() => onColorChange(block.id, color)}
                    >
                      {block.color === color && color !== 'transparent' && <Check size={12} />}
                    </button>
                  ))}
                </div>
              </div>

              <div className="block-overflow-group">
                <button type="button" className="block-overflow-item" role="menuitem" disabled={isFirst} onClick={() => { onMoveUp?.(block.id); setMenuOpen(false); }}>
                  <ChevronUp size={14} /> Move up
                </button>
                <button type="button" className="block-overflow-item" role="menuitem" disabled={isLast} onClick={() => { onMoveDown?.(block.id); setMenuOpen(false); }}>
                  <ChevronDown size={14} /> Move down
                </button>
                <button type="button" className="block-overflow-item danger" role="menuitem" onClick={() => { onDelete(block.id); setMenuOpen(false); }}>
                  <Trash2 size={14} /> Delete
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Block body: the editor + a selection bubble for inline formatting */}
      <div className="block-body">
        {editor && (
          <BubbleMenu editor={editor} className="bubble-toolbar">
            <button
              type="button"
              className={`bubble-btn${editor.isActive('bold') ? ' is-active' : ''}`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => editor.chain().focus().toggleBold().run()}
              title="Bold"
            >
              <Bold size={15} />
            </button>
            <button
              type="button"
              className={`bubble-btn${editor.isActive('italic') ? ' is-active' : ''}`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => editor.chain().focus().toggleItalic().run()}
              title="Italic"
            >
              <Italic size={15} />
            </button>
            <button
              type="button"
              className={`bubble-btn${editor.isActive('underline') ? ' is-active' : ''}`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => editor.chain().focus().toggleUnderline().run()}
              title="Underline"
            >
              <UnderlineIcon size={15} />
            </button>
          </BubbleMenu>
        )}
        <EditorContent editor={editor} className="editor-content-wrapper" />
      </div>
    </div>
  );
}

export default RichTextBlock;
