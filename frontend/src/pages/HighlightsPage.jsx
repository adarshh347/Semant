// frontend/src/pages/HighlightsPage.jsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import PostFeedCard from '../components/PostFeedCard';
const API_URL = 'http://127.0.0.1:5008';

function HighlightsPage() {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchHighlights = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`${API_URL}/api/v1/posts/highlights/`);
        setPosts(response.data);
      } catch (error) {
        console.error("Error fetching highlights:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchHighlights();
  }, []);

  return (
    <div className="main-content-card">
      <div className="page-header">
        <h1>Recent Highlights</h1>
        <p>The latest stories being told.</p>
      </div>

      {loading ? (
        <p>Loading highlights...</p>
      ) : (
        <div className="highlights-feed">
          {posts.map(post => (
            <PostFeedCard key={post.id} post={post} />
          ))}
        </div>
      )}
    </div>
  );
}
export default HighlightsPage;
