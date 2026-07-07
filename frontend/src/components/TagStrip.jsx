// frontend/src/components/TagStrip.jsx
// One home for tags across both modes (Lane 4 meta-foot).
//  - mode="view"  → read-only chips
//  - mode="edit"  → chips-with-remove + popular row + add input, sticky & collapsible
// All tag capability (display / add / remove / popular) lives here now; the old
// .tags-section (view) and .tags-edit-section (edit) homes are gone.

import { useState } from 'react';
import { Plus, X, Tag, ChevronDown } from 'lucide-react';

function TagStrip({
  mode = 'view',
  // view
  tags = [],
  // edit
  editedTags = [],
  popularTags = [],
  currentTagInput = '',
  onTagInputChange,
  onAddTag,
  onRemoveTag,
  onAddPopularTag,
  onTagInputKeyDown,
}) {
  const [collapsed, setCollapsed] = useState(false);

  // View mode: quiet read-only chips. Render nothing when there are none so the
  // meta-foot doesn't show an empty labelled band.
  if (mode !== 'edit') {
    if (!tags || tags.length === 0) return null;
    return (
      <div className="tag-strip tag-strip-view">
        <span className="tag-strip-label"><Tag size={12} /> Tags</span>
        <ul className="tags-list">
          {tags.map((tag) => (
            <li key={tag} className="tag-item">{tag}</li>
          ))}
        </ul>
      </div>
    );
  }

  // Edit mode: sticky, collapsible so tags stay reachable while writing a long column.
  return (
    <div className={`tag-strip tag-strip-edit${collapsed ? ' collapsed' : ''}`}>
      <button
        type="button"
        className="tag-strip-head"
        aria-expanded={!collapsed}
        onClick={() => setCollapsed(c => !c)}
      >
        <span className="tag-strip-label"><Tag size={12} /> Tags</span>
        {editedTags.length > 0 && <span className="tag-strip-count">{editedTags.length}</span>}
        <ChevronDown size={14} className="tag-strip-caret" />
      </button>

      {!collapsed && (
        <div className="tags-card">
          <div className="tags-container">
            {editedTags.map(tag => (
              <span key={tag} className="tag-item">
                {tag}
                <button onClick={() => onRemoveTag(tag)} className="remove-tag-btn">
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>

          {popularTags.length > 0 && (
            <div className="popular-tags-row">
              <span className="popular-tags-label">Popular:</span>
              {popularTags.filter(tag => !editedTags.includes(tag)).slice(0, 5).map(tag => (
                <button key={tag} onClick={() => onAddPopularTag(tag)} className="popular-tag-btn">
                  <Plus size={10} /> {tag}
                </button>
              ))}
            </div>
          )}

          <div className="tag-input-row">
            <input
              type="text"
              placeholder="Add tag..."
              value={currentTagInput}
              onChange={(e) => onTagInputChange(e.target.value)}
              onKeyDown={onTagInputKeyDown}
              className="tag-input"
            />
            <button className="action-btn tag-add-btn" onClick={onAddTag}><Plus size={16} /> Add</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default TagStrip;
