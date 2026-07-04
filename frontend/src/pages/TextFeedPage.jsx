
import { useState, useEffect } from 'react';
import axios from 'axios';
import TextPostCard from '../components/TextPostCard'; // Use the feed card
const API_URL = 'http://127.0.0.1:5008';


function TextFeedPage() {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);

  const fetchTextPosts = async (page) => {
    try {
      setLoading(true);
      // Fetches posts with text_blocks, 20 per page
      const response = await axios.get(`${API_URL}/api/v1/posts/with-text?page=${page}&limit=20`);
      setPosts(response.data.posts);
      setTotalPages(response.data.total_pages);
      setCurrentPage(response.data.current_page);
    } catch (error) {
      console.error("Error fetching text posts:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTextPosts(currentPage);
  }, [currentPage]);

  return (
    <div className="main-content-card"> {/* Wrap in the standard card for consistent padding/background */}
      <div className="page-header">
        <h1>Latest Stories</h1>
        <p>Explore posts with rich descriptions.</p>
      </div>

      {loading ? (
        <p style={{ textAlign: 'center' }}>Loading feed...</p>
      ) : (
        <>
          <div className="highlights-feed"> {/* Use the feed layout class */}
            {posts.length > 0 ? (
              posts.map(post => (
                <TextPostCard key={post.id} post={post} />
              ))
            ) : (
              <p style={{ textAlign: 'center' }}>No posts with stories found yet.</p>
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
