// The Archive rail — a thin fixed scrubber down the right edge that maps a
// position to a query offset, so you can fling deep into the archive fast.
//
// It indexes the archive by *sequence*, not by date: the corpus arrives in
// upload bursts (a reel split into frames, a carousel saved at once), and that
// grain is what you actually navigate by. Loaded sequences are ticked on the
// rail with their "Sequence · N frames" label; the rest stays a plain position
// scrubber, because we can't honestly name a sequence we haven't loaded — a
// global sequence index needs `source_group`, which the vision-pipeline thread
// owns (architecture-lab/feature-source-groups.md).
import { useCallback, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { API_URL } from '../config/api';
import { PAGE_SIZE } from './ArchiveGrid';
import { PerceptMark } from './brand/glyphs';
import './ArchiveTimeline.css';

const clamp01 = (n) => Math.min(1, Math.max(0, n));
const ordinal = (n) => `${Math.max(1, Math.round(n)).toLocaleString()}`;

async function fetchCount(selectedTag) {
  const tagQ = selectedTag ? `&tag=${selectedTag}` : '';
  // limit=1 → total_pages equals the exact document count.
  const head = (await axios.get(`${API_URL}/api/v1/posts?page=1&limit=1${tagQ}`)).data;
  const count = head?.total_pages ?? 0;
  return { count, totalPages: Math.ceil(count / PAGE_SIZE) };
}

export default function ArchiveTimeline({ selectedTag, currentPage, onJump, sequences = [], startPage = 1 }) {
  const trackRef = useRef(null);
  const [drag, setDrag] = useState(null);

  const { data } = useQuery({
    queryKey: ['archive', 'count', selectedTag ?? '__all__'],
    queryFn: () => fetchCount(selectedTag),
    staleTime: 5 * 60 * 1000,
  });

  const count = data?.count ?? 0;
  const totalPages = data?.totalPages ?? 0;

  // Where each loaded sequence sits in the whole archive.
  const seqMarks = useMemo(() => {
    if (!count) return [];
    const base = (startPage - 1) * PAGE_SIZE;
    const out = [];
    let i = 0;
    for (const s of sequences) {
      out.push({ pos: clamp01((base + i) / Math.max(1, count - 1)), label: s.label, n: s.items.length });
      i += s.items.length;
    }
    // Only the substantial ones earn a label; singles would litter the rail.
    const notable = out.filter((m) => m.n > 1);
    return (notable.length ? notable : out).slice(0, 14);
  }, [sequences, count, startPage]);

  // Plain position ticks so the whole rail stays legible, not just the loaded part.
  const posTicks = useMemo(() => {
    if (!count) return [];
    return [0, 0.25, 0.5, 0.75, 1].map((p) => ({ pos: p, label: ordinal(p * (count - 1) + 1) }));
  }, [count]);

  const posToPage = useCallback(
    (pos) => Math.min(totalPages, Math.max(1, Math.floor(pos * totalPages) + 1)),
    [totalPages],
  );
  const posFromEvent = useCallback((e) => {
    const rect = trackRef.current.getBoundingClientRect();
    return clamp01((e.clientY - rect.top) / rect.height);
  }, []);

  // While dragging: name the sequence under the cursor if we know it, else the
  // position in the archive.
  const bubbleFor = useCallback(
    (pos) => {
      const near = seqMarks.find((m) => Math.abs(m.pos - pos) < 0.012);
      if (near) return near.label;
      return `${ordinal(pos * (count - 1) + 1)} of ${count.toLocaleString()}`;
    },
    [seqMarks, count],
  );

  const onPointerDown = (e) => {
    if (!totalPages) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    setDrag({ pos: posFromEvent(e) });
  };
  const onPointerMove = (e) => { if (drag) setDrag({ pos: posFromEvent(e) }); };
  const endDrag = (e) => {
    if (!drag) return;
    onJump?.(posToPage(posFromEvent(e)));
    setDrag(null);
  };

  if (!totalPages || totalPages <= 1) return null;

  const thumbPos = drag
    ? drag.pos
    : totalPages > 1
      ? clamp01((currentPage - 1) / (totalPages - 1))
      : 0;

  return (
    <div className="arch-timeline">
      <div
        ref={trackRef}
        className="arch-tl-track"
        role="slider"
        aria-label="Jump through the archive by sequence"
        aria-valuemin={1}
        aria-valuemax={totalPages}
        aria-valuenow={currentPage}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      >
        {posTicks.map((m) => (
          <div key={`p${m.pos}`} className="arch-tl-mark" style={{ top: `${m.pos * 100}%` }}>
            <span className="arch-tl-tick" />
            <span className="arch-tl-label">{m.label}</span>
          </div>
        ))}
        {seqMarks.map((m, i) => (
          <div key={`s${i}`} className="arch-tl-mark is-seq" style={{ top: `${m.pos * 100}%` }} title={m.label}>
            <span className="arch-tl-seqmark" aria-hidden><PerceptMark size="1em" /></span>
          </div>
        ))}
        <span className="arch-tl-thumb" style={{ top: `${thumbPos * 100}%` }} />
      </div>

      {drag && (
        <div className="arch-tl-bubble" style={{ top: `${drag.pos * 100}%` }}>
          {bubbleFor(drag.pos)}
        </div>
      )}
    </div>
  );
}
