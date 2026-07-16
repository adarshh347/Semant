import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchRecentPosts, percepts, perceptLabel } from './homeData';

// Parts you recently noticed (3×1). Recent Percept chips (◈, plum) drawn from the
// region annotations on your recent readings — each a jump back to that image's
// reading. The region-mark motif is the tile's signature.
export default function PerceptsTile() {
  const { data, isLoading } = useQuery({
    queryKey: ['home', 'percepts'],
    queryFn: () => fetchRecentPosts(24),
    staleTime: 5 * 60 * 1000,
  });

  // Flatten recent posts → their marked parts, newest first, deduped by label.
  const chips = [];
  const seen = new Set();
  for (const post of data ?? []) {
    for (const region of percepts(post)) {
      const label = perceptLabel(region);
      const key = label.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      chips.push({ label, postId: post.id, regionId: region.id });
      if (chips.length >= 12) break;
    }
    if (chips.length >= 12) break;
  }

  return (
    <section className="tile tile-percepts">
      <span className="eyebrow">Parts you recently noticed</span>
      {isLoading ? (
        <p className="tile-muted">Gathering the parts you marked…</p>
      ) : chips.length > 0 ? (
        <div className="percept-chips">
          {chips.map((c) => (
            <Link key={`${c.postId}:${c.regionId}`} to={`/posts/${c.postId}`} className="percept-chip">
              <span className="mark" aria-hidden>◈</span> {c.label}
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
