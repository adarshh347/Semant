import { Glyph } from './Glyph';

// ── Inspector glyphs (raw components) ────────────────────────────────────────
// The dense right-console (First Attention · Ways of looking · Sources ·
// Operation memory) speaks in tiny labels; this module gives the genuinely new
// concepts a mark in the SAME 24-grid vocabulary as the rest of the family. Most
// of the console REUSES existing marks (Find parts → Dissect, Brush light →
// Field, YOLO → Dissect, SAM → Refine, Operation memory → Recall, Suggest/auto →
// Percept); the lookups that wire those live in ./inspectorRegistry (kept
// component-free so this file stays fast-refresh clean). Nothing animates.

// map_gaze — mapping where the eye travels: an aperture with the gaze trailing off.
export function GazeGlyph(props) {
  return (
    <Glyph title="Map gaze" {...props}>
      <path d="M3.6 12 Q12 6.4 20.4 12 Q12 17.6 3.6 12 Z" />
      <circle cx="11" cy="12" r="1.9" fill="currentColor" stroke="none" />
      <circle cx="16.4" cy="8.4" r="0.9" fill="currentColor" stroke="none" />
      <circle cx="19" cy="6.4" r="0.7" fill="currentColor" stroke="none" />
    </Glyph>
  );
}

// start_note — beginning to write: a small leaf of prose with ruled lines.
export function NoteGlyph(props) {
  return (
    <Glyph title="Start note" {...props}>
      <rect x="6" y="4" width="12" height="16" rx="2.4" />
      <line x1="9" y1="9" x2="15" y2="9" />
      <line x1="9" y1="12" x2="15" y2="12" />
      <line x1="9" y1="15" x2="12.6" y2="15" />
    </Glyph>
  );
}

// counter_reading — asking for the reading against the reading: a chiasmatic
// cross of two lines whose ends swap sides (the Écart made a mark).
export function CounterGlyph(props) {
  return (
    <Glyph title="Ask for counter-reading" {...props}>
      <path d="M7 8 Q12 8 12 12 Q12 16 17 16" />
      <path d="M17 8 Q12 8 12 12 Q12 16 7 16" />
      <circle cx="7" cy="8" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="17" cy="16" r="1.4" fill="currentColor" stroke="none" />
    </Glyph>
  );
}

// general — ordinary looking: the plain open aperture, no specialist lens.
export function OrdinaryWayGlyph(props) {
  return (
    <Glyph title="Ordinary looking" {...props}>
      <circle cx="12" cy="12" r="7.2" />
      <circle cx="12" cy="12" r="2.1" fill="currentColor" stroke="none" />
    </Glyph>
  );
}

// fashion — fashion & body: a garment silhouette (shoulders into an A-line).
export function FashionWayGlyph(props) {
  return (
    <Glyph title="Fashion & body" {...props}>
      <path d="M9 5 L12 6.6 L15 5 L17.4 10.6 L15 11.6 L15.6 19 L8.4 19 L9 11.6 L6.6 10.6 Z"
        fill="currentColor" stroke="none" />
    </Glyph>
  );
}

// architecture — built space: an arch springing from two piers.
export function ArchitectureWayGlyph(props) {
  return (
    <Glyph title="Built space" {...props}>
      <path d="M5 19.5 L5 11 A7 7 0 0 1 19 11 L19 19.5" />
      <line x1="3.6" y1="19.5" x2="20.4" y2="19.5" />
    </Glyph>
  );
}

// painting — painting & surface: a brushstroke laid across a framed surface.
export function PaintingWayGlyph(props) {
  return (
    <Glyph title="Painting & surface" {...props}>
      <rect x="4" y="4" width="16" height="16" rx="3.2" />
      <path d="M7.4 15.2 Q11 8.8 16.6 12" strokeWidth="2.6" />
    </Glyph>
  );
}
