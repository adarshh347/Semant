import {
  GazeGlyph, NoteGlyph, CounterGlyph,
  OrdinaryWayGlyph, FashionWayGlyph, ArchitectureWayGlyph, PaintingWayGlyph,
} from './inspectorGlyphs';
import { FieldGlyph } from './groundGlyphs';
import { DissectGlyph, RefineGlyph } from './actGlyphs';

// ── Inspector lookups ────────────────────────────────────────────────────────
// (component-free module, so the glyph files stay fast-refresh clean — same
// discipline as ./registry for the ground/tool maps)

// Ways of looking → domain glyph (SeeingConsole `data-way` keys).
export const WAY_GLYPHS = {
  general: OrdinaryWayGlyph,
  fashion: FashionWayGlyph,
  architecture: ArchitectureWayGlyph,
  painting: PaintingWayGlyph,
};

// First-Attention quick acts → glyph (attunementPlanner QUICK_CHIPS keys).
// Brush light IS the soft Field; Find parts IS the Dissect scan — reused, not
// redrawn, so the console shares one alphabet with the tool rail.
export const ACT_GLYPHS = {
  map_gaze: GazeGlyph,
  brush_light: FieldGlyph,
  find_parts: DissectGlyph,
  start_note: NoteGlyph,
  counter_reading: CounterGlyph,
};

// Source models → instrument glyph. The vision passes reuse the act marks that
// name what they DO: YOLO segments (Dissect), SAM refines a mask (Refine),
// SegFormer pools a soft field (Field).
export const SOURCE_GLYPHS = {
  yolo11n_seg: DissectGlyph,
  segformer_b0_ade: FieldGlyph,
  sam21_hiera_tiny: RefineGlyph,
};
