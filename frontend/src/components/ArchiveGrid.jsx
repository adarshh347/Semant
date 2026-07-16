// The Archive — a justified, virtualized, infinite image grid.
//
// Data: still TanStack Query (the Phase-1 race fix). react-photo-album's
// first-party <InfiniteScroll> owns the scroll + virtualization (offscreen rows
// unmount), and its `fetch(index)` delegates to queryClient.fetchQuery so every
// page is ordered, de-duped and cached exactly as before — `singleton` keeps a
// single fetch in flight, so pages can never resolve out of order.
//
// Layout needs per-image width/height, which the posts don't store. We resolve
// the aspect client-side from a tiny Cloudinary LQIP thumb (which also serves as
// the blur-up placeholder), and read `post.width ?? probed` so a future backend
// backfill just works.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { RowsPhotoAlbum } from 'react-photo-album';
import InfiniteScroll from 'react-photo-album/scroll';
import 'react-photo-album/rows.css';
import { API_URL } from '../config/api';
import { cldAt, cldSrcSet, cldLqip } from '../lib/cloudinary';
import './ArchiveGrid.css';

export const PAGE_SIZE = 50;

// Load the tiny LQIP thumb once to read the true aspect ratio; fall back to a
// 4:5 portrait if a probe fails — or simply never resolves. A single hanging
// image URL (older posts can carry non-Cloudinary sources) must not wedge the
// whole page's fetch, so the probe is bounded by a timeout.
function probeAspect(lqipUrl) {
  return new Promise((resolve) => {
    let done = false;
    const finish = (dims) => { if (!done) { done = true; resolve(dims); } };
    const img = new Image();
    img.onload = () => finish({ width: img.naturalWidth || 4, height: img.naturalHeight || 5 });
    img.onerror = () => finish({ width: 4, height: 5 });
    img.src = lqipUrl;
    setTimeout(() => finish({ width: 4, height: 5 }), 4000);
  });
}

// Custom image render: the real <img> carries the blurred LQIP as its own
// background, so the tile shows the blurred image (never grey) until the
// full-res pixels paint over it. `is-loaded` lifts the extra CSS blur.
function renderImage(props, context) {
  const { photo } = context;
  const { style, ...rest } = props;
  return (
    <img
      {...rest}
      loading="lazy"
      className="arch-img"
      style={{ ...style, backgroundImage: `url("${photo.lqip}")` }}
      onLoad={(e) => e.currentTarget.classList.add('is-loaded')}
    />
  );
}

// Each tile is a router link into Chiasm (/posts/:id) — the archive's job is to
// get you into the work. SPA nav (no full reload), still a real <a href> so
// middle-click / open-in-new-tab work.
function renderLink(props) {
  const { href, children, ...rest } = props;
  return (
    <Link to={href} viewTransition {...rest}>
      {children}
    </Link>
  );
}

export default function ArchiveGrid({ selectedTag, startPage = 1 }) {
  const queryClient = useQueryClient();
  // Bumped when an upload lands — remounts the scroller so a new image appears.
  const [nonce, setNonce] = useState(0);
  const seenRef = useRef(null);
  const scopeRef = useRef(null);

  // Fresh de-dup memory per filter / refresh / timeline jump.
  const scopeKey = `${selectedTag ?? '__all__'}:${startPage}:${nonce}`;
  useMemo(() => { seenRef.current = new Set(); }, [scopeKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // A timeline jump re-anchors the scroller to a page offset; bring that new
  // anchor up to the top so the jumped-to images are what you see.
  useEffect(() => {
    if (startPage > 1 && scopeRef.current) {
      scopeRef.current.scrollIntoView({ block: 'start', behavior: 'auto' });
    }
  }, [startPage]);

  useEffect(() => {
    const onChanged = () => {
      queryClient.invalidateQueries({ queryKey: ['posts'] });
      setNonce((n) => n + 1);
    };
    window.addEventListener('semant:posts-changed', onChanged);
    return () => window.removeEventListener('semant:posts-changed', onChanged);
  }, [queryClient]);

  const fetchPage = useCallback(
    async (index) => {
      // Anchor at startPage: index 0 is the jumped-to page, and we page forward
      // (toward older) from there.
      const page = startPage + index;
      const data = await queryClient.fetchQuery({
        queryKey: ['posts', 'archive', selectedTag ?? '__all__', page],
        queryFn: async () => {
          let url = `${API_URL}/api/v1/posts?page=${page}&limit=${PAGE_SIZE}`;
          if (selectedTag) url += `&tag=${selectedTag}`;
          const res = await axios.get(url);
          return res.data;
        },
        staleTime: 5 * 60 * 1000,
      });

      if (!data?.posts?.length || page > (data.total_pages ?? 0)) return null;

      const seen = seenRef.current;
      const fresh = data.posts.filter((p) => p.photo_url && !seen.has(p.id));
      return Promise.all(
        fresh.map(async (p) => {
          seen.add(p.id);
          const lqip = cldLqip(p.photo_url);
          const dims = p.width && p.height
            ? { width: p.width, height: p.height }
            : await probeAspect(lqip);
          const aspect = dims.height / dims.width; // height / width, ratio only
          // Give the layout a real-magnitude size with the correct ratio; the
          // srcSet carries the actual resolution choices.
          const width = 1024;
          const height = Math.round(width * aspect);
          return {
            key: p.id,
            src: cldAt(p.photo_url, width),
            srcSet: cldSrcSet(p.photo_url, aspect),
            width,
            height,
            href: `/posts/${p.id}`,
            alt: p.description || 'Archive image',
            lqip,
          };
        }),
      );
    },
    [selectedTag, queryClient, startPage],
  );

  return (
    <div ref={scopeRef} className="archive-grid-scope">
      <InfiniteScroll
        key={scopeKey}
        singleton
        fetch={fetchPage}
        fetchRootMargin="800px 0px"
        offscreenRootMargin="2000px 0px"
        loading={<p className="arch-status">Loading more of the archive…</p>}
        finished={<p className="arch-status">You've reached the end of the archive.</p>}
        error={<p className="arch-status">Couldn't load more of the archive.</p>}
      >
        <RowsPhotoAlbum
          photos={[]}
          targetRowHeight={230}
          spacing={10}
          rowConstraints={{ singleRowMaxHeight: 340 }}
          render={{ image: renderImage, link: renderLink }}
        />
      </InfiniteScroll>
    </div>
  );
}
