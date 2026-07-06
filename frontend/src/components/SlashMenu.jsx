import React, { forwardRef, useEffect, useImperativeHandle, useState } from 'react';

/**
 * The floating "/" command menu. Rendered once per active suggestion by
 * slashCommand.jsx and positioned at the caret with floating-ui. Phase 1 lists
 * block types only (paragraph / heading / quote) — no AI actions yet.
 *
 * Keyboard: ↑/↓ move, Enter selects, Esc closes (handled upstream). The parent
 * suggestion plugin forwards keydowns via the imperative `onKeyDown` handle.
 */
const SlashMenu = forwardRef(function SlashMenu({ items, command }, ref) {
  const [selectedIndex, setSelectedIndex] = useState(0);

  // Reset the cursor whenever the filtered list changes so it never points past
  // the end of a shorter list.
  useEffect(() => setSelectedIndex(0), [items]);

  const selectItem = (index) => {
    const item = items[index];
    if (item) command(item);
  };

  useImperativeHandle(ref, () => ({
    onKeyDown: ({ event }) => {
      if (!items.length) return false;
      if (event.key === 'ArrowUp') {
        setSelectedIndex((i) => (i + items.length - 1) % items.length);
        return true;
      }
      if (event.key === 'ArrowDown') {
        setSelectedIndex((i) => (i + 1) % items.length);
        return true;
      }
      if (event.key === 'Enter') {
        selectItem(selectedIndex);
        return true;
      }
      return false;
    },
  }));

  if (!items.length) {
    return <div className="slash-menu slash-menu--empty">No matching blocks</div>;
  }

  return (
    <div className="slash-menu" role="listbox" aria-label="Insert block">
      {items.map((item, index) => (
        <button
          key={item.title}
          type="button"
          role="option"
          aria-selected={index === selectedIndex}
          className={`slash-menu-item${index === selectedIndex ? ' is-selected' : ''}`}
          onMouseEnter={() => setSelectedIndex(index)}
          // mousedown (not click) + preventDefault keeps the editor selection
          // alive so deleteRange targets the right spot.
          onMouseDown={(e) => { e.preventDefault(); selectItem(index); }}
        >
          <span className="slash-menu-icon">{item.icon}</span>
          <span className="slash-menu-body">
            <span className="slash-menu-title">{item.title}</span>
            <span className="slash-menu-desc">{item.description}</span>
          </span>
        </button>
      ))}
    </div>
  );
});

export default SlashMenu;
