// frontend/src/components/PostDetailPage.jsx
// LeetCode-style split-screen layout with Highlights feature

import { useState, useEffect, useRef, useMemo } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { ArrowLeft, Sparkles, Plus, X, ChevronRight, BookOpen, Trash2, Edit, Save, XCircle, Highlighter, Underline, Pilcrow, Heading1, Quote, Wand2, PenLine, Eye, Scan } from 'lucide-react';
import BoundingBoxEditor from './BoundingBoxEditor';
import RegionDetectorModal from './RegionDetectorModal';
import RichTextBlock from './RichTextBlock';
import ChatbotPanel from './ChatbotPanel';
import StoryFlow from './StoryFlow';
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
  const [aiPrompt, setAiPrompt] = useState('');
  const [aiBusy, setAiBusy] = useState(null); // 'draft' | 'write' | null
  const [aiError, setAiError] = useState('');
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

  const addBlock = (type = 'paragraph') => {
    // Seed the TipTap node so Heading/Quote start in the right form.
    const seed = type === 'h1' ? '<h1></h1>' : type === 'quote' ? '<blockquote></blockquote>' : '';
    const newBlock = { id: `block_${Date.now()}`, type, content: seed, color: 'transparent' };
    setEditedBlocks(currentBlocks => [...currentBlocks, newBlock]);
  };

  const deleteBlock = (id) => {
    setEditedBlocks(currentBlocks => currentBlocks.filter(b => b.id !== id));
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
    const newBlock = {
      id: `block_${Date.now()}`,
      type: 'paragraph',
      content: suggestion,
      color: 'transparent'
    };
    setEditedBlocks([...editedBlocks, newBlock]);
  };

  const handleTagInputKeyDown = (event) => {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault();
      handleAddTag();
    }
  };

  // --- Reorder blocks ---
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

  const draftFromImage = async () => {
    setAiError('');
    setAiBusy('draft');
    try {
      const res = await epicService.autoRecommendText(post.photo_url, existingTextForAI());
      const text = res?.suggestion;
      if (!text) throw new Error('No suggestion returned');
      setEditedBlocks(blocks => [
        ...blocks,
        { id: `block_${Date.now()}`, type: 'paragraph', content: htmlFromText(text), color: 'transparent' },
      ]);
    } catch (e) {
      setAiError('Could not draft from the image. Is the vision service running?');
    } finally {
      setAiBusy(null);
    }
  };

  const writeFromPrompt = async () => {
    const prompt = aiPrompt.trim();
    if (!prompt) return;
    setAiError('');
    setAiBusy('write');
    try {
      const res = await epicService.promptEnhancedText(post.photo_url, prompt);
      const text = res?.suggestion;
      if (!text) throw new Error('No suggestion returned');
      setEditedBlocks(blocks => [
        ...blocks,
        { id: `block_${Date.now()}`, type: 'paragraph', content: htmlFromText(text), color: 'transparent' },
      ]);
      setAiPrompt('');
    } catch (e) {
      setAiError('Could not write from that prompt. Is the vision service running?');
    } finally {
      setAiBusy(null);
    }
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
    <div className="post-detail-page">
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

      {/* Top Bar */}
      <div className="post-detail-topbar">
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
            className={`action-btn ${isChatOpen ? 'primary' : 'secondary'}`}
            onClick={() => setIsChatOpen(!isChatOpen)}
            title="Toggle AI Assistant"
            style={{ marginRight: '1rem' }}
          >
            <Sparkles size={16} /> AI Assistant
          </button>
          {!isEditing && (
            <button className="action-btn" onClick={() => {
              setIsEditing(true);
              setEditedBlocks(post.text_blocks || []);
              setEditedTags(post.general_tags || []);
            }}>
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
            {/* Source account (Darpan persona context attached at save time) */}
            {post.instagram_handle && (
              <div className="source-account-section">
                {post.source_account?.avatar_url && (
                  <img className="source-account-avatar" src={post.source_account.avatar_url} alt="" referrerPolicy="no-referrer" />
                )}
                <span className="source-account-text">
                  From <strong>@{post.instagram_handle}</strong>
                  {post.source_account?.display_name ? ` · ${post.source_account.display_name}` : ''}
                </span>
                <Link to={`/personas#${post.instagram_handle}`} className="source-account-link">
                  Open persona →
                </Link>
              </div>
            )}

            {/* Epic Association */}
            {post.associated_epics && post.associated_epics.length > 0 && (
              <div className="epic-badge-section">
                <h5>Part of Epic</h5>
                {post.associated_epics.map(epic => (
                  <Link to={`/epics/${epic.epic_id}`} key={epic.epic_id} className="epic-link">
                    <BookOpen size={14} /> {epic.title}
                  </Link>
                ))}
              </div>
            )}

            {activeRightTab === 'content' && (
              <>
                {isEditing ? (
                  <div className="edit-section">
                    <div className="edit-section-head">
                      <h4>Story Blocks</h4>
                    </div>
                    <div className="editor-meta">
                      <span><strong>{wordStats.words}</strong> words</span>
                      <span><strong>{wordStats.minutes}</strong> min read</span>
                      <span><strong>{editedBlocks.length}</strong> {editedBlocks.length === 1 ? 'block' : 'blocks'}</span>
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
                          isFirst={index === 0}
                          isLast={index === editedBlocks.length - 1}
                        />
                      ))}
                    </div>
                    <div className="editor-subsection editor-tools-section">
                      <div className="subsection-heading">
                        <span className="subsection-kicker">Add block</span>
                        <p>Insert a new passage, heading, or pull-quote into the draft.</p>
                      </div>
                      <div className="add-block-menu">
                        <button className="add-block-btn" onClick={() => addBlock('paragraph')}>
                        <Pilcrow size={15} /> Paragraph
                        </button>
                        <button className="add-block-btn" onClick={() => addBlock('h1')}>
                        <Heading1 size={15} /> Heading
                        </button>
                        <button className="add-block-btn" onClick={() => addBlock('quote')}>
                        <Quote size={15} /> Quote
                        </button>
                      </div>
                    </div>

                    {/* Sutradhar's quill — AI composition from the image */}
                    <div className="editor-subsection sutradhar-composer">
                      <div className="composer-head">
                        <div className="composer-heading">
                          <span className="sd-spark"><Wand2 size={16} /></span>
                          <span>Compose with Sutradhar</span>
                        </div>
                        <p>Use the image as a prompt, or steer the voice with a short instruction.</p>
                      </div>
                      <div className="composer-row">
                        <button
                          className="composer-btn"
                          onClick={draftFromImage}
                          disabled={aiBusy !== null}
                          title="Let the image speak — drafts a passage from what's seen"
                        >
                          {aiBusy === 'draft' ? <span className="sd-spin" /> : <Sparkles size={15} />}
                          Draft from image
                        </button>
                      </div>
                      <div className="composer-row composer-row-tight">
                        <input
                          className="composer-input"
                          placeholder="Tell Sutradhar what to write…"
                          value={aiPrompt}
                          onChange={(e) => setAiPrompt(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && aiBusy === null && writeFromPrompt()}
                          disabled={aiBusy !== null}
                        />
                        <button
                          className="composer-btn primary"
                          onClick={writeFromPrompt}
                          disabled={aiBusy !== null || !aiPrompt.trim()}
                        >
                          {aiBusy === 'write' ? <span className="sd-spin" /> : <PenLine size={15} />}
                          Write
                        </button>
                      </div>
                      <p className="composer-hint">New passages are appended as blocks — reorder or edit them above, then Save.</p>
                      {aiError && <p className="composer-error">{aiError}</p>}
                    </div>

                    <div className="edit-section" style={{ marginTop: '2rem' }}>
                      <h4>Tags</h4>
                      <div className="tags-container" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '0.5rem' }}>
                        {editedTags.map(tag => (
                          <span key={tag} className="tag-item">
                            {tag}
                            <button
                              onClick={() => handleRemoveTag(tag)}
                              className="remove-tag-btn"
                            >
                              <X size={12} />
                            </button>
                          </span>
                        ))}
                      </div>

                      {popularTags.length > 0 && (
                        <div style={{ marginBottom: '0.5rem' }}>
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>Popular: </span>
                          {popularTags.filter(tag => !editedTags.includes(tag)).slice(0, 5).map(tag => (
                            <button
                              key={tag}
                              onClick={() => handleAddPopularTag(tag)}
                              className="popular-tag-btn"
                            >
                              <Plus size={10} /> {tag}
                            </button>
                          ))}
                        </div>
                      )}

                      <div style={{ display: 'flex', gap: '0.4rem' }}>
                        <input
                          type="text"
                          placeholder="Add tag..."
                          value={currentTagInput}
                          onChange={(e) => setCurrentTagInput(e.target.value)}
                          onKeyDown={handleTagInputKeyDown}
                          className="tag-input"
                        />
                        <button className="action-btn" onClick={handleAddTag}><Plus size={16} /> Add</button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <>
                    {/* Hint for underlining */}
                    {post.text_blocks && post.text_blocks.length > 0 && (
                      <div className="underline-hint">
                        <Highlighter size={14} />
                        <span>Select text to underline and save to Highlights</span>
                      </div>
                    )}

                    {(post.text_blocks || []).map((block) => (
                      <div
                        key={block.id}
                        data-block-id={block.id}
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
              </>
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
                    {highlights.map((highlight, index) => (
                      <div key={highlight.id} className="highlight-card">
                        <div className="highlight-number">{index + 1}</div>
                        <blockquote className="highlight-text">
                          "{highlight.text}"
                        </blockquote>
                        <button
                          className="remove-highlight-btn"
                          onClick={() => handleRemoveHighlight(highlight.id)}
                          title="Remove highlight"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ))}
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

          {/* Tags display (when not editing) */}
          {!isEditing && activeRightTab === 'content' && (
            <div className="tags-section">
              <h4>Tags</h4>
              <ul className="tags-list">
                {(post.general_tags || []).map((tag) => (
                  <li key={tag} className="tag-item">{tag}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Edit actions */}
          {isEditing && (
            <div className="edit-actions">
              <button className="action-btn primary" onClick={handleSave}><Save size={16} /> Save</button>
              <button className="action-btn" onClick={() => {
                setIsEditing(false);
                setEditedTags(post.general_tags || []);
                setEditedBlocks(post.text_blocks || []);
              }}>
                <XCircle size={16} /> Cancel
              </button>
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
