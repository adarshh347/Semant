import React from 'react';
import { PostFeedCard } from 'frontend';
import { IMAGES } from './_img';

// PostFeedCard — a horizontal feed row: thumbnail + first text block + tag
// pills, linking to the post. Used in the highlights / feed streams.
export const Default = () => (
  <div style={{ maxWidth: 640 }}>
    <PostFeedCard
      post={{
        id: 1,
        photo_url: IMAGES.terracotta,
        text_blocks: [
          { content: 'The potter works the wheel at dawn, the terracotta still cool from the night air.' },
        ],
        general_tags: ['craft', 'heritage', 'clay'],
      }}
    />
  </div>
);

export const NoTags = () => (
  <div style={{ maxWidth: 640 }}>
    <PostFeedCard
      post={{
        id: 2,
        photo_url: IMAGES.dusk,
        text_blocks: [{ content: 'A quiet field at dusk — indigo bleeding into the last of the light.' }],
        general_tags: [],
      }}
    />
  </div>
);
