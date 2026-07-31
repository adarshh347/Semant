import { RegionTick } from './glyphs';
import './section.css';

// ── The global tell ─────────────────────────────────────────────────────────
// One region-mark tick before every uppercase eyebrow / kicker / section-head,
// so home tiles, the reading hook, the 404 and every page head all read as
// *Semant* at a glance. Aesthetic only: the label text is unchanged and the tick
// is decorative (aria-hidden), so nothing new is announced to assistive tech.
//
// It PASSES THROUGH the call-site's existing eyebrow class (`eyebrow`,
// `hook-kicker`, `sk-eyebrow`, `placeholder-eyebrow`, …), so each spot keeps its
// own colour, size and tracking — the component only prepends the mark. The tick
// pins to the plum accent (`--accent`, which flips in dark) rather than riding
// the label colour, so the tell stays plum even where a kicker is muted.
export function SectionEyebrow({ className = '', tickSize = 11, children, ...rest }) {
  return (
    <span className={`section-eyebrow ${className}`.trim()} {...rest}>
      <RegionTick size={tickSize} className="section-eyebrow__tick" />
      {children}
    </span>
  );
}

// ── The section divider ──────────────────────────────────────────────────────
// A hairline with a centered region-mark — the chrome-level companion to the
// eyebrow tick (nav menus, section breaks). Purely presentational.
export function SectionDivider({ className = '', markSize = 12, ...rest }) {
  return (
    <div className={`section-divider ${className}`.trim()} role="presentation" {...rest}>
      <span className="section-divider__line" />
      <RegionTick size={markSize} className="section-divider__mark" />
      <span className="section-divider__line" />
    </div>
  );
}

export default SectionEyebrow;
