// frontend/src/components/PostDetailPage.jsx
// LeetCode-style split-screen layout with Highlights feature

import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useParams, Link, useNavigate, useLocation } from 'react-router-dom';
import { PanelGroup, Panel, PanelResizeHandle } from 'react-resizable-panels';
import axios from 'axios';
import { ArrowLeft, Sparkles, Plus, X, ChevronRight, ChevronLeft, BookOpen, Trash2, Edit, Save, XCircle, Highlighter, Underline, PenLine, MoreHorizontal } from 'lucide-react';
import RegionSurface from './RegionSurface';
import DifferentialWorkspace from '../differential/DifferentialWorkspace';
import Manuscript from './blocknote/Manuscript';
import ChatbotPanel from './ChatbotPanel';
import StoryFlow from './StoryFlow';
import TagStrip from './TagStrip';
import RefPicker from './RefPicker';
import PassageInspector from '../manuscript/PassageInspector';
import { API_URL } from '../config/api';
import { epicService } from '../services/epicService';
import { RegionStoreContext, useRegionState } from '../state/regionStore';
import { canCiteMark } from '../differential/suggestionQuarantine';
import { crossPostReference } from '../differential/visualMarks';
import { resolveCrossPost, crossPostNote, crossPostResolves } from '../differential/crossPost';
import { emptyHandoff, requestHandoff, canFlush, completeHandoff, wasDelivered } from '../state/manuscriptHandoff';
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

// Field | Manuscript split sizes (% of the row) — react-resizable-panels props.
const SPLIT_DEFAULT = 45; // resting ratio
const SPLIT_MIN = 20;
const SPLIT_MAX = 80;
const SPLIT_RAIL = 4;     // collapsed "focus the writing" rail

