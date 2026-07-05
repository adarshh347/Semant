import React from 'react';
import { PostCard } from 'frontend';
import { IMAGES } from './_img';

// PostCard — a single tappable gallery tile (3:4 image, hover lift). The unit
// the masonry gallery grid is built from.
const posts = [
  { id: 1, photo_url: IMAGES.terracotta, description: 'Terracotta study' },
  { id: 2, photo_url: IMAGES.paper, description: 'Paper & pigment' },
  { id: 3, photo_url: IMAGES.ink, description: 'Ink field' },
  { id: 4, photo_url: IMAGES.dusk, description: 'Dusk' },
];

export const Default = () => (
  <div style={{ width: 260 }}>
    <PostCard post={posts[0]} />
  </div>
);

export const GalleryGrid = () => (
  <div className="gallery-grid" style={{ maxWidth: 760 }}>
    {posts.map((p) => (
      <PostCard key={p.id} post={p} />
    ))}
  </div>
);
