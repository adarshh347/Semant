import { WAY_GLYPHS, ACT_GLYPHS, SOURCE_GLYPHS } from './inspectorRegistry';
import { OrdinaryWayGlyph } from './inspectorGlyphs';
import { FrameGlyph } from './groundGlyphs';
import { PerceptMark } from './actGlyphs';

// Convenience lookups — <WayGlyph way="fashion" />, <ActGlyph act="map_gaze" />,
// <SourceGlyph source="yolo11n_seg" />. Each falls back to a calm default rather
// than throwing on an unknown key. Mirrors ./GroundGlyph for the ground map.

export function WayGlyph({ way, ...props }) {
  const Mark = WAY_GLYPHS[way] || OrdinaryWayGlyph;
  return <Mark {...props} />;
}

export function ActGlyph({ act, ...props }) {
  const Mark = ACT_GLYPHS[act] || PerceptMark;
  return <Mark {...props} />;
}

export function SourceGlyph({ source, ...props }) {
  const Mark = SOURCE_GLYPHS[source] || FrameGlyph;
  return <Mark {...props} />;
}
