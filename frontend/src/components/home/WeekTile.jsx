import { useQuery } from '@tanstack/react-query';
import {
  fetchRecentPosts, perceptCount, wordCount, updatedWithin, isInProgress,
} from './homeData';

// This week (1×1) — the one dark tile, for contrast. Glanceable numbers:
// readings touched · words written · percepts marked, over the last 7 days.
// Derived from recent posts by `updated_at`; no stats endpoint needed.
export default function WeekTile() {
  const { data, isLoading } = useQuery({
    queryKey: ['home', 'week'],
    queryFn: () => fetchRecentPosts(50),
    staleTime: 5 * 60 * 1000,
  });

  const recent = (data ?? []).filter((p) => updatedWithin(p, 7));
  // "readings" = images you actually began reading this week (marked a part or
  // wrote), not every frame that happened to be ingested — so the three numbers
  // stay honest and consistent with each other.
  const readings = recent.filter(isInProgress).length;
  const words = recent.reduce((sum, p) => sum + wordCount(p), 0);
  const marks = recent.reduce((sum, p) => sum + perceptCount(p), 0);

  const stats = [
    { n: readings, label: readings === 1 ? 'reading' : 'readings' },
    { n: words, label: words === 1 ? 'word' : 'words' },
    { n: marks, label: marks === 1 ? 'percept' : 'percepts' },
  ];

  return (
    <section className="tile tile-week">
      <span className="eyebrow tile-week-eyebrow">This week</span>
      {isLoading ? (
        <p className="tile-muted tile-week-muted">Counting…</p>
      ) : (
        <dl className="week-stats">
          {stats.map((s) => (
            <div key={s.label} className="week-stat">
              <dt className="week-num">{s.n.toLocaleString()}</dt>
              <dd className="week-label">{s.label}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
