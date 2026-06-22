import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import React from 'react';
import { Bold, Italic, Underline as UnderlineIcon, Quote, Heading1, Pilcrow, Trash2, ChevronUp, ChevronDown } from 'lucide-react';

const MenuBar = ({ editor }) => {
  if (!editor) return null;

  return (
    <div className="block-toolbar">
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
        className={`toolbar-btn ${editor.isActive('heading', { level: 1 }) ? 'is-active' : ''}`}
        title="Heading 1"
      >
        <Heading1 size={16} />
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().setParagraph().run()}
        className={`toolbar-btn ${editor.isActive('paragraph') ? 'is-active' : ''}`}
        title="Paragraph"
      >
        <Pilcrow size={16} />
      </button>
      <div className="toolbar-divider"></div>
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleBold().run()}
        className={`toolbar-btn ${editor.isActive('bold') ? 'is-active' : ''}`}
        title="Bold"
      >
        <Bold size={16} />
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleItalic().run()}
        className={`toolbar-btn ${editor.isActive('italic') ? 'is-active' : ''}`}
        title="Italic"
      >
        <Italic size={16} />
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleUnderline().run()}
        className={`toolbar-btn ${editor.isActive('underline') ? 'is-active' : ''}`}
        title="Underline"
      >
        <UnderlineIcon size={16} />
      </button>
      <button
        type="button"
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
        className={`toolbar-btn ${editor.isActive('blockquote') ? 'is-active' : ''}`}
        title="Quote"
      >
        <Quote size={16} />
      </button>
    </div>
  );
};

function RichTextBlock({ block, onContentChange, onColorChange, onDelete, onMoveUp, onMoveDown, isFirst, isLast }) {
  const editor = useEditor({
    extensions: [StarterKit, Underline],
    content: block.content,
    onUpdate: ({ editor }) => {
      onContentChange(block.id, editor.getHTML());
    },
    editorProps: {
      attributes: {
        class: 'prose prose-sm focus:outline-none',
      },
    },
  });

  // Use CSS variables for theme-aware colors if possible, but valid hex needed for style prop
  // If we want color coding, we should stick to hex.
  const colorOptions = ['transparent', '#fef3c7', '#dcfce7', '#dbeafe', '#f3e8ff', '#fee2e2'];

  return (
    <div className="rich-text-block" style={{ backgroundColor: block.color && block.color !== '#2a2a2a' ? block.color : 'transparent' }}>
      <MenuBar editor={editor} />
      <EditorContent editor={editor} className="editor-content-wrapper" />
      <div className="block-controls">
        <div className="block-actions-left">
          {(onMoveUp || onMoveDown) && (
            <div className="block-move-group">
              <button
                type="button"
                className="block-move-btn"
                onClick={() => onMoveUp?.(block.id)}
                disabled={isFirst}
                title="Move up"
              >
                <ChevronUp size={16} />
              </button>
              <button
                type="button"
                className="block-move-btn"
                onClick={() => onMoveDown?.(block.id)}
                disabled={isLast}
                title="Move down"
              >
                <ChevronDown size={16} />
              </button>
            </div>
          )}
          <div className="color-picker">
            {colorOptions.map(color => (
              <button
                key={color}
                onClick={() => onColorChange(block.id, color)}
                style={{ backgroundColor: color === 'transparent' ? 'var(--bg-secondary)' : color }}
                className={`color-swatch ${block.color === color ? 'active' : ''}`}
                title={color === 'transparent' ? 'Default' : 'Color'}
              />
            ))}
          </div>
        </div>
        <button onClick={() => onDelete(block.id)} className="delete-block-btn" title="Delete block">
          <Trash2 size={16} />
        </button>
      </div>
    </div>
  );
}

export default RichTextBlock;