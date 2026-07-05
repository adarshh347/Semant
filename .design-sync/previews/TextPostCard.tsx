import React from 'react';
import { TextPostCard } from 'frontend';
import { IMAGES } from './_img';

// TextPostCard — a feed row for text-forward posts: thumbnail + an
// HTML-stripped, truncated preview (with Show More), tag pills, and a
// last-updated timestamp.
export const Default = () => (
  <div style={{ maxWidth: 640 }}>
    <TextPostCard
      post={{
        id: 1,
        photo_url: IMAGES.ink,
        text_blocks: [
          {
            content:
              '<p>In the old quarter the walls remember every monsoon. The ink of the sign-painter has faded to a rust that matches the brick, and the letters lean into one another like old friends sharing a secret.</p>',
            color: 'transparent',
          },
        ],
        general_tags: ['essay', 'city', 'memory'],
        updated_at: '2026-06-18T09:30:00Z',
      }}
    />
  </div>
);

export const ShortPost = () => (
  <div style={{ maxWidth: 640 }}>
    <TextPostCard
      post={{
        id: 2,
        photo_url: IMAGES.paper,
        text_blocks: [{ content: '<p>A single line, and nothing more.</p>', color: 'transparent' }],
        general_tags: ['fragment'],
        updated_at: '2026-07-01T12:00:00Z',
      }}
    />
  </div>
);
