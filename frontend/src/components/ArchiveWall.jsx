// A dense, virtualized uniform-square view of the Archive. Serves two of the
// three view modes:
//   · Grid — larger square cells, no fisheye (a calm uniform grid).
//   · Wall — tiny cells where the tile under the pointer magnifies (a dock/
//     fisheye effect), so you can skim thousands at a glance and pull one forward.
//
// Uniform cell size makes virtualization trivial (fixed row height) with no
// dependency, and — crucially — lets the fisheye run entirely on the DOM:
// pointermove writes transforms directly to the visible cells inside a rAF, so
// React never re-renders on mouse movement.
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { API_URL } from '../config/api';
import { PAGE_SIZE } from './ArchiveGrid';
import { cldCrop, cldLqip } from '../lib/cloudinary';
import { MarkLoader } from './brand/MarkLoader';
import './ArchiveWall.css';

const GAP = 4;
const OVERSCAN = 4; // rows above/below the viewport

export default function ArchiveWall({ selectedTag, startPage = 1, cell = 150, fisheye = false }) {
  const queryClient = useQueryClient();
  const scrollRef = useRef(null);
  const innerRef = useRef(null);
  const seenRef = useRef(new Set());
  const stateRef = useRef({ nextPage: startPage, loading: false, done: false });

  const [cells, setCells] = useState([]);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [scrollTop, setScrollTop] = useState(0);
  const lastPtrRef = useRef(null);
  const applyFisheyeRef = useRef(null);

  const scope = `${selectedTag ?? '__all__'}:${startPage}`;

  const fetchNext = useCallback(async () => {
    const s = stateRef.current;
    if (s.loading || s.done) return;
    s.loading = true;
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
        return;
      }
      const seen = seenRef.current;
      const fresh = data.posts
        .filter((p) => p.photo_url && !seen.has(p.id))
        .map((p) => {
          seen.add(p.id);
          return { id: p.id, href: `/posts/${p.id}`, src: cldCrop(p.photo_url, 200, 200), lqip: cldLqip(p.photo_url) };
        });
      s.nextPage = page + 1;
      setCells((prev) => [...prev, ...fresh]);
    } finally {
      s.loading = false;
    }
  }, [selectedTag, queryClient]);

  // Reset when the scope (filter / timeline anchor) changes.
  useEffect(() => {
    seenRef.current = new Set();
    stateRef.current = { nextPage: startPage, loading: false, done: false };
    setCells([]);
    setScrollTop(0);
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
    fetchNext();
  }, [scope]); // eslint-disable-line react-hooks/exhaustive-deps

  // Measure the scroll viewport.
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return undefined;
    const measure = () => setSize({ w: el.clientWidth, h: el.clientHeight });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const stride = cell + GAP;
  const cols = Math.max(1, Math.floor((size.w + GAP) / stride));
  const totalRows = Math.ceil(cells.length / cols);
  const innerHeight = totalRows * stride;

  const firstRow = Math.max(0, Math.floor(scrollTop / stride) - OVERSCAN);
  const lastRow = Math.min(totalRows, Math.ceil((scrollTop + size.h) / stride) + OVERSCAN);
  const visible = useMemo(() => {
    const out = [];
    for (let i = firstRow * cols; i < lastRow * cols && i < cells.length; i++) {
      const col = i % cols;
      const row = Math.floor(i / cols);
      out.push({ ...cells[i], left: col * stride, top: row * stride });
    }
    return out;
  }, [cells, firstRow, lastRow, cols, stride]);

  // Keep loading until the viewport is filled (tiny cells need many to fill, and
  // a short column never scrolls, so onScroll alone wouldn't top it up).
  useEffect(() => {
    if (size.h > 0 && innerHeight < size.h * 1.6) fetchNext();
  }, [size.h, innerHeight, cells.length, fetchNext]);

  // Infinite load when the window nears the end.
  const onScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setScrollTop(el.scrollTop);
    if (el.scrollHeight - (el.scrollTop + el.clientHeight) < size.h * 1.5) fetchNext();
    // Re-apply at the last pointer position so wheel-scrolling (no pointermove)
    // doesn't leave a stale cell magnified after the grid re-flows.
    if (fisheye && lastPtrRef.current) {
      applyFisheyeRef.current?.(lastPtrRef.current.x, lastPtrRef.current.y);
    }
  }, [fetchNext, size.h, fisheye]);

  // --- the fisheye, run on the DOM (no React re-render per move) ------------
  const rafRef = useRef(0);
  const applyFisheye = useCallback((clientX, clientY) => {
    const el = innerRef.current;
    const scroller = scrollRef.current;
    if (!el || !scroller) return;
    const rect = scroller.getBoundingClientRect();
    const px = clientX - rect.left + scroller.scrollLeft;
    const py = clientY - rect.top + scroller.scrollTop;
    const R = stride * 3.2;         // influence radius
    const boost = 1.6;              // peak extra scale
    const nodes = el.children;
    for (let i = 0; i < nodes.length; i++) {
      const node = nodes[i];
      const cx = node.offsetLeft + cell / 2;
      const cy = node.offsetTop + cell / 2;
      const d = Math.hypot(px - cx, py - cy);
      const influence = Math.max(0, 1 - d / R);
      const scale = 1 + boost * influence * influence;
      node.style.transform = influence > 0 ? `scale(${scale.toFixed(3)})` : '';
      node.style.zIndex = influence > 0 ? String(10 + Math.round(influence * 90)) : '';
    }
  }, [stride, cell]);
  applyFisheyeRef.current = applyFisheye;

  const onPointerMove = useCallback((e) => {
    if (!fisheye) return;
    const { clientX, clientY } = e;
    lastPtrRef.current = { x: clientX, y: clientY };
    if (rafRef.current) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = 0;
      applyFisheye(clientX, clientY);
    });
  }, [fisheye, applyFisheye]);

  const clearFisheye = useCallback(() => {
    const el = innerRef.current;
    if (!el) return;
    for (let i = 0; i < el.children.length; i++) {
      el.children[i].style.transform = '';
      el.children[i].style.zIndex = '';
    }
  }, []);

  useEffect(() => () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); }, []);

  return (
    <div
      ref={scrollRef}
      className={`arch-wall${fisheye ? ' is-fisheye' : ''}`}
      onScroll={onScroll}
      onPointerMove={onPointerMove}
      onPointerLeave={clearFisheye}
    >
      <div ref={innerRef} className="arch-wall-inner" style={{ height: innerHeight }}>
        {visible.map((c) => (
          <Link
            key={c.id}
            to={c.href}
            viewTransition
            className="wall-cell"
            style={{
              left: c.left,
              top: c.top,
              width: cell,
              height: cell,
              backgroundImage: `url("${c.lqip}")`,
            }}
          >
            <img
              src={c.src}
              alt=""
              loading="lazy"
              draggable={false}
              onLoad={(e) => e.currentTarget.classList.add('is-loaded')}
            />
          </Link>
        ))}
      </div>
      {cells.length === 0 && <div className="arch-status arch-wall-status"><MarkLoader fullscreen={false} size={30} label="Loading the archive…" /></div>}
    </div>
  );
}
