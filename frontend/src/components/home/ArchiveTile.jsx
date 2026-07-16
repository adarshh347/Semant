import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { cldCrop, cldLqip } from '../../lib/cloudinary';
import { fetchRecentPosts, fetchArchiveCount } from './homeData';

// The Archive (1×1). A live 3-image mosaic + "N images →" — the door to the full
// justified archive. A quiet three-cell crop (one tall, two stacked) rather than
// cramming the justified grid into a thumbnail; the real react-photo-album layout
// lives on the Gallery.
export default function ArchiveTile() {
  const { data: posts } = useQuery({
    queryKey: ['home', 'archive-mosaic'],
    queryFn: () => fetchRecentPosts(24),
    staleTime: 5 * 60 * 1000,
  });
  const { data: count } = useQuery({
    queryKey: ['home', 'archive-count'],
    queryFn: fetchArchiveCount,
    staleTime: 5 * 60 * 1000,
  });

  const mosaic = (posts ?? []).filter((p) => p.photo_url).slice(0, 3);
  const label = count != null ? `${count.toLocaleString()} images` : 'the archive';

  return (
    <Link to="/gallery" className="tile tile-archive" viewTransition>
      <span className="eyebrow">The Archive</span>
      <div className="archive-mosaic">
        {mosaic.map((p, i) => (
          <div
            key={p.id}
            className={`archive-cell${i === 0 ? ' archive-cell-lead' : ''}`}
            style={{ backgroundImage: `url("${cldLqip(p.photo_url)}")` }}
          >
            <img
              src={i === 0 ? cldCrop(p.photo_url, 360, 460) : cldCrop(p.photo_url, 240, 240)}
              alt=""
              loading="lazy"
              onLoad={(e) => e.currentTarget.classList.add('is-loaded')}
            />
          </div>
        ))}
      </div>
      <span className="tile-link archive-count">{label} →</span>
    </Link>
  );
}
