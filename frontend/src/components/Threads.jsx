// Threads — the Archive's filter rail.
//
// Replaces the old boxed tag slab (a padded, tinted, bordered panel of chunky
// default buttons). A filter is L5 in the border grammar — inline tools, no box:
// whitespace and one quiet row of chips, the active one carrying the emphasis.
// "Threads" because a tag is the line running through the images that share it.
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { API_URL } from '../config/api';
import './Threads.css';

async function fetchTags() {
  const res = await axios.get(`${API_URL}/api/v1/posts/tags/`);
  return Array.isArray(res.data) ? res.data.filter(Boolean) : [];
}

export default function Threads({ selectedTag, onTagSelect }) {
  const { data: tags = [] } = useQuery({
    queryKey: ['posts', 'tags'],
    queryFn: fetchTags,
    staleTime: 5 * 60 * 1000,
  });

  return (
    <div className="threads" role="group" aria-label="Filter the archive by thread">
      <span className="threads-label">Threads</span>
      <div className="threads-rail">
        <button
          type="button"
          className={`thread${selectedTag == null ? ' is-active' : ''}`}
          aria-pressed={selectedTag == null}
          onClick={() => onTagSelect(null)}
        >
          Everything
        </button>
        {tags.map((tag) => (
          <button
            key={tag}
            type="button"
            className={`thread${selectedTag === tag ? ' is-active' : ''}`}
            aria-pressed={selectedTag === tag}
            onClick={() => onTagSelect(tag)}
          >
            {tag}
          </button>
        ))}
      </div>
    </div>
  );
}
