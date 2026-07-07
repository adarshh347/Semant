// frontend/src/components/PostDetailPage.jsx
// LeetCode-style split-screen layout with Highlights feature

import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { ArrowLeft, Sparkles, Plus, X, ChevronRight, BookOpen, Trash2, Edit, Save, XCircle, Highlighter, Underline, PenLine, Eye, Scan } from 'lucide-react';
import BoundingBoxEditor from './BoundingBoxEditor';
import RegionDetectorModal from './RegionDetectorModal';
import RichTextBlock from './RichTextBlock';
import ChatbotPanel from './ChatbotPanel';
import StoryFlow from './StoryFlow';
import TagStrip from './TagStrip';
import ThemeToggle from './ThemeToggle';
import { API_URL } from '../config/api';
import { epicService } from '../services/epicService';
import './PostDetailPage.css';

// Convert plain AI text (paragraphs split by blank lines) into simple HTML blocks.
const htmlFromText = (text) =>
  (text || '')
    .split(/\n{2,}/)
    .map(p => p.trim())
    .filter(Boolean)
    .map(p => `<p>${p.replace(/\n/g, '<br/>')}</p>`)
    .join('') || `<p>${(text || '').trim()}</p>`;

// Strip HTML to count words / reading time.
const plainText = (html) => (html || '').replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ');

