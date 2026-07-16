// The Archive date-scrubber — a thin fixed rail down the right edge that maps a
// position to a query offset, so you can fling to old images fast. The archive
// is ordered newest→oldest by _id, and a MongoDB ObjectId's first 4 bytes encode
// its creation time, so every post's date is derivable client-side — no backend
// date index needed. Dragging picks a fraction of the archive; releasing jumps
// the grid's page anchor there.
import { useCallback, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { API_URL } from '../config/api';
import { PAGE_SIZE } from './ArchiveGrid';
import './ArchiveTimeline.css';

const clamp01 = (n) => Math.min(1, Math.max(0, n));
const DAY = 864e5;

// Creation date from an ObjectId hex string (first 8 hex chars = unix seconds).
function objectIdDate(id) {
  if (typeof id !== 'string' || id.length < 8) return null;
  const secs = parseInt(id.slice(0, 8), 16);
  return Number.isFinite(secs) ? new Date(secs * 1000) : null;
}

async function fetchMeta(selectedTag) {
  const tagQ = selectedTag ? `&tag=${selectedTag}` : '';
  // limit=1 → total_pages equals the exact document count, and posts[0] is the
  // newest.
  const head = (await axios.get(`${API_URL}/api/v1/posts?page=1&limit=1${tagQ}`)).data;
  const count = head?.total_pages ?? 0;
  const newest = objectIdDate(head?.posts?.[0]?.id);
  if (!count || !newest) return { count: 0 };
  const totalPages = Math.ceil(count / PAGE_SIZE);
  // The oldest post is the last one on the last full-size page.
  const tail = (await axios.get(`${API_URL}/api/v1/posts?page=${totalPages}&limit=${PAGE_SIZE}${tagQ}`)).data;
  const tailPosts = tail?.posts ?? [];
  const oldest = objectIdDate(tailPosts[tailPosts.length - 1]?.id) || newest;
  return { count, totalPages, newest: +newest, oldest: +oldest };
}

// Marker dates + labels, granularity adapted to the span (years → months → days
// → hours). Thinned to a legible number of labels.
function buildMarkers(oldest, newest) {
  const span = newest - oldest;
  if (span <= 0) return [];
  const out = [];
  const push = (t, label, major) => {
    const pos = (newest - t) / span;
    if (pos >= -1e-3 && pos <= 1 + 1e-3) out.push({ pos: clamp01(pos), label, major });
  };
  if (span > 730 * DAY) {
    for (let y = new Date(oldest).getFullYear(); y <= new Date(newest).getFullYear(); y++) {
      push(+new Date(y, 0, 1), String(y), true);
    }
  } else if (span > 75 * DAY) {
    const d = new Date(new Date(oldest).getFullYear(), new Date(oldest).getMonth(), 1);
    while (+d <= newest) {
      push(+d, d.toLocaleString('en', { month: 'short', year: '2-digit' }), d.getMonth() === 0);
      d.setMonth(d.getMonth() + 1);
    }
  } else if (span > 3 * DAY) {
    for (let i = 0; i <= 8; i++) {
      const t = newest - (i / 8) * span;
      push(t, new Date(t).toLocaleString('en', { month: 'short', day: 'numeric' }), i === 0 || i === 8);
    }
  } else {
    for (let i = 0; i <= 5; i++) {
      const t = newest - (i / 5) * span;
      push(t, new Date(t).toLocaleString('en', { month: 'short', day: 'numeric', hour: 'numeric' }), i === 0 || i === 5);
    }
  }
  // Thin to <= 16 labels so the rail stays legible.
  if (out.length > 16) {
    const step = Math.ceil(out.length / 16);
    return out.filter((_, i) => i % step === 0 || out[i].major);
  }
  return out;
}

function labelFor(t, span) {
  const d = new Date(t);
  if (span > 730 * DAY) return d.toLocaleString('en', { month: 'short', year: 'numeric' });
  if (span > 3 * DAY) return d.toLocaleString('en', { month: 'short', day: 'numeric', year: 'numeric' });
  return d.toLocaleString('en', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

export default function ArchiveTimeline({ selectedTag, currentPage, onJump }) {
  const trackRef = useRef(null);
  const [drag, setDrag] = useState(null); // { pos, t } while scrubbing

  const { data } = useQuery({
    queryKey: ['archive', 'timeline', selectedTag ?? '__all__'],
    queryFn: () => fetchMeta(selectedTag),
    staleTime: 5 * 60 * 1000,
  });

  const span = data?.newest && data?.oldest ? data.newest - data.oldest : 0;
  const markers = useMemo(
    () => (span > 0 ? buildMarkers(data.oldest, data.newest) : []),
    [span, data?.oldest, data?.newest],
  );

  const posToPage = useCallback(
    (pos) => Math.min(data.totalPages, Math.max(1, Math.floor(pos * data.totalPages) + 1)),
    [data],
  );

  const posFromEvent = useCallback((e) => {
    const rect = trackRef.current.getBoundingClientRect();
    return clamp01((e.clientY - rect.top) / rect.height);
  }, []);

  const onPointerDown = (e) => {
    if (!data?.totalPages) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    const pos = posFromEvent(e);
    setDrag({ pos, t: data.newest - pos * span });
  };
  const onPointerMove = (e) => {
    if (!drag) return;
    const pos = posFromEvent(e);
    setDrag({ pos, t: data.newest - pos * span });
  };
  const endDrag = (e) => {
    if (!drag) return;
    const pos = posFromEvent(e);
    onJump?.(posToPage(pos));
    setDrag(null);
  };

  if (!data?.totalPages || data.totalPages <= 1 || span <= 0) return null;

  const thumbPos = drag
    ? drag.pos
    : data.totalPages > 1
      ? clamp01((currentPage - 1) / (data.totalPages - 1))
      : 0;

  return (
    <div className="arch-timeline" aria-hidden={false}>
      <div
        ref={trackRef}
        className="arch-tl-track"
        role="slider"
        aria-label="Jump through the archive by date"
        aria-valuemin={1}
        aria-valuemax={data.totalPages}
        aria-valuenow={currentPage}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      >
        {markers.map((m, i) => (
          <div
            key={i}
            className={`arch-tl-mark${m.major ? ' is-major' : ''}`}
            style={{ top: `${m.pos * 100}%` }}
          >
            <span className="arch-tl-tick" />
            <span className="arch-tl-label">{m.label}</span>
          </div>
        ))}
        <span className="arch-tl-thumb" style={{ top: `${thumbPos * 100}%` }} />
      </div>

      {drag && (
        <div className="arch-tl-bubble" style={{ top: `${drag.pos * 100}%` }}>
          {labelFor(drag.t, span)}
        </div>
      )}
    </div>
  );
}