function PostDetailPage() {
  const [post, setPost] = useState(null);
  const { postId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  // P5-A · the crossing. When a foreign chip's source is gone, we STATE the loss rather than
  // crash or silently no-op — this holds that honest note for a moment (matches recall's tone).
  const [crossPostNotice, setCrossPostNotice] = useState('');

  const [isEditing, setIsEditing] = useState(false);
  const [editedBlocks, setEditedBlocks] = useState([]);
  const [editedTags, setEditedTags] = useState([]);
  const [currentTagInput, setCurrentTagInput] = useState('');
  const [popularTags, setPopularTags] = useState([]);
  const [loadingPopularTags, setLoadingPopularTags] = useState(false);
  // Field | Manuscript split is owned by react-resizable-panels (persists via
  // autoSaveId); we track only whether the Field is collapsed, for the toggle icon.
  const [isCollapsed, setIsCollapsed] = useState(false);
  // 'regions' by default: the unified pane IS the working surface; 'image' hides the
  // overlay for a clean look at the photograph.
  const [activeLeftTab, setActiveLeftTab] = useState('regions');
  // Differential (v1) is a full-workspace MODE, not a route: unsaved Manuscript
  // content lives in this component's state (editedBlocks), and a route change
  // would unmount and silently lose it. The Chiasm shell stays mounted (hidden
  // via CSS) while Differential is open, so enter/leave loses nothing.
  const [workspaceMode, setWorkspaceMode] = useState('chiasm'); // 'chiasm' | 'differential'
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
  const [writingRegionId, setWritingRegionId] = useState(null); // "write about this part"
  // Minimal inline prompt for /write, positioned at the caret (viewport coords).
  const [slashPrompt, setSlashPrompt] = useState({ open: false, x: 0, y: 0 });
  // The /part · /lens picker, positioned at the caret the same way.
  const [refPicker, setRefPicker] = useState({ open: false, x: 0, y: 0, kind: 'part' });
  // Unconceal (per-image microscopic context)
  // Aletheia reading, curator commentary and region detection all moved into
  // VisualPane (Track D) — they belong beside the image, not in a tab across the split.
  const [topbarMenuOpen, setTopbarMenuOpen] = useState(false); // "⋯" overflow (Delete)
  const contentAreaRef = useRef(null);
  const topbarMenuRef = useRef(null);
  const fieldPanelRef = useRef(null); // the Field Panel imperative handle (collapse/expand)
  const blockSeq = useRef(0); // monotonic, avoids Date.now() id collisions within a ms

  // The regions and the reading, held once for both panes (Visual↔Content). The Visual
  // pane marks them; the story points at them. Declared before the `!post` early return
  // so the hook order never changes, and it tolerates a null post while loading.
  const regionStore = useRegionState(post, setPost);
  // Dev affordance — inspect the shared Chiasm store from the console (Field↔Manuscript).
  useEffect(() => { if (import.meta.env?.DEV) window.__chiasm = regionStore; }, [regionStore]);

  // Chip → Field: the regionRef chip emits semant:region-* DOM events; they drive the
  // store (hover throttled to one write per frame so rapid hover targets the highlight,
  // not a doc re-render). RegionSurface reads store.hoveredId/selectedId — no cross-pane
  // DOM coupling. A store ref keeps the listeners registered once.
  const storeRef = useRef(regionStore);
  storeRef.current = regionStore;
  useEffect(() => {
    let raf = null;
    let pending = null;
    const flush = () => { raf = null; storeRef.current.setHoveredId(pending); };
    const onHover = (e) => {
      // A percept OR mark chip's ids are GROUND ids — hovering lights the evidence
      // channel, not the region channel. Regular chips behave as before.
      if (e.detail?.markId || e.detail?.perceptId?.startsWith?.('pctx_')) {
        storeRef.current.setHoveredGroundId((e.detail.regionIds || [])[0] || null);
        return;
      }
      storeRef.current.setHoveredGroundId?.(null);
      pending = (e.detail?.regionIds || [])[0] || null;
      if (raf == null) raf = requestAnimationFrame(flush);
    };
    const onFocus = (e) => {
      // Mention focus → recall. A percept-Mention replays the noticing; a mark-Mention
      // (CIRCUIT-001 P3-A) performs the mark. Either way the Field pane must be visible,
      // so expand a collapsed one first. `markId` is checked before percept: a mark chip
      // carries ground ids in regionIds but is NOT a region focus.
      if (e.detail?.markId) {
        setActiveLeftTab('regions');
        if (fieldPanelRef.current?.isCollapsed()) fieldPanelRef.current.expand();
        storeRef.current.playMarkRecall(e.detail.markId);
        return;
      }
      if (e.detail?.perceptId?.startsWith?.('pctx_')) {
        setActiveLeftTab('regions');
        if (fieldPanelRef.current?.isCollapsed()) fieldPanelRef.current.expand();
        storeRef.current.playRecall(e.detail.perceptId);
        return;
      }
      const ids = e.detail?.regionIds || [];
      if (ids.length) storeRef.current.focusRegions(ids);
    };
    window.addEventListener('semant:region-hover', onHover);
    window.addEventListener('semant:region-focus', onFocus);
    return () => {
      window.removeEventListener('semant:region-hover', onHover);
      window.removeEventListener('semant:region-focus', onFocus);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  // P5-A · the crossing lands. When we arrived here via a foreign chip (navigate carried
  // `crossRecall` in router state), perform the armed focus once THIS post has loaded — the
  // recall then runs natively, as if the noticing had been made here. We clear the router state
  // afterward so a refresh does not re-fire, and surface staleness as an honest note.
  useEffect(() => {
    const cr = location.state?.crossRecall;
    if (!cr || !post) return;
    setActiveLeftTab('regions');
    if (fieldPanelRef.current?.isCollapsed()) fieldPanelRef.current.expand();
    if (cr.regionId) storeRef.current.focusRegions([cr.regionId]);
    if (cr.stale) setCrossPostNotice('Source has changed since cited — showing it as it stands now.');
    // Drop the one-shot instruction so navigating back / refreshing does not replay it.
    navigate(location.pathname, { replace: true, state: {} });
  }, [location.key, post?.id]);

  // The crossing note is a brief, honest breath — let it settle like recall's calm does.
  useEffect(() => {
    if (!crossPostNotice) return undefined;
    const t = setTimeout(() => setCrossPostNotice(''), 6000);
    return () => clearTimeout(t);
  }, [crossPostNotice]);

  // Close the topbar "⋯" overflow on outside-click / Escape.
  useEffect(() => {
    if (!topbarMenuOpen) return undefined;
    const onDocPointer = (e) => {
      if (topbarMenuRef.current && !topbarMenuRef.current.contains(e.target)) setTopbarMenuOpen(false);
    };
    const onKey = (e) => { if (e.key === 'Escape') setTopbarMenuOpen(false); };
    document.addEventListener('mousedown', onDocPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [topbarMenuOpen]);

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

  // "Focus the writing" — collapse the Field to a rail, or bring it back. Drag +
  // keyboard resize + min/max clamp are handled natively by <PanelResizeHandle>.
  const toggleCollapse = () => {
    const panel = fieldPanelRef.current;
    if (!panel) return;
    if (panel.isCollapsed()) panel.expand(); else panel.collapse();
  };

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
  // ── CIRCUIT-001 P1B — the Differential → Manuscript crossing ────────────────
  // A REQUEST, not a call. See state/manuscriptHandoff.js for why the same-tick
  // call in P1A could not work.
  const [handoff, setHandoff] = useState(emptyHandoff);

  const sendPerceptToManuscript = (percept) => {
    if (!percept?.id) return;
    // Leave Differential, make sure the writing surface will actually exist
    // (<Manuscript> renders only while editing), and put the story tab in front.
    setWorkspaceMode('chiasm');
    setActiveRightTab('content');
    // `seed: false` — on an empty story the percept's own chip is the first
    // thing in the document; a seeded blank paragraph would sit above it.
    if (!isEditing) startEditing({ seed: false });
    setHandoff((h) => requestHandoff(h, percept));
    // The crossing must be FELT. Play the percept on the image so its grounds
    // light and its expression speaks while the chip lands in the writing —
    // otherwise the surface simply navigates away and the noticing is lost from
    // view at the exact moment it travels.
    regionStore.playRecall(percept.id);
  };

  // Flush when — and only when — the editor is genuinely there. Runs on every
  // render; `canFlush` is the whole guard, and `completeHandoff` makes delivery
  // at-most-once so a remount cannot produce a second chip.
  useEffect(() => {
    const handle = manuscriptRef.current;
    if (!canFlush(handoff, { isEditing, hasHandle: !!handle })) return;
    const percept = handoff.percept;
    if (wasDelivered(handoff, percept.id)) { setHandoff(completeHandoff); return; }
    // Insert against the block the editor is actually on, not a stale ref.
    insertRef(percept, 'percept', handle.currentBlockId?.() || null);
    setHandoff(completeHandoff);
    handle.focus?.();
  });   // eslint-disable-line react-hooks/exhaustive-deps -- must re-check after every render until the editor mounts

  // ── CIRCUIT-001 P2C-MS2 — Manuscript circulation actions ────────────────────
  // The writing acting back on the image and on Differential. All are safe: none
  // mutates the corpus, none dispatches a model, none autosaves. They are the
  // return leg the P2C-MS report named as the smallest useful piece of the
  // circuit's governing rule — nothing may leave the circuit without being able
  // to return.
  const recallFromManuscript = (perceptId) => {
    if (perceptId) regionStore.playRecall(perceptId);
  };

  // CIRCUIT-001 P2E — a sentence or percept expression carried into Differential's
  // First Attention. Seeds the prompt; the curator still presses "Suggest acts".
  // Cleared on exit so a later manual open of Differential does not re-seed.
  const [firstAttentionPrefill, setFirstAttentionPrefill] = useState(null);

  const reviseInDifferential = (perceptId) => {
    if (!perceptId) return;
    const percept = (regionStore.percepts || []).find((p) => p.id === perceptId);
    // P2E: the percept's own expression seeds First Attention — you land in
    // Differential already holding what the writing said about it.
    if (percept?.expression) setFirstAttentionPrefill(percept.expression);
    setWorkspaceMode('differential');
    // Return to where the percept was formed: light its grounds and replay the
    // noticing so the crossing is felt, not merely navigated. If the grounds no
    // longer resolve, playRecall already refuses to point at nothing (P1B).
    const regionIds = (percept?.ground_ids || [])
      .map((gid) => regionStore.groundById(gid)?.region_id)
      .filter(Boolean);
    if (regionIds.length) regionStore.focusRegions(regionIds);
    regionStore.playRecall(perceptId);
  };

  const startPassageFromChip = (blockId) => {
    // The inspector only mounts while editing, so the editor handle is present.
    manuscriptRef.current?.startPassage?.({ blockId: blockId || null });
  };

  const sendSelectionToDifferential = (text) => {
    // The reverse crossing for prose: return to the image side AND seed First
    // Attention with the sentence (P2E — the MS2 deferred caveat, now wired). It
    // does not auto-submit and it mutates nothing.
    if (text && text.trim()) setFirstAttentionPrefill(text.trim());
    setWorkspaceMode('differential');
  };

  const exitDifferential = () => {
    setWorkspaceMode('chiasm');
    // Consume the prefill so opening Differential manually later starts blank.
    setFirstAttentionPrefill(null);
  };

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

  // --- "Write about this part" ---------------------------------------------------
  // The Visual pane's answer to the blank page: pick a part, and Sutradhar writes from
  // what you noticed about it. The server grounds the call in this image's reading and
  // the curator's taste (Anuraṇana); the ask below only has to point at ONE part, and
  // to carry that part's own note — the context pack caps its note list, so a region
  // the curator hasn't prioritised could otherwise be missing from its own briefing.
  const buildRegionPrompt = (region, lens) => {
    const what = [region.category, region.material].filter(Boolean).join(' · ');
    const lines = [
      `Write about a single part of this image: "${region.label || 'this part'}"${what ? ` (${what})` : ''}.`,
    ];
    const note = (region.user_note || '').trim();
    if (note) lines.push(`What this person said about it, in their own words: "${note}"`);
    if (lens?.reading) lines.push(`The ${lens.name} lens reads it as: "${lens.reading}"`);
    lines.push(
      'Stay with this one part — do not describe the whole image.',
      // Handing the note over invites the model to hand it straight back. It did: the
      // first draft opened by repeating the curator's own sentence at them. The note is
      // evidence of what they noticed, not a line to be quoted.
      'Never repeat their words back to them. Write from what they noticed, in their voice.',
      'Two short paragraphs. No preamble, no heading. Return only the passage.',
    );
    return lines.join('\n');
  };

  const escHtml = (s) => String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  // The seeded block opens with a chip, so the passage is visibly *about* that part and
  // clicking it walks straight back to the polygon it came from.
  const withChip = (region, html) => {
    const label = escHtml(region.label || 'part');
    const chip = `<span data-region-ref data-ref-kind="part" data-region-ids="${escHtml(region.id)}"`
      + ` data-label="${label}" class="ref-chip ref-chip--part">${label}</span>`;
    return html.replace('<p>', `<p>${chip} `);
  };

  const writeAboutRegion = async (region) => {
    if (!region || writingRegionId) return;
    // `seed: false` — on an empty story the generated block IS the first block; seeding
    // an empty paragraph would leave a blank line above every passage written this way.
    if (!isEditing) startEditing({ seed: false });
    setActiveRightTab('content');
    setAiError('');
    setWritingRegionId(region.id);
    setAiBusy('part');
    try {
      const prompt = buildRegionPrompt(region, regionStore.lensFor(region.id));
      const res = await epicService.promptEnhancedText(post.photo_url, prompt);
      const text = res?.suggestion;
      if (!text) throw new Error('No suggestion returned');
      const handle = manuscriptRef.current;
      if (!handle) throw new Error('editor not ready');
      // A grounded sutradhar block (origin sutradhar), led by the chip of the region
      // it interprets. The Mention interprets (block form); Region.block_id stays primary.
      const percept = regionStore.ensurePercept(region);
      const inlineContentId = `ic_${Date.now().toString(36)}_${icSeq.current++}`;
      const newBlockId = handle.insertSutradharBlock({
        text,
        chipProps: { refKind: 'part', regionIds: region.id, label: region.label || 'part', perceptId: percept?.id || '' },
      });
      regionStore.addMention({
        perceptId: percept?.id || null, regionId: region.id, blockId: newBlockId, inlineContentId,
        form: 'block', relationType: 'interprets', actor: 'sutradhar',
      });
      if (newBlockId) regionStore.linkRegionToBlock(region.id, newBlockId);
    } catch {
      setAiError('Could not write about that part. Is the vision service running?');
    } finally {
      setWritingRegionId(null);
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

  // --- Inline references into the image (/part, /lens) -------------------------------
  // The editor whose caret the picker opened at. Held in a ref, not state: the picker's
  // own input takes focus, and by the time a row is clicked React's selection state
  // would be a render behind.
  // The Manuscript editor handle + the block the picker opened at (held in refs:
  // the picker's own input takes focus, so React state would be a render behind).
  const manuscriptRef = useRef(null);
  const refBlockIdRef = useRef(null);
  const icSeq = useRef(0);

  // /part · /lens in Manuscript → open the RefPicker at the caret, remembering the
  // block so the chip (and its Mention) land in the right place after the pick.
  const onRefTrigger = (kind) => {
    let x = 0; let y = 0;
    try {
      const rect = window.getSelection()?.getRangeAt(0)?.getBoundingClientRect();
      if (rect) { x = rect.left; y = rect.bottom; }
    } catch { /* no selection */ }
    refBlockIdRef.current = manuscriptRef.current?.currentBlockId?.() || null;
    setRefPicker({ open: true, x, y, kind });
  };

  const closeRefPicker = () => setRefPicker({ open: false, x: 0, y: 0, kind: 'part' });

  // Legacy Path-A entry (RichTextBlock is no longer rendered) — kept so refCommandRef
  // resolves; routes to the same picker.
  const runRefSlashCommand = ({ key } = {}) => onRefTrigger(key || 'part');

  /** Drop the chip in Manuscript AND record the Mention (Region.block_id kept primary). */
  // `kindOverride` lets a caller that did not come through the RefPicker say what
  // it is inserting — the Differential artery (CIRCUIT-001 P1A Part A) inserts a
  // percept without a slash command, and must reuse THIS path rather than build a
  // second one, so the two can never drift.
  //
  // `blockIdOverride` matters for the queued handoff: `refBlockIdRef` is written
  // by the slash-command flow only (onRefTrigger), so a crossing that never typed
  // "/" would otherwise land against a stale block id from a previous insertion.
  const insertRef = (raw, kindOverride = null, blockIdOverride = undefined) => {
    const kind = kindOverride || refPicker.kind;
    const blockId = blockIdOverride !== undefined ? blockIdOverride : refBlockIdRef.current;
    closeRefPicker();
    const handle = manuscriptRef.current;
    if (!handle) return;

    const inlineContentId = `ic_${Date.now().toString(36)}_${icSeq.current++}`;

    if (kind === 'lens') {
      const regionIds = raw.region_ids || [];
      // A lens cites several regions — one Mention per region, all in this block.
      regionIds.forEach((rid) => regionStore.addMention({
        regionId: rid, blockId, inlineContentId, form: 'inline', relationType: 'cites', actor: 'human',
      }));
      handle.insertRegionChip({ refKind: 'lens', regionIds: regionIds.join(','), label: raw.name, blockId });
      return;
    }

    if (kind === 'part-block') {
      // The evidence BLOCK form — sustained attention; a Mention that INTERPRETS.
      const percept = regionStore.ensurePercept(raw);
      const newBlockId = handle.insertPartBlock({
        regionId: raw.id, perceptId: percept?.id || '', label: raw.label || 'part', origin: 'human', blockId,
      });
      regionStore.addMention({
        perceptId: percept?.id || null, regionId: raw.id, blockId: newBlockId, inlineContentId,
        form: 'block', relationType: 'interprets', actor: 'human',
      });
      if (newBlockId) regionStore.linkRegionToBlock(raw.id, newBlockId);
      return;
    }

    if (kind === 'percept') {
      // A percept-Mention: the chip carries the pctx id (recall trigger) and the
      // GROUND ids in regionIds (the chip machinery is id-agnostic). Focus/click
      // routes to playRecall via the perceptId, never to region selection.
      const label = (raw.expression || 'percept').length > 46
        ? `${raw.expression.slice(0, 43)}…` : (raw.expression || 'percept');
      const mention = regionStore.addMention({
        perceptId: raw.id, regionId: null, blockId, inlineContentId,
        form: 'inline', relationType: 'cites', actor: 'human',
      });
      handle.insertRegionChip({
        refKind: 'percept', regionIds: (raw.ground_ids || []).join(','), label,
        perceptId: raw.id, mentionId: mention?.id || '', blockId,
      });
      return;
    }

    if (kind === 'mark') {
      // A mark-Mention (CIRCUIT-001 P3-A). The RefPicker only offers citable marks,
      // but this is the ENFORCING seam: even a caller that reached here another way
      // cannot cite a suggestion/draft. Fails closed — no chip, no Mention — because
      // a chip on the page IS a claim of evidence, and the claim must be earned.
      if (!canCiteMark(raw)) return;
      const label = (raw.label || raw.role || raw.type || 'mark').replace(/_/g, ' ');
      // P5-A · the crossing. A cited mark whose geometry references ANOTHER post carries the
      // border on its chip: the source post id rides along so a click resolves + navigates
      // there. A same-post mark leaves it null and the chip is byte-identical to before.
      const crossRef = crossPostReference(raw);
      const crossPost = crossRef?.post_id || '';
      const mention = regionStore.addMention({
        markId: raw.id, perceptId: null, regionId: null, blockId, inlineContentId,
        postId: crossPost || null, form: 'inline', relationType: 'cites', actor: 'human',
      });
      handle.insertRegionChip({
        refKind: 'mark', regionIds: (raw.linked_ground_ids || []).join(','), label,
        markId: raw.id, mentionId: mention?.id || '', blockId,
        ...(crossPost ? { postId: crossPost } : {}),
      });
      return;
    }

    // /part — inserting a reference IS attention: ensure the Percept, write the Mention.
    const percept = regionStore.ensurePercept(raw);
    const mention = regionStore.addMention({
      perceptId: percept?.id || null, regionId: raw.id, blockId, inlineContentId,
      form: 'inline', relationType: 'cites', actor: 'human',
    });
    if (blockId) regionStore.linkRegionToBlock(raw.id, blockId); // Region.block_id — primary edge
    handle.insertRegionChip({
      refKind: 'part', regionIds: raw.id, label: raw.label || 'part',
      perceptId: percept?.id || '', mentionId: mention?.id || '', blockId,
    });
  };

  // Stable handles passed into each block editor; always call the latest closure.
  const aiCommandRef = useRef(null);
  aiCommandRef.current = runAiSlashCommand;
  const onAiCommand = useCallback((args) => aiCommandRef.current?.(args), []);

  const refCommandRef = useRef(null);
  refCommandRef.current = runRefSlashCommand;
  const onRefCommand = useCallback((args) => refCommandRef.current?.(args), []);

  // Read when the menu opens, so a part marked (or a reading run) after this editor
  // was created still offers its command.
  const refCountsRef = useRef(null);
  refCountsRef.current = () => ({
    parts: regionStore.regions.length,
    lenses: (regionStore.aletheia?.lenses || []).length,
  });
  const refCounts = useCallback(() => refCountsRef.current(), []);

  // --- Visual ↔ Content: the two directions of the same edge --------------------------
  //
  // region → block. Which blocks talk about the hovered part? Two sources, because two
  // things can create the edge: a chip the curator inserted (ids live in the block's
  // markup) and Region.block_id (written when that chip landed, and by "write about this
  // part"). Reading both means a block still lights up when a chip is deleted but the
  // block_id survives, and vice versa — the link degrades instead of vanishing.
  // `post` is still null while loading — these hooks run before the early return.
  const liveBlocks = useMemo(
    () => (isEditing ? editedBlocks : (post?.text_blocks || [])),
    [isEditing, editedBlocks, post],
  );

  const blockRegionIds = useMemo(() => {
    const map = new Map();
    for (const b of liveBlocks) {
      const ids = new Set();
      const re = /data-region-ids="([^"]*)"/g;
      let m;
      while ((m = re.exec(b.content || '')) !== null) {
        m[1].split(',').forEach((id) => id && ids.add(id));
      }
      map.set(b.id, ids);
    }
    return map;
  }, [liveBlocks]);

  const linkedBlockIds = useMemo(() => {
    const focus = regionStore.hoveredId;
    if (!focus) return new Set();
    const linked = new Set();
    for (const [blockId, ids] of blockRegionIds) if (ids.has(focus)) linked.add(blockId);
    const region = regionStore.regions.find((r) => r.id === focus);
    if (region?.block_id) linked.add(region.block_id);
    return linked;
  }, [regionStore.hoveredId, regionStore.regions, blockRegionIds]);

  // block → region. Delegated, so it catches chips in the TipTap editor and chips in the
  // read view's dangerouslySetInnerHTML alike — the read view has no React to bind to.
  const chipClickRef = useRef(null);
  chipClickRef.current = (e) => {
    const chip = e.target.closest?.('[data-region-ref]');
    if (!chip) return;

    // P5-A · the crossing. A chip whose source post is NOT the one we are on reaches across the
    // border. We resolve it truthfully — the reference lives on the local `region_ref` mark
    // (never on the chip alone), so we look the mark up, FETCH the source post (never assume it
    // loaded), and either navigate to it with recall armed, or STATE the loss. Never a crash,
    // never a silent no-op — a foreign chip degrades exactly as a detached ground does.
    const chipPostId = chip.getAttribute('data-post-id') || '';
    if (chipPostId && post && chipPostId !== post.id && chipPostId !== postId) {
      const localMarkId = chip.getAttribute('data-mark-id') || '';
      const localMark = (regionStore.visualMarks || []).find((m) => m.id === localMarkId);
      const ref = localMark ? crossPostReference(localMark) : null;
      if (!ref) {
        setCrossPostNotice('Evidence unavailable — the cited reference is no longer in this manuscript.');
        return;
      }
      const fetchPost = async (pid) => (await axios.get(`${API_URL}/api/v1/posts/${pid}`)).data;
      resolveCrossPost(ref, { fetchPost })
        .then((res) => {
          if (!crossPostResolves(res)) { setCrossPostNotice(crossPostNote(res)); return; }
          // Navigate to the source with the region focus armed; the existing recall performs
          // natively there. Carry staleness so the destination can state the drift in inspection
          // (the crossing still performs — drift is reported, never a reason to refuse).
          navigate(`/posts/${ref.post_id}`, {
            state: { crossRecall: { regionId: ref.region_id, stale: res.status === 'stale' } },
          });
        })
        .catch(() => setCrossPostNotice('Evidence unavailable — the source could not be reached.'));
      return;
    }

    // A mark chip performs its mark (recall), exactly as a percept chip does — its
    // data-region-ids carry GROUND ids for hover, but the click routes on the mark id.
    // Read view (dangerouslySetInnerHTML) + editor alike land here.
    const markId = chip.getAttribute('data-mark-id') || '';
    if (markId.startsWith('vm_')) {
      setActiveLeftTab('regions');
      if (fieldPanelRef.current?.isCollapsed()) fieldPanelRef.current.expand();
      regionStore.playMarkRecall(markId);
      setTimeout(() => {
        document.querySelector('.post-detail-left .rs-stage')
          ?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
      }, 60);
      return;
    }

    // A percept chip replays its noticing (recall), it does not select a region —
    // its data-region-ids carry GROUND ids. Read view + editor alike land here.
    const perceptId = chip.getAttribute('data-percept-id') || '';
    if (perceptId.startsWith('pctx_')) {
      setActiveLeftTab('regions');
      if (fieldPanelRef.current?.isCollapsed()) fieldPanelRef.current.expand();
      regionStore.playRecall(perceptId);
      setTimeout(() => {
        document.querySelector('.post-detail-left .rs-stage')
          ?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
      }, 60);
      return;
    }

    const ids = (chip.getAttribute('data-region-ids') || '').split(',').filter(Boolean);
    if (!ids.length) return;

    // The overlay is what does the highlighting, so a chip clicked while the pane is
    // showing the bare photograph must bring the regions back first.
    setActiveLeftTab('regions');
    if (fieldPanelRef.current?.isCollapsed()) fieldPanelRef.current.expand();
    regionStore.focusRegions(ids);

    // Let the pane re-render (and un-collapse) before we scroll to it.
    setTimeout(() => {
      document.querySelector('.post-detail-left .rs-stage')
        ?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
    }, 60);
  };

  useEffect(() => {
    const area = contentAreaRef.current;
    if (!area) return undefined;
    const onClick = (e) => chipClickRef.current?.(e);
    area.addEventListener('click', onClick);
    return () => area.removeEventListener('click', onClick);
  }, [post]);

  // A chip is lit when the image is looking at exactly what it points at. Painted after
  // every commit rather than toggled on click, because the read view's blocks are
  // `dangerouslySetInnerHTML` — React rewrites those children on re-render and would
  // silently wipe any class we set by hand. This makes the class a projection of the
  // store rather than a fact we have to keep true.
  useEffect(() => {
    const area = contentAreaRef.current;
    if (!area) return;
    const focus = regionStore.focusIds;
    area.querySelectorAll('[data-region-ref]').forEach((chip) => {
      const ids = (chip.getAttribute('data-region-ids') || '').split(',').filter(Boolean);
      // Set equality, not overlap: selecting one part must not light a lens chip that
      // merely happens to cite it among others.
      const lit = !!focus && ids.length === focus.size && ids.every((id) => focus.has(id));
      chip.classList.toggle('is-active', lit);
    });
  });

  const submitSlashWrite = () => {
    const instruction = aiPrompt.trim();
    if (!instruction) return;
    setSlashPrompt({ open: false, x: 0, y: 0 });
    setAiPrompt('');
    runAiGenerate('write', '', instruction);
  };

  // Esc puts a playing recall down and restores calm (matches Differential).
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape' && storeRef.current?.recall) storeRef.current.clearRecall();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

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
    <RegionStoreContext.Provider value={regionStore}>
    <div className={`post-detail-page${isEditing ? ' editing-mode' : ''}${workspaceMode === 'differential' ? ' differential-open' : ''}`}>
      {/* P5-A · the crossing degrades OUT LOUD. When a foreign chip's source is gone or drifted,
          say so — never a crash, never a silent no-op. A minimal, honest breath here; P5F: B5's
          Passage Rail may render this in its own idiom (a border-inspection surface). */}
      {crossPostNotice && (
        <div className="cross-post-notice" role="status" aria-live="polite"
          style={{ position: 'fixed', top: 12, left: '50%', transform: 'translateX(-50%)', zIndex: 200,
            padding: '8px 14px', borderRadius: 8, background: 'rgba(20,20,24,0.92)', color: '#f4f4f5',
            fontSize: 13, boxShadow: '0 4px 20px rgba(0,0,0,0.3)', maxWidth: '80vw' }}
          onClick={() => setCrossPostNotice('')}>
          {crossPostNotice}
        </div>
      )}
      {/* Differential — swaps in over the parked (still-mounted) Chiasm shell. */}
      {workspaceMode === 'differential' && (
        <DifferentialWorkspace
          post={post}
          store={regionStore}
          onExit={exitDifferential}
          firstAttentionPrefill={firstAttentionPrefill}
          /* The artery. A percept formed here could previously reach the writing
             only if the curator left, remembered it existed, typed /percept and
             found it again in a picker. Same insertion path as the slash command
             — deliberately, so the chip is identical either way. The Chiasm shell
             stays mounted while Differential is open, so the editor handle is
             already live and no remount is involved. */
          onSendToManuscript={sendPerceptToManuscript}
          onPostChange={setPost}
        />
      )}
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

      {/* "/part" and "/lens" — a picker of what the image already holds. */}
      {refPicker.open && (
        <RefPicker
          kind={refPicker.kind}
          x={refPicker.x}
          y={refPicker.y}
          regions={regionStore.regions}
          lenses={regionStore.aletheia?.lenses || []}
          percepts={(regionStore.percepts || []).filter((p) => String(p.id || '').startsWith('pctx_'))}
          grounds={regionStore.grounds || []}
          marks={regionStore.visualMarks || []}
          onPick={insertRef}
          onClose={closeRefPicker}
        />
      )}

      {/* Top Bar */}
      <div className={`post-detail-topbar${isEditing ? ' compact' : ''}`}>
        <div className="topbar-left">
          <Link to="/gallery" className="back-link">
            <ArrowLeft size={18} /> Gallery
          </Link>
          {/* Sutradhar — folded to a small quiet left label (no center slot). */}
          <span className="sutradhar-brand" title="सूत्रधार · the thread-holder">
            <span className="sd-name">Sutradhar</span>
          </span>
        </div>

        <div className="post-detail-actions">
          {isDirty && (
            <span className="dirty-pill" title="You have unsaved changes (⌘S to save)">
              <span className="dot" /> Unsaved
            </span>
          )}
          {/* AI Assistant — de-weighted to a quiet secondary (slash carries
              everyday AI; this opens the sidebar for occasional deep chat). */}
          <button
            className={`action-btn topbar-ai-btn secondary${isChatOpen ? ' active' : ''}`}
            onClick={() => setIsChatOpen(!isChatOpen)}
            title="Toggle AI Assistant"
          >
            <Sparkles size={16} /> AI Assistant
          </button>

          {/* Rare + destructive Delete tucked behind a "⋯" overflow. */}
          <div className="topbar-overflow" ref={topbarMenuRef}>
            <button
              type="button"
              className="action-btn topbar-overflow-btn"
              aria-haspopup="menu"
              aria-expanded={topbarMenuOpen}
              aria-label="More actions"
              title="More actions"
              onClick={() => setTopbarMenuOpen((o) => !o)}
            >
              <MoreHorizontal size={18} />
            </button>
            {topbarMenuOpen && (
              <div className="topbar-overflow-menu" role="menu">
                <button
                  type="button"
                  className="topbar-overflow-item danger"
                  role="menuitem"
                  onClick={() => { setTopbarMenuOpen(false); handleDelete(); }}
                >
                  <Trash2 size={16} /> Delete post
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Field | Manuscript split — react-resizable-panels; width persists via autoSaveId. */}
      <PanelGroup direction="horizontal" autoSaveId="chiasm-split" className="post-detail-split">
        {/* Field pane */}
        <Panel
          className="post-detail-left"
          ref={fieldPanelRef}
          collapsible
          collapsedSize={SPLIT_RAIL}
          minSize={SPLIT_MIN}
          maxSize={SPLIT_MAX}
          defaultSize={SPLIT_DEFAULT}
          onCollapse={() => setIsCollapsed(true)}
          onExpand={() => setIsCollapsed(false)}
        >
          <div className="panel-header">
            {/* Was a dead toggle (set state, rendered nothing). Now a real layer
                control over the one unified region surface. */}
            <div className="panel-tabs">
              <button
                className={`panel-tab ${activeLeftTab === 'image' ? 'active' : ''}`}
                onClick={() => setActiveLeftTab('image')}
              >
                Image
              </button>
              <button
                className={`panel-tab ${activeLeftTab === 'regions' ? 'active' : ''}`}
                onClick={() => setActiveLeftTab('regions')}
              >
                Regions
              </button>
            </div>
            {/* Right-aligned per-pane actions slot (kept for Lane 3 verbs). */}
            <div className="panel-actions">
              {/* The one quiet entry into the Differential workspace — Chiasm's
                  resting state stays calm; no permanent tool rail here. */}
              <button
                type="button"
                className="panel-diff-btn"
                title="Open Differential — construct Percepts from this image"
                onClick={() => setWorkspaceMode('differential')}
              >
                ◈ Differential
              </button>
            </div>
          </div>

          <div className="image-display">
            {/* Chiasm · Field — the advanced region surface (RegionSurface +
                Overlay + Lightbox), wired to the shared store so selection/hover
                and attention (percepts) are the single channel to Manuscript.
                Replaces the VisualPane per Track D. write-about-part re-wires in
                Phase 4. */}
            <RegionSurface
              post={post}
              aletheia={regionStore.aletheia}
              onPostChange={setPost}
              store={regionStore}
              onWriteAboutRegion={writeAboutRegion}
              writingRegionId={writingRegionId}
            />
          </div>
        </Panel>

        {/* Resize handle — drag + keyboard resize + min/max clamp are native; the
            button collapses the Field to a rail ("focus the writing"). */}
        <PanelResizeHandle className={`split-divider${isCollapsed ? ' collapsed' : ''}`}>
          <button
            type="button"
            className="divider-collapse-btn"
            aria-label={isCollapsed ? 'Expand the Field' : 'Collapse the Field to a rail'}
            title={isCollapsed ? 'Expand Field' : 'Collapse Field (focus writing)'}
            onClick={toggleCollapse}
          >
            {isCollapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
          </button>
        </PanelResizeHandle>

        {/* Manuscript pane */}
        <Panel className="post-detail-right" minSize={SPLIT_MIN}>
          <div className="panel-header">
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
                {/* Unconceal tab retired (Track D §4): the reading is only powerful
                    beside the parts it cites, so Aletheia + commentary now live in the
                    Visual pane. The right pane reclaims a tab. */}
              </div>
              {/* Right-aligned actions slot — entry to editing lives here. */}
              <div className="panel-actions">
                {!isEditing && (
                  <button
                    type="button"
                    className="panel-edit-btn"
                    title="Edit the story"
                    aria-label="Edit the story"
                    onClick={() => { setActiveRightTab('content'); startEditing(); }}
                  >
                    <Edit size={15} />
                  </button>
                )}
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
                          <h4>Manuscript</h4>
                        </div>
                        {/* Editor Path B — one BlockNote document (Manuscript)
                            replaces the Path-A per-block editors. Seeded from and
                            saved to text_blocks via the converter, so every block
                            id (and Highlight/Region cross-link) survives. The old
                            block/drag/insert handlers are now dead — removed in
                            Phase 5. */}
                        <Manuscript
                          ref={manuscriptRef}
                          initialBlocks={editedBlocks}
                          onChange={setEditedBlocks}
                          store={regionStore}
                          onRefTrigger={onRefTrigger}
                        />
                        {/* CIRCUIT-001 P2C-MS — the writing answering back. Read-only:
                            it listens to the chip's existing `semant:region-focus`
                            event and the live selection, and derives what the
                            selection rests on. It persists nothing, calls no model,
                            and creates no Mention. */}
                        <PassageInspector
                          store={regionStore}
                          blocks={editedBlocks}
                          postId={post?.id}
                          onRecall={recallFromManuscript}
                          onReviseInDifferential={reviseInDifferential}
                          onStartPassage={startPassageFromChip}
                          onSendToDifferential={sendSelectionToDifferential}
                        />
                        {aiError && <p className="composer-error">{aiError}</p>}
                      </div>
                    </div>
                  </div>
                ) : (!post.text_blocks || post.text_blocks.length === 0) ? (
                  <div className="story-empty">
                    <div className="story-empty-icon"><PenLine size={22} /></div>
                    <h3 className="story-empty-title">No story yet</h3>
                    <p className="story-empty-sub">
                      This image is still silent. Write its story — then type
                      <code>/</code> to let Sutradhar draft from what it sees.
                    </p>
                    <div className="story-empty-actions">
                      <button className="story-empty-btn primary" onClick={startEditing}>
                        <Edit size={15} /> Write the story
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
                        className={`text-block-item${linkedBlockIds.has(block.id) ? ' is-linked' : ''}`}
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
        </Panel>
      </PanelGroup>

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

      {/* Region detection is no longer a modal — it happens in the Visual pane itself. */}
    </div>
    </RegionStoreContext.Provider>
  );
}

export default PostDetailPage;
