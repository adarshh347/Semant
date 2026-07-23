import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchRecentPosts, percepts, perceptLabel } from './homeData';
import PerceptCrop from './PerceptCrop';
import { PerceptMark } from '../brand/glyphs';

// Parts you recently noticed (3×1). Recent Percept chips (◈, plum) drawn from the
// region annotations on your recent readings — each a jump back to that image's
// reading. The region-mark motif is the tile's signature.
export default function PerceptsTile() {
  const { data, isLoading } = useQuery({
    queryKey: ['home', 'percepts'],
    queryFn: () => fetchRecentPosts(24),
    staleTime: 5 * 60 * 1000,
  });

  // Flatten recent posts → their marked parts (need a box to crop), newest
  // first, deduped by label.
  const marks = [];
  const seen = new Set();
  for (const post of data ?? []) {
    if (!post.photo_url) continue;
    for (const region of percepts(post)) {
      if (!region.box) continue;
      const label = perceptLabel(region);
      const key = label.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      marks.push({ label, region, postId: post.id, photoUrl: post.photo_url });
      if (marks.length >= 8) break;
    }
    if (marks.length >= 8) break;
  }

  return (
    <section className="tile tile-percepts">
      <span className="eyebrow">Parts you recently noticed</span>
      {isLoading ? (
        <p className="tile-muted">Gathering the parts you marked…</p>
      ) : marks.length > 0 ? (
        <div className="percept-strip">
          {marks.map((m) => (
            <Link
              key={`${m.postId}:${m.region.id}`}
              to={`/posts/${m.postId}`}
              className="percept-lift"
              viewTransition
            >
              <PerceptCrop photoUrl={m.photoUrl} region={m.region} label={m.label} />
              <span className="percept-lift-label">
                <span className="mark" aria-hidden><PerceptMark size="1em" className="glyph--inline" /></span> {m.label}
              </span>
            </Link>
          ))}
        </div>
      ) : (
        <p className="tile-muted">
          The parts you mark while reading will collect here.{' '}
          <Link to="/gallery" className="tile-link">Read an image →</Link>
        </p>
      )}
    </section>
  );
}
