import { Glyph } from './Glyph';

// ── Percept + the acts ────────────────────────────────────────────────────
// The Percept mark (retiring the literal ◈ scattered site-wide) and the five
// acts of the circulation — Mention, Reading, Recall, Dissect, Refine — drawn
// in the same 24-grid vocabulary as the Ground types so the whole set reads as
// one family. None of these animate: the live/animated versions (recall replay,
// perceptual scan, stage-pulse) are Field-owned and gate on REAL runtime state
// (Invariant 9). These are the calm, static concept marks.

// PerceptMark — the durable part seen: a rounded diamond holding a filled core.
// This replaces the bare `◈` character across the shell (Archive, Home tiles).
export function PerceptMark({ className = '', ...props }) {
  return (
    <Glyph title="Percept" className={`${className}`.trim()} {...props}>
      <rect x="6.2" y="6.2" width="11.6" height="11.6" rx="3" transform="rotate(45 12 12)" />
      <rect x="9.6" y="9.6" width="4.8" height="4.8" rx="1.4" transform="rotate(45 12 12)" fill="currentColor" stroke="none" />
    </Glyph>
  );
}

// Mention — a reference to a percept inside prose: brackets embracing the part.
export function MentionGlyph(props) {
  return (
    <Glyph title="Mention" {...props}>
      <path d="M9 6 Q6 6 6 9 L6 15 Q6 18 9 18" />
      <path d="M15 6 Q18 6 18 9 L18 15 Q18 18 15 18" />
      <circle cx="12" cy="12" r="2" fill="currentColor" stroke="none" />
    </Glyph>
  );
}

// Reading — the model interpreting a part: an aperture focused on a percept.
export function ReadingGlyph(props) {
  return (
    <Glyph title="Reading" {...props}>
      <path d="M3.4 12 Q12 5 20.6 12 Q12 19 3.4 12 Z" />
      <rect x="9.9" y="9.9" width="4.2" height="4.2" rx="1" transform="rotate(45 12 12)" fill="currentColor" stroke="none" />
    </Glyph>
  );
}

// Recall — the return point coming back: a return arc around the part. Static —
// the *animated* replay lives in the Field's GroundLayers and runs only on real
// progress; this is the calm mark for it.
export function RecallGlyph(props) {
  return (
    <Glyph title="Recall" {...props}>
      <path d="M18.8 8.8 A7.4 7.4 0 1 0 19.7 13.2" />
      <path d="M15.7 7.7 L18.9 8.5 L18.2 11.6" />
      <circle cx="12" cy="12" r="1.55" fill="currentColor" stroke="none" />
    </Glyph>
  );
}

// Dissect — the perceptual scan resolving parts: a reticle over the frame.
export function DissectGlyph(props) {
  return (
    <Glyph title="Dissect" {...props}>
      <path d="M5 8.5 L5 5.6 Q5 5 5.6 5 L8.5 5" />
      <path d="M15.5 5 L18.4 5 Q19 5 19 5.6 L19 8.5" />
      <path d="M5 15.5 L5 18.4 Q5 19 5.6 19 L8.5 19" />
      <path d="M15.5 19 L18.4 19 Q19 19 19 18.4 L19 15.5" />
      <line x1="6.6" y1="12" x2="17.4" y2="12" />
      <circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none" />
    </Glyph>
  );
}

// Refine — tightening a mask by its anchors: a region with editable handles.
export function RefineGlyph(props) {
  return (
    <Glyph title="Refine" {...props}>
      <rect x="5.6" y="6" width="12.8" height="12" rx="3" />
      <rect x="3.7" y="4.1" width="3.2" height="3.2" rx="0.7" fill="currentColor" stroke="none" />
      <rect x="17.1" y="4.1" width="3.2" height="3.2" rx="0.7" fill="currentColor" stroke="none" />
      <rect x="10.4" y="16.7" width="3.2" height="3.2" rx="0.7" fill="currentColor" stroke="none" />
    </Glyph>
  );
}
