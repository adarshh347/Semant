// Shared Suspense fallback for lazy-loaded routes. Deliberately quiet — a
// centered plum spinner on the paper canvas — so route chunk loads don't flash
// heavy skeletons. Themed to v1.3 tokens.
import './RouteFallback.css';

export default function RouteFallback() {
  return (
    <div className="route-fallback" role="status" aria-live="polite">
      <span className="route-fallback-spinner" aria-hidden="true" />
      <span className="route-fallback-label">Loading…</span>
    </div>
  );
}
