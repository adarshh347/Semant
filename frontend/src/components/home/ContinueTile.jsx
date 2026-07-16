import { useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import useEmblaCarousel from 'embla-carousel-react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cldCrop, cldLqip } from '../../lib/cloudinary';
import {
  fetchRecentPosts, isInProgress, titleOf, progressLine,
} from './homeData';

// Continue in Chiasm (2×2). Recent readings you've begun — thumb · title ·
// "N percepts · M words" — overflowing horizontally via Embla. Click → resume
// the reading at /posts/:id. Falls back to the most recent images if nothing has
// been marked yet, so the tile is always a door, never an empty box.
export default function ContinueTile() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['home', 'continue'],
    queryFn: () => fetchRecentPosts(24),
    staleTime: 5 * 60 * 1000,
  });

  const [emblaRef, embla] = useEmblaCarousel({ align: 'start', dragFree: true, containScroll: 'trimSnaps' });
  const scrollPrev = useCallback(() => embla?.scrollPrev(), [embla]);
  const scrollNext = useCallback(() => embla?.scrollNext(), [embla]);

  const posts = data ?? [];
  const withPhoto = posts.filter((p) => p.photo_url);
  const inProgress = withPhoto.filter(isInProgress);
  // Prefer begun readings; backfill with recent so the strip is never thin.
  const items = (inProgress.length >= 4 ? inProgress : [...inProgress, ...withPhoto])
    .filter((p, i, arr) => arr.findIndex((q) => q.id === p.id) === i)
    .slice(0, 10);

  return (
    <section className="tile tile-continue">
      <header className="tile-head">
        <div>
          <span className="eyebrow">Continue in Chiasm</span>
          <h2 className="tile-title">Pick up a reading</h2>
        </div>
        {items.length > 1 && (
          <div className="tile-continue-nav">
            <button type="button" className="tile-navbtn" onClick={scrollPrev} aria-label="Previous">
              <ChevronLeft size={16} />
            </button>
            <button type="button" className="tile-navbtn" onClick={scrollNext} aria-label="Next">
              <ChevronRight size={16} />
            </button>
          </div>
        )}
      </header>

      {isLoading ? (
        <p className="tile-muted">Gathering your recent readings…</p>
      ) : isError || items.length === 0 ? (
        <p className="tile-muted">
          Nothing in progress yet. <Link to="/gallery" className="tile-link">Open the Archive</Link> and read an image.
        </p>
      ) : (
        <div className="tile-continue-embla" ref={emblaRef}>
          <div className="tile-continue-track">
            {items.map((p) => (
              <Link key={p.id} to={`/posts/${p.id}`} className="continue-card" viewTransition>
                <div
                  className="continue-thumb"
                  style={{ backgroundImage: `url("${cldLqip(p.photo_url)}")` }}
                >
                  <img
                    src={cldCrop(p.photo_url, 320, 400)}
                    alt={titleOf(p)}
                    loading="lazy"
                    onLoad={(e) => e.currentTarget.classList.add('is-loaded')}
                  />
                </div>
                <div className="continue-meta">
                  <span className="continue-name">{titleOf(p)}</span>
                  <span className="continue-progress">
                    <span className="mark" aria-hidden>◈</span> {progressLine(p)}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
