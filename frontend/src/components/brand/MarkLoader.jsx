import './brand.css';

// A branded loading state — the Ground mark drawing itself in a gentle loop,
// not a generic spinner. `prefers-reduced-motion` freezes it to a static mark
// (see brand.css). Use as the route Suspense fallback and any full-view wait.
export function MarkLoader({ size = 44, label = 'Loading…', fullscreen = true }) {
  return (
    <div className={`mark-loader ${fullscreen ? 'mark-loader--full' : ''}`.trim()} role="status" aria-live="polite">
      <svg
        viewBox="0 0 64 64"
        width={size}
        height={size}
        className="mark-loader__mark"
        aria-hidden="true"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <rect className="mark-loader__frame" x="3" y="3" width="52" height="52" rx="12" fill="none" stroke="currentColor" strokeWidth="3.4" />
        <rect className="mark-loader__region" x="14" y="20" width="26" height="22" rx="6" transform="rotate(-9 27 31)" fill="currentColor" />
        <line className="mark-loader__stem" x1="42" y1="42" x2="55" y2="55" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
        <circle className="mark-loader__point" cx="58" cy="58" r="4.4" fill="none" stroke="currentColor" strokeWidth="2.6" />
      </svg>
      <span className="mark-loader__label">{label}</span>
    </div>
  );
}

export default MarkLoader;
