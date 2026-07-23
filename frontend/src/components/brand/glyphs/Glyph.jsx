import './glyphs.css';

// The base of the Semant glyph family. EVERY concept glyph — the seven Ground
// types, Percept, Mention, Reading, Recall, Dissect, Refine — is drawn on this
// one 24-unit grid, at one stroke weight, with round caps/joins and a shared
// corner-radius family. That is what makes them read as ONE set rather than
// thirteen unrelated icons, and it echoes the SemantMark's own geometry
// (rounded frame · filled region · return point).
//
// Everything rides on `currentColor`, so a glyph inherits the surrounding
// ink/plum and flips with the theme automatically. Pass `color` (e.g. the plum
// accent) to pin it where context shouldn't drive it. A `title` makes the glyph
// an announced image; without one it is decorative (`aria-hidden`).
export function Glyph({
  size = 20,
  color = 'currentColor',
  title,
  className = '',
  strokeWidth = 1.7,
  children,
  style,
  ...rest
}) {
  const labelled = title ? { role: 'img', 'aria-label': title } : { 'aria-hidden': 'true' };
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={`glyph ${className}`.trim()}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={color !== 'currentColor' ? { color, ...style } : style}
      xmlns="http://www.w3.org/2000/svg"
      {...labelled}
      {...rest}
    >
      {children}
    </svg>
  );
}

export default Glyph;
