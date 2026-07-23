// The Archive — a justified, infinite, sequence-grouped image scroll.
//
// The archive's grain is the sequence: a reel split into frames or a carousel
// saved in one go arrives as a burst of sibling posts. So the scroll is broken
// by quiet "Sequence · N frames" dividers rather than running as one anonymous
// river (see lib/sequences.js for how a sequence is recovered).
//
// Why we own the paging instead of react-photo-album's <InfiniteScroll>: that
// component renders a single album and has no seam for group headers. We keep
// its two virtues by hand — pages fetched one at a time through TanStack Query
// (ordered, de-duped, cached: the Phase-1 race fix), and offscreen work skipped
// via `content-visibility: auto` on each sequence, which lets the browser drop
// layout+paint for sequences you can't see.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { RowsPhotoAlbum } from 'react-photo-album';
import 'react-photo-album/rows.css';
import { API_URL } from '../config/api';
import { cldAt, cldSrcSet, cldLqip } from '../lib/cloudinary';
import { groupIntoSequences } from '../lib/sequences';
import { PerceptMark } from './brand/glyphs';
import { MarkLoader } from './brand/MarkLoader';
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

function renderLink(props) {
  const { href, children, ...rest } = props;
  return (
    <Link to={href} viewTransition {...rest}>
      {children}
    </Link>
  );
}

async function toPhoto(p) {
  const lqip = cldLqip(p.photo_url);
  const dims = p.width && p.height ? { width: p.width, height: p.height } : await probeAspect(lqip);
  const aspect = dims.height / dims.width;
  const width = 1024;
  return {
    key: p.id,
    src: cldAt(p.photo_url, width),
    srcSet: cldSrcSet(p.photo_url, aspect),
    width,
    height: Math.round(width * aspect),
    href: `/posts/${p.id}`,
    alt: p.description || 'Archive image',
    lqip,
  };
}

export default function ArchiveGrid({ selectedTag, startPage = 1, onSequences }) {
  const queryClient = useQueryClient();
  const [nonce, setNonce] = useState(0);
  const [posts, setPosts] = useState([]);
  const [status, setStatus] = useState('loading'); // loading | idle | done | error
  const seenRef = useRef(new Set());
  const stateRef = useRef({ nextPage: startPage, busy: false, done: false });
  const scopeRef = useRef(null);
  const sentinelRef = useRef(null);

  const scope = `${selectedTag ?? '__all__'}:${startPage}:${nonce}`;

  const fetchNext = useCallback(async () => {
    const s = stateRef.current;
    if (s.busy || s.done) return;
    s.busy = true;
    setStatus('loading');
    try {
      const page = s.nextPage;
      let url = `${API_URL}/api/v1/posts?page=${page}&limit=${PAGE_SIZE}`;
      if (selectedTag) url += `&tag=${selectedTag}`;
      const data = await queryClient.fetchQuery({
        queryKey: ['posts', 'archive', selectedTag ?? '__all__', page],
        queryFn: async () => (await axios.get(url)).data,
        staleTime: 5 * 60 * 1000,
      });
      if (!data?.posts?.length || page > (data.total_pages ?? 0)) {
        s.done = true;
        setStatus('done');
        return;
      }
      const fresh = data.posts.filter((p) => p.photo_url && !seenRef.current.has(p.id));
      fresh.forEach((p) => seenRef.current.add(p.id));
      s.nextPage = page + 1;
      setPosts((prev) => [...prev, ...fresh]);
      setStatus('idle');
    } catch {
      setStatus('error');
    } finally {
      s.busy = false;
    }
  }, [selectedTag, queryClient]);

  // Reset on filter change / timeline jump / upload.
  useEffect(() => {
    seenRef.current = new Set();
    stateRef.current = { nextPage: startPage, busy: false, done: false };
    setPosts([]);
    setStatus('loading');
    fetchNext();
    if (startPage > 1 && scopeRef.current) {
      scopeRef.current.scrollIntoView({ block: 'start', behavior: 'auto' });
    }
  }, [scope]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onChanged = () => {
      queryClient.invalidateQueries({ queryKey: ['posts'] });
      setNonce((n) => n + 1);
    };
    window.addEventListener('semant:posts-changed', onChanged);
    return () => window.removeEventListener('semant:posts-changed', onChanged);
  }, [queryClient]);

  // Infinite scroll — the sentinel below the last sequence.
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return undefined;
    const io = new IntersectionObserver(
      (entries) => { if (entries[0].isIntersecting) fetchNext(); },
      { rootMargin: '800px 0px' },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [fetchNext, posts.length]);

  const sequences = useMemo(() => groupIntoSequences(posts), [posts]);

  // Photos are cached per POST, not per sequence: a burst that straddles a page
  // boundary keeps its key while gaining items, so a sequence-keyed cache would
  // freeze it at its first page's photos. Per-post also means each aspect probe
  // runs exactly once.
  const [photosById, setPhotosById] = useState({});
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const missing = posts.filter((p) => !photosById[p.id]);
      if (!missing.length) return;
      const resolved = await Promise.all(missing.map(async (p) => [p.id, await toPhoto(p)]));
      if (!cancelled) setPhotosById((prev) => ({ ...prev, ...Object.fromEntries(resolved) }));
    })();
    return () => { cancelled = true; };
  }, [posts]); // eslint-disable-line react-hooks/exhaustive-deps

  // Report the sequences up so the rail can index them.
  useEffect(() => { onSequences?.(sequences); }, [sequences, onSequences]);

  return (
    <div ref={scopeRef} className="archive-grid-scope">
      {sequences.map((seq) => {
        const photos = seq.items.map((p) => photosById[p.id]).filter(Boolean);
        return (
          <section key={seq.key} className="arch-seq" data-seq={seq.key}>
            <header className="arch-seq-divider">
              <span className="arch-seq-mark" aria-hidden><PerceptMark size="1em" /></span>
              <span className="arch-seq-label">{seq.label}</span>
              <span className="arch-seq-rule" />
            </header>
            {photos.length > 0 && (
              <RowsPhotoAlbum
                photos={photos}
                targetRowHeight={230}
                spacing={10}
                rowConstraints={{ singleRowMaxHeight: 340 }}
                render={{ image: renderImage, link: renderLink }}
              />
            )}
          </section>
        );
      })}

      <div ref={sentinelRef} className="arch-sentinel" aria-hidden />
      {status === 'loading' && <div className="arch-status"><MarkLoader fullscreen={false} size={26} label="Loading more of the archive…" /></div>}
      {status === 'done' && <p className="arch-status">You&rsquo;ve reached the end of the archive.</p>}
      {status === 'error' && <p className="arch-status">Couldn&rsquo;t load more of the archive.</p>}
    </div>
  );
}
