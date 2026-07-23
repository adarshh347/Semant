import {
  RegionGlyph, FieldGlyph, PathGlyph, BoundaryGlyph,
  FrameGlyph, ConstellationGlyph, RelationGlyph,
} from './groundGlyphs';
import { ReadingGlyph, DissectGlyph, RefineGlyph } from './actGlyphs';

// ── The unification registries ─────────────────────────────────────────────
// (kept in a component-free module so the glyph barrel stays fast-refresh clean)

// GROUND_GLYPHS is keyed EXACTLY like the unicode `GROUND_GLYPH` map in
// differential/DifferentialWorkspace.jsx and the duplicate in
// components/RefPicker.jsx, so the Field session can swap a one-liner:
//     {GROUND_GLYPH[g.ground_type] || '◇'}
//  →  <GroundGlyph type={g.ground_type} size={16} />
// One source, no third dialect.
export const GROUND_GLYPHS = {
  region: RegionGlyph,
  field: FieldGlyph,
  path: PathGlyph,
  boundary: BoundaryGlyph,
  frame: FrameGlyph,
  constellation: ConstellationGlyph,
  relation: RelationGlyph,
};

// TOOL_GLYPHS maps the lucide `.diff-tools` rail keys (DifferentialWorkspace.jsx
// TOOLS) onto the same marks, so the rail and the ground-type map finally speak
// one alphabet. `select` and `similar` stay on their lucide icons (they are
// shell/navigation actions, not Ground types).
export const TOOL_GLYPHS = {
  brush: FieldGlyph,      // Soft Field
  trace: PathGlyph,       // Path / Boundary — a drawn line
  collect: ConstellationGlyph,
  connect: RelationGlyph,
  frame: FrameGlyph,
  refine: RefineGlyph,
  read: ReadingGlyph,
  dissect: DissectGlyph,
};
