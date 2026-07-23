import { GROUND_GLYPHS } from './registry';
import { FrameGlyph } from './groundGlyphs';

// Convenience: <GroundGlyph type="region" size={18} />. Looks the mark up in the
// unified GROUND_GLYPHS registry and falls back to the frame mark for an unknown
// type rather than throwing. The one call the Field session will use to retire
// the unicode GROUND_GLYPH map.
export function GroundGlyph({ type, ...props }) {
  const Mark = GROUND_GLYPHS[type] || FrameGlyph;
  return <Mark {...props} />;
}

export default GroundGlyph;
