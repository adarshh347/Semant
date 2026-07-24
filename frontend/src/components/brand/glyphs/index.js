// The Semant concept-glyph family — one unified SVG set for the domain
// vocabulary. See ./Glyph.jsx for the shared grid, and the plan
// (vault/Concepts/Frontend Analysis/The graphic system — a layered plan.md, L2).
//
// Pure re-export barrel — components in ./groundGlyphs · ./actGlyphs ·
// ./GroundGlyph, the divergence-retiring registries in ./registry.

export { Glyph } from './Glyph';
export {
  RegionGlyph, RegionTick, FieldGlyph, PathGlyph, BoundaryGlyph,
  FrameGlyph, ConstellationGlyph, RelationGlyph,
} from './groundGlyphs';
export {
  PerceptMark, MentionGlyph, ReadingGlyph, RecallGlyph, DissectGlyph, RefineGlyph,
} from './actGlyphs';
export { GroundGlyph } from './GroundGlyph';
export { GROUND_GLYPHS, TOOL_GLYPHS } from './registry';
export {
  GazeGlyph, NoteGlyph, CounterGlyph,
  OrdinaryWayGlyph, FashionWayGlyph, ArchitectureWayGlyph, PaintingWayGlyph,
} from './inspectorGlyphs';
export { WAY_GLYPHS, ACT_GLYPHS, SOURCE_GLYPHS } from './inspectorRegistry';
export { WayGlyph, ActGlyph, SourceGlyph } from './InspectorGlyph';
// Operation memory is a returned recording (the Recall arc); "Let it choose" and
// "Suggest acts" both mean *Semant proposes* (the Percept mark). Reused, aliased.
export { RecallGlyph as OperationMemoryGlyph, PerceptMark as SuggestGlyph } from './actGlyphs';