function PostDetailPage() {
  const [post, setPost] = useState(null);
  const { postId } = useParams();
  const navigate = useNavigate();

  const [isEditing, setIsEditing] = useState(false);
  const [editedBlocks, setEditedBlocks] = useState([]);
  const [editedTags, setEditedTags] = useState([]);
  const [currentTagInput, setCurrentTagInput] = useState('');
  const [popularTags, setPopularTags] = useState([]);
  const [loadingPopularTags, setLoadingPopularTags] = useState(false);
  const [leftPanelWidth, setLeftPanelWidth] = useState(45); // percentage
  const [activeLeftTab, setActiveLeftTab] = useState('image');
  const [activeRightTab, setActiveRightTab] = useState('content');
  const [isChatOpen, setIsChatOpen] = useState(false); // AI Sidebar toggle
  const [clickedNode, setClickedNode] = useState(null); // For node expansion in chatbot
  const [highlights, setHighlights] = useState([]); // Underlined text collection
  const [showUnderlineTooltip, setShowUnderlineTooltip] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });
  const [selectedText, setSelectedText] = useState('');
  const [selectedBlockId, setSelectedBlockId] = useState(null);
  const [activeBlockId, setActiveBlockId] = useState(null); // focused block in edit mode
  const [draggingId, setDraggingId] = useState(null);       // block being dragged
  const [dropTargetId, setDropTargetId] = useState(null);   // block hovered while dragging
  const [aiPrompt, setAiPrompt] = useState('');
  const [aiBusy, setAiBusy] = useState(null); // slash command key while running | null
  const [aiError, setAiError] = useState('');
  // Minimal inline prompt for /write, positioned at the caret (viewport coords).
  const [slashPrompt, setSlashPrompt] = useState({ open: false, x: 0, y: 0 });
  // Unconceal (per-image microscopic context)
  const [aletheia, setAletheia] = useState(null);     // { lenses, concealed, uncertainty }
  const [aletheiaBusy, setAletheiaBusy] = useState(false);
  const [commentary, setCommentary] = useState('');
  const [feedPersona, setFeedPersona] = useState(true);
  const [ctxBusy, setCtxBusy] = useState(false);
  const [ctxSavedAt, setCtxSavedAt] = useState(null);
  const [ctxError, setCtxError] = useState('');
  const [showAnatomy, setShowAnatomy] = useState(false);
  const dividerRef = useRef(null);
  const containerRef = useRef(null);
  const contentAreaRef = useRef(null);
  const blockSeq = useRef(0); // monotonic, avoids Date.now() id collisions within a ms

  // Handler for when a story flow node is clicked
  const handleFlowNodeClick = (nodeText) => {
    setClickedNode(nodeText);
    setIsChatOpen(true); // Open the AI sidebar with this context
  };

  const fetchPost = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/v1/posts/${postId}`);
      setPost(response.data);
      setEditedBlocks(response.data.text_blocks || []);
      setEditedTags(response.data.general_tags || []);
      setHighlights(response.data.highlights || []);
      const lc = response.data.local_context;
      if (lc) {
        setCommentary(lc.commentary || '');
        setAletheia(lc.aletheia || null);
        setCtxSavedAt(lc.updated_at || null);
      }
    } catch (error) {
      console.error("Error fetching post:", error);
    }
  };

  const fetchPopularTags = async () => {
    setLoadingPopularTags(true);
    try {
      const response = await axios.get(`${API_URL}/api/v1/posts/tags/popular?limit=10`);
      setPopularTags(response.data);
    } catch (error) {
      console.error("Error fetching popular tags:", error);
    } finally {
      setLoadingPopularTags(false);
    }
  };

  useEffect(() => {
    fetchPost();
    fetchPopularTags();
  }, [postId]);

  // Text selection handler for underlining
  const handleTextSelection = (e) => {
    if (isEditing) return; // Don't show underline option while editing

    const selection = window.getSelection();
    const text = selection.toString().trim();

    if (text && text.length > 0) {
      // Find which block the selection is in
      const range = selection.getRangeAt(0);
      const container = range.commonAncestorContainer;
      const blockElement = container.nodeType === 3
        ? container.parentElement?.closest('.text-block-item')
        : container.closest?.('.text-block-item');

      const blockId = blockElement?.getAttribute('data-block-id') || null;

      setSelectedText(text);
      setSelectedBlockId(blockId);

      // Position tooltip near selection
      const rect = range.getBoundingClientRect();
      setTooltipPosition({
        x: rect.left + rect.width / 2,
        y: rect.top - 10
      });
      setShowUnderlineTooltip(true);
    } else {
      setShowUnderlineTooltip(false);
    }
  };

  // Add highlight
  const handleAddHighlight = async () => {
    if (!selectedText) return;

    const newHighlight = {
      id: `hl_${Date.now()}`,
      text: selectedText,
      block_id: selectedBlockId,
      created_at: new Date().toISOString()
    };

    const updatedHighlights = [...highlights, newHighlight];
    setHighlights(updatedHighlights);
    setShowUnderlineTooltip(false);

    // Clear selection
    window.getSelection().removeAllRanges();
    setSelectedText('');

    // Save to backend
    try {
      await axios.patch(`${API_URL}/api/v1/posts/${postId}`, {
        highlights: updatedHighlights
      });
    } catch (error) {
      console.error("Error saving highlight:", error);
    }
  };

  // Remove highlight
  const handleRemoveHighlight = async (highlightId) => {
    const updatedHighlights = highlights.filter(h => h.id !== highlightId);
    setHighlights(updatedHighlights);

    // Save to backend
    try {
      await axios.patch(`${API_URL}/api/v1/posts/${postId}`, {
        highlights: updatedHighlights
      });
    } catch (error) {
      console.error("Error removing highlight:", error);
    }
  };

  // Jump from a highlight card back to where the quote lives in the story.
  // Uses the block_id saved with each highlight ↔ data-block-id on the reading
  // block. Switches to the Story tab first, then scrolls + briefly flashes the
  // target. Callers only pass a blockId when it resolves to a live block, so a
  // missing/stale link simply never becomes clickable (graceful degradation).
  const jumpToBlock = (blockId) => {
    if (!blockId) return;
    setActiveRightTab('content');
    // Let the Story tab render before querying for the target node.
    setTimeout(() => {
      const el = contentAreaRef.current?.querySelector(`[data-block-id="${CSS.escape(blockId)}"]`);
      if (!el) return;
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.classList.add('block-flash');
      setTimeout(() => el.classList.remove('block-flash'), 1200);
    }, 60);
  };

  // Close tooltip when clicking elsewhere
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (!e.target.closest('.underline-tooltip')) {
        setShowUnderlineTooltip(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Resizable divider logic
  const isDraggingRef = useRef(false);

  const handleMouseDown = (e) => {
    isDraggingRef.current = true;
    dividerRef.current?.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  };

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDraggingRef.current || !containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const newWidth = ((e.clientX - containerRect.left) / containerRect.width) * 100;
      if (newWidth >= 20 && newWidth <= 80) {
        setLeftPanelWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      if (isDraggingRef.current) {
        isDraggingRef.current = false;
        dividerRef.current?.classList.remove('dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  const handleSave = async () => {
    try {
      const updatePayload = {
        text_blocks: editedBlocks,
        general_tags: editedTags
      };
      await axios.patch(`${API_URL}/api/v1/posts/${postId}`, updatePayload);
      fetchPost();
      setIsEditing(false);
    } catch (error) {
      console.error('Error updating post:', error);
      alert('Failed to save changes.');
    }
  };

  const handleDelete = async () => {
    if (window.confirm('Are you sure you want to delete this post?')) {
      try {
        await axios.delete(`${API_URL}/api/v1/posts/${postId}`);
        alert('Post deleted successfully.');
        navigate('/gallery');
      } catch (error) {
        console.error('Error deleting post:', error);
        alert('Failed to delete post.');
      }
    }
  };

  const handleBlockContentChange = (id, newContent) => {
    setEditedBlocks(currentBlocks =>
      currentBlocks.map(b => b.id === id ? { ...b, content: newContent } : b)
    );
  };

  const handleBlockColorChange = (id, newColor) => {
    setEditedBlocks(currentBlocks =>
      currentBlocks.map(b => b.id === id ? { ...b, color: newColor } : b)
    );
  };

  // Single block factory — every creation point flows through here so the
  // `origin` field is always set (human vs sutradhar). Id combines the clock
  // with a monotonic counter so two blocks made in the same ms never collide.
  const makeBlock = ({ type = 'paragraph', content = '', origin = 'human' }) => ({
    id: `block_${Date.now()}_${blockSeq.current++}`,
    type,
    content,
    color: 'transparent',
    origin,
  });

  // Single, position-aware insertion path. Inserts AFTER the active block
  // (or the caret's block); falls back to append when nothing is focused.
  const insertBlock = (block) => {
    setEditedBlocks(currentBlocks => {
      const i = activeBlockId ? currentBlocks.findIndex(b => b.id === activeBlockId) : -1;
      if (i < 0) return [...currentBlocks, block];
      const next = [...currentBlocks];
      next.splice(i + 1, 0, block);
      return next;
    });
    setActiveBlockId(block.id);
  };

  const addBlock = (type = 'paragraph') => {
    // Seed the TipTap node so Heading/Quote start in the right form.
    const seed = type === 'h1' ? '<h1></h1>' : type === 'quote' ? '<blockquote></blockquote>' : '';
    insertBlock(makeBlock({ type, content: seed, origin: 'human' }));
  };

  const deleteBlock = (id) => {
    const idx = editedBlocks.findIndex(b => b.id === id);
    const remaining = editedBlocks.filter(b => b.id !== id);
    setEditedBlocks(remaining);
    // Don't leave activeBlockId dangling on a removed block, or position-aware
    // insertion silently falls back to append. Move focus to a neighbour.
    if (id === activeBlockId) {
      const fallback = remaining[idx - 1] || remaining[idx] || null;
      setActiveBlockId(fallback ? fallback.id : null);
    }
  };

  const handleAddTag = () => {
    const newTag = currentTagInput.trim();
    if (newTag && !editedTags.includes(newTag)) {
      setEditedTags([...editedTags, newTag]);
      setCurrentTagInput('');
    }
  };

  const handleRemoveTag = (tagToRemove) => {
    setEditedTags(editedTags.filter(tag => tag !== tagToRemove));
  };

  const handleAddPopularTag = (tag) => {
    if (!editedTags.includes(tag)) {
      setEditedTags([...editedTags, tag]);
    }
  };

  const handleSuggestionSelect = (suggestion) => {
    // AI sidebar add-path — routes through the shared position-aware insertion.
    insertBlock(makeBlock({ type: 'paragraph', content: suggestion, origin: 'sutradhar' }));
  };

  const handleTagInputKeyDown = (event) => {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault();
      handleAddTag();
    }
  };

  // --- Reorder blocks (overflow menu: move up/down) ---
  const moveBlock = (id, dir) => {
    setEditedBlocks(blocks => {
      const i = blocks.findIndex(b => b.id === id);
      const j = i + dir;
      if (i < 0 || j < 0 || j >= blocks.length) return blocks;
      const next = [...blocks];
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });
  };

  // --- Reorder blocks (drag handle) ---
  const handleBlockDragEnter = (targetId) => {
    if (draggingId && targetId !== draggingId) setDropTargetId(targetId);
  };

  const handleBlockDrop = (targetId) => {
    setEditedBlocks(blocks => {
      if (!draggingId || draggingId === targetId) return blocks;
      const from = blocks.findIndex(b => b.id === draggingId);
      const to = blocks.findIndex(b => b.id === targetId);
      if (from < 0 || to < 0) return blocks;
      const next = [...blocks];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return next;
    });
    setDraggingId(null);
    setDropTargetId(null);
  };

  const handleBlockDragEnd = () => {
    setDraggingId(null);
    setDropTargetId(null);
  };

  // --- Dirty state (unsaved changes) ---
  const isDirty = useMemo(() => {
    if (!post || !isEditing) return false;
    const a = JSON.stringify({ b: editedBlocks, t: editedTags });
    const b = JSON.stringify({ b: post.text_blocks || [], t: post.general_tags || [] });
    return a !== b;
  }, [post, isEditing, editedBlocks, editedTags]);

  // --- Word count / reading time ---
  const wordStats = useMemo(() => {
    const words = editedBlocks
      .map(b => plainText(b.content))
      .join(' ')
      .trim()
      .split(/\s+/)
      .filter(Boolean).length;
    return { words, minutes: Math.max(1, Math.ceil(words / 200)) };
  }, [editedBlocks]);

  // --- AI composer (Sutradhar's quill) ---
  const existingTextForAI = () =>
    editedBlocks.map(b => plainText(b.content)).join('\n\n').trim();

  // Enter edit mode with the current post's blocks/tags loaded in.
  // On an empty story, seed one focused empty paragraph so the caret is ready
  // to type (skip when `seed:false`, e.g. the draft-from-image path fills it).
  const startEditing = ({ seed = true } = {}) => {
    setIsEditing(true);
    const existing = post.text_blocks || [];
    if (existing.length === 0 && seed) {
      const first = makeBlock({ type: 'paragraph' });
      setEditedBlocks([first]);
      setActiveBlockId(first.id);
    } else {
      setEditedBlocks(existing);
      setActiveBlockId(null);
    }
    setEditedTags(post.general_tags || []);
  };

  const draftFromImage = async () => {
    setAiError('');
    setAiBusy('draft');
    try {
      const res = await epicService.autoRecommendText(post.photo_url, existingTextForAI());
      const text = res?.suggestion;
      if (!text) throw new Error('No suggestion returned');
      insertBlock(makeBlock({ type: 'paragraph', content: htmlFromText(text), origin: 'sutradhar' }));
    } catch (e) {
      setAiError('Could not draft from the image. Is the vision service running?');
    } finally {
      setAiBusy(null);
    }
  };

  // --- Inline AI slash commands (Phase 2) — non-streaming, land as sutradhar blocks ---
  const currentNodeText = (editor) => {
    try { return (editor?.state.selection.$from.parent.textContent || '').trim(); }
    catch { return ''; }
  };

  const buildAiPrompt = (key, instruction, nodeText) => {
    switch (key) {
      case 'write': return instruction;
      case 'continue': return `Continue this passage naturally, matching its voice. Return only the continuation:\n\n${nodeText}`;
      case 'rewrite': return `Rewrite this passage for clarity and flow, keeping its meaning. Return only the rewrite:\n\n${nodeText}`;
      case 'expand': return `Expand this passage with vivid, relevant detail. Return only the expanded passage:\n\n${nodeText}`;
      case 'shorten': return `Shorten this passage to its essence, keeping the key meaning. Return only the shortened passage:\n\n${nodeText}`;
      default: return instruction || nodeText;
    }
  };

  // Runs a generation and inserts one sutradhar block after the current one.
  const runAiGenerate = async (key, nodeText, instruction) => {
    setAiError('');
    setAiBusy(key);
    try {
      let text;
      if (key === 'draft' || key === 'version') {
        const res = await epicService.autoRecommendText(post.photo_url, existingTextForAI());
        text = res?.suggestion;
      } else {
        const res = await epicService.promptEnhancedText(post.photo_url, buildAiPrompt(key, instruction, nodeText));
        text = res?.suggestion;
      }
      if (!text) throw new Error('No suggestion returned');
      insertBlock(makeBlock({ type: 'paragraph', content: htmlFromText(text), origin: 'sutradhar' }));
    } catch (e) {
      setAiError('Sutradhar could not write that. Is the vision service running?');
    } finally {
      setAiBusy(null);
    }
  };

  // Dispatched from the "/" menu (AI verbs). '/write' opens a minimal caret
  // prompt; everything else runs immediately over the current block's text.
  const runAiSlashCommand = ({ key, editor, range }) => {
    if (editor && range) editor.chain().focus().deleteRange(range).run();
    if (key === 'write') {
      let x = 0; let y = 0;
      try {
        const c = editor.view.coordsAtPos(editor.state.selection.from);
        x = c.left; y = c.bottom;
      } catch { /* fall back to 0,0 */ }
      setAiPrompt('');
      setSlashPrompt({ open: true, x, y });
      return;
    }
    runAiGenerate(key, currentNodeText(editor));
  };

  // Stable handle passed into each block editor; always calls the latest closure.
  const aiCommandRef = useRef(null);
  aiCommandRef.current = runAiSlashCommand;
  const onAiCommand = useCallback((args) => aiCommandRef.current?.(args), []);

  const submitSlashWrite = () => {
    const instruction = aiPrompt.trim();
    if (!instruction) return;
    setSlashPrompt({ open: false, x: 0, y: 0 });
    setAiPrompt('');
    runAiGenerate('write', '', instruction);
  };

  // --- Unconceal: Aletheia reading + curator commentary (microscopic context) ---
  const runAletheia = async () => {
    setCtxError(''); setAletheiaBusy(true);
    try {
      const res = await axios.post(`${API_URL}/api/v1/posts/brainstorm`, {
        image_url: post.photo_url,
        source_url: post.source_url || '',
      });
      // keep only the interpretive parts (drop the MCQ questions for the in-app note)
      const { lenses, concealed, uncertainty } = res.data || {};
      setAletheia({ lenses: lenses || [], concealed: concealed || '', uncertainty: uncertainty || '' });
    } catch (e) {
      setCtxError('Aletheia could not read this image (is the vision service running?).');
    } finally { setAletheiaBusy(false); }
  };

  const saveLocalContext = async () => {
    setCtxError(''); setCtxBusy(true);
    try {
      const res = await axios.post(`${API_URL}/api/v1/posts/${postId}/local-context`, {
        commentary,
        aletheia,
        feed_to_persona: feedPersona,
      });
      setCtxSavedAt(res.data?.post?.local_context?.updated_at || new Date().toISOString());
      setPost(res.data.post);
    } catch (e) {
      setCtxError('Could not save the context.');
    } finally { setCtxBusy(false); }
  };

  // --- Keyboard save (Cmd/Ctrl+S) + unsaved-changes guard ---
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') {
        if (isEditing) {
          e.preventDefault();
          handleSave();
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isEditing, editedBlocks, editedTags]);

  useEffect(() => {
    const onBeforeUnload = (e) => {
      if (isDirty) { e.preventDefault(); e.returnValue = ''; }
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [isDirty]);

  useEffect(() => {
    document.body.classList.toggle('post-detail-editing', isEditing);
    return () => document.body.classList.remove('post-detail-editing');
  }, [isEditing]);

  if (!post) {
    return (
      <div className="post-detail-page">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-secondary)' }}>
          Loading...
        </div>
      </div>
    );
  }

  return (
    <div className={`post-detail-page${isEditing ? ' editing-mode' : ''}`}>
      {/* Underline Tooltip */}
      {showUnderlineTooltip && (
        <div
          className="underline-tooltip"
          style={{
            position: 'fixed',
            left: tooltipPosition.x,
            top: tooltipPosition.y,
            transform: 'translate(-50%, -100%)',
            zIndex: 1000
          }}
        >
          <button onClick={handleAddHighlight} className="underline-btn">
            <Underline size={16} />
            <span>Underline</span>
          </button>
        </div>
      )}

      {/* Minimal inline prompt for "/write" — opens at the caret. */}
      {slashPrompt.open && (
        <div
          className="slash-prompt"
          style={{ position: 'fixed', left: slashPrompt.x, top: slashPrompt.y + 6, zIndex: 90 }}
        >
          <PenLine size={14} className="slash-prompt-icon" />
          <input
            autoFocus
            className="slash-prompt-input"
            placeholder="Tell Sutradhar what to write…"
            value={aiPrompt}
            onChange={(e) => setAiPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') { e.preventDefault(); submitSlashWrite(); }
              else if (e.key === 'Escape') { setSlashPrompt({ open: false, x: 0, y: 0 }); setAiPrompt(''); }
            }}
            onBlur={() => setSlashPrompt({ open: false, x: 0, y: 0 })}
          />
        </div>
      )}

      {/* Top Bar */}
      <div className={`post-detail-topbar${isEditing ? ' compact' : ''}`}>
        <Link to="/gallery" className="back-link">
          <ArrowLeft size={18} /> Gallery
        </Link>

        {/* Sutradhar — the thread-holder (editor identity) */}
        <div className="sutradhar-brand">
          <span className="sd-name">Sutradhar</span>
          <span className="sd-deva">सूत्रधार · the thread-holder</span>
        </div>

        <div className="post-detail-actions">
          {isDirty && (
            <span className="dirty-pill" title="You have unsaved changes (⌘S to save)">
              <span className="dot" /> Unsaved
            </span>
          )}
          <ThemeToggle />
          <button
            className={`action-btn topbar-ai-btn ${isChatOpen ? 'primary' : 'secondary'}`}
            onClick={() => setIsChatOpen(!isChatOpen)}
            title="Toggle AI Assistant"
          >
            <Sparkles size={16} /> AI Assistant
          </button>
          {!isEditing && (
            <button className="action-btn" onClick={startEditing}>
              <Edit size={16} /> Edit
            </button>
          )}
          <button className="action-btn danger" onClick={handleDelete}>
            <Trash2 size={16} /> Delete
          </button>
        </div>
      </div>

      {/* Split Container */}
      <div className="post-detail-split" ref={containerRef}>
        {/* Left Pane - Image */}
        <div className="post-detail-left" style={{ width: `${leftPanelWidth}%` }}>
          <div className="panel-header">
            <h3>Visual</h3>
            <div className="panel-tabs">
              <button
                className={`panel-tab ${activeLeftTab === 'image' ? 'active' : ''}`}
                onClick={() => setActiveLeftTab('image')}
              >
                Image
              </button>
              <button
                className={`panel-tab ${activeLeftTab === 'bbox' ? 'active' : ''}`}
                onClick={() => setActiveLeftTab('bbox')}
              >
                Annotations
              </button>
            </div>
          </div>

          <div className="image-display">
            <BoundingBoxEditor post={post} onUpdate={fetchPost} />
          </div>
        </div>

        {/* Resizable Divider */}
        <div
          className="split-divider"
          ref={dividerRef}
          onMouseDown={handleMouseDown}
          title="Drag to resize"
        ></div>

        {/* Right Pane - Content */}
        <div className="post-detail-right" style={{ width: `${100 - leftPanelWidth}%` }}>
          <div className="panel-header">
            <h3>Content</h3>
            <div className="panel-tabs">
              <button
                className={`panel-tab ${activeRightTab === 'content' ? 'active' : ''}`}
                onClick={() => setActiveRightTab('content')}
              >
                Story
              </button>
              <button
                className={`panel-tab ${activeRightTab === 'highlights' ? 'active' : ''}`}
                onClick={() => setActiveRightTab('highlights')}
              >
                <Highlighter size={14} style={{ marginRight: '0.3rem' }} />
                Highlights {highlights.length > 0 && <span className="highlight-count">{highlights.length}</span>}
              </button>
              <button
                className={`panel-tab ${activeRightTab === 'unconceal' ? 'active' : ''}`}
                onClick={() => setActiveRightTab('unconceal')}
                title="Aletheia reading + your own commentary, attached to this image"
              >
                <Eye size={14} style={{ marginRight: '0.3rem' }} />
                Unconceal {(post.local_context?.commentary || post.local_context?.aletheia) && <span className="highlight-count">•</span>}
              </button>
            </div>
          </div>

          <div className="content-area" ref={contentAreaRef} onMouseUp={handleTextSelection}>
            {activeRightTab === 'content' && (
              <div className="story-column">
                {/* Meta-head — identity for this image: provenance (@handle) and
                    an epic chip. Gated to the Story tab so it no longer bleeds
                    onto Highlights / Unconceal, and lives here only (Lane 1 must
                    not duplicate the handle in the topbar). */}
                {(post.instagram_handle || (post.associated_epics && post.associated_epics.length > 0)) && (
                  <div className="source-account-section meta-head">
                    {post.instagram_handle && post.source_account?.avatar_url && (
                      <img className="source-account-avatar" src={post.source_account.avatar_url} alt="" referrerPolicy="no-referrer" />
                    )}
                    {post.instagram_handle && (
                      <span className="source-account-text">
                        From <strong>@{post.instagram_handle}</strong>
                        {post.source_account?.display_name ? ` · ${post.source_account.display_name}` : ''}
                      </span>
                    )}
                    {(post.associated_epics || []).map(epic => (
                      <Link to={`/epics/${epic.epic_id}`} key={epic.epic_id} className="epic-chip" title={`Part of epic: ${epic.title}`}>
                        <BookOpen size={13} /> {epic.title}
                      </Link>
                    ))}
                    {post.instagram_handle && (
                      <Link to={`/personas#${post.instagram_handle}`} className="source-account-link">
                        Open persona →
                      </Link>
                    )}
                  </div>
                )}

                {isEditing ? (
                  <div className="edit-shell">
                    <div className="edit-layout">
                      <div className="edit-section">
                        <div className="edit-section-head">
                          <h4>Story blocks</h4>
                        </div>
                        <div className="advanced-editor">
                            {editedBlocks.map((block, index) => (
                              <RichTextBlock
                                key={block.id}
                                block={block}
                                onContentChange={handleBlockContentChange}
                                onColorChange={handleBlockColorChange}
                                onDelete={deleteBlock}
                                onMoveUp={(id) => moveBlock(id, -1)}
                                onMoveDown={(id) => moveBlock(id, 1)}
                                onFocusBlock={setActiveBlockId}
                                onAiCommand={onAiCommand}
                                isActive={block.id === activeBlockId}
                                isFirst={index === 0}
                                isLast={index === editedBlocks.length - 1}
                                onDragStartBlock={setDraggingId}
                                onDragEnterBlock={handleBlockDragEnter}
                                onDropBlock={handleBlockDrop}
                                onDragEndBlock={handleBlockDragEnd}
                                isDropTarget={block.id === dropTargetId}
                              />
                            ))}
                          </div>

                          {/* Insert row: a recognisable "+ Add block". Block types
                              AND AI verbs (/draft /write /continue /rewrite …) now
                              live on the "/" menu — no Compose button. */}
                          <div className="block-insert">
                            <button
                              type="button"
                              className="block-insert-trigger"
                              onClick={() => addBlock('paragraph')}
                              title="Add an empty block · then type / for block types or Sutradhar"
                            >
                              <Plus size={16} /> Add block
                            </button>
                            {aiBusy && (
                              <span className="ai-busy-pill" role="status">
                                <span className="sd-spin" /> Sutradhar is writing…
                              </span>
                            )}
                          </div>
                          {aiError && <p className="composer-error">{aiError}</p>}
                        </div>
                    </div>
                  </div>
                ) : (!post.text_blocks || post.text_blocks.length === 0) ? (
                  <div className="story-empty">
                    <div className="story-empty-icon"><PenLine size={22} /></div>
                    <h3 className="story-empty-title">No story yet</h3>
                    <p className="story-empty-sub">
                      This image is still silent. Write its story, or let Sutradhar
                      draft one from what it sees.
                    </p>
                    <div className="story-empty-actions">
                      <button className="story-empty-btn primary" onClick={startEditing}>
                        <Edit size={15} /> Write the story
                      </button>
                      <button
                        className="story-empty-btn"
                        onClick={() => { startEditing({ seed: false }); draftFromImage(); }}
                      >
                        <Sparkles size={15} /> Draft from image
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    {(post.text_blocks || []).map((block) => (
                      <div
                        key={block.id}
                        data-block-id={block.id}
                        data-origin={block.origin || 'human'}
                        className="text-block-item"
                        dangerouslySetInnerHTML={{ __html: block.content }}
                        style={{
                          backgroundColor: block.color && block.color !== 'inherit' && block.color !== '#2a2a2a' ? block.color : 'transparent',
                          padding: block.color && block.color !== 'inherit' && block.color !== 'transparent' ? '1rem' : '0 0 0 0.75rem',
                          borderRadius: 'var(--radius-md)'
                        }}
                      />
                    ))}

                    {/* Generate Flow Button - appears below story blocks in view mode */}
                    {post.text_blocks && post.text_blocks.length > 0 && (
                      <StoryFlow
                        story={post.text_blocks.map(b => b.content).join('\n\n')}
                        detailLevel="med"
                        imageUrl={post.photo_url}
                        onNodeClick={handleFlowNodeClick}
                        showGenerateButton={true}
                      />
                    )}
                  </>
                )}

                {/* Meta-foot — one home for tags, both modes. Sticky/collapsible
                    while editing so they stay reachable down a long column. */}
                <TagStrip
                  mode={isEditing ? 'edit' : 'view'}
                  tags={post.general_tags || []}
                  editedTags={editedTags}
                  popularTags={popularTags}
                  currentTagInput={currentTagInput}
                  onTagInputChange={setCurrentTagInput}
                  onAddTag={handleAddTag}
                  onRemoveTag={handleRemoveTag}
                  onAddPopularTag={handleAddPopularTag}
                  onTagInputKeyDown={handleTagInputKeyDown}
                />
              </div>
            )}

            {/* HIGHLIGHTS TAB (Replaced Flow Tab) */}
            {activeRightTab === 'highlights' && (
              <div className="highlights-section">
                <div className="highlights-header">
                  <Highlighter size={20} style={{ color: 'var(--accent-primary)' }} />
                  <h4>Your Highlights</h4>
                </div>

                {highlights.length === 0 ? (
                  <div className="empty-highlights">
                    <Underline size={48} style={{ color: 'var(--border-medium)', marginBottom: '1rem' }} />
                    <p>No highlights yet</p>
                    <p className="hint">Select text in the Story tab and click "Underline" to save passages here.</p>
                  </div>
                ) : (
                  <div className="highlights-list">
                    {highlights.map((highlight, index) => {
                      // Only offer the jump when the quote's source block still
                      // exists — a null or stale block_id degrades to a plain card.
                      const canJump = highlight.block_id
                        && (post.text_blocks || []).some(b => b.id === highlight.block_id);
                      return (
                        <div
                          key={highlight.id}
                          className={`highlight-card${canJump ? ' jumpable' : ''}`}
                          role={canJump ? 'button' : undefined}
                          tabIndex={canJump ? 0 : undefined}
                          title={canJump ? 'Jump to this passage in the story' : undefined}
                          onClick={canJump ? () => jumpToBlock(highlight.block_id) : undefined}
                          onKeyDown={canJump ? (e) => {
                            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); jumpToBlock(highlight.block_id); }
                          } : undefined}
                        >
                          <div className="highlight-number">{index + 1}</div>
                          <blockquote className="highlight-text">
                            "{highlight.text}"
                          </blockquote>
                          <button
                            className="remove-highlight-btn"
                            onClick={(e) => { e.stopPropagation(); handleRemoveHighlight(highlight.id); }}
                            title="Remove highlight"
                          >
                            <X size={14} />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* UNCONCEAL TAB — per-image microscopic context (Aletheia + your commentary) */}
            {activeRightTab === 'unconceal' && (
              <div className="unconceal-section">
                <div className="unconceal-intro">
                  <h4>Unconceal this image</h4>
                  <p>Let Aletheia read it, then add your own seeing. What you save attaches to this image{post.instagram_handle ? <> and can feed <strong>@{post.instagram_handle}</strong>’s persona</> : ''}.</p>
                </div>

                {/* Anatomy — clickable detected parts */}
                <div className="uncon-anatomy">
                  <div className="uncon-block-head">
                    <span className="uncon-kicker">Anatomy</span>
                    <button className="uncon-run-btn" onClick={() => setShowAnatomy(true)}>
                      <Scan size={14} /> Detect parts
                    </button>
                  </div>
                  {(post.region_annotations || []).filter(r => r.prioritised).length > 0 ? (
                    <div className="uncon-parts">
                      {(post.region_annotations || []).filter(r => r.prioritised).map(r => (
                        <span className="uncon-part-chip" key={r.id} title={r.user_note || r.description}>
                          {r.label}{r.weight ? ` · ${r.weight}` : ''}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="uncon-empty">Dissect the image into clickable parts, then star the ones that affect you and say how.</p>
                  )}
                </div>

                {/* Aletheia reading */}
                <div className="uncon-aletheia">
                  <div className="uncon-block-head">
                    <span className="uncon-kicker">Aletheia</span>
                    <button className="uncon-run-btn" onClick={runAletheia} disabled={aletheiaBusy}>
                      {aletheiaBusy ? <span className="sd-spin" /> : <Sparkles size={14} />}
                      {aletheia ? 'Re-read' : 'Read the image'}
                    </button>
                  </div>
                  {aletheia && (aletheia.lenses?.length > 0 || aletheia.concealed) ? (
                    <div className="uncon-reading">
                      {(aletheia.lenses || []).map((lens, i) => (
                        <div className="uncon-lens" key={i}>
                          <div className="uncon-lens-head">
                            <span className="uncon-lens-name">{lens.name}</span>
                            <span className="uncon-lens-pct">{lens.intensity ?? 0}</span>
                          </div>
                          <div className="uncon-bar"><span className="uncon-bar-fill" style={{ width: `${Math.max(0, Math.min(100, lens.intensity ?? 0))}%` }} /></div>
                          <p className="uncon-lens-reading">{lens.reading}</p>
                        </div>
                      ))}
                      {aletheia.concealed && <p className="uncon-foot"><strong>Concealed</strong> — {aletheia.concealed}</p>}
                      {aletheia.uncertainty && <p className="uncon-foot"><strong>Uncertain</strong> — {aletheia.uncertainty}</p>}
                    </div>
                  ) : (
                    <p className="uncon-empty">No reading yet — run Aletheia to get a starting interpretation, or write your own below.</p>
                  )}
                </div>

                {/* Curator commentary */}
                <div className="uncon-commentary">
                  <span className="uncon-kicker">Your unconcealment</span>
                  <textarea
                    className="uncon-textarea"
                    placeholder="What does this image do to you? What does it withhold? Write what only you can see…"
                    value={commentary}
                    onChange={(e) => setCommentary(e.target.value)}
                  />
                </div>

                {/* Save + feed toggle */}
                <div className="uncon-actions">
                  {post.instagram_handle && (
                    <label className="uncon-feed">
                      <input type="checkbox" checked={feedPersona} onChange={(e) => setFeedPersona(e.target.checked)} />
                      Also feed <strong>{(post.instagram_handles || [post.instagram_handle]).map(h => `@${h}`).join(' + ')}</strong>{(post.instagram_handles || []).length > 1 ? "’ personas" : "’s persona"}
                    </label>
                  )}
                  <button className="action-btn primary uncon-save" onClick={saveLocalContext} disabled={ctxBusy || (!commentary.trim() && !aletheia)}>
                    {ctxBusy ? <span className="sd-spin" /> : <Save size={16} />} Attach context
                  </button>
                  {ctxSavedAt && !ctxBusy && <span className="uncon-saved">saved {new Date(ctxSavedAt).toLocaleString()}</span>}
                </div>
                {ctxError && <p className="composer-error">{ctxError}</p>}
              </div>
            )}
          </div>

          {/* Edit actions */}
          {isEditing && (
            <div className="edit-actions">
              <div className="edit-statusline">
                <span><strong>{wordStats.words}</strong> words</span>
                <span><strong>{wordStats.minutes}</strong> min read</span>
                <span><strong>{editedBlocks.length}</strong> {editedBlocks.length === 1 ? 'block' : 'blocks'}</span>
              </div>
              <div className="edit-actions-buttons">
                <button
                  className={`action-btn${isDirty ? ' primary' : ''}`}
                  onClick={handleSave}
                  title={isDirty ? 'Save changes (⌘S)' : 'No unsaved changes'}
                ><Save size={16} /> Save</button>
                <button className="action-btn" onClick={() => {
                  setIsEditing(false);
                  setActiveBlockId(null);
                  setSlashPrompt({ open: false, x: 0, y: 0 });
                  setEditedTags(post.general_tags || []);
                  setEditedBlocks(post.text_blocks || []);
                }}>
                  <XCircle size={16} /> Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* AI Slide-out Sidebar */}
      <div className={`ai-sidebar-backdrop ${isChatOpen ? 'open' : ''}`} onClick={() => setIsChatOpen(false)}></div>
      <div className={`ai-sidebar ${isChatOpen ? 'open' : ''}`}>
        <div className="ai-sidebar-content">
          <ChatbotPanel
            imageUrl={post.photo_url}
            textBlocks={isEditing ? editedBlocks : (post.text_blocks || [])}
            onAddBlock={isEditing ? handleSuggestionSelect : undefined}
            initialPrompt={clickedNode}
            initialContext={post.text_blocks ? post.text_blocks.map(b => b.content).join('\n\n') : ''}
          />
        </div>
        <button
          className="ai-sidebar-close"
          onClick={() => setIsChatOpen(false)}
          title="Close AI Assistant"
        >
          <ChevronRight size={20} />
        </button>
      </div>

      {/* Anatomy — clickable region detection + per-part correspondence */}
      {showAnatomy && (
        <RegionDetectorModal
          post={post}
          onClose={() => setShowAnatomy(false)}
          onSaved={(updated) => { setPost(updated); }}
        />
      )}
    </div>
  );
}

export default PostDetailPage;
