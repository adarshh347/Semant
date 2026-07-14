import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import UploadForm from '../components/UploadForm';
import TagFilter from '../components/TagFilter';
import UntaggedImagesSidebar from '../components/UntaggedImagesSidebar';
import StoryFlow from '../components/StoryFlow';
import PhraseGenerator from '../components/PhraseGenerator';
import { useToast } from '../components/ui';

import { API_URL } from '../config/api';

const PAGE_SIZE = 50;

function GalleryPage() {
  const [selectedTag, setSelectedTag] = useState(null);
  const [summaryData, setSummaryData] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  // New state for story generation
  const [activePlotIndex, setActivePlotIndex] = useState(null);
  const [userCommentary, setUserCommentary] = useState("");
  const [generatedStory, setGeneratedStory] = useState(null);
  const [loadingStory, setLoadingStory] = useState(false);
  const [showUntaggedSidebar, setShowUntaggedSidebar] = useState(false);

  const queryClient = useQueryClient();
  const { toast } = useToast();

  // The archive read → TanStack Query `useInfiniteQuery`, keyed by tag. Pages are
  // fetched in order and appended; identical in-flight requests are deduped by
  // Query. This kills the old prev/next race structurally: there is no
  // `currentPage` state to fight a response echo, and no out-of-order axios call
  // can win — the cache owns page order.
  const {
    data,
    isLoading,
    isError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['posts', selectedTag],
    queryFn: async ({ pageParam }) => {
      let url = `${API_URL}/api/v1/posts?page=${pageParam}&limit=${PAGE_SIZE}`;
      if (selectedTag) url += `&tag=${selectedTag}`;
      const response = await axios.get(url);
      return response.data; // { posts, total_pages, current_page }
    },
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.current_page < lastPage.total_pages ? lastPage.current_page + 1 : undefined,
  });

  const posts = data?.pages.flatMap((page) => page.posts) ?? [];

  // Any write elsewhere (upload, phrase save, story attach) just invalidates the
  // cache; the infinite query refetches its pages.
  const refreshPosts = () => queryClient.invalidateQueries({ queryKey: ['posts'] });

  // Infinite scroll: an IntersectionObserver sentinel below the grid pulls the
  // next page as it nears the viewport. `hasNextPage`/`isFetchingNextPage` guard
  // against double-fetching.
  const sentinelRef = useRef(null);
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return undefined;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { rootMargin: '600px' },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  const handleAnalyzeTag = async () => {
    if (!selectedTag) return;
    setLoadingSummary(true);
    setSummaryData(null);
    setActivePlotIndex(null);
    setGeneratedStory(null);
    try {
      const response = await axios.get(`${API_URL}/api/v1/posts/summary/${selectedTag}`);
      setSummaryData(response.data);
    } catch (error) {
      console.error("Error fetching tag analysis:", error);
      setSummaryData({ summary: "Failed to generate summary.", plot_suggestions: [] });
    } finally {
      setLoadingSummary(false);
    }
  };

  const handleGenerateStory = async (plotSuggestion) => {
    setLoadingStory(true);
    setGeneratedStory(null);
    setShowUntaggedSidebar(false);
    try {
      const response = await axios.post(`${API_URL}/api/v1/posts/summary/generate_story`, {
        tag: selectedTag,
        plot_suggestion: plotSuggestion,
        user_commentary: userCommentary
      });
      setGeneratedStory(response.data.story);
      setShowUntaggedSidebar(true);
    } catch (error) {
      console.error("Error generating story:", error);
      toast({ variant: 'error', title: 'Story generation failed', description: 'Please try again.' });
    } finally {
      setLoadingStory(false);
    }
  };

  const handleImageSelect = () => {
    refreshPosts();
    toast({
      variant: 'success',
      title: 'Story linked to image',
      description: `Tag "${selectedTag}" was added.`,
    });
  };

  const handleTagSelect = (tag) => {
    setSelectedTag(tag); // new query key → the infinite list restarts at page 1
    setSummaryData(null);
    setActivePlotIndex(null);
    setGeneratedStory(null);
    setShowUntaggedSidebar(false);
  };

  return (
    <div className="main-content-card">
      <div className="page-header">
        <h1>Explore the Collection</h1>
        <p>"Every image is a story waiting to be told."</p>
      </div>

      <UploadForm onUploadSuccess={refreshPosts} />
      <hr />
      <TagFilter onTagSelect={handleTagSelect} />

      {selectedTag && (
        <div className="tag-analysis-section">
          <h3>Analysis for tag: <span style={{ color: 'var(--accent-primary)' }}>{selectedTag}</span></h3>

          {!summaryData && !loadingSummary && (
            <button
              onClick={handleAnalyzeTag}
              className="primary"
            >
              Generate Summary & Plot Suggestions
            </button>
          )}

          {loadingSummary && <p>Analyzing content with AI... Please wait...</p>}

          {summaryData && (
            <div className="analysis-results">
              <div className="summary-box">
                <h4>Summary</h4>
                <p>{summaryData.summary}</p>
              </div>

              <div className="plots-box">
                <h4>Plot Suggestions</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {summaryData.plot_suggestions.map((plot, index) => (
                    <div key={index}>
                      <button
                        className={`plot-btn ${activePlotIndex === index ? 'active' : ''}`}
                        onClick={() => {
                          if (activePlotIndex === index) {
                            setActivePlotIndex(null);
                          } else {
                            setActivePlotIndex(index);
                            setGeneratedStory(null);
                            setUserCommentary("");
                          }
                        }}
                      >
                        <strong>Suggestion {index + 1}</strong>
                        <span>{plot}</span>
                      </button>

                      {activePlotIndex === index && (
                        <div className="plot-detail-panel">
                          <p>Add your commentary or specific instructions for the story:</p>
                          <textarea
                            value={userCommentary}
                            onChange={(e) => setUserCommentary(e.target.value)}
                            placeholder="E.g., Make the tone dark and mysterious, focus on the character's redemption..."
                            className="commentary-input"
                          />
                          <button
                            onClick={() => handleGenerateStory(plot)}
                            disabled={loadingStory}
                            className="primary"
                          >
                            {loadingStory ? 'Generating Story...' : 'Generate Full Story'}
                          </button>

                          {generatedStory && (
                            <div className="generated-story-box">
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                                <h4 style={{ color: 'var(--accent-primary)', marginTop: 0, marginBottom: 0 }}>Generated Story</h4>
                              </div>
                              <p style={{ whiteSpace: 'pre-wrap', lineHeight: '1.8', marginBottom: '0' }}>{generatedStory}</p>
                              <StoryFlow story={generatedStory} detailLevel="med" />
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {isError && (
        <p style={{ textAlign: 'center', color: 'var(--ink-muted)' }}>Couldn't load the gallery.</p>
      )}
      {isLoading && posts.length === 0 && (
        <p style={{ textAlign: 'center', color: 'var(--ink-muted)' }}>Loading the collection…</p>
      )}

      <div className="gallery-grid">
        {posts.map((post) => (
          <div key={post.id} className="gallery-item">
            <Link to={`/posts/${post.id}`}>
              <img src={post.photo_url} alt={post.description || `Post ${post.id}`} loading="lazy" />
              {post.associated_epics && post.associated_epics.length > 0 && (
                <div className="epic-badge" title={`Linked to: ${post.associated_epics.map(e => e.title).join(', ')}`}>
                  📖
                </div>
              )}
            </Link>
            <PhraseGenerator post={post} onPhraseSaved={refreshPosts} />
          </div>
        ))}
      </div>

      {/* Infinite-scroll sentinel — nearing it fetches the next page. */}
      <div ref={sentinelRef} style={{ height: 1 }} aria-hidden="true" />
      {isFetchingNextPage && (
        <p style={{ textAlign: 'center', color: 'var(--ink-muted)' }}>Loading more…</p>
      )}
      {!hasNextPage && posts.length > 0 && (
        <p style={{ textAlign: 'center', color: 'var(--ink-subtle)', fontSize: '0.85rem' }}>
          That's everything.
        </p>
      )}

      <UntaggedImagesSidebar
        isVisible={showUntaggedSidebar}
        onClose={() => setShowUntaggedSidebar(false)}
        onImageSelect={handleImageSelect}
        selectedTag={selectedTag}
        story={generatedStory}
      />
    </div>
  );
}

export default GalleryPage;