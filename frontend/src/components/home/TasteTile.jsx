import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { API_URL } from '../../config/api';
import { tasteHeaders } from '../../lib/tasteSession';
import { PerceptMark } from '../brand/glyphs';

// Your taste · Anuraṇana (2×1). "Your eye leans toward…" + motif chips, read from
// the taste portfolio (thresholded — one tap is noise). Anonymous until you've
// read enough to form a lean, so it degrades to an honest invitation.
async function fetchPortfolio() {
  const res = await fetch(`${API_URL}/api/v1/taste/portfolio`, { headers: tasteHeaders() });
  if (!res.ok) throw new Error('portfolio unavailable');
  return res.json();
}

export default function TasteTile() {
  const { data, isLoading } = useQuery({
    queryKey: ['home', 'taste'],
    queryFn: fetchPortfolio,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const leans = data?.leans ?? {};
  // Parts first (the most legible lean), then attributes — the motif chips.
  const chips = [
    ...(leans.parts ?? []),
    ...(leans.attributes ?? []),
  ].slice(0, 6);

  return (
    <section className="tile tile-taste">
      <span className="eyebrow">Your taste · Anuraṇana</span>
      {isLoading ? (
        <p className="tile-muted">Reading your eye…</p>
      ) : chips.length > 0 ? (
        <>
          <h2 className="tile-title tile-taste-lede">Your eye leans toward</h2>
          <div className="tile-taste-chips">
            {chips.map((c) => (
              <span key={`${c.name}`} className="taste-chip">
                <span className="mark" aria-hidden><PerceptMark size="1em" className="glyph--inline" /></span> {c.name}
              </span>
            ))}
          </div>
          <Link to="/you" className="tile-link tile-taste-more">See your taste portrait →</Link>
        </>
      ) : (
        <>
          <h2 className="tile-title tile-taste-lede">Your eye, written down</h2>
          <p className="tile-muted">
            Read a few images and the parts you keep noticing gather here —
            your taste, shown back to you.
          </p>
          <Link to="/feed" className="tile-link tile-taste-more">Start reading →</Link>
        </>
      )}
    </section>
  );
}
