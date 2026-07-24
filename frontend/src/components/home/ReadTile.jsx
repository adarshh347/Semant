import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { cldCrop, cldLqip } from '../../lib/cloudinary';
import { fetchRecentPosts } from './homeData';
import { PerceptMark } from '../brand/glyphs';
import { SectionEyebrow } from '../brand/SectionEyebrow';

// Read (1×1). One Aletheia hook — an image with the reading's opening move and a
// perceptual fork — a door into the felt reading at /read/:postId. Deterministic
// pick (a recent image) so it doesn't churn between renders.
export default function ReadTile() {
  const { data, isLoading } = useQuery({
    queryKey: ['home', 'read'],
    queryFn: () => fetchRecentPosts(24),
    staleTime: 5 * 60 * 1000,
  });

  const withPhoto = (data ?? []).filter((p) => p.photo_url);
  // Second recent image so it differs from the Archive lead / Continue head.
  const post = withPhoto[1] || withPhoto[0];

  return (
    <section className="tile tile-read">
      <SectionEyebrow className="eyebrow">Read</SectionEyebrow>
      {isLoading || !post ? (
        <p className="tile-muted">Finding an image to read…</p>
      ) : (
        <Link to={`/read/${post.id}`} className="read-hook" viewTransition>
          <div
            className="read-stage"
            style={{ backgroundImage: `url("${cldLqip(post.photo_url)}")` }}
          >
            <img
              src={cldCrop(post.photo_url, 560, 360)}
              alt="An image waiting to be read"
              loading="lazy"
              onLoad={(e) => e.currentTarget.classList.add('is-loaded')}
            />
          </div>
          <p className="read-fork">
            <span className="mark" aria-hidden><PerceptMark size="1em" className="glyph--inline" /></span> What do you notice first?
          </p>
          <span className="tile-link">Read this deeper →</span>
        </Link>
      )}
    </section>
  );
}
