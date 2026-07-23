import './brand.css';

// "The Ground" — the one Semant glyph. A perceptual world (the frame) holding a
// durable region and a return point. Drawn in `currentColor` so it inherits the
// surrounding ink/plum and flips with the theme automatically; pass `color` to
// pin it (e.g. the plum accent) where context shouldn't drive it.
export function SemantMark({ size = 28, color = 'currentColor', title = 'Semant', className = '', ...rest }) {
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={`semant-mark ${className}`.trim()}
      role="img"
      aria-label={title}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...rest}
    >
      <rect x="3" y="3" width="52" height="52" rx="12" fill="none" stroke={color} strokeWidth="3.4" />
      <rect x="14" y="20" width="26" height="22" rx="6" transform="rotate(-9 27 31)" fill={color} />
      <line x1="42" y1="42" x2="55" y2="55" stroke={color} strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="58" cy="58" r="4.4" fill="none" stroke={color} strokeWidth="2.6" />
    </svg>
  );
}

// The nav lockup: the mark + the "Semant" Fraunces wordmark. Used site-wide as
// the logo. The mark rides on `currentColor`, so on a dark surface it reverses
// with the wordmark — no separate reversed asset needed in the shell.
export function SemantLogo({ size = 24, wordmark = true, className = '', ...rest }) {
  return (
    <span className={`semant-logo ${className}`.trim()} {...rest}>
      <SemantMark size={size} className="semant-logo__mark" title="Semant" aria-hidden={wordmark ? 'true' : undefined} />
      {wordmark && <span className="semant-logo__word">Semant</span>}
    </span>
  );
}

export default SemantMark;
