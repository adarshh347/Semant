import { useState } from 'react';
import axios from 'axios';
import { useQuery } from '@tanstack/react-query';
import TextPostCard from '../components/TextPostCard'; // Use the feed card
import { API_URL } from '../config/api';
import EmptyState from '../components/brand/EmptyState';
import { FeedSkeleton } from '../components/brand/Skeleton';

function TextFeedPage() {
  const [currentPage, setCurrentPage] = useState(1);

  // Feed read → TanStack Query. Uses the shared API_URL (previously hardcoded
  // to a stale :5008, which bypassed the .env backend).
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['feed', currentPage],
    queryFn: async () => {
      const response = await axios.get(
        `${API_URL}/api/v1/posts/with-text?page=${currentPage}&limit=20`,
      );
      return response.data;
    },
    placeholderData: (prev) => prev,
  });

  const posts = data?.posts ?? [];
  const totalPages = data?.total_pages ?? 0;

  return (
    <div className="main-content-card"> {/* Wrap in the standard card for consistent padding/background */}
      <div className="page-header">
        <h1>Latest Stories</h1>
        <p>Explore posts with rich descriptions.</p>
      </div>

      {isLoading && posts.length === 0 ? (
        <FeedSkeleton count={4} />
      ) : isError ? (
        <EmptyState
          tone="error"
          motif="stack"
          title="Couldn't load the feed"
          body="Something interrupted the connection. Give it another try in a moment."
          action={{ onClick: () => refetch(), label: 'Try again' }}
        />
      ) : (
        <>
          <div className="highlights-feed"> {/* Use the feed layout class */}
            {posts.length > 0 ? (
              posts.map(post => (
                <TextPostCard key={post.id} post={post} />
              ))
            ) : (
              <EmptyState
                motif="stack"
                title="No stories yet"
                body="Posts with written descriptions gather here. Read an image to write the first one."
                action={{ to: '/gallery', label: 'Open the Archive' }}
              />
            )}
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
             <div className="pagination" style={{ marginTop: '2rem' }}>
                <button onClick={() => setCurrentPage(p => p - 1)} disabled={currentPage === 1}>
                &larr; Previous
                </button>
                <span>Page {currentPage} of {totalPages}</span>
                <button onClick={() => setCurrentPage(p => p + 1)} disabled={currentPage >= totalPages}>
                Next &rarr;
                </button>
             </div>
          )}
        </>
      )}
    </div>
  );
}
export default TextFeedPage;
