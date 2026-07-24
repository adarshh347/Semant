import { Glyph } from './Glyph';

// ── The seven Ground types ────────────────────────────────────────────────
// One bespoke plum mark for each of Semant's seven ways of grounding a part.
// This is the SINGLE SOURCE that retires the two divergent dialects the plan
// flagged: the unicode `GROUND_GLYPH` map ('◐↝∥▣◈⁘⤝', DifferentialWorkspace.jsx)
// AND the lucide `.diff-tools` rail — both name these same seven types in their
// own alphabet. Wiring the Field call-sites onto this set belongs to the
// session that owns the Field files; the set is built ready for them (see the
// GROUND_GLYPHS / TOOL_GLYPHS registries in ./index.js).
//
// Each mark is drawn in the SemantMark's own vocabulary — rounded rectangles
// (the frame/region), a stem line, small return-point dots, soft curves.

// region — a single durable "seen" patch, tilted like the mark's own region.
export function RegionGlyph(props) {
  return (
    <Glyph title="Region" {...props}>
      <rect x="6" y="7.2" width="12" height="9.6" rx="2.6" transform="rotate(-8 12 12)" fill="currentColor" stroke="none" />
    </Glyph>
  );
}

// region tick — the compact region mark used as the section-eyebrow tell: a tiny
// tilted plum lozenge set before every uppercase eyebrow/kicker so each section
// reads as *Semant* at a glance. Decorative by default (no forced title): it is
// a brand accent before a label the reader already sees, not new information.
export function RegionTick(props) {
  return (
    <Glyph className="region-tick" {...props}>
      <rect x="5.4" y="8.4" width="13.2" height="7.2" rx="2.2" transform="rotate(-8 12 12)" fill="currentColor" stroke="none" />
    </Glyph>
  );
}

// field — soft, diffuse light pooling on one side (the old ◐, in the family).
export function FieldGlyph(props) {
  return (
    <Glyph title="Field" {...props}>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 4 A8 8 0 0 0 12 20 Z" fill="currentColor" stroke="none" />
    </Glyph>
  );
}

// path — a directional line that flows and arrives (the old ↝).
export function PathGlyph(props) {
  return (
    <Glyph title="Path" {...props}>
      <circle cx="4.9" cy="15.4" r="1.35" fill="currentColor" stroke="none" />
      <path d="M5.2 15 C 9 9 13 9 18.4 10.2" />
      <path d="M15.4 8.3 L18.9 10 L16.3 12.9" />
    </Glyph>
  );
}

// boundary — an edge that divides two grounds (the old ∥), a strong seam.
export function BoundaryGlyph(props) {
  return (
    <Glyph title="Boundary" {...props}>
      <rect x="4" y="4" width="16" height="16" rx="4" />
      <line x1="12" y1="5" x2="12" y2="19" strokeWidth="2.4" />
    </Glyph>
  );
}

// frame — the whole image as evidence (the old ▣), nested.
export function FrameGlyph(props) {
  return (
    <Glyph title="Frame" {...props}>
      <rect x="3.6" y="3.6" width="16.8" height="16.8" rx="4.4" />
      <rect x="7.6" y="7.6" width="8.8" height="8.8" rx="2.4" />
    </Glyph>
  );
}

// constellation — several grounds gathered into one figure (the old ⁘).
export function ConstellationGlyph(props) {
  return (
    <Glyph title="Constellation" {...props}>
      <path d="M7 8 L16.4 6.8 L12 13.2 L7 8 Z" />
      <path d="M12 13.2 L9 17.4" />
      <circle cx="7" cy="8" r="1.5" fill="currentColor" stroke="none" />
      <circle cx="16.4" cy="6.8" r="1.5" fill="currentColor" stroke="none" />
      <circle cx="12" cy="13.2" r="1.5" fill="currentColor" stroke="none" />
      <circle cx="9" cy="17.4" r="1.5" fill="currentColor" stroke="none" />
    </Glyph>
  );
}

// relation — two grounds tied together (the old ⤝).
export function RelationGlyph(props) {
  return (
    <Glyph title="Relation" {...props}>
      <rect x="3.4" y="8.4" width="6.4" height="6.4" rx="2" />
      <rect x="14.2" y="8.4" width="6.4" height="6.4" rx="2" />
      <path d="M9.8 11.6 Q12 8.4 14.2 11.6" />
    </Glyph>
  );
}
