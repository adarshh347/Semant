import './states.css';

// Branded loading skeletons — a calm plum-tinted shimmer over the shape the
// real content will take, so a wait reads as "arriving" rather than "spinner".
// The shimmer is decorative (it does NOT encode progress); under
// prefers-reduced-motion it freezes to a still tint (see states.css).

// A single shimmer block. Pass width/height/radius or a className.
export function Skeleton({ width, height = 16, radius = 6, className = '', style }) {
  return (
    <span
      className={`skel ${className}`.trim()}
      aria-hidden="true"
      style={{ width, height, borderRadius: radius, ...style }}
    />
  );
}

// A card skeleton for the Feed / Epics list shapes.
export function CardSkeleton() {
  return (
    <div className="skel-card" aria-hidden="true">
      <Skeleton height={148} radius={10} className="skel-card__media" />
      <Skeleton width="62%" height={18} />
      <Skeleton width="90%" height={12} />
      <Skeleton width="74%" height={12} />
    </div>
  );
}

// A grid of card skeletons — the initial load for a list surface.
export function CardGridSkeleton({ count = 6, label = 'Loading…' }) {
  return (
    <div className="skel-grid" role="status" aria-live="polite" aria-label={label}>
      {Array.from({ length: count }, (_, i) => <CardSkeleton key={i} />)}
    </div>
  );
}

// A stacked-row skeleton — the Feed / list-of-stories shape.
export function FeedSkeleton({ count = 4, label = 'Loading feed…' }) {
  return (
    <div className="skel-feed" role="status" aria-live="polite" aria-label={label}>
      {Array.from({ length: count }, (_, i) => (
        <div className="skel-row" key={i}>
          <Skeleton width={132} height={96} radius={10} className="skel-row__thumb" />
          <div className="skel-row__lines">
            <Skeleton width="54%" height={18} />
            <Skeleton width="92%" height={12} />
            <Skeleton width="80%" height={12} />
            <Skeleton width="40%" height={12} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default Skeleton;
