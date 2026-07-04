import {useState,useEffect} from 'react';
import axios from 'axios';
import UploadForm from '../components/UploadForm';
import PostCard from '../components/PostCard';

const API_URL='http://127.0.0.1:5008';

function HomePage(){
    const [posts,setPosts]= useState([]);

    const fetchPosts = async()=>{
        try{
        const response= await axios.get(`${API_URL}/api/v1/posts/`);
        setPosts(response.data);

            }
        catch(error){
            console.error("Error fetching posts:", error);
            }
        };

      useEffect(() => {
    fetchPosts();
  }, []);


return (
    <div>
      <UploadForm onUploadSuccess={fetchPosts} />
      <hr />
      <h2>Gallery</h2>
      <div className="gallery-grid">
        {posts.map((post) => (
          // Use the new PostCard component in our loop
          <PostCard key={post.id} post={post} />
        ))}
      </div>
    </div>
  );

    }

export default HomePage;
